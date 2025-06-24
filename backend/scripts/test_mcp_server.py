"""
MCP server integration test script.

This script tests the MCP server integration with the FastAPI app.
"""

import asyncio
import json
import sys
import inspect
from fastmcp.client import Client

async def test_mcp_server(server_url="http://localhost:8000"):
    """Test MCP server endpoints"""
    print(f"Testing MCP server at {server_url}")
    # Connect to the MCP server using the recommended context manager pattern
    client = Client(server_url)
    
    async with client:  # This properly connects the client
        try:
            # List available tools
            print("\nListing available tools...")
            tools = await client.list_tools()
            print(f"Available tools: {json.dumps(tools, indent=2)}")
            
            # List available resources
            print("\nListing available resources...")
            resources = await client.list_resources()
            print(f"Available resources: {json.dumps(resources, indent=2)}")
            
            # Test getting MCP info (using proper method)
            print("\nGetting MCP info...")
            try:
                info = await client.info()  # Try this method
                print(f"MCP Info: {json.dumps(info, indent=2)}")
            except Exception as e:
                print(f"Error getting info: {e}")
            
            # Test calculate tool if it exists
            if any("calculate" in tool for tool in tools):
                print("\nTesting calculate tool...")
                result = await client.call_tool("calculate", {
                    "operation": "add",
                    "a": 5,
                    "b": 3
                })
                print(f"Calculation result: {json.dumps(result, indent=2)}")
            else:
                print("\nCalculate tool not available")
            
            # Test weather forecast tool if it exists
            if any("get_weather_forecast" in tool for tool in tools):
                print("\nTesting weather forecast tool...")
                try:
                    weather = await client.call_tool("get_weather_forecast", {
                        "city": "London",
                        "days": 3
                    })
                    print(f"Weather forecast: {json.dumps(weather, indent=2)}")
                except Exception as e:
                    print(f"Error calling get_weather_forecast: {e}")
            else:
                print("\nWeather forecast tool not available")
            
            # Test app version resource
            try:
                print("\nTesting version resource...")
                # First try the integrated app's resource path
                try:
                    version = await client.read_resource("app://version/latest")
                    print(f"App version (app://version/latest): {version}")
                except Exception as e:
                    print(f"Error reading app://version/latest: {e}")
                
                # Then try the standalone test server's resource path
                try:
                    version = await client.read_resource("test://version/latest")
                    print(f"Test version (test://version/latest): {version}")
                except Exception as e:
                    print(f"Error reading test://version/latest: {e}")
                    
                # Also try config resource paths
                try:
                    config = await client.read_resource("config://server-info")
                    print(f"Server info (config://server-info): {json.dumps(config, indent=2)}")
                except Exception as e:
                    print(f"Error reading config://server-info: {e}")
                    
                try:
                    config = await client.read_resource("config://app-version")
                    print(f"App version (config://app-version): {config}")
                except Exception as e:
                    print(f"Error reading config://app-version: {e}")
            except Exception as e:
                print(f"Error testing resources: {e}")
            
            print("\nAll tests completed.")
            
        except Exception as e:
            print(f"Error testing MCP server: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # Check if an argument was provided for the server URL
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
        asyncio.run(test_mcp_server(server_url))
    else:
        # Try the standalone server first (more likely to work for testing)
        print("No server URL provided, trying the standalone MCP server first...")
        asyncio.run(test_mcp_server("http://localhost:8765"))
        
        # Optionally try the integrated server as well
        try_integrated = input("\nDo you want to also test the integrated server at http://localhost:8000? (y/n): ")
        if try_integrated.lower() in ['y', 'yes']:
            asyncio.run(test_mcp_server("http://localhost:8000"))
