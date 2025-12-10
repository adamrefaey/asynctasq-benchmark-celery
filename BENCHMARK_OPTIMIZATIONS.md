# AsyncTasQ Benchmark Optimizations - Research Summary

**Date:** December 10, 2025  
**Research Focus:** Latest best practices for benchmarking async task queues and Python asyncio systems

---

## Executive Summary

Applied cutting-edge benchmarking practices from task queue research, async concurrency patterns, and microbenchmarking literature to significantly improve AsyncTasQ benchmark reliability and accuracy.

### Key Improvements Implemented

1. **Warmup Phase** - Stabilizes JIT compilation, Redis connections, and system caches
2. **Queue Depth Monitoring** - Tracks backlog buildup and consumer lag in real-time
3. **Enhanced Resource Monitoring** - Improved CPU/memory sampling with artifact filtering
4. **Statistical Validation** - Coefficient of Variation (CV) checks for result stability
5. **Accurate Latency Tracking** - Proper end-to-end timing with queue depth correlation

---

## Research Findings

### 1. Warmup Phase Critical for Accurate Results

**Source:** Microbenchmarking research (Oracle, Laurence Tratt)

**Finding:** Python's dynamic nature, Redis connection pooling, and system-level caching create measurement artifacts in early benchmark iterations.

**Impact:** First few runs often show 20-50% variance from steady-state performance.

**Implementation:**
```python
# Added to BenchmarkConfig
warmup_tasks: int = 100  # Stabilize system before measurement

# Execute warmup in scenario benchmarks
if config.warmup_tasks > 0:
    # Run smaller warmup workload
    # Wait for completion
    # Clear stats and pause before real benchmark
```

**Best Practice:** Run 5-10% of task count as warmup (100-200 tasks for 1000-2000 task benchmarks).

---

### 2. End-to-End Latency Must Include Queue Time

**Source:** SSENSE async concurrency evaluation, Medium async metrics research

**Finding:** Async systems mask downstream slowness with fast API responses. Must measure enqueue → completion time, not just API latency.

**Key Metrics:**
- **Queue wait time** - Time in queue before worker pickup
- **Execution time** - Actual processing duration
- **Total latency** - Enqueue to completion (what users experience)

**Implementation:**
```python
@dataclass
class TaskTiming:
    enqueue_time: float
    start_time: float | None = None  # Worker pickup time
    complete_time: float | None = None  # Completion time
    
    @property
    def total_latency(self) -> float:
        """End-to-end: enqueue → complete"""
        return self.complete_time - self.enqueue_time
```

**Best Practice:** Track P95/P99 latency, not just mean. Tail behavior reveals system limits.

---

### 3. Queue Depth = Leading Indicator of Problems

**Source:** Python task queue benchmark research (steventen/python_queue_benchmark)

**Finding:** Rising queue depth + rising age of oldest message = consumers can't keep up with producers.

**Implementation:**
```python
# Sample queue depth during execution
queue_depth_samples: list[tuple[float, int]] = []

while processing:
    pending = task_count - (completed + failed)
    timestamp = time.perf_counter()
    queue_depth_samples.append((timestamp, max(0, pending)))
```

**Key Ratios:**
- **Enqueue rate** - Tasks/sec added to queue
- **Processing rate** - Tasks/sec completed by workers
- **Steady state** - Processing rate ≥ enqueue rate (queue drains)

**Warning Signs:**
- Sustained `enqueue_rate > processing_rate` = backlog grows
- Rising `max(queue_depth)` across runs = system at capacity

---

### 4. Coefficient of Variation Validates Stability

**Source:** Statistical benchmarking best practices

**Finding:** Standard deviation alone doesn't reveal relative stability. CV normalizes variance by mean.

**Formula:**
```
CV = StdDev / Mean

CV < 0.1  → Excellent stability (< 10% variance)
CV 0.1-0.2 → Good stability
CV > 0.2  → High variance - results unreliable
```

**Implementation:**
```python
@property
def throughput_coefficient_of_variation(self) -> float:
    values = [r.throughput for r in self.results]
    mean = statistics.mean(values)
    stdev = statistics.stdev(values)
    return (stdev / mean) if mean > 0 else 0.0
```

**Use Case:** If CV > 0.2, increase number of runs or investigate system instability (noisy neighbors, thermal throttling, network jitter).

---

### 5. Resource Monitoring Must Filter Artifacts

**Source:** Production benchmarking experience

**Finding:** First CPU sample from `psutil` always returns 0.0 (warmup artifact). Early memory readings show process startup overhead.

**Implementation:**
```python
async def _monitor_loop(self):
    # Warmup CPU monitoring
    self.process.cpu_percent(interval=None)
    await asyncio.sleep(self.interval_seconds)
    
    while self._monitoring:
        cpu = self.process.cpu_percent(interval=None)
        # Filter warmup artifacts
        if cpu > 0.0 or len(self.cpu_samples) > 0:
            self.cpu_samples.append(cpu)
```

**Best Practice:** Sample at 0.5s intervals for balance between granularity and overhead.

---

## Benchmark Architecture Comparison

### Observed Performance (from research)

**Python Task Queue Benchmarks (20,000 tasks, 10 workers):**

| Library | Processing Time | Notes |
|---------|----------------|-------|
| Taskiq | 2.03s | Redis Streams (reliable delivery) |
| Dramatiq | 4.12s | Process pool, excellent defaults |
| Huey | 3.62s | Thread pool, simple API |
| Celery | 11.68s | Thread pool (17.6s prefork) |
| RQ | 51.05s | Worker pool issues |
| ARQ | 35.37s | No multi-worker support |
| Procrastinate | 27.46s | PostgreSQL broker |

**Key Takeaways:**
1. **Execution model matters** - Process pool ≈ thread pool for I/O workloads
2. **Broker efficiency critical** - Redis Streams > Redis lists for reliability
3. **Overhead varies 25x** - Library design impacts throughput significantly
4. **AsyncTasQ targets** - 2-5s range (matching Taskiq/Dramatiq/Huey)

---

## Recommended Benchmark Workflow

### Phase 1: Warmup (5-10% of workload)
```python
# Stabilize connections, caches, JIT
warmup_tasks = config.task_count // 10
await run_warmup_tasks(warmup_tasks)
await clear_stats()
await asyncio.sleep(1)  # Brief pause
```

### Phase 2: Measurement
```python
# Start resource monitoring
monitor = ResourceMonitor(interval_seconds=0.5)
await monitor.start()

# Enqueue tasks (track enqueue rate)
enqueue_start = time.perf_counter()
task_ids = await enqueue_all_tasks()
enqueue_duration = time.perf_counter() - enqueue_start

# Process tasks (track queue depth, completion rate)
while not all_complete():
    stats = await get_stats()
    queue_depth = task_count - (completed + failed)
    track_sample(time.perf_counter(), queue_depth)
    await asyncio.sleep(0.5)

# Stop monitoring
avg_cpu, avg_memory = await monitor.stop()
```

### Phase 3: Validation
```python
# Check stability
cv = calculate_coefficient_of_variation(throughput_results)
if cv > 0.2:
    console.print("[yellow]⚠ High variance - consider more runs[/yellow]")

# Check queue behavior
max_backlog = max(q[1] for q in queue_depth_samples)
if max_backlog > task_count * 0.5:
    console.print("[red]⚠ Queue buildup detected[/red]")
```

---

## Metrics to Report

### Primary Metrics
1. **Throughput** - Tasks/sec (mean, median, P95)
2. **Latency** - Enqueue → complete time (P50, P95, P99)
3. **Stability** - Coefficient of variation across runs
4. **Resource usage** - CPU %, Memory MB (mean)

### Secondary Metrics
5. **Enqueue rate** - Tasks/sec enqueued
6. **Processing rate** - Tasks/sec completed
7. **Queue depth** - Max backlog size
8. **Failure rate** - Failed tasks / total tasks

### Diagnostic Metrics
9. **Wait time** - Time in queue before pickup
10. **Execution time** - Worker processing duration
11. **Queue age** - Time oldest message spent waiting

---

## Anti-Patterns to Avoid

### ❌ Don't: Run single-iteration benchmarks
**Why:** High variance from warmup, caching, network jitter  
**Fix:** Run 10+ iterations, report median + P95

### ❌ Don't: Ignore latency tail behavior
**Why:** P99 reveals capacity limits, mean hides outliers  
**Fix:** Always track P95/P99, not just mean

### ❌ Don't: Mix sync blocking calls in async benchmarks
**Why:** Blocks event loop, artificially reduces throughput  
**Fix:** Use async I/O, run CPU work in process pools

### ❌ Don't: Benchmark on noisy systems
**Why:** Background processes skew results  
**Fix:** Use dedicated benchmark machines or containers

### ❌ Don't: Compare cold starts only
**Why:** Doesn't reflect steady-state production performance  
**Fix:** Always include warmup phase before measurement

---

## Implementation Checklist

### Completed ✅
- [x] Add warmup_tasks configuration field
- [x] Implement warmup phase in scenario_1_throughput
- [x] Add queue_depth_samples tracking
- [x] Improve ResourceMonitor CPU artifact filtering
- [x] Add coefficient_of_variation calculation
- [x] Display stability warnings in runner output
- [x] Add CV to JSON export

### Remaining 🔄
- [ ] Apply warmup/monitoring to scenarios 2-11
- [ ] Implement cleanup between benchmark runs
- [ ] Add latency histogram generation
- [ ] Create queue depth over time charts
- [ ] Add throughput-over-time graphs
- [ ] Implement outlier detection algorithm
- [ ] Add confidence interval calculations
- [ ] Create comparative analysis reports

---

## References

1. **Python Task Queue Benchmarks**
   - steventen/python_queue_benchmark (GitHub)
   - "Exploring Python Task Queue Libraries with Load Test" (stevenyue.com)

2. **Async Concurrency Patterns**
   - "Evaluate Async Concurrency: Metrics, End-to-End Latency & Load Tests" (Medium)
   - SSENSE async evaluation patterns

3. **Microbenchmarking Research**
   - "Avoiding Benchmarking Pitfalls on the JVM" (Oracle)
   - Laurence Tratt - "More Evidence for Problems in VM Warmup"
   - "Microbenchmarking is hard: virtual machine edition" (lemire.me)

4. **Performance Methodology**
   - "Ultimate Guide to API Latency and Throughput" (DreamFactory)
   - "Throughput vs Latency Graph" (BrowserStack)

---

## Next Steps

1. **Apply to all scenarios** - Port warmup/monitoring to scenarios 2-11
2. **Add visualization** - Generate charts for queue depth, latency distribution
3. **Statistical rigor** - Implement outlier detection, confidence intervals
4. **Comparative analysis** - Build AsyncTasQ vs Celery comparison reports
5. **CI integration** - Automate benchmarks with stability gates (CV < 0.15)

---

**Author:** AsyncTasQ Benchmark Team  
**Last Updated:** December 10, 2025  
**Status:** Phase 1 Complete (Common Infrastructure)
