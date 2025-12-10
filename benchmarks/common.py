"""Shared utilities and data models for benchmarking."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import os
import statistics
import time
from typing import Any

import psutil


class Framework(str, Enum):
    """Task queue framework being tested."""

    ASYNCTASQ = "asynctasq"
    CELERY = "celery"


class Driver(str, Enum):
    """Queue driver/broker type.

    Note: This benchmark focuses on Redis, the most common production
    deployment for both asynctasq and Celery. For multi-driver asynctasq
    benchmarks, see the main asynctasq repository.
    """

    REDIS = "redis"


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""

    framework: Framework
    driver: Driver | None = None  # Only for AsyncTasQ
    worker_count: int = 10
    task_count: int = 20000
    runs: int = 10
    timeout_seconds: int = 300

    # Worker configuration
    worker_type: str = "default"  # For Celery: prefork, threads, gevent, eventlet
    concurrency: int | None = None  # Override worker concurrency

    # Test-specific config
    extra_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskTiming:
    """Timing data for a single task."""

    task_id: str
    enqueue_time: float
    start_time: float | None = None
    complete_time: float | None = None
    error_time: float | None = None
    error: str | None = None

    @property
    def total_latency(self) -> float | None:
        """Total time from enqueue to completion."""
        if self.complete_time:
            return self.complete_time - self.enqueue_time
        return None

    @property
    def wait_time(self) -> float | None:
        """Time waiting in queue before starting."""
        if self.start_time:
            return self.start_time - self.enqueue_time
        return None

    @property
    def execution_time(self) -> float | None:
        """Time spent executing the task."""
        if self.start_time and self.complete_time:
            return self.complete_time - self.start_time
        return None


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""

    config: BenchmarkConfig
    run_number: int

    # Overall metrics
    total_time: float  # Total benchmark duration (enqueue + processing)
    enqueue_time: float  # Time to enqueue all tasks
    processing_time: float  # Time from first task start to last task complete

    # Task-level metrics
    tasks_completed: int
    tasks_failed: int
    task_timings: list[TaskTiming] = field(default_factory=list)

    # Resource metrics
    memory_mb: float = 0.0
    cpu_percent: float = 0.0

    # Queue depth monitoring (timestamp, depth) pairs
    queue_depth_samples: list[tuple[float, int]] = field(default_factory=list)

    # Extra metrics
    extra_metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def throughput(self) -> float:
        """Tasks per second (total)."""
        if self.total_time > 0:
            return self.tasks_completed / self.total_time
        return 0.0

    @property
    def enqueue_rate(self) -> float:
        """Enqueue operations per second."""
        if self.enqueue_time > 0:
            return self.config.task_count / self.enqueue_time
        return 0.0

    @property
    def processing_rate(self) -> float:
        """Processing rate (tasks/sec during execution)."""
        if self.processing_time > 0:
            return self.tasks_completed / self.processing_time
        return 0.0

    @property
    def latencies(self) -> list[float]:
        """All task latencies (enqueue to complete)."""
        return [t.total_latency for t in self.task_timings if t.total_latency is not None]

    @property
    def mean_latency(self) -> float:
        """Mean task latency in milliseconds."""
        latencies = self.latencies
        return statistics.mean(latencies) * 1000 if latencies else 0.0

    @property
    def median_latency(self) -> float:
        """Median task latency in milliseconds."""
        latencies = self.latencies
        return statistics.median(latencies) * 1000 if latencies else 0.0

    @property
    def p95_latency(self) -> float:
        """95th percentile latency in milliseconds."""
        latencies = sorted(self.latencies)
        if not latencies:
            return 0.0
        index = int(len(latencies) * 0.95)
        return latencies[index] * 1000

    @property
    def p99_latency(self) -> float:
        """99th percentile latency in milliseconds."""
        latencies = sorted(self.latencies)
        if not latencies:
            return 0.0
        index = int(len(latencies) * 0.99)
        return latencies[index] * 1000


@dataclass
class BenchmarkSummary:
    """Statistical summary across multiple runs."""

    config: BenchmarkConfig
    results: list[BenchmarkResult]

    def _get_metric_stats(self, metric_name: str) -> dict[str, float]:
        """Calculate statistics for a metric across all runs."""
        values = [getattr(r, metric_name) for r in self.results]
        return {
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }

    @property
    def throughput_stats(self) -> dict[str, float]:
        """Throughput statistics (tasks/sec)."""
        return self._get_metric_stats("throughput")

    @property
    def mean_latency_stats(self) -> dict[str, float]:
        """Mean latency statistics (ms)."""
        return self._get_metric_stats("mean_latency")

    @property
    def p95_latency_stats(self) -> dict[str, float]:
        """P95 latency statistics (ms)."""
        return self._get_metric_stats("p95_latency")

    @property
    def p99_latency_stats(self) -> dict[str, float]:
        """P99 latency statistics (ms)."""
        return self._get_metric_stats("p99_latency")

    @property
    def memory_stats(self) -> dict[str, float]:
        """Memory usage statistics (MB)."""
        return self._get_metric_stats("memory_mb")

    @property
    def cpu_stats(self) -> dict[str, float]:
        """CPU utilization statistics (%)."""
        return self._get_metric_stats("cpu_percent")

    @property
    def throughput_coefficient_of_variation(self) -> float:
        """Coefficient of variation for throughput (lower is more stable).
        
        CV < 0.1 = excellent stability
        CV 0.1-0.2 = good stability
        CV > 0.2 = high variance, results may be unreliable
        """
        values = [r.throughput for r in self.results]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0.0
        return (stdev / mean) if mean > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary for serialization."""
        return {
            "framework": self.config.framework.value,
            "driver": self.config.driver.value if self.config.driver else None,
            "worker_count": self.config.worker_count,
            "task_count": self.config.task_count,
            "runs": len(self.results),
            "throughput": self.throughput_stats,
            "throughput_cv": self.throughput_coefficient_of_variation,
            "mean_latency_ms": self.mean_latency_stats,
            "p95_latency_ms": self.p95_latency_stats,
            "p99_latency_ms": self.p99_latency_stats,
            "memory_mb": self.memory_stats,
            "cpu_percent": self.cpu_stats,
        }


class Timer:
    """Context manager for timing operations."""

    def __init__(self) -> None:
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self) -> Timer:
        """Start timer."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        """Stop timer and calculate elapsed time."""
        self.end_time = time.perf_counter()
        self.elapsed = self.end_time - self.start_time


class ResourceMonitor:
    """Monitor CPU and memory usage during benchmark execution.

    Tracks resource usage at regular intervals and provides average metrics.
    """

    def __init__(self, interval_seconds: float = 0.5) -> None:
        """Initialize resource monitor.

        Args:
            interval_seconds: How often to sample resource usage (default: 0.5s)
        """
        self.interval_seconds = interval_seconds
        self.process = psutil.Process(os.getpid())
        self.cpu_samples: list[float] = []
        self.memory_samples: list[float] = []
        self._monitoring = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start monitoring resource usage in background."""
        self._monitoring = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> tuple[float, float]:
        """Stop monitoring and return average metrics.

        Returns:
            Tuple of (average_cpu_percent, average_memory_mb)
        """
        self._monitoring = False
        if self._task:
            await self._task

        avg_cpu = statistics.mean(self.cpu_samples) if self.cpu_samples else 0.0
        avg_memory = statistics.mean(self.memory_samples) if self.memory_samples else 0.0

        return avg_cpu, avg_memory

    async def _monitor_loop(self) -> None:
        """Background loop to sample resource usage."""
        # Initial sample to "warm up" cpu_percent (first call returns 0.0)
        self.process.cpu_percent(interval=None)
        await asyncio.sleep(self.interval_seconds)

        while self._monitoring:
            try:
                # CPU percent (per-core, so can exceed 100%)
                cpu = self.process.cpu_percent(interval=None)
                
                # Only include non-zero CPU samples (skip initial warmup)
                if cpu > 0.0 or len(self.cpu_samples) > 0:
                    self.cpu_samples.append(cpu)

                # Memory in MB
                memory_info = self.process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                self.memory_samples.append(memory_mb)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process may have terminated
                break

            await asyncio.sleep(self.interval_seconds)

    async def __aenter__(self) -> ResourceMonitor:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.stop()
