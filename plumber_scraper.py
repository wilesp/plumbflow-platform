"""
PLUMBER REGISTRY SCRAPER
Automatically builds plumber database from official UK registries

Sources:
- WaterSafe (water regulations compliance)
- CIPHE (Chartered Institute of Plumbing & Heating)
- APHC (Association of Plumbing & Heating Contractors)
- Gas Safe Register (gas work)
"""

import re
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import hashlib


class PlumberRegistryScraper:
    """
    Scrapes official UK plumbing registries to build contact database
    """
    
    # London and South East postcodes to scrape
    LONDON_SE_POSTCODES = [
        # Central London
        'EC1', 'EC2', 'EC3', 'EC4', 'WC1', 'WC2',
        # North London
        'N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7', 'N8', 'N9', 'N10',
        'N11', 'N12', 'N13', 'N14', 'N15', 'N16', 'N17', 'N18', 'N19', 'N20',
        # East London
        'E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E10',
        'E11', 'E12', 'E13', 'E14', 'E15', 'E16', 'E17', 'E18',
        # South London
        'SE1', 'SE2', 'SE3', 'SE4', 'SE5', 'SE6', 'SE7', 'SE8', 'SE9', 'SE10',
        'SE11', 'SE12', 'SE13', 'SE14', 'SE15', 'SE16', 'SE17', 'SE18', 'SE19', 'SE20',
        # South West London
        'SW1', 'SW2', 'SW3', 'SW4', 'SW5', 'SW6', 'SW7', 'SW8', 'SW9', 'SW10',
        'SW11', 'SW12', 'SW13', 'SW14', 'SW15', 'SW16', 'SW17', 'SW18', 'SW19', 'SW20',
        # West London
        'W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8', 'W9', 'W10',
        'W11', 'W12', 'W13', 'W14',
        # North West London
        'NW1', 'NW2', 'NW3', 'NW4', 'NW5', 'NW6', 'NW7', 'NW8', 'NW9', 'NW10',
        # Outer London / South East
        'BR1', 'BR2', 'BR3', 'BR4', 'BR5', 'BR6', 'BR7', 'BR8',  # Bromley
        'CR0', 'CR2', 'CR3', 'CR4', 'CR5', 'CR6', 'CR7', 'CR8', 'CR9',  # Croydon
        'DA1', 'DA5', 'DA6', 'DA7', 'DA8', 'DA14', 'DA15', 'DA16', 'DA17', 'DA18',  # Dartford
        'EN1', 'EN2', 'EN3', 'EN4', 'EN5',  # Enfield
        'HA0', 'HA1', 'HA2', 'HA3', 'HA4', 'HA5', 'HA6', 'HA7', 'HA8', 'HA9',  # Harrow
        'IG1', 'IG2', 'IG3', 'IG4', 'IG5', 'IG6', 'IG7', 'IG8', 'IG11',  # Ilford
        'KT1', 'KT2', 'KT3', 'KT4', 'KT5', 'KT6', 'KT9',  # Kingston
        'RM1', 'RM2', 'RM3', 'RM5', 'RM6', 'RM7', 'RM8', 'RM9', 'RM10',  # Romford
        'SM1', 'SM2', 'SM3', 'SM4', 'SM5', 'SM6', 'SM7',  # Sutton
        'TW1', 'TW2', 'TW3', 'TW4', 'TW5', 'TW7', 'TW8', 'TW9', 'TW10',  # Twickenham
        'UB1', 'UB2', 'UB3', 'UB4', 'UB5', 'UB6', 'UB7', 'UB8', 'UB10',  # Uxbridge
    ]
    
    def __init__(self):
        self.plumbers_db = {}  # In-memory database
        self.duplicate_checker = set()
    
    def generate_plumber_id(self, name: str, postcode: str) -> str:
        """Generate unique ID for plumber"""
        unique_string = f"{name.lower().strip()}{postcode.lower().strip()}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:12]
    
    def extract_contact_info(self, text: str) -> Dict:
        """Extract phone, email, website from text"""
        
        # Phone patterns
        phone_patterns = [
            r'(\+44\s?7\d{3}\s?\d{6})',  # Mobile
            r'(07\d{3}\s?\d{6})',
            r'(\+44\s?[1-9]\d{2,4}\s?\d{6})',  # Landline
            r'(0[1-9]\d{2,4}\s?\d{6})'
        ]
        
        phone = None
        for pattern in phone_patterns:
            match = re.search(pattern, text.replace('-', ' '))
            if match:
                phone = match.group(1).replace(' ', '')
                break
        
        # Email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        email = email_match.group(0) if email_match else None
        
        # Website
        website_match = re.search(r'https?://[\w\.-]+\.\w+', text)
        website = website_match.group(0) if website_match else None
        
        return {
            'phone': phone,
            'email': email,
            'website': website
        }
    
    def scrape_watersafe(self, postcode: str) -> List[Dict]:
        """
        Scrape WaterSafe directory
        URL: https://www.watersafe.org.uk/
        
        In production: Use requests + BeautifulSoup
        For demo: Return sample data
        """
        print(f"  Scraping WaterSafe for {postcode}...")
        
        # DEMO DATA - In production, this would scrape the actual site
        sample_plumbers = [
            {
                'name': 'ABC Plumbing & Heating Ltd',
                'trading_name': 'ABC Plumbing',
                'address': f'123 High Street, {postcode}',
                'postcode': postcode,
                'phone': '02081234567',
                'email': 'info@abcplumbing.co.uk',
                'website': 'https://abcplumbing.co.uk',
                'qualifications': ['WaterSafe Approved', 'WIAPS Member'],
                'services': ['General plumbing', 'Bathroom installation', 'Emergency repairs'],
                'source': 'WaterSafe',
                'registered_date': '2020-01-15',
                'last_verified': '2024-01-10'
            }
        ]
        
        return sample_plumbers
    
    def scrape_ciphe(self, postcode: str) -> List[Dict]:
        """
        Scrape CIPHE directory
        URL: https://www.ciphe.org.uk/find-plumbing-heating-engineers
        """
        print(f"  Scraping CIPHE for {postcode}...")
        
        # DEMO DATA
        sample_plumbers = [
            {
                'name': 'John Smith Plumbing',
                'trading_name': 'JS Plumbing',
                'address': f'45 Market Road, {postcode}',
                'postcode': postcode,
                'phone': '07700900123',
                'email': 'john@jsplumbing.co.uk',
                'website': None,
                'qualifications': ['CIPHE Member', 'City & Guilds Level 3'],
                'services': ['Heating systems', 'Boiler installation', 'Bathroom fitting'],
                'source': 'CIPHE',
                'registered_date': '2018-06-20',
                'last_verified': '2023-12-15'
            }
        ]
        
        return sample_plumbers
    
    def scrape_aphc(self, postcode: str) -> List[Dict]:
        """
        Scrape APHC directory
        URL: https://aphc.co.uk/find-an-aphc-member
        """
        print(f"  Scraping APHC for {postcode}...")
        
        # DEMO DATA
        sample_plumbers = [
            {
                'name': 'Premier Heating Solutions Ltd',
                'trading_name': 'Premier Heating',
                'address': f'78 Station Road, {postcode}',
                'postcode': postcode,
                'phone': '02081235678',
                'email': 'contact@premierheating.com',
                'website': 'https://premierheating.com',
                'qualifications': ['APHC Member', 'Worcester Bosch Accredited'],
                'services': ['Gas boilers', 'Central heating', 'Power flushing'],
                'source': 'APHC',
                'registered_date': '2019-03-10',
                'last_verified': '2024-02-01'
            }
        ]
        
        return sample_plumbers
    
    def scrape_gassafe(self, postcode: str) -> List[Dict]:
        """
        Scrape Gas Safe Register
        URL: https://www.gassaferegister.co.uk/find-an-engineer
        """
        print(f"  Scraping Gas Safe Register for {postcode}...")
        
        # DEMO DATA
        sample_plumbers = [
            {
                'name': 'Safe Gas Services',
                'trading_name': 'Safe Gas',
                'address': f'12 Park Lane, {postcode}',
                'postcode': postcode,
                'phone': '07700900456',
                'email': 'info@safegas.co.uk',
                'website': None,
                'qualifications': ['Gas Safe Registered', 'ACS Qualified'],
                'services': ['Gas boiler repair', 'Gas appliance installation', 'Gas safety checks'],
                'source': 'Gas Safe Register',
                'gas_safe_number': '123456',
                'registered_date': '2017-09-05',
                'last_verified': '2024-01-20'
            }
        ]
        
        return sample_plumbers
    
    def scrape_yell(self, postcode: str) -> List[Dict]:
        """
        Scrape Yell.com (UK Business Directory)
        URL: https://www.yell.com/
        
        Yell.com is excellent because:
        - Comprehensive business listings (like Yellow Pages)
        - Phone numbers always displayed
        - Often has websites and emails
        - Customer reviews and ratings
        - Detailed business descriptions
        
        Search URL format:
        https://www.yell.com/s/plumbers-{postcode}.html
        or
        https://www.yell.com/ucs/UcsSearchAction.do?keywords=plumber&location={postcode}
        """
        print(f"  Scraping Yell.com for {postcode}...")
        
        # In production, would scrape actual site:
        # url = f"https://www.yell.com/s/plumbers-{postcode}.html"
        # html = fetch_page(url)
        # soup = BeautifulSoup(html, 'html.parser')
        # listings = soup.find_all('div', class_='businessCapsule--title')
        # for listing in listings:
        #     extract phone, website, address, reviews, etc.
        
        # DEMO DATA
        sample_plumbers = [
            {
                'name': 'London Emergency Plumbers Ltd',
                'trading_name': 'London Emergency Plumbers',
                'address': f'Unit 5, Business Park, {postcode}',
                'postcode': postcode,
                'phone': '02081239999',
                'email': 'contact@londonemergency.co.uk',
                'website': 'https://londonemergency.co.uk',
                'qualifications': ['Fully Insured', '24/7 Emergency Service'],
                'services': ['Emergency plumbing', 'Burst pipes', 'Leak detection', 'Drain unblocking'],
                'source': 'Yell.com',
                'yell_rating': 4.7,
                'yell_review_count': 89,
                'years_in_business': 12,
                'registered_date': '2012-03-15',
                'last_verified': '2024-02-01'
            },
            {
                'name': 'Quality Plumbing Solutions',
                'trading_name': 'Quality Plumbing',
                'address': f'15 High Street, {postcode}',
                'postcode': postcode,
                'phone': '07900123456',
                'email': 'info@qualityplumbing.com',
                'website': 'https://qualityplumbing.com',
                'qualifications': ['City & Guilds Qualified', 'Public Liability Insurance'],
                'services': ['Bathroom installation', 'Kitchen plumbing', 'General repairs', 'Boiler servicing'],
                'source': 'Yell.com',
                'yell_rating': 4.9,
                'yell_review_count': 142,
                'years_in_business': 8,
                'registered_date': '2016-06-20',
                'last_verified': '2024-01-28'
            }
        ]
        
        return sample_plumbers
    
    def scrape_yell(self, postcode: str) -> List[Dict]:
        """
        Scrape Yell.com business directory
        URL: https://www.yell.com/
        
        Yell.com is UK's leading business directory
        Has extensive plumber listings with:
        - Business name
        - Phone numbers
        - Email addresses
        - Websites
        - Customer reviews
        - Services offered
        
        In production: Search for "plumbers" in each postcode area
        URL format: https://www.yell.com/ucs/UcsSearchAction.do?keywords=plumbers&location={postcode}
        """
        print(f"  Scraping Yell.com for {postcode}...")
        
        # DEMO DATA - In production, this would scrape actual Yell.com
        sample_plumbers = [
            {
                'name': 'London Plumbing Experts',
                'trading_name': 'LPE Plumbing',
                'address': f'Unit 5, Industrial Estate, {postcode}',
                'postcode': postcode,
                'phone': '02081237890',
                'email': 'contact@londonplumbingexperts.co.uk',
                'website': 'https://londonplumbingexperts.co.uk',
                'qualifications': ['Established 15 years', 'Fully insured'],
                'services': [
                    'Emergency plumbing',
                    'Bathroom installation',
                    'Heating repairs',
                    'Drain unblocking',
                    'Leak detection'
                ],
                'source': 'Yell.com',
                'yell_rating': 4.7,
                'yell_reviews': 89,
                'registered_date': '2008-03-20',
                'last_verified': '2024-02-01'
            },
            {
                'name': 'Quick Fix Plumbing Services',
                'trading_name': 'QuickFix',
                'address': f'22 High Street, {postcode}',
                'postcode': postcode,
                'phone': '07700900999',
                'email': 'hello@quickfixplumbing.com',
                'website': 'https://quickfixplumbing.com',
                'qualifications': ['24/7 Emergency Service', 'No call-out charge'],
                'services': [
                    'Emergency callouts',
                    'Boiler repairs',
                    'Tap replacements',
                    'Toilet repairs',
                    'Power flushing'
                ],
                'source': 'Yell.com',
                'yell_rating': 4.5,
                'yell_reviews': 142,
                'registered_date': '2012-06-15',
                'last_verified': '2024-01-28'
            },
            {
                'name': 'Elite Heating & Plumbing Ltd',
                'trading_name': 'Elite H&P',
                'address': f'67 Station Road, {postcode}',
                'postcode': postcode,
                'phone': '02081239876',
                'email': 'info@elitehp.co.uk',
                'website': 'https://elitehp.co.uk',
                'qualifications': ['Worcester Bosch Approved', 'Gas Safe'],
                'services': [
                    'Boiler installation',
                    'Central heating',
                    'Bathroom design',
                    'Underfloor heating',
                    'Solar thermal'
                ],
                'source': 'Yell.com',
                'yell_rating': 4.9,
                'yell_reviews': 203,
                'registered_date': '2005-11-08',
                'last_verified': '2024-02-03',
                'premium_listing': True  # Yell premium advertisers
            }
        ]
        
        return sample_plumbers
    
    def deduplicate_plumber(self, plumber: Dict) -> bool:
        """Check if plumber already in database"""
        plumber_id = self.generate_plumber_id(plumber['name'], plumber['postcode'])
        
        if plumber_id in self.duplicate_checker:
            return True  # Duplicate
        
        self.duplicate_checker.add(plumber_id)
        return False  # New plumber
    
    def normalize_plumber_data(self, plumber: Dict) -> Dict:
        """Standardize plumber data format"""
        
        plumber_id = self.generate_plumber_id(plumber['name'], plumber['postcode'])
        
        # Determine if gas safe certified
        gas_safe = any(
            'gas safe' in qual.lower() 
            for qual in plumber.get('qualifications', [])
        ) or plumber.get('gas_safe_number') is not None
        
        # Extract primary skills
        skills = []
        services = plumber.get('services', [])
        for service in services:
            service_lower = service.lower()
            if 'tap' in service_lower or 'leak' in service_lower:
                skills.append('leaking_tap')
            if 'toilet' in service_lower:
                skills.append('toilet_replacement')
            if 'boiler' in service_lower:
                skills.append('boiler_repair')
            if 'bathroom' in service_lower:
                skills.append('bathroom_fitting')
            if 'burst' in service_lower or 'emergency' in service_lower:
                skills.append('burst_pipe')
        
        # Remove duplicates
        skills = list(set(skills))
        if not skills:
            skills = ['general_plumbing']
        
        return {
            'plumber_id': plumber_id,
            'name': plumber['name'],
            'trading_name': plumber.get('trading_name', plumber['name']),
            'email': plumber.get('email'),
            'phone': plumber.get('phone'),
            'website': plumber.get('website'),
            'address': plumber.get('address'),
            'postcode': plumber['postcode'],
            'gas_safe_certified': gas_safe,
            'gas_safe_number': plumber.get('gas_safe_number'),
            'qualifications': plumber.get('qualifications', []),
            'services': plumber.get('services', []),
            'skills': skills,
            'source_registry': plumber['source'],
            'registered_date': plumber.get('registered_date'),
            'last_verified': plumber.get('last_verified'),
            'added_to_db': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'pending_contact',  # pending_contact, contacted, active, declined
            'contact_attempts': 0,
            'last_contacted': None,
            'credit_balance': 0.0,
            'jobs_completed': 0
        }
    
    def scrape_all_registries(self, postcodes: List[str] = None) -> Dict:
        """
        Scrape all registries for given postcodes
        
        Args:
            postcodes: List of postcodes to scrape. If None, uses all London/SE
        
        Returns:
            Dictionary of plumbers indexed by plumber_id
        """
        if postcodes is None:
            postcodes = self.LONDON_SE_POSTCODES[:10]  # Limit to 10 for demo
        
        print(f"\n{'='*70}")
        print(f"SCRAPING PLUMBER REGISTRIES")
        print(f"{'='*70}")
        print(f"Postcodes to scrape: {len(postcodes)}")
        print(f"Registries: WaterSafe, CIPHE, APHC, Gas Safe, Yell.com")
        print()
        
        all_plumbers = []
        
        for i, postcode in enumerate(postcodes, 1):
            print(f"\n[{i}/{len(postcodes)}] Processing {postcode}...")
            
            # Scrape each registry
            scrapers = [
                self.scrape_watersafe,
                self.scrape_ciphe,
                self.scrape_aphc,
                self.scrape_gassafe,
                self.scrape_yell  # Yell.com - UK business directory
            ]
            
            for scraper in scrapers:
                try:
                    plumbers = scraper(postcode)
                    all_plumbers.extend(plumbers)
                    time.sleep(0.5)  # Rate limiting
                except Exception as e:
                    print(f"  Error in {scraper.__name__}: {e}")
        
        print(f"\n{'='*70}")
        print(f"PROCESSING RESULTS")
        print(f"{'='*70}")
        print(f"Total plumbers scraped: {len(all_plumbers)}")
        
        # Deduplicate and normalize
        unique_count = 0
        duplicate_count = 0
        
        for plumber in all_plumbers:
            if not self.deduplicate_plumber(plumber):
                # New plumber - normalize and add to database
                normalized = self.normalize_plumber_data(plumber)
                self.plumbers_db[normalized['plumber_id']] = normalized
                unique_count += 1
            else:
                duplicate_count += 1
        
        print(f"Unique plumbers: {unique_count}")
        print(f"Duplicates removed: {duplicate_count}")
        print(f"\n{'='*70}\n")
        
        return self.plumbers_db
    
    def save_to_database(self, filename: str = 'plumbers_database.json'):
        """Save scraped plumbers to JSON file"""
        with open(filename, 'w') as f:
            json.dump(self.plumbers_db, f, indent=2)
        print(f"✓ Database saved to {filename}")
        print(f"  Total plumbers: {len(self.plumbers_db)}")
    
    def load_from_database(self, filename: str = 'plumbers_database.json'):
        """Load existing database"""
        try:
            with open(filename, 'r') as f:
                self.plumbers_db = json.load(f)
            print(f"✓ Loaded {len(self.plumbers_db)} plumbers from {filename}")
            
            # Rebuild duplicate checker
            for plumber_id in self.plumbers_db.keys():
                self.duplicate_checker.add(plumber_id)
            
            return self.plumbers_db
        except FileNotFoundError:
            print(f"Database file {filename} not found")
            return {}
    
    def get_plumbers_by_postcode(self, postcode_prefix: str) -> List[Dict]:
        """Get all plumbers in a specific postcode area"""
        return [
            p for p in self.plumbers_db.values()
            if p['postcode'].startswith(postcode_prefix)
        ]
    
    def get_plumbers_by_skill(self, skill: str) -> List[Dict]:
        """Get all plumbers with specific skill"""
        return [
            p for p in self.plumbers_db.values()
            if skill in p['skills']
        ]
    
    def generate_contact_list(self, filters: Dict = None) -> List[Dict]:
        """
        Generate contact list for outreach
        
        Filters can include:
        - status: 'pending_contact', 'contacted', 'active', 'declined'
        - gas_safe: True/False
        - skills: list of required skills
        - postcodes: list of postcode prefixes
        """
        plumbers = list(self.plumbers_db.values())
        
        if filters:
            if 'status' in filters:
                plumbers = [p for p in plumbers if p['status'] == filters['status']]
            
            if 'gas_safe' in filters:
                plumbers = [p for p in plumbers if p['gas_safe_certified'] == filters['gas_safe']]
            
            if 'skills' in filters:
                required_skills = filters['skills']
                plumbers = [
                    p for p in plumbers 
                    if any(skill in p['skills'] for skill in required_skills)
                ]
            
            if 'postcodes' in filters:
                postcode_prefixes = filters['postcodes']
                plumbers = [
                    p for p in plumbers
                    if any(p['postcode'].startswith(prefix) for prefix in postcode_prefixes)
                ]
        
        return plumbers


# ============================================================================
# AUTO-CONTACT SYSTEM
# ============================================================================

class PlumberOutreachSystem:
    """
    Automatically contacts plumbers from database with job opportunities
    """
    
    def __init__(self, plumber_db: Dict):
        self.plumber_db = plumber_db
    
    def generate_introduction_email(self, plumber: Dict) -> str:
        """Generate personalized introduction email"""
        
        email = f"""
Subject: New Lead Opportunities in {plumber['postcode']} - Plumber Matching Platform

Dear {plumber['name']},

I hope this email finds you well.

My name is [Your Name], and I run a lead generation service that connects qualified plumbers with homeowners in London and the South East who need plumbing work done.

I came across your details on {plumber['source_registry']} and noticed you're based in {plumber['postcode']}.

**How it works:**

1. We find homeowners who need plumbing work (from ads on Gumtree, Facebook, local listings)
2. We match them to the nearest qualified plumber (that's you!)
3. You get notified instantly via SMS/Email/App
4. You accept or decline the lead
5. If you accept, we charge £10-25 per lead from prepaid credits
6. You contact the customer and do the job

**What you get:**

✓ Pre-qualified leads in your area ({plumber['postcode']})
✓ Instant notifications (no waiting)
✓ Only pay for leads you accept
✓ Average job value: £100-300
✓ Your earnings: £85-275 per job (after our fee)

**First 3 leads FREE** to prove the quality.

Would you be interested in testing this out? I can set you up today.

Reply YES to get started, or call me on [Your Number] if you have questions.

Best regards,
[Your Name]
Plumber Matching Platform
"""
        return email.strip()
    
    def generate_introduction_sms(self, plumber: Dict) -> str:
        """Generate introduction SMS"""
        
        sms = f"""Hi {plumber['trading_name']}, we send plumbing leads in {plumber['postcode']} direct to plumbers. £10-25 per lead, avg job £150-250. First 3 FREE. Interested? Reply YES or call [Number]"""
        
        return sms.strip()
    
    def contact_plumbers_batch(self, plumbers: List[Dict], method: str = 'email'):
        """
        Contact batch of plumbers
        
        Args:
            plumbers: List of plumber dicts
            method: 'email', 'sms', or 'both'
        """
        print(f"\n{'='*70}")
        print(f"CONTACTING {len(plumbers)} PLUMBERS")
        print(f"{'='*70}\n")
        
        for i, plumber in enumerate(plumbers, 1):
            print(f"[{i}/{len(plumbers)}] {plumber['name']} ({plumber['postcode']})")
            
            if method in ['email', 'both']:
                if plumber['email']:
                    email = self.generate_introduction_email(plumber)
                    print(f"  📧 Email: {plumber['email']}")
                    # In production: send_email(plumber['email'], email)
                else:
                    print(f"  ✗ No email address")
            
            if method in ['sms', 'both']:
                if plumber['phone']:
                    sms = self.generate_introduction_sms(plumber)
                    print(f"  📱 SMS: {plumber['phone']}")
                    # In production: send_sms(plumber['phone'], sms)
                else:
                    print(f"  ✗ No phone number")
            
            print()
            
            # Update contact status
            plumber['contact_attempts'] += 1
            plumber['last_contacted'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            plumber['status'] = 'contacted'


# ============================================================================
# DEMO / USAGE
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  PLUMBER REGISTRY SCRAPER - DEMO")
    print("="*70)
    print()
    print("  This tool scrapes official UK plumbing registries to build")
    print("  a contact database of qualified plumbers in London & South East.")
    print()
    print("  Registries scraped:")
    print("  • WaterSafe (water regulations compliance)")
    print("  • CIPHE (Chartered Institute)")
    print("  • APHC (Association of Plumbing & Heating Contractors)")
    print("  • Gas Safe Register (gas work)")
    print("  • Yell.com (UK's leading business directory)")
    print()
    print("="*70)
    
    input("\nPress ENTER to start scraping...")
    
    # Initialize scraper
    scraper = PlumberRegistryScraper()
    
    # Scrape registries (demo: just 5 postcodes)
    demo_postcodes = ['SW19', 'SW18', 'SW17', 'SE1', 'E1']
    plumber_db = scraper.scrape_all_registries(demo_postcodes)
    
    # Show results
    print("SAMPLE PLUMBERS IN DATABASE:\n")
    for i, (plumber_id, plumber) in enumerate(list(plumber_db.items())[:5], 1):
        print(f"{i}. {plumber['name']}")
        print(f"   Location: {plumber['postcode']}")
        print(f"   Phone: {plumber['phone']}")
        print(f"   Email: {plumber['email']}")
        print(f"   Gas Safe: {'Yes' if plumber['gas_safe_certified'] else 'No'}")
        print(f"   Skills: {', '.join(plumber['skills'])}")
        print(f"   Source: {plumber['source_registry']}")
        print()
    
    # Save database
    scraper.save_to_database('plumbers_database.json')
    
    # Demo: Auto-contact system
    print("\n" + "="*70)
    print("AUTO-CONTACT DEMONSTRATION")
    print("="*70)
    
    outreach = PlumberOutreachSystem(plumber_db)
    
    # Get plumbers who haven't been contacted yet
    pending_plumbers = [
        p for p in plumber_db.values()
        if p['status'] == 'pending_contact'
    ]
    
    print(f"\nFound {len(pending_plumbers)} plumbers to contact")
    print("\nSample introduction email:\n")
    print("-" * 70)
    print(outreach.generate_introduction_email(pending_plumbers[0]))
    print("-" * 70)
    
    # Contact batch
    choice = input("\nContact all pending plumbers? (y/n): ")
    if choice.lower() == 'y':
        outreach.contact_plumbers_batch(pending_plumbers[:3], method='both')
    
    print("\n" + "="*70)
    print("  ✓ DEMO COMPLETE")
    print("="*70)
    print()
    print("  Next steps:")
    print("  1. Add real scraping code (requests + BeautifulSoup)")
    print("  2. Run monthly to update database")
    print("  3. Integrate with notification system")
    print("  4. Track responses and conversions")
    print()
    print("="*70 + "\n")
