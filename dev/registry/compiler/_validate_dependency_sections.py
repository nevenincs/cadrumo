"""Dependency-classification and filing-schedule validation helpers.

Cross-model folds are binding providers now.  This module therefore validates
the dependency metadata against the provider-owned binding ids rather than a
second relation record family.
"""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.bindings import binding_source_modelo
from cadrumo.domain.calculations.registry.bindings_previous_filing import (
    is_direct_previous_filing_binding,
    previous_filing_source_reference,
)
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
    classifications_by_source = {
        classification.source_modelo: classification for classification in classifications
    }

    for classification in classifications:
        owner = f"dependency classification {classification.id}"
        failures.extend(missing_refs(prefix, owner, classification.legal_refs, legal_refs, "legal"))
        failures.extend(missing_refs(prefix, owner, classification.source_refs, source_refs, "source"))
        failures.extend(
            evidence.require_source_tier(prefix, owner, classification.source_refs, "official_source_guidance"),
        )
        for construct_id in classification.target_constructs:
            construct = construct_by_id.get(construct_id)
            if construct is None:
                failures.append(f"{prefix}: {owner} references unknown construct {construct_id!r}")
            elif classification.id not in construct.dependency_classifications:
                failures.append(
                    f"{prefix}: {owner} targets construct {construct_id!r} but the construct does not list it",
                )
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
            missing_legal_refs = sorted(set(binding.legal_refs).difference(classification.legal_refs))
            if missing_legal_refs:
                failures.append(
                    f"{prefix}: {owner} binding {binding_id!r} does not include binding legal refs "
                    f"{missing_legal_refs!r}",
                )
            missing_source_refs = sorted(set(binding.source_refs).difference(classification.source_refs))
            if missing_source_refs:
                failures.append(
                    f"{prefix}: {owner} binding {binding_id!r} does not include binding source refs "
                    f"{missing_source_refs!r}",
                )

    for duplicate in sorted(duplicates(item.source_modelo for item in classifications)):
        failures.append(f"{prefix}: duplicate dependency classification source modelo {duplicate!r}")

    bindings_by_source: dict[str, list[BindingDefinition]] = {}
    for binding in revision.bindings:
        source_modelo = binding_source_modelo(binding)
        if source_modelo is not None:
            bindings_by_source.setdefault(source_modelo, []).append(binding)

    for source_modelo, bindings in sorted(bindings_by_source.items()):
        classification = classifications_by_source.get(source_modelo)
        if classification is None:
            failures.append(
                f"{prefix}: binding source modelo {source_modelo!r} has no dependency classification",
            )
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
    selector_periods = set(revision.period_selector.periods)
    for schedule in revision.filing_schedules:
        owner = f"filing schedule {schedule.id}"
        failures.extend(missing_refs(prefix, owner, schedule.legal_refs, legal_refs, "legal"))
        failures.extend(missing_refs(prefix, owner, schedule.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(prefix, owner, schedule.source_refs, "official_source_guidance"))
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
