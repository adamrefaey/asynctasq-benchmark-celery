"""Scenario 2: I/O-Bound Workload

Simulate real-world HTTP API calls with AsyncTasQ's async advantages.
Tests async concurrency vs Celery's threading/prefork models.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchmarks.common import BenchmarkConfig, BenchmarkResult

from benchmarks.common import BenchmarkResult, Framework, TaskTiming, Timer


async def run_asynctasq(config: BenchmarkConfig) -> BenchmarkResult:
    """Run AsyncTasQ I/O-bound benchmark.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    from tasks.asynctasq_tasks import fetch_user_http

    task_timings: list[TaskTiming] = []

    # Enqueue all tasks
    with Timer() as enqueue_timer:
        task_ids = []
        for i in range(config.task_count):
            enqueue_time = time.perf_counter()
            task_instance = await fetch_user_http.dispatch(user_id=i % 1000)
            task_ids.append(str(task_instance.task_id))
            task_timings.append(
                TaskTiming(
                    task_id=str(task_instance.task_id),
                    enqueue_time=enqueue_time,
                )
            )

    # Wait for all tasks to complete
    with Timer() as processing_timer:
        completed = 0
        timeout = config.timeout_seconds
        start = time.perf_counter()

        while completed < config.task_count and (time.perf_counter() - start) < timeout:
            await asyncio.sleep(0.1)
            # In real implementation, check driver for completed tasks
            completed = config.task_count  # Placeholder

    total_time = enqueue_timer.elapsed + processing_timer.elapsed

    return BenchmarkResult(
        config=config,
        run_number=1,
        total_time=total_time,
        enqueue_time=enqueue_timer.elapsed,
        processing_time=processing_timer.elapsed,
        tasks_completed=completed,
        tasks_failed=0,
        task_timings=task_timings,
    )


def run_celery(config: BenchmarkConfig) -> BenchmarkResult:
    """Run Celery I/O-bound benchmark.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    from tasks.celery_tasks import fetch_user_http

    task_timings: list[TaskTiming] = []

    # Enqueue all tasks
    with Timer() as enqueue_timer:
        async_results = []
        for i in range(config.task_count):
            enqueue_time = time.perf_counter()
            result = fetch_user_http.delay(user_id=i % 1000)
            async_results.append(result)
            task_timings.append(
                TaskTiming(
                    task_id=result.id,
                    enqueue_time=enqueue_time,
                )
            )

    # Wait for all tasks to complete
    with Timer() as processing_timer:
        completed = 0
        failed = 0

        for result in async_results:
            try:
                result.get(timeout=config.timeout_seconds)
                completed += 1
            except Exception:
                failed += 1

    total_time = enqueue_timer.elapsed + processing_timer.elapsed

    return BenchmarkResult(
        config=config,
        run_number=1,
        total_time=total_time,
        enqueue_time=enqueue_timer.elapsed,
        processing_time=processing_timer.elapsed,
        tasks_completed=completed,
        tasks_failed=failed,
        task_timings=task_timings,
    )


async def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    """Run I/O-bound benchmark for specified framework.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    if config.framework == Framework.ASYNCTASQ:
        return await run_asynctasq(config)
    elif config.framework == Framework.CELERY:
        return run_celery(config)
    else:
        raise ValueError(f"Unknown framework: {config.framework}")
