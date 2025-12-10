# Redis Database Separation - Verification Guide

## Overview

This document describes the Redis database separation strategy to ensure AsyncTasQ and Celery workers don't interfere with each other when running in parallel.

## Database Allocation

| Framework | Purpose | Redis DB | Configuration |
|-----------|---------|----------|---------------|
| **AsyncTasQ** | Task queue | DB 0 | `ASYNCTASQ_REDIS_URL=redis://localhost:6379/0` |
| **Celery** | Broker (task queue) | DB 1 | `CELERY_BROKER_URL=redis://localhost:6379/1` |
| **Celery** | Result backend | DB 2 | `CELERY_RESULT_BACKEND=redis://localhost:6379/2` |

## Implementation Details

### 1. AsyncTasQ Configuration

**File: `benchmarks/scenario_1_throughput.py`**
```python
cfg = Config(redis_url="redis://localhost:6379/0")
driver = DriverFactory.create_from_config(cfg)
```

**File: `justfile` (worker command)**
```bash
ASYNCTASQ_REDIS_URL=redis://localhost:6379/0 python -m asynctasq worker --queue default --concurrency 10
```

### 2. Celery Configuration

**File: `tasks/celery_tasks.py`**
```python
app = Celery(
    "celery_tasks",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
)
```

**File: `justfile` (worker command)**
```bash
CELERY_BROKER_URL=redis://localhost:6379/1 CELERY_RESULT_BACKEND=redis://localhost:6379/2 uv run celery -A tasks.celery_tasks worker --loglevel=info --concurrency=10
```

## Verification Steps

### Step 1: Check Redis Keys Before Starting Workers

```bash
# Connect to Redis CLI
redis-cli

# Check all databases are empty
SELECT 0
KEYS *
# Should return: (empty array)

SELECT 1
KEYS *
# Should return: (empty array)

SELECT 2
KEYS *
# Should return: (empty array)
```

### Step 2: Start AsyncTasQ Worker

```bash
# Terminal 1
just worker-asynctasq
```

Expected output should include: `Redis DB 0`

### Step 3: Start Celery Worker

```bash
# Terminal 2
just worker-celery
```

Expected output should include: `Redis DB 1 & 2`

### Step 4: Verify Database Usage

```bash
# Terminal 3: Monitor Redis
redis-cli

# Check AsyncTasQ (DB 0)
SELECT 0
KEYS *
# Should show AsyncTasQ queue keys like: queue:default, queue:default:processing

# Check Celery Broker (DB 1)
SELECT 1
KEYS *
# Should show Celery keys like: _kombu.*, celery

# Check Celery Backend (DB 2)
SELECT 2
KEYS *
# Should show result keys like: celery-task-meta-*
```

### Step 5: Run Benchmark and Verify Isolation

```bash
# Terminal 4: Run benchmark
just benchmark 1

# Monitor in Redis CLI (Terminal 3)
# DB 0 should show AsyncTasQ activity (if testing asynctasq)
# DB 1 should show Celery activity (if testing celery)
# They should NEVER overlap
```

## Troubleshooting

### Problem: AsyncTasQ processes Celery tasks (or vice versa)

**Symptom:** In scenario 2 or 3, you see AsyncTasQ worker picking up Celery tasks or Celery worker processing AsyncTasQ tasks

**Root Cause:** The benchmark script didn't explicitly set AsyncTasQ's global config to use Redis DB 0

**Solution:**
1. **FIXED:** The benchmark runner and all scenarios now explicitly call `set_global_config()` to ensure Redis DB 0
2. Verify the fix by checking Redis:
   ```bash
   redis-cli
   SELECT 0
   KEYS *  # Should only show AsyncTasQ keys when AsyncTasQ benchmark runs
   SELECT 1
   KEYS *  # Should only show Celery keys when Celery benchmark runs
   ```
3. If still seeing issues, restart workers and flush Redis:
   ```bash
   # Stop all workers (Ctrl+C)
   redis-cli FLUSHALL
   # Restart workers
   just worker-asynctasq  # Terminal 1
   just worker-celery     # Terminal 2
   ```

### Problem: Workers processing wrong tasks

**Symptom:** AsyncTasQ worker tries to process Celery tasks or vice versa

**Solution:**
1. Stop all workers (Ctrl+C)
2. Flush all Redis databases:
   ```bash
   redis-cli FLUSHALL
   ```
3. Restart workers using `just worker-asynctasq` and `just worker-celery`
4. Verify database allocation using steps above

### Problem: Environment variables not being used

**Symptom:** Workers connect to wrong database despite environment variables

**Solution:**
1. Check that you're using the `just` commands (not manual commands)
2. Verify environment variables are set:
   ```bash
   echo $ASYNCTASQ_REDIS_URL
   echo $CELERY_BROKER_URL
   echo $CELERY_RESULT_BACKEND
   ```
3. If using `.env` file, ensure it's loaded:
   ```bash
   export $(cat .env | xargs)
   ```

### Problem: Redis connection errors

**Symptom:** `Connection refused` or `NOAUTH` errors

**Solution:**
1. Ensure Redis is running:
   ```bash
   just docker-up
   just check-health
   ```
2. Verify Redis is accessible:
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

## Best Practices

1. **Always use `just` commands** - They include the correct environment variables
2. **Flush between tests** - Run `redis-cli FLUSHALL` between benchmarks to ensure clean state
3. **Monitor Redis** - Keep a Redis CLI terminal open to verify database separation
4. **Check worker logs** - Ensure workers are connecting to the correct database
5. **Use .env.example** - Copy to `.env` and customize for your environment

## Quick Reference

```bash
# Start infrastructure
just docker-up

# Start workers (in separate terminals)
just worker-asynctasq  # Uses Redis DB 0
just worker-celery     # Uses Redis DB 1 & 2

# Run benchmarks
just benchmark 1       # Test both frameworks
just benchmark-all     # Run all scenarios

# Monitor Redis
redis-cli
SELECT 0  # AsyncTasQ
SELECT 1  # Celery broker
SELECT 2  # Celery backend
KEYS *    # Show keys in current database

# Clean up
redis-cli FLUSHALL    # Clear all databases
just docker-down      # Stop Redis
```

## Expected Behavior

✅ **Correct:** Each framework only sees its own tasks
✅ **Correct:** Workers process tasks from their assigned database only
✅ **Correct:** No cross-contamination between AsyncTasQ and Celery
❌ **Incorrect:** AsyncTasQ worker processes Celery tasks
❌ **Incorrect:** Celery worker processes AsyncTasQ tasks
❌ **Incorrect:** Tasks appear in multiple databases

## Additional Resources

- AsyncTasQ Configuration: https://github.com/yourusername/asynctasq
- Celery Configuration: https://docs.celeryq.dev/en/stable/userguide/configuration.html
- Redis Databases: https://redis.io/commands/select/
