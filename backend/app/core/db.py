from sqlmodel import Session, create_engine, select, SQLModel

from app import crud
from app.core.config import settings
from app.models import User, UserCreate, Item  # Import all models here

# This ensures all SQLModel models are imported and registered with SQLModel
# before creating the database tables.

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db() -> None:
    """
    Initialize the database by creating all tables and creating the first superuser.
    This should be called during application startup.
    """
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    # Create initial data
    with Session(engine) as session:
        # Create first superuser if it doesn't exist
        user = session.exec(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        ).first()
        
        if not user and settings.FIRST_SUPERUSER and settings.FIRST_SUPERUSER_PASSWORD:
            user_in = UserCreate(
                email=settings.FIRST_SUPERUSER,
                password=settings.FIRST_SUPERUSER_PASSWORD,
                is_superuser=True,
                is_active=True,
                full_name="Initial Superuser"
            )
            user = crud.create_user(session=session, user_create=user_in)
            session.commit()
            print("Created initial superuser:", user.email)
