"""
Google Maps Trade Scraper - Production Version
Scrapes tradespeople nationwide across all trade categories
Stays within Google Maps API monthly limits
"""

import os
import googlemaps
import time
import re
from datetime import datetime
from database import db

# Configuration
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# Month 1 Configuration (Update each month)
CURRENT_MONTH_TRADES = [
    'electrician',
    'gas engineer', 
    'heating engineer',
    'boiler installer'
]

CURRENT_MONTH_LOCATIONS = [
    'London, UK',
    'Birmingham, UK',
    'Manchester, UK',
    'Leeds, UK',
    'Glasgow, UK',
    'Liverpool, UK',
    'Newcastle, UK',
    'Sheffield, UK',
    'Bristol, UK',
    'Edinburgh, UK'
]

# Results per search (Google Maps typically returns 20-60)
MAX_RESULTS_PER_SEARCH = 50

def extract_postcode(address):
    """Extract UK postcode from address"""
    # UK postcode regex
    postcode_pattern = r'[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}'
    match = re.search(postcode_pattern, address, re.IGNORECASE)
    return match.group(0).upper() if match else None

def clean_phone_number(phone):
    """Clean and validate UK phone number"""
    if not phone:
        return None
    
    # Remove all non-digit characters except +
    phone = re.sub(r'[^\d+]', '', phone)
    
    # UK phone validation
    if phone.startswith('+44'):
        return phone
    elif phone.startswith('07') or phone.startswith('01') or phone.startswith('02'):
        return '+44' + phone[1:]
    
    return None

def validate_email(email):
    """Basic email validation"""
    if not email:
        return None
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return email if re.match(pattern, email) else None

def calculate_quality_score(contact):
    """
    Calculate quality score for contact (0-100)
    Higher score = better quality lead
    """
    score = 0
    
    # Phone number (30 points)
    if contact.get('phone'):
        score += 30
    
    # Website (20 points)
    if contact.get('website'):
        score += 20
    
    # Google rating (20 points)
    rating = contact.get('google_rating', 0)
    if rating >= 4.5:
        score += 20
    elif rating >= 4.0:
        score += 15
    elif rating >= 3.5:
        score += 10
    
    # Number of reviews (15 points)
    reviews = contact.get('user_ratings_total', 0)
    if reviews >= 50:
        score += 15
    elif reviews >= 20:
        score += 10
    elif reviews >= 5:
        score += 5
    
    # Address/postcode (15 points)
    if contact.get('postcode'):
        score += 15
    
    return score

def scrape_trade_location(trade, location, max_results=50):
    """
    Scrape contacts for a specific trade in a specific location
    
    Args:
        trade: Trade type (e.g., 'electrician')
        location: Location (e.g., 'London, UK')
        max_results: Maximum results to retrieve
    
    Returns:
        List of contact dictionaries
    """
    query = f"{trade} in {location}"
    
    print(f"  Searching: {query}")
    
    try:
        # Google Places Text Search
        places_result = gmaps.places(query=query)
        
        contacts = []
        results = places_result.get('results', [])
        
        print(f"  Found {len(results)} results")
        
        for idx, place in enumerate(results[:max_results]):
            # Get place details with additional fields
            place_id = place.get('place_id')
            
            try:
                details = gmaps.place(
                    place_id=place_id,
                    fields=[
                        'name',
                        'formatted_phone_number',
                        'international_phone_number',
                        'formatted_address',
                        'website',
                        'rating',
                        'user_ratings_total',
                        'business_status',
                        'opening_hours'
                    ]
                )
                
                place_details = details.get('result', {})
                
                # Extract and clean data
                phone = clean_phone_number(
                    place_details.get('formatted_phone_number') or 
                    place_details.get('international_phone_number')
                )
                
                address = place_details.get('formatted_address', '')
                postcode = extract_postcode(address)
                
                contact = {
                    'trading_name': place_details.get('name'),
                    'phone': phone,
                    'address': address,
                    'postcode': postcode,
                    'website': place_details.get('website'),
                    'google_rating': place_details.get('rating'),
                    'google_reviews': place_details.get('user_ratings_total', 0),
                    'business_status': place_details.get('business_status', 'OPERATIONAL'),
                    'trade_category': trade,
                    'location_searched': location,
                    'source': 'google_maps',
                    'scraped_at': datetime.utcnow()
                }
                
                # Calculate quality score
                contact['quality_score'] = calculate_quality_score(contact)
                
                contacts.append(contact)
                
                # Rate limiting between detail requests
                time.sleep(0.2)
                
                # Progress indicator
                if (idx + 1) % 10 == 0:
                    print(f"    Processed {idx + 1}/{len(results)} results")
                
            except Exception as e:
                print(f"    Error getting details for place {place_id}: {str(e)}")
                continue
        
        return contacts
        
    except Exception as e:
        print(f"  ERROR scraping {trade} in {location}: {str(e)}")
        return []

def check_duplicate(cursor, contact):
    """
    Check if contact already exists in database
    Returns: (is_duplicate, existing_id)
    """
    # Check by phone number first (most reliable)
    if contact.get('phone'):
        cursor.execute("""
            SELECT id FROM tradespeople 
            WHERE phone = %s
        """, (contact['phone'],))
        
        result = cursor.fetchone()
        if result:
            return True, result[0]
    
    # Check by trading name + location
    if contact.get('trading_name') and contact.get('location_searched'):
        cursor.execute("""
            SELECT id FROM tradespeople 
            WHERE LOWER(trading_name) = LOWER(%s)
            AND address LIKE %s
        """, (
            contact['trading_name'],
            f"%{contact['location_searched'].split(',')[0]}%"
        ))
        
        result = cursor.fetchone()
        if result:
            return True, result[0]
    
    return False, None

def save_contacts_to_db(contacts):
    """
    Save scraped contacts to database with deduplication and quality filtering
    
    Returns: (saved_count, duplicate_count, low_quality_count)
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    
    saved_count = 0
    duplicate_count = 0
    low_quality_count = 0
    
    for contact in contacts:
        # Skip if quality score too low (below 30)
        if contact.get('quality_score', 0) < 30:
            low_quality_count += 1
            print(f"    Skipping low quality: {contact.get('trading_name')} (score: {contact.get('quality_score')})")
            continue
        
        # Check for duplicates
        is_duplicate, existing_id = check_duplicate(cursor, contact)
        
        if is_duplicate:
            duplicate_count += 1
            print(f"    Duplicate: {contact.get('trading_name')} (ID: {existing_id})")
            continue
        
        # Insert new contact
        try:
            cursor.execute("""
                INSERT INTO tradespeople (
                    trading_name, phone, address, postcode, website,
                    trade_category, source, scraped_at, quality_score,
                    subscription_status, subscription_tier, can_receive_jobs,
                    created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                    'pending', 'none', false, NOW()
                )
                RETURNING id
            """, (
                contact['trading_name'],
                contact['phone'],
                contact['address'],
                contact['postcode'],
                contact['website'],
                contact['trade_category'],
                contact['source'],
                contact['scraped_at'],
                contact['quality_score']
            ))
            
            new_id = cursor.fetchone()[0]
            saved_count += 1
            print(f"    ✅ Saved: {contact['trading_name']} (ID: {new_id}, Score: {contact['quality_score']})")
            
        except Exception as e:
            print(f"    ❌ Error saving {contact.get('trading_name')}: {str(e)}")
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return saved_count, duplicate_count, low_quality_count

def run_monthly_scraping_batch():
    """
    Run the monthly scraping batch
    Uses CURRENT_MONTH_TRADES and CURRENT_MONTH_LOCATIONS
    """
    print("=" * 80)
    print("BEST TRADE - MONTHLY SCRAPING BATCH")
    print(f"Started: {datetime.now()}")
    print("=" * 80)
    print(f"\nTrades: {', '.join(CURRENT_MONTH_TRADES)}")
    print(f"Locations: {len(CURRENT_MONTH_LOCATIONS)} cities")
    print(f"Expected searches: {len(CURRENT_MONTH_TRADES) * len(CURRENT_MONTH_LOCATIONS)}")
    print("=" * 80)
    
    total_contacts = []
    search_count = 0
    
    start_time = time.time()
    
    for trade in CURRENT_MONTH_TRADES:
        print(f"\n{'='*80}")
        print(f"TRADE: {trade.upper()}")
        print(f"{'='*80}")
        
        for location in CURRENT_MONTH_LOCATIONS:
            search_count += 1
            print(f"\n[{search_count}/{len(CURRENT_MONTH_TRADES) * len(CURRENT_MONTH_LOCATIONS)}] {trade} in {location}")
            
            # Scrape
            contacts = scrape_trade_location(trade, location, MAX_RESULTS_PER_SEARCH)
            total_contacts.extend(contacts)
            
            print(f"  Retrieved: {len(contacts)} contacts")
            
            # Rate limiting between searches (respect API limits)
            time.sleep(2)
    
    # Save all contacts to database
    print("\n" + "=" * 80)
    print("SAVING TO DATABASE")
    print("=" * 80)
    
    saved, duplicates, low_quality = save_contacts_to_db(total_contacts)
    
    elapsed_time = time.time() - start_time
    
    # Summary
    print("\n" + "=" * 80)
    print("SCRAPING COMPLETE!")
    print("=" * 80)
    print(f"Total searches: {search_count}")
    print(f"Total contacts found: {len(total_contacts)}")
    print(f"✅ Saved to database: {saved}")
    print(f"⚠️  Duplicates skipped: {duplicates}")
    print(f"❌ Low quality skipped: {low_quality}")
    print(f"⏱️  Time elapsed: {elapsed_time/60:.1f} minutes")
    print(f"📊 Success rate: {(saved/(len(total_contacts) or 1)*100):.1f}%")
    print("=" * 80)
    
    return {
        'total_found': len(total_contacts),
        'saved': saved,
        'duplicates': duplicates,
        'low_quality': low_quality,
        'elapsed_time': elapsed_time
    }

if __name__ == "__main__":
    # Run the scraping batch
    results = run_monthly_scraping_batch()
    
    # Log results to database
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO scraping_batches (
            trades, locations, contacts_found, contacts_saved,
            duplicates, low_quality, elapsed_seconds, completed_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    """, (
        ','.join(CURRENT_MONTH_TRADES),
        ','.join(CURRENT_MONTH_LOCATIONS),
        results['total_found'],
        results['saved'],
        results['duplicates'],
        results['low_quality'],
        int(results['elapsed_time'])
    ))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n✅ Results logged to database")
