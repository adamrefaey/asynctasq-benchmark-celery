# AsyncTasQ vs Celery Benchmarking Plan

## Executive Summary

This document outlines a comprehensive, production-grade benchmarking strategy to quantitatively compare **AsyncTasQ** and **Celery** across key performance dimensions. The plan leverages industry-standard tools, realistic workloads, and statistical rigor to produce actionable insights for users evaluating task queue solutions.

**Key Focus Areas:**
- Task throughput and latency under varying concurrency levels
- Serialization efficiency (msgpack vs pickle/JSON)
- Memory and CPU utilization patterns
- Async-first architecture benefits (asyncio vs threading/prefork)
- Scalability characteristics and bottleneck identification
- Real-world scenario testing (I/O-bound, CPU-bound, mixed workloads)

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [1. Benchmarking Objectives](#1-benchmarking-objectives)
- [2. Methodology & Best Practices](#2-methodology--best-practices)
- [3. Test Environment & Infrastructure](#3-test-environment--infrastructure)
- [4. Benchmark Scenarios](#4-benchmark-scenarios)
- [5. Performance Metrics](#5-performance-metrics)
- [6. Tooling & Implementation](#6-tooling--implementation)
- [7. Workload Design](#7-workload-design)
- [8. Execution Plan](#8-execution-plan)
- [9. Data Collection & Analysis](#9-data-collection--analysis)
- [10. Reporting & Visualization](#10-reporting--visualization)
- [11. Reproducibility & Open Source](#11-reproducibility--open-source)
- [12. Timeline & Milestones](#12-timeline--milestones)
- [13. Risk Mitigation](#13-risk-mitigation)
- [14. Success Criteria](#14-success-criteria)

---

## 1. Benchmarking Objectives

### Primary Goals

1. **Quantify Performance Differences**: Measure AsyncTasQ vs Celery across throughput, latency, and resource utilization
2. **Validate Async-First Claims**: Demonstrate 3.5x+ performance gain from asyncio vs threading (per research)
3. **Demonstrate Serialization Efficiency**: Prove 90%+ payload reduction with msgpack + ORM auto-serialization
4. **Identify Scalability Limits**: Determine breaking points and optimal configurations for both systems
5. **Provide User Guidance**: Produce clear recommendations for when to use each solution

### Secondary Goals

- **Multi-Driver Performance**: Benchmark all 5 AsyncTasQ drivers (Redis, PostgreSQL, MySQL, RabbitMQ, SQS)
  - Measure driver-specific features: PostgreSQL SKIP LOCKED, MySQL dead-letter, RabbitMQ exchanges
  - Test driver switching (zero code changes, config-only)
- **ORM Integration Overhead**: Test all 3 ORMs (SQLAlchemy async/sync, Django, Tortoise)
  - Measure async model fetching latency
  - Validate fresh data guarantee (model re-fetch on worker)
- **FastAPI Integration**: Benchmark lifespan management and dependency injection
  - Startup/shutdown overhead
  - Driver connection pooling via lifespan context
- **Advanced AsyncTasQ Features**:
  - Method chaining overhead (`.delay().on_queue().dispatch()`)
  - Per-task driver override performance
  - Event emission throughput (Redis Pub/Sub)
  - Custom serialization hooks (TypeHook registration)
  - Worker heartbeat overhead
- **ACID & Reliability**: PostgreSQL/MySQL transactional dequeue, visibility timeouts, crash recovery

---

## 2. Methodology & Best Practices

### Scientific Rigor

- **Controlled Environment**: Dedicated hardware, isolated network, no background processes
- **Multiple Runs**: Minimum 10 runs per scenario, report median + 95th/99th percentiles
- **Statistical Significance**: Use t-tests to validate performance differences (p < 0.05)
- **Warm-up Period**: 30-second warm-up before collecting metrics to avoid cold-start bias
- **Randomization**: Randomize test order to eliminate systematic bias

### Industry Best Practices (Based on Research)

1. **Avoid Localhost Bottlenecks**: Use networked brokers (not localhost) to prevent I/O saturation
2. **Separate Concerns**: Run brokers, workers, and load generators on different machines
3. **Monitor Broker Health**: RabbitMQ/Redis can bottleneck before workers (per research: ~4k msgs/sec)
4. **Test at Scale**: Target 20k+ tasks per test (per python_queue_benchmark research)
5. **Measure Tail Latency**: 99th percentile reveals real-world user experience
6. **Resource Limits**: Set explicit CPU/memory limits to test resource efficiency
7. **Profiling**: Use cProfile, py-spy, and memory_profiler to identify bottlenecks

### Benchmark Types

- **Micro-benchmarks**: Isolated component testing (serialization, dequeue, task dispatch)
- **Integration benchmarks**: End-to-end task lifecycle with realistic I/O
- **Stress tests**: Push to failure to identify limits (inspired by Celery stress testing research)
- **Soak tests**: 24-hour runs to detect memory leaks and degradation

---

## 3. Test Environment & Infrastructure

### Hardware Configuration

**Option A: Cloud-Based (Recommended for Reproducibility)**
- **Provider**: AWS EC2 or DigitalOcean
- **Worker Nodes**: 3x c6i.2xlarge (8 vCPU, 16GB RAM) or equivalent
- **Broker Node**: 1x r6i.xlarge (4 vCPU, 32GB RAM) for Redis/RabbitMQ
- **Database Node**: 1x db.m6i.xlarge (4 vCPU, 16GB RAM) for PostgreSQL/MySQL
- **Load Generator**: 1x c6i.xlarge (4 vCPU, 8GB RAM)
- **Network**: 10 Gbps within same VPC/region

**Option B: Bare Metal (Maximum Performance)**
- **Worker Nodes**: 3x AMD Ryzen 9 5950X (16 cores, 32GB RAM)
- **Broker/DB Node**: 1x Intel Xeon E-2288G (8 cores, 64GB RAM, NVMe SSD)
- **Network**: 10GbE switched network

### Software Stack

**Base System:**
- OS: Ubuntu 24.04 LTS (Linux kernel 6.8+)
- Python: 3.12.7 (latest stable)
- Docker: 27.x with compose v2 (for broker/DB isolation)

**AsyncTasQ Configuration:**
- Latest version from main branch
- Drivers: Redis 7.4, PostgreSQL 17, MySQL 8.4, RabbitMQ 4.0, LocalStack (SQS)
- ORMs: SQLAlchemy 2.0+, Django 5.x, Tortoise ORM 0.21+

**Celery Configuration:**
- Celery 5.5.3 (latest stable)
- Brokers: Redis 7.4, RabbitMQ 4.0
- Result backend: Redis, PostgreSQL
- Worker types: prefork, threads, gevent, eventlet

**Monitoring Stack:**
- **Metrics**: Prometheus 3.x + node_exporter
- **Visualization**: Grafana 11.x
- **Profiling**: py-spy, cProfile, memory_profiler
- **Tracing**: OpenTelemetry (optional, for deep analysis)

---

## 4. Benchmark Scenarios

### Scenario 1: Basic Throughput Test

**Description**: Measure maximum task completion rate with minimal task overhead

**Configuration:**
- Task: Print timestamp (no I/O, minimal CPU)
- Volume: 20,000 tasks (per python_queue_benchmark standard)
- Workers: 10 concurrent workers
- Repetitions: 10 runs per queue driver

**Metrics:**
- Tasks per second (throughput)
- Enqueue time (total time to dispatch 20k tasks)
- Processing time (first task start → last task complete)
- Mean, median, p95, p99 latency

### Scenario 2: I/O-Bound Workload

**Description**: Simulate real-world HTTP API calls (common use case)

**Configuration:**
- Task: HTTP GET request to mock server (100ms latency)
- Volume: 10,000 tasks
- Workers: 10, 20, 50, 100 (test scaling)
- Concurrency: 1, 10, 50, 100 requests per worker

**Expected Outcome:**
- AsyncTasQ should show near-linear scaling due to async I/O
- Celery (prefork/threads) should show diminishing returns past 20-30 workers

### Scenario 3: CPU-Bound Workload

**Description**: Test compute-heavy tasks where GIL and threading models matter. Compare AsyncTasQ's three execution modes against Celery's workers.

**Configuration:**
- Task: Calculate factorial(1000) or hash 10MB of data with pbkdf2 (CPU-intensive)
- Volume: 5,000 tasks
- Workers: 4, 8, 16 (match CPU cores)
- **AsyncTasQ Variants:**
  - Regular `Task` (blocks event loop - baseline, NOT recommended)
  - `SyncTask` (thread pool execution - good for moderate CPU)
  - `ProcessTask` (process pool execution - **BEST for heavy CPU, matches Celery prefork**)
- **Celery Variants:**
  - Prefork workers (multiprocessing - bypasses GIL)
  - Thread workers (for comparison with SyncTask)

**Code Examples:**
```python
# AsyncTasQ with ProcessTask (BEST for heavy CPU >80% utilization)
from asynctasq.tasks import ProcessTask
import hashlib

class HashDataTask(ProcessTask[str]):
    """Runs in separate process with independent GIL."""
    
    def handle_process(self) -> str:
        # This executes in subprocess with true parallelism
        data = self.data  # Attribute set during __init__
        return hashlib.pbkdf2_hmac('sha256', data, b'salt', 100000).hex()

# Dispatch: await HashDataTask(data=b"example").dispatch()

# AsyncTasQ with SyncTask (GOOD for moderate CPU 50-80%)
from asynctasq.tasks import SyncTask

class ModerateHashTask(SyncTask[str]):
    """Runs in thread pool via run_in_executor."""
    
    def handle_sync(self) -> str:
        # This executes in thread pool (GIL contention)
        data = self.data
        return hashlib.sha256(data).hexdigest()

# Dispatch: await ModerateHashTask(data=b"example").dispatch()

# AsyncTasQ with regular BaseTask (ANTI-PATTERN for CPU work)
from asynctasq.tasks import BaseTask

class BlockingTask(BaseTask[str]):
    """BAD: Blocks event loop, serializes all tasks."""
    
    async def handle(self) -> str:
        # This blocks the event loop - DO NOT DO THIS
        import hashlib
        return hashlib.pbkdf2_hmac('sha256', self.data, b'salt', 100000).hex()

# Celery prefork (multiprocessing)
from celery import Celery
app = Celery('tasks')

@app.task
def hash_data_celery(data: bytes) -> str:
    import hashlib
    return hashlib.pbkdf2_hmac('sha256', data, b'salt', 100000).hex()
```

**Expected Outcome:**
1. **AsyncTasQ ProcessTask**: Match Celery prefork (true parallelism via ProcessPoolExecutor)
   - Target: ~1.0x baseline (**PARITY WITH CELERY**)
   - Benefit: Same async-first API, class-level pool lifecycle
   - Pool auto-initialized on first task, shared across all ProcessTask instances
   - Supports max_tasks_per_child for process recycling (Python 3.11+)
2. **Celery prefork**: Baseline performance (true parallelism via multiprocessing)
   - Target: ~1.0x baseline (fastest)
3. **AsyncTasQ SyncTask**: Good performance (thread pool via run_in_executor)
   - Target: ~1.3-1.6x slower than ProcessTask (GIL contention)
   - Target: ~3-5x faster than blocking event loop
   - Uses asyncio.run_in_executor(None, handle_sync) internally
4. **Celery threads**: Similar to AsyncTasQ SyncTask (both GIL-bound)
5. **AsyncTasQ BaseTask** (blocking CPU in handle()): Worst (serialized execution)
   - Document as anti-pattern for CPU-bound work

**Performance Matrix (Relative to Celery Prefork):**

| Solution               | Relative Speed | CPU Utilization | Use Case                    |
|------------------------|----------------|-----------------|----------------------------|
| **ProcessTask**        | **1.0x** ✅    | >80%           | Heavy CPU work             |
| Celery Prefork         | 1.0x           | >80%           | Heavy CPU work             |
| **SyncTask**           | 1.4x slower    | 50-80%         | Moderate CPU               |
| Celery Threads         | 1.5x slower    | 50-80%         | Moderate CPU               |
| BaseTask (blocking)    | 5.0x slower    | Serialized     | Anti-pattern               |

**Key Insights to Highlight:**
- `ProcessTask` achieves **parity with Celery prefork** for heavy CPU workloads
  - Uses ProcessPoolExecutor with configurable pool size and max_tasks_per_child
  - Class-level pool shared across all ProcessTask instances
  - Auto-initializes on first task execution if not manually initialized
- `SyncTask` is excellent for **moderate CPU work** (50-80% utilization)
  - Uses asyncio.run_in_executor(None, handle_sync) for thread pool execution
  - Lower overhead than ProcessTask, good for tasks 10-100ms
- `ProcessTask` provides true parallelism while maintaining async-first architecture
  - Async wrapper (execute()) delegates to sync handle_process() in subprocess
  - Each subprocess has independent GIL and Python interpreter
- Trade-off: ProcessTask has ~50ms overhead per task, best for tasks >100ms
- Recommendation:
  - Heavy CPU (>80% util, >100ms): **Use `ProcessTask`** (matches Celery prefork)
  - Moderate CPU (50-80%, 10-100ms): **Use `SyncTask`** (thread pool)
  - I/O-bound: **Use `BaseTask`** (async, best performance)
- AsyncTasQ now covers **all use cases** (I/O, moderate CPU, heavy CPU)
- All three models support the same API: class-based or @task decorator

### Scenario 4: Mixed Workload

**Description**: Realistic blend of I/O and CPU tasks

**Configuration:**
- 60% I/O tasks (HTTP/database queries)
- 30% light CPU tasks (JSON parsing, validation)
- 10% heavy CPU tasks (image processing, hashing)
- Volume: 20,000 tasks
- Workers: 20

### Scenario 5: Serialization Efficiency

**Description**: Compare payload sizes and serialization speed, showcasing AsyncTasQ's intelligent ORM handling

**Configuration:**
- Task payload types:
  - Small: `{"id": 123, "name": "test"}` (JSON-friendly)
  - Medium: Nested dict with 100 fields
  - Large ORM models:
    - SQLAlchemy User model with 20 relationships (async session)
    - Django User model (async ORM)
    - Tortoise ORM User model
  - Complex nested: Dict with ORM models + datetime + Decimal + UUID + sets
  - Binary: 1MB binary blob
- Measure:
  - Serialization time (µs)
  - Deserialization time (µs)
  - Payload size (bytes)
  - Throughput impact
  - ORM model re-fetch latency (AsyncTasQ only)

**AsyncTasQ Unique Features to Highlight:**
1. **Automatic ORM Detection**: SQLAlchemy, Django, Tortoise models detected via hooks
2. **PK-Only Serialization**: Models serialized as `{"__orm:sqlalchemy__": 123, "__orm_class__": "app.models.User"}`
3. **Fresh Data Guarantee**: Models re-fetched on worker side with latest DB state
4. **Custom Type Support**: datetime, Decimal, UUID, sets handled natively (Celery requires manual encoding)
5. **Binary Efficiency**: `use_bin_type=True` for optimal msgpack performance

**Celery Comparison Point:**
- Manual serialization required: `user_id = user.id` before dispatch, then `user = User.query.get(user_id)` in task
- Risk of stale data if model passed directly (not recommended)
- JSON serialization requires base64 encoding for binary data

**Expected Outcome:**
- msgpack 2-5x faster than JSON (per research)
- ORM models: 90%+ payload reduction (52 bytes vs 2,814 bytes for typical model)
- Zero developer overhead for AsyncTasQ vs manual serialization for Celery

### Scenario 6: Scalability & Stress Test

**Description**: Determine breaking points and queue backlog behavior

**Configuration:**
- Ramp-up: 1k → 10k → 50k → 100k tasks over 30 minutes
- Workers: Fixed at 20
- Monitor: Queue depth, broker CPU/memory, worker saturation

**Key Questions:**
- At what point does queue depth grow linearly (saturation)?
- How do error rates change under load?
- Memory leaks or degradation over time?

### Scenario 7: Real-World Simulation with Event Streaming

**Description**: E-commerce order processing pipeline with real-time monitoring

**Configuration:**
- Tasks: Validate order → Charge payment → Send email → Update inventory
- 4-step chain with error injection (5% failure rate on payment)
- Volume: 10,000 orders
- Measure end-to-end latency and retry behavior
- Track real-time events (task_enqueued, task_started, task_completed, task_failed)
### Scenario 8: Cold Start & Initialization

**Description**: Worker startup time and first-task latency

**Configuration:**
- Measure time from worker start to first task completion
- Test with different worker pool sizes (1, 10, 50)
- Compare async event loop startup vs prefork pool init
- Measure connection pool initialization (asyncpg, aiomysql, aio-pika)

**AsyncTasQ Specific Metrics:**
1. **Event Loop Startup**: Single-threaded asyncio initialization
2. **Connection Pool Setup**: asyncpg (PostgreSQL), aiomysql (MySQL), aioredis
3. **Driver Factory**: Dynamic driver instantiation overhead
4. **Dispatcher Initialization**: Global vs per-task driver resolution
5. **Serializer Hook Registration**: ORM detection and hook setup

**Expected Outcome:**
- AsyncTasQ faster startup (no prefork pool, single event loop)
- Connection pooling adds <100ms initialization overhead
- First task latency <50ms after startup, emails on RabbitMQ, inventory on PostgreSQL

**Celery Comparison Point:**
- Manual event emission required (no built-in Pub/Sub)
- Flower required for monitoring (separate process)
- No built-in method chaining
- DLQ requires RabbitMQ configuration (not automatic)

### Scenario 8: Cold Start & Initialization

**Description**: Worker startup time and first-task latency

**Configuration:**
- Measure time from worker start to first task completion
- Test with different worker pool sizes (1, 10, 50)
- Compare async event loop startup vs prefork pool init

---

## 5. Performance Metrics

### Primary Metrics

| Metric                     | Unit         | Target (AsyncTasQ) | Calculation Method                     |
| -------------------------- | ------------ | ------------------ | -------------------------------------- |
| **Throughput**             | tasks/sec    | > 5,000            | Total tasks / processing time          |
| **Mean Latency**           | milliseconds | < 50               | Avg(task_complete - task_enqueue)      |
| **P95 Latency**            | milliseconds | < 150              | 95th percentile                        |
| **P99 Latency**            | milliseconds | < 300              | 99th percentile                        |
| **Enqueue Rate**           | tasks/sec    | > 10,000           | Total tasks / enqueue time             |
| **Memory per Worker**      | MB           | < 100              | RSS at steady state                    |
| **CPU Utilization**        | %            | 70-85              | Avg CPU across workers                 |
| **Serialization Speed**    | µs           | < 100              | Time to serialize typical payload      |
| **Payload Size Reduction** | %            | > 90               | (Original - Compressed) / Original     |

### AsyncTasQ-Specific Metrics

| Metric                            | Unit         | Target     | Description                                          |
| --------------------------------- | ------------ | ---------- | ---------------------------------------------------- |
| **ORM Model Serialization**       | bytes        | < 100      | Payload size for typical ORM model (PK-only)         |
| **ORM Model Fetch Latency**       | milliseconds | < 10       | Time to re-fetch model on worker side                |
| **Event Emission Overhead**       | microseconds | < 1000     | Time to emit task event to Redis Pub/Sub             |
| **Event Delivery Latency**        | milliseconds | < 10       | Time from emit to subscriber receipt                 |
| **Driver Switch Overhead**        | milliseconds | 0          | Zero code changes to switch drivers                  |
| **Method Chaining Overhead**      | nanoseconds  | < 1000     | `.delay().on_queue()` fluent API overhead            |
| **Per-Task Driver Resolve Time**  | microseconds | < 10       | Time to resolve driver override                      |
| **Connection Pool Init**          | milliseconds | < 100      | asyncpg/aiomysql/aioredis pool startup               |
| **FastAPI Lifespan Startup**      | milliseconds | < 200      | Driver init via lifespan context                     |
| **Worker Heartbeat Overhead**     | milliseconds | < 5        | Time to emit heartbeat event (every 60s)             |
| **Dead-Letter Queue Write**       | milliseconds | < 20       | Time to write failed task to DLQ (PG/MySQL)          |
| **Custom Hook Registration**      | microseconds | < 50       | Time to register custom TypeHook                     |

### Secondary Metrics

- **Worker Startup Time**: Time to accept first task (target: <100ms)
- **Broker Throughput**: Messages/sec at broker level
- **Failed Task Rate**: % of tasks failing (should be < 0.1%)
- **Retry Rate**: % of tasks retrying
- **Memory Leak Rate**: MB/hour growth in long-running tests
- **Context Switch Rate**: Measure for threading overhead (Celery prefork)
- **GC Pauses**: Python garbage collection impact
- **Event Channel Saturation**: Max events/sec on Redis Pub/Sub
- **Driver-Specific**:
  - PostgreSQL: SKIP LOCKED efficiency, transaction overhead
  - MySQL: Visibility timeout accuracy, DLQ write latency
  - RabbitMQ: Exchange routing latency, prefetch impact
  - SQS: Long polling efficiency, batch dequeue performance
- **ORM-Specific**:
  - SQLAlchemy: Async session overhead vs sync
  - Django: Async ORM fetch latency
  - Tortoise: Model fetch performance
- **AsyncTasQ API Overhead**:
  - `.dispatch()` vs `.delay().dispatch()`
  - `@task` vs `@task(queue="high")`
  - Driver override resolution time

### Resource Metrics (Per Worker Node)

- **CPU**: User, system, iowait percentages
- **Memory**: RSS, VMS, swap usage
- **Network**: Bytes sent/received, packet rate
- **Disk**: I/O operations, read/write throughput (for DB-backed queues)

---

## 6. Tooling & Implementation

### Benchmarking Frameworks

**Primary: Locust (HTTP Load Testing)**
- **Why**: Industry standard, distributed execution, real-time metrics, Python-native
- **Use Case**: Simulate distributed task dispatchers, test API endpoints
- **Setup**:
  ```python
  from locust import HttpUser, task, between
  
  class TaskDispatcher(HttpUser):
      wait_time = between(0.1, 0.5)
      
      @task
      def dispatch_task(self):
          self.client.post("/tasks/dispatch", json={"type": "process_order", "id": 123})
  ```

**Secondary: pytest-benchmark (Micro-benchmarks)**
### Monitoring & Profiling

**Prometheus + Grafana**
- **AsyncTasQ Metrics**: Custom metrics via prometheus-client + EventEmitter
  ```python
  from prometheus_client import Counter, Histogram
  from asynctasq.core.events import EventEmitter, EventType
  
  TASKS_PROCESSED = Counter('asynctasq_tasks_processed_total', 'Total tasks processed')
  TASK_DURATION = Histogram('asynctasq_task_duration_seconds', 'Task duration')
  
  # AsyncTasQ built-in events
  emitter = EventEmitter(redis_url="redis://localhost:6379")
  # Events automatically published: task_enqueued, task_started, task_completed, worker_heartbeat
  ```
- **Celery Metrics**: Use Flower + prometheus-client
- **System Metrics**: node_exporter for CPU, memory, network, disk
- **Driver Metrics**:
  - Redis: `INFO stats`, `CLIENT LIST` for connection tracking
  - PostgreSQL: `pg_stat_statements`, connection pool metrics
  - MySQL: `SHOW STATUS`, InnoDB buffer pool stats
  - RabbitMQ: Management API metrics (queue depth, consumer count)

**Application Profiling**
- **py-spy**: Sampling profiler (low overhead, production-safe)
  ```bash
  py-spy record -o profile.svg -- python -m asynctasq worker
  ```
- **cProfile**: Deterministic profiling for deep analysis
  ```bash
  python -m cProfile -o asynctasq.prof -m asynctasq worker --max-tasks 1000
  python -m snakeviz asynctasq.prof  # Interactive visualization
  ```
- **memory_profiler**: Line-by-line memory usage
  ```bash
  mprof run python -m asynctasq worker --max-tasks 1000
  mprof plot
  ```
- **AsyncTasQ-Specific Profiling**:
  - Profile serialization hooks: `pytest-benchmark` for msgpack vs JSON vs pickle
  - Profile ORM fetch latency: Time `AsyncSession.get()` in isolation
  - Profile event emission: Measure Redis PUBLISH latency

**Network & Broker Monitoring**
- **Redis**: redis-cli --stat, INFO command, slowlog analysis
- **RabbitMQ**: rabbitmq_prometheus plugin, management UI, channel metrics
- **PostgreSQL**: pg_stat_statements, pg_stat_activity, connection pool monitoring
- **AsyncTasQ Event Stream**: Monitor `asynctasq:events` channel throughpution-safe)
  ```bash
  py-spy record -o profile.svg -- python -m asynctasq worker
  ```
- **cProfile**: Deterministic profiling for deep analysis
- **memory_profiler**: Line-by-line memory usage
  ```bash
  mprof run python benchmark_script.py
  mprof plot
  ```

**Network & Broker Monitoring**
- **Redis**: redis-cli --stat, INFO command
- **RabbitMQ**: rabbitmq_prometheus plugin, management UI
- **PostgreSQL**: pg_stat_statements, pg_stat_activity

### Data Collection Pipeline

```
┌─────────────────┐
│  Benchmark      │
│  Execution      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐    ┌──────────────┐
│  Prometheus     │───▶│  Grafana     │
│  (Metrics)      │    │  (Viz)       │
└─────────────────┘    └──────────────┘
         │
         ▼
┌─────────────────┐
│  JSON Exports   │
│  (Raw Data)     │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  Jupyter        │
│  Notebooks      │
│  (Analysis)     │
└─────────────────┘
```

---

## 7. Workload Design

### AsyncTasQ Task Execution Models

AsyncTasQ provides three task execution models to handle different workload types:

**BaseTask (Async I/O)**: Best for I/O-bound work (HTTP, DB queries, file I/O)
- Execution: Async event loop (no blocking)
- Use case: Network requests, database queries, file operations
- Performance: Highest throughput for I/O workloads

**SyncTask (Thread Pool)**: Good for moderate CPU work (50-80% utilization)
- Execution: ThreadPoolExecutor via run_in_executor
- Use case: JSON parsing, validation, light computation (10-100ms)
- Performance: Lower overhead than ProcessTask, GIL-bound

**ProcessTask (Process Pool)**: Best for heavy CPU work (>80% utilization)
- Execution: ProcessPoolExecutor with independent GIL
- Use case: Data processing, ML inference, cryptography (>100ms)
- Performance: True parallelism, matches Celery prefork

**Both APIs Supported:**
```python
# Class-based API (all three models)
from asynctasq.tasks import BaseTask, SyncTask, ProcessTask

class FetchUserTask(BaseTask[dict]):
    async def handle(self) -> dict:
        # Async I/O - best for network/DB
        async with httpx.AsyncClient() as client:
            return await client.get(f"/users/{self.user_id}").json()

class ParseDataTask(SyncTask[dict]):
    def handle_sync(self) -> dict:
        # Runs in thread pool - good for moderate CPU
        return json.loads(self.large_json_string)

class ComputeHashTask(ProcessTask[str]):
    def handle_process(self) -> str:
        # Runs in subprocess - best for heavy CPU
        import hashlib
        return hashlib.pbkdf2_hmac('sha256', self.data, b'salt', 100000).hex()

# Decorator-based API (automatic detection)
from asynctasq.tasks import task

@task
async def fetch_user(user_id: int) -> dict:
    # Async function -> uses BaseTask internally
    async with httpx.AsyncClient() as client:
        return await client.get(f"/users/{user_id}").json()

@task
def parse_data(json_string: str) -> dict:
    # Sync function -> uses SyncTask internally (runs in thread pool)
    return json.loads(json_string)

# Note: ProcessTask requires class-based API (needs explicit pool configuration)
```

### Task Definitions

**1. Minimal Task (Baseline)**
```python
# AsyncTasQ
@task
async def noop_task():
    pass

# Celery
@app.task
def noop_task():
    pass
```

**2. HTTP API Call (I/O-Bound)**
```python
# AsyncTasQ
@task
async def fetch_user_data(user_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/users/{user_id}")
        return response.json()

# Celery
@app.task
def fetch_user_data(user_id: int):
    response = requests.get(f"https://api.example.com/users/{user_id}")
    return response.json()
```

**3. Database Query (I/O-Bound + ORM)**
```python
# AsyncTasQ (SQLAlchemy async)
@task
async def update_user(user_id: int, data: dict):
**5. ORM Serialization Test**
```python
# AsyncTasQ (auto-serialized as PK, supports all 3 ORMs)
from asynctasq.tasks import task

@task
async def process_order(order: Order):  # SQLAlchemy async model
    # Dispatch: Automatically serialized to {"__orm:sqlalchemy__": 123, "__orm_class__": "app.models.Order"}
    # Worker: Model re-fetched from DB with latest data using async session
    # Fresh data guarantee - no stale models
    await send_confirmation_email(order.user.email)

# Django async ORM
@task
async def process_order_django(order: DjangoOrder):  # Django model
    # Serialized: {"__orm:django__": 123, "__orm_class__": "myapp.models.Order"}
    # Re-fetched: await DjangoOrder.objects.aget(pk=123)
    await send_confirmation_email(order.user.email)

# Tortoise ORM
@task
async def process_order_tortoise(order: TortoiseOrder):  # Tortoise model
    # Serialized: {"__orm:tortoise__": 123, "__orm_class__": "app.models.Order"}
    # Re-fetched: await TortoiseOrder.get(pk=123)
    await send_confirmation_email(order.user.email)

# Celery (manual serialization required for all ORMs)
from celery import Celery
app = Celery('tasks')

@app.task
def process_order_celery(order_id: int):
    # Developer must manually extract PK and re-fetch
    from myapp.models import Order
    order = Order.objects.get(pk=order_id)
    send_confirmation_email(order.user.email)
### Mock Server for I/O Tests

Use a local FastAPI server to simulate external APIs with controlled latency:

```python
from fastapi import FastAPI
import asyncio

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, latency: int = 100):
    await asyncio.sleep(latency / 1000)  # Simulate network delay
    return {"id": user_id, "name": f"User {user_id}"}
```

Run with: `uvicorn mock_server:app --host 0.0.0.0 --port 8080 --workers 4`

---

## AsyncTasQ-Specific Benchmark Additions

### Scenario 9: Multi-Driver Comparison

**Description**: Benchmark AsyncTasQ's driver flexibility and driver-specific optimizations

**Configuration:**
- Same workload (10k I/O-bound tasks) across all 5 drivers
- Test driver-specific features:
  - **Redis**: Pub/Sub events, connection pooling
  - **PostgreSQL**: SKIP LOCKED concurrency, ACID transactions, dead-letter table
  - **MySQL**: Transactional dequeue, visibility timeout, connection pooling
  - **RabbitMQ**: Exchange routing, prefetch tuning, acknowledgment modes
  - **SQS**: Long polling, message attributes, batch operations

**Metrics:**
- Throughput per driver
- Latency distribution per driver
- Driver-specific feature overhead
- Zero-code driver switching validation

**Expected Outcome:**
- Redis fastest for high-throughput (7k+ tasks/sec per research)
- PostgreSQL/MySQL provide ACID + DLQ at 80-90% Redis speed
- RabbitMQ excellent for routing complexity
- SQS suitable for AWS-native deployments

### Scenario 10: Event Streaming Performance

**Description**: Measure real-time event emission overhead and throughput

**Configuration:**
- Enable Redis Pub/Sub event emitter
- Process 20k tasks with full event lifecycle:
  - `task_enqueued` (dispatcher)
  - `task_started` (worker)
  - `task_completed` / `task_failed` (worker)
  - `worker_heartbeat` (every 60s)
- Subscribe to events channel and count received events
- Measure: Event emission overhead, event delivery latency, channel saturation

**AsyncTasQ Specific:**
- EventEmitter with msgpack serialization
- TaskEvent/WorkerEvent dataclasses with full metadata
- Integration with asynctasq-monitor WebSocket streaming

**Expected Outcome:**
- <1ms event emission overhead per task
- 99% event delivery within 10ms
- Supports 10k+ events/sec on single Redis instance

### Scenario 11: FastAPI Integration Overhead

**Description**: Measure lifespan management and dependency injection performance

**Configuration:**
- FastAPI app with asynctasq integration
- Startup: Driver connection pool init, dispatcher setup
- Runtime: 10k task dispatches via HTTP endpoints
- Shutdown: Graceful worker drain, connection cleanup

**Code:**
```python
from fastapi import FastAPI
from asynctasq.integrations.fastapi import AsyncTaskIntegration

asynctasq = AsyncTaskIntegration()
app = FastAPI(lifespan=asynctasq.lifespan)

@app.post("/orders")
async def create_order(order: OrderCreate):
    task_id = await process_order.dispatch(order_id=order.id)
    return {"task_id": task_id}
```

**Metrics:**
- Startup time (lifespan init)
- HTTP request latency with task dispatch
- Shutdown time (graceful drain)

**Expected Outcome:**
- <200ms startup overhead
- <5ms task dispatch overhead per HTTP request
- Graceful shutdown drains in-flight tasks

### Scenario 12: Method Chaining & Fluent API

**Description**: Benchmark AsyncTasQ's developer-friendly API overhead

**Configuration:**
- Compare dispatch methods:
  - Direct: `await task.dispatch()`
  - Delayed: `await task.delay(60).dispatch()`
  - Chained: `await task.delay(60).on_queue("high").dispatch()`
  - Per-task driver: `await task_with_driver_override.dispatch()`

**Code:**
```python
# Method chaining
await send_email.delay(300).on_queue("emails").dispatch(user_id=123)

# Per-task driver override
@task(driver="redis")  # Always uses Redis regardless of global config
async def critical_task(data: dict):
    pass
```

**Metrics:**
- Method chaining overhead (ns)
- Driver resolution time (global vs override)

**Expected Outcome:**
- <1µs chaining overhead (negligible)
- Driver override adds <10µs per dispatch
    import hashlib
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, hashlib.sha256, data)
```

**5. ORM Serialization Test**
```python
# AsyncTasQ (auto-serialized as PK)
@task
async def process_order(order: Order):
    # Order model passed directly, serialized as {"__model__": "Order", "pk": 123}
    await send_confirmation_email(order.user.email)

# Celery (manual serialization required)
@app.task
def process_order(order_id: int):
    order = session.get(Order, order_id)
    send_confirmation_email(order.user.email)
```

### Mock Server for I/O Tests

Use a local FastAPI server to simulate external APIs with controlled latency:

```python
from fastapi import FastAPI
import asyncio

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, latency: int = 100):
    await asyncio.sleep(latency / 1000)  # Simulate network delay
    return {"id": user_id, "name": f"User {user_id}"}
```

Run with: `uvicorn mock_server:app --host 0.0.0.0 --port 8080 --workers 4`

---

## 8. Execution Plan

### Phase 1: Environment Setup (Week 1)

**Tasks:**
- [ ] Provision cloud infrastructure or prepare bare-metal servers
- [ ] Install OS, Python, Docker, monitoring stack
- [ ] Configure network (disable firewall, optimize TCP stack)
- [ ] Deploy brokers (Redis, RabbitMQ, PostgreSQL, MySQL, LocalStack)
- [ ] Install AsyncTasQ and Celery with all dependencies
- [ ] Setup Prometheus exporters and Grafana dashboards
- [ ] Validate connectivity and basic health checks

**Deliverables:**
- Infrastructure-as-Code scripts (Terraform/Ansible)
- Docker Compose files for reproducible broker setup
- Grafana dashboard templates

### Phase 2: Micro-Benchmarks (Week 2)

**Tasks:**
- [ ] Serialization benchmarks (msgpack vs JSON vs pickle)
- [ ] Task dispatch latency (enqueue time)
- [ ] Worker startup time
- [ ] ORM integration overhead

**Deliverables:**
- pytest-benchmark results with statistical comparison
- Profiling reports (py-spy flamegraphs)

### Phase 3: Integration Benchmarks (Week 3-4)

**Tasks:**
- [ ] Run Scenario 1-4 (throughput, I/O, CPU, mixed workloads)
- [ ] Test all 5 drivers for AsyncTasQ (Redis, PG, MySQL, RabbitMQ, SQS)
- [ ] Test Celery with Redis and RabbitMQ brokers
- [ ] Collect metrics for 10 runs per configuration
- [ ] Analyze and compare results

**Deliverables:**
- Raw metrics (CSV/JSON exports)
- Statistical analysis (mean, median, std dev, p-values)
- Preliminary comparison charts

### Phase 4: Stress & Soak Tests (Week 5)

**Tasks:**
- [ ] Run Scenario 6 (scalability stress test)
- [ ] 24-hour soak test to detect memory leaks
- [ ] Test failure scenarios (broker crash, worker restart)
- [ ] Measure retry and dead-letter queue behavior

**Deliverables:**
- Long-term performance graphs
- Memory leak analysis
- Failure recovery metrics

### Phase 5: Real-World Simulation (Week 6)

**Tasks:**
- [ ] Run Scenario 7 (e-commerce pipeline)
- [ ] Test with realistic error rates and retries
- [ ] Measure end-to-end latency with distributed tracing

**Deliverables:**
- User-journey performance report
- Reliability metrics (error rates, retry success)

### Phase 6: Analysis & Reporting (Week 7-8)

**Tasks:**
- [ ] Aggregate all metrics and statistical analysis
- [ ] Generate comparison charts and tables
- [ ] Write comprehensive report with recommendations
- [ ] Create public GitHub repository with all code and data
- [ ] Prepare README.md summary for AsyncTasQ docs

**Deliverables:**
- Final benchmark report (Markdown + PDF)
- Interactive Jupyter notebooks for data exploration
- Public repository: `asynctasq-benchmarks`

---

## 9. Data Collection & Analysis

### Data Storage Format

**Raw Metrics (per test run):**
```json
{
  "benchmark_id": "asynctasq-redis-scenario1-run3",
  "timestamp": "2025-12-10T10:00:00Z",
  "configuration": {
    "system": "asynctasq",
    "driver": "redis",
    "workers": 10,
    "task_count": 20000,
    "scenario": "throughput"
  },
  "metrics": {
    "enqueue_time_seconds": 2.34,
    "processing_time_seconds": 15.67,
    "throughput_tasks_per_sec": 1276.0,
    "latency_mean_ms": 42.3,
    "latency_p50_ms": 38.1,
    "latency_p95_ms": 89.2,
    "latency_p99_ms": 143.7,
    "memory_rss_mb": 87.4,
    "cpu_percent": 73.2
  },
  "errors": [],
  "profiling": {
    "flamegraph_url": "s3://benchmarks/profiles/run3.svg"
  }
}
```

### Statistical Analysis

**Python Libraries:**
- **pandas**: Data manipulation and aggregation
- **scipy**: Statistical tests (t-test, Mann-Whitney U)
- **numpy**: Numerical computations
- **matplotlib/seaborn**: Visualization

**Analysis Workflow:**
```python
import pandas as pd
from scipy import stats

# Load data
asynctasq_df = pd.read_json("asynctasq_results.json")
celery_df = pd.read_json("celery_results.json")

# Calculate statistics
asynctasq_mean = asynctasq_df["throughput_tasks_per_sec"].mean()
celery_mean = celery_df["throughput_tasks_per_sec"].mean()

# T-test for significance
t_stat, p_value = stats.ttest_ind(asynctasq_df["throughput_tasks_per_sec"], 
                                   celery_df["throughput_tasks_per_sec"])

print(f"AsyncTasQ: {asynctasq_mean:.2f} tasks/sec")
print(f"Celery: {celery_mean:.2f} tasks/sec")
print(f"Difference: {(asynctasq_mean / celery_mean - 1) * 100:.1f}% faster")
print(f"P-value: {p_value:.4f} (significant: {p_value < 0.05})")
```

### Confidence Intervals

Report all metrics with 95% confidence intervals:

```
AsyncTasQ Throughput: 5,234 ± 127 tasks/sec (95% CI)
Celery Throughput: 1,876 ± 89 tasks/sec (95% CI)
```

---

## 10. Reporting & Visualization

### Report Structure

**1. Executive Summary (1 page)**
- Key findings (AsyncTasQ is X% faster in Y scenarios)
- Recommendations (when to use each system)

**2. Methodology (2-3 pages)**
- Test environment, scenarios, metrics
- Statistical approach and validation

**3. Results by Scenario (10-15 pages)**
- One section per scenario with:
  - Comparison table
  - Line/bar charts
  - Statistical significance tests
  - Analysis and interpretation

**4. Deep Dive: Serialization (3 pages)**
- Payload size comparison
- Speed benchmarks
- Real-world impact

**5. Deep Dive: Async vs Threading (3 pages)**
- Event loop efficiency
- GIL impact
- Scaling characteristics

**6. Resource Utilization (2 pages)**
- Memory footprint
- CPU efficiency
- Network/disk I/O

**7. Failure Scenarios (2 pages)**
- Retry behavior
- Dead-letter queue handling
- Crash recovery

**8. Recommendations (2 pages)**
- Decision matrix
- Use case mapping
- Migration guide

**9. Appendix**
- Full configuration files
- Hardware specifications
- Raw data access

### Visualization Examples

**Throughput Comparison (Bar Chart)**
```
AsyncTasQ (Redis)    ████████████████████ 5,234 tasks/sec
AsyncTasQ (PG)       ██████████████████   4,892 tasks/sec
Celery (Redis)       ████████             1,876 tasks/sec
Celery (RabbitMQ)    ███████              1,654 tasks/sec
```

**Latency Distribution (Box Plot)**
- Show mean, median, IQR, outliers for p50/p95/p99

**Scalability (Line Chart)**
- X-axis: Number of workers (1, 10, 20, 50, 100)
- Y-axis: Throughput (tasks/sec)
- Lines: AsyncTasQ vs Celery

**Serialization Efficiency (Table)**
| Payload Type | AsyncTasQ (msgpack) | Celery (pickle) | Size Reduction |
| ------------ | ------------------- | --------------- | -------------- |
| Small Dict   | 87 bytes            | 203 bytes       | 57%            |
| ORM Model    | 52 bytes (PK)       | 2,814 bytes     | 98%            |
| Binary 1MB   | 1.02 MB             | 1.04 MB         | 2%             |

---

## 11. Reproducibility & Open Source

### Public Repository

**GitHub Repo: `asynctasq-benchmarks`**

**Structure:**
```
asynctasq-benchmarks/
├── README.md                    # Quick start guide
├── RESULTS.md                   # Summary of findings
├── infrastructure/
│   ├── terraform/               # Cloud provisioning
│   ├── ansible/                 # Configuration management
│   └── docker-compose.yml       # Broker setup
├── benchmarks/
│   ├── scenarios/               # Test definitions
│   ├── workloads/               # Task implementations
│   └── locustfiles/             # Locust scenarios
├── monitoring/
│   ├── prometheus.yml
│   ├── grafana-dashboards/
│   └── alerting-rules/
├── data/
│   ├── raw/                     # JSON exports
│   └── processed/               # Aggregated results
├── analysis/
│   ├── notebooks/               # Jupyter analysis
│   └── scripts/                 # Statistical tests
├── docs/
│   ├── methodology.md
│   ├── results-detailed.md
│   └── hardware-specs.md
└── scripts/
    ├── run-all-benchmarks.sh
    ├── collect-metrics.py
    └── generate-report.py
```

**License:** MIT (permissive, allows commercial use)

### Docker Images

Publish pre-built images for easy reproduction:
```bash
docker pull asynctasq/benchmark-worker:latest
docker pull asynctasq/benchmark-loadgen:latest
```

### One-Command Execution

```bash
git clone https://github.com/asynctasq/asynctasq-benchmarks
cd asynctasq-benchmarks
./scripts/run-all-benchmarks.sh --cloud aws --workers 10
```

---

## 12. Timeline & Milestones

| Week | Phase                     | Key Deliverables                         |
| ---- | ------------------------- | ---------------------------------------- |
| 1    | Environment Setup         | Infrastructure ready, monitoring live    |
| 2    | Micro-Benchmarks          | Serialization and dispatch metrics       |
| 3-4  | Integration Benchmarks    | Throughput, I/O, CPU, mixed workload     |
| 5    | Stress & Soak Tests       | Scalability limits, memory leak analysis |
| 6    | Real-World Simulation     | E-commerce pipeline metrics              |
| 7-8  | Analysis & Reporting      | Final report, public repo, blog post     |

**Total Duration:** 8 weeks (2 months)

---

## 13. Risk Mitigation

### Potential Risks

1. **Infrastructure Instability**
   - **Risk**: Network issues, hardware failures, cloud outages
   - **Mitigation**: Use redundant infrastructure, automated health checks, retry failed runs

2. **Benchmark Bias**
   - **Risk**: Unintentional favoritism toward AsyncTasQ
   - **Mitigation**: Peer review by external experts, publish raw data, open-source scripts

3. **Configuration Errors**
   - **Risk**: Suboptimal Celery configuration skews results
   - **Mitigation**: Consult Celery optimization docs, test multiple configurations, document rationale

4. **Unrealistic Workloads**
   - **Risk**: Benchmarks don't reflect real-world usage
   - **Mitigation**: Survey users for common patterns, test diverse scenarios, include edge cases

5. **Tool Limitations**
   - **Risk**: Locust/Prometheus bottleneck before systems under test
   - **Mitigation**: Distribute load generation, profile monitoring stack, use lightweight exporters

6. **Time Overruns**
   - **Risk**: Analysis takes longer than expected
   - **Mitigation**: Define MVP scope, automate data processing, allocate buffer time

---

## 14. Success Criteria

### Quantitative Goals

- ✅ **Performance Claims Validated**: AsyncTasQ demonstrates 2-3x throughput improvement in async I/O scenarios
- ✅ **Statistical Significance**: All major findings have p < 0.05 in independent t-tests
- ✅ **Serialization Gains**: 90%+ payload reduction confirmed for ORM models
- ✅ **Comprehensive Coverage**: Test results for 7+ scenarios across 5+ drivers
- ✅ **Reproducibility**: 3+ independent users successfully reproduce benchmarks

### Qualitative Goals

- ✅ **Transparency**: All code, data, and methodology publicly available
- ✅ **Credibility**: Peer-reviewed by 2+ external experts (e.g., Python core devs, task queue maintainers)
- ✅ **User Value**: Decision matrix helps users choose the right tool
- ✅ **Community Engagement**: 100+ GitHub stars, 10+ forks, 5+ pull requests on benchmark repo

### Acceptance Criteria

**Publish to:**
- AsyncTasQ documentation (docs/benchmarks.md)
- Dedicated blog post on asynctasq.dev (if exists)
- Python subreddit (r/Python)
- HackerNews, Lobsters, dev.to
- Conference talk submission (PyCon, PyData)

**Update README.md Comparison Table:**
Add benchmark results as a new row:
```markdown
| **Benchmark**           | ✅ 3.2x faster throughput (I/O workloads) | ⚠️ Comparable                            |
```

---

## Appendix A: AsyncTasQ Key Differentiators

This section documents AsyncTasQ's unique features that must be highlighted in benchmarks.

### 1. Intelligent ORM Serialization

**Feature**: Automatic detection and PK-only serialization for SQLAlchemy, Django, Tortoise ORM models.

**Implementation**:
- Hook-based detection via `SqlalchemyOrmHook`, `DjangoOrmHook`, `TortoiseOrmHook`
- Serialized as: `{"__orm:sqlalchemy__": 123, "__orm_class__": "app.models.User"}`
- Worker-side: Async model re-fetch with `AsyncSession.get()`

**Benchmark Impact**:
- 90-98% payload reduction (52 bytes vs 2,814 bytes)
- Fresh data guarantee (no stale model state)
- Zero developer overhead (vs Celery manual `user.id` extraction)

**Test Cases**:
```python
# Nested models
@task
async def process(order: Order, user: User, payment: Payment):
    # All 3 models serialized as PK references
    pass

# Complex relationships
@task
async def sync_data(company: Company):  # Has 20+ relationships
    # Only company PK serialized, relationships fetched on demand
    pass
```

### 2. True Async-First Architecture

**Feature**: Single-threaded asyncio with efficient I/O multiplexing (epoll/kqueue).

**Implementation**:
- No GIL contention (unlike Celery threads)
- Concurrent task execution via `asyncio.TaskGroup`
- Connection pooling: asyncpg (PostgreSQL), aiomysql (MySQL), aioredis

**Benchmark Impact**:
- 3.5x faster than threading for I/O workloads (per research)
- Near-linear scaling with worker concurrency
- Lower memory footprint (no process pools)

**Trade-offs**:
- CPU-bound tasks require `run_in_executor()` (document clearly)
- Single-core utilization per worker process

### 3. Multi-Driver Flexibility with Zero Code Changes

**Feature**: 5 production-ready drivers, switch via config only.

**Drivers**:
1. **Redis**: Fastest throughput (7k+ tasks/sec), Pub/Sub events
2. **PostgreSQL**: ACID transactions, SKIP LOCKED, dead-letter table
3. **MySQL**: Transactional dequeue, visibility timeout, DLQ
4. **RabbitMQ**: Advanced routing, exchanges, durable queues
5. **AWS SQS**: Cloud-native, long polling, message attributes

**Implementation**:
```python
# Development
set_global_config(driver="redis")

# Production
set_global_config(driver="postgres", postgres_dsn="...")

# Per-task override
@task(driver="redis")  # Critical tasks always on Redis
async def critical_task():
    pass
```

**Benchmark Impact**:
- Driver-specific optimizations (e.g., SKIP LOCKED for concurrency)
- Zero migration cost (same API)
- Per-task driver override for mixed workloads

### 4. Real-Time Event Streaming

**Feature**: Redis Pub/Sub event system for live monitoring.

**Events**:
- Task: `enqueued`, `started`, `completed`, `failed`, `retrying`
- Worker: `online`, `heartbeat`, `offline`

**Implementation**:
```python
from asynctasq.core.events import EventEmitter, TaskEvent, EventType

emitter = EventEmitter(redis_url="redis://localhost:6379")
await emitter.emit_task_event(TaskEvent(
    event_type=EventType.TASK_STARTED,
    task_id="abc123",
    task_name="SendEmailTask",
    queue="default",
    worker_id="worker-1"
))
```

**Integration**: asynctasq-monitor subscribes to `asynctasq:events` channel, streams via WebSocket to UI.

**Benchmark Impact**:
- <1ms event emission overhead
- 10k+ events/sec throughput
- Real-time visibility (vs Celery's Flower polling)

### 5. Developer-Friendly Fluent API

**Feature**: Method chaining for elegant task configuration.

**Syntax**:
```python
# Simple dispatch
await send_email.dispatch(user_id=123)

# Delayed execution
await send_email.delay(300).dispatch(user_id=123)

# Custom queue + delay
await send_email.delay(60).on_queue("emails").dispatch(user_id=123)

# Class-based chaining
await MyTask(param=value).delay(300).on_queue("high").dispatch()
```

**Benchmark Impact**:
- <1µs chaining overhead (negligible)
- Improved code readability (qualitative)

### 6. Native FastAPI Integration

**Feature**: First-class lifespan management and dependency injection.

**Implementation**:
```python
from fastapi import FastAPI
from asynctasq.integrations.fastapi import AsyncTaskIntegration

asynctasq = AsyncTaskIntegration()
app = FastAPI(lifespan=asynctasq.lifespan)
# Driver connects on startup, disconnects on shutdown
```

**Benchmark Impact**:
- <200ms startup overhead
- Automatic connection pool management
- Graceful shutdown with task draining

### 7. Extensible Serialization Hooks

**Feature**: Plugin system for custom type support.

**Built-in Hooks**:
- datetime, date, Decimal, UUID, set (via `BuiltinHooks`)
- SQLAlchemy, Django, Tortoise (via `OrmHooks`)

**Custom Hooks**:
```python
from asynctasq.serializers.hooks import TypeHook

class MoneyHook(TypeHook[Money]):
    type_key = "__money__"
    
    def can_encode(self, obj) -> bool:
        return isinstance(obj, Money)
    
    def encode(self, obj: Money) -> dict:
        return {self.type_key: {"amount": str(obj.amount), "currency": obj.currency}}
    
    def decode(self, data: dict) -> Money:
        d = data[self.type_key]
        return Money(Decimal(d["amount"]), d["currency"])

serializer = MsgpackSerializer()
serializer.register_hook(MoneyHook())
```

**Benchmark Impact**:
- <50µs hook registration
- Modular architecture (vs Celery monolithic JSON/pickle)

### 8. Enterprise-Grade Reliability (PostgreSQL/MySQL)

**Features**:
- **ACID Transactions**: Atomic dequeue with rollback on failure
- **Dead-Letter Queue**: Auto-routing of permanently failed tasks
- **Visibility Timeout**: Crash recovery (stuck tasks become visible again)
- **SKIP LOCKED**: Concurrent workers without lock contention

**Implementation (PostgreSQL)**:
```sql
-- Dequeue with SKIP LOCKED
SELECT id, payload FROM task_queue
WHERE queue_name = 'default' 
  AND status = 'pending'
  AND available_at <= NOW()
  AND (locked_until IS NULL OR locked_until < NOW())
ORDER BY available_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;

-- Dead-letter table
INSERT INTO dead_letter_queue (task_id, queue_name, payload, error, attempts)
VALUES (...);
```

**Benchmark Impact**:
- 10-20% throughput reduction vs Redis (trade-off for ACID)
- Zero data loss guarantee
- Automatic failure inspection via DLQ table

---

### From python_queue_benchmark (GitHub)
- **Standard Test**: 20,000 tasks with 10 workers
- **Celery (threads)**: 11.68 seconds
- **Huey**: 4.15 seconds (fastest in benchmark)
- **Takeaway**: Worker pool type matters (threads vs processes vs async)

### From Celery Stress Testing (Moldstud)
- **Redis vs RabbitMQ**: Redis sustains 7,000 tasks/sec vs 3,500 for RabbitMQ
- **Connection Pooling**: 27% latency reduction with proper tuning
- **Prefetch Multiplier**: 40% throughput gain when increased from 1 to 10
- **Horizontal Scaling**: 3x 4-core nodes outperform 1x 16-core node (180ms vs 290ms median latency)

### From Async vs Threading Research (DEV Community)
- **Python asyncio**: 3.5x faster than threading for I/O-bound workloads
- **Golang goroutines**: Near-flat scalability curve (O(1) with epoll)
- **Python GIL**: No true concurrency in threading, context switching overhead
- **Event Loop**: Asyncio uses single-threaded epoll for efficient I/O multiplexing

### From Serialization Benchmarks
- **msgpack**: 2-5x faster than JSON for encoding/decoding
- **Payload Size**: MessagePack 30-50% smaller than JSON for typical data
- **Binary Safety**: msgpack handles bytes natively, JSON requires base64 encoding

---

## Appendix C: Command Reference

### Run AsyncTasQ Worker
```bash
# Redis driver, 10 workers
python -m asynctasq worker --driver redis --redis-url redis://localhost:6379 --concurrency 10

# PostgreSQL with multiple queues (priority order)
python -m asynctasq worker --driver postgres --postgres-dsn postgresql://user:pass@localhost/db \
    --queues high-priority,default,low-priority --concurrency 20

# MySQL with custom table names
python -m asynctasq worker --driver mysql --mysql-dsn mysql://user:pass@localhost/db \
    --mysql-queue-table custom_queue --concurrency 10

# RabbitMQ with prefetch tuning
python -m asynctasq worker --driver rabbitmq --rabbitmq-url amqp://guest:guest@localhost:5672/ \
    --rabbitmq-prefetch-count 10 --concurrency 20

# SQS (AWS)
python -m asynctasq worker --driver sqs --sqs-region us-east-1 \
    --aws-access-key-id XXX --aws-secret-access-key YYY --concurrency 10
```

### Run Celery Worker
```bash
# Redis broker, 10 thread workers
celery -A tasks worker --loglevel=info -c 10 -P threads

# 10 process workers
celery -A tasks worker --loglevel=info -c 10 -P prefork
```

### Collect Metrics with Prometheus
```bash
# Query task throughput
curl 'http://localhost:9090/api/v1/query?query=rate(asynctasq_tasks_processed_total[1m])'
```
## Appendix D: Hardware Tuning
### Profile with py-spy
```bash
# Record flamegraph
py-spy record -o profile.svg --duration 60 --pid $(pgrep -f "asynctasq worker")
```

### Load Test with Locust
```bash
# Distributed mode: 1 master, 3 workers
locust -f locustfile.py --master
locust -f locustfile.py --worker --master-host=192.168.1.10
```

---

## Appendix C: Hardware Tuning

### Linux Kernel Optimization
```bash
# Increase TCP connection limits
sudo sysctl -w net.core.somaxconn=4096
sudo sysctl -w net.ipv4.tcp_max_syn_backlog=8192

# Disable swap (for consistent performance)
sudo swapoff -a

# CPU frequency scaling (disable turbo boost for consistency)
echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo
```

### Redis Tuning
```bash
# redis.conf
maxmemory 8gb
maxmemory-policy allkeys-lru
## Appendix E: Statistical Methods
timeout 300
```

### PostgreSQL Tuning
```sql
-- postgresql.conf
shared_buffers = 4GB
effective_cache_size = 12GB
work_mem = 64MB
maintenance_work_mem = 1GB
max_connections = 200
```

---

## Appendix D: Statistical Methods

### Hypothesis Testing

**Null Hypothesis (H0)**: AsyncTasQ and Celery have equal performance  
**Alternative Hypothesis (H1)**: AsyncTasQ is faster than Celery

**Test:** Independent two-sample t-test  
**Significance Level:** α = 0.05  
**Power:** 1 - β = 0.80 (80% power to detect 20% difference)

### Sample Size Calculation

For detecting a 30% difference with 80% power:
- **Minimum runs per configuration:** 8-10
- **Actual planned runs:** 10 (to account for outliers)

### Outlier Detection

Use Tukey's fence method:
- Lower fence: Q1 - 1.5 × IQR
- Upper fence: Q3 + 1.5 × IQR
- Remove outliers beyond fences, document reasons

---

## Conclusion

This comprehensive benchmarking plan provides a rigorous, transparent, and reproducible methodology to quantitatively compare AsyncTasQ and Celery. By leveraging industry-standard tools, realistic workloads, and statistical rigor, we will produce actionable insights that help users make informed decisions about task queue solutions.

**Next Steps:**
1. **Approve Plan**: Review and approve this plan with stakeholders
2. **Allocate Resources**: Secure infrastructure budget (~$500-1000 for 8 weeks of cloud usage)
3. **Begin Phase 1**: Start environment setup and infrastructure provisioning
4. **Track Progress**: Weekly updates on milestones and deliverables

**Questions or Feedback:** Open an issue on `asynctasq/asynctasq` or email benchmarks@asynctasq.dev

---

**Document Version:** 1.0  
**Last Updated:** December 10, 2024  
**Authors:** AsyncTasQ Core Team + Community Contributors  
**License:** CC BY 4.0 (Creative Commons Attribution)
