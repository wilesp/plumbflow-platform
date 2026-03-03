-- ============================================================================
-- PLUMBERFLOW V2 - SUBSCRIPTION SYSTEM DATABASE MIGRATION
-- ============================================================================
-- Run this on your Railway PostgreSQL database
-- Command: psql $DATABASE_URL < database_migration_v2.sql

-- Add subscription columns to plumbers table
ALTER TABLE plumbers ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR(20) DEFAULT 'none';
ALTER TABLE plumbers ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) DEFAULT 'inactive';
ALTER TABLE plumbers ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(100);
ALTER TABLE plumbers ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(100);
ALTER TABLE plumbers ADD COLUMN IF NOT EXISTS subscription_start_date TIMESTAMP;
ALTER TABLE plumbers ADD COLUMN IF NOT EXISTS subscription_end_date TIMESTAMP;
ALTER TABLE plumbers ADD COLUMN IF NOT EXISTS trade_category VARCHAR(50) DEFAULT 'plumber';
ALTER TABLE plumbers ADD COLUMN IF NOT EXISTS trade_categories JSONB DEFAULT '["plumber"]';

-- Add trade category to jobs table
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS job_category VARCHAR(50) DEFAULT 'plumber';

-- Create quotes table for subscription model
CREATE TABLE IF NOT EXISTS quotes (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    plumber_id INTEGER REFERENCES plumbers(id) ON DELETE CASCADE,
    quote_amount DECIMAL(10,2),
    quote_message TEXT,
    quote_details JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    responded_at TIMESTAMP,
    accepted_by_customer BOOLEAN DEFAULT FALSE,
    customer_response TEXT,
    UNIQUE(job_id, plumber_id)
);

-- Create subscription transactions table
CREATE TABLE IF NOT EXISTS subscription_transactions (
    id SERIAL PRIMARY KEY,
    plumber_id INTEGER REFERENCES plumbers(id) ON DELETE CASCADE,
    stripe_payment_intent_id VARCHAR(100),
    stripe_subscription_id VARCHAR(100),
    amount DECIMAL(10,2),
    tier VARCHAR(20),
    period_start DATE,
    period_end DATE,
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_plumbers_subscription_status ON plumbers(subscription_status);
CREATE INDEX IF NOT EXISTS idx_plumbers_subscription_tier ON plumbers(subscription_tier);
CREATE INDEX IF NOT EXISTS idx_plumbers_trade_category ON plumbers(trade_category);
CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(job_category);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_quotes_job_id ON quotes(job_id);
CREATE INDEX IF NOT EXISTS idx_quotes_plumber_id ON quotes(plumber_id);
CREATE INDEX IF NOT EXISTS idx_quotes_status ON quotes(status);

-- Update existing plumbers to have plumber category
UPDATE plumbers SET trade_category = 'plumber' WHERE trade_category IS NULL;
UPDATE plumbers SET trade_categories = '["plumber"]' WHERE trade_categories IS NULL;

-- Update existing jobs to have plumber category
UPDATE jobs SET job_category = 'plumber' WHERE job_category IS NULL;

-- Add comments for documentation
COMMENT ON COLUMN plumbers.subscription_tier IS 'Subscription tier: none, basic, pro, premium';
COMMENT ON COLUMN plumbers.subscription_status IS 'Status: inactive, active, cancelled, past_due';
COMMENT ON COLUMN plumbers.trade_category IS 'Primary trade category (for filtering)';
COMMENT ON COLUMN plumbers.trade_categories IS 'All trade categories this person can do (JSONB array)';
COMMENT ON TABLE quotes IS 'Quotes sent by tradespeople to customers for jobs';
COMMENT ON TABLE subscription_transactions IS 'Record of all subscription payments';

-- Grant permissions (if using specific user)
-- GRANT ALL PRIVILEGES ON TABLE quotes TO your_app_user;
-- GRANT ALL PRIVILEGES ON TABLE subscription_transactions TO your_app_user;
-- GRANT USAGE, SELECT ON SEQUENCE quotes_id_seq TO your_app_user;
-- GRANT USAGE, SELECT ON SEQUENCE subscription_transactions_id_seq TO your_app_user;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- Next steps:
-- 1. Verify migration: SELECT column_name FROM information_schema.columns WHERE table_name='plumbers';
-- 2. Check new tables: \dt quotes
-- 3. Deploy updated main.py with subscription endpoints
-- ============================================================================
