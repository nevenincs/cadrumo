"""Modelo 390 rate-specific box layer draws each official rate box separately.

The annual resumen exported one rate-blind casilla per tier to a rate-specific
AEAT box, so a 10 % and a 7,5 % sale merged into box [04] while [670] stayed
empty. Splitting a tier's roles gives each official box its own casilla, bound
to exactly one rate.

The layer is deliberately NOT exported yet. The rate-blind tier casillas still
write offsets 98/200/234, and flipping those fields onto this layer is only safe
alongside the gate that refuses a return whose rate boxes sum below its declared
total. Until that lands, a declared-but-unpopulated money field would render
``0,00`` rather than a blank, turning a silence into a false nil.

Real-behaviour: the committed revision through the real registry authority,
resolved by the real ``ledger_iva_aggregation`` resolver over real
:class:`IvaLedgerObservation` rows. No mocks, stubs, skips or xfail.

Non-tautology: every tier carries a distinct base and a distinct cuota, and no
cuota is derivable from its base by the tier's rate, so a resolver that summed
the wrong rate, leaked a neighbouring rate, or returned base for cuota fails on
value. Three rates are date-windowed by RDL 4/2024 art. 1 and are exercised
inside their real windows, so a binding that ignored the window would also fail.
No registry formula is re-computed here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import resources
from ....iva import IvaCategory, IvaFlowDirection, IvaRateKind
from .. import IvaLedgerObservation, ModeloRevision, resolve_ledger_iva_aggregation_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# rate suffix, category, tier, a date inside the rate's 2024 window, base, cuota.
# 5 % applies 1 Jul - 30 Sep 2024 and 7,5 % / 2 % from 1 Oct (RDL 4/2024 art. 1),
# so each windowed rate is exercised on a date where it is actually in force.
_TIERS = (
    ("21", IvaCategory.DOMESTIC_GENERAL, IvaRateKind.GENERAL, date(2024, 3, 10), "4000.00", "840.00"),
    ("10", IvaCategory.DOMESTIC_REDUCED, IvaRateKind.REDUCED, date(2024, 3, 11), "2500.00", "250.00"),
    ("7-5", IvaCategory.DOMESTIC_REDUCED, IvaRateKind.REDUCED, date(2024, 11, 12), "1600.00", "120.00"),
    ("5", IvaCategory.DOMESTIC_REDUCED, IvaRateKind.REDUCED, date(2024, 8, 13), "1400.00", "70.00"),
    ("4", IvaCategory.DOMESTIC_SUPER_REDUCED, IvaRateKind.SUPER_REDUCED, date(2024, 3, 14), "1200.00", "48.00"),
    ("2", IvaCategory.DOMESTIC_SUPER_REDUCED, IvaRateKind.SUPER_REDUCED, date(2024, 11, 15), "900.00", "18.00"),
    ("0", IvaCategory.DOMESTIC_ZERO, IvaRateKind.ZERO, date(2024, 3, 16), "700.00", "0.00"),
)

_APPLIED_RATE = {"21": "0.21", "10": "0.10", "7-5": "0.075", "5": "0.05", "4": "0.04", "2": "0.02", "0": "0.00"}

_UNRATED_CUOTA = Decimal("33.00")
_UNRATED_BASE = Decimal("330.00")


def _m390_revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("390", filing_year=2024, period="0A").revision


def _observation(
    *,
    category: IvaCategory,
    rate_kind: IvaRateKind,
    on: date,
    base: Decimal,
    cuota: Decimal,
    applied_rate: Decimal | None,
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id="ledger-m390-rate-box",
        transaction_date=on,
        category=category,
        exemption_article=None,
        rate_kind=rate_kind,
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        base_amount=base,
        iva_amount=cuota,
        recargo_amount=Decimal("0"),
        applied_rate=applied_rate,
    )


def _rated_rows() -> tuple[IvaLedgerObservation, ...]:
    return tuple(
        _observation(
            category=category,
            rate_kind=tier,
            on=on,
            base=Decimal(base),
            cuota=Decimal(cuota),
            applied_rate=Decimal(_APPLIED_RATE[suffix]),
        )
        for suffix, category, tier, on, base, cuota in _TIERS
    )


def _unrated_row() -> IvaLedgerObservation:
    """A reducido row whose rate the ledger never captured (``iva_rate`` is optional)."""
    return _observation(
        category=IvaCategory.DOMESTIC_REDUCED,
        rate_kind=IvaRateKind.REDUCED,
        on=date(2024, 6, 1),
        base=_UNRATED_BASE,
        cuota=_UNRATED_CUOTA,
        applied_rate=None,
    )


def _resolve(rows: tuple[IvaLedgerObservation, ...]) -> dict[str, Decimal]:
    return dict(resolve_ledger_iva_aggregation_binding_values(_m390_revision(), rows))


@pytest.mark.parametrize(("suffix", "base", "cuota"), tuple((t[0], t[4], t[5]) for t in _TIERS))
def test_each_rate_box_draws_only_its_own_rate(suffix: str, base: str, cuota: str) -> None:
    """Each official rate box resolves to its own rate's amounts, not its tier's."""
    resolved = _resolve(_rated_rows())
    assert resolved[f"modelo-390-iva-repercutido-tipo-{suffix}-base"] == Decimal(base)
    assert resolved[f"modelo-390-iva-repercutido-tipo-{suffix}-cuota"] == Decimal(cuota)


def test_the_tier_merge_is_separated() -> None:
    """The 10 % and 7,5 % rows that merged into one box now land in two."""
    resolved = _resolve(_rated_rows())
    assert resolved["modelo-390-iva-repercutido-tipo-10-cuota"] == Decimal("250.00")
    assert resolved["modelo-390-iva-repercutido-tipo-7-5-cuota"] == Decimal("120.00")
    # The rate-blind tier casilla still carries both, because it feeds the total.
    assert resolved["modelo-390-iva-repercutido-reducido-cuota"] == Decimal("440.00")


def test_a_windowed_rate_resolves_inside_its_window() -> None:
    """5 % applies 1 Jul - 30 Sep 2024 only, and an annual return spans that window.

    A binding that could never resolve non-zero would be dormant capacity. This
    pins that the windowed rates are reachable, which a Q4-only fixture would
    have missed for 5 % and a Q1-only fixture would have missed for 7,5 % and 2 %.
    """
    resolved = _resolve(_rated_rows())
    for suffix in ("5", "7-5", "2"):
        assert resolved[f"modelo-390-iva-repercutido-tipo-{suffix}-cuota"] > 0


def test_no_rate_box_claims_the_rate_unrecorded_row() -> None:
    """A row whose rate is unknown must not be asserted into a rate-specific box."""
    resolved = _resolve((*_rated_rows(), _unrated_row()))
    for suffix, *_ in _TIERS:
        cuota = resolved[f"modelo-390-iva-repercutido-tipo-{suffix}-cuota"]
        assert cuota != _UNRATED_CUOTA, f"tipo-{suffix} absorbed the rate-unrecorded row"
    assert resolved["modelo-390-iva-repercutido-tipo-10-cuota"] == Decimal("250.00")


def test_the_rate_blind_total_layer_retains_the_unrated_row() -> None:
    """The property the whole split rests on: unrated money stays in the total.

    If a later change narrows the tier binding, this row reaches no casilla at
    all and its money leaves the annual devengada total silently.
    """
    without = _resolve(_rated_rows())["modelo-390-iva-repercutido-reducido-cuota"]
    with_unrated = _resolve((*_rated_rows(), _unrated_row()))["modelo-390-iva-repercutido-reducido-cuota"]
    assert with_unrated - without == _UNRATED_CUOTA


def test_base_and_cuota_of_a_tier_drop_the_same_rows() -> None:
    """Base and cuota must narrow symmetrically, or an impossible record appears.

    A populated cuota beside an empty base asserts tax charged on no taxable
    amount. Because both bindings of a rate carry the same ``applied_rates``,
    the rate-unrecorded row falls out of both together.
    """
    rated = _resolve(_rated_rows())
    with_unrated = _resolve((*_rated_rows(), _unrated_row()))
    for suffix, *_ in _TIERS:
        for kind in ("base", "cuota"):
            key = f"modelo-390-iva-repercutido-tipo-{suffix}-{kind}"
            assert rated[key] == with_unrated[key], f"{key} moved when an unrated row was added"


def test_a_non_zero_rate_cuota_implies_a_non_zero_base() -> None:
    """Tax charged on no taxable amount is not a legitimate absence.

    Scoped to the Reg. ordinario RATE-TIER boxes only. It is NOT a universal
    registry rule: regularizaciones, compensaciones, several totals, and the
    régimen simplificado (which computes from módulos, so there is no base to
    declare) all carry legitimate cuota-only boxes. The 0 % tier satisfies this
    vacuously -- its cuota is zero by definition while its base is a real
    quantity -- which is why the implication is one-directional.
    """
    resolved = _resolve(_rated_rows())
    for suffix, *_ in _TIERS:
        cuota = resolved[f"modelo-390-iva-repercutido-tipo-{suffix}-cuota"]
        base = resolved[f"modelo-390-iva-repercutido-tipo-{suffix}-base"]
        if cuota > 0:
            assert base > 0, f"tipo-{suffix} declares cuota {cuota} on base {base}"


def test_the_box_layer_is_not_exported_yet() -> None:
    """Declaring an export field before it populates would render a false nil.

    An omitted money field leaves buffer bytes; a declared one renders ``0,00``,
    which asserts a figure rather than staying silent. The flip belongs with the
    gate that refuses an inconsistent return.
    """
    revision = _m390_revision()
    box_layer = [c for c in revision.casillas if c.id.startswith("iva.anual.repercutido.tipo-")]
    assert len(box_layer) == 14
    for casilla in box_layer:
        assert not casilla.export_refs, f"{casilla.id} is exported before the refusal gate exists"


def test_no_box_layer_casilla_enters_an_annual_total_formula() -> None:
    """A box-layer cuota in the devengada total would double-count its tier.

    The tier casillas already carry these rows for the total. If a box-layer
    casilla were summed as well, every rate-recorded row would be counted twice
    and the return would over-declare.
    """
    revision = _m390_revision()
    box_layer_ids = {c.id for c in revision.casillas if c.id.startswith("iva.anual.repercutido.tipo-")}
    for formula in revision.formulas:
        referenced = {arg.casilla_id for arg in formula.expression.args if arg.casilla_id is not None}
        leaked = referenced & box_layer_ids
        assert not leaked, f"formula {formula.id} sums box-layer casillas {sorted(leaked)}"
