"""An export receipt must describe the artefact it names, not merely a payload.

``DeclaracionExportResult`` documents ``byte_size`` and ``file_sha256`` as
metadata of the file at ``output_path``, and the modelo export service
transplants both onto a *different* path: the draft renderer measures the
sibling ``.tmp`` staging file, and ``ModeloExportResult`` republishes those
numbers against the operator-visible destination after an atomic rename. The
same pair is written into the durable ``MODELO_EXPORTED`` bucket event, where a
wrong number outlives the artefact.

Nothing compared the two. Every field was individually well-formed -- a real
digest of real bytes, a non-negative size -- so no shape constraint could see a
receipt that truthfully describes a payload which is not the file it points at.
The tabular seam had already answered this for a result that *carries* its
payload (``verify_export_metadata`` validates the metadata against the bytes in
the model); a filing receipt carries a path instead, so the binding has to read
the artefact and therefore cannot live in the model.

One declaration, two consumers: the draft writer supplies the path it just
wrote, and the work-unit finaliser supplies the destination it renamed into
place. Each supplies the path it legitimately knows, so the binding is one
invariant rather than two conventions.

Real registry snapshots, real drafts, real files on disk, real digests. Only
the artefact bytes are ever rewritten, and only after a genuine export produced
them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.hashing import sha256_hex
from ....domain.filing import FilingExportError
from .._export import (
    DeclaracionExportFormat,
    DeclaracionExportResult,
    assert_export_artifact_matches_receipt,
    export_draft,
)
from ._export_support import (
    _approved_registry_draft,
    _modelo_130_export_headers,
    _schema_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _real_export(tmp_path: Path) -> tuple[DeclaracionExportResult, Path]:
    """Run a genuine registry-backed export and return its receipt and artefact."""
    output_path = tmp_path / "modelo-130-2026Q1.boe"
    receipt = export_draft(
        _approved_registry_draft(),
        output_path=output_path,
        headers=_modelo_130_export_headers(),
        schema_provider=_schema_provider(),
    )
    return receipt, output_path


def test_receipt_binding_accepts_the_artefact_the_export_actually_wrote(tmp_path: Path) -> None:
    """Positive control: a refuse-everything binding cannot satisfy this suite."""
    receipt, output_path = _real_export(tmp_path)

    assert output_path.exists()
    payload = output_path.read_bytes()
    assert receipt.byte_size == len(payload)
    assert receipt.file_sha256 == sha256_hex(payload)

    assert_export_artifact_matches_receipt(receipt, artifact_path=output_path)


def test_receipt_binding_refuses_an_artefact_whose_bytes_differ(tmp_path: Path) -> None:
    """A same-length artefact with different bytes is caught by the digest."""
    receipt, output_path = _real_export(tmp_path)
    original = output_path.read_bytes()

    flipped = bytearray(original)
    flipped[0] = original[0] ^ 0xFF
    output_path.write_bytes(bytes(flipped))

    # The tamper preserves length, so only the digest comparison can see it.
    assert output_path.stat().st_size == receipt.byte_size
    assert sha256_hex(bytes(flipped)) != receipt.file_sha256

    with pytest.raises(FilingExportError) as excinfo:
        assert_export_artifact_matches_receipt(receipt, artifact_path=output_path)
    assert "sha256" in str(excinfo.value)


def test_receipt_binding_refuses_an_artefact_of_a_different_length(tmp_path: Path) -> None:
    """A truncated artefact is caught by the byte count."""
    receipt, output_path = _real_export(tmp_path)
    original = output_path.read_bytes()
    assert len(original) > 1

    output_path.write_bytes(original[:-1])

    with pytest.raises(FilingExportError) as excinfo:
        assert_export_artifact_matches_receipt(receipt, artifact_path=output_path)
    assert "byte size" in str(excinfo.value)


def test_receipt_binding_refuses_a_path_that_holds_no_artefact(tmp_path: Path) -> None:
    """A receipt naming a destination the rename never produced is refused."""
    receipt, output_path = _real_export(tmp_path)

    with pytest.raises(FilingExportError):
        assert_export_artifact_matches_receipt(receipt, artifact_path=output_path.with_suffix(".absent"))


def test_receipt_binding_is_to_bytes_not_to_path_identity(tmp_path: Path) -> None:
    """A receipt describes content, so any path carrying those bytes satisfies it.

    This is what lets the work-unit service bind a receipt measured against the
    staging ``.tmp`` path to the destination the rename produced. An
    implementation that keyed on ``receipt.output_path`` instead would refuse
    that legitimate call, and would pass every refusal test above for the wrong
    reason.
    """
    receipt, output_path = _real_export(tmp_path)
    renamed = output_path.with_name("renamed-by-the-caller.boe")
    output_path.replace(renamed)

    assert not output_path.exists()
    assert receipt.output_path != renamed
    assert_export_artifact_matches_receipt(receipt, artifact_path=renamed)


def test_export_draft_returns_a_receipt_that_reproduces_from_its_artefact(tmp_path: Path) -> None:
    """The post-condition ``export_draft`` now establishes before it returns.

    This fences the receipt against a renderer that measures bytes other than
    the ones it wrote -- a second render, a re-encode between write and
    measurement. It does not, on its own, prove the call site is wired: an
    atomic write followed by an immediate read-back cannot be made to diverge
    without a test double, which this suite does not use.
    """
    receipt, output_path = _real_export(tmp_path)

    assert receipt.output_path == output_path
    assert receipt.format is DeclaracionExportFormat.FICHERO_BOE
    assert_export_artifact_matches_receipt(receipt, artifact_path=receipt.output_path)
