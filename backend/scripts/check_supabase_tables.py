#!/usr/bin/env python
"""
Supabase Tables Check Script

This script checks if the necessary tables exist in Supabase for the FastAPI Connect application.

Usage:
    python check_supabase_tables.py
"""

import os
import sys
from pathlib import Path
import logging

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
    level=logging.INFO,
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
        return False

def check_table_exists(table_name):
    """Check if a table exists by trying to fetch data from it."""
    logger.info(f"Checking if table '{table_name}' exists...")
    
    try:
        # Try to fetch metadata about the table (limit=0 means we don't actually fetch any rows)
        database_service = supabase.get_database_service()
        response = database_service._make_request(
            method="GET",
            endpoint=f"/rest/v1/{table_name}",
            params={"limit": 0},
            is_admin=True,
        )
        
        # If we get a 200 response, the table exists
        logger.info(f"✅ Table '{table_name}' exists")
        return True
    except Exception as e:
        # If we get a 404 response, the table doesn't exist
        logger.error(f"❌ Table '{table_name}' does not exist or is not accessible")
        logger.debug(f"Error details: {str(e)}")
        return False

def main():
    """Main function to check Supabase tables."""
    logger.info("Checking Supabase tables...")
    
    # Check Supabase connection
    if not check_supabase_connection():
        logger.error("Failed to connect to Supabase. Cannot continue.")
        sys.exit(1)
    
    # Check tables
    user_table_exists = check_table_exists("user")
    item_table_exists = check_table_exists("item")
    
    if user_table_exists and item_table_exists:
        logger.info("✅ All required tables exist in Supabase")
        sys.exit(0)
    elif not user_table_exists and not item_table_exists:
        logger.error("❌ No required tables exist in Supabase")
        logger.info("Please run the SQL setup script in the Supabase SQL Editor")
        logger.info("The script is located at: backend/scripts/supabase_setup.sql")
        sys.exit(1)
    else:
        logger.warning("⚠️ Some tables exist, but not all required tables")
        if not user_table_exists:
            logger.error("❌ Table 'user' does not exist")
        if not item_table_exists:
            logger.error("❌ Table 'item' does not exist")
        logger.info("Please run the SQL setup script in the Supabase SQL Editor")
        logger.info("The script is located at: backend/scripts/supabase_setup.sql")
        sys.exit(1)

if __name__ == "__main__":
    main()
