"""Typed, edge-local attestations for registry lineage.

An attestation is the small piece of authored evidence that lets a later
revision carry one family member from its exact predecessor.  It is kept
separate from the revision's materialised declarations so a compiler can
strip inherited rows without losing the decision that made the inheritance
safe.

This module deliberately contains no registry loading or family dispatch.  A
loader integration supplies the already-selected predecessor relation and a
membership index from the canonical revisions, then calls
:func:`validate_lineage_attestations` before publishing its snapshot.  Raw
TOML, display numbers, and labels cannot satisfy that validation on their own.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from typing import Annotated

from pydantic import Field, model_validator

from ....core.identity.continuidad import ContinuidadId
from .casilla_lineage import CasillaLineageOriginField
from .errors import RegistryValidationError
from .ids import RevisionId
from .schema_base import LegalRefs, RegistryModel, SourceRefs

__all__ = [
    "LineageAttestation",
    "LineageAttestationSet",
    "LineageFamilyId",
    "LineageMemberId",
    "RevisionFamilyMembers",
    "validate_lineage_attestations",
]


type LineageFamilyId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$",
    ),
]
"""A stable lower-snake-case family name used by a lineage attestation."""


type LineageMemberId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:+-]*$",
    ),
]
"""A family member identity, never a display number or a translated label."""


type RevisionFamilyMembers = Mapping[str, Mapping[str, Collection[str]]]
"""Revision -> family -> stable member identities used by the pure validator.

The caller builds this index from the canonical, validated revision snapshot.
For a casilla family, the collection contains ``continuidad_id`` values; for
an identifier-keyed family it contains that family's declared ``id``.  Keeping
this meaning at the adapter boundary lets this module remain independent of
family dispatch and of revision loader internals.
"""


class LineageAttestation(RegistryModel):
    """One grounded continuation across one exact predecessor edge.

    Exactly one of ``member`` and ``continuidad_id`` is the stable family
    identity used by the inheritance policy.  Identifier-keyed families use
    ``member``; the casilla family uses ``continuidad_id``.  Keeping the two
    alternatives explicit prevents a revision-local id and a cross-revision
    chain id from being silently conflated.

    Origins that describe absence (``new_on_form``, ``not_on_form``, and
    ``predecessor_edition_silent``) do not belong in this sidecar: they have no
    predecessor edge to attest.  They remain ordinary row declarations.
    """

    family: LineageFamilyId
    member: LineageMemberId | None = None
    continuidad_id: ContinuidadId | None = None
    from_revision: RevisionId
    to_revision: RevisionId
    origin: CasillaLineageOriginField
    evidence: str | None = Field(default=None, min_length=1, max_length=1024)
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @model_validator(mode="after")
    def _validate_attestation_shape(self) -> LineageAttestation:
        """Enforce the row-local continuation and grounding contract."""
        if (self.member is None) == (self.continuidad_id is None):
            raise RegistryValidationError(
                f"lineage attestation {self.family!r} must declare exactly one of "
                "member or continuidad_id as its family identity",
            )
        if self.from_revision == self.to_revision:
            raise RegistryValidationError(
                f"lineage attestation {self.family!r}/{self.identity!r} must span two "
                "different revisions",
            )
        if not self.origin.continues_a_chain:
            raise RegistryValidationError(
                f"lineage attestation {self.family!r}/{self.identity!r} cannot use "
                f"absence origin {self.origin.value!r}",
            )
        if self.origin.requires_evidence and self.evidence is None:
            raise RegistryValidationError(
                f"lineage attestation {self.family!r}/{self.identity!r} with origin "
                f"{self.origin.value!r} must declare evidence",
            )
        if self.evidence is not None and not self.evidence.strip():
            raise RegistryValidationError(
                f"lineage attestation {self.family!r}/{self.identity!r} evidence must "
                "be non-empty",
            )
        return self

    @property
    def identity(self) -> str:
        """Return the one canonical family identity carried by this attestation."""
        if self.member is not None:
            return self.member
        if self.continuidad_id is not None:
            return str(self.continuidad_id)
        raise RegistryValidationError(
            f"lineage attestation {self.family!r} has no family identity",
        )

    def target_key(self) -> tuple[str, str, str]:
        """Return the unique family/identity key at the target revision."""
        return (self.family, self.identity, self.to_revision)


class LineageAttestationSet(RegistryModel):
    """A typed sidecar payload whose target attestations are unique."""

    attestations: tuple[LineageAttestation, ...] = ()

    @model_validator(mode="after")
    def _validate_unique_targets(self) -> LineageAttestationSet:
        _validate_unique_targets(self.attestations)
        return self


def _validate_unique_targets(attestations: Iterable[LineageAttestation]) -> tuple[LineageAttestation, ...]:
    """Reject duplicate or conflicting target identities in one sidecar."""
    materialized = tuple(attestations)
    seen_targets: set[tuple[str, str, str]] = set()

    for attestation in materialized:
        target_key = attestation.target_key()
        if target_key in seen_targets:
            raise RegistryValidationError(
                f"lineage sidecar declares duplicate or many-to-one target identity "
                f"{target_key!r}",
            )
        seen_targets.add(target_key)

    return materialized


def _members_for(
    members_by_revision: RevisionFamilyMembers,
    *,
    revision: str,
    family: str,
    side: str,
) -> frozenset[str]:
    """Read one validated revision/family membership set with typed failures."""
    revision_members = members_by_revision.get(revision)
    if revision_members is None:
        raise RegistryValidationError(
            f"lineage attestation references {side} revision {revision!r}, but the "
            "canonical membership index does not declare it",
        )
    family_members = revision_members.get(family)
    if family_members is None:
        raise RegistryValidationError(
            f"lineage attestation references family {family!r} in {side} revision "
            f"{revision!r}, but that family is not declared",
        )
    if isinstance(family_members, (str, bytes)):
        raise RegistryValidationError(
            f"lineage membership index for {family!r}/{revision!r} must be a "
            "collection of member identities, not a scalar",
        )
    if any(not isinstance(member, str) for member in family_members):
        raise RegistryValidationError(
            f"lineage membership index for {family!r}/{revision!r} contains a "
            "non-string member identity",
        )
    return frozenset(family_members)


def validate_lineage_attestations(
    attestations: Iterable[LineageAttestation],
    *,
    predecessors: Mapping[str, str],
    members_by_revision: RevisionFamilyMembers,
) -> tuple[LineageAttestation, ...]:
    """Validate sidecar attestations against a canonical revision snapshot.

    The function is pure: it returns the same authored order and does not
    load, mutate, or materialise registry declarations.  Every target must be
    present in the target revision and in its exact predecessor revision, and
    the declared edge must equal the canonical predecessor relation.  This
    catches stale sidecar rows as well as duplicate and many-to-one identity
    claims before a loader publishes a snapshot.

    Args:
        attestations: Authored edge-local continuation statements.
        predecessors: Canonical ``to_revision -> from_revision`` relation.
        members_by_revision: Canonical ``revision -> family -> members`` index.

    Raises:
        RegistryValidationError: If an attestation is stale, is on the wrong
            edge, or conflicts with another attestation.
    """
    if not isinstance(predecessors, Mapping):
        raise RegistryValidationError("lineage predecessor index must be a mapping")
    if not isinstance(members_by_revision, Mapping):
        raise RegistryValidationError("lineage membership index must be a mapping")

    materialized = _validate_unique_targets(attestations)
    for attestation in materialized:
        expected_predecessor = predecessors.get(attestation.to_revision)
        if expected_predecessor is None:
            raise RegistryValidationError(
                f"lineage attestation {attestation.family!r}/{attestation.identity!r} "
                f"targets revision {attestation.to_revision!r}, which has no declared "
                "predecessor edge",
            )
        if expected_predecessor != attestation.from_revision:
            raise RegistryValidationError(
                f"lineage attestation {attestation.family!r}/{attestation.identity!r} "
                f"declares {attestation.from_revision!r} -> {attestation.to_revision!r}, "
                f"but the canonical predecessor is {expected_predecessor!r} -> "
                f"{attestation.to_revision!r}",
            )

        predecessor_members = _members_for(
            members_by_revision,
            revision=attestation.from_revision,
            family=attestation.family,
            side="predecessor",
        )
        if attestation.identity not in predecessor_members:
            raise RegistryValidationError(
                f"lineage attestation {attestation.family!r}/{attestation.identity!r} is "
                f"stale: member is absent from predecessor revision "
                f"{attestation.from_revision!r}",
            )

        target_members = _members_for(
            members_by_revision,
            revision=attestation.to_revision,
            family=attestation.family,
            side="target",
        )
        if attestation.identity not in target_members:
            raise RegistryValidationError(
                f"lineage attestation {attestation.family!r}/{attestation.identity!r} is "
                f"stale: member is absent from target revision {attestation.to_revision!r}",
            )

    return materialized
