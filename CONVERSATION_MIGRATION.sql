-- ============================================================================
-- SUPABASE MIGRATION: Add Conversation Memory Support
-- ============================================================================
-- Run this SQL in your Supabase SQL Editor to add conversation memory support.
-- 
-- This adds columns to the chats table for conversation summaries:
-- 1. summary: Compressed conversation context (structured text)
-- 2. summary_updated_at: Timestamp of last summary update
-- 3. message_count_at_summary: Message count when summary was last generated
-- ============================================================================

-- Add summary column
-- Stores compressed conversation context in structured format
-- Format:
-- ## Current Focus
-- [One sentence on what user is investigating]
-- 
-- ## Entities (preserve verbatim)
-- - People: ...
-- - Vendors: ...
-- - Invoices: ...
-- 
-- ## Findings
-- - ...
-- 
-- ## Open Questions
-- - ...
ALTER TABLE chats ADD COLUMN IF NOT EXISTS summary TEXT;

-- Add summary_updated_at column
-- Tracks when the summary was last regenerated
ALTER TABLE chats ADD COLUMN IF NOT EXISTS summary_updated_at TIMESTAMPTZ;

-- Add message_count_at_summary column
-- Tracks how many messages existed when summary was generated
-- Used to determine when to regenerate (every ~8 messages)
ALTER TABLE chats ADD COLUMN IF NOT EXISTS message_count_at_summary INTEGER DEFAULT 0;

-- ============================================================================
-- UPDATE MESSAGES TABLE: Enhanced sources schema
-- ============================================================================
-- The sources column now stores richer debug information:
-- {
--   "retrieved": [{"chunk_id": "...", "file_id": "...", "score": 0.78, "page": 3}],
--   "cited": [{"chunk_id": "...", "file_id": "...", "page": 3}],
--   "rewrite": {
--     "original": "what about the second one?",
--     "standalone": "What is the amount of Invoice INV-1043?"
--   }
-- }
-- (No schema change needed - sources is already JSONB)

-- ============================================================================
-- VERIFICATION QUERY
-- Run this after migration to verify the columns were added:
-- ============================================================================
-- SELECT column_name, data_type, column_default 
-- FROM information_schema.columns 
-- WHERE table_name = 'chats' 
-- AND column_name IN ('summary', 'summary_updated_at', 'message_count_at_summary');

-- ============================================================================
-- EXAMPLE DATA (for reference)
-- ============================================================================
-- After a conversation with ~10 messages, the chat might look like:
-- 
-- id: "550e8400-e29b-41d4-a716-446655440000"
-- project_id: "660f9500-f39c-51e5-b827-557766550001"
-- title: "Foundation Costs"
-- summary: "## Current Focus\nInvestigating foundation costs and vendor quotes\n\n## Entities\n- Vendors: ABC Contractors, XYZ Foundation\n- Invoices: INV-1043 ($47,500)\n- People: John from Acme\n\n## Findings\n- ABC quoted $47,500 for pile work\n- Pile length is 45 feet per Drawing S-201\n\n## Open Questions\n- Waiting for XYZ counter-quote"
-- summary_updated_at: "2025-01-29T10:30:00Z"
-- message_count_at_summary: 8
