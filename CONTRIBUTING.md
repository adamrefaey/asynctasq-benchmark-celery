# Contributing to AsyncTasQ Benchmark Suite

Thank you for your interest in improving the AsyncTasQ vs Celery benchmarking suite!

## Getting Started

### Prerequisites

- Python 3.12+
- Docker 27.x with Compose v2
- [uv](https://github.com/astral-sh/uv) package manager
- 16GB+ RAM (recommended for running full benchmark suite)

### Setup

```bash
# Clone the repository
cd asynctasq-benchmark-celery

# Run quick start
./quick-start.sh

# Or manually:
uv sync --all-extras
just docker-up
```

## Development Workflow

### Adding a New Benchmark Scenario

1. **Create scenario file**: `benchmarks/scenario_N_name.py`

```python
"""Scenario N: Description

Detailed explanation of what this scenario tests.
"""

from __future__ import annotations

from benchmarks.common import BenchmarkConfig, BenchmarkResult, Framework

async def run_asynctasq(config: BenchmarkConfig) -> BenchmarkResult:
    """Run AsyncTasQ benchmark."""
    # Implementation
    pass

def run_celery(config: BenchmarkConfig) -> BenchmarkResult:
    """Run Celery benchmark."""
    # Implementation
    pass

async def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    """Run benchmark for specified framework."""
    if config.framework == Framework.ASYNCTASQ:
        return await run_asynctasq(config)
    elif config.framework == Framework.CELERY:
        return run_celery(config)
    else:
        raise ValueError(f"Unknown framework: {config.framework}")
```

2. **Add scenario to runner**: Update `SCENARIOS` dict in `benchmarks/runner.py`

3. **Create task definitions**: Add tasks to `tasks/asynctasq_tasks.py` and `tasks/celery_tasks.py`

4. **Test the scenario**:
```bash
just benchmark N
```

5. **Update documentation**: Add scenario details to README.md

### Code Standards

- **Type hints**: All public functions must have type hints
- **Docstrings**: Use Google style docstrings
- **Formatting**: Run `just format` before committing
- **Linting**: Ensure `just lint` passes
- **Type checking**: Ensure `just typecheck` passes

### Running Tests

```bash
# Format code
just format

# Run linter
just lint

# Run type checker
just typecheck

# Run all checks
just check
```

## Benchmark Design Guidelines

### Fair Comparison

1. **Equivalent implementations**: AsyncTasQ and Celery tasks should perform identical work
2. **Same resources**: Use identical worker counts, task counts, and timeouts
3. **Multiple runs**: Minimum 10 runs per scenario for statistical validity
4. **Warm-up period**: 30 seconds before collecting metrics

### Metric Collection

All scenarios should collect:
- **Throughput**: Tasks per second
- **Latency**: Mean, median, P95, P99
- **Resource usage**: Memory (MB), CPU (%)
- **Task timings**: Enqueue, wait, execution times

### Statistical Rigor

- Report mean, median, standard deviation, min, max
- Use t-tests for significance (p < 0.05)
- Calculate effect sizes (Cohen's d)
- Run multiple iterations (10+ recommended)

## Adding New Analysis Tools

### Visualization

Add new charts in `analysis/visualizer.py`:

```python
def plot_new_metric(df: pd.DataFrame, output_file: Path) -> None:
    """Create new metric visualization."""
    # Implementation using matplotlib/seaborn
    pass
```

### Statistical Analysis

Add new analyses in `analysis/analyzer.py`:

```python
def analyze_new_metric(results: dict) -> dict:
    """Analyze new performance metric."""
    # Implementation
    return analysis_results
```

## Infrastructure

### Adding New Services

To add a new service to Docker Compose:

1. Edit `infrastructure/docker-compose.yml`
2. Add healthcheck for the service
3. Update `justfile` `check-health` recipe
4. Document configuration in README.md

### Prometheus Metrics

Add custom metrics in benchmark scenarios:

```python
from prometheus_client import Counter, Histogram

# Define metrics
tasks_completed = Counter('benchmark_tasks_completed', 'Tasks completed')
task_duration = Histogram('benchmark_task_duration_seconds', 'Task duration')

# Use in benchmark
tasks_completed.inc()
task_duration.observe(duration)
```

## Pull Request Process

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/my-new-scenario`
3. **Make changes** following code standards
4. **Run checks**: `just check`
5. **Test thoroughly**: Run your scenario multiple times
6. **Commit with clear messages**: `git commit -m "Add scenario N: Description"`
7. **Push to your fork**: `git push origin feature/my-new-scenario`
8. **Create Pull Request** with:
   - Clear description of changes
   - Benchmark results (if applicable)
   - Any new dependencies or infrastructure requirements

## Commit Message Guidelines

Use conventional commits format:

```
feat: Add scenario 5 for serialization efficiency
fix: Correct Celery worker timeout handling
docs: Update README with new scenario
perf: Optimize task timing collection
test: Add unit tests for Timer class
chore: Update dependencies
```

## Questions or Issues?

- Check existing [GitHub Issues](https://github.com/adamrefaey/asynctasq/issues)
- Start a [Discussion](https://github.com/adamrefaey/asynctasq/discussions)
- Review the [benchmarking plan](../asynctasq/docs/benchmarking-plan.md)

## License

By contributing, you agree that your contributions will be licensed under the same MIT License as the project.
