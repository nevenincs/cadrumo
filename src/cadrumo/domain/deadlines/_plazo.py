"""Registry lookup for filing window close dates (plazo voluntario).

Provides a profile-free function to ask "when does the plazo voluntario
close for this modelo + filing year + period?" directly from the registry
deadline windows.  The result feeds the pre-calculation extemporaneidad
surface in :mod:`cadrumo.application.modelo._work_plazo`.  Post-calculation
consumers that know resultado or Modelo 210 tipo-renta context call the sibling
``resolve_filing_window`` entry point; both paths therefore share the same
canonical matcher.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import TYPE_CHECKING

from ...core import M210_TIPO_RENTA_CODE_PROJECTION, Modelo, Period, PeriodKind, ResultDisposition
from .errors import DeadlineValidationError

if TYPE_CHECKING:
    from ..calculations.registry.schema import DeadlineWindowDefinition, ModeloRevision

    type DeadlineWindowProjection = tuple[str, ModeloRevision, DeadlineWindowDefinition]


def resolve_filing_closes_on(modelo: str, filing_year: int, period: Period) -> date | None:
    """Return the close date of the plazo voluntario for a modelo+year+period.

    Queries the validated registry authority for ``filing_year`` through
    :func:`resolve_filing_window` and returns the ``closes_on`` of its unique
    unqualified match. This function deliberately accepts no resultado or
    Modelo 210 tipo-renta context: it is the pre-calculation convenience, while
    post-calculation callers use ``resolve_filing_window`` directly rather than
    owning another matcher.

    The resolved value belongs to the matching
    :class:`~cadrumo.domain.calculations.registry.DeadlineWindowDefinition`.

    Matching rule: the registry window period must carry the same
    filing year and bare registry period token as the supplied ``WorkUnit``
    period (e.g. ``"1T"``, ``"0A"``, ``"01"``).

    Annual Modelo 100 uses its tax year as the registry key even though
    its normal campaign runs in the following calendar year. A close date
    for tax year 2024 can therefore fall in 2025. This function never
    borrows a following-year or future-year window when an exact match is
    absent.

    Returns ``None`` when no registry window exactly matches the
    combination. The modelo might have no deadline window for that year,
    or its period token might not match any window. ``None`` means the
    deadline data is unavailable; callers continue without a close date.

    A modelo absent from the registry is NOT one of those causes and REFUSES
    with :exc:`RegistrySnapshotError` rather than returning ``None``. Production
    reaches this through the ``Modelo`` enum, so an unregistered id is a caller
    bug or unvalidated external input; returning ``None`` would hand that caller
    "no deadline", and an extemporaneidad computed from it would silently drop
    the recargo.

    Args:
        modelo: Agencia Estatal de Administración Tributaria (AEAT) modelo code
            (e.g. ``"130"``, ``"303"``).
        filing_year: Tax year for which the work unit was created.
        period: ``WorkUnit`` bare registry period token (e.g. ``"1T"``,
            ``"0A"``, ``"01"``).

    Returns:
        The :class:`~datetime.date` on which the filing window closes,
        or ``None`` if not found.
    """
    window = resolve_filing_window(modelo, filing_year, period)
    return None if window is None else window.closes_on


@lru_cache(maxsize=256, typed=True)
def resolve_filing_window(
    modelo: str,
    filing_year: int,
    period: Period,
    *,
    resultado: ResultDisposition | None = None,
    tipo_renta_code: str | None = None,
) -> DeadlineWindowDefinition | None:
    """Return the registry deadline window for a modelo+year+period, or ``None``.

    This is the single matching authority for "which registry deadline window
    covers this filing target". Every consumer — the extemporaneidad surface
    that needs only
    :attr:`~cadrumo.domain.calculations.registry.DeadlineWindowDefinition.closes_on`,
    and the overview calendar that also
    needs ``opens_on`` and ``payment_cutoff_on`` — resolves through here, so a
    change to the year/token matching rule or to the no-window behaviour can
    never move one surface without the other.

    Matching uses the registry's canonical atomic deadline coordinate. The
    filing year and bare period token must be exact; a window's absent qualifier
    scope is a wildcard, while an authored resultado or tipo-renta scope must
    contain the requested canonical value. No following-year or future-year
    window is ever borrowed when an exact match is absent.

    ``None`` means one thing only: the registry loaded, and declares no window
    matching this combination. A registry that cannot be read or validated is
    NOT an absence of deadline and is not reported as one -- the
    :class:`~cadrumo.domain.calculations.registry.RegistryError` propagates.

    Reading ``deadline_windows`` costs full modelo validation, because the
    authority validates the modelo before projecting its windows. Catching that
    failure here and returning ``None`` turned any registry-wide validation
    fault into the claim that AEAT declares no filing deadline for this modelo
    and period -- a failure laundered into a confident answer about when a
    taxpayer must file. The sibling deadline engine wraps the same call and
    raises with the failing stage named; this now agrees with it.

    Args:
        modelo: Agencia Estatal de Administración Tributaria (AEAT) modelo code
            (e.g. ``"130"``, ``"303"``).
        filing_year: Tax year for which the filing target was created.
        period: The typed filing period to match.
        resultado: Optional canonical post-calculation result disposition.
        tipo_renta_code: Optional official two-digit Modelo 210 tipo-renta code.

    Returns:
        The matching
        :class:`~cadrumo.domain.calculations.registry.DeadlineWindowDefinition`,
        or ``None`` when the registry declares no window for the combination.

    Raises:
        RegistryError: The registry could not be read or validated. The caller
            is told the deadline is unknown rather than absent.
        DeadlineValidationError: More than one window matches the atomic request
            coordinate. Ambiguous registry authority is never treated as absence.
    """
    from ..calculations.registry.authority import bundled_authority

    if resultado is not None and not isinstance(resultado, ResultDisposition):
        raise DeadlineValidationError(
            f"filing window resultado must be ResultDisposition, got {type(resultado).__name__}",
        )
    if tipo_renta_code is not None and (
        modelo != Modelo.M210 or tipo_renta_code not in M210_TIPO_RENTA_CODE_PROJECTION
    ):
        raise DeadlineValidationError(
            f"filing window tipo_renta_code {tipo_renta_code!r} is not a canonical official Modelo 210 code",
        )

    authority = bundled_authority()

    windows = authority.deadline_windows(filing_year, modelos=(modelo,))
    return _resolve_projected_filing_window(
        windows,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        resultado=resultado,
        tipo_renta_code=tipo_renta_code,
    )


def _resolve_projected_filing_window(
    windows: tuple[DeadlineWindowProjection, ...],
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    resultado: ResultDisposition | None,
    tipo_renta_code: str | None,
) -> DeadlineWindowDefinition | None:
    """Resolve one already-validated authority projection by semantic coordinate."""
    # Registry applicability imports this deadline facade, so defer the public
    # registry-facade import until resolution time to keep that dependency cycle
    # out of module initialisation.
    from ..calculations.registry.deadline_coordinate import (
        deadline_semantic_coordinate,
        deadline_window_semantic_coordinates,
    )
    from ..calculations.registry.period_selector_match import selector_period_matches_request

    requested = deadline_semantic_coordinate(modelo, period, resultado, tipo_renta_code)
    if requested.filing_year != filing_year:
        return None

    qualified_m210_event = (
        modelo == Modelo.M210
        and selector_period_matches_request("EVENT-N", period.registry_token)
        and (resultado is not None or tipo_renta_code is not None)
    )
    matches: tuple[DeadlineWindowDefinition, ...]
    if qualified_m210_event:
        matches = tuple(
            window
            for projected_modelo, _revision, window in windows
            if projected_modelo == modelo
            and window.period.kind is PeriodKind.ANNUAL
            and any(
                coordinate.filing_year == filing_year
                and coordinate.resultado_scope == resultado
                and coordinate.tipo_renta_code == tipo_renta_code
                for coordinate in deadline_window_semantic_coordinates(projected_modelo, window)
            )
        )
    else:
        matches = tuple(
            window
            for projected_modelo, _revision, window in windows
            if projected_modelo == modelo
            and requested in deadline_window_semantic_coordinates(projected_modelo, window)
        )
    if not matches:
        return None
    if len(matches) > 1:
        raise DeadlineValidationError(
            f"filing window resolution is ambiguous for {requested!r}: "
            f"matched window ids {[window.id for window in matches]!r}",
        )
    return matches[0]


__all__ = ["resolve_filing_closes_on", "resolve_filing_window"]
