"""Main benchmark runner.

Orchestrates all benchmark scenarios and generates reports.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from benchmarks.common import BenchmarkConfig, BenchmarkSummary, Driver, Framework

console = Console()


# Import all scenarios
SCENARIOS: dict[str, Any] = {
    "1": {
        "name": "Basic Throughput",
        "module": "benchmarks.scenario_1_throughput",
        "description": "Minimal tasks with no I/O or CPU work",
        "task_count": 20000,
        "worker_count": 10,
    },
    # Add more scenarios as they're implemented
}


async def run_scenario(
    scenario_id: str,
    framework: Framework,
    driver: Driver | None,
    runs: int,
) -> BenchmarkSummary:
    """Run a single scenario multiple times.

    Args:
        scenario_id: Scenario identifier (1-11)
        framework: Framework to test
        driver: Driver for AsyncTasQ (None for Celery)
        runs: Number of repetitions

    Returns:
        Benchmark summary with statistics
    """
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario_id}")

    scenario = SCENARIOS[scenario_id]

    # Import scenario module dynamically
    import importlib

    module = importlib.import_module(scenario["module"])

    # Create config
    config = BenchmarkConfig(
        framework=framework,
        driver=driver,
        task_count=scenario["task_count"],
        worker_count=scenario["worker_count"],
        runs=runs,
    )

    console.print(f"\n[bold cyan]Running Scenario {scenario_id}: {scenario['name']}[/bold cyan]")
    console.print(f"Framework: {framework.value}")
    if driver:
        console.print(f"Driver: {driver.value}")
    console.print(f"Tasks: {config.task_count}, Workers: {config.worker_count}, Runs: {runs}")

    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Running {runs} iterations...", total=runs)

        for run in range(1, runs + 1):
            progress.update(task, description=f"Run {run}/{runs}")

            config.runs = run
            result = await module.run_benchmark(config)
            results.append(result)

            progress.advance(task)

    summary = BenchmarkSummary(config=config, results=results)

    # Display results
    _display_summary(scenario_id, scenario["name"], summary)

    return summary


def _display_summary(scenario_id: str, scenario_name: str, summary: BenchmarkSummary) -> None:
    """Display benchmark summary in a formatted table."""
    table = Table(title=f"Scenario {scenario_id}: {scenario_name} - Results")

    table.add_column("Metric", style="cyan")
    table.add_column("Mean", justify="right", style="green")
    table.add_column("Median", justify="right", style="yellow")
    table.add_column("StdDev", justify="right", style="magenta")
    table.add_column("Min", justify="right", style="blue")
    table.add_column("Max", justify="right", style="red")

    # Throughput
    stats = summary.throughput_stats
    table.add_row(
        "Throughput (tasks/sec)",
        f"{stats['mean']:.0f}",
        f"{stats['median']:.0f}",
        f"{stats['stdev']:.0f}",
        f"{stats['min']:.0f}",
        f"{stats['max']:.0f}",
    )

    # Mean latency
    stats = summary.mean_latency_stats
    table.add_row(
        "Mean Latency (ms)",
        f"{stats['mean']:.2f}",
        f"{stats['median']:.2f}",
        f"{stats['stdev']:.2f}",
        f"{stats['min']:.2f}",
        f"{stats['max']:.2f}",
    )

    # P95 latency
    stats = summary.p95_latency_stats
    table.add_row(
        "P95 Latency (ms)",
        f"{stats['mean']:.2f}",
        f"{stats['median']:.2f}",
        f"{stats['stdev']:.2f}",
        f"{stats['min']:.2f}",
        f"{stats['max']:.2f}",
    )

    # P99 latency
    stats = summary.p99_latency_stats
    table.add_row(
        "P99 Latency (ms)",
        f"{stats['mean']:.2f}",
        f"{stats['median']:.2f}",
        f"{stats['stdev']:.2f}",
        f"{stats['min']:.2f}",
        f"{stats['max']:.2f}",
    )

    # Memory
    stats = summary.memory_stats
    table.add_row(
        "Memory (MB)",
        f"{stats['mean']:.1f}",
        f"{stats['median']:.1f}",
        f"{stats['stdev']:.1f}",
        f"{stats['min']:.1f}",
        f"{stats['max']:.1f}",
    )

    # CPU
    stats = summary.cpu_stats
    table.add_row(
        "CPU (%)",
        f"{stats['mean']:.1f}",
        f"{stats['median']:.1f}",
        f"{stats['stdev']:.1f}",
        f"{stats['min']:.1f}",
        f"{stats['max']:.1f}",
    )

    console.print(table)


def save_results(summaries: list[BenchmarkSummary], output_dir: Path) -> None:
    """Save benchmark results to JSON files.

    Args:
        summaries: List of benchmark summaries
        output_dir: Output directory for results
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for summary in summaries:
        framework = summary.config.framework.value
        driver = summary.config.driver.value if summary.config.driver else "default"
        scenario_id = "unknown"  # TODO: Extract from config

        filename = f"scenario_{scenario_id}_{framework}_{driver}.json"
        filepath = output_dir / filename

        with open(filepath, "w") as f:
            json.dump(summary.to_dict(), f, indent=2)

        console.print(f"[green]✓[/green] Saved results to {filepath}")


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AsyncTasQ vs Celery Benchmark Suite")
    parser.add_argument(
        "--scenario",
        type=str,
        help="Scenario ID to run (1-11). Omit for all scenarios.",
    )
    parser.add_argument(
        "--framework",
        type=str,
        choices=["asynctasq", "celery", "both"],
        default="both",
        help="Framework to test (default: both)",
    )
    parser.add_argument(
        "--driver",
        type=str,
        choices=["redis"],
        default="redis",
        help="Driver for AsyncTasQ (only Redis supported in this benchmark)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of repetitions per scenario (default: 10)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results"),
        help="Output directory for results (default: ./results)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all scenarios",
    )

    args = parser.parse_args()

    # Determine scenarios to run
    if args.all or args.scenario is None:
        scenario_ids = list(SCENARIOS.keys())
    else:
        scenario_ids = [args.scenario]

    # Determine frameworks to test
    if args.framework == "both":
        frameworks = [Framework.ASYNCTASQ, Framework.CELERY]
    else:
        frameworks = [Framework(args.framework)]

    # Determine drivers (AsyncTasQ only)
    if args.driver == "all":
        drivers = list(Driver)
    else:
        drivers = [Driver(args.driver)]

    console.print("[bold green]AsyncTasQ vs Celery Benchmark Suite[/bold green]\n")
    console.print(f"Scenarios: {', '.join(scenario_ids)}")
    console.print(f"Frameworks: {', '.join(f.value for f in frameworks)}")
    console.print(f"Runs per scenario: {args.runs}")
    console.print(f"Output: {args.output}\n")

    summaries: list[BenchmarkSummary] = []

    for scenario_id in scenario_ids:
        for framework in frameworks:
            if framework == Framework.ASYNCTASQ:
                for driver in drivers:
                    summary = await run_scenario(scenario_id, framework, driver, args.runs)
                    summaries.append(summary)
            else:
                summary = await run_scenario(scenario_id, framework, None, args.runs)
                summaries.append(summary)

    # Save all results
    save_results(summaries, args.output)

    console.print("\n[bold green]✓ Benchmark complete![/bold green]")
    console.print(f"Results saved to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
