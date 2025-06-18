import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload
from sqlmodel import select

from app.core.security import get_password_hash, verify_password
from app.models import Item, ItemCreate, User, UserCreate, UserUpdate
from app.api.dependencies.cache import ValkeyCache, valkey_cache, invalidate_cache

# Import metrics - but use sparingly to avoid duplication
from app.api.dependencies.metrics import (
    time_db_query,
    record_user_operation,
)


# These cached functions are NEW additions, so they should have metrics
@valkey_cache(ttl=300, key_prefix="user:")
async def get_user_by_id(db: Session, user_id: int):
    """Get user by ID with Valkey caching."""
    try:
        with time_db_query(operation="read", table="users"):
            user = db.query(User).filter(User.id == user_id).first()
        
        if user:
            record_user_operation(operation="get_user_by_id_cached", status="success")
        else:
            record_user_operation(operation="get_user_by_id_cached", status="not_found")
        
        return user
    except Exception as e:
        record_user_operation(operation="get_user_by_id_cached", status="failure")
        raise


@invalidate_cache("user:*")
async def update_user_cached(db: Session, user_id: int, user_data: dict):
    """Update user and invalidate cache."""
    try:
        with time_db_query(operation="read", table="users"):
            user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            record_user_operation(operation="update_user_cached", status="not_found")
            return None
        
        with time_db_query(operation="update", table="users"):
            for key, value in user_data.items():
                setattr(user, key, value)
            
            db.commit()
            db.refresh(user)
        
        record_user_operation(operation="update_user_cached", status="success")
        return user
    except Exception as e:
        record_user_operation(operation="update_user_cached", status="failure")
        raise


# These functions are called by routes that already have metrics, so NO metrics here
def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user(*, session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
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
    session.delete(user)
    session.commit()


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
