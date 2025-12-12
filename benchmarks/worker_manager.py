import os
from pathlib import Path
import signal
import subprocess
import time

from rich.console import Console

from benchmarks.common import Framework, WorkerConfig

console = Console()


class WorkerManager:
    def __init__(self):
        self.processes: list[subprocess.Popen] = []
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)

    def start_workers(self, config: WorkerConfig):
        self.stop_workers()

        cmd = []
        env = os.environ.copy()
        # Ensure current directory is in PYTHONPATH
        env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")

        if config.framework == Framework.CELERY:
            # Celery command
            # celery -A tasks.celery_tasks worker --loglevel=INFO --concurrency=...
            cmd = [
                "celery",
                "-A",
                config.app_path,
                "worker",
                "--loglevel=INFO",
                f"--concurrency={config.concurrency}",
                f"--pool={config.pool}",
                "-O",
                "fair",
                # "-E", # Enable events for monitoring if needed
            ]
            # Add queues if specified
            if config.queues:
                cmd.extend(["-Q", ",".join(config.queues)])

        elif config.framework == Framework.ASYNCTASQ:
            # AsyncTasQ command
            # asynctasq worker --concurrency ...
            # Note: asynctasq CLI doesn't take an app path, but relies on importability of tasks
            # We assume tasks are defined in tasks.asynctasq_tasks and will be imported by the worker
            # when deserializing if they are in PYTHONPATH.
            # However, to be safe, we might want to preload them if possible, but the CLI doesn't support it.
            # We rely on the fact that we are running from the root and tasks.asynctasq_tasks is importable.

            cmd = [
                "asynctasq",
                "worker",
                "--concurrency",
                str(config.concurrency),
                "--loglevel",
                "INFO",
            ]
            # Add queues if specified
            if config.queues:
                cmd.extend(["--queues", ",".join(config.queues)])

        console.print(
            f"[bold blue]Starting {config.worker_count} {config.framework} workers...[/bold blue]"
        )
        console.print(f"[dim]Command: {' '.join(cmd)}[/dim]")

        for i in range(config.worker_count):
            log_file = self.log_dir / f"{config.framework}_worker_{i}.log"
            with open(log_file, "w") as f:
                p = subprocess.Popen(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    cwd=os.getcwd(),
                    preexec_fn=os.setsid,  # Create new process group for clean kill
                )
                self.processes.append(p)

        # Wait for workers to be ready (naive wait)
        # Ideally we would check for a "ready" log message
        time.sleep(5)

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
