#!/usr/bin/env python3
"""
Database connection test script
This script will help debug database connection issues
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from app.database import test_database_connection, create_tables


async def main():
    """Main test function"""
    print("=" * 50)
    print("DATABASE CONNECTION TEST")
    print("=" * 50)
    
    # Test basic connection
    print("\n1. Testing database connection...")
    success, message = await test_database_connection()
    
    if success:
        print(f"✅ Connection successful: {message}")
        
        # Test table creation
        print("\n2. Testing table creation...")
        try:
            await create_tables()
            print("✅ Tables created successfully")
        except Exception as e:
            print(f"❌ Table creation failed: {e}")
            
    else:
        print(f"❌ Connection failed: {message}")
        print("\nTroubleshooting steps:")
        print("1. Check if PostgreSQL is running")
        print("2. Verify environment variables in .env file")
        print("3. Check network connectivity to database host")
        print("4. Verify database credentials")
        print("5. Ensure database exists")
        
    print("\n" + "=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
