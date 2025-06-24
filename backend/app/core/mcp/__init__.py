"""
MCP module initialization.

This module initializes the MCP (Model Context Protocol) components
for the FastAPI Connect application.
"""

# Import submodules to ensure they are registered
from app.core.mcp import tools
from app.core.mcp import resources

# Export the MCP instance getter
from app.core.mcp_server import get_mcp

__all__ = ["get_mcp"]
