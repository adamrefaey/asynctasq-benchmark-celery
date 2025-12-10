#!/usr/bin/env python3
"""Verify Redis Database Separation

This script checks that AsyncTasQ and Celery are configured to use separate Redis databases.
Run this BEFORE starting benchmarks to ensure proper isolation.
"""

import os
import sys


def check_env_vars() -> bool:
    """Check environment variables for database separation."""
    print("=" * 70)
    print("Environment Variables Check")
    print("=" * 70)
    
    asynctasq_url = os.getenv("ASYNCTASQ_REDIS_URL", "NOT SET")
    celery_broker = os.getenv("CELERY_BROKER_URL", "NOT SET")
    celery_backend = os.getenv("CELERY_RESULT_BACKEND", "NOT SET")
    
    print(f"ASYNCTASQ_REDIS_URL:     {asynctasq_url}")
    print(f"CELERY_BROKER_URL:       {celery_broker}")
    print(f"CELERY_RESULT_BACKEND:   {celery_backend}")
    print()
    
    # Check for DB 0 in AsyncTasQ
    if "NOT SET" in asynctasq_url:
        print("⚠️  ASYNCTASQ_REDIS_URL not set (will default to redis://localhost:6379/0)")
        asynctasq_ok = True  # Default is acceptable
    elif "/0" in asynctasq_url or asynctasq_url.endswith("6379"):
        print("✓  AsyncTasQ configured for Redis DB 0")
        asynctasq_ok = True
    else:
        print("❌ AsyncTasQ NOT using DB 0 - will conflict with Celery!")
        asynctasq_ok = False
    
    # Check for DB 1 in Celery broker
    if "NOT SET" in celery_broker:
        print("⚠️  CELERY_BROKER_URL not set (will default to redis://localhost:6379/1)")
        celery_broker_ok = True  # Default is acceptable
    elif "/1" in celery_broker:
        print("✓  Celery broker configured for Redis DB 1")
        celery_broker_ok = True
    else:
        print("❌ Celery broker NOT using DB 1 - will conflict with AsyncTasQ!")
        celery_broker_ok = False
    
    # Check for DB 2 in Celery backend
    if "NOT SET" in celery_backend:
        print("⚠️  CELERY_RESULT_BACKEND not set (will default to redis://localhost:6379/2)")
        celery_backend_ok = True  # Default is acceptable
    elif "/2" in celery_backend:
        print("✓  Celery backend configured for Redis DB 2")
        celery_backend_ok = True
    else:
        print("❌ Celery backend NOT using DB 2!")
        celery_backend_ok = False
    
    print()
    return asynctasq_ok and celery_broker_ok and celery_backend_ok


def check_redis_keys() -> None:
    """Check Redis databases for existing keys."""
    try:
        import redis
    except ImportError:
        print("⚠️  redis-py not installed, skipping Redis key check")
        print("   Install with: pip install redis")
        return
    
    print("=" * 70)
    print("Redis Database Key Check")
    print("=" * 70)
    
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        print("✓  Connected to Redis\n")
    except redis.ConnectionError:
        print("❌ Cannot connect to Redis")
        print("   Start Redis with: just docker-up")
        return
    
    # Check DB 0 (AsyncTasQ)
    r.select(0)
    keys_db0 = r.keys('*')
    print(f"DB 0 (AsyncTasQ):        {len(keys_db0)} keys")
    if keys_db0:
        print(f"   Sample keys: {', '.join(keys_db0[:5])}")
        if any('celery' in k.lower() for k in keys_db0):
            print("   ⚠️  WARNING: Found Celery-like keys in AsyncTasQ database!")
    
    # Check DB 1 (Celery broker)
    r.select(1)
    keys_db1 = r.keys('*')
    print(f"DB 1 (Celery broker):    {len(keys_db1)} keys")
    if keys_db1:
        print(f"   Sample keys: {', '.join(keys_db1[:5])}")
        if any('queue:' in k for k in keys_db1):
            print("   ⚠️  WARNING: Found AsyncTasQ-like keys in Celery database!")
    
    # Check DB 2 (Celery backend)
    r.select(2)
    keys_db2 = r.keys('*')
    print(f"DB 2 (Celery backend):   {len(keys_db2)} keys")
    if keys_db2:
        print(f"   Sample keys: {', '.join(keys_db2[:5])}")
    
    print()
    
    if keys_db0 or keys_db1 or keys_db2:
        print("⚠️  Databases contain keys from previous runs")
        print("   Recommend flushing before benchmarks: redis-cli FLUSHALL")
    else:
        print("✓  All databases are clean")


def check_code_config() -> None:
    """Check that code has proper database separation."""
    print("=" * 70)
    print("Code Configuration Check")
    print("=" * 70)
    
    try:
        # Check AsyncTasQ task configuration
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from asynctasq.config import get_global_config, set_global_config
        
        # Set config as the benchmark will
        redis_url = os.getenv("ASYNCTASQ_REDIS_URL", "redis://localhost:6379/0")
        set_global_config(driver="redis", redis_url=redis_url)
        
        config = get_global_config()
        print(f"AsyncTasQ Config:")
        print(f"   Driver: {config.driver}")
        print(f"   Redis URL: {config.redis_url}")
        print(f"   Redis DB: {config.redis_db}")
        
        if config.redis_db == 0:
            print("   ✓  Using Redis DB 0")
        else:
            print(f"   ❌ Using Redis DB {config.redis_db} - should be 0!")
        
    except ImportError:
        print("⚠️  asynctasq not installed, skipping config check")
    
    print()
    
    try:
        # Check Celery configuration
        from tasks.celery_tasks import app
        
        print(f"Celery Config:")
        print(f"   Broker: {app.conf.broker_url}")
        print(f"   Backend: {app.conf.result_backend}")
        
        broker_ok = "/1" in str(app.conf.broker_url)
        backend_ok = "/2" in str(app.conf.result_backend)
        
        if broker_ok:
            print("   ✓  Broker using Redis DB 1")
        else:
            print(f"   ❌ Broker NOT using Redis DB 1!")
        
        if backend_ok:
            print("   ✓  Backend using Redis DB 2")
        else:
            print(f"   ❌ Backend NOT using Redis DB 2!")
        
    except ImportError:
        print("⚠️  Celery tasks not found, skipping Celery check")
    
    print()


def main() -> int:
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("Redis Database Separation Verification")
    print("=" * 70)
    print()
    
    env_ok = check_env_vars()
    check_redis_keys()
    check_code_config()
    
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    
    if env_ok:
        print("✓  Configuration looks correct")
        print("   AsyncTasQ will use Redis DB 0")
        print("   Celery will use Redis DB 1 (broker) and DB 2 (backend)")
        print()
        print("Next steps:")
        print("   1. Start workers: just worker-asynctasq (Terminal 1)")
        print("   2. Start workers: just worker-celery (Terminal 2)")
        print("   3. Run benchmarks: just benchmark-all (Terminal 3)")
        return 0
    else:
        print("❌ Configuration issues detected!")
        print()
        print("Fix by setting environment variables:")
        print("   export ASYNCTASQ_REDIS_URL=redis://localhost:6379/0")
        print("   export CELERY_BROKER_URL=redis://localhost:6379/1")
        print("   export CELERY_RESULT_BACKEND=redis://localhost:6379/2")
        print()
        print("Or use the provided justfile commands (recommended):")
        print("   just worker-asynctasq")
        print("   just worker-celery")
        return 1


if __name__ == "__main__":
    sys.exit(main())
