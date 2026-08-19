"""Modelo 390 recargo de equivalencia draws each official rate box separately.

The recargo block declared one casilla per IVA rate TIER while the official
design keys its recargo boxes by the recargo RATE, and those are not the same
axis. One reducido tier carries three recargo rates, so a 10 % supply charging
1,4 % recargo and a 7,5 % supply charging 1 % both landed in box [600] and box
[694] stayed empty. Splitting a tier's roles gives each official box its own
casilla, bound to exactly one rate.

The declared annual TOTAL was never wrong. ``iva.anual.cuota-devengada-total``
enumerates all three rate-blind recargo casillas, so every recargo euro reached
the return; what was false was the breakdown across official boxes. That is why
the repair adds a box layer instead of narrowing the tier bindings: narrowing
would fix the breakdown by deleting the rate-unrecorded rows from the total.

Those three tier casillas remain the TOTAL layer here, unchanged and still in the
devengada formula. The box layer carries no ``export_refs`` yet: the record
decomposition for this block is established separately, and a declared but
unpopulated money field renders ``0,00`` rather than a blank, which would turn a
silence into a false nil.

Real-behaviour: the committed revision through the real registry authority, rows
built by the real ``invoice_line_to_iva_observation`` bridge from operator inputs
only, resolved by the real ``ledger_iva_aggregation`` resolver. No mocks, stubs,
skips or xfail.

Non-tautology: every rung carries a distinct recargo amount, and no recargo
amount is its base multiplied by the rung's recargo rate, so a resolver that
summed the wrong rate, leaked a neighbouring rate, or returned the IVA cuota for
the recargo fails on value. The statutory IVA-to-recargo pairings are read from
LIVA art. 161 and RDL 4/2024 art. 1, not derived from the registry under test.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel

from .....core.resources import resources
from ....invoices import IvaRate
from ....iva import InvoiceKind, invoice_line_to_iva_observation
from .. import (
    DataBindingDefinition,
    IvaLedgerObservation,
    ModeloRevision,
    resolve_ledger_iva_aggregation_binding_values,
    selector_as_dict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# Recargo box suffix, the IVA rate slot statute pairs it with, a date inside that
# slot's window, base, IVA cuota, recargo cuota.
#
# The pairings are statutory, not chosen here: LIVA art. 161 fixes 5,2 % against
# the general rate, 1,4 % against art. 91.uno (10 %) and 0,5 % against art.
# 91.dos (4 %); RDL 4/2024 art. 1 fixes 0,62 % against the temporary 5 %, and
# 1 % and 0,26 % against the temporary 7,5 % and 2 %.
#
# Three rungs share the reducido tier (1,4 / 1 / 0,62) and two share the
# super-reducido tier (0,5 / 0,26). That many-to-one relation is exactly why a
# per-tier casilla cannot serve a per-rate box, and it is what this module pins.
_RUNGS = (
    ("5-2", IvaRate.RATE_21, date(2024, 3, 10), "4000.00", "817.00", "203.00"),
    ("1-4", IvaRate.RATE_10, date(2024, 3, 11), "2500.00", "241.00", "31.00"),
    ("1", IvaRate.RATE_7_5, date(2024, 11, 12), "1600.00", "127.00", "17.00"),
    ("0-62", IvaRate.RATE_5, date(2024, 8, 13), "1400.00", "73.00", "11.00"),
    ("0-5", IvaRate.RATE_4, date(2024, 3, 14), "1200.00", "51.00", "7.00"),
    ("0-26", IvaRate.RATE_2, date(2024, 11, 15), "900.00", "19.00", "3.00"),
)

# The official AEAT box each recargo rung occupies, read off the bundled 2024
# Diseno de Registros (Pag. 2 bis, apartado 5, "Recargo de equivalencia" rows)
# and confirmed against the 2025 workbook.
#
# Read from the DESCRIPTION text, where the box appears as "[NN]", never by
# searching a bare number: column 1 of those workbooks is a field sequence index
# and column 2 a byte offset, so a bare-number search returns index rows that
# read as hits.
#
# Two scoping caveats, both load-bearing. Every position in this apartado appears
# twice, once under Reg. ordinario and once under Recargo de equivalencia, so
# these are segment-resolved rather than matched on offset alone. And the
# identities are DESIGN-YEAR-SCOPED: AEAT re-laid this record repeatedly inside
# the single revision these casillas belong to, and one byte offset can carry
# several different official boxes across its span. These numbers are asserted
# for the 2024/2025 designs, not as a claim about every year the revision spans.
_OFFICIAL_BOX_NUMBER = {
    "iva.anual.repercutido.recargo.tipo-5-2.cuota": "602",
    "iva.anual.repercutido.recargo.tipo-1-4.cuota": "600",
    "iva.anual.repercutido.recargo.tipo-1.cuota": "694",
    "iva.anual.repercutido.recargo.tipo-0-62.cuota": "666",
    "iva.anual.repercutido.recargo.tipo-0-5.cuota": "36",
    "iva.anual.repercutido.recargo.tipo-0-26.cuota": "692",
}

# A reducido row carrying recargo whose IVA rate the ledger never captured.
_UNRATED_RECARGO = Decimal("29.00")
_UNRATED_BASE = Decimal("330.00")
_UNRATED_CUOTA = Decimal("33.00")


def _axis_sequence(axes: Mapping[str, object], key: str) -> tuple[object, ...]:
    """Return a selector's sequence axis as a hashable tuple, absent or not.

    An absent axis and an empty one are the same grouping identity here: both
    mean "this binding does not narrow on that axis".
    """
    value = axes.get(key)
    return tuple(value) if isinstance(value, (list, tuple)) else ()


#: Modelo 390's four exact-year revisions, after the revision-span split.
_M390_REVISION_IDS: tuple[str, ...] = ("2022", "2023", "2024", "2025")


def _m390_revision(filing_year: str | int = 2024) -> ModeloRevision:
    """Resolve one filing year's revision through the law-determined selector."""
    return resources().modelos.authority.snapshot("390", filing_year=int(filing_year), period="0A").revision


def _rated_rows() -> tuple[IvaLedgerObservation, ...]:
    """Rows built the way production builds them, from operator inputs only.

    Only a rate slot, a date and three amounts are supplied. The classification
    triple the selectors match on -- category, tier and applied rate -- is derived
    by the bridge, so a box reachable only from a hand-built fixture fails here.
    """
    return tuple(
        invoice_line_to_iva_observation(
            invoice_id=f"inv-m390-recargo-{suffix}",
            issued_at=on,
            invoice_kind=InvoiceKind.ISSUED,
            iva_rate=slot,
            base_amount=Decimal(base),
            iva_amount=Decimal(cuota),
            deduction_fact_kind=None,
            deduction_provenance=None,
            recargo_amount=Decimal(recargo),
        )
        for suffix, slot, on, base, cuota, recargo in _RUNGS
    )


def _unrated_row() -> IvaLedgerObservation:
    """A reducido row carrying recargo whose ``applied_rate`` is unknown.

    Built directly rather than through the bridge on purpose: the bridge derives
    a rate from the slot, so it cannot produce the rate-less shape. This is the
    shape a pre-classified or historic ledger row has, and the one the whole
    split exists to keep inside the total.
    """
    rated = _rated_rows()[1]
    return rated.model_copy(
        update={
            "ledger_id": "inv-m390-recargo-unrated",
            "transaction_date": date(2024, 6, 1),
            "applied_rate": None,
            "base_amount": _UNRATED_BASE,
            "iva_amount": _UNRATED_CUOTA,
            "recargo_amount": _UNRATED_RECARGO,
        },
    )


def _resolve(rows: tuple[IvaLedgerObservation, ...]) -> dict[str, Decimal]:
    return dict(resolve_ledger_iva_aggregation_binding_values(_m390_revision(), rows))


@pytest.mark.parametrize(("suffix", "recargo"), tuple((r[0], r[5]) for r in _RUNGS))
def test_each_recargo_box_draws_only_its_own_rate(suffix: str, recargo: str) -> None:
    """Each official recargo box resolves to its own rate's cuota, not its tier's."""
    resolved = _resolve(_rated_rows())
    assert resolved[f"modelo-390-iva-recargo-equivalencia-tipo-{suffix}-cuota"] == Decimal(recargo)


def test_the_reducido_tier_merge_is_separated() -> None:
    """The three reducido-tier recargo rates that merged into one box now land in three.

    Before the split every reducido row reached ``recargo.reducido`` and, through
    it, box [600] alone -- so a 7,5 % supply's 1 % recargo was declared as 1,4 %
    while [694] and [666] stayed empty.
    """
    resolved = _resolve(_rated_rows())
    assert resolved["modelo-390-iva-recargo-equivalencia-tipo-1-4-cuota"] == Decimal("31.00")
    assert resolved["modelo-390-iva-recargo-equivalencia-tipo-1-cuota"] == Decimal("17.00")
    assert resolved["modelo-390-iva-recargo-equivalencia-tipo-0-62-cuota"] == Decimal("11.00")
    # The rate-blind tier casilla still carries all three, because it feeds the total.
    assert resolved["modelo-390-iva-recargo-equivalencia-reducido-cuota"] == Decimal("59.00")


def test_the_super_reducido_tier_merge_is_separated() -> None:
    """The second merged tier: 0,5 % and 0,26 % shared one casilla and one box."""
    resolved = _resolve(_rated_rows())
    assert resolved["modelo-390-iva-recargo-equivalencia-tipo-0-5-cuota"] == Decimal("7.00")
    assert resolved["modelo-390-iva-recargo-equivalencia-tipo-0-26-cuota"] == Decimal("3.00")
    assert resolved["modelo-390-iva-recargo-equivalencia-super-reducido-cuota"] == Decimal("10.00")


def test_a_windowed_recargo_rate_resolves_inside_its_window() -> None:
    """The transitional rungs must be reachable, not merely declared.

    0,62 % applies 1 Jul - 30 Sep 2024 and 1 % and 0,26 % from 1 Oct (RDL 4/2024
    art. 1). A binding that could never resolve non-zero would be dormant
    capacity, and a fixture confined to one quarter would miss it.
    """
    resolved = _resolve(_rated_rows())
    for suffix in ("1", "0-62", "0-26"):
        assert resolved[f"modelo-390-iva-recargo-equivalencia-tipo-{suffix}-cuota"] > 0


def test_no_recargo_box_claims_the_rate_unrecorded_row() -> None:
    """A row whose IVA rate is unknown must not be asserted into a rate-specific box.

    Its recargo cuota is real money, but nothing in the evidence says which rate
    was charged, and placing it in box [600] would assert a rate the operator
    never stated.
    """
    resolved = _resolve((*_rated_rows(), _unrated_row()))
    for suffix, *_ in _RUNGS:
        cuota = resolved[f"modelo-390-iva-recargo-equivalencia-tipo-{suffix}-cuota"]
        assert cuota != _UNRATED_RECARGO, f"tipo-{suffix} absorbed the rate-unrecorded recargo"
    assert resolved["modelo-390-iva-recargo-equivalencia-tipo-1-4-cuota"] == Decimal("31.00")


def test_the_rate_blind_total_layer_retains_the_unrated_recargo() -> None:
    """The control the whole split rests on: unrated recargo stays in the total.

    The rate boxes deliberately exclude it, so the rate-blind tier casilla is the
    only thing keeping it in ``iva.anual.cuota-devengada-total``. If a later
    change narrows that binding, this money reaches no casilla at all and leaves
    the declared annual total silently.
    """
    without = _resolve(_rated_rows())["modelo-390-iva-recargo-equivalencia-reducido-cuota"]
    with_unrated = _resolve((*_rated_rows(), _unrated_row()))["modelo-390-iva-recargo-equivalencia-reducido-cuota"]
    assert with_unrated - without == _UNRATED_RECARGO


def test_every_rate_split_recargo_group_carries_exactly_one_rate_blind_binding() -> None:
    """Gate the property, not the rung list: a rate-split recargo group needs a total layer.

    Derived from the revision rather than from a fixture list, so a rung added
    later without a blind sibling fails here instead of passing vacuously. That
    is the one shape that loses money silently, and it is invisible to a per-rung
    test enumerating only the rungs someone remembered.

    Scoped to ``recargo_amount_sum``. It passes today partly by ABSENCE: the 0 %
    recargo rung (boxes [663]/[664]) is deliberately not declared, because the
    recargo block has no rate-blind ZERO tier binding to sit behind it. Adding one
    means adding a term to the annual devengada total formula, which is a change
    to a money-bearing total and a decision of its own. Declaring the 0 % box
    without that change would red this assertion, which is the intended outcome.
    """
    revision = _m390_revision()
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for binding in revision.bindings:
        if str(binding.source) != "ledger_iva_aggregation":
            continue
        axes = selector_as_dict(binding)
        if axes.get("fact") != "recargo_amount_sum":
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
            f"selector identity {key} declares {len(rated)} rate-specific recargo binding(s) "
            f"and {len(blind)} rate-blind sibling(s); a rate-split group needs exactly one "
            f"total layer or a rate-unrecorded recargo row reaches nothing"
        )


def test_every_recargo_box_casilla_states_its_official_box_number() -> None:
    """Each recargo box casilla names its AEAT number rather than implying it by position.

    The recargo segment repeats every offset the Reg. ordinario segment uses, so
    a consumer matching on offset alone would land on the ordinario twin while
    looking conclusive. Stating the number keeps the correspondence readable.
    """
    casillas = {casilla.id: casilla for casilla in _m390_revision().casillas}
    for casilla_id, number in _OFFICIAL_BOX_NUMBER.items():
        assert casilla_id in casillas, f"{casilla_id} is not declared by the revision"
        assert casillas[casilla_id].number == number, (
            f"{casilla_id} claims box {casillas[casilla_id].number}, official design says {number}"
        )


def test_no_recargo_box_casilla_enters_an_annual_total_formula() -> None:
    """A recargo box casilla in the devengada total would double-count its tier.

    The three tier casillas already carry these rows for the total. Summing a box
    casilla as well would count every rate-recorded recargo euro twice and make
    the return OVER-declare -- the opposite error from the one being fixed, and
    the only way this repair could damage a figure that is currently correct.
    """
    revision = _m390_revision()
    box_ids = set(_OFFICIAL_BOX_NUMBER)
    for formula in revision.formulas:
        referenced = {arg.casilla_id for arg in formula.expression.args if arg.casilla_id is not None}
        leaked = referenced & box_ids
        assert not leaked, f"formula {formula.id} sums recargo box casillas {sorted(leaked)}"


def test_the_rate_blind_recargo_casillas_still_feed_the_devengada_total() -> None:
    """The total layer must stay wired, or the split becomes the narrowing it replaces.

    This is the assertion that distinguishes "breakdown repaired, total intact"
    from "breakdown repaired, total silently reduced". It reads the formula rather
    than the resolver, so removing a tier casilla from the sum fails here even
    when every rung still resolves correctly.
    """
    revision = _m390_revision()
    total = next(f for f in revision.formulas if f.id == "modelo-390-iva-anual-cuota-devengada-total")
    referenced = {arg.casilla_id for arg in total.expression.args if arg.casilla_id is not None}
    for tier in ("general", "reducido", "super-reducido"):
        casilla_id = f"iva.anual.repercutido.recargo.{tier}"
        assert casilla_id in referenced, f"{casilla_id} left the annual devengada total"


def test_no_recargo_rate_box_exports_without_something_to_populate_it() -> None:
    """A recargo rate box may export only once something computes its figure.

    The hazard is precise: an export reference on a box that nothing populates
    renders an empty money field as ``0,00``, which turns a silence into a false
    nil -- a filer who owes recargo reads a declared zero. That is why this
    originally asserted the whole box layer exports NOTHING: the layer landed
    inert while the recargo decomposition was established separately.

    The layer is no longer inert. All six boxes now carry a ledger binding, and
    the three AEAT prints on "Pag. 2 bis" -- the sheet the 2024 diseno added --
    export to their own official positions. Keeping the blanket refusal would now
    assert the ABSENCE of shipped, grounded behaviour.

    So the guard is narrowed to the hazard rather than dropped, and it is the
    binding, not the export, that is the precondition: an exporting box with no
    binding and no formula still fails here. Measured across all four revisions,
    nothing currently trips it (2022 exports 0 of 6, 2023 one, 2024 and 2025
    three each, every one of them bound), so this discards no live finding.
    """
    for revision_id in _M390_REVISION_IDS:
        casillas = {casilla.id: casilla for casilla in _m390_revision(revision_id).casillas}
        for casilla_id in _OFFICIAL_BOX_NUMBER:
            casilla = casillas.get(casilla_id)
            if casilla is None or not casilla.export_refs:
                continue
            assert casilla.binding is not None or casilla.formula is not None, (
                f"{casilla_id} exports in revision {revision_id} while nothing populates it, "
                "so an empty field would render as a false 0,00"
            )


def _with_applied_rates(
    binding_id: str,
    applied_rates: tuple[Decimal, ...] | None,
) -> ModeloRevision:
    """Return the real revision with one binding's ``applied_rates`` axis replaced.

    The mutation is applied to the loaded revision and re-resolved through the
    real resolver, so it proves a property of the shipped selector logic rather
    than of a re-implementation of it.
    """
    revision = _m390_revision()

    def _rated(binding: DataBindingDefinition) -> DataBindingDefinition:
        selector = binding.selector
        assert isinstance(selector, BaseModel), f"{binding.id} carries an untyped selector; nothing to mutate"
        return binding.model_copy(update={"selector": selector.model_copy(update={"applied_rates": applied_rates})})

    mutated = tuple(_rated(binding) if binding.id == binding_id else binding for binding in revision.bindings)
    return revision.model_copy(update={"bindings": mutated})


def test_mutation_widening_a_recargo_box_binding_re_creates_the_tier_merge() -> None:
    """Mutation one: clearing a box's rate axis restores the defect being fixed.

    Dropping ``applied_rates`` from the 1,4 % box makes it swallow every reducido
    row -- the 1 %, the 0,62 % and the rate-unrecorded one -- so box [600]
    overstates exactly as it did before the split. This reddens
    ``test_each_recargo_box_draws_only_its_own_rate``.
    """
    rows = (*_rated_rows(), _unrated_row())
    mutated = _with_applied_rates("modelo-390-iva-recargo-equivalencia-tipo-1-4-cuota", None)
    widened = dict(resolve_ledger_iva_aggregation_binding_values(mutated, rows))[
        "modelo-390-iva-recargo-equivalencia-tipo-1-4-cuota"
    ]
    assert widened != Decimal("31.00"), "the mutation changed nothing; the rate axis is not load-bearing"
    assert widened == Decimal("31.00") + Decimal("17.00") + Decimal("11.00") + _UNRATED_RECARGO


def test_mutation_narrowing_the_total_binding_deletes_the_unrecorded_recargo() -> None:
    """Mutation two: narrowing the total layer deletes money from the return.

    This is why the repair is a split rather than a narrowing. Giving the
    rate-blind reducido recargo binding an ``applied_rates`` axis makes it drop
    the row whose rate was never recorded, and that money reaches no other
    casilla -- it leaves the annual devengada total. This reddens
    ``test_the_rate_blind_total_layer_retains_the_unrated_recargo``.
    """
    rows = (*_rated_rows(), _unrated_row())
    intact = _resolve(rows)["modelo-390-iva-recargo-equivalencia-reducido-cuota"]
    mutated = _with_applied_rates(
        "modelo-390-iva-recargo-equivalencia-reducido-cuota",
        (Decimal("0.10"), Decimal("0.075"), Decimal("0.05")),
    )
    narrowed = dict(resolve_ledger_iva_aggregation_binding_values(mutated, rows))[
        "modelo-390-iva-recargo-equivalencia-reducido-cuota"
    ]
    assert narrowed == intact - _UNRATED_RECARGO
    assert narrowed < intact, "the narrowing dropped nothing; the fixture would prove nothing"


def test_no_recargo_amount_is_derivable_from_its_base_by_its_rate() -> None:
    """The anti-tautology guard for every amount above.

    If a fixture's recargo were its base times the rung's statutory rate, a
    resolver that recomputed the recargo instead of reading the ledger figure
    would pass every assertion in this module. Each amount is deliberately not
    that product, so the tests measure what the ledger recorded.
    """
    statutory = {
        "5-2": Decimal("0.052"),
        "1-4": Decimal("0.014"),
        "1": Decimal("0.01"),
        "0-62": Decimal("0.0062"),
        "0-5": Decimal("0.005"),
        "0-26": Decimal("0.0026"),
    }
    for suffix, _slot, _on, base, _cuota, recargo in _RUNGS:
        assert Decimal(recargo) != Decimal(base) * statutory[suffix], (
            f"tipo-{suffix} recargo {recargo} equals base x rate; the fixture is tautological"
        )
