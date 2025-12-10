"""Visualization tools for benchmark results."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from rich.console import Console
import seaborn as sns

console = Console()

# Set style
sns.set_theme(style="whitegrid")
plt.rcParams["figure.figsize"] = (12, 6)


def load_results_as_dataframe(results_dir: Path) -> pd.DataFrame:
    """Load all results into a pandas DataFrame.

    Args:
        results_dir: Directory containing JSON result files

    Returns:
        DataFrame with all benchmark data
    """
    rows = []

    for filepath in results_dir.glob("scenario_*.json"):
        with open(filepath) as f:
            data = json.load(f)

        # Extract scenario ID from filename
        parts = filepath.stem.split("_")
        scenario_id = parts[1] if len(parts) > 1 else "unknown"

        rows.append(
            {
                "scenario": scenario_id,
                "framework": data["framework"],
                "driver": data.get("driver", "default"),
                "throughput": data["throughput"]["mean"],
                "mean_latency_ms": data["mean_latency_ms"]["mean"],
                "p95_latency_ms": data["p95_latency_ms"]["mean"],
                "p99_latency_ms": data["p99_latency_ms"]["mean"],
                "memory_mb": data["memory_mb"]["mean"],
                "cpu_percent": data["cpu_percent"]["mean"],
            }
        )

    return pd.DataFrame(rows)


def plot_throughput_comparison(df: pd.DataFrame, output_file: Path) -> None:
    """Create throughput comparison bar chart.

    Args:
        df: DataFrame with benchmark results
        output_file: Path to save plot
    """
    plt.figure(figsize=(14, 8))

    # Group by scenario and framework
    pivot = df.pivot_table(
        values="throughput",
        index="scenario",
        columns="framework",
        aggfunc="mean",
    )

    ax = pivot.plot(kind="bar", width=0.8)
    plt.title("Throughput Comparison: AsyncTasQ vs Celery", fontsize=16, fontweight="bold")
    plt.xlabel("Scenario", fontsize=12)
    plt.ylabel("Throughput (tasks/sec)", fontsize=12)
    plt.legend(title="Framework", fontsize=11)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    # Add value labels on bars
    for container in ax.containers:
        ax.bar_label(container, fmt="%.0f", padding=3)

    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    console.print(f"[green]✓[/green] Saved throughput chart to {output_file}")
    plt.close()


def plot_latency_comparison(df: pd.DataFrame, output_file: Path) -> None:
    """Create latency comparison chart with P95/P99.

    Args:
        df: DataFrame with benchmark results
        output_file: Path to save plot
    """
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    metrics = ["mean_latency_ms", "p95_latency_ms", "p99_latency_ms"]
    titles = ["Mean Latency", "P95 Latency", "P99 Latency"]

    for ax, metric, title in zip(axes, metrics, titles, strict=True):
        pivot = df.pivot_table(
            values=metric,
            index="scenario",
            columns="framework",
            aggfunc="mean",
        )

        pivot.plot(kind="bar", ax=ax, width=0.8)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel("Scenario", fontsize=11)
        ax.set_ylabel("Latency (ms)", fontsize=11)
        ax.legend(title="Framework", fontsize=10)
        ax.tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    console.print(f"[green]✓[/green] Saved latency chart to {output_file}")
    plt.close()


def plot_resource_usage(df: pd.DataFrame, output_file: Path) -> None:
    """Create resource usage comparison (memory and CPU).

    Args:
        df: DataFrame with benchmark results
        output_file: Path to save plot
    """
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Memory usage
    pivot_memory = df.pivot_table(
        values="memory_mb",
        index="scenario",
        columns="framework",
        aggfunc="mean",
    )

    pivot_memory.plot(kind="bar", ax=axes[0], width=0.8, color=["#3498db", "#e74c3c"])
    axes[0].set_title("Memory Usage", fontsize=14, fontweight="bold")
    axes[0].set_xlabel("Scenario", fontsize=11)
    axes[0].set_ylabel("Memory (MB)", fontsize=11)
    axes[0].legend(title="Framework", fontsize=10)
    axes[0].tick_params(axis="x", rotation=45)

    # CPU usage
    pivot_cpu = df.pivot_table(
        values="cpu_percent",
        index="scenario",
        columns="framework",
        aggfunc="mean",
    )

    pivot_cpu.plot(kind="bar", ax=axes[1], width=0.8, color=["#2ecc71", "#f39c12"])
    axes[1].set_title("CPU Utilization", fontsize=14, fontweight="bold")
    axes[1].set_xlabel("Scenario", fontsize=11)
    axes[1].set_ylabel("CPU (%)", fontsize=11)
    axes[1].legend(title="Framework", fontsize=10)
    axes[1].tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    console.print(f"[green]✓[/green] Saved resource usage chart to {output_file}")
    plt.close()


def plot_driver_comparison(df: pd.DataFrame, output_file: Path) -> None:
    """Create AsyncTasQ multi-driver performance comparison.

    Args:
        df: DataFrame with benchmark results
        output_file: Path to save plot
    """
    # Filter AsyncTasQ results only
    asynctasq_df = df[df["framework"] == "asynctasq"].copy()

    if asynctasq_df.empty:
        console.print("[yellow]⚠[/yellow] No AsyncTasQ multi-driver data found")
        return

    plt.figure(figsize=(14, 8))

    pivot = asynctasq_df.pivot_table(
        values="throughput",
        index="scenario",
        columns="driver",
        aggfunc="mean",
    )

    ax = pivot.plot(kind="bar", width=0.8)
    plt.title("AsyncTasQ Driver Performance Comparison", fontsize=16, fontweight="bold")
    plt.xlabel("Scenario", fontsize=12)
    plt.ylabel("Throughput (tasks/sec)", fontsize=12)
    plt.legend(title="Driver", fontsize=11)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    # Add value labels
    for container in ax.containers:
        ax.bar_label(container, fmt="%.0f", padding=3)

    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    console.print(f"[green]✓[/green] Saved driver comparison chart to {output_file}")
    plt.close()


def generate_all_visualizations(results_dir: Path, output_dir: Path) -> None:
    """Generate all visualization charts.

    Args:
        results_dir: Directory containing benchmark results
        output_dir: Directory to save charts
    """
    console.print("[bold cyan]Generating Visualizations[/bold cyan]\n")

    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_results_as_dataframe(results_dir)

    if df.empty:
        console.print("[red]✗[/red] No results found in {results_dir}")
        return

    console.print(f"Loaded {len(df)} benchmark results\n")

    # Generate all charts
    plot_throughput_comparison(df, output_dir / "throughput_comparison.png")
    plot_latency_comparison(df, output_dir / "latency_comparison.png")
    plot_resource_usage(df, output_dir / "resource_usage.png")
    plot_driver_comparison(df, output_dir / "driver_comparison.png")

    console.print("\n[bold green]✓ All visualizations generated![/bold green]")


if __name__ == "__main__":
    import sys

    results_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results")
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("results/charts")

    generate_all_visualizations(results_dir, output_dir)
