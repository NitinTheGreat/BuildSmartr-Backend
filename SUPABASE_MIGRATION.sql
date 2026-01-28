-- ============================================================================
-- SUPABASE MIGRATION: Add AI Integration Columns
-- ============================================================================
-- Run this SQL in your Supabase SQL Editor to add AI integration support.
-- 
-- This adds two columns to the projects table:
-- 1. ai_project_id: The Pinecone namespace ID (e.g., "microsoft_azure_a1b2c3d4")
-- 2. indexing_status: Current indexing status
-- ============================================================================

-- Add ai_project_id column
-- This stores the AI backend's project ID (Pinecone namespace)
-- Format: {project_name_normalized}_{8_char_hash_of_user_email}
-- Example: "microsoft_azure_a1b2c3d4"
ALTER TABLE projects ADD COLUMN IF NOT EXISTS ai_project_id TEXT;

-- Add indexing_status column
-- Tracks the current state of AI indexing
-- Values: 'not_started', 'indexing', 'completed', 'failed', 'cancelled'
ALTER TABLE projects ADD COLUMN IF NOT EXISTS indexing_status TEXT DEFAULT 'not_started';

-- Add indexing_error column
-- Stores the error message when indexing fails
-- NULL when status is not 'failed'
ALTER TABLE projects ADD COLUMN IF NOT EXISTS indexing_error TEXT;

-- Create index for faster lookups by ai_project_id
CREATE INDEX IF NOT EXISTS idx_projects_ai_project_id ON projects(ai_project_id);

-- Create index for filtering by indexing_status
CREATE INDEX IF NOT EXISTS idx_projects_indexing_status ON projects(indexing_status);

-- ============================================================================
-- VERIFICATION QUERY
-- Run this after migration to verify the columns were added:
-- ============================================================================
-- SELECT column_name, data_type, column_default 
-- FROM information_schema.columns 
-- WHERE table_name = 'projects' 
-- AND column_name IN ('ai_project_id', 'indexing_status');

-- ============================================================================
-- EXAMPLE DATA (for testing)
-- ============================================================================
-- After indexing a project, the data will look like:
-- 
-- id: "550e8400-e29b-41d4-a716-446655440000"  (Supabase UUID)
-- name: "Microsoft Azure"
-- ai_project_id: "microsoft_azure_a1b2c3d4"   (Pinecone namespace)
-- indexing_status: "completed"
