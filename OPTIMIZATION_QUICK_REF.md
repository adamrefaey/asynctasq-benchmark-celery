# Benchmark Optimization Quick Reference

## Key Changes Summary

### 1. BenchmarkConfig - New Fields
```python
warmup_tasks: int = 100  # Warmup phase size
```

### 2. BenchmarkResult - New Fields  
```python
queue_depth_samples: list[tuple[float, int]]  # (timestamp, depth) tracking
```

### 3. BenchmarkSummary - New Properties
```python
throughput_coefficient_of_variation: float  # Stability metric (CV)
```

---

## Usage Example

### Before (Old Approach)
```python
# No warmup - measurement includes startup artifacts
config = BenchmarkConfig(
    framework=Framework.ASYNCTASQ,
    task_count=20000,
    worker_count=10,
    runs=10
)

# No queue depth tracking
# No stability validation
result = await run_benchmark(config)
```

### After (Optimized Approach)
```python
# Warmup stabilizes connections/caches
config = BenchmarkConfig(
    framework=Framework.ASYNCTASQ,
    task_count=20000,
    worker_count=10,
    runs=10,
    warmup_tasks=200  # 1% of workload
)

# Automatic queue depth tracking
# Stability validation in output
result = await run_benchmark(config)

# Check stability
summary = BenchmarkSummary(config=config, results=[result])
cv = summary.throughput_coefficient_of_variation

if cv > 0.2:
    print("⚠ High variance - increase runs or check system")
```

---

## Coefficient of Variation Interpretation

| CV Range | Stability | Action |
|----------|-----------|--------|
| < 0.1 | Excellent ✅ | Results are reliable |
| 0.1 - 0.2 | Good 👍 | Acceptable for comparisons |
| > 0.2 | Poor ⚠️ | Increase runs or investigate |

---

## Queue Depth Analysis

```python
# Access queue depth samples
for timestamp, depth in result.queue_depth_samples:
    if depth > config.task_count * 0.5:
        print(f"⚠ Backlog at {timestamp}: {depth} tasks")

# Calculate max backlog
max_backlog = max(depth for _, depth in result.queue_depth_samples)
backlog_ratio = max_backlog / config.task_count

if backlog_ratio > 0.7:
    print("⚠ System struggling - consider more workers")
```

---

## Warmup Guidelines

| Task Count | Warmup Tasks | Reasoning |
|------------|--------------|-----------|
| 1,000 | 100 | 10% for small benchmarks |
| 10,000 | 500 | 5% for medium benchmarks |
| 100,000 | 1,000 | 1% for large benchmarks |

**Rule of Thumb:** 1-10% of task count, minimum 100 tasks

---

## Resource Monitoring Best Practices

```python
# Automatic filtering of CPU warmup artifacts
monitor = ResourceMonitor(interval_seconds=0.5)
await monitor.start()

# ... run benchmark ...

avg_cpu, avg_memory = await monitor.stop()

# CPU > 80% consistently = CPU bound
# CPU < 20% = I/O bound or underutilized
# Memory growing = potential leak
```

---

## Running Optimized Benchmarks

```bash
# Single scenario with optimizations
python -m benchmarks.scenario_1_throughput asynctasq

# Full benchmark suite with stability checks
python -m benchmarks.runner --scenario 1 --framework both --runs 10

# Look for stability warnings in output:
# ✓ Excellent stability (CV: 0.045)
# ⚠ Good stability (CV: 0.158)  
# ⚠ High variance - results may be unreliable (CV: 0.234)
```

---

## Migration Checklist

For each scenario file:

- [ ] Add warmup phase before measurement
- [ ] Track queue_depth_samples during execution
- [ ] Pass queue_depth_samples to BenchmarkResult
- [ ] Verify CV displayed in runner output
- [ ] Test with `python -m py_compile`

---

## Performance Targets

Based on research of 7 Python task queue libraries:

| Metric | Target | Notes |
|--------|--------|-------|
| Throughput | 5,000-10,000 tasks/sec | 20k tasks in 2-4s |
| Latency P50 | < 50ms | Half tasks complete quickly |
| Latency P95 | < 200ms | Most tasks complete fast |
| Latency P99 | < 500ms | Even slow tasks reasonable |
| CV | < 0.15 | Consistent across runs |
| Max Backlog | < 50% of task count | Queue drains faster than fills |

**AsyncTasQ Goal:** Match or exceed Taskiq/Dramatiq/Huey (2-5s for 20k tasks)

---

## Common Issues & Solutions

### Issue: CV > 0.2 (High Variance)
**Causes:**
- System under load (noisy neighbors)
- Network jitter
- Thermal throttling
- Too few runs

**Solutions:**
- Run on dedicated machine
- Increase `runs` to 15-20
- Use containers for isolation
- Check system resources (top/htop)

### Issue: Queue Backlog Growing
**Causes:**
- Workers too slow
- Not enough workers
- CPU/memory bottleneck

**Solutions:**
- Increase `worker_count`
- Use ProcessTask for CPU-bound work
- Profile worker code
- Check resource usage

### Issue: First Run Much Slower
**Causes:**
- No warmup phase
- Redis connection pool cold
- Python JIT compilation

**Solutions:**
- Ensure `warmup_tasks > 0`
- Increase warmup to 10% of task count
- Discard first result if needed

---

## Next Phase: Visualization

Coming soon:
- Throughput over time graphs
- Latency distribution histograms  
- Queue depth time series
- Comparative framework charts
- HTML report generation

See `BENCHMARK_OPTIMIZATIONS.md` for full details.
