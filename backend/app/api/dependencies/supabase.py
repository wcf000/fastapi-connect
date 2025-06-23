from typing import Annotated
from fastapi import Depends, HTTPException, status
from app.core.third_party_integrations.supabase_home.client import supabase

def get_supabase_database():
    """
    Dependency to get the Supabase database service
    """
    return supabase.get_database_service()

def get_supabase_auth():
    """
    Dependency to get the Supabase auth service
    """
    return supabase.get_auth_service()

def get_supabase_storage():
    """
    Dependency to get the Supabase storage service
    """
    return supabase.get_storage_service()

def get_supabase_edge_functions():
    """
    Dependency to get the Supabase edge functions service
    """
    return supabase.get_edge_functions_service()

def get_supabase_realtime():
    """
    Dependency to get the Supabase realtime service
    """
    return supabase.get_realtime_service()

# Create annotated dependencies for easy use in route functions
SupabaseDatabase = Annotated[get_supabase_database.__annotations__["return"], Depends(get_supabase_database)]
SupabaseAuth = Annotated[get_supabase_auth.__annotations__["return"], Depends(get_supabase_auth)]
SupabaseStorage = Annotated[get_supabase_storage.__annotations__["return"], Depends(get_supabase_storage)]
SupabaseEdgeFunctions = Annotated[get_supabase_edge_functions.__annotations__["return"], Depends(get_supabase_edge_functions)]
SupabaseRealtime = Annotated[get_supabase_realtime.__annotations__["return"], Depends(get_supabase_realtime)]
