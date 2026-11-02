"""Carry a predecessor edition's family dispositions into the edition that follows it.

A delta edition inherits what it does not restate, and a family disposition is
part of what it inherits: an omitted disposition means the predecessor's claim
that the law requires nothing of that family still stands, not that the claim
is missing. The merge follows the same predecessor link the keyed families use,
so one edge answers for every family an edition takes from it.

An edition changes the inherited answer in exactly two ways. It authors its own
disposition for a family, which replaces the inherited one, or it lists the
family in ``family_disposition_removals``, which deletes it. Silence never
deletes, so an edition that populates a family its predecessor declared not
applicable must say so with a removal; the typed revision refuses the
contradiction otherwise.

Inheriting a claim is not new evidence. The inherited entry keeps the reason
and references its stating edition wrote and names that edition in
``inherited_from``; no grade is derived from it.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.modelo_localization import as_toml_array
from dev.registry.compiler._toml_helpers import as_toml_table as _as_toml_table

from .loader_fields import _DISPOSITION_REMOVALS_FIELD, _DISPOSITIONS_FIELD, _ROW_INHERITED_FROM_FIELD


def refuse_authored_disposition_markers(source_path: Path, raw_revisions: Mapping[str, object]) -> None:
    """Refuse a disposition that authors ``inherited_from``, which only the merge may set.

    Raises:
        RegistryLoadError: When any edition's authored disposition names the marker.
    """
    for revision_id, raw_revision in raw_revisions.items():
        table = _as_toml_table(raw_revision)
        if table is None:
            continue
        for family, entry in (_as_toml_table(table.get(_DISPOSITIONS_FIELD)) or {}).items():
            entry_table = _as_toml_table(entry)
            if entry_table is not None and _ROW_INHERITED_FROM_FIELD in entry_table:
                raise RegistryLoadError(
                    f"{source_path}: revision {revision_id!r} family disposition {family!r} authors "
                    f"{_ROW_INHERITED_FROM_FIELD}, which the loader sets on the dispositions an edition inherits "
                    "from its predecessor; remove it",
                )


def refuse_removals_without_predecessor(source_path: Path, raw_revisions: Mapping[str, object]) -> None:
    """Refuse a removal in a modelo none of whose editions inherits anything.

    Raises:
        RegistryLoadError: When any edition lists a disposition removal.
    """
    for revision_id, raw_revision in raw_revisions.items():
        table = _as_toml_table(raw_revision)
        if table is not None and _removed_families(table):
            raise RegistryLoadError(
                f"{source_path}: revision {revision_id!r} removes family dispositions "
                f"{sorted(_removed_families(table))!r} but inherits none from any predecessor",
            )


def inherit_family_dispositions(
    context: str,
    *,
    baseline_id: str | None,
    predecessor: Mapping[str, object] | None,
    successor: Mapping[str, object],
) -> dict[str, object]:
    """Return the edition's effective dispositions, family to raw declaration.

    The result is the predecessor's effective dispositions, less the families the
    edition removes, overlaid by the dispositions it authors.

    Args:
        context: Locator prefix for refusals.
        baseline_id: The edition the families resolve against, or ``None``.
        predecessor: That edition's materialised table, or ``None`` with no baseline.
        successor: The edition's own authored table.

    Raises:
        RegistryLoadError: When a removal names a family the edition does not
            inherit, repeats a family, or names a family the edition also authors.
    """
    authored = _as_toml_table(successor.get(_DISPOSITIONS_FIELD)) or {}
    inherited = _inheritable(baseline_id, predecessor)
    removals = _removed_families(successor)
    _refuse_invalid_removals(context, removals=removals, inherited=inherited, authored=authored)
    effective: dict[str, object] = {}
    for family, entry in inherited.items():
        if family in removals or family in authored:
            continue
        effective[family] = entry
    effective.update(authored)
    return effective


def _inheritable(baseline_id: str | None, predecessor: Mapping[str, object] | None) -> dict[str, object]:
    if baseline_id is None or predecessor is None:
        return {}
    inherited: dict[str, object] = {}
    for family, entry in (_as_toml_table(predecessor.get(_DISPOSITIONS_FIELD)) or {}).items():
        entry_table = _as_toml_table(entry)
        if entry_table is None:
            continue
        origin = entry_table.get(_ROW_INHERITED_FROM_FIELD) or baseline_id
        inherited[family] = {**entry_table, _ROW_INHERITED_FROM_FIELD: origin}
    return inherited


def _removed_families(table: Mapping[str, object]) -> list[str]:
    removals = as_toml_array(table.get(_DISPOSITION_REMOVALS_FIELD, ())) or ()
    return [removal for removal in removals if isinstance(removal, str)]


def _refuse_invalid_removals(
    context: str,
    *,
    removals: list[str],
    inherited: Mapping[str, object],
    authored: Mapping[str, object],
) -> None:
    seen: set[str] = set()
    for family in removals:
        if family in seen:
            raise RegistryLoadError(f"{context}: family disposition {family!r} is removed more than once")
        seen.add(family)
        if family in authored:
            raise RegistryLoadError(
                f"{context}: family disposition {family!r} is both removed and authored; keep the authored "
                "disposition, which already replaces the inherited one, or drop the removal",
            )
        if family not in inherited:
            raise RegistryLoadError(
                f"{context}: family disposition {family!r} is removed but not inherited from the predecessor; "
                "a removal deletes only an inherited disposition",
            )
