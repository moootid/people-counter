#!/usr/bin/env python3
"""
Environment checker for database configuration
This script will help identify missing environment variables
"""

import os
from dotenv import load_dotenv

def check_environment():
    """Check if all required environment variables are set"""
    print("=" * 60)
    print("ENVIRONMENT VARIABLES CHECKER")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Required environment variables for database
    required_vars = {
        "DB_HOST": "Database host (e.g., localhost, db)",
        "DB_PORT": "Database port (usually 5432 for PostgreSQL)",
        "DB_NAME": "Database name",
        "DB_USER": "Database username",
        "DB_PASSWORD": "Database password"
    }
    
    print("\nChecking required database environment variables:\n")
    
    missing_vars = []
    set_vars = []
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            if var == "DB_PASSWORD":
                print(f"✅ {var:<12}: ***HIDDEN*** ({description})")
            else:
                print(f"✅ {var:<12}: {value} ({description})")
            set_vars.append(var)
        else:
            print(f"❌ {var:<12}: NOT SET ({description})")
            missing_vars.append(var)
    
    print("\n" + "=" * 60)
    
    if missing_vars:
        print(f"\n❌ Missing {len(missing_vars)} required environment variable(s):")
        for var in missing_vars:
            print(f"   - {var}")
        
        print("\nTo fix this:")
        print("1. Create a .env file in the project root")
        print("2. Copy the template from .env.example")
        print("3. Fill in the missing values")
        print("4. Example .env file content:")
        print()
        print("   DB_HOST=localhost")
        print("   DB_PORT=5432")
        print("   DB_NAME=your_database_name")
        print("   DB_USER=your_username")
        print("   DB_PASSWORD=your_password")
        
        return False
    else:
        print(f"\n✅ All {len(set_vars)} required environment variables are set!")
        return True


if __name__ == "__main__":
    check_environment()
