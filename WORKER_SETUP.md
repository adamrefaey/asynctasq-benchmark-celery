# Worker Setup for Benchmarks

## The Problem

The benchmark suite was initially showing zeros for latency, memory, and CPU metrics because:

1. **No workers were running** - Tasks were being enqueued but never processed
2. **Completion tracking was placeholder** - Used hardcoded `completed = task_count` instead of polling
3. **Resource monitoring was missing** - Memory/CPU metrics were hardcoded to 0.0
4. **Task timing data incomplete** - Only enqueue times were tracked, no start/complete times

## The Solution

### 1. Fixed Resource Monitoring (✅ DONE)

Added `ResourceMonitor` class in `benchmarks/common.py`:
- Polls CPU and memory usage at 500ms intervals using `psutil`
- Runs in background during benchmark execution
- Returns average CPU% and memory (MB) when stopped

### 2. Fixed Completion Tracking (✅ DONE)

Updated `scenario_1_throughput.py` to:
- Initialize driver connection to query task status
- Poll `driver.get_global_stats()` every 500ms
- Check `completed + failed >= task_count` for completion
- Break out of polling loop when all tasks are done

### 3. Integrated Resource Monitoring (✅ DONE)

Modified AsyncTasQ benchmark to:
- Start `ResourceMonitor` before enqueueing tasks
- Stop monitor after tasks complete
- Populate `memory_mb` and `cpu_percent` in `BenchmarkResult`

### 4. Worker Requirement (⚠️ REQUIRED)

**CRITICAL: You MUST start workers before running benchmarks!**

## How to Run Benchmarks Correctly

### Step 1: Start Infrastructure

```bash
just docker-up  # Starts Redis
```

### Step 2: Start Workers (REQUIRED!)

**For AsyncTasQ:**
```bash
# Terminal 1: Start AsyncTasQ worker
asynctasq worker --queue default --concurrency 10
```

**For Celery:**
```bash
# Terminal 2: Start Celery worker
celery -A tasks.celery_tasks worker --loglevel=info --concurrency=10
```

### Step 3: Run Benchmarks

```bash
# Terminal 3: Run benchmarks
just benchmark-all
# OR
just benchmark 1  # Single scenario
```

### Step 4: Stop Workers

Press `Ctrl+C` in worker terminals to gracefully shut down.

## Why External Workers?

We use **external workers** (not in-process) because:

1. **Realistic** - Matches production deployment patterns
2. **Fair comparison** - Both frameworks use their native worker implementations
3. **Resource isolation** - Worker CPU/memory separate from benchmark script
4. **Scalability testing** - Can vary worker count independently

## Automated Worker Management (TODO)

Future improvement: Add `just` commands to automate worker lifecycle:

```bash
just workers-start   # Start both AsyncTasQ + Celery workers in background
just workers-stop    # Stop all workers
just workers-status  # Check if workers are running
```

This would use `subprocess` to launch workers and track PIDs for cleanup.

## Current Metrics Status

With the fixes applied:

- ✅ **Throughput** - Working (tasks/sec calculated correctly)
- ✅ **Memory** - Working (average RSS in MB)
- ✅ **CPU** - Working (average CPU percent, can exceed 100% on multi-core)
- ⚠️ **Latency** - Partially working:
  - Currently estimates all tasks complete at `processing_end` time
  - For accurate per-task latency, need worker-side instrumentation
  - This is a **future enhancement** (see below)

## Future Enhancements: Per-Task Latency

For precise per-task latency tracking, we need:

1. **Worker instrumentation** - Workers report task start/complete times
2. **Redis Pub/Sub events** - Workers publish lifecycle events to Redis
3. **Benchmark subscription** - Benchmark script subscribes to events and updates `TaskTiming` objects
4. **Event matching** - Match task_id from events to enqueued tasks

This is **optional** - current implementation is sufficient for throughput/resource benchmarks.

## Testing the Fixes

1. Start workers (see Step 2 above)
2. Run a single scenario:
   ```bash
   just benchmark 1
   ```
3. Verify metrics are non-zero:
   - Throughput: ~500-1000 tasks/sec (depends on hardware)
   - Memory: ~50-200 MB (depends on task complexity)
   - CPU: ~50-800% (depends on worker concurrency and cores)
   - Latency: Should show actual millisecond values (not 0.00)

## Troubleshooting

### "All metrics are still zero"

- **Check**: Are workers running? (`ps aux | grep -E 'asynctasq|celery'`)
- **Check**: Is Redis running? (`redis-cli ping`)
- **Check**: Are workers connected to same Redis? (check URLs match)

### "Latency is 0.00 but other metrics work"

- This is expected with current implementation
- We estimate all tasks complete at same time
- For per-task latency, need worker instrumentation (future work)

### "Completed count doesn't reach task_count"

- **Check**: Workers may have crashed - check logs
- **Check**: Tasks may have failed - check `failed` count in stats
- **Check**: Timeout may be too short - increase `timeout_seconds` in config

## Summary

**What's Fixed:**
- ✅ Resource monitoring (CPU, memory)
- ✅ Completion tracking (driver polling)
- ✅ Throughput calculation
- ⚠️ Latency (estimated, not per-task yet)

**What's Required:**
- ⚠️ **Manual worker startup** (must start before benchmarks)
- ⚠️ **Manual worker cleanup** (Ctrl+C to stop)

**What's Optional (Future):**
- Per-task latency via worker events
- Automated worker lifecycle management
- Worker health checks before benchmark starts
