-- Supabase SQL Setup Script
-- Execute this in the Supabase SQL Editor at https://app.supabase.com/project/_/sql

-- Create UUID extension if it doesn't exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create user table
CREATE TABLE IF NOT EXISTS "user" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    full_name TEXT
);

-- Set up RLS policies for user table
ALTER TABLE "user" ENABLE ROW LEVEL SECURITY;

-- Create policy to allow authenticated users to read any user
DROP POLICY IF EXISTS "Allow authenticated users to read any user" ON "user";
CREATE POLICY "Allow authenticated users to read any user"
ON "user"
FOR SELECT
TO authenticated
USING (true);

-- Create policy to allow users to update their own data
DROP POLICY IF EXISTS "Allow users to update their own data" ON "user";
CREATE POLICY "Allow users to update their own data"
ON "user"
FOR UPDATE
TO authenticated
USING (auth.uid()::text = id::text)
WITH CHECK (auth.uid()::text = id::text);

-- Create item table
CREATE TABLE IF NOT EXISTS "item" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE
);

-- Set up RLS policies for item table
ALTER TABLE "item" ENABLE ROW LEVEL SECURITY;

-- Create policy to allow authenticated users to read their own items
DROP POLICY IF EXISTS "Allow users to read their own items" ON "item";
CREATE POLICY "Allow users to read their own items"
ON "item"
FOR SELECT
TO authenticated
USING (auth.uid()::text = owner_id::text);

-- Create policy to allow users to insert their own items
DROP POLICY IF EXISTS "Allow users to insert their own items" ON "item";
CREATE POLICY "Allow users to insert their own items"
ON "item"
FOR INSERT
TO authenticated
WITH CHECK (auth.uid()::text = owner_id::text);

-- Create policy to allow users to update their own items
DROP POLICY IF EXISTS "Allow users to update their own items" ON "item";
CREATE POLICY "Allow users to update their own items"
ON "item"
FOR UPDATE
TO authenticated
USING (auth.uid()::text = owner_id::text)
WITH CHECK (auth.uid()::text = owner_id::text);

-- Create policy to allow users to delete their own items
DROP POLICY IF EXISTS "Allow users to delete their own items" ON "item";
CREATE POLICY "Allow users to delete their own items"
ON "item"
FOR DELETE
TO authenticated
USING (auth.uid()::text = owner_id::text);

-- Grant permissions to the authenticated role
GRANT ALL ON "user" TO authenticated;
GRANT ALL ON "item" TO authenticated;

-- Create exec_sql function for future use
CREATE OR REPLACE FUNCTION exec_sql(query text) 
RETURNS JSONB 
LANGUAGE plpgsql
SECURITY DEFINER -- Run with privileges of the function creator
SET search_path = public
AS $$
DECLARE
    result JSONB;
BEGIN
    EXECUTE query;
    RETURN jsonb_build_object('success', true);
EXCEPTION WHEN OTHERS THEN
    RETURN jsonb_build_object(
        'success', false,
        'error', SQLERRM,
        'detail', SQLSTATE
    );
END;
$$;

-- Grant execute permission on the function
GRANT EXECUTE ON FUNCTION exec_sql TO authenticated;
GRANT EXECUTE ON FUNCTION exec_sql TO anon;
GRANT EXECUTE ON FUNCTION exec_sql TO service_role;
