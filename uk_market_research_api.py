# ============================================================================
# UK MARKET RESEARCH API ENDPOINTS - Add to main.py
# ============================================================================

"""
Add these endpoints to your main.py file to support the UK market research dashboard
Scraper runs and returns data IN MEMORY - NO DATABASE SAVES
"""

import subprocess
import json
from pathlib import Path
from typing import Optional

# Global variable to store scraper results in memory
_market_research_data = {
    'status': 'idle',  # idle, running, complete, failed
    'progress': 0,
    'message': '',
    'data': None,
    'error': None
}

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.post("/api/market-research/run")
async def run_uk_market_research():
    """
    Run UK-wide market research scraper
    Returns data in memory - DOES NOT save to database
    """
    global _market_research_data
    
    try:
        # Reset state
        _market_research_data = {
            'status': 'running',
            'progress': 0,
            'message': 'Starting UK-wide scraper...',
            'data': None,
            'error': None
        }
        
        logger.info("Starting UK market research scraper...")
        
        # Run scraper in background
        import threading
        thread = threading.Thread(target=_run_market_scraper_thread)
        thread.daemon = True
        thread.start()
        
        return {
            "status": "started",
            "message": "UK market research scraper started"
        }
    
    except Exception as e:
        logger.error(f"Error starting market research: {e}")
        _market_research_data['status'] = 'failed'
        _market_research_data['error'] = str(e)
        raise HTTPException(status_code=500, detail=str(e))


def _run_market_scraper_thread():
    """Run scraper in background thread"""
    global _market_research_data
    
    try:
        _market_research_data['message'] = 'Scraping Gumtree UK-wide...'
        _market_research_data['progress'] = 20
        
        # Import scraper
        import sys
        import os
        
        # Add current directory to path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # Import and run UK scraper
        from uk_wide_scraper import UKWideScraper
        
        _market_research_data['message'] = 'Running scrapers...'
        _market_research_data['progress'] = 40
        
        scraper = UKWideScraper()
        scraper.run()
        
        _market_research_data['message'] = 'Processing results...'
        _market_research_data['progress'] = 80
        
        # Get results (scraper saves to file)
        import glob
        files = glob.glob('scraped_ads_*.json')
        if files:
            latest_file = max(files, key=os.path.getctime)
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            _market_research_data['data'] = data
            _market_research_data['status'] = 'complete'
            _market_research_data['progress'] = 100
            _market_research_data['message'] = f"Complete! Found {data.get('total_jobs', 0)} jobs"
            
            logger.info(f"✅ Market research complete: {data.get('total_jobs', 0)} jobs found")
            
            # Optional: Clean up file
            # os.remove(latest_file)
        else:
            raise Exception("No results file generated")
    
    except Exception as e:
        logger.error(f"Market research scraper failed: {e}")
        _market_research_data['status'] = 'failed'
        _market_research_data['error'] = str(e)
        _market_research_data['progress'] = 0


@app.get("/api/market-research/status")
async def get_market_research_status():
    """Get current status of market research scraper"""
    global _market_research_data
    
    return {
        "status": _market_research_data['status'],
        "progress": _market_research_data['progress'],
        "message": _market_research_data['message'],
        "data": _market_research_data['data'],
        "error": _market_research_data['error']
    }


@app.get("/api/market-research/results")
async def get_market_research_results():
    """Get latest market research results"""
    global _market_research_data
    
    if _market_research_data['status'] != 'complete':
        raise HTTPException(status_code=404, detail="No results available")
    
    return _market_research_data['data']


@app.post("/api/market-research/export")
async def export_market_research():
    """
    Export market research data as CSV
    Returns CSV content for download
    """
    global _market_research_data
    
    if _market_research_data['status'] != 'complete':
        raise HTTPException(status_code=404, detail="No results available")
    
    data = _market_research_data['data']
    jobs = data.get('jobs', [])
    
    # Convert to CSV
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'title', 'region', 'county', 'location', 'postcode', 
        'urgency', 'price_mentioned', 'description', 'source', 'source_url'
    ])
    
    writer.writeheader()
    for job in jobs:
        writer.writerow({
            'title': job.get('title', ''),
            'region': job.get('region', ''),
            'county': job.get('county', ''),
            'location': job.get('location', ''),
            'postcode': job.get('postcode', ''),
            'urgency': job.get('urgency', ''),
            'price_mentioned': job.get('price_mentioned', ''),
            'description': (job.get('description', '') or '')[:200],
            'source': job.get('source', ''),
            'source_url': job.get('source_url', '')
        })
    
    csv_content = output.getvalue()
    
    return Response(
        content=csv_content,
        media_type='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename="uk-market-research-{datetime.now().strftime("%Y%m%d")}.csv"'
        }
    )


# ============================================================================
# DEPLOYMENT NOTES
# ============================================================================

"""
To deploy these endpoints:

1. Make sure uk_wide_scraper.py is in your project root

2. Add to requirements.txt:
   beautifulsoup4==4.12.2
   lxml==4.9.3

3. Copy the endpoints above into main.py

4. Upload uk-market-research.html to frontend/ folder

5. Deploy:
   git add main.py uk_wide_scraper.py uk-market-research.html requirements.txt
   git commit -m "Add UK market research dashboard"
   git push

6. Access at:
   https://plumberflow.co.uk/uk-market-research.html

7. Click "Run UK-Wide Scraper" button
   - Scraper runs in background (5-10 minutes)
   - Results show in dashboard
   - Export to Excel/CSV
   - NO database saves! ✅
"""
