import logging
import os
from typing import Any

from sqlalchemy import text
from sqlmodel import Session

from app.core.db import engine, init_db
from app.core.config import settings
from app.models import User
from app.crud import create_user
from app.schemas.user import UserCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ensure_admin_user() -> None:
    """Ensure the admin user exists in the database."""
    logger.info("Ensuring admin user exists...")
    
    with Session(engine) as session:
        # Check if admin user exists
        result = session.execute(
            text("SELECT EXISTS (SELECT 1 FROM \"user\" WHERE email = :email)"),
            {"email": settings.FIRST_SUPERUSER}
        )
        admin_exists = result.scalar()
        
        if not admin_exists and settings.FIRST_SUPERUSER and settings.FIRST_SUPERUSER_PASSWORD:
            logger.info("Creating initial admin user...")
            user_in = UserCreate(
                email=settings.FIRST_SUPERUSER,
                password=settings.FIRST_SUPERUSER_PASSWORD,
                is_superuser=True,
                is_active=True,
                full_name="Admin User"
            )
            create_user(session=session, user_create=user_in)
            session.commit()
            logger.info(f"Created admin user: {settings.FIRST_SUPERUSER}")
        else:
            logger.info("Admin user already exists")


def main() -> None:
    logger.info("Starting initial data setup...")
    
    # Initialize the database (create tables, etc.)
    init_db()
    
    # Ensure admin user exists
    ensure_admin_user()
    
    logger.info("Initial data setup complete")


if __name__ == "__main__":
    main()
