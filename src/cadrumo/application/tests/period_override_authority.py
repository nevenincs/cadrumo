"""A real registry authority whose one modelo revision overrides a filing year's periods.

No shipped revision declares ``period_overrides`` yet, so the consumers that
must honour one cannot be exercised against the bundled corpus. This support
builds a REAL authority -- real catalogues, real typed models, the real
snapshot path -- from the bundled corpus with ONE revision's selector replaced
by one that overrides its first covered year and drops the leading flat token.
Every other revision, and the whole predecessor chain, is carried verbatim. A
consumer reading the flat tuple therefore picks ``1T``, a period the override
says the edition does not file that year; a consumer reading the override
surface picks ``2T``.
"""

from __future__ import annotations

from typing import Final

from ...domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from ...domain.calculations.registry.schema_references import PeriodOverride, PeriodSelector

OVERRIDE_MODELO: Final = "216"
"""The modelo the fixture rebuilds; every other bundled modelo is carried verbatim."""

OVERRIDE_REVISION: Final = "2024-y-siguientes"
"""The rebuilt revision -- the modelo's current provider, and open-ended."""

OVERRIDE_YEAR: Final = 2024
"""The filing year whose surface the override replaces."""

DROPPED_PERIOD: Final = "1T"
"""The first flat token the override removes -- what a flat read still returns."""

OVERRIDE_PERIODS: Final = ("2T", "3T", "4T")
"""The surface the overridden year actually serves."""


def authority_with_period_override(
    *,
    modelo_id: str,
    revision_id: str,
    year: int,
    periods: tuple[str, ...],
) -> ValidatedRegistryAuthority:
    """Return the bundled authority with one revision's year surface overridden.

    Only the named revision's ``period_selector`` is rebuilt, and it is rebuilt
    through the typed constructor, so the override is validated exactly as an
    authored one would be. The revision's declared years and flat tuple are
    carried over unchanged.
    """
    base = bundled_authority()
    modelo = base.modelo(modelo_id)
    revision = modelo.revisions[revision_id]
    declared = revision.period_selector
    selector = PeriodSelector(
        years=declared.years,
        year_from=declared.year_from,
        year_to=declared.year_to,
        periods=declared.periods,
        period_overrides=(PeriodOverride(year=year, periods=periods),),
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
        identity_digest=f"period-override-fixture-{modelo_id}-{revision_id}-{year}",
    )


def override_authority() -> ValidatedRegistryAuthority:
    """Return the authority whose :data:`OVERRIDE_MODELO` overrides :data:`OVERRIDE_YEAR`."""
    return authority_with_period_override(
        modelo_id=OVERRIDE_MODELO,
        revision_id=OVERRIDE_REVISION,
        year=OVERRIDE_YEAR,
        periods=OVERRIDE_PERIODS,
    )
