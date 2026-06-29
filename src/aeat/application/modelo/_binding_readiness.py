"""Binding-readiness query for the ``bindings list --missing`` surface.

``bindings list`` reports the registry bindings a modelo revision
declares. ``--missing`` narrows that list to the bindings an operator
still owes — the ones not yet resolvable from the workspace's current
state. A binding is resolvable when it carries its own literal value
(``constant_value``) or when the active profile already holds the fact
the binding selects (``source = "profile"``). Every other binding —
ledger aggregations, prior-filing pulls, live observations — needs data
the operator has not supplied yet and is therefore *missing*.

This module owns the cross-domain step (registry snapshot + user
profile) so the registry-query CLI stays a thin caller. The revision is
fetched through a :class:`ValidatedRegistryAuthority` given the
requested modelo, year, and period.

See Also:
    :func:`aeat.application.modelo._profile_binding.resolve_profile_sourced_bindings`
        Profile binding resolver whose typed binding channels become the
        profile-resolved id set returned here.
    :mod:`aeat.application.state_projection`
        Broader modelo readiness projection that reports formula-consumed
        profile/manual bindings for the readiness command.
"""

from __future__ import annotations

from ...core import Period
from ...core.logging import get_logger
from ...domain.calculations.registry import (
    AmbiguousRevisionSelectionError,
    RegistrySnapshotError,
    RegistryValidationError,
    ValidatedRegistryAuthority,
)
from ...domain.user_profile import ProfileNotFoundError
from ._profile_binding import resolve_profile_sourced_bindings

_log = get_logger(__name__)


def profile_resolvable_binding_ids(
    *,
    modelo: str,
    bucket_id: str,
    filing_year: int,
    period: Period | None,
) -> frozenset[str]:
    """Return binding ids resolvable from the active profile's stored facts.

    Resolves the registry snapshot for ``(modelo, filing_year, period)`` — or,
    when ``period`` is ``None``, the revision covering ``filing_year`` — and
    projects the bucket's user profile onto its ``source = "profile"`` bindings.
    A supplied :class:`Period` must match ``filing_year`` and contributes the
    registry token used at the snapshot boundary. The returned set is the binding
    ids the profile already satisfies; ``constant_value`` bindings are handled
    separately by the caller because they carry a literal value independent of
    any profile.

    Returns an empty set when the snapshot cannot be resolved or the
    bucket has no profile — the caller then treats every non-constant
    binding as missing, which is the correct conservative answer.
    """
    authority = _resources_authority()
    if period is not None and period.year != filing_year:
        raise RegistryValidationError(
            f"binding-readiness period {period} does not match filing year {filing_year}",
        )
    resolved_period = (
        period.registry_token
        if period is not None
        else _annual_period_for_year(
            authority,
            modelo=modelo,
            filing_year=filing_year,
        )
    )
    if resolved_period is None:
        return frozenset()
    try:
        snapshot = authority.snapshot(
            modelo,
            filing_year=filing_year,
            period=resolved_period,
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
        return frozenset()
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
        return frozenset()
    return frozenset(
        set(result.binding_values) | set(result.enum_binding_values) | set(result.date_binding_values),
    )


def _resources_authority() -> ValidatedRegistryAuthority:
    """Return the registry authority via the central resource registry."""
    from ...core.resources import resources

    return resources().modelos.authority


def _annual_period_for_year(authority: ValidatedRegistryAuthority, *, modelo: str, filing_year: int) -> str | None:
    """Return a registry period token a snapshot for ``filing_year`` accepts.

    With no ``--period`` the operator wants the revision covering the
    year. A snapshot still needs a concrete period token; pick the
    first period the covering revision declares so the snapshot
    resolves. The binding *set* is revision-wide, so the period choice
    does not change which bindings the revision declares.

    Raises:
        AmbiguousRevisionSelectionError: When more than one revision covers the
            requested year and no period is available to select between them.
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
    covering = [
        revision for revision in definition.revisions.values() if revision.period_selector.includes_year(filing_year)
    ]
    if not covering:
        return None
    if len(covering) > 1:
        raise AmbiguousRevisionSelectionError(
            modelo_id=str(definition.id),
            candidate_ids=tuple(revision.id for revision in covering),
        )
    revision = covering[0]
    periods = revision.period_selector.periods
    return periods[0] if periods else None


__all__ = ["profile_resolvable_binding_ids"]
