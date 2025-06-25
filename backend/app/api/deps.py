import os
from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.models import TokenPayload, User
from app import db_adapter as crud
from app.core.db import engine

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]


async def get_current_user(
    session: SessionDep, token: Annotated[str, Depends(reusable_oauth2)]
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    # Check if Supabase is configured
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "")
    
    user = None
    
    # First try Supabase if it's configured
    if supabase_url and supabase_key:
        try:
            # Use Supabase adapter to get user
            user = await crud.get_user(user_id=token_data.sub)
        except Exception as e:
            # Log the error but continue to try SQL if Supabase fails
            print(f"Supabase user lookup failed: {str(e)}")
    
    # If user not found via Supabase, try SQL (or if Supabase wasn't configured)
    if not user and not (supabase_url and supabase_key):
        try:
            # Use SQLModel to get user
            user = session.get(User, token_data.sub)
        except Exception as e:
            # If we get here and Supabase is configured, the SQL error doesn't matter
            if not (supabase_url and supabase_key):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database error: {str(e)}"
                )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not crud.is_active(user):
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user
