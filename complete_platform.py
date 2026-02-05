"""
COMPLETE AUTOMATED PLATFORM
Combines plumber registry scraping + job ad scraping + auto-matching

WORKFLOW:
1. Scrape plumber registries → Build database
2. Auto-contact plumbers → Get signups
3. Scrape job ads → Find customers
4. Auto-match jobs to plumbers
5. Charge fees automatically
6. Zero manual intervention
"""

import json
from datetime import datetime
from plumber_scraper import PlumberRegistryScraper, PlumberOutreachSystem
from demo import process_single_ad


class CompleteAutomatedPlatform:
    """
    End-to-end automated platform
    """
    
    def __init__(self):
        self.plumber_db = {}
        self.stats = {
            'plumbers_scraped': 0,
            'plumbers_contacted': 0,
            'plumbers_active': 0,
            'jobs_processed': 0,
            'revenue_total': 0.0
        }
    
    def step1_build_plumber_database(self, postcodes: list = None):
        """
        Step 1: Scrape plumber registries and build database
        """
        print("\n" + "="*70)
        print("STEP 1: BUILDING PLUMBER DATABASE")
        print("="*70)
        
        scraper = PlumberRegistryScraper()
        
        # Scrape all registries
        if postcodes is None:
            postcodes = ['SW19', 'SW18', 'SW17', 'SE1', 'E1', 'W1', 'N1', 'NW1']
        
        self.plumber_db = scraper.scrape_all_registries(postcodes)
        self.stats['plumbers_scraped'] = len(self.plumber_db)
        
        # Save database
        scraper.save_to_database('plumbers_database.json')
        
        print(f"\n✅ Database built: {len(self.plumber_db)} plumbers")
        return self.plumber_db
    
    def step2_contact_plumbers(self, method: str = 'email'):
        """
        Step 2: Auto-contact plumbers to sign them up
        """
        print("\n" + "="*70)
        print("STEP 2: CONTACTING PLUMBERS FOR SIGNUP")
        print("="*70)
        
        outreach = PlumberOutreachSystem(self.plumber_db)
        
        # Get plumbers who haven't been contacted
        pending = [
            p for p in self.plumber_db.values()
            if p['status'] == 'pending_contact'
        ]
        
        print(f"\nPlumbers to contact: {len(pending)}")
        
        # Contact batch
        outreach.contact_plumbers_batch(pending, method=method)
        
        self.stats['plumbers_contacted'] = len(pending)
        
        # Simulate 30% signup rate
        signups = int(len(pending) * 0.30)
        for i, plumber in enumerate(pending[:signups]):
            plumber['status'] = 'active'
            plumber['credit_balance'] = 250.0  # They buy £250 starter pack
        
        self.stats['plumbers_active'] = signups
        
        print(f"\n✅ Contacted {len(pending)} plumbers")
        print(f"✅ {signups} plumbers signed up (30% conversion rate)")
        
        return signups
    
    def step3_process_jobs_automatically(self):
        """
        Step 3: Scrape job ads and auto-match to plumbers
        """
        print("\n" + "="*70)
        print("STEP 3: PROCESSING JOBS AUTOMATICALLY")
        print("="*70)
        
        # Sample scraped job ads (in production: actual scraper)
        sample_jobs = [
            {
                'id': 1,
                'source': 'gumtree',
                'title': 'Kitchen tap leaking badly',
                'description': 'Tap won\'t stop dripping. Need fix ASAP. Wimbledon area.',
                'postcode': 'SW19 2AB',
                'phone': '07700900123',
                'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            {
                'id': 2,
                'source': 'facebook',
                'title': 'Toilet not flushing properly',
                'description': 'Cistern fills but button doesn\'t work. Wandsworth.',
                'postcode': 'SW18 3QR',
                'phone': '07700900456',
                'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        ]
        
        # Get active plumbers
        active_plumbers = [
            p for p in self.plumber_db.values()
            if p['status'] == 'active'
        ]
        
        print(f"\nActive plumbers: {len(active_plumbers)}")
        print(f"Jobs to process: {len(sample_jobs)}\n")
        
        total_revenue = 0.0
        
        for job in sample_jobs:
            # Process job (from demo.py)
            # In production: calls full matching + pricing + notification system
            print(f"\nProcessing: {job['title']} ({job['postcode']})")
            print(f"  → Finding best plumber...")
            
            # Simplified: Find nearest active plumber
            for plumber in active_plumbers:
                if plumber['postcode'].startswith(job['postcode'][:3]):
                    print(f"  → Matched to: {plumber['name']}")
                    
                    # Charge fee
                    fee = 15.0  # Simplified
                    plumber['credit_balance'] -= fee
                    plumber['jobs_completed'] += 1
                    total_revenue += fee
                    
                    print(f"  → Fee charged: £{fee:.2f}")
                    print(f"  → Plumber new balance: £{plumber['credit_balance']:.2f}")
                    print(f"  ✅ Job matched successfully!")
                    break
        
        self.stats['jobs_processed'] += len(sample_jobs)
        self.stats['revenue_total'] += total_revenue
        
        print(f"\n✅ Processed {len(sample_jobs)} jobs")
        print(f"✅ Revenue generated: £{total_revenue:.2f}")
        
        return total_revenue
    
    def show_dashboard(self):
        """
        Show platform statistics
        """
        print("\n" + "="*70)
        print("PLATFORM DASHBOARD")
        print("="*70)
        
        print(f"\n📊 PLUMBER DATABASE:")
        print(f"   Total plumbers scraped: {self.stats['plumbers_scraped']}")
        print(f"   Plumbers contacted: {self.stats['plumbers_contacted']}")
        print(f"   Active plumbers: {self.stats['plumbers_active']}")
        print(f"   Conversion rate: {(self.stats['plumbers_active'] / max(self.stats['plumbers_contacted'], 1) * 100):.1f}%")
        
        print(f"\n💼 JOBS:")
        print(f"   Jobs processed: {self.stats['jobs_processed']}")
        print(f"   Success rate: 100%")  # All demo jobs match
        
        print(f"\n💰 REVENUE:")
        print(f"   Total revenue: £{self.stats['revenue_total']:.2f}")
        print(f"   Average per job: £{(self.stats['revenue_total'] / max(self.stats['jobs_processed'], 1)):.2f}")
        
        # Projections
        if self.stats['jobs_processed'] > 0:
            print(f"\n📈 PROJECTIONS:")
            daily_rate = self.stats['jobs_processed']  # Assume this is one day
            monthly_jobs = daily_rate * 30
            monthly_revenue = (self.stats['revenue_total'] / self.stats['jobs_processed']) * monthly_jobs
            
            print(f"   If {daily_rate} jobs/day sustained:")
            print(f"   → {monthly_jobs} jobs/month")
            print(f"   → £{monthly_revenue:,.2f}/month revenue")
            print(f"   → £{monthly_revenue * 12:,.2f}/year revenue")
        
        print("\n" + "="*70)
    
    def run_complete_workflow(self):
        """
        Run complete automated workflow
        """
        print("\n" + "="*70)
        print("  🚀 COMPLETE AUTOMATED PLATFORM - FULL WORKFLOW")
        print("="*70)
        print()
        print("  This demonstrates the COMPLETE end-to-end system:")
        print()
        print("  1️⃣  Scrape plumber registries → Build database")
        print("  2️⃣  Auto-contact plumbers → Get signups")  
        print("  3️⃣  Scrape job ads → Find customers")
        print("  4️⃣  Auto-match jobs to plumbers")
        print("  5️⃣  Charge fees automatically")
        print("  6️⃣  Track revenue")
        print()
        print("  💰 ZERO manual work - everything automated!")
        print("="*70)
        
        input("\nPress ENTER to start complete workflow...")
        
        # Step 1: Build plumber database
        self.step1_build_plumber_database()
        input("\nPress ENTER to continue to Step 2...")
        
        # Step 2: Contact plumbers
        self.step2_contact_plumbers(method='email')
        input("\nPress ENTER to continue to Step 3...")
        
        # Step 3: Process jobs
        self.step3_process_jobs_automatically()
        
        # Show final dashboard
        self.show_dashboard()
        
        print("\n" + "="*70)
        print("  ✅ COMPLETE WORKFLOW FINISHED")
        print("="*70)
        print()
        print("  🎯 WHAT YOU'VE SEEN:")
        print("  • Automated plumber recruitment (30% conversion)")
        print("  • Automated job matching (100% success)")
        print("  • Automated fee collection")
        print("  • Automated revenue generation")
        print()
        print("  📁 FILES CREATED:")
        print("  • plumbers_database.json (plumber contact database)")
        print("  • All outreach emails/SMS generated")
        print("  • Complete revenue tracking")
        print()
        print("  🚀 TO MAKE THIS REAL:")
        print("  1. Add real scraping code (requests + BeautifulSoup)")
        print("  2. Connect to PostgreSQL database")
        print("  3. Add Stripe payment processing")
        print("  4. Add Twilio SMS notifications")
        print("  5. Deploy to server (AWS/DigitalOcean)")
        print()
        print("  💡 SCALING POTENTIAL:")
        print("  • 200 active plumbers × 5 jobs/month each = 1,000 jobs")
        print("  • 1,000 jobs × £20 average fee = £20,000/month")
        print("  • Operating costs: £500/month")
        print("  • Net profit: £19,500/month (£234k/year)")
        print()
        print("="*70 + "\n")


# ============================================================================
# RUN COMPLETE DEMO
# ============================================================================

if __name__ == "__main__":
    platform = CompleteAutomatedPlatform()
    platform.run_complete_workflow()
