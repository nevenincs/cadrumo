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

All FOUR mínimo-family collectors the coordinator wires are covered here. An
earlier pass claimed "both collectors" and covered two, having enumerated the
population from what it had touched rather than from the coordinator's own call
block. Reading that block whole gives ten collectors, four of them
mínimo-family: undeclared, prorrata-inferred, rentas-undeclared and
count-desync.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Modelo
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, ModeloRevision
from ....domain.contribuyente import DescendantInfo, RentaMaritalStatus, descendant_facts_from_list
from ....domain.user_profile import UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ...user_profile import profile_create_storage_span, set_active_fields
from ...workflow import workflow_state_repository
from .._calculation_diagnostics import collect_bucket_aggregation_advisory_diagnostics

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


@pytest.fixture(autouse=True)
def _bucket(tmp_path: Path) -> Iterator[None]:
    from ... import wizard as _wizard

    assert _wizard.WIZARD_FLOWS
    with isolated_profile_storage_root(tmp_path=tmp_path), profile_create_storage_span(_BUCKET_ID):
        workflow_state_repository().update(lambda s: register_minimal_profile(s, profile_id=_BUCKET_ID))
        yield


def _revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("100", filing_year=_FILING_YEAR, period="0A").revision


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
        facts.append(UserProfileFact(path="filing_export.declaration_type", value=declaration_type))
    if descendientes_count is not None:
        # Overwrite the aggregate the projection just derived, which is how the
        # profile manager desyncs it: the count renders as an editable row while
        # the rows it counts are an indexed namespace the manager never shows.
        facts.append(UserProfileFact(path="renta_family.descendientes_count", value=descendientes_count))
    workflow_state_repository().update(lambda s: set_active_fields(s, tuple(facts)))


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
