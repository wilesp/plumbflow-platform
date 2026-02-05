#!/usr/bin/env python3
"""
PLUMBER PLATFORM - STARTUP SCRIPT
Quick launcher for the platform
"""

import os
import sys
import subprocess
from pathlib import Path

def print_header():
    print("="*60)
    print("    PLUMBER MATCHING PLATFORM - STARTUP")
    print("="*60)
    print()

def check_dependencies():
    """Check if all required packages are installed"""
    print("Checking dependencies...")
    
    required = [
        'psycopg2',
        'requests',
        'beautifulsoup4',
        'openai',
        'stripe',
        'twilio',
        'sendgrid'
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} - MISSING")
            missing.append(package)
    
    if missing:
        print(f"\nMissing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    print("\n✓ All dependencies installed\n")
    return True

def check_env_vars():
    """Check if required environment variables are set"""
    print("Checking environment variables...")
    
    required = {
        'DATABASE_URL': 'PostgreSQL connection string',
        'OPENAI_API_KEY': 'OpenAI API key (optional for demo)',
        'STRIPE_SECRET_KEY': 'Stripe API key (optional for demo)',
        'TWILIO_ACCOUNT_SID': 'Twilio Account SID (optional for demo)',
    }
    
    missing = []
    for var, description in required.items():
        if os.getenv(var):
            print(f"  ✓ {var}")
        else:
            print(f"  ⚠ {var} - Not set ({description})")
            missing.append(var)
    
    if missing:
        print("\n⚠ Some environment variables are not set.")
        print("The platform will run in DEMO MODE with simulated services.")
        print("\nTo enable full functionality, set:")
        for var in missing:
            print(f"  export {var}=your_value_here")
        print()
    else:
        print("\n✓ All environment variables configured\n")
    
    return True

def check_database():
    """Check if database is accessible"""
    print("Checking database connection...")
    
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("  ⚠ DATABASE_URL not set - using in-memory simulation")
        return True
    
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        conn.close()
        print("  ✓ Database connection successful\n")
        return True
    except Exception as e:
        print(f"  ✗ Database connection failed: {e}")
        print("  Platform will run with in-memory storage\n")
        return True

def show_menu():
    """Show startup menu"""
    print("\nWhat would you like to do?\n")
    print("1. Run single scraping cycle (test mode)")
    print("2. Start continuous operation (production mode)")
    print("3. Open plumber dashboard (web browser)")
    print("4. View system status")
    print("5. Exit")
    print()
    
    choice = input("Enter choice (1-5): ").strip()
    return choice

def run_test_cycle():
    """Run single scraping and processing cycle"""
    print("\n" + "="*60)
    print("RUNNING TEST CYCLE")
    print("="*60 + "\n")
    
    from main_orchestrator import PlatformOrchestrator
    
    platform = PlatformOrchestrator()
    platform.run_scraping_and_processing_cycle()
    
    print("\n✓ Test cycle complete!")
    input("\nPress Enter to return to menu...")

def run_continuous():
    """Start continuous operation"""
    print("\n" + "="*60)
    print("STARTING CONTINUOUS OPERATION")
    print("="*60 + "\n")
    
    interval = input("Scraping interval in minutes (default 15): ").strip() or "15"
    
    try:
        interval = int(interval)
    except:
        interval = 15
    
    print(f"\nStarting platform with {interval} minute intervals...")
    print("Press Ctrl+C to stop\n")
    
    from main_orchestrator import PlatformOrchestrator
    
    platform = PlatformOrchestrator()
    platform.start_continuous_operation(interval_minutes=interval)

def open_dashboard():
    """Open plumber dashboard in browser"""
    dashboard_path = Path(__file__).parent / "plumber_dashboard.html"
    
    if not dashboard_path.exists():
        print("✗ Dashboard file not found!")
        input("\nPress Enter to return to menu...")
        return
    
    print("\nOpening dashboard in browser...")
    
    # Try to open in default browser
    import webbrowser
    webbrowser.open(f"file://{dashboard_path.absolute()}")
    
    print("✓ Dashboard opened!")
    print("\nNote: This is a demo dashboard with sample data.")
    print("In production, it would connect to your backend API.")
    input("\nPress Enter to return to menu...")

def show_status():
    """Show system status"""
    print("\n" + "="*60)
    print("SYSTEM STATUS")
    print("="*60 + "\n")
    
    # Check services
    services = {
        'Database': bool(os.getenv('DATABASE_URL')),
        'OpenAI (AI Analysis)': bool(os.getenv('OPENAI_API_KEY')),
        'Stripe (Payments)': bool(os.getenv('STRIPE_SECRET_KEY')),
        'Twilio (SMS)': bool(os.getenv('TWILIO_ACCOUNT_SID')),
        'SendGrid (Email)': bool(os.getenv('SENDGRID_API_KEY')),
    }
    
    print("Service Status:")
    for service, enabled in services.items():
        status = "✓ ENABLED" if enabled else "⚠ SIMULATED"
        print(f"  {service:30} {status}")
    
    print("\n" + "="*60)
    
    # Show configuration
    print("\nConfiguration:")
    print(f"  Python Version: {sys.version.split()[0]}")
    print(f"  Working Directory: {Path.cwd()}")
    print(f"  Database: {'PostgreSQL' if os.getenv('DATABASE_URL') else 'In-Memory Simulation'}")
    
    print("\n" + "="*60)
    input("\nPress Enter to return to menu...")

def main():
    """Main entry point"""
    print_header()
    
    # Pre-flight checks
    if not check_dependencies():
        sys.exit(1)
    
    check_env_vars()
    check_database()
    
    # Main loop
    while True:
        choice = show_menu()
        
        if choice == '1':
            run_test_cycle()
        elif choice == '2':
            run_continuous()
        elif choice == '3':
            open_dashboard()
        elif choice == '4':
            show_status()
        elif choice == '5':
            print("\nGoodbye! 👋\n")
            break
        else:
            print("\nInvalid choice. Please try again.\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nShutting down...\n")
        sys.exit(0)
