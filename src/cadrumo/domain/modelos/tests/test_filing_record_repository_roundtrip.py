"""Strict roundtrip across the encrypted ModeloRecordCatalogueRepository.

Persists :class:`ModeloRecordCatalogue` under
``cadrumo.domain.modelos.filing_records`` at
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

from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.storage.secure_object_namespaces import MODELO_FILING_RECORD_CATALOGUE_NAMESPACE
from ....core.classification.policies import SensitivityClass
from ....core.period import Period
from ....tests.secure_sql import isolated_runtime_profile
from ..codes import ModeloCode
from ..filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ..filing_repository import ModeloRecordPersistenceError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The registry definition is the sole authority for this namespace's identifier,
# singleton object key, and envelope schema version; the probe reads it rather
# than restating the values the repository under test writes at.
_FILING_NAMESPACE = MODELO_FILING_RECORD_CATALOGUE_NAMESPACE.namespace
_FILING_OBJECT_KEY = MODELO_FILING_RECORD_CATALOGUE_NAMESPACE.require_default_object_key()
_FILING_CATALOGUE_VERSION = MODELO_FILING_RECORD_CATALOGUE_NAMESPACE.schema_version
_BUCKET_ID = "30330300-0000-4000-8000-000000000700"
# The catalogue is one encrypted object per bucket and the repository refuses
# records from another bucket, so the fixture's records carry the same bucket
# the repository is bound to. _FOREIGN_BUCKET_ID is the isolation probe.
_RECORD_BUCKET_ID = _BUCKET_ID
_FOREIGN_BUCKET_ID = "30330300-0000-4000-8000-000000000701"
_P_2024_2T = Period.from_year_and_code(2024, "2T")
_P_2026_01 = Period.from_year_and_code(2026, "01")
_CORRUPT_ENVELOPE_WRITTEN_AT = datetime(2026, 5, 28, 10, 55, 0, tzinfo=UTC)
_FUTURE_ENVELOPE_WRITTEN_AT = datetime(2026, 5, 28, 11, 0, 0, tzinfo=UTC)


def _hex(seed: str) -> str:
    """Return a stable 64-char hex blob for typed-id fixture values."""

    base = seed * 64
    return base[:64]


def _populated_catalogue() -> ModeloRecordCatalogue:
    bucket_id = _RECORD_BUCKET_ID
    work_unit_id = _hex("a")
    superseded_revision = _hex("b")
    current_revision = _hex("c")
    superseded_filed_at = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)
    current_filed_at = superseded_filed_at + timedelta(days=45)

    superseded_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=superseded_revision,
        filed_by="aeat.cli.modelo.file",
    )
    current_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=current_revision,
        filed_by="aeat.cli.modelo.amend",
    )

    superseded = ModeloRecord(
        filing_record_id=superseded_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=superseded_revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
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
        period=_P_2024_2T,
        filed_at=current_filed_at,
        filed_by="aeat.cli.modelo.amend",
        notes="rectifying amendment - missing input IVA on invoice INV-2024-0145",
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
        bucket_id=_RECORD_BUCKET_ID,
        modelo="303",
        filing_year=2024,
        period=_P_2024_2T,
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
    assert profile.paths.database_file.is_file()


def test_filing_record_catalogue_allows_distinct_current_group_members() -> None:
    """Member-scoped filing history keeps separate grupo members independent."""

    bucket_id = _RECORD_BUCKET_ID
    filed_at = datetime(2026, 2, 20, 9, 0, 0, tzinfo=UTC)
    member_a_id = derive_filing_record_id(
        work_unit_id=_hex("1"),
        calculation_revision_id=_hex("2"),
        filed_by="aeat.cli.modelo.file",
        member_nif="A00000000",
    )
    member_b_id = derive_filing_record_id(
        work_unit_id=_hex("3"),
        calculation_revision_id=_hex("4"),
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
                period=_P_2026_01,
                member_nif="A00000000",
                filed_at=filed_at,
                filed_by="aeat.cli.modelo.file",
            ),
            member_b_id: ModeloRecord(
                filing_record_id=member_b_id,
                work_unit_id=_hex("3"),
                calculation_revision_id=_hex("4"),
                bucket_id=bucket_id,
                modelo=ModeloCode("322"),
                filing_year=2026,
                period=_P_2026_01,
                member_nif="B00000001",
                filed_at=filed_at + timedelta(minutes=5),
                filed_by="aeat.cli.modelo.file",
            ),
        },
    )

    assert (
        catalogue.current_for(
            bucket_id=bucket_id,
            modelo="322",
            filing_year=2026,
            period=_P_2026_01,
        )
        is None
    )
    current_a = catalogue.current_for(
        bucket_id=bucket_id,
        modelo="322",
        filing_year=2026,
        period=_P_2026_01,
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
            period=_P_2026_01,
            member_nif="B00000001",
        )
    ) == (member_b_id,)


def test_filing_record_rejects_aeat_acceptance_without_external_evidence() -> None:
    """AEAT acceptance must be backed by an external evidence reference."""
    filed_at = datetime(2026, 4, 20, 9, 0, 0, tzinfo=UTC)
    filing_id = derive_filing_record_id(
        work_unit_id=_hex("9"),
        calculation_revision_id=_hex("a"),
        filed_by="aeat.cli.modelo.file",
    )

    with pytest.raises(ValidationError, match="AEAT-accepted filing record must carry external evidence"):
        ModeloRecord(
            filing_record_id=filing_id,
            work_unit_id=_hex("9"),
            calculation_revision_id=_hex("a"),
            bucket_id=_RECORD_BUCKET_ID,
            modelo=ModeloCode("303"),
            filing_year=2024,
            period=_P_2024_2T,
            filed_at=filed_at,
            filed_by="aeat.cli.modelo.file",
            aeat_accepted=True,
        )


def test_filing_record_model_copy_revalidates_aeat_acceptance_invariant() -> None:
    """Domain copies must not bypass the external-evidence acceptance invariant."""
    filed_at = datetime(2026, 4, 20, 9, 0, 0, tzinfo=UTC)
    filing_id = derive_filing_record_id(
        work_unit_id=_hex("b"),
        calculation_revision_id=_hex("c"),
        filed_by="aeat.cli.modelo.file",
    )
    record = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=_hex("b"),
        calculation_revision_id=_hex("c"),
        bucket_id=_RECORD_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
    )

    with pytest.raises(ValidationError, match="AEAT-accepted filing record must carry external evidence"):
        record.model_copy(update={"aeat_accepted": True})


def test_filing_record_rejects_external_evidence_without_aeat_acceptance() -> None:
    """External evidence cannot exist as a half-stamped filing record."""
    filed_at = datetime(2026, 4, 20, 9, 0, 0, tzinfo=UTC)
    filing_id = derive_filing_record_id(
        work_unit_id=_hex("d"),
        calculation_revision_id=_hex("e"),
        filed_by="aeat.cli.modelo.file",
    )
    evidence = ExternalEvidence(
        kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        reference_id="just-303-2024-2T",
        imported_at=filed_at,
    )

    with pytest.raises(ValidationError, match="external filing evidence must carry AEAT acceptance"):
        ModeloRecord(
            filing_record_id=filing_id,
            work_unit_id=_hex("d"),
            calculation_revision_id=_hex("e"),
            bucket_id=_RECORD_BUCKET_ID,
            modelo=ModeloCode("303"),
            filing_year=2024,
            period=_P_2024_2T,
            filed_at=filed_at,
            filed_by="aeat.cli.modelo.file",
            external_evidence=evidence,
        )


def test_filing_record_model_copy_revalidates_external_evidence_acceptance_invariant() -> None:
    """Copy updates cannot attach external evidence without the acceptance bit."""
    filed_at = datetime(2026, 4, 20, 9, 0, 0, tzinfo=UTC)
    filing_id = derive_filing_record_id(
        work_unit_id=_hex("f"),
        calculation_revision_id=_hex("0"),
        filed_by="aeat.cli.modelo.file",
    )
    record = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=_hex("f"),
        calculation_revision_id=_hex("0"),
        bucket_id=_RECORD_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
    )
    evidence = ExternalEvidence(
        kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        reference_id="just-303-2024-2T",
        imported_at=filed_at,
    )

    with pytest.raises(ValidationError, match="external filing evidence must carry AEAT acceptance"):
        record.model_copy(update={"external_evidence": evidence})


def test_filing_record_catalogue_rejects_duplicate_current_group_member() -> None:
    """A member axis widens, but does not weaken, current-record uniqueness."""

    filed_at = datetime(2026, 2, 20, 9, 0, 0, tzinfo=UTC)
    first_id = derive_filing_record_id(
        work_unit_id=_hex("5"),
        calculation_revision_id=_hex("6"),
        filed_by="aeat.cli.modelo.file",
        member_nif="A00000000",
    )
    second_id = derive_filing_record_id(
        work_unit_id=_hex("7"),
        calculation_revision_id=_hex("8"),
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
                    bucket_id=_RECORD_BUCKET_ID,
                    modelo=ModeloCode("322"),
                    filing_year=2026,
                    period=_P_2026_01,
                    member_nif="A00000000",
                    filed_at=filed_at,
                    filed_by="aeat.cli.modelo.file",
                ),
                second_id: ModeloRecord(
                    filing_record_id=second_id,
                    work_unit_id=_hex("7"),
                    calculation_revision_id=_hex("8"),
                    bucket_id=_RECORD_BUCKET_ID,
                    modelo=ModeloCode("322"),
                    filing_year=2026,
                    period=_P_2026_01,
                    member_nif="A00000000",
                    filed_at=filed_at + timedelta(minutes=5),
                    filed_by="aeat.cli.modelo.file",
                ),
            },
        )


def test_filing_record_catalogue_rejects_amendment_across_member_nif() -> None:
    """An amendment link across two different ``member_nif`` values is refused.

    A declaracion complementaria corrects one earlier filing for the SAME
    (bucket, modelo, filing_year, period, member_nif) coordinate. A record
    claiming to amend another member's filing -- matching bucket, modelo,
    year, and period but naming a different member -- is not a within-member
    correction, and must be rejected rather than silently accepted as a valid
    audit chain across two unrelated members' filings.
    """

    bucket_id = _RECORD_BUCKET_ID
    filed_at = datetime(2026, 3, 10, 9, 0, 0, tzinfo=UTC)
    baseline_id = derive_filing_record_id(
        work_unit_id=_hex("1"),
        calculation_revision_id=_hex("2"),
        filed_by="aeat.cli.modelo.file",
        member_nif="A00000000",
    )
    amendment_id = derive_filing_record_id(
        work_unit_id=_hex("1"),
        calculation_revision_id=_hex("3"),
        filed_by="aeat.cli.modelo.amend",
        member_nif="B00000001",
    )

    with pytest.raises(ValidationError, match="across filing"):
        ModeloRecordCatalogue(
            records={
                baseline_id: ModeloRecord(
                    filing_record_id=baseline_id,
                    work_unit_id=_hex("1"),
                    calculation_revision_id=_hex("2"),
                    bucket_id=bucket_id,
                    modelo=ModeloCode("322"),
                    filing_year=2026,
                    period=_P_2026_01,
                    member_nif="A00000000",
                    filed_at=filed_at,
                    filed_by="aeat.cli.modelo.file",
                    status=ModeloRecordStatus.SUPERSEDIDO,
                    superseded_at=filed_at + timedelta(minutes=5),
                    superseded_by_filing_record_id=amendment_id,
                ),
                amendment_id: ModeloRecord(
                    filing_record_id=amendment_id,
                    work_unit_id=_hex("1"),
                    calculation_revision_id=_hex("3"),
                    bucket_id=bucket_id,
                    modelo=ModeloCode("322"),
                    filing_year=2026,
                    period=_P_2026_01,
                    member_nif="B00000001",
                    filed_at=filed_at + timedelta(minutes=5),
                    filed_by="aeat.cli.modelo.amend",
                    status=ModeloRecordStatus.VIGENTE,
                    amends_filing_record_id=baseline_id,
                ),
            },
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

    from ....adapters.persistence.storage.envelope._envelope import Envelope

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[ModeloRecordCatalogue](
            schema_version=_FILING_CATALOGUE_VERSION,
            written_at=_CORRUPT_ENVELOPE_WRITTEN_AT,
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

    from ....adapters.persistence.storage.envelope._envelope import Envelope

    stored_schema_version = _FILING_CATALOGUE_VERSION + 1
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[ModeloRecordCatalogue](
            schema_version=stored_schema_version,
            written_at=_FUTURE_ENVELOPE_WRITTEN_AT,
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


def _source_transaction_ids() -> tuple[str, ...]:
    return (_hex("7"), _hex("8"))


def test_filing_record_source_transaction_ids_survive_roundtrip(tmp_path: Path) -> None:
    """The denormalised source_transaction_ids footprint round-trips with non-default values."""
    work_unit_id = _hex("a")
    revision_id = _hex("c")
    filed_at = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="aeat.cli.modelo.file",
    )
    record = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_RECORD_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
        source_transaction_ids=_source_transaction_ids(),
    )
    original = ModeloRecordCatalogue(records={filing_id: record})

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        repo = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)
        repo.save(original)
        loaded = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert loaded == original
    (loaded_record,) = loaded.records.values()
    assert loaded_record.source_transaction_ids == _source_transaction_ids()


def test_derive_filing_record_id_is_stable_regardless_of_source_transaction_ids() -> None:
    """source_transaction_ids is excluded from the content address; the id is unaffected."""
    work_unit_id = _hex("a")
    revision_id = _hex("c")
    filed_at = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)
    derived = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="aeat.cli.modelo.file",
    )

    empty_footprint = ModeloRecord(
        filing_record_id=derived,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_RECORD_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
    )
    full_footprint = empty_footprint.model_copy(update={"source_transaction_ids": _source_transaction_ids()})

    # Same derived id accepted by both — the validator's derived-id check is
    # independent of source_transaction_ids.
    assert empty_footprint.filing_record_id == full_footprint.filing_record_id == derived


def test_filing_record_absent_source_transaction_ids_defaults_to_empty(tmp_path: Path) -> None:
    """Anti-tautology proof: a payload missing source_transaction_ids loads as ()."""
    import json as _json

    work_unit_id = _hex("a")
    revision_id = _hex("c")
    filed_at = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="aeat.cli.modelo.file",
    )
    record = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_RECORD_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
        filed_at=filed_at,
        filed_by="aeat.cli.modelo.file",
        source_transaction_ids=_source_transaction_ids(),
    )
    original = ModeloRecordCatalogue(records={filing_id: record})

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)
        repo.save(original)

        stored = profile.repository.load(
            _FILING_NAMESPACE,
            _FILING_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_FILING_CATALOGUE_VERSION,
        )
        assert stored is not None
        envelope = _json.loads(stored.payload.decode("utf-8"))
        persisted = envelope["payload"]["records"][filing_id]
        assert persisted["source_transaction_ids"] == list(_source_transaction_ids())
        # Drop the field: the model default of () must surface on reload, so the
        # mutated catalogue compares UNEQUAL to the original (which carried two ids).
        del persisted["source_transaction_ids"]
        profile.repository.save(
            namespace=_FILING_NAMESPACE,
            object_key=_FILING_OBJECT_KEY,
            classification=stored.classification,
            schema_version=stored.schema_version,
            written_at=stored.written_at,
            payload=_json.dumps(envelope).encode("utf-8"),
        )

        mutated = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID).load()

    (mutated_record,) = mutated.records.values()
    assert mutated_record.source_transaction_ids == ()
    assert mutated != original


def test_filing_record_id_is_clock_free_and_outcome_pinned() -> None:
    """filed_at is excluded from the filing-record identity; the outcome inputs define it.

    Two records that differ ONLY in filed_at share the same content-addressed id
    (the model validator accepts both), so a re-file of the same revision by the
    same actor collapses onto one record rather than minting a time-stamped
    duplicate; a different actor diverges the identity.
    """
    work_unit_id = _hex("d")
    revision_id = _hex("e")
    record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="operator-A",
    )
    early = ModeloRecord(
        filing_record_id=record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_RECORD_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=_P_2026_01,
        filed_at=datetime(2026, 1, 31, 9, 0, 0, tzinfo=UTC),
        filed_by="operator-A",
        status=ModeloRecordStatus.VIGENTE,
    )
    late = ModeloRecord(
        filing_record_id=record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_RECORD_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=_P_2026_01,
        filed_at=datetime(2026, 1, 31, 23, 59, 0, tzinfo=UTC),
        filed_by="operator-A",
        status=ModeloRecordStatus.VIGENTE,
    )
    assert early.filing_record_id == late.filing_record_id == record_id
    assert early.filed_at != late.filed_at
    # A different actor diverges the outcome identity.
    other_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="operator-B",
    )
    assert other_id != record_id


def test_filing_record_rejects_id_not_matching_outcome() -> None:
    """Anti-tautology: a ModeloRecord whose id does not match the outcome derivation is refused.

    The id is derived for ``operator-Z`` but the record carries ``operator-A``;
    the model validator re-derives the outcome-pinned id and raises, with
    ``filed_at`` populated non-default to confirm it never participates in the id.
    """
    work_unit_id = _hex("f")
    revision_id = _hex("e")
    mismatched_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="operator-Z",
    )
    with pytest.raises(ValidationError):
        ModeloRecord(
            filing_record_id=mismatched_id,
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            bucket_id=_RECORD_BUCKET_ID,
            modelo=ModeloCode("303"),
            filing_year=2026,
            period=_P_2026_01,
            filed_at=datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC),
            filed_by="operator-A",
            status=ModeloRecordStatus.VIGENTE,
        )


def _amendment_pair(
    *,
    target_id_override: str | None = None,
    amendment_period: Period | None = None,
    amendment_filing_year: int | None = None,
    baseline_successor_override: str | None = None,
) -> ModeloRecordCatalogue:
    """Build a baseline plus an amendment whose link can be steered off target."""
    bucket_id = _RECORD_BUCKET_ID
    work_unit_id = _hex("a")
    baseline_revision = _hex("b")
    amendment_revision = _hex("c")
    baseline_filed_at = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)
    amendment_filed_at = baseline_filed_at + timedelta(days=45)

    baseline_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=baseline_revision,
        filed_by="aeat.cli.modelo.file",
    )
    amendment_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=amendment_revision,
        filed_by="aeat.cli.modelo.amend",
    )
    baseline = ModeloRecord(
        filing_record_id=baseline_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=baseline_revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
        filed_at=baseline_filed_at,
        filed_by="aeat.cli.modelo.file",
        status=ModeloRecordStatus.SUPERSEDIDO,
        superseded_at=amendment_filed_at,
        superseded_by_filing_record_id=baseline_successor_override or amendment_id,
    )
    period = amendment_period or _P_2024_2T
    amendment = ModeloRecord(
        filing_record_id=amendment_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=amendment_revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=amendment_filing_year or 2024,
        period=period,
        filed_at=amendment_filed_at,
        filed_by="aeat.cli.modelo.amend",
        status=ModeloRecordStatus.VIGENTE,
        amends_filing_record_id=target_id_override or baseline_id,
    )
    return ModeloRecordCatalogue(records={baseline_id: baseline, amendment_id: amendment})


def test_amendment_link_to_a_record_outside_the_catalogue_is_refused() -> None:
    """A complementaria must correct a filing that exists, not a claimed one."""
    with pytest.raises(ValidationError, match="not in this catalogue"):
        _amendment_pair(target_id_override=_hex("f"))


def test_amendment_link_to_itself_is_refused() -> None:
    """A record cannot be its own amendment baseline."""
    bucket_id = _RECORD_BUCKET_ID
    work_unit_id = _hex("a")
    revision = _hex("b")
    record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision,
        filed_by="aeat.cli.modelo.amend",
    )
    self_amending = ModeloRecord(
        filing_record_id=record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
        filed_at=datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC),
        filed_by="aeat.cli.modelo.amend",
        status=ModeloRecordStatus.VIGENTE,
        amends_filing_record_id=record_id,
    )

    with pytest.raises(ValidationError, match="cannot amend itself"):
        ModeloRecordCatalogue(records={record_id: self_amending})


def test_amendment_link_across_filing_coordinates_is_refused() -> None:
    """An amendment corrects the same (bucket, modelo, year, period) coordinate."""
    with pytest.raises(ValidationError, match="across filing coordinates"):
        _amendment_pair(
            amendment_period=Period.from_year_and_code(2024, "3T"),
        )


def test_resolvable_same_coordinate_amendment_survives_encrypted_storage(
    tmp_path: Path,
) -> None:
    """Valid parity: a resolvable, distinct, same-coordinate link round-trips."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        original = _amendment_pair()
        ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID).save(original)
        loaded = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert loaded == original
    amendment = loaded.current_for(
        bucket_id=_RECORD_BUCKET_ID,
        modelo="303",
        filing_year=2024,
        period=_P_2024_2T,
    )
    assert amendment is not None
    assert amendment.amends_filing_record_id is not None
    baseline = loaded.get(amendment.amends_filing_record_id)
    assert baseline is not None
    assert baseline.filing_record_id != amendment.filing_record_id
    assert (baseline.bucket_id, baseline.modelo, baseline.filing_year, baseline.period) == (
        amendment.bucket_id,
        amendment.modelo,
        amendment.filing_year,
        amendment.period,
    )


def _record_with_source_transactions(source_transaction_ids: tuple[str, ...]) -> ModeloRecord:
    """Build a current filing record carrying the given ledger provenance footprint."""
    work_unit_id = _hex("a")
    revision_id = _hex("c")
    return ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            filed_by="aeat.cli.modelo.file",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_RECORD_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
        filed_at=datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC),
        filed_by="aeat.cli.modelo.file",
        status=ModeloRecordStatus.VIGENTE,
        source_transaction_ids=source_transaction_ids,
    )


@pytest.mark.parametrize(
    "malformed",
    (
        ("bad",),
        (_hex("a").upper(),),
        (" " + _hex("a")[1:] + "z",),
        (_hex("a")[:-1] + "g",),
    ),
    ids=("too-short", "uppercase-hex", "non-hex-tail", "non-hex-digit"),
)
def test_source_transaction_ids_must_be_canonical_transaction_identities(malformed: tuple[str, ...]) -> None:
    """The provenance footprint holds real ledger identities, not arbitrary strings."""
    with pytest.raises(ValidationError):
        _record_with_source_transactions(malformed)


def test_source_transaction_ids_reject_a_repeated_transaction() -> None:
    """A repeat is a double count or a merged footprint, never a second contribution."""
    with pytest.raises(ValidationError, match="must not repeat a transaction"):
        _record_with_source_transactions((_hex("7"), _hex("7")))


def test_canonical_source_transaction_footprint_survives_encrypted_storage(tmp_path: Path) -> None:
    """Valid parity: a distinct, canonical footprint round-trips unchanged."""
    footprint = (_hex("7"), _hex("8"))
    record = _record_with_source_transactions(footprint)
    original = ModeloRecordCatalogue(records={record.filing_record_id: record})

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID).save(original)
        loaded = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID).load()

    assert loaded == original
    loaded_record = loaded.get(record.filing_record_id)
    assert loaded_record is not None
    assert loaded_record.source_transaction_ids == footprint


def _foreign_bucket_catalogue() -> ModeloRecordCatalogue:
    """Build a catalogue whose single record belongs to another taxpayer's bucket."""
    work_unit_id = _hex("a")
    revision_id = _hex("c")
    record = ModeloRecord(
        filing_record_id=derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision_id,
            filed_by="aeat.cli.modelo.file",
        ),
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_FOREIGN_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
        filed_at=datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC),
        filed_by="aeat.cli.modelo.file",
        status=ModeloRecordStatus.VIGENTE,
    )
    return ModeloRecordCatalogue(records={record.filing_record_id: record})


def test_foreign_bucket_filing_record_is_refused_at_save(tmp_path: Path) -> None:
    """A receipt from another taxpayer's bucket must not enter this catalogue."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID),
        pytest.raises(ModeloRecordPersistenceError) as raised,
    ):
        ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID).save(_foreign_bucket_catalogue())

    assert raised.value.context == {
        "reason": "foreign_bucket_record",
        "boundary": "save",
        "expected_bucket_id": _BUCKET_ID,
        "record_bucket_ids": [_FOREIGN_BUCKET_ID],
    }


def test_foreign_bucket_filing_record_is_refused_at_load(tmp_path: Path) -> None:
    """Anti-tautology proof: the isolation is durable, not a caller convention.

    Writes the foreign-bucket catalogue straight through the secure-object
    substrate, bypassing the repository's write guard, then asserts the read
    path refuses it. Without this the save-side check would only hold for
    callers that go through the repository.
    """
    from ....adapters.persistence.storage.envelope._envelope import Envelope

    catalogue = _foreign_bucket_catalogue()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        envelope = Envelope[ModeloRecordCatalogue](
            schema_version=_FILING_CATALOGUE_VERSION,
            written_at=_CORRUPT_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.FINANCIAL,
            payload=catalogue,
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

    assert raised.value.context == {
        "reason": "foreign_bucket_record",
        "boundary": "load",
        "expected_bucket_id": _BUCKET_ID,
        "record_bucket_ids": [_FOREIGN_BUCKET_ID],
    }


def test_one_sided_amendment_link_is_refused() -> None:
    """Both records must agree about the amendment relationship they share.

    The three-record disagreement: the amendment correctly resolves to its
    baseline, but the baseline names a third record as its successor. Read
    forwards the chain is coherent; read backwards it is not, so the audit
    history depends on which end you start from.
    """
    third_party_successor = _hex("e")

    with pytest.raises(ValidationError, match="one-sided amendment link"):
        _amendment_pair(baseline_successor_override=third_party_successor)


def test_amendment_whose_baseline_names_no_successor_is_refused() -> None:
    """An amendment with no answering back-reference is the same one-sided defect.

    Reaches the refusal through a baseline that is still current, so the
    supersession side of the link is absent rather than merely wrong.
    """
    bucket_id = _RECORD_BUCKET_ID
    work_unit_id = _hex("a")
    baseline_revision = _hex("b")
    amendment_revision = _hex("c")
    baseline_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=baseline_revision,
        filed_by="aeat.cli.modelo.file",
    )
    amendment_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=amendment_revision,
        filed_by="aeat.cli.modelo.amend",
    )
    baseline_filed_at = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)
    baseline = ModeloRecord(
        filing_record_id=baseline_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=baseline_revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
        filed_at=baseline_filed_at,
        filed_by="aeat.cli.modelo.file",
        status=ModeloRecordStatus.VIGENTE,
    )
    amendment = ModeloRecord(
        filing_record_id=amendment_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=amendment_revision,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2024,
        period=_P_2024_2T,
        filed_at=baseline_filed_at + timedelta(days=45),
        filed_by="aeat.cli.modelo.amend",
        status=ModeloRecordStatus.SUPERSEDIDO,
        superseded_at=baseline_filed_at + timedelta(days=90),
        superseded_by_filing_record_id=_hex("e"),
        amends_filing_record_id=baseline_id,
    )

    with pytest.raises(ValidationError, match="one-sided amendment link"):
        ModeloRecordCatalogue(records={baseline_id: baseline, amendment_id: amendment})


def test_agreeing_amendment_link_is_accepted() -> None:
    """Valid parity: forward and reverse links naming each other pass."""
    catalogue = _amendment_pair()

    amendment = catalogue.current_for(
        bucket_id=_RECORD_BUCKET_ID,
        modelo="303",
        filing_year=2024,
        period=_P_2024_2T,
    )
    assert amendment is not None
    assert amendment.amends_filing_record_id is not None
    baseline = catalogue.get(amendment.amends_filing_record_id)
    assert baseline is not None
    assert baseline.superseded_by_filing_record_id == amendment.filing_record_id


def test_amendment_chain_of_three_agrees_at_every_hop() -> None:
    """A -> B -> C: each hop's forward and reverse links must name each other."""
    bucket_id = _RECORD_BUCKET_ID
    work_unit_id = _hex("a")
    first_filed_at = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)
    revisions = (_hex("b"), _hex("c"), _hex("d"))
    actors = ("aeat.cli.modelo.file", "aeat.cli.modelo.amend", "aeat.cli.modelo.amend")
    ids = tuple(
        derive_filing_record_id(
            work_unit_id=work_unit_id,
            calculation_revision_id=revision,
            filed_by=actor,
        )
        for revision, actor in zip(revisions, actors, strict=True)
    )
    records: dict[str, ModeloRecord] = {}
    for index, (record_id, revision, actor) in enumerate(zip(ids, revisions, actors, strict=True)):
        is_last = index == len(ids) - 1
        filed_at = first_filed_at + timedelta(days=45 * index)
        records[record_id] = ModeloRecord(
            filing_record_id=record_id,
            work_unit_id=work_unit_id,
            calculation_revision_id=revision,
            bucket_id=bucket_id,
            modelo=ModeloCode("303"),
            filing_year=2024,
            period=_P_2024_2T,
            filed_at=filed_at,
            filed_by=actor,
            status=ModeloRecordStatus.VIGENTE if is_last else ModeloRecordStatus.SUPERSEDIDO,
            superseded_at=None if is_last else filed_at + timedelta(days=45),
            superseded_by_filing_record_id=None if is_last else ids[index + 1],
            amends_filing_record_id=None if index == 0 else ids[index - 1],
        )

    catalogue = ModeloRecordCatalogue(records=records)

    assert len(catalogue) == 3
    for index, record_id in enumerate(ids[1:], start=1):
        record = catalogue.get(record_id)
        assert record is not None
        assert record.amends_filing_record_id == ids[index - 1]
        baseline = catalogue.get(ids[index - 1])
        assert baseline is not None
        assert baseline.superseded_by_filing_record_id == record_id
