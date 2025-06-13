import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from app.core.security import get_password_hash, verify_password
from app.models import Item, ItemCreate, User, UserCreate, UserUpdate
from app.core.redis.decorators import get_or_set_cache
from app.core.redis.redis_cache import RedisCache


# Cache key functions
def user_email_cache_key(email: str) -> str:
    return f"user:email:{email}"


def user_permissions_cache_key(user_id: int) -> str:
    return f"user:permissions:{user_id}"


@get_or_set_cache(
    key_fn=user_email_cache_key,
    ttl=300,  # 5 minutes TTL
    stale_ttl=60  # Use stale data for up to 60s if DB is down
)
async def get_user_by_email(db_session: Session, email: str) -> Optional[User]:
    """
    Get a user by email with Redis caching.
    Frequently used during authentication flows.
    """
    return db_session.query(User).filter(User.email == email).first()


@get_or_set_cache(
    key_fn=user_permissions_cache_key,
    ttl=600,  # 10 minutes TTL
    warm_cache=True  # Enable background refresh for hot keys
)
async def get_user_with_permissions(db_session: Session, user_id: int) -> Optional[User]:
    """
    Get a user with permissions via joinedload with Redis caching.
    Used for authorization checks.
    """
    return db_session.query(User).filter(User.id == user_id).options(
        joinedload(User.permissions)
    ).first()


# Make sure to invalidate the cache when a user is updated
async def update_user(db_session: Session, user_id: int, user_data: UserUpdate) -> User:
    """Update user with cache invalidation"""
    from app.core.redis.decorators import invalidate_cache
    
    user = db_session.query(User).filter(User.id == user_id).first()
    
    if not user:
        return None
        
    # Update user data
    for field, value in user_data.dict(exclude_unset=True).items():
        setattr(user, field, value)
    
    db_session.commit()
    db_session.refresh(user)
    
    # Invalidate user caches
    await invalidate_cache(
        f"user:permissions:{user_id}",
        f"user:email:{user.email}"
    )
    
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
