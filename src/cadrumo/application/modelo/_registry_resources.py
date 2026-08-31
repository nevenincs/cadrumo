"""Registry path and work-unit guards shared by modelo application actions.

Modelo application services access the packaged registry through the canonical
:func:`~cadrumo.domain.calculations.registry.authority.bundled_authority`.
This module owns the bundled ``registry/aeat`` path projection used in
application errors and the work-unit revision/period guards.

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

from pathlib import Path

from ...core import Period
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.ids import RevisionId
from ...domain.modelos.errors import ModeloError


def registry_root() -> Path:
    """Return the bundled ``registry/aeat`` root used by modelo services.

    The returned :class:`~pathlib.Path` is the path passed to registry-facing
    errors when the packaged registry cannot be loaded. It intentionally mirrors
    the root resolved by the canonical bundled registry authority.
    """
    from ...core.resources import bundled_path

    return bundled_path("registry", "aeat")


def reject_unknown_revision(*, modelo: str, revision_id: RevisionId) -> None:
    """Refuse a work-unit create that names an undeclared revision id.

    The central :class:`ValidatedRegistryAuthority` first resolves the modelo
    definition. If the modelo exists but ``revision_id`` is absent from its
    revision map, this raises :class:`ModeloError` with the available revision
    ids.
    """
    from ...domain.calculations.registry.errors import RegistrySnapshotError

    try:
        modelo_def = bundled_authority().modelo(modelo)
    except RegistrySnapshotError as exc:
        raise ModeloError(str(exc)) from exc
    if revision_id in modelo_def.revisions:
        return
    available = ", ".join(sorted(modelo_def.revisions))
    raise ModeloError(
        f"revision_id {revision_id!r} is not declared on modelo {modelo!r}. Available revisions: {available}",
    )


def reject_unknown_period_for_revision(*, modelo: str, revision_id: RevisionId, period: Period) -> None:
    """Refuse a work-unit create whose :class:`Period` is absent from the revision schedules.

    The guard inspects the named revision's filing schedules and compares the
    caller's ``period.registry_token`` to the declared period tokens. A revision
    with no declared schedule is accepted here; a missing revision is also left
    alone because :func:`reject_unknown_revision` owns that refusal.
    """
    from ...domain.calculations.registry.errors import RegistrySnapshotError
    from ...domain.calculations.registry.period_selector_match import selector_period_matches_request

    try:
        modelo_def = bundled_authority().modelo(modelo)
    except RegistrySnapshotError as exc:
        raise ModeloError(str(exc)) from exc
    revision = modelo_def.revisions.get(revision_id)
    if revision is None:
        return
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
