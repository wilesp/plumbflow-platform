"""
Database Connection and Operations
PostgreSQL database layer for PlumberFlow
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import os
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class Database:
    """
    PostgreSQL database connection and operations
    Handles all database interactions for PlumberFlow
    """
    
    def __init__(self, database_url: str = None):
        """
        Initialize database connection pool
        
        Args:
            database_url: PostgreSQL connection string
                         Format: postgresql://user:pass@host:5432/dbname
        """
        self.database_url = database_url or os.getenv('DATABASE_URL')
        
        if not self.database_url:
            raise ValueError("DATABASE_URL not provided")
        
        # Create connection pool (min 1, max 10 connections)
        try:
            self.pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=self.database_url
            )
            logger.info("✅ Database connection pool created")
        except Exception as e:
            logger.error(f"❌ Failed to create database pool: {e}")
            raise
    
    def get_connection(self):
        """Get a connection from the pool"""
        return self.pool.getconn()
    
    def return_connection(self, conn):
        """Return connection to pool"""
        self.pool.putconn(conn)
    
    def execute_query(self, query: str, params: tuple = None, fetch=True):
        """
        Execute a database query
        
        Args:
            query: SQL query string
            params: Query parameters (tuple)
            fetch: Whether to fetch results
            
        Returns:
            List of dicts if fetch=True, else None
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(query, params)
            
            if fetch:
                result = cursor.fetchall()
                conn.commit()  # ✅ COMMIT EVEN WHEN FETCHING!
                # Convert to list of dicts
                return [dict(row) for row in result]
            else:
                conn.commit()
                return None
                
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    # ========================================================================
    # PLUMBER OPERATIONS
    # ========================================================================
    
    def create_plumber(self, plumber_data: Dict) -> str:
        """
        Create a new plumber record
        
        Args:
            plumber_data: Dictionary with plumber information
            
        Returns:
            Plumber ID
        """
        plumber_id = plumber_data.get('id') or f"PLUMBER-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        query = """
            INSERT INTO plumbers (
                id, business_name, full_name, email, phone, postcode,
                areas_served, years_experience, gas_safe_number,
                stripe_customer_id, stripe_payment_method_id,
                membership_tier, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
        """
        
        params = (
            plumber_id,
            plumber_data.get('businessName'),
            plumber_data.get('fullName'),
            plumber_data.get('email'),
            plumber_data.get('phone'),
            plumber_data.get('postcode'),
            plumber_data.get('areasServed'),
            plumber_data.get('yearsExperience'),
            plumber_data.get('gasSafeNumber'),
            plumber_data.get('stripeCustomerId'),
            plumber_data.get('stripePaymentMethodId'),
            plumber_data.get('membershipTier', 'free'),
            plumber_data.get('status', 'active')
        )
        
        result = self.execute_query(query, params, fetch=True)
        logger.info(f"✅ Plumber created: {plumber_id}")
        return result[0]['id']
    
    def get_plumber(self, plumber_id: str) -> Optional[Dict]:
        """Get plumber by ID"""
        query = "SELECT * FROM plumbers WHERE id = %s"
        result = self.execute_query(query, (plumber_id,))
        return result[0] if result else None
    
    def get_plumber_by_phone(self, phone: str) -> Optional[Dict]:
        """Get plumber by phone number - handles both +44 and 07 formats"""
        # Normalize phone number to match database format
        # Twilio sends: +447813603470
        # Database has: 07813603470
        
        # Remove spaces and dashes
        phone_clean = phone.replace(' ', '').replace('-', '')
        
        # Convert +44 to 0
        if phone_clean.startswith('+44'):
            phone_normalized = '0' + phone_clean[3:]
        elif phone_clean.startswith('44'):
            phone_normalized = '0' + phone_clean[2:]
        else:
            phone_normalized = phone_clean
        
        query = "SELECT * FROM plumbers WHERE phone = %s AND status = 'active'"
        result = self.execute_query(query, (phone_normalized,))
        return result[0] if result else None
    
    def get_plumber_by_email(self, email: str) -> Optional[Dict]:
        """Get plumber by email"""
        query = "SELECT * FROM plumbers WHERE email = %s"
        result = self.execute_query(query, (email,))
        return result[0] if result else None
    
    def find_plumbers_by_postcode(
        self,
        postcode: str,
        radius_miles: int = 10,
        job_type: str = None,
        limit: int = 5  # REDUCED from unlimited to 5 max (SMS cost control!)
    ) -> List[Dict]:
        """
        Find plumbers near a postcode
        
        CRITICAL: Only returns plumbers with can_receive_jobs=true
        (i.e., fully registered with payment method, not just scraped contacts)
        
        SMS COST OPTIMIZATION:
        - Max 5 plumbers per job (was unlimited before)
        - Only sends to plumbers who can actually accept (have payment method)
        - Saves 90%+ on SMS costs
        
        Regional matching system:
        - Central London: All central London postcodes match each other
        - South East England: All SE counties match each other within region
        - Local matching: For areas outside main regions
        
        Args:
            postcode: Customer postcode
            radius_miles: Search radius (used for fallback range)
            job_type: Job type filter
            limit: Max results (default 5 for SMS cost control)
            
        Returns:
            List of plumber dicts (max 5, all can_receive_jobs=true)
        """
        # Normalize postcode: remove spaces and convert to uppercase
        postcode_normalized = postcode.replace(' ', '').upper()
        
        # Extract postcode area (first 1-2 letters)
        # Examples: W1A -> W, EC1A -> EC, HP1 -> HP
        postcode_area = ''.join([c for c in postcode_normalized if c.isalpha()])[:2]
        
        # Extract outward code (area + district, e.g., W1, EC1, HP2)
        outward_code = ''
        for i, char in enumerate(postcode_normalized):
            if char.isdigit():
                # Include area + district number
                outward_code = postcode_normalized[:i+1]
                break
        
        # Define matching regions
        # Central London - all match each other (tight geographic area)
        central_london = ['EC', 'WC', 'W', 'SW', 'SE', 'E', 'N', 'NW']
        
        # Hertfordshire postcodes
        hertfordshire = ['AL', 'SG', 'WD', 'HP', 'EN']
        
        # Bedfordshire postcodes
        bedfordshire = ['LU', 'MK']
        
        # Essex postcodes
        essex = ['CM', 'CO', 'RM', 'SS', 'IG']
        
        # Kent postcodes
        kent = ['BR', 'CT', 'DA', 'ME', 'TN']
        
        # Hampshire postcodes
        hampshire = ['GU', 'PO', 'SO', 'BH', 'RG']
        
        # Oxfordshire postcodes
        oxfordshire = ['OX']
        
        # Northamptonshire postcodes
        northamptonshire = ['NN']
        
        # Combine all South East England regions
        south_east_england = (
            central_london + 
            hertfordshire + 
            bedfordshire + 
            essex + 
            kent + 
            hampshire + 
            oxfordshire + 
            northamptonshire
        )
        
        # Build flexible matching query
        # CRITICAL: Added "AND can_receive_jobs = true" to ALL queries
        # This filters out scraped plumbers who haven't registered yet
        
        if postcode_area in central_london:
            # Central London: Match only within central London (tight matching)
            patterns = [f"{area}%" for area in central_london]
            placeholders = ','.join(['%s'] * len(patterns))
            
            query = f"""
                SELECT * FROM plumbers
                WHERE status = 'active'
                AND can_receive_jobs = true
                AND (
                    REPLACE(UPPER(postcode), ' ', '') LIKE ANY(ARRAY[{placeholders}])
                )
                ORDER BY 
                    CASE membership_tier
                        WHEN 'enterprise' THEN 4
                        WHEN 'professional' THEN 3
                        WHEN 'starter' THEN 2
                        ELSE 1
                    END DESC,
                    created_at ASC
                LIMIT %s
            """
            
            params = patterns + [limit]
            
        elif postcode_area in south_east_england:
            # South East England: Match across ALL South East regions
            # This allows plumbers from Hertfordshire to serve Kent, etc.
            patterns = [f"{area}%" for area in south_east_england]
            placeholders = ','.join(['%s'] * len(patterns))
            
            query = f"""
                SELECT * FROM plumbers
                WHERE status = 'active'
                AND can_receive_jobs = true
                AND (
                    REPLACE(UPPER(postcode), ' ', '') LIKE ANY(ARRAY[{placeholders}])
                )
                ORDER BY 
                    CASE membership_tier
                        WHEN 'enterprise' THEN 4
                        WHEN 'professional' THEN 3
                        WHEN 'starter' THEN 2
                        ELSE 1
                    END DESC,
                    created_at ASC
                LIMIT %s
            """
            
            params = patterns + [limit]
            
        else:
            # For areas outside South East, match by postcode area only
            # E.g., B (Birmingham) matches B1, B2, B3, etc.
            query = """
                SELECT * FROM plumbers
                WHERE status = 'active'
                AND can_receive_jobs = true
                AND REPLACE(UPPER(postcode), ' ', '') LIKE %s
                ORDER BY 
                    CASE membership_tier
                        WHEN 'enterprise' THEN 4
                        WHEN 'professional' THEN 3
                        WHEN 'starter' THEN 2
                        ELSE 1
                    END DESC,
                    created_at ASC
                LIMIT %s
            """
            
            params = (f"{postcode_area}%", limit)
        
        result = self.execute_query(query, params)
        logger.info(f"Found {len(result)} plumbers near {postcode} (area: {postcode_area}, region: {'Central London' if postcode_area in central_london else 'South East England' if postcode_area in south_east_england else 'Local'}, can_receive_jobs=true only)")
        return result
    
    def update_plumber_stats(self, plumber_id: str, leads_received: int = 0, leads_accepted: int = 0, revenue: float = 0):
        """Update plumber statistics"""
        query = """
            UPDATE plumbers
            SET 
                total_leads_received = total_leads_received + %s,
                total_leads_accepted = total_leads_accepted + %s,
                total_revenue_generated = total_revenue_generated + %s,
                last_active_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        self.execute_query(query, (leads_received, leads_accepted, revenue, plumber_id), fetch=False)
    
    # ========================================================================
    # JOB OPERATIONS
    # ========================================================================
    
    def create_job(self, job_data: Dict) -> str:
        """
        Create a new job record
        
        Args:
            job_data: Dictionary with job information
            
        Returns:
            Job ID
        """
        job_id = job_data.get('id') or f"JOB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Convert complications list to JSON
        complications = json.dumps(job_data.get('complications', []))
        
        query = """
            INSERT INTO jobs (
                id, customer_name, email, phone, postcode, address,
                job_type, title, description, urgency,
                property_type, property_age, job_details,
                price_low, price_typical, price_high, confidence,
                callout_fee, labor_cost, parts_cost_low, parts_cost_high,
                complications, lead_fee, status, expires_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            RETURNING id
        """
        
        params = (
            job_id,
            job_data.get('customerName'),
            job_data.get('email'),
            job_data.get('phone'),
            job_data.get('postcode'),
            job_data.get('address'),
            job_data.get('jobType'),
            job_data.get('title', job_data.get('jobType')),
            job_data.get('description'),
            job_data.get('urgency'),
            job_data.get('propertyType'),
            job_data.get('propertyAge'),
            json.dumps(job_data.get('jobDetails', {})),
            job_data.get('price_low'),
            job_data.get('price_typical'),
            job_data.get('price_high'),
            job_data.get('confidence'),
            job_data.get('callout_fee'),
            job_data.get('labor_cost'),
            job_data.get('parts_cost_low'),
            job_data.get('parts_cost_high'),
            complications,
            job_data.get('lead_fee', 18),
            job_data.get('status', 'pending'),
            datetime.now() + timedelta(hours=2)  # Expires in 2 hours
        )
        
        result = self.execute_query(query, params, fetch=True)
        logger.info(f"✅ Job created: {job_id}")
        return result[0]['id']
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID"""
        query = "SELECT * FROM jobs WHERE id = %s"
        result = self.execute_query(query, (job_id,))
        
        if result:
            job = result[0]
            # Parse JSON fields
            if job.get('complications'):
                job['complications'] = json.loads(job['complications'])
            if job.get('job_details'):
                job['job_details'] = json.loads(job['job_details'])
            return job
        return None
    
    def update_job_status(self, job_id: str, status: str, **kwargs):
        """Update job status and related fields"""
        
        # Build dynamic SET clause
        set_clauses = ['status = %s']
        params = [status]
        
        for key, value in kwargs.items():
            set_clauses.append(f"{key} = %s")
            params.append(value)
        
        params.append(job_id)
        
        query = f"""
            UPDATE jobs
            SET {', '.join(set_clauses)}
            WHERE id = %s
        """
        
        self.execute_query(query, tuple(params), fetch=False)
        logger.info(f"✅ Job {job_id} updated to status: {status}")
    
    # ========================================================================
    # PENDING LEADS OPERATIONS
    # ========================================================================
    
    def add_pending_lead(self, job_id: str, plumber_id: str, magic_link_token: str = None):
        """Add a pending lead (plumber notified about job)"""
        query = """
            INSERT INTO pending_leads (
                job_id, plumber_id, notification_method, magic_link_token, token_expires_at
            ) VALUES (
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (job_id, plumber_id) DO NOTHING
        """
        
        params = (
            job_id,
            plumber_id,
            'sms',
            magic_link_token,
            datetime.now() + timedelta(hours=24) if magic_link_token else None
        )
        
        self.execute_query(query, params, fetch=False)
    
    def get_pending_leads_for_plumber(self, plumber_id: str) -> List[Dict]:
        """Get all pending leads for a plumber"""
        query = """
            SELECT 
                j.*,
                pl.notified_at,
                pl.magic_link_token
            FROM pending_leads pl
            JOIN jobs j ON pl.job_id = j.id
            WHERE pl.plumber_id = %s
            AND j.status = 'pending'
            AND j.expires_at > CURRENT_TIMESTAMP
            ORDER BY pl.notified_at DESC
        """
        
        result = self.execute_query(query, (plumber_id,))
        
        # Parse JSON fields
        for job in result:
            if job.get('complications'):
                job['complications'] = json.loads(job['complications'])
            if job.get('job_details'):
                job['job_details'] = json.loads(job['job_details'])
        
        return result
    
    # ========================================================================
    # ACCEPTED LEADS OPERATIONS
    # ========================================================================
    
    def create_accepted_lead(
        self,
        job_id: str,
        plumber_id: str,
        acceptance_method: str,
        lead_fee: float,
        stripe_charge_id: str = None
    ) -> int:
        """Record a lead acceptance"""
        query = """
            INSERT INTO accepted_leads (
                job_id, plumber_id, acceptance_method, lead_fee,
                stripe_charge_id, stripe_charge_status
            ) VALUES (
                %s, %s, %s, %s, %s, %s
            )
            RETURNING id
        """
        
        params = (
            job_id,
            plumber_id,
            acceptance_method,
            lead_fee,
            stripe_charge_id,
            'succeeded' if stripe_charge_id else 'pending'
        )
        
        result = self.execute_query(query, params, fetch=True)
        logger.info(f"✅ Lead acceptance recorded: Job {job_id} → Plumber {plumber_id}")
        return result[0]['id']
    
    def get_accepted_lead_by_job(self, job_id: str) -> Optional[Dict]:
        """Get accepted lead record by job ID"""
        query = "SELECT * FROM accepted_leads WHERE job_id = %s"
        result = self.execute_query(query, (job_id,))
        return result[0] if result else None
    
    # ========================================================================
    # ANALYTICS / STATS
    # ========================================================================
    
    def get_plumber_stats(self, plumber_id: str) -> Dict:
        """Get plumber statistics"""
        query = """
            SELECT 
                total_leads_received,
                total_leads_accepted,
                total_revenue_generated,
                CASE 
                    WHEN total_leads_received > 0 
                    THEN ROUND((total_leads_accepted::DECIMAL / total_leads_received) * 100, 1)
                    ELSE 0
                END as acceptance_rate
            FROM plumbers
            WHERE id = %s
        """
        result = self.execute_query(query, (plumber_id,))
        return result[0] if result else {}
    
    def get_daily_stats(self) -> Dict:
        """Get today's platform statistics"""
        query = """
            SELECT 
                (SELECT COUNT(*) FROM jobs WHERE DATE(created_at) = CURRENT_DATE) as jobs_today,
                (SELECT COUNT(*) FROM accepted_leads WHERE DATE(accepted_at) = CURRENT_DATE) as leads_accepted_today,
                (SELECT COALESCE(SUM(lead_fee), 0) FROM accepted_leads WHERE DATE(accepted_at) = CURRENT_DATE) as revenue_today,
                (SELECT COUNT(*) FROM plumbers WHERE status = 'active') as active_plumbers
        """
        result = self.execute_query(query)
        return result[0] if result else {}
    
    # ========================================================================
    # UTILITY
    # ========================================================================
    
    def close(self):
        """Close all database connections"""
        if self.pool:
            self.pool.closeall()
            logger.info("✅ Database connections closed")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example usage
    db = Database()
    
    # Create test plumber
    plumber_id = db.create_plumber({
        'businessName': 'Test Plumbing Ltd',
        'fullName': 'John Test',
        'email': 'test@example.com',
        'phone': '+447700900123',
        'postcode': 'SW19 2AB',
        'stripeCustomerId': 'cus_test123'
    })
    
    print(f"Created plumber: {plumber_id}")
    
    # Get plumber
    plumber = db.get_plumber(plumber_id)
    print(f"Plumber: {plumber['business_name']}")
    
    # Close connections
    db.close()
