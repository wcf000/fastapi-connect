import logging
import os
import time
from typing import Any

from sqlalchemy import Engine, text
from sqlmodel import Session, select
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

from app.core.db import engine, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


def wait_for_db() -> None:
    """Wait for the database to be available."""
    logger.info("Waiting for database to be available...")
    for _ in range(max_tries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database is available!")
            return
        except Exception as e:
            logger.warning(f"Database is not ready yet: {e}")
            time.sleep(wait_seconds)
    raise Exception(f"Database not available after {max_tries} attempts")


def init() -> None:
    """Initialize the database."""
    logger.info("Initializing database...")
    try:
        # Wait for the database to be available
        wait_for_db()
        
        # Initialize the database (create tables, etc.)
        init_db()
        
        # Verify the database is accessible
        with Session(engine) as session:
            # Check if the user table exists
            result = session.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = 'user'
                    );
                    """
                )
            )
            table_exists = result.scalar()
            
            if not table_exists:
                logger.warning("User table does not exist after initialization")
                # Try to create tables again
                from sqlmodel import SQLModel
                SQLModel.metadata.create_all(engine)
                logger.info("Created database tables")
            else:
                logger.info("Database tables exist")
                
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


def main() -> None:
    logger.info("Starting backend pre-start")
    init()
    logger.info("Backend pre-start complete")


if __name__ == "__main__":
    main()
