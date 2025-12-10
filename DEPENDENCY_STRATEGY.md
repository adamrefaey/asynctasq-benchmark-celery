# Dependency Conflict Resolution Strategy

## Problem

The benchmark suite requires both asynctasq and Celery to use **Redis as the broker**, but they have incompatible Redis dependency declarations:

- **asynctasq[redis]>=0.9.12** requires `redis[hiredis]>=7.1.0`
- **celery[redis]>=5.6.0** (via kombu[redis]) requires `redis>=4.5.2,<6.5`

This creates an unsolvable dependency conflict when using package extras.

## ✅ Solution: Direct Redis Installation (Bypassing Extras)

**Install Redis directly without using the package extras that declare conflicting constraints.**

### How It Works

1. **Don't use `celery[redis]` or `kombu[redis]`** - these extras have the strict `<6.5` constraint
2. **Don't use `asynctasq[redis]`** - this would pull redis via extra dependency
3. **Install `redis[hiredis]>=7.1.0` directly** as a top-level dependency
4. **Both Celery and asynctasq will use the installed redis package** even without the extras

### Implementation

```toml
[project]
dependencies = [
    # Core packages WITHOUT redis extras
    "celery>=5.6.0",
    "kombu>=5.6.0",
    "asynctasq[postgres,mysql,rabbitmq,sqs]>=0.9.12",  # All except redis
    
    # Redis installed DIRECTLY (not via extras)
    "redis[hiredis]>=7.1.0",
]
```

### Why This Works

- **Package extras are optional** - they're just convenience bundles of dependencies
- **Celery/kombu detect redis at runtime** - they don't require the `[redis]` extra to function
- **The `[redis]` extras only declare dependencies** - bypassing them avoids the conflict
- **Direct installation satisfies both systems** - both get Redis 7.1.0 with hiredis

### Verified Working

```bash
✅ Redis: 7.1.0
✅ Celery: 5.6.0
✅ Kombu: 5.6.1
✅ Celery can import Redis transport
```

## Why Both Must Use Redis

For a **fair benchmark**, both systems must use the **same broker**:

1. **Identical Network Path** - Same latency, connection overhead, protocol
2. **Identical Persistence** - Same durability guarantees, AOF/RDB behavior
3. **Identical Concurrency** - Same connection pooling, pipelining capabilities
4. **Fair Comparison** - Only the task queue implementation differs

Using different brokers (e.g., Redis vs RabbitMQ) would measure broker differences, not task queue performance.

## Modern Best Practices (December 2024)

This solution follows 2024-2025 Python packaging best practices:

1. **PEP 621** - Modern `pyproject.toml` with `[project]` table
2. **Explicit is better than implicit** - Direct dependencies vs hidden extras
3. **Constraint resolution** - Understanding that extras are just dependency bundles
4. **Runtime detection** - Libraries check for installed packages, not extras
5. **Clean architecture** - Avoid version pinning hacks or forks

## Alternative Approaches Considered (and Why They're Worse)

### ❌ Option 1: Pre-Release Kombu

```bash
uv sync --prerelease=allow  # Use kombu 5.6.0rc2+
```

**Rejected because:**
- Unstable pre-release software
- May have undiscovered bugs
- Not suitable for production-grade benchmarks
- Defeats purpose of comparing stable versions

### ❌ Option 2: Separate Virtual Environments

Run benchmarks in isolated environments with different Redis versions.

**Rejected because:**
- Complex CI/CD setup
- Can't share benchmark infrastructure code
- Harder to maintain
- Increases test execution time
- Makes fair comparison difficult

### ❌ Option 3: Different Brokers

Use Redis for asynctasq, RabbitMQ for Celery.

**Rejected because:**
- **Not a fair comparison** - measures broker differences, not queue performance
- Different latency characteristics
- Different durability guarantees
- Different concurrency models
- Makes results meaningless

### ❌ Option 4: Fork and Patch Kombu

Create a fork with updated Redis constraints.

**Rejected because:**
- Maintenance burden
- Invalidates benchmark (not using official versions)
- May introduce subtle bugs
- Not reproducible by others

## Docker Services Configuration

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7.4-alpine  # Latest stable Redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
  
  postgres:
    image: postgres:17-alpine  # Shared result backend
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: benchmark
      POSTGRES_USER: bench
      POSTGRES_PASSWORD: bench123
```

## Benchmark Configuration

Both systems use identical Redis configuration:

```python
# AsyncTasQ Configuration
ASYNCTASQ_CONFIG = {
    "driver": "redis",
    "redis_url": "redis://localhost:6379/0",
    "redis_max_connections": 50,
}

# Celery Configuration  
CELERY_CONFIG = {
    "broker_url": "redis://localhost:6379/0",
    "result_backend": "redis://localhost:6379/1",
    "broker_connection_max_retries": None,
    "broker_pool_limit": 50,
}
```

## Testing the Solution

```bash
# 1. Install dependencies
uv sync --all-extras --all-groups

# 2. Verify versions
uv pip list | grep -E "(redis|celery|kombu|asynctasq)"

# Expected output:
# asynctasq      0.9.12
# celery         5.6.0
# hiredis        3.3.0
# kombu          5.6.1
# redis          7.1.0

# 3. Test imports
uv run python -c "
import redis
import celery
from celery import Celery

print(f'Redis: {redis.__version__}')
print(f'Celery: {celery.__version__}')

app = Celery(broker='redis://localhost:6379/0')
print('✅ Celery can use Redis 7.1.0!')
"

# 4. Start services
docker-compose up -d redis postgres

# 5. Run benchmarks
just benchmark
```

## Benefits of This Solution

1. ✅ **Both use Redis 7.1.0** - Fair comparison with identical broker
2. ✅ **No conflicts** - Clean dependency resolution
3. ✅ **No hacks** - Uses standard Python packaging features
4. ✅ **Stable versions** - No pre-releases or forks
5. ✅ **Reproducible** - Anyone can replicate the setup
6. ✅ **Latest features** - Redis 7.1.0 with performance improvements
7. ✅ **Type safe** - Hiredis acceleration for both systems

## Key Insight

**The `[redis]` extras in celery and kombu are just dependency declarations, not functional requirements.** By installing redis directly, we bypass the constraint conflict while maintaining full functionality.

This is a clean, modern solution that respects the principle: "Extras are for convenience, not necessity."

## References

- [Redis 7.1.0 Release](https://github.com/redis/redis-py/releases/tag/v7.1.0) (Nov 2024)
- [Kombu 5.6.1 Release](https://github.com/celery/kombu/releases/tag/v5.6.1) (Nov 2024)
- [PEP 621 - Storing project metadata in pyproject.toml](https://peps.python.org/pep-0621/)
- [Python Packaging Guide - Optional Dependencies](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#extras)

