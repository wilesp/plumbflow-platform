"""
PLUMBERFLOW - YELL.COM SCRAPER
Simple HTTP scraper for Yell business directory - no JavaScript needed.
"""

import os, re, time, json, random, hashlib, logging
from datetime import datetime
from typing import List, Dict, Optional

try:
    import requests
    from bs4 import BeautifulSoup
    import psycopg2
except ImportError:
    os.system("pip install requests beautifulsoup4 psycopg2-binary lxml --break-system-packages -q")
    import requests
    from bs4 import BeautifulSoup
    import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# UK Postcodes - London & South East (curated list)
POSTCODES = [
    # Central/Inner London
    'EC1','EC2','WC1','N1','N4','N7','N16','E1','E2','E8','E9','E14','E17',
    'SE1','SE5','SE8','SE15','SE16','SW1','SW4','SW8','SW9','SW11','SW15','SW18','SW19',
    'W1','W2','W6','W10','W12','NW1','NW3','NW5','NW6','NW8',
    # Outer London
    'BR1','CR0','DA1','EN1','HA1','IG1','KT1','KT2','RM1','SM1','TW1','UB1',
    # Home Counties  
    'GU1','GU2','KT10','RH1','ME1','TN1','CM1','SS1','AL1','SG1','WD1',
]

# Global status dict - read by main.py API
_scraper_stats = {
    'running': False, 'started_at': None, 'completed_at': None,
    'current_postcode': '', 'postcodes_done': 0, 'postcodes_total': 0,
    'total_saved': 0, 'by_source': {}, 'error': None, 'stop_requested': False,
}

def clean_phone(raw):
    if not raw: return None
    d = re.sub(r'[^\d]', '', str(raw))
    if d.startswith('44') and len(d)==12: d='0'+d[2:]
    if len(d)==11 and d.startswith('0'): return d
    if len(d)==10 and d.startswith('7'): return '0'+d
    return None

def clean_postcode(raw):
    if not raw: return None
    pc = re.sub(r'[^A-Z0-9]','',str(raw).upper())
    return pc if 5<=len(pc)<=7 else None

def make_id(name, pc):
    return hashlib.sha256(f"{name.lower()}{pc.lower()}".encode()).hexdigest()[:16]

def extract_phones(text):
    found = []
    for pat in [r'\b(07\d{9})\b', r'\b(0[1-9]\d{9})\b', r'\b(0[1-9]\d\s?\d{4}\s?\d{4})\b']:
        for m in re.finditer(pat, text.replace('-','').replace('(','').replace(')','')):
            p = clean_phone(m.group(1))
            if p and p not in found: found.append(p)
    return found

def extract_postcode(text):
    m = re.search(r'\b([A-Z]{1,2}[0-9]{1,2}[A-Z]?\s?[0-9][A-Z]{2})\b', text.upper())
    return clean_postcode(m.group(1)) if m else None


class DatabaseHandler:
    def __init__(self):
        self.db_url = os.getenv('DATABASE_URL')
        self.conn = None
        self._saved = 0
        self._total = 0

        if self.db_url:
            try:
                self.conn = psycopg2.connect(self.db_url, connect_timeout=10)
                self._ensure_table()
                self._total = self._count()
                log.info(f"✅ DB connected. Existing: {self._total} records")
            except Exception as e:
                log.error(f"❌ DB error: {e}")
                self.conn = None
        else:
            log.warning("No DATABASE_URL - scraper will not save data")

    def _ensure_table(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scraped_plumbers (
                    id VARCHAR(16) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    phone VARCHAR(20),
                    email VARCHAR(255),
                    address TEXT,
                    postcode VARCHAR(10),
                    postcode_area VARCHAR(8),
                    source VARCHAR(50),
                    scraped_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sp_pc ON scraped_plumbers(postcode_area)")
            self.conn.commit()

    def save(self, name, phone, postcode, address=''):
        if not self.conn or not name or not phone: 
            return False
        
        rec_id = make_id(name, postcode or '')
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO scraped_plumbers (id,name,phone,postcode,postcode_area,address,source,scraped_at)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(id) DO NOTHING
                """, (rec_id, name[:255], phone, postcode, postcode[:4] if postcode else '',
                      address[:300], 'yell', datetime.now()))
                inserted = cur.rowcount > 0
                self.conn.commit()
                if inserted: 
                    self._saved += 1
                    self._total += 1
                return inserted
        except Exception as e:
            try: self.conn.rollback()
            except: pass
            log.debug(f"Save error: {e}")
            return False

    def _count(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM scraped_plumbers")
                return cur.fetchone()[0]
        except: return 0

    def count(self): return self._total
    def saved_this_run(self): return self._saved
    
    def count_by_source(self):
        if not self.conn: return {}
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT source,COUNT(*) FROM scraped_plumbers GROUP BY source")
                return {r[0]:r[1] for r in cur.fetchall()}
        except: return {}

    def close(self):
        if self.conn:
            try: self.conn.close()
            except: pass


class YellScraper:
    """Scrapes Yell.com with multiple fallback strategies"""
    
    def __init__(self, db: DatabaseHandler):
        self.db = db
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-GB,en;q=0.9',
        })
    
    def scrape_postcode(self, postcode: str, max_pages: int = 3) -> int:
        """Scrape Yell for plumbers in postcode"""
        saved = 0
        log.info(f"[Yell] {postcode}")
        
        for page in range(1, max_pages + 1):
            try:
                count = self._scrape_page(postcode, page)
                saved += count
                if count == 0:  # No results, don't try more pages
                    break
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                log.error(f"[Yell] {postcode} pg{page} error: {e}")
                break
        
        log.info(f"[Yell] {postcode}: saved {saved} new")
        return saved
    
    def _scrape_page(self, postcode: str, page: int) -> int:
        """Scrape one page with fallback strategies"""
        url = 'https://www.yell.com/ucs/UcsSearchAction.do'
        params = {'keywords': 'plumbers', 'location': postcode, 'pageNum': page}
        
        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                log.warning(f"HTTP {resp.status_code}")
                return 0
            
            soup = BeautifulSoup(resp.text, 'lxml')
            
            # Strategy 1: Try known Yell selectors
            selectors = [
                '[class*="businessCapsule"]',
                '[data-ys-businessid]',
                '[itemtype*="LocalBusiness"]',
                'article.listing',
                'div.listing',
            ]
            
            for sel in selectors:
                items = soup.select(sel)
                if items and len(items) < 100:  # Sanity check
                    log.debug(f"  Using selector: {sel} ({len(items)} items)")
                    saved = sum(1 for item in items if self._extract_from_container(item, postcode))
                    if saved > 0:
                        return saved
            
            # Strategy 2: Find any article tags
            articles = soup.find_all('article')
            if articles and len(articles) < 50:
                log.debug(f"  Trying {len(articles)} article tags")
                saved = sum(1 for art in articles if self._extract_from_container(art, postcode))
                if saved > 0:
                    return saved
            
            # Strategy 3: Phone number scan fallback
            log.debug(f"  Fallback: scanning for phones in page text")
            text = soup.get_text(' ')
            phones = extract_phones(text)
            
            if not phones:
                log.warning(f"  No phones found on page")
                return 0
            
            log.debug(f"  Found {len(phones)} phones, extracting names...")
            saved = 0
            for phone in phones[:15]:  # Cap at 15 per page
                # Find surrounding text
                idx = text.find(phone)
                if idx < 0: continue
                
                chunk = text[max(0, idx-250):idx+50]
                lines = [l.strip() for l in chunk.split('\n') if l.strip() and len(l.strip())>2]
                
                # Find business name in preceding lines
                name = ''
                for line in reversed(lines[-6:]):
                    # Business name heuristic: 2-8 words, not just numbers
                    words = line.split()
                    if 2 <= len(words) <= 8 and not re.match(r'^[\d\s\+\(\)\-]+$', line):
                        name = line
                        break
                
                if name and len(name) >= 5:
                    pc = extract_postcode(chunk) or postcode
                    if self.db.save(name, phone, pc, chunk[:250]):
                        saved += 1
            
            return saved
            
        except Exception as e:
            log.error(f"Scrape error: {e}")
            return 0
    
    def _extract_from_container(self, item, search_postcode: str) -> bool:
        """Extract from a structured container (article/div)"""
        try:
            text = item.get_text(' ', strip=True)
            if len(text) < 20:
                return False
            
            # Name from heading
            name_el = item.find(['h2', 'h3', 'h4', 'a'])
            if not name_el:
                return False
            name = name_el.get_text(strip=True)
            if len(name) < 3:
                return False
            
            # Phone
            phones = extract_phones(text)
            if not phones:
                return False
            
            # Postcode
            postcode = extract_postcode(text) or search_postcode
            
            # Save
            return self.db.save(name, phones[0], postcode, text[:300])
            
        except Exception:
            return False


class PlumberScraper:
    """Main orchestrator - runs Yell scraper across all postcodes"""
    
    def __init__(self):
        self.db = DatabaseHandler()
        self.yell = YellScraper(self.db)
    
    def run(self, postcodes: List[str] = None, limit: int = None):
        global _scraper_stats
        
        postcodes = postcodes or POSTCODES
        if limit: postcodes = postcodes[:limit]
        
        _scraper_stats.update({
            'running': True, 'postcodes_total': len(postcodes), 'postcodes_done': 0,
            'started_at': datetime.now().isoformat(), 'stop_requested': False, 'error': None,
        })
        
        log.info(f"🚀 Yell Scraper Starting | Postcodes: {len(postcodes)} | DB: {self.db.count()}")
        
        for i, postcode in enumerate(postcodes, 1):
            if _scraper_stats.get('stop_requested'):
                log.info("🛑 Stop requested")
                break
            
            _scraper_stats['current_postcode'] = postcode
            _scraper_stats['postcodes_done'] = i
            
            try:
                saved = self.yell.scrape_postcode(postcode)
                _scraper_stats['total_saved'] = self.db.saved_this_run()
                _scraper_stats['by_source'] = {'yell': self.db.saved_this_run()}
            except Exception as e:
                log.error(f"{postcode} error: {e}")
            
            if i % 10 == 0:
                log.info(f"📊 Progress: {i}/{len(postcodes)} | DB total: {self.db.count()} | This run: {self.db.saved_this_run()}")
        
        self.db.close()
        _scraper_stats.update({
            'running': False, 
            'completed_at': datetime.now().isoformat(),
            'total_saved': self.db.saved_this_run(),
        })
        log.info(f"✅ DONE | New: {self.db.saved_this_run()} | Total DB: {self.db.count()}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--postcode', help='Single postcode test')
    parser.add_argument('--limit', type=int, help='Limit postcodes')
    parser.add_argument('--test', action='store_true', help='Quick test: 3 postcodes')
    args = parser.parse_args()
    
    scraper = PlumberScraper()
    if args.test:
        scraper.run(postcodes=['SW19', 'SE1', 'W1'])
    elif args.postcode:
        scraper.run(postcodes=[args.postcode.upper()])
    else:
        scraper.run(limit=args.limit)
