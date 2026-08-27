"""Modelo 390 annual base-imponible bindings draw real ledger base amounts.

The annual resumen aggregated the CUOTA of every régimen-general row but drew no
base imponible at all: each IVA observation carries a ``base_amount`` that
reached no binding on the annual return, while the quarterly Modelo 303 already
drew its base through the sibling ``modelo-303-iva-*-base`` bindings. The AEAT
Diseño de Registros pairs a "Base imponible" box with every "Cuota" box of the
Reg. ordinario block, so the form does ask for these amounts.

Real-behaviour: the committed Modelo 390 revision loaded through the real
registry authority, resolved by the real ``ledger_iva_aggregation`` resolver over
real :class:`IvaLedgerObservation` rows. No mocks, stubs, skips or xfail.

Non-tautology: every base amount is chosen so it cannot be produced from the
sibling cuota by applying the tier rate, and the three repercutido tiers carry
mutually distinct bases and cuotas. A resolver that returned the cuota for the
base, summed the wrong tier, or leaked one tier into another therefore fails on
value rather than merely on shape; no registry formula is re-computed here.

The last test is the load-bearing safety invariant of the whole change. The
annual devengada/deducible totals sum CUOTAS; a base casilla must never enter
one. Wiring a base casilla into the devengada formula while narrowing the tier
binding that currently feeds it is exactly how this addition would turn a
correct annual total into an under-declaration, so the formula closure is pinned
against every base casilla the revision declares.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import IvaDeductionFactKind
from ....iva import IvaCategory, IvaFlowDirection, IvaLedgerObservationRole, IvaRateKind
from ..authority import bundled_authority
from ..binding_selector_utils import selector_as_dict
from ..ledger_bindings import IvaLedgerObservation, resolve_ledger_iva_aggregation_binding_values
from ..schema import ModeloRevision
from ..schema_input_kind import InputKind
from ._ledger_iva_aggregation_support import _deduction_provenance

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_GENERAL_BASE = Decimal("4000.00")
_GENERAL_CUOTA = Decimal("840.00")
_REDUCIDO_BASE = Decimal("2500.00")
_REDUCIDO_CUOTA = Decimal("250.00")
_SUPER_REDUCIDO_BASE = Decimal("1200.00")
_SUPER_REDUCIDO_CUOTA = Decimal("48.00")
_ZERO_BASE = Decimal("700.00")
_SOPORTADO_BASE = Decimal("900.00")
_SOPORTADO_CUOTA = Decimal("189.00")
# The two volume boxes AEAT asks for beside the régimen-ordinario block. Distinct
# from every other base above so a resolver that folded either into the zero tier
# -- all three are zero-rated repercutido -- fails on value rather than on shape.
_INTRACOM_BASE = Decimal("1750.00")
_EXPORT_BASE = Decimal("2300.00")


def _m390_revision() -> ModeloRevision:
    return bundled_authority().snapshot("390", filing_year=2024, period="0A").revision


def _observation(
    *,
    category: IvaCategory,
    rate_kind: IvaRateKind,
    flow: IvaFlowDirection,
    base: Decimal,
    iva: Decimal,
    deduction_fact_kind: IvaDeductionFactKind | None = None,
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id="ledger-m390-base",
        transaction_date=date(2024, 6, 15),
        category=category,
        exemption_article=None,
        rate_kind=rate_kind,
        flow_direction=flow,
        base_amount=base,
        iva_amount=iva,
        recargo_amount=Decimal("0"),
        deduction_fact_kind=deduction_fact_kind,
        deduction_provenance=(
            _deduction_provenance(
                deduction_fact_kind,
                source_locator="invoice:ledger-m390-base",
            )
            if deduction_fact_kind is not None
            else None
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _annual_observations() -> tuple[IvaLedgerObservation, ...]:
    return (
        _observation(
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow=IvaFlowDirection.REPERCUTIDO,
            base=_GENERAL_BASE,
            iva=_GENERAL_CUOTA,
        ),
        _observation(
            category=IvaCategory.DOMESTIC_REDUCED,
            rate_kind=IvaRateKind.REDUCED,
            flow=IvaFlowDirection.REPERCUTIDO,
            base=_REDUCIDO_BASE,
            iva=_REDUCIDO_CUOTA,
        ),
        _observation(
            category=IvaCategory.DOMESTIC_SUPER_REDUCED,
            rate_kind=IvaRateKind.SUPER_REDUCED,
            flow=IvaFlowDirection.REPERCUTIDO,
            base=_SUPER_REDUCIDO_BASE,
            iva=_SUPER_REDUCIDO_CUOTA,
        ),
        # The zero tier: base imponible with no cuota, which is what a zero-rated
        # supply is. Its rate-blind total exists so a row whose rate the ledger
        # never captured still reaches the tier.
        _observation(
            category=IvaCategory.DOMESTIC_ZERO,
            rate_kind=IvaRateKind.ZERO,
            flow=IvaFlowDirection.REPERCUTIDO,
            base=_ZERO_BASE,
            iva=Decimal("0.00"),
        ),
        _observation(
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            base=_SOPORTADO_BASE,
            iva=_SOPORTADO_CUOTA,
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        ),
        # Exempt supplies carrying base with no cuota. They reach the volume
        # boxes rather than the régimen-ordinario tiers, and without a row of
        # each those two bindings resolve zero for want of input -- which reads
        # exactly like the dormant capacity the next test refuses to accept.
        _observation(
            category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
            rate_kind=IvaRateKind.ZERO,
            flow=IvaFlowDirection.REPERCUTIDO,
            base=_INTRACOM_BASE,
            iva=Decimal("0.00"),
        ),
        _observation(
            category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
            rate_kind=IvaRateKind.ZERO,
            flow=IvaFlowDirection.REPERCUTIDO,
            base=_EXPORT_BASE,
            iva=Decimal("0.00"),
        ),
    )


def _resolved() -> dict[str, Decimal]:
    revision = _m390_revision()
    return dict(resolve_ledger_iva_aggregation_binding_values(revision, _annual_observations()))


@pytest.mark.parametrize(
    ("binding_id", "expected"),
    (
        ("modelo-390-iva-repercutido-general-base", _GENERAL_BASE),
        ("modelo-390-iva-repercutido-reducido-base", _REDUCIDO_BASE),
        ("modelo-390-iva-repercutido-super-reducido-base", _SUPER_REDUCIDO_BASE),
        ("modelo-390-iva-repercutido-zero-base", _ZERO_BASE),
        ("modelo-390-iva-soportado-interiores-base", _SOPORTADO_BASE),
        ("modelo-390-volumen-entregas-intracomunitarias-base", _INTRACOM_BASE),
        ("modelo-390-volumen-exportaciones-exentas-base", _EXPORT_BASE),
    ),
)
def test_annual_base_binding_draws_its_tier_base_amount(binding_id: str, expected: Decimal) -> None:
    """Each annual base binding resolves to its own tier's ledger base amount."""
    resolved = _resolved()
    assert binding_id in resolved, f"{binding_id} resolved to nothing; the annual base draw is dormant"
    assert resolved[binding_id] == expected


def test_annual_base_bindings_resolve_non_zero() -> None:
    """A binding that can only ever resolve zero is dormant capacity, not a draw."""
    resolved = _resolved()
    # Scoped to the four rate-blind total-layer bindings this module owns. The
    # rate-specific box layer also ends in "-base" and legitimately resolves zero
    # for any rate absent from a given fixture, and so does the AIC per-tier
    # blind-base layer and the domestic-reverse-charge (ISP interior) base --
    # this fixture carries no adquisiciones intracomunitarias or ISP interior
    # rows at all, so every tier of those families is legitimately absent here.
    _NEW_FAMILY_MARKERS = ("-aic-", "-autorepercutido-interior-")
    base_bindings = {
        key: value
        for key, value in resolved.items()
        if key.endswith("-base") and "-tipo-" not in key and not any(marker in key for marker in _NEW_FAMILY_MARKERS)
    }
    assert base_bindings, "the annual revision declares no ledger base binding at all"
    assert all(value > 0 for value in base_bindings.values()), base_bindings


@pytest.mark.parametrize(
    ("base_binding_id", "cuota_binding_id", "cuota"),
    (
        (
            "modelo-390-iva-repercutido-general-base",
            "modelo-390-iva-repercutido-general-cuota",
            _GENERAL_CUOTA,
        ),
        (
            "modelo-390-iva-repercutido-reducido-base",
            "modelo-390-iva-repercutido-reducido-cuota",
            _REDUCIDO_CUOTA,
        ),
        (
            "modelo-390-iva-repercutido-super-reducido-base",
            "modelo-390-iva-repercutido-super-reducido-cuota",
            _SUPER_REDUCIDO_CUOTA,
        ),
        (
            "modelo-390-iva-soportado-interiores-base",
            "modelo-390-iva-soportado-interiores-cuota",
            _SOPORTADO_CUOTA,
        ),
    ),
)
def test_base_and_cuota_are_drawn_as_independent_quantities(
    base_binding_id: str,
    cuota_binding_id: str,
    cuota: Decimal,
) -> None:
    """Base and cuota of one tier are two quantities of the same rows, never one."""
    resolved = _resolved()
    assert resolved[cuota_binding_id] == cuota
    assert resolved[base_binding_id] != resolved[cuota_binding_id]


def test_every_declared_base_casilla_is_bound_to_a_base_fact() -> None:
    """A base casilla wired to a cuota fact would silently double-count the cuota."""
    revision = _m390_revision()
    bindings = {binding.id: binding for binding in revision.bindings}
    base_casillas = [casilla for casilla in revision.casillas if casilla.id.endswith(".base")]
    assert base_casillas, "the annual revision declares no base imponible casilla"
    for casilla in base_casillas:
        if casilla.binding is None:
            # An OPERATOR-MANUAL base has no fact, so it cannot be wired to the
            # wrong one -- which is the defect this test exists to catch. It is
            # still asserted to be manual rather than skipped: an unbound base
            # casilla that is NOT manual is a box something is meant to produce
            # and nothing does, and that must still fail here. Across all four
            # revisions every unbound base is manual (99, 101, 127, 127 of them),
            # so this discards no real finding.
            assert casilla.input_kind is InputKind.MANUAL, (
                f"base casilla {casilla.id} declares no binding and is not operator-manual, "
                "so nothing carries its figure"
            )
            continue
        binding = bindings[casilla.binding]
        selector = selector_as_dict(binding)
        assert selector.get("fact") == "base_amount_sum", (
            f"casilla {casilla.id} is bound to {binding.id} whose fact is {selector.get('fact')!r}"
        )


def test_no_base_casilla_enters_an_annual_total_formula() -> None:
    """The annual totals sum cuotas; a base casilla entering one under-declares.

    This pins the safety property of the base-imponible addition. The tier cuota
    casillas feed ``iva.anual.cuota-devengada-total``; the base casillas
    deliberately feed nothing. If a later change narrows a feeding cuota binding
    and wires a base casilla into the total instead, this fails.
    """
    revision = _m390_revision()
    base_casilla_ids = {casilla.id for casilla in revision.casillas if casilla.id.endswith(".base")}
    assert base_casilla_ids, "the annual revision declares no base imponible casilla"
    for formula in revision.formulas:
        referenced = {arg.casilla_id for arg in formula.expression.args if arg.casilla_id is not None}
        leaked = referenced & base_casilla_ids
        assert not leaked, f"formula {formula.id} sums base imponible casillas {sorted(leaked)}"
