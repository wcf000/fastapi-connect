from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core import security
from app.core.config import settings
# Replace Redis import with Valkey
from app.core.valkey_init import get_valkey
from app.core.valkey_core.limiting.rate_limit import check_rate_limit
from app.core.security import get_password_hash
from app.models import Message, NewPassword, Token, UserPublic
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

# Import metrics dependencies
from app.api.dependencies.metrics import (
    record_user_login,
    record_user_operation,
    time_db_query,
    record_cache_operation,
    time_cache_operation
)

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
async def login_access_token(
    request: Request,  # Add request parameter to get client IP
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """
    OAuth2 compatible token login with rate limiting protection
    """
    try:
        # Get Valkey client
        valkey_client = get_valkey()
        
        # Rate limit by IP address (5 attempts per minute)
        client_ip = request.client.host
        rate_limit_key = f"login:{client_ip}"

        # Check if rate limited using Valkey client
        with time_cache_operation("rate_limit_check"):
            is_allowed = await check_rate_limit(valkey_client, rate_limit_key, 5, 60)
            
        if not is_allowed:
            record_user_login(status="rate_limited")
            record_cache_operation("rate_limit_check", "rejected")
            raise HTTPException(
                status_code=429, detail="Too many login attempts. Please try again later."
            )

        record_cache_operation("rate_limit_check", "allowed")

        # Existing authentication logic with metrics
        with time_db_query(operation="authenticate", table="users"):
            user = crud.authenticate(
                session=session, email=form_data.username, password=form_data.password
            )
            
        if not user:
            record_user_login(status="failure")
            raise HTTPException(status_code=400, detail="Incorrect email or password")
        elif not user.is_active:
            record_user_login(status="inactive_user")
            raise HTTPException(status_code=400, detail="Inactive user")
            
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # Record successful login
        record_user_login(status="success")
        
        return Token(
            access_token=security.create_access_token(
                user.id, expires_delta=access_token_expires
            )
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_login(status="error")
        raise HTTPException(
            status_code=500, detail=f"Login failed: {str(e)}"
        )


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    record_user_operation(operation="test_token", status="success")
    return current_user


@router.post("/password-recovery/{email}")
async def recover_password(
    request: Request,
    email: str,
    session: SessionDep,
) -> Message:
    """
    Password Recovery with rate limiting
    """
    try:
        # Get Valkey client
        valkey_client = get_valkey()
        
        # Rate limit by IP (3 attempts per hour)
        client_ip = request.client.host
        rate_limit_key = f"pwd_recovery:{client_ip}"

        # Use Valkey rate limiting
        with time_cache_operation("rate_limit_check"):
            is_allowed = await check_rate_limit(valkey_client, rate_limit_key, 3, 3600)
            
        if not is_allowed:
            record_user_operation(operation="password_recovery", status="rate_limited")
            record_cache_operation("rate_limit_check", "rejected")
            raise HTTPException(
                status_code=429, 
                detail="Too many password recovery attempts. Please try again later."
            )

        record_cache_operation("rate_limit_check", "allowed")

        with time_db_query(operation="read", table="users"):
            user = crud.get_user_by_email(session=session, email=email)

        if not user:
            record_user_operation(operation="password_recovery", status="user_not_found")
            raise HTTPException(
                status_code=404,
                detail="The user with this email does not exist in the system.",
            )
            
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
        
        record_user_operation(operation="password_recovery", status="success")
        return Message(message="Password recovery email sent")
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="password_recovery", status="error")
        raise HTTPException(
            status_code=500, detail=f"Password recovery failed: {str(e)}"
        )


@router.post("/reset-password/")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    try:
        email = verify_password_reset_token(token=body.token)
        if not email:
            record_user_operation(operation="reset_password", status="invalid_token")
            raise HTTPException(status_code=400, detail="Invalid token")
            
        with time_db_query(operation="read", table="users"):
            user = crud.get_user_by_email(session=session, email=email)
            
        if not user:
            record_user_operation(operation="reset_password", status="user_not_found")
            raise HTTPException(
                status_code=404,
                detail="The user with this email does not exist in the system.",
            )
            
        with time_db_query(operation="update", table="users"):
            hashed_password = get_password_hash(body.new_password)
            user.hashed_password = hashed_password
            session.add(user)
            session.commit()
            
        record_user_operation(operation="reset_password", status="success")
        return Message(message="Password updated successfully")
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="reset_password", status="error")
        raise HTTPException(
            status_code=500, detail=f"Password reset failed: {str(e)}"
        )


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    try:
        with time_db_query(operation="read", table="users"):
            user = crud.get_user_by_email(session=session, email=email)
            
        if not user:
            record_user_operation(operation="password_recovery_html", status="user_not_found")
            raise HTTPException(
                status_code=404,
                detail="The user with this email does not exist in the system.",
            )
            
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        
        record_user_operation(operation="password_recovery_html", status="success")
        return email_data.html_content
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="password_recovery_html", status="error")
        raise HTTPException(
            status_code=500, detail=f"HTML content generation failed: {str(e)}"
        )
