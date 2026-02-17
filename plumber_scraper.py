"""
================================================================================
PLUMBFLOW - PLUMBER REGISTRY SCRAPER (PRODUCTION)
================================================================================

Scrapes 5 official UK plumbing registries to build contact database:
  1. Yell.com          - 10,000+ listings, public phones/postcodes
  2. WaterSafe         - Official water regs registry
  3. CIPHE             - Chartered Institute of Plumbing & Heating
  4. APHC              - Association of Plumbing & Heating Contractors
  5. Gas Safe Register - Mandatory gas work registry

Target: 18,000+ plumber contacts across London & South East England

Usage:
  python3 plumber_scraper.py                   # Run all sources, all postcodes
  python3 plumber_scraper.py --source yell     # Single source only
  python3 plumber_scraper.py --postcode SW19   # Single postcode test
  python3 plumber_scraper.py --limit 10        # Limit pages per area (testing)
================================================================================
"""

import os
import re
import sys
import time
import json
import random
import hashlib
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlencode, quote_plus

try:
    import requests
    from bs4 import BeautifulSoup
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("Installing required packages...")
    os.system("pip install requests beautifulsoup4 psycopg2-binary lxml --break-system-packages -q")
    import requests
    from bs4 import BeautifulSoup
    import psycopg2
    from psycopg2.extras import execute_values

# ============================================================================
# CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scraper.log')
    ]
)
log = logging.getLogger(__name__)

# Realistic browser headers to avoid blocking
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-GB,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Rate limiting - polite scraping
DELAY_MIN = 2.0   # seconds between requests
DELAY_MAX = 4.0   # seconds between requests

# ============================================================================
# TARGET POSTCODES - London & South East England
# ============================================================================

POSTCODE_AREAS = {
    'Central London': ['EC1', 'EC2', 'EC3', 'EC4', 'WC1', 'WC2'],
    'North London': ['N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7', 'N8', 'N9', 'N10',
                     'N11', 'N12', 'N13', 'N14', 'N15', 'N16', 'N17', 'N18', 'N19', 'N20'],
    'East London': ['E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E10',
                    'E11', 'E12', 'E13', 'E14', 'E15', 'E16', 'E17', 'E18'],
    'South East London': ['SE1', 'SE2', 'SE3', 'SE4', 'SE5', 'SE6', 'SE7', 'SE8', 'SE9', 'SE10',
                          'SE11', 'SE12', 'SE13', 'SE14', 'SE15', 'SE16', 'SE17', 'SE18', 'SE19', 'SE20'],
    'South West London': ['SW1', 'SW2', 'SW3', 'SW4', 'SW5', 'SW6', 'SW7', 'SW8', 'SW9', 'SW10',
                          'SW11', 'SW12', 'SW13', 'SW14', 'SW15', 'SW16', 'SW17', 'SW18', 'SW19', 'SW20'],
    'West London': ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8', 'W9', 'W10', 'W11', 'W12', 'W13', 'W14'],
    'North West London': ['NW1', 'NW2', 'NW3', 'NW4', 'NW5', 'NW6', 'NW7', 'NW8', 'NW9', 'NW10'],
    'Outer London - Bromley': ['BR1', 'BR2', 'BR3', 'BR4', 'BR5', 'BR6', 'BR7', 'BR8'],
    'Outer London - Croydon': ['CR0', 'CR2', 'CR3', 'CR4', 'CR5', 'CR6', 'CR7', 'CR8'],
    'Outer London - Dartford': ['DA1', 'DA5', 'DA6', 'DA7', 'DA8', 'DA14', 'DA15', 'DA16', 'DA17'],
    'Outer London - Enfield': ['EN1', 'EN2', 'EN3', 'EN4', 'EN5'],
    'Outer London - Harrow': ['HA0', 'HA1', 'HA2', 'HA3', 'HA4', 'HA5', 'HA6', 'HA7', 'HA8', 'HA9'],
    'Outer London - Ilford': ['IG1', 'IG2', 'IG3', 'IG4', 'IG5', 'IG6', 'IG7', 'IG8', 'IG11'],
    'Outer London - Kingston': ['KT1', 'KT2', 'KT3', 'KT4', 'KT5', 'KT6', 'KT9'],
    'Outer London - Romford': ['RM1', 'RM2', 'RM3', 'RM5', 'RM6', 'RM7', 'RM8', 'RM9', 'RM10'],
    'Outer London - Sutton': ['SM1', 'SM2', 'SM3', 'SM4', 'SM5', 'SM6', 'SM7'],
    'Outer London - Twickenham': ['TW1', 'TW2', 'TW3', 'TW4', 'TW5', 'TW7', 'TW8', 'TW9', 'TW10'],
    'Outer London - Uxbridge': ['UB1', 'UB2', 'UB3', 'UB4', 'UB5', 'UB6', 'UB7', 'UB8', 'UB10'],
    'Surrey': ['GU1', 'GU2', 'GU3', 'GU4', 'GU5', 'GU6', 'GU7', 'GU9', 'GU10',
               'KT10', 'KT11', 'KT12', 'KT13', 'KT15', 'KT16', 'KT17', 'KT18', 'KT19', 'KT20', 'KT22', 'KT23', 'KT24',
               'RH1', 'RH2', 'RH3', 'RH4', 'RH5', 'RH6'],
    'Kent': ['ME1', 'ME2', 'ME3', 'ME4', 'ME5', 'ME6', 'ME7', 'ME8', 'ME9', 'ME10',
             'TN1', 'TN2', 'TN4', 'TN8', 'TN9', 'TN10', 'TN11', 'TN12', 'TN13', 'TN14', 'TN15', 'TN16'],
    'Essex': ['CM1', 'CM2', 'CM3', 'CM4', 'CM5', 'CM6', 'CM7', 'CM8',
              'SS0', 'SS1', 'SS2', 'SS3', 'SS4', 'SS5', 'SS6', 'SS7', 'SS8', 'SS9'],
    'Hertfordshire': ['AL1', 'AL2', 'AL3', 'AL4', 'AL5', 'AL6', 'AL7', 'AL8', 'AL9', 'AL10',
                      'SG1', 'SG2', 'SG3', 'SG4', 'SG5', 'SG6', 'SG7', 'SG8', 'SG9', 'SG11', 'SG12', 'SG13', 'SG14',
                      'WD1', 'WD2', 'WD3', 'WD4', 'WD5', 'WD6', 'WD7', 'WD17', 'WD18', 'WD19', 'WD23', 'WD24', 'WD25'],
}

# Flatten to single list
ALL_POSTCODES = [pc for region in POSTCODE_AREAS.values() for pc in region]


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def clean_phone(phone: str) -> Optional[str]:
    """Normalise UK phone number"""
    if not phone:
        return None
    # Remove everything except digits and +
    cleaned = re.sub(r'[^\d+]', '', phone)
    # Convert +44 to 0
    if cleaned.startswith('+44'):
        cleaned = '0' + cleaned[3:]
    # Validate length
    if len(cleaned) in [10, 11] and cleaned.startswith('0'):
        return cleaned
    return None


def clean_postcode(postcode: str) -> Optional[str]:
    """Normalise UK postcode"""
    if not postcode:
        return None
    cleaned = re.sub(r'[^A-Z0-9]', '', postcode.upper().strip())
    # UK postcodes are 5-7 chars
    if 5 <= len(cleaned) <= 7:
        return cleaned
    return None


def extract_postcode_area(postcode: str) -> str:
    """Extract area code from full postcode e.g. SW19 2AB -> SW19"""
    if not postcode:
        return ''
    match = re.match(r'^([A-Z]{1,2}[0-9]{1,2}[A-Z]?)', postcode.upper().strip())
    return match.group(1) if match else postcode


def generate_id(name: str, postcode: str) -> str:
    """Generate stable unique ID"""
    key = f"{name.lower().strip()}{postcode.lower().strip()}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def polite_delay():
    """Wait between requests to avoid overloading servers"""
    delay = random.uniform(DELAY_MIN, DELAY_MAX)
    time.sleep(delay)


def safe_get(session: requests.Session, url: str, params: dict = None, retries: int = 3) -> Optional[requests.Response]:
    """HTTP GET with retry logic"""
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, timeout=15, headers=HEADERS)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:
                # Rate limited - wait longer
                wait = 30 * (attempt + 1)
                log.warning(f"Rate limited on {url}. Waiting {wait}s...")
                time.sleep(wait)
            elif resp.status_code in [403, 404]:
                log.warning(f"HTTP {resp.status_code} on {url}")
                return None
            else:
                log.warning(f"HTTP {resp.status_code} on {url}, attempt {attempt+1}")
                time.sleep(5)
        except requests.exceptions.ConnectionError:
            log.warning(f"Connection error on {url}, attempt {attempt+1}")
            time.sleep(10)
        except requests.exceptions.Timeout:
            log.warning(f"Timeout on {url}, attempt {attempt+1}")
            time.sleep(5)
    return None


# ============================================================================
# SOURCE 1: YELL.COM SCRAPER
# ============================================================================

class YellScraper:
    """
    Scrapes Yell.com business directory for plumbers.
    
    URL pattern: https://www.yell.com/ucs/UcsSearchAction.do?keywords=plumbers&location={postcode}
    
    Data available: Business name, phone, address, postcode (clearly listed)
    Volume: 100,000+ UK listings
    Difficulty: Easy - public data, no login required
    """
    
    BASE_URL = "https://www.yell.com"
    SEARCH_URL = "https://www.yell.com/ucs/UcsSearchAction.do"
    
    def __init__(self, session: requests.Session):
        self.session = session
        self.source_name = 'yell'
    
    def scrape_postcode(self, postcode: str, max_pages: int = 10) -> List[Dict]:
        """Scrape all plumbers in a postcode area from Yell"""
        results = []
        
        for page in range(1, max_pages + 1):
            params = {
                'keywords': 'plumbers',
                'location': postcode,
                'pageNum': page,
            }
            
            log.info(f"  [Yell] {postcode} page {page}")
            resp = safe_get(self.session, self.SEARCH_URL, params=params)
            
            if not resp:
                break
            
            soup = BeautifulSoup(resp.text, 'lxml')
            
            # Find all business listings
            listings = soup.select('article.businessCapsule')
            if not listings:
                # Try alternative selector
                listings = soup.select('div[data-ys-businessid]')
            
            if not listings:
                log.info(f"  [Yell] No listings on page {page} for {postcode}")
                break
            
            for listing in listings:
                plumber = self._parse_listing(listing, postcode)
                if plumber:
                    results.append(plumber)
            
            # Check if there's a next page
            next_btn = soup.select_one('a.pagination__item--next')
            if not next_btn:
                break
            
            polite_delay()
        
        log.info(f"  [Yell] Found {len(results)} plumbers in {postcode}")
        return results
    
    def _parse_listing(self, listing, search_postcode: str) -> Optional[Dict]:
        """Parse a single Yell business listing"""
        try:
            # Business name
            name_el = listing.select_one('a.businessCapsule__name') or listing.select_one('h2.businessCapsule__name')
            if not name_el:
                return None
            name = name_el.get_text(strip=True)
            
            # Phone number
            phone_el = listing.select_one('span.phone-number') or listing.select_one('a[href^="tel:"]')
            phone = None
            if phone_el:
                raw_phone = phone_el.get('href', '').replace('tel:', '') or phone_el.get_text(strip=True)
                phone = clean_phone(raw_phone)
            
            # Address / postcode
            address_el = listing.select_one('span.businessCapsule__address') or listing.select_one('address')
            address = address_el.get_text(strip=True) if address_el else ''
            
            # Extract postcode from address
            postcode_match = re.search(r'[A-Z]{1,2}[0-9]{1,2}[A-Z]?\s?[0-9][A-Z]{2}', address.upper())
            postcode = clean_postcode(postcode_match.group(0)) if postcode_match else search_postcode
            
            # Website
            website_el = listing.select_one('a[href*="http"]')
            website = None
            if website_el:
                href = website_el.get('href', '')
                if 'yell.com' not in href and href.startswith('http'):
                    website = href
            
            # Rating
            rating_el = listing.select_one('span.star-rating__score')
            rating = float(rating_el.get_text(strip=True)) if rating_el else None
            
            # Review count
            reviews_el = listing.select_one('span.reviewCount')
            reviews = int(re.sub(r'\D', '', reviews_el.get_text())) if reviews_el else 0
            
            if not name:
                return None
            
            return {
                'id': generate_id(name, postcode or search_postcode),
                'name': name,
                'trading_name': name,
                'phone': phone,
                'email': None,  # Yell doesn't show emails
                'website': website,
                'address': address,
                'postcode': postcode or search_postcode,
                'postcode_area': extract_postcode_area(postcode or search_postcode),
                'rating': rating,
                'review_count': reviews,
                'source': self.source_name,
                'qualifications': [],
                'gas_safe': False,  # Unknown from Yell
                'scraped_at': datetime.now().isoformat(),
                'can_receive_jobs': False,
                'status': 'scraped',
            }
        except Exception as e:
            log.debug(f"Error parsing Yell listing: {e}")
            return None


# ============================================================================
# SOURCE 2: WATERSAFE SCRAPER
# ============================================================================

class WaterSafeScraper:
    """
    Scrapes WaterSafe approved contractor directory.
    
    URL: https://www.watersafe.org.uk/find-an-approved-contractor/
    API: Has a search endpoint that returns JSON
    
    Data: Business name, address, phone, qualifications
    Volume: ~8,000 UK contractors
    """
    
    BASE_URL = "https://www.watersafe.org.uk"
    # WaterSafe uses a POST form or API to search
    SEARCH_URL = "https://www.watersafe.org.uk/find-an-approved-contractor/"
    
    def __init__(self, session: requests.Session):
        self.session = session
        self.source_name = 'watersafe'
    
    def scrape_postcode(self, postcode: str) -> List[Dict]:
        """Search WaterSafe for contractors in postcode"""
        results = []
        
        log.info(f"  [WaterSafe] Searching {postcode}")
        
        # WaterSafe search form
        data = {
            'postcode': postcode,
            'radius': '10',  # 10 mile radius
            'search': 'Search',
        }
        
        try:
            resp = self.session.post(
                self.SEARCH_URL,
                data=data,
                timeout=15,
                headers={**HEADERS, 'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if not resp or resp.status_code != 200:
                return results
            
            soup = BeautifulSoup(resp.text, 'lxml')
            
            # Find contractor listings
            contractors = soup.select('div.contractor-result') or soup.select('article.member') or soup.select('li.result')
            
            for contractor in contractors:
                plumber = self._parse_contractor(contractor)
                if plumber:
                    results.append(plumber)
        
        except Exception as e:
            log.debug(f"WaterSafe error for {postcode}: {e}")
        
        polite_delay()
        log.info(f"  [WaterSafe] Found {len(results)} contractors in {postcode}")
        return results
    
    def _parse_contractor(self, el) -> Optional[Dict]:
        """Parse a WaterSafe contractor entry"""
        try:
            name_el = el.select_one('h2, h3, .company-name, .contractor-name')
            if not name_el:
                return None
            name = name_el.get_text(strip=True)
            
            # Get all text for regex extraction
            full_text = el.get_text(' ', strip=True)
            
            # Extract phone
            phone_match = re.search(r'(0[1-9]\d{8,9}|07\d{9})', full_text.replace(' ', ''))
            phone = clean_phone(phone_match.group(1)) if phone_match else None
            
            # Extract postcode
            pc_match = re.search(r'[A-Z]{1,2}[0-9]{1,2}[A-Z]?\s?[0-9][A-Z]{2}', full_text.upper())
            postcode = clean_postcode(pc_match.group(0)) if pc_match else None
            
            # Extract email
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', full_text)
            email = email_match.group(0).lower() if email_match else None
            
            # Qualifications
            quals = []
            if 'watersafe' in full_text.lower():
                quals.append('WaterSafe Approved')
            if 'wiaps' in full_text.lower():
                quals.append('WIAPS Member')
            
            return {
                'id': generate_id(name, postcode or ''),
                'name': name,
                'trading_name': name,
                'phone': phone,
                'email': email,
                'website': None,
                'address': full_text[:200],
                'postcode': postcode or '',
                'postcode_area': extract_postcode_area(postcode or ''),
                'rating': None,
                'review_count': 0,
                'source': self.source_name,
                'qualifications': quals,
                'gas_safe': False,
                'scraped_at': datetime.now().isoformat(),
                'can_receive_jobs': False,
                'status': 'scraped',
            }
        except Exception as e:
            log.debug(f"WaterSafe parse error: {e}")
            return None


# ============================================================================
# SOURCE 3: CIPHE SCRAPER
# ============================================================================

class CIPHEScraper:
    """
    Scrapes CIPHE (Chartered Institute of Plumbing & Heating Engineering).
    
    URL: https://www.ciphe.org.uk/find-a-plumber/
    """
    
    SEARCH_URL = "https://www.ciphe.org.uk/find-a-plumber/"
    
    def __init__(self, session: requests.Session):
        self.session = session
        self.source_name = 'ciphe'
    
    def scrape_postcode(self, postcode: str) -> List[Dict]:
        """Search CIPHE for plumbers in postcode"""
        results = []
        log.info(f"  [CIPHE] Searching {postcode}")
        
        params = {
            'q': postcode,
            'radius': '10',
        }
        
        resp = safe_get(self.session, self.SEARCH_URL, params=params)
        if not resp:
            return results
        
        soup = BeautifulSoup(resp.text, 'lxml')
        
        # CIPHE member listings
        members = soup.select('div.member-result') or soup.select('div.search-result') or soup.select('article.member')
        
        for member in members:
            plumber = self._parse_member(member)
            if plumber:
                results.append(plumber)
        
        polite_delay()
        log.info(f"  [CIPHE] Found {len(results)} members in {postcode}")
        return results
    
    def _parse_member(self, el) -> Optional[Dict]:
        """Parse CIPHE member entry"""
        try:
            name_el = el.select_one('h2, h3, .member-name, strong')
            if not name_el:
                return None
            name = name_el.get_text(strip=True)
            
            full_text = el.get_text(' ', strip=True)
            
            phone_match = re.search(r'(0[1-9]\d{8,9}|07\d{9})', full_text.replace(' ', ''))
            phone = clean_phone(phone_match.group(1)) if phone_match else None
            
            pc_match = re.search(r'[A-Z]{1,2}[0-9]{1,2}[A-Z]?\s?[0-9][A-Z]{2}', full_text.upper())
            postcode = clean_postcode(pc_match.group(0)) if pc_match else None
            
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', full_text)
            email = email_match.group(0).lower() if email_match else None
            
            return {
                'id': generate_id(name, postcode or ''),
                'name': name,
                'trading_name': name,
                'phone': phone,
                'email': email,
                'website': None,
                'address': full_text[:200],
                'postcode': postcode or '',
                'postcode_area': extract_postcode_area(postcode or ''),
                'rating': None,
                'review_count': 0,
                'source': self.source_name,
                'qualifications': ['CIPHE Member'],
                'gas_safe': False,
                'scraped_at': datetime.now().isoformat(),
                'can_receive_jobs': False,
                'status': 'scraped',
            }
        except Exception as e:
            log.debug(f"CIPHE parse error: {e}")
            return None


# ============================================================================
# SOURCE 4: APHC SCRAPER
# ============================================================================

class APHCScraper:
    """
    Scrapes APHC (Association of Plumbing & Heating Contractors).
    
    URL: https://aphc.co.uk/find-a-member/
    """
    
    SEARCH_URL = "https://aphc.co.uk/find-a-member/"
    
    def __init__(self, session: requests.Session):
        self.session = session
        self.source_name = 'aphc'
    
    def scrape_postcode(self, postcode: str) -> List[Dict]:
        """Search APHC for members in postcode"""
        results = []
        log.info(f"  [APHC] Searching {postcode}")
        
        # APHC uses a form POST
        data = {
            'location': postcode,
            'radius': '10',
        }
        
        try:
            resp = self.session.post(
                self.SEARCH_URL,
                data=data,
                timeout=15,
                headers={**HEADERS, 'Referer': self.SEARCH_URL}
            )
            
            if not resp or resp.status_code != 200:
                return results
            
            soup = BeautifulSoup(resp.text, 'lxml')
            members = soup.select('div.member') or soup.select('article.company') or soup.select('li.result-item')
            
            for member in members:
                plumber = self._parse_member(member)
                if plumber:
                    results.append(plumber)
        
        except Exception as e:
            log.debug(f"APHC error for {postcode}: {e}")
        
        polite_delay()
        log.info(f"  [APHC] Found {len(results)} members in {postcode}")
        return results
    
    def _parse_member(self, el) -> Optional[Dict]:
        """Parse APHC member entry"""
        try:
            name_el = el.select_one('h2, h3, .company-name, strong')
            if not name_el:
                return None
            name = name_el.get_text(strip=True)
            
            full_text = el.get_text(' ', strip=True)
            
            phone_match = re.search(r'(0[1-9]\d{8,9}|07\d{9})', full_text.replace(' ', ''))
            phone = clean_phone(phone_match.group(1)) if phone_match else None
            
            pc_match = re.search(r'[A-Z]{1,2}[0-9]{1,2}[A-Z]?\s?[0-9][A-Z]{2}', full_text.upper())
            postcode = clean_postcode(pc_match.group(0)) if pc_match else None
            
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', full_text)
            email = email_match.group(0).lower() if email_match else None
            
            return {
                'id': generate_id(name, postcode or ''),
                'name': name,
                'trading_name': name,
                'phone': phone,
                'email': email,
                'website': None,
                'address': full_text[:200],
                'postcode': postcode or '',
                'postcode_area': extract_postcode_area(postcode or ''),
                'rating': None,
                'review_count': 0,
                'source': self.source_name,
                'qualifications': ['APHC Member'],
                'gas_safe': False,
                'scraped_at': datetime.now().isoformat(),
                'can_receive_jobs': False,
                'status': 'scraped',
            }
        except Exception as e:
            log.debug(f"APHC parse error: {e}")
            return None


# ============================================================================
# SOURCE 5: GAS SAFE REGISTER SCRAPER
# ============================================================================

class GasSafeScraper:
    """
    Scrapes Gas Safe Register for registered engineers.
    
    URL: https://www.gassaferegister.co.uk/find-an-engineer/
    
    Note: Gas Safe has strong anti-scraping. We use their public search
    and extract visible results only. Rate limit heavily.
    """
    
    SEARCH_URL = "https://www.gassaferegister.co.uk/find-an-engineer/"
    
    def __init__(self, session: requests.Session):
        self.session = session
        self.source_name = 'gas_safe'
    
    def scrape_postcode(self, postcode: str) -> List[Dict]:
        """Search Gas Safe for engineers in postcode"""
        results = []
        log.info(f"  [Gas Safe] Searching {postcode}")
        
        params = {
            'postcode': postcode,
            'distance': '10',
        }
        
        resp = safe_get(self.session, self.SEARCH_URL, params=params)
        if not resp:
            return results
        
        soup = BeautifulSoup(resp.text, 'lxml')
        
        # Gas Safe result cards
        engineers = (soup.select('div.engineer-card') or 
                    soup.select('div.search-result') or 
                    soup.select('li.engineer'))
        
        for eng in engineers:
            plumber = self._parse_engineer(eng)
            if plumber:
                results.append(plumber)
        
        # Gas Safe - extra delay to be polite
        time.sleep(random.uniform(4.0, 7.0))
        log.info(f"  [Gas Safe] Found {len(results)} engineers in {postcode}")
        return results
    
    def _parse_engineer(self, el) -> Optional[Dict]:
        """Parse Gas Safe engineer entry"""
        try:
            name_el = el.select_one('h2, h3, .engineer-name, .business-name')
            if not name_el:
                return None
            name = name_el.get_text(strip=True)
            
            full_text = el.get_text(' ', strip=True)
            
            phone_match = re.search(r'(0[1-9]\d{8,9}|07\d{9})', full_text.replace(' ', ''))
            phone = clean_phone(phone_match.group(1)) if phone_match else None
            
            pc_match = re.search(r'[A-Z]{1,2}[0-9]{1,2}[A-Z]?\s?[0-9][A-Z]{2}', full_text.upper())
            postcode = clean_postcode(pc_match.group(0)) if pc_match else None
            
            # Gas Safe number
            gs_match = re.search(r'Gas Safe.*?(\d{6})', full_text)
            gs_number = gs_match.group(1) if gs_match else None
            
            return {
                'id': generate_id(name, postcode or ''),
                'name': name,
                'trading_name': name,
                'phone': phone,
                'email': None,
                'website': None,
                'address': full_text[:200],
                'postcode': postcode or '',
                'postcode_area': extract_postcode_area(postcode or ''),
                'rating': None,
                'review_count': 0,
                'source': self.source_name,
                'qualifications': ['Gas Safe Registered'],
                'gas_safe': True,
                'gas_safe_number': gs_number,
                'scraped_at': datetime.now().isoformat(),
                'can_receive_jobs': False,
                'status': 'scraped',
            }
        except Exception as e:
            log.debug(f"Gas Safe parse error: {e}")
            return None


# ============================================================================
# DATABASE HANDLER
# ============================================================================

class DatabaseHandler:
    """
    Saves scraped plumbers to PostgreSQL database.
    Falls back to JSON file if no database configured.
    """
    
    def __init__(self):
        self.db_url = os.getenv('DATABASE_URL')
        self.conn = None
        self.json_fallback = 'scraped_plumbers.json'
        self.json_data = {}
        
        if self.db_url:
            self._connect()
        else:
            log.info("No DATABASE_URL - using JSON file fallback")
            self._load_json()
    
    def _connect(self):
        """Connect to PostgreSQL"""
        try:
            self.conn = psycopg2.connect(self.db_url)
            self.conn.autocommit = False
            self._ensure_table()
            log.info("Connected to PostgreSQL database")
        except Exception as e:
            log.error(f"Database connection failed: {e}")
            log.info("Falling back to JSON file")
            self.conn = None
    
    def _ensure_table(self):
        """Create scraped_plumbers table if not exists"""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scraped_plumbers (
                    id VARCHAR(16) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    trading_name VARCHAR(255),
                    phone VARCHAR(20),
                    email VARCHAR(255),
                    website VARCHAR(500),
                    address TEXT,
                    postcode VARCHAR(10),
                    postcode_area VARCHAR(6),
                    rating DECIMAL(3,1),
                    review_count INTEGER DEFAULT 0,
                    source VARCHAR(50),
                    qualifications JSONB DEFAULT '[]',
                    gas_safe BOOLEAN DEFAULT FALSE,
                    gas_safe_number VARCHAR(20),
                    scraped_at TIMESTAMP,
                    can_receive_jobs BOOLEAN DEFAULT FALSE,
                    status VARCHAR(50) DEFAULT 'scraped',
                    contacted_at TIMESTAMP,
                    registered_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Add index on postcode for fast lookups
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_scraped_plumbers_postcode 
                ON scraped_plumbers(postcode_area)
            """)
            self.conn.commit()
            log.info("Database table ready")
    
    def save_plumber(self, plumber: Dict) -> bool:
        """Save single plumber, skip if duplicate"""
        if self.conn:
            return self._save_to_db(plumber)
        else:
            return self._save_to_json(plumber)
    
    def save_batch(self, plumbers: List[Dict]) -> Tuple[int, int]:
        """Save batch of plumbers. Returns (saved, skipped) count."""
        saved = 0
        skipped = 0
        
        for plumber in plumbers:
            if plumber.get('id') and self.save_plumber(plumber):
                saved += 1
            else:
                skipped += 1
        
        return saved, skipped
    
    def _save_to_db(self, plumber: Dict) -> bool:
        """Insert or skip if duplicate (ON CONFLICT DO NOTHING)"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO scraped_plumbers 
                    (id, name, trading_name, phone, email, website, address,
                     postcode, postcode_area, rating, review_count, source,
                     qualifications, gas_safe, scraped_at, can_receive_jobs, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    plumber['id'],
                    plumber['name'],
                    plumber.get('trading_name'),
                    plumber.get('phone'),
                    plumber.get('email'),
                    plumber.get('website'),
                    plumber.get('address'),
                    plumber.get('postcode'),
                    plumber.get('postcode_area'),
                    plumber.get('rating'),
                    plumber.get('review_count', 0),
                    plumber.get('source'),
                    json.dumps(plumber.get('qualifications', [])),
                    plumber.get('gas_safe', False),
                    plumber.get('scraped_at'),
                    plumber.get('can_receive_jobs', False),
                    plumber.get('status', 'scraped'),
                ))
                rows_affected = cur.rowcount
                self.conn.commit()
                return rows_affected > 0
        except Exception as e:
            self.conn.rollback()
            log.debug(f"DB save error: {e}")
            return False
    
    def _save_to_json(self, plumber: Dict) -> bool:
        """Save to JSON file fallback"""
        pid = plumber.get('id')
        if not pid or pid in self.json_data:
            return False
        self.json_data[pid] = plumber
        self._write_json()
        return True
    
    def _load_json(self):
        """Load existing JSON database"""
        if os.path.exists(self.json_fallback):
            with open(self.json_fallback) as f:
                self.json_data = json.load(f)
            log.info(f"Loaded {len(self.json_data)} existing records from JSON")
    
    def _write_json(self):
        """Write JSON database to disk"""
        with open(self.json_fallback, 'w') as f:
            json.dump(self.json_data, f, indent=2, default=str)
    
    def count(self) -> int:
        """Return total records"""
        if self.conn:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM scraped_plumbers")
                return cur.fetchone()[0]
        return len(self.json_data)
    
    def count_by_source(self) -> Dict[str, int]:
        """Return counts per source"""
        if self.conn:
            with self.conn.cursor() as cur:
                cur.execute("SELECT source, COUNT(*) FROM scraped_plumbers GROUP BY source ORDER BY COUNT(*) DESC")
                return {row[0]: row[1] for row in cur.fetchall()}
        
        counts = {}
        for p in self.json_data.values():
            src = p.get('source', 'unknown')
            counts[src] = counts.get(src, 0) + 1
        return counts
    
    def close(self):
        """Close DB connection"""
        if self.conn:
            self.conn.close()
        if self.json_data:
            self._write_json()


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

class PlumberScraper:
    """
    Orchestrates scraping across all sources and postcodes.
    Handles deduplication, progress tracking, and database saving.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        
        self.db = DatabaseHandler()
        self.seen_ids = set()
        
        # Initialise all scrapers
        self.scrapers = {
            'yell': YellScraper(self.session),
            'watersafe': WaterSafeScraper(self.session),
            'ciphe': CIPHEScraper(self.session),
            'aphc': APHCScraper(self.session),
            'gas_safe': GasSafeScraper(self.session),
        }
        
        # Progress tracking
        self.stats = {
            'total_found': 0,
            'total_saved': 0,
            'total_skipped': 0,
            'by_source': {},
            'started_at': datetime.now().isoformat(),
        }
    
    def run(self, sources: List[str] = None, postcodes: List[str] = None, 
            max_pages: int = 10, limit_postcodes: int = None):
        """
        Main scraping run.
        
        Args:
            sources: List of sources to use. None = all sources.
            postcodes: List of postcodes to scrape. None = all postcodes.
            max_pages: Max pages per postcode per source (Yell).
            limit_postcodes: Limit number of postcodes (for testing).
        """
        sources = sources or list(self.scrapers.keys())
        postcodes = postcodes or ALL_POSTCODES
        
        if limit_postcodes:
            postcodes = postcodes[:limit_postcodes]
        
        log.info("=" * 70)
        log.info("PLUMBFLOW PLUMBER SCRAPER - STARTING")
        log.info("=" * 70)
        log.info(f"Sources: {', '.join(sources)}")
        log.info(f"Postcodes: {len(postcodes)} areas to scrape")
        log.info(f"Existing records in DB: {self.db.count()}")
        log.info("=" * 70)
        
        total_postcodes = len(postcodes)
        
        for i, postcode in enumerate(postcodes, 1):
            log.info(f"\n[{i}/{total_postcodes}] Processing postcode area: {postcode}")
            
            for source_name in sources:
                if source_name not in self.scrapers:
                    log.warning(f"Unknown source: {source_name}")
                    continue
                
                scraper = self.scrapers[source_name]
                
                try:
                    if source_name == 'yell':
                        plumbers = scraper.scrape_postcode(postcode, max_pages=max_pages)
                    else:
                        plumbers = scraper.scrape_postcode(postcode)
                    
                    # Deduplicate within this run
                    new_plumbers = []
                    for p in plumbers:
                        if p and p.get('id') and p['id'] not in self.seen_ids:
                            self.seen_ids.add(p['id'])
                            new_plumbers.append(p)
                    
                    # Save to database
                    saved, skipped = self.db.save_batch(new_plumbers)
                    
                    self.stats['total_found'] += len(plumbers)
                    self.stats['total_saved'] += saved
                    self.stats['total_skipped'] += skipped
                    self.stats['by_source'][source_name] = self.stats['by_source'].get(source_name, 0) + saved
                    
                    log.info(f"    ✓ {source_name}: {len(plumbers)} found, {saved} new, {skipped} duplicates")
                
                except Exception as e:
                    log.error(f"Error scraping {source_name} for {postcode}: {e}")
                
                polite_delay()
            
            # Progress update every 10 postcodes
            if i % 10 == 0:
                self._print_progress(i, total_postcodes)
        
        self._print_final_report()
    
    def _print_progress(self, current: int, total: int):
        """Print progress update"""
        pct = (current / total) * 100
        log.info("\n" + "─" * 50)
        log.info(f"PROGRESS: {current}/{total} postcodes ({pct:.0f}%)")
        log.info(f"Total in DB: {self.db.count()}")
        log.info(f"This run: {self.stats['total_saved']} new records")
        log.info("─" * 50 + "\n")
    
    def _print_final_report(self):
        """Print final scraping report"""
        log.info("\n" + "=" * 70)
        log.info("SCRAPING COMPLETE")
        log.info("=" * 70)
        log.info(f"Total found:   {self.stats['total_found']:,}")
        log.info(f"New saved:     {self.stats['total_saved']:,}")
        log.info(f"Duplicates:    {self.stats['total_skipped']:,}")
        log.info(f"Total in DB:   {self.db.count():,}")
        log.info("\nBy source:")
        for source, count in self.stats['by_source'].items():
            log.info(f"  {source:15}: {count:,} new records")
        log.info("\nBy source (DB totals):")
        for source, count in self.db.count_by_source().items():
            log.info(f"  {source:15}: {count:,} total")
        log.info("=" * 70)
        
        # Save stats report
        stats_file = f"scraping_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
        log.info(f"\nReport saved to: {stats_file}")


# ============================================================================
# FLASK API ENDPOINTS (for Railway deployment)
# ============================================================================

def register_scraper_routes(app):
    """
    Register scraper control endpoints with Flask app.
    Call this from your main.py:
    
        from plumber_scraper import register_scraper_routes
        register_scraper_routes(app)
    """
    import threading
    
    scraper_status = {
        'running': False,
        'progress': 0,
        'total': 0,
        'saved': 0,
        'started_at': None,
        'completed_at': None,
        'error': None,
    }
    
    def run_scraper_thread(sources, limit_postcodes):
        """Run scraper in background thread"""
        try:
            scraper_status['running'] = True
            scraper_status['started_at'] = datetime.now().isoformat()
            scraper_status['error'] = None
            
            scraper = PlumberScraper()
            scraper.run(sources=sources, limit_postcodes=limit_postcodes)
            
            scraper_status['saved'] = scraper.stats['total_saved']
            scraper_status['completed_at'] = datetime.now().isoformat()
        except Exception as e:
            scraper_status['error'] = str(e)
            log.error(f"Scraper thread error: {e}")
        finally:
            scraper_status['running'] = False
    
    @app.route('/api/scraper/start', methods=['POST'])
    def start_scraper():
        from flask import request, jsonify
        
        if scraper_status['running']:
            return jsonify({'error': 'Scraper already running'}), 409
        
        data = request.get_json(silent=True) or {}
        sources = data.get('sources', None)  # None = all sources
        limit_postcodes = data.get('limit_postcodes', None)  # None = all postcodes
        
        thread = threading.Thread(
            target=run_scraper_thread,
            args=(sources, limit_postcodes),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            'status': 'started',
            'sources': sources or 'all',
            'message': 'Scraper started in background. Check /api/scraper/status for progress.'
        })
    
    @app.route('/api/scraper/status')
    def scraper_status_endpoint():
        from flask import jsonify
        db = DatabaseHandler()
        total_in_db = db.count()
        by_source = db.count_by_source()
        db.close()
        
        return jsonify({
            **scraper_status,
            'total_in_database': total_in_db,
            'by_source': by_source,
        })
    
    @app.route('/api/scraper/results')
    def scraper_results():
        from flask import jsonify, request
        
        db = DatabaseHandler()
        
        if db.conn:
            postcode_area = request.args.get('postcode')
            source = request.args.get('source')
            limit = int(request.args.get('limit', 50))
            
            with db.conn.cursor() as cur:
                query = "SELECT id, name, phone, email, postcode, postcode_area, source, gas_safe, status FROM scraped_plumbers WHERE 1=1"
                params = []
                
                if postcode_area:
                    query += " AND postcode_area = %s"
                    params.append(postcode_area.upper())
                
                if source:
                    query += " AND source = %s"
                    params.append(source)
                
                query += " ORDER BY created_at DESC LIMIT %s"
                params.append(limit)
                
                cur.execute(query, params)
                cols = [desc[0] for desc in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        else:
            rows = list(db.json_data.values())[:50]
        
        db.close()
        return jsonify({'count': len(rows), 'plumbers': rows})


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='PlumbFlow Plumber Registry Scraper')
    parser.add_argument('--source', choices=['yell', 'watersafe', 'ciphe', 'aphc', 'gas_safe'],
                        help='Single source to scrape (default: all)')
    parser.add_argument('--postcode', type=str, help='Single postcode to test (e.g. SW19)')
    parser.add_argument('--limit', type=int, default=None, help='Limit to N postcodes (for testing)')
    parser.add_argument('--max-pages', type=int, default=10, help='Max pages per postcode on Yell (default: 10)')
    parser.add_argument('--test', action='store_true', help='Quick test: 5 postcodes, Yell only')
    
    args = parser.parse_args()
    
    # Quick test mode
    if args.test:
        log.info("TEST MODE: 5 postcodes, Yell only")
        scraper = PlumberScraper()
        scraper.run(
            sources=['yell'],
            postcodes=['SW19', 'SW18', 'SE1', 'E1', 'N1'],
            max_pages=3
        )
        sys.exit(0)
    
    # Single postcode test
    if args.postcode:
        sources = [args.source] if args.source else list(PlumberScraper().__class__.scrapers if False else ['yell', 'watersafe', 'ciphe', 'aphc', 'gas_safe'])
        scraper = PlumberScraper()
        scraper.run(
            sources=[args.source] if args.source else None,
            postcodes=[args.postcode.upper()],
            max_pages=args.max_pages
        )
        sys.exit(0)
    
    # Full run
    scraper = PlumberScraper()
    scraper.run(
        sources=[args.source] if args.source else None,
        limit_postcodes=args.limit,
        max_pages=args.max_pages
    )
