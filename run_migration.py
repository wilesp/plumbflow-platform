#!/usr/bin/env python3
"""
Database Migration Script
Run this once to create all database tables
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def run_migration():
    """Run database migration"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL not set in environment")
        print("   Set it in Railway or your .env file")
        sys.exit(1)
    
    print("🗄️  PlumberFlow Database Migration")
    print("=" * 50)
    print(f"📍 Database: {database_url.split('@')[1] if '@' in database_url else 'localhost'}")
    print()
    
    # Read SQL schema file
    try:
        with open('database_schema.sql', 'r') as f:
            schema_sql = f.read()
    except FileNotFoundError:
        print("❌ database_schema.sql not found")
        print("   Make sure you're running this from the project root")
        sys.exit(1)
    
    # Connect to database
    try:
        print("🔌 Connecting to database...")
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        print("✅ Connected successfully")
        print()
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)
    
    # Run migration
    try:
        print("📝 Running migration script...")
        print("-" * 50)
        
        cursor.execute(schema_sql)
        
        print()
        print("✅ Migration completed successfully!")
        print()
        
        # Verify tables created
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        
        print("📊 Tables created:")
        for table in tables:
            print(f"   ✓ {table[0]}")
        
        print()
        print("🎉 Database is ready!")
        print()
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        print()
        print("This might mean:")
        print("  - Tables already exist (run DROP TABLE first)")
        print("  - Database permissions issue")
        print("  - SQL syntax error")
        sys.exit(1)
    
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_migration()
