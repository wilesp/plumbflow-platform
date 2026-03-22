"""
Best Trade - Database Connection Module
Handles PostgreSQL connections via Railway
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

class Database:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set")
    
    def get_connection(self):
        """Get a new database connection"""
        try:
            conn = psycopg2.connect(
                self.database_url,
                cursor_factory=RealDictCursor
            )
            return conn
        except Exception as e:
            print(f"Database connection error: {str(e)}")
            raise

# Global database instance
db = Database()
