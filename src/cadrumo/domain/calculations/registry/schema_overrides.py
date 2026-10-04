"""Typed declarations for sparse predecessor storage overrides."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from pydantic import Field, model_validator

from ....core.casilla_id import CasillaId
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.frozen_mapping import FROZEN_MAPPING
from .errors import RegistryValidationError
from .ids import RevisionId
from .schema_base import LegalRefs, RegistryModel, SourceRefs
from .schema_surfaces import CasillaConstraints, CasillaDefinition

__all__ = [
    "CasillaFieldOverride",
    "CasillaMemberPosition",
    "CasillaMemberRemoval",
    "CasillaStorageSelector",
    "FamilyFieldOverride",
    "FamilyMemberPosition",
    "FamilyMemberRemoval",
    "FamilyStorageSelector",
    "SchemaFamilyDispositionDeclaration",
]


class SchemaFamilyDispositionDeclaration(RegistryModel):
    """A revision's declared reason that one of its schema families does not apply.

    The only way an empty family reads as anything but
    :attr:`RegistrySchemaFamilyDisposition.BLOCKED_PENDING_EVIDENCE`, and it is
    deliberately expensive to make: a substantive claim about what the law does
    not require of this modelo, so it carries a reason somebody wrote and the
    references it stands on.

    The alternative — an allowlist of families permitted to be empty — was
    rejected as the shape of the problem rather than its solution. An allowlist
    entry records that somebody wanted the check quiet; this records what they
    claim and what backs it, which is the thing a later reviewer can disagree
    with.
    """

    reason: str = Field(min_length=1, max_length=1024)
    legal_refs: LegalRefs
    source_refs: SourceRefs


class CasillaStorageSelector(RegistryModel):
    """Unambiguous address of one effective casilla in a declared predecessor.

    This selector is storage identity only.  It neither declares nor implies
    legal continuity between the selected member and the successor edition.
    """

    revision: str
    id: CasillaId


class CasillaFieldOverride(RegistryModel):
    """Typed declaration of fields changed from one predecessor casilla."""

    selector: CasillaStorageSelector
    fields: Annotated[Mapping[str, object], FROZEN_MAPPING] = Field(default_factory=dict)
    removed_fields: tuple[str, ...] = ()
    restate_provenance: bool = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_patch(self) -> CasillaFieldOverride:
        patchable = set(CasillaDefinition.model_fields) | {"additional_source_refs"}
        constraint_patchable = set(CasillaConstraints.model_fields) | {"additional_source_refs"}
        _require_well_formed_removed_fields(self.removed_fields)
        _require_known_casilla_fields(self.fields, self.removed_fields, patchable, constraint_patchable)
        _require_nonoverlapping_casilla_patch(self.fields, self.removed_fields)
        _require_nonempty_casilla_patch(self.fields, self.removed_fields, self.restate_provenance)
        _require_no_inherited_from_patch(self.fields, self.removed_fields)
        return self


class CasillaMemberRemoval(RegistryModel):
    """Explicitly remove one member inherited from the declared predecessor."""

    selector: CasillaStorageSelector


class CasillaMemberPosition(RegistryModel):
    """Place an effective casilla without restating its payload."""

    id: CasillaId
    position: int = Field(ge=0)


class FamilyStorageSelector(RegistryModel):
    """Address one keyed-family member in the immediate predecessor."""

    revision: RevisionId
    id: str = Field(min_length=1)


class FamilyFieldOverride(RegistryModel):
    """Patch only the changed fields of one inherited keyed-family member."""

    family: str = Field(min_length=1)
    selector: FamilyStorageSelector
    fields: Annotated[Mapping[str, object], FROZEN_MAPPING] = Field(default_factory=dict)
    removed_fields: tuple[str, ...] = ()
    sequence_additions: Annotated[Mapping[str, tuple[object, ...]], FROZEN_MAPPING] = Field(default_factory=dict)
    sequence_removals: Annotated[Mapping[str, tuple[int, ...]], FROZEN_MAPPING] = Field(default_factory=dict)
    sequence_order: Annotated[Mapping[str, tuple[int, ...]], FROZEN_MAPPING] = Field(default_factory=dict)
    restate_identity: bool = False
    replacement_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_patch(self) -> FamilyFieldOverride:
        identity = _require_keyed_family_identity(self.family)
        _require_nonempty_family_patch(self)
        _require_nonoverlapping_family_patch(self.fields, self.removed_fields)
        _require_family_identity_unchanged(identity, self.fields, self.removed_fields)
        _require_valid_family_sequence_paths(self)
        return self


class FamilyMemberRemoval(RegistryModel):
    """Explicitly remove one member inherited from a keyed family."""

    family: str = Field(min_length=1)
    selector: FamilyStorageSelector


class FamilyMemberPosition(RegistryModel):
    """Place one effective keyed-family member without restating its payload."""

    family: str = Field(min_length=1)
    id: str = Field(min_length=1)
    position: int = Field(ge=0)


def _require_well_formed_removed_fields(removed_fields: tuple[str, ...]) -> None:
    malformed = sorted(
        path
        for path in removed_fields
        if not path or any(not segment for segment in path.split(".")) or len(path.split(".")) > 2
    )
    if malformed:
        raise RegistryValidationError(f"casilla field override has malformed removed fields {malformed!r}")


def _require_known_casilla_fields(
    fields: Mapping[str, object],
    removed_fields: tuple[str, ...],
    patchable: set[str],
    constraint_patchable: set[str],
) -> None:
    unknown_removed = {
        path
        for path in removed_fields
        if (
            (len(segments := path.split(".")) == 1 and segments[0] not in patchable)
            or (len(segments) == 2 and (segments[0] != "constraints" or segments[1] not in constraint_patchable))
        )
    }
    unknown = sorted((set(fields) - patchable) | unknown_removed)
    if unknown:
        raise RegistryValidationError(f"casilla field override names unknown fields {unknown!r}")


def _require_nonoverlapping_casilla_patch(fields: Mapping[str, object], removed_fields: tuple[str, ...]) -> None:
    overlap = set(fields) & set(removed_fields)
    constraint_fields = fields.get("constraints")
    for path in removed_fields:
        segments = path.split(".")
        if len(segments) != 2 or segments[0] != "constraints" or "constraints" not in fields:
            continue
        if not isinstance(constraint_fields, Mapping) or segments[1] in constraint_fields:
            overlap.add(path)
    overlap = sorted(overlap)
    if overlap:
        raise RegistryValidationError(f"casilla field override both sets and removes fields {overlap!r}")


def _require_nonempty_casilla_patch(
    fields: Mapping[str, object],
    removed_fields: tuple[str, ...],
    restate_provenance: bool,
) -> None:
    if not fields and not removed_fields and not restate_provenance:
        raise RegistryValidationError("casilla field override must set or remove at least one field")


def _require_no_inherited_from_patch(fields: Mapping[str, object], removed_fields: tuple[str, ...]) -> None:
    if "inherited_from" in fields or any(path.split(".")[0] == "inherited_from" for path in removed_fields):
        raise RegistryValidationError("inherited_from is loader-owned and cannot be overridden")


def _require_keyed_family_identity(family: str) -> str:
    from .keyed_families import family_spec

    spec = family_spec(family)
    if spec is None or not spec.keyed or spec.identity is None:
        raise RegistryValidationError(f"family field override requires an inherited keyed family, got {family!r}")
    return spec.identity


def _require_nonempty_family_patch(override: FamilyFieldOverride) -> None:
    if (
        not override.fields
        and not override.removed_fields
        and not override.sequence_additions
        and not override.sequence_removals
        and not override.sequence_order
        and not override.restate_identity
        and override.replacement_id is None
    ):
        raise RegistryValidationError("family field override must set or remove at least one field")


def _require_nonoverlapping_family_patch(fields: Mapping[str, object], removed_fields: tuple[str, ...]) -> None:
    overlap = sorted(set(fields) & set(removed_fields))
    if overlap:
        raise RegistryValidationError(f"family field override both sets and removes fields {overlap!r}")


def _require_family_identity_unchanged(
    identity: str,
    fields: Mapping[str, object],
    removed_fields: tuple[str, ...],
) -> None:
    if identity in fields or identity in removed_fields:
        raise RegistryValidationError(f"family identity {identity!r} cannot be patched")


def _require_valid_family_sequence_paths(override: FamilyFieldOverride) -> None:
    sequence_paths = set(override.sequence_additions) | set(override.sequence_removals) | set(override.sequence_order)
    if "" in sequence_paths:
        raise RegistryValidationError("family sequence paths must not be empty")
    _require_valid_family_sequence_indices(override)


def _require_valid_family_sequence_indices(override: FamilyFieldOverride) -> None:
    for path, indices in (*override.sequence_removals.items(), *override.sequence_order.items()):
        if any(index < 0 for index in indices) or len(set(indices)) != len(indices):
            raise RegistryValidationError(f"family sequence path {path!r} has invalid indices")
