from collections.abc import Sequence
import os
from pathlib import Path
import signal
import subprocess
import time

from rich.console import Console

from benchmarks.common import Framework, WorkerConfig

console = Console()


class WorkerManager:
    """Fire-and-forget worker launcher used by the benchmark runner."""

    def __init__(self) -> None:
        self.processes: list[subprocess.Popen] = []
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

    def start_workers(self, configs: Sequence[WorkerConfig]) -> None:
        """Start one or more worker groups based on the provided configs."""

        if not configs:
            console.print("[yellow]No worker configs provided; assuming manual workers.[/yellow]")
            return

        self.stop_workers()

        for config in configs:
            self._launch_group(config)

    def _launch_group(self, config: WorkerConfig) -> None:
        env = os.environ.copy()
        env.update(config.env_overrides)
        env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")

        if config.framework == Framework.CELERY and config.prefetch_multiplier is not None:
            env.setdefault("CELERY_WORKER_PREFETCH_MULTIPLIER", str(config.prefetch_multiplier))

        cmd = self._build_command(config)
        console.print(
            f"[bold blue]Starting {config.worker_count} {config.framework.value} worker(s) ({config.description or 'no description'})...[/bold blue]"
        )
        console.print(f"[dim]Command: {' '.join(cmd)}[/dim]")

        for idx in range(config.worker_count):
            log_file = self.log_dir / f"{config.framework.value}_worker_{idx}.log"
            with open(log_file, "w", encoding="utf-8") as handle:
                process = subprocess.Popen(
                    cmd,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    env=env,
                    cwd=os.getcwd(),
                    preexec_fn=os.setsid,
                )
                self.processes.append(process)

        time.sleep(5)

    def _build_command(self, config: WorkerConfig) -> list[str]:
        if config.framework == Framework.ASYNCTASQ:
            cmd: list[str] = [
                "uv",
                "run",
                "python",
                "-m",
                "asynctasq",
                "worker",
                "--concurrency",
                str(config.concurrency),
                "--log-level",
                config.log_level.lower(),
            ]
            if config.queues:
                cmd.extend(["--queues", ",".join(config.queues)])
            cmd.extend(config.extra_args)
            return cmd

        if config.framework == Framework.CELERY:
            cmd = [
                "uv",
                "run",
                "celery",
                "-A",
                config.app_path or "tasks.celery_tasks",
                "worker",
                f"--loglevel={config.log_level.lower()}",
                f"--concurrency={config.concurrency}",
                f"--pool={config.pool}",
            ]
            if config.autoscale:
                cmd.append(f"--autoscale={config.autoscale[0]},{config.autoscale[1]}")
            if config.queues:
                cmd.extend(["-Q", ",".join(config.queues)])
            cmd.extend(config.extra_args)
            return cmd

        raise ValueError(f"Unsupported framework: {config.framework}")

    def stop_workers(self):
        if not self.processes:
            return

        console.print(f"[bold yellow]Stopping {len(self.processes)} workers...[/bold yellow]")
        for p in self.processes:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass

        # Wait for exit
        for p in self.processes:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass

        self.processes = []
