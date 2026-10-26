"""Dependency-classification and filing-schedule validation helpers.

Cross-model folds are binding providers now.  This module therefore validates
the dependency metadata against the provider-owned binding ids rather than a
second relation record family.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cadrumo.domain.calculations.registry.bindings import binding_source_modelo
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_deadlines import filing_schedule_period_kind_mismatches
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference
from cadrumo.domain.calculations.registry.schema_revision_members import (
    ConstructDefinition,
    DependencyClassificationDefinition,
)
from cadrumo.domain.calculations.registry.validate_revision_identity import duplicates

from ._validate_helpers import missing_refs
from .validate_evidence import EvidenceValidator


def _classification_declaration_failures(
    *,
    prefix: str,
    classification: DependencyClassificationDefinition,
    construct_by_id: Mapping[str, ConstructDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    """Validate one classification's declared references and target constructs."""
    failures: list[str] = []
    owner = f"dependency classification {classification.id}"
    failures.extend(missing_refs(prefix, owner, classification.legal_refs, legal_refs, "legal"))
    failures.extend(missing_refs(prefix, owner, classification.source_refs, source_refs, "source"))
    failures.extend(evidence.require_source_tier(prefix, owner, classification.source_refs, "official_source_guidance"))
    for construct_id in classification.target_constructs:
        construct = construct_by_id.get(construct_id)
        if construct is None:
            failures.append(f"{prefix}: {owner} references unknown construct {construct_id!r}")
        elif classification.id not in construct.dependency_classifications:
            failures.append(
                f"{prefix}: {owner} targets construct {construct_id!r} but the construct does not list it",
            )
    return failures


def _binding_reference_failure(
    *,
    prefix: str,
    owner: str,
    binding_id: BindingId,
    reference_kind: str,
    binding_refs: Sequence[str],
    classification_refs: Sequence[str],
) -> str | None:
    """Describe binding references omitted by their dependency classification."""
    missing = sorted(set(binding_refs).difference(classification_refs))
    if not missing:
        return None
    return f"{prefix}: {owner} binding {binding_id!r} does not include binding {reference_kind} refs {missing!r}"


def _classification_binding_failures(
    *,
    prefix: str,
    classification: DependencyClassificationDefinition,
    binding_by_id: Mapping[BindingId, BindingDefinition],
) -> list[str]:
    """Validate every binding attached to one dependency classification."""
    failures: list[str] = []
    owner = f"dependency classification {classification.id}"
    for binding_id in classification.binding_refs:
        binding = binding_by_id.get(binding_id)
        if binding is None:
            failures.append(f"{prefix}: {owner} references unknown binding {binding_id!r}")
            continue
        source_modelo = binding_source_modelo(binding)
        if source_modelo != classification.source_modelo:
            failures.append(
                f"{prefix}: {owner} source_modelo {classification.source_modelo!r} does not match "
                f"binding {binding_id!r} source_modelo {source_modelo!r}",
            )
        for kind, binding_refs, classification_refs in (
            ("legal", binding.legal_refs, classification.legal_refs),
            ("source", binding.source_refs, classification.source_refs),
        ):
            failure = _binding_reference_failure(
                prefix=prefix,
                owner=owner,
                binding_id=binding_id,
                reference_kind=kind,
                binding_refs=binding_refs,
                classification_refs=classification_refs,
            )
            if failure is not None:
                failures.append(failure)
    return failures


def _bindings_by_source_modelo(revision: ModeloRevision) -> dict[str, list[BindingDefinition]]:
    """Group source-backed bindings by their declared source modelo."""
    grouped: dict[str, list[BindingDefinition]] = {}
    for binding in revision.bindings:
        source_modelo = binding_source_modelo(binding)
        if source_modelo is not None:
            grouped.setdefault(source_modelo, []).append(binding)
    return grouped


def _binding_source_coverage_failures(
    *,
    prefix: str,
    bindings_by_source: Mapping[str, list[BindingDefinition]],
    classifications_by_source: Mapping[str, DependencyClassificationDefinition],
) -> list[str]:
    """Require a non-exempt classification to cover each source binding."""
    failures: list[str] = []
    for source_modelo, bindings in sorted(bindings_by_source.items()):
        classification = classifications_by_source.get(source_modelo)
        if classification is None:
            failures.append(f"{prefix}: binding source modelo {source_modelo!r} has no dependency classification")
            continue
        if classification.treatment == "non_dependency":
            failures.append(
                f"{prefix}: binding source modelo {source_modelo!r} cannot be classified as non_dependency",
            )
            continue
        declared = set(classification.binding_refs)
        missing = sorted(binding.id for binding in bindings if binding.id not in declared)
        if missing:
            failures.append(
                f"{prefix}: dependency classification {classification.id!r} does not cover binding refs {missing!r}",
            )
    return failures


def validate_dependency_classification_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    construct_by_id: Mapping[str, ConstructDefinition],
    binding_by_id: Mapping[BindingId, BindingDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    """Return dependency-classification closure and grounding failures."""
    failures: list[str] = []
    classifications = revision.dependency_classifications
    classifications_by_source = {classification.source_modelo: classification for classification in classifications}

    for classification in classifications:
        failures.extend(
            _classification_declaration_failures(
                prefix=prefix,
                classification=classification,
                construct_by_id=construct_by_id,
                legal_refs=legal_refs,
                source_refs=source_refs,
                evidence=evidence,
            )
        )
        failures.extend(
            _classification_binding_failures(
                prefix=prefix,
                classification=classification,
                binding_by_id=binding_by_id,
            )
        )

    for duplicate in sorted(duplicates(item.source_modelo for item in classifications)):
        failures.append(f"{prefix}: duplicate dependency classification source modelo {duplicate!r}")

    failures.extend(
        _binding_source_coverage_failures(
            prefix=prefix,
            bindings_by_source=_bindings_by_source_modelo(revision),
            classifications_by_source=classifications_by_source,
        )
    )

    return failures


def validate_filing_schedule_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    """Return filing-schedule reference and period-selector failures."""
    failures: list[str] = []
    # A filing schedule is year-less, so a token the selector serves only in an
    # override year is still declared by the revision and must not be reported
    # as "outside the selector".
    selector_periods = set(revision.period_selector.declared_periods)
    for schedule in revision.filing_schedules:
        owner = f"filing schedule {schedule.id}"
        failures.extend(missing_refs(prefix, owner, schedule.legal_refs, legal_refs, "legal"))
        failures.extend(missing_refs(prefix, owner, schedule.source_refs, source_refs, "source"))
        failures.extend(
            evidence.require_procedural_evidence(
                prefix,
                owner,
                schedule.source_refs,
                schedule.legal_refs,
                valid_from=revision.valid_from,
                valid_to=revision.valid_to,
            )
        )
        unknown_periods = sorted(set(schedule.periods).difference(selector_periods))
        if unknown_periods:
            failures.append(
                f"{prefix}: filing schedule {schedule.id!r} declares periods outside revision selector "
                f"{unknown_periods!r}",
            )
        cadence_mismatches = filing_schedule_period_kind_mismatches(schedule.period_kind, schedule.periods)
        if cadence_mismatches:
            failures.append(
                f"{prefix}: filing schedule {schedule.id!r} period_kind {schedule.period_kind!r} "
                f"contradicts periods {cadence_mismatches!r}",
            )
        for condition in schedule.profile_conditions:
            condition_owner = f"filing schedule {schedule.id} condition {condition.field}"
            failures.extend(missing_refs(prefix, condition_owner, condition.legal_refs, legal_refs, "legal"))
            failures.extend(missing_refs(prefix, condition_owner, condition.source_refs, source_refs, "source"))
            failures.extend(
                evidence.require_source_tier(
                    prefix,
                    condition_owner,
                    condition.source_refs,
                    "official_source_guidance",
                ),
            )
    return failures
