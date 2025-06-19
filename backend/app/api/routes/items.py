import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import Item, ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message

# Import metrics dependencies
from app.api.dependencies.metrics import (
    record_user_operation,
    time_db_query,
    record_cache_hit,
    record_cache_miss,
    time_cache_operation,
    record_cache_operation
)
from app.core.valkey_init import get_valkey

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/", response_model=ItemsPublic)
async def read_items(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve items.
    """
    try:
        # Check cache first
        valkey = get_valkey()
        cache_key = f"user:{current_user.id}:items:list:{skip}:{limit}"
        
        with time_cache_operation("get"):
            cached_items = await valkey.get(cache_key)
            
        if cached_items:
            record_cache_hit()
            record_user_operation(operation="read_items", status="success")
            return cached_items

        record_cache_miss()

        # Original database query logic
        with time_db_query(operation="read", table="items"):
            if current_user.is_superuser:
                count_statement = select(func.count()).select_from(Item)
                count = session.exec(count_statement).one()
                statement = select(Item).offset(skip).limit(limit)
                items = session.exec(statement).all()
            else:
                count_statement = (
                    select(func.count())
                    .select_from(Item)
                    .where(Item.owner_id == current_user.id)
                )
                count = session.exec(count_statement).one()
                statement = (
                    select(Item)
                    .where(Item.owner_id == current_user.id)
                    .offset(skip)
                    .limit(limit)
                )
                items = session.exec(statement).all()

        result = ItemsPublic(data=items, count=count)

        # Cache the result
        with time_cache_operation("set"):
            await valkey.set(cache_key, result, ttl=300)  # Cache for 5 minutes
            record_cache_operation("set", "success")

        record_user_operation(operation="read_items", status="success")
        return result
    except Exception as e:
        record_user_operation(operation="read_items", status="failure")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve items: {str(e)}"
        )


@router.get("/{id}", response_model=ItemPublic)
async def read_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get item by ID.
    """
    try:
        # Check cache first
        valkey = get_valkey()
        cache_key = f"item:{id}"
        
        with time_cache_operation("get"):
            cached_item = await valkey.get(cache_key)
            
        if cached_item:
            record_cache_hit()
            # Still need to check permissions
            if not current_user.is_superuser and cached_item.owner_id != current_user.id:
                record_user_operation(operation="read_item", status="permission_denied")
                raise HTTPException(status_code=403, detail="Not enough permissions")
            record_user_operation(operation="read_item", status="success")
            return cached_item

        record_cache_miss()

        # Original database query
        with time_db_query(operation="read", table="items"):
            item = session.get(Item, id)
            
        if not item:
            record_user_operation(operation="read_item", status="not_found")
            raise HTTPException(status_code=404, detail="Item not found")
            
        if not current_user.is_superuser and (item.owner_id != current_user.id):
            record_user_operation(operation="read_item", status="permission_denied")
            raise HTTPException(status_code=403, detail="Not enough permissions")

        # Cache the result
        with time_cache_operation("set"):
            await valkey.set(cache_key, item, ttl=300)  # Cache for 5 minutes
            record_cache_operation("set", "success")

        record_user_operation(operation="read_item", status="success")
        return item
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="read_item", status="error")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve item: {str(e)}"
        )


@router.post("/", response_model=ItemPublic)
async def create_item(
    *, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate
) -> Any:
    """
    Create new item.
    """
    try:
        # Original item creation logic
        with time_db_query(operation="create", table="items"):
            item = crud.create_item(session=session, item_in=item_in, owner_id=current_user.id)

        # Invalidate cache
        valkey = get_valkey()
        cache_pattern = f"user:{current_user.id}:items:list:*"
        
        with time_cache_operation("delete_pattern"):
            # In practice, you'd need to implement pattern deletion
            # For now, we'll just delete a few common cache keys
            for skip in [0, 10, 20, 50, 100]:
                for limit in [10, 20, 50, 100]:
                    cache_key = f"user:{current_user.id}:items:list:{skip}:{limit}"
                    await valkey.delete(cache_key)
            record_cache_operation("delete_pattern", "success")

        record_user_operation(operation="create_item", status="success")
        return item
    except Exception as e:
        record_user_operation(operation="create_item", status="error")
        raise HTTPException(
            status_code=500, detail=f"Failed to create item: {str(e)}"
        )


@router.put("/{id}", response_model=ItemPublic)
async def update_item(
    *, session: SessionDep, current_user: CurrentUser, id: uuid.UUID, item_in: ItemUpdate
) -> Any:
    """
    Update an item.
    """
    try:
        # Original update logic
        with time_db_query(operation="read", table="items"):
            item = session.get(Item, id)
            
        if not item:
            record_user_operation(operation="update_item", status="not_found")
            raise HTTPException(status_code=404, detail="Item not found")
            
        if not current_user.is_superuser and (item.owner_id != current_user.id):
            record_user_operation(operation="update_item", status="permission_denied")
            raise HTTPException(status_code=403, detail="Not enough permissions")

        with time_db_query(operation="update", table="items"):
            update_dict = item_in.model_dump(exclude_unset=True)
            item.sqlmodel_update(update_dict)
            session.add(item)
            session.commit()
            session.refresh(item)

        # Invalidate cache
        valkey = get_valkey()
        cache_key = f"item:{id}"
        
        with time_cache_operation("delete"):
            await valkey.delete(cache_key)
            record_cache_operation("delete", "success")

        record_user_operation(operation="update_item", status="success")
        return item
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="update_item", status="error")
        raise HTTPException(
            status_code=500, detail=f"Failed to update item: {str(e)}"
        )


@router.delete("/{id}")
async def delete_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Message:
    """
    Delete an item.
    """
    try:
        # Original delete logic
        with time_db_query(operation="read", table="items"):
            item = session.get(Item, id)
            
        if not item:
            record_user_operation(operation="delete_item", status="not_found")
            raise HTTPException(status_code=404, detail="Item not found")
            
        if not current_user.is_superuser and (item.owner_id != current_user.id):
            record_user_operation(operation="delete_item", status="permission_denied")
            raise HTTPException(status_code=403, detail="Not enough permissions")

        with time_db_query(operation="delete", table="items"):
            session.delete(item)
            session.commit()

        # Invalidate cache
        valkey = get_valkey()
        cache_key = f"item:{id}"
        
        with time_cache_operation("delete"):
            await valkey.delete(cache_key)
            record_cache_operation("delete", "success")

        record_user_operation(operation="delete_item", status="success")
        return Message(message="Item deleted successfully")
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        record_user_operation(operation="delete_item", status="error")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete item: {str(e)}"
        )
