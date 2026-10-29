"""Measure a real native ledger journey without model inference.

Uses the enrolled CLI sequence, native profile worker and encrypted storage.
Boundary durations are inclusive: nested totals must not be added. Wall time
remains diagnostic on a shared host; CPU and call counts accompany it. Run
comparisons sequentially with distinct output directories.
"""

from __future__ import annotations

import argparse
from collections.abc import Generator
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import pytest

from dev.ci.modelo_runtime_benchmark import (
    RuntimeBenchmarkRecorder,
    copy_instrumented_worker,
    record_runtime_tree,
)
from dev.ci.modelo_runtime_benchmark import (
    observe_runtime_boundaries as observe_modelo_boundaries,
)
from dev.ci.profile_wizard_benchmark import _observe, observe_worker, summarize


@contextmanager
def observe_ledger_boundaries(recorder: RuntimeBenchmarkRecorder) -> Generator[None]:
    """Measure real IPC, custody, journals and transaction reads without payloads."""
    from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from cadrumo.adapters.persistence.storage.custody.tests.kdf_benchmark_observation import observe_kdf_startup
    from cadrumo_client.transport.framing import VerifiedConnection
    from cadrumo_client.transport.frontend_client import FrontendClient

    with pytest.MonkeyPatch.context() as patch, observe_modelo_boundaries(recorder), observe_worker(recorder):
        observe_kdf_startup(partial(_observe, patch, recorder))
        for owner, method, label in (
            (FrontendClient, "operation", "frontend.operation"),
            (FrontendClient, "contract", "frontend.contract"),
            (FrontendClient, "read_result_document", "frontend.result"),
            (VerifiedConnection, "operation", "ipc.exchange"),
            (TransactionCatalogueRepository, "load", "ledger.load"),
            (TransactionCatalogueRepository, "load_revisioned", "ledger.load_revisioned"),
        ):
            _observe(patch, recorder, owner, method, label)
        try:
            yield
        finally:
            recorder.flush()


def copy_ledger_worker(output: Path) -> Path:
    """Instrument the canonical native fixture, refusing a changed bootstrap."""
    worker = copy_instrumented_worker(output)
    source = worker.read_text(encoding="utf-8")
    original = "from dev.ci.modelo_runtime_benchmark import RuntimeBenchmarkRecorder, observe_worker_composition"
    replacement = (
        "from dev.ci.modelo_runtime_benchmark import RuntimeBenchmarkRecorder, observe_worker_composition\n"
        "    from dev.ci.ledger_runtime_benchmark import observe_ledger_boundaries"
    )
    if source.count(original) != 1:
        raise ValueError("instrumented worker bootstrap changed")
    source = source.replace(original, replacement)
    if source.count("profile_setup=False):") != 1:
        raise ValueError("instrumented worker observer setup changed")
    source = source.replace("profile_setup=False):", "profile_setup=False, observer=observe_ledger_boundaries):")
    compile(source, str(worker), "exec")
    worker.write_text(source, encoding="utf-8")
    return worker


def benchmark(output: Path, *, sequence_id: str) -> None:
    """Run one isolated journey and retain process-separated measurements."""
    from dev.docs.build import ensure_isolated_storage_root

    ensure_isolated_storage_root()
    from cadrumo.core.config import load_settings, override_settings
    from cadrumo.tests.env_scope import derived_storage_settings
    from dev.docs.sequences.checks import discover_sequences
    from dev.docs.sequences.runner import execute_sequence, observe_sequence_frames
    from dev.docs.sequences.runtime_fixture import sequence_worker_script

    discovered, problems = discover_sequences(page="how-to/classify-transactions", sequence_id=sequence_id)
    if problems or len(discovered) != 1:
        raise ValueError("benchmark requires exactly one enrolled ledger sequence")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    authority_root = load_settings().cadrumo_authority_root
    recorder = RuntimeBenchmarkRecorder(output, role="parent")
    worker = copy_ledger_worker(output)

    @contextmanager
    def frame(index: int) -> Generator[None]:
        with recorder.measure(f"sequence.frame.{index}"):
            yield
        recorder.flush()

    result = 1
    try:
        with (
            derived_storage_settings(output / "storage-base"),
            override_settings(cadrumo_authority_root=authority_root),
            sequence_worker_script(worker),
            observe_sequence_frames(frame),
            observe_ledger_boundaries(recorder),
            record_runtime_tree(recorder),
            recorder.measure("sequence.total"),
        ):
            execute_sequence(discovered[0].sequence, sandbox_root=output / "sandbox")
        result = 0
    finally:
        recorder.flush()
        summarize(output, result)


def main() -> int:
    """Run one ledger benchmark, refusing reused output directories."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sequence-id", default="classify-from-csv")
    args = parser.parse_args()
    benchmark(args.output, sequence_id=args.sequence_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
