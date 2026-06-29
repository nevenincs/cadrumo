"""Tests for ledger-backed Modelo 130 income registry bindings.

Pins the committed M130 casilla 01 contract: the casilla binds the
``modelo-130-actividad-economica-ingresos-cumulative`` binding whose fact
is ``ingresos_integros_sum`` — the per-observation IVA-exclusive measure.
Per the AEAT M130 instructions, casilla 01 consigns "la totalidad de los
ingresos íntegros fiscalmente computables"; IVA repercutido is collected
on behalf of Hacienda and is not computable income, so an IVA-tagged
invoice contributes its base imponible while an untagged bank receipt
falls back to its gross transfer amount (the only available measure).

Worked example grounding the values (AEAT-style professional invoice):
1000 EUR base + 21% IVA (210 EUR) = 1210 EUR gross transfer. Casilla 01
must carry 1000, never 1210. The mixed-set assertions use distinct
non-equal seeds so a gross-summing or base-only regression cannot
coincidentally satisfy them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from .....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from .....core.resources import bundled_path
from .. import (
    CasillaId,
    DataBindingDefinition,
    build_snapshot,
    load_registry_tree,
    resolve_ledger_renta_income_aggregation_binding_values,
    unsupported_ledger_renta_income_observations,
    validate_ledger_renta_income_aggregation_binding_definition,
    validated_casilla_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_INGRESOS_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"
_RETENCIONES_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id(
    "03",
    surface="_M130_RENDIMIENTO_NETO_CASILLA",
)


def _modelo_130_snapshot():
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(item for item in modelos if item.id == "130")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )


class _IncomeObservation(BaseModel):
    """Minimal structural stand-in satisfying RentaIncomeObservationProtocol."""

    transaction_id: str
    target_casilla_id: CasillaId
    gross_amount: Decimal
    taxable_base_amount: Decimal | None
    withheld_amount: Decimal = Decimal("0")
    filing_date: date


def test_committed_m130_casilla_01_binds_ingresos_integros_fact() -> None:
    """The committed registry routes casilla 01 through ingresos_integros_sum."""
    revision = _modelo_130_snapshot().revision

    casilla_01 = next(casilla for casilla in revision.casillas if casilla.id == _M130_INGRESOS_CASILLA)
    assert casilla_01.binding == _INGRESOS_BINDING

    binding = next(binding for binding in revision.bindings if binding.id == _INGRESOS_BINDING)
    assert binding.source == "ledger_renta_income_aggregation"
    assert dict(binding.selector)["fact"] == "ingresos_integros_sum"
    validate_ledger_renta_income_aggregation_binding_definition(binding)


def test_ingresos_integros_sum_uses_base_when_tagged_and_gross_when_not() -> None:
    """An IVA-tagged invoice contributes its base; an untagged receipt its gross.

    Tagged row: 1210 gross = 1000 base + 210 IVA (21%). Untagged row:
    500 gross, no declared base. Casilla 01's binding must resolve to
    1000 + 500 = 1500 — not the 1710 gross sum (IVA repercutido is not
    computable income) and not the 1000 base-only sum (an untagged
    receipt must not vanish from ingresos).
    """
    revision = _modelo_130_snapshot().revision
    tagged = _IncomeObservation(
        transaction_id="inv-tagged",
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("1210.00"),
        taxable_base_amount=Decimal("1000.00"),
        filing_date=date(2026, 2, 10),
    )
    untagged = _IncomeObservation(
        transaction_id="receipt-untagged",
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("500.00"),
        taxable_base_amount=None,
        filing_date=date(2026, 3, 5),
    )

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, (tagged, untagged))

    # Field-selection wiring contract: the tagged row contributes its
    # IVA-exclusive base, the untagged row its gross — never any other
    # field pairing. The inequality guards prove the selection is live:
    # a gross-summing regression yields 1710, a base-only regression 1000.
    assert tagged.taxable_base_amount is not None
    assert resolved[_INGRESOS_BINDING] == tagged.taxable_base_amount + untagged.gross_amount
    assert resolved[_INGRESOS_BINDING] != tagged.gross_amount + untagged.gross_amount, (
        "IVA-inclusive gross must not feed casilla 01"
    )
    assert resolved[_INGRESOS_BINDING] != tagged.taxable_base_amount, "untagged receipts must not vanish"


def test_committed_m130_retenciones_binding_reads_withheld_amount_fact() -> None:
    revision = _modelo_130_snapshot().revision

    binding = next(binding for binding in revision.bindings if binding.id == _RETENCIONES_BINDING)
    assert binding.source == "ledger_renta_income_aggregation"
    assert dict(binding.selector) == {
        "modelo": "130",
        "target_casilla_id": _M130_INGRESOS_CASILLA,
        "fact": "withheld_amount_sum",
    }
    validate_ledger_renta_income_aggregation_binding_definition(binding)

    net_paid = _IncomeObservation(
        transaction_id="inv-net-paid",
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("2120.00"),
        taxable_base_amount=Decimal("2000.00"),
        withheld_amount=Decimal("300.00"),
        filing_date=date(2026, 3, 15),
    )
    no_withholding = _IncomeObservation(
        transaction_id="inv-no-withholding",
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("1210.00"),
        taxable_base_amount=Decimal("1000.00"),
        withheld_amount=Decimal("0.00"),
        filing_date=date(2026, 3, 20),
    )

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, (net_paid, no_withholding))

    assert resolved[_RETENCIONES_BINDING] == Decimal("300.00")
    assert resolved[_RETENCIONES_BINDING] != net_paid.gross_amount
    assert resolved[_RETENCIONES_BINDING] != net_paid.taxable_base_amount


def test_income_binding_validator_rejects_unknown_fact() -> None:
    # ``net_income_sum`` is outside the ``_RentaLedgerIncomeSelector`` fact
    # Literal, a selector-SHAPE violation the F8 construction-time gate refuses
    # the moment the binding is built.
    with pytest.raises(ValidationError):
        DataBindingDefinition(
            id="m130-income-bad-fact",
            source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
            selector={"modelo": "130", "target_casilla_id": _M130_INGRESOS_CASILLA, "fact": "net_income_sum"},
            aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-modelo-130-instructions",),
        )


def test_income_binding_validator_rejects_legacy_target_casilla_key() -> None:
    # The legacy ``target_casilla`` key is a selector-SHAPE violation (the strict
    # selector model forbids the extra key), refused at construction under F8;
    # the diagnostic still names both the canonical and legacy key.
    with pytest.raises(ValidationError) as exc_info:
        DataBindingDefinition(
            id="m130-income-legacy-target-key",
            source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
            selector={"modelo": "130", "target_casilla": _M130_INGRESOS_CASILLA, "fact": "gross_income_sum"},
            aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-modelo-130-instructions",),
        )

    detail = str(exc_info.value)
    assert "target_casilla_id" in detail
    assert "target_casilla" in detail


def test_unsupported_renta_income_flags_observation_routed_to_no_binding() -> None:
    """A non-zero income whose target_casilla_id matches no binding is surfaced.

    Every committed M130 income binding selects casilla 01; an observation
    routed to casilla 03 reaches no binding and would silently vanish, so the
    fail-closed screen MUST report it (no-silent-under-declaration).
    """
    revision = _modelo_130_snapshot().revision

    routed = _IncomeObservation(
        transaction_id="inv-routed",
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("1000.00"),
        taxable_base_amount=None,
        filing_date=date(2026, 2, 10),
    )
    unrouted = _IncomeObservation(
        transaction_id="inv-unrouted",
        target_casilla_id=_M130_RENDIMIENTO_NETO_CASILLA,
        gross_amount=Decimal("500.00"),
        taxable_base_amount=None,
        filing_date=date(2026, 3, 5),
    )

    result = unsupported_ledger_renta_income_observations(revision, (routed, unrouted))
    assert result == (unrouted,)


def test_unsupported_renta_income_does_not_flag_zero_income() -> None:
    """A zero-income observation routed to no binding must NOT false-fire.

    A zero declarable income contributes nothing whether or not it is routed, so
    the false-fire guard excludes it even when its target_casilla_id is unbound.
    """
    revision = _modelo_130_snapshot().revision

    zero_unrouted = _IncomeObservation(
        transaction_id="inv-zero",
        target_casilla_id=_M130_RENDIMIENTO_NETO_CASILLA,
        gross_amount=Decimal("0.00"),
        taxable_base_amount=None,
        filing_date=date(2026, 3, 5),
    )

    result = unsupported_ledger_renta_income_observations(revision, (zero_unrouted,))
    assert result == ()
