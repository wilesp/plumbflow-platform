"""
MAIN ORCHESTRATOR
Ties together all components into automated workflow:
Scrape → Process → Price → Match → Notify → Charge
"""

import time
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import schedule

# Import our modules
from ad_scraper import ScraperOrchestrator, ScrapedAd
from pricing_calculator import PricingCalculator, JobAnalysis, PlumberProfile
from matching_engine import PlumberMatcher, Job, Plumber as PlumberMatch, Match
from notification_service import NotificationService, NotificationTemplates
from payment_system import CreditManager, TransactionType


class AIJobAnalyzer:
    """
    Uses AI to analyze scraped ads and extract structured job data
    In production: Use OpenAI GPT-4 API
    """
    
    def analyze_ad(self, ad: ScrapedAd) -> JobAnalysis:
        """
        Analyze scraped ad and extract job details
        
        In production, this would call OpenAI API:
        ```
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        ```
        """
        # Simplified AI simulation
        text = f"{ad.title} {ad.description}".lower()
        
        # Determine job type
        if any(word in text for word in ['tap', 'faucet', 'drip']):
            job_type = 'leaking_tap'
            estimated_hours = 0.5
            estimated_parts = 8.0
        elif any(word in text for word in ['toilet', 'flush', 'cistern']):
            job_type = 'toilet_flush'
            estimated_hours = 0.75
            estimated_parts = 20.0
        elif any(word in text for word in ['burst', 'pipe', 'leak']):
            job_type = 'burst_pipe'
            estimated_hours = 1.5
            estimated_parts = 40.0
        elif any(word in text for word in ['boiler', 'heating', 'gas']):
            job_type = 'boiler_repair'
            estimated_hours = 2.5
            estimated_parts = 150.0
        else:
            job_type = 'general_plumbing'
            estimated_hours = 1.0
            estimated_parts = 30.0
        
        # Determine urgency
        if any(word in text for word in ['emergency', 'urgent', 'asap', 'now']):
            urgency = 'emergency'
        elif any(word in text for word in ['today', 'immediate']):
            urgency = 'today'
        elif any(word in text for word in ['this week', 'soon']):
            urgency = 'this_week'
        else:
            urgency = 'flexible'
        
        # Determine complexity
        if any(word in text for word in ['simple', 'basic', 'just']):
            complexity = 'easy'
        elif any(word in text for word in ['difficult', 'complex', 'major']):
            complexity = 'hard'
        else:
            complexity = 'medium'
        
        return JobAnalysis(
            job_type=job_type,
            urgency=urgency,
            complexity=complexity,
            estimated_hours=estimated_hours,
            estimated_parts_cost=estimated_parts,
            confidence=0.85,  # AI confidence score
            keywords=[job_type, urgency]
        )


class DatabaseService:
    """
    Placeholder for database operations
    In production: Use PostgreSQL with SQLAlchemy
    """
    
    def __init__(self):
        # In production: self.connection = psycopg2.connect(...)
        self.jobs = {}
        self.plumbers = self._load_sample_plumbers()
        self.assignments = []
    
    def _load_sample_plumbers(self) -> Dict:
        """Load sample plumber data"""
        return {
            1: {
                'id': 1,
                'name': 'John Smith',
                'email': 'john@example.com',
                'phone': '+447700900001',
                'base_postcode': 'SW18',
                'hourly_rate': 65.0,
                'emergency_rate': 97.5,
                'minimum_callout': 75.0,
                'travel_rate': 65.0,
                'gas_safe_certified': True,
                'status': 'active',
                'credit_balance': 250.0,
                'skills': ['leaking_tap', 'boiler_repair', 'burst_pipe'],
                'service_postcodes': [
                    {'prefix': 'SW18', 'priority': 'primary', 'min_job_value': 0},
                    {'prefix': 'SW19', 'priority': 'primary', 'min_job_value': 0},
                    {'prefix': 'SW17', 'priority': 'secondary', 'min_job_value': 100}
                ],
                'performance_metrics': {
                    'contact_rate': 0.92,
                    'conversion_rate': 0.58,
                    'average_rating': 4.8,
                    'total_jobs_completed': 89
                },
                'current_jobs_count': 3,
                'available_today': True,
                'device_token': None
            },
            2: {
                'id': 2,
                'name': 'Sarah Johnson',
                'email': 'sarah@example.com',
                'phone': '+447700900002',
                'base_postcode': 'SW19',
                'hourly_rate': 60.0,
                'emergency_rate': 90.0,
                'minimum_callout': 75.0,
                'travel_rate': 60.0,
                'gas_safe_certified': False,
                'status': 'active',
                'credit_balance': 180.0,
                'skills': ['leaking_tap', 'toilet_replacement', 'unblock_sink'],
                'service_postcodes': [
                    {'prefix': 'SW19', 'priority': 'primary', 'min_job_value': 0},
                    {'prefix': 'SW20', 'priority': 'primary', 'min_job_value': 0}
                ],
                'performance_metrics': {
                    'contact_rate': 0.78,
                    'conversion_rate': 0.45,
                    'average_rating': 4.6,
                    'total_jobs_completed': 42
                },
                'current_jobs_count': 5,
                'available_today': True,
                'device_token': None
            }
        }
    
    def save_job(self, job_data: Dict) -> int:
        """Save job to database"""
        job_id = len(self.jobs) + 1
        job_data['id'] = job_id
        self.jobs[job_id] = job_data
        return job_id
    
    def save_assignment(self, assignment_data: Dict):
        """Save job assignment"""
        self.assignments.append(assignment_data)
    
    def get_active_plumbers(self) -> List[Dict]:
        """Get all active plumbers"""
        return [p for p in self.plumbers.values() if p['status'] == 'active']
    
    def update_plumber_balance(self, plumber_id: int, new_balance: float):
        """Update plumber credit balance"""
        if plumber_id in self.plumbers:
            self.plumbers[plumber_id]['credit_balance'] = new_balance


class PlatformOrchestrator:
    """
    Main orchestrator that runs the complete platform workflow
    """
    
    def __init__(self):
        # Initialize all services
        self.db = DatabaseService()
        self.scraper = ScraperOrchestrator()
        self.ai_analyzer = AIJobAnalyzer()
        self.pricing_calc = PricingCalculator()
        self.matcher = PlumberMatcher()
        self.notifications = NotificationService(db_connection=self.db)
        self.payments = CreditManager(db_connection=self.db)
        
        print("Platform Orchestrator initialized")
        print("All services ready")
    
    def process_scraped_ad(self, ad: ScrapedAd) -> Optional[int]:
        """
        Complete workflow for single scraped ad
        
        Steps:
        1. Validate ad quality
        2. AI analysis → extract job details
        3. Find matching plumbers
        4. Calculate pricing for each match
        5. Send notifications to top plumbers
        6. Wait for acceptance
        7. Charge lead fee
        8. Notify customer
        
        Returns: job_id if successful, None if failed
        """
        print(f"\n{'='*60}")
        print(f"Processing ad: {ad.title}")
        print(f"{'='*60}")
        
        # Step 1: AI Analysis
        print("\n1. Analyzing job with AI...")
        job_analysis = self.ai_analyzer.analyze_ad(ad)
        print(f"   Job type: {job_analysis.job_type}")
        print(f"   Urgency: {job_analysis.urgency}")
        print(f"   Complexity: {job_analysis.complexity}")
        print(f"   Confidence: {job_analysis.confidence:.0%}")
        
        if job_analysis.confidence < 0.6:
            print("   ✗ Low confidence, skipping")
            return None
        
        # Step 2: Save job to database
        print("\n2. Creating job record...")
        job_data = {
            'title': ad.title,
            'description': ad.description,
            'job_type': job_analysis.job_type,
            'postcode': ad.customer_postcode,
            'urgency': job_analysis.urgency,
            'complexity': job_analysis.complexity,
            'customer_phone': ad.customer_phone,
            'customer_email': ad.customer_email,
            'source': ad.source_platform,
            'status': 'pending',
            'created_at': datetime.now()
        }
        job_id = self.db.save_job(job_data)
        print(f"   ✓ Job #{job_id} created")
        
        # Step 3: Find matching plumbers
        print("\n3. Finding matching plumbers...")
        
        # Convert to Job object
        job = Job(
            id=job_id,
            title=ad.title,
            description=ad.description,
            job_type=job_analysis.job_type,
            postcode=ad.customer_postcode,
            urgency=job_analysis.urgency,
            complexity=job_analysis.complexity,
            estimated_value=150.0,  # Placeholder
            ai_confidence=job_analysis.confidence,
            gas_safe_required='boiler' in job_analysis.job_type.lower()
        )
        
        # Get active plumbers and convert to match format
        active_plumbers_data = self.db.get_active_plumbers()
        plumbers = []
        
        for p_data in active_plumbers_data:
            plumber = PlumberMatch(
                id=p_data['id'],
                name=p_data['name'],
                base_postcode=p_data['base_postcode'],
                hourly_rate=p_data['hourly_rate'],
                status=p_data['status'],
                credit_balance=p_data['credit_balance'],
                gas_safe_certified=p_data['gas_safe_certified'],
                skills=p_data['skills'],
                service_postcodes=p_data['service_postcodes'],
                performance_metrics=p_data['performance_metrics'],
                current_jobs_count=p_data['current_jobs_count'],
                available_today=p_data['available_today']
            )
            plumbers.append(plumber)
        
        matches = self.matcher.find_matches(job, plumbers, top_n=3)
        
        if not matches:
            print("   ✗ No suitable plumbers found")
            return None
        
        print(f"   ✓ Found {len(matches)} matches")
        for match in matches:
            plumber = next(p for p in plumbers if p.id == match.plumber_id)
            print(f"     #{match.ranking}: {plumber.name} (score: {match.match_score:.1f})")
        
        # Step 4: Calculate pricing for each match
        print("\n4. Calculating pricing...")
        
        for match in matches:
            plumber_data = self.db.plumbers[match.plumber_id]
            
            # Convert to PlumberProfile for pricing
            plumber_profile = PlumberProfile(
                id=plumber_data['id'],
                name=plumber_data['name'],
                base_postcode=plumber_data['base_postcode'],
                hourly_rate=plumber_data['hourly_rate'],
                emergency_rate=plumber_data['emergency_rate'],
                minimum_callout=plumber_data['minimum_callout'],
                travel_rate=plumber_data['travel_rate'],
                gas_safe_certified=plumber_data['gas_safe_certified'],
                specialties=plumber_data['skills']
            )
            
            # Calculate price
            pricing = self.pricing_calc.calculate_job_price(
                job_analysis=job_analysis,
                plumber=plumber_profile,
                job_postcode=ad.customer_postcode,
                distance_km=match.distance_km,
                travel_time_mins=match.travel_time_mins
            )
            
            # Save pricing to assignment
            assignment_data = {
                'job_id': job_id,
                'plumber_id': match.plumber_id,
                'match_score': match.match_score,
                'ranking': match.ranking,
                'quoted_total': pricing['pricing']['customer_pays'],
                'plumber_earnings': pricing['pricing']['plumber_earns'],
                'finder_fee': pricing['pricing']['platform_fee'],
                'status': 'pending',
                'offered_at': datetime.now(),
                'pricing_breakdown': pricing
            }
            self.db.save_assignment(assignment_data)
            
            print(f"   Plumber: {plumber_profile.name}")
            print(f"     Customer pays: £{pricing['pricing']['customer_pays']:.2f}")
            print(f"     Plumber earns: £{pricing['pricing']['plumber_earns']:.2f}")
            print(f"     Platform fee: £{pricing['pricing']['platform_fee']:.2f}")
        
        # Step 5: Send notifications (exclusive model - one at a time)
        print("\n5. Sending notifications to plumbers...")
        
        # Send to #1 ranked plumber first
        top_match = matches[0]
        top_plumber_data = self.db.plumbers[top_match.plumber_id]
        top_assignment = [a for a in self.db.assignments if a['job_id'] == job_id and a['ranking'] == 1][0]
        
        notification = NotificationTemplates.new_lead_for_plumber(
            job_title=ad.title,
            postcode=ad.customer_postcode,
            urgency=job_analysis.urgency,
            earnings=float(top_assignment['plumber_earnings']),
            work_hours=job_analysis.estimated_hours,
            lead_fee=float(top_assignment['finder_fee']),
            job_id=job_id
        )
        
        self.notifications.send_to_plumber(
            plumber_id=top_match.plumber_id,
            plumber_phone=top_plumber_data['phone'],
            plumber_email=top_plumber_data['email'],
            notification=notification,
            device_token=top_plumber_data.get('device_token')
        )
        
        print(f"   ✓ Notification sent to {top_plumber_data['name']}")
        print(f"     Waiting for acceptance...")
        
        # In production: Wait for plumber response via webhook/API
        # For demo: Simulate acceptance
        print("\n6. [SIMULATED] Plumber accepts lead...")
        
        # Step 6: Charge lead fee
        print("\n7. Charging lead fee...")
        
        fee_result = self.payments.charge_lead_fee(
            plumber_id=top_match.plumber_id,
            job_id=job_id,
            fee_amount=Decimal(str(top_assignment['finder_fee'])),
            job_title=ad.title
        )
        
        if fee_result['success']:
            print(f"   ✓ Fee charged: £{fee_result['fee_charged']}")
            print(f"   New balance: £{fee_result['new_balance']}")
            
            # Update database
            self.db.update_plumber_balance(
                top_match.plumber_id,
                float(fee_result['new_balance'])
            )
        else:
            print(f"   ✗ Failed to charge fee: {fee_result['error']}")
            return None
        
        # Step 7: Notify customer
        print("\n8. Notifying customer...")
        
        customer_notification = NotificationTemplates.job_accepted_customer(
            plumber_name=top_plumber_data['name'],
            plumber_phone=top_plumber_data['phone'],
            rating=top_plumber_data['performance_metrics']['average_rating'],
            estimated_price=top_assignment['quoted_total'],
            job_id=job_id
        )
        
        self.notifications.send_to_customer(
            customer_id=0,  # Placeholder
            customer_phone=ad.customer_phone,
            customer_email=ad.customer_email,
            notification=customer_notification
        )
        
        print(f"   ✓ Customer notified")
        
        print(f"\n{'='*60}")
        print(f"✓ COMPLETE: Job #{job_id} processed successfully")
        print(f"{'='*60}\n")
        
        return job_id
    
    def run_scraping_and_processing_cycle(self):
        """
        Run complete cycle:
        1. Scrape ads from all platforms
        2. Process each ad through workflow
        """
        print("\n" + "="*60)
        print(f"SCRAPING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Run scrapers
        scraped_ads = self.scraper.run_scraping_cycle()
        
        if not scraped_ads:
            print("\nNo new ads found this cycle")
            return
        
        # Process each ad
        print(f"\nProcessing {len(scraped_ads)} ads...")
        
        successful = 0
        failed = 0
        
        for ad in scraped_ads:
            try:
                job_id = self.process_scraped_ad(ad)
                if job_id:
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"Error processing ad: {e}")
                failed += 1
        
        print("\n" + "="*60)
        print(f"CYCLE COMPLETE")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print("="*60 + "\n")
    
    def start_continuous_operation(self, interval_minutes: int = 15):
        """
        Start platform in continuous operation mode
        
        Args:
            interval_minutes: How often to run scraping cycle (default 15)
        """
        print("\n" + "="*60)
        print("PLUMBER PLATFORM - STARTING")
        print("="*60)
        print(f"Scraping interval: Every {interval_minutes} minutes")
        print("Press Ctrl+C to stop")
        print("="*60 + "\n")
        
        # Schedule scraping cycle
        schedule.every(interval_minutes).minutes.do(self.run_scraping_and_processing_cycle)
        
        # Run immediately on start
        self.run_scraping_and_processing_cycle()
        
        # Then run on schedule
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n\nShutting down platform...")
            print("Goodbye!")


# ================================================================
# MAIN ENTRY POINT
# ================================================================

if __name__ == "__main__":
    # Initialize platform
    platform = PlatformOrchestrator()
    
    # Option 1: Run single cycle (for testing)
    print("\nRunning single test cycle...")
    platform.run_scraping_and_processing_cycle()
    
    # Option 2: Start continuous operation (uncomment to use)
    # platform.start_continuous_operation(interval_minutes=15)
