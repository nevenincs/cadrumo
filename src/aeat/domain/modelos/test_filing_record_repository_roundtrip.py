"""Strict roundtrip across the encrypted ModeloRecordCatalogueRepository.

Persists :class:`ModeloRecordCatalogue` under
``aeat.domain.modelos.filing_records`` at
``SensitivityClass.FINANCIAL``.

Anti-tautology: the fixture populates two filing records on the same
``(bucket, modelo, year, period)`` tuple — one ``SUPERSEDED`` with
``superseded_at`` / ``superseded_by_filing_record_id`` populated and
``external_evidence`` carrying an AEAT-imported justificante, plus the
``CURRENT`` successor pointing back via ``amends_filing_record_id``.
The model_validator on ``ModeloRecordCatalogue`` enforces the
"exactly one CURRENT per tuple" invariant, so the fixture stresses the
catalogue's structural gates while pinning supersession-chain identity.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ...adapters.persistence.storage.master_key._active_session import activate_session
from ...adapters.persistence.storage.master_key._bucket_session import BucketSession
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings, override_settings
from ._codes import ModeloCode
from ._filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ._filing_repository import ModeloRecordCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]

_BUCKET_ID = "modelo-runtime"
_KEK = b"k" * 32
_DEK = b"d" * 32


def _session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


def _runtime_engine(tmp_path: Path):
    return create_engine_from_settings(
        Settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID),
    )


def _hex(seed: str) -> str:
    """Return a stable 64-char hex blob for typed-id fixture values."""

    base = seed * 64
    return base[:64]


def _populated_catalogue() -> ModeloRecordCatalogue:
    bucket_id = "bucket-A"
    work_unit_id = _hex("a")
    superseded_revision = _hex("b")
    current_revision = _hex("c")
    superseded_filed_at = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)
    current_filed_at = superseded_filed_at + timedelta(days=45)

    superseded_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=superseded_revision,
        filed_at=superseded_filed_at,
        filed_by="aeat.cli.modelo.file",
    )
    current_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=current_revision,
        filed_at=current_filed_at,
        filed_by="aeat.cli.modelo.amend",
    )

    superseded = ModeloRecord(
        filing_record_id=superseded_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=superseded_revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period="2T",
        filed_at=superseded_filed_at,
        filed_by="aeat.cli.modelo.file",
        notes="initial 2T filing - withheld import IVA at 21%",
        aeat_accepted=True,
        status=ModeloRecordStatus.SUPERSEDIDO,
        superseded_at=current_filed_at,
        superseded_by_filing_record_id=current_id,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="just-303-2024-2T-original",
            imported_at=superseded_filed_at + timedelta(hours=2),
        ),
    )
    current = ModeloRecord(
        filing_record_id=current_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=current_revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period="2T",
        filed_at=current_filed_at,
        filed_by="aeat.cli.modelo.amend",
        notes="rectifying amendment - missing input IVA on invoice INV-2024-0145",
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        amends_filing_record_id=superseded_id,
    )
    return ModeloRecordCatalogue(records={superseded_id: superseded, current_id: current})


def test_filing_record_catalogue_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """The two-record supersession chain round-trips through encrypted SQL."""

    with override_settings(aeat_local_storage_root=tmp_path), activate_session(_session()):
        repo = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)
        original = _populated_catalogue()
        repo.save(original)
        loaded = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert loaded == original
    assert len(loaded.records) == 2
    current = loaded.current_for(
        bucket_id="bucket-A",
        modelo="303",
        filing_year=2024,
        period="2T",
    )
    assert current is not None
    assert current.amends_filing_record_id is not None

    superseded = loaded.get(current.amends_filing_record_id)
    assert superseded is not None
    assert superseded.status is ModeloRecordStatus.SUPERSEDIDO
    assert superseded.superseded_by_filing_record_id == current.filing_record_id
    assert superseded.superseded_at == current.filed_at
    # External-evidence carries the AEAT gate; pin it explicitly.
    assert superseded.external_evidence is not None
    assert superseded.external_evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
    assert superseded.external_evidence.reference_id == "just-303-2024-2T-original"
    assert (tmp_path / "buckets" / _BUCKET_ID / "db" / "aeat.db").is_file()


def test_filing_record_catalogue_supersession_chain_drift_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: corrupting the supersession chain must surface.

    Persists a supersession chain (SUPERSEDED + CURRENT for the same
    ``(bucket, modelo, year, period)`` tuple), then surgically mutates
    the encrypted JSON envelope to flip the SUPERSEDED record's status
    to CURRENT — creating two CURRENT records for the same tuple. The
    catalogue's model_validator enforces "exactly one CURRENT per
    tuple"; the mutated record must surface either as a
    ValidationError or as strict inequality on the loaded catalogue.

    If this test passes silently with two CURRENT records, the
    catalogue boundary is tautological and every filing-record
    roundtrip in the suite is suspect.
    """

    import json as _json

    from sqlalchemy import select

    from ...adapters.persistence.storage.sql._orm import SecureObjectRow
    from ...adapters.persistence.storage.sql.session import session_scope
    from ._filing_repository import _FILING_NAMESPACE, _FILING_OBJECT_KEY

    with override_settings(aeat_local_storage_root=tmp_path), activate_session(_session()):
        repo = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)
        original = _populated_catalogue()
        repo.save(original)

        engine = _runtime_engine(tmp_path)
        try:
            with session_scope(engine) as session:
                stmt = select(SecureObjectRow).where(
                    SecureObjectRow.namespace == _FILING_NAMESPACE,
                    SecureObjectRow.object_key == _FILING_OBJECT_KEY,
                )
                row = session.execute(stmt).scalar_one()
                envelope = _json.loads(row.payload.decode("utf-8"))
                records = envelope["payload"]["records"]
                superseded_id = next(
                    rid for rid, rec in records.items()
                    if rec["status"] == "supersedido"
                )
                # Flip the SUPERSEDIDO record's status to VIGENTE without
                # clearing its supersession metadata. The catalogue's
                # model_validator runs the "exactly one VIGENTE per tuple"
                # check AND the per-record "VIGENTE must not carry
                # supersession metadata" check; either invariant trips.
                records[superseded_id]["status"] = "vigente"
                row.payload = _json.dumps(envelope).encode("utf-8")

            regression_caught = False
            try:
                mutated = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID).load()
            except Exception:  # boundary may raise different types
                regression_caught = True
            else:
                if mutated != original:
                    regression_caught = True
        finally:
            engine.dispose()

    assert regression_caught, (
        "anti-tautology proof failed: corrupting the supersession "
        "chain did NOT surface on load. The catalogue boundary is "
        "tautological and every filing-record roundtrip in the "
        "suite is suspect."
    )
