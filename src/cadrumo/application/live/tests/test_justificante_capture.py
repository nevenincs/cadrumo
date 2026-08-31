"""Strict roundtrip and lifecycle tests for live justificante captures.

Persists :class:`JustificanteCaptureSnapshot` records under
``cadrumo.application.live.justificante_capture_snapshot`` at
``SensitivityClass.FINANCIAL`` through the real encrypted secure-object
store. The load-bearing field is the captured PDF: the binary receipt
rides the JSON envelope as base64, so the roundtrip witnesses that the
exact bytes survive. The anti-tautology proof surgically drops the
supersession pointer from the on-disk envelope and asserts the load
path rejects the record.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import pytest

from ....core import Modelo, Period
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ..errors import LiveApplicationInputError
from ..justificante import (
    JustificanteCaptureSnapshot,
    JustificanteCaptureSnapshotRepository,
    JustificanteCaptureSnapshotService,
    SnapshotLifecycleState,
    derive_justificante_capture_snapshot_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Canonical UUIDv4 profile identity. Test buckets are published through
# ``canonical_profile_bucket_id``, which accepts only a version-4 UUID,
# so a readable label cannot address a bucket.
_BUCKET_ID = "1a5c0000-0000-4000-8000-000000000001"

_PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
_PDF_SHA256 = hashlib.sha256(_PDF_BYTES).hexdigest()
_OTHER_PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Rev 2>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
_OTHER_PDF_SHA256 = hashlib.sha256(_OTHER_PDF_BYTES).hexdigest()
_PERIOD_2T = Period.from_year_and_code(2026, "2T")


class _CaptureKwargs(TypedDict):
    """Typed keyword bundle for ``JustificanteCaptureSnapshotService.capture``.

    Mirrors the capture signature so a ``**``-unpack type-checks each field to
    its parameter instead of collapsing to the value union ``dict(...)`` infers.
    """

    modelo: str
    filing_year: int
    period: Period
    expediente_id: str
    csv: str
    pdf_bytes: bytes
    pdf_sha256: str
    captured_at: datetime


def _active_snapshot(
    *,
    bucket_id: str,
    pdf_bytes: bytes = _PDF_BYTES,
    pdf_sha256: str = _PDF_SHA256,
) -> JustificanteCaptureSnapshot:
    import base64

    captured_at = datetime(2026, 7, 18, 10, 5, 0, tzinfo=UTC)
    snapshot_id = derive_justificante_capture_snapshot_id(
        modelo=Modelo.M130.value,
        filing_year=2026,
        period=_PERIOD_2T,
        pdf_sha256=pdf_sha256,
    )
    return JustificanteCaptureSnapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        modelo=Modelo.M130.value,
        filing_year=2026,
        period=_PERIOD_2T,
        expediente_id="202613000522456T",
        csv="ABCD1234EFGH5678",
        pdf_sha256=pdf_sha256,
        pdf_base64=base64.b64encode(pdf_bytes).decode("ascii"),
        # Non-default: the default is aeat_sede_live_capture; populate a
        # different official kind to witness the field survives the boundary.
        source_kind="aeat_sede_justificante",
        captured_at=captured_at,
        state=SnapshotLifecycleState.ACTIVE,
    )


def test_active_capture_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """A populated ACTIVE capture round-trips, PDF bytes byte-for-byte intact."""
    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        repo = JustificanteCaptureSnapshotRepository(bucket_id=bucket_id)
        original = _active_snapshot(bucket_id=bucket_id)
        repo.save(original)
        loaded = repo.load(original.snapshot_id)

        assert profile.paths.database_file.is_file()
        assert loaded == original
        # The load-bearing binary field: the exact PDF survives the envelope.
        assert loaded.decoded_pdf_bytes() == _PDF_BYTES
        assert hashlib.sha256(loaded.decoded_pdf_bytes()).hexdigest() == loaded.pdf_sha256
        assert loaded.source_kind == "aeat_sede_justificante"


def test_capture_rejects_pdf_hash_that_does_not_match_decoded_bytes() -> None:
    """The persisted source-bytes hash must describe the exact PDF payload."""
    with pytest.raises(
        LiveApplicationInputError,
        match=r"application\.live\.justificante\.errors\.pdf_sha256_mismatch",
    ):
        JustificanteCaptureSnapshot(
            snapshot_id=derive_justificante_capture_snapshot_id(
                modelo=Modelo.M130.value,
                filing_year=2026,
                period=_PERIOD_2T,
                pdf_sha256=_OTHER_PDF_SHA256,
            ),
            bucket_id=_BUCKET_ID,
            modelo=Modelo.M130.value,
            filing_year=2026,
            period=_PERIOD_2T,
            expediente_id="202613000522456T",
            csv="ABCD1234EFGH5678",
            pdf_sha256=_OTHER_PDF_SHA256,
            pdf_base64=base64.b64encode(_PDF_BYTES).decode("ascii"),
            source_kind="aeat_sede_live_capture",
            captured_at=datetime(2026, 7, 18, 10, 5, 0, tzinfo=UTC),
            state=SnapshotLifecycleState.ACTIVE,
        )


def test_superseded_capture_survives_roundtrip(tmp_path: Path) -> None:
    """A SUPERSEDED capture round-trips with its successor pointer intact."""
    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        repo = JustificanteCaptureSnapshotRepository(bucket_id=bucket_id)
        successor = _active_snapshot(bucket_id=bucket_id)
        repo.save(successor)

        predecessor = _active_snapshot(
            bucket_id=bucket_id,
            pdf_bytes=_OTHER_PDF_BYTES,
            pdf_sha256=_OTHER_PDF_SHA256,
        ).model_copy(
            update={
                "state": SnapshotLifecycleState.SUPERSEDED,
                "superseded_by_snapshot_id": successor.snapshot_id,
            },
        )
        repo.save(predecessor)
        loaded = repo.load(predecessor.snapshot_id)

        assert loaded == predecessor
        assert loaded.state is SnapshotLifecycleState.SUPERSEDED
        assert loaded.superseded_by_snapshot_id == successor.snapshot_id


def test_discarded_capture_survives_roundtrip(tmp_path: Path) -> None:
    """A DISCARDED capture round-trips with all discard audit metadata populated non-default."""
    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        repo = JustificanteCaptureSnapshotRepository(bucket_id=bucket_id)
        discarded = _active_snapshot(bucket_id=bucket_id).model_copy(
            update={
                "state": SnapshotLifecycleState.DISCARDED,
                "discarded_at": datetime(2026, 8, 1, 9, 0, 0, tzinfo=UTC),
                "discarded_by": "operator-1",
                "discard_reason": "superseded by a corrected filing",
            },
        )
        repo.save(discarded)
        loaded = repo.load(discarded.snapshot_id)

        assert loaded == discarded
        assert loaded.state is SnapshotLifecycleState.DISCARDED
        assert loaded.discarded_by == "operator-1"
        assert loaded.discard_reason == "superseded by a corrected filing"


def test_dropped_superseded_pointer_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology: deleting the on-disk supersession pointer must surface.

    If this test ever passes silently with the pointer dropped, every
    justificante-capture roundtrip in the suite is tautological.
    """
    from pydantic import ValidationError
    from sqlalchemy import select

    from ....adapters.persistence.storage.sql import SecureObjectRow
    from ..justificante import (
        JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
        justificante_capture_snapshot_object_key,
    )

    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        repo = JustificanteCaptureSnapshotRepository(bucket_id=bucket_id)
        successor = _active_snapshot(bucket_id=bucket_id)
        repo.save(successor)
        predecessor = _active_snapshot(
            bucket_id=bucket_id,
            pdf_bytes=_OTHER_PDF_BYTES,
            pdf_sha256=_OTHER_PDF_SHA256,
        ).model_copy(
            update={
                "state": SnapshotLifecycleState.SUPERSEDED,
                "superseded_by_snapshot_id": successor.snapshot_id,
            },
        )
        repo.save(predecessor)

        object_key = justificante_capture_snapshot_object_key(bucket_id, predecessor.snapshot_id)
        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
            SecureObjectRow.object_key == object_key,
        )

        def mutate(decoded):
            assert "superseded_by_snapshot_id" in decoded["payload"], (
                "fixture must serialise superseded_by_snapshot_id for this test to be meaningful"
            )
            del decoded["payload"]["superseded_by_snapshot_id"]

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=stmt,
            mutate=mutate,
        )

        with pytest.raises(
            (ValidationError, LiveApplicationInputError),
            match=r"state_supersession_pointer_required|superseded",
        ):
            repo.load(predecessor.snapshot_id)


def test_service_capture_supersedes_prior_on_refile(tmp_path: Path) -> None:
    """A re-filed period (a different signed PDF) supersedes the prior ACTIVE capture."""
    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        service = JustificanteCaptureSnapshotService(bucket_id=bucket_id)
        first = service.capture(
            modelo=Modelo.M130.value,
            filing_year=2026,
            period=_PERIOD_2T,
            expediente_id="202613000522456T",
            csv="ABCD1234EFGH5678",
            pdf_bytes=_PDF_BYTES,
            pdf_sha256=_PDF_SHA256,
            captured_at=datetime(2026, 7, 18, 10, 5, 0, tzinfo=UTC),
        )
        second = service.capture(
            modelo=Modelo.M130.value,
            filing_year=2026,
            period=_PERIOD_2T,
            expediente_id="202613000522456T",
            csv="ABCD1234EFGH5678",
            pdf_bytes=_OTHER_PDF_BYTES,
            pdf_sha256=_OTHER_PDF_SHA256,
            captured_at=datetime(2026, 7, 20, 8, 0, 0, tzinfo=UTC),
        )

        assert second.snapshot_id != first.snapshot_id
        active = service.list_snapshots()
        assert active == (second,)
        prior = service.show(first.snapshot_id)
        assert prior.state is SnapshotLifecycleState.SUPERSEDED
        assert prior.superseded_by_snapshot_id == second.snapshot_id


def test_service_capture_is_idempotent_on_same_receipt(tmp_path: Path) -> None:
    """Re-capturing the identical signed PDF returns the existing snapshot."""
    bucket_id = _BUCKET_ID
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        service = JustificanteCaptureSnapshotService(bucket_id=bucket_id)
        kwargs = _CaptureKwargs(
            modelo=Modelo.M130.value,
            filing_year=2026,
            period=_PERIOD_2T,
            expediente_id="202613000522456T",
            csv="ABCD1234EFGH5678",
            pdf_bytes=_PDF_BYTES,
            pdf_sha256=_PDF_SHA256,
            captured_at=datetime(2026, 7, 18, 10, 5, 0, tzinfo=UTC),
        )
        first = service.capture(**kwargs)
        second = service.capture(**kwargs)

        assert first.snapshot_id == second.snapshot_id
        assert service.list_snapshots() == (first,)
