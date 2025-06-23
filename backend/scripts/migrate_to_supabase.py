#!/usr/bin/env python
"""
PostgreSQL to Supabase Migration Script

This script migrates data from PostgreSQL to Supabase.
It reads data from the PostgreSQL database and writes it to Supabase.

Usage:
    python migrate_to_supabase.py
"""

import os
import sys
import logging
import json
from datetime import datetime, date

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Custom JSON encoder to handle date and datetime objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

def check_env_vars():
    """Check if the necessary environment variables are set."""
    required_vars = [
        'SUPABASE_URL', 'SUPABASE_ANON_KEY', 
        'POSTGRES_SERVER', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB'
    ]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Please set these environment variables and try again.")
        return False
    
    logger.info("✅ Environment variables check passed")
    return True

def get_postgres_connection():
    """Get a connection to the PostgreSQL database."""
    import sqlalchemy
    from sqlalchemy import create_engine
    from app.core.config import settings
    
    try:
        engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
        conn = engine.connect()
        logger.info("✅ Connected to PostgreSQL database")
        return conn
    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL database: {e}")
        return None

def get_supabase_client():
    """Get a Supabase client."""
    try:
        from app.core.third_party_integrations.supabase_home.client import supabase
        logger.info("✅ Connected to Supabase")
        return supabase
    except Exception as e:
        logger.error(f"❌ Failed to connect to Supabase: {e}")
        return None

def get_postgres_tables(conn):
    """Get a list of tables in the PostgreSQL database."""
    try:
        from sqlalchemy import inspect
        inspector = inspect(conn.engine)
        tables = inspector.get_table_names()
        logger.info(f"Found {len(tables)} tables in PostgreSQL: {', '.join(tables)}")
        return tables
    except Exception as e:
        logger.error(f"❌ Failed to get PostgreSQL tables: {e}")
        return []

def migrate_table(table_name, conn, supabase):
    """Migrate data from a PostgreSQL table to Supabase."""
    try:
        # Get data from PostgreSQL
        query = f"SELECT * FROM {table_name}"
        result = conn.execute(query)
        rows = [dict(row) for row in result]
        
        if not rows:
            logger.info(f"Table {table_name} is empty, skipping")
            return True
        
        logger.info(f"Migrating {len(rows)} rows from table {table_name}")
        
        # Convert rows to JSON
        json_rows = json.dumps(rows, cls=CustomJSONEncoder)
        rows = json.loads(json_rows)
        
        # Insert data into Supabase
        db_service = supabase.get_database_service()
        
        # Check if table exists in Supabase
        try:
            db_service.execute_sql(f"SELECT * FROM {table_name} LIMIT 1")
            table_exists = True
        except:
            table_exists = False
        
        if not table_exists:
            logger.warning(f"Table {table_name} does not exist in Supabase. Please create it first.")
            return False
        
        # Insert data in batches
        batch_size = 100
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            result = db_service.insert_data(table_name, batch)
            logger.info(f"Inserted batch {i//batch_size + 1}/{(len(rows)-1)//batch_size + 1} into {table_name}")
        
        logger.info(f"✅ Successfully migrated table {table_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to migrate table {table_name}: {e}")
        return False

def migrate_all_tables():
    """Migrate all tables from PostgreSQL to Supabase."""
    if not check_env_vars():
        return False
    
    # Connect to PostgreSQL
    conn = get_postgres_connection()
    if not conn:
        return False
    
    # Connect to Supabase
    supabase = get_supabase_client()
    if not supabase:
        return False
    
    # Get tables
    tables = get_postgres_tables(conn)
    if not tables:
        return False
    
    # Migrate each table
    results = {}
    for table in tables:
        results[table] = migrate_table(table, conn, supabase)
    
    # Check if all migrations were successful
    all_successful = all(results.values())
    
    if all_successful:
        logger.info("✅ All tables migrated successfully!")
    else:
        failed_tables = [name for name, success in results.items() if not success]
        logger.error(f"❌ Failed to migrate tables: {', '.join(failed_tables)}")
    
    # Close connections
    conn.close()
    
    return all_successful

if __name__ == "__main__":
    logger.info("Starting PostgreSQL to Supabase migration...")
    success = migrate_all_tables()
    
    if success:
        logger.info("Migration completed successfully!")
        sys.exit(0)
    else:
        logger.error("Migration failed. Check the logs for details.")
        sys.exit(1)
