"""The mínimo advisory collectors are actually consulted by the coordinator.

A collector that returns the right rows when called directly, and is never
called, protects nobody. Every mínimo-por-descendientes collector was wired
into :func:`collect_bucket_aggregation_advisory_diagnostics` with no test on
the wiring itself: deleting a call line failed nothing, because every test
invoked the collectors directly.

So these tests drive the COORDINATOR and assert the advisory arrives through it.
Nothing here calls a collector, which is the whole point -- a test that would
still pass with the wiring line removed is testing the collector twice and the
wiring never.

All four mínimo-family collectors are covered, plus ``settlement_not_computed``
as the first of the non-mínimo wirings. An earlier pass claimed "both
collectors" and covered two, having enumerated the population from what it had
touched rather than from the coordinator's own call block. Read whole, that
block wires TEN collectors.

Audit state of the other five, measured rather than assumed:
``prorrata_regularizacion`` is covered by
``test_prorrata_especial_mandatory_live_emit``, which drives this coordinator
and asserts its kind arrives. ``official_box_unpopulated``,
``prior_payment_not_deducted``, ``prior_payment_minoracion_not_captured`` and
``bienes_inversion_regularizacion`` remain unwired-tested: each needs its own
modelo fixture (a seeded observation repository, an M303 ledger) rather than a
revision and a profile, so they are a separate piece of work rather than more
cases here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId
from ....core.modelo import Modelo
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.contribuyente.renta_codes import RentaMaritalStatus
from ....domain.user_profile.values import UserProfileFact
from ....tests.profile_capsule import set_active_test_profile_facts
from .._calculation_diagnostics import collect_bucket_aggregation_advisory_diagnostics
from .._minimo_descendientes_advisory import collect_minimo_descendientes_undeclared_diagnostics
from ._advisory_bucket_fixture import _bucket  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "5c5c5c5c-5c5c-4c5c-8c5c-5c5c5c5c5c5c"
_FILING_YEAR = 2024
_ESTATAL_CASILLA: CasillaId = "0513"
#: Annual period token for the Modelo 100 walk (named so the literal does not
#: read as a credential to the security linter).
_ANNUAL_PERIOD = "0A"

_RENTAS_UNDECLARED = "minimo_descendientes_rentas_undeclared"
_UNDECLARED = "minimo_descendientes_undeclared"
_PRORRATA_INFERRED = "minimo_descendientes_prorrata_inferred"
_COUNT_DESYNC = "descendientes_count_desync"
_SETTLEMENT = "settlement_casilla"


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _revision() -> ModeloRevision:
    return bundled_authority().snapshot("100", filing_year=_FILING_YEAR, period="0A").revision


def _write(
    *descendants: DescendantInfo,
    marital_status: str | None = None,
    declaration_type: str | None = None,
    descendientes_count: str | None = None,
) -> None:
    facts = [UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(list(descendants))]
    if marital_status is not None:
        facts.append(UserProfileFact(path="renta_taxpayer.marital_status", value=marital_status))
    if declaration_type is not None:
        facts.append(UserProfileFact(path="renta_filing.declaration_type", value=declaration_type))
    if descendientes_count is not None:
        # Overwrite the aggregate the projection just derived, which is how the
        # profile manager desyncs it: the count renders as an editable row while
        # the rows it counts are an indexed namespace the manager never shows.
        facts.append(UserProfileFact(path="renta_family.descendientes_count", value=descendientes_count))
    set_active_test_profile_facts(tuple(facts))


def _source_kinds(casilla_values: dict[CasillaId, Decimal]) -> set[str]:
    """Every source kind the COORDINATOR raises for this bucket."""
    diagnostics = collect_bucket_aggregation_advisory_diagnostics(
        _revision(),
        casilla_values,
        modelo=Modelo.M100.value,
        period_token=_ANNUAL_PERIOD,
        filing_year=_FILING_YEAR,
        bucket_id=_BUCKET_ID,
    )
    return {diagnostic.source_kind for diagnostic in diagnostics}


def test_the_rentas_undeclared_advisory_reaches_the_coordinator() -> None:
    """The new collector's wiring, which would otherwise ship unguarded.

    A cohabiting 10-year-old with no rentas figure, against a non-zero
    aggregate: exactly the state the collector fires on. If its call line were
    removed from the coordinator this set would not contain the kind.
    """
    _write(DescendantInfo(birth_date=date(_FILING_YEAR - 10, 5, 1)))
    assert _RENTAS_UNDECLARED in _source_kinds({_ESTATAL_CASILLA: Decimal("2400")})


def test_the_undeclared_advisory_reaches_the_coordinator() -> None:
    """The pre-existing wiring the review found unguarded.

    A profile with no descendiente facts against a zero aggregate is the state
    that collector owns, and it is reached through the coordinator here rather
    than by calling it.
    """
    assert _UNDECLARED in _source_kinds({_ESTATAL_CASILLA: Decimal("0")})


def test_the_prorrata_inferred_advisory_reaches_the_coordinator() -> None:
    """The wiring of the collector the disclosed-under-claim default depends on.

    Applying the prorrata rather than the full amount is justified on the
    operator being told, so this wiring is what makes a disclosed under-claim
    disclosed. A partnered filer declaring individually, with no explicit
    per-descendant answer, is the state it fires on.
    """
    _write(
        DescendantInfo(birth_date=date(_FILING_YEAR - 10, 5, 1)),
        marital_status=RentaMaritalStatus.CASADO.value,
        declaration_type="1",
    )
    assert _PRORRATA_INFERRED in _source_kinds({_ESTATAL_CASILLA: Decimal("1200")})


def test_the_count_desync_advisory_reaches_the_coordinator() -> None:
    """The fourth mínimo collector: direct tests existed, its wiring had none.

    A stored count contradicting the rows it aggregates splits the filing --
    one binding follows the operator's number, the casillas follow the rows.
    Reached through the coordinator here rather than by calling it.
    """
    _write(DescendantInfo(birth_date=date(_FILING_YEAR - 10, 5, 1)), descendientes_count="7")
    assert _COUNT_DESYNC in _source_kinds({_ESTATAL_CASILLA: Decimal("2400")})


def test_the_settlement_advisory_reaches_the_coordinator() -> None:
    """A non-mínimo wiring, audited because this class keeps producing findings.

    ``settlement_not_computed`` fires where a revision declares a settlement-role
    casilla that is NOT computed, which the 2020-2023 Modelo 100 revisions do
    (2024 computes them, which is why the fixture year differs from every other
    case in this module). The state is a property of the revision alone, so no
    profile setup is needed.
    """
    revision = bundled_authority().snapshot("100", filing_year=2020, period=_ANNUAL_PERIOD).revision
    diagnostics = collect_bucket_aggregation_advisory_diagnostics(
        revision,
        {},
        modelo=Modelo.M100.value,
        period_token=_ANNUAL_PERIOD,
        filing_year=2020,
        bucket_id=_BUCKET_ID,
    )
    assert _SETTLEMENT in {diagnostic.source_kind for diagnostic in diagnostics}


def test_the_settlement_advisory_is_absent_where_the_revision_computes_it() -> None:
    """Control for the case above, and it is the same collector on a different year.

    2024 computes its settlement casillas, so the kind must NOT appear. Without
    this the test above would pass against a collector that fired on every
    revision, which would say nothing about the condition it claims to detect.
    """
    revision = bundled_authority().snapshot("100", filing_year=2024, period=_ANNUAL_PERIOD).revision
    diagnostics = collect_bucket_aggregation_advisory_diagnostics(
        revision,
        {},
        modelo=Modelo.M100.value,
        period_token=_ANNUAL_PERIOD,
        filing_year=2024,
        bucket_id=_BUCKET_ID,
    )
    assert _SETTLEMENT not in {diagnostic.source_kind for diagnostic in diagnostics}


def test_the_coordinator_stays_quiet_when_no_collector_has_anything_to_say() -> None:
    """Control: every kind above is ABSENT when its own conditions do not hold.

    Without this the four tests above could all pass against a coordinator
    that raised every advisory unconditionally, which would satisfy the wiring
    claim while telling an operator nothing. A declared zero rentas figure, a
    declared prorrata answer, an unpartnered filer and a count that matches
    the rows: nothing for any of the four to say.
    """
    _write(
        DescendantInfo(
            birth_date=date(_FILING_YEAR - 10, 5, 1),
            rentas_anuales_euros=Decimal("0"),
            prorrata_minimo=False,
        ),
        marital_status=RentaMaritalStatus.SOLTERO.value,
        declaration_type="1",
    )
    kinds = _source_kinds({_ESTATAL_CASILLA: Decimal("2400")})
    assert _RENTAS_UNDECLARED not in kinds
    assert _UNDECLARED not in kinds
    assert _PRORRATA_INFERRED not in kinds
    assert _COUNT_DESYNC not in kinds


def test_the_undeclared_advisory_grounds_from_the_casilla_it_addresses() -> None:
    """Casilla-derived: this advisory's subject IS casilla 0513's own zero.

    Population A in the grounding reference's own terms -- the casilla already
    carries the exact provision the message names (plain "Art. 58"), so the
    correct disposition is the casilla-derived path, not a minted assertion.
    """
    diagnostics = collect_minimo_descendientes_undeclared_diagnostics(
        _revision(),
        {_ESTATAL_CASILLA: Decimal("0")},
        modelo=Modelo.M100.value,
        bucket_id=_BUCKET_ID,
    )
    assert len(diagnostics) == 1
    assert diagnostics[0].legal_refs == ("ley-35-2006:art-56", "ley-35-2006:art-58", "ley-35-2006:art-61")
    assert diagnostics[0].asserted_legal_refs == ()
