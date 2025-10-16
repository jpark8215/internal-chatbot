#!/bin/bash

# Enhanced Feedback System Database Migration Script
# This script runs the database migration for the enhanced feedback system

set -e  # Exit on any error

echo "Enhanced Feedback System Database Migration"
echo "=========================================="

# Check if required files exist
REQUIRED_FILES=(
    "enhanced_feedback_schema.sql"
    "optimize_feedback_indexes.sql"
    "migrate_feedback_schema.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Required file missing: $file"
        exit 1
    fi
done

echo "✅ All required files found"

# Check if Python is available
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Python not found. Please install Python to run the migration."
    exit 1
fi

echo "✅ Python found: $PYTHON_CMD"

# Run syntax validation if available
if [ -f "test_schema_syntax.py" ]; then
    echo "🔍 Running syntax validation..."
    if $PYTHON_CMD test_schema_syntax.py; then
        echo "✅ Syntax validation passed"
    else
        echo "❌ Syntax validation failed"
        exit 1
    fi
fi

# Check database connection environment variables
if [ -z "$DB_HOST" ] && [ -z "$DATABASE_URL" ]; then
    echo "⚠️  Warning: No database connection environment variables found"
    echo "   Please ensure DB_HOST, DB_NAME, DB_USER, DB_PASSWORD are set"
    echo "   Or set DATABASE_URL for connection string"
    echo ""
    echo "   Example:"
    echo "   export DB_HOST=localhost"
    echo "   export DB_NAME=rag_db"
    echo "   export DB_USER=postgres"
    echo "   export DB_PASSWORD=your_password"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Run the migration
echo "🚀 Starting database migration..."
echo "   This will:"
echo "   - Create backup of existing data"
echo "   - Add new columns to user_feedback table"
echo "   - Create new tables for enhanced functionality"
echo "   - Add indexes for optimal performance"
echo "   - Create views and functions for analytics"
echo ""

read -p "Proceed with migration? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration cancelled"
    exit 0
fi

# Run the Python migration script
echo "📊 Running migration script..."
if $PYTHON_CMD migrate_feedback_schema.py; then
    echo ""
    echo "🎉 Migration completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Update your application code to use new feedback fields"
    echo "2. Configure alert thresholds in feedback_system_config table"
    echo "3. Set up automated maintenance scheduling"
    echo "4. Test the new feedback interface"
    echo ""
    echo "For more information, see README_enhanced_feedback.md"
else
    echo ""
    echo "❌ Migration failed!"
    echo "Please check the error messages above and try again."
    echo "If the issue persists, you can try manual migration:"
    echo "  psql -d your_database -f enhanced_feedback_schema.sql"
    echo "  psql -d your_database -f optimize_feedback_indexes.sql"
    exit 1
fi