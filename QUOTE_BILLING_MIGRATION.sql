-- ============================================================================
-- QUOTE BILLING & LEAD GENERATION MIGRATION
-- Run this SQL in your Supabase SQL Editor AFTER QUOTE_FEATURE_MIGRATION.sql
-- ============================================================================

-- ============================================================================
-- 1. ADD COMPANY_DESCRIPTION TO VENDOR_SERVICES
-- ============================================================================
ALTER TABLE vendor_services ADD COLUMN IF NOT EXISTS company_description text;

-- ============================================================================
-- 2. QUOTE_IMPRESSIONS TABLE - Tracks when vendor quotes are shown (billing)
-- ============================================================================
CREATE TABLE IF NOT EXISTS quote_impressions (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- The quote context
    quote_request_id uuid NOT NULL REFERENCES quote_requests(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    segment text NOT NULL REFERENCES segments(id),
    
    -- The vendor whose quote was shown
    vendor_service_id uuid NOT NULL REFERENCES vendor_services(id) ON DELETE CASCADE,
    vendor_email text NOT NULL,
    vendor_company_name text NOT NULL,
    
    -- The customer who saw the quote (for vendor's lead info)
    customer_user_id uuid NOT NULL,
    customer_email text NOT NULL,
    customer_name text,
    project_name text NOT NULL,
    project_location text NOT NULL,
    project_sqft integer NOT NULL,
    
    -- The quote details (snapshot at time of display)
    quoted_rate_per_sf numeric(10,2) NOT NULL,
    quoted_total numeric(12,2) NOT NULL,
    
    -- Billing
    amount_charged numeric(10,2) NOT NULL DEFAULT 250.00,
    billing_status text NOT NULL DEFAULT 'pending',
    -- Values: 'pending', 'invoiced', 'paid', 'waived'
    
    -- Email notification tracking
    email_sent_at timestamptz,
    email_status text DEFAULT 'pending',
    -- Values: 'pending', 'sent', 'failed'
    
    -- Metadata
    created_at timestamptz DEFAULT now(),
    
    -- CRITICAL: Prevent duplicate charges for same project+segment+vendor
    CONSTRAINT unique_impression_per_project_segment_vendor 
        UNIQUE(project_id, segment, vendor_service_id)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_impressions_vendor ON quote_impressions(vendor_email);
CREATE INDEX IF NOT EXISTS idx_impressions_project ON quote_impressions(project_id);
CREATE INDEX IF NOT EXISTS idx_impressions_customer ON quote_impressions(customer_user_id);
CREATE INDEX IF NOT EXISTS idx_impressions_billing ON quote_impressions(billing_status) WHERE billing_status = 'pending';
CREATE INDEX IF NOT EXISTS idx_impressions_email ON quote_impressions(email_status) WHERE email_status = 'pending';

-- ============================================================================
-- 3. ROW LEVEL SECURITY - CRITICAL FOR DATA ISOLATION
-- ============================================================================

ALTER TABLE quote_impressions ENABLE ROW LEVEL SECURITY;

-- Vendors can ONLY see their own impressions (leads)
CREATE POLICY "Vendors see only their own impressions" ON quote_impressions
    FOR SELECT USING (
        vendor_email = auth.jwt() ->> 'email'
    );

-- Customers can see impressions for their own projects (quote history)
CREATE POLICY "Customers see impressions for their projects" ON quote_impressions
    FOR SELECT USING (
        project_id IN (SELECT id FROM projects WHERE user_id = auth.uid())
    );

-- Only system can insert impressions (via service role)
CREATE POLICY "System can insert impressions" ON quote_impressions
    FOR INSERT WITH CHECK (true);

-- Only system can update impressions (billing status, email status)
CREATE POLICY "System can update impressions" ON quote_impressions
    FOR UPDATE USING (true);

-- ============================================================================
-- 4. HELPER VIEW FOR VENDOR DASHBOARD (Optional but useful)
-- ============================================================================
CREATE OR REPLACE VIEW vendor_lead_summary AS
SELECT 
    vendor_email,
    COUNT(*) as total_leads,
    SUM(amount_charged) as total_owed,
    SUM(CASE WHEN billing_status = 'paid' THEN amount_charged ELSE 0 END) as total_paid,
    SUM(CASE WHEN billing_status = 'pending' THEN amount_charged ELSE 0 END) as balance_due
FROM quote_impressions
GROUP BY vendor_email;

-- ============================================================================
-- 5. ADD PHONE TO USER_INFO (for future use)
-- ============================================================================
ALTER TABLE user_info ADD COLUMN IF NOT EXISTS phone text;

-- ============================================================================
-- VERIFICATION QUERIES
-- Run these after migration to verify:
-- ============================================================================
-- \d quote_impressions  -- Check table structure
-- SELECT * FROM vendor_lead_summary;  -- Should be empty initially
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'vendor_services' AND column_name = 'company_description';
