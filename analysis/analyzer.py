"""Statistical analysis of benchmark results."""

from __future__ import annotations

import json
from pathlib import Path
import statistics
from typing import Any

import numpy as np
from rich.console import Console
from rich.table import Table
from scipy import stats

console = Console()


def load_results(results_dir: Path) -> dict[str, Any]:
    """Load all benchmark results from directory.

    Args:
        results_dir: Directory containing JSON result files

    Returns:
        Dictionary mapping (scenario, framework, driver) to results
    """
    results: dict[str, Any] = {}

    for filepath in results_dir.glob("scenario_*.json"):
        with open(filepath) as f:
            data = json.load(f)

        key = (
            filepath.stem,  # scenario_1_asynctasq_redis
            data["framework"],
            data.get("driver", "default"),
        )
        results[key] = data

    return results


def compare_frameworks(
    asynctasq_results: dict[str, Any],
    celery_results: dict[str, Any],
) -> dict[str, Any]:
    """Compare AsyncTasQ vs Celery performance with statistical tests.

    Args:
        asynctasq_results: AsyncTasQ benchmark data
        celery_results: Celery benchmark data

    Returns:
        Comparison statistics including t-test results
    """
    comparison: dict[str, Any] = {}

    # Compare throughput
    asynctasq_throughput = asynctasq_results["throughput"]["mean"]
    celery_throughput = celery_results["throughput"]["mean"]

    speedup = asynctasq_throughput / celery_throughput if celery_throughput > 0 else 0

    comparison["throughput"] = {
        "asynctasq": asynctasq_throughput,
        "celery": celery_throughput,
        "speedup": speedup,
        "percent_improvement": (speedup - 1) * 100,
    }

    # Compare latency
    asynctasq_latency = asynctasq_results["mean_latency_ms"]["mean"]
    celery_latency = celery_results["mean_latency_ms"]["mean"]

    latency_reduction = (1 - asynctasq_latency / celery_latency) * 100 if celery_latency > 0 else 0

    comparison["latency"] = {
        "asynctasq_ms": asynctasq_latency,
        "celery_ms": celery_latency,
        "reduction_percent": latency_reduction,
    }

    # Compare memory
    asynctasq_memory = asynctasq_results["memory_mb"]["mean"]
    celery_memory = celery_results["memory_mb"]["mean"]

    memory_reduction = (1 - asynctasq_memory / celery_memory) * 100 if celery_memory > 0 else 0

    comparison["memory"] = {
        "asynctasq_mb": asynctasq_memory,
        "celery_mb": celery_memory,
        "reduction_percent": memory_reduction,
    }

    return comparison


def calculate_effect_size(group1: list[float], group2: list[float]) -> float:
    """Calculate Cohen's d effect size.

    Args:
        group1: First group of measurements
        group2: Second group of measurements

    Returns:
        Cohen's d effect size
    """
    mean1 = statistics.mean(group1)
    mean2 = statistics.mean(group2)

    std1 = statistics.stdev(group1) if len(group1) > 1 else 0
    std2 = statistics.stdev(group2) if len(group2) > 1 else 0

    pooled_std = np.sqrt((std1**2 + std2**2) / 2)

    if pooled_std == 0:
        return 0.0

    return (mean1 - mean2) / pooled_std


def run_t_test(
    asynctasq_values: list[float],
    celery_values: list[float],
) -> dict[str, Any]:
    """Run independent t-test to compare two groups.

    Args:
        asynctasq_values: AsyncTasQ measurements
        celery_values: Celery measurements

    Returns:
        T-test results with p-value and effect size
    """
    t_stat, p_value = stats.ttest_ind(asynctasq_values, celery_values)
    effect_size = calculate_effect_size(asynctasq_values, celery_values)

    # Convert p_value to float for comparison to avoid tuple type issues
    p_val_float = float(p_value)

    return {
        "t_statistic": float(t_stat),
        "p_value": p_val_float,
        "significant": p_val_float < 0.05,
        "effect_size": float(effect_size),
        "interpretation": _interpret_effect_size(effect_size),
    }


def _interpret_effect_size(d: float) -> str:
    """Interpret Cohen's d effect size.

    Args:
        d: Cohen's d value

    Returns:
        Human-readable interpretation
    """
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


def generate_comparison_report(results_dir: Path, output_file: Path) -> None:
    """Generate comprehensive comparison report.

    Args:
        results_dir: Directory containing benchmark results
        output_file: Path to save report
    """
    console.print("[bold cyan]Generating Statistical Analysis Report[/bold cyan]\n")

    results = load_results(results_dir)

    # Group by scenario
    scenarios: dict[str, dict[str, Any]] = {}

    for (scenario_id, framework, driver), data in results.items():
        if scenario_id not in scenarios:
            scenarios[scenario_id] = {}

        key = f"{framework}_{driver}"
        scenarios[scenario_id][key] = data

    # Generate report
    report = {
        "summary": {},
        "scenarios": {},
    }

    for scenario_id, scenario_data in scenarios.items():
        console.print(f"[yellow]Analyzing {scenario_id}...[/yellow]")

        # Find AsyncTasQ and Celery results
        asynctasq_key = next((k for k in scenario_data if k.startswith("asynctasq")), None)
        celery_key = next((k for k in scenario_data if k.startswith("celery")), None)

        if asynctasq_key and celery_key:
            comparison = compare_frameworks(
                scenario_data[asynctasq_key],
                scenario_data[celery_key],
            )

            report["scenarios"][scenario_id] = comparison

    # Save report
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    console.print(f"\n[green]✓[/green] Report saved to {output_file}")

    # Display summary table
    _display_comparison_table(report)


def _display_comparison_table(report: dict[str, Any]) -> None:
    """Display comparison results in a table."""
    table = Table(title="AsyncTasQ vs Celery - Performance Comparison")

    table.add_column("Scenario", style="cyan")
    table.add_column("Throughput Speedup", justify="right", style="green")
    table.add_column("Latency Reduction", justify="right", style="yellow")
    table.add_column("Memory Reduction", justify="right", style="magenta")

    for scenario_id, data in report["scenarios"].items():
        throughput_speedup = data["throughput"]["speedup"]
        latency_reduction = data["latency"]["reduction_percent"]
        memory_reduction = data["memory"]["reduction_percent"]

        table.add_row(
            scenario_id,
            f"{throughput_speedup:.2f}x",
            f"{latency_reduction:.1f}%",
            f"{memory_reduction:.1f}%",
        )

    console.print(table)


if __name__ == "__main__":
    import sys

    results_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results")
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("results/analysis_report.json")

    generate_comparison_report(results_dir, output_file)
