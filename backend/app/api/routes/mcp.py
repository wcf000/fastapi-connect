"""
API routes for Model Context Protocol (MCP).

This module contains routes for interacting with the MCP server.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.core.mcp_server import get_mcp

router = APIRouter(
    prefix="/mcp",
    tags=["mcp"],
    responses={404: {"description": "Not found"}},
)

class MCPStatusResponse(BaseModel):
    """Response model for MCP status"""
    status: str
    version: str
    available_tools: int
    available_resources: int
    message: str

@router.get("/status", response_model=MCPStatusResponse)
async def get_mcp_status():
    """
    Get the status of the MCP server.
    
    Returns:
        MCPStatusResponse: Status information about the MCP server
    """
    mcp = get_mcp()
    
    if not mcp:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server is not initialized"
        )
    
    # Count available tools and resources
    tool_count = len(mcp.list_tools()) if hasattr(mcp, 'list_tools') else 0
    resource_count = len(mcp.list_resources()) if hasattr(mcp, 'list_resources') else 0
    
    return MCPStatusResponse(
        status="running",
        version="1.0.0",
        available_tools=tool_count,
        available_resources=resource_count,
        message="MCP server is running"
    )

@router.get("/health")
async def health_check():
    """
    Simple health check endpoint for the MCP server.
    
    Returns:
        dict: Health status
    """
    mcp = get_mcp()
    
    if not mcp:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server is not initialized"
        )
    
    return {"status": "ok", "service": "mcp"}

@router.get("/discovery")
async def discovery():
    """
    Discover all available MCP tools and resources.
    
    Returns:
        dict: Lists of all tools and resources with their details
    """
    mcp = get_mcp()
    
    if not mcp:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server is not initialized"
        )
    
    tools = mcp.list_tools() if hasattr(mcp, 'list_tools') else []
    resources = mcp.list_resources() if hasattr(mcp, 'list_resources') else []
    
    # Format tool details
    tool_details = []
    for tool in tools:
        # Extract tool name and details
        tool_name = getattr(tool, 'name', str(tool))
        tool_description = getattr(tool, 'description', None)
        tool_details.append({
            "name": tool_name,
            "description": tool_description,
            "url": f"/.well-known/mcp/tools/{tool_name}"
        })
    
    # Format resource details
    resource_details = []
    for resource in resources:
        # Extract resource name and details
        resource_name = getattr(resource, 'name', str(resource))
        resource_description = getattr(resource, 'description', None)
        resource_details.append({
            "name": resource_name,
            "description": resource_description,
            "url": f"/.well-known/mcp/resources/{resource_name}"
        })
    
    return {
        "tools": tool_details,
        "resources": resource_details,
        "mcp_base_url": "/.well-known/mcp",
        "documentation": "Check the FastMCP documentation for more details on how to use these endpoints."
    }
