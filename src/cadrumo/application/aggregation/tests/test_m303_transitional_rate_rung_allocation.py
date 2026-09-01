"""Modelo 303's régimen-general devengado rungs place a row by RATE, not by tier.

The block is six base/Tipo%/cuota triplets and AEAT fixes each rung's rate
itself: every Tipo % field in the diseño de registro is a ``Constante``. Three
rungs carry the ordinary tier rates ([01]/[03] at 4 %, [04]/[06] at 10 %,
[07]/[09] at 21 %) and two carry the RD-ley 4/2024 transitional food rates
([153]/[155] at 5 %, then 7,5 % from period 10/4T 2024 per Nota 8; [165]/[167]
at 2 % per Nota 10). The transitional rates COEXIST with their tier's ordinary
rate rather than replacing it, so a tier-keyed binding cannot place a row: a
7,5 % sale and a 10 % sale share the reduced tier and were both landing on
[04]/[06].

That merge published a rate the line never carried, and it is arithmetically
detectable from the filed record alone -- AEAT can check base x tipo against
cuota per rung, and a merged rung admits no tipo that satisfies it.

Real-behaviour: real :class:`Transaction` rows through the real
``aggregate_iva_ledger_observations`` classifier and the real
``ledger_iva_aggregation`` resolver, against the committed revision loaded
through the real registry authority. Nothing is stubbed, and in particular
``applied_rate`` is DECIDED by the classifier from the row's ``iva_rate``
rather than set here -- which is the field the whole allocation turns on.

Non-tautology: every rung carries a distinct base and a distinct cuota, and no
cuota equals another rung's base or is reachable from a neighbouring rung's
rate, so a resolver that leaked one rung into another, summed the wrong rate, or
returned base for cuota fails on value rather than on shape. The two windowed
rates are exercised on dates where they were actually in force.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.binding_selector_utils import selector_as_dict
from ....domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.iva.flow import IvaFlowDirection
from ....domain.iva.lookup import rate_kinds_for_declared_rate
from ....domain.iva.schema import EUMemberState, IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .._iva_ledger import resolve_iva_ledger_binding_values
from .iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# Each rung: its two binding ids, the rate a row must carry to reach it, a date
# on which that rate was in force, and a distinct base/cuota pair. 5 % applies
# before 10/4T 2024 and 7,5 % from it (Nota 8), 2 % from 10/4T 2024 (Nota 10).
_RUNGS = (
    ("general", "0.21", date(2024, 11, 4), "4000.00", "840.00"),
    ("reducido", "0.10", date(2024, 11, 5), "2500.00", "250.00"),
    ("reducido-transitorio", "0.075", date(2024, 11, 6), "1600.00", "120.00"),
    ("super-reducido", "0.04", date(2024, 11, 7), "1200.00", "48.00"),
    ("super-reducido-transitorio", "0.02", date(2024, 11, 8), "900.00", "18.00"),
)

# The 5 % half of the [153] rung, exercised in its own window (period 09/3T
# 2024, before Nota 8 flips the mandated constant to 7,5 %). It must reach the
# SAME rung -- AEAT reuses one rung across the flip rather than opening a
# second, so the rung admits both rates and the two never coexist in a period.
_EARLIER_WINDOW = date(2024, 9, 10)

_PERIOD_4T_2024 = Period.from_year_and_code(2024, "4T")
_PERIOD_3T_2024 = Period.from_year_and_code(2024, "3T")


def _revision() -> ModeloRevision:
    return bundled_authority().snapshot(Modelo.M303, filing_year=2024, period="4T").revision


def _transaction(
    row_id: str,
    *,
    on_date: date,
    taxable_base: Decimal,
    iva_rate: Decimal | None,
    iva_amount: Decimal,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=row_id,
                booked_date=on_date,
                value_date=on_date,
                amount=taxable_base + iva_amount,
                currency="EUR",
                counterparty="Cliente",
                description=f"venta {row_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="c" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(2024, 12, 1, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "ledger_transaction"},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": None,
            "exemption_article": None,
            "art_104_tres_exclusion": None,
            "prorrata_reference": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "fx_rate": None,
            "value_in_eur": None,
            "classified_at": datetime(2024, 12, 2, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _resolve(transactions: tuple[Transaction, ...], *, period: Period) -> dict[str, Decimal]:
    catalogue = TransactionCatalogue.model_validate(
        {"transactions": {t.transaction_id: t for t in transactions}},
    )
    aggregation = aggregate_iva_ledger_observations(catalogue, period=period)
    assert aggregation.issues == (), f"classifier refused a row: {aggregation.issues}"
    return {str(k): v for k, v in resolve_iva_ledger_binding_values(_revision(), aggregation.observations).items()}


def _all_rungs_catalogue() -> tuple[Transaction, ...]:
    return tuple(
        _transaction(
            f"row-{suffix}",
            on_date=on_date,
            taxable_base=Decimal(base),
            iva_rate=Decimal(rate),
            iva_amount=Decimal(cuota),
        )
        for suffix, rate, on_date, base, cuota in _RUNGS
    )


def test_each_rate_reaches_its_own_rung_and_no_other() -> None:
    """One row per rate, all in one period: each rung gets exactly its own row.

    This is the finding's direct inverse. Before the split, the 7,5 % row landed
    on the reducido rung's bindings and the 2 % row on the super-reducido rung's,
    so those two rungs held a sum of two rows and the transitional rungs held
    nothing.
    """
    values = _resolve(_all_rungs_catalogue(), period=_PERIOD_4T_2024)

    for suffix, _rate, _on_date, base, cuota in _RUNGS:
        assert values[f"modelo-303-iva-repercutido-{suffix}-base"] == Decimal(base)
        assert values[f"modelo-303-iva-repercutido-{suffix}-cuota"] == Decimal(cuota)


def test_the_five_percent_half_reaches_the_same_rung_as_seven_and_a_half() -> None:
    """Nota 8 reuses [153] across the flip, so the rung admits both its rates.

    A revision split per AEAT design would not separate these: the flip happens
    INSIDE the 2024-late design, at the 10/4T 2024 period boundary.
    """
    row = _transaction(
        "row-5pct",
        on_date=_EARLIER_WINDOW,
        taxable_base=Decimal("1400.00"),
        iva_rate=Decimal("0.05"),
        iva_amount=Decimal("70.00"),
    )
    values = _resolve((row,), period=_PERIOD_3T_2024)

    assert values["modelo-303-iva-repercutido-reducido-transitorio-base"] == Decimal("1400.00")
    assert values["modelo-303-iva-repercutido-reducido-transitorio-cuota"] == Decimal("70.00")
    # And it must NOT also land on the ordinary 10 % rung, which is the merge.
    assert values["modelo-303-iva-repercutido-reducido-base"] == Decimal("0")
    assert values["modelo-303-iva-repercutido-reducido-cuota"] == Decimal("0")


def test_the_rung_split_neither_loses_nor_duplicates_a_row() -> None:
    """Narrowing a tier binding is only safe if its siblings cover the remainder.

    Modelo 390 could add rate-specific boxes beside rate-blind tier bindings
    because its annual total draws from the rate-blind ones. Modelo 303 has no
    such box -- these bindings ARE the inputs to total cuota devengada [27] --
    so the tier bindings had to be narrowed, and a rate that fell between the
    narrowed sets would leave the return silently.
    """
    values = _resolve(_all_rungs_catalogue(), period=_PERIOD_4T_2024)

    declared_cuota = sum(
        (values[f"modelo-303-iva-repercutido-{suffix}-cuota"] for suffix, *_ in _RUNGS),
        Decimal("0"),
    )
    charged_cuota = sum((Decimal(cuota) for *_, cuota in _RUNGS), Decimal("0"))
    assert declared_cuota == charged_cuota

    declared_base = sum(
        (values[f"modelo-303-iva-repercutido-{suffix}-base"] for suffix, *_ in _RUNGS),
        Decimal("0"),
    )
    charged_base = sum((Decimal(base) for *_, base, _cuota in _RUNGS), Decimal("0"))
    assert declared_base == charged_base


def test_every_rung_cuota_carrier_reaches_total_cuota_devengada() -> None:
    """A rung placed correctly still under-declares if [27] does not enumerate it.

    The rungs' cuota bindings write semantic carriers, and casilla [27] sums
    those carriers -- the diseño's own printed formula for [27] lists every
    rung's cuota box. Splitting a rate onto a new carrier and leaving the total
    alone would move the cuota off the return entirely, which is the failure
    narrowing a binding invites. Derived from the registry both sides, so a
    future rung that is bound but not totalled reds this rather than shipping.
    """
    revision = _revision()
    carriers = {
        str(c.binding): c.id
        for c in revision.casillas
        if c.binding is not None and str(c.binding).startswith("modelo-303-iva-repercutido-")
    }
    rung_carriers = {casilla_id for binding_id, casilla_id in carriers.items() if binding_id.endswith("-cuota")}
    assert rung_carriers, "no rung cuota carrier found -- the probe proves nothing"

    total = next(f for f in revision.formulas if f.target_casilla_id == "iva.cuota-devengada-total")
    summed = {str(arg.casilla_id) for arg in total.expression.args if arg.casilla_id is not None}

    assert rung_carriers <= summed, (
        f"rung cuota carriers missing from total cuota devengada: {sorted(rung_carriers - summed)}"
    )


def test_the_narrowed_rate_sets_are_exhaustive_against_the_rate_table() -> None:
    """No domestic rate the registry admits may fall outside the rungs.

    The safety of narrowing rests on this and not on the rate list being
    plausible: whatever rates the table declares for a tier on a given date, the
    rungs' union must cover them, or a row carrying the uncovered rate reaches no
    casilla at all. Derived from the registry rather than restated, so adding a
    rate to the table without giving it a rung reds this.
    """
    revision = _revision()
    # ``None`` is the rate-blind marker -- that tier's rung covers everything it
    # admits, which is not the same as covering nothing. Declared in the type so
    # the distinction is not carried by a suppression.
    rungs_by_tier: dict[IvaRateKind, set[Decimal] | None] = {}
    for binding in revision.bindings:
        if not binding.id.startswith("modelo-303-iva-repercutido-") or not binding.id.endswith("-cuota"):
            continue
        axes = selector_as_dict(binding)
        rates = axes.get("applied_rates")
        assert rates is None or isinstance(rates, (list, tuple)), "applied_rates is not a sequence"
        rate_kinds = axes["rate_kinds"]
        assert isinstance(rate_kinds, (list, tuple)), "rate_kinds is not a sequence"
        for kind in rate_kinds:
            tier = IvaRateKind(kind)
            # A rate-blind rung covers everything its tier admits.
            rungs_by_tier.setdefault(tier, set())
            if rates is None:
                rungs_by_tier[tier] = None
            else:
                covered = rungs_by_tier[tier]
                if covered is not None:
                    covered.update(Decimal(str(rate)) for rate in rates)

    probe_dates = (date(2024, 3, 1), _EARLIER_WINDOW, date(2024, 11, 1), date(2025, 6, 1), date(2026, 6, 1))
    candidates = [Decimal(n) / Decimal("1000") for n in range(0, 300, 5)]
    for tier, covered in rungs_by_tier.items():
        if covered is None:
            continue
        for on_date in probe_dates:
            for pct in candidates:
                if tier in rate_kinds_for_declared_rate(EUMemberState.ES, pct, on_date):
                    assert pct in covered, f"{tier.value} admits {pct} on {on_date} but no Modelo 303 rung accepts it"


def test_a_domestic_row_always_carries_the_rate_the_rungs_key_on() -> None:
    """The narrowing assumes the classifier never emits a rate-less domestic row.

    If ``applied_rate`` could be ``None`` on a reduced or super-reducido
    observation, that row would match no rung and drop out of [27] entirely --
    turning this fix into a silent under-declaration. The classifier gates a
    missing ``iva_rate`` out before classification and derives the tier FROM the
    rate, so the invariant holds by construction; this pins it, because the
    narrowing is only correct while it does.
    """
    catalogue = TransactionCatalogue.model_validate(
        {"transactions": {t.transaction_id: t for t in _all_rungs_catalogue()}},
    )
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD_4T_2024)

    domestic = [
        o
        for o in aggregation.observations
        if o.rate_kind in {IvaRateKind.REDUCED, IvaRateKind.SUPER_REDUCED, IvaRateKind.GENERAL}
    ]
    assert domestic, "no domestic observation was produced -- the probe proves nothing"
    for observation in domestic:
        assert observation.applied_rate is not None, (
            f"observation {observation.ledger_id} reached a domestic tier with no recorded rate"
        )


def test_a_rate_less_row_is_refused_at_ingest_rather_than_silently_dropped() -> None:
    """The narrowing's whole safety case rests on this refusal, so it is gated here.

    The accepted rate-box decision rejects narrowing a tier binding because
    underdetermined rows then reach no box and leave the declared total. Modelo
    303 narrows anyway, and is safe only because the underdetermined row cannot
    exist on this path: the classifier refuses a transaction with no
    ``iva_rate`` and says so, rather than emitting an observation whose rate is
    unknown.

    A refusal is a stronger guarantee than a catch-all layer -- the amount never
    enters the return AND the operator is told -- but it is a different mechanism
    from the one that decision prescribes, so it needs its own gate. If this ever
    stops refusing, the narrowing becomes a silent under-declaration.
    """
    row = _transaction(
        "row-no-rate",
        on_date=date(2024, 11, 6),
        taxable_base=Decimal("1600.00"),
        iva_rate=None,
        iva_amount=Decimal("120.00"),
    )
    catalogue = TransactionCatalogue.model_validate({"transactions": {row.transaction_id: row}})
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD_4T_2024)

    assert aggregation.observations == (), "a rate-less row produced an observation instead of being refused"
    assert [i.reason.value for i in aggregation.issues] == ["missing_iva_rate"]


def test_an_underdetermined_observation_would_reach_no_rung_at_all() -> None:
    """Positive control: the probe above can only mean something if this fails.

    Proving a rate-less row never appears says nothing unless we also show what
    would happen if it did. Fed straight to the resolver, an observation with no
    recorded rate reaches NO rung -- exactly the loss the rate-box decision warns
    of -- while its determined twin reaches the ordinary reducido rung. So the
    refusal above is load-bearing, not incidental.
    """
    revision = _revision()

    def reached(applied_rate: Decimal | None) -> dict[str, Decimal]:
        observation = IvaLedgerObservation(
            ledger_id="control",
            transaction_date=date(2024, 11, 6),
            category=IvaCategory.DOMESTIC_REDUCED,
            rate_kind=IvaRateKind.REDUCED,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("1600.00"),
            iva_amount=Decimal("120.00"),
            recargo_amount=Decimal("0"),
            applied_rate=applied_rate,
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        )
        values = resolve_iva_ledger_binding_values(revision, (observation,))
        return {str(k): v for k, v in values.items() if "iva-repercutido" in str(k) and v != Decimal("0")}

    assert reached(None) == {}, "an underdetermined row reached a rate-specific rung"
    assert reached(Decimal("0.10")) == {
        "modelo-303-iva-repercutido-reducido-base": Decimal("1600.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("120.00"),
    }


def test_total_cuota_devengada_enumerates_every_recargo_rung_aeat_sums() -> None:
    """The aggregate must carry every rung AEAT's own [27] formula enumerates.

    The diseño prints casilla 27 as an explicit sum, and it names the recargo
    rungs [158], [170] and [26] alongside [18], [21] and [24]. Three of those
    were missing here, and [158] is the one that cost money: it is bound, so a
    super-reducido recargo cuota reached that box, but the box reached no total
    -- declared on the face of the return and absent from the figure the
    resultado chain uses.

    Keyed on the rungs rather than on a count, so adding a rung without totalling
    it reds this rather than passing on a stale tally. [158] and [26] appear in
    the printed formula of every design this revision spans; [170] appears from
    the 2024-late design, and is included so the total stays correct on both
    sides of the pending box move rather than needing a second edit then.
    """
    revision = _revision()
    total = next(f for f in revision.formulas if f.target_casilla_id == "iva.cuota-devengada-total")
    summed = {str(arg.casilla_id) for arg in total.expression.args if arg.casilla_id is not None}

    recargo_rungs_aeat_sums = {"18", "21", "24", "158", "170", "26"}
    assert recargo_rungs_aeat_sums <= summed, (
        f"recargo rungs AEAT sums into [27] but this total omits: {sorted(recargo_rungs_aeat_sums - summed)}"
    )


#: Every term AEAT prints inside casilla [27] in the 2025 diseno. [11] is the one
#: deliberate exclusion: it projects the AIC official-box PARITY casilla, while
#: iva.autorepercutido.intracomunitaria already books that same cuota into the
#: total, so summing it would count the AIC cuota twice. Declared here with its
#: reason rather than silently absent, because an undeclared gap in this list is
#: indistinguishable from the omission the test exists to catch.
_AEAT_TOTAL_TERMS = ("152", "167", "03", "155", "06", "09", "11", "13", "15", "158", "170", "18", "21", "24", "26")
_DELIBERATELY_EXCLUDED = {"11": "AIC parity box; iva.autorepercutido.intracomunitaria already books the cuota"}


def test_total_cuota_devengada_covers_every_term_aeat_prints() -> None:
    """Each printed term must be reachable, directly or through its projection.

    A term can be covered indirectly: [03] is a projection of
    iva.repercutido.super-reducido, so summing the carrier covers the box. This
    resolves each term to whatever actually feeds it rather than matching ids,
    which is what makes it safe to compare a semantic-layer total against a
    box-layer formula.

    Non-tautology: the projection map is derived from the loaded revision, not
    restated here, so dropping either a summed carrier or the projection that
    links a box to it fails this.
    """
    revision = _revision()
    total = next(f for f in revision.formulas if f.target_casilla_id == "iva.cuota-devengada-total")
    summed = {str(arg.casilla_id) for arg in total.expression.args if arg.casilla_id is not None}

    projects: dict[str, str] = {}
    for formula in revision.formulas:
        target = str(formula.target_casilla_id) if formula.target_casilla_id else None
        operands = [str(a.casilla_id) for a in formula.expression.args if a.casilla_id is not None]
        source = getattr(formula.expression, "casilla_id", None)
        if target and source is not None and not operands:
            projects[target] = str(source)

    uncovered = [
        term
        for term in _AEAT_TOTAL_TERMS
        if term not in _DELIBERATELY_EXCLUDED and term not in summed and projects.get(term) not in summed
    ]
    assert not uncovered, f"terms AEAT prints in [27] that this total cannot reach: {uncovered}"
