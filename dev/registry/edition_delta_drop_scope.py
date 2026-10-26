"""The keyed families and baseline rules admitted by restatement dropping."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from cadrumo.domain.calculations.registry.keyed_families import (
    CASILLAS_FAMILY,
    DROPPABLE_FAMILY_SPECS,
    HELD_BACK_FAMILY_REASONS,
)


@dataclass(frozen=True, slots=True)
class _DroppableFamily:
    """One family whose restated members a successor edition may stop declaring.

    ``section`` is the table key and the fragment directory, ``identity`` the
    field naming the same member across editions, and ``identity_fields`` the
    fields that carry what the member IS rather than what it declares. A stated
    member whose identity field differs from the inherited one is a divergence,
    never a restatement: dropping it would silently change the member the
    edition holds, so it is always kept.
    """

    section: str
    identity: str
    identity_fields: tuple[str, ...] = ()


_DROPPABLE_FAMILIES: Final[tuple[_DroppableFamily, ...]] = tuple(
    _DroppableFamily(
        section=spec.section,
        identity=spec.identity,
        identity_fields=spec.identity_fields,
    )
    for spec in DROPPABLE_FAMILY_SPECS
    if spec.identity is not None
)

_HELD_BACK_FAMILIES: Final[Mapping[str, str]] = HELD_BACK_FAMILY_REASONS

_NEVER_STRIPPED_SCALARS: Final[frozenset[str]] = frozenset({"orden_aplicabilidad", "casilla_source_refs"})


def _family_storage_baseline(manifest: Mapping[str, object], section: str) -> str | None:
    """The edition a family's stated members inherit from, or ``None`` when the family inherits nothing.

    A storage baseline names the payload ancestry a family is stored against,
    independently of the edition's legal ``predecessor``; an explicit
    no-predecessor root can still store a family against an earlier edition's
    payload. Without a baseline the family inherits from the named predecessor.
    """
    key = "casilla_storage_baseline" if section == CASILLAS_FAMILY else "family_storage_baseline"
    baseline = manifest.get(key)
    if isinstance(baseline, str):
        return baseline
    return _declared_predecessor(manifest)


def _declared_predecessor(manifest: Mapping[str, object]) -> str | None:
    """The predecessor this edition names, or ``None`` for a root or an undeclared edition.

    A ``predecessor`` table rather than a string is the explicit no-predecessor
    root declaration. It inherits nothing, so it has no restatement to drop.
    """
    declared = manifest.get("predecessor")
    return declared if isinstance(declared, str) else None
