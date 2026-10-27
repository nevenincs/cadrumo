"""Benchmark diagnostic producers and Windows handles using synthetic records only."""

from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from cadrumo.core.config import override_settings
from cadrumo.core.diagnostic_dispatch import DiagnosticDispatch
from cadrumo.core.log_file_handler import AnnouncingRotatingFileHandler
from cadrumo.core.logging import (
    configure_logging,
    diagnostic_delivery_status,
    flush_logging,
    get_logger,
    shutdown_logging,
)


def _handles() -> int | None:
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    current = kernel.GetCurrentProcess
    current.argtypes, current.restype = (), wintypes.HANDLE
    count = kernel.GetProcessHandleCount
    count.argtypes, count.restype = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)), wintypes.BOOL
    result = wintypes.DWORD()
    if not count(current(), ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    return result.value


def _percentile(values: list[int], fraction: float) -> float:
    return values[min(len(values) - 1, int(len(values) * fraction))] / 1000


def main() -> None:
    """Emit a bounded benchmark report, never diagnostic payloads."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("normal", "slow", "blocked"), default="normal")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--records", type=int, default=5000)
    parser.add_argument("--duration", type=float, default=0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ready", type=Path)
    options = parser.parse_args()
    if not 1 <= options.threads <= 32 or not 1 <= options.records <= 1_000_000 or not 0 <= options.duration <= 120:
        parser.error("threads must be 1..32, records 1..1000000 and duration 0..120")
    baseline_handles = _handles()
    entered, release = threading.Event(), threading.Event()
    original = AnnouncingRotatingFileHandler.emit

    def emit(self: AnnouncingRotatingFileHandler, record: logging.LogRecord) -> None:
        entered.set()
        if options.mode == "blocked":
            release.wait(180)
        elif options.mode == "slow":
            release.wait(0.005)
        original(self, record)

    with tempfile.TemporaryDirectory(prefix="cadrumo-logging-benchmark-") as directory:
        with override_settings(
            cadrumo_local_storage_root=Path(directory),
            cadrumo_log_dir=Path(directory) / "logs",
            cadrumo_log_stderr_level="CRITICAL",
            cadrumo_log_file_max_bytes=10 * 1024 * 1024,
        ):
            configure_logging()
        if not flush_logging(timeout=10):
            raise RuntimeError("logging configuration did not settle")
        logger = get_logger("cadrumo.benchmarks.logging")
        logger.info("benchmark warmup")
        if not flush_logging(timeout=10):
            raise RuntimeError("logging warmup did not settle")
        warm_handles = _handles()
        AnnouncingRotatingFileHandler.emit = emit
        try:
            logger.warning("benchmark sink admission")
            if not entered.wait(5):
                raise RuntimeError("file sink did not receive its probe")
            if options.ready is not None:
                options.ready.write_text(json.dumps({"pid": os.getpid(), "mode": options.mode}), encoding="utf-8")
            barrier = threading.Barrier(options.threads + 1)

            def produce(writer: int) -> tuple[int, list[int]]:
                samples: list[int] = []
                barrier.wait()
                deadline = time.monotonic() + options.duration
                count = 0
                while count < options.records or (options.duration > 0 and time.monotonic() < deadline):
                    started = time.perf_counter_ns()
                    logger.info("logging benchmark writer=%d record=%d", writer, count)
                    elapsed = time.perf_counter_ns() - started
                    if len(samples) < 8192:
                        samples.append(elapsed)
                    count += 1
                return count, samples

            with ThreadPoolExecutor(max_workers=options.threads) as pool:
                futures = [pool.submit(produce, writer) for writer in range(options.threads)]
                started = time.monotonic()
                barrier.wait()
                measurements = [future.result() for future in futures]
                elapsed = time.monotonic() - started
            blocked_status = {name: asdict(status) for name, status in diagnostic_delivery_status().items()}
            release.set()
            drained = flush_logging(timeout=15)
            final_status = {name: asdict(status) for name, status in diagnostic_delivery_status().items()}
        finally:
            release.set()
            AnnouncingRotatingFileHandler.emit = original
        shutdown_logging(timeout=2)
    # Repeated queue lifetimes expose leaked native thread or event handles.
    before_churn = _handles()
    for _ in range(100):
        queue = DiagnosticDispatch[int](lambda _: None, name="diagnostic-handle-probe")
        queue.submit(1)
        if not queue.close(timeout=1):
            raise RuntimeError("diagnostic queue did not terminate")
    time.sleep(0.05)
    after_churn = _handles()
    samples = sorted(sample for _, values in measurements for sample in values)
    records = sum(count for count, _ in measurements)
    report = {
        "pid": os.getpid(),
        "mode": options.mode,
        "threads": options.threads,
        "records": records,
        "producer_seconds": elapsed,
        "records_per_second": records / elapsed,
        "latency_us": {
            "median": statistics.median(samples) / 1000,
            "p95": _percentile(samples, 0.95),
            "p99": _percentile(samples, 0.99),
            "maximum_sampled": max(samples) / 1000,
        },
        "drained": drained,
        "while_producing": blocked_status,
        "after_drain": final_status,
        "handles": {
            "baseline": baseline_handles,
            "warm": warm_handles,
            "before_100_queue_lifetimes": before_churn,
            "after_100_queue_lifetimes": after_churn,
        },
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
