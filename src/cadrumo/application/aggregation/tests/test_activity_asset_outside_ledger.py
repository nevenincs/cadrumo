"""An element acquired outside the ledger goes through the register, claims, Modelo 100 and a baja with no row.

Figures are hand-worked from the 12,000.00 element at a 10% linear coefficient.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.tipos_actividad import TipoActividad
from cadrumo.domain.renta.actividad_asset.disposal import ActivityAssetDisposal, ActivityAssetDisposalReason
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetValidationError
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetRevision,
)

from ...actividad_asset.acquisition_candidates import acquisition_candidates
from ...actividad_asset.acquisition_ledger import require_acquisition_in_ledger
from ...actividad_asset.history import ActivityAssetHistory
from ...actividad_asset.operation_dtos import ActivityAssetRevisionSnapshot
from ...actividad_asset.tests.ledger_support import MemoryLedger, acquisition_transaction
from ...modelo.calculation_notes import GATE_REFUSED_REASONS
from .ledger_source_mesh_support import _register_claim, reasons, register_asset, resolve_m100, resolve_m130

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _facts(**changes: Any) -> dict[str, Any]:
    template = register_asset("old-press", transaction_id="c" * 64)
    facts = {name: getattr(template, name) for name in type(template).model_fields}
    facts.update(
        acquisition=AcquisitionLineageReference(invoice_evidence_id="Factura 2014/118, Prensas SA"),
        acquisition_shape=AcquisitionShape.ACQUIRED_OUTSIDE_LEDGER,
        declared_acquisition_date=date(2014, 3, 1),
        declared_activity=TipoActividad.A03_RESTO_EMPRESARIALES,
    )
    facts.update(changes)
    return facts


def _element(**changes: Any) -> ActivityAssetRevision:
    return ActivityAssetRevision(**_facts(**changes))


def _assert_lineage_refusal(error: ValidationError, key: str) -> None:
    details = error.errors()
    assert len(details) == 1
    wrapper = details[0].get("ctx", {}).get("error")
    assert isinstance(wrapper, ValueError)
    cause = wrapper.__cause__
    assert isinstance(cause, ActividadAssetValidationError)
    assert cause.translated_message == f"ledger.actividad_asset.errors.{key}"
    assert cause.context == {"field": "acquisition"}


def test_it_owns_no_row_and_needs_no_reconciliation() -> None:
    element = _element()

    assert element.acquisition_transaction_ids == ()
    assert element.acquisition_row_in({}) is None
    assert require_acquisition_in_ledger(element, MemoryLedger()) is None


def test_a_claim_reaches_modelo_100_and_the_instalment_with_no_row() -> None:
    element = _element()
    history = ActivityAssetHistory(revisions=(element,), claims=(_register_claim(element, amount=Decimal("1200.00")),))

    annual = resolve_m100(history)

    assert Decimal("1200.00") in annual.binding_values.values()
    assert set(reasons(annual)) & GATE_REFUSED_REASONS == set()
    assert set(reasons(resolve_m130(history, "4T"))) & GATE_REFUSED_REASONS == set()


def test_a_baja_routes_its_gain_with_no_row() -> None:
    element = _element()
    baja = ActivityAssetDisposal(
        disposal_date=date(2025, 6, 30),
        reason=ActivityAssetDisposalReason.SALE,
        proceeds=Decimal("12000.00"),
        transmission_costs=Decimal("0.00"),
    )

    resolution = resolve_m100(ActivityAssetHistory(revisions=(element, element.with_disposal(baja))))

    # The minimum 12,000 x 5% x 181 / 365 = 297.53 is all gain.
    gains = [
        value for binding, value in resolution.binding_values.items() if str(binding).endswith("gain-element-1654")
    ]
    assert gains == [Decimal("297.53")]
    assert set(reasons(resolution)) & GATE_REFUSED_REASONS == set()


@pytest.mark.parametrize("reference", ["", "   "])
def test_it_is_refused_without_an_evidence_reference(reference: str) -> None:
    with pytest.raises(ValueError, match="acquisition_evidence_reference_required"):
        _element(acquisition=AcquisitionLineageReference(invoice_evidence_id=reference))


def test_it_is_refused_without_an_acquisition_date() -> None:
    with pytest.raises(ValueError, match="declared_acquisition_date_required"):
        _element(declared_acquisition_date=None)


def test_it_is_refused_without_a_declared_activity() -> None:
    with pytest.raises(ValueError, match="declared_activity_required"):
        _element(declared_activity=None)


def test_another_shape_cannot_declare_an_activity() -> None:
    purchase = register_asset("press", transaction_id="c" * 64)
    facts = {name: getattr(purchase, name) for name in type(purchase).model_fields}

    with pytest.raises(ValidationError) as caught:
        ActivityAssetRevision(**{**facts, "declared_activity": TipoActividad.B01_AGRICOLA})
    _assert_lineage_refusal(caught.value, "primary_purchase_lineage_shape")


def test_an_agrarian_element_stays_out_of_the_instalment_and_in_the_annual_return() -> None:
    agrarian = _element(declared_activity=TipoActividad.B01_AGRICOLA)
    other = _element()
    claims = (_register_claim(agrarian, amount=Decimal("1200.00")),)
    agrarian_history = ActivityAssetHistory(revisions=(agrarian,), claims=claims)
    other_history = ActivityAssetHistory(
        revisions=(other,), claims=(_register_claim(other, amount=Decimal("1200.00")),)
    )

    excluded = resolve_m130(agrarian_history, "4T")
    counted = resolve_m130(other_history, "4T")

    assert "activity_asset_agrarian_excluded" in reasons(excluded)
    assert sum(excluded.binding_values.values(), Decimal("0")) == Decimal("0")
    assert "activity_asset_agrarian_excluded" not in reasons(counted)
    # 12,000 x 10% for the year, the same element counted once its activity is not agrarian.
    assert sum(counted.binding_values.values(), Decimal("0")) == Decimal("1200.00")
    assert Decimal("1200.00") in resolve_m100(agrarian_history).binding_values.values()


def test_it_is_refused_with_a_date_after_service() -> None:
    with pytest.raises(ValueError, match="declared_acquisition_after_service"):
        _element(declared_acquisition_date=date(2025, 1, 2))


def test_it_cannot_also_name_a_ledger_row() -> None:
    row = AcquisitionLineageReference(observed_transaction_id="c" * 64, invoice_evidence_id="reference")

    with pytest.raises(ValidationError) as caught:
        _element(acquisition=row)
    _assert_lineage_refusal(caught.value, "outside_ledger_names_no_row")


def test_only_this_shape_may_go_without_a_row() -> None:
    lineage = AcquisitionLineageReference(invoice_evidence_id="reference")

    with pytest.raises(ValidationError) as caught:
        _element(acquisition=lineage, acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE)
    _assert_lineage_refusal(caught.value, "primary_purchase_lineage_shape")


def test_the_lease_stays_refused() -> None:
    with pytest.raises(ValueError, match="financial_lease_unexercised"):
        _element(acquisition_shape=AcquisitionShape.FINANCIAL_LEASE_UNEXERCISED)


def test_an_existing_purchase_keeps_its_identity() -> None:
    purchase = register_asset("press", transaction_id="c" * 64)
    payload = purchase.model_dump(mode="json", exclude={"supersedes_revision_id", "disposal", "further_acquisitions"})
    del payload["declared_acquisition_date"]
    del payload["declared_activity"]
    payload["supersedes_revision_id"] = None

    assert purchase.revision_id == content_hash_hex(payload)


def test_it_crosses_the_operation_boundary_unchanged() -> None:
    element = _element()

    restored = ActivityAssetRevisionSnapshot.from_domain(element).to_domain()

    assert restored == element
    assert restored.revision_id == element.revision_id


def test_it_leaves_every_ledger_payment_a_candidate() -> None:
    row = acquisition_transaction()

    candidates = acquisition_candidates(MemoryLedger(row).load(), ActivityAssetHistory(revisions=(_element(),)))

    assert [item.transaction_id for item in candidates] == [row.transaction_id]
