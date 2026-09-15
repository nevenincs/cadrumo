"""Generic schedule-attestation mechanics for registry-selected declarations."""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.schema import ModeloRevision


# Registry authority: M111 schedule and applicability are consumed through the pinned operation
def _registry_no_retenciones_periods(
    revision: ModeloRevision | None = None,
    *,
    modelo: str | None = None,
    filing_year: int | None = None,
    period_token: str | None = None,
    operation: PinnedAuthorityOperation,
) -> frozenset[tuple[int, str]]:
    """Resolve a declared filing period through selected registry declarations.

    The public describe query selects the revision for the full filing scope;
    its isolated snapshot then supplies the schedule and applicability
    declarations. Missing, malformed, or divergent declarations return an
    empty set, so no no-retenciones period is inferred from profile input.
    """
    if modelo is None or filing_year is None or period_token is None:
        return frozenset[tuple[int, str]]()
    try:
        selected_revision = operation.revision_for_context(
            modelo,
            filing_year=filing_year,
            period=period_token,
        )
        if revision is not None and str(selected_revision.id) != str(revision.id):
            return frozenset[tuple[int, str]]()
        snapshot = operation.snapshot(
            modelo,
            filing_year=filing_year,
            period=period_token,
            revision_id=selected_revision.id,
        )
    except (RegistrySnapshotError, RegistryValidationError):
        return frozenset[tuple[int, str]]()
    if str(snapshot.revision.id) != str(selected_revision.id):
        return frozenset[tuple[int, str]]()
    schedules = tuple(snapshot.filing_schedules.values())
    if not schedules or not any(period_token in schedule.periods for schedule in schedules):
        return frozenset[tuple[int, str]]()
    if not snapshot.revision.applicability:
        return frozenset[tuple[int, str]]()
    return frozenset({(filing_year, period_token)})


def parse_m111_no_retenciones_periods(
    raw: str | None,
    *,
    modelo: str | None = None,
    filing_year: int | None = None,
    period_token: str | None = None,
    revision: ModeloRevision | None = None,
    operation: PinnedAuthorityOperation,
) -> frozenset[tuple[int, str]]:
    """Resolve schedule-attestation periods through registry authority."""
    del raw
    return _registry_no_retenciones_periods(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
        operation=operation,
    )


def m111_no_retenciones_periods_from_profile_values(
    values: Mapping[str, str] | None,
    *,
    modelo: str | None = None,
    filing_year: int | None = None,
    period_token: str | None = None,
    revision: ModeloRevision | None = None,
    operation: PinnedAuthorityOperation,
) -> frozenset[tuple[int, str]]:
    """Resolve schedule-attestation periods through registry authority."""
    del values
    return _registry_no_retenciones_periods(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
        operation=operation,
    )


def m111_no_retenciones_periods_for_bucket(
    bucket_id: str,
    *,
    modelo: str | None = None,
    filing_year: int | None = None,
    period_token: str | None = None,
    revision: ModeloRevision | None = None,
    operation: PinnedAuthorityOperation,
) -> frozenset[tuple[int, str]]:
    """Resolve a bucket's periods only when its modelo scope is explicit.

    A bucket identifier is storage identity, not a modelo selector. Callers
    that do not provide the selected modelo therefore receive no periods
    rather than having the bucket value interpreted as a registry identity.
    """
    del bucket_id
    return _registry_no_retenciones_periods(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period_token=period_token,
        operation=operation,
    )


def is_m111_no_retenciones_period(
    *,
    source_modelo: str,
    filing_year: int,
    period_token: str,
    attested_periods: frozenset[tuple[int, str]],
    operation: PinnedAuthorityOperation,
) -> bool:
    """Resolve whether a source period is covered by registry schedule data."""
    if (filing_year, period_token) not in attested_periods:
        return False
    return (filing_year, period_token) in _registry_no_retenciones_periods(
        modelo=source_modelo,
        filing_year=filing_year,
        period_token=period_token,
        operation=operation,
    )


__all__ = [
    "is_m111_no_retenciones_period",
    "m111_no_retenciones_periods_for_bucket",
    "m111_no_retenciones_periods_from_profile_values",
    "parse_m111_no_retenciones_periods",
]
