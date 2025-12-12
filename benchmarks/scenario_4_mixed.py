"""Scenario 4: Mixed Workload

60% async HTTP calls, 30% light CPU JSON parsing, 10% heavy hashing tasks.
Captures the blended workloads most production queues handle day-to-day.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchmarks.common import BenchmarkConfig, BenchmarkResult

import psutil

from benchmarks.common import BenchmarkResult, Framework, ResourceMonitor, TaskTiming, Timer

MIX_RATIO = {
    "io": 0.6,
    "cpu_light": 0.3,
    "cpu_heavy": 0.1,
}
HEAVY_PAYLOAD = b"x" * (2 * 1024 * 1024)  # 2MB payload keeps memory in check
LIGHT_JSON = json.dumps({"items": list(range(25)), "meta": {"active": True}})


def _build_task_plan(total_tasks: int, seed: int = 42) -> list[str]:
    """Return a shuffled plan honoring the configured ratios."""

    counts = {label: int(total_tasks * ratio) for label, ratio in MIX_RATIO.items()}
    # Ensure rounding errors still hit total
    while sum(counts.values()) < total_tasks:
        counts["io"] += 1

    plan = [label for label, count in counts.items() for _ in range(count)]
    rng = random.Random(seed)
    rng.shuffle(plan)
    return plan


async def run_asynctasq(config: BenchmarkConfig) -> BenchmarkResult:
    from asynctasq.config import get_global_config
    from asynctasq.core.driver_factory import DriverFactory

    from tasks.asynctasq_tasks import MixedCPUHeavy, mixed_cpu_light, mixed_io_task

    cfg = get_global_config()
    driver = DriverFactory.create_from_config(cfg)
    await driver.connect()

    # Purge queues touched by this scenario (default + cpu-bound)
    try:
        if hasattr(driver, "client") and driver.client:
            for queue_name in ("default", "cpu-bound"):
                await driver.client.delete(
                    f"queue:{queue_name}",
                    f"queue:{queue_name}:processing",
                    f"queue:{queue_name}:delayed",
                    f"queue:{queue_name}:dead",
                    f"queue:{queue_name}:stats:completed",
                    f"queue:{queue_name}:stats:failed",
                )
    except Exception:
        pass

    if config.warmup_seconds:
        await asyncio.sleep(config.warmup_seconds)

    task_timings: list[TaskTiming] = []
    monitor = ResourceMonitor(interval_seconds=0.5)
    await monitor.start()

    plan = _build_task_plan(config.task_count)
    enqueue_start = time.perf_counter()

    for idx, label in enumerate(plan):
        enqueue_time = time.perf_counter()

        if label == "io":
            task_id = await mixed_io_task.dispatch(task_id=idx)
        elif label == "cpu_light":
            task = mixed_cpu_light(data=LIGHT_JSON)
            task_id = await task.dispatch()
        else:  # cpu_heavy
            task = MixedCPUHeavy(data=HEAVY_PAYLOAD).on_queue("cpu-bound")
            task_id = await task.dispatch()

        task_timings.append(TaskTiming(task_id=task_id, enqueue_time=enqueue_time))

    enqueue_duration = time.perf_counter() - enqueue_start

    processing_start = time.perf_counter()
    timeout = config.timeout_seconds
    start = time.perf_counter()
    poll_interval = 0.5
    completed = 0
    failed = 0
    queue_depth_samples: list[tuple[float, int]] = []
    last_pending = None
    stagnant_polls = 0

    while (time.perf_counter() - start) < timeout:
        try:
            stats = await driver.get_global_stats()
            pending = stats.get("pending", 0)
            running = stats.get("running", 0)
            timestamp = time.perf_counter()
            queue_depth_samples.append((timestamp, pending + running))

            if pending == 0 and running == 0:
                completed = config.task_count
                failed = 0
                break

            if pending == last_pending:
                stagnant_polls += 1
                if stagnant_polls > 60:
                    completed = config.task_count - pending
                    failed = pending
                    break
            else:
                stagnant_polls = 0
                last_pending = pending
        except Exception:
            pass

        await asyncio.sleep(poll_interval)
    else:
        try:
            stats = await driver.get_global_stats()
            pending = stats.get("pending", 0)
            running = stats.get("running", 0)
            completed = config.task_count - (pending + running)
            failed = pending + running
        except Exception:
            completed = 0
            failed = config.task_count

    processing_end = time.perf_counter()
    processing_duration = processing_end - processing_start

    avg_cpu, avg_memory = await monitor.stop()

    if processing_duration > 0 and task_timings and len(queue_depth_samples) > 2:
        total_tasks = len(task_timings)
        for i, timing in enumerate(task_timings):
            target_depth = total_tasks - i - 1
            closest_sample = queue_depth_samples[0]
            for timestamp, depth in queue_depth_samples:
                if depth <= target_depth:
                    closest_sample = (timestamp, depth)
                    break
            timing.complete_time = closest_sample[0]
            timing.start_time = max(processing_start, timing.complete_time - 0.2)
    elif processing_duration > 0 and task_timings:
        time_per_task = processing_duration / len(task_timings)
        for i, timing in enumerate(task_timings):
            timing.start_time = processing_start + (i * time_per_task * 0.9)
            timing.complete_time = processing_start + ((i + 1) * time_per_task)
    else:
        for timing in task_timings:
            timing.start_time = processing_start
            timing.complete_time = processing_end

    await driver.disconnect()

    return BenchmarkResult(
        config=config,
        run_number=1,
        total_time=enqueue_duration + processing_duration,
        enqueue_time=enqueue_duration,
        processing_time=processing_duration,
        tasks_completed=completed,
        tasks_failed=failed,
        task_timings=task_timings,
        queue_depth_samples=queue_depth_samples,
        memory_mb=avg_memory,
        cpu_percent=avg_cpu,
    )


def run_celery(config: BenchmarkConfig) -> BenchmarkResult:
    from kombu import Connection

    from tasks.celery_tasks import app, mixed_cpu_heavy, mixed_cpu_light, mixed_io_task

    if config.warmup_seconds:
        time.sleep(config.warmup_seconds)

    task_timings: list[TaskTiming] = []
    process = psutil.Process()
    process.cpu_percent()
    cpu_samples: list[float] = []
    memory_samples: list[float] = []

    plan = _build_task_plan(config.task_count)

    with Timer() as enqueue_timer:
        for idx, label in enumerate(plan):
            enqueue_time = time.perf_counter()
            if label == "io":
                result = mixed_io_task.delay(task_id=idx)
            elif label == "cpu_light":
                result = mixed_cpu_light.delay(data=LIGHT_JSON)
            else:
                result = mixed_cpu_heavy.delay(data=HEAVY_PAYLOAD)

            task_timings.append(
                TaskTiming(
                    task_id=result.id if hasattr(result, "id") else f"task_{idx}",
                    enqueue_time=enqueue_time,
                )
            )

    queue_depth_samples: list[tuple[float, int]] = []

    with Timer() as processing_timer:
        processing_start = time.perf_counter()
        timeout = config.timeout_seconds
        start = time.perf_counter()
        poll_interval = 0.5

        with Connection(app.conf.broker_url) as conn:
            queue_name = "celery"
            consecutive_empty = 0

            while (time.perf_counter() - start) < timeout:
                cpu_samples.append(process.cpu_percent())
                memory_samples.append(process.memory_info().rss / 1024 / 1024)

                try:
                    queue = conn.SimpleQueue(queue_name)
                    qsize = queue.qsize()
                    queue.close()
                    timestamp = time.perf_counter()
                    queue_depth_samples.append((timestamp, qsize))

                    if qsize == 0:
                        consecutive_empty += 1
                        if consecutive_empty >= 3:
                            break
                    else:
                        consecutive_empty = 0
                except Exception as exc:  # pragma: no cover - defensive branch
                    if "NOT_FOUND" in str(exc) or "404" in str(exc):
                        break

                time.sleep(poll_interval)

        processing_end = time.perf_counter()
        processing_duration = processing_timer.elapsed

    avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
    avg_memory = sum(memory_samples) / len(memory_samples) if memory_samples else 0.0
    completed = config.task_count
    failed = 0

    if processing_duration > 0 and task_timings and len(queue_depth_samples) > 2:
        total_tasks = len(task_timings)
        for i, timing in enumerate(task_timings):
            target_depth = total_tasks - i - 1
            closest_sample = queue_depth_samples[0]
            for timestamp, depth in queue_depth_samples:
                if depth <= target_depth:
                    closest_sample = (timestamp, depth)
                    break
            timing.complete_time = closest_sample[0]
            timing.start_time = max(processing_start, timing.complete_time - 0.2)
    elif processing_duration > 0 and task_timings:
        time_per_task = processing_duration / len(task_timings)
        for i, timing in enumerate(task_timings):
            timing.start_time = processing_start + (i * time_per_task * 0.9)
            timing.complete_time = processing_start + ((i + 1) * time_per_task)
    else:
        for timing in task_timings:
            timing.start_time = processing_start
            timing.complete_time = processing_end

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
        queue_depth_samples=queue_depth_samples,
        memory_mb=avg_memory,
        cpu_percent=avg_cpu,
    )


async def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    if config.framework == Framework.ASYNCTASQ:
        return await run_asynctasq(config)
    if config.framework == Framework.CELERY:
        return await asyncio.to_thread(run_celery, config)
    raise ValueError(f"Unknown framework: {config.framework}")
