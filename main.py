#!/usr/bin/env python3
"""
Google Drive Statement Organizer

This application organizes financial statements from a "Monthly Statements" folder
into a structured "Statements by Account" folder based on company names and statement types.
"""

import os
import re
import json
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import tempfile
import concurrent.futures
import threading
from functools import partial
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn, TimeElapsedColumn
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

import PyPDF2
import io

from file_mapping import FileMapping

class ProcessedFilesTracker:
    """Track files that have already been processed to avoid duplicates."""
    
    def __init__(self, cache_file: str = 'processed_files.json'):
        self.cache_file = cache_file
        self.processed_files = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load processed files cache from disk."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def _save_cache(self):
        """Save processed files cache to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.processed_files, f, indent=2)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save processed files cache: {e}[/yellow]")
    
    def is_processed(self, file_id: str, file_name: str, target_folder_id: str) -> bool:
        """Check if a file has already been processed."""
        key = f"{file_id}:{target_folder_id}"
        return key in self.processed_files
    
    def mark_processed(self, file_id: str, file_name: str, target_folder_id: str, target_folder_name: str):
        """Mark a file as processed."""
        key = f"{file_id}:{target_folder_id}"
        self.processed_files[key] = {
            'file_name': file_name,
            'target_folder_name': target_folder_name,
            'processed_at': datetime.now().isoformat()
        }
        self._save_cache()
    
    def get_stats(self) -> Dict:
        """Get statistics about processed files."""
        return {
            'total_processed': len(self.processed_files),
            'cache_file': self.cache_file
        }

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Drive API scopes
SCOPES = ['https://www.googleapis.com/auth/drive']

# Initialize Rich console
console = Console()


class GoogleDriveOrganizer:
    """Main class for organizing Google Drive statements."""
    
    def __init__(self, credentials_file: str = 'credentials.json', token_file: str = 'token.json', workers: int = 4):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self.creds = None  # Store credentials for thread-local services
        self.file_mapping = FileMapping()
        self.processed_tracker = ProcessedFilesTracker()
        self.workers = workers
        # Caches to reduce API calls
        self._dest_folders_cache = None  # Pre-fetched destination folders
        self._folder_info_cache = {}  # folder_id -> folder_info
        self._dest_folder_id = None  # Destination folder ID for reuse
        # Thread-local storage for per-thread API services
        self._thread_local = threading.local()
        self._cache_lock = threading.Lock()
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Google Drive API."""
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    console.print(f"[red]Error: {self.credentials_file} not found. Please download your OAuth credentials from Google Cloud Console.[/red]")
                    raise FileNotFoundError(f"Credentials file {self.credentials_file} not found")
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.creds = creds  # Store for creating thread-local services
        self.service = build('drive', 'v3', credentials=creds)
        console.print("[green]✓ Successfully authenticated with Google Drive[/green]")
    
    def get_thread_service(self):
        """Get a thread-local Google Drive service instance.
        
        Each thread needs its own service instance to avoid SSL/connection issues.
        """
        if not hasattr(self._thread_local, 'service') or self._thread_local.service is None:
            # Create a new service instance for this thread
            self._thread_local.service = build('drive', 'v3', credentials=self.creds)
        return self._thread_local.service
    
    def prefetch_destination_folders(self, dest_folder_id: str) -> List[Dict]:
        """Pre-fetch all destination folders once to avoid repeated API calls."""
        if self._dest_folders_cache is not None and self._dest_folder_id == dest_folder_id:
            return self._dest_folders_cache
        
        try:
            console.print("[dim]Pre-fetching destination folders...[/dim]")
            results = self.service.files().list(
                q=f"'{dest_folder_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            self._dest_folders_cache = results.get('files', [])
            self._dest_folder_id = dest_folder_id
            
            # Pre-populate folder info cache
            for folder in self._dest_folders_cache:
                self._folder_info_cache[folder['id']] = folder
            
            console.print(f"[dim]Cached {len(self._dest_folders_cache)} destination folders[/dim]")
            return self._dest_folders_cache
        except HttpError as error:
            console.print(f"[yellow]Warning: Could not prefetch folders: {error}[/yellow]")
            return []
    
    def get_cached_folder_info(self, folder_id: str) -> Optional[Dict]:
        """Get folder info from cache or fetch if not cached. Thread-safe."""
        with self._cache_lock:
            if folder_id in self._folder_info_cache:
                return self._folder_info_cache[folder_id]
        
        try:
            folder_info = self.service.files().get(fileId=folder_id, fields='id,name').execute()
            with self._cache_lock:
                self._folder_info_cache[folder_id] = folder_info
            return folder_info
        except:
            return None
    
    def find_folder_by_name(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """Find a folder by name and optionally parent folder ID."""
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        try:
            results = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
            files = results.get('files', [])
            
            if files:
                return files[0]['id']
            else:
                console.print(f"[yellow]Warning: Folder '{folder_name}' not found[/yellow]")
                return None
        except HttpError as error:
            console.print(f"[red]Error finding folder '{folder_name}': {error}[/red]")
            return None
    
    def get_files_in_folder(self, folder_id: str, recursive: bool = True) -> List[Dict]:
        """Get all files in a folder, optionally searching recursively through subfolders."""
        all_files = []
        
        try:
            # Get immediate children of the folder
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id, name, mimeType, size)'
            ).execute()
            items = results.get('files', [])
            
            for item in items:
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    # It's a folder, recursively search it if recursive=True
                    if recursive:
                        subfolder_files = self.get_files_in_folder(item['id'], recursive=True)
                        all_files.extend(subfolder_files)
                else:
                    # It's a file, add it to our list
                    all_files.append(item)
            
            return all_files
        except HttpError as error:
            console.print(f"[red]Error getting files from folder: {error}[/red]")
            return []
    
    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """Create a folder in Google Drive."""
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_id:
            file_metadata['parents'] = [parent_id]
        
        try:
            folder = self.service.files().create(body=file_metadata, fields='id').execute()
            console.print(f"[green]✓ Created folder: {folder_name}[/green]")
            return folder.get('id')
        except HttpError as error:
            console.print(f"[red]Error creating folder '{folder_name}': {error}[/red]")
            return None
    
    def download_file(self, file_id: str) -> Optional[bytes]:
        """Download a file from Google Drive."""
        try:
            request = self.service.files().get_media(fileId=file_id)
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            return file.getvalue()
        except HttpError as error:
            console.print(f"[red]Error downloading file: {error}[/red]")
            return None
    
    def rename_folder(self, folder_id: str, new_name: str) -> bool:
        """Rename a Google Drive folder."""
        try:
            # Update the folder name
            file_metadata = {'name': new_name}
            updated_folder = self.service.files().update(
                fileId=folder_id,
                body=file_metadata
            ).execute()
            
            console.print(f"[green]✓ Renamed folder to: {new_name}[/green]")
            return True
            
        except HttpError as error:
            console.print(f"[red]Error renaming folder: {error}[/red]")
            return False

    def get_folder_info(self, folder_id: str) -> Optional[dict]:
        """Get folder information including current name."""
        try:
            folder = self.service.files().get(
                fileId=folder_id,
                fields='id,name,parents'
            ).execute()
            return folder
        except HttpError as error:
            console.print(f"[red]Error getting folder info: {error}[/red]")
            return None

    def find_folder_by_exact_name(self, folder_name: str, parent_folder_id: str = None) -> Optional[str]:
        """Find a folder by exact name match in a specific parent folder."""
        try:
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            if parent_folder_id:
                query += f" and '{parent_folder_id}' in parents"
            
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            folders = results.get('files', [])
            if folders:
                return folders[0]['id']
            return None
            
        except HttpError as error:
            console.print(f"[red]Error finding folder: {error}[/red]")
            return None

    def batch_rename_folders(self, rename_mapping: dict, dry_run: bool = True) -> dict:
        """Batch rename multiple folders with progress tracking."""
        results = {
            'success': [],
            'failed': [],
            'skipped': []
        }
        
        console.print(f"\n[bold blue]{'DRY RUN: ' if dry_run else ''}Batch Renaming {len(rename_mapping)} Folders[/bold blue]")
        
        # Find destination folder
        dest_folder_id = self.find_folder_by_name('Statements by Account')
        if not dest_folder_id:
            console.print("[red]Error: Could not find 'Statements by Account' folder[/red]")
            return results
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        ) as progress:
            
            task = progress.add_task("Renaming folders...", total=len(rename_mapping))
            
            for old_name, new_name in rename_mapping.items():
                progress.update(task, description=f"Processing: {old_name[:30]}...")
                
                try:
                    # Find the folder by old name
                    folder_id = self.find_folder_by_exact_name(old_name, dest_folder_id)
                    
                    if not folder_id:
                        console.print(f"[yellow]⚠️  Folder not found: {old_name}[/yellow]")
                        results['skipped'].append(old_name)
                        progress.advance(task)
                        continue
                    
                    # Get current folder info
                    folder_info = self.get_folder_info(folder_id)
                    if not folder_info:
                        results['failed'].append(old_name)
                        progress.advance(task)
                        continue
                    
                    current_name = folder_info['name']
                    
                    if current_name == new_name:
                        console.print(f"[dim]Already correct: {new_name}[/dim]")
                        results['skipped'].append(old_name)
                        progress.advance(task)
                        continue
                    
                    if dry_run:
                        console.print(f"[cyan]Would rename: '{current_name}' → '{new_name}'[/cyan]")
                        results['success'].append(old_name)
                    else:
                        # Actually rename the folder
                        if self.rename_folder(folder_id, new_name):
                            results['success'].append(old_name)
                        else:
                            results['failed'].append(old_name)
                    
                except Exception as e:
                    console.print(f"[red]Error processing {old_name}: {e}[/red]")
                    results['failed'].append(old_name)
                
                progress.advance(task)
        
        return results

    def backup_folder_structure(self, parent_folder_id: str) -> dict:
        """Create a backup of the current folder structure."""
        try:
            console.print("[blue]Creating backup of folder structure...[/blue]")
            
            results = self.service.files().list(
                q=f"'{parent_folder_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'",
                spaces='drive',
                fields='files(id, name, parents, createdTime, modifiedTime)'
            ).execute()
            
            folders = results.get('files', [])
            
            from datetime import datetime
            backup_data = {
                'backup_date': datetime.now().isoformat(),
                'parent_folder_id': parent_folder_id,
                'total_folders': len(folders),
                'folders': folders
            }
            
            # Save backup to local file
            backup_filename = f"folder_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_filename, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            console.print(f"[green]✓ Backup saved to: {backup_filename}[/green]")
            return backup_data
            
        except HttpError as error:
            console.print(f"[red]Error creating backup: {error}[/red]")
            return {}

    def copy_file(self, file_id: str, destination_folder_id: str, new_name: Optional[str] = None, check_duplicates: bool = True) -> bool:
        """Copy a file to a new location in Google Drive with duplicate detection."""
        try:
            # Get file metadata
            file_metadata = self.service.files().get(fileId=file_id).execute()
            original_name = file_metadata['name']
            
            # Check for duplicates if requested
            if check_duplicates:
                duplicates = self.check_for_duplicates(file_id, destination_folder_id, original_name)
                
                if duplicates['recommended_action'] == 'skip':
                    console.print(f"[yellow]⏭️  Skipped: {original_name} - {duplicates['reason']}[/yellow]")
                    return True  # Return True since this is expected behavior
                
                elif duplicates['recommended_action'] == 'rename':
                    if not new_name:  # Only auto-rename if no custom name provided
                        new_name = self.generate_unique_filename(original_name, destination_folder_id)
                        console.print(f"[blue]🔄 Renaming duplicate: {original_name} → {new_name}[/blue]")
                    else:
                        console.print(f"[blue]🔄 Using custom name for duplicate: {original_name} → {new_name}[/blue]")
                
                elif duplicates['recommended_action'] == 'copy':
                    if duplicates['exact_filename'] or duplicates['content_duplicate']:
                        console.print(f"[blue]ℹ️  Info: {original_name} - {duplicates['reason']}[/blue]")
            
            # Prepare copy metadata
            copy_metadata = {
                'name': new_name or original_name,
                'parents': [destination_folder_id]
            }
            
            # Copy the file
            copied_file = self.service.files().copy(
                fileId=file_id,
                body=copy_metadata
            ).execute()
            
            console.print(f"[green]✓ Copied: {copy_metadata['name']}[/green]")
            return True
        except HttpError as error:
            console.print(f"[red]Error copying file: {error}[/red]")
            return False
    
    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extract text content from PDF bytes."""
        try:
            pdf_file = io.BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return text
        except Exception as e:
            console.print(f"[yellow]Warning: Could not extract text from PDF: {e}[/yellow]")
            return ""
    
    def classify_file(self, file_name: str, file_content: Optional[bytes] = None, file_id: str = None, file_size: str = None, skip_download_on_cache: bool = True) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Classify a file based on filename and optionally content. Returns (company, statement_type, account_info).
        
        Args:
            skip_download_on_cache: If True and classification is cached, returns immediately without needing file_content.
        """
        
        # Check cache first if we have file ID
        if file_id:
            cached_result = self.file_mapping.get_classification(file_id, file_name, file_size)
            if cached_result:
                # If all fields are present or we're skipping download, return cached result
                company, stmt_type, acct_info = cached_result
                if skip_download_on_cache or (company and stmt_type):
                    console.print(f"[dim]Using cached result for {file_name}[/dim]")
                    return cached_result
        
        company = None
        statement_type = None
        account_info = None
        
        # Import patterns from config
        from config import COMPANY_PATTERNS, STATEMENT_PATTERNS
        
        # Analyze filename
        file_lower = file_name.lower()
        
        # Find company
        for company_name, patterns in COMPANY_PATTERNS.items():
            if any(pattern in file_lower for pattern in patterns):
                company = company_name
                break
        
        # Find statement type
        for stmt_type, patterns in STATEMENT_PATTERNS.items():
            if any(pattern in file_lower for pattern in patterns):
                statement_type = stmt_type
                break
        
        # Extract account information
        account_info = self.extract_account_info(file_name, file_content)
        
        # If filename analysis didn't work, try PDF content
        if (not company or not statement_type) and file_content:
            pdf_text = self.extract_text_from_pdf(file_content)
            pdf_lower = pdf_text.lower()
            
            # Find company in PDF content
            if not company:
                for company_name, patterns in COMPANY_PATTERNS.items():
                    if any(pattern in pdf_lower for pattern in patterns):
                        company = company_name
                        break
            
            # Find statement type in PDF content
            if not statement_type:
                for stmt_type, patterns in STATEMENT_PATTERNS.items():
                    if any(pattern in pdf_lower for pattern in patterns):
                        statement_type = stmt_type
                        break
            
            # Extract account info from PDF content if not found in filename
            if not account_info:
                account_info = self.extract_account_info_from_text(pdf_text)
        
        # Cache the result if we have file ID
        if file_id:
            self.file_mapping.set_classification(file_id, file_name, company, statement_type, account_info, file_size)
        
        return company, statement_type, account_info
    
    def extract_account_info(self, file_name: str, file_content: Optional[bytes] = None) -> Optional[str]:
        """Extract account information from filename or content."""
        import re
        
        # Common account patterns
        account_patterns = [
            r'account[:\s_]*([A-Z0-9\-]+)',  # Account: 1234-5678 or account_1234-5678
            r'#([A-Z0-9\-]+)',              # #1234-5678
            r'ending[:\s]*([0-9]{4})',      # ending 1234
            r'last[:\s]*([0-9]{4})',        # last 1234
            r'([0-9]{4}[-*][0-9]{4}[-*][0-9]{4}[-*][0-9]{4})',  # Credit card format
            r'checking[:\s]*([A-Z0-9\-]+)', # Checking: 1234-5678
            r'savings[:\s]*([A-Z0-9\-]+)',  # Savings: 1234-5678
            r'brokerage[:\s]*([A-Z0-9\-]+)', # Brokerage: 1234-5678
        ]
        
        # Check filename first
        for pattern in account_patterns:
            match = re.search(pattern, file_name, re.IGNORECASE)
            if match:
                return match.group(1) if match.groups() else match.group(0)
        
        # Check PDF content if available
        if file_content:
            pdf_text = self.extract_text_from_pdf(file_content)
            for pattern in account_patterns:
                match = re.search(pattern, pdf_text, re.IGNORECASE)
                if match:
                    return match.group(1) if match.groups() else match.group(0)
        
        return None
    
    def extract_account_info_from_text(self, text: str) -> Optional[str]:
        """Extract account information from text content."""
        import re
        
        # Enhanced account number patterns - DIGITS ONLY
        account_patterns = [
            # Full account numbers with clear delimiters
            r'account\s*(?:number|#|no\.?)[:\s]*([0-9]{4,20})',  # account number: 12345678
            r'account[:\s]+([0-9]{4,20})',  # account: 12345678
            r'acct\.?\s*(?:number|#|no\.?)[:\s]*([0-9]{4,20})',  # acct number: 12345678
            r'acct[:\s]+([0-9]{4,20})',  # acct: 12345678
            
            # Ending patterns - most common in statements
            r'ending\s+in[:\s]*([0-9]{3,8})',  # ending in 12345
            r'ending[:\s]+([0-9]{3,8})',  # ending: 12345
            r'account\s+ending[:\s]+([0-9]{3,8})',  # account ending: 12345
            
            # Card patterns with masking
            r'(?:x{4,}|\*{4,})[^0-9]*([0-9]{4,5})',  # xxxx1234 or ****12345
            r'card\s+ending[:\s]*([0-9]{4,5})',  # card ending: 1234
            
            # Hyphenated patterns (common format)
            r'([0-9]{4}-[0-9]{4,8})',  # 1234-56789
            r'([0-9]{6,8}-[0-9]{2,4})',  # 123456-78
            
            # Direct number patterns (be more selective)
            r'\b([0-9]{8,16})\b',  # 8-16 digit standalone numbers
        ]
        
        for pattern in account_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                account = match.group(1) if match.groups() else match.group(0)
                # Clean and validate
                clean_account = account.replace('-', '').replace(' ', '')
                if (len(clean_account) >= 3 and 
                    clean_account.isdigit() and 
                    len(set(clean_account)) > 1):  # Not all same digit
                    return account
        
        return None
    
    def get_last_digits(self, account_info: str, num_digits: int = 5) -> str:
        """Extract the last N digits from account information."""
        import re
        
        # Remove all non-alphanumeric characters and get digits/letters
        clean_account = re.sub(r'[^A-Z0-9]', '', account_info.upper())
        
        # If it's shorter than requested digits, return the whole thing
        if len(clean_account) <= num_digits:
            return clean_account
        
        # Return last N characters
        return clean_account[-num_digits:]
    
    def find_matching_existing_folder(self, company_folder_id: str, account_type: str, account_digits: str) -> Optional[str]:
        """Find existing folder that matches the account type and digits."""
        try:
            # Get all folders in the company folder
            results = self.service.files().list(
                q=f"'{company_folder_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            folders = results.get('files', [])
            
            for folder in folders:
                folder_name = folder['name'].lower()
                
                # Check if folder contains the account digits
                if account_digits.lower() in folder_name:
                    # Check if it's the right type of account
                    if any(keyword in folder_name for keyword in [
                        account_type.lower(),
                        'checking' if account_type.lower() == 'bank' else '',
                        'savings' if account_type.lower() == 'bank' else '',
                        'credit' if account_type.lower() == 'credit card' else '',
                        'brokerage' if account_type.lower() == 'investment' else '',
                    ]):
                        return folder['name']  # Return the actual existing folder name
            
            return None
            
        except HttpError as error:
            console.print(f"[red]Error finding existing folders: {error}[/red]")
            return None
    
    def find_target_folder(self, dest_folder_id: str, company: str, statement_type: str, account_info: Optional[str]) -> Optional[str]:
        """Find the best matching existing folder for this statement using smart matching."""
        try:
            # Use pre-fetched folders cache if available
            if self._dest_folders_cache is not None and self._dest_folder_id == dest_folder_id:
                folders = self._dest_folders_cache
            else:
                # Fallback to API call if cache not available
                results = self.service.files().list(
                    q=f"'{dest_folder_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'",
                    spaces='drive',
                    fields='files(id, name)'
                ).execute()
                folders = results.get('files', [])
            
            # Extract account digits from account_info if available
            account_digits = None
            if account_info:
                import re
                # Extract all digits from account info
                digits = re.findall(r'\d+', str(account_info))
                if digits:
                    # Try to get last 4-5 digits from the longest number
                    longest_digits = max(digits, key=len)
                    if len(longest_digits) >= 4:
                        account_digits = longest_digits[-5:] if len(longest_digits) >= 5 else longest_digits[-4:]
            
            # Smart folder matching logic
            best_matches = []
            
            for folder in folders:
                folder_name = folder['name'].lower()
                match_score = 0
                match_reasons = []
                
                # Company matching with flexible patterns
                company_patterns = {
                    'american express': ['amex', 'american express', 'blue'],
                    'chase': ['chase', 'freedom'],
                    'citi': ['citi', 'best buy', 'american airlines', 'double cash'],
                    'schwab': ['schwab', 'charles schwab'],
                    'capital one': ['capital one', 'quicksilver', 'savor'],
                    'synchrony': ['synchrony', 'amazon store'],
                    'sofi': ['sofi'],
                    't-mobile': ['t-mobile', 'tmobile'],
                    'paypal': ['paypal'],
                    'wise': ['wise'],
                    'wells fargo': ['wells'],
                    'bank of america': ['bank of america', 'bofa'],
                    'apple': ['apple'],
                    'td bank': ['td bank', 'td'],
                    'at&t': ['at&t', 'att'],
                    'swan bitcoin': ['swan'],
                    'okcoin': ['okcoin', 'ok coin'],
                }
                
                # Check company match
                if company and company.lower() in company_patterns:
                    patterns = company_patterns[company.lower()]
                    for pattern in patterns:
                        if pattern in folder_name:
                            match_score += 10
                            match_reasons.append(f'company:{pattern}')
                            break
                
                # Check account number match (highest priority)
                if account_digits:
                    if account_digits in folder_name:
                        match_score += 50  # High priority for exact account match
                        match_reasons.append(f'account:{account_digits}')
                    else:
                        # Try partial matches (last 3-4 digits)
                        for i in range(3, min(len(account_digits) + 1, 6)):
                            partial = account_digits[-i:]
                            if partial in folder_name and len(partial) >= 3:
                                match_score += 20 + i  # More points for longer matches
                                match_reasons.append(f'partial_account:{partial}')
                                break
                
                # Statement type matching (more flexible)
                type_patterns = {
                    'bank statement': ['checking', 'savings', 'money', 'bank'],
                    'credit card statement': ['credit', 'card'],
                    'investment statement': ['brokerage', 'ira', 'broker', 'investment'],
                    'loan statement': ['loan'],
                    'utility statement': ['bill', 'utility'],
                    'monthly statement': ['statement', 'checking', 'savings', 'money']  # Monthly can be bank statements
                }
                
                if statement_type and statement_type in type_patterns:
                    patterns = type_patterns[statement_type]
                    for pattern in patterns:
                        if pattern in folder_name:
                            match_score += 5
                            match_reasons.append(f'type:{pattern}')
                            break
                
                if match_score > 0:
                    best_matches.append({
                        'folder': folder,
                        'score': match_score,
                        'reasons': match_reasons
                    })
            
            if best_matches:
                # Sort by score (highest first)
                best_matches.sort(key=lambda x: x['score'], reverse=True)
                best_match = best_matches[0]
                
                # Check for exact company name matches as fallback (case insensitive)
                if best_match['score'] < 15 and company:
                    for folder in folders:
                        folder_name = folder['name'].lower()
                        if company.lower() == folder_name or company.lower() in folder_name:
                            console.print(f"[dim]✅ Fallback match to existing folder: {folder['name']} (exact company name)[/dim]")
                            return folder['id']
                
                # Lower threshold for better matches (score >= 10)
                if best_match['score'] >= 10:
                    console.print(f"[dim]✅ Matched to existing folder: {best_match['folder']['name']} (score: {best_match['score']}, reasons: {', '.join(best_match['reasons'])})[/dim]")
                    return best_match['folder']['id']
                else:
                    console.print(f"[dim]⚠️  Low confidence match for {company}/{statement_type}, will create new folder[/dim]")
            
            # Final fallback: check for exact company name matches when no scored matches found
            if company:
                for folder in folders:
                    folder_name = folder['name'].lower()
                    if company.lower() == folder_name or company.lower() in folder_name:
                        console.print(f"[dim]✅ Final fallback match: {folder['name']} (company name found)[/dim]")
                        return folder['id']
            
            return None
            
        except Exception as e:
            console.print(f"[red]Error in folder matching: {str(e)}[/red]")
            return None
            
            if account_info:
                account_digits = self.get_last_digits(account_info, 4)
                
                # Look for folders that contain the account digits
                for folder in folders:
                    folder_name = folder['name'].lower()
                    if account_digits.lower() in folder_name:
                        # Check if company matches
                        if company in company_keywords:
                            if any(keyword in folder_name for keyword in company_keywords[company]):
                                return folder['id']
                
                # Look for folders that match company and account type
                for folder in folders:
                    folder_name = folder['name'].lower()
                    
                    # Check company match
                    if company in company_keywords:
                        if any(keyword in folder_name for keyword in company_keywords[company]):
                            # Check account type match
                            if statement_type in type_keywords:
                                if any(keyword in folder_name for keyword in type_keywords[statement_type]):
                                    return folder['id']
            
            return None
            
        except HttpError as error:
            console.print(f"[red]Error finding target folder: {error}[/red]")
            return None
    
    def _process_single_file(self, file: Dict, dest_folder_id: str, dry_run: bool, duplicate_handling: str) -> Dict:
        """Process a single file - designed for parallel execution.
        
        Returns a dict with: status ('copied', 'skipped', 'unclassified', 'error'), and optional message.
        Uses thread-local API service to avoid SSL/connection issues.
        """
        result = {'status': None, 'message': None, 'file_name': file['name']}
        
        try:
            # Skip non-PDF files
            if not file['name'].lower().endswith('.pdf'):
                result['status'] = 'skipped'
                result['message'] = 'Non-PDF file'
                return result
            
            # First check cache - if cached, we can skip the expensive PDF download
            cached_result = self.file_mapping.get_classification(
                file['id'], file['name'], file.get('size')
            )
            
            if cached_result and cached_result[0] and cached_result[1]:
                # Use cached classification - NO download needed!
                company, statement_type, account_info = cached_result
                file_content = None  # Don't download
            else:
                # Cache miss - need to download and classify using thread-local service
                file_content = self._download_file_threadsafe(file['id'])
                if file_content is None:
                    result['status'] = 'error'
                    result['message'] = f"Failed to download: {file['name']}"
                    return result
                    
                company, statement_type, account_info = self.classify_file(
                    file['name'], 
                    file_content, 
                    file_id=file['id'], 
                    file_size=file.get('size'),
                    skip_download_on_cache=False
                )
            
            if not company or not statement_type:
                result['status'] = 'unclassified'
                result['message'] = f"Could not classify: {file['name']}"
                return result
            
            # Find target folder (uses pre-fetched cache - thread-safe)
            target_folder_id = self.find_target_folder(dest_folder_id, company, statement_type, account_info)
            
            if target_folder_id:
                if not dry_run:
                    # Copy with appropriate duplicate handling using thread-local service
                    check_dupes = duplicate_handling != 'force'
                    success = self._copy_file_threadsafe(file['id'], target_folder_id, check_duplicates=check_dupes)
                    result['status'] = 'copied' if success else 'error'
                else:
                    # Dry run - use cached folder info (thread-safe)
                    with self._cache_lock:
                        folder_info = self._folder_info_cache.get(target_folder_id)
                    folder_name = folder_info['name'] if folder_info else 'existing folder'
                    result['status'] = 'copied'
                    result['message'] = f"Would copy: {file['name']} → {folder_name}/"
            else:
                # No existing folder - would create new
                if dry_run:
                    clean_type = statement_type.replace(" statement", "").replace("_statement", "")
                    if account_info:
                        account_digits = self.get_last_digits(account_info, 4)
                        folder_path = f"{company}/{clean_type} -{account_digits}"
                    else:
                        folder_path = f"{company}/{clean_type}"
                    result['status'] = 'copied'
                    result['message'] = f"Would copy: {file['name']} → {folder_path}/ (new folder)"
                else:
                    # Create folder and copy - use main thread's service for folder creation
                    # to avoid race conditions
                    company_folder_id = self.find_folder_by_name(company, dest_folder_id)
                    if not company_folder_id:
                        company_folder_id = self.create_folder(company, dest_folder_id)
                    if company_folder_id:
                        success = self._copy_file_threadsafe(file['id'], company_folder_id, check_duplicates=True)
                        result['status'] = 'copied' if success else 'error'
                    else:
                        result['status'] = 'error'
                        result['message'] = f"Failed to create folder for {company}"
            
            return result
            
        except Exception as e:
            result['status'] = 'error'
            result['message'] = f"Error processing {file['name']}: {e}"
            return result
    
    def _download_file_threadsafe(self, file_id: str) -> Optional[bytes]:
        """Thread-safe file download using thread-local service."""
        try:
            service = self.get_thread_service()
            request = service.files().get_media(fileId=file_id)
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            return file.getvalue()
        except Exception as e:
            # Don't print errors here - they'll clutter parallel output
            return None
    
    def _copy_file_threadsafe(self, file_id: str, destination_folder_id: str, check_duplicates: bool = True) -> bool:
        """Thread-safe file copy using thread-local service."""
        try:
            service = self.get_thread_service()
            
            # Get file metadata
            file_metadata = service.files().get(fileId=file_id).execute()
            original_name = file_metadata['name']
            
            # Simple duplicate check - just check if same name exists
            if check_duplicates:
                query = f"name='{original_name}' and '{destination_folder_id}' in parents and trashed=false"
                existing = service.files().list(q=query, fields='files(id)').execute()
                if existing.get('files'):
                    # File already exists, skip
                    return True
            
            # Copy the file
            copy_metadata = {
                'name': original_name,
                'parents': [destination_folder_id]
            }
            
            service.files().copy(fileId=file_id, body=copy_metadata).execute()
            console.print(f"[green]✓ Copied: {original_name}[/green]")
            return True
            
        except Exception as e:
            return False

    def organize_statements(self, source_folder_id: str, dest_folder_id: str, dry_run: bool = False, duplicate_handling: str = 'smart') -> Dict:
        """Organize statements from source folder to destination folder.
        
        Uses sequential processing (threading causes SSL crashes on macOS) but with
        optimizations: caching, pre-fetched folders, skip downloads on cache hit.
        """
        console.print(f"\n[bold blue]Starting statement organization (optimized sequential mode)...[/bold blue]")
        
        # Get files from source folder (recursively)
        console.print("Searching for files recursively through all subfolders...")
        files = self.get_files_in_folder(source_folder_id, recursive=True)
        
        if not files:
            console.print("[yellow]No files found in source folder or its subfolders[/yellow]")
            return {}
        
        console.print(f"Found {len(files)} files to process")
        
        # Show file types found
        file_types = {}
        for file in files:
            ext = os.path.splitext(file['name'])[1].lower()
            file_types[ext] = file_types.get(ext, 0) + 1
        
        console.print(f"File types found: {dict(file_types)}")
        
        # PRE-FETCH destination folders once (major optimization!)
        self.prefetch_destination_folders(dest_folder_id)
        
        # Statistics
        stats = {
            'total_files': len(files),
            'processed': 0,
            'copied': 0,
            'skipped': 0,
            'errors': 0,
            'unclassified': 0
        }
        
        # Process files sequentially (threading causes SSL crashes on macOS)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Processing files...", total=len(files))
            
            for file in files:
                progress.update(task, description=f"Processing: {file['name'][:40]}...")
                
                try:
                    # Skip non-PDF files
                    if not file['name'].lower().endswith('.pdf'):
                        stats['skipped'] += 1
                        progress.advance(task)
                        continue
                    
                    # Check cache first - skip download if cached
                    cached_result = self.file_mapping.get_classification(
                        file['id'], file['name'], file.get('size')
                    )
                    
                    if cached_result and cached_result[0] and cached_result[1]:
                        # Use cached classification - NO download needed!
                        company, statement_type, account_info = cached_result
                    else:
                        # Cache miss - need to download and classify
                        file_content = self.download_file(file['id'])
                        if file_content is None:
                            stats['errors'] += 1
                            progress.advance(task)
                            continue
                            
                        company, statement_type, account_info = self.classify_file(
                            file['name'], 
                            file_content, 
                            file_id=file['id'], 
                            file_size=file.get('size'),
                            skip_download_on_cache=False
                        )
                    
                    if not company or not statement_type:
                        stats['unclassified'] += 1
                        progress.advance(task)
                        continue
                    
                    # Find target folder (uses pre-fetched cache)
                    target_folder_id = self.find_target_folder(dest_folder_id, company, statement_type, account_info)
                    
                    if target_folder_id:
                        if not dry_run:
                            check_dupes = duplicate_handling != 'force'
                            success = self.copy_file(file['id'], target_folder_id, check_duplicates=check_dupes)
                            if success:
                                stats['copied'] += 1
                            else:
                                stats['errors'] += 1
                        else:
                            folder_info = self.get_cached_folder_info(target_folder_id)
                            folder_name = folder_info['name'] if folder_info else 'existing folder'
                            console.print(f"[green]Would copy: {file['name']} → {folder_name}/[/green]")
                            stats['copied'] += 1
                    else:
                        # No existing folder - would create new
                        if dry_run:
                            clean_type = statement_type.replace(" statement", "").replace("_statement", "")
                            if account_info:
                                account_digits = self.get_last_digits(account_info, 4)
                                folder_path = f"{company}/{clean_type} -{account_digits}"
                            else:
                                folder_path = f"{company}/{clean_type}"
                            console.print(f"[blue]Would copy: {file['name']} → {folder_path}/ (new folder)[/blue]")
                            stats['copied'] += 1
                        else:
                            company_folder_id = self.find_folder_by_name(company, dest_folder_id)
                            if not company_folder_id:
                                company_folder_id = self.create_folder(company, dest_folder_id)
                            if company_folder_id:
                                success = self.copy_file(file['id'], company_folder_id, check_duplicates=True)
                                if success:
                                    stats['copied'] += 1
                                else:
                                    stats['errors'] += 1
                            else:
                                stats['errors'] += 1
                    
                    stats['processed'] += 1
                    
                except Exception as e:
                    console.print(f"[red]Error processing {file['name']}: {e}[/red]")
                    stats['errors'] += 1
                
                progress.advance(task)
        
        # Flush any pending cache entries
        self.file_mapping.flush()
        
        return stats

    def check_for_duplicates(self, file_id: str, destination_folder_id: str, file_name: str = None) -> Dict:
        """
        Check for various types of duplicates before copying a file.
        Returns dict with duplicate info and recommended action.
        """
        try:
            # Get file metadata if not provided
            if not file_name:
                file_metadata = self.service.files().get(fileId=file_id, fields='name,size,md5Checksum').execute()
                file_name = file_metadata['name']
                file_size = file_metadata.get('size', '0')
                file_md5 = file_metadata.get('md5Checksum')
            else:
                file_metadata = self.service.files().get(fileId=file_id, fields='size,md5Checksum').execute()
                file_size = file_metadata.get('size', '0')
                file_md5 = file_metadata.get('md5Checksum')
            
            duplicates = {
                'exact_filename': None,
                'content_duplicate': None,
                'similar_filename': [],
                'recommended_action': 'copy',
                'reason': 'No duplicates found'
            }
            
            # 1. Check for exact filename match
            query = f"name='{file_name}' and '{destination_folder_id}' in parents and trashed=false"
            exact_matches = self.service.files().list(q=query, fields='files(id,name,size,md5Checksum)').execute()
            
            if exact_matches['files']:
                exact_match = exact_matches['files'][0]
                duplicates['exact_filename'] = exact_match
                
                # Check if it's the same file (same ID)
                if exact_match['id'] == file_id:
                    duplicates['recommended_action'] = 'skip'
                    duplicates['reason'] = 'File already exists in destination (same file ID)'
                else:
                    # Check if content is identical (same MD5)
                    if file_md5 and exact_match.get('md5Checksum') and file_md5 == exact_match['md5Checksum']:
                        duplicates['recommended_action'] = 'skip'
                        duplicates['reason'] = 'Identical file already exists in destination'
                    else:
                        duplicates['recommended_action'] = 'rename'
                        duplicates['reason'] = 'File with same name exists but content differs'
            
            # 2. Check for content duplicates (same MD5 hash)
            if file_md5:
                query = f"md5Checksum='{file_md5}' and '{destination_folder_id}' in parents and trashed=false"
                content_matches = self.service.files().list(q=query, fields='files(id,name,size,md5Checksum)').execute()
                
                if content_matches['files']:
                    # Filter out the current file
                    content_dupes = [f for f in content_matches['files'] if f['id'] != file_id]
                    if content_dupes:
                        duplicates['content_duplicate'] = content_dupes[0]
                        if duplicates['recommended_action'] == 'copy':
                            duplicates['recommended_action'] = 'skip'
                            duplicates['reason'] = 'Identical content already exists in destination'
            
            # 3. Check for similar filenames (same base name, different extensions or dates)
            base_name = os.path.splitext(file_name)[0]
            # Remove common date patterns
            base_name_clean = re.sub(r'[-_]\d{4}[-_]\d{2}[-_]\d{2}', '', base_name)
            base_name_clean = re.sub(r'[-_]\d{8}', '', base_name_clean)
            
            query = f"'{destination_folder_id}' in parents and trashed=false"
            all_files = self.service.files().list(q=query, fields='files(id,name,size)').execute()
            
            for file in all_files['files']:
                if file['id'] != file_id:
                    other_base = os.path.splitext(file['name'])[0]
                    other_base_clean = re.sub(r'[-_]\d{4}[-_]\d{2}[-_]\d{2}', '', other_base)
                    other_base_clean = re.sub(r'[-_]\d{8}', '', other_base_clean)
                    
                    # Check for similar base names
                    if (base_name_clean.lower() == other_base_clean.lower() or 
                        base_name_clean.lower().startswith(other_base_clean.lower()) or
                        other_base_clean.lower().startswith(base_name_clean.lower())):
                        duplicates['similar_filename'].append(file)
            
            return duplicates
            
        except Exception as e:
            console.print(f"[yellow]Warning: Could not check for duplicates: {e}[/yellow]")
            return {
                'exact_filename': None,
                'content_duplicate': None,
                'similar_filename': [],
                'recommended_action': 'copy',
                'reason': f'Error checking duplicates: {e}'
            }

    def generate_unique_filename(self, original_name: str, destination_folder_id: str) -> str:
        """
        Generate a unique filename for the destination folder.
        Handles duplicates by adding (1), (2), etc.
        """
        base_name, extension = os.path.splitext(original_name)
        counter = 1
        new_name = original_name
        
        while True:
            query = f"name='{new_name}' and '{destination_folder_id}' in parents and trashed=false"
            matches = self.service.files().list(q=query, fields='files(id)').execute()
            
            if not matches['files']:
                break
            
            new_name = f"{base_name} ({counter}){extension}"
            counter += 1
            
            # Prevent infinite loop
            if counter > 100:
                new_name = f"{base_name}_{int(time.time())}{extension}"
                break
        
        return new_name

    def analyze_duplicates(self, destination_folder_id: str) -> Dict:
        """
        Analyze destination folders for potential duplicates and provide a report.
        """
        console.print(f"\n[bold blue]Analyzing duplicates in destination folders...[/bold blue]")
        
        try:
            # Get all files in destination folders
            all_files = self.get_files_in_folder(destination_folder_id, recursive=True)
            
            if not all_files:
                console.print("[yellow]No files found in destination folders[/yellow]")
                return {}
            
            console.print(f"Found {len(all_files)} files to analyze")
            
            # Group files by MD5 hash and filename
            md5_groups = {}
            filename_groups = {}
            potential_duplicates = []
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Analyzing files...", total=len(all_files))
                
                for file in all_files:
                    progress.update(task, description=f"Analyzing: {file['name']}")
                    
                    try:
                        # Get file metadata with MD5
                        file_metadata = self.service.files().get(
                            fileId=file['id'], 
                            fields='name,size,md5Checksum,parents'
                        ).execute()
                        
                        file_name = file_metadata['name']
                        file_size = file_metadata.get('size', '0')
                        file_md5 = file_metadata.get('md5Checksum')
                        file_parents = file_metadata.get('parents', [])
                        
                        # Group by MD5 hash
                        if file_md5:
                            if file_md5 not in md5_groups:
                                md5_groups[file_md5] = []
                            md5_groups[file_md5].append({
                                'id': file['id'],
                                'name': file_name,
                                'size': file_size,
                                'parents': file_parents
                            })
                        
                        # Group by filename
                        if file_name not in filename_groups:
                            filename_groups[file_name] = []
                        filename_groups[file_name].append({
                            'id': file['id'],
                            'name': file_name,
                            'size': file_size,
                            'md5': file_md5,
                            'parents': file_parents
                        })
                        
                    except Exception as e:
                        console.print(f"[yellow]Warning: Could not analyze {file['name']}: {e}[/yellow]")
                    
                    progress.advance(task)
            
            # Find duplicates
            duplicate_report = {
                'total_files': len(all_files),
                'md5_duplicates': [],
                'filename_duplicates': [],
                'summary': {}
            }
            
            # MD5 duplicates (identical content)
            for md5, files in md5_groups.items():
                if len(files) > 1:
                    duplicate_report['md5_duplicates'].append({
                        'md5': md5,
                        'files': files,
                        'count': len(files)
                    })
            
            # Filename duplicates (same name, potentially different content)
            for filename, files in filename_groups.items():
                if len(files) > 1:
                    duplicate_report['filename_duplicates'].append({
                        'filename': filename,
                        'files': files,
                        'count': len(files)
                    })
            
            # Generate summary
            duplicate_report['summary'] = {
                'md5_duplicate_groups': len(duplicate_report['md5_duplicates']),
                'filename_duplicate_groups': len(duplicate_report['filename_duplicates']),
                'total_duplicate_files': sum(len(group['files']) for group in duplicate_report['md5_duplicates']) + 
                                       sum(len(group['files']) for group in duplicate_report['filename_duplicates'])
            }
            
            # Display results
            console.print(f"\n[bold]Duplicate Analysis Results:[/bold]")
            console.print(f"Total files analyzed: {duplicate_report['total_files']}")
            console.print(f"MD5 duplicate groups: {duplicate_report['summary']['md5_duplicate_groups']}")
            console.print(f"Filename duplicate groups: {duplicate_report['summary']['filename_duplicate_groups']}")
            
            if duplicate_report['md5_duplicates']:
                console.print(f"\n[bold yellow]Content Duplicates (Identical Files):[/bold yellow]")
                for group in duplicate_report['md5_duplicates']:
                    console.print(f"  MD5: {group['md5'][:8]}... - {group['count']} files:")
                    for file in group['files']:
                        folder_name = "Unknown"
                        if file['parents']:
                            try:
                                parent_info = self.service.files().get(fileId=file['parents'][0], fields='name').execute()
                                folder_name = parent_info['name']
                            except:
                                pass
                        console.print(f"    • {file['name']} ({folder_name}/)")
            
            if duplicate_report['filename_duplicates']:
                console.print(f"\n[bold yellow]Filename Duplicates:[/bold yellow]")
                for group in duplicate_report['filename_duplicates']:
                    console.print(f"  Filename: {group['filename']} - {group['count']} files:")
                    for file in group['files']:
                        folder_name = "Unknown"
                        if file['parents']:
                            try:
                                parent_info = self.service.files().get(fileId=file['parents'][0], fields='name').execute()
                                folder_name = parent_info['name']
                            except:
                                pass
                        console.print(f"    • {file['name']} ({folder_name}/) - Size: {file['size']} bytes")
            
            return duplicate_report
            
        except Exception as e:
            console.print(f"[red]Error analyzing duplicates: {e}[/red]")
            return {}


@click.command()
@click.option('--source-folder-id', envvar='SOURCE_FOLDER_ID', help='Google Drive folder ID for source folder')
@click.option('--dest-folder-id', envvar='DEST_FOLDER_ID', help='Google Drive folder ID for destination folder')
@click.option('--credentials-file', default='credentials.json', help='Path to Google API credentials file')
@click.option('--dry-run', is_flag=True, help='Preview changes without making them')
@click.option('--monthly-statements', default='Monthly Statements', help='Name of monthly statements folder')
@click.option('--statements-by-account', default='Statements by Account', help='Name of statements by account folder')
@click.option('--clear-cache', is_flag=True, help='Clear the file classification cache')
@click.option('--export-cache', help='Export cache to specified file')
@click.option('--rename-folders', is_flag=True, help='Rename folders with confirmed account numbers')
@click.option('--backup-folders', is_flag=True, help='Create backup of current folder structure')
@click.option('--test-rename', help='Test renaming a single folder (format: "old_name,new_name")')
@click.option('--workers', default=4, help='Number of parallel workers for processing (default: 4)')
@click.option('--duplicate-handling', default='smart', type=click.Choice(['smart', 'skip', 'rename', 'force']), 
              help='How to handle duplicates: smart=auto-detect, skip=skip all, rename=auto-rename, force=overwrite (default: smart)')
@click.option('--analyze-duplicates', is_flag=True, help='Analyze and report on duplicates in destination folders')
def main(source_folder_id: str, dest_folder_id: str, credentials_file: str, dry_run: bool, 
         monthly_statements: str, statements_by_account: str, clear_cache: bool, export_cache: str,
         rename_folders: bool, backup_folders: bool, test_rename: str, workers: int, duplicate_handling: str, analyze_duplicates: bool):
    """Organize Google Drive statements by company and type."""
    
    console.print("[bold green]Google Drive Statement Organizer[/bold green]")
    
    if dry_run:
        console.print("[yellow]Running in DRY RUN mode - no changes will be made[/yellow]")
    
    # Initialize organizer
    try:
        organizer = GoogleDriveOrganizer(credentials_file, workers=workers)
    except Exception as e:
        console.print(f"[red]Failed to initialize: {e}[/red]")
        return 1
    
    # Handle cache operations
    if clear_cache:
        organizer.file_mapping.clear_cache()
        console.print("[green]✓ Cache cleared successfully[/green]")
        return 0
    
    if export_cache:
        export_file = organizer.file_mapping.export_mapping(export_cache)
        console.print(f"[green]✓ Cache exported to {export_file}[/green]")
        return 0
    
    # Handle folder operations
    if backup_folders:
        dest_folder_id = organizer.find_folder_by_name(statements_by_account)
        if dest_folder_id:
            backup_data = organizer.backup_folder_structure(dest_folder_id)
            console.print(f"[green]✓ Backup created with {backup_data.get('total_folders', 0)} folders[/green]")
        return 0
    
    if analyze_duplicates:
        dest_folder_id = organizer.find_folder_by_name(statements_by_account)
        if dest_folder_id:
            duplicate_report = organizer.analyze_duplicates(dest_folder_id)
            if duplicate_report:
                console.print(f"\n[green]✓ Duplicate analysis completed![/green]")
        else:
            console.print("[red]Error: Could not find 'Statements by Account' folder[/red]")
            return 1
        return 0
    
    if test_rename:
        if ',' not in test_rename:
            console.print("[red]Error: test-rename format should be 'old_name,new_name'[/red]")
            return 1
        
        old_name, new_name = test_rename.split(',', 1)
        old_name, new_name = old_name.strip(), new_name.strip()
        
        dest_folder_id = organizer.find_folder_by_name(statements_by_account)
        if not dest_folder_id:
            console.print("[red]Error: Could not find 'Statements by Account' folder[/red]")
            return 1
        
        folder_id = organizer.find_folder_by_exact_name(old_name, dest_folder_id)
        if not folder_id:
            console.print(f"[red]Error: Folder '{old_name}' not found[/red]")
            return 1
        
        if dry_run:
            console.print(f"[cyan]Would rename: '{old_name}' → '{new_name}'[/cyan]")
        else:
            success = organizer.rename_folder(folder_id, new_name)
            if success:
                console.print(f"[green]✓ Successfully renamed folder[/green]")
            else:
                console.print(f"[red]✗ Failed to rename folder[/red]")
                return 1
        return 0
    
    if rename_folders:
        # Define confirmed renamings
        # Final mapping - only add account numbers where missing, keep all existing numbers
        confirmed_renames = {
            # Add account numbers to folders that are missing them
            "Chase Freedom Card": "Chase Freedom Card -64649",
            "Amazon Store Card - Synchrony": "Amazon Store Card - Synchrony -27717",
            "Citi Double Cash Personal": "Citi Double Cash Personal -80521",
            "AmEx Blue Cash": "AmEx Blue Cash -84002",  # Updated from screenshot
            "Capital One Quicksilver Credit Card": "Capital One Quicksilver Credit Card -40318",
            "Personal PayPal": "Personal PayPal -53762",
            "SoFi Money": "SoFi Money -20516",
            "Wise": "Wise -18903",
            
            # AmEx cards from screenshot
            "AmEx Blue Business Cash": "AmEx Blue Business Cash -41003",  # Blue Business Cash(TM)
            "Blue Business Plus Credit Card": "Blue Business Plus Credit Card -61005",  # Schwab Investor Card
            "AmEx Personal Loan": "AmEx Personal Loan -91003",  # Cancelled but keep for archival
            
            # SoFi accounts
            "SoFi Loan": "SoFi Loan -61582",  # From PDF: Account Number PA-761582
            
            # Mark unresolved account
            "Schwab Business American Express": "Schwab Business American Express -UNRESOLVED",
            
            # Simplify crypto name only
            "Swan Bitcoin / Prime Trust LLC": "Swan Bitcoin"
            
            # KEEP ALL EXISTING ACCOUNT NUMBERS AS-IS:
            # ✅ "Citi American Airlines -5619" (existing -5619 is likely correct)
            # ✅ "Citi Best Buy -1383" (existing -1383 matches our -91383)
            # ✅ "Personal Brokerage -608" (existing -608)
            # ✅ "Personal Checking -624" (existing -624)
            # ✅ "Business Checking -417" (existing -417)
            # ✅ "Antifragile Broker -485" (existing -485)
            # ✅ "Schwab Checking -7641" (existing -7641)
            # ✅ "OkCoin" (already correct)
            # ✅ "IRA Accounts - Not reconciled anymore - Skip" (contains subfolders)
        }
        
        console.print(f"[bold yellow]Renaming {len(confirmed_renames)} folders with confirmed account numbers[/bold yellow]")
        
        results = organizer.batch_rename_folders(confirmed_renames, dry_run=dry_run)
        
        # Display results
        console.print(f"\n[bold blue]Rename Results:[/bold blue]")
        console.print(f"✅ Success: {len(results['success'])}")
        console.print(f"⚠️  Skipped: {len(results['skipped'])}")
        console.print(f"❌ Failed: {len(results['failed'])}")
        
        if results['failed']:
            console.print(f"\n[red]Failed folders:[/red]")
            for folder in results['failed']:
                console.print(f"  • {folder}")
        
        return 0
    
    # Find folders if IDs not provided
    if not source_folder_id:
        console.print(f"Looking for '{monthly_statements}' folder...")
        source_folder_id = organizer.find_folder_by_name(monthly_statements)
        if not source_folder_id:
            console.print(f"[red]Could not find '{monthly_statements}' folder[/red]")
            return 1
    
    if not dest_folder_id:
        console.print(f"Looking for '{statements_by_account}' folder...")
        dest_folder_id = organizer.find_folder_by_name(statements_by_account)
        if not dest_folder_id:
            console.print(f"[red]Could not find '{statements_by_account}' folder[/red]")
            return 1
    
    # Organize statements
    stats = organizer.organize_statements(source_folder_id, dest_folder_id, dry_run, duplicate_handling)
    
    # Display results
    console.print(f"\n[bold blue]Organization Complete![/bold blue]")
    
    table = Table(title="Processing Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="magenta")
    
    table.add_row("Total Files", str(stats['total_files']))
    table.add_row("Processed", str(stats['processed']))
    table.add_row("Copied", str(stats['copied']))
    table.add_row("Skipped", str(stats['skipped']))
    table.add_row("Unclassified", str(stats['unclassified']))
    table.add_row("Errors", str(stats['errors']))
    
    console.print(table)
    
    # Show cache statistics
    cache_stats = organizer.file_mapping.get_cache_stats()
    console.print(f"\n[bold blue]Cache Statistics:[/bold blue]")
    console.print(f"📁 Total cached files: {cache_stats['total_cached_files']}")
    console.print(f"✅ Classified files: {cache_stats['classified_files']}")
    console.print(f"❓ Unclassified files: {cache_stats['unclassified_files']}")
    console.print(f"💾 Cache file size: {cache_stats['cache_file_size']} bytes")
    
    return 0


if __name__ == '__main__':
    exit(main())
