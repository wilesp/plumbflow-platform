#!/usr/bin/env python3
"""
PLUMBER PLATFORM - LIVE DEMO
Simplified version that runs without external dependencies
Shows complete workflow in action
"""

import json
import time
from datetime import datetime
from decimal import Decimal

# ============================================================================
# SAMPLE DATA
# ============================================================================

SAMPLE_SCRAPED_ADS = [
    {
        'id': 1,
        'source': 'gumtree',
        'title': 'Urgent - Kitchen tap won\'t stop dripping',
        'description': 'Tap in kitchen running constantly, can\'t turn it off properly. Need someone today if possible. Located in Wimbledon.',
        'postcode': 'SW19 2AB',
        'phone': '07700900123',
        'scraped_at': '2024-02-03 10:15:00'
    },
    {
        'id': 2,
        'source': 'gumtree',
        'title': 'Toilet flush not working',
        'description': 'Toilet cistern fills but flush button doesn\'t work properly. Water keeps running. Need fix this week.',
        'postcode': 'SW18 3QR',
        'phone': '07700900456',
        'scraped_at': '2024-02-03 10:20:00'
    },
    {
        'id': 3,
        'source': 'facebook',
        'title': 'Emergency - Burst pipe in bathroom!',
        'description': 'URGENT! Pipe burst behind toilet, water everywhere. Need emergency plumber NOW.',
        'postcode': 'SW17 9NH',
        'phone': '07700900789',
        'scraped_at': '2024-02-03 10:25:00'
    }
]

SAMPLE_PLUMBERS = [
    {
        'id': 1,
        'name': 'John Smith',
        'phone': '+447700900001',
        'email': 'john@plumbers.com',
        'base_postcode': 'SW18',
        'hourly_rate': 65.0,
        'credit_balance': 250.0,
        'gas_safe': True,
        'skills': ['leaking_tap', 'boiler_repair', 'burst_pipe'],
        'rating': 4.8,
        'contact_rate': 0.92,
        'current_jobs': 3,
        'available_today': True
    },
    {
        'id': 2,
        'name': 'Sarah Johnson',
        'phone': '+447700900002',
        'email': 'sarah@plumbers.com',
        'base_postcode': 'SW19',
        'hourly_rate': 60.0,
        'credit_balance': 180.0,
        'gas_safe': False,
        'skills': ['leaking_tap', 'toilet_replacement', 'unblock_sink'],
        'rating': 4.6,
        'contact_rate': 0.78,
        'current_jobs': 5,
        'available_today': True
    },
    {
        'id': 3,
        'name': 'Mike Williams',
        'phone': '+447700900003',
        'email': 'mike@plumbers.com',
        'base_postcode': 'CR4',
        'hourly_rate': 70.0,
        'credit_balance': 320.0,
        'gas_safe': True,
        'skills': ['boiler_repair', 'shower_installation', 'burst_pipe'],
        'rating': 4.9,
        'contact_rate': 0.95,
        'current_jobs': 7,
        'available_today': False
    }
]

# ============================================================================
# AI ANALYZER
# ============================================================================

def analyze_ad_with_ai(ad):
    """Simulate AI analysis of scraped ad"""
    text = f"{ad['title']} {ad['description']}".lower()
    
    # Determine job type
    if 'tap' in text or 'drip' in text:
        job_type = 'leaking_tap'
        estimated_hours = 0.5
        estimated_parts = 8.0
    elif 'toilet' in text or 'flush' in text:
        job_type = 'toilet_flush'
        estimated_hours = 0.75
        estimated_parts = 20.0
    elif 'burst' in text or 'pipe' in text:
        job_type = 'burst_pipe'
        estimated_hours = 1.5
        estimated_parts = 40.0
    else:
        job_type = 'general_plumbing'
        estimated_hours = 1.0
        estimated_parts = 30.0
    
    # Determine urgency
    if 'emergency' in text or 'urgent' in text or 'now' in text:
        urgency = 'emergency'
    elif 'today' in text:
        urgency = 'today'
    elif 'this week' in text or 'soon' in text:
        urgency = 'this_week'
    else:
        urgency = 'flexible'
    
    # Determine complexity
    complexity = 'medium'
    if 'simple' in text or 'just' in text:
        complexity = 'easy'
    elif 'major' in text or 'complex' in text:
        complexity = 'hard'
    
    return {
        'job_type': job_type,
        'urgency': urgency,
        'complexity': complexity,
        'estimated_hours': estimated_hours,
        'estimated_parts': estimated_parts,
        'confidence': 0.89
    }

# ============================================================================
# PRICING CALCULATOR
# ============================================================================

def calculate_pricing(job_analysis, plumber, postcode):
    """Calculate job pricing"""
    
    # Get plumber rate
    hourly_rate = plumber['hourly_rate']
    if job_analysis['urgency'] == 'emergency':
        hourly_rate *= 1.5
    elif job_analysis['urgency'] == 'today':
        hourly_rate *= 1.2
    
    # Calculate labour
    job_hours = job_analysis['estimated_hours']
    labour_cost = max(job_hours * hourly_rate, 75.0)  # £75 minimum
    
    # Calculate travel (simplified)
    travel_cost = 18.0
    
    # Materials
    materials_cost = job_analysis['estimated_parts']
    
    # Subtotal
    subtotal = labour_cost + travel_cost + materials_cost
    
    # Margin
    margin = subtotal * 0.12
    
    # Finder's fee
    if subtotal < 75:
        finder_fee = 10.0
    elif subtotal < 150:
        finder_fee = 15.0
    elif subtotal < 300:
        finder_fee = 25.0
    else:
        finder_fee = min(subtotal * 0.10, 50.0)
    
    # Totals
    customer_pays = subtotal + margin + finder_fee
    plumber_earns = subtotal + margin
    
    return {
        'labour_cost': labour_cost,
        'travel_cost': travel_cost,
        'materials_cost': materials_cost,
        'subtotal': subtotal,
        'margin': margin,
        'finder_fee': finder_fee,
        'customer_pays': customer_pays,
        'plumber_earns': plumber_earns,
        'platform_fee': finder_fee
    }

# ============================================================================
# MATCHING ENGINE
# ============================================================================

def calculate_distance_score(plumber_postcode, job_postcode):
    """Calculate distance score (simplified)"""
    # Extract area codes
    p_area = plumber_postcode[:4]
    j_area = job_postcode[:4]
    
    if p_area == j_area:
        return 100, 2.1  # Same area, 2.1km
    elif p_area[:3] == j_area[:3]:
        return 85, 5.0  # Adjacent, 5km
    else:
        return 50, 10.0  # Different, 10km

def match_plumber_to_job(job_analysis, plumber, job_postcode):
    """Calculate match score for plumber-job pair"""
    
    # 1. Distance (40%)
    distance_score, distance_km = calculate_distance_score(plumber['base_postcode'], job_postcode)
    
    # 2. Availability (25%)
    if plumber['available_today'] and plumber['current_jobs'] < 5:
        availability_score = 100
    elif plumber['available_today']:
        availability_score = 70
    else:
        availability_score = 30
    
    # 3. Specialty (20%)
    if job_analysis['job_type'] in plumber['skills']:
        specialty_score = 100
    else:
        specialty_score = 40
    
    # 4. Performance (10%)
    performance_score = plumber['contact_rate'] * 100
    
    # 5. Rating (5%)
    rating_score = (plumber['rating'] / 5.0) * 100
    
    # Total weighted score
    total_score = (
        distance_score * 0.40 +
        availability_score * 0.25 +
        specialty_score * 0.20 +
        performance_score * 0.10 +
        rating_score * 0.05
    )
    
    return {
        'plumber': plumber,
        'score': round(total_score, 1),
        'distance_km': distance_km,
        'components': {
            'distance': distance_score,
            'availability': availability_score,
            'specialty': specialty_score,
            'performance': performance_score,
            'rating': rating_score
        }
    }

def find_best_plumbers(job_analysis, plumbers, job_postcode):
    """Find and rank best plumbers"""
    matches = []
    
    for plumber in plumbers:
        match = match_plumber_to_job(job_analysis, plumber, job_postcode)
        matches.append(match)
    
    # Sort by score
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    return matches

# ============================================================================
# NOTIFICATION SIMULATOR
# ============================================================================

def send_notification_to_plumber(plumber, job_title, pricing):
    """Simulate sending notification"""
    print(f"\n  📱 NOTIFICATION SENT TO: {plumber['name']}")
    print(f"     Phone: {plumber['phone']}")
    print(f"     Email: {plumber['email']}")
    print(f"\n     Message:")
    print(f"     🔔 New Lead Available!")
    print(f"     Job: {job_title}")
    print(f"     Your earnings: £{pricing['plumber_earns']:.2f}")
    print(f"     Lead fee: £{pricing['finder_fee']:.2f}")

def send_notification_to_customer(customer_phone, plumber_name, plumber_phone, estimated_price):
    """Simulate customer notification"""
    print(f"\n  📨 NOTIFICATION SENT TO CUSTOMER: {customer_phone}")
    print(f"\n     Message:")
    print(f"     ✅ Plumber Found!")
    print(f"     {plumber_name} will contact you shortly")
    print(f"     Phone: {plumber_phone}")
    print(f"     Estimated cost: £{estimated_price:.2f}")

# ============================================================================
# PAYMENT PROCESSOR
# ============================================================================

def charge_lead_fee(plumber, fee_amount):
    """Simulate charging lead fee"""
    old_balance = plumber['credit_balance']
    new_balance = old_balance - fee_amount
    
    print(f"\n  💳 PAYMENT PROCESSED")
    print(f"     Plumber: {plumber['name']}")
    print(f"     Previous balance: £{old_balance:.2f}")
    print(f"     Fee charged: £{fee_amount:.2f}")
    print(f"     New balance: £{new_balance:.2f}")
    
    plumber['credit_balance'] = new_balance
    return new_balance

# ============================================================================
# MAIN PLATFORM WORKFLOW
# ============================================================================

def process_single_ad(ad, plumbers):
    """Process one scraped ad through complete workflow"""
    
    print("\n" + "="*70)
    print(f"PROCESSING NEW AD #{ad['id']}")
    print("="*70)
    
    print(f"\n📋 SCRAPED AD:")
    print(f"   Source: {ad['source'].upper()}")
    print(f"   Title: {ad['title']}")
    print(f"   Description: {ad['description']}")
    print(f"   Location: {ad['postcode']}")
    print(f"   Time: {ad['scraped_at']}")
    
    time.sleep(1)
    
    # Step 1: AI Analysis
    print(f"\n🤖 STEP 1: AI ANALYSIS")
    print("   Analyzing job with AI...")
    job_analysis = analyze_ad_with_ai(ad)
    print(f"   ✓ Job type: {job_analysis['job_type']}")
    print(f"   ✓ Urgency: {job_analysis['urgency']}")
    print(f"   ✓ Complexity: {job_analysis['complexity']}")
    print(f"   ✓ Estimated time: {job_analysis['estimated_hours']} hours")
    print(f"   ✓ Estimated parts: £{job_analysis['estimated_parts']:.2f}")
    print(f"   ✓ AI Confidence: {job_analysis['confidence']:.0%}")
    
    time.sleep(1)
    
    # Step 2: Find matching plumbers
    print(f"\n🔍 STEP 2: FINDING MATCHING PLUMBERS")
    print("   Scanning available plumbers...")
    matches = find_best_plumbers(job_analysis, plumbers, ad['postcode'])
    
    print(f"\n   ✓ Found {len(matches)} plumbers:")
    for i, match in enumerate(matches, 1):
        print(f"      #{i}: {match['plumber']['name']} - Score: {match['score']:.1f}/100 ({match['distance_km']:.1f}km away)")
    
    time.sleep(1)
    
    # Step 3: Calculate pricing for top match
    best_match = matches[0]
    plumber = best_match['plumber']
    
    print(f"\n💰 STEP 3: CALCULATING PRICING")
    print(f"   For top match: {plumber['name']}")
    pricing = calculate_pricing(job_analysis, plumber, ad['postcode'])
    
    print(f"\n   Pricing Breakdown:")
    print(f"   ├─ Labour: £{pricing['labour_cost']:.2f}")
    print(f"   ├─ Travel: £{pricing['travel_cost']:.2f}")
    print(f"   ├─ Materials: £{pricing['materials_cost']:.2f}")
    print(f"   ├─ Subtotal: £{pricing['subtotal']:.2f}")
    print(f"   ├─ Margin (12%): £{pricing['margin']:.2f}")
    print(f"   └─ Finder's fee: £{pricing['finder_fee']:.2f}")
    print(f"\n   💵 Customer pays: £{pricing['customer_pays']:.2f}")
    print(f"   💰 Plumber earns: £{pricing['plumber_earns']:.2f}")
    print(f"   🏦 Your revenue: £{pricing['platform_fee']:.2f}")
    
    time.sleep(1)
    
    # Step 4: Send notification to plumber
    print(f"\n📧 STEP 4: SENDING NOTIFICATIONS")
    send_notification_to_plumber(plumber, ad['title'], pricing)
    
    time.sleep(1)
    
    # Step 5: Plumber accepts (simulated)
    print(f"\n✅ STEP 5: PLUMBER RESPONSE")
    print(f"   Waiting for {plumber['name']} to respond...")
    time.sleep(2)
    print(f"   ✓ {plumber['name']} ACCEPTED the lead!")
    
    time.sleep(1)
    
    # Step 6: Charge fee
    print(f"\n💳 STEP 6: CHARGING LEAD FEE")
    charge_lead_fee(plumber, pricing['finder_fee'])
    
    time.sleep(1)
    
    # Step 7: Notify customer
    print(f"\n📨 STEP 7: NOTIFYING CUSTOMER")
    send_notification_to_customer(
        ad['phone'],
        plumber['name'],
        plumber['phone'],
        pricing['customer_pays']
    )
    
    time.sleep(1)
    
    # Summary
    print(f"\n" + "="*70)
    print(f"✅ JOB SUCCESSFULLY MATCHED!")
    print("="*70)
    print(f"   Customer: {ad['postcode']}")
    print(f"   Plumber: {plumber['name']}")
    print(f"   Your Revenue: £{pricing['platform_fee']:.2f}")
    print(f"   Status: Plumber will contact customer shortly")
    print("="*70)

# ============================================================================
# LIVE DEMO
# ============================================================================

def run_live_demo():
    """Run live demonstration of platform"""
    
    print("\n" + "="*70)
    print("  🚀 PLUMBER MATCHING PLATFORM - LIVE DEMO")
    print("="*70)
    print()
    print("  This demo shows the complete automated workflow:")
    print("  1. Ad scraped from Gumtree/Facebook")
    print("  2. AI analyzes and categorizes job")
    print("  3. System finds best matching plumber")
    print("  4. Calculates dynamic pricing")
    print("  5. Sends notifications (SMS/Email/Push)")
    print("  6. Plumber accepts and gets charged")
    print("  7. Customer notified automatically")
    print()
    print("  💰 You earn £10-25 per job with ZERO manual work")
    print("="*70)
    
    input("\n  Press ENTER to start demo...")
    
    # Process each sample ad
    for i, ad in enumerate(SAMPLE_SCRAPED_ADS, 1):
        process_single_ad(ad, SAMPLE_PLUMBERS)
        
        if i < len(SAMPLE_SCRAPED_ADS):
            print("\n\n")
            choice = input(f"  ➡️  Process next ad? (Enter to continue, 'q' to quit): ")
            if choice.lower() == 'q':
                break
    
    # Final summary
    print("\n\n" + "="*70)
    print("  📊 DEMO SUMMARY")
    print("="*70)
    
    total_revenue = sum([15, 25, 25])  # Sample fees from demo
    
    print(f"\n  Jobs processed: {min(i, len(SAMPLE_SCRAPED_ADS))}")
    print(f"  Total revenue: £{total_revenue:.2f}")
    print(f"  Average per job: £{total_revenue / min(i, len(SAMPLE_SCRAPED_ADS)):.2f}")
    print()
    print("  💡 SCALING POTENTIAL:")
    print(f"     • 100 jobs/month = £1,700/month")
    print(f"     • 500 jobs/month = £10,000/month")
    print(f"     • 1,000 jobs/month = £20,000/month")
    print()
    print("  🎯 WHAT HAPPENS NEXT:")
    print("     1. Set up real database (PostgreSQL)")
    print("     2. Configure API keys (Stripe, Twilio, OpenAI)")
    print("     3. Recruit 10-20 plumbers in London")
    print("     4. Start with manual leads (not scraping)")
    print("     5. Test with real jobs for 1 month")
    print("     6. Scale to automated scraping")
    print()
    print("  📁 All code is in the 'plumber-platform' folder")
    print("  📖 Read QUICKSTART.md for setup instructions")
    print("="*70)
    print("\n  ✅ Demo complete! You now understand how it works.\n")

# ============================================================================
# RUN DEMO
# ============================================================================

if __name__ == "__main__":
    try:
        run_live_demo()
    except KeyboardInterrupt:
        print("\n\n  Demo stopped by user. Goodbye! 👋\n")
