#!/usr/bin/env python
"""
Supabase Tables Setup Script (Direct API Approach)

This script sets up the necessary tables in Supabase for the FastAPI Connect application.
It creates the following tables:
- user
- item

Instead of using the exec_sql RPC function, it creates tables directly through the REST API.

Usage:
    python setup_supabase_tables_direct.py
"""

import os
import sys
from pathlib import Path
import logging
import json
import uuid

# Configure path to find the app modules
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent
sys.path.insert(0, str(backend_dir))

# Import the environment file loader
from app.core.utils.sensitive import load_environment_files

# Load environment variables
load_environment_files()

# Now import supabase client
from app.core.third_party_integrations.supabase_home.client import supabase

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def check_supabase_connection():
    """Check if we can connect to Supabase."""
    logger.info("Checking Supabase connection...")
    try:
        # Try a simple query to check connection
        database_service = supabase.get_database_service()
        
        # Just getting the service doesn't actually connect, so let's try to fetch something
        response = database_service._make_request(
            method="GET",
            endpoint="/rest/v1/",
            is_admin=True,
        )
        logger.info(f"✅ Successfully connected to Supabase")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to connect to Supabase: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def check_table_exists(table_name):
    """Check if a table exists in Supabase."""
    logger.info(f"Checking if table '{table_name}' exists...")
    
    # We'll use the Postgres information_schema to check if the table exists
    database_service = supabase.get_database_service()
    
    try:
        # This endpoint allows querying information_schema directly (if permissions allow)
        response = database_service._make_request(
            method="GET",
            endpoint=f"/rest/v1/information_schema/tables",
            is_admin=True,
            params={
                "select": "*",
                "table_schema": "eq.public", 
                "table_name": f"eq.{table_name}"
            }
        )
        
        # If we get any results, the table exists
        exists = len(response) > 0
        logger.info(f"Table '{table_name}' exists: {exists}")
        return exists
    except Exception as e:
        logger.error(f"❌ Error checking if table exists: {str(e)}")
        return False

def create_user_table():
    """Create the user table in Supabase."""
    logger.info("Creating user table...")
    
    if check_table_exists("user"):
        logger.info("User table already exists, skipping creation.")
        return True
    
    database_service = supabase.get_database_service()
    
    # First, create the basic table structure
    try:
        # We'll use the raw REST API to create the table
        # Note: This requires the service role key with appropriate permissions
        logger.info("Creating user table structure...")
        
        # Create uuid extension if it doesn't exist
        response = database_service._make_request(
            method="POST",
            endpoint=f"/rest/v1/",
            is_admin=True,
            headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            data={
                "cmd": "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
            }
        )
        
        # Create the user table
        response = database_service._make_request(
            method="POST",
            endpoint=f"/rest/v1/",
            is_admin=True,
            headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            data={
                "cmd": """
                CREATE TABLE IF NOT EXISTS "user" (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    email TEXT NOT NULL UNIQUE,
                    hashed_password TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
                    full_name TEXT
                );
                """
            }
        )
        
        # Enable RLS on the table
        response = database_service._make_request(
            method="POST",
            endpoint=f"/rest/v1/",
            is_admin=True,
            headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            data={
                "cmd": 'ALTER TABLE "user" ENABLE ROW LEVEL SECURITY;'
            }
        )
        
        # Create policy for read access
        response = database_service._make_request(
            method="POST",
            endpoint=f"/rest/v1/",
            is_admin=True,
            headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            data={
                "cmd": """
                DROP POLICY IF EXISTS "Allow authenticated users to read any user" ON "user";
                CREATE POLICY "Allow authenticated users to read any user"
                ON "user"
                FOR SELECT
                TO authenticated
                USING (true);
                """
            }
        )
        
        # Create policy for update access
        response = database_service._make_request(
            method="POST",
            endpoint=f"/rest/v1/",
            is_admin=True,
            headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            data={
                "cmd": """
                DROP POLICY IF EXISTS "Allow users to update their own data" ON "user";
                CREATE POLICY "Allow users to update their own data"
                ON "user"
                FOR UPDATE
                TO authenticated
                USING (auth.uid()::text = id::text)
                WITH CHECK (auth.uid()::text = id::text);
                """
            }
        )
        
        logger.info(f"✅ User table created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create user table: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def create_item_table():
    """Create the item table in Supabase."""
    logger.info("Creating item table...")
    
    if check_table_exists("item"):
        logger.info("Item table already exists, skipping creation.")
        return True
    
    database_service = supabase.get_database_service()
    
    # First, create the basic table structure
    try:
        # Create the item table
        response = database_service._make_request(
            method="POST",
            endpoint=f"/rest/v1/",
            is_admin=True,
            headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            data={
                "cmd": """
                CREATE TABLE IF NOT EXISTS "item" (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    title TEXT NOT NULL,
                    description TEXT,
                    owner_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE
                );
                """
            }
        )
        
        # Enable RLS on the table
        response = database_service._make_request(
            method="POST",
            endpoint=f"/rest/v1/",
            is_admin=True,
            headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            data={
                "cmd": 'ALTER TABLE "item" ENABLE ROW LEVEL SECURITY;'
            }
        )
        
        # Create policy for read access
        response = database_service._make_request(
            method="POST",
            endpoint=f"/rest/v1/",
            is_admin=True,
            headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            data={
                "cmd": """
                DROP POLICY IF EXISTS "Allow users to read their own items" ON "item";
                CREATE POLICY "Allow users to read their own items"
                ON "item"
                FOR SELECT
                TO authenticated
                USING (auth.uid()::text = owner_id::text);
                """
            }
        )
        
        # Create policy for insert access
        response = database_service._make_request(
            method="POST",
            endpoint=f"/rest/v1/",
            is_admin=True,
            headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            data={
                "cmd": """
                DROP POLICY IF EXISTS "Allow users to insert their own items" ON "item";
                CREATE POLICY "Allow users to insert their own items"
                ON "item"
                FOR INSERT
                TO authenticated
                WITH CHECK (auth.uid()::text = owner_id::text);
                """
            }
        )
        
        # Create policy for update access
        response = database_service._make_request(
            method="POST",
            endpoint=f"/rest/v1/",
            is_admin=True,
            headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            data={
                "cmd": """
                DROP POLICY IF EXISTS "Allow users to update their own items" ON "item";
                CREATE POLICY "Allow users to update their own items"
                ON "item"
                FOR UPDATE
                TO authenticated
                USING (auth.uid()::text = owner_id::text)
                WITH CHECK (auth.uid()::text = owner_id::text);
                """
            }
        )
        
        # Create policy for delete access
        response = database_service._make_request(
            method="POST",
            endpoint=f"/rest/v1/",
            is_admin=True,
            headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            data={
                "cmd": """
                DROP POLICY IF EXISTS "Allow users to delete their own items" ON "item";
                CREATE POLICY "Allow users to delete their own items"
                ON "item"
                FOR DELETE
                TO authenticated
                USING (auth.uid()::text = owner_id::text);
                """
            }
        )
        
        logger.info(f"✅ Item table created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create item table: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function to set up Supabase tables."""
    logger.info("Setting up Supabase tables...")
    
    # Check Supabase connection
    if not check_supabase_connection():
        logger.error("Failed to connect to Supabase. Cannot continue.")
        sys.exit(1)
    
    # Create tables
    success = True
    success = create_user_table() and success
    success = create_item_table() and success
    
    if success:
        logger.info("✅ All tables created successfully")
        sys.exit(0)
    else:
        logger.error("❌ Failed to create some tables")
        sys.exit(1)

if __name__ == "__main__":
    main()
