-- ================================================================
-- PLUMBER MATCHING PLATFORM - DATABASE SCHEMA
-- ================================================================

-- Drop existing tables (for clean setup)
DROP TABLE IF EXISTS job_updates CASCADE;
DROP TABLE IF EXISTS invoices CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS job_assignments CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS plumber_availability CASCADE;
DROP TABLE IF EXISTS plumber_skills CASCADE;
DROP TABLE IF EXISTS plumber_postcodes CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;
DROP TABLE IF EXISTS plumbers CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS pricing_cards CASCADE;
DROP TABLE IF EXISTS scraped_ads CASCADE;

-- ================================================================
-- PLUMBERS TABLE
-- ================================================================
CREATE TABLE plumbers (
    id SERIAL PRIMARY KEY,
    
    -- Basic Info
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) NOT NULL,
    company_name VARCHAR(255),
    
    -- Location
    base_postcode VARCHAR(10) NOT NULL,
    base_latitude DECIMAL(10, 8),
    base_longitude DECIMAL(11, 8),
    
    -- Rates
    hourly_rate DECIMAL(6, 2) DEFAULT 60.00,
    emergency_rate DECIMAL(6, 2) DEFAULT 90.00,
    minimum_callout DECIMAL(6, 2) DEFAULT 75.00,
    travel_rate DECIMAL(6, 2) DEFAULT 60.00,
    
    -- Credentials
    gas_safe_certified BOOLEAN DEFAULT false,
    gas_safe_number VARCHAR(50),
    insurance_verified BOOLEAN DEFAULT false,
    
    -- Account Status
    status VARCHAR(20) DEFAULT 'active', -- active, paused, suspended
    credit_balance DECIMAL(8, 2) DEFAULT 0.00,
    auto_reload_enabled BOOLEAN DEFAULT false,
    auto_reload_threshold DECIMAL(6, 2) DEFAULT 50.00,
    auto_reload_amount DECIMAL(6, 2) DEFAULT 250.00,
    
    -- Performance Metrics
    total_leads_sent INTEGER DEFAULT 0,
    total_leads_accepted INTEGER DEFAULT 0,
    total_jobs_completed INTEGER DEFAULT 0,
    average_rating DECIMAL(3, 2) DEFAULT 0.00,
    contact_rate DECIMAL(4, 3) DEFAULT 0.00, -- % of leads where plumber contacted customer
    conversion_rate DECIMAL(4, 3) DEFAULT 0.00, -- % of leads that became jobs
    
    -- Notification Preferences
    notify_push BOOLEAN DEFAULT true,
    notify_sms BOOLEAN DEFAULT true,
    notify_email BOOLEAN DEFAULT true,
    notify_voice BOOLEAN DEFAULT false, -- Emergency voice calls
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP
);

CREATE INDEX idx_plumbers_postcode ON plumbers(base_postcode);
CREATE INDEX idx_plumbers_status ON plumbers(status);
CREATE INDEX idx_plumbers_gas_safe ON plumbers(gas_safe_certified);

-- ================================================================
-- PLUMBER POSTCODES (Service Areas)
-- ================================================================
CREATE TABLE plumber_postcodes (
    id SERIAL PRIMARY KEY,
    plumber_id INTEGER REFERENCES plumbers(id) ON DELETE CASCADE,
    postcode_prefix VARCHAR(6) NOT NULL, -- e.g., 'SW19', 'CR4'
    priority VARCHAR(20) DEFAULT 'secondary', -- primary, secondary, extended
    min_job_value DECIMAL(6, 2) DEFAULT 0.00, -- Only accept if job worth at least this
    max_distance_km DECIMAL(5, 2) DEFAULT 20.00,
    
    UNIQUE(plumber_id, postcode_prefix)
);

CREATE INDEX idx_plumber_postcodes_prefix ON plumber_postcodes(postcode_prefix);

-- ================================================================
-- PLUMBER SKILLS
-- ================================================================
CREATE TABLE plumber_skills (
    id SERIAL PRIMARY KEY,
    plumber_id INTEGER REFERENCES plumbers(id) ON DELETE CASCADE,
    skill_type VARCHAR(50) NOT NULL, -- leak_repair, boiler_repair, toilet_replacement, etc.
    proficiency VARCHAR(20) DEFAULT 'competent', -- basic, competent, expert
    
    UNIQUE(plumber_id, skill_type)
);

CREATE INDEX idx_plumber_skills_type ON plumber_skills(skill_type);

-- ================================================================
-- PLUMBER AVAILABILITY
-- ================================================================
CREATE TABLE plumber_availability (
    id SERIAL PRIMARY KEY,
    plumber_id INTEGER REFERENCES plumbers(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    is_available BOOLEAN DEFAULT true,
    max_jobs INTEGER DEFAULT 5, -- Max jobs willing to accept that day
    notes TEXT,
    
    UNIQUE(plumber_id, date)
);

CREATE INDEX idx_availability_date ON plumber_availability(plumber_id, date);

-- ================================================================
-- PRICING CARDS (Job Type Templates)
-- ================================================================
CREATE TABLE pricing_cards (
    id SERIAL PRIMARY KEY,
    
    -- Job Definition
    job_type VARCHAR(100) UNIQUE NOT NULL, -- leaking_tap, burst_pipe, etc.
    display_name VARCHAR(255) NOT NULL,
    category VARCHAR(50), -- quick_fix, standard, complex
    
    -- Time Estimates
    base_time_hours DECIMAL(4, 2) NOT NULL,
    complexity_easy_multiplier DECIMAL(3, 2) DEFAULT 1.0,
    complexity_medium_multiplier DECIMAL(3, 2) DEFAULT 1.5,
    complexity_hard_multiplier DECIMAL(3, 2) DEFAULT 2.5,
    
    -- Requirements
    skill_level VARCHAR(20) DEFAULT 'basic', -- basic, medium, advanced
    gas_safe_required BOOLEAN DEFAULT false,
    
    -- Parts Cost Range
    parts_cost_min DECIMAL(6, 2) DEFAULT 0.00,
    parts_cost_max DECIMAL(6, 2) DEFAULT 100.00,
    parts_cost_typical DECIMAL(6, 2) DEFAULT 20.00,
    
    -- Pricing Modifiers
    urgency_multiplier DECIMAL(3, 2) DEFAULT 1.0,
    is_emergency_job BOOLEAN DEFAULT false,
    
    -- Metadata
    description TEXT,
    common_complications JSONB,
    keywords TEXT[], -- For AI matching
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Populate with common job types
INSERT INTO pricing_cards (job_type, display_name, category, base_time_hours, skill_level, parts_cost_typical, keywords) VALUES
('leaking_tap', 'Leaking Tap Repair', 'quick_fix', 0.5, 'basic', 8.00, ARRAY['tap', 'drip', 'leak', 'washer']),
('toilet_flush', 'Toilet Flush Repair', 'quick_fix', 0.75, 'basic', 20.00, ARRAY['toilet', 'flush', 'cistern', 'running']),
('unblock_sink', 'Unblock Sink/Drain', 'quick_fix', 0.75, 'basic', 15.00, ARRAY['blocked', 'drain', 'sink', 'slow']),
('replace_tap', 'Replace Tap', 'standard', 1.0, 'basic', 50.00, ARRAY['tap', 'replace', 'install', 'new']),
('burst_pipe', 'Burst Pipe Repair', 'standard', 1.5, 'medium', 40.00, ARRAY['burst', 'pipe', 'leak', 'emergency']),
('toilet_replacement', 'Toilet Replacement', 'standard', 2.0, 'medium', 150.00, ARRAY['toilet', 'replace', 'new', 'install']),
('radiator_replacement', 'Radiator Replacement', 'standard', 2.5, 'medium', 120.00, ARRAY['radiator', 'replace', 'heating']),
('boiler_repair', 'Boiler Repair', 'complex', 2.5, 'advanced', 150.00, ARRAY['boiler', 'heating', 'no heat', 'gas']),
('shower_installation', 'Shower Installation', 'complex', 5.0, 'advanced', 600.00, ARRAY['shower', 'install', 'bathroom']),
('bathroom_fitting', 'Bathroom Fitting', 'complex', 16.0, 'advanced', 1200.00, ARRAY['bathroom', 'suite', 'full', 'refit']);

UPDATE pricing_cards SET gas_safe_required = true WHERE job_type IN ('boiler_repair');
UPDATE pricing_cards SET is_emergency_job = true, urgency_multiplier = 1.5 WHERE job_type IN ('burst_pipe', 'boiler_repair');

-- ================================================================
-- SCRAPED ADS (Raw leads from scraping)
-- ================================================================
CREATE TABLE scraped_ads (
    id SERIAL PRIMARY KEY,
    
    -- Source Info
    source_platform VARCHAR(50) NOT NULL, -- gumtree, facebook, checkatrade
    source_url TEXT,
    ad_id_on_platform VARCHAR(255),
    
    -- Raw Data
    title TEXT,
    description TEXT,
    raw_html TEXT,
    
    -- Extracted Info
    customer_name VARCHAR(255),
    customer_phone VARCHAR(20),
    customer_email VARCHAR(255),
    customer_postcode VARCHAR(10),
    
    -- Status
    processing_status VARCHAR(30) DEFAULT 'pending', -- pending, processed, invalid, duplicate
    quality_score INTEGER, -- 1-10
    is_duplicate BOOLEAN DEFAULT false,
    duplicate_of_id INTEGER REFERENCES scraped_ads(id),
    
    -- Timestamps
    posted_date TIMESTAMP,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

CREATE INDEX idx_scraped_status ON scraped_ads(processing_status);
CREATE INDEX idx_scraped_platform ON scraped_ads(source_platform);
CREATE INDEX idx_scraped_date ON scraped_ads(scraped_at);

-- ================================================================
-- CUSTOMERS
-- ================================================================
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    
    -- Contact Info
    name VARCHAR(255),
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    postcode VARCHAR(10) NOT NULL,
    full_address TEXT,
    
    -- Source
    source VARCHAR(50), -- scraped_ad, direct_submission, referral
    source_id INTEGER, -- Link to scraped_ads if applicable
    
    -- Reputation
    is_verified BOOLEAN DEFAULT false,
    blacklisted BOOLEAN DEFAULT false,
    blacklist_reason TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customers_phone ON customers(phone);
CREATE INDEX idx_customers_postcode ON customers(postcode);

-- ================================================================
-- JOBS
-- ================================================================
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    
    -- References
    customer_id INTEGER REFERENCES customers(id),
    scraped_ad_id INTEGER REFERENCES scraped_ads(id),
    
    -- Job Details
    job_type VARCHAR(100) REFERENCES pricing_cards(job_type),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    postcode VARCHAR(10) NOT NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Categorization (AI-generated)
    ai_job_type VARCHAR(100),
    ai_urgency VARCHAR(20), -- emergency, today, this_week, flexible
    ai_complexity VARCHAR(20), -- easy, medium, hard
    ai_estimated_hours DECIMAL(4, 2),
    ai_estimated_parts_cost DECIMAL(6, 2),
    ai_confidence DECIMAL(3, 2), -- 0.00 to 1.00
    
    -- Pricing
    estimated_customer_price DECIMAL(8, 2),
    price_range_min DECIMAL(8, 2),
    price_range_max DECIMAL(8, 2),
    finder_fee DECIMAL(6, 2) DEFAULT 25.00,
    
    -- Status
    status VARCHAR(30) DEFAULT 'pending', -- pending, assigned, in_progress, completed, cancelled
    urgency VARCHAR(20),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_at TIMESTAMP,
    completed_at TIMESTAMP,
    cancelled_at TIMESTAMP
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_postcode ON jobs(postcode);
CREATE INDEX idx_jobs_urgency ON jobs(urgency);
CREATE INDEX idx_jobs_created ON jobs(created_at);

-- ================================================================
-- JOB ASSIGNMENTS (Many plumbers can be offered same job)
-- ================================================================
CREATE TABLE job_assignments (
    id SERIAL PRIMARY KEY,
    
    -- References
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    plumber_id INTEGER REFERENCES plumbers(id) ON DELETE CASCADE,
    
    -- Matching Score
    match_score DECIMAL(5, 2), -- 0-100 from matching algorithm
    distance_km DECIMAL(5, 2),
    travel_time_mins INTEGER,
    
    -- Assignment Details
    assignment_type VARCHAR(20) DEFAULT 'exclusive', -- exclusive, shared
    sequence_number INTEGER DEFAULT 1, -- 1st choice, 2nd choice, etc.
    
    -- Quote Details
    quoted_labour_cost DECIMAL(8, 2),
    quoted_travel_cost DECIMAL(8, 2),
    quoted_materials_cost DECIMAL(8, 2),
    quoted_total DECIMAL(8, 2),
    plumber_earnings DECIMAL(8, 2), -- What they'll earn (total - finder_fee)
    
    -- Status
    status VARCHAR(30) DEFAULT 'pending', -- pending, accepted, declined, expired, cancelled
    response_deadline TIMESTAMP,
    
    -- Lead Fee
    lead_fee_charged DECIMAL(6, 2),
    lead_fee_paid BOOLEAN DEFAULT false,
    
    -- Timestamps
    offered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP,
    accepted_at TIMESTAMP,
    declined_at TIMESTAMP,
    
    UNIQUE(job_id, plumber_id)
);

CREATE INDEX idx_assignments_job ON job_assignments(job_id);
CREATE INDEX idx_assignments_plumber ON job_assignments(plumber_id);
CREATE INDEX idx_assignments_status ON job_assignments(status);

-- ================================================================
-- JOB UPDATES (Communication between plumber and customer)
-- ================================================================
CREATE TABLE job_updates (
    id SERIAL PRIMARY KEY,
    
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    assignment_id INTEGER REFERENCES job_assignments(id),
    
    -- Update Details
    update_type VARCHAR(50), -- quote_revised, on_way, arrived, completed, issue_found
    message TEXT,
    
    -- Revised Quote (if applicable)
    revised_quote DECIMAL(8, 2),
    revision_reason TEXT,
    customer_approved BOOLEAN,
    
    -- Photos/Evidence
    photo_urls TEXT[],
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(20) -- plumber, customer, system
);

CREATE INDEX idx_updates_job ON job_updates(job_id);

-- ================================================================
-- INVOICES
-- ================================================================
CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    
    -- References
    job_id INTEGER REFERENCES jobs(id),
    assignment_id INTEGER REFERENCES job_assignments(id),
    customer_id INTEGER REFERENCES customers(id),
    plumber_id INTEGER REFERENCES plumbers(id),
    
    -- Invoice Details
    invoice_number VARCHAR(50) UNIQUE,
    
    -- Line Items
    labour_hours DECIMAL(4, 2),
    labour_rate DECIMAL(6, 2),
    labour_cost DECIMAL(8, 2),
    
    travel_time_hours DECIMAL(4, 2),
    travel_cost DECIMAL(8, 2),
    
    materials_cost DECIMAL(8, 2),
    materials_description TEXT,
    
    -- Totals
    subtotal DECIMAL(8, 2),
    margin DECIMAL(8, 2), -- Contingency buffer
    finder_fee DECIMAL(6, 2),
    total_amount DECIMAL(8, 2),
    
    -- Payment
    payment_status VARCHAR(30) DEFAULT 'pending', -- pending, paid, overdue, disputed
    paid_at TIMESTAMP,
    
    -- Distribution
    plumber_payout DECIMAL(8, 2),
    platform_fee DECIMAL(8, 2),
    payout_status VARCHAR(30) DEFAULT 'pending', -- pending, paid
    payout_paid_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date TIMESTAMP
);

CREATE INDEX idx_invoices_job ON invoices(job_id);
CREATE INDEX idx_invoices_plumber ON invoices(plumber_id);
CREATE INDEX idx_invoices_status ON invoices(payment_status);

-- ================================================================
-- TRANSACTIONS (Credit purchases, fee charges, payouts)
-- ================================================================
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    
    plumber_id INTEGER REFERENCES plumbers(id),
    
    -- Transaction Details
    transaction_type VARCHAR(30), -- credit_purchase, lead_fee, refund, payout
    amount DECIMAL(8, 2),
    balance_before DECIMAL(8, 2),
    balance_after DECIMAL(8, 2),
    
    -- References
    job_id INTEGER REFERENCES jobs(id),
    assignment_id INTEGER REFERENCES job_assignments(id),
    invoice_id INTEGER REFERENCES invoices(id),
    
    -- Payment Gateway
    stripe_payment_intent_id VARCHAR(255),
    stripe_charge_id VARCHAR(255),
    stripe_transfer_id VARCHAR(255),
    
    -- Status
    status VARCHAR(30) DEFAULT 'completed', -- pending, completed, failed, refunded
    
    -- Metadata
    description TEXT,
    metadata JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transactions_plumber ON transactions(plumber_id);
CREATE INDEX idx_transactions_type ON transactions(transaction_type);
CREATE INDEX idx_transactions_date ON transactions(created_at);

-- ================================================================
-- NOTIFICATIONS
-- ================================================================
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    
    -- Recipient
    plumber_id INTEGER REFERENCES plumbers(id),
    customer_id INTEGER REFERENCES customers(id),
    
    -- Notification Details
    notification_type VARCHAR(50), -- new_lead, job_accepted, quote_revised, payment_due, etc.
    channel VARCHAR(20), -- push, sms, email, voice
    
    -- Content
    title VARCHAR(255),
    message TEXT,
    
    -- References
    job_id INTEGER REFERENCES jobs(id),
    assignment_id INTEGER REFERENCES job_assignments(id),
    
    -- Delivery Status
    status VARCHAR(30) DEFAULT 'pending', -- pending, sent, delivered, failed, read
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    
    -- External IDs
    twilio_sid VARCHAR(255),
    firebase_message_id VARCHAR(255),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_plumber ON notifications(plumber_id);
CREATE INDEX idx_notifications_customer ON notifications(customer_id);
CREATE INDEX idx_notifications_status ON notifications(status);
CREATE INDEX idx_notifications_type ON notifications(notification_type);

-- ================================================================
-- VIEWS FOR COMMON QUERIES
-- ================================================================

-- Active jobs with assigned plumbers
CREATE VIEW active_jobs_view AS
SELECT 
    j.id as job_id,
    j.title,
    j.job_type,
    j.status,
    j.urgency,
    j.postcode,
    c.name as customer_name,
    c.phone as customer_phone,
    p.name as plumber_name,
    p.phone as plumber_phone,
    ja.status as assignment_status,
    ja.quoted_total,
    j.created_at
FROM jobs j
LEFT JOIN customers c ON j.customer_id = c.id
LEFT JOIN job_assignments ja ON j.id = ja.job_id AND ja.status = 'accepted'
LEFT JOIN plumbers p ON ja.plumber_id = p.id
WHERE j.status IN ('assigned', 'in_progress');

-- Plumber performance dashboard
CREATE VIEW plumber_performance_view AS
SELECT 
    p.id,
    p.name,
    p.email,
    p.status,
    p.credit_balance,
    p.total_leads_sent,
    p.total_leads_accepted,
    p.total_jobs_completed,
    p.average_rating,
    ROUND(p.contact_rate::NUMERIC, 2) as contact_rate,
    ROUND(p.conversion_rate::NUMERIC, 2) as conversion_rate,
    COUNT(DISTINCT ja.id) FILTER (WHERE ja.status = 'pending' AND ja.response_deadline > NOW()) as pending_leads,
    COUNT(DISTINCT j.id) FILTER (WHERE j.status = 'in_progress') as active_jobs
FROM plumbers p
LEFT JOIN job_assignments ja ON p.id = ja.plumber_id
LEFT JOIN jobs j ON ja.job_id = j.id AND ja.status = 'accepted'
GROUP BY p.id;

-- ================================================================
-- FUNCTIONS
-- ================================================================

-- Update plumber performance metrics
CREATE OR REPLACE FUNCTION update_plumber_metrics(p_plumber_id INTEGER)
RETURNS void AS $$
BEGIN
    UPDATE plumbers SET
        total_leads_sent = (
            SELECT COUNT(*) FROM job_assignments 
            WHERE plumber_id = p_plumber_id
        ),
        total_leads_accepted = (
            SELECT COUNT(*) FROM job_assignments 
            WHERE plumber_id = p_plumber_id AND status = 'accepted'
        ),
        total_jobs_completed = (
            SELECT COUNT(*) FROM jobs j
            JOIN job_assignments ja ON j.id = ja.job_id
            WHERE ja.plumber_id = p_plumber_id AND j.status = 'completed'
        ),
        contact_rate = (
            SELECT COALESCE(
                COUNT(*) FILTER (WHERE ja.status != 'expired')::DECIMAL / 
                NULLIF(COUNT(*)::DECIMAL, 0), 
                0
            )
            FROM job_assignments ja
            WHERE ja.plumber_id = p_plumber_id
        ),
        conversion_rate = (
            SELECT COALESCE(
                COUNT(*) FILTER (WHERE j.status = 'completed')::DECIMAL / 
                NULLIF(COUNT(*)::DECIMAL, 0), 
                0
            )
            FROM job_assignments ja
            JOIN jobs j ON ja.job_id = j.id
            WHERE ja.plumber_id = p_plumber_id AND ja.status = 'accepted'
        ),
        updated_at = NOW()
    WHERE id = p_plumber_id;
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- TRIGGERS
-- ================================================================

-- Auto-update plumber metrics when assignment changes
CREATE OR REPLACE FUNCTION trigger_update_plumber_metrics()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM update_plumber_metrics(NEW.plumber_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER assignment_status_changed
AFTER INSERT OR UPDATE ON job_assignments
FOR EACH ROW
EXECUTE FUNCTION trigger_update_plumber_metrics();

-- Auto-update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER plumbers_updated_at
BEFORE UPDATE ON plumbers
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- ================================================================
-- SAMPLE DATA (for testing)
-- ================================================================

-- Sample plumbers
INSERT INTO plumbers (name, email, phone, base_postcode, hourly_rate, gas_safe_certified, status) VALUES
('John Smith', 'john@example.com', '07700900001', 'SW18', 65.00, true, 'active'),
('Sarah Johnson', 'sarah@example.com', '07700900002', 'SW19', 60.00, false, 'active'),
('Mike Williams', 'mike@example.com', '07700900003', 'CR4', 70.00, true, 'active');

-- Sample postcode coverage
INSERT INTO plumber_postcodes (plumber_id, postcode_prefix, priority) VALUES
(1, 'SW18', 'primary'),
(1, 'SW19', 'primary'),
(1, 'SW17', 'secondary'),
(2, 'SW19', 'primary'),
(2, 'SW20', 'primary'),
(3, 'CR4', 'primary'),
(3, 'SM4', 'secondary');

-- Sample skills
INSERT INTO plumber_skills (plumber_id, skill_type, proficiency) VALUES
(1, 'leaking_tap', 'expert'),
(1, 'boiler_repair', 'expert'),
(1, 'burst_pipe', 'competent'),
(2, 'leaking_tap', 'competent'),
(2, 'toilet_replacement', 'expert'),
(3, 'boiler_repair', 'expert'),
(3, 'shower_installation', 'expert');

-- Give plumbers some initial credits
UPDATE plumbers SET credit_balance = 250.00;

-- ================================================================
-- END OF SCHEMA
-- ================================================================
