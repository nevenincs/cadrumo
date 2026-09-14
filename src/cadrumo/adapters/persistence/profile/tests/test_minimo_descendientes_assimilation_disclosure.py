"""Both mínimo disclosures must judge descendants against the FILER's profile.

``DescendantInfo.meets_non_income_conditions`` takes
``dependencia_assimilation_available``, which turns on a filer-level fact (the
judicial anualidades figure) that no descendant row carries. Its default is
``False`` -- the under-granting answer -- so a caller that omits it silently
drops every descendant reaching the mínimo through the Art. 58 economic-dependency
assimilation.

The figure path passes it at six sites, and where one caller deliberately
suppresses it, it says so in five lines of comment. Both DISCLOSURE surfaces
simply omitted it, and the two omissions failed in OPPOSITE directions:

* the rentas-undeclared advisory exists to catch an OVER-claim -- a descendant
  contributing a full tranche on a figure nobody entered. Dropping the
  assimilated population means the descendant is in the mínimo but not in the
  prompt to declare their rentas.
* the entry-date advisory exists to make an UNDER-grant visible -- an adopted or
  fostered child whose Art. 58.2 window has no anchor. Dropping the assimilated
  population means that household is under-granted AND unreported, which is the
  one thing the disclosure exists to prevent.

Both directions are tested because a fix threading the flag through one surface
would leave the other broken while looking done.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from cadrumo.adapters.persistence.profile.tests.advisory_profile_bucket_fixture import (
    advisory_profile_bucket,  # noqa: F401
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import set_active_test_profile_facts
from cadrumo.application.aggregation.source_mesh import CalculationSourceDiagnostic
from cadrumo.application.modelo.calculation_diagnostics import collect_bucket_aggregation_advisory_diagnostics
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.descendant_relacion import DescendantRelacion
from cadrumo.core.modelo import Modelo
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.contribuyente.descendant import DescendantInfo
from cadrumo.domain.contribuyente.descendant_facts import descendant_facts_from_list
from cadrumo.domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "6c6c6c6c-6c6c-4c6c-8c6c-6c6c6c6c6c6c"
_FILING_YEAR = 2024
_ANNUAL_PERIOD = "0A"
_ESTATAL_CASILLA: CasillaId = "0513"
_CLAIMED = {_ESTATAL_CASILLA: Decimal("2400")}


def _coordinator_diagnostics() -> tuple[CalculationSourceDiagnostic, ...]:
    return collect_bucket_aggregation_advisory_diagnostics(
        _revision(),
        _CLAIMED,
        modelo=Modelo("100").value,
        period_token=_ANNUAL_PERIOD,
        filing_year=_FILING_YEAR,
        bucket_id=_BUCKET_ID,
        observation_repository=Mock(),
        prorrata_register_repository=Mock(bucket_id=_BUCKET_ID),
        bienes_inversion_repository=Mock(),
        transaction_repository=Mock(bucket_id=_BUCKET_ID),
    )


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _revision() -> ModeloRevision:
    return compiled_bundled_authority().snapshot("100", filing_year=_FILING_YEAR, period=_ANNUAL_PERIOD).revision


def _write(*descendants: DescendantInfo) -> None:
    """Write descendant rows and NO anualidades fact.

    An absent anualidades figure is what makes the assimilation available, so
    this is the household the omission silently excluded. Writing a positive
    figure here would suppress the assimilation and make both cases vacuous.
    """
    facts = tuple(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(list(descendants)))
    set_active_test_profile_facts(facts)


def _assimilated_child(
    *,
    relacion: DescendantRelacion = DescendantRelacion.DESCENDIENTE,
    inscripcion_registro_civil_date: date | None = None,
) -> DescendantInfo:
    """A NON-cohabiting descendant the filer economically supports.

    Reaches the mínimo only through the Art. 58 dependency limb, which is exactly
    the population a ``dependencia_assimilation_available=False`` default drops.

    The relación and its Art. 58.2 entry anchor are the only axes these tests
    vary, so they are named parameters rather than a ``**overrides`` bag: the bag
    erased every field to ``object`` on the way into the strict model, so the
    constructor could check none of them.
    """
    return DescendantInfo(
        birth_date=date(_FILING_YEAR - 10, 5, 1),
        relacion=relacion,
        inscripcion_registro_civil_date=inscripcion_registro_civil_date,
        convive_con_contribuyente=False,
        dependencia_economica=True,
        rentas_anuales_euros=None,
    )


def _rentas_advisories() -> tuple[CalculationSourceDiagnostic, ...]:
    return tuple(
        diagnostic
        for diagnostic in _coordinator_diagnostics()
        if diagnostic.source_kind == "minimo_descendientes_rentas_undeclared"
    )


def _entry_date_advisories() -> tuple[CalculationSourceDiagnostic, ...]:
    return tuple(
        diagnostic
        for diagnostic in _coordinator_diagnostics()
        if diagnostic.source_kind == "minimo_descendientes_entry_date_missing"
    )


def test_the_fixture_child_reaches_the_minimo_only_through_the_assimilation() -> None:
    """Anchor test: if the fixture ever cohabits, both cases below go vacuous.

    A cohabiting descendant satisfies the household limb outright, so the flag
    would not matter and each assertion would pass while testing nothing.
    """
    child = _assimilated_child()
    assert child.convive_con_contribuyente is False
    assert child.qualifies_on_household_limb() is False
    assert child.qualifies_on_household_limb(dependencia_assimilation_available=True) is True


def test_the_over_claim_disclosure_covers_an_assimilated_descendant() -> None:
    """Direction one: in the mínimo, absent from the prompt to declare rentas.

    This descendant contributes a full tranche on a figure nobody entered. The
    advisory that exists to catch exactly that dropped them.
    """
    _write(_assimilated_child())

    diagnostics = _rentas_advisories()

    assert len(diagnostics) == 1, "an assimilated descendant claiming on no rentas figure went unreported"
    assert diagnostics[0].source_kind == "minimo_descendientes_rentas_undeclared"


def test_the_under_grant_disclosure_covers_an_assimilated_descendant() -> None:
    """Direction two: under-granted AND unreported.

    An adopted descendant over three with no inscription date cannot take the
    Art. 58.2 age-independent increase. That under-grant is the safe direction
    only while something says so; for this household nothing did.
    """
    _write(
        _assimilated_child(
            relacion=DescendantRelacion.ADOPTADO,
            inscripcion_registro_civil_date=None,
        ),
    )

    diagnostics = _entry_date_advisories()

    assert len(diagnostics) == 1, "an assimilated adopted descendant's missing anchor went unreported"
    assert diagnostics[0].source_kind == "minimo_descendientes_entry_date_missing"


def test_a_suppressed_household_is_still_excluded_from_both_disclosures() -> None:
    """Positive control: the fix widens the population, it does not blanket-fire.

    A filer declaring judicial anualidades has the assimilation suppressed for
    every descendant, so the same non-cohabiting child takes no mínimo and
    belongs in neither advisory. Without this, a collector that reported every
    descendant unconditionally would satisfy both cases above.
    """
    descendants = (
        _assimilated_child(
            relacion=DescendantRelacion.ADOPTADO,
            inscripcion_registro_civil_date=None,
        ),
    )
    facts = [
        *(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(list(descendants))),
        UserProfileFact(path="renta_family.anualidades_alimentos_euros", value="1200"),
    ]
    set_active_test_profile_facts(tuple(facts))

    assert _rentas_advisories() == ()
    assert _entry_date_advisories() == ()
