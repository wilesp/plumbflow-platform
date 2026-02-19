"""
PLUMBERFLOW - COMPLETE HOME COUNTIES SCRAPER v2.1
Google Maps API + Manual Yell Import
All 222 postcodes: London + Herts + Beds + Bucks + Essex + Kent + Oxon + Northants
Cost: ~£35-40 | Results: ~2,220 plumbers
"""

import os, re, time, json, random, hashlib, logging, csv
from datetime import datetime
from typing import List, Dict, Optional
from io import StringIO

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

# SAFETY LIMITS
MAX_POSTCODES_PER_RUN = 250  # Increased for complete regional coverage
COST_PER_POSTCODE = 0.20     # Estimated cost per postcode
MAX_COST_PER_RUN = 50.00     # £50 max per run (allows full regional coverage)

# COMPLETE HOME COUNTIES COVERAGE - 112 Postcodes
# London + Hertfordshire + Bedfordshire + Buckinghamshire + Essex + Kent + Oxfordshire + Northamptonshire
POSTCODES = [
    # ===== LONDON (48 postcodes) =====
    # Central/Inner London
    'EC1','EC2','WC1','WC2',
    'N1','N4','N5','N7','N8','N16','N19',
    'E1','E2','E3','E5','E8','E9','E10','E14','E15','E17',
    'SE1','SE5','SE8','SE10','SE13','SE15','SE16','SE18',
    'SW1','SW3','SW4','SW6','SW8','SW9','SW11','SW12','SW15','SW17','SW18','SW19',
    'W1','W2','W3','W4','W6','W8','W10','W11','W12','W14',
    'NW1','NW3','NW5','NW6','NW8','NW10',
    
    # Outer London
    'BR1','BR2','CR0','DA1','DA14','DA15','DA16',
    'EN1','EN2','EN3','EN4','EN5',
    'HA0','HA1','HA2','HA3','HA4','HA5','HA8','HA9',
    'IG1','IG2','IG3','IG6','IG8',
    'KT1','KT2','KT3','KT4','KT5','KT6',
    'RM1','RM3','RM6','RM8','RM9','RM10',
    'SM1','SM2','SM3','SM4','SM5','SM6',
    'TW1','TW2','TW3','TW4','TW5','TW7','TW8','TW9','TW10',
    'UB1','UB2','UB3','UB4','UB5','UB6','UB7','UB8','UB10',
    
    # ===== HERTFORDSHIRE (22 postcodes) =====
    'AL1','AL2','AL3','AL4','AL5','AL7','AL8','AL9','AL10',  # St Albans, Hatfield, Welwyn
    'SG1','SG2','SG4','SG5','SG6',                            # Stevenage, Hitchin, Letchworth
    'WD3','WD4','WD5','WD6','WD17','WD18','WD19','WD23',     # Watford, Rickmansworth
    
    # ===== BEDFORDSHIRE (10 postcodes) =====
    'LU1','LU2','LU3','LU4','LU5','LU6','LU7',  # Luton, Dunstable
    'MK40','MK41','MK42',                        # Bedford
    
    # ===== BUCKINGHAMSHIRE (14 postcodes) =====
    'HP1','HP2','HP3','HP5','HP6','HP7','HP8','HP9','HP10',  # High Wycombe, Amersham, Chesham
    'MK3','MK4','MK5','MK6','MK7',                            # Milton Keynes
    
    # ===== ESSEX (18 postcodes) =====
    'CM1','CM2','CM3','CM11','CM12','CM13','CM14','CM15',  # Chelmsford, Brentwood, Basildon
    'CO1','CO2','CO3','CO4',                                # Colchester
    'RM14','RM15','RM16',                                   # Essex Thames
    'SS0','SS1','SS2',                                      # Southend
    
    # ===== KENT (20 postcodes) =====
    'ME1','ME2','ME3','ME4','ME5','ME7','ME8',              # Medway, Rochester
    'ME14','ME15','ME16','ME17',                            # Maidstone
    'TN1','TN2','TN4','TN9','TN13','TN14','TN15',          # Tunbridge Wells, Sevenoaks
    'DA9','DA10',                                           # Dartford
    
    # ===== OXFORDSHIRE (10 postcodes) =====
    'OX1','OX2','OX3','OX4','OX5',      # Oxford
    'OX16','OX17',                       # Banbury
    'OX26','OX27','OX28',               # Bicester, Witney
    
    # ===== NORTHAMPTONSHIRE (10 postcodes) =====
    'NN1','NN2','NN3','NN4','NN5',      # Northampton
    'NN6','NN7','NN8','NN9','NN10',     # Wellingborough, Kettering
]

# Global status dict
_scraper_stats = {
    'running': False, 'started_at': None, 'completed_at': None,
    'current_source': '', 'current_postcode': '', 
    'postcodes_done': 0, 'postcodes_total': 0,
    'total_saved': 0, 'by_source': {}, 'error': None, 'stop_requested': False,
    'estimated_cost': 0, 'actual_api_calls': 0,
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

def extract_postcode(text):
    if not text: return None
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
                    website TEXT,
                    source VARCHAR(50) NOT NULL,
                    gas_safe BOOLEAN DEFAULT false,
                    rating DECIMAL(3,2),
                    reviews_count INTEGER,
                    status VARCHAR(20) DEFAULT 'active',
                    notes TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()

    def _count(self):
        if not self.conn: return 0
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM scraped_plumbers")
            return cur.fetchone()[0]

    def count_by_source(self):
        if not self.conn: return {}
        with self.conn.cursor() as cur:
            cur.execute("SELECT source, COUNT(*) FROM scraped_plumbers GROUP BY source")
            return {row[0]: row[1] for row in cur.fetchall()}

    def save(self, name, phone, postcode, source, notes='', website='', email='', address='', rating=None, reviews=None):
        if not self.conn or not name or not postcode:
            return False

        try:
            plumber_id = make_id(name, postcode)
            postcode_area = postcode[:4] if len(postcode) >= 4 else postcode

            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO scraped_plumbers 
                    (id, name, phone, email, address, postcode, postcode_area, website, source, rating, reviews_count, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (plumber_id, name, phone, email, address, postcode, postcode_area, website, source, rating, reviews, notes))
                
                if cur.rowcount > 0:
                    self.conn.commit()
                    self._saved += 1
                    return True
        except Exception as e:
            log.error(f"Save error: {e}")
            self.conn.rollback()
        
        return False

    def count(self):
        return self._count()

    def close(self):
        if self.conn:
            self.conn.close()


class GoogleMapsAPI:
    """Google Maps Places API with cost tracking"""
    
    def __init__(self, db: DatabaseHandler):
        self.db = db
        self.api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        self.api_calls = 0
        
        if not self.api_key:
            log.warning("⚠️ GOOGLE_MAPS_API_KEY not set")
    
    def scrape(self, postcodes: List[str] = None):
        """Search for plumbers near postcodes"""
        
        if not self.api_key:
            log.warning("[Google Maps] Skipped - no API key")
            return 0
        
        postcodes = postcodes or POSTCODES
        log.info(f"[Google Maps] Starting search for {len(postcodes)} locations...")
        
        saved = 0
        
        for i, postcode in enumerate(postcodes, 1):
            if _scraper_stats.get('stop_requested'):
                break
            
            _scraper_stats['current_postcode'] = postcode
            _scraper_stats['postcodes_done'] = i
            
            try:
                url = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
                params = {
                    'query': f'plumber near {postcode} UK',
                    'key': self.api_key
                }
                
                response = requests.get(url, params=params, timeout=15)
                self.api_calls += 1
                _scraper_stats['actual_api_calls'] = self.api_calls
                
                if response.status_code != 200:
                    log.warning(f"[Google Maps] HTTP {response.status_code}")
                    continue
                
                data = response.json()
                
                if data.get('status') not in ['OK', 'ZERO_RESULTS']:
                    log.warning(f"[Google Maps] {postcode}: {data.get('status')}")
                    if data.get('status') == 'REQUEST_DENIED':
                        log.error("❌ REQUEST_DENIED - Check API key")
                        break
                    continue
                
                results = data.get('results', [])
                log.info(f"[Google Maps] {postcode}: Found {len(results)} plumbers")
                
                for place in results[:10]:
                    try:
                        place_id = place.get('place_id')
                        details = self._get_place_details(place_id)
                        
                        if not details:
                            continue
                        
                        name = details.get('name', '')
                        phone = clean_phone(details.get('formatted_phone_number', ''))
                        address = details.get('formatted_address', '')
                        website = details.get('website', '')
                        rating = details.get('rating')
                        reviews_count = details.get('user_ratings_total')
                        
                        place_postcode = extract_postcode(address) or postcode
                        
                        if self.db.save(
                            name=name,
                            phone=phone,
                            postcode=place_postcode,
                            source='google_maps',
                            address=address,
                            website=website,
                            rating=rating,
                            reviews=reviews_count,
                            notes=f"Google Place ID: {place_id}"
                        ):
                            saved += 1
                            _scraper_stats['total_saved'] = saved
                    
                    except Exception as e:
                        log.debug(f"Error processing place: {e}")
                        continue
                
                time.sleep(0.5)
                
                if i % 10 == 0:
                    actual_cost = self.api_calls * 0.017
                    log.info(f"📊 Progress: {i}/{len(postcodes)} | Saved: {saved} | Cost: £{actual_cost:.2f}")
            
            except Exception as e:
                log.error(f"[Google Maps] Error for {postcode}: {e}")
                continue
        
        actual_cost = self.api_calls * 0.017
        log.info(f"✅ Complete! Saved {saved} plumbers | API calls: {self.api_calls} | Cost: £{actual_cost:.2f}")
        return saved
    
    def _get_place_details(self, place_id):
        """Get detailed place information"""
        try:
            url = 'https://maps.googleapis.com/maps/api/place/details/json'
            params = {
                'place_id': place_id,
                'fields': 'name,formatted_phone_number,formatted_address,website,rating,user_ratings_total',
                'key': self.api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            self.api_calls += 1
            _scraper_stats['actual_api_calls'] = self.api_calls
            
            if response.status_code == 200:
                data = response.json()
                return data.get('result', {})
        except Exception:
            pass
        return None


class ManualYellImporter:
    """Import plumbers from manually exported Yell CSV"""
    
    def __init__(self, db: DatabaseHandler):
        self.db = db
    
    def import_csv(self, csv_content: str):
        """Import plumbers from CSV string"""
        
        log.info("[Yell Import] Processing CSV...")
        
        reader = csv.DictReader(StringIO(csv_content))
        saved = 0
        
        for row in reader:
            try:
                name = row.get('Business Name', '').strip()
                phone = clean_phone(row.get('Phone', ''))
                postcode = clean_postcode(row.get('Postcode', ''))
                website = row.get('Website', '').strip()
                address = row.get('Address', '').strip()
                
                if not name or not postcode:
                    continue
                
                if self.db.save(
                    name=name,
                    phone=phone,
                    postcode=postcode,
                    source='yell_manual',
                    address=address,
                    website=website,
                    notes='Manually imported from Yell'
                ):
                    saved += 1
            
            except Exception as e:
                log.debug(f"Error importing row: {e}")
                continue
        
        log.info(f"[Yell Import] Imported {saved} plumbers")
        return saved


class PlumberScraper:
    """Main orchestrator with regional coverage"""
    
    def __init__(self):
        self.db = DatabaseHandler()
        self.google_maps = GoogleMapsAPI(self.db)
        self.yell_importer = ManualYellImporter(self.db)
    
    def run(self, postcodes: List[str] = None, limit: int = None):
        """
        Run Google Maps scraper
        
        Args:
            postcodes: List of postcodes or None for all 112
            limit: Limit number of postcodes
        """
        global _scraper_stats
        
        postcodes = postcodes or POSTCODES
        
        if limit and limit < len(postcodes):
            postcodes = postcodes[:limit]
        
        if len(postcodes) > MAX_POSTCODES_PER_RUN:
            log.warning(f"🚨 Capping at {MAX_POSTCODES_PER_RUN} postcodes")
            postcodes = postcodes[:MAX_POSTCODES_PER_RUN]
        
        estimated_cost = len(postcodes) * COST_PER_POSTCODE
        _scraper_stats['estimated_cost'] = estimated_cost
        
        log.info(f"💰 Estimated cost: £{estimated_cost:.2f} for {len(postcodes)} postcodes")
        
        if estimated_cost > MAX_COST_PER_RUN:
            error_msg = f"🚨 COST LIMIT: £{estimated_cost:.2f} > £{MAX_COST_PER_RUN} max"
            log.error(error_msg)
            _scraper_stats['error'] = error_msg
            raise Exception(error_msg)
        
        _scraper_stats.update({
            'running': True,
            'started_at': datetime.now().isoformat(),
            'postcodes_total': len(postcodes),
            'postcodes_done': 0,
            'stop_requested': False,
            'error': None,
            'by_source': {},
            'actual_api_calls': 0
        })
        
        log.info(f"🚀 HOME COUNTIES SCRAPER")
        log.info(f"   Region: London + Herts + Beds + Bucks + Essex + Kent + Oxon + Northants")
        log.info(f"   Postcodes: {len(postcodes)}")
        log.info(f"   Expected: ~{len(postcodes) * 10} plumbers")
        log.info(f"   Estimated cost: £{estimated_cost:.2f}")
        
        total_saved = 0
        
        try:
            _scraper_stats['current_source'] = 'Google Maps'
            saved = self.google_maps.scrape(postcodes=postcodes)
            total_saved += saved
            _scraper_stats['by_source']['google_maps'] = saved
            
            _scraper_stats['total_saved'] = total_saved
            _scraper_stats['completed_at'] = datetime.now().isoformat()
            
            actual_cost = _scraper_stats['actual_api_calls'] * 0.017
            
            log.info(f"🎉 SCRAPING COMPLETE!")
            log.info(f"   Postcodes: {len(postcodes)}")
            log.info(f"   Plumbers saved: {total_saved}")
            log.info(f"   API calls: {_scraper_stats['actual_api_calls']}")
            log.info(f"   Actual cost: £{actual_cost:.2f}")
            log.info(f"   Database total: {self.db.count()}")
        
        except Exception as e:
            log.error(f"❌ Scraper error: {e}")
            _scraper_stats['error'] = str(e)
        
        finally:
            _scraper_stats['running'] = False
    
    def import_yell_csv(self, csv_content: str):
        """Import manually exported Yell data"""
        return self.yell_importer.import_csv(csv_content)


if __name__ == '__main__':
    scraper = PlumberScraper()
    scraper.run(limit=5)  # Test with 5 postcodes
