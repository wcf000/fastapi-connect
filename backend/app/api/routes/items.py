import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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

# Import Pulsar dependencies
from app.core.pulsar.client import PulsarClient
from app.core.pulsar.decorators import pulsar_task

# Define Pulsar topics
ITEM_CREATED_TOPIC = "persistent://public/default/item-created"
ITEM_UPDATED_TOPIC = "persistent://public/default/item-updated"
ITEM_DELETED_TOPIC = "persistent://public/default/item-deleted"
DLQ_TOPIC = "persistent://public/default/dead-letter-queue"

# Get Pulsar client instance
def get_pulsar_client():
    """Dependency to get Pulsar client."""
    return PulsarClient()

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
    *, 
    session: SessionDep, 
    current_user: CurrentUser, 
    item_in: ItemCreate,
    background_tasks: BackgroundTasks
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

        # Send item created event to Pulsar
        item_data = {
            "id": str(item.id),
            "title": item.title,
            "description": item.description,
            "owner_id": str(item.owner_id),
            "event_type": "item_created",
            "timestamp": str(uuid.uuid4())
        }
        
        # Use background task for non-blocking operation
        background_tasks.add_task(
            publish_item_event,
            ITEM_CREATED_TOPIC,
            item_data
        )

        # Publish item created event to Pulsar
        pulsar_client = get_pulsar_client()
        with pulsar_client.producer() as producer:
            producer.send(ITEM_CREATED_TOPIC, value=item.model_dump_json())

        record_user_operation(operation="create_item", status="success")
        return item
    except Exception as e:
        record_user_operation(operation="create_item", status="error")
        raise HTTPException(
            status_code=500, detail=f"Failed to create item: {str(e)}"
        )


@router.put("/{id}", response_model=ItemPublic)
async def update_item(
    *, 
    session: SessionDep, 
    current_user: CurrentUser, 
    id: uuid.UUID, 
    item_in: ItemUpdate,
    background_tasks: BackgroundTasks
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
            
        # Send item updated event to Pulsar
        item_data = {
            "id": str(item.id),
            "title": item.title,
            "description": item.description,
            "owner_id": str(item.owner_id),
            "event_type": "item_updated",
            "timestamp": str(uuid.uuid4()),
            "updated_fields": list(update_dict.keys())
        }
        
        # Use background task for non-blocking operation
        background_tasks.add_task(
            publish_item_event,
            ITEM_UPDATED_TOPIC,
            item_data
        )

        # Publish item updated event to Pulsar
        pulsar_client = get_pulsar_client()
        with pulsar_client.producer() as producer:
            producer.send(ITEM_UPDATED_TOPIC, value=item.model_dump_json())

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
async def delete_item(
    session: SessionDep, 
    current_user: CurrentUser, 
    id: uuid.UUID,
    background_tasks: BackgroundTasks
) -> Message:
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

        # Save item info before deletion for the event
        item_data = {
            "id": str(item.id),
            "title": item.title,
            "description": item.description,
            "owner_id": str(item.owner_id),
            "event_type": "item_deleted",
            "timestamp": str(uuid.uuid4())
        }

        with time_db_query(operation="delete", table="items"):
            session.delete(item)
            session.commit()

        # Invalidate cache
        valkey = get_valkey()
        cache_key = f"item:{id}"
        
        with time_cache_operation("delete"):
            await valkey.delete(cache_key)
            record_cache_operation("delete", "success")
            
        # Send item deleted event to Pulsar
        background_tasks.add_task(
            publish_item_event,
            ITEM_DELETED_TOPIC,
            item_data
        )

        # Publish item deleted event to Pulsar
        pulsar_client = get_pulsar_client()
        with pulsar_client.producer() as producer:
            producer.send(ITEM_DELETED_TOPIC, value={"id": str(id)})

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


# Pulsar message publishing function using the pulsar_task decorator
@pulsar_task(topic=ITEM_CREATED_TOPIC, dlq_topic=DLQ_TOPIC)
async def publish_item_event(topic: str, item_data: dict) -> dict:
    """
    Publish an item event to a Pulsar topic.
    This function is decorated with pulsar_task which handles
    sending the message to Pulsar.
    
    Returns the event data for tracking.
    """
    # Add additional metadata to the message
    item_data["published_at"] = str(uuid.uuid4())
    item_data["topic"] = topic
    
    # This will be sent to Pulsar by the decorator
    return item_data
