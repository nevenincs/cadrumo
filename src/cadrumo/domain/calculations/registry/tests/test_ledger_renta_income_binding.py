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
from pydantic import ValidationError

from .....application.aggregation import RentaIncomeObservation
from .....core.aggregation import (
    BindingAggregation,
    BindingAggregationOp,
    BindingSourceKind,
    LedgerIncomeGrounding,
)
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources.bundled_data import bundled_path
from .....tests.registry_snapshot import build_snapshot
from ..binding_selector_utils import selector_as_dict
from ..ledger_renta_income_bindings import (
    resolve_ledger_renta_income_aggregation_binding_values,
    ungrounded_ledger_renta_income_observations,
    unsupported_ledger_renta_income_observations,
    validate_ledger_renta_income_aggregation_binding_definition,
)
from ..schema import DataBindingDefinition
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_INGRESOS_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"
_RETENCIONES_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"
_TAXABLE_BASE_BINDING = "modelo-130-actividad-economica-ingresos-taxable-base-cumulative"
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id(
    "03",
    surface="_M130_RENDIMIENTO_NETO_CASILLA",
)


def _tx(suffix: str) -> str:
    """A real hex-64 shape ending in ``suffix``.

    ``RentaIncomeObservation.transaction_id`` is typed
    :data:`~core.identity.TransactionId`, so a human-readable placeholder
    like the prior ``"inv-tagged"`` literal fails shape validation before
    the aggregation behaviour each test exercises is ever reached. ``suffix``
    must itself be hex-safe; distinct suffixes keep the fixtures below
    distinguishable in failure output.
    """
    return suffix.rjust(64, "0")


def _modelo_130_snapshot():
    modelo, catalogues = _committed_modelo("130")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )


def test_committed_m130_casilla_01_binds_ingresos_integros_fact() -> None:
    """The committed registry routes casilla 01 through ingresos_integros_sum."""
    revision = _modelo_130_snapshot().revision

    casilla_01 = next(casilla for casilla in revision.casillas if casilla.id == _M130_INGRESOS_CASILLA)
    assert casilla_01.binding == _INGRESOS_BINDING

    binding = next(binding for binding in revision.bindings if binding.id == _INGRESOS_BINDING)
    assert binding.source == "ledger_renta_income_aggregation"
    assert selector_as_dict(binding)["fact"] == "ingresos_integros_sum"
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
    tagged = RentaIncomeObservation(
        transaction_id=_tx("1a"),
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("1210.00"),
        taxable_base_amount=Decimal("1000.00"),
        filing_date=date(2026, 2, 10),
        grounding=LedgerIncomeGrounding.SUBSTRATE_DECLARED,
    )
    untagged = RentaIncomeObservation(
        transaction_id=_tx("1b"),
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("500.00"),
        taxable_base_amount=None,
        filing_date=date(2026, 3, 5),
        grounding=LedgerIncomeGrounding.CASH_FALLBACK,
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
    assert selector_as_dict(binding) == {
        "modelo": "130",
        "target_casilla_id": _M130_INGRESOS_CASILLA,
        "fact": "withheld_amount_sum",
    }
    validate_ledger_renta_income_aggregation_binding_definition(binding)

    net_paid = RentaIncomeObservation(
        transaction_id=_tx("2a"),
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("2120.00"),
        taxable_base_amount=Decimal("2000.00"),
        withheld_amount=Decimal("300.00"),
        filing_date=date(2026, 3, 15),
        grounding=LedgerIncomeGrounding.SUBSTRATE_DECLARED,
    )
    no_withholding = RentaIncomeObservation(
        transaction_id=_tx("2b"),
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("1210.00"),
        taxable_base_amount=Decimal("1000.00"),
        withheld_amount=Decimal("0.00"),
        filing_date=date(2026, 3, 20),
        grounding=LedgerIncomeGrounding.SUBSTRATE_DECLARED,
    )

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, (net_paid, no_withholding))

    assert resolved[_RETENCIONES_BINDING] == Decimal("300.00")
    assert resolved[_RETENCIONES_BINDING] != net_paid.gross_amount
    assert resolved[_RETENCIONES_BINDING] != net_paid.taxable_base_amount


def test_taxable_base_sum_fact_sums_only_declared_taxable_base() -> None:
    """The taxable_base_sum binding sums taxable_base_amount, zeroing undeclared bases.

    Grounds a fact no existing test asserted end to end through the
    resolver: ``modelo-130-actividad-economica-ingresos-taxable-base-
    cumulative`` runs on the same M130 revision as the ``ingresos_integros_
    sum`` / ``withheld_amount_sum`` bindings already covered above, but no
    prior test read ITS resolved value (an earlier resolver call exercised
    it only as an unchecked side effect). An untagged row (no declared
    base) must contribute zero here — the opposite of ingresos_integros_
    sum's gross-amount fallback — so a regression collapsing the two facts
    together is caught.
    """
    revision = _modelo_130_snapshot().revision
    tagged = RentaIncomeObservation(
        transaction_id=_tx("3a"),
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("1210.00"),
        taxable_base_amount=Decimal("1000.00"),
        filing_date=date(2026, 2, 10),
        grounding=LedgerIncomeGrounding.SUBSTRATE_DECLARED,
    )
    untagged = RentaIncomeObservation(
        transaction_id=_tx("3b"),
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("500.00"),
        taxable_base_amount=None,
        filing_date=date(2026, 3, 5),
        grounding=LedgerIncomeGrounding.CASH_FALLBACK,
    )

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, (tagged, untagged))

    # The tagged row is the one carrying a base; naming that here keeps the
    # contrast below arithmetic on a real Decimal rather than an optional one.
    tagged_base = tagged.taxable_base_amount
    assert tagged_base is not None

    assert resolved[_TAXABLE_BASE_BINDING] == Decimal("1000.00")
    assert resolved[_TAXABLE_BASE_BINDING] != tagged_base + untagged.gross_amount, (
        "taxable_base_sum must not fall back to the untagged row's gross_amount"
    )


def test_cash_received_sum_fact_sums_gross_amount_unconditionally() -> None:
    """A cash_received_sum binding sums gross_amount even when a taxable_base_amount is declared.

    No committed ``ledger_renta_income_aggregation`` binding declares
    ``cash_received_sum``, so this branch of the resolver's fact dispatch had
    zero test coverage before this test. Constructs a synthetic sibling
    binding on the real casilla 01 — a structural wiring check, not a
    legal-grounding claim.

    The fact is deliberately reachable but never committed: it sums the raw
    bank-credited cash, which is neither gross of retención nor IVA-exclusive
    and is therefore not the ingresos-íntegros measure casilla 01 asks for.
    """
    revision = _modelo_130_snapshot().revision
    committed_binding = next(binding for binding in revision.bindings if binding.id == _INGRESOS_BINDING)
    gross_binding = committed_binding.model_copy(
        update={
            "id": "test-m130-gross-income-sum",
            "selector": {"modelo": "130", "target_casilla_id": _M130_INGRESOS_CASILLA, "fact": "cash_received_sum"},
        },
    )
    revision_with_gross_binding = revision.model_copy(update={"bindings": (*revision.bindings, gross_binding)})

    tagged = RentaIncomeObservation(
        transaction_id=_tx("4a"),
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("1210.00"),
        taxable_base_amount=Decimal("1000.00"),
        filing_date=date(2026, 2, 10),
        grounding=LedgerIncomeGrounding.SUBSTRATE_DECLARED,
    )

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision_with_gross_binding, (tagged,))

    assert resolved[gross_binding.id] == Decimal("1210.00")
    assert resolved[gross_binding.id] != tagged.taxable_base_amount, (
        "cash_received_sum must not fall back to the ingresos_integros_sum base-preferring behaviour"
    )


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
            selector={"modelo": "130", "target_casilla": _M130_INGRESOS_CASILLA, "fact": "cash_received_sum"},
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

    routed = RentaIncomeObservation(
        transaction_id=_tx("5a"),
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("1000.00"),
        taxable_base_amount=None,
        filing_date=date(2026, 2, 10),
        grounding=LedgerIncomeGrounding.CASH_FALLBACK,
    )
    unrouted = RentaIncomeObservation(
        transaction_id=_tx("5b"),
        target_casilla_id=_M130_RENDIMIENTO_NETO_CASILLA,
        gross_amount=Decimal("500.00"),
        taxable_base_amount=None,
        filing_date=date(2026, 3, 5),
        grounding=LedgerIncomeGrounding.CASH_FALLBACK,
    )

    result = unsupported_ledger_renta_income_observations(revision, (routed, unrouted))
    assert result == (unrouted,)


def test_unsupported_renta_income_does_not_flag_zero_income() -> None:
    """A zero-income observation routed to no binding must NOT false-fire.

    A zero declarable income contributes nothing whether or not it is routed, so
    the false-fire guard excludes it even when its target_casilla_id is unbound.
    """
    revision = _modelo_130_snapshot().revision

    zero_unrouted = RentaIncomeObservation(
        transaction_id=_tx("6a"),
        target_casilla_id=_M130_RENDIMIENTO_NETO_CASILLA,
        gross_amount=Decimal("0.00"),
        taxable_base_amount=None,
        filing_date=date(2026, 3, 5),
        grounding=LedgerIncomeGrounding.CASH_FALLBACK,
    )

    result = unsupported_ledger_renta_income_observations(revision, (zero_unrouted,))
    assert result == ()


def test_ungrounded_screen_flags_cash_fallback_rows_a_binding_consumes() -> None:
    """A consumed row with no declared base is surfaced as ungrounded.

    The complement of the unrouted screen above: this row IS consumed (it
    targets casilla 01, which every committed M130 income binding selects),
    so nothing vanishes — but its contribution rests on bank-credited cash
    rather than an invoice base imponible. The M130 revision declares BOTH
    base-reading facts, so the screen must report both: the row folded cash
    into ``ingresos_integros_sum`` AND contributed nothing to
    ``taxable_base_sum``.
    """
    revision = _modelo_130_snapshot().revision

    grounded = RentaIncomeObservation(
        transaction_id=_tx("7a"),
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("1210.00"),
        taxable_base_amount=Decimal("1000.00"),
        filing_date=date(2026, 2, 10),
        grounding=LedgerIncomeGrounding.SUBSTRATE_DECLARED,
    )
    ungrounded = RentaIncomeObservation(
        transaction_id=_tx("7b"),
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("500.00"),
        taxable_base_amount=None,
        filing_date=date(2026, 3, 5),
        grounding=LedgerIncomeGrounding.CASH_FALLBACK,
    )

    result = ungrounded_ledger_renta_income_observations(revision, (grounded, ungrounded))

    assert result.observations == (ungrounded,), "only the substrate-less row is ungrounded"
    assert result.facts == frozenset({"ingresos_integros_sum", "taxable_base_sum"})


def test_ungrounded_screen_reports_nothing_when_every_row_declares_its_base() -> None:
    """Full substrate declaration must not fire the advisory.

    The advisory only earns operator trust if every fire is a real ungrounded
    contribution; a revision whose consumed rows all carry a base has nothing
    to report.
    """
    revision = _modelo_130_snapshot().revision

    grounded = RentaIncomeObservation(
        transaction_id=_tx("7a"),
        target_casilla_id=_M130_INGRESOS_CASILLA,
        gross_amount=Decimal("1210.00"),
        taxable_base_amount=Decimal("1000.00"),
        filing_date=date(2026, 2, 10),
        grounding=LedgerIncomeGrounding.SUBSTRATE_DECLARED,
    )

    result = ungrounded_ledger_renta_income_observations(revision, (grounded,))

    assert result.observations == ()


def test_ungrounded_screen_ignores_rows_no_base_reading_binding_consumes() -> None:
    """A base-less row routed to an unbound casilla is the unrouted screen's business.

    The two screens must not double-report the same row: casilla 03 is
    selected by no committed M130 income binding, so this row is already
    surfaced by ``unsupported_ledger_renta_income_observations`` and must not
    also appear as an ungrounded contribution to a binding that never
    consumed it.
    """
    revision = _modelo_130_snapshot().revision

    unrouted = RentaIncomeObservation(
        transaction_id=_tx("8b"),
        target_casilla_id=_M130_RENDIMIENTO_NETO_CASILLA,
        gross_amount=Decimal("500.00"),
        taxable_base_amount=None,
        filing_date=date(2026, 3, 5),
        grounding=LedgerIncomeGrounding.CASH_FALLBACK,
    )

    assert ungrounded_ledger_renta_income_observations(revision, (unrouted,)).observations == ()
    assert unsupported_ledger_renta_income_observations(revision, (unrouted,)) == (unrouted,)


def test_selector_refuses_an_omitted_fact_and_names_the_accepted_set() -> None:
    """A binding that omits ``fact`` is refused, listing every accepted fact.

    The requiredness exists so no binding can silently inherit a legal
    measure; the refusal is only useful if it tells the author what to
    choose, so the message must enumerate the accepted set rather than
    saying "Field required".
    """
    with pytest.raises(ValidationError) as exc_info:
        DataBindingDefinition(
            id="m130-income-no-fact",
            source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
            selector={"modelo": "130", "target_casilla_id": _M130_INGRESOS_CASILLA},
            aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-modelo-130-instructions",),
        )

    detail = str(exc_info.value)
    assert "requires an explicit 'fact'" in detail
    for fact in ("ingresos_integros_sum", "cash_received_sum", "taxable_base_sum", "withheld_amount_sum"):
        assert fact in detail, f"the refusal must name the accepted fact {fact!r}"


def test_observation_refuses_a_grounding_marker_that_contradicts_its_base() -> None:
    """The marker and the base it describes cannot drift apart.

    Every consumer reads the marker rather than re-deriving nullness, so a
    row claiming declared substrate while carrying no base would send the
    advisory and the aggregation to opposite conclusions about the same row.
    """
    with pytest.raises(ValidationError, match="contradicts taxable_base_amount"):
        RentaIncomeObservation(
            transaction_id=_tx("9a"),
            target_casilla_id=_M130_INGRESOS_CASILLA,
            gross_amount=Decimal("500.00"),
            taxable_base_amount=None,
            filing_date=date(2026, 3, 5),
            grounding=LedgerIncomeGrounding.SUBSTRATE_DECLARED,
        )
