import uuid
from typing import Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session, joinedload
from sqlmodel import select
from opentelemetry import trace
from sqlalchemy import func

from app.core.security import get_password_hash, verify_password
from app.models import Item, ItemCreate, User, UserCreate, UserUpdate
from app.api.dependencies.cache import ValkeyCache, valkey_cache, invalidate_cache
from app.core.telemetry.decorators import trace_function, measure_performance

# Import metrics - but use sparingly to avoid duplication
from app.api.dependencies.metrics import (
    time_db_query,
    record_user_operation,
)

# Import messaging functions for user events
from app.api.messaging.users import (
    send_user_created_event,
    send_user_updated_event,
    send_user_deleted_event
)


# These cached functions are NEW additions, so they should have metrics
@trace_function("get_user_by_id")
@valkey_cache(ttl=300, key_prefix="user:")
async def get_user_by_id(db: Session, user_id: int):
    """Get user by ID with Valkey caching."""
    try:
        user = db.query(User).filter(User.id == user_id).first()

        # Add business context to the current span
        span = trace.get_current_span()
        span.set_attribute("user.id", user_id)
        span.set_attribute("cache.enabled", True)
        if user:
            span.set_attribute("user.found", True)
        else:
            span.set_attribute("user.found", False)
        
        return user
    except Exception as e:
        # Errors automatically captured by @trace_function
        raise


@trace_function("update_user_cached")
@invalidate_cache("user:*")
async def update_user_cached(db: Session, user_id: int, user_data: dict):
    """Update user and invalidate cache."""
    span = trace.get_current_span()
    span.set_attribute("user.id", user_id)
    
    try:
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "read")
            query_span.set_attribute("db.table", "users")
            
            user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            span.set_attribute("operation.status", "not_found")
            return None
        
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "update")
            query_span.set_attribute("db.table", "users")
            
            for key, value in user_data.items():
                setattr(user, key, value)
            
            db.commit()
            db.refresh(user)
        
        span.set_attribute("operation.status", "success")
        span.set_attribute("cache.invalidated", True)
        return user
    except Exception as e:
        span.set_attribute("operation.status", "failure")
        span.record_exception(e)
        raise


# These functions are called by routes that already have metrics, so NO metrics here
@measure_performance("create_user_db")  # Monitor slow DB operations
async def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    
    # Send user created event asynchronously
    user_data = {
        "id": str(db_obj.id),
        "email": db_obj.email,
        "is_active": db_obj.is_active,
        "is_superuser": db_obj.is_superuser,
        "full_name": getattr(db_obj, "full_name", ""),
        "created_at": datetime.now().isoformat()
    }
    await send_user_created_event(user_data)
    
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    
    # Save original state for change tracking
    updated_fields = list(user_data.keys())
    
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    
    # Send user updated event asynchronously (in background)
    user_update_data = {
        "id": str(db_user.id),
        "email": db_user.email,
        "is_active": db_user.is_active,
        "updated_fields": updated_fields,
        "updated_at": datetime.now().isoformat()
    }
    # Use asyncio.create_task to avoid waiting
    import asyncio
    asyncio.create_task(send_user_updated_event(user_update_data))
    
    return db_user


def get_user(*, session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


@trace_function("get_user_by_email")
def get_user_by_email(*, session: Session, email: str) -> User | None:
    span = trace.get_current_span()
    span.set_attribute("user.email", email)
    
    statement = select(User).where(User.email == email)
    user = session.exec(statement).first()
    
    span.set_attribute("user.found", user is not None)
    return user


@trace_function("authenticate_user")
def authenticate(*, session: Session, email: str, password: str) -> User | None:
    span = trace.get_current_span()
    span.set_attribute("user.email", email)
    
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        span.set_attribute("authentication.status", "user_not_found")
        return None
        
    if not verify_password(password, db_user.hashed_password):
        span.set_attribute("authentication.status", "invalid_password")
        return None
        
    span.set_attribute("authentication.status", "success")
    span.set_attribute("user.id", str(db_user.id))
    return db_user


def get_users(*, session: Session, skip: int = 0, limit: int = 100) -> list[User]:
    statement = select(User).offset(skip).limit(limit)
    users = session.exec(statement).all()
    return users


# Item functions - these might be called independently, so add minimal metrics
def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


def get_item(*, session: Session, item_id: uuid.UUID) -> Item | None:
    return session.get(Item, item_id)


def get_items(*, session: Session, skip: int = 0, limit: int = 100) -> list[Item]:
    statement = select(Item).offset(skip).limit(limit)
    items = session.exec(statement).all()
    return items


def get_items_by_owner(
    *, session: Session, owner_id: uuid.UUID, skip: int = 0, limit: int = 100
) -> list[Item]:
    statement = (
        select(Item)
        .where(Item.owner_id == owner_id)
        .offset(skip)
        .limit(limit)
    )
    items = session.exec(statement).all()
    return items


def update_item(*, session: Session, db_item: Item, item_in: ItemCreate) -> Item:
    update_dict = item_in.model_dump(exclude_unset=True)
    db_item.sqlmodel_update(update_dict)
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


def delete_item(*, session: Session, item: Item) -> None:
    session.delete(item)
    session.commit()


def delete_user(*, session: Session, user: User) -> None:
    # Save user data for event before deletion
    user_data = {
        "id": str(user.id),
        "email": user.email,
        "deleted_at": datetime.now().isoformat()
    }
    
    # Delete the user
    session.delete(user)
    session.commit()
    
    # Send user deleted event asynchronously
    import asyncio
    asyncio.create_task(send_user_deleted_event(user_data))


def is_superuser(user: User) -> bool:
    return user.is_superuser


def is_active(user: User) -> bool:
    return user.is_active


# Utility functions that might be called independently - add metrics only for these
def get_user_count(*, session: Session) -> int:
    """Get total user count - standalone function, add metrics"""
    try:
        with time_db_query(operation="count", table="users"):
            statement = select(func.count(User.id))
            count = session.exec(statement).one()
        
        record_user_operation(operation="get_user_count", status="success")
        return count
    except Exception as e:
        record_user_operation(operation="get_user_count", status="failure")
        raise


def get_item_count_by_owner(*, session: Session, owner_id: uuid.UUID) -> int:
    """Get item count for a specific owner - standalone function, add metrics"""
    try:
        with time_db_query(operation="count", table="items"):
            statement = select(func.count(Item.id)).where(Item.owner_id == owner_id)
            count = session.exec(statement).one()
        
        record_user_operation(operation="get_item_count_by_owner", status="success")
        return count
    except Exception as e:
        record_user_operation(operation="get_item_count_by_owner", status="failure")
        raise
