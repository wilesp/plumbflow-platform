"""
PLUMBERFLOW - UK-WIDE AD SCRAPER (Market Research Mode)
Saves to JSON file for offline review - NO DATABASE
"""

import os, re, time, json, hashlib, logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# Output file
OUTPUT_FILE = f"scraped_ads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

# ============================================================================
# GUMTREE SCRAPER - UK WIDE
# ============================================================================

class GumtreeScraper:
    """Scrape plumbing job ads from Gumtree - UK-wide"""
    
    def __init__(self):
        self.base_url = "https://www.gumtree.com"
        # UK-wide search - no location filter
        self.search_url = "https://www.gumtree.com/search?search_category=services&q=plumber+needed"
        self.jobs = []
    
    def scrape(self, max_pages: int = 5) -> List[Dict]:
        """Scrape Gumtree job listings - UK-wide"""
        
        log.info("[Gumtree UK] Starting UK-wide scrape...")
        
        try:
            for page in range(1, max_pages + 1):
                url = f"{self.search_url}&page={page}"
                
                response = requests.get(url, timeout=15, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                if response.status_code != 200:
                    log.warning(f"Page {page} returned {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                listings = soup.find_all('article', class_='listing-maxi')
                
                log.info(f"[Gumtree UK] Page {page}: Found {len(listings)} listings")
                
                for listing in listings:
                    try:
                        job_data = self._extract_job_data(listing)
                        if job_data:
                            self.jobs.append(job_data)
                    except Exception as e:
                        log.error(f"Error processing listing: {e}")
                
                time.sleep(2)  # Be polite
            
            log.info(f"[Gumtree UK] ✅ Complete! Total: {len(self.jobs)} jobs")
            
            return self.jobs
        
        except Exception as e:
            log.error(f"[Gumtree UK] Scraper error: {e}")
            return self.jobs
    
    def _extract_job_data(self, listing) -> Optional[Dict]:
        """Extract job data from listing element"""
        try:
            title_elem = listing.find('h2', class_='listing-title')
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            
            # Skip if it's a plumber advertising their services
            skip_keywords = ['plumber available', 'plumbing services', 'qualified plumber', 'gas safe registered', 'plumbing & heating']
            if any(keyword in title.lower() for keyword in skip_keywords):
                return None
            
            link_elem = title_elem.find('a')
            url = self.base_url + link_elem['href'] if link_elem and 'href' in link_elem.attrs else None
            
            desc_elem = listing.find('div', class_='listing-description')
            description = desc_elem.get_text(strip=True) if desc_elem else ""
            
            location_elem = listing.find('span', class_='listing-location')
            location = location_elem.get_text(strip=True) if location_elem else ""
            
            # Extract postcode and geographic info
            postcode = self._extract_postcode(location + " " + description + " " + title)
            county = self._extract_county(location)
            region = self._extract_region(location, postcode)
            
            # Extract price if mentioned
            price = self._extract_price(title + " " + description)
            
            # Extract urgency keywords
            urgency = self._extract_urgency(title + " " + description)
            
            return {
                'source': 'gumtree',
                'source_url': url,
                'title': title,
                'description': description,
                'location': location,
                'postcode': postcode,
                'county': county,
                'region': region,
                'price_mentioned': price,
                'urgency': urgency,
                'scraped_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            log.debug(f"Error extracting job data: {e}")
            return None
    
    def _extract_postcode(self, text: str) -> Optional[str]:
        """Extract UK postcode from text"""
        match = re.search(r'\b([A-Z]{1,2}[0-9]{1,2}[A-Z]?\s?[0-9][A-Z]{2})\b', text.upper())
        return match.group(1).replace(' ', '') if match else None
    
    def _extract_county(self, location: str) -> Optional[str]:
        """Extract county from location"""
        counties = {
            'Greater London': ['london', 'sw', 'se', 'nw', 'ne', 'ec', 'wc', 'e1', 'n1'],
            'Hertfordshire': ['hertfordshire', 'herts', 'watford', 'hemel', 'stevenage'],
            'Essex': ['essex', 'chelmsford', 'colchester', 'southend'],
            'Kent': ['kent', 'maidstone', 'canterbury', 'dover'],
            'Surrey': ['surrey', 'guildford', 'woking'],
            'Berkshire': ['berkshire', 'reading', 'slough'],
            'Buckinghamshire': ['buckinghamshire', 'bucks', 'milton keynes'],
            'Bedfordshire': ['bedfordshire', 'beds', 'luton', 'bedford'],
            'Oxfordshire': ['oxfordshire', 'oxford'],
            'Northamptonshire': ['northamptonshire', 'northampton'],
            'Hampshire': ['hampshire', 'southampton', 'portsmouth'],
            'West Sussex': ['west sussex', 'brighton', 'worthing'],
            'East Sussex': ['east sussex', 'eastbourne', 'hastings'],
            'Cambridgeshire': ['cambridgeshire', 'cambridge', 'peterborough'],
            'Suffolk': ['suffolk', 'ipswich'],
            'Norfolk': ['norfolk', 'norwich'],
            'Leicestershire': ['leicestershire', 'leicester'],
            'Nottinghamshire': ['nottinghamshire', 'nottingham'],
            'Derbyshire': ['derbyshire', 'derby'],
            'Staffordshire': ['staffordshire', 'stoke'],
            'West Midlands': ['birmingham', 'wolverhampton', 'coventry'],
            'Warwickshire': ['warwickshire', 'warwick'],
            'Worcestershire': ['worcestershire', 'worcester'],
            'Gloucestershire': ['gloucestershire', 'gloucester'],
            'Wiltshire': ['wiltshire', 'swindon'],
            'Somerset': ['somerset', 'bath', 'bristol'],
            'Devon': ['devon', 'exeter', 'plymouth'],
            'Cornwall': ['cornwall', 'truro'],
            'Dorset': ['dorset', 'bournemouth'],
            'Yorkshire': ['yorkshire', 'leeds', 'sheffield', 'bradford', 'york'],
            'Lancashire': ['lancashire', 'preston', 'blackpool'],
            'Greater Manchester': ['manchester', 'salford', 'stockport'],
            'Merseyside': ['liverpool', 'wirral'],
            'Cheshire': ['cheshire', 'chester'],
            'Tyne and Wear': ['newcastle', 'sunderland', 'gateshead'],
            'Durham': ['durham', 'darlington'],
            'Cumbria': ['cumbria', 'carlisle'],
            'Scotland': ['scotland', 'edinburgh', 'glasgow', 'aberdeen'],
            'Wales': ['wales', 'cardiff', 'swansea'],
            'Northern Ireland': ['belfast', 'northern ireland']
        }
        
        location_lower = location.lower()
        for county, keywords in counties.items():
            if any(keyword in location_lower for keyword in keywords):
                return county
        
        return None
    
    def _extract_region(self, location: str, postcode: Optional[str]) -> str:
        """Determine UK region"""
        if not location and not postcode:
            return 'Unknown'
        
        text = (location + ' ' + (postcode or '')).lower()
        
        # London & South East
        if any(x in text for x in ['london', 'sw', 'se', 'nw', 'ne', 'ec', 'wc']):
            return 'London'
        if any(x in text for x in ['hertfordshire', 'essex', 'kent', 'surrey', 'berkshire', 'buckinghamshire', 'oxfordshire']):
            return 'South East'
        
        # South West
        if any(x in text for x in ['bristol', 'bath', 'plymouth', 'exeter', 'cornwall', 'devon', 'somerset', 'dorset', 'gloucestershire', 'wiltshire']):
            return 'South West'
        
        # Midlands
        if any(x in text for x in ['birmingham', 'nottingham', 'leicester', 'derby', 'coventry', 'wolverhampton', 'stoke']):
            return 'Midlands'
        
        # North West
        if any(x in text for x in ['manchester', 'liverpool', 'preston', 'blackpool', 'chester', 'lancashire', 'cheshire', 'merseyside']):
            return 'North West'
        
        # North East & Yorkshire
        if any(x in text for x in ['newcastle', 'sunderland', 'durlington', 'middlesbrough', 'leeds', 'sheffield', 'bradford', 'york', 'hull']):
            return 'North'
        
        # Scotland
        if any(x in text for x in ['scotland', 'edinburgh', 'glasgow', 'aberdeen', 'dundee']):
            return 'Scotland'
        
        # Wales
        if any(x in text for x in ['wales', 'cardiff', 'swansea', 'newport']):
            return 'Wales'
        
        # Northern Ireland
        if any(x in text for x in ['belfast', 'northern ireland', 'derry']):
            return 'Northern Ireland'
        
        return 'Unknown'
    
    def _extract_price(self, text: str) -> Optional[str]:
        """Extract price mention from text"""
        match = re.search(r'£\s?[0-9,]+', text)
        return match.group(0) if match else None
    
    def _extract_urgency(self, text: str) -> str:
        """Extract urgency level"""
        text_lower = text.lower()
        if any(word in text_lower for word in ['emergency', 'urgent', 'asap', 'immediately', 'today', 'now']):
            return 'emergency'
        if any(word in text_lower for word in ['soon', 'quick', 'this week']):
            return 'high'
        return 'normal'


# ============================================================================
# REDDIT SCRAPER - UK WIDE
# ============================================================================

class RedditScraper:
    """Scrape plumbing requests from UK Reddit - UK-wide"""
    
    def __init__(self):
        self.subreddits = [
            'london', 'AskUK', 'DIYUK', 'HousingUK',
            'manchester', 'birmingham', 'leeds', 'glasgow', 'edinburgh', 'liverpool',
            'bristol', 'sheffield', 'newcastle', 'cardiff',
            'unitedkingdom', 'CasualUK'
        ]
        self.search_terms = ['plumber', 'plumbing', 'leak', 'boiler', 'pipe', 'heating']
        self.jobs = []
    
    def scrape(self, days_back: int = 2) -> List[Dict]:
        """Scrape Reddit posts - UK-wide"""
        
        log.info("[Reddit UK] Starting UK-wide scrape...")
        
        try:
            for subreddit in self.subreddits:
                for term in self.search_terms:
                    url = f"https://www.reddit.com/r/{subreddit}/search.json?q={term}&restrict_sr=1&sort=new&t=week&limit=25"
                    
                    response = requests.get(url, headers={
                        'User-Agent': 'PlumberFlow Market Research v1.0'
                    }, timeout=10)
                    
                    if response.status_code != 200:
                        log.warning(f"Reddit API returned {response.status_code}")
                        continue
                    
                    data = response.json()
                    posts = data.get('data', {}).get('children', [])
                    
                    log.info(f"[Reddit UK] r/{subreddit} '{term}': {len(posts)} posts")
                    
                    for post in posts:
                        try:
                            job_data = self._extract_job_data(post['data'])
                            if job_data:
                                self.jobs.append(job_data)
                        except Exception as e:
                            log.error(f"Error processing post: {e}")
                    
                    time.sleep(2)  # Reddit rate limit
            
            # Deduplicate by URL
            unique_jobs = {job['source_url']: job for job in self.jobs}.values()
            self.jobs = list(unique_jobs)
            
            log.info(f"[Reddit UK] ✅ Complete! Total: {len(self.jobs)} jobs")
            
            return self.jobs
        
        except Exception as e:
            log.error(f"[Reddit UK] Scraper error: {e}")
            return self.jobs
    
    def _extract_job_data(self, post: Dict) -> Optional[Dict]:
        """Extract job data from Reddit post"""
        try:
            title = post.get('title', '')
            selftext = post.get('selftext', '')
            subreddit = post.get('subreddit', '')
            
            # Check if it's a job request
            request_keywords = ['need', 'looking for', 'recommend', 'help', 'emergency', 'urgent', 'anyone know']
            if not any(keyword in title.lower() or keyword in selftext.lower() for keyword in request_keywords):
                return None
            
            # Extract location info
            location = self._extract_location(title + " " + selftext)
            postcode = self._extract_postcode(title + " " + selftext)
            region = self._determine_region(subreddit, location, postcode)
            
            # Extract urgency
            urgency = self._extract_urgency(title + " " + selftext)
            
            return {
                'source': 'reddit',
                'source_url': f"https://reddit.com{post.get('permalink', '')}",
                'source_id': post.get('id'),
                'title': title,
                'description': selftext[:500],  # Limit description
                'location': location or f"r/{subreddit}",
                'postcode': postcode,
                'county': None,
                'region': region,
                'price_mentioned': None,
                'urgency': urgency,
                'scraped_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            log.debug(f"Error extracting Reddit job: {e}")
            return None
    
    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location from text"""
        # Try postcode areas first
        match = re.search(r'\b([A-Z]{1,2}\d{1,2})\b', text.upper())
        if match:
            return match.group(1)
        
        # Try city names
        cities = ['London', 'Manchester', 'Birmingham', 'Leeds', 'Glasgow', 'Liverpool', 'Bristol', 'Sheffield']
        for city in cities:
            if city.lower() in text.lower():
                return city
        
        return None
    
    def _extract_postcode(self, text: str) -> Optional[str]:
        """Extract UK postcode"""
        match = re.search(r'\b([A-Z]{1,2}[0-9]{1,2}[A-Z]?\s?[0-9][A-Z]{2})\b', text.upper())
        return match.group(1).replace(' ', '') if match else None
    
    def _determine_region(self, subreddit: str, location: Optional[str], postcode: Optional[str]) -> str:
        """Determine region from subreddit/location"""
        text = (subreddit + ' ' + (location or '') + ' ' + (postcode or '')).lower()
        
        if 'london' in text or (postcode and postcode[:2] in ['SW', 'SE', 'NW', 'NE', 'EC', 'WC']):
            return 'London'
        if any(x in text for x in ['manchester', 'liverpool', 'preston']):
            return 'North West'
        if any(x in text for x in ['birmingham', 'leicester', 'nottingham']):
            return 'Midlands'
        if any(x in text for x in ['leeds', 'sheffield', 'york']):
            return 'North'
        if any(x in text for x in ['glasgow', 'edinburgh', 'scotland']):
            return 'Scotland'
        if any(x in text for x in ['bristol', 'plymouth', 'exeter']):
            return 'South West'
        if any(x in text for x in ['cardiff', 'swansea', 'wales']):
            return 'Wales'
        
        return 'Unknown'
    
    def _extract_urgency(self, text: str) -> str:
        """Extract urgency level"""
        text_lower = text.lower()
        if any(word in text_lower for word in ['emergency', 'urgent', 'asap', 'help!', '!!!']):
            return 'emergency'
        if any(word in text_lower for word in ['soon', 'quickly']):
            return 'high'
        return 'normal'


# ============================================================================
# MASTER SCRAPER
# ============================================================================

class UKWideScraper:
    """UK-wide market research scraper"""
    
    def __init__(self):
        self.gumtree = GumtreeScraper()
        self.reddit = RedditScraper()
        self.all_jobs = []
    
    def run(self):
        """Run all scrapers and save to file"""
        
        log.info("=" * 80)
        log.info("🇬🇧 UK-WIDE MARKET RESEARCH SCRAPER")
        log.info("=" * 80)
        
        # Scrape Gumtree
        gumtree_jobs = self.gumtree.scrape(max_pages=5)
        log.info(f"✅ Gumtree: {len(gumtree_jobs)} jobs")
        
        # Scrape Reddit
        reddit_jobs = self.reddit.scrape(days_back=2)
        log.info(f"✅ Reddit: {len(reddit_jobs)} jobs")
        
        # Combine
        self.all_jobs = gumtree_jobs + reddit_jobs
        
        # Save to file
        self._save_to_file()
        
        # Print summary
        self._print_summary()
        
        log.info("=" * 80)
        log.info(f"🎉 SCRAPING COMPLETE!")
        log.info(f"📁 Results saved to: {OUTPUT_FILE}")
        log.info("=" * 80)
    
    def _save_to_file(self):
        """Save results to JSON file"""
        
        output_data = {
            'scraped_at': datetime.now().isoformat(),
            'total_jobs': len(self.all_jobs),
            'sources': {
                'gumtree': len([j for j in self.all_jobs if j['source'] == 'gumtree']),
                'reddit': len([j for j in self.all_jobs if j['source'] == 'reddit'])
            },
            'jobs': self.all_jobs
        }
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        log.info(f"💾 Saved {len(self.all_jobs)} jobs to {OUTPUT_FILE}")
    
    def _print_summary(self):
        """Print quick summary"""
        
        # Regional breakdown
        regions = {}
        for job in self.all_jobs:
            region = job.get('region', 'Unknown')
            regions[region] = regions.get(region, 0) + 1
        
        log.info("")
        log.info("📊 GEOGRAPHIC BREAKDOWN:")
        for region, count in sorted(regions.items(), key=lambda x: x[1], reverse=True):
            log.info(f"   {region}: {count} jobs")
        
        # Urgency breakdown
        urgencies = {}
        for job in self.all_jobs:
            urgency = job.get('urgency', 'normal')
            urgencies[urgency] = urgencies.get(urgency, 0) + 1
        
        log.info("")
        log.info("⚡ URGENCY BREAKDOWN:")
        for urgency, count in urgencies.items():
            log.info(f"   {urgency}: {count} jobs")
        
        # Postcode coverage
        with_postcode = len([j for j in self.all_jobs if j.get('postcode')])
        log.info("")
        log.info(f"📮 POSTCODE DATA: {with_postcode}/{len(self.all_jobs)} ({int(with_postcode/len(self.all_jobs)*100)}% have postcodes)")


if __name__ == '__main__':
    scraper = UKWideScraper()
    scraper.run()
