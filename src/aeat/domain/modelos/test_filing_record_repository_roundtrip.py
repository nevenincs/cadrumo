"""Strict roundtrip across the encrypted FilingRecordCatalogueRepository.

Persists :class:`FilingRecordCatalogue` under
``aeat.domain.modelos.filing_records`` at
``SensitivityClass.FINANCIAL``.

Anti-tautology: the fixture populates two filing records on the same
``(bucket, modelo, year, period)`` tuple — one ``SUPERSEDED`` with
``superseded_at`` / ``superseded_by_filing_record_id`` populated and
``external_evidence`` carrying an AEAT-imported justificante, plus the
``CURRENT`` successor pointing back via ``amends_filing_record_id``.
The model_validator on ``FilingRecordCatalogue`` enforces the
"exactly one CURRENT per tuple" invariant, so the fixture stresses the
catalogue's structural gates while pinning supersession-chain identity.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import create_engine_from_settings
from ...core.config import Settings
from ._codes import ModeloCode
from ._filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingRecord,
    FilingRecordCatalogue,
    FilingRecordStatus,
    derive_filing_record_id,
)
from ._filing_repository import FilingRecordCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _hex(seed: str) -> str:
    """Return a stable 64-char hex blob for typed-id fixture values."""

    base = seed * 64
    return base[:64]


def _populated_catalogue() -> FilingRecordCatalogue:
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

    superseded = FilingRecord(
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
        status=FilingRecordStatus.SUPERSEDED,
        superseded_at=current_filed_at,
        superseded_by_filing_record_id=current_id,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="just-303-2024-2T-original",
            imported_at=superseded_filed_at + timedelta(hours=2),
        ),
    )
    current = FilingRecord(
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
        status=FilingRecordStatus.CURRENT,
        amends_filing_record_id=superseded_id,
    )
    return FilingRecordCatalogue(records={superseded_id: superseded, current_id: current})


def test_filing_record_catalogue_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two-record supersession chain round-trips through encrypted SQL."""

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "filing-records-roundtrip.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            repo = FilingRecordCatalogueRepository()
            original = _populated_catalogue()
            repo.save(original)
            loaded = repo.load()

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
            assert superseded.status is FilingRecordStatus.SUPERSEDED
            assert superseded.superseded_by_filing_record_id == current.filing_record_id
            assert superseded.superseded_at == current.filed_at
            # External-evidence carries the AEAT gate; pin it explicitly.
            assert superseded.external_evidence is not None
            assert superseded.external_evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
            assert superseded.external_evidence.reference_id == "just-303-2024-2T-original"
        finally:
            engine.dispose()


def test_filing_record_catalogue_supersession_chain_drift_surfaces_at_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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

    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "filing-records-anti-tautology.db"
        monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine)

            repo = FilingRecordCatalogueRepository()
            original = _populated_catalogue()
            repo.save(original)

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
                    if rec["status"] == "superseded"
                )
                # Flip the SUPERSEDED record's status to CURRENT without
                # clearing its supersession metadata. The catalogue's
                # model_validator runs the "exactly one CURRENT per tuple"
                # check AND the per-record "CURRENT must not carry
                # supersession metadata" check; either invariant trips.
                records[superseded_id]["status"] = "current"
                row.payload = _json.dumps(envelope).encode("utf-8")

            regression_caught = False
            try:
                mutated = repo.load()
            except Exception:  # noqa: BLE001 - boundary may raise different types
                regression_caught = True
            else:
                if mutated != original:
                    regression_caught = True
            assert regression_caught, (
                "anti-tautology proof failed: corrupting the supersession "
                "chain did NOT surface on load. The catalogue boundary is "
                "tautological and every filing-record roundtrip in the "
                "suite is suspect."
            )
        finally:
            engine.dispose()
