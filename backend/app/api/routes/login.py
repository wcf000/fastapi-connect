from datetime import timedelta
from typing import Annotated, Any
from datetime import datetime
import sys
import os
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from opentelemetry import trace

from app import db_adapter as crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core import security
from app.core.config import settings
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
from app.core.telemetry.decorators import trace_function, measure_performance, track_errors
from app.api.dependencies.metrics import time_db_query, record_user_operation

# Import messaging functions
from app.api.messaging.auth import (
    send_login_event,
    send_password_reset_event,
    send_suspicious_activity_event
)

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
@trace_function("login_access_token")
@measure_performance()
async def login_access_token(
    request: Request,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    background_tasks: BackgroundTasks
) -> Token:
    """
    OAuth2 compatible token login with rate limiting protection
    """
    span = trace.get_current_span()
    span.set_attribute("client.ip", request.client.host)
    span.set_attribute("user.email", form_data.username)
    
    try:
        # Get Valkey client
        valkey_client = get_valkey()
        
        # Rate limit by IP address (5 attempts per minute)
        client_ip = request.client.host
        rate_limit_key = f"login:{client_ip}"

        # Check if rate limited using Valkey client
        with trace.get_tracer(__name__).start_as_current_span("rate_limit_check") as rate_span:
            is_allowed = await check_rate_limit(valkey_client, rate_limit_key, 5, 60)
            rate_span.set_attribute("rate_limit.allowed", is_allowed)
            rate_span.set_attribute("rate_limit.key", rate_limit_key)
            
        if not is_allowed:
            span.set_attribute("login.status", "rate_limited")
            raise HTTPException(
                status_code=429, detail="Too many login attempts. Please try again later."
            )

        # Existing authentication logic with spans
        with trace.get_tracer(__name__).start_as_current_span("authenticate") as auth_span:
            auth_span.set_attribute("db.operation", "authenticate")
            auth_span.set_attribute("db.table", "users")
            
            try:
                # Properly await the authenticate function since it's async
                user = await crud.authenticate(
                    session=session, email=form_data.username, password=form_data.password
                )
                auth_span.set_attribute("authentication.success", True if user else False)
            except Exception as auth_error:
                auth_span.set_attribute("authentication.error", str(auth_error))
                auth_span.record_exception(auth_error)
                logger.error(f"Authentication error: {str(auth_error)}")
                
                # Try Supabase auth as fallback if PostgreSQL fails
                if "getaddrinfo failed" in str(auth_error) and os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"):
                    logger.warning("PostgreSQL connection failed, trying Supabase authentication")
                    import app.supabase_crud as supabase_crud
                    user = await supabase_crud.authenticate(email=form_data.username, password=form_data.password)
                    auth_span.set_attribute("authentication.fallback", "supabase")
                    auth_span.set_attribute("authentication.success", True if user else False)
                else:
                    raise
            
        if not user:
            span.set_attribute("login.status", "failure")
            span.set_attribute("failure.reason", "invalid_credentials")
            
            # Send failed login event to Pulsar in the background
            login_event_data = {
                "email": form_data.username,
                "client_ip": request.client.host,
                "user_agent": request.headers.get("user-agent", ""),
                "success": False,
                "failure_reason": "invalid_credentials",
                "login_time": datetime.now().isoformat()
            }
            background_tasks.add_task(send_login_event, login_event_data)
            
            raise HTTPException(status_code=400, detail="Incorrect email or password")
        elif not user.is_active:
            span.set_attribute("login.status", "failure")
            span.set_attribute("failure.reason", "inactive_user")
            raise HTTPException(status_code=400, detail="Inactive user")
            
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # Record successful login in span
        span.set_attribute("login.status", "success")
        span.set_attribute("user.id", str(user.id))
        
        # Send login event to Pulsar in the background
        login_event_data = {
            "user_id": str(user.id),
            "email": form_data.username,
            "client_ip": request.client.host,
            "user_agent": request.headers.get("user-agent", ""),
            "success": True,
            "login_time": datetime.now().isoformat()
        }
        background_tasks.add_task(send_login_event, login_event_data)
        
        # Create access token and then return the Token object
        access_token = security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
        return Token(access_token=access_token)
    except HTTPException:
        raise
    except Exception as e:
        span.set_attribute("login.status", "error")
        span.record_exception(e)
        raise HTTPException(
            status_code=500, detail=f"Login failed: {str(e)}"
        )


@router.post("/login/test-token", response_model=UserPublic)
@trace_function("test_token")
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    span = trace.get_current_span()
    span.set_attribute("user.id", str(current_user.id))
    span.set_attribute("operation.status", "success")
    return current_user


@router.post("/password-recovery/{email}")
@trace_function("recover_password")
@track_errors
async def recover_password(
    request: Request,
    email: str,
    session: SessionDep,
    background_tasks: BackgroundTasks
) -> Message:
    """
    Password Recovery with rate limiting
    """
    span = trace.get_current_span()
    span.set_attribute("user.email", email)
    span.set_attribute("client.ip", request.client.host)
    
    try:
        # Get Valkey client
        valkey_client = get_valkey()
        
        # Rate limit by IP (3 attempts per hour)
        client_ip = request.client.host
        rate_limit_key = f"pwd_recovery:{client_ip}"

        # Use Valkey rate limiting with OpenTelemetry
        with trace.get_tracer(__name__).start_as_current_span("rate_limit_check") as rate_span:
            is_allowed = await check_rate_limit(valkey_client, rate_limit_key, 3, 3600)
            rate_span.set_attribute("rate_limit.allowed", is_allowed)
            rate_span.set_attribute("rate_limit.key", rate_limit_key)
            
        if not is_allowed:
            span.set_attribute("operation.status", "rate_limited")
            
            # Send suspicious activity event for rate limit hit
            suspicious_data = {
                "email": email,
                "client_ip": request.client.host,
                "user_agent": request.headers.get("user-agent", ""),
                "activity_type": "password_recovery_rate_limit",
                "timestamp": datetime.now().isoformat()
            }
            background_tasks.add_task(send_suspicious_activity_event, suspicious_data)
            
            raise HTTPException(
                status_code=429, 
                detail="Too many password recovery attempts. Please try again later."
            )

        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "read")
            query_span.set_attribute("db.table", "users")
            
            user = await crud.get_user_by_email(session=session, email=email)
            query_span.set_attribute("user.found", user is not None)

        if not user:
            span.set_attribute("operation.status", "failure")
            span.set_attribute("failure.reason", "user_not_found")
            raise HTTPException(
                status_code=404,
                detail="The user with this email does not exist in the system.",
            )
            
        with trace.get_tracer(__name__).start_as_current_span("send_email") as email_span:
            email_span.set_attribute("email.to", email)
            
            password_reset_token = generate_password_reset_token(email=email)
            recovery_email = generate_reset_password_email(
                email_to=user.email, email=email, token=password_reset_token
            )
            
            # Send email
            send_email(
                email_to=user.email,
                subject=recovery_email.subject,
                html_content=recovery_email.html_content,
            )
            
            # Send password reset event to Pulsar
            reset_event_data = {
                "user_id": str(user.id),
                "email": email,
                "client_ip": request.client.host,
                "user_agent": request.headers.get("user-agent", ""),
                "timestamp": datetime.now().isoformat()
            }
            background_tasks.add_task(send_password_reset_event, reset_event_data)
        
        span.set_attribute("operation.status", "success")
        return Message(message="Password recovery email sent")
    except HTTPException:
        # Error attributes already set above
        raise
    except Exception as e:
        span.set_attribute("operation.status", "failure")
        span.record_exception(e)
        raise HTTPException(
            status_code=500, detail=f"Password recovery failed: {str(e)}"
        )


@router.post("/reset-password/")
async def reset_password(
    session: SessionDep, 
    body: NewPassword,
    background_tasks: BackgroundTasks
) -> Message:
    """
    Reset password
    """
    try:
        email = verify_password_reset_token(token=body.token)
        if not email:
            record_user_operation(operation="reset_password", status="invalid_token")
            raise HTTPException(status_code=400, detail="Invalid token")
            
        with time_db_query(operation="read", table="users"):
            user = await crud.get_user_by_email(session=session, email=email)
            
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
            
        # Send password reset completion event
        reset_complete_event = {
            "user_id": str(user.id),
            "email": email,
            "timestamp": datetime.now().isoformat(),
            "event_type": "password_reset_complete"
        }
        background_tasks.add_task(send_password_reset_event, reset_complete_event)
            
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
async def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    try:
        with time_db_query(operation="read", table="users"):
            user = await crud.get_user_by_email(session=session, email=email)
            
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
