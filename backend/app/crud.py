import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from app.core.security import get_password_hash, verify_password
from app.models import Item, ItemCreate, User, UserCreate, UserUpdate
# Replace Redis import with Valkey
from app.api.dependencies.cache import ValkeyCache, valkey_cache, invalidate_cache


# Example of using Valkey caching in CRUD operations
@valkey_cache(ttl=300, key_prefix="user:")
async def get_user_by_id(db: Session, user_id: int):
    """Get user by ID with Valkey caching."""
    user = db.query(User).filter(User.id == user_id).first()
    return user


@invalidate_cache("user:*")
async def update_user(db: Session, user_id: int, user_data: dict):
    """Update user and invalidate cache."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    
    for key, value in user_data.items():
        setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    return user


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


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item
