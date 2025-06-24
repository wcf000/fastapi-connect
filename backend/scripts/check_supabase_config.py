#!/usr/bin/env python
"""
Check Supabase Config

This script checks if the Supabase configuration is correctly loaded from the 
environment variables or config files. It only verifies the presence of the
configuration, not the actual connection to Supabase.

Usage:
    python check_supabase_config.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    # Load environment variables from .env file
    env_file = Path(__file__).parents[2] / '.env'
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(f"Loaded environment from {env_file}")
    else:
        logger.warning(f"Warning: .env file not found at {env_file}")
    
    # Check for required environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    # Print environment variable information
    logger.info("Supabase Configuration Check")
    logger.info("===========================")
    
    # Check SUPABASE_URL
    if supabase_url:
        # Remove trailing slash if present
        if supabase_url.endswith('/'):
            logger.warning(f"SUPABASE_URL has trailing slash which may cause issues: {supabase_url}")
            supabase_url = supabase_url.rstrip('/')
        
        # Check for invalid characters
        if '<' in supabase_url or '>' in supabase_url:
            logger.error(f"SUPABASE_URL contains invalid characters: {supabase_url}")
            logger.error("Fix this by removing '<' and '>' characters")
        else:
            logger.info(f"✅ SUPABASE_URL: {supabase_url}")
    else:
        logger.error("❌ SUPABASE_URL is not set")
    
    # Check SUPABASE_ANON_KEY
    if supabase_key:
        # Check if it looks like a JWT token
        if supabase_key.count('.') != 2:
            logger.warning(f"SUPABASE_ANON_KEY doesn't look like a valid JWT token (should have 2 dots)")
        
        # Truncate key for display
        display_key = f"{supabase_key[:10]}...{supabase_key[-5:]}" if len(supabase_key) > 20 else supabase_key
        logger.info(f"✅ SUPABASE_ANON_KEY: {display_key}")
    else:
        logger.error("❌ SUPABASE_ANON_KEY is not set")
    
    # Check SUPABASE_SERVICE_ROLE_KEY
    if supabase_service_key:
        # Check if it looks like a JWT token
        if supabase_service_key.count('.') != 2:
            logger.warning(f"SUPABASE_SERVICE_ROLE_KEY doesn't look like a valid JWT token (should have 2 dots)")
        
        # Truncate key for display
        display_key = f"{supabase_service_key[:10]}...{supabase_service_key[-5:]}" if len(supabase_service_key) > 20 else supabase_service_key
        logger.info(f"✅ SUPABASE_SERVICE_ROLE_KEY: {display_key}")
    else:
        logger.warning("⚠️ SUPABASE_SERVICE_ROLE_KEY is not set (optional for some operations)")
    
    # Overall status
    if supabase_url and supabase_key:
        logger.info("✅ Basic Supabase configuration is present")
        return True
    else:
        logger.error("❌ Required Supabase configuration is missing")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
