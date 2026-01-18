#!/usr/bin/env python3
"""
Tests for Google Drive Statement Organizer
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import io

from main import GoogleDriveOrganizer


class TestGoogleDriveOrganizer(unittest.TestCase):
    """Test cases for GoogleDriveOrganizer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the authentication to avoid requiring real credentials
        with patch.object(GoogleDriveOrganizer, 'authenticate'):
            self.organizer = GoogleDriveOrganizer()
            self.organizer.service = Mock()
    
    def test_classify_file_bank_statement(self):
        """Test classification of bank statement files."""
        filename = "chase_bank_statement_january_2024.pdf"
        company, statement_type, account_info = self.organizer.classify_file(filename, file_id="test_id")
        
        self.assertEqual(company, "chase")
        self.assertEqual(statement_type, "bank statement")
        self.assertIsNone(account_info)  # No account info in this filename
    
    def test_classify_file_credit_card(self):
        """Test classification of credit card statement files."""
        filename = "amex_credit_card_statement_february_2024.pdf"
        company, statement_type, account_info = self.organizer.classify_file(filename, file_id="test_id2")
        
        self.assertEqual(company, "american express")
        self.assertEqual(statement_type, "credit card statement")
        self.assertIsNone(account_info)  # No account info in this filename
    
    def test_classify_file_investment(self):
        """Test classification of investment statement files."""
        filename = "fidelity_investment_statement_march_2024.pdf"
        company, statement_type, account_info = self.organizer.classify_file(filename, file_id="test_id3")
        
        self.assertEqual(company, "fidelity")
        self.assertEqual(statement_type, "investment statement")
        self.assertIsNone(account_info)  # No account info in this filename
    
    def test_classify_file_with_account_info(self):
        """Test classification with account information."""
        filename = "schwab_investment_statement_account_1234-5678.pdf"
        company, statement_type, account_info = self.organizer.classify_file(filename, file_id="test_id4")
        
        self.assertEqual(company, "schwab")
        self.assertEqual(statement_type, "investment statement")
        self.assertEqual(account_info, "1234-5678")
    
    def test_classify_file_unknown_company(self):
        """Test classification with unknown company."""
        filename = "random_document.pdf"  # Changed to avoid matching "statement"
        company, statement_type, account_info = self.organizer.classify_file(filename, file_id="test_id5")
        
        self.assertIsNone(company)
        self.assertIsNone(statement_type)
        self.assertIsNone(account_info)
    
    def test_extract_text_from_pdf(self):
        """Test PDF text extraction."""
        # Create a simple PDF-like content for testing
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        
        with patch('PyPDF2.PdfReader') as mock_reader:
            mock_page = Mock()
            mock_page.extract_text.return_value = "Sample PDF content"
            mock_reader.return_value.pages = [mock_page]
            
            text = self.organizer.extract_text_from_pdf(pdf_content)
            self.assertEqual(text, "Sample PDF content\n")
    
    def test_find_folder_by_name(self):
        """Test finding folder by name."""
        mock_response = {
            'files': [{'id': 'test_folder_id', 'name': 'Test Folder'}]
        }
        self.organizer.service.files().list().execute.return_value = mock_response
        
        folder_id = self.organizer.find_folder_by_name('Test Folder')
        self.assertEqual(folder_id, 'test_folder_id')
    
    def test_find_folder_by_name_not_found(self):
        """Test finding folder that doesn't exist."""
        mock_response = {'files': []}
        self.organizer.service.files().list().execute.return_value = mock_response
        
        folder_id = self.organizer.find_folder_by_name('Non-existent Folder')
        self.assertIsNone(folder_id)
    
    def test_get_files_in_folder(self):
        """Test getting files from a folder."""
        mock_response = {
            'files': [
                {'id': 'file1', 'name': 'statement1.pdf', 'mimeType': 'application/pdf'},
                {'id': 'file2', 'name': 'statement2.pdf', 'mimeType': 'application/pdf'}
            ]
        }
        self.organizer.service.files().list().execute.return_value = mock_response
        
        files = self.organizer.get_files_in_folder('test_folder_id')
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]['name'], 'statement1.pdf')
    
    def test_create_folder(self):
        """Test creating a new folder."""
        mock_response = {'id': 'new_folder_id'}
        self.organizer.service.files().create().execute.return_value = mock_response
        
        folder_id = self.organizer.create_folder('New Folder')
        self.assertEqual(folder_id, 'new_folder_id')
    
    def test_copy_file(self):
        """Test copying a file."""
        mock_file_metadata = {'name': 'test_file.pdf'}
        mock_copy_response = {'id': 'copied_file_id'}
        
        self.organizer.service.files().get().execute.return_value = mock_file_metadata
        self.organizer.service.files().copy().execute.return_value = mock_copy_response
        
        success = self.organizer.copy_file('source_file_id', 'dest_folder_id')
        self.assertTrue(success)


class TestFileClassification(unittest.TestCase):
    """Test cases for file classification logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the authentication to avoid requiring real credentials
        with patch.object(GoogleDriveOrganizer, 'authenticate'):
            self.organizer = GoogleDriveOrganizer()
    
    def test_company_patterns(self):
        """Test various company name patterns."""
        test_cases = [
            ("chase_statement.pdf", "chase"),
            ("jpmorgan_statement.pdf", "chase"),
            ("wells_fargo_statement.pdf", "wells fargo"),
            ("bank_of_america_statement.pdf", "bank of america"),
            ("amex_statement.pdf", "american express"),
            ("fidelity_statement.pdf", "fidelity"),
            ("vanguard_statement.pdf", "vanguard"),
        ]
        
        for i, (filename, expected_company) in enumerate(test_cases):
            with self.subTest(filename=filename):
                company, _, _ = self.organizer.classify_file(filename, file_id=f"test_company_{i}")
                self.assertEqual(company, expected_company)
    
    def test_statement_type_patterns(self):
        """Test various statement type patterns."""
        test_cases = [
            ("bank_statement.pdf", "bank statement"),
            ("credit_card_statement.pdf", "credit card statement"),
            ("investment_statement.pdf", "investment statement"),
            ("loan_statement.pdf", "loan statement"),
            ("insurance_statement.pdf", "insurance statement"),
            ("utility_statement.pdf", "utility statement"),
        ]
        
        for i, (filename, expected_type) in enumerate(test_cases):
            with self.subTest(filename=filename):
                _, statement_type, _ = self.organizer.classify_file(filename, file_id=f"test_type_{i}")
                self.assertEqual(statement_type, expected_type)
    
    def test_debug_classification(self):
        """Debug test to see what's happening with classification."""
        filename = "chase_bank_statement.pdf"
        company, statement_type, account_info = self.organizer.classify_file(filename, file_id="debug_test")
        print(f"Debug: filename='{filename}', company='{company}', statement_type='{statement_type}', account_info='{account_info}'")
        
        # This should help us understand what's happening
        self.assertIsNotNone(company, f"Company should be found for {filename}")
        self.assertIsNotNone(statement_type, f"Statement type should be found for {filename}")


class TestFileMapping(unittest.TestCase):
    """Test cases for FileMapping caching system."""
    
    def setUp(self):
        """Set up test fixtures with a temporary cache file."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        self.temp_file.write('{}')
        self.temp_file.close()
        
        from file_mapping import FileMapping
        self.mapping = FileMapping(cache_file=self.temp_file.name, batch_size=3)
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_set_and_get_classification(self):
        """Test setting and getting a classification."""
        self.mapping.set_classification(
            file_id='test123',
            file_name='test.pdf',
            company='chase',
            statement_type='bank statement',
            account_info='1234'
        )
        
        result = self.mapping.get_classification('test123', 'test.pdf')
        self.assertEqual(result, ('chase', 'bank statement', '1234'))
    
    def test_batch_save(self):
        """Test that batch saving works (saves every N files)."""
        # Set batch_size to 3, so it should save after 3 entries
        for i in range(2):
            self.mapping.set_classification(
                file_id=f'file{i}',
                file_name=f'test{i}.pdf',
                company='chase',
                statement_type='bank statement',
                account_info=str(i)
            )
        
        # Check pending saves count
        self.assertEqual(self.mapping._pending_saves, 2)
        
        # Add one more to trigger save
        self.mapping.set_classification(
            file_id='file2',
            file_name='test2.pdf',
            company='chase',
            statement_type='bank statement',
            account_info='2'
        )
        
        # After batch save, pending should be 0
        self.assertEqual(self.mapping._pending_saves, 0)
    
    def test_flush(self):
        """Test manual flush of pending saves."""
        self.mapping.set_classification(
            file_id='flush_test',
            file_name='flush.pdf',
            company='wells fargo',
            statement_type='credit card statement',
            account_info='5678'
        )
        
        self.assertEqual(self.mapping._pending_saves, 1)
        self.mapping.flush()
        self.assertEqual(self.mapping._pending_saves, 0)
    
    def test_thread_safe_mode(self):
        """Test enabling thread-safe mode."""
        self.assertIsNone(self.mapping._lock)
        self.mapping.set_thread_safe()
        self.assertIsNotNone(self.mapping._lock)
    
    def test_cache_stats(self):
        """Test cache statistics."""
        self.mapping.set_classification(
            file_id='stats1',
            file_name='stats1.pdf',
            company='amex',
            statement_type='credit card statement',
            account_info='9999',
            force_save=True
        )
        
        stats = self.mapping.get_cache_stats()
        self.assertEqual(stats['total_cached_files'], 1)
        self.assertEqual(stats['classified_files'], 1)
        self.assertEqual(stats['unclassified_files'], 0)


class TestParallelProcessing(unittest.TestCase):
    """Test cases for parallel processing functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch.object(GoogleDriveOrganizer, 'authenticate'):
            self.organizer = GoogleDriveOrganizer(workers=2)
            self.organizer.service = Mock()
            self.organizer.creds = Mock()
    
    def test_thread_local_service(self):
        """Test that thread-local services are created."""
        with patch('main.build') as mock_build:
            mock_build.return_value = Mock()
            
            # Get service twice - should create one per call in different threads
            service1 = self.organizer.get_thread_service()
            self.assertIsNotNone(service1)
    
    def test_prefetch_folders(self):
        """Test pre-fetching destination folders."""
        mock_response = {
            'files': [
                {'id': 'folder1', 'name': 'Chase Freedom'},
                {'id': 'folder2', 'name': 'Schwab Checking'}
            ]
        }
        self.organizer.service.files().list().execute.return_value = mock_response
        
        folders = self.organizer.prefetch_destination_folders('dest_id')
        
        self.assertEqual(len(folders), 2)
        self.assertEqual(self.organizer._dest_folders_cache, folders)
        self.assertEqual(len(self.organizer._folder_info_cache), 2)
    
    def test_cached_folder_info(self):
        """Test cached folder info retrieval."""
        # Pre-populate cache
        self.organizer._folder_info_cache['cached_id'] = {'id': 'cached_id', 'name': 'Cached Folder'}
        
        # Should return from cache without API call
        result = self.organizer.get_cached_folder_info('cached_id')
        self.assertEqual(result['name'], 'Cached Folder')


if __name__ == '__main__':
    unittest.main()
