"""Registry-backed work-unit guards shared by modelo application actions.

Modelo application services access the packaged registry through one
generation-pinned indexed operation. This module owns work-unit revision and
period guards.

The revision and period guards are create-work-unit checks: they reject user
input that names a modelo revision or filing period the committed registry does
not declare, before a work unit records a law-determined registry identity.

See Also:
    :mod:`cadrumo.core.resources`:
        Owns the packaged resource registry and bundled-path resolution.
    :class:`cadrumo.domain.calculations.registry.ValidatedRegistryAuthority`:
        Loads and validates modelo definitions, then serves registry snapshots.
    :mod:`cadrumo.application.modelo._registry_helpers`:
        Owns import/amendment registry checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.period import Period
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.ids import RevisionId
from ...domain.modelos.errors import ModeloError

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def reject_unknown_revision(
    *,
    modelo: str,
    revision_id: RevisionId,
    operation: PinnedAuthorityOperation | None = None,
) -> None:
    """Refuse a work-unit create that names an undeclared revision id.

    The central :class:`ValidatedRegistryAuthority` first resolves the modelo
    definition. If the modelo exists but ``revision_id`` is absent from its
    revision map, this raises :class:`ModeloError` with the available revision
    ids.
    """
    from ...domain.calculations.registry.errors import RegistrySnapshotError

    try:
        if operation is not None:
            revisions = operation.modelo_directory(modelo).revisions
        else:
            with bundled_indexed_authority().operation() as indexed_operation:
                return reject_unknown_revision(modelo=modelo, revision_id=revision_id, operation=indexed_operation)
    except (RegistrySnapshotError, ValueError) as exc:
        raise ModeloError(str(exc)) from exc
    if any(revision.id == revision_id for revision in revisions):
        return
    available = ", ".join(sorted(str(revision.id) for revision in revisions))
    raise ModeloError(
        f"revision_id {revision_id!r} is not declared on modelo {modelo!r}. Available revisions: {available}",
    )


def reject_unknown_period_for_revision(
    *,
    modelo: str,
    revision_id: RevisionId,
    period: Period,
    operation: PinnedAuthorityOperation | None = None,
) -> None:
    """Refuse a work-unit create whose :class:`Period` is absent from the revision schedules.

    The guard inspects the named revision's filing schedules and compares the
    caller's ``period.registry_token`` to the declared period tokens. A revision
    with no declared schedule is accepted here; a missing revision is also left
    alone because :func:`reject_unknown_revision` owns that refusal.
    """
    from ...domain.calculations.registry.errors import RegistrySnapshotError
    from ...domain.calculations.registry.period_selector_match import selector_period_matches_request

    try:
        if operation is not None:
            revision = operation.revision(modelo, str(revision_id))
        else:
            with bundled_indexed_authority().operation() as indexed_operation:
                return reject_unknown_period_for_revision(
                    modelo=modelo,
                    revision_id=revision_id,
                    period=period,
                    operation=indexed_operation,
                )
    except (RegistrySnapshotError, ValueError) as exc:
        raise ModeloError(str(exc)) from exc
    declared: set[str] = set()
    for schedule in revision.filing_schedules:
        declared.update(schedule.periods)
    if not declared or any(selector_period_matches_request(token, period.registry_token) for token in declared):
        return
    available = ", ".join(sorted(declared))
    raise ModeloError(
        f"period {period.registry_token!r} is not declared on modelo {modelo!r} "
        f"revision {revision_id!r}. Available periods: {available}",
    )
