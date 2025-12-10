# AsyncTasQ vs Celery Benchmarking Suite

Production-grade benchmarking infrastructure for comprehensive performance comparison between **AsyncTasQ** and **Celery** task queues over Redis.

## ⚡ Recent Optimizations (Dec 2025)

This benchmark suite implements **cutting-edge async benchmarking practices** based on research of 7+ Python task queue libraries and academic microbenchmarking literature:

- ✅ **Pre-warmed workers** - Workers must be running before benchmarks start (eliminates startup variance)
- ✅ **Queue depth monitoring** - Real-time backlog tracking to detect consumer lag
- ✅ **Statistical validation** - Coefficient of Variation (CV) checks for result stability
- ✅ **Enhanced resource monitoring** - Improved CPU/memory sampling with artifact filtering
- ✅ **End-to-end latency** - Proper enqueue→completion tracking (not just API response time)

**See:** [BENCHMARK_OPTIMIZATIONS.md](BENCHMARK_OPTIMIZATIONS.md) for research findings | [OPTIMIZATION_QUICK_REF.md](OPTIMIZATION_QUICK_REF.md) for usage guide

## Overview

This benchmarking suite implements focused performance testing between AsyncTasQ and Celery using Redis (the most common production deployment) with:

- **11 comprehensive scenarios** covering throughput, latency, I/O-bound, CPU-bound, mixed workloads, serialization, scalability, ORM integration, event streaming, and FastAPI integration
- **Redis backend** for both frameworks (most common and fair comparison)
- **Multiple execution models**: AsyncTasQ BaseTask/SyncTask/ProcessTask vs Celery prefork/threads
- **Statistical rigor**: 10+ runs per scenario, p95/p99 latency, stability validation (CV < 0.15)
- **Full observability**: Prometheus metrics, Grafana dashboards, py-spy profiling, memory tracking
- **Docker-based infrastructure**: Isolated Redis service for reproducible testing

> **Note**: For multi-driver benchmarks of AsyncTasQ (PostgreSQL, MySQL, RabbitMQ, AWS SQS), see the main asynctasq repository.

## Quick Start

```bash
# 1. Install dependencies
just init

# 2. Start Redis infrastructure
just docker-up              # For Scenario 1 only (minimal tasks)
# OR
just docker-up-mock         # For Scenarios 2+ (includes Mock API on port 8080)

# 3. Verify database separation (RECOMMENDED)
just verify-separation      # Checks that AsyncTasQ uses DB 0, Celery uses DB 1 & 2

# 4. ⚠️ START WORKERS FIRST (REQUIRED!)
#    Open separate terminal windows for each worker:

# Terminal 1: AsyncTasQ worker
just worker-asynctasq

# Terminal 2: Celery worker (if testing Celery scenarios)
just worker-celery

# 5. Run benchmarks (in Terminal 3, AFTER workers are running)
just benchmark-all  # All scenarios
just benchmark 1    # Single scenario

# 6. View results
just report  # Generate HTML report with charts

# 7. Stop everything
# Ctrl+C in worker terminals, then:
just docker-down
```

**⚠️ CRITICAL:** 
- The benchmark runner **DOES NOT start workers automatically**. You **MUST** start workers in separate terminals before running `just benchmark-all` or the benchmark will freeze. See [Worker Setup](./WORKER_SETUP.md) for details.
- **Database Isolation**: AsyncTasQ uses Redis DB 0, Celery uses DB 1 & 2. Run `just verify-separation` to confirm proper configuration. See [REDIS_DATABASE_SEPARATION.md](./REDIS_DATABASE_SEPARATION.md) for details.
- **Scenario 2 (I/O-bound)** requires the Mock API server. Use `just docker-up-mock` instead of `just docker-up`.

## Architecture

```
asynctasq-benchmark-celery/
├── benchmarks/           # Benchmark scenarios (scenario_*.py)
├── tasks/                # Task definitions (asynctasq_tasks.py, celery_tasks.py)
├── infrastructure/       # Docker compose, monitoring configs
├── analysis/             # Data processing and visualization
├── results/              # CSV/JSON outputs, profiling data
└── reports/              # Generated HTML/PDF reports
```

## Scenarios

| Scenario | Description | Key Metrics | Requirements |
|----------|-------------|-------------|--------------|
| 1 | Basic Throughput (20k minimal tasks) | tasks/sec, enqueue rate | Redis only |
| 2 | I/O-Bound (HTTP requests with mock server) | async scaling efficiency | **Mock API required** (`just docker-up-mock`) |
| 3 | CPU-Bound (ProcessTask vs prefork) | GIL impact, process parallelism | Redis only |
| 4 | Mixed Workload (60% I/O, 30% light CPU, 10% heavy CPU) | realistic performance | **Mock API required** |
| 5 | Serialization (msgpack vs JSON/pickle, ORM models) | payload size, speed | Redis only |
| 6 | Scalability (1k → 100k task ramp-up) | saturation point, queue depth | Redis only |
| 7 | Real-World (e-commerce order pipeline) | end-to-end latency, retry behavior | **Mock API required** |
| 8 | Cold Start (worker initialization time) | startup latency, first task | Redis only |
| 9 | Multi-Queue (priority queues, routing) | queue management | Redis only |
| 10 | Event Streaming (Redis Pub/Sub overhead) | event delivery latency | Redis only |
| 11 | FastAPI Integration (lifespan overhead) | HTTP dispatch performance | Redis only |

## Requirements

- **Python**: 3.12+ (both AsyncTasQ and Celery)
- **Docker**: 27.x with Compose v2
- **Memory**: 8GB+ RAM recommended
- **CPU**: 8+ cores for optimal parallelism testing
- **Disk**: 5GB+ for logs, profiling data, results

## Environment Variables

```bash
# AsyncTasQ Configuration (uses Redis DB 0)
ASYNCTASQ_DRIVER=redis
ASYNCTASQ_REDIS_URL=redis://localhost:6379/0

# Celery Configuration (uses Redis DB 1 for broker, DB 2 for backend)
# IMPORTANT: Separate databases ensure workers don't process each other's tasks
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Benchmarking Configuration
BENCHMARK_RUNS=10  # Number of repetitions per scenario
BENCHMARK_WORKERS=10  # Worker count (overridden per scenario)
BENCHMARK_WARMUP_SECONDS=30  # Warm-up period before metrics collection
BENCHMARK_OUTPUT_DIR=./results  # Output directory for CSV/JSON

# Monitoring (Optional)
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
```

**Database Isolation:**
- **AsyncTasQ**: Uses Redis database **0** exclusively
- **Celery**: Uses Redis database **1** for broker and database **2** for result backend
- This separation ensures workers running in parallel don't interfere with each other's tasks

## Monitoring

### Grafana Dashboards

Access at `http://localhost:3000` (default: admin/admin):

- **AsyncTasQ Dashboard**: Throughput, latency, queue depth, worker health, event stream
- **Celery Dashboard**: Task rate, prefork/thread metrics, broker connections
- **System Metrics**: CPU, memory, network, disk I/O per node
- **Comparison View**: Side-by-side AsyncTasQ vs Celery performance

### Prometheus Metrics

Access at `http://localhost:9090`:

- `asynctasq_tasks_total` - Task completion counter
- `asynctasq_task_duration_seconds` - Task execution time histogram
- `asynctasq_queue_depth` - Current queue size
- `asynctasq_event_emission_duration_seconds` - Event overhead
- `celery_tasks_total` - Celery task counter
- `celery_task_duration_seconds` - Celery task duration

## Key Commands

```bash
# Initialization
just init                 # Install all dependencies (Python + Docker)

# Infrastructure
just docker-up                # Start Redis only
just docker-up-monitoring     # Start Redis + Prometheus/Grafana
just docker-up-mock           # Start Redis + Mock API server
just docker-down              # Stop all services
just docker-logs              # Tail service logs
just docker-clean             # Remove volumes and reset state
just check-health             # Verify Redis is running

# Benchmarking
just benchmark-all        # Run all scenarios
just benchmark scenario1  # Run specific scenario
just benchmark-quick      # Quick test (1 run per scenario)
just benchmark-stress     # 24-hour soak test

# Profiling
just profile-asynctasq    # py-spy profiling for AsyncTasQ worker
just profile-celery       # py-spy profiling for Celery worker
just profile-memory       # memory_profiler analysis

# Analysis
just analyze              # Statistical analysis (mean, p95, p99, t-tests)
just visualize            # Generate charts (matplotlib/seaborn)
just report               # Generate full HTML report with all metrics

# Redis Utilities
just reset-redis          # Flush all Redis data
just redis-info           # Show Redis statistics
just redis-monitor        # Monitor Redis commands in real-time
```

## Interpreting Results

### Expected Performance (Targets)

| Metric | AsyncTasQ Target | Celery Baseline |
|--------|------------------|-----------------|
| Throughput (I/O) | >5000 tasks/sec | ~1500 tasks/sec |
| Throughput (CPU) | Match Celery prefork (ProcessTask) | Baseline |
| Mean Latency | <50ms | ~200ms |
| P99 Latency | <300ms | ~1000ms |
| Serialization (ORM) | 90% payload reduction | Manual (N/A) |
| Worker Memory | <100MB | ~150MB (prefork) |
| Startup Time | <100ms | ~500ms (prefork pool) |

### Statistical Significance

- All comparisons include **t-tests** with p < 0.05 threshold
- Report includes **effect size** (Cohen's d) for practical significance
- Confidence intervals: 95% for all metrics

### Anti-Patterns to Validate

The benchmark suite explicitly tests these anti-patterns to document them:

1. **AsyncTasQ BaseTask with CPU-bound work** (blocks event loop) - should show 5x+ slowdown
2. **Celery threads with heavy CPU** (GIL contention) - should show ~1.5x slower than prefork
3. **Passing ORM models to Celery without manual serialization** - causes stale data issues (documented)

## Output Structure

```
results/
├── scenario_1_throughput.csv           # Raw timing data
├── scenario_1_throughput_stats.json    # Statistical summary
├── scenario_1_throughput_profile.svg   # py-spy flamegraph
├── scenario_2_io_bound.csv
├── ...
└── summary_report.html                 # Full report with charts
### CSV Format

```csv
framework,run,task_count,total_time,throughput,mean_latency,p50,p95,p99,memory_mb,cpu_percent
asynctasq,1,20000,3.45,5797.1,12.3,10.2,45.6,89.3,87.4,72.3
asynctasq,2,20000,3.52,5681.8,13.1,10.8,47.2,91.1,88.1,71.8
celery,1,20000,12.34,1620.7,123.4,98.2,456.7,892.1,142.3,68.9
...
```

## Why Redis Only?

## Reproducibility

- **Docker images pinned** to specific versions (Redis 8.4, Prometheus 3.1, Grafana 11.4)
- **Python dependencies locked** with `uv.lock` for exact versions
- **Random seed fixed** for reproducible test ordering
- **Warm-up period** to eliminate cold-start bias
- **Multiple runs** to account for variance (min 10 per scenario)
For multi-driver AsyncTasQ benchmarks (PostgreSQL, MySQL, RabbitMQ, SQS), see the main asynctasq repository.ery,redis,1,20000,12.34,1620.7,123.4,98.2,456.7,892.1,142.3,68.9
...
```

## Reproducibility

- **Docker images pinned** to specific versions (Redis 7.4, PostgreSQL 17, etc.)
- **Python dependencies locked** with `uv.lock` for exact versions
- **Random seed fixed** for reproducible test ordering
- **Warm-up period** to eliminate cold-start bias
- **Multiple runs** to account for variance (min 10 per scenario)

## Contributing

To add new benchmark scenarios:

1. Create `benchmarks/scenario_N_description.py`
2. Implement `run_benchmark()` function returning `BenchmarkResult`
3. Add scenario to `justfile` commands
4. Update `analysis/report_generator.py` for new metrics
5. Run `just ci` to validate (linting, type checking, tests)

## License

MIT License (matches parent AsyncTasQ project)

## References

- [AsyncTasQ Benchmarking Plan](../asynctasq/docs/benchmarking-plan.md)
- [Celery Best Practices](https://docs.celeryq.dev/en/stable/userguide/optimizing.html)
- [Python Queue Benchmark Research](https://github.com/GoodManWEN/python_queue_benchmark)
- [Async vs Threading Performance](https://www.cloudcity.io/blog/2019/02/27/things-i-wish-they-told-me-about-multiprocessing-in-python/)
