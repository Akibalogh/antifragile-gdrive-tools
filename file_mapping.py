"""
File mapping system for caching PDF classification results.
"""

import json
import os
import hashlib
from typing import Dict, Optional, Tuple
from datetime import datetime


class FileMapping:
    """Manages local file mapping cache for PDF classifications."""
    
    def __init__(self, cache_file: str = 'file_mapping_cache.json', batch_size: int = 50):
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.batch_size = batch_size
        self._pending_saves = 0
        self._lock = None  # Will be set if threading is used
    
    def set_thread_safe(self):
        """Enable thread-safe operations."""
        import threading
        self._lock = threading.Lock()
    
    def _acquire_lock(self):
        """Acquire lock if in thread-safe mode."""
        if self._lock:
            self._lock.acquire()
    
    def _release_lock(self):
        """Release lock if in thread-safe mode."""
        if self._lock:
            self._lock.release()
    
    def _load_cache(self) -> Dict:
        """Load existing cache from file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_cache(self):
        """Save cache to file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except IOError:
            pass  # Fail silently if can't save
    
    def _get_file_key(self, file_id: str, file_name: str, file_size: Optional[str] = None) -> str:
        """Generate unique key for file based on ID, name, and size."""
        key_data = f"{file_id}:{file_name}:{file_size or ''}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get_classification(self, file_id: str, file_name: str, file_size: Optional[str] = None) -> Optional[Tuple[str, str, str]]:
        """Get cached classification for a file."""
        self._acquire_lock()
        try:
            key = self._get_file_key(file_id, file_name, file_size)
            
            if key in self.cache:
                cached = self.cache[key]
                return (
                    cached.get('company'),
                    cached.get('statement_type'),
                    cached.get('account_info')
                )
            
            return None
        finally:
            self._release_lock()
    
    def set_classification(self, file_id: str, file_name: str, company: Optional[str], 
                          statement_type: Optional[str], account_info: Optional[str],
                          file_size: Optional[str] = None, force_save: bool = False):
        """Cache classification result for a file. Uses batch saving for performance."""
        self._acquire_lock()
        try:
            key = self._get_file_key(file_id, file_name, file_size)
            
            self.cache[key] = {
                'file_id': file_id,
                'file_name': file_name,
                'file_size': file_size,
                'company': company,
                'statement_type': statement_type,
                'account_info': account_info,
                'last_updated': datetime.now().isoformat(),
                'classification_version': '1.0'  # For future compatibility
            }
            
            self._pending_saves += 1
            
            # Batch save: only write to disk every batch_size files or if forced
            if force_save or self._pending_saves >= self.batch_size:
                self._save_cache()
                self._pending_saves = 0
        finally:
            self._release_lock()
    
    def flush(self):
        """Force save any pending cache entries to disk."""
        self._acquire_lock()
        try:
            if self._pending_saves > 0:
                self._save_cache()
                self._pending_saves = 0
        finally:
            self._release_lock()
    
    def clear_cache(self):
        """Clear all cached data."""
        self.cache = {}
        self._save_cache()
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about the cache."""
        total_files = len(self.cache)
        classified_files = sum(1 for item in self.cache.values() 
                             if item.get('company') and item.get('statement_type'))
        unclassified_files = total_files - classified_files
        
        return {
            'total_cached_files': total_files,
            'classified_files': classified_files,
            'unclassified_files': unclassified_files,
            'cache_file_size': os.path.getsize(self.cache_file) if os.path.exists(self.cache_file) else 0
        }
    
    def export_mapping(self, export_file: str = 'file_mapping_export.json'):
        """Export mapping in a readable format."""
        export_data = {
            'export_date': datetime.now().isoformat(),
            'total_files': len(self.cache),
            'files': []
        }
        
        for key, data in self.cache.items():
            export_data['files'].append({
                'file_name': data.get('file_name'),
                'company': data.get('company'),
                'statement_type': data.get('statement_type'),
                'account_info': data.get('account_info'),
                'last_updated': data.get('last_updated')
            })
        
        # Sort by company, then by file name
        export_data['files'].sort(key=lambda x: (x.get('company') or '', x.get('file_name') or ''))
        
        with open(export_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return export_file
    
    def import_manual_mapping(self, mapping_file: str):
        """Import manual mappings from a file."""
        try:
            with open(mapping_file, 'r') as f:
                manual_mappings = json.load(f)
            
            for mapping in manual_mappings.get('files', []):
                # Find existing cache entry by file name
                for key, cached in self.cache.items():
                    if cached.get('file_name') == mapping.get('file_name'):
                        # Update with manual classification
                        cached.update({
                            'company': mapping.get('company'),
                            'statement_type': mapping.get('statement_type'),
                            'account_info': mapping.get('account_info'),
                            'last_updated': datetime.now().isoformat(),
                            'manual_override': True
                        })
                        break
            
            self._save_cache()
            return True
            
        except (json.JSONDecodeError, IOError, KeyError):
            return False
