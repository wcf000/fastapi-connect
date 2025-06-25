"""
User and account activity messaging with Pulsar.
"""
import uuid
from datetime import datetime
from typing import Dict, Any

from app.core.pulsar.decorators import pulsar_task, pulsar_consumer
from app.core.pulsar.client import PulsarClient

# Define topic constants for user events
USER_CREATED_TOPIC = "persistent://public/default/user-created"
USER_UPDATED_TOPIC = "persistent://public/default/user-updated"
USER_DELETED_TOPIC = "persistent://public/default/user-deleted"
USER_DLQ_TOPIC = "persistent://public/default/user-dlq"

# Message sending functions with Pulsar decorators
@pulsar_task(topic=USER_CREATED_TOPIC, dlq_topic=USER_DLQ_TOPIC)
async def send_user_created_event(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a user created event to the user-created Pulsar topic.
    
    Args:
        user_data: Dictionary containing user data
        
    Returns:
        The user data with additional metadata
    """
    # Add metadata for tracking
    user_data["event_id"] = str(uuid.uuid4())
    user_data["timestamp"] = datetime.now().isoformat()
    user_data["event_type"] = "user_created"
    
    # Return for the decorator to send to Pulsar
    return user_data

@pulsar_task(topic=USER_UPDATED_TOPIC, dlq_topic=USER_DLQ_TOPIC)
async def send_user_updated_event(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a user updated event to the user-updated Pulsar topic.
    
    Args:
        user_data: Dictionary containing user data
        
    Returns:
        The user data with additional metadata
    """
    # Add metadata for tracking
    user_data["event_id"] = str(uuid.uuid4())
    user_data["timestamp"] = datetime.now().isoformat()
    user_data["event_type"] = "user_updated"
    
    # Return for the decorator to send to Pulsar
    return user_data

@pulsar_task(topic=USER_DELETED_TOPIC, dlq_topic=USER_DLQ_TOPIC)
async def send_user_deleted_event(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a user deleted event to the user-deleted Pulsar topic.
    
    Args:
        user_data: Dictionary containing user data
        
    Returns:
        The user data with additional metadata
    """
    # Add metadata for tracking
    user_data["event_id"] = str(uuid.uuid4())
    user_data["timestamp"] = datetime.now().isoformat()
    user_data["event_type"] = "user_deleted"
    
    # Return for the decorator to send to Pulsar
    return user_data

# Consumer functions - these will be started by the background processor
@pulsar_consumer(
    topic=USER_CREATED_TOPIC, 
    subscription="user-created-processor"
)
async def process_user_created_event(message: Dict[str, Any]) -> None:
    """
    Process user created events from the user-created topic.
    
    This could update analytics, send welcome emails, etc.
    """
    print(f"Processing user created event: {message}")
    # Example: Send welcome email, setup user in other systems, etc.

@pulsar_consumer(
    topic=USER_UPDATED_TOPIC, 
    subscription="user-updated-processor"
)
async def process_user_updated_event(message: Dict[str, Any]) -> None:
    """
    Process user updated events from the user-updated topic.
    
    This could update search indexes, sync to other systems, etc.
    """
    print(f"Processing user updated event: {message}")
    # Example: Sync profile to other systems, update indexes, etc.

@pulsar_consumer(
    topic=USER_DELETED_TOPIC, 
    subscription="user-deleted-processor"
)
async def process_user_deleted_event(message: Dict[str, Any]) -> None:
    """
    Process user deleted events from the user-deleted topic.
    
    This could clean up resources, update analytics, etc.
    """
    print(f"Processing user deleted event: {message}")
    # Example: Remove user from other systems, archive data, etc.
