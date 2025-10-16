@echo off
REM Enhanced Feedback System Database Migration Script for Windows
REM This script runs the database migration for the enhanced feedback system

setlocal enabledelayedexpansion

echo Enhanced Feedback System Database Migration
echo ==========================================

REM Check if required files exist
set "REQUIRED_FILES=enhanced_feedback_schema.sql optimize_feedback_indexes.sql migrate_feedback_schema.py"

for %%f in (%REQUIRED_FILES%) do (
    if not exist "%%f" (
        echo ❌ Required file missing: %%f
        exit /b 1
    )
)

echo ✅ All required files found

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    echo ✅ Python found: python
) else (
    python3 --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=python3"
        echo ✅ Python found: python3
    ) else (
        echo ❌ Python not found. Please install Python to run the migration.
        exit /b 1
    )
)

REM Run syntax validation if available
if exist "test_schema_syntax.py" (
    echo 🔍 Running syntax validation...
    %PYTHON_CMD% test_schema_syntax.py
    if !errorlevel! neq 0 (
        echo ❌ Syntax validation failed
        exit /b 1
    )
    echo ✅ Syntax validation passed
)

REM Check database connection environment variables
if "%DB_HOST%"=="" if "%DATABASE_URL%"=="" (
    echo ⚠️  Warning: No database connection environment variables found
    echo    Please ensure DB_HOST, DB_NAME, DB_USER, DB_PASSWORD are set
    echo    Or set DATABASE_URL for connection string
    echo.
    echo    Example:
    echo    set DB_HOST=localhost
    echo    set DB_NAME=rag_db
    echo    set DB_USER=postgres
    echo    set DB_PASSWORD=your_password
    echo.
    set /p "continue=Continue anyway? (y/N): "
    if /i not "!continue!"=="y" (
        exit /b 1
    )
)

REM Run the migration
echo 🚀 Starting database migration...
echo    This will:
echo    - Create backup of existing data
echo    - Add new columns to user_feedback table
echo    - Create new tables for enhanced functionality
echo    - Add indexes for optimal performance
echo    - Create views and functions for analytics
echo.

set /p "proceed=Proceed with migration? (y/N): "
if /i not "%proceed%"=="y" (
    echo Migration cancelled
    exit /b 0
)

REM Run the Python migration script
echo 📊 Running migration script...
%PYTHON_CMD% migrate_feedback_schema.py

if %errorlevel% equ 0 (
    echo.
    echo 🎉 Migration completed successfully!
    echo.
    echo Next steps:
    echo 1. Update your application code to use new feedback fields
    echo 2. Configure alert thresholds in feedback_system_config table
    echo 3. Set up automated maintenance scheduling
    echo 4. Test the new feedback interface
    echo.
    echo For more information, see README_enhanced_feedback.md
) else (
    echo.
    echo ❌ Migration failed!
    echo Please check the error messages above and try again.
    echo If the issue persists, you can try manual migration:
    echo   psql -d your_database -f enhanced_feedback_schema.sql
    echo   psql -d your_database -f optimize_feedback_indexes.sql
    exit /b 1
)

pause