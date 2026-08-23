"""Strict roundtrip across the encrypted inventory ledger repository.

Persists :class:`InventoryLedgerDocument` (a tuple of
:class:`InventoryLedger` rows) under
``cadrumo.persistence.profile.inventory`` at
``SensitivityClass.FINANCIAL``.

Anti-tautology: the fixture populates non-default values on every
optional axis of ``InventoryLedger`` (``opening_layers``,
``closing_stock``, ``period_movements`` with two distinct kinds /
SKUs / iva shapes). Witness clauses pin per-field identity so a drift
silently flattening movements or layers fails on inequality.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pydantic
import pytest
from sqlalchemy import select

from .....domain.contribuyente.inventory import (
    INVENTORY_SCHEMA_VERSION,
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
    InventoryAttributableCostComponent,
    InventoryAttributableCostKind,
    InventoryLedger,
    InventoryLedgerDocument,
    MovementKind,
    MovementRecord,
    StockLayer,
    ValuationMethod,
    inventory_acquisition_fingerprint,
)
from .....domain.filing_evidence import FilingEvidenceReference
from .....tests.secure_sql import (
    isolated_runtime_profile,
    mutate_encrypted_secure_object_json,
    read_db_at_rest_bytes,
)
from ....persistence.storage import PROFILE_INVENTORY_LEDGER_NAMESPACE, HashedLookup
from ....persistence.storage.sql import SecureObjectRow
from ....persistence.storage.sql.engine import get_engine
from ....persistence.storage.sql.session import session_scope
from ..inventory import InventoryLedgerRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PRIVATE_COMPONENT_ID = "S165-PRIVATE-FREIGHT-COMPONENT"
_PRIVATE_INVOICE_REFERENCE = "S165-PRIVATE-PURCHASE-INVOICE-EVIDENCE"
_PRIVATE_FREIGHT_REFERENCE = "S165-PRIVATE-FREIGHT-EVIDENCE"
_PRIVATE_COST_REVIEW_REFERENCE = "S165-PRIVATE-ATTRIBUTABLE-COST-REVIEW"
_PRIVATE_IVA_REVIEW_REFERENCE = "S165-PRIVATE-IVA-RECOVERABILITY-REVIEW"
_PRIVATE_INVOICE_DIGEST = "d1" * 32
_PRIVATE_FREIGHT_DIGEST = "d2" * 32
_PRIVATE_COST_REVIEW_DIGEST = "d3" * 32
_PRIVATE_IVA_REVIEW_DIGEST = "d4" * 32


def _ref(value: str) -> FilingEvidenceReference:
    return FilingEvidenceReference(reference=value)


def _complete_acquisition() -> InventoryAcquisitionCost:
    """Return a non-default complete cost with partial IVA and typed review evidence."""
    return InventoryAcquisitionCost(
        consideration_excluding_iva=Decimal("825.00"),
        consideration_iva_amount=Decimal("173.25"),
        consideration_deductible_iva_ratio=Decimal("0.50"),
        attributable_cost_components=(
            InventoryAttributableCostComponent(
                component_id=_PRIVATE_COMPONENT_ID,
                kind=InventoryAttributableCostKind.FREIGHT,
                taxable_base=Decimal("37.00"),
                iva_amount=Decimal("7.77"),
                deductible_iva_ratio=Decimal("0.25"),
                evidence_references=(_ref(_PRIVATE_FREIGHT_REFERENCE),),
            ),
        ),
        evidence=(
            InventoryAcquisitionEvidence(
                reference=_ref(_PRIVATE_INVOICE_REFERENCE),
                evidence_kind=InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE,
                content_digest=_PRIVATE_INVOICE_DIGEST,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref(_PRIVATE_FREIGHT_REFERENCE),
                evidence_kind=InventoryAcquisitionEvidenceKind.TRANSPORT_DOCUMENT,
                content_digest=_PRIVATE_FREIGHT_DIGEST,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref(_PRIVATE_COST_REVIEW_REFERENCE),
                evidence_kind=InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
                content_digest=_PRIVATE_COST_REVIEW_DIGEST,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref(_PRIVATE_IVA_REVIEW_REFERENCE),
                evidence_kind=InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
                content_digest=_PRIVATE_IVA_REVIEW_DIGEST,
            ),
        ),
        completeness=InventoryAcquisitionCompleteness(
            consideration_evidence=_ref(_PRIVATE_INVOICE_REFERENCE),
            attributable_cost_review_evidence=_ref(_PRIVATE_COST_REVIEW_REFERENCE),
            iva_recoverability_review_evidence=_ref(_PRIVATE_IVA_REVIEW_REFERENCE),
        ),
        directly_attributable_cost_total=Decimal("37.00"),
        nonrecoverable_iva_included=Decimal("92.45"),
        recoverable_iva_excluded=Decimal("88.57"),
        total_acquisition_cost=Decimal("954.45"),
    )


def _populated_ledger() -> InventoryLedger:
    return InventoryLedger(
        actividad_id="iae.501.1",
        year=2024,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("1500.00"),
        closing_authority_record=None,
        opening_layers=(
            StockLayer(
                sku="widget-blue",
                quantity=Decimal("100"),
                unit_cost=Decimal("10.00"),
                source_movement_id="opening-widget-blue-2024",
            ),
            StockLayer(
                sku="widget-red",
                quantity=Decimal("50"),
                unit_cost=Decimal("10.00"),
                source_movement_id="opening-widget-red-2024",
            ),
        ),
        period_movements=(
            MovementRecord.from_purchase_acquisition(
                movement_id="mv-2024-001",
                movement_date=date(2024, 2, 15),
                sku="widget-blue",
                quantity=Decimal("75"),
                acquisition_cost=_complete_acquisition(),
            ),
            MovementRecord(
                movement_id="mv-2024-002",
                movement_date=date(2024, 5, 30),
                kind=MovementKind.COGS,
                sku="widget-blue",
                quantity=Decimal("40"),
                unit_cost=Decimal("10.40"),
            ),
        ),
    )


def test_inventory_ledger_survives_encrypted_storage_roundtrip(tmp_path: Path) -> None:
    """InventoryLedgerDocument roundtrips strictly with non-default movements + layers."""

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = InventoryLedgerRepository()
        ledger = _populated_ledger()
        original_doc = InventoryLedgerDocument(ledgers=(ledger,))
        repo.save(original_doc)
        loaded_doc = repo.load()

        assert loaded_doc == original_doc
        loaded_ledger = loaded_doc.ledgers[0]
        assert len(loaded_ledger.opening_layers) == 2
        assert tuple(layer.sku for layer in loaded_ledger.opening_layers) == (
            "widget-blue",
            "widget-red",
        )
        assert len(loaded_ledger.period_movements) == 2
        assert tuple(m.kind for m in loaded_ledger.period_movements) == (
            MovementKind.PURCHASE,
            MovementKind.COGS,
        )
        # IVA decomposition is FINANCIAL-class identity; pin the
        # explicit iva_amount survives un-quantised.
        purchase = loaded_ledger.period_movements[0]
        assert purchase.iva_amount == Decimal("173.25")
        assert purchase.deductible_iva_ratio == Decimal("0.50")
        assert purchase.acquisition_cost == _complete_acquisition()
        assert purchase.acquisition_cost.attributable_cost_components[0].taxable_base == Decimal("37.00")
        assert purchase.acquisition_cost.evidence[2].evidence_kind is InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW
        assert purchase.acquisition_cost.completeness.iva_recoverability_review_evidence.reference == _PRIVATE_IVA_REVIEW_REFERENCE
        assert purchase.capitalized_value == Decimal("954.45")
        assert purchase.resolved_unit_cost == Decimal("12.726")
        assert inventory_acquisition_fingerprint(purchase) == inventory_acquisition_fingerprint(
            original_doc.ledgers[0].period_movements[0],
        )
        assert loaded_doc.schema_version == INVENTORY_SCHEMA_VERSION

        engine = get_engine(profile.settings)
        stmt = _inventory_row_statement()
        with session_scope(engine) as session:
            rows = session.execute(stmt).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.namespace == PROFILE_INVENTORY_LEDGER_NAMESPACE.namespace
        assert row.object_key == HashedLookup.compute(
            PROFILE_INVENTORY_LEDGER_NAMESPACE.require_default_object_key(),
        )
        assert row.classification == PROFILE_INVENTORY_LEDGER_NAMESPACE.sensitivity.value
        assert row.schema_version == PROFILE_INVENTORY_LEDGER_NAMESPACE.schema_version

        at_rest = read_db_at_rest_bytes(profile.paths.database_file)
        for canary in (
            _PRIVATE_COMPONENT_ID,
            _PRIVATE_INVOICE_REFERENCE,
            _PRIVATE_FREIGHT_REFERENCE,
            _PRIVATE_COST_REVIEW_REFERENCE,
            _PRIVATE_IVA_REVIEW_REFERENCE,
            _PRIVATE_INVOICE_DIGEST,
            _PRIVATE_FREIGHT_DIGEST,
            _PRIVATE_COST_REVIEW_DIGEST,
            _PRIVATE_IVA_REVIEW_DIGEST,
            "954.45",
        ):
            assert canary.encode() not in at_rest


def _inventory_row_statement():
    return select(SecureObjectRow).where(
        SecureObjectRow.namespace == PROFILE_INVENTORY_LEDGER_NAMESPACE.namespace,
        SecureObjectRow.object_key == PROFILE_INVENTORY_LEDGER_NAMESPACE.require_default_object_key(),
    )


def _purchase_payload(document: dict[str, Any]) -> dict[str, Any]:
    movement = document["ledgers"][0]["period_movements"][0]
    assert movement["movement_id"] == "mv-2024-001"
    acquisition = movement.get("acquisition_cost")
    assert isinstance(acquisition, dict), "fixture must persist the complete acquisition envelope"
    return acquisition


def _drop_acquisition(document: dict[str, Any]) -> None:
    movement = document["ledgers"][0]["period_movements"][0]
    assert movement.get("acquisition_cost")
    del movement["acquisition_cost"]


def _drop_referenced_evidence(document: dict[str, Any]) -> None:
    acquisition = _purchase_payload(document)
    evidence = acquisition["evidence"]
    assert any(item["reference"]["reference"] == _PRIVATE_FREIGHT_REFERENCE for item in evidence)
    acquisition["evidence"] = [
        item for item in evidence if item["reference"]["reference"] != _PRIVATE_FREIGHT_REFERENCE
    ]


def _drop_content_digest(document: dict[str, Any]) -> None:
    evidence = _purchase_payload(document)["evidence"][0]
    assert evidence["content_digest"] == _PRIVATE_INVOICE_DIGEST
    del evidence["content_digest"]


def _replace_review_role(document: dict[str, Any]) -> None:
    acquisition = _purchase_payload(document)
    review = next(
        item
        for item in acquisition["evidence"]
        if item["reference"]["reference"] == _PRIVATE_COST_REVIEW_REFERENCE
    )
    assert review["evidence_kind"] == "attributable_cost_review"
    review["evidence_kind"] = "purchase_invoice"


def _change_component_amount(document: dict[str, Any]) -> None:
    component = _purchase_payload(document)["attributable_cost_components"][0]
    assert component["taxable_base"] == "37.00"
    component["taxable_base"] = "38.00"


def _change_total_cost(document: dict[str, Any]) -> None:
    acquisition = _purchase_payload(document)
    assert acquisition["total_acquisition_cost"] == "954.45"
    acquisition["total_acquisition_cost"] = "954.44"


def _change_recoverability(document: dict[str, Any]) -> None:
    acquisition = _purchase_payload(document)
    assert acquisition["consideration_deductible_iva_ratio"] == "0.50"
    acquisition["consideration_deductible_iva_ratio"] = "0.75"


def _drop_component(document: dict[str, Any]) -> None:
    acquisition = _purchase_payload(document)
    assert acquisition["attributable_cost_components"][0]["component_id"] == _PRIVATE_COMPONENT_ID
    acquisition["attributable_cost_components"] = []


def _drop_completeness_reference(document: dict[str, Any]) -> None:
    completeness = _purchase_payload(document)["completeness"]
    assert completeness["iva_recoverability_review_evidence"]["reference"] == _PRIVATE_IVA_REVIEW_REFERENCE
    del completeness["iva_recoverability_review_evidence"]


_ACQUISITION_MUTATIONS: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
    ("missing_acquisition", _drop_acquisition),
    ("missing_referenced_evidence", _drop_referenced_evidence),
    ("missing_content_digest", _drop_content_digest),
    ("wrong_review_role", _replace_review_role),
    ("changed_component_amount", _change_component_amount),
    ("changed_total", _change_total_cost),
    ("changed_recoverability", _change_recoverability),
    ("missing_component", _drop_component),
    ("missing_completeness_reference", _drop_completeness_reference),
)


@pytest.mark.parametrize(("case_id", "mutate"), _ACQUISITION_MUTATIONS, ids=[case[0] for case in _ACQUISITION_MUTATIONS])
def test_inventory_acquisition_corruption_fails_closed_at_encrypted_load(
    tmp_path: Path,
    case_id: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    """Every acquisition identity/completeness mutation is observed at the real load boundary."""
    del case_id
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = InventoryLedgerRepository()
        repo.save(InventoryLedgerDocument(ledgers=(_populated_ledger(),)))
        mutate_encrypted_secure_object_json(
            get_engine(profile.settings),
            row_statement=_inventory_row_statement(),
            mutate=mutate,
        )

        with pytest.raises(pydantic.ValidationError):
            repo.load()


def test_inventory_acquisition_digest_substitution_changes_loaded_fingerprint(tmp_path: Path) -> None:
    """A valid substituted digest survives strict load but changes source identity."""
    replacement_digest = "e1" * 32
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = InventoryLedgerRepository()
        original = _populated_ledger()
        original_purchase = original.period_movements[0]
        original_fingerprint = inventory_acquisition_fingerprint(original_purchase)
        repo.save(InventoryLedgerDocument(ledgers=(original,)))

        def substitute_digest(document: dict[str, Any]) -> None:
            evidence = _purchase_payload(document)["evidence"][0]
            assert evidence["content_digest"] == _PRIVATE_INVOICE_DIGEST
            evidence["content_digest"] = replacement_digest

        mutate_encrypted_secure_object_json(
            get_engine(profile.settings),
            row_statement=_inventory_row_statement(),
            mutate=substitute_digest,
        )
        loaded_purchase = repo.load().ledgers[0].period_movements[0]

        assert loaded_purchase.acquisition_cost is not None
        assert loaded_purchase.acquisition_cost.evidence[0].content_digest == replacement_digest
        assert inventory_acquisition_fingerprint(loaded_purchase) != original_fingerprint


def test_inventory_ledger_dropped_layer_balance_surfaces_at_load(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: corrupting the opening-layer balance must surface.

    :class:`InventoryLedger` carries a model_validator that enforces
    the sum of ``opening_layers`` (quantity * unit_cost) value-
    balances with ``opening_stock``. The persistence boundary
    serialises both components; if the wire shape silently strips a
    layer or skews a unit_cost, the rehydrated ledger's invariant
    must trip.

    Persists a populated ledger, reaches into SecureObjectRow via
    ``session_scope``, surgically halves the persisted
    ``opening_stock`` (breaking the value-balance), and asserts the
    load path catches the drift via the model_validator.

    If this test ever passes silently with a corrupted
    opening_stock, the inventory ledger boundary is tautological and
    every ledger roundtrip in the suite is suspect.
    """

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        engine = get_engine(profile.settings)
        repo = InventoryLedgerRepository()
        ledger = _populated_ledger()
        repo.save(InventoryLedgerDocument(ledgers=(ledger,)))

        stmt = _inventory_row_statement()

        def mutate(document):
            ledger_dict = document["ledgers"][0]
            assert ledger_dict.get("opening_stock"), (
                "fixture must serialise opening_stock onto the ledger for this proof test to be meaningful"
            )
            # Halve the opening_stock so the layer-balance check fails
            # (sum of layers no longer matches the declared aggregate).
            ledger_dict["opening_stock"] = "750.00"

        mutate_encrypted_secure_object_json(engine, row_statement=stmt, mutate=mutate)

        with pytest.raises(pydantic.ValidationError, match="opening_stock must equal the value of opening_layers"):
            repo.load()
