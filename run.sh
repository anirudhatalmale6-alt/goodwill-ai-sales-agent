#!/bin/bash
# Goodwill AI Sales Agent - Run Script

# Initialize database from Excel files
echo "Initializing database..."
python3 -c "from app.database import seed_database; seed_database()"

# Start the server
echo "Starting Goodwill AI Sales Agent..."
echo "Dashboard: http://localhost:8000"
echo ""
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
