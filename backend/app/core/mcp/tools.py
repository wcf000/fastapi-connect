"""
Custom MCP tools for the FastAPI Connect application.

This module contains custom MCP tools that can be used by LLMs or other clients
to interact with the application.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastmcp import Context, mcp

# Import the global MCP instance
from app.core.mcp_server import get_mcp

# Get the MCP instance
mcp = get_mcp()

# Define Pydantic models for tool input/output
class UserData(BaseModel):
    """User data for creating or updating users"""
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool = True

class UserResponse(BaseModel):
    """Response model for user operations"""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    message: str

# Register tools with the MCP instance if available
if mcp:
    @mcp.tool()
    async def get_system_stats(ctx: Optional[Context] = None) -> Dict[str, Any]:
        """
        Get system statistics including user count, database status, etc.
        
        Args:
            ctx: Optional MCP context
            
        Returns:
            Dict: System statistics
        """
        # In a real implementation, you would fetch actual system stats
        stats = {
            "user_count": 100,
            "active_sessions": 25,
            "database_status": "healthy",
            "api_requests_per_minute": 150,
            "system_uptime": "5 days, 6 hours",
        }
        
        if ctx:
            await ctx.info("System stats retrieved")
            
        return stats
    
    @mcp.tool()
    async def create_user(user_data: UserData, ctx: Optional[Context] = None) -> UserResponse:
        """
        Create a new user in the system.
        
        Args:
            user_data: User data including username, email, etc.
            ctx: Optional MCP context
            
        Returns:
            UserResponse: Created user information
        """
        # In a real implementation, you would call your user creation service
        # For now, we'll just return a mock response
        
        if ctx:
            await ctx.info(f"Creating user with username: {user_data.username}")
            await ctx.report_progress(1, 2)
        
        # Simulate user creation
        user_id = "usr_" + user_data.username.lower()
        
        if ctx:
            await ctx.info(f"User created with ID: {user_id}")
            await ctx.report_progress(2, 2)
            
        return UserResponse(
            id=user_id,
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name,
            is_active=user_data.is_active,
            message=f"User {user_data.username} created successfully"
        )
    
    @mcp.tool()
    async def search_users(query: str, limit: int = 10, ctx: Optional[Context] = None) -> List[Dict[str, Any]]:
        """
        Search for users based on a query string.
        
        Args:
            query: Search query (username, email, etc.)
            limit: Maximum number of results to return
            ctx: Optional MCP context
            
        Returns:
            List[Dict]: List of users matching the query
        """
        # In a real implementation, you would query your database
        # For now, we'll return mock data
        
        if ctx:
            await ctx.info(f"Searching for users with query: {query}")
        
        # Mock user data
        users = [
            {"id": "usr_john", "username": "john_doe", "email": "john@example.com", "full_name": "John Doe"},
            {"id": "usr_jane", "username": "jane_doe", "email": "jane@example.com", "full_name": "Jane Doe"},
            {"id": "usr_bob", "username": "bob_smith", "email": "bob@example.com", "full_name": "Bob Smith"},
        ]
        
        # Filter users based on query
        filtered_users = [
            user for user in users 
            if query.lower() in user["username"].lower() 
            or query.lower() in user["email"].lower()
            or (user.get("full_name") and query.lower() in user["full_name"].lower())
        ]
        
        # Apply limit
        results = filtered_users[:limit]
        
        if ctx:
            await ctx.info(f"Found {len(results)} users matching query: {query}")
            
        return results
    
    @mcp.tool()
    async def get_weather_forecast(city: str, days: int = 3, ctx: Optional[Context] = None) -> Dict[str, Any]:
        """
        Get a mock weather forecast for a city.
        
        Args:
            city: The name of the city to get the forecast for
            days: Number of days to forecast (1-7)
            ctx: Optional MCP context
            
        Returns:
            Dict[str, Any]: Weather forecast data
        """
        import random
        
        if ctx:
            await ctx.info(f"Getting weather forecast for {city} for {days} days")
        
        # Limit days to 1-7 range
        days = max(1, min(7, days))
        
        # Mock weather conditions
        conditions = ["Sunny", "Partly Cloudy", "Cloudy", "Rainy", "Thunderstorms", "Snowy", "Windy"]
        
        # Generate a deterministic but random-looking forecast based on city name
        # This ensures the same city always gets the same forecast
        city_seed = sum(ord(c) for c in city)
        random.seed(city_seed)
        
        forecast = {
            "city": city,
            "country": "Mock Country",
            "days": []
        }
        
        for i in range(days):
            temp_high = random.randint(15, 35)  # Celsius
            temp_low = temp_high - random.randint(5, 15)
            condition = random.choice(conditions)
            humidity = random.randint(30, 90)
            
            forecast["days"].append({
                "day": i + 1,
                "condition": condition,
                "temperature_high": temp_high,
                "temperature_low": temp_low,
                "humidity": humidity,
                "chance_of_rain": random.randint(0, 100) if "Rain" in condition or "Thunder" in condition else random.randint(0, 30)
            })
        
        if ctx:
            await ctx.info(f"Generated forecast with {len(forecast['days'])} days")
        
        return forecast
