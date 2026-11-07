"""Registry lookup for filing window close dates (plazo voluntario).

Provides one profile-free matcher for the modelo, filing year, period and
optional resultado or Modelo 210 tipo-renta context. The typed resolution says
whether the window is authored, projected from the governed filing-window rule,
or projected with an unknown close, and feeds calendar, extemporaneidad, export
and workflow projections through ``resolve_filing_window``.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema_deadlines.DeadlineWindowDefinition`,
:data:`~cadrumo.domain.deadlines.filing_window_projection.FilingWindowResolution`.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from ...core.period import Period, PeriodKind
from ...core.result_disposition import ResultDisposition
from ..calculations.registry.errors import RegistrySnapshotError
from ..calculations.registry.form_codes import form_for_role
from ..calculations.registry.irnr_tipo_renta import m210_tipo_renta_code_projection
from .errors import DeadlineValidationError
from .filing_window_projection import AuthoredFilingWindow

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation
    from ..calculations.registry.deadline_coordinate import DeadlineSemanticCoordinate
    from ..calculations.registry.schema_deadlines import DeadlineWindowDefinition
    from .engine import DeadlineWindowProjection
    from .filing_window_projection import FilingWindowResolution


def resolve_filing_window(
    modelo: str,
    filing_year: int,
    period: Period,
    *,
    resultado: ResultDisposition | None = None,
    tipo_renta_code: str | None = None,
    authority: PinnedAuthorityOperation | None = None,
) -> FilingWindowResolution | None:
    """Return the deadline window resolution for a modelo+year+period, or ``None``.

    This is the single matching authority for "which deadline window covers
    this filing target". Every consumer -- extemporaneidad, the overview
    calendar, export and the workflow gate -- resolves through here, so a change
    to the year/token matching rule, to precedence or to the no-window behaviour
    can never move one surface without the other.

    The resolution says where the window comes from. An authored window always
    wins. A scheduled coordinate no revision authors is projected from the
    governed filing-window rule into a
    :class:`~cadrumo.domain.deadlines.filing_window_projection.ProjectedFilingWindow`,
    a dated window like an authored one. A close whose holiday calendar is
    unpublished is never reported as ``None``: an unknown close is not an
    absent window.

    Matching uses the registry's canonical atomic deadline coordinate. The
    filing year and bare period token must be exact; a window's absent qualifier
    scope is a wildcard, while an authored resultado or tipo-renta scope must
    contain the requested canonical value. No following-year or future-year
    window is ever borrowed when an exact match is absent.

    ``None`` means one thing only: the registry loaded, and declares no window
    matching this combination. A registry that cannot be read or validated is
    NOT an absence of deadline and is not reported as one -- the
    :class:`~cadrumo.domain.calculations.registry.errors.RegistryError` propagates.

    Reading ``deadline_windows`` costs full modelo validation, because the
    authority validates the modelo before projecting its windows. Catching that
    failure here and returning ``None`` turned any registry-wide validation
    fault into the claim that AEAT declares no filing deadline for this modelo
    and period -- a failure laundered into a confident answer about when a
    taxpayer must file. The sibling deadline engine wraps the same call and
    raises with the failing stage named; this now agrees with it.

    A year the support envelope gates answers the same way as any other: the
    window a revision authors for it, or ``None``. No rule is projected for it,
    because the product files nothing there, and the answer is never an
    envelope refusal. The envelope decides what can be filed, not what the law
    dated.

    Args:
        modelo: Agencia Estatal de Administración Tributaria (AEAT) modelo code
            (e.g. ``"130"``, ``"303"``).
        filing_year: Tax year for which the filing target was created.
        period: The typed filing period to match.
        resultado: Optional canonical post-calculation result disposition.
        tipo_renta_code: Optional official two-digit Modelo 210 tipo-renta code.
        authority: Optional generation-pinned authority operation.

    Returns:
        The authored or projected resolution, or ``None``
        when the registry neither authors nor can project a window for the
        combination.

    Raises:
        RegistryError: The registry could not be read or validated. The caller
            is told the deadline is unknown rather than absent.
        DeadlineValidationError: More than one window matches the atomic request
            coordinate. Ambiguous registry authority is never treated as absence.
    """
    selected_authority = authority
    if selected_authority is None:
        from ..calculations.registry.authority import bundled_indexed_authority

        with bundled_indexed_authority().operation() as operation:
            return _resolve_filing_window_with_operation(
                operation,
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                resultado=resultado,
                tipo_renta_code=tipo_renta_code,
            )
    return _resolve_filing_window_with_operation(
        selected_authority,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        resultado=resultado,
        tipo_renta_code=tipo_renta_code,
    )


def _resolve_filing_window_with_operation(
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    resultado: ResultDisposition | None,
    tipo_renta_code: str | None,
) -> FilingWindowResolution | None:
    """Resolve one filing window from a single generation-pinned operation."""
    if modelo not in operation.modelo_ids():
        raise RegistrySnapshotError.for_modelo_not_registered(modelo_id=modelo)
    # The closing coordinate of the filing year, which is how a filing year is
    # projected onto the date axis the governed catalogue is selected by. It is
    # the same coordinate for every modelo, so it is derived before the branch
    # rather than inside a Modelo 210 condition, where it would read as a value
    # this modelo fixes in code.
    filing_year_close = date(filing_year, 12, 31)
    if tipo_renta_code is not None and (
        modelo != form_for_role("irnr.income")
        or tipo_renta_code
        not in m210_tipo_renta_code_projection(
            effective_date=filing_year_close,
            authority=operation,
        )
    ):
        raise DeadlineValidationError(
            f"filing window tipo_renta_code {tipo_renta_code!r} is not a canonical official Modelo 210 code",
        )
    from .engine import indexed_deadline_window_year

    year_index = indexed_deadline_window_year(operation, filing_year)
    windows = tuple(item for item in year_index.dated if item[0] == modelo)
    window = resolve_projected_filing_window(
        windows,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        resultado=resultado,
        tipo_renta_code=tipo_renta_code,
    )
    if window is None:
        return None
    projected = year_index.projected.get(window.id)
    return AuthoredFilingWindow(window=window) if projected is None else projected


def resolve_projected_filing_window(
    windows: tuple[DeadlineWindowProjection, ...],
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    resultado: ResultDisposition | None,
    tipo_renta_code: str | None,
) -> DeadlineWindowDefinition | None:
    """Resolve one already-validated authority projection by semantic coordinate."""
    # Registry applicability imports this defining module, so defer the
    # registry coordinate import until resolution time to keep that dependency
    # cycle out of module initialisation.
    from ..calculations.registry.deadline_coordinate import deadline_semantic_coordinate

    requested = deadline_semantic_coordinate(modelo, period, resultado, tipo_renta_code)
    if requested.filing_year != filing_year:
        return None

    qualified_m210_event = _is_qualified_m210_event(
        modelo=modelo,
        period=period,
        resultado=resultado,
        tipo_renta_code=tipo_renta_code,
    )
    matches = _matching_projected_windows(
        windows,
        modelo=modelo,
        requested=requested,
        filing_year=filing_year,
        resultado=resultado,
        tipo_renta_code=tipo_renta_code,
        qualified_m210_event=qualified_m210_event,
    )
    return _select_unique_projected_window(matches, requested=requested)


def _is_qualified_m210_event(
    *,
    modelo: str,
    period: Period,
    resultado: ResultDisposition | None,
    tipo_renta_code: str | None,
) -> bool:
    from ..calculations.registry.period_selector_match import selector_period_matches_request

    return (
        modelo == form_for_role("irnr.income")
        and selector_period_matches_request("EVENT-N", period.registry_token)
        and (resultado is not None or tipo_renta_code is not None)
    )


def _matching_projected_windows(
    windows: tuple[DeadlineWindowProjection, ...],
    *,
    modelo: str,
    requested: DeadlineSemanticCoordinate,
    filing_year: int,
    resultado: ResultDisposition | None,
    tipo_renta_code: str | None,
    qualified_m210_event: bool,
) -> tuple[DeadlineWindowDefinition, ...]:
    if qualified_m210_event:
        return _matching_qualified_m210_event_windows(
            windows,
            modelo=modelo,
            filing_year=filing_year,
            resultado=resultado,
            tipo_renta_code=tipo_renta_code,
        )
    return _matching_general_projected_windows(windows, modelo=modelo, requested=requested)


def _matching_qualified_m210_event_windows(
    windows: tuple[DeadlineWindowProjection, ...],
    *,
    modelo: str,
    filing_year: int,
    resultado: ResultDisposition | None,
    tipo_renta_code: str | None,
) -> tuple[DeadlineWindowDefinition, ...]:
    return tuple(
        window
        for projected_modelo, _revision, window in windows
        if _matches_qualified_m210_event_window(
            projected_modelo,
            window,
            modelo=modelo,
            filing_year=filing_year,
            resultado=resultado,
            tipo_renta_code=tipo_renta_code,
        )
    )


def _matches_qualified_m210_event_window(
    projected_modelo: str,
    window: DeadlineWindowDefinition,
    *,
    modelo: str,
    filing_year: int,
    resultado: ResultDisposition | None,
    tipo_renta_code: str | None,
) -> bool:
    if projected_modelo != modelo:
        return False
    if window.period.kind is not PeriodKind.ANNUAL:
        return False
    return any(
        (coordinate.filing_year, coordinate.resultado_scope, coordinate.tipo_renta_code)
        == (filing_year, resultado, tipo_renta_code)
        for coordinate in _window_semantic_coordinates(projected_modelo, window)
    )


def _matching_general_projected_windows(
    windows: tuple[DeadlineWindowProjection, ...],
    *,
    modelo: str,
    requested: DeadlineSemanticCoordinate,
) -> tuple[DeadlineWindowDefinition, ...]:
    return tuple(
        window
        for projected_modelo, _revision, window in windows
        if _matches_general_projected_window(projected_modelo, window, modelo=modelo, requested=requested)
    )


def _matches_general_projected_window(
    projected_modelo: str,
    window: DeadlineWindowDefinition,
    *,
    modelo: str,
    requested: DeadlineSemanticCoordinate,
) -> bool:
    if projected_modelo != modelo:
        return False
    return requested in _window_semantic_coordinates(projected_modelo, window)


def _window_semantic_coordinates(
    modelo: str,
    window: DeadlineWindowDefinition,
) -> tuple[DeadlineSemanticCoordinate, ...]:
    from ..calculations.registry.deadline_coordinate import deadline_window_semantic_coordinates

    return deadline_window_semantic_coordinates(modelo, window)


def _select_unique_projected_window(
    matches: tuple[DeadlineWindowDefinition, ...],
    *,
    requested: DeadlineSemanticCoordinate,
) -> DeadlineWindowDefinition | None:
    if not matches:
        return None
    if len(matches) > 1:
        raise DeadlineValidationError(
            f"filing window resolution is ambiguous for {requested!r}: "
            f"matched window ids {[window.id for window in matches]!r}",
        )
    return next(iter(matches))


__all__ = ["resolve_filing_window"]
