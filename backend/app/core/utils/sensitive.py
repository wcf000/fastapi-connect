import os
from pathlib import Path
from dotenv import load_dotenv

def load_environment_files():
    """
    Loads environment variables from a .env file located at the project root.
    This function is safe to call multiple times and will not overwrite existing environment variables unless override=True.
    """
    # Try to find the .env file two or three levels up from this file
    possible_paths = [
        Path(__file__).resolve().parents[2] / '.env',
        Path(__file__).resolve().parents[4] / '.env',
        Path(__file__).resolve().parents[5] / '.env',
        Path(__file__).resolve().parents[3] / '.env',
        Path(__file__).resolve().parents[1] / '.env',
        Path.cwd() / '.env',
    ]
    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
            print(f"Loaded .env from: {env_path}")
            break
    else:
        print("Warning: .env file not found in any expected location.")

    # Debug: Print Supabase envs
    print(f"SUPABASE_URL: {os.getenv('SUPABASE_URL', 'Not found')}")
    print(f"SUPABASE_ANON_KEY: {os.getenv('SUPABASE_ANON_KEY', 'Not found')}")
    print(f"SUPABASE_SERVICE_ROLE_KEY: {os.getenv('SUPABASE_SERVICE_ROLE_KEY', 'Not found')[:5]}... (truncated)")
