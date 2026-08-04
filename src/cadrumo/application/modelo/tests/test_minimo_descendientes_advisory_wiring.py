"""The mínimo advisory collectors are actually consulted by the coordinator.

A collector that returns the right rows when called directly, and is never
called, protects nobody. Both mínimo-por-descendientes collectors were wired
into :func:`collect_bucket_aggregation_advisory_diagnostics` with no test on the
wiring itself: deleting either call line failed nothing, because every test
invoked the collectors directly.

So these tests drive the COORDINATOR and assert the advisory arrives through it.
Nothing here calls a collector, which is the whole point -- a test that would
still pass with the wiring line removed is testing the collector twice and the
wiring never.

Two collectors are covered rather than one. The undeclared advisory is the
pre-existing wiring the review found unguarded; the rentas-undeclared advisory
is the new one, which would otherwise have shipped with the identical gap.
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
from ....domain.contribuyente import DescendantInfo, descendant_facts_from_list
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

_RENTAS_UNDECLARED = "minimo_descendientes_rentas_undeclared"
_UNDECLARED = "minimo_descendientes_undeclared"


@pytest.fixture(autouse=True)
def _bucket(tmp_path: Path) -> Iterator[None]:
    from ... import wizard as _wizard

    assert _wizard.WIZARD_FLOWS
    with isolated_profile_storage_root(tmp_path=tmp_path), profile_create_storage_span(_BUCKET_ID):
        workflow_state_repository().update(lambda s: register_minimal_profile(s, profile_id=_BUCKET_ID))
        yield


def _revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("100", filing_year=_FILING_YEAR, period="0A").revision


def _write(*descendants: DescendantInfo) -> None:
    facts = tuple(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(list(descendants)))
    workflow_state_repository().update(lambda s: set_active_fields(s, facts))


def _source_kinds(casilla_values: dict[CasillaId, Decimal]) -> set[str]:
    """Every source kind the COORDINATOR raises for this bucket."""
    diagnostics = collect_bucket_aggregation_advisory_diagnostics(
        _revision(),
        casilla_values,
        modelo=Modelo.M100.value,
        period_token="0A",
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


def test_the_coordinator_stays_quiet_when_neither_collector_has_anything_to_say() -> None:
    """Control: the kinds above are absent when their own conditions do not hold.

    Without this the two tests above could pass against a coordinator that
    raised every advisory unconditionally, which would satisfy the wiring claim
    while telling an operator nothing.
    """
    _write(DescendantInfo(birth_date=date(_FILING_YEAR - 10, 5, 1), rentas_anuales_euros=Decimal("0")))
    kinds = _source_kinds({_ESTATAL_CASILLA: Decimal("2400")})
    assert _RENTAS_UNDECLARED not in kinds
    assert _UNDECLARED not in kinds
