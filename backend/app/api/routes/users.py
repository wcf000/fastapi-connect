import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select
from opentelemetry import trace

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    Item,
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils import generate_new_account_email, send_email
from app.core.telemetry.decorators import trace_function, measure_performance, track_errors

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
@trace_function("read_users")
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """
    span = trace.get_current_span()
    span.set_attribute("users.skip", skip)
    span.set_attribute("users.limit", limit)
    
    try:
        # Using span to time the database query
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "read")
            query_span.set_attribute("db.table", "users")
            
            count_statement = select(func.count()).select_from(User)
            count = session.exec(count_statement).one()

            statement = select(User).offset(skip).limit(limit)
            users = session.exec(statement).all()
            
            query_span.set_attribute("db.rows_fetched", len(users))

        span.set_attribute("operation.status", "success")
        span.set_attribute("users.count", count)
        return UsersPublic(data=users, count=count)
    except Exception as e:
        span.set_attribute("operation.status", "failure")
        span.record_exception(e)
        raise


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
@trace_function("create_user") 
@track_errors
async def create_user(user_in: UserCreate, session: SessionDep) -> Any:
    """
    Create new user.
    """
    span = trace.get_current_span()
    span.set_attribute("user.email", user_in.email)
    
    try:
        # Check if user exists
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "read")
            query_span.set_attribute("db.table", "users")
            
            user = crud.get_user_by_email(session=session, email=user_in.email)
            
        if user:
            span.set_attribute("registration.status", "failure")
            span.set_attribute("failure.reason", "email_exists")
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists in the system.",
            )

        # Create user
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "create")
            query_span.set_attribute("db.table", "users")
            
            user = crud.create_user(session=session, user_create=user_in)
            query_span.set_attribute("user.id", str(user.id))
            
        # Send email if enabled
        if settings.emails_enabled and user_in.email:
            with trace.get_tracer(__name__).start_as_current_span("send_email"):
                email_data = generate_new_account_email(
                    email_to=user_in.email, username=user_in.email, password=user_in.password
                )
                send_email(
                    email_to=user_in.email,
                    subject=email_data.subject,
                    html_content=email_data.html_content,
                )
            
        span.set_attribute("registration.status", "success")
        span.set_attribute("user.id", str(user.id))
        return user
    except HTTPException as he:
        span.set_attribute("error.type", "http_exception")
        span.set_attribute("error.status_code", he.status_code)
        raise
    except Exception as e:
        span.set_attribute("registration.status", "failure")
        span.set_attribute("error.type", str(type(e).__name__))
        raise


@router.patch("/me", response_model=UserPublic)
@trace_function("update_user_me")
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """
    span = trace.get_current_span()
    span.set_attribute("user.id", str(current_user.id))
    
    try:
        if user_in.email:
            with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
                query_span.set_attribute("db.operation", "read")
                query_span.set_attribute("db.table", "users")
                
                existing_user = crud.get_user_by_email(session=session, email=user_in.email)
                
            if existing_user and existing_user.id != current_user.id:
                span.set_attribute("operation.status", "failure")
                span.set_attribute("failure.reason", "email_exists")
                raise HTTPException(
                    status_code=409, detail="User with this email already exists"
                )
                
        # Update user
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "update")
            query_span.set_attribute("db.table", "users")
            
            user_data = user_in.model_dump(exclude_unset=True)
            current_user.sqlmodel_update(user_data)
            session.add(current_user)
            session.commit()
            session.refresh(current_user)
            
        span.set_attribute("operation.status", "success")
        return current_user
    except HTTPException as he:
        span.set_attribute("error.type", "http_exception")
        span.set_attribute("error.status_code", he.status_code)
        raise
    except Exception as e:
        span.set_attribute("operation.status", "failure")
        span.record_exception(e)
        raise


@router.patch("/me/password", response_model=Message)
@trace_function("update_password_me")
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    span = trace.get_current_span()
    span.set_attribute("user.id", str(current_user.id))
    
    try:
        if not verify_password(body.current_password, current_user.hashed_password):
            span.set_attribute("operation.status", "failure")
            span.set_attribute("failure.reason", "incorrect_password")
            raise HTTPException(status_code=400, detail="Incorrect password")
            
        if body.current_password == body.new_password:
            span.set_attribute("operation.status", "failure")
            span.set_attribute("failure.reason", "same_password")
            raise HTTPException(
                status_code=400, detail="New password cannot be the same as the current one"
            )
            
        # Update password
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "update")
            query_span.set_attribute("db.table", "users")
            
            hashed_password = get_password_hash(body.new_password)
            current_user.hashed_password = hashed_password
            session.add(current_user)
            session.commit()
            
        span.set_attribute("operation.status", "success")
        return Message(message="Password updated successfully")
    except HTTPException:
        # Error attributes already set above
        raise
    except Exception as e:
        span.set_attribute("operation.status", "failure")
        span.record_exception(e)
        raise


@router.get("/me", response_model=UserPublic)
@trace_function("read_user_me")
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    span = trace.get_current_span()
    span.set_attribute("user.id", str(current_user.id))
    span.set_attribute("operation.status", "success")
    return current_user


@router.delete("/me", response_model=Message)
@trace_function("delete_user_me")
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    span = trace.get_current_span()
    span.set_attribute("user.id", str(current_user.id))
    
    try:
        if current_user.is_superuser:
            span.set_attribute("operation.status", "failure")
            span.set_attribute("failure.reason", "superuser_self_delete")
            raise HTTPException(
                status_code=403, detail="Super users are not allowed to delete themselves"
            )
            
        # Delete user
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "delete")
            query_span.set_attribute("db.table", "users")
            
            session.delete(current_user)
            session.commit()
            
        span.set_attribute("operation.status", "success")
        return Message(message="User deleted successfully")
    except HTTPException:
        # Error attributes already set above
        raise
    except Exception as e:
        span.set_attribute("operation.status", "failure")
        span.record_exception(e)
        raise


@router.post("/signup", response_model=UserPublic)
@trace_function("register_user")
@track_errors
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    span = trace.get_current_span()
    span.set_attribute("user.email", user_in.email)
    
    try:
        # Check if user exists
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "read")
            query_span.set_attribute("db.table", "users")
            
            user = crud.get_user_by_email(session=session, email=user_in.email)
            
        if user:
            span.set_attribute("registration.status", "failure")
            span.set_attribute("failure.reason", "email_exists")
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists in the system",
            )
            
        # Create user
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "create")
            query_span.set_attribute("db.table", "users")
            
            user_create = UserCreate.model_validate(user_in)
            user = crud.create_user(session=session, user_create=user_create)
            query_span.set_attribute("user.id", str(user.id))
            
        span.set_attribute("registration.status", "success")
        span.set_attribute("user.id", str(user.id))
        return user
    except HTTPException:
        # Error attributes already set above
        raise
    except Exception as e:
        span.set_attribute("registration.status", "failure")
        span.record_exception(e)
        raise


@router.get("/{user_id}", response_model=UserPublic)
@trace_function("read_user_by_id")
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    span = trace.get_current_span()
    span.set_attribute("user.id", str(user_id))
    span.set_attribute("requester.id", str(current_user.id))
    
    try:
        # Get user
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "read")
            query_span.set_attribute("db.table", "users")
            
            user = session.get(User, user_id)
            query_span.set_attribute("user.found", user is not None)
            
        if not user:
            span.set_attribute("operation.status", "failure")
            span.set_attribute("failure.reason", "user_not_found")
            raise HTTPException(status_code=404, detail="User not found")
            
        if user == current_user:
            span.set_attribute("operation.type", "read_self")
            span.set_attribute("operation.status", "success")
            return user
            
        if not current_user.is_superuser:
            span.set_attribute("operation.status", "failure")
            span.set_attribute("failure.reason", "insufficient_privileges")
            raise HTTPException(
                status_code=403,
                detail="The user doesn't have enough privileges",
            )
            
        span.set_attribute("operation.type", "read_other")
        span.set_attribute("operation.status", "success")
        return user
    except HTTPException:
        # Error attributes already set above
        raise
    except Exception as e:
        span.set_attribute("operation.status", "failure")
        span.record_exception(e)
        raise


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
@trace_function("update_user_by_id")
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """
    span = trace.get_current_span()
    span.set_attribute("user.id", str(user_id))
    
    try:
        # Get user
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "read")
            query_span.set_attribute("db.table", "users")
            
            db_user = session.get(User, user_id)
            query_span.set_attribute("user.found", db_user is not None)
            
        if not db_user:
            span.set_attribute("operation.status", "failure")
            span.set_attribute("failure.reason", "user_not_found")
            raise HTTPException(
                status_code=404,
                detail="The user with this id does not exist in the system",
            )
            
        if user_in.email:
            with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
                query_span.set_attribute("db.operation", "read")
                query_span.set_attribute("db.table", "users")
                
                existing_user = crud.get_user_by_email(session=session, email=user_in.email)
                query_span.set_attribute("email.exists", existing_user is not None)
                
            if existing_user and existing_user.id != user_id:
                span.set_attribute("operation.status", "failure")
                span.set_attribute("failure.reason", "email_exists")
                raise HTTPException(
                    status_code=409, detail="User with this email already exists"
                )

        # Update user
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "update")
            query_span.set_attribute("db.table", "users")
            
            db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
            
        span.set_attribute("operation.status", "success")
        span.set_attribute("operation.type", "update_other")
        return db_user
    except HTTPException as he:
        span.set_attribute("error.type", "http_exception")
        span.set_attribute("error.status_code", he.status_code)
        raise
    except Exception as e:
        span.set_attribute("operation.status", "failure")
        span.set_attribute("error.type", str(type(e).__name__))
        span.record_exception(e)
        raise


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
@trace_function("delete_user_by_id")
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    span = trace.get_current_span()
    span.set_attribute("user.id", str(user_id))
    span.set_attribute("requester.id", str(current_user.id))
    
    try:
        # Get user
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "read")
            query_span.set_attribute("db.table", "users")
            
            user = session.get(User, user_id)
            query_span.set_attribute("user.found", user is not None)
            
        if not user:
            span.set_attribute("operation.status", "failure")
            span.set_attribute("failure.reason", "user_not_found")
            raise HTTPException(status_code=404, detail="User not found")
            
        if user == current_user:
            span.set_attribute("operation.status", "failure")
            span.set_attribute("failure.reason", "self_delete_forbidden")
            raise HTTPException(
                status_code=403, detail="Super users are not allowed to delete themselves"
            )
            
        # Delete user and their items
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "delete")
            query_span.set_attribute("db.table", "items")
            
            statement = delete(Item).where(col(Item.owner_id) == user_id)
            result = session.exec(statement)  # type: ignore
            query_span.set_attribute("items.deleted", result.rowcount if hasattr(result, "rowcount") else 0)
            
        with trace.get_tracer(__name__).start_as_current_span("db_query") as query_span:
            query_span.set_attribute("db.operation", "delete")
            query_span.set_attribute("db.table", "users")
            
            session.delete(user)
            session.commit()
            
        span.set_attribute("operation.status", "success")
        span.set_attribute("operation.type", "delete_other")
        return Message(message="User deleted successfully")
    except HTTPException:
        # Error attributes already set above
        raise
    except Exception as e:
        span.set_attribute("operation.status", "failure")
        span.set_attribute("error.type", str(type(e).__name__))
        span.record_exception(e)
        raise
