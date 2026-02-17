"""
PLUMBFLOW - PLUMBER SCRAPER v2
Robust regex-based extraction across 5 UK directories.
"""

import os, re, sys, time, json, random, hashlib, logging, argparse
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', handlers=[logging.StreamHandler()])
log = logging.getLogger(__name__)

DELAY_MIN, DELAY_MAX = 2.5, 5.0
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
]

POSTCODE_AREAS = {
    'Central': ['EC1','EC2','EC3','EC4','WC1','WC2'],
    'North': ['N1','N4','N5','N7','N8','N10','N12','N15','N16','N17','N19'],
    'East': ['E1','E2','E3','E5','E6','E7','E8','E9','E10','E11','E13','E14','E15','E16','E17'],
    'SE': ['SE1','SE4','SE5','SE6','SE8','SE9','SE13','SE14','SE15','SE16','SE18','SE19'],
    'SW': ['SW1','SW2','SW4','SW6','SW8','SW9','SW11','SW12','SW15','SW16','SW17','SW18','SW19'],
    'West': ['W1','W2','W3','W4','W5','W6','W9','W10','W11','W12','W13','W14'],
    'NW': ['NW1','NW2','NW3','NW4','NW5','NW6','NW8','NW10'],
    'Outer': ['BR1','BR3','CR0','CR4','CR7','DA1','DA7','EN1','EN3','HA1','HA3','HA5','IG1','IG3','KT1','KT2','KT3','RM1','RM3','RM7','SM1','SM3','TW1','TW3','TW9','UB1','UB4'],
    'Surrey': ['GU1','GU2','GU4','KT10','KT12','KT17','RH1','RH2'],
    'Kent': ['BR5','BR6','DA5','DA14','ME1','ME4','ME7','TN1','TN9','TN13'],
    'Essex': ['CM1','CM2','IG8','IG11','RM10','SS1','SS4','SS7'],
    'Herts': ['AL1','AL3','AL5','EN4','EN5','SG1','SG4','WD1','WD3','WD6','WD23'],
}
ALL_POSTCODES = [pc for pcs in POSTCODE_AREAS.values() for pc in pcs]

# Global status dict - read by main.py API
_scraper_stats = {
    'running': False, 'started_at': None, 'completed_at': None,
    'current_postcode': '', 'postcodes_done': 0, 'postcodes_total': 0,
    'total_saved': 0, 'by_source': {}, 'error': None,
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

def pc_area(pc):
    m = re.match(r'^([A-Z]{1,2}[0-9]{1,2}[A-Z]?)', (pc or '').upper())
    return m.group(1) if m else ''

def make_id(name, pc):
    return hashlib.sha256(f"{name.lower()}{pc.lower()}".encode()).hexdigest()[:16]

def extract_phones(text):
    t = re.sub(r'[.\-]',' ',text)
    found = []
    for pat in [r'\b(07\d{3}\s?\d{6})\b', r'\b(0[1-9]\d\s?\d{4}\s?\d{4})\b', r'\b(0[1-9]\d{2}\s?\d{3}\s?\d{4})\b']:
        for m in re.finditer(pat, t):
            p = clean_phone(m.group(1))
            if p and p not in found: found.append(p)
    return found

def extract_emails(text):
    return list(set(re.findall(r'[\w\.\-\+]+@[\w\.\-]+\.[a-z]{2,6}', text.lower())))

def extract_pc(text):
    m = re.search(r'\b([A-Z]{1,2}[0-9]{1,2}[A-Z]?\s?[0-9][A-Z]{2})\b', text.upper())
    return clean_postcode(m.group(1)) if m else None

def polite(): time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

def new_session():
    s = requests.Session()
    s.headers.update({'User-Agent': random.choice(USER_AGENTS), 'Accept-Language':'en-GB,en;q=0.9'})
    return s

def safe_get(session, url, params=None, retries=3):
    for i in range(retries):
        try:
            r = session.get(url, params=params, timeout=20)
            if r.status_code == 200: return r
            if r.status_code == 429: time.sleep(30*(i+1))
            elif r.status_code in [403,404,503]: return None
            else: time.sleep(5*(i+1))
        except Exception as e:
            log.warning(f"GET error ({i+1}): {e}")
            time.sleep(5)
    return None

def build_record(name, phone, email, pc, address, source, gas_safe=False, quals=None):
    if not name or len(name.strip())<3: return None
    if not phone and not email: return None
    return {
        'id': make_id(name, pc or ''),
        'name': name.strip(), 'trading_name': name.strip(),
        'phone': phone, 'email': email,
        'address': (address or '')[:300], 'postcode': pc or '',
        'postcode_area': pc_area(pc or ''), 'source': source,
        'qualifications': quals or [], 'gas_safe': gas_safe,
        'scraped_at': datetime.now().isoformat(),
        'can_receive_jobs': False, 'status': 'scraped',
    }

def parse_containers(soup, postcode, source, quals=None, gas_safe=False):
    """Extract plumbers from BeautifulSoup using multiple selector strategies"""
    results = []
    selectors = [
        '[class*="businessCapsule"]', '[class*="business-result"]',
        '[class*="listing"]', '[class*="result"]', '[class*="member"]',
        '[class*="contractor"]', '[class*="engineer"]',
        '[itemtype*="LocalBusiness"]', 'article', 'li'
    ]
    containers = []
    for sel in selectors:
        containers = soup.select(sel)
        if containers and len(containers) < 200:  # avoid generic li tags with 1000s of items
            break

    if not containers:
        # Full page fallback
        text = soup.get_text(' ')
        phones = extract_phones(text)
        for phone in phones[:30]:
            idx = text.find(phone)
            if idx < 0: continue
            surrounding = text[max(0,idx-200):idx+50]
            lines = [l.strip() for l in surrounding.split('\n') if l.strip() and len(l.strip())>3]
            name = ''
            for line in reversed(lines[-5:]):
                if 2<=len(line.split())<=8 and not re.match(r'^[\d\s\+\(\)]+$',line):
                    name=line; break
            if name:
                rec = build_record(name, phone, None, extract_pc(surrounding) or postcode, surrounding[:200], source, gas_safe, quals)
                if rec: results.append(rec)
        return results

    for container in containers:
        text = container.get_text(' ', strip=True)
        if len(text) < 20: continue
        phones = extract_phones(text)
        emails = extract_emails(text)
        if not phones and not emails: continue
        name_el = container.find(['h2','h3','h4','strong','b'])
        name = name_el.get_text(strip=True) if name_el else ''
        if not name:
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            name = lines[0][:60] if lines else ''
        pc = extract_pc(text) or postcode
        rec = build_record(name, phones[0] if phones else None, emails[0] if emails else None, pc, text[:200], source, gas_safe, quals)
        if rec: results.append(rec)

    return results


class DatabaseHandler:
    def __init__(self):
        self.db_url = os.getenv('DATABASE_URL')
        self.conn = None
        self._saved = 0
        self._total = 0
        self.fallback = {}

        if self.db_url:
            try:
                self.conn = psycopg2.connect(self.db_url, connect_timeout=10)
                self._ensure_table()
                self._total = self._count()
                log.info(f"DB connected. Existing records: {self._total}")
            except Exception as e:
                log.error(f"DB connect failed: {e}")
                self.conn = None
        else:
            log.warning("No DATABASE_URL - using in-memory fallback")

    def _ensure_table(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scraped_plumbers (
                    id VARCHAR(16) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    trading_name VARCHAR(255),
                    phone VARCHAR(20),
                    email VARCHAR(255),
                    address TEXT,
                    postcode VARCHAR(10),
                    postcode_area VARCHAR(8),
                    source VARCHAR(50),
                    qualifications JSONB DEFAULT '[]',
                    gas_safe BOOLEAN DEFAULT FALSE,
                    scraped_at TIMESTAMP,
                    can_receive_jobs BOOLEAN DEFAULT FALSE,
                    status VARCHAR(50) DEFAULT 'scraped',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sp_pc ON scraped_plumbers(postcode_area)")
            self.conn.commit()

    def save(self, rec):
        if not rec or not rec.get('id'): return False
        if self.conn:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO scraped_plumbers
                        (id,name,trading_name,phone,email,address,postcode,postcode_area,source,qualifications,gas_safe,scraped_at,can_receive_jobs,status)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(id) DO NOTHING
                    """, (rec['id'],rec['name'],rec.get('trading_name'),rec.get('phone'),rec.get('email'),
                          rec.get('address'),rec.get('postcode'),rec.get('postcode_area'),rec.get('source'),
                          json.dumps(rec.get('qualifications',[])),rec.get('gas_safe',False),
                          rec.get('scraped_at'),False,'scraped'))
                    inserted = cur.rowcount > 0
                    self.conn.commit()
                    if inserted: self._saved+=1; self._total+=1
                    return inserted
            except Exception as e:
                try: self.conn.rollback()
                except: pass
                log.debug(f"DB save err: {e}")
                return False
        else:
            if rec['id'] in self.fallback: return False
            self.fallback[rec['id']] = rec
            self._saved+=1; self._total+=1
            return True

    def _count(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM scraped_plumbers")
                return cur.fetchone()[0]
        except: return 0

    def count(self): return self._count() if self.conn else len(self.fallback)
    def saved_this_run(self): return self._saved

    def count_by_source(self):
        if self.conn:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT source,COUNT(*) FROM scraped_plumbers GROUP BY source ORDER BY COUNT(*) DESC")
                    return {r[0]:r[1] for r in cur.fetchall()}
            except: return {}
        counts={}
        for p in self.fallback.values():
            s=p.get('source','?'); counts[s]=counts.get(s,0)+1
        return counts

    def close(self):
        if self.conn:
            try: self.conn.close()
            except: pass


class PlumberScraper:
    SOURCE_MAP = ['yell','watersafe','ciphe','aphc','gas_safe']

    def __init__(self):
        self.db = DatabaseHandler()
        self.stats = {'total_saved':0, 'by_source':{}}

    def run(self, sources=None, postcodes=None, limit_postcodes=None):
        global _scraper_stats
        sources = sources or self.SOURCE_MAP
        postcodes = postcodes or ALL_POSTCODES
        if limit_postcodes: postcodes = postcodes[:limit_postcodes]

        _scraper_stats.update({'running':True,'postcodes_total':len(postcodes),'postcodes_done':0,'error':None,'started_at':datetime.now().isoformat(),'stop_requested':False})
        log.info(f"Starting scraper | Sources: {sources} | Postcodes: {len(postcodes)}")

        for i, postcode in enumerate(postcodes, 1):
            _scraper_stats['current_postcode'] = postcode
            _scraper_stats['postcodes_done'] = i
            log.info(f"[{i}/{len(postcodes)}] {postcode}")

            # Check if stop was requested
            if _scraper_stats.get('stop_requested'):
                log.info("🛑 Stop requested — halting scraper.")
                break

            for source in sources:
                try:
                    saved = self._scrape_source(source, postcode)
                    self.stats['total_saved'] += saved
                    self.stats['by_source'][source] = self.stats['by_source'].get(source,0)+saved
                    _scraper_stats['total_saved'] = self.db.saved_this_run()
                    _scraper_stats['by_source'] = dict(self.stats['by_source'])
                except Exception as e:
                    log.error(f"Error {source}/{postcode}: {e}")

            if i%5==0:
                log.info(f"Progress {i}/{len(postcodes)} | DB: {self.db.count()} | This run: {self.db.saved_this_run()}")

        self.db.close()
        _scraper_stats.update({'running':False,'completed_at':datetime.now().isoformat(),'total_saved':self.db.saved_this_run()})
        log.info(f"DONE. Saved: {self.db.saved_this_run()} | By source: {self.stats['by_source']}")

    def _scrape_source(self, source, postcode):
        session = new_session()
        if source == 'yell':       return self._yell(session, postcode)
        if source == 'watersafe':  return self._registry(session, postcode, 'https://www.watersafe.org.uk/find-an-approved-contractor/', 'watersafe', ['WaterSafe Approved'])
        if source == 'ciphe':      return self._registry(session, postcode, 'https://www.ciphe.org.uk/find-a-plumber/', 'ciphe', ['CIPHE Member'])
        if source == 'aphc':       return self._registry(session, postcode, 'https://aphc.co.uk/find-a-member/', 'aphc', ['APHC Member'])
        if source == 'gas_safe':   return self._gassafe(session, postcode)
        return 0

    def _yell(self, session, postcode, max_pages=5):
        saved = 0
        for page in range(1, max_pages+1):
            resp = safe_get(session, 'https://www.yell.com/ucs/UcsSearchAction.do',
                           {'keywords':'plumbers','location':postcode,'pageNum':page})
            if not resp: break
            soup = BeautifulSoup(resp.text, 'lxml')
            for tag in soup(['script','style']): tag.decompose()
            records = parse_containers(soup, postcode, 'yell')
            if not records: break
            for r in records:
                if self.db.save(r): saved+=1
            polite()
        log.info(f"  [Yell] {postcode}: {saved} saved")
        return saved

    def _registry(self, session, postcode, url, source, quals):
        saved = 0
        # Try GET then POST
        resp = safe_get(session, url, {'postcode':postcode,'location':postcode,'radius':'10'})
        if not resp:
            try:
                resp = session.post(url, data={'postcode':postcode,'radius':'10','search':'Search'}, timeout=20)
                if resp.status_code != 200: resp = None
            except: resp = None
        if not resp: return 0

        soup = BeautifulSoup(resp.text, 'lxml')
        for tag in soup(['script','style']): tag.decompose()
        records = parse_containers(soup, postcode, source, quals)
        for r in records:
            if self.db.save(r): saved+=1
        polite()
        log.info(f"  [{source}] {postcode}: {saved} saved")
        return saved

    def _gassafe(self, session, postcode):
        saved = 0
        resp = safe_get(session, 'https://www.gassaferegister.co.uk/find-an-engineer/',
                       {'postcode':postcode,'distance':'10'})
        if not resp: return 0
        soup = BeautifulSoup(resp.text, 'lxml')
        for tag in soup(['script','style']): tag.decompose()
        records = parse_containers(soup, postcode, 'gas_safe', ['Gas Safe Registered'], gas_safe=True)
        for r in records:
            if self.db.save(r): saved+=1
        time.sleep(random.uniform(5,9))
        log.info(f"  [gas_safe] {postcode}: {saved} saved")
        return saved


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=PlumberScraper.SOURCE_MAP)
    parser.add_argument('--postcode')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--test', action='store_true')
    args = parser.parse_args()

    scraper = PlumberScraper()
    if args.test:
        scraper.run(sources=['yell'], postcodes=['SW19','SE1','N1'])
    elif args.postcode:
        scraper.run(sources=[args.source] if args.source else None, postcodes=[args.postcode.upper()])
    else:
        scraper.run(sources=[args.source] if args.source else None, limit_postcodes=args.limit)


# ============================================================================
# COMPANIES HOUSE API SOURCE
# ============================================================================

class CompaniesHouseScraper:
    """
    Companies House API - official UK government company registry.
    FREE, reliable JSON API, no bot blocking.
    
    Finds all registered plumbing/heating companies in England.
    Returns: company name, registered address, company number, status.
    
    API Key: Get free at https://developer.company-information.service.gov.uk/
    Set env var: COMPANIES_HOUSE_API_KEY
    """
    
    BASE_URL = "https://api.company-information.service.gov.uk"
    
    SEARCH_TERMS = [
        'plumbing', 'plumber', 'plumbers', 
        'heating engineer', 'gas engineer',
        'boiler installation', 'central heating',
    ]
    
    def __init__(self, db: DatabaseHandler):
        self.db = db
        self.api_key = os.getenv('COMPANIES_HOUSE_API_KEY', '')
        if not self.api_key:
            log.warning("No COMPANIES_HOUSE_API_KEY set - skipping Companies House source")
    
    def scrape(self, postcode: str) -> int:
        if not self.api_key:
            return 0
        
        saved = 0
        session = requests.Session()
        session.auth = (self.api_key, '')
        
        for term in self.SEARCH_TERMS[:3]:  # 3 terms per postcode
            results = self._search(session, term, postcode)
            for company in results:
                rec = self._to_record(company, postcode)
                if rec and self.db.save(rec):
                    saved += 1
            time.sleep(0.5)  # CH rate limit: 600 req/5min
        
        log.info(f"  [CompaniesHouse] {postcode}: {saved} saved")
        return saved
    
    def _search(self, session, term: str, postcode: str) -> list:
        try:
            # Search by company name + filter active companies
            r = session.get(
                f"{self.BASE_URL}/search/companies",
                params={
                    'q': f"{term} {postcode.split()[0]}",
                    'items_per_page': 20,
                },
                timeout=10
            )
            if r.status_code != 200:
                return []
            data = r.json()
            return [
                c for c in data.get('items', [])
                if c.get('company_status') == 'active'
            ]
        except Exception as e:
            log.debug(f"CH search error: {e}")
            return []
    
    def _to_record(self, company: dict, search_postcode: str) -> Optional[dict]:
        name = company.get('title', '')
        if not name:
            return None
        
        addr = company.get('address', {})
        address_parts = [
            addr.get('address_line_1', ''),
            addr.get('address_line_2', ''),
            addr.get('locality', ''),
            addr.get('postal_code', ''),
        ]
        address = ', '.join(p for p in address_parts if p)
        pc = clean_postcode(addr.get('postal_code', '')) or search_postcode
        
        # Companies House doesn't provide phone/email directly
        # But name + address is enough to enrich later
        # Use company number as a pseudo-phone for dedup purposes
        company_number = company.get('company_number', '')
        
        return {
            'id': make_id(name, pc),
            'name': name,
            'trading_name': name,
            'phone': None,
            'email': None,
            'address': address,
            'postcode': pc,
            'postcode_area': pc_area(pc),
            'source': 'companies_house',
            'qualifications': ['Registered Company'],
            'gas_safe': False,
            'company_number': company_number,
            'scraped_at': datetime.now().isoformat(),
            'can_receive_jobs': False,
            'status': 'scraped',
        }
