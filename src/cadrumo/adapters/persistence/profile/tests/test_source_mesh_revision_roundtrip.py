"""Encrypted roundtrip coverage for calculation-revision source-mesh provenance.

Exercises the ``source_provenance`` field on
:class:`~domain.modelos.CalculationRevision`: the
resolver-to-source-object-to-fingerprint trace must survive the real encrypted
``SecureObjectRepository`` -> SQLite -> decrypt cycle with strict model equality,
and a corrupted on-disk payload must be refused on load so the field's
constraints are proven non-tautological.

See Also:
    :class:`~domain.modelos.CalculationSourceRef`
        Domain provenance row whose non-default fields are round-tripped here.
    :func:`~domain.modelos.derive_calculation_revision_id`
        Content-addressed id derivation that deliberately excludes provenance.
    :class:`~adapters.persistence.profile.modelos_calculation.CalculationRevisionCatalogueRepository`
        Encrypted catalogue repository exercised by the save/load cycle.
    :class:`~adapters.persistence.storage.SecureObjectRepository`
        Secure SQL-backed object boundary used for the corruption proof.
    :func:`~application.modelo._revision_persistence.persist_calculation_revision`
        Application writer that threads source provenance into persisted revisions.
    :func:`~application.modelo._revision_persistence._source_provenance_trace_sha256`
        Bucket-event digest over source provenance used by the live writer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....core import CasillaId, Period, validated_casilla_id
from .....core.aggregation import BindingSourceKind
from .....domain.calculations.registry import CasillaObservation
from .....domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    CalculationSourceRef,
    derive_calculation_revision_id,
    derive_work_unit_id,
)
from .....tests.secure_objects_fixture import secure_objects
from ...storage.sql import SecureObjectRepository
from ..modelos_calculation import CalculationRevisionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 7, 4, 14, 0, tzinfo=UTC)
_BUCKET_ID = "30330300-0000-4000-8000-000000000601"
_TX_ID = "d" * 64
_LEGAL_REFS = ("ley-37-1992:art-99",)
_SOURCE_REFS = ("boe-modelo-303-2025-form",)


_CASILLA: CasillaId = validated_casilla_id("00501")

__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _source_provenance() -> tuple[CalculationSourceRef, ...]:
    """Two provenance rows with every field populated non-default.

    A binding-backed invoice row (fingerprint present, typed ``binding_source``)
    plus a second invoice row, so the persisted tuple carries more than one entry
    and every :class:`CalculationSourceRef` field is exercised. The two rows
    carry distinct, non-default ``dependency_treatment`` values so a
    save-drops-field regression on either declared treatment is not masked by
    both rows sharing the same value.
    """
    return (
        CalculationSourceRef(
            source_kind="collectible_invoice",
            binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
            source_ref="collectible_invoice:inv-0001",
            fingerprint="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            dependency_treatment="direct_annual_settlement",
        ),
        CalculationSourceRef(
            source_kind="payable_invoice",
            binding_source=BindingSourceKind.PAYABLE_INVOICE,
            source_ref="payable_invoice:inv-0002",
            fingerprint="sha256:2222222222222222222222222222222222222222222222222222222222222222",
            dependency_treatment="factual_evidence",
        ),
    )


def _revision(source_provenance: tuple[CalculationSourceRef, ...]) -> CalculationRevision:
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2009-2022",
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_CASILLA: "140000.00"},
        binding_overrides={},
        casilla_values={_CASILLA: Decimal("140000.00")},
        source_transaction_ids=(_TX_ID,),
        filing_instance_evidence=None,
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={_CASILLA: "140000.00"},
        source_transaction_ids=(_TX_ID,),
        casilla_values={_CASILLA: Decimal("140000.00")},
        observations=(
            CasillaObservation(
                casilla_id=_CASILLA,
                value=Decimal("140000.00"),
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
        source_provenance=source_provenance,
        created_at=_NOW,
        updated_at=_NOW,
        filing_instance_evidence=None,
    )


def test_source_provenance_roundtrips_through_encrypted_revision(secure_objects: SecureObjectRepository) -> None:
    provenance = _source_provenance()
    original = _revision(provenance)
    repository = CalculationRevisionCatalogueRepository(objects=secure_objects)

    repository.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))
    loaded = CalculationRevisionCatalogueRepository(objects=secure_objects).load().get(original.calculation_revision_id)

    assert loaded is not None
    assert loaded == original
    assert loaded.source_provenance == provenance
    assert loaded.source_provenance[0].binding_source is BindingSourceKind.COLLECTIBLE_INVOICE
    assert loaded.source_provenance[0].fingerprint == provenance[0].fingerprint
    assert loaded.source_provenance[1].source_ref == "payable_invoice:inv-0002"
    # Both declared carry classifications survive the encrypted cycle intact and
    # distinguishable from one another; carrying the treatment must not disturb
    # the values it accompanies.
    assert loaded.source_provenance[0].dependency_treatment == "direct_annual_settlement"
    assert loaded.source_provenance[1].dependency_treatment == "factual_evidence"
    assert loaded.casilla_values == original.casilla_values

    # source_provenance is additive and NOT part of the content-addressed id.
    stripped = original.model_copy(update={"source_provenance": ()})
    assert stripped != original
    assert stripped.calculation_revision_id == original.calculation_revision_id


def test_source_provenance_blank_source_ref_payload_rejected_at_load(secure_objects: SecureObjectRepository) -> None:
    """Anti-tautology proof: a persisted provenance row with a blank ``source_ref`` is refused.

    Persist a valid revision, then surgically blank the on-disk ``source_ref`` of
    a source-provenance row and re-save the encrypted record. The load path MUST
    reject the mutated payload because :class:`CalculationSourceRef` enforces
    ``min_length=1`` on rehydration. If the load silently admitted the blank
    reference, the constraint would be tautological and every source-provenance
    roundtrip in the suite would be suspect.
    """

    import json as _json

    from ...storage import SensitivityClass
    from ..modelos_calculation import (
        _CALCULATION_CATALOGUE_VERSION,
        _CALCULATION_NAMESPACE,
        _CALCULATION_OBJECT_KEY,
    )

    original = _revision(_source_provenance())
    repository = CalculationRevisionCatalogueRepository(objects=secure_objects)
    repository.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))

    record = secure_objects.load(
        _CALCULATION_NAMESPACE,
        _CALCULATION_OBJECT_KEY,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=_CALCULATION_CATALOGUE_VERSION,
    )
    assert record is not None
    envelope = _json.loads(record.payload.decode("utf-8"))
    revision_dict = envelope["payload"]["revisions"][original.calculation_revision_id]
    row = revision_dict["source_provenance"][0]
    assert row["source_ref"] == "collectible_invoice:inv-0001", (
        "fixture must serialise the source_ref for this proof to be meaningful"
    )
    row["source_ref"] = ""
    secure_objects.save(
        namespace=_CALCULATION_NAMESPACE,
        object_key=_CALCULATION_OBJECT_KEY,
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=_json.dumps(envelope).encode("utf-8"),
    )

    with pytest.raises(ValidationError):
        CalculationRevisionCatalogueRepository(objects=secure_objects).load()


def test_source_provenance_dropped_dependency_treatment_is_detected_not_masked(
    secure_objects: SecureObjectRepository,
) -> None:
    """Anti-tautology proof: a silently dropped ``dependency_treatment`` is detectable.

    Unlike ``source_ref``, ``dependency_treatment`` is optional and defaults to
    the empty string, so a load path that dropped the persisted field on the
    way back would not raise: it would silently re-default to ``""``. Delete the
    on-disk key entirely (rather than blank it, which would coincide with an
    undeclared carry) and prove the reload surfaces STRICT INEQUALITY against
    the original persisted row, so a real save-drops-field regression on this
    field would be caught rather than masked by the default.
    """

    import json as _json

    from ...storage import SensitivityClass
    from ..modelos_calculation import (
        _CALCULATION_CATALOGUE_VERSION,
        _CALCULATION_NAMESPACE,
        _CALCULATION_OBJECT_KEY,
    )

    original = _revision(_source_provenance())
    repository = CalculationRevisionCatalogueRepository(objects=secure_objects)
    repository.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))

    record = secure_objects.load(
        _CALCULATION_NAMESPACE,
        _CALCULATION_OBJECT_KEY,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=_CALCULATION_CATALOGUE_VERSION,
    )
    assert record is not None
    envelope = _json.loads(record.payload.decode("utf-8"))
    revision_dict = envelope["payload"]["revisions"][original.calculation_revision_id]
    row = revision_dict["source_provenance"][0]
    assert row["dependency_treatment"] == "direct_annual_settlement", (
        "fixture must serialise a non-default dependency_treatment for this proof to be meaningful"
    )
    del row["dependency_treatment"]
    secure_objects.save(
        namespace=_CALCULATION_NAMESPACE,
        object_key=_CALCULATION_OBJECT_KEY,
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=_json.dumps(envelope).encode("utf-8"),
    )

    reloaded = (
        CalculationRevisionCatalogueRepository(objects=secure_objects).load().get(original.calculation_revision_id)
    )
    assert reloaded is not None
    assert reloaded.source_provenance[0].dependency_treatment != original.source_provenance[0].dependency_treatment
    assert reloaded.source_provenance[0].dependency_treatment == ""
    # Dropping the treatment field must never disturb the casilla value it accompanies.
    assert reloaded.casilla_values == original.casilla_values
