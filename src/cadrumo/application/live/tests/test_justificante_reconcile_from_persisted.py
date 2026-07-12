"""Persisted justificante reconciliation tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core import Modelo
from ...modelo import ModeloReconciliationVerdict, ReconciliationEvidenceInvalidError, list_modelo_reconciliations
from .._justificante import JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE, reconcile_capture
from ._justificante_reconcile_support import (
    MODELO_130_FIXTURE,
    _active_bucket_id,
    _persist_capture,
    _seed_work_unit,
    isolated_justificante_backend,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_justificante_backend(tmp_path):
        yield


def test_reconcile_from_persisted_capture_matches() -> None:
    """A persisted real-fixture capture reconciles to MATCHES against its work unit."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    report = reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert report.diffs == ()
    assert report.work_unit_id == work_unit_id
    assert report.source_path == f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{snapshot.snapshot_id}"
    history = list_modelo_reconciliations(bucket_id=_active_bucket_id(), work_unit_id=work_unit_id)
    assert len(history) == 1
    assert history[0].source_path == report.source_path


def test_reconcile_from_persisted_capture_writes_nothing_to_disk(tmp_path: Path) -> None:
    """The live reconcile parses the receipt from in-memory bytes only.

    Honours ``sensitive-financial-data-secure-storage-only``: the decrypted
    justificante bytes must not persist as plaintext. The real secure store and
    parser run unmocked; this test verifies the reconciliation is addressed by
    its secure-object reference and that the isolated storage tree contains no
    durable copy of the raw PDF bytes after the reconcile call.
    """
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    pdf_bytes = MODELO_130_FIXTURE.read_bytes()
    snapshot = _persist_capture(
        pdf_bytes=pdf_bytes,
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    report = reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert report.source_path == f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{snapshot.snapshot_id}"
    assert _files_containing_bytes(tmp_path, pdf_bytes) == ()


def _files_containing_bytes(root: Path, needle: bytes) -> tuple[Path, ...]:
    matches: list[Path] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        try:
            if needle in path.read_bytes():
                matches.append(path.relative_to(root))
        except OSError:
            continue
    return tuple(matches)


def test_reconcile_from_persisted_capture_mismatches_on_modelo() -> None:
    """A 303 work unit reconciled against the persisted 130 capture mismatches."""
    work_unit_id = _seed_work_unit(modelo="303", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=MODELO_130_FIXTURE.read_bytes(),
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    report = reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    assert any(diff.field_name == "modelo" for diff in report.diffs)


def test_reconcile_from_malformed_capture_raises_without_leaking_temp_path() -> None:
    """A capture whose bytes are not a parseable justificante refuses cleanly.

    The persisted secure object reference is the only source identifier surfaced
    in the error; no plaintext filesystem path is involved.
    """
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    snapshot = _persist_capture(
        pdf_bytes=b"%PDF-1.4\nnot a real justificante\n%%EOF\n",
        modelo=Modelo.M130.value,
        filing_year=2026,
        period="1T",
    )

    with pytest.raises(ReconciliationEvidenceInvalidError) as exc_info:
        reconcile_capture(work_unit_id=work_unit_id, snapshot=snapshot)
    message = str(exc_info.value)
    assert f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{snapshot.snapshot_id}" in message
    assert "Temp" not in message
    assert ".pdf" not in message
