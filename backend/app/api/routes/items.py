import uuid
import logging
from typing import Any
import sys

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import func, select
from opentelemetry import trace

# Replace direct import with adapter
from app import db_adapter as crud
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

logging.basicConfig(
    level=logging.DEBUG,  # Or INFO if you want less verbosity
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# logger = logging.getLogger(__name__)

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
    print(f"[INFO] Retrieving items for user: {current_user.id}, is_superuser: {current_user.is_superuser}")
    print(f"[INFO] Skip: {skip}, Limit: {limit}")
    
    try:
        # Check cache first
        print("[DEBUG] Checking cache...")
        valkey = get_valkey()
        cache_key = f"user:{current_user.id}:items:list:{skip}:{limit}"
        
        with time_cache_operation("get"):
            cached_items = await valkey.get(cache_key)
            
        if cached_items:
            print("[INFO] Cache hit, returning cached items")
            record_cache_hit()
            record_user_operation(operation="read_items", status="success")
            return cached_items

        print("[INFO] Cache miss, fetching items from database")
        record_cache_miss()

        # Using adapter to get items
        with time_db_query(operation="read", table="items"):
            if current_user.is_superuser:
                print("[INFO] Superuser - fetching all items")
                try:
                    items = await crud.get_items(session=session, skip=skip, limit=limit)
                    print(f"[DEBUG] Retrieved {len(items)} items")
                    print(f"[DEBUG] First item type: {type(items[0]) if items else 'No items'}")
                except Exception as fetch_error:
                    print(f"[ERROR] Error fetching all items: {str(fetch_error)}")
                    import traceback
                    traceback.print_exc()
                    raise
                count = len(items)
            else:
                print(f"[INFO] Regular user - fetching owned items for {current_user.id}")
                try:
                    items = await crud.get_items_by_owner(
                        session=session, 
                        owner_id=current_user.id, 
                        skip=skip, 
                        limit=limit
                    )
                    print(f"[DEBUG] Retrieved {len(items)} items")
                    print(f"[DEBUG] First item type: {type(items[0]) if items else 'No items'}")
                except Exception as fetch_error:
                    print(f"[ERROR] Error fetching owned items: {str(fetch_error)}")
                    import traceback
                    traceback.print_exc()
                    raise
                count = len(items)

        print(f"[INFO] Creating ItemsPublic with {count} items")
        try:
            result = ItemsPublic(data=items, count=count)
            print("[INFO] ItemsPublic created successfully")
        except Exception as model_error:
            print(f"[ERROR] Error creating ItemsPublic model: {str(model_error)}")
            import traceback
            traceback.print_exc()
            raise

        # Cache the result
        try:
            with time_cache_operation("set"):
                await valkey.set(cache_key, result, ttl=300)  # Cache for 5 minutes
                record_cache_operation("set", "success")
            print("[INFO] Result cached successfully")
        except Exception as cache_error:
            print(f"[WARN] Error caching result: {str(cache_error)}")
            # Continue even if caching fails

        record_user_operation(operation="read_items", status="success")
        return result
    except Exception as e:
        print(f"[ERROR] Unhandled exception in read_items: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve items: {str(e)}"
        )


@router.get("/{id}", response_model=ItemPublic)
async def read_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get item by ID.
    """
    span = trace.get_current_span()
    span.set_attribute("item.id", str(id))
    span.set_attribute("user.id", str(current_user.id))
    
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

        # Use adapter to get item
        with time_db_query(operation="read", table="items"):
            item = await crud.get_item(session=session, item_id=id)
            
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
        span.set_attribute("operation.status", "failure")
        span.record_exception(e)
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
    span = trace.get_current_span()
    span.set_attribute("user.id", str(current_user.id))
    
    try:
        # Use adapter to create item
        print(f"[INFO] Creating item with title: {item_in.title}, owner_id: {current_user.id}")
        print(f"[DEBUG] Item data: {item_in.model_dump()}")
        print(f"[DEBUG] Using session: {session}")
        
        # Debug current database implementation
        from app.db_adapter import get_crud_implementation
        current_crud = get_crud_implementation()
        print(f"[INFO] Using database implementation: {current_crud.__name__}")
        
        # Check environment variables for Supabase configuration
        import os
        supabase_url = os.getenv("SUPABASE_URL", "")
        supabase_key = os.getenv("SUPABASE_ANON_KEY", "")
        print(f"[INFO] Supabase URL configured: {'Yes' if supabase_url else 'No'}")
        print(f"[INFO] Supabase key configured: {'Yes' if supabase_key else 'No'}")
        
        with time_db_query(operation="create", table="items"):
            try:
                # If using Supabase, test the client initialization
                if current_crud.__name__ == 'app.supabase_crud':
                    from app.core.third_party_integrations.supabase_home.client import supabase
                    client = supabase.get_database_service()
                    print(f"[INFO] Supabase client initialized: {client is not None}")
                
                # Attempt to create the item
                item = await crud.create_item(
                    session=session, 
                    item_in=item_in, 
                    owner_id=current_user.id
                )
                print(f"[INFO] Item created successfully with ID: {item.id if hasattr(item, 'id') else 'unknown'}")
            except Exception as create_error:
                print(f"[ERROR] Error in crud.create_item: {str(create_error)}")
                import traceback
                traceback.print_exc()
                raise

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
        
        # Add this function
        def publish_item_event_wrapper(topic: str, item_data: dict):
            """Non-async wrapper for background tasks"""
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(publish_item_event(topic, item_data))
            except Exception as e:
                print(f"[ERROR] Error in publish_item_event_wrapper: {str(e)}")
        
        # Use background task for non-blocking operation
        try:
            background_tasks.add_task(
                publish_item_event_wrapper,
                ITEM_CREATED_TOPIC,
                item_data
            )
        except Exception as e:
            print(f"[WARN] Failed to queue Pulsar event: {str(e)}")
            # The operation still succeeds even if the event fails

        span.set_attribute("operation.status", "success")
        span.set_attribute("item.id", str(item.id))
        record_user_operation(operation="create_item", status="success")
        return item
    except Exception as e:
        span.set_attribute("operation.status", "failure")
        span.record_exception(e)
        record_user_operation(operation="create_item", status="error")
        print(f"[ERROR] Failed to create item: {str(e)}")
        import traceback
        traceback.print_exc()
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
    span = trace.get_current_span()
    span.set_attribute("item.id", str(id))
    span.set_attribute("user.id", str(current_user.id))
    
    try:
        # Get the item first
        with time_db_query(operation="read", table="items"):
            item = await crud.get_item(session=session, item_id=id)
            
        if not item:
            record_user_operation(operation="update_item", status="not_found")
            raise HTTPException(status_code=404, detail="Item not found")
            
        if not current_user.is_superuser and (item.owner_id != current_user.id):
            record_user_operation(operation="update_item", status="permission_denied")
            raise HTTPException(status_code=403, detail="Not enough permissions")

        # Use adapter to update item
        with time_db_query(operation="update", table="items"):
            updated_item = await crud.update_item(
                session=session,
                item_id=id,
                item_in=item_in
            )

        # Invalidate cache
        valkey = get_valkey()
        cache_key = f"item:{id}"
        
        with time_cache_operation("delete"):
            await valkey.delete(cache_key)
            record_cache_operation("delete", "success")
            
        # Send item updated event to Pulsar
        update_dict = item_in.model_dump(exclude_unset=True)
        item_data = {
            "id": str(updated_item.id),
            "title": updated_item.title,
            "description": updated_item.description,
            "owner_id": str(updated_item.owner_id),
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

        span.set_attribute("operation.status", "success")
        record_user_operation(operation="update_item", status="success")
        return updated_item
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        span.set_attribute("operation.status", "failure")
        span.record_exception(e)
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
    span = trace.get_current_span()
    span.set_attribute("item.id", str(id))
    span.set_attribute("user.id", str(current_user.id))
    
    try:
        # Get the item first
        with time_db_query(operation="read", table="items"):
            item = await crud.get_item(session=session, item_id=id)
            
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

        # Use adapter to delete item
        with time_db_query(operation="delete", table="items"):
            await crud.delete_item(session=session, item_id=id)

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

        span.set_attribute("operation.status", "success")
        record_user_operation(operation="delete_item", status="success")
        return Message(message="Item deleted successfully")
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        span.set_attribute("operation.status", "failure")
        span.record_exception(e)
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
