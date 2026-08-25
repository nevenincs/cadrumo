"""One typed finalizer for filed-declaration calculation-history enrollment.

Single, bulk, and source capture all drive their calculation-history enrollment
through :func:`finalize_filed_capture`. The finalizer owns latest-observation
selection, history ordering (delegated to the persistence authority's
:func:`select_latest_filed_observations_in_history_order`), per-observation
registry-grounded persistence, and typed failure accumulation. The caller
chooses the failure policy: fail-fast for single and source capture (a
registry-enrollment failure aborts the operation), best-effort for bulk capture
(failures accumulate into the report and the sweep continues).

Consolidating these into one authority removes the duplicate selector and
persistence loop that capture orchestration previously carried, and guarantees
every route persists the same observations in the same order rather than each
reimplementing selection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from ...adapters.outbound.aeat.sede import (
    FiledDeclaracionObservation,
    SedeParseError,
    non_numeric_observed_casillas,
)
from .errors import LiveApplicationError, LiveApplicationInputError
from .filed_observation_persistence import (
    justificante_csvs_for_observation,
    persist_filed_calculation_observation,
    select_latest_filed_observations_in_history_order,
)
from .remote_state_models import FiledCasillaSkipRow, FiledDataCaptureFailureRow
from .remote_state_outcomes import bounded_context_text


class FiledCaptureFailurePolicy(StrEnum):
    """How a filed-capture finalizer reacts to a registry-enrollment failure."""

    #: Single and source capture: abort the operation on the first failure.
    FAIL_FAST = "fail_fast"
    #: Bulk capture: accumulate failures into the report and keep persisting.
    BEST_EFFORT = "best_effort"


@dataclass(frozen=True)
class FiledCaptureFinalization:
    """Result of finalising a filed-capture batch into calculation history."""

    calculation_observation_keys: tuple[str, ...]
    failures: tuple[FiledDataCaptureFailureRow, ...]
    #: Casillas the filing carries that the Decimal-only registry channel cannot
    #: read. Reported separately from ``failures`` because they are not a failed
    #: capture: the artefact was read correctly and these are what it holds.
    #: Collected whether or not the observation went on to enrol, so an operator
    #: learns which fields of their own return are outside the channel rather
    #: than inferring it from a refusal that names only the first one.
    skipped_casillas: tuple[FiledCasillaSkipRow, ...] = ()


def finalize_filed_capture(
    observations: tuple[FiledDeclaracionObservation, ...],
    *,
    justificante_csvs_by_observation: Mapping[tuple[str, int, str, str], tuple[str, ...]] | None = None,
    policy: FiledCaptureFailurePolicy,
) -> FiledCaptureFinalization:
    """Persist the latest filed observation per period into calculation history.

    Selection and history ordering delegate to the persistence authority, so all
    capture routes agree. Each registry-enrollment failure is accumulated as a
    typed :class:`FiledDataCaptureFailureRow`. Under
    :attr:`FiledCaptureFailurePolicy.FAIL_FAST` any accumulated failure is raised
    as a :class:`LiveApplicationError`; under
    :attr:`FiledCaptureFailurePolicy.BEST_EFFORT` the failures are returned for the
    caller's report.
    """
    keys: list[str] = []
    failures: list[FiledDataCaptureFailureRow] = []
    skips: list[FiledCasillaSkipRow] = []
    for observation in select_latest_filed_observations_in_history_order(observations):
        skips.extend(_filed_casilla_skip_rows(observation))
        try:
            keys.append(
                persist_filed_calculation_observation(
                    observation,
                    justificante_csvs=justificante_csvs_for_observation(
                        observation,
                        justificante_csvs_by_observation,
                    ),
                ),
            )
        except (LiveApplicationInputError, SedeParseError) as exc:
            failures.append(_filed_registry_enrollment_failure_row(observation, exc))
    finalization = FiledCaptureFinalization(tuple(keys), tuple(failures), tuple(skips))
    if policy is FiledCaptureFailurePolicy.FAIL_FAST:
        _raise_registry_enrollment_failure(finalization.failures)
    return finalization


def _filed_casilla_skip_rows(
    observation: FiledDeclaracionObservation,
) -> tuple[FiledCasillaSkipRow, ...]:
    """Project the adapter's skip query onto the report's row shape.

    Collected before enrolment is attempted, and independently of whether it
    succeeds, because the answer does not depend on it: these are casillas the
    filing carries, not casillas the enrolment lost.
    """
    return tuple(
        FiledCasillaSkipRow(
            modelo=observation.modelo,
            year=observation.ejercicio,
            period=observation.period,
            expediente_id=observation.expediente_id,
            casilla_id=skip.casilla_id,
            label=skip.label,
            value_kind=skip.value_kind.value,
            reason=skip.reason,
        )
        for skip in non_numeric_observed_casillas(observation)
    )


def _filed_registry_enrollment_failure_row(
    observation: FiledDeclaracionObservation,
    error: BaseException,
) -> FiledDataCaptureFailureRow:
    return FiledDataCaptureFailureRow(
        modelo=observation.modelo,
        year=observation.ejercicio,
        period=observation.period,
        expediente_id=observation.expediente_id,
        error_type=error.__class__.__name__,
        message=bounded_context_text(error),
    )


def _raise_registry_enrollment_failure(failures: tuple[FiledDataCaptureFailureRow, ...]) -> None:
    if not failures:
        return
    first = failures[0]
    raise LiveApplicationError(
        translated_message="application.live.filed_observations.errors.registry_enrollment_failed",
        context={
            "failed_count": len(failures),
            "modelo": first.modelo,
            "year": first.year,
            "period": first.period.registry_token if first.period is not None else None,
            "expediente_id": first.expediente_id,
            "error_type": first.error_type,
            "message": first.message,
        },
    )


__all__ = [
    "FiledCaptureFailurePolicy",
    "FiledCaptureFinalization",
    "finalize_filed_capture",
]
