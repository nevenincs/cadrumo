"""Shared modelo CLI support helpers.

These helpers stay at the Typer boundary: they validate operator token shape,
translate application refusals into ``BadParameter`` messages, and choose the
default audit actor. Filing selection and revision eligibility remain delegated
to application services by the caller.
"""

from __future__ import annotations

import re

import typer

from ...application.modelo import (
    CalculationRevisionNotFoundError,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloWorkAddressNotFoundError,
    ModeloWorkRevisionConflictError,
    ModeloWorkUnitCandidate,
    ModeloWorkVisibleTargetAmbiguousError,
    get_work_unit,
)
from ...core.errors import resolve_error_message
from ...core.i18n import tr
from ...core.logging import get_logger
from ._modelo_rendering import short_id

_log = get_logger(__name__)

_WORK_UNIT_ID_RE = r"^[0-9a-f]{64}$"
"""SHA-256 hex digest expected as the canonical work-unit identifier."""


def validate_work_unit_id(value: str) -> str:
    """Validate that *value* is a 64-character lowercase hex string."""
    stripped = value.strip()
    if not re.fullmatch(_WORK_UNIT_ID_RE, stripped):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_work_unit_id",
                default=(f"work_unit_id must be a 64-character lowercase hex string (SHA-256 digest); got {value!r}"),
            )
        )
    return stripped


def validate_calculation_revision_id(value: str) -> str:
    """Validate that *value* is a 64-character lowercase hex string."""
    stripped = value.strip()
    if not re.fullmatch(_WORK_UNIT_ID_RE, stripped):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_calculation_revision_id",
                default=(
                    "calculation_revision_id must be a 64-character lowercase "
                    f"hex string (SHA-256 digest); got {value!r}"
                ),
            )
        )
    return stripped


def bad_parameter_from_error(exc: BaseException) -> typer.BadParameter:
    """Render registered domain errors before crossing the Typer boundary."""
    return typer.BadParameter(resolve_error_message(exc))


def bad_parameter_from_localized_context(exc: BaseException) -> typer.BadParameter:
    """Render local projection refusals that intentionally are not error-code registered."""
    key = getattr(exc, "translated_message", None)
    context = getattr(exc, "context", None) or {}
    if isinstance(key, str) and key:
        return typer.BadParameter(tr(key, **context))
    return typer.BadParameter(str(exc))


def calculation_revision_not_found_bad_parameter(
    calculation_revision_id: str, exc: CalculationRevisionNotFoundError
) -> typer.BadParameter:
    """Render a not-found calc-revision id, hinting when it is really a work-unit id."""
    stripped = calculation_revision_id.strip()
    try:
        unit = get_work_unit(stripped)
    except Exception:
        _log.debug(
            "calculation revision hint lookup failed; falling back to registered error rendering",
            exc_info=True,
        )
        return bad_parameter_from_error(exc)
    return typer.BadParameter(
        tr(
            "cli.app.modelo.work.id_is_work_unit_not_calc_revision_natural",
            default=(
                "This id is a work-unit-id, but verify/file need a calculation-revision-id. "
                "For the common path, run 'aeat app modelo work calculate --modelo %{modelo} "
                "--year %{year} --period %{period}' and then rerun verify/file for that "
                "same modelo/year/period. Exact ids remain available as an advanced escape hatch."
            ),
            modelo=unit.modelo,
            year=unit.filing_year,
            period=unit.period,
        )
    )


def work_candidate_lines(candidates: tuple[ModeloWorkUnitCandidate, ...]) -> str:
    """Return tabular candidate guidance for ambiguous visible filing targets."""
    rows = [
        "candidates:",
        "short_id\tmodelo\tyear\tperiod\trevision_id\tstate\tcurrent\tfiled\tname",
    ]
    for candidate in candidates:
        rows.append(
            "\t".join(
                (
                    candidate.short_work_unit_id,
                    str(candidate.modelo),
                    str(candidate.filing_year),
                    candidate.period,
                    candidate.revision_id,
                    candidate.state.value,
                    short_id(candidate.current_calculation_revision_id) or "",
                    short_id(candidate.filed_calculation_revision_id) or "",
                    candidate.work_unit_id,
                )
            )
        )
    return "\n".join(rows)


def selector_bad_parameter(exc: BaseException) -> typer.BadParameter:
    """Translate visible-target and revision selector refusals for Typer."""
    if isinstance(exc, ModeloWorkVisibleTargetAmbiguousError):
        return typer.BadParameter(
            tr(
                "cli.app.modelo.work.selector_ambiguous",
                default=(
                    "More than one active work unit matches this modelo/year/period. "
                    "Choose a registry revision or pass an explicit work-unit id.\n{candidates}"
                ),
                candidates=work_candidate_lines(exc.candidates),
            )
        )
    if isinstance(exc, ModeloWorkRevisionConflictError):
        return typer.BadParameter(
            tr(
                "cli.app.modelo.work.selector_revision_conflict",
                default=(
                    "An active work unit already exists for this modelo/year/period with "
                    "registry revision {existing_revision}; requested {requested_revision}. "
                    "Resume the existing work unit, discard it explicitly, or pass an exact id."
                ),
                existing_revision=exc.existing.revision_id,
                requested_revision=exc.requested_revision_id,
            )
        )
    if isinstance(exc, ModeloCalculationRevisionSelectorAmbiguousError):
        candidates = "\n".join(
            f"{candidate.short_calculation_revision_id}\t{candidate.state.value}\t{candidate.created_at}"
            for candidate in exc.candidates
        )
        return typer.BadParameter(
            tr(
                "cli.app.modelo.work.revision_selector_ambiguous",
                default=(
                    "More than one calculation revision matches this selector. "
                    "Choose one explicitly.\n{candidates}"
                ),
                candidates=candidates,
            )
        )
    if isinstance(exc, ModeloWorkAddressNotFoundError):
        return typer.BadParameter(
            tr(
                "cli.app.modelo.work.selector_not_found",
                default="No active work unit matches this modelo/year/period. Run `aeat app modelo work create` first.",
            )
        )
    return typer.BadParameter(str(exc))


def parse_revision_selector(value: str) -> ModeloCalculationRevisionSelector:
    """Parse a command-line revision selector token."""
    try:
        return ModeloCalculationRevisionSelector(value)
    except ValueError as exc:
        choices = ", ".join(selector.value for selector in ModeloCalculationRevisionSelector)
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_revision_selector",
                default="Unknown revision selector {value!r}; choose one of: {choices}.",
                value=value,
                choices=choices,
            )
        ) from exc


def resolve_default_actor() -> str:
    """Return the active profile display_name, or a permanent fallback label."""
    try:
        from ...application.workflow import workflow_state_repository
        from ...core import resolve_active_bucket_id

        state = workflow_state_repository().load()
        record = state.active_profile_record()
        if record is not None and record.display_name:
            return record.display_name
        active = resolve_active_bucket_id()
        if active:
            return active
    except Exception:
        _log.debug("default actor lookup failed; falling back to operator label", exc_info=True)
    return "operator"


__all__ = [
    "bad_parameter_from_error",
    "bad_parameter_from_localized_context",
    "calculation_revision_not_found_bad_parameter",
    "parse_revision_selector",
    "resolve_default_actor",
    "selector_bad_parameter",
    "validate_calculation_revision_id",
    "validate_work_unit_id",
    "work_candidate_lines",
]
