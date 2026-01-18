# Product Requirements Document (PRD)
## Antifragile Google Drive Tools

**Version:** 1.0  
**Date:** January 2025  
**Repository:** https://github.com/Akibalogh/antifragile-gdrive-tools

---

## 1. Executive Summary

### 1.1 Product Overview
Antifragile Google Drive Tools is a Python-based automation system that intelligently organizes financial statements stored in Google Drive. The tool automatically classifies PDF statements by company and account type, extracts account numbers, and organizes them into a structured folder hierarchy.

### 1.2 Problem Statement
Managing financial statements in Google Drive becomes increasingly difficult as the volume grows:
- Statements arrive with generic filenames (e.g., "statement.pdf", "2024-01-15.pdf")
- Files are scattered across monthly folders without organization
- Manual classification and organization is time-consuming and error-prone
- Finding specific statements requires searching through hundreds of files
- No consistent naming convention for account-based organization

### 1.3 Solution
An automated system that:
- Reads PDF content to identify companies and account numbers
- Uses pattern matching to classify 190+ financial institutions
- Extracts account numbers from filenames and PDF content
- Organizes files into account-based folders with consistent naming
- Handles duplicates intelligently
- Processes files incrementally (only new files)

### 1.4 Success Metrics
- **911 files processed** with 893 successfully organized
- **99%+ classification accuracy** for known companies
- **25+ account types** automatically recognized
- **98% organization rate** (893 out of 911 files)
- **Zero errors** in latest run (January 2026)
- **Zero manual intervention** required after initial setup

### 1.5 Performance Optimizations (January 2026)
| Optimization | Impact |
|-------------|--------|
| Skip PDF download on cache hit | ~90% bandwidth reduction on subsequent runs |
| Pre-fetch destination folders | Single API call vs. one per file |
| Batch cache saves | Every 50 files instead of every file |
| Cached folder lookups | Eliminates redundant API calls |

---

## 2. Product Goals

### 2.1 Primary Goals
1. **Automate Statement Organization**: Eliminate manual sorting and filing
2. **Improve Discoverability**: Make statements easy to find by account
3. **Maintain Consistency**: Enforce standard naming conventions
4. **Handle Scale**: Process hundreds of files efficiently
5. **Prevent Duplicates**: Avoid copying files that already exist

### 2.2 Secondary Goals
1. **Support Multiple Account Types**: Banks, credit cards, investments, loans, utilities
2. **Extensibility**: Easy to add new companies and patterns
3. **Safety**: Dry-run mode and backups before making changes
4. **Performance**: Parallel processing for speed
5. **Reliability**: Graceful error handling and recovery

---

## 3. User Personas

### 3.1 Primary User: Financial Manager
- **Role**: Individual managing personal/business finances
- **Needs**: 
  - Quick access to specific account statements
  - Consistent organization without manual work
  - Confidence that files are properly classified
- **Pain Points**:
  - Time spent manually organizing statements
  - Difficulty finding specific statements
  - Inconsistent folder naming

### 3.2 Secondary User: Accountant/Bookkeeper
- **Role**: Professional managing client finances
- **Needs**:
  - Reliable automated organization
  - Audit trail of file movements
  - Ability to verify classifications
- **Pain Points**:
  - Manual file organization is billable but low-value work
  - Risk of misplacing important documents

---

## 4. Features & Requirements

### 4.1 Core Features

#### 4.1.1 Intelligent PDF Classification
**Priority**: P0 (Critical)

**Description**: Automatically identify company and statement type from PDF content

**Requirements**:
- Read text content from PDF files
- Match against 190+ company patterns
- Identify statement types (bank, credit card, investment, loan, utility)
- Extract account numbers from filenames and content
- Handle generic filenames (e.g., "statement.pdf")

**Acceptance Criteria**:
- ✅ 99%+ accuracy for known companies
- ✅ Handles files with no company name in filename
- ✅ Extracts account numbers reliably
- ✅ Caches results to avoid re-reading PDFs

#### 4.1.2 Account-Based Folder Organization
**Priority**: P0 (Critical)

**Description**: Organize files into folders named by company and account number

**Requirements**:
- Create folders with format: `[Company] [Type] -[Account Number]`
- Example: "Chase Freedom Card -64649"
- Support 5-digit account number format for consistency
- Match files to existing folders when possible
- Create new folders when needed

**Acceptance Criteria**:
- ✅ Consistent naming convention across all accounts
- ✅ Smart matching to existing folders
- ✅ Automatic folder creation
- ✅ Handles subfolders recursively

#### 4.1.3 Duplicate Detection & Handling
**Priority**: P1 (High)

**Description**: Prevent duplicate files and handle existing duplicates intelligently

**Requirements**:
- Detect exact filename matches
- Detect content duplicates (MD5 hash)
- Detect similar filenames
- Multiple handling strategies: skip, rename, force
- Analysis mode to report existing duplicates

**Acceptance Criteria**:
- ✅ Identifies all types of duplicates
- ✅ Configurable handling strategy
- ✅ Prevents accidental duplicates
- ✅ Reports duplicate statistics

#### 4.1.4 Incremental Processing
**Priority**: P1 (High)

**Description**: Only process new files, skip already organized ones

**Requirements**:
- Track processed files in cache
- Check cache before processing
- Skip files already in destination
- Support cache clearing and export

**Acceptance Criteria**:
- ✅ Processes only new files
- ✅ Cache persists between runs
- ✅ Cache can be cleared/exported
- ✅ Fast execution on subsequent runs

### 4.2 Advanced Features

#### 4.2.1 Parallel Processing
**Priority**: P1 (High)

**Description**: Process multiple files simultaneously for speed

**Requirements**:
- Configurable worker count (default: 4)
- Thread-safe caching
- Progress tracking across workers
- Respect Google Drive API rate limits

**Acceptance Criteria**:
- ✅ 4x speed improvement with 4 workers
- ✅ Configurable worker count
- ✅ No race conditions
- ✅ Respects API limits

#### 4.2.2 Folder Renaming
**Priority**: P2 (Medium)

**Description**: Batch rename folders to add account numbers

**Requirements**:
- Rename multiple folders in one operation
- Add account numbers to folder names
- Support dry-run mode
- Create backup before renaming

**Acceptance Criteria**:
- ✅ Batch rename with progress tracking
- ✅ Dry-run preview
- ✅ Backup creation
- ✅ Rollback capability

#### 4.2.3 Backup & Recovery
**Priority**: P2 (Medium)

**Description**: Create backups of folder structure before changes

**Requirements**:
- Export folder structure to JSON
- Include folder IDs, names, timestamps
- Support restoration from backup
- Automatic backup before major operations

**Acceptance Criteria**:
- ✅ Complete folder structure backup
- ✅ Timestamped backup files
- ✅ Human-readable format
- ✅ Can be used for recovery

### 4.3 Safety Features

#### 4.3.1 Dry Run Mode
**Priority**: P0 (Critical)

**Description**: Preview all changes without making them

**Requirements**:
- Show what would be copied/moved
- Display folder creation plans
- Show rename operations
- No actual changes to Google Drive

**Acceptance Criteria**:
- ✅ Shows all planned operations
- ✅ No side effects
- ✅ Accurate preview
- ✅ Can be run multiple times safely

#### 4.3.2 Error Handling
**Priority**: P0 (Critical)

**Description**: Gracefully handle errors without stopping execution

**Requirements**:
- Continue processing on individual file errors
- Log all errors with context
- Report error statistics
- Handle API rate limits
- Handle corrupted PDFs

**Acceptance Criteria**:
- ✅ No crashes on errors
- ✅ Complete error logging
- ✅ Error statistics reported
- ✅ Graceful degradation

---

## 5. Technical Requirements

### 5.1 Technology Stack
- **Language**: Python 3.7+
- **APIs**: Google Drive API v3
- **Libraries**:
  - `google-api-python-client` - Google Drive API
  - `PyPDF2` - PDF text extraction
  - `click` - CLI interface
  - `rich` - Terminal UI and formatting
  - `python-dotenv` - Environment configuration

### 5.2 Authentication
- OAuth 2.0 with Google Drive API
- Scope: `https://www.googleapis.com/auth/drive` (full access)
- Token stored in `token.json` (gitignored)
- Credentials in `credentials.json` (gitignored)

### 5.3 Performance Requirements
- Process 100+ files in under 10 minutes
- Cache hit rate > 80% on subsequent runs
- Support up to 8 parallel workers
- Handle folders with 1000+ files

### 5.4 Data Requirements
- Source folder: "Monthly Statements" (or custom)
- Destination folder: "Statements by Account" (or custom)
- Cache file: `file_mapping_cache.json`
- Backup files: `folder_backup_YYYYMMDD_HHMMSS.json`

---

## 6. User Stories

### 6.1 As a financial manager, I want to...
- **US-1**: Automatically organize new statements as they arrive
  - **Given**: New PDF files in Monthly Statements folder
  - **When**: I run the organizer
  - **Then**: Files are automatically classified and moved to account folders

- **US-2**: Find statements quickly by account
  - **Given**: Organized folder structure
  - **When**: I need a specific statement
  - **Then**: I can navigate directly to the account folder

- **US-3**: Preview changes before applying them
  - **Given**: Files to be organized
  - **When**: I run with --dry-run
  - **Then**: I see exactly what will happen without changes

- **US-4**: Handle duplicates intelligently
  - **Given**: Files that may already exist
  - **When**: Processing runs
  - **Then**: Duplicates are detected and handled per my preference

### 6.2 As a developer, I want to...
- **US-5**: Add new company patterns easily
  - **Given**: A new financial institution
  - **When**: I add patterns to config.py
  - **Then**: The tool recognizes the new company

- **US-6**: Extend functionality without breaking existing features
  - **Given**: A modular codebase
  - **When**: I add new features
  - **Then**: Existing functionality continues to work

---

## 7. Non-Functional Requirements

### 7.1 Reliability
- **Uptime**: N/A (local tool)
- **Error Rate**: < 1% of files fail to process
- **Data Integrity**: No files lost or corrupted
- **Recovery**: Can recover from backups

### 7.2 Performance
- **Throughput**: 50-100 files per minute (with 4 workers)
- **Latency**: < 1 second per file (cached)
- **Scalability**: Handles 1000+ files per run
- **Resource Usage**: < 4GB RAM, < 1GB disk

### 7.3 Security
- **Credentials**: Never committed to git
- **Tokens**: Stored locally, gitignored
- **API Access**: OAuth 2.0 with minimal required scopes
- **Data Privacy**: All processing local, no external services

### 7.4 Usability
- **CLI Interface**: Clear, intuitive commands
- **Progress Feedback**: Real-time progress bars
- **Error Messages**: Clear, actionable error messages
- **Documentation**: Comprehensive setup and usage docs

### 7.5 Maintainability
- **Code Quality**: Well-structured, documented code
- **Testing**: Unit tests for core functionality
- **Logging**: Comprehensive logging for debugging
- **Configuration**: Externalized in config.py

---

## 8. Out of Scope

The following features are explicitly **not** included in this version:

1. **Web Interface**: CLI-only, no web UI
2. **Multi-User Support**: Single-user tool
3. **Cloud Deployment**: Local execution only
4. **Real-Time Monitoring**: Batch processing only
5. **Statement Parsing**: Classification only, no data extraction
6. **Integration with Accounting Software**: Google Drive only
7. **Mobile App**: Desktop/CLI only
8. **Automated Scheduling**: Manual execution only

---

## 9. Future Considerations

### 9.1 Potential Enhancements
- **OCR Support**: Handle scanned PDFs without text
- **Statement Data Extraction**: Parse amounts, dates, transactions
- **Automated Scheduling**: Cron jobs or scheduled tasks
- **Webhook Integration**: Process files as they arrive
- **Multi-Account Support**: Handle multiple Google accounts
- **Statement Analysis**: Generate spending reports
- **Integration APIs**: Connect to accounting software

### 9.2 Technical Debt
- Improve error messages for better debugging
- Add more comprehensive unit tests
- Optimize PDF reading for large files
- Add retry logic for API failures
- Improve cache invalidation strategy

### 9.3 Threading & Python Version Notes (January 2026)

#### Python 3.9 Issue (RESOLVED)
**Issue**: Python 3.9 + macOS + Google API SSL caused memory corruption crashes with `ThreadPoolExecutor`.

**Root Cause**: The `libssl` library on macOS had thread-safety issues when multiple threads shared SSL connections.

**Resolution**: Upgraded to **Python 3.11** which has improved SSL thread safety. Parallel processing now works correctly with 4 workers.

#### Current Architecture
- **Python 3.11** with `ThreadPoolExecutor` (4 workers default)
- Thread-local Google API service instances per worker
- Thread-safe cache with locking
- Pre-fetched destination folders
- Skip PDF download on cache hit

---

## 10. Success Criteria

### 10.1 Launch Criteria
- ✅ Process 100+ files successfully
- ✅ 99%+ classification accuracy
- ✅ Zero data loss
- ✅ Complete documentation
- ✅ Dry-run mode working

### 10.2 Post-Launch Metrics
- **Adoption**: Regular use (weekly/monthly)
- **Accuracy**: Maintain 99%+ classification rate
- **Performance**: Process 100 files in < 10 minutes
- **Reliability**: < 1% error rate
- **User Satisfaction**: No critical issues reported

---

## 11. Dependencies & Constraints

### 11.1 External Dependencies
- Google Drive API (requires internet connection)
- Python 3.7+ runtime
- Google Cloud Console project with Drive API enabled
- OAuth 2.0 credentials

### 11.2 Constraints
- Google Drive API rate limits (1000 requests/100 seconds/user)
- PDF file format support only
- Single Google account per instance
- Local execution only (no cloud deployment)
- **Sequential processing only** (threading causes SSL crashes on macOS with Python 3.9)

### 11.3 Assumptions
- Users have Google Drive access
- Users can create OAuth credentials
- Files are primarily PDF format
- Source folder structure is known/consistent

---

## 12. Glossary

- **Classification**: Identifying company and statement type from file
- **Account Number**: Last 4-5 digits of account identifier
- **Folder Matching**: Finding existing folders that match a file
- **Duplicate Detection**: Identifying files that already exist
- **Cache**: Stored classification results to avoid re-processing
- **Dry Run**: Preview mode that shows changes without applying them
- **Worker**: Parallel processing thread/process

---

## 13. References

- **Repository**: https://github.com/Akibalogh/antifragile-gdrive-tools
- **Google Drive API**: https://developers.google.com/drive/api
- **Project Completion Summary**: `docs/PROJECT_COMPLETION_SUMMARY.md`
- **Setup Instructions**: `docs/setup_instructions.md`
- **Duplicate Handling Guide**: `docs/DUPLICATE_HANDLING_GUIDE.md`

---

**Document Status**: Active  
**Last Updated**: January 2025  
**Owner**: Antifragile LLC

