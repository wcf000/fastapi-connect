import uuid
from typing import Any, Dict, List, Optional, Union
import json
from datetime import datetime
import logging

from opentelemetry import trace
from pydantic import EmailStr

from app.core.security import get_password_hash, verify_password
from app.models import Item, ItemCreate, User, UserCreate, UserUpdate
from app.api.dependencies.cache import invalidate_cache
from app.core.telemetry.decorators import trace_function, measure_performance

# Import the Supabase client
from app.core.third_party_integrations.supabase_home.client import supabase

# Import messaging functions for user events
from app.api.messaging.users import (
    send_user_created_event,
    send_user_updated_event,
    send_user_deleted_event
)

logger = logging.getLogger(__name__)

# User CRUD operations
@measure_performance()
async def create_user(*, user_create: UserCreate) -> User:
    """
    Create a new user in Supabase.
    
    Args:
        user_create: User data for creation
        
    Returns:
        Created user as a User model instance
    """
    # Generate UUID for user
    user_id = str(uuid.uuid4())
    
    # Convert UserCreate to dict for Supabase
    user_data = user_create.model_dump()
    
    # Replace password with hashed_password
    password = user_data.pop("password")
    user_data["hashed_password"] = get_password_hash(password)
    
    # Add UUID
    user_data["id"] = user_id
    
    try:
        # Insert user into Supabase
        created_user = supabase.get_database_service().insert_data(
            table="user",
            data=user_data,
            # is_admin=True  # Use admin rights to bypass RLS for creation
        )
        
        if not created_user or len(created_user) == 0:
            raise ValueError("Failed to create user in Supabase")
        
        # Convert to a User model
        user_dict = created_user[0]
        
        # Send user created event asynchronously
        event_data = {
            "id": user_dict["id"],
            "email": user_dict["email"],
            "is_active": user_dict["is_active"],
            "is_superuser": user_dict["is_superuser"],
            "full_name": user_dict.get("full_name", ""),
            "created_at": datetime.now().isoformat()
        }
        await send_user_created_event(event_data)
        
        # Convert dict to User model before returning
        user = User.model_validate(user_dict)
        return user
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise


@trace_function("get_user_supabase")
async def get_user(*, user_id: uuid.UUID) -> Optional[User]:
    """
    Get a user by ID from Supabase.
    
    Args:
        user_id: User ID
        
    Returns:
        User model instance or None if not found
    """
    span = trace.get_current_span()
    span.set_attribute("user.id", str(user_id))
    
    try:
        # Query Supabase for the user
        users = supabase.get_database_service().fetch_data(
            table="user",
            filters={"id": str(user_id)},
            is_admin=True  # Use admin rights to bypass RLS
        )
        
        span.set_attribute("user.found", len(users) > 0)
        
        if not users or len(users) == 0:
            return None
            
        # Convert dict to User model before returning
        user_dict = users[0]
        user = User.model_validate(user_dict)
        return user
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        span.record_exception(e)
        raise


@trace_function("get_user_by_email_supabase")
async def get_user_by_email(*, email: str) -> Optional[User]:
    """
    Get a user by email from Supabase.
    
    Args:
        email: User email
        
    Returns:
        User model instance or None if not found
    """
    span = trace.get_current_span()
    span.set_attribute("user.email", email)
    
    try:
        # Query Supabase for the user
        users = supabase.get_database_service().fetch_data(
            table="user",
            filters={"email": email},
        )
        
        span.set_attribute("user.found", len(users) > 0)
        
        if not users or len(users) == 0:
            return None
            
        # Convert dict to User model before returning
        user_dict = users[0]
        user = User.model_validate(user_dict)
        return user
    except Exception as e:
        logger.error(f"Error getting user by email: {e}")
        span.record_exception(e)
        raise


@trace_function("authenticate_user_supabase")
async def authenticate(*, email: str, password: str) -> Optional[User]:
    """
    Authenticate a user with email and password.
    
    Args:
        email: User email
        password: User password
        
    Returns:
        User model instance if authentication successful, None otherwise
    """
    span = trace.get_current_span()
    span.set_attribute("user.email", email)
    
    try:
        # Get user by email
        user = await get_user_by_email(email=email)
        
        if not user:
            span.set_attribute("authentication.status", "user_not_found")
            return None
            
        # Check password
        if not verify_password(password, user.hashed_password):
            span.set_attribute("authentication.status", "invalid_password")
            return None
            
        span.set_attribute("authentication.status", "success")
        span.set_attribute("user.id", str(user.id))
        return user
    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        span.record_exception(e)
        raise


@trace_function("update_user_supabase")
@invalidate_cache("user:*")
async def update_user(*, user_id: uuid.UUID, user_in: UserUpdate) -> Optional[Dict[str, Any]]:
    """
    Update a user in Supabase.
    
    Args:
        user_id: User ID
        user_in: User data for update
        
    Returns:
        Updated user data or None if not found
    """
    span = trace.get_current_span()
    span.set_attribute("user.id", str(user_id))
    
    try:
        # Get current user
        user = await get_user(user_id=user_id)
        
        if not user:
            span.set_attribute("operation.status", "not_found")
            return None
            
        # Convert UserUpdate to dict
        update_data = user_in.model_dump(exclude_unset=True)
        
        # Handle password separately
        if "password" in update_data:
            password = update_data.pop("password")
            update_data["hashed_password"] = get_password_hash(password)
            
        # Save updated fields for event
        updated_fields = list(update_data.keys())
        
        # Update user in Supabase
        updated_users = supabase.get_database_service().update_data(
            table="user",
            data=update_data,
            filters={"id": str(user_id)},
            is_admin=True  # Use admin rights to bypass RLS
        )
        
        if not updated_users or len(updated_users) == 0:
            span.set_attribute("operation.status", "failed")
            return None
            
        updated_user = updated_users[0]
        
        # Send user updated event asynchronously
        event_data = {
            "id": updated_user["id"],
            "email": updated_user["email"],
            "is_active": updated_user["is_active"],
            "updated_fields": updated_fields,
            "updated_at": datetime.now().isoformat()
        }
        # Use asyncio.create_task to avoid waiting
        import asyncio
        asyncio.create_task(send_user_updated_event(event_data))
        
        span.set_attribute("operation.status", "success")
        span.set_attribute("cache.invalidated", True)
        return updated_user
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        span.set_attribute("operation.status", "error")
        span.record_exception(e)
        raise


async def get_users(*, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get a list of users from Supabase.
    
    Args:
        skip: Number of users to skip
        limit: Maximum number of users to return
        
    Returns:
        List of users
    """
    try:
        # Query Supabase for users
        users = supabase.get_database_service().fetch_data(
            table="user",
            limit=limit,
            offset=skip,
            is_admin=True  # Use admin rights to bypass RLS
        )
        
        return users
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise


async def delete_user(*, user_id: uuid.UUID) -> bool:
    """
    Delete a user from Supabase.
    
    Args:
        user_id: User ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get user first to save data for event
        user = await get_user(user_id=user_id)
        
        if not user:
            return False
            
        # Delete user from Supabase
        deleted_users = supabase.get_database_service().delete_data(
            table="user",
            filters={"id": str(user_id)},
            is_admin=True  # Use admin rights to bypass RLS
        )
        
        if not deleted_users or len(deleted_users) == 0:
            return False
            
        # Send user deleted event asynchronously
        event_data = {
            "id": user["id"],
            "email": user["email"],
            "deleted_at": datetime.now().isoformat()
        }
        # Use asyncio.create_task to avoid waiting
        import asyncio
        asyncio.create_task(send_user_deleted_event(event_data))
        
        return True
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise


# Item CRUD operations
async def create_item(*, item_in: ItemCreate, owner_id: uuid.UUID) -> Dict[str, Any]:
    """
    Create a new item in Supabase.
    
    Args:
        item_in: Item data for creation
        owner_id: User ID of the item owner
        
    Returns:
        Created item data
    """
    # Generate UUID for item
    item_id = str(uuid.uuid4())
    
    # Convert ItemCreate to dict for Supabase
    item_data = item_in.model_dump()
    
    # Add UUID and owner_id
    item_data["id"] = item_id
    item_data["owner_id"] = str(owner_id)
    
    try:
        # Insert item into Supabase
        created_items = supabase.get_database_service().insert_data(
            table="item",
            data=item_data,
            is_admin=True  # Use admin rights to bypass RLS
        )
        
        if not created_items or len(created_items) == 0:
            raise ValueError("Failed to create item in Supabase")
        
        return created_items[0]
    except Exception as e:
        logger.error(f"Error creating item: {e}")
        raise


async def get_item(*, item_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """
    Get an item by ID from Supabase.
    
    Args:
        item_id: Item ID
        
    Returns:
        Item data or None if not found
    """
    try:
        # Query Supabase for the item
        items = supabase.get_database_service().fetch_data(
            table="item",
            filters={"id": str(item_id)},
            is_admin=True  # Use admin rights to bypass RLS
        )
        
        if not items or len(items) == 0:
            return None
            
        return items[0]
    except Exception as e:
        logger.error(f"Error getting item: {e}")
        raise


async def get_items(*, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get a list of items from Supabase.
    
    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return
        
    Returns:
        List of items
    """
    try:
        # Query Supabase for items
        items = supabase.get_database_service().fetch_data(
            table="item",
            limit=limit,
            offset=skip,
            is_admin=True  # Use admin rights to bypass RLS
        )
        
        return items
    except Exception as e:
        logger.error(f"Error getting items: {e}")
        raise


async def get_items_by_owner(*, owner_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get a list of items by owner from Supabase.
    
    Args:
        owner_id: User ID of the item owner
        skip: Number of items to skip
        limit: Maximum number of items to return
        
    Returns:
        List of items
    """
    try:
        # Query Supabase for items by owner
        items = supabase.get_database_service().fetch_data(
            table="item",
            filters={"owner_id": str(owner_id)},
            limit=limit,
            offset=skip,
            is_admin=True  # Use admin rights to bypass RLS
        )
        
        return items
    except Exception as e:
        logger.error(f"Error getting items by owner: {e}")
        raise


async def update_item(*, item_id: uuid.UUID, item_in: ItemCreate) -> Optional[Dict[str, Any]]:
    """
    Update an item in Supabase.
    
    Args:
        item_id: Item ID
        item_in: Item data for update
        
    Returns:
        Updated item data or None if not found
    """
    try:
        # Get current item
        item = await get_item(item_id=item_id)
        
        if not item:
            return None
            
        # Convert ItemCreate to dict
        update_data = item_in.model_dump(exclude_unset=True)
        
        # Update item in Supabase
        updated_items = supabase.get_database_service().update_data(
            table="item",
            data=update_data,
            filters={"id": str(item_id)},
            is_admin=True  # Use admin rights to bypass RLS
        )
        
        if not updated_items or len(updated_items) == 0:
            return None
            
        return updated_items[0]
    except Exception as e:
        logger.error(f"Error updating item: {e}")
        raise


async def delete_item(*, item_id: uuid.UUID) -> bool:
    """
    Delete an item from Supabase.
    
    Args:
        item_id: Item ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Delete item from Supabase
        deleted_items = supabase.get_database_service().delete_data(
            table="item",
            filters={"id": str(item_id)},
            is_admin=True  # Use admin rights to bypass RLS
        )
        
        if not deleted_items or len(deleted_items) == 0:
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error deleting item: {e}")
        raise


def is_superuser(user: Dict[str, Any]) -> bool:
    """
    Check if a user is a superuser.
    
    Args:
        user: User data
        
    Returns:
        True if superuser, False otherwise
    """
    return user.get("is_superuser", False)
