"""Ledger measurements retain real behavior and restore all observation hooks."""

from __future__ import annotations

import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.tests.audited_process import run_audited_process
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient

from ..ledger_runtime_benchmark import copy_ledger_worker, observe_ledger_boundaries
from ..modelo_runtime_benchmark import RuntimeBenchmarkRecorder, observe_worker_composition

pytestmark = [pytest.mark.hex_core]


@pytest.mark.unit
def test_worker_composition_uses_selected_observer(tmp_path: Path) -> None:
    events: list[str] = []
    recorder = RuntimeBenchmarkRecorder(tmp_path, role="worker")

    @contextmanager
    def composition() -> Generator[None]:
        events.append("composition")
        yield

    @contextmanager
    def observer(selected: RuntimeBenchmarkRecorder) -> Generator[None]:
        assert selected is recorder
        events.append("observer")
        yield

    with observe_worker_composition(recorder, composition, observer=observer):
        assert events == ["composition", "observer"]


@pytest.mark.unit
def test_ledger_observers_restore_on_failure_without_logging_exception_payload(tmp_path: Path) -> None:
    watched = (
        (FrontendClient, "operation"),
        (FrontendClient, "contract"),
        (FrontendClient, "read_result_document"),
        (VerifiedConnection, "operation"),
        (TransactionCatalogueRepository, "load"),
        (TransactionCatalogueRepository, "load_revisioned"),
    )
    originals = [getattr(owner, name) for owner, name in watched]
    recorder = RuntimeBenchmarkRecorder(tmp_path, role="parent")
    error = RuntimeError("synthetic-private-payload")
    with pytest.raises(RuntimeError) as caught, observe_ledger_boundaries(recorder):
        for (owner, name), original in zip(watched, originals, strict=True):
            assert getattr(owner, name) is not original
        raise error

    assert caught.value is error
    for (owner, name), original in zip(watched, originals, strict=True):
        assert getattr(owner, name) is original
    assert str(error) not in recorder.path.read_text(encoding="utf-8")


@pytest.mark.integration
def test_ledger_worker_reaches_the_real_isolated_native_parser(tmp_path: Path) -> None:
    child = copy_ledger_worker(tmp_path)
    result = run_audited_process(
        [sys.executable, "-I", str(child), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=None,
    )
    assert result.returncode == 0, result.stderr
    assert isinstance(result.stdout, str)
    assert "--storage-root" in result.stdout
    assert "--worker-id" in result.stdout
