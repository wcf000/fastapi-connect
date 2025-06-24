"""
Custom MCP resources for the FastAPI Connect application.

This module contains custom MCP resources that can be accessed by LLMs or other clients.
"""

from typing import Dict, Any, Optional
from fastmcp import Context

# Import the global MCP instance
from app.core.mcp_server import get_mcp

# Get the MCP instance
mcp = get_mcp()

# Register resources with the MCP instance if available
if mcp:
    @mcp.resource("app://version/{dummy}")
    async def get_app_version(dummy: str = "latest", ctx: Optional[Context] = None) -> str:
        """
        Get the application version.
        
        Args:
            dummy: A dummy parameter to satisfy MCP requirements
            ctx: Optional MCP context
            
        Returns:
            str: Application version
        """
        if ctx:
            await ctx.info("App version requested")
            
        return "1.0.0"
    
    @mcp.resource("app://config/{dummy}")
    async def get_app_config(dummy: str = "default", ctx: Optional[Context] = None) -> Dict[str, Any]:
        """
        Get public application configuration.
        
        Args:
            dummy: A dummy parameter to satisfy MCP requirements
            ctx: Optional MCP context
            
        Returns:
            Dict: Application configuration
        """
        # Include only public configuration that's safe to expose
        config = {
            "name": "FastAPI Connect",
            "api_version": "v1",
            "features": {
                "authentication": True,
                "database": True,
                "mcp": True,
                "metrics": True,
                "telemetry": True,
            }
        }
        
        if ctx:
            await ctx.info("App config requested")
            
        return config
    
    @mcp.resource("user://{user_id}")
    async def get_user_info(user_id: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
        """
        Get information about a specific user.
        
        Args:
            user_id: The ID of the user
            ctx: Optional MCP context
            
        Returns:
            Dict: User information
        """
        # In a real implementation, you would fetch user data from your database
        # For now, we'll return mock data
        
        if ctx:
            await ctx.info(f"User info requested for user_id: {user_id}")
            
        # Check if this is a known mock user
        if user_id == "usr_john":
            return {
                "id": "usr_john",
                "username": "john_doe",
                "email": "john@example.com",
                "full_name": "John Doe",
                "is_active": True,
                "created_at": "2024-01-01T12:00:00Z"
            }
        elif user_id == "usr_jane":
            return {
                "id": "usr_jane",
                "username": "jane_doe",
                "email": "jane@example.com",
                "full_name": "Jane Doe",
                "is_active": True,
                "created_at": "2024-01-02T10:30:00Z"
            }
        else:
            # Return a generic response for unknown users
            return {
                "id": user_id,
                "message": f"User with ID {user_id} not found",
                "exists": False
            }
