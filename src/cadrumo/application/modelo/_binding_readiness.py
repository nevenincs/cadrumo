"""Binding-readiness query for the ``bindings list --missing`` surface.

``bindings list`` reports the registry bindings a modelo revision
declares. ``--missing`` narrows that list to the bindings an operator
still owes — the ones not yet resolvable from the workspace's current
state. A binding is resolvable when the active profile already holds the fact
the binding selects (``source = "profile"``). Every other binding —
ledger aggregations, prior-filing pulls, live observations — needs data
the operator has not supplied yet and is therefore *missing*.

This module owns the cross-domain step (registry snapshot + user
profile) so the registry-query CLI stays a thin caller. The revision is
fetched through a :class:`ValidatedRegistryAuthority` given the
requested modelo, year, and period.

See Also:
    :func:`cadrumo.application.modelo._profile_binding.resolve_profile_sourced_bindings`
        Profile binding resolver whose typed binding channels become the
        profile-resolved id set returned here.
    :mod:`cadrumo.application.state_projection`
        Broader modelo readiness projection that reports formula-consumed
        profile/manual bindings for the readiness command.
"""

from __future__ import annotations

from datetime import date

from ...core import Period
from ...core.logging import get_logger
from ...domain.calculations.registry.errors import (
    AmbiguousRevisionSelectionError,
    NoRevisionForPeriodError,
    RegistrySnapshotError,
    RegistryValidationError,
)
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority
from ...domain.calculations.registry.temporal import select_revision_for_year
from ...domain.user_profile.errors import ProfileNotFoundError
from ._profile_binding import profile_resolved_binding_ids, resolve_profile_sourced_bindings
from ._registry_resources import authority_via_resources

_log = get_logger(__name__)


def profile_resolvable_binding_ids(
    *,
    modelo: str,
    bucket_id: str,
    filing_year: int,
    period: Period | None,
    as_of: date | None = None,
    revision_id: RevisionId | None = None,
) -> frozenset[str]:
    """Return binding ids resolvable from the active profile's stored facts.

    Resolves the registry snapshot for ``(modelo, filing_year, period)`` — or,
    when ``period`` is ``None``, the revision covering ``filing_year`` — and
    projects the bucket's user profile onto its ``source = "profile"`` bindings.
    A supplied :class:`Period` must match ``filing_year`` and contributes the
    registry token used at the snapshot boundary. The returned set is the binding
    ids the profile already satisfies.

    Returns an empty set when the snapshot cannot be resolved or the
    bucket has no profile — the caller then treats every binding as missing,
    which is the correct conservative answer.
    """
    authority = authority_via_resources()
    if period is not None and period.filing_year != filing_year:
        raise RegistryValidationError(
            translated_message="errors.error.error_calculations_registry_validation",
            context={"period": str(period), "filing_year": str(filing_year), "period_matches_year": False},
        )
    resolved_period = (
        period.registry_token
        if period is not None
        else _annual_period_for_year(
            authority,
            modelo=modelo,
            filing_year=filing_year,
            as_of=as_of,
        )
    )
    if resolved_period is None:
        return frozenset[str]()
    try:
        snapshot = authority.snapshot(
            modelo,
            filing_year=filing_year,
            period=resolved_period,
            on=as_of,
        )
    except RegistrySnapshotError as exc:
        _log.debug(
            "binding-readiness: registry snapshot unavailable for modelo=%s filing_year=%s period=%s; "
            "treating profile bindings as unresolved (%s: %s)",
            modelo,
            filing_year,
            resolved_period,
            type(exc).__name__,
            exc,
        )
        return frozenset[str]()
    if revision_id is not None and snapshot.revision.id != revision_id:
        _log.debug(
            "binding-readiness: law-determined revision %s does not match supplied revision_id %s "
            "for modelo=%s filing_year=%s period=%s; treating profile bindings as unresolved",
            snapshot.revision.id,
            revision_id,
            modelo,
            filing_year,
            resolved_period,
        )
        return frozenset[str]()
    try:
        result = resolve_profile_sourced_bindings(snapshot, bucket_id=bucket_id)
    except ProfileNotFoundError as exc:
        _log.debug(
            "binding-readiness: active profile unavailable while resolving modelo=%s filing_year=%s period=%s; "
            "treating profile bindings as unresolved (%s: %s)",
            modelo,
            filing_year,
            resolved_period,
            type(exc).__name__,
            exc,
        )
        return frozenset[str]()
    return frozenset(str(binding_id) for binding_id in profile_resolved_binding_ids(result))


def _annual_period_for_year(
    authority: ValidatedRegistryAuthority,
    *,
    modelo: str,
    filing_year: int,
    as_of: date | None = None,
) -> str | None:
    """Return a registry period token a snapshot for ``filing_year`` accepts.

    With no ``--period`` the operator wants the revision covering the
    year. A snapshot still needs a concrete period token; pick the
    first period the covering revision declares so the snapshot
    resolves. The binding *set* is revision-wide, so the period choice
    does not change which bindings the revision declares.

    The shared temporal selector resolves same-year revision windows using
    ``as_of`` before this helper chooses the revision's first legal period.
    """
    try:
        definition = authority.validate_modelo(modelo.strip())
    except (RegistrySnapshotError, RegistryValidationError) as exc:
        _log.debug(
            "binding-readiness: annual period unavailable for modelo=%s filing_year=%s; "
            "treating profile bindings as unresolved (%s: %s)",
            modelo,
            filing_year,
            type(exc).__name__,
            exc,
        )
        return None
    try:
        revision = select_revision_for_year(definition, filing_year=filing_year, on=as_of)
    except NoRevisionForPeriodError:
        return None
    except AmbiguousRevisionSelectionError as exc:
        # A filing year carrying a mid-year AEAT design boundary is covered by more
        # than one revision, so the year-only selector refuses rather than picking.
        # This is a read-only discovery helper whose contract is already "None means
        # undetermined", so it answers the same way it does for a missing revision --
        # but it must CATCH the refusal, because propagating it turns a discovery
        # question into an operator-facing error from a surface that only reports
        # readiness. That is not hypothetical: this helper caught only the
        # missing-revision case, so the first split year would have raised here.
        #
        # The remedy is NOT restated locally. It rides on the raiser, so the log
        # quotes the error rather than composing a second copy that could drift from
        # the selector's own advice.
        _log.debug(
            "binding-readiness: filing_year=%s for modelo=%s is covered by revisions %s, so no "
            "year-only period can be chosen; treating profile bindings as unresolved (%s)",
            filing_year,
            modelo,
            ", ".join(exc.candidate_ids),
            exc,
        )
        return None
    periods = revision.period_selector.periods
    return periods[0] if periods else None


__all__ = ["profile_resolvable_binding_ids"]
