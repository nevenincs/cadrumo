"""Construct closure and support-removal validation helpers.

Validates that every construct and support-removal decision declared on
a :class:`~cadrumo.domain.calculations.registry.ModeloRevision` has coherent member
references and legal grounding.

Construct member closure compares each member's
:class:`~cadrumo.domain.calculations.registry.LegalReference` and
:class:`~cadrumo.domain.calculations.registry.SourceReference` requirements with the
refs declared by the owning construct. Support-removal decisions are separately
gated through the
:class:`~cadrumo.domain.calculations.registry._validate_evidence.EvidenceValidator`.

See Also:
    :func:`cadrumo.domain.calculations.registry._validate_revision_closure._validate_revision_closure_sections`
        Revision-level runner that invokes both validators in this module.
    :func:`cadrumo.domain.calculations.registry.resolve_revision_constructs`
        Runtime projection of validated construct declarations.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ._schema import LegalReference, ModeloRevision, SourceReference
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import missing_refs as _missing_refs

_CONSTRUCT_MEMBER_ATTRS = {
    "casilla": "casilla_ids",
    "formula": "formulas",
    "parameter": "parameters",
    "binding": "bindings",
    "algorithm provider": "algorithm_providers",
    "algorithm binding": "algorithm_bindings",
    "relation": "relations",
    "export layout": "export_layouts",
    "extraction profile": "extraction_profiles",
    "cross-reference": "live_cross_references",
    "workbook parity reference": "workbook_parity_refs",
    "verification expectation": "verification_expectations",
    "application link": "application_links",
    "deadline window": "deadline_windows",
    "filing schedule": "filing_schedules",
    "support removal decision": "support_removal_decisions",
    "dependency classification": "dependency_classifications",
}
_SUPPORT_REMOVAL_SOURCE_TIERS = ("official_source_guidance", "layout_authority")


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
    :class:`~cadrumo.domain.calculations.registry._validate_evidence.EvidenceValidator`
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
                member_legal_refs = set(getattr(member, "legal_refs", ()))
                missing_legal = sorted(member_legal_refs.difference(construct_legal_refs))
                if missing_legal:
                    failures.append(
                        f"{scope}: construct {construct.id!r} does not include legal refs "
                        f"{missing_legal!r} required by {kind} {member_id!r}",
                    )
                member_source_refs = set(getattr(member, "source_refs", ()))
                missing_sources = sorted(member_source_refs.difference(construct_source_refs))
                if missing_sources:
                    failures.append(
                        f"{scope}: construct {construct.id!r} does not include source refs "
                        f"{missing_sources!r} required by {kind} {member_id!r}",
                    )
    return failures


def validate_support_removal_decisions(
    scope: str,
    revision: ModeloRevision,
    *,
    export_layout_ids: Iterable[str],
    extraction_profile_ids: Iterable[str],
    cross_reference_ids: Iterable[str],
    workbook_parity_ids: Iterable[str],
    verification_expectation_ids: Iterable[str],
    application_link_ids: Iterable[str],
    deadline_window_ids: Iterable[str],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
    filing_schedule_ids: Iterable[str] = (),
) -> list[str]:
    """Return support-removal decision failures for one revision.

    Each
    :class:`~cadrumo.domain.calculations.registry.SupportRemovalDecisionDefinition`
    declared by the
    :class:`~cadrumo.domain.calculations.registry.ModeloRevision` must cite known
    legal/source refs and one accepted source tier. A decision also fails when it
    claims to remove a subject id that remains active in the supplied subject-id
    indexes.
    """
    failures: list[str] = []
    active_subjects = {
        "export_layout": set(export_layout_ids),
        "extraction_profile": set(extraction_profile_ids),
        "live_cross_reference": set(cross_reference_ids),
        "workbook_parity_ref": set(workbook_parity_ids),
        "verification_expectation": set(verification_expectation_ids),
        "application_link": set(application_link_ids),
        "deadline_window": set(deadline_window_ids),
        "filing_schedule": set(filing_schedule_ids),
    }
    for decision in revision.support_removal_decisions:
        failures.extend(
            _missing_refs(scope, f"support removal decision {decision.id}", decision.legal_refs, legal_refs, "legal"),
        )
        failures.extend(
            _missing_refs(
                scope,
                f"support removal decision {decision.id}",
                decision.source_refs,
                source_refs,
                "source",
            ),
        )
        failures.extend(
            evidence.require_any_source_tier(
                scope,
                f"support removal decision {decision.id}",
                decision.source_refs,
                _SUPPORT_REMOVAL_SOURCE_TIERS,
            ),
        )
        active_ids = active_subjects.get(decision.subject_type)
        if active_ids is not None and decision.subject_id in active_ids:
            failures.append(
                f"{scope}: support removal decision {decision.id!r} removes "
                f"{decision.subject_type} {decision.subject_id!r} but it is still present",
            )
    return failures
