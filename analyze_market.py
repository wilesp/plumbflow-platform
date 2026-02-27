"""
MARKET ANALYSIS SCRIPT
Analyzes scraped ads JSON file to show UK-wide opportunities
"""

import json
import sys
from collections import defaultdict, Counter
from datetime import datetime

def analyze_scraped_data(filename):
    """Comprehensive analysis of scraped job ads"""
    
    print("=" * 80)
    print("🔍 PLUMBERFLOW - UK MARKET ANALYSIS")
    print("=" * 80)
    print()
    
    # Load data
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ File not found: {filename}")
        print("Run uk_wide_scraper.py first!")
        return
    
    jobs = data.get('jobs', [])
    total = len(jobs)
    
    print(f"📊 OVERVIEW")
    print(f"   Total Jobs Scraped: {total}")
    print(f"   Scraped At: {data.get('scraped_at', 'Unknown')}")
    print(f"   Gumtree: {data['sources'].get('gumtree', 0)}")
    print(f"   Reddit: {data['sources'].get('reddit', 0)}")
    print()
    
    # ========================================================================
    # REGIONAL BREAKDOWN
    # ========================================================================
    
    print("=" * 80)
    print("🗺️  REGIONAL OPPORTUNITY MAP")
    print("=" * 80)
    print()
    
    regions = defaultdict(int)
    for job in jobs:
        region = job.get('region', 'Unknown')
        regions[region] += 1
    
    print("Region                    | Jobs | % of Total | Daily Proj | Monthly Rev (£18/lead)")
    print("-" * 80)
    for region, count in sorted(regions.items(), key=lambda x: x[1], reverse=True):
        pct = (count / total * 100) if total > 0 else 0
        daily_proj = int(count * 0.5)  # Conservative daily projection
        monthly_rev = daily_proj * 30 * 18  # £18 per lead
        print(f"{region:<25} | {count:>4} | {pct:>6.1f}% | {daily_proj:>10} | £{monthly_rev:>15,}")
    print()
    
    # ========================================================================
    # YOUR SERVICE AREA vs REST OF UK
    # ========================================================================
    
    print("=" * 80)
    print("🎯 SERVICE AREA ANALYSIS")
    print("=" * 80)
    print()
    
    service_area_regions = ['London', 'South East']
    service_area_jobs = sum(regions.get(r, 0) for r in service_area_regions)
    rest_of_uk_jobs = total - service_area_jobs
    
    print(f"Your Current Coverage (London + Home Counties):")
    print(f"   Jobs: {service_area_jobs} ({service_area_jobs/total*100:.1f}%)")
    print(f"   Daily Projection: ~{int(service_area_jobs * 0.5)} jobs/day")
    print(f"   Monthly Revenue: £{int(service_area_jobs * 0.5) * 30 * 18:,}/month")
    print()
    print(f"Rest of UK (Expansion Opportunity):")
    print(f"   Jobs: {rest_of_uk_jobs} ({rest_of_uk_jobs/total*100:.1f}%)")
    print(f"   Daily Projection: ~{int(rest_of_uk_jobs * 0.5)} jobs/day")
    print(f"   Monthly Revenue: £{int(rest_of_uk_jobs * 0.5) * 30 * 18:,}/month")
    print()
    
    # ========================================================================
    # COUNTY BREAKDOWN (Top 20)
    # ========================================================================
    
    print("=" * 80)
    print("📍 TOP 20 COUNTIES BY VOLUME")
    print("=" * 80)
    print()
    
    counties = defaultdict(int)
    for job in jobs:
        county = job.get('county') or job.get('region', 'Unknown')
        if county:
            counties[county] += 1
    
    print("County               | Jobs | Monthly Revenue Potential")
    print("-" * 60)
    for county, count in sorted(counties.items(), key=lambda x: x[1], reverse=True)[:20]:
        monthly_rev = int(count * 0.5) * 30 * 18
        print(f"{county:<20} | {count:>4} | £{monthly_rev:>10,}/month")
    print()
    
    # ========================================================================
    # DATA QUALITY METRICS
    # ========================================================================
    
    print("=" * 80)
    print("✅ DATA QUALITY ASSESSMENT")
    print("=" * 80)
    print()
    
    with_postcode = sum(1 for j in jobs if j.get('postcode'))
    with_location = sum(1 for j in jobs if j.get('location'))
    with_description = sum(1 for j in jobs if j.get('description') and len(j.get('description', '')) > 50)
    with_price = sum(1 for j in jobs if j.get('price_mentioned'))
    
    print(f"Postcode Available:     {with_postcode:>4} / {total} ({with_postcode/total*100:.1f}%)")
    print(f"Location Data:          {with_location:>4} / {total} ({with_location/total*100:.1f}%)")
    print(f"Detailed Description:   {with_description:>4} / {total} ({with_description/total*100:.1f}%)")
    print(f"Price Mentioned:        {with_price:>4} / {total} ({with_price/total*100:.1f}%)")
    print()
    
    # Quality score
    quality_score = (with_postcode * 0.4 + with_location * 0.2 + with_description * 0.3 + with_price * 0.1) / total * 100
    print(f"Overall Quality Score:  {quality_score:.1f}/100")
    print()
    
    if quality_score >= 70:
        print("✅ EXCELLENT - Data quality is high")
    elif quality_score >= 50:
        print("⚠️  GOOD - Usable but some gaps")
    else:
        print("❌ FAIR - Significant data gaps")
    print()
    
    # ========================================================================
    # URGENCY BREAKDOWN
    # ========================================================================
    
    print("=" * 80)
    print("⚡ URGENCY ANALYSIS")
    print("=" * 80)
    print()
    
    urgencies = Counter(j.get('urgency', 'normal') for j in jobs)
    
    print("Urgency Level | Jobs | % of Total | Premium Pricing Opportunity")
    print("-" * 70)
    print(f"Emergency     | {urgencies.get('emergency', 0):>4} | {urgencies.get('emergency', 0)/total*100:>6.1f}% | £25-30/lead (higher value)")
    print(f"High          | {urgencies.get('high', 0):>4} | {urgencies.get('high', 0)/total*100:>6.1f}% | £20-25/lead")
    print(f"Normal        | {urgencies.get('normal', 0):>4} | {urgencies.get('normal', 0)/total*100:>6.1f}% | £15-18/lead (standard)")
    print()
    
    # ========================================================================
    # EXPANSION OPPORTUNITIES
    # ========================================================================
    
    print("=" * 80)
    print("🚀 EXPANSION PRIORITY RANKING")
    print("=" * 80)
    print()
    
    expansion_regions = {
        'South West': regions.get('South West', 0),
        'Midlands': regions.get('Midlands', 0),
        'North West': regions.get('North West', 0),
        'North': regions.get('North', 0),
        'Scotland': regions.get('Scotland', 0),
        'Wales': regions.get('Wales', 0)
    }
    
    print("Rank | Region        | Jobs | Est. Monthly Revenue | Priority")
    print("-" * 75)
    for i, (region, count) in enumerate(sorted(expansion_regions.items(), key=lambda x: x[1], reverse=True), 1):
        monthly_rev = int(count * 0.5) * 30 * 18
        
        if i <= 2:
            priority = "🔥 HIGH"
        elif i <= 4:
            priority = "⭐ MEDIUM"
        else:
            priority = "💡 LOW"
        
        print(f"{i:>4} | {region:<13} | {count:>4} | £{monthly_rev:>18,} | {priority}")
    print()
    
    # ========================================================================
    # SAMPLE JOBS BY REGION
    # ========================================================================
    
    print("=" * 80)
    print("📋 SAMPLE JOBS (Top 3 from each major region)")
    print("=" * 80)
    print()
    
    for region in ['London', 'South East', 'Midlands', 'North West', 'South West']:
        region_jobs = [j for j in jobs if j.get('region') == region][:3]
        
        if region_jobs:
            print(f"\n{region}:")
            print("-" * 70)
            for job in region_jobs:
                print(f"  • {job.get('title', 'No title')[:60]}")
                print(f"    Location: {job.get('location', 'Unknown')}")
                print(f"    Urgency: {job.get('urgency', 'normal')}")
                if job.get('price_mentioned'):
                    print(f"    Price: {job.get('price_mentioned')}")
                print()
    
    # ========================================================================
    # INVESTMENT RECOMMENDATIONS
    # ========================================================================
    
    print("=" * 80)
    print("💰 REVENUE PROJECTIONS & ROI")
    print("=" * 80)
    print()
    
    scenarios = [
        ("Current (London + SE only)", service_area_jobs, 1.0),
        ("+ South West", service_area_jobs + regions.get('South West', 0), 1.2),
        ("+ Midlands", service_area_jobs + regions.get('South West', 0) + regions.get('Midlands', 0), 1.5),
        ("UK-Wide (All regions)", total, 2.0)
    ]
    
    print("Scenario                    | Daily Jobs | Monthly Jobs | Monthly Revenue | Setup Cost")
    print("-" * 90)
    for scenario, job_count, multiplier in scenarios:
        daily = int(job_count * 0.5)
        monthly_jobs = daily * 30
        monthly_rev = monthly_jobs * 18
        setup_cost = int(5000 * multiplier)  # Estimated setup per region
        
        print(f"{scenario:<27} | {daily:>10} | {monthly_jobs:>12} | £{monthly_rev:>14,} | £{setup_cost:>10,}")
    print()
    
    # ========================================================================
    # KEY INSIGHTS & RECOMMENDATIONS
    # ========================================================================
    
    print("=" * 80)
    print("🎯 KEY INSIGHTS & RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    print("1. MARKET SIZE:")
    print(f"   ✓ UK-wide opportunity: ~{int(total * 0.5)} jobs/day = £{int(total * 0.5) * 30 * 18:,}/month")
    print(f"   ✓ Your current area: ~{int(service_area_jobs * 0.5)} jobs/day = £{int(service_area_jobs * 0.5) * 30 * 18:,}/month")
    print()
    
    print("2. DATA QUALITY:")
    if quality_score >= 70:
        print(f"   ✓ High quality ({quality_score:.0f}/100) - Ready to use")
    else:
        print(f"   ⚠ Medium quality ({quality_score:.0f}/100) - May need enrichment")
    print()
    
    print("3. EXPANSION PRIORITY:")
    top_region = max(expansion_regions.items(), key=lambda x: x[1])
    print(f"   ✓ Next target: {top_region[0]} ({top_region[1]} jobs = £{int(top_region[1] * 0.5) * 30 * 18:,}/month)")
    print()
    
    print("4. QUICK WINS:")
    emergency_count = urgencies.get('emergency', 0)
    print(f"   ✓ {emergency_count} emergency jobs ({emergency_count/total*100:.0f}%) = Premium pricing opportunity")
    print(f"   ✓ {with_postcode} jobs ({with_postcode/total*100:.0f}%) with postcodes = Easy to match")
    print()
    
    print("=" * 80)
    print(f"📁 Full data available in: {filename}")
    print("=" * 80)
    print()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        # Find most recent file
        import glob
        import os
        
        files = glob.glob('scraped_ads_*.json')
        if not files:
            print("❌ No scraped data files found!")
            print("Run: python3 uk_wide_scraper.py first")
            sys.exit(1)
        
        filename = max(files, key=os.path.getctime)
        print(f"📂 Analyzing most recent file: {filename}")
        print()
    
    analyze_scraped_data(filename)
