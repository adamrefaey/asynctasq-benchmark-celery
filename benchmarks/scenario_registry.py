"""Declarative registry describing every benchmark scenario.

The runner uses this metadata to spin up the correct worker topology per
framework, apply warm-up periods, and document requirements. Keeping the
scenario catalog centralized makes it trivial to add future workloads
without touching the orchestration code.
"""

from __future__ import annotations

from collections.abc import Iterable

from benchmarks.common import Framework, ScenarioDefinition, WorkerConfig

# ----------------------------------------------------------------------------
# Scenario metadata
# ----------------------------------------------------------------------------

SCENARIO_REGISTRY: dict[str, ScenarioDefinition] = {
    "1": ScenarioDefinition(
        id="1",
        name="Basic Throughput",
        module="benchmarks.scenario_1_throughput",
        description="20k no-op tasks to establish pure broker throughput.",
        task_count=20_000,
        worker_count=10,
        warmup_seconds=10,
        tags=("baseline", "prefetch-1"),
        requirements=("redis",),
        worker_profiles={
            Framework.ASYNCTASQ: WorkerConfig(
                framework=Framework.ASYNCTASQ,
                concurrency=12,
                queues=["default"],
                description="AsyncTasQ default queue warmed with 12 coroutines",
            ),
            Framework.CELERY: WorkerConfig(
                framework=Framework.CELERY,
                app_path="tasks.celery_tasks",
                concurrency=12,
                pool="prefork",
                queues=["celery"],
                prefetch_multiplier=1,
                env_overrides={"CELERY_ACKS_LATE": "1"},
                description="Celery prefork workers (prefetch=1) per Mahmud 2025 guidance",
            ),
        },
        notes="Prefetch multiplier forced to 1 to avoid dequeue bursts and to match Redis connection guidance from Mahmud 2025.",
    ),
    "2": ScenarioDefinition(
        id="2",
        name="I/O-Bound",
        module="benchmarks.scenario_2_io_bound",
        description="HTTP heavy workload hitting the mock API with async fan-out.",
        task_count=5_000,
        worker_count=10,
        warmup_seconds=15,
        tags=("io", "mock-api"),
        requirements=("redis", "mock-api"),
        worker_profiles={
            Framework.ASYNCTASQ: WorkerConfig(
                framework=Framework.ASYNCTASQ,
                concurrency=32,
                queues=["default"],
                description="High concurrency coroutine worker for HTTP fan-out",
            ),
            Framework.CELERY: WorkerConfig(
                framework=Framework.CELERY,
                app_path="tasks.celery_tasks",
                concurrency=32,
                pool="threads",
                queues=["celery"],
                prefetch_multiplier=4,
                description="Threads pool per Celery docs for blocking HTTP workloads",
            ),
        },
        notes="Mock API must be running (just docker-up-mock).",
    ),
    "3": ScenarioDefinition(
        id="3",
        name="CPU-Bound",
        module="benchmarks.scenario_3_cpu_bound",
        description="PBKDF2 hashing of 10MB payloads to stress process pools.",
        task_count=1_000,
        worker_count=4,
        warmup_seconds=20,
        tags=("cpu", "process"),
        requirements=("redis",),
        worker_profiles={
            Framework.ASYNCTASQ: WorkerConfig(
                framework=Framework.ASYNCTASQ,
                concurrency=8,
                queues=["cpu-bound"],
                description="ProcessTask pool pinned to cpu-bound queue",
            ),
            Framework.CELERY: WorkerConfig(
                framework=Framework.CELERY,
                app_path="tasks.celery_tasks",
                concurrency=8,
                pool="prefork",
                queues=["celery"],
                prefetch_multiplier=1,
                description="Celery prefork workers sized to available cores",
            ),
        },
    ),
    "4": ScenarioDefinition(
        id="4",
        name="Mixed Workload",
        module="benchmarks.scenario_4_mixed",
        description="Blend of 60% async I/O, 30% light CPU, and 10% heavy CPU to mimic real services.",
        task_count=10_000,
        worker_count=12,
        warmup_seconds=20,
        tags=("mixed", "mock-api"),
        requirements=("redis", "mock-api"),
        worker_profiles={
            Framework.ASYNCTASQ: WorkerConfig(
                framework=Framework.ASYNCTASQ,
                concurrency=24,
                queues=["default", "cpu-bound"],
                description="Mixed AsyncTasQ worker (default + cpu-bound queues)",
            ),
            Framework.CELERY: WorkerConfig(
                framework=Framework.CELERY,
                app_path="tasks.celery_tasks",
                concurrency=24,
                pool="prefork",
                queues=["celery"],
                prefetch_multiplier=2,
                description="Celery prefork tuned for heterogeneous workload",
            ),
        },
    ),
    # Planned scenarios - documented so users can see roadmap.
    "5": ScenarioDefinition(
        id="5",
        name="Serialization",
        module="",
        description="Msgpack vs JSON payloads, ORM fan-out",
        task_count=5_000,
        worker_count=8,
        warmup_seconds=10,
        tags=("serialization",),
        requirements=("redis",),
        implemented=False,
        notes="TODO: leverage ORM fixtures to compare payload sizes.",
    ),
    "6": ScenarioDefinition(
        id="6",
        name="Scalability Sweep",
        module="",
        description="Ramp from 1k to 100k tasks to study saturation and queue depth.",
        task_count=100_000,
        worker_count=12,
        warmup_seconds=30,
        tags=("scale",),
        implemented=False,
    ),
    "7": ScenarioDefinition(
        id="7",
        name="Real-World Pipeline",
        module="",
        description="E-commerce style orchestrations with retries and sagas.",
        task_count=2_000,
        worker_count=10,
        warmup_seconds=20,
        tags=("pipeline",),
        requirements=("redis", "mock-api"),
        implemented=False,
    ),
    "8": ScenarioDefinition(
        id="8",
        name="Cold Start",
        module="",
        description="Measure worker spin-up and first task latency.",
        task_count=200,
        worker_count=1,
        warmup_seconds=0,
        tags=("startup",),
        implemented=False,
    ),
    "9": ScenarioDefinition(
        id="9",
        name="Multi-Queue",
        module="",
        description="Priority routing and queue partitioning stress test.",
        task_count=8_000,
        worker_count=10,
        warmup_seconds=15,
        tags=("routing",),
        implemented=False,
    ),
    "10": ScenarioDefinition(
        id="10",
        name="Event Streaming",
        module="",
        description="Pub/Sub throughput and event emission overhead.",
        task_count=15_000,
        worker_count=10,
        warmup_seconds=15,
        tags=("events",),
        implemented=False,
    ),
    "11": ScenarioDefinition(
        id="11",
        name="FastAPI Integration",
        module="",
        description="HTTP dispatch path integration and request lifecycle hooks.",
        task_count=3_000,
        worker_count=6,
        warmup_seconds=10,
        tags=("fastapi",),
        requirements=("redis",),
        implemented=False,
    ),
}


# ----------------------------------------------------------------------------
# Registry helpers
# ----------------------------------------------------------------------------


def get_scenario_definition(scenario_id: str) -> ScenarioDefinition:
    """Return scenario metadata or raise helpful error."""

    try:
        return SCENARIO_REGISTRY[scenario_id]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Unknown scenario '{scenario_id}'.") from exc


def implemented_scenarios() -> dict[str, ScenarioDefinition]:
    """Return only scenarios that have runnable modules."""

    return {k: v for k, v in SCENARIO_REGISTRY.items() if v.implemented}


def scenario_choices(include_unimplemented: bool = False) -> Iterable[str]:
    """List scenario keys for CLI help text."""

    if include_unimplemented:
        return SCENARIO_REGISTRY.keys()
    return implemented_scenarios().keys()
