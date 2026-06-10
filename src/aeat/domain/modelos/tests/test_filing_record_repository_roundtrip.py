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
from pydantic import ValidationError

from ....adapters.persistence.storage import SensitivityClass
from ....tests.secure_sql import isolated_runtime_profile
from .._codes import ModeloCode
from .._filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from .._filing_repository import (
    _FILING_CATALOGUE_VERSION,
    _FILING_NAMESPACE,
    _FILING_OBJECT_KEY,
    ModeloRecordCatalogueRepository,
    ModeloRecordPersistenceError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "modelo-runtime"


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

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
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
    assert (profile.paths.db_dir / "aeat.db").is_file()


def test_filing_record_catalogue_allows_distinct_current_group_members() -> None:
    """Member-scoped filing history keeps separate grupo members independent."""

    bucket_id = "bucket-A"
    filed_at = datetime(2026, 2, 20, 9, 0, 0, tzinfo=UTC)
    member_a_id = derive_filing_record_id(
        work_unit_id=_hex("1"),
        calculation_revision_id=_hex("2"),
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
        member_nif="A00000000",
    )
    member_b_id = derive_filing_record_id(
        work_unit_id=_hex("3"),
        calculation_revision_id=_hex("4"),
        filed_at=filed_at + timedelta(minutes=5),
        filed_by="aeat.cli.modelo.file",
        member_nif="B00000001",
    )

    catalogue = ModeloRecordCatalogue(
        records={
            member_a_id: ModeloRecord(
                filing_record_id=member_a_id,
                work_unit_id=_hex("1"),
                calculation_revision_id=_hex("2"),
                bucket_id=bucket_id,
                modelo=ModeloCode("322"),
                filing_year=2026,
                period="01",
                member_nif="A00000000",
                filed_at=filed_at,
                filed_by="aeat.cli.modelo.file",
                aeat_accepted=True,
            ),
            member_b_id: ModeloRecord(
                filing_record_id=member_b_id,
                work_unit_id=_hex("3"),
                calculation_revision_id=_hex("4"),
                bucket_id=bucket_id,
                modelo=ModeloCode("322"),
                filing_year=2026,
                period="01",
                member_nif="B00000001",
                filed_at=filed_at + timedelta(minutes=5),
                filed_by="aeat.cli.modelo.file",
                aeat_accepted=True,
            ),
        }
    )

    assert (
        catalogue.current_for(
            bucket_id=bucket_id,
            modelo="322",
            filing_year=2026,
            period="01",
        )
        is None
    )
    current_a = catalogue.current_for(
        bucket_id=bucket_id,
        modelo="322",
        filing_year=2026,
        period="01",
        member_nif="A00000000",
    )
    assert current_a is not None
    assert current_a.filing_record_id == member_a_id
    assert tuple(
        record.filing_record_id
        for record in catalogue.history_for(
            bucket_id=bucket_id,
            modelo="322",
            filing_year=2026,
            period="01",
            member_nif="B00000001",
        )
    ) == (member_b_id,)


def test_filing_record_catalogue_rejects_duplicate_current_group_member() -> None:
    """A member axis widens, but does not weaken, current-record uniqueness."""

    filed_at = datetime(2026, 2, 20, 9, 0, 0, tzinfo=UTC)
    first_id = derive_filing_record_id(
        work_unit_id=_hex("5"),
        calculation_revision_id=_hex("6"),
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
        member_nif="A00000000",
    )
    second_id = derive_filing_record_id(
        work_unit_id=_hex("7"),
        calculation_revision_id=_hex("8"),
        filed_at=filed_at + timedelta(minutes=5),
        filed_by="aeat.cli.modelo.file",
        member_nif="A00000000",
    )

    with pytest.raises(ValidationError, match="more than one current filing record"):
        ModeloRecordCatalogue(
            records={
                first_id: ModeloRecord(
                    filing_record_id=first_id,
                    work_unit_id=_hex("5"),
                    calculation_revision_id=_hex("6"),
                    bucket_id="bucket-A",
                    modelo=ModeloCode("322"),
                    filing_year=2026,
                    period="01",
                    member_nif="A00000000",
                    filed_at=filed_at,
                    filed_by="aeat.cli.modelo.file",
                    aeat_accepted=True,
                ),
                second_id: ModeloRecord(
                    filing_record_id=second_id,
                    work_unit_id=_hex("7"),
                    calculation_revision_id=_hex("8"),
                    bucket_id="bucket-A",
                    modelo=ModeloCode("322"),
                    filing_year=2026,
                    period="01",
                    member_nif="A00000000",
                    filed_at=filed_at + timedelta(minutes=5),
                    filed_by="aeat.cli.modelo.file",
                    aeat_accepted=True,
                ),
            }
        )


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

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)
        original = _populated_catalogue()
        repo.save(original)

        record = profile.repository.load(
            _FILING_NAMESPACE,
            _FILING_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_FILING_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = _json.loads(record.payload.decode("utf-8"))
        records = envelope["payload"]["records"]
        superseded_id = next(rid for rid, rec in records.items() if rec["status"] == "supersedido")
        # Flip the SUPERSEDIDO record's status to VIGENTE without
        # clearing its supersession metadata. The catalogue's
        # model_validator runs the "exactly one VIGENTE per tuple"
        # check AND the per-record "VIGENTE must not carry
        # supersession metadata" check; either invariant trips.
        records[superseded_id]["status"] = "vigente"
        profile.repository.save(
            namespace=_FILING_NAMESPACE,
            object_key=_FILING_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        with pytest.raises(ValidationError):
            ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID).load()


def test_filing_record_catalogue_wrong_inner_classification_is_localized(
    tmp_path: Path,
) -> None:
    """A corrupted envelope classification raises a translated persistence error."""

    from ....adapters.persistence.storage import Envelope

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[ModeloRecordCatalogue](
            schema_version=_FILING_CATALOGUE_VERSION,
            written_at=datetime.now(UTC).replace(microsecond=0),
            classification=SensitivityClass.AUDIT,
            payload=ModeloRecordCatalogue(),
        )
        profile.repository.save(
            namespace=_FILING_NAMESPACE,
            object_key=_FILING_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_FILING_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

        with pytest.raises(ModeloRecordPersistenceError) as raised:
            ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert raised.value.translated_message == "errors.fail.fail_modelo_filing_record_persistence"
    assert raised.value.context == {
        "reason": "classification_mismatch",
        "expected_classification": "financial",
        "actual_classification": "audit",
    }


def test_filing_record_catalogue_unsupported_inner_version_is_localized(
    tmp_path: Path,
) -> None:
    """A future inner envelope schema version raises a translated persistence error."""

    from ....adapters.persistence.storage import Envelope

    stored_schema_version = _FILING_CATALOGUE_VERSION + 1
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[ModeloRecordCatalogue](
            schema_version=stored_schema_version,
            written_at=datetime.now(UTC).replace(microsecond=0),
            classification=SensitivityClass.FINANCIAL,
            payload=ModeloRecordCatalogue(),
        )
        profile.repository.save(
            namespace=_FILING_NAMESPACE,
            object_key=_FILING_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_FILING_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

        with pytest.raises(ModeloRecordPersistenceError) as raised:
            ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert raised.value.translated_message == "errors.fail.fail_modelo_filing_record_persistence"
    assert raised.value.context == {
        "reason": "unsupported_envelope_version",
        "stored_schema_version": stored_schema_version,
        "max_supported_version": _FILING_CATALOGUE_VERSION,
    }
