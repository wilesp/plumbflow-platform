"""
AD SCRAPER ENGINE
Automatically scrapes plumbing job ads from multiple platforms
"""

import re
import time
import json
import hashlib
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import requests
from bs4 import BeautifulSoup

@dataclass
class ScrapedAd:
    """Raw scraped advertisement"""
    source_platform: str
    source_url: str
    ad_id_on_platform: str
    title: str
    description: str
    raw_html: str
    customer_name: Optional[str]
    customer_phone: Optional[str]
    customer_email: Optional[str]
    customer_postcode: Optional[str]
    posted_date: Optional[datetime]
    scraped_at: datetime
    
    def to_dict(self):
        data = asdict(self)
        # Convert datetime to string
        data['posted_date'] = self.posted_date.isoformat() if self.posted_date else None
        data['scraped_at'] = self.scraped_at.isoformat()
        return data
    
    def get_unique_id(self) -> str:
        """Generate unique ID for deduplication"""
        content = f"{self.title}{self.description}{self.customer_phone}"
        return hashlib.md5(content.encode()).hexdigest()


class BaseScraper:
    """Base class for all platform scrapers"""
    
    PLUMBING_KEYWORDS = [
        'plumber', 'plumbing', 'leak', 'tap', 'toilet', 'boiler',
        'radiator', 'heating', 'pipe', 'drain', 'water', 'bathroom',
        'shower', 'sink', 'cistern', 'flush', 'burst', 'emergency'
    ]
    
    LONDON_POSTCODES = [
        'SW', 'SE', 'E', 'N', 'W', 'NW', 'EC', 'WC',
        'CR', 'BR', 'DA', 'EN', 'HA', 'IG', 'KT', 'RM', 'SM', 'TW', 'UB'
    ]
    
    def __init__(self, use_proxy: bool = False):
        self.use_proxy = use_proxy
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def extract_postcode(self, text: str) -> Optional[str]:
        """Extract UK postcode from text"""
        # UK postcode pattern
        pattern = r'([A-Z]{1,2}[0-9]{1,2}[A-Z]?\s?[0-9][A-Z]{2})'
        match = re.search(pattern, text.upper())
        return match.group(1) if match else None
    
    def extract_phone(self, text: str) -> Optional[str]:
        """Extract UK phone number from text"""
        # UK phone patterns
        patterns = [
            r'(\+44\s?7\d{3}\s?\d{6})',  # +44 7xxx xxxxxx
            r'(07\d{3}\s?\d{6})',         # 07xxx xxxxxx
            r'(\+44\s?[1-9]\d{2,4}\s?\d{6})',  # +44 landline
            r'(0[1-9]\d{2,4}\s?\d{6})'    # 0xxxx xxxxxx
        ]
        for pattern in patterns:
            match = re.search(pattern, text.replace('-', ' '))
            if match:
                return match.group(1).replace(' ', '')
        return None
    
    def extract_email(self, text: str) -> Optional[str]:
        """Extract email from text"""
        pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        match = re.search(pattern, text)
        return match.group(0) if match else None
    
    def is_plumbing_related(self, text: str) -> bool:
        """Check if text is plumbing-related"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.PLUMBING_KEYWORDS)
    
    def is_london_area(self, text: str) -> bool:
        """Check if location is in London/SE"""
        text_upper = text.upper()
        return any(postcode in text_upper for postcode in self.LONDON_POSTCODES)
    
    def fetch_page(self, url: str, retries: int = 3) -> Optional[str]:
        """Fetch page content with retries"""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response.text
            except Exception as e:
                print(f"Error fetching {url} (attempt {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        return None
    
    def scrape(self) -> List[ScrapedAd]:
        """Override in subclass"""
        raise NotImplementedError


class GumtreeScraper(BaseScraper):
    """Scraper for Gumtree classifieds"""
    
    BASE_URL = "https://www.gumtree.com"
    
    SEARCH_QUERIES = [
        "/search?search_category=services-wanted&q=plumber&search_location=london",
        "/search?search_category=services-wanted&q=leak&search_location=london",
        "/search?search_category=services-wanted&q=boiler&search_location=london",
        "/search?search_category=services-wanted&q=toilet&search_location=london",
    ]
    
    def scrape(self) -> List[ScrapedAd]:
        """Scrape Gumtree for plumbing service requests"""
        ads = []
        
        for query in self.SEARCH_QUERIES:
            print(f"Scraping Gumtree: {query}")
            url = self.BASE_URL + query
            html = self.fetch_page(url)
            
            if not html:
                continue
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all listing cards
            listings = soup.find_all('article', class_='listing-maxi')
            
            for listing in listings:
                try:
                    ad = self._parse_listing(listing)
                    if ad and self._validate_ad(ad):
                        ads.append(ad)
                except Exception as e:
                    print(f"Error parsing Gumtree listing: {e}")
                    continue
            
            time.sleep(2)  # Rate limiting
        
        print(f"Scraped {len(ads)} ads from Gumtree")
        return ads
    
    def _parse_listing(self, listing) -> Optional[ScrapedAd]:
        """Parse individual Gumtree listing"""
        
        # Extract title
        title_elem = listing.find('h2', class_='listing-title')
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)
        
        # Extract description
        desc_elem = listing.find('p', class_='listing-description')
        description = desc_elem.get_text(strip=True) if desc_elem else ""
        
        # Extract URL
        link_elem = listing.find('a', class_='listing-link')
        if not link_elem or not link_elem.get('href'):
            return None
        listing_url = self.BASE_URL + link_elem['href']
        
        # Extract ad ID from URL
        ad_id = listing_url.split('/')[-1]
        
        # Extract location
        location_elem = listing.find('span', class_='listing-location')
        location = location_elem.get_text(strip=True) if location_elem else ""
        
        # Extract date
        date_elem = listing.find('span', class_='listing-posted-date')
        posted_date = self._parse_date(date_elem.get_text(strip=True)) if date_elem else None
        
        # Combine text for contact extraction
        full_text = f"{title} {description} {location}"
        
        # Extract contact info
        postcode = self.extract_postcode(full_text)
        phone = self.extract_phone(full_text)
        email = self.extract_email(full_text)
        
        # Try to fetch detail page for more contact info
        # NOTE: In production, this should be done asynchronously to avoid blocking
        detail_html = self.fetch_page(listing_url)
        if detail_html:
            detail_soup = BeautifulSoup(detail_html, 'html.parser')
            detail_text = detail_soup.get_text()
            
            if not phone:
                phone = self.extract_phone(detail_text)
            if not email:
                email = self.extract_email(detail_text)
            if not postcode:
                postcode = self.extract_postcode(detail_text)
        
        return ScrapedAd(
            source_platform='gumtree',
            source_url=listing_url,
            ad_id_on_platform=ad_id,
            title=title,
            description=description,
            raw_html=str(listing),
            customer_name=None,  # Usually not available
            customer_phone=phone,
            customer_email=email,
            customer_postcode=postcode,
            posted_date=posted_date,
            scraped_at=datetime.now()
        )
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse Gumtree date strings like '2 hours ago', 'Yesterday', etc."""
        now = datetime.now()
        date_str = date_str.lower().strip()
        
        if 'min' in date_str or 'hour' in date_str:
            return now
        elif 'yesterday' in date_str:
            return now.replace(day=now.day-1)
        elif 'day' in date_str:
            days = int(re.search(r'\d+', date_str).group())
            return now.replace(day=now.day-days)
        else:
            return now
    
    def _validate_ad(self, ad: ScrapedAd) -> bool:
        """Validate ad meets criteria"""
        # Must be plumbing-related
        if not self.is_plumbing_related(ad.title + " " + ad.description):
            return False
        
        # Must have location in London/SE
        if ad.customer_postcode:
            if not self.is_london_area(ad.customer_postcode):
                return False
        else:
            # No postcode, check description
            if not self.is_london_area(ad.description):
                return False
        
        # Must have some contact info
        if not (ad.customer_phone or ad.customer_email):
            return False
        
        return True


class FacebookMarketplaceScraper(BaseScraper):
    """
    Scraper for Facebook Marketplace service requests
    
    NOTE: Facebook has strong anti-scraping measures.
    In production, use Facebook Graph API instead.
    This is a simplified example.
    """
    
    def scrape(self) -> List[ScrapedAd]:
        """
        Placeholder for Facebook scraping
        
        In production, you should:
        1. Use Facebook Graph API (requires business approval)
        2. Or create browser extension for manual submission
        3. Or use official Facebook partner integrations
        """
        print("Facebook scraping requires Graph API - skipping for now")
        return []


class EmailLeadParser:
    """
    Parse leads from forwarded emails
    
    Plumbers can forward Checkatrade/MyBuilder emails to a dedicated inbox
    This parser extracts lead info from those emails
    """
    
    def parse_checkatrade_email(self, email_body: str) -> Optional[ScrapedAd]:
        """Parse lead from Checkatrade email notification"""
        
        # Extract key fields using regex
        job_title_match = re.search(r'Job:\s*(.+)', email_body)
        description_match = re.search(r'Description:\s*(.+?)(?:\n\n|\Z)', email_body, re.DOTALL)
        postcode_match = re.search(r'Postcode:\s*([A-Z0-9\s]+)', email_body)
        phone_match = re.search(r'Phone:\s*([\d\s+]+)', email_body)
        
        if not (job_title_match and description_match):
            return None
        
        return ScrapedAd(
            source_platform='checkatrade_email',
            source_url='email',
            ad_id_on_platform=f"email_{datetime.now().timestamp()}",
            title=job_title_match.group(1).strip(),
            description=description_match.group(1).strip(),
            raw_html=email_body,
            customer_name=None,
            customer_phone=phone_match.group(1).strip() if phone_match else None,
            customer_email=None,
            customer_postcode=postcode_match.group(1).strip() if postcode_match else None,
            posted_date=datetime.now(),
            scraped_at=datetime.now()
        )


class ScraperOrchestrator:
    """
    Orchestrates all scrapers and manages scraping schedule
    """
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self.scrapers = [
            GumtreeScraper(),
            # FacebookMarketplaceScraper(),  # Requires API access
        ]
        self.seen_ads = set()  # For deduplication
    
    def run_scraping_cycle(self) -> List[ScrapedAd]:
        """Run one complete scraping cycle across all platforms"""
        all_ads = []
        
        print(f"\n{'='*60}")
        print(f"Starting scraping cycle at {datetime.now()}")
        print(f"{'='*60}\n")
        
        for scraper in self.scrapers:
            try:
                ads = scraper.scrape()
                # Deduplicate
                new_ads = self._deduplicate(ads)
                all_ads.extend(new_ads)
                print(f"Found {len(new_ads)} new ads from {scraper.__class__.__name__}")
            except Exception as e:
                print(f"Error in {scraper.__class__.__name__}: {e}")
        
        print(f"\nTotal new ads this cycle: {len(all_ads)}")
        
        # Save to database if connected
        if self.db:
            self._save_to_database(all_ads)
        
        return all_ads
    
    def _deduplicate(self, ads: List[ScrapedAd]) -> List[ScrapedAd]:
        """Remove duplicate ads"""
        new_ads = []
        
        for ad in ads:
            ad_id = ad.get_unique_id()
            if ad_id not in self.seen_ads:
                self.seen_ads.add(ad_id)
                new_ads.append(ad)
        
        return new_ads
    
    def _save_to_database(self, ads: List[ScrapedAd]):
        """Save scraped ads to database"""
        # In production, use proper DB connection
        # This is a placeholder
        for ad in ads:
            print(f"Would save to DB: {ad.title[:50]}...")
    
    def start_continuous_scraping(self, interval_minutes: int = 15):
        """
        Start continuous scraping on schedule
        
        Args:
            interval_minutes: How often to scrape (default 15 mins)
        """
        import schedule
        
        schedule.every(interval_minutes).minutes.do(self.run_scraping_cycle)
        
        print(f"Started continuous scraping every {interval_minutes} minutes")
        print("Press Ctrl+C to stop")
        
        # Run immediately on start
        self.run_scraping_cycle()
        
        # Then run on schedule
        while True:
            schedule.run_pending()
            time.sleep(60)


# ================================================================
# DEMO / TESTING
# ================================================================

if __name__ == "__main__":
    print("PLUMBER AD SCRAPER - DEMO MODE")
    print("="*60)
    
    # Test individual scraper
    print("\nTesting Gumtree scraper...")
    scraper = GumtreeScraper()
    
    # NOTE: This is a demo. Actual scraping would work on live Gumtree
    # For testing, we'll create sample data
    print("\n⚠️  NOTE: This is demo mode with sample data")
    print("In production, this would scrape live Gumtree listings")
    
    # Create sample scraped ads for demonstration
    sample_ads = [
        ScrapedAd(
            source_platform='gumtree',
            source_url='https://gumtree.com/example/123',
            ad_id_on_platform='123',
            title='Urgent - Kitchen tap leaking badly',
            description='Need plumber ASAP. Kitchen tap dripping constantly. Located in Wimbledon SW19. Please call 07700900123',
            raw_html='<html>...</html>',
            customer_name=None,
            customer_phone='07700900123',
            customer_email=None,
            customer_postcode='SW19',
            posted_date=datetime.now(),
            scraped_at=datetime.now()
        ),
        ScrapedAd(
            source_platform='gumtree',
            source_url='https://gumtree.com/example/124',
            ad_id_on_platform='124',
            title='Toilet won\'t stop running',
            description='Toilet cistern fills continuously, wasting water. Need fix this week. Tooting SW17. Contact: test@example.com',
            raw_html='<html>...</html>',
            customer_name=None,
            customer_phone=None,
            customer_email='test@example.com',
            customer_postcode='SW17',
            posted_date=datetime.now(),
            scraped_at=datetime.now()
        ),
        ScrapedAd(
            source_platform='gumtree',
            source_url='https://gumtree.com/example/125',
            ad_id_on_platform='125',
            title='Emergency - Burst pipe in bathroom',
            description='URGENT! Pipe burst behind toilet, water everywhere. Need emergency plumber NOW. Clapham SW4 8TH. Call 07700900456',
            raw_html='<html>...</html>',
            customer_name=None,
            customer_phone='07700900456',
            customer_email=None,
            customer_postcode='SW4 8TH',
            posted_date=datetime.now(),
            scraped_at=datetime.now()
        )
    ]
    
    print(f"\nFound {len(sample_ads)} sample ads:")
    print("="*60)
    
    for i, ad in enumerate(sample_ads, 1):
        print(f"\n📋 Ad {i}:")
        print(f"Title: {ad.title}")
        print(f"Platform: {ad.source_platform}")
        print(f"Postcode: {ad.customer_postcode}")
        print(f"Phone: {ad.customer_phone or 'N/A'}")
        print(f"Email: {ad.customer_email or 'N/A'}")
        print(f"Description: {ad.description[:100]}...")
    
    print("\n" + "="*60)
    print("To run continuous scraping:")
    print("  orchestrator = ScraperOrchestrator()")
    print("  orchestrator.start_continuous_scraping(interval_minutes=15)")
    print("="*60)
