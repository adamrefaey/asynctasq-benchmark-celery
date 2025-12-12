# AsyncTasQ vs Celery Benchmarking Suite

Production-grade benchmarking infrastructure for comprehensive performance comparison between **AsyncTasQ** and **Celery** task queues.

## Overview

This benchmarking suite provides rigorous performance testing between AsyncTasQ and Celery using Redis as the common backend.

### Key Features

**Test Coverage**
- 11 comprehensive scenarios covering throughput, latency, I/O-bound, CPU-bound, mixed workloads, serialization, scalability, ORM integration, event streaming, and FastAPI integration
- Multiple execution models: AsyncTasQ (BaseTask/SyncTask/ProcessTask) vs Celery (prefork/threads)

**Statistical Rigor**
- Pre-warmed workers (eliminates startup variance)
- Queue depth monitoring (detects consumer lag)
- 10+ runs per scenario with stability validation (CV < 0.15)
- p50/p95/p99 latency percentiles
- End-to-end latency tracking (enqueue → completion)

**Observability**
- Prometheus metrics with custom exporters
- Grafana dashboards for real-time monitoring
- py-spy flamegraphs for profiling
- Memory and CPU tracking

**Infrastructure**
- Docker-based services for reproducibility
- Isolated Redis databases (AsyncTasQ: DB 0, Celery: DB 1 & 2)
- Optional Mock API server for I/O testing

> **Note**: This suite focuses on Redis (the most common production deployment). For multi-driver AsyncTasQ benchmarks (PostgreSQL, MySQL, RabbitMQ, AWS SQS), see the main asynctasq repository.

### Recent Optimizations (Dec 2025)

Based on research of 7+ Python task queue libraries and academic microbenchmarking literature:

- Pre-warmed workers eliminate cold-start bias
- Queue depth monitoring detects backlog and consumer lag
- Coefficient of Variation (CV) checks ensure result stability
- Enhanced resource monitoring with artifact filtering
- Proper end-to-end latency measurement (not just API response time)

## Quick Start

### Prerequisites

- Python 3.14+
- Docker 27.x with Compose v2
- 8GB+ RAM, 8+ CPU cores recommended
- 5GB+ disk space

### Running Benchmarks

**Step 1: Install dependencies**
```bash
just init
```

**Step 2: Start infrastructure**
```bash
# For Scenario 1 only (basic throughput)
just docker-up

# For Scenarios 2-11 (I/O-bound, mixed workloads)
just docker-up-mock  # Includes Mock API on port 8080
```

**Step 3: Verify database separation** (recommended)
```bash
just verify-separation  # Checks AsyncTasQ (DB 0) vs Celery (DB 1 & 2)
```

**Step 4: (Optional) Start workers manually**

> The new runner auto-starts scenario-specific workers by default (`--auto-workers`). Only follow the manual steps below if you pass `--no-auto-workers`.

```bash
# Terminal 1: AsyncTasQ worker
just worker-asynctasq

# Terminal 2: Celery worker
just worker-celery
```

**Step 5: Run benchmarks** (new terminal)
```bash
just benchmark-all                # All implemented scenarios with auto-managed workers
just benchmark 1                  # Single scenario
just benchmark-quick              # Quick test (1 run per scenario)
just benchmark --no-auto-workers  # Reuse manually started workers
just benchmark --list-scenarios   # Inspect catalog + requirements
```

**Step 6: Generate reports**
```bash
just report  # HTML report with charts and analysis
```

**Step 7: Cleanup**
```bash
# Stop workers (Ctrl+C in worker terminals)
just docker-down
just docker-clean  # Remove volumes and reset state
```

### Important Notes

**Database Isolation**
- AsyncTasQ: Redis DB 0
- Celery: Redis DB 1 (broker) + DB 2 (results)
- This prevents workers from processing each other's tasks

**Worker Requirements**
- Workers MUST be running before benchmarks start
- Benchmark runner will freeze if workers are not available

**Mock API Server**
- Required for Scenarios 2, 4, 7 (I/O-bound workloads)
- Started with `just docker-up-mock`
- Listens on port 8080

## Architecture

```
asynctasq-benchmark-celery/
├── benchmarks/           # Benchmark scenarios (scenario_*.py)
│   ├── common.py         # Shared utilities (BenchmarkResult, timing)
│   ├── runner.py         # Main benchmark orchestrator
│   └── scenario_*.py     # Individual test scenarios
│
├── tasks/                # Task definitions
│   ├── asynctasq_tasks.py  # AsyncTasQ BaseTask/SyncTask/ProcessTask
│   └── celery_tasks.py     # Celery tasks (prefork/threads)
│
├── infrastructure/       # Docker infrastructure
│   ├── docker-compose.yml  # Redis, Prometheus, Grafana
│   ├── mock_api.py         # FastAPI mock server for I/O tests
│   ├── prometheus/         # Scraping configs
│   └── grafana/            # Dashboard JSONs
│
├── analysis/             # Post-benchmark analysis
│   ├── analyzer.py         # Statistical analysis (t-tests, CV)
│   ├── visualizer.py       # Chart generation (matplotlib)
│   └── report_generator.py # HTML report builder
│
├── results/              # Benchmark outputs
│   ├── *.csv              # Raw timing data
│   ├── *_stats.json       # Statistical summaries
│   └── *_profile.svg      # py-spy flamegraphs
│
└── reports/              # Generated reports
    └── summary_report.html
```

### Scenario Catalog & Worker Profiles

- **Registry:** `benchmarks/scenario_registry.py` defines every scenario with tags, warm-up durations, requirements, and per-framework worker profiles.
- **Auto workers:** The runner reads these profiles to start Celery/AsyncTasQ workers with the appropriate pool (`prefork` for CPU, thread pool for HTTP) and tuned concurrency, matching the guidance from [Mahmud 2025](https://medium.com/@sizanmahmud08/mastering-celery-a-complete-guide-to-task-management-database-connections-and-scaling-417b15eefc07).
- **Future roadmap:** Scenarios 5-11 are documented in the registry even if not implemented yet, so you can plan infrastructure ahead of time or contribute new workloads without touching the orchestrator.

## Benchmark Scenarios

### Overview

11 planned scenarios testing different performance characteristics (currently 4 implemented):

| #   | Scenario            | Description                       | Key Metrics                 | Requirements      |
| --- | ------------------- | --------------------------------- | --------------------------- | ----------------- |
| 1   | Basic Throughput    | 20k minimal tasks                 | tasks/sec, enqueue rate     | Redis only        |
| 2   | I/O-Bound           | HTTP requests with mock server    | async scaling efficiency    | Mock API required |
| 3   | CPU-Bound           | ProcessTask vs prefork            | GIL impact, parallelism     | Redis only        |
| 4   | Mixed Workload      | 60% I/O, 30% light CPU, 10% heavy | realistic performance       | Mock API required |
| 5   | Serialization       | msgpack vs JSON/pickle, ORM       | payload size, speed         | Redis only        |
| 6   | Scalability         | 1k → 100k task ramp               | saturation, queue depth     | Redis only        |
| 7   | Real-World          | E-commerce order pipeline         | end-to-end latency, retries | Mock API required |
| 8   | Cold Start          | Worker initialization             | startup time, first task    | Redis only        |
| 9   | Multi-Queue         | Priority queues, routing          | queue management            | Redis only        |
| 10  | Event Streaming     | Redis Pub/Sub overhead            | event delivery latency      | Redis only        |
| 11  | FastAPI Integration | Lifespan integration              | HTTP dispatch               | Redis only        |

### Execution Models Tested

**AsyncTasQ**
- `BaseTask` - Async I/O operations (coroutines)
- `SyncTask` - Blocking I/O in thread pool
- `ProcessTask` - CPU-bound work in process pool

**Celery**
- `prefork` - Process pool (default, CPU-bound)
- `threads` - Thread pool (I/O-bound)
- `solo` - Single process (cold start testing)

## Configuration

### Environment Variables

**AsyncTasQ** (Redis DB 0)
```bash
ASYNCTASQ_DRIVER=redis
ASYNCTASQ_REDIS_URL=redis://localhost:6379/0
```

**Celery** (Redis DB 1 & 2)
```bash
CELERY_BROKER_URL=redis://localhost:6379/1      # Task queue
CELERY_RESULT_BACKEND=redis://localhost:6379/2  # Results storage
```

**Benchmarking**
```bash
BENCHMARK_RUNS=10                 # Repetitions per scenario
BENCHMARK_WORKERS=10              # Worker count (per-scenario override)
BENCHMARK_WARMUP_SECONDS=30       # Warm-up before metrics
BENCHMARK_OUTPUT_DIR=./results    # Output directory
```

**Monitoring** (optional)
```bash
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
```

### Database Isolation

Separate Redis databases prevent cross-contamination:
- **AsyncTasQ:** DB 0 (tasks only)
- **Celery:** DB 1 (broker) + DB 2 (results)

Verify with `just verify-separation` before running benchmarks.

## Monitoring & Observability

### Grafana Dashboards

Access: `http://localhost:3000` (admin/admin)

**Available Dashboards:**
- **AsyncTasQ Performance** - Throughput, latency histograms, queue depth, worker health, event stream overhead
- **Celery Performance** - Task rate, prefork/thread pool metrics, broker connections, result backend stats
- **System Resources** - CPU, memory, network, disk I/O (per-container breakdown)
- **Comparison View** - Side-by-side AsyncTasQ vs Celery metrics with delta calculations

### Prometheus Metrics

Access: `http://localhost:9090`

**AsyncTasQ Metrics:**
- `asynctasq_tasks_total` - Task completion counter (labels: status, queue)
- `asynctasq_task_duration_seconds` - Execution time histogram (p50/p95/p99)
- `asynctasq_queue_depth` - Current backlog size
- `asynctasq_event_emission_duration_seconds` - Event system overhead

**Celery Metrics:**
- `celery_tasks_total` - Task counter (labels: state, worker)
- `celery_task_duration_seconds` - Task duration histogram
- `celery_worker_pool_*` - Pool utilization metrics

## Command Reference

### Setup & Infrastructure

```bash
just init                     # Install all dependencies
just docker-up                # Start Redis only
just docker-up-monitoring     # Start Redis + Prometheus/Grafana
just docker-up-mock           # Start Redis + Mock API (port 8080)
just docker-down              # Stop all services
just docker-clean             # Remove volumes and reset state
just check-health             # Verify services are running
just verify-separation        # Check database isolation
```

### Workers

```bash
just worker-asynctasq         # Start AsyncTasQ worker
just worker-celery            # Start Celery worker
```

### Benchmarking

```bash
just benchmark-all            # Run all scenarios (10 runs each)
just benchmark 1              # Run specific scenario
just benchmark-quick          # Quick test (1 run per scenario)
just benchmark-stress         # 24-hour soak test
```

### Profiling

```bash
just profile-asynctasq        # py-spy flamegraph for AsyncTasQ
just profile-celery           # py-spy flamegraph for Celery
just profile-memory           # memory_profiler analysis
```

### Analysis & Reporting

```bash
just analyze                  # Statistical analysis (t-tests, CV)
just visualize                # Generate charts (matplotlib/seaborn)
just report                   # Generate full HTML report
```

### Redis Utilities

```bash
just reset-redis              # Flush all databases
just redis-info               # Show Redis stats
just redis-monitor            # Monitor commands in real-time
just docker-logs              # Tail service logs
```

## Results & Analysis

### Expected Performance

Performance targets based on production workloads:

| Metric              | AsyncTasQ Target      | Celery Baseline       |
| ------------------- | --------------------- | --------------------- |
| **I/O Throughput**  | >5,000 tasks/sec      | ~1,500 tasks/sec      |
| **CPU Throughput**  | Match Celery prefork  | Baseline (prefork)    |
| Mean Latency        | <50ms                 | ~200ms                |
| P99 Latency         | <300ms                | ~1000ms               |
| Serialization (ORM) | 90% payload reduction | Manual (N/A)          |
| Worker Memory       | <100MB                | ~150MB (prefork)      |
| Startup Time        | <100ms                | ~500ms (prefork pool) |

### Statistical Significance

- All comparisons include **t-tests** with p < 0.05 threshold
- Report includes **effect size** (Cohen's d) for practical significance
- Confidence intervals: 95% for all metrics

### Full Latency Distribution

- Every run now records an HDR Histogram and surfaces **p99.9** and **p99.99** latencies, matching the methodology recommended by [Brave New Geek](https://bravenewgeek.com/benchmarking-message-queue-latency/) to avoid "average latency" traps.
- Histograms capture up to 10 minutes of latency with 3 significant digits so you can spot long-tail issues that would be invisible in p95-only dashboards.

### Anti-Patterns Documentation

The suite explicitly tests these known anti-patterns for educational purposes:

1. **AsyncTasQ BaseTask + CPU-bound work** → Blocks event loop (5x+ slowdown expected)
2. **Celery threads + heavy CPU** → GIL contention (~1.5x slower than prefork)
3. **Celery + ORM models without serialization** → Stale data issues (documented, not benchmarked)

## Output Files

### Directory Structure

```
results/
├── scenario_1_throughput.csv           # Raw timing data
├── scenario_1_throughput_stats.json    # Statistical summary
├── scenario_1_throughput_profile.svg   # py-spy flamegraph
├── scenario_2_io_bound.csv             # I/O benchmark data
├── ...
└── summary_report.html                 # Full report with charts
```

### CSV Format

```csv
framework,run,task_count,total_time,throughput,mean_latency,p50,p95,p99,memory_mb,cpu_percent
asynctasq,1,20000,3.45,5797.1,12.3,10.2,45.6,89.3,87.4,72.3
asynctasq,2,20000,3.52,5681.8,13.1,10.8,47.2,91.1,88.1,71.8
celery,1,20000,12.34,1620.7,123.4,98.2,456.7,892.1,142.3,68.9
```

### JSON Stats Format

```json
{
  "scenario": "Basic Throughput",
  "scenario_id": "1",
  "asynctasq": {
    "mean_throughput": 5739.4,
    "std_throughput": 58.3,
    "p95_latency": 46.4,
    "cv": 0.01,
    "high_percentiles_ms": {
      "p999": 75.1,
      "p9999": 120.3
    }
  },
  "celery": { ... },
  "t_test": {
    "statistic": 45.2,
    "p_value": 0.0001,
    "significant": true
  }
}
```

## Reproducibility

The suite ensures consistent results across runs:

- **Pinned Docker images** - Redis 8.4, Prometheus 3.1, Grafana 11.4
- **Locked Python deps** - `uv.lock` for exact versions
- **Fixed random seeds** - Reproducible test ordering
- **Warm-up periods** - Eliminate cold-start bias
- **Multiple runs** - Minimum 10 per scenario for variance analysis
- **CV validation** - Coefficient of Variation < 0.15 for result stability

## Why Redis Only?

This suite focuses on Redis because:

1. **Most common deployment** - 80%+ of Celery production uses Redis
2. **Fair comparison** - Both frameworks support Redis natively
3. **Reduced complexity** - Easier to isolate performance differences
4. **Focus on design** - Tests async-first vs process pool architecture

For multi-driver AsyncTasQ benchmarks (PostgreSQL, MySQL, RabbitMQ, AWS SQS), see the main asynctasq repository.

## Development

### Adding New Scenarios

1. Create `benchmarks/scenario_N_description.py`
2. Implement `run_benchmark()` returning `BenchmarkResult`
3. Register metadata + worker profiles in `benchmarks/scenario_registry.py`
4. Update docs/analysis as needed (charts, report text)
5. Run `just ci` to validate (format, lint, typecheck, tests)

### Code Quality

```bash
just ci        # Full validation (MUST pass before committing)
just check     # Quick check (format + lint + typecheck)
just test      # Run all tests
```

### Project Standards

- **Type safety:** Full type hints (pyright strict mode)
- **Code style:** Ruff formatter + linter (line-length: 100)
- **Testing:** pytest with >90% coverage target
- **Async-first:** All I/O uses asyncio (no blocking calls)

## Troubleshooting

### Workers Not Starting
- Check Docker services: `just check-health`
- Verify Redis databases: `just verify-separation`
- Check logs: `just docker-logs`

### Benchmark Hangs
- Ensure workers are running BEFORE benchmarks
- Check queue depth: `just redis-monitor`
- Verify database isolation

### Inconsistent Results
- Increase warm-up period: `BENCHMARK_WARMUP_SECONDS=60`
- Check CV values in stats.json (should be < 0.15)
- Reduce system load (close other applications)

### Mock API Not Responding
- Use `just docker-up-mock` instead of `just docker-up`
- Verify port 8080: `curl http://localhost:8080/health`
- Check logs: `docker logs mock-api`

## References

**Documentation**
- [AsyncTasQ Documentation](../asynctasq/docs/)
- [Infrastructure README](./infrastructure/README.md)

**External Resources**
- [Celery Performance Best Practices](https://docs.celeryq.dev/en/stable/userguide/optimizing.html)
- [Python Queue Benchmark Research](https://github.com/GoodManWEN/python_queue_benchmark)
- [Async vs Threading Performance](https://www.cloudcity.io/blog/2019/02/27/things-i-wish-they-told-me-about-multiprocessing-in-python/)

## License

MIT License - Same license as parent AsyncTasQ project
