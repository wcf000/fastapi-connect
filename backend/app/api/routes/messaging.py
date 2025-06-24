"""
Messaging routes for handling Pulsar message operations.
"""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep
from app.models import User, Message
from app.core.pulsar.client import PulsarClient
from app.core.pulsar.decorators import pulsar_task, pulsar_consumer
from app.api.dependencies.metrics import record_user_operation, time_cache_operation

# Define router with prefix and tag
router = APIRouter(prefix="/messaging", tags=["messaging"])

# Models for messaging
class MessageCreate(BaseModel):
    """Model for creating a new message."""
    content: str = Field(..., description="Message content")
    topic: str = Field(..., description="Pulsar topic to send message to")
    recipient_id: Optional[uuid.UUID] = Field(None, description="Optional recipient user ID")
    
class MessageResponse(BaseModel):
    """Response model for message operations."""
    id: str = Field(..., description="Message ID")
    status: str = Field(..., description="Message status")
    timestamp: str = Field(..., description="Message timestamp")

class TopicStats(BaseModel):
    """Statistics for a Pulsar topic."""
    topic: str
    message_count: int
    producer_count: int
    consumer_count: int
    subscription_count: int

# Pulsar topic constants - follow a consistent naming pattern
NOTIFICATION_TOPIC = "persistent://public/default/notifications"
USER_ACTIVITY_TOPIC = "persistent://public/default/user-activity"
SYSTEM_ALERTS_TOPIC = "persistent://public/default/system-alerts"
DLQ_TOPIC = "persistent://public/default/dead-letter-queue"

# Get pulsar client instance
def get_pulsar_client():
    """Dependency to get Pulsar client."""
    return PulsarClient()

@router.post("/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    message: MessageCreate,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    pulsar_client: PulsarClient = Depends(get_pulsar_client),
) -> Any:
    """
    Send a message to a Pulsar topic.
    
    This endpoint allows users to send messages to different Pulsar topics
    for asynchronous processing.
    """
    with time_cache_operation("send_message"):
        # Prepare message data with user context
        message_data = {
            "content": message.content,
            "sender_id": str(current_user.id),
            "sender_email": current_user.email,
            "timestamp": str(uuid.uuid4()),  # Use as message ID
            "recipient_id": str(message.recipient_id) if message.recipient_id else None
        }
        
        # Use background task for non-blocking operation
        background_tasks.add_task(
            send_message_to_topic,
            message.topic,
            message_data
        )
        
        record_user_operation(
            operation="send_message",
            status="success",
            details={"topic": message.topic}
        )
        
        return {
            "id": message_data["timestamp"],
            "status": "queued",
            "timestamp": message_data["timestamp"]
        }

@router.get("/topics", response_model=List[str])
async def list_topics(
    current_user: CurrentUser,
    pulsar_client: PulsarClient = Depends(get_pulsar_client),
) -> Any:
    """
    List available Pulsar topics.
    """
    # Return the list of available topics
    available_topics = [
        NOTIFICATION_TOPIC,
        USER_ACTIVITY_TOPIC,
        SYSTEM_ALERTS_TOPIC
    ]
    
    return available_topics

@router.get("/topics/{topic}/stats", response_model=TopicStats)
async def get_topic_stats(
    topic: str,
    current_user: CurrentUser,
    pulsar_client: PulsarClient = Depends(get_pulsar_client),
) -> Any:
    """
    Get statistics for a specific Pulsar topic.
    """
    # In a real implementation, you would fetch actual stats from Pulsar
    # Here we return mock data
    return {
        "topic": topic,
        "message_count": 1250,
        "producer_count": 5,
        "consumer_count": 10,
        "subscription_count": 3
    }

# Message sending functions using Pulsar decorators
@pulsar_task(topic=NOTIFICATION_TOPIC, dlq_topic=DLQ_TOPIC)
async def send_message_to_topic(topic: str, message_data: dict) -> dict:
    """
    Send a message to the specified Pulsar topic.
    This function is decorated with pulsar_task which handles
    sending the message to Pulsar.
    
    Returns the message data for tracking.
    """
    # Add metadata to the message
    message_data["published_at"] = str(uuid.uuid4())
    message_data["topic"] = topic
    
    # This will be sent to Pulsar by the decorator
    return message_data

# Message processing functions
@pulsar_consumer(
    topic=NOTIFICATION_TOPIC,
    subscription="notification-processor"
)
async def process_notification(message: dict) -> None:
    """
    Process notifications from the notifications topic.
    This is automatically called by the Pulsar consumer.
    """
    # In a real implementation, you would process the notification
    # For example, sending emails, push notifications, etc.
    print(f"Processing notification: {message}")

# For use with background tasks
async def send_system_alert(alert_type: str, content: str, metadata: dict = None) -> None:
    """
    Send a system alert to the system alerts topic.
    """
    message_data = {
        "alert_type": alert_type,
        "content": content,
        "timestamp": str(uuid.uuid4()),
        "metadata": metadata or {}
    }
    
    # Use the Pulsar client directly for this function
    client = PulsarClient()
    await client.send_message(SYSTEM_ALERTS_TOPIC, message_data)
