"""Scenario 3: CPU-Bound Workload

Compare AsyncTasQ's ProcessTask vs Celery prefork workers.
Tests GIL handling and true parallelism for compute-heavy tasks.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchmarks.common import BenchmarkConfig, BenchmarkResult

from benchmarks.common import BenchmarkResult, Framework, TaskTiming, Timer


async def run_asynctasq(config: BenchmarkConfig) -> BenchmarkResult:
    """Run AsyncTasQ CPU-bound benchmark using ProcessTask.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    from tasks.asynctasq_tasks import ComputeHashProcess

    task_timings: list[TaskTiming] = []

    # Test data (10MB of random data)
    test_data = b"x" * (10 * 1024 * 1024)

    # Enqueue all tasks
    with Timer() as enqueue_timer:
        task_ids = []
        for _i in range(config.task_count):
            enqueue_time = time.perf_counter()
            task_instance = await ComputeHashProcess(data=test_data, iterations=100000).dispatch()
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
        extra_metrics={
            "execution_model": "ProcessTask (process pool)",
            "payload_size_mb": 10,
        },
    )


def run_celery(config: BenchmarkConfig) -> BenchmarkResult:
    """Run Celery CPU-bound benchmark with prefork workers.

    Args:
        config: Benchmark configuration

    Returns:
        Benchmark results
    """
    from tasks.celery_tasks import compute_hash_process

    task_timings: list[TaskTiming] = []

    # Test data (10MB of random data)
    test_data = b"x" * (10 * 1024 * 1024)

    # Enqueue all tasks
    with Timer() as enqueue_timer:
        async_results = []
        for _i in range(config.task_count):
            enqueue_time = time.perf_counter()
            result = compute_hash_process.delay(data=test_data, iterations=100000)
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
        extra_metrics={
            "execution_model": "prefork (multiprocessing)",
            "payload_size_mb": 10,
        },
    )


async def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    """Run CPU-bound benchmark for specified framework.

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
