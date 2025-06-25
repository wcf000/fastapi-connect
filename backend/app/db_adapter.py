"""
Database adapter to allow the application to use either PostgreSQL (SQLModel) or Supabase.
This module provides a consistent interface for CRUD operations, regardless of the backend database.
"""

import os
from typing import Union, Any, Dict, List, Optional, Callable, Awaitable, TypeVar, Generic, cast
import uuid
import logging
from fastapi import Depends, Request

from sqlmodel import Session

# Import both CRUD implementations
import app.crud as sql_crud
import app.supabase_crud as supabase_crud
from app.models import User, Item, ItemCreate, UserCreate, UserUpdate

# Setup logging
logger = logging.getLogger(__name__)

# Type variable for generics
T = TypeVar('T')

def get_crud_implementation():
    """
    Determine which CRUD implementation to use based on environment variables.
    
    Returns:
        Module: Either sql_crud or supabase_crud
    """
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "")
    postgres_server = os.getenv("POSTGRES_SERVER", "")
    postgres_user = os.getenv("POSTGRES_USER", "")
    
    # Check for Supabase configuration
    if supabase_url.strip() and supabase_key.strip():
        logger.info("Using Supabase for database operations")
        return supabase_crud
    # Check for PostgreSQL configuration
    elif postgres_server.strip() and postgres_user.strip():
        logger.info("Using PostgreSQL for database operations")
        return sql_crud
    else:
        # Default to PostgreSQL for backward compatibility
        logger.warning("No database configuration found, defaulting to PostgreSQL")
        return sql_crud

# Get the appropriate CRUD implementation based on configuration
_crud = get_crud_implementation()

# Re-export functions from the selected CRUD implementation
# User operations
async def create_user(*, session: Optional[Session] = None, user_create: UserCreate) -> User:
    """Create a new user using the appropriate database backend."""
    if isinstance(_crud, supabase_crud.__class__):
        # Supabase doesn't need session
        return await _crud.create_user(user_create=user_create)
    else:
        # SQLModel needs session
        if session is None:
            raise ValueError("Session is required for PostgreSQL operations")
        return await _crud.create_user(session=session, user_create=user_create)

async def get_user(*, session: Optional[Session] = None, user_id: uuid.UUID) -> Optional[User]:
    """Get a user by ID using the appropriate database backend."""
    if isinstance(_crud, supabase_crud.__class__):
        return await _crud.get_user(user_id=user_id)
    else:
        if session is None:
            raise ValueError("Session is required for PostgreSQL operations")
        return await _crud.get_user(session=session, user_id=user_id)

async def get_user_by_email(*, session: Optional[Session] = None, email: str) -> Optional[User]:
    """Get a user by email using the appropriate database backend."""
    if isinstance(_crud, supabase_crud.__class__):
        return await _crud.get_user_by_email(email=email)
    else:
        if session is None:
            raise ValueError("Session is required for PostgreSQL operations")
        return await _crud.get_user_by_email(session=session, email=email)

async def authenticate(*, session: Optional[Session] = None, email: str, password: str) -> Optional[User]:
    """Authenticate a user using the appropriate database backend."""
    if isinstance(_crud, supabase_crud.__class__):
        return await _crud.authenticate(email=email, password=password)
    else:
        if session is None:
            raise ValueError("Session is required for PostgreSQL operations")
        return await _crud.authenticate(session=session, email=email, password=password)

async def update_user(*, session: Optional[Session] = None, db_user: Optional[User] = None, 
                   user_id: Optional[uuid.UUID] = None, user_in: UserUpdate) -> User:
    """Update a user using the appropriate database backend."""
    if isinstance(_crud, supabase_crud.__class__):
        return await _crud.update_user(user_id=user_id, user_in=user_in)
    else:
        if session is None or db_user is None:
            raise ValueError("Session and db_user are required for PostgreSQL operations")
        return await _crud.update_user(session=session, db_user=db_user, user_in=user_in)

async def delete_user(*, session: Optional[Session] = None, user: Optional[User] = None,
                   user_id: Optional[uuid.UUID] = None) -> None:
    """Delete a user using the appropriate database backend."""
    if isinstance(_crud, supabase_crud.__class__):
        return await _crud.delete_user(user_id=user_id)
    else:
        if session is None or user is None:
            raise ValueError("Session and user are required for PostgreSQL operations")
        return await _crud.delete_user(session=session, user=user)

# Item operations
async def create_item(*, session: Optional[Session] = None, item_in: ItemCreate, 
                    owner_id: uuid.UUID) -> Item:
    """Create a new item using the appropriate database backend."""
    logger = logging.getLogger(__name__)
    logger.info(f"Creating item using {'Supabase' if isinstance(_crud, type(supabase_crud)) else 'PostgreSQL'} backend")
    
    try:
        if isinstance(_crud, type(supabase_crud)):
            # Log the Supabase state
            from app.core.third_party_integrations.supabase_home.client import supabase
            from app.core.third_party_integrations.supabase_home.init import get_supabase_client
            
            try:
                # Check if Supabase client can be initialized
                client = get_supabase_client()
                logger.info("Supabase client initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing Supabase client: {str(e)}")
                raise ValueError(f"Failed to initialize Supabase client: {str(e)}")
            
            # Supabase doesn't need session
            return await _crud.create_item(item_in=item_in, owner_id=owner_id)
        else:
            # SQLModel needs session
            if session is None:
                logger.error("Session is required for PostgreSQL operations but was None")
                raise ValueError("Session is required for PostgreSQL operations")
            return await _crud.create_item(session=session, item_in=item_in, owner_id=owner_id)
    except Exception as e:
        logger.exception(f"Error in create_item adapter: {str(e)}")
        raise

async def get_item(*, session: Optional[Session] = None, item_id: uuid.UUID) -> Optional[Item]:
    """Get an item by ID using the appropriate database backend."""
    if isinstance(_crud, supabase_crud.__class__):
        return await _crud.get_item(item_id=item_id)
    else:
        if session is None:
            raise ValueError("Session is required for PostgreSQL operations")
        return await _crud.get_item(session=session, item_id=item_id)

async def get_items(*, session: Optional[Session] = None, skip: int = 0, limit: int = 100) -> List[Item]:
    """Get a list of items using the appropriate database backend."""
    if isinstance(_crud, supabase_crud.__class__):
        return await _crud.get_items(skip=skip, limit=limit)
    else:
        if session is None:
            raise ValueError("Session is required for PostgreSQL operations")
        return await _crud.get_items(session=session, skip=skip, limit=limit)

async def get_items_by_owner(*, session: Optional[Session] = None, 
                          owner_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Item]:
    """Get a list of items by owner ID using the appropriate database backend."""
    if isinstance(_crud, supabase_crud.__class__):
        return await _crud.get_items_by_owner(owner_id=owner_id, skip=skip, limit=limit)
    else:
        if session is None:
            raise ValueError("Session is required for PostgreSQL operations")
        return await _crud.get_items_by_owner(session=session, owner_id=owner_id, skip=skip, limit=limit)

async def update_item(*, session: Optional[Session] = None, db_item: Optional[Item] = None,
                    item_id: Optional[uuid.UUID] = None, item_in: ItemCreate) -> Item:
    """Update an item using the appropriate database backend."""
    if isinstance(_crud, supabase_crud.__class__):
        return await _crud.update_item(item_id=item_id, item_in=item_in)
    else:
        if session is None or db_item is None:
            raise ValueError("Session and db_item are required for PostgreSQL operations")
        return await _crud.update_item(session=session, db_item=db_item, item_in=item_in)

async def delete_item(*, session: Optional[Session] = None, item: Optional[Item] = None,
                    item_id: Optional[uuid.UUID] = None) -> None:
    """Delete an item using the appropriate database backend."""
    if isinstance(_crud, supabase_crud.__class__):
        return await _crud.delete_item(item_id=item_id)
    else:
        if session is None or item is None:
            raise ValueError("Session and item are required for PostgreSQL operations")
        return await _crud.delete_item(session=session, item=item)

# Utility functions
def is_superuser(user: User) -> bool:
    """Check if a user is a superuser."""
    return user.is_superuser

def is_active(user: User) -> bool:
    """Check if a user is active."""
    return user.is_active

async def get_users(*, session: Optional[Session] = None, skip: int = 0, limit: int = 100) -> List[User]:
    """Get all users using the appropriate database backend."""
    if isinstance(_crud, type(supabase_crud)):
        # Supabase doesn't need session
        users = await _crud.get_users(skip=skip, limit=limit)
        # Convert dictionary to User objects if needed
        if users and isinstance(users[0], dict):
            return [
                User(
                    id=uuid.UUID(user["id"]) if isinstance(user["id"], str) else user["id"],
                    email=user["email"],
                    is_active=user.get("is_active", True),
                    is_superuser=user.get("is_superuser", False),
                    full_name=user.get("full_name", ""),
                    hashed_password=user.get("hashed_password", ""),
                    items=[]  # Always use an empty list for now
                ) for user in users
            ]
        return users
    else:
        # SQLModel needs session
        if session is None:
            raise ValueError("Session is required for PostgreSQL operations")
        return await _crud.get_users(session=session, skip=skip, limit=limit)
