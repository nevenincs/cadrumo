"""Registry resource helpers shared by modelo application actions.

All modelo application services access the packaged registry through the
central :class:`ValidatedRegistryAuthority` exposed by
``resources().modelos.authority``. The create-work-unit guards below use that
authority to reject unknown revisions or periods before a work unit records a
law-determined registry identity.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...core import Period
from ...domain.modelos._errors import ModeloError

if TYPE_CHECKING:
    from ...domain.calculations.registry import ValidatedRegistryAuthority


def registry_root() -> Path:
    """Resolve the registry root from the packaged data tree."""
    from ...core.resources import bundled_path

    return bundled_path("registry", "aeat")


def authority_via_resources() -> ValidatedRegistryAuthority:
    """Return the :class:`ValidatedRegistryAuthority` via the central resource registry."""
    from ...core.resources import resources

    return resources().modelos.authority


def reject_unknown_revision(*, modelo: str, revision_id: str) -> None:
    """Refuse a work-unit create that names a revision the registry does not declare."""
    from ...domain.calculations.registry import RegistrySnapshotError

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


def reject_unknown_period_for_revision(*, modelo: str, revision_id: str, period: Period) -> None:
    """Refuse a work-unit create that names a period the revision does not declare."""
    from ...domain.calculations.registry import RegistrySnapshotError

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
    if not declared or period.registry_token in declared:
        return
    available = ", ".join(sorted(declared))
    raise ModeloError(
        f"period {period.registry_token!r} is not declared on modelo {modelo!r} "
        f"revision {revision_id!r}. Available periods: {available}",
    )
