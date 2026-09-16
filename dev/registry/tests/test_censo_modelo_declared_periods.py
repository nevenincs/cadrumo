"""Censo event kinds are the union the selector declares, not one year's surface.

Censo ownership is a year-less inventory: it asks which censal event kinds the
active modelo declares at all. Reading the flat tuple would under-declare an
event kind that a selector serves only in an overridden year, and the
under-declaration would pass silently because the shorter tuple is still valid.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.censo_modelos import (
    CENSO_MODELO_EVENT_KINDS,
    _active_036_ownership_from_registry,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodOverride, PeriodSelector

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CENSO_MODELO = "036"
_OVERRIDE_YEAR = 2026


def _latest_revision(authority: ValidatedRegistryAuthority) -> ModeloRevision:
    """The revision censo ownership reads -- the modelo's latest by validity then id."""
    modelo = authority.modelo(_CENSO_MODELO)
    return max(modelo.revisions.values(), key=lambda item: (item.valid_from, str(item.id)))


def _authority_with_036_override(periods: tuple[str, ...]) -> ValidatedRegistryAuthority:
    """The bundled authority with modelo 036's latest revision overriding one year."""
    base = compiled_bundled_authority()
    modelo = base.modelo(_CENSO_MODELO)
    revision_id = max(modelo.revisions, key=lambda item: (modelo.revisions[item].valid_from, item))
    revision = modelo.revisions[revision_id]
    declared = revision.period_selector
    selector = PeriodSelector(
        years=declared.years,
        year_from=declared.year_from,
        year_to=declared.year_to,
        periods=declared.periods,
        period_overrides=(PeriodOverride(year=_OVERRIDE_YEAR, periods=periods),),
    )
    overridden = modelo.model_copy(
        update={
            "revisions": {
                **modelo.revisions,
                revision_id: revision.model_copy(update={"period_selector": selector}),
            },
        },
    )
    return ValidatedRegistryAuthority.from_validated_components(
        modelos=tuple(overridden if candidate.id == modelo.id else candidate for candidate in base.modelos),
        catalogues=base.catalogues,
        identity_digest="censo-period-override-fixture",
    )


def test_an_override_that_narrows_one_year_does_not_narrow_the_event_kinds() -> None:
    """The kinds are the union, so a year serving only ``alta`` still owns all three."""
    authority = _authority_with_036_override(("alta",))
    selector = _latest_revision(authority).period_selector
    assert selector.periods_for_year(_OVERRIDE_YEAR) == ("alta",), "the fixture must discriminate"

    ownership = _active_036_ownership_from_registry(authority)

    assert ownership.modelo == _CENSO_MODELO
    assert selector.declared_periods == CENSO_MODELO_EVENT_KINDS


def test_an_override_declaring_a_foreign_event_kind_is_refused() -> None:
    """A token declared only in an override year still reaches the ownership check."""
    authority = _authority_with_036_override((*CENSO_MODELO_EVENT_KINDS, "comunicacion"))

    with pytest.raises(RegistryValidationError, match="event periods must come from the registry"):
        _active_036_ownership_from_registry(authority)
