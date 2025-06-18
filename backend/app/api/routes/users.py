import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select

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

# Import metrics dependencies
from app.api.dependencies.metrics import (
    record_user_operation,
    record_user_registration,
    record_user_login,
    time_db_query,
    ACTIVE_USERS
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """
    try:
        # Using context manager to time the database queries
        with time_db_query(operation="read", table="users"):
            count_statement = select(func.count()).select_from(User)
            count = session.exec(count_statement).one()

            statement = select(User).offset(skip).limit(limit)
            users = session.exec(statement).all()

        # Record successful operation
        record_user_operation(operation="read_list", status="success")
        return UsersPublic(data=users, count=count)
    except Exception as e:
        # Record failed operation
        record_user_operation(operation="read_list", status="failure")
        raise


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    try:
        # Check if user exists
        with time_db_query(operation="read", table="users"):
            user = crud.get_user_by_email(session=session, email=user_in.email)
            
        if user:
            record_user_operation(operation="create", status="failure")
            record_user_registration(status="failure")
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists in the system.",
            )

        # Create user
        with time_db_query(operation="create", table="users"):
            user = crud.create_user(session=session, user_create=user_in)
            
        # Send email if enabled
        if settings.emails_enabled and user_in.email:
            email_data = generate_new_account_email(
                email_to=user_in.email, username=user_in.email, password=user_in.password
            )
            send_email(
                email_to=user_in.email,
                subject=email_data.subject,
                html_content=email_data.html_content,
            )
            
        record_user_operation(operation="create", status="success")
        record_user_registration(status="success")
        return user
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="create", status="failure")
        record_user_registration(status="failure")
        raise


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """
    try:
        if user_in.email:
            with time_db_query(operation="read", table="users"):
                existing_user = crud.get_user_by_email(session=session, email=user_in.email)
                
            if existing_user and existing_user.id != current_user.id:
                record_user_operation(operation="update_self", status="failure")
                raise HTTPException(
                    status_code=409, detail="User with this email already exists"
                )
                
        # Update user
        with time_db_query(operation="update", table="users"):
            user_data = user_in.model_dump(exclude_unset=True)
            current_user.sqlmodel_update(user_data)
            session.add(current_user)
            session.commit()
            session.refresh(current_user)
            
        record_user_operation(operation="update_self", status="success")
        return current_user
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="update_self", status="failure")
        raise


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    try:
        if not verify_password(body.current_password, current_user.hashed_password):
            record_user_operation(operation="update_password", status="failure")
            raise HTTPException(status_code=400, detail="Incorrect password")
            
        if body.current_password == body.new_password:
            record_user_operation(operation="update_password", status="failure")
            raise HTTPException(
                status_code=400, detail="New password cannot be the same as the current one"
            )
            
        # Update password
        with time_db_query(operation="update", table="users"):
            hashed_password = get_password_hash(body.new_password)
            current_user.hashed_password = hashed_password
            session.add(current_user)
            session.commit()
            
        record_user_operation(operation="update_password", status="success")
        return Message(message="Password updated successfully")
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="update_password", status="failure")
        raise


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    # Increment active users counter
    ACTIVE_USERS.inc()
    record_user_operation(operation="read_self", status="success")
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    try:
        if current_user.is_superuser:
            record_user_operation(operation="delete_self", status="failure")
            raise HTTPException(
                status_code=403, detail="Super users are not allowed to delete themselves"
            )
            
        # Delete user
        with time_db_query(operation="delete", table="users"):
            session.delete(current_user)
            session.commit()
            
        record_user_operation(operation="delete_self", status="success")
        return Message(message="User deleted successfully")
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="delete_self", status="failure")
        raise


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    try:
        # Check if user exists
        with time_db_query(operation="read", table="users"):
            user = crud.get_user_by_email(session=session, email=user_in.email)
            
        if user:
            record_user_operation(operation="signup", status="failure")
            record_user_registration(status="failure")
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists in the system",
            )
            
        # Create user
        with time_db_query(operation="create", table="users"):
            user_create = UserCreate.model_validate(user_in)
            user = crud.create_user(session=session, user_create=user_create)
            
        record_user_operation(operation="signup", status="success")
        record_user_registration(status="success")
        return user
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="signup", status="failure")
        record_user_registration(status="failure")
        raise


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    try:
        # Get user
        with time_db_query(operation="read", table="users"):
            user = session.get(User, user_id)
            
        if user == current_user:
            record_user_operation(operation="read_self", status="success")
            return user
            
        if not current_user.is_superuser:
            record_user_operation(operation="read_other", status="failure")
            raise HTTPException(
                status_code=403,
                detail="The user doesn't have enough privileges",
            )
            
        record_user_operation(operation="read_other", status="success")
        return user
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="read_other", status="failure")
        raise


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """
    try:
        # Get user
        with time_db_query(operation="read", table="users"):
            db_user = session.get(User, user_id)
            
        if not db_user:
            record_user_operation(operation="update_other", status="failure")
            raise HTTPException(
                status_code=404,
                detail="The user with this id does not exist in the system",
            )
            
        if user_in.email:
            with time_db_query(operation="read", table="users"):
                existing_user = crud.get_user_by_email(session=session, email=user_in.email)
                
            if existing_user and existing_user.id != user_id:
                record_user_operation(operation="update_other", status="failure")
                raise HTTPException(
                    status_code=409, detail="User with this email already exists"
                )

        # Update user
        with time_db_query(operation="update", table="users"):
            db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
            
        record_user_operation(operation="update_other", status="success")
        return db_user
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="update_other", status="failure")
        raise


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    try:
        # Get user
        with time_db_query(operation="read", table="users"):
            user = session.get(User, user_id)
            
        if not user:
            record_user_operation(operation="delete_other", status="failure")
            raise HTTPException(status_code=404, detail="User not found")
            
        if user == current_user:
            record_user_operation(operation="delete_other", status="failure")
            raise HTTPException(
                status_code=403, detail="Super users are not allowed to delete themselves"
            )
            
        # Delete user and their items
        with time_db_query(operation="delete", table="users"):
            statement = delete(Item).where(col(Item.owner_id) == user_id)
            session.exec(statement)  # type: ignore
            session.delete(user)
            session.commit()
            
        record_user_operation(operation="delete_other", status="success")
        return Message(message="User deleted successfully")
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="delete_other", status="failure")
        raise
