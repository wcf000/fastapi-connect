#!/usr/bin/env python
"""
Supabase Tables Setup Script

This script sets up the necessary tables in Supabase for the FastAPI Connect application.
It creates the following tables:
- user
- item

Usage:
    python setup_supabase_tables.py
"""

import os
import sys
from pathlib import Path
import logging
import json
import uuid

print("Script started")

# Configure path to find the app modules
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
sys.path.insert(0, str(backend_dir))
print(f"Added {backend_dir} to sys.path")

# Import the environment file loader
print("Importing environment loader...")
from app.core.utils.sensitive import load_environment_files
print("Environment loader imported")

# Load environment variables
print("Loading environment variables...")
load_environment_files()
print("Environment variables loaded")

# Now import supabase client
print("Importing Supabase client...")
from app.core.third_party_integrations.supabase_home.client import supabase
print("Supabase client imported")

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more verbose output
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
print("Logging configured")

def check_supabase_connection():
    """Check if we can connect to Supabase."""
    print("Checking Supabase connection...")
    try:
        # Try a simple query to check connection
        database_service = supabase.get_database_service()
        print("Got database service")
        
        # Just getting the service doesn't actually connect, so let's try to fetch something
        print("Making test request...")
        response = database_service._make_request(
            method="GET",
            endpoint="/rest/v1/",
            is_admin=True,
        )
        print(f"Response: {response}")
        logger.info(f"✅ Successfully connected to Supabase")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to connect to Supabase: {str(e)}")
        print(f"Exception during connection check: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def create_user_table():
    """Create the user table in Supabase."""
    logger.info("Creating user table...")
    print("Creating user table...")
    
    sql = """
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    
    CREATE TABLE IF NOT EXISTS "user" (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        email TEXT NOT NULL UNIQUE,
        hashed_password TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
        full_name TEXT
    );
    
    -- Set up RLS policies
    ALTER TABLE "user" ENABLE ROW LEVEL SECURITY;
    
    -- Create policy to allow authenticated users to read any user
    DROP POLICY IF EXISTS "Allow authenticated users to read any user" ON "user";
    CREATE POLICY "Allow authenticated users to read any user"
    ON "user"
    FOR SELECT
    TO authenticated
    USING (true);
    
    -- Create policy to allow users to update their own data
    DROP POLICY IF EXISTS "Allow users to update their own data" ON "user";
    CREATE POLICY "Allow users to update their own data"
    ON "user"
    FOR UPDATE
    TO authenticated
    USING (auth.uid()::text = id::text)
    WITH CHECK (auth.uid()::text = id::text);
    """
    
    try:
        database_service = supabase.get_database_service()
        print("Executing SQL for user table...")
        response = database_service._make_request(
            method="POST",
            endpoint="/rest/v1/rpc/exec_sql",
            is_admin=True,
            data={"query": sql}
        )
        print(f"Response: {response}")
        logger.info(f"✅ User table created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create user table: {str(e)}")
        print(f"Exception during user table creation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def create_item_table():
    """Create the item table in Supabase."""
    logger.info("Creating item table...")
    print("Creating item table...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS "item" (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        title TEXT NOT NULL,
        description TEXT,
        owner_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE
    );
    
    -- Set up RLS policies
    ALTER TABLE "item" ENABLE ROW LEVEL SECURITY;
    
    -- Create policy to allow authenticated users to read their own items
    DROP POLICY IF EXISTS "Allow users to read their own items" ON "item";
    CREATE POLICY "Allow users to read their own items"
    ON "item"
    FOR SELECT
    TO authenticated
    USING (auth.uid()::text = owner_id::text);
    
    -- Create policy to allow users to insert their own items
    DROP POLICY IF EXISTS "Allow users to insert their own items" ON "item";
    CREATE POLICY "Allow users to insert their own items"
    ON "item"
    FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid()::text = owner_id::text);
    
    -- Create policy to allow users to update their own items
    DROP POLICY IF EXISTS "Allow users to update their own items" ON "item";
    CREATE POLICY "Allow users to update their own items"
    ON "item"
    FOR UPDATE
    TO authenticated
    USING (auth.uid()::text = owner_id::text)
    WITH CHECK (auth.uid()::text = owner_id::text);
    
    -- Create policy to allow users to delete their own items
    DROP POLICY IF EXISTS "Allow users to delete their own items" ON "item";
    CREATE POLICY "Allow users to delete their own items"
    ON "item"
    FOR DELETE
    TO authenticated
    USING (auth.uid()::text = owner_id::text);
    """
    
    try:
        database_service = supabase.get_database_service()
        print("Executing SQL for item table...")
        response = database_service._make_request(
            method="POST",
            endpoint="/rest/v1/rpc/exec_sql",
            is_admin=True,
            data={"query": sql}
        )
        print(f"Response: {response}")
        logger.info(f"✅ Item table created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create item table: {str(e)}")
        print(f"Exception during item table creation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function to set up Supabase tables."""
    logger.info("Setting up Supabase tables...")
    print("Setting up Supabase tables...")
    
    # Check Supabase connection
    if not check_supabase_connection():
        logger.error("Failed to connect to Supabase. Cannot continue.")
        print("Failed to connect to Supabase. Cannot continue.")
        sys.exit(1)
    
    # Create tables
    success = True
    print("Creating tables...")
    success = create_user_table() and success
    success = create_item_table() and success
    
    if success:
        logger.info("✅ All tables created successfully")
        print("✅ All tables created successfully")
        sys.exit(0)
    else:
        logger.error("❌ Failed to create some tables")
        print("❌ Failed to create some tables")
        sys.exit(1)

if __name__ == "__main__":
    print("Starting main function...")
    main()
