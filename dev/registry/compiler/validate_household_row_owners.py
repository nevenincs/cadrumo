"""Check that the form and group the registry names as owner of a profile row object's repeat limit cap that object.

The registry names one form and one layout group per stored profile row object. A reader
takes the object's repeat limit from that group alone, so the build refuses an owner that
is not a declared form, that no revision reads the object through, or whose layout leaves a
reading revision without the named group reading the object and declaring a limit. A tree in
which no revision reads the object cannot judge its owner, so an owner form that tree does not
hold is refused only where the tree reads the object: an isolated candidate of one other
modelo carries the shared facts without the owning form.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, governed_facts_in_scope
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.profile_row_limits import (
    RowLimitOwner,
    repeating_group,
    row_limit_owners,
    row_reading_binding_ids,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision

from . import fact_providers

_OWNERS_FACT = "household-row-limit-owners"


def household_row_owner_failures(modelos: Iterable[ModeloDefinition], owners: Mapping[str, RowLimitOwner]) -> list[str]:
    """Return failures for each named row-limit owner whose layout does not cap the object it owns."""
    by_id = {str(modelo.id): modelo for modelo in modelos}
    failures: list[str] = []
    for object_path, owner in owners.items():
        modelo = by_id.get(owner.form)
        if modelo is None:
            if _object_is_read(by_id.values(), object_path):
                failures.append(f"row object {object_path!r} names owner {owner.form!r}, which is not a declared form")
            continue
        failures.extend(_owner_failures(modelo, object_path, owner))
    return failures


def _object_is_read(modelos: Iterable[ModeloDefinition], object_path: str) -> bool:
    return any(
        row_reading_binding_ids(revision, object_path)
        for candidate in modelos
        for revision in candidate.revisions.values()
    )


def _owner_failures(modelo: ModeloDefinition, object_path: str, owner: RowLimitOwner) -> list[str]:
    failures: list[str] = []
    reading_revisions = 0
    for revision_id, revision in modelo.revisions.items():
        reading = row_reading_binding_ids(revision, object_path)
        if not reading:
            continue
        reading_revisions += 1
        prefix = f"modelo {owner.form} revision {revision_id} row object {object_path!r}"
        failures.extend(_revision_owner_failures(revision, owner, reading, prefix))
    if not reading_revisions:
        failures.append(f"modelo {owner.form} owns the row limit of {object_path!r} but no revision reads it")
    return failures


def _revision_owner_failures(
    revision: ModeloRevision, owner: RowLimitOwner, reading: frozenset[BindingId], prefix: str
) -> list[str]:
    groups = [repeating_group(layout, owner.group_id) for layout in revision.form_layouts]
    capped = [group for group in groups if group is not None and group.binding_id in reading]
    if not capped:
        return [f"{prefix}: no layout has the repeating group {owner.group_id!r} reading the object"]
    if any(group.max_rows is None for group in capped):
        return [f"{prefix}: repeating group {owner.group_id!r} declares no repeat limit"]
    return []


def validate_household_row_owners(modelos: Iterable[ModeloDefinition]) -> tuple[str, ...]:
    """Return failures for row-limit owners the registry names but whose layouts do not cap the object."""
    authority = governed_facts_in_scope()
    if authority is None:
        return ()
    if (
        isinstance(authority, CandidateFactAuthority)
        and not fact_providers.FACT_PROVIDER_REGISTRATIONS
        and _OWNERS_FACT not in authority.catalogue.facts
    ):
        # A provider-free partial candidate may omit the entire family.
        return ()
    return tuple(household_row_owner_failures(modelos, row_limit_owners()))


__all__ = ["household_row_owner_failures", "validate_household_row_owners"]
