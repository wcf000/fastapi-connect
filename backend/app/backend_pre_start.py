import logging
import os

from sqlalchemy import Engine
from sqlmodel import Session, select
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

from app.core.db import engine
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
def init(db_engine: Engine) -> None:
    try:
        with Session(db_engine) as session:
            # Try to create session to check if DB is awake
            session.exec(select(1))
    except Exception as e:
        logger.error(e)
        raise e


def init_supabase() -> None:
    """Initialize and check Supabase connection"""
    try:
        from app.core.third_party_integrations.supabase_home.init import get_supabase_client
        from app.core.third_party_integrations.supabase_home.tests._verify_supabase_connection import run_verification

        logger.info("Verifying Supabase connection...")
        success = run_verification()
        if not success:
            logger.error("Supabase connection verification failed!")
            raise RuntimeError("Failed to connect to Supabase")
        logger.info("Supabase connection verified successfully")
    except Exception as e:
        logger.error(f"Error connecting to Supabase: {e}")
        raise e


def main() -> None:
    logger.info("Initializing service")

    # Determine which database to use
    supabase_url = getattr(settings, "SUPABASE_URL", "") or os.getenv("SUPABASE_URL", "")
    supabase_key = getattr(settings, "SUPABASE_ANON_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")

    if supabase_url.strip() and supabase_key.strip():
        logger.info("Using Supabase backend")
        init_supabase()
    else:
        logger.info("Using PostgreSQL backend")
        init(engine)

    logger.info("Service finished initializing")


if __name__ == "__main__":
    main()
