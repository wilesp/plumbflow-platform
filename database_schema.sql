-- ============================================================================
-- PLUMBERFLOW DATABASE SCHEMA
-- PostgreSQL Database for Production
-- ============================================================================

-- Drop existing tables (for clean migration)
DROP TABLE IF EXISTS accepted_leads CASCADE;
DROP TABLE IF EXISTS pending_leads CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;
DROP TABLE IF EXISTS plumbers CASCADE;

-- ============================================================================
-- PLUMBERS TABLE
-- ============================================================================

CREATE TABLE plumbers (
    id VARCHAR(50) PRIMARY KEY,
    business_name VARCHAR(200) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    email VARCHAR(200) NOT NULL UNIQUE,
    phone VARCHAR(20) NOT NULL UNIQUE,
    postcode VARCHAR(10) NOT NULL,
    areas_served TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    years_experience INTEGER,
    gas_safe_number VARCHAR(50),
    qualifications TEXT,
    stripe_customer_id VARCHAR(100),
    stripe_payment_method_id VARCHAR(100),
    membership_tier VARCHAR(20) DEFAULT 'free',
    membership_started_at TIMESTAMP,
    membership_expires_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active',
    verified BOOLEAN DEFAULT false,
    total_leads_received INTEGER DEFAULT 0,
    total_leads_accepted INTEGER DEFAULT 0,
    total_revenue_generated DECIMAL(10, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_plumbers_phone ON plumbers(phone);
CREATE INDEX idx_plumbers_postcode ON plumbers(postcode);
CREATE INDEX idx_plumbers_membership ON plumbers(membership_tier);
CREATE INDEX idx_plumbers_status ON plumbers(status);

-- ============================================================================
-- JOBS TABLE
-- ============================================================================

CREATE TABLE jobs (
    id VARCHAR(50) PRIMARY KEY,
    customer_name VARCHAR(200) NOT NULL,
    email VARCHAR(200),
    phone VARCHAR(20) NOT NULL,
    postcode VARCHAR(10) NOT NULL,
    address TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    job_type VARCHAR(100) NOT NULL,
    title VARCHAR(200),
    description TEXT NOT NULL,
    urgency VARCHAR(20) NOT NULL,
    property_type VARCHAR(50),
    property_age VARCHAR(50),
    job_details JSONB,
    photo_url TEXT,
    photo_base64 TEXT,
    price_low INTEGER,
    price_typical INTEGER,
    price_high INTEGER,
    confidence VARCHAR(20),
    callout_fee INTEGER,
    labor_cost INTEGER,
    parts_cost_low INTEGER,
    parts_cost_high INTEGER,
    complications JSONB,
    lead_fee INTEGER DEFAULT 18,
    status VARCHAR(20) DEFAULT 'pending',
    assigned_plumber_id VARCHAR(50),
    accepted_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY (assigned_plumber_id) REFERENCES plumbers(id) ON DELETE SET NULL
);

CREATE INDEX idx_jobs_postcode ON jobs(postcode);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_job_type ON jobs(job_type);
CREATE INDEX idx_jobs_urgency ON jobs(urgency);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX idx_jobs_assigned_plumber ON jobs(assigned_plumber_id);

-- ============================================================================
-- PENDING_LEADS TABLE
-- ============================================================================

CREATE TABLE pending_leads (
    job_id VARCHAR(50) NOT NULL,
    plumber_id VARCHAR(50) NOT NULL,
    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notification_method VARCHAR(20),
    magic_link_token TEXT,
    token_expires_at TIMESTAMP,
    notification_delay_minutes INTEGER DEFAULT 0,
    viewed BOOLEAN DEFAULT false,
    viewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (job_id, plumber_id),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (plumber_id) REFERENCES plumbers(id) ON DELETE CASCADE
);

CREATE INDEX idx_pending_leads_plumber ON pending_leads(plumber_id);
CREATE INDEX idx_pending_leads_job ON pending_leads(job_id);
CREATE INDEX idx_pending_leads_notified ON pending_leads(notified_at DESC);

-- ============================================================================
-- ACCEPTED_LEADS TABLE
-- ============================================================================

CREATE TABLE accepted_leads (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(50) NOT NULL,
    plumber_id VARCHAR(50) NOT NULL,
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acceptance_method VARCHAR(20),
    lead_fee DECIMAL(10, 2) NOT NULL,
    stripe_charge_id VARCHAR(100),
    stripe_charge_status VARCHAR(20),
    payment_error TEXT,
    outcome VARCHAR(20),
    outcome_notes TEXT,
    outcome_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (plumber_id) REFERENCES plumbers(id) ON DELETE CASCADE,
    UNIQUE(job_id)
);

CREATE INDEX idx_accepted_leads_plumber ON accepted_leads(plumber_id);
CREATE INDEX idx_accepted_leads_job ON accepted_leads(job_id);
CREATE INDEX idx_accepted_leads_accepted_at ON accepted_leads(accepted_at DESC);
CREATE INDEX idx_accepted_leads_stripe_charge ON accepted_leads(stripe_charge_id);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_plumbers_updated_at
    BEFORE UPDATE ON plumbers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
