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
        Content-addressed id derivation over complete canonical provenance.
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

import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from .....core import CasillaId, Period, validated_casilla_id
from .....core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from .....domain.calculations import RowSourceIdentity
from .....domain.calculations.registry import CasillaObservation
from .....domain.modelos import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionPersistenceError,
    CalculationRevisionState,
    CalculationSourceRef,
    derive_calculation_revision_id,
    derive_calculation_revision_id_from_revision,
    derive_work_unit_id,
)
from .....tests.secure_objects_fixture import secure_objects
from .....tests.secure_sql import mutate_encrypted_secure_object_json
from ...storage import MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
from ...storage.sql import SecureObjectRepository, SecureObjectRow
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

    A binding-backed invoice row (fingerprint present, typed resolved/contributor axes)
    plus a second invoice row, so the persisted tuple carries more than one entry
    and every :class:`CalculationSourceRef` field is exercised. The two rows
    carry distinct, non-default ``dependency_treatment`` values so a
    save-drops-field regression on either declared treatment is not masked by
    both rows sharing the same value.
    """
    return (
        CalculationSourceRef(
            resolver_id="invoice_catalogue",
            resolved_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
            contributor_source_kind="collectible_invoice",
            contributor_binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref="collectible_invoice:inv-0001",
            parent_source_ref=None,
            fingerprint="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            dependency_treatment="direct_annual_settlement",
        ),
        CalculationSourceRef(
            resolver_id="invoice_catalogue",
            resolved_binding_source=BindingSourceKind.PAYABLE_INVOICE,
            contributor_source_kind="payable_invoice",
            contributor_binding_source=BindingSourceKind.PAYABLE_INVOICE,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref="payable_invoice:inv-0002",
            parent_source_ref=None,
            fingerprint="sha256:2222222222222222222222222222222222222222222222222222222222222222",
            dependency_treatment="factual_evidence",
        ),
    )


def _revision(
    source_provenance: tuple[CalculationSourceRef, ...],
    *,
    row_identity: RowSourceIdentity | None = None,
) -> CalculationRevision:
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2022",
    )
    row_values = {"inventory-operation-0181": {"1": "120.00"}} if row_identity is not None else {}
    row_identities: dict[tuple[str, int], RowSourceIdentity] = (
        {("inventory-operation-0181", 1): row_identity} if row_identity is not None else {}
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_CASILLA: "140000.00"},
        binding_overrides={},
        row_binding_values=row_values,
        row_source_identities=row_identities,
        casilla_values={_CASILLA: Decimal("140000.00")},
        source_transaction_ids=(_TX_ID,),
        source_provenance=source_provenance,
        filing_instance_evidence=None,
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={_CASILLA: "140000.00"},
        row_binding_values=row_values,
        row_source_identities=row_identities,
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


def test_row_source_identity_roundtrips_only_through_encrypted_revision(
    secure_objects: SecureObjectRepository,
) -> None:
    canary = "opaque-inventory-activity-canary"
    identity = RowSourceIdentity(
        source_kind=BindingSourceKind.INVENTORY,
        source_row_identity=canary,
        fingerprint="3" * 64,
    )
    original = _revision(_source_provenance(), row_identity=identity)
    repository = CalculationRevisionCatalogueRepository(objects=secure_objects)

    assert canary not in original.model_dump_json()
    repository.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))
    database_path = Path(str(secure_objects._engine.url.database))
    wal_path = database_path.with_name(database_path.name + "-wal")
    at_rest = database_path.read_bytes() + (wal_path.read_bytes() if wal_path.exists() else b"")
    for plaintext in (
        canary,
        "3" * 64,
        "collectible_invoice:inv-0001",
        "payable_invoice:inv-0002",
        "120.00",
    ):
        assert plaintext.encode() not in at_rest
    loaded = repository.load().get(original.calculation_revision_id)

    assert loaded is not None
    assert loaded.row_source_identities == original.row_source_identities
    assert loaded == original


def _calculation_row_statement():
    return select(SecureObjectRow).where(
        SecureObjectRow.namespace == MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace,
        SecureObjectRow.object_key
        == MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.require_default_object_key(),
    )


def _drop_row_identities(document: dict[str, Any]) -> None:
    revision = next(iter(document["payload"]["revisions"].values()))
    del revision["row_source_identities"]


def _orphan_row_identity(document: dict[str, Any]) -> None:
    revision = next(iter(document["payload"]["revisions"].values()))
    revision["row_source_identities"][0]["row_index"] = 2


def _duplicate_row_identity(document: dict[str, Any]) -> None:
    revision = next(iter(document["payload"]["revisions"].values()))
    revision["row_source_identities"].append(dict(revision["row_source_identities"][0]))


@pytest.mark.parametrize("mutate", [_drop_row_identities, _orphan_row_identity, _duplicate_row_identity])
def test_row_source_identity_corruption_is_value_free(
    secure_objects: SecureObjectRepository,
    mutate: Callable[[dict[str, Any]], None],
    caplog: pytest.LogCaptureFixture,
) -> None:
    canary = "opaque-inventory-activity-canary"
    original = _revision(
        _source_provenance(),
        row_identity=RowSourceIdentity(
            source_kind=BindingSourceKind.INVENTORY,
            source_row_identity=canary,
            fingerprint="3" * 64,
        ),
    )
    repository = CalculationRevisionCatalogueRepository(objects=secure_objects)
    repository.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))
    mutate_encrypted_secure_object_json(
        secure_objects._engine,
        row_statement=_calculation_row_statement(),
        mutate=mutate,
    )

    with pytest.raises(CalculationRevisionPersistenceError) as exc_info:
        repository.load()

    exc = exc_info.value
    assert exc.__cause__ is None
    assert exc.__context__ is None
    rendered = "".join(traceback.format_exception(exc))
    exposed = f"{exc!r} {exc} {getattr(exc, 'context', None)!r} {rendered} {caplog.text}"
    for plaintext in (canary, "3" * 64, "120.00", "collectible_invoice:inv-0001"):
        assert plaintext not in exposed


def test_source_provenance_roundtrips_through_encrypted_revision(secure_objects: SecureObjectRepository) -> None:
    provenance = _source_provenance()
    original = _revision(provenance)
    repository = CalculationRevisionCatalogueRepository(objects=secure_objects)

    repository.save(CalculationRevisionCatalogue(revisions={original.calculation_revision_id: original}))
    loaded = CalculationRevisionCatalogueRepository(objects=secure_objects).load().get(original.calculation_revision_id)

    assert loaded is not None
    assert loaded == original
    assert loaded.source_provenance == provenance
    assert loaded.source_provenance[0].resolved_binding_source is BindingSourceKind.COLLECTIBLE_INVOICE
    assert loaded.source_provenance[0].resolver_id == "invoice_catalogue"
    assert loaded.source_provenance[0].fingerprint == provenance[0].fingerprint
    assert loaded.source_provenance[1].source_ref == "payable_invoice:inv-0002"
    # Both declared carry classifications survive the encrypted cycle intact and
    # distinguishable from one another; carrying the treatment must not disturb
    # the values it accompanies.
    assert loaded.source_provenance[0].dependency_treatment == "direct_annual_settlement"
    assert loaded.source_provenance[1].dependency_treatment == "factual_evidence"
    assert loaded.casilla_values == original.casilla_values

    # Source provenance is a complete identity axis and is order-independent.
    stripped = original.model_copy(update={"source_provenance": ()})
    assert stripped != original
    assert stripped.calculation_revision_id != derive_calculation_revision_id_from_revision(stripped)
    resolver_changed = original.model_copy(
        update={
            "source_provenance": (
                original.source_provenance[0].model_copy(update={"resolver_id": "different-resolver"}),
                *original.source_provenance[1:],
            ),
        },
    )
    assert resolver_changed != original
    assert resolver_changed.calculation_revision_id != derive_calculation_revision_id_from_revision(resolver_changed)
    fingerprint_changed = original.model_copy(
        update={
            "source_provenance": (
                original.source_provenance[0].model_copy(update={"fingerprint": "sha256:" + "f" * 64}),
                *original.source_provenance[1:],
            ),
        },
    )
    assert fingerprint_changed.calculation_revision_id != derive_calculation_revision_id_from_revision(
        fingerprint_changed,
    )
    reordered = _revision(tuple(reversed(provenance)))
    assert reordered.calculation_revision_id == original.calculation_revision_id


@pytest.mark.parametrize(
    ("missing_field", "expected_value"),
    [
        ("resolver_id", "invoice_catalogue"),
        ("resolved_binding_source", BindingSourceKind.COLLECTIBLE_INVOICE.value),
        ("contributor_source_kind", BindingSourceKind.COLLECTIBLE_INVOICE.value),
        ("contributor_binding_source", BindingSourceKind.COLLECTIBLE_INVOICE.value),
        ("lineage_role", CalculationSourceLineageRole.PRIMARY.value),
        ("parent_source_ref", None),
    ],
)
def test_legacy_source_provenance_without_required_identity_is_rejected_at_encrypted_load(
    secure_objects: SecureObjectRepository,
    missing_field: str,
    expected_value: object,
) -> None:
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
    row = envelope["payload"]["revisions"][original.calculation_revision_id]["source_provenance"][0]
    assert row.pop(missing_field) == expected_value
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


def test_source_provenance_dropped_dependency_treatment_breaks_content_identity(
    secure_objects: SecureObjectRepository,
) -> None:
    """Anti-tautology proof: a silently dropped ``dependency_treatment`` is detectable.

    Unlike ``source_ref``, ``dependency_treatment`` is optional and defaults to
    the empty string, so a load path that dropped the persisted field on the
    way back would otherwise re-default to ``""``. Delete the on-disk key
    entirely and prove the persisted content-address check rejects the row.
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

    with pytest.raises(ValidationError, match="does not match the derived id"):
        CalculationRevisionCatalogueRepository(objects=secure_objects).load()
