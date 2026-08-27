"""Modelo 390 rate-specific box layer draws each official rate box separately.

The annual resumen exported one rate-blind casilla per tier to a rate-specific
AEAT box, so a 10 % and a 7,5 % sale merged into box [04] while [670] stayed
empty. Splitting a tier's roles gives each official box its own casilla, bound
to exactly one rate.

This layer now owns the official boxes: all fourteen carry ``export_refs`` and
the rate-blind tier casillas carry none, so no casilla both totals and asserts a
rate. That flip was safe only alongside the gate refusing a return whose rate
boxes sum below its declared total, because a declared-but-unpopulated money
field renders ``0,00`` rather than a blank, turning a silence into a false nil.

What this module pins is the RESOLUTION -- which rows reach which casilla. The
byte positions those casillas then occupy are pinned separately, against the
Diseño de Registro, in the filing suite's rate-box offset tests.

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

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel

from ....iva import IvaCategory, IvaFlowDirection, IvaLedgerObservationRole, IvaRateKind
from ..authority import bundled_authority
from ..binding_selector_utils import selector_as_dict
from ..ledger_bindings import IvaLedgerObservation, resolve_ledger_iva_aggregation_binding_values
from ..schema import DataBindingDefinition, ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _axis_sequence(axes: Mapping[str, object], key: str) -> tuple[object, ...]:
    """Return a selector's sequence axis as a hashable tuple, absent or not.

    A selector axis is ``object`` once the mapping is read generically, and an
    absent axis and an empty one are the same grouping identity here -- both
    mean "this binding does not narrow on that axis".
    """
    value = axes.get(key)
    return tuple(value) if isinstance(value, (list, tuple)) else ()


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
    return bundled_authority().snapshot("390", filing_year=2024, period="0A").revision


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
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
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


def _unrated_zero_row() -> IvaLedgerObservation:
    """A zero-tier row whose rate the ledger never captured."""
    return _observation(
        category=IvaCategory.DOMESTIC_ZERO,
        rate_kind=IvaRateKind.ZERO,
        on=date(2024, 6, 2),
        base=_UNRATED_BASE,
        cuota=Decimal("0.00"),
        applied_rate=None,
    )


def test_the_zero_tier_retains_a_rate_unrecorded_row() -> None:
    """The zero tier had no blind layer at all, so such a row reached NOTHING.

    Its two bindings both pinned ``applied_rates = 0.00``, so a zero-rated row
    with no recorded rate matched neither and its base imponible left the return
    silently. No cuota was lost -- a zero-rated supply's cuota is zero -- but the
    base is a declared figure AEAT reconciles.

    The reducido tier is the control: an identical rate-unrecorded row has always
    been retained there, so a failure here is the zero tier specifically rather
    than the resolver dropping unrated rows generally.
    """
    without = _resolve(_rated_rows())
    with_unrated = _resolve((*_rated_rows(), _unrated_zero_row()))
    zero_total = "modelo-390-iva-repercutido-zero-base"
    assert with_unrated[zero_total] - without[zero_total] == _UNRATED_BASE

    control_without = _resolve(_rated_rows())["modelo-390-iva-repercutido-reducido-base"]
    control_with = _resolve((*_rated_rows(), _unrated_row()))["modelo-390-iva-repercutido-reducido-base"]
    assert control_with - control_without == _UNRATED_BASE


def test_every_rate_split_base_tier_carries_exactly_one_rate_blind_binding() -> None:
    """Gate the property, not the tier list: a rate-split base tier needs a total layer.

    The zero tier shipped with rate boxes and no blind sibling, which is the one
    shape that loses money silently -- and it is invisible to a per-tier test
    that only enumerates the tiers someone remembered. Derived from the revision
    so a tier added later without a blind layer fails here rather than passing
    vacuously.

    Scoped to ``base_amount_sum``. The cuota axis is NOT asserted here, and the
    exclusion is a real limit rather than a convenience: the zero tier has no
    blind cuota sibling either, so a rate-unrecorded zero row carrying a non-zero
    cuota still drops that cuota. Closing it means adding a term to the annual
    devengada total formula for a figure that is zero whenever the row is
    self-consistent, which is a change to a money-bearing total and a decision in
    its own right. Widening this assertion to every fact without making that
    change would only red the suite; it is tracked separately instead.
    """
    revision = _m390_revision()
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for binding in revision.bindings:
        if str(binding.source) != "ledger_iva_aggregation":
            continue
        axes = selector_as_dict(binding)
        if axes.get("fact") != "base_amount_sum":
            continue
        key = (
            _axis_sequence(axes, "categories"),
            _axis_sequence(axes, "rate_kinds"),
            axes.get("flow_direction"),
        )
        grouped.setdefault(key, []).append(axes)

    for key, members in grouped.items():
        rated = [axes for axes in members if axes.get("applied_rates")]
        blind = [axes for axes in members if not axes.get("applied_rates")]
        if not rated:
            continue
        assert len(blind) == 1, (
            f"selector identity {key} declares {len(rated)} rate-specific binding(s) and "
            f"{len(blind)} rate-blind sibling(s); a rate-split tier needs exactly one "
            f"total layer or a rate-unrecorded row reaches nothing"
        )


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


def test_the_box_layer_exports_and_the_total_layer_does_not() -> None:
    """Exactly one layer reaches the record, and it is the rate-specific one.

    The split's whole point: a casilla may total OR assert a rate, never both.
    The box layer owns the official boxes because each admits exactly one rate;
    the tier casillas stay silent in the record because a tier figure written to
    a rate box declares a rate the taxpayer's rows do not all carry.

    Both directions are asserted. Dropping a box casilla's ``export_refs`` would
    delete that rate's money from the fichero; restoring a tier casilla's would
    reinstate the merged mis-declaration this layer exists to end.
    """
    revision = _m390_revision()
    box_layer = [c for c in revision.casillas if c.id.startswith("iva.anual.repercutido.tipo-")]
    assert len(box_layer) == 14
    for casilla in box_layer:
        assert casilla.export_refs, f"{casilla.id} reaches no official box"
    for tier in ("general", "reducido", "super-reducido"):
        for suffix in ("", ".base"):
            total = next(c for c in revision.casillas if c.id == f"iva.anual.repercutido.{tier}{suffix}")
            assert not total.export_refs, f"{total.id} both totals and asserts a rate"


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


# The official AEAT box each rate casilla occupies, read off the bundled 2024
# Diseno de Registros, apartado 5, "Reg. ordin." rows. The Recargo de
# equivalencia segment carries its own twins ([663]/[664], [691]/[692], [35]/[36])
# at the same record positions, so these numbers are segment-resolved rather than
# matched on offset alone.
_OFFICIAL_BOX_NUMBER = {
    "iva.anual.repercutido.tipo-21.base": "05",
    "iva.anual.repercutido.tipo-21.cuota": "06",
    "iva.anual.repercutido.tipo-10.base": "03",
    "iva.anual.repercutido.tipo-10.cuota": "04",
    "iva.anual.repercutido.tipo-7-5.base": "669",
    "iva.anual.repercutido.tipo-7-5.cuota": "670",
    "iva.anual.repercutido.tipo-5.base": "702",
    "iva.anual.repercutido.tipo-5.cuota": "703",
    "iva.anual.repercutido.tipo-4.base": "01",
    "iva.anual.repercutido.tipo-4.cuota": "02",
    "iva.anual.repercutido.tipo-2.base": "667",
    "iva.anual.repercutido.tipo-2.cuota": "668",
    "iva.anual.repercutido.tipo-0.base": "700",
    "iva.anual.repercutido.tipo-0.cuota": "701",
}


def _with_applied_rates(
    binding_id: str,
    applied_rates: tuple[Decimal, ...] | None,
) -> ModeloRevision:
    """Return the real revision with one binding's ``applied_rates`` axis replaced.

    The mutation is applied to the loaded revision and re-resolved through the
    real resolver, so what it proves is a property of the shipped selector logic
    rather than of a re-implementation of it.
    """
    revision = _m390_revision()

    def _rated(binding: DataBindingDefinition) -> DataBindingDefinition:
        selector = binding.selector
        # A selector compiles to either a typed model or a raw mapping. This
        # mutation only means anything against the typed form, so the raw one
        # is refused by name rather than reaching `model_copy` and failing with
        # an attribute error that says nothing about why.
        assert isinstance(selector, BaseModel), f"{binding.id} carries an untyped selector; nothing to mutate"
        return binding.model_copy(update={"selector": selector.model_copy(update={"applied_rates": applied_rates})})

    mutated = tuple(_rated(binding) if binding.id == binding_id else binding for binding in revision.bindings)
    return revision.model_copy(update={"bindings": mutated})


def test_every_box_layer_casilla_states_its_official_box_number() -> None:
    """Each box casilla names its AEAT number rather than implying it by position.

    Modelo 390 addresses its slots by semantic id while the record design
    addresses them by box number, and the two vocabularies do not intersect at
    all. Stating the number keeps the correspondence readable instead of
    requiring a later consumer to re-derive it from an export offset and then
    disambiguate which régimen segment the record belongs to.
    """
    casillas = {casilla.id: casilla for casilla in _m390_revision().casillas}
    for casilla_id, number in _OFFICIAL_BOX_NUMBER.items():
        assert casilla_id in casillas, f"{casilla_id} is not declared by the revision"
        assert casillas[casilla_id].number == number, (
            f"{casilla_id} claims box {casillas[casilla_id].number}, official design says {number}"
        )


def test_rate_blind_base_casillas_claim_no_rate_specific_box_number() -> None:
    """A rate-blind casilla must not claim a rate-specific box as its identity.

    The three repercutido base casillas once carried 05/03/01 while binding
    rate-blindly. That asserted a false identity and collided head-on with the
    box-layer casillas that legitimately own those numbers.

    ``iva.anual.soportado.interiores.base`` deliberately KEEPS number 48. Box 48
    is "Total oper. inter. corrientes bienes y servic. - Base imponible", a
    genuine TOTAL box, so a rate-blind binding is exactly what it asks for. The
    rule is that the number follows the box's own semantics, not that a
    rate-blind casilla never carries a number.
    """
    casillas = {casilla.id: casilla for casilla in _m390_revision().casillas}
    rate_specific = set(_OFFICIAL_BOX_NUMBER.values())
    for casilla_id in (
        "iva.anual.repercutido.general.base",
        "iva.anual.repercutido.reducido.base",
        "iva.anual.repercutido.super-reducido.base",
        "iva.anual.repercutido.zero.base",
    ):
        assert casillas[casilla_id].number not in rate_specific, (
            f"{casilla_id} is rate-blind but claims rate-specific box {casillas[casilla_id].number}"
        )
    assert casillas["iva.anual.soportado.interiores.base"].number == "48"


def test_mutation_widening_a_box_binding_re_creates_the_tier_merge() -> None:
    """Mutation one: clearing a box's rate axis restores the defect being fixed.

    Dropping ``applied_rates`` from the 10 % cuota box makes it swallow every
    reducido row - the 7,5 %, the 5 % and the rate-unrecorded one - so box [04]
    overstates exactly as it did before the split. This reddens
    ``test_each_rate_box_draws_only_its_own_rate``.
    """
    rows = (*_rated_rows(), _unrated_row())
    mutated = _with_applied_rates("modelo-390-iva-repercutido-tipo-10-cuota", None)
    widened = dict(resolve_ledger_iva_aggregation_binding_values(mutated, rows))[
        "modelo-390-iva-repercutido-tipo-10-cuota"
    ]
    assert widened != Decimal("250.00"), "the mutation changed nothing; the rate axis is not load-bearing"
    assert widened == Decimal("250.00") + Decimal("120.00") + Decimal("70.00") + _UNRATED_CUOTA


def test_mutation_narrowing_the_total_binding_deletes_the_unrecorded_row() -> None:
    """Mutation two: narrowing the total layer deletes money from the return.

    This is why the repair is a split rather than a narrowing. Giving the
    rate-blind reducido cuota binding an ``applied_rates`` axis makes it drop the
    row whose rate was never recorded, and that money reaches no other casilla -
    it leaves the annual devengada total. This reddens
    ``test_the_rate_blind_total_layer_retains_the_unrated_row``.
    """
    rows = (*_rated_rows(), _unrated_row())
    intact = _resolve(rows)["modelo-390-iva-repercutido-reducido-cuota"]
    mutated = _with_applied_rates(
        "modelo-390-iva-repercutido-reducido-cuota",
        (Decimal("0.10"), Decimal("0.075"), Decimal("0.05")),
    )
    narrowed = dict(resolve_ledger_iva_aggregation_binding_values(mutated, rows))[
        "modelo-390-iva-repercutido-reducido-cuota"
    ]
    assert narrowed == intact - _UNRATED_CUOTA
    assert narrowed < intact, "the narrowing dropped nothing; the fixture would prove nothing"
