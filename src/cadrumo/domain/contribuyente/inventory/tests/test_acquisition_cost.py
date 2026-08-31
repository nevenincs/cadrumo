"""Complete inventory acquisition-cost contract and valuation tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....filing_evidence import FilingEvidenceReference
from ..records import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
    InventoryAttributableCostComponent,
    InventoryAttributableCostKind,
    InventoryLedger,
    MovementKind,
    MovementRecord,
    ValuationMethod,
    compute_inventory_valuation,
    inventory_acquisition_fingerprint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_DIGEST_C = "c" * 64
_DIGEST_D = "d" * 64


def _ref(value: str) -> FilingEvidenceReference:
    return FilingEvidenceReference(reference=value)


def _acquisition(**overrides: object) -> InventoryAcquisitionCost:
    fields: dict[str, object] = {
        "consideration_excluding_iva": Decimal("100.00"),
        "consideration_iva_amount": Decimal("21.00"),
        "consideration_deductible_iva_ratio": Decimal("0.50"),
        "attributable_cost_components": (
            InventoryAttributableCostComponent(
                component_id="freight-1",
                kind=InventoryAttributableCostKind.FREIGHT,
                taxable_base=Decimal("10.00"),
                iva_amount=Decimal("2.10"),
                deductible_iva_ratio=Decimal("0"),
                evidence_references=(_ref("freight-evidence"),),
            ),
        ),
        "evidence": (
            InventoryAcquisitionEvidence(
                reference=_ref("invoice-evidence"),
                evidence_kind=InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE,
                content_digest=_DIGEST_A,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref("freight-evidence"),
                evidence_kind=InventoryAcquisitionEvidenceKind.TRANSPORT_DOCUMENT,
                content_digest=_DIGEST_B,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref("cost-review-evidence"),
                evidence_kind=InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
                content_digest=_DIGEST_C,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref("iva-review-evidence"),
                evidence_kind=InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
                content_digest=_DIGEST_D,
            ),
        ),
        "completeness": InventoryAcquisitionCompleteness(
            consideration_evidence=_ref("invoice-evidence"),
            attributable_cost_review_evidence=_ref("cost-review-evidence"),
            iva_recoverability_review_evidence=_ref("iva-review-evidence"),
        ),
        "directly_attributable_cost_total": Decimal("10.00"),
        "nonrecoverable_iva_included": Decimal("12.60"),
        "recoverable_iva_excluded": Decimal("10.50"),
        "total_acquisition_cost": Decimal("122.60"),
    }
    fields.update(overrides)
    return InventoryAcquisitionCost.model_validate(fields)


def _purchase(**overrides: object) -> MovementRecord:
    fields: dict[str, object] = {
        "movement_id": "purchase-1",
        "movement_date": date(2025, 2, 1),
        "kind": MovementKind.PURCHASE,
        "quantity": Decimal("2"),
        "unit_cost": Decimal("50.00"),
        "taxable_base": Decimal("100.00"),
        "iva_rate": Decimal("21"),
        "iva_amount": Decimal("21.00"),
        "deductible_iva_ratio": Decimal("0.50"),
        "acquisition_cost": _acquisition(),
    }
    fields.update(overrides)
    return MovementRecord.model_validate(fields)


def test_complete_acquisition_is_the_sole_fifo_and_pmp_cost_authority() -> None:
    purchase = _purchase()
    sale = MovementRecord(
        movement_id="sale-1",
        movement_date=date(2025, 3, 1),
        kind=MovementKind.COGS,
        quantity=Decimal("1"),
    )

    for method in (ValuationMethod.FIFO, ValuationMethod.PMP):
        result = compute_inventory_valuation(
            InventoryLedger(
                actividad_id="retail",
                year=2025,
                valuation_method=method,
                opening_stock=Decimal("0.00"),
                closing_authority_record=None,
                period_movements=(purchase, sale),
            ),
        )
        assert result.purchase_value == Decimal("122.60")
        assert result.cogs_value == Decimal("61.30")
        assert result.closing_value == Decimal("61.30")


@pytest.mark.parametrize(
    ("ratio", "recoverable", "nonrecoverable", "total"),
    [
        ("0", "0.00", "23.10", "133.10"),
        ("0.50", "10.50", "12.60", "122.60"),
        ("1", "21.00", "2.10", "112.10"),
    ],
)
def test_purchase_factory_preserves_every_iva_recoverability_boundary(
    ratio: str, recoverable: str, nonrecoverable: str, total: str
) -> None:
    acquisition = _acquisition(
        consideration_deductible_iva_ratio=Decimal(ratio),
        recoverable_iva_excluded=Decimal(recoverable),
        nonrecoverable_iva_included=Decimal(nonrecoverable),
        total_acquisition_cost=Decimal(total),
    )
    movement = MovementRecord.from_purchase_acquisition(
        movement_id="purchase-ratio",
        movement_date=date(2025, 2, 1),
        quantity=Decimal("2"),
        acquisition_cost=acquisition,
    )
    assert movement.deductible_iva_ratio == Decimal(ratio)
    assert movement.acquisition_cost == acquisition


def test_purchase_factory_uses_zero_rate_for_zero_consideration() -> None:
    acquisition = _acquisition(
        consideration_excluding_iva=Decimal("0.00"),
        consideration_iva_amount=Decimal("0.00"),
        consideration_deductible_iva_ratio=Decimal("0"),
        attributable_cost_components=(),
        directly_attributable_cost_total=Decimal("0.00"),
        recoverable_iva_excluded=Decimal("0.00"),
        nonrecoverable_iva_included=Decimal("0.00"),
        total_acquisition_cost=Decimal("0.00"),
    )
    movement = MovementRecord.from_purchase_acquisition(
        movement_id="free-purchase",
        movement_date=date(2025, 2, 1),
        quantity=Decimal("1"),
        acquisition_cost=acquisition,
    )
    assert movement.iva_rate == Decimal("0")


def test_pmp_repeating_unit_cost_layers_reconcile_to_exact_closing_value() -> None:
    acquisition = _acquisition(
        consideration_excluding_iva=Decimal("100.00"),
        consideration_iva_amount=Decimal("0.00"),
        consideration_deductible_iva_ratio=Decimal("1"),
        attributable_cost_components=(),
        directly_attributable_cost_total=Decimal("0.00"),
        recoverable_iva_excluded=Decimal("0.00"),
        nonrecoverable_iva_included=Decimal("0.00"),
        total_acquisition_cost=Decimal("100.00"),
    )
    purchase = _purchase(
        quantity=Decimal("3"),
        unit_cost=None,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0"),
        iva_amount=Decimal("0.00"),
        deductible_iva_ratio=Decimal("1"),
        acquisition_cost=acquisition,
    )
    result = compute_inventory_valuation(
        InventoryLedger(
            actividad_id="retail",
            year=2025,
            valuation_method=ValuationMethod.PMP,
            opening_stock=Decimal("0.00"),
            closing_authority_record=None,
            period_movements=(purchase,),
        ),
    )

    assert result.closing_value == Decimal("100.00")
    next_year = InventoryLedger(
        actividad_id="retail",
        year=2026,
        valuation_method=ValuationMethod.PMP,
        opening_stock=result.closing_value,
        closing_authority_record=None,
        opening_layers=result.closing_layers,
    )
    assert next_year.opening_stock == Decimal("100.00")


@pytest.mark.parametrize("ratio", [Decimal("0"), Decimal("0.50"), Decimal("1")])
def test_iva_split_is_exact_at_zero_partial_and_full_recoverability(ratio: Decimal) -> None:
    recoverable = Decimal("21.00") * ratio
    acquisition = _acquisition(
        consideration_deductible_iva_ratio=ratio,
        attributable_cost_components=(),
        directly_attributable_cost_total=Decimal("0.00"),
        recoverable_iva_excluded=recoverable,
        nonrecoverable_iva_included=Decimal("21.00") - recoverable,
        total_acquisition_cost=Decimal("121.00") - recoverable,
    )

    assert acquisition.recoverable_iva_excluded + acquisition.nonrecoverable_iva_included == Decimal("21.00")


def test_iva_split_uses_one_rounded_recoverable_value_and_subtraction() -> None:
    acquisition = _acquisition(
        consideration_iva_amount=Decimal("0.05"),
        consideration_deductible_iva_ratio=Decimal("0.50"),
        attributable_cost_components=(),
        directly_attributable_cost_total=Decimal("0.00"),
        recoverable_iva_excluded=Decimal("0.03"),
        nonrecoverable_iva_included=Decimal("0.02"),
        total_acquisition_cost=Decimal("100.02"),
    )

    assert acquisition.recoverable_iva_excluded + acquisition.nonrecoverable_iva_included == Decimal("0.05")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("directly_attributable_cost_total", Decimal("9.99")),
        ("recoverable_iva_excluded", Decimal("10.49")),
        ("nonrecoverable_iva_included", Decimal("12.59")),
        ("total_acquisition_cost", Decimal("122.59")),
        ("total_acquisition_cost", Decimal("122.601")),
    ],
)
def test_acquisition_refuses_inconsistent_or_subcent_totals(field: str, value: Decimal) -> None:
    with pytest.raises(ValidationError):
        _acquisition(**{field: value})


def test_acquisition_refuses_dangling_and_duplicate_evidence_or_components() -> None:
    duplicate_component = _acquisition().attributable_cost_components[0]
    with pytest.raises(ValidationError, match="component identities must be unique"):
        _acquisition(attributable_cost_components=(duplicate_component, duplicate_component))

    incomplete = _acquisition().model_dump()
    incomplete["evidence"] = tuple(incomplete["evidence"][:1])
    with pytest.raises(ValidationError, match="references are unresolved"):
        InventoryAcquisitionCost.model_validate(incomplete)


def test_completeness_requires_role_specific_review_evidence() -> None:
    acquisition = _acquisition()
    wrong_role = acquisition.completeness.model_copy(
        update={"attributable_cost_review_evidence": _ref("invoice-evidence")},
    )
    with pytest.raises(ValidationError, match="attributable-cost review evidence"):
        InventoryAcquisitionCost.model_validate({**acquisition.model_dump(), "completeness": wrong_role})


def test_purchase_requires_complete_cost_and_other_kinds_forbid_it() -> None:
    with pytest.raises(ValidationError, match="require complete acquisition_cost"):
        _purchase(acquisition_cost=None)

    with pytest.raises(ValidationError, match="permitted only for purchase"):
        MovementRecord(
            movement_id="opening-1",
            movement_date=date(2025, 1, 1),
            kind=MovementKind.OPENING,
            quantity=Decimal("1"),
            unit_cost=Decimal("100.00"),
            acquisition_cost=_acquisition(),
        )


def test_purchase_refuses_competing_consideration_iva_and_recoverability() -> None:
    with pytest.raises(ValidationError, match="taxable_base must equal"):
        _purchase(unit_cost=Decimal("49.99"))
    with pytest.raises(ValidationError, match="consideration must equal"):
        _purchase(
            acquisition_cost=_acquisition(
                consideration_excluding_iva=Decimal("99.00"),
                total_acquisition_cost=Decimal("121.60"),
            ),
        )
    with pytest.raises(ValidationError, match="consideration IVA must equal"):
        _purchase(
            acquisition_cost=_acquisition(
                consideration_iva_amount=Decimal("20.00"),
                recoverable_iva_excluded=Decimal("10.00"),
                nonrecoverable_iva_included=Decimal("12.10"),
                total_acquisition_cost=Decimal("122.10"),
            ),
        )
    with pytest.raises(ValidationError, match="recoverability must equal"):
        acquisition = _acquisition(
            consideration_deductible_iva_ratio=Decimal("1"),
            recoverable_iva_excluded=Decimal("21.00"),
            nonrecoverable_iva_included=Decimal("2.10"),
            total_acquisition_cost=Decimal("112.10"),
        )
        _purchase(acquisition_cost=acquisition)


def test_fingerprint_is_order_independent_and_mutation_sensitive() -> None:
    purchase = _purchase()
    acquisition = purchase.acquisition_cost
    assert acquisition is not None
    reordered = InventoryAcquisitionCost.model_validate(
        {
            **acquisition.model_dump(),
            "evidence": tuple(reversed(acquisition.evidence)),
        },
    )
    assert inventory_acquisition_fingerprint(purchase) == inventory_acquisition_fingerprint(
        _purchase(acquisition_cost=reordered),
    )

    mutated_evidence = acquisition.evidence[0].model_copy(update={"content_digest": "d" * 64})
    mutated = InventoryAcquisitionCost.model_validate(
        {
            **acquisition.model_dump(),
            "evidence": (mutated_evidence, *acquisition.evidence[1:]),
        },
    )
    assert inventory_acquisition_fingerprint(purchase) != inventory_acquisition_fingerprint(
        _purchase(acquisition_cost=mutated),
    )

    scale_variant = _purchase(quantity=Decimal("2.0"), deductible_iva_ratio=Decimal("0.500"))
    assert inventory_acquisition_fingerprint(purchase) == inventory_acquisition_fingerprint(scale_variant)


def test_fingerprint_refuses_non_purchase_movements() -> None:
    with pytest.raises(ValueError, match="only a complete purchase"):
        inventory_acquisition_fingerprint(
            MovementRecord(
                movement_id="sale-1",
                movement_date=date(2025, 3, 1),
                kind=MovementKind.COGS,
                quantity=Decimal("1"),
            ),
        )
