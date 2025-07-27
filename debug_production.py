#!/usr/bin/env python3
"""
Production Debugging Script
This script provides comprehensive debugging information for production issues
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent / "app"))


async def run_comprehensive_debug():
    """Run all debugging checks"""
    
    print("=" * 80)
    print("PEOPLE COUNTER - PRODUCTION DEBUGGING")
    print("=" * 80)
    print(f"Debug started at: {datetime.utcnow()}")
    print()
    
    debug_results = {
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # 1. Environment Variables Check
    print("1. ENVIRONMENT VARIABLES CHECK")
    print("-" * 40)
    
    env_vars = [
        "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD",
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"
    ]
    
    env_status = {}
    for var in env_vars:
        value = os.getenv(var)
        if var == "DB_PASSWORD" or "SECRET" in var:
            status = "SET" if value else "NOT SET"
            print(f"  {var:<20}: {status}")
        else:
            print(f"  {var:<20}: {value or 'NOT SET'}")
        env_status[var] = bool(value)
    
    debug_results["checks"]["environment"] = env_status
    print()
    
    # 2. Database Connection Test
    print("2. DATABASE CONNECTION TEST")
    print("-" * 40)
    
    try:
        from app.database import test_database_connection
        db_success, db_message = await test_database_connection()
        print(f"  Status: {'✅ SUCCESS' if db_success else '❌ FAILED'}")
        print(f"  Message: {db_message}")
        debug_results["checks"]["database"] = {
            "success": db_success,
            "message": db_message
        }
    except Exception as e:
        print(f"  Status: ❌ ERROR")
        print(f"  Error: {str(e)}")
        debug_results["checks"]["database"] = {
            "success": False,
            "error": str(e)
        }
    print()
    
    # 3. Video Processor Test
    print("3. VIDEO PROCESSOR TEST")
    print("-" * 40)
    
    try:
        from app.video_processor import VideoProcessor
        processor = VideoProcessor()
        await processor.initialize()
        print(f"  Status: ✅ SUCCESS")
        print(f"  Model path: {getattr(processor, 'model_path', 'Unknown')}")
        debug_results["checks"]["video_processor"] = {
            "success": True,
            "model_path": getattr(processor, 'model_path', 'Unknown')
        }
    except Exception as e:
        print(f"  Status: ❌ ERROR")
        print(f"  Error: {str(e)}")
        debug_results["checks"]["video_processor"] = {
            "success": False,
            "error": str(e)
        }
    print()
    
    # 4. File System Check
    print("4. FILE SYSTEM CHECK")
    print("-" * 40)
    
    important_paths = [
        "/app",
        "/app/yolo11n.pt",
        "/app/app",
        "/tmp"
    ]
    
    fs_status = {}
    for path in important_paths:
        exists = os.path.exists(path)
        if exists:
            if os.path.isfile(path):
                size = os.path.getsize(path)
                print(f"  {path:<20}: ✅ FILE ({size} bytes)")
            else:
                print(f"  {path:<20}: ✅ DIRECTORY")
        else:
            print(f"  {path:<20}: ❌ NOT FOUND")
        fs_status[path] = exists
    
    debug_results["checks"]["filesystem"] = fs_status
    print()
    
    # 5. Memory and Resource Check
    print("5. SYSTEM RESOURCES CHECK")
    print("-" * 40)
    
    try:
        import psutil
        
        # Memory usage
        memory = psutil.virtual_memory()
        print(f"  Memory Usage: {memory.percent}% ({memory.used // (1024*1024)} MB used)")
        
        # Disk usage
        disk = psutil.disk_usage('/')
        print(f"  Disk Usage: {disk.percent}% ({disk.used // (1024*1024*1024)} GB used)")
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        print(f"  CPU Usage: {cpu_percent}%")
        
        debug_results["checks"]["resources"] = {
            "memory_percent": memory.percent,
            "disk_percent": disk.percent,
            "cpu_percent": cpu_percent
        }
        
    except ImportError:
        print("  psutil not available - install with: pip install psutil")
        debug_results["checks"]["resources"] = {"error": "psutil not available"}
    except Exception as e:
        print(f"  Error checking resources: {e}")
        debug_results["checks"]["resources"] = {"error": str(e)}
    print()
    
    # 6. Network Connectivity Test
    print("6. NETWORK CONNECTIVITY TEST")
    print("-" * 40)
    
    try:
        import socket
        
        # Test database connection
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = int(os.getenv("DB_PORT", "5432"))
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((db_host, db_port))
        sock.close()
        
        if result == 0:
            print(f"  Database ({db_host}:{db_port}): ✅ REACHABLE")
            network_db = True
        else:
            print(f"  Database ({db_host}:{db_port}): ❌ UNREACHABLE")
            network_db = False
        
        debug_results["checks"]["network"] = {
            "database_reachable": network_db
        }
        
    except Exception as e:
        print(f"  Network test error: {e}")
        debug_results["checks"]["network"] = {"error": str(e)}
    print()
    
    # 7. Recent Logs Check
    print("7. RECENT LOGS CHECK")
    print("-" * 40)
    
    log_files = [
        "/tmp/people_counter.log",
        "/app/logs/people_counter.log",
        "/var/log/people_counter.log"
    ]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            try:
                stat = os.stat(log_file)
                size = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime)
                print(f"  {log_file}: ✅ EXISTS ({size} bytes, modified: {mtime})")
                
                # Show last few lines
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        print(f"    Last entry: {lines[-1].strip()}")
                        
            except Exception as e:
                print(f"  {log_file}: ❌ ERROR reading ({e})")
        else:
            print(f"  {log_file}: ❌ NOT FOUND")
    print()
    
    # Summary
    print("8. SUMMARY")
    print("-" * 40)
    
    total_checks = 0
    passed_checks = 0
    
    for category, results in debug_results["checks"].items():
        if isinstance(results, dict) and "success" in results:
            total_checks += 1
            if results["success"]:
                passed_checks += 1
    
    print(f"  Total Checks: {total_checks}")
    print(f"  Passed: {passed_checks}")
    print(f"  Failed: {total_checks - passed_checks}")
    print(f"  Success Rate: {(passed_checks/total_checks*100):.1f}%" if total_checks > 0 else "N/A")
    
    # Save debug results to file
    debug_file = f"/tmp/debug_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(debug_file, 'w') as f:
            json.dump(debug_results, f, indent=2, default=str)
        print(f"\n📄 Debug results saved to: {debug_file}")
    except Exception as e:
        print(f"\n❌ Failed to save debug results: {e}")
    
    print("\n" + "=" * 80)
    print("DEBUG COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_comprehensive_debug())
