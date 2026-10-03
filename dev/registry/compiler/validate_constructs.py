"""Construct closure validation helpers.

Validates that every construct declared on a
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` has coherent member
references and legal grounding.

Construct member closure compares each member's
:class:`~cadrumo.domain.calculations.registry.LegalReference` and
:class:`~cadrumo.domain.calculations.registry.SourceReference` requirements with the
refs declared by the owning construct.

See Also:
    :func:`cadrumo.domain.calculations.registry.validate_revision_closure._validate_revision_closure_sections`
        Revision-level runner that invokes the validator in this module.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol, runtime_checkable

from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference
from cadrumo.domain.calculations.registry.schema_revision_members import ConstructDefinition

from ._validate_helpers import missing_refs as _missing_refs
from .validate_evidence import EvidenceValidator

__all__ = ["CONSTRUCT_MEMBER_ATTRIBUTES", "validate_construct_closure"]


@runtime_checkable
class _ConstructMember(Protocol):
    """Grounding fields shared by every construct-member schema record."""

    legal_refs: Iterable[str]
    source_refs: Iterable[str]


CONSTRUCT_MEMBER_ATTRIBUTES = {
    "casilla": "casilla_ids",
    "formula": "formulas",
    "parameter": "parameters",
    "binding": "bindings",
    "export layout": "export_layouts",
    "extraction profile": "extraction_profiles",
    "cross-reference": "live_cross_references",
    "workbook parity reference": "workbook_parity_refs",
    "verification expectation": "verification_expectations",
    "application link": "application_links",
    "deadline window": "deadline_windows",
    "filing schedule": "filing_schedules",
    "dependency classification": "dependency_classifications",
}


def validate_construct_closure(
    scope: str,
    revision: ModeloRevision,
    *,
    member_objects: Mapping[str, Mapping[str, object]],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    """Return construct member and grounding failures for one revision.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    construct declarations; ``member_objects`` is the prebuilt member index from
    the revision validation context. Each member's legal/source refs must be
    included by the construct that claims it, and
    :class:`~cadrumo.domain.calculations.registry.validate_evidence.EvidenceValidator`
    enforces official-source grounding for the construct itself.

    ``member_objects`` values are typed ``object`` here rather than the closed
    :class:`~cadrumo.domain.calculations.registry._validate_revision_context.ConstructMemberObject`
    union its real caller narrows to: the production caller always supplies
    that narrower, already-validated mapping (a narrower argument fits a wider
    parameter), and the direct ``member.legal_refs`` / ``member.source_refs``
    reads below -- never a tolerant ``getattr(..., default=())`` -- are what
    actually enforces the contract, raising ``AttributeError`` loud on a member
    that does not carry them. Narrowing this parameter back to the closed union
    would just move that same runtime guarantee out of reach of a caller
    proving it, not strengthen it.
    """
    failures: list[str] = []
    for construct in revision.constructs:
        failures.extend(_construct_grounding_failures(scope, construct, legal_refs, source_refs, evidence))
        failures.extend(_construct_member_failures(scope, construct, member_objects))
    return failures


def _construct_grounding_failures(
    scope: str,
    construct: ConstructDefinition,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    owner = f"construct {construct.id}"
    failures = _missing_refs(scope, owner, construct.legal_refs, legal_refs, "legal")
    failures.extend(_missing_refs(scope, owner, construct.source_refs, source_refs, "source"))
    failures.extend(evidence.require_source_tier(scope, owner, construct.source_refs, "official_source_guidance"))
    return failures


def _construct_member_failures(
    scope: str,
    construct: ConstructDefinition,
    member_objects: Mapping[str, Mapping[str, object]],
) -> list[str]:
    failures: list[str] = []
    construct_legal_refs = set(construct.legal_refs)
    construct_source_refs = set(construct.source_refs)
    for kind, attr in CONSTRUCT_MEMBER_ATTRIBUTES.items():
        known = member_objects[kind]
        for member_id in getattr(construct, attr):
            member = known.get(member_id)
            if member is None:
                failures.append(f"{scope}: construct {construct.id!r} references unknown {kind} {member_id!r}")
                continue
            if not isinstance(member, _ConstructMember):
                raise AttributeError(f"{kind} {member_id!r} does not expose legal_refs and source_refs")
            failures.extend(
                _construct_member_grounding_failures(
                    scope,
                    construct,
                    kind,
                    member_id,
                    member,
                    construct_legal_refs,
                    construct_source_refs,
                )
            )
    return failures


def _construct_member_grounding_failures(
    scope: str,
    construct: ConstructDefinition,
    kind: str,
    member_id: str,
    member: _ConstructMember,
    construct_legal_refs: set[str],
    construct_source_refs: set[str],
) -> list[str]:
    # Every member kind in ``CONSTRUCT_MEMBER_ATTRIBUTES`` declares both refs.
    # Reading them directly preserves loud refusal if a future member drops
    # either required grounding field.
    member_legal_refs = set(member.legal_refs)
    missing_legal = sorted(member_legal_refs.difference(construct_legal_refs))
    failures: list[str] = []
    if missing_legal:
        failures.append(
            f"{scope}: construct {construct.id!r} does not include legal refs "
            f"{missing_legal!r} required by {kind} {member_id!r}",
        )
    member_source_refs = set(member.source_refs)
    missing_sources = sorted(member_source_refs.difference(construct_source_refs))
    if missing_sources:
        failures.append(
            f"{scope}: construct {construct.id!r} does not include source refs "
            f"{missing_sources!r} required by {kind} {member_id!r}",
        )
    return failures
