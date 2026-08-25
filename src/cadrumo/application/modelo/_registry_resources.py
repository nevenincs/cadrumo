"""Registry resource helpers shared by modelo application actions.

Modelo application services access the packaged registry through the central
:class:`ValidatedRegistryAuthority` exposed by ``resources().modelos.authority``.
This module keeps that access path in one place for work-unit creation,
calculation, verification, import, and comparison code that needs the bundled
``registry/aeat`` tree or its cached authority.

The revision and period guards are create-work-unit checks: they reject user
input that names a modelo revision or filing period the committed registry does
not declare, before a work unit records a law-determined registry identity.

See Also:
    :mod:`cadrumo.core.resources`:
        Owns the packaged resource registry and bundled-path resolution.
    :class:`cadrumo.domain.calculations.registry.ValidatedRegistryAuthority`:
        Loads and validates modelo definitions, then serves registry snapshots.
    :mod:`cadrumo.application.modelo._registry_helpers`:
        Uses this authority helper for import/amendment registry checks.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...core import Period
from ...domain.calculations.registry.ids import RevisionId
from ...domain.modelos import ModeloError

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import ValidatedRegistryAuthority


def registry_root() -> Path:
    """Return the bundled ``registry/aeat`` root used by modelo services.

    The returned :class:`~pathlib.Path` is the path passed to registry-facing
    errors when the packaged registry cannot be loaded. It intentionally mirrors
    the root used by :func:`authority_via_resources`.
    """
    from ...core.resources import bundled_path

    return bundled_path("registry", "aeat")


def authority_via_resources() -> ValidatedRegistryAuthority:
    """Return the central :class:`ValidatedRegistryAuthority` for modelo registry access.

    Callers use this instead of constructing a local authority so calculation,
    verification, import, and create-work-unit paths share the same packaged
    registry cache and source-root configuration.
    """
    from ...core.resources import resources

    return resources().modelos.authority


def reject_unknown_revision(*, modelo: str, revision_id: RevisionId) -> None:
    """Refuse a work-unit create that names an undeclared revision id.

    The central :class:`ValidatedRegistryAuthority` first resolves the modelo
    definition. If the modelo exists but ``revision_id`` is absent from its
    revision map, this raises :class:`ModeloError` with the available revision
    ids.
    """
    from ...domain.calculations.registry.errors import RegistrySnapshotError

    try:
        modelo_def = authority_via_resources().modelo(modelo)
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
        modelo_def = authority_via_resources().modelo(modelo)
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
