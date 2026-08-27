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
    :func:`cadrumo.domain.calculations.registry.resolve_revision_constructs`
        Runtime projection of validated construct declarations.
"""

from __future__ import annotations

from collections.abc import Mapping

from ._validate_evidence import EvidenceValidator
from ._validate_helpers import missing_refs as _missing_refs
from ._validate_revision_context import ConstructMemberObject
from .schema import ModeloRevision
from .schema_references import LegalReference, SourceReference

_CONSTRUCT_MEMBER_ATTRS = {
    "casilla": "casilla_ids",
    "formula": "formulas",
    "parameter": "parameters",
    "binding": "bindings",
    "relation": "relations",
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
    member_objects: Mapping[str, Mapping[str, ConstructMemberObject]],
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
    """
    failures: list[str] = []
    for construct in revision.constructs:
        owner = f"construct {construct.id}"
        failures.extend(_missing_refs(scope, owner, construct.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(scope, owner, construct.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(scope, owner, construct.source_refs, "official_source_guidance"))
        construct_legal_refs = set(construct.legal_refs)
        construct_source_refs = set(construct.source_refs)
        for kind, attr in _CONSTRUCT_MEMBER_ATTRS.items():
            known = member_objects[kind]
            for member_id in getattr(construct, attr):
                member = known.get(member_id)
                if member is None:
                    failures.append(f"{scope}: construct {construct.id!r} references unknown {kind} {member_id!r}")
                    continue
                # Every member kind in ``_CONSTRUCT_MEMBER_ATTRS`` declares
                # ``legal_refs`` and ``source_refs`` (verified across all 14
                # kinds' classes: casilla, formula, parameter, binding,
                # relation, export layout,
                # extraction profile, cross-reference, workbook parity
                # reference, verification expectation, application link,
                # deadline window, filing schedule, dependency
                # classification). Direct attribute access, not a
                # ``getattr(..., default=())`` reach-around: a member kind
                # ever added here whose class does NOT declare the field
                # must fail loud, never silently under-count the construct's
                # required grounding.
                member_legal_refs = set(member.legal_refs)
                missing_legal = sorted(member_legal_refs.difference(construct_legal_refs))
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
