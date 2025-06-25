"""
FastMCP Server Integration for FastAPI Backend

This module integrates the Model Context Protocol (MCP) with the main FastAPI application.
It initializes a FastMCP server that can be used to expose tools and resources.
"""

import os
import importlib
import sys
from io import BytesIO
from typing import Optional

from fastapi import FastAPI
from fastmcp import Context, FastMCP, Image
from PIL import Image as PILImage

# Global MCP instance to be used throughout the application
mcp: Optional[FastMCP] = None

def init_mcp(app: FastAPI) -> FastMCP:
    """
    Initialize and configure the MCP server with the FastAPI app.
    
    Args:
        app: The FastAPI application instance
        
    Returns:
        FastMCP: The initialized FastMCP instance
    """
    global mcp
    
    try:
        print("Initializing MCP server with FastAPI app...")
        
        # Create MCP instance from FastAPI app
        mcp = FastMCP.from_fastapi(app, name="FastAPI Connect MCP Server")
        
        # Register basic tools and resources
        register_basic_tools(mcp)
        
        # Import custom tools and resources
        # This will register them with the MCP instance
        try:
            from app.core.mcp import tools, resources
            print("MCP custom tools and resources registered")
        except ImportError as e:
            print(f"Warning: Could not import custom MCP tools and resources: {e}")
        
        # Print all registered routes
        print("\nRegistered MCP Routes via FastAPI integration:")
        for i, route in enumerate(mcp.routes(), 1):
            print(f"{i}. {route.method} {route.path}")
            
        print(f"MCP server initialized successfully with {len(list(mcp.routes()))} routes")
        return mcp
    except Exception as e:
        print(f"ERROR: Failed to initialize MCP server: {e}")
        import traceback
        traceback.print_exc()
        # Return a blank MCP instance to prevent startup failure
        return FastMCP(name="Error MCP Server")

def register_basic_tools(mcp_instance: FastMCP) -> None:
    """
    Register basic MCP tools and resources.
    
    Args:
        mcp_instance: The FastMCP instance to register tools with
    """
    # Example tool - basic calculator
    @mcp_instance.tool()
    def calculate(operation: str, a: float, b: float, ctx: Context = None) -> dict:
        """
        Perform a basic calculation operation.
        
        Args:
            operation: The operation to perform (add, subtract, multiply, divide)
            a: First number
            b: Second number
            ctx: Optional MCP context for logging
            
        Returns:
            dict: Result of the calculation with metadata
        """
        result = None
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                if ctx:
                    ctx.error("Division by zero error")
                return {"error": "Division by zero", "result": None}
            result = a / b
        else:
            if ctx:
                ctx.error(f"Unknown operation: {operation}")
            return {"error": f"Unknown operation: {operation}", "result": None}
        
        if ctx:
            ctx.info(f"Calculation result: {result}")
        
        return {
            "operation": operation,
            "a": a,
            "b": b,
            "result": result
        }
    
    # Example resource - server info
    @mcp_instance.resource("config://server-info")
    def get_server_info(ctx: Context = None) -> dict:
        """
        Returns server configuration information.
        
        Args:
            ctx: Optional MCP context for logging
            
        Returns:
            dict: Server information
        """
        server_info = {
            "version": "1.0.0",
            "name": "FastAPI Connect",
            "environment": os.getenv("ENVIRONMENT", "development"),
        }
        
        if ctx:
            ctx.info("Server info accessed")
            
        return server_info

def get_mcp() -> Optional[FastMCP]:
    """
    Get the global MCP instance.
    
    Returns:
        Optional[FastMCP]: The global MCP instance or None if not initialized
    """
    return mcp

def run_standalone_mcp_server():
    """
    Run the MCP server as a standalone application.
    Used when executing this module directly.
    """
    # Import the FastAPI app
    try:
        print("Starting standalone MCP server...")
        
        sys.path.insert(
            0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        )
        app_module = importlib.import_module("app.main")
        fastapi_app = app_module.app
        
        print("FastAPI app imported successfully")
        
        # Initialize MCP with the FastAPI app
        mcp_server = init_mcp(fastapi_app)
        
        # Run the MCP server
        host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_SERVER_PORT", "8000"))
        
        print(f"Starting MCP server on {host}:{port}...")
        print("Available routes:")
        for i, route in enumerate(mcp_server.routes(), 1):
            print(f"{i}. {route.method} {route.path}")
            
        # Start the server with HTTP transport
        mcp_server.run(transport="http", host=host, port=port)
    except Exception as e:
        print(f"ERROR: Failed to start standalone MCP server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_standalone_mcp_server()
