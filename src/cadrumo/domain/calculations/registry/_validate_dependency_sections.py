"""Relation, dependency-classification, and filing-schedule validation helpers.

Validates relations, dependency classifications, and filing schedules
declared on a :class:`~cadrumo.domain.calculations.registry.ModeloRevision` for
reference closure and legal grounding.

Relation validation ties
:class:`~cadrumo.domain.calculations.registry.schema.RelationDefinition` records
back to declared :class:`~cadrumo.domain.calculations.registry.DataBindingDefinition`
targets. Dependency classification validation checks
:class:`~cadrumo.domain.calculations.registry.DependencyClassificationDefinition`
rows against constructs, relations, and official-source evidence.

See Also:
    :func:`cadrumo.domain.calculations.registry.validate_revision_sections.validate_revision_definition`
        Per-revision dispatcher that invokes these section validators.
    :func:`cadrumo.domain.calculations.registry.relation_source_requirements`
        Runtime relation requirement projection that relies on validated
        relation/dependency metadata.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core.aggregation import BindingSourceKind
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import missing_refs
from .bindings_previous_filing import previous_filing_source_reference
from .ids import BindingId
from .schema import (
    DataBindingDefinition,
    ModeloRevision,
)
from .schema_deadlines import filing_schedule_period_kind_mismatches
from .schema_references import LegalReference, SourceReference
from .schema_revision_members import ConstructDefinition, DependencyClassificationDefinition
from .schema_surfaces import RelationDefinition
from .validate_revision_identity import duplicates


def validate_relation_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    bindings: set[BindingId],
    binding_by_id: Mapping[BindingId, DataBindingDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    """Return relation reference, period, and grounding failures.

    The supplied :class:`~cadrumo.domain.calculations.registry.ModeloRevision`
    contributes relation declarations. Each relation must target a known
    :class:`~cadrumo.domain.calculations.registry.BindingId`, include the legal and
    source refs carried by that target binding, and stay inside the revision
    period selector.
    """
    failures: list[str] = []
    for relation in revision.relations:
        owner = f"relation {relation.id}"
        failures.extend(missing_refs(prefix, owner, relation.legal_refs, legal_refs, "legal"))
        failures.extend(missing_refs(prefix, owner, relation.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(prefix, owner, relation.source_refs, "official_source_guidance"))
        if relation.target_binding not in bindings:
            failures.append(f"{prefix}: relation {relation.id!r} targets unknown binding {relation.target_binding!r}")
        else:
            target_binding = binding_by_id[relation.target_binding]
            missing_legal_refs = sorted(set(relation.legal_refs).difference(target_binding.legal_refs))
            if missing_legal_refs:
                failures.append(
                    f"{prefix}: relation {relation.id!r} target binding {relation.target_binding!r} "
                    f"does not include relation legal refs {missing_legal_refs!r}",
                )
            missing_source_refs = sorted(set(relation.source_refs).difference(target_binding.source_refs))
            if missing_source_refs:
                failures.append(
                    f"{prefix}: relation {relation.id!r} target binding {relation.target_binding!r} "
                    f"does not include relation source refs {missing_source_refs!r}",
                )
        unknown_target_periods = sorted(set(relation.target_periods).difference(revision.period_selector.periods))
        if unknown_target_periods:
            failures.append(
                f"{prefix}: relation {relation.id!r} targets periods outside revision selector "
                f"{unknown_target_periods!r}",
            )
    return failures


def validate_dependency_classification_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    construct_by_id: Mapping[str, ConstructDefinition],
    relation_by_id: Mapping[str, RelationDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    """Return dependency-classification closure and duplicate failures.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    dependency classifications and relations. Each
    :class:`~cadrumo.domain.calculations.registry.DependencyClassificationDefinition`
    must cite known refs, point at declared constructs/relations, and cover every
    relation source modelo with a dependency-bearing treatment.
    """
    failures: list[str] = []
    previous_filing_bindings_by_source = _previous_filing_bindings_by_source(revision)
    for classification in revision.dependency_classifications:
        _validate_single_dependency_classification(
            failures,
            prefix=prefix,
            classification=classification,
            construct_by_id=construct_by_id,
            relation_by_id=relation_by_id,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        )
        _validate_direct_previous_filing_classification(
            failures,
            prefix=prefix,
            classification=classification,
            direct_bindings=previous_filing_bindings_by_source.get(classification.source_modelo, ()),
            construct_by_id=construct_by_id,
        )

    for duplicate in sorted(duplicates([item.source_modelo for item in revision.dependency_classifications])):
        failures.append(f"{prefix}: duplicate dependency classification source modelo {duplicate!r}")
    classifications_by_source = {
        classification.source_modelo: classification for classification in revision.dependency_classifications
    }
    relation_ids_by_source: dict[str, set[str]] = {}
    for relation in revision.relations:
        relation_ids_by_source.setdefault(relation.source_modelo, set()).add(relation.id)
    for source_modelo, relation_ids_for_source in sorted(relation_ids_by_source.items()):
        classification = classifications_by_source.get(source_modelo)
        if classification is None:
            failures.append(f"{prefix}: relation source modelo {source_modelo!r} has no dependency classification")
            continue
        if classification.treatment == "non_dependency":
            failures.append(
                f"{prefix}: relation source modelo {source_modelo!r} cannot be classified as non_dependency",
            )
            continue
        missing_relation_refs = sorted(relation_ids_for_source.difference(classification.relation_refs))
        if missing_relation_refs:
            failures.append(
                f"{prefix}: dependency classification {classification.id!r} does not cover relation refs "
                f"{missing_relation_refs!r}",
            )
    _validate_previous_filing_classification_completeness(
        failures,
        prefix=prefix,
        classifications_by_source=classifications_by_source,
        previous_filing_bindings_by_source=previous_filing_bindings_by_source,
        construct_by_id=construct_by_id,
    )
    return failures


def _validate_single_dependency_classification(
    failures: list[str],
    *,
    prefix: str,
    classification: DependencyClassificationDefinition,
    construct_by_id: Mapping[str, ConstructDefinition],
    relation_by_id: Mapping[str, RelationDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append failures for one dependency-classification declaration.

    The
    :class:`~cadrumo.domain.calculations.registry.DependencyClassificationDefinition`
    must be grounded by the supplied legal/source maps, target declared
    :class:`~cadrumo.domain.calculations.registry.ConstructDefinition` rows, and
    mirror the source-modelo plus refs of each referenced relation.
    """
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
            continue
        if classification.id not in construct.dependency_classifications:
            failures.append(f"{prefix}: {owner} targets construct {construct_id!r} but the construct does not list it")
    for relation_id in classification.relation_refs:
        relation = relation_by_id.get(relation_id)
        if relation is None:
            failures.append(f"{prefix}: {owner} references unknown relation {relation_id!r}")
            continue
        if relation.source_modelo != classification.source_modelo:
            failures.append(
                f"{prefix}: {owner} source_modelo {classification.source_modelo!r} does not match "
                f"relation {relation_id!r} source_modelo {relation.source_modelo!r}",
            )
        missing_legal_refs = sorted(set(relation.legal_refs).difference(classification.legal_refs))
        if missing_legal_refs:
            failures.append(
                f"{prefix}: {owner} relation {relation_id!r} "
                f"does not include relation legal refs {missing_legal_refs!r}",
            )
        missing_source_refs = sorted(set(relation.source_refs).difference(classification.source_refs))
        if missing_source_refs:
            failures.append(
                f"{prefix}: {owner} relation {relation_id!r} "
                f"does not include relation source refs {missing_source_refs!r}",
            )


def _validate_direct_previous_filing_classification(
    failures: list[str],
    *,
    prefix: str,
    classification: DependencyClassificationDefinition,
    direct_bindings: tuple[DataBindingDefinition, ...],
    construct_by_id: Mapping[str, ConstructDefinition],
) -> None:
    """Require a relation-less direct settlement to cover its direct carries.

    A direct ``previous_filing`` carry has no relation id to declare, but its
    source-modelo classification must identify every target binding and carry
    their legal grounding.
    """
    if classification.treatment != "direct_annual_settlement" or classification.relation_refs:
        return

    if not direct_bindings:
        failures.append(
            f"{prefix}: dependency classification {classification.id!r} with direct_annual_settlement "
            "must declare relation refs or cover direct previous_filing bindings",
        )
        return

    _validate_direct_previous_filing_binding_coverage(
        failures,
        prefix=prefix,
        classification=classification,
        direct_bindings=direct_bindings,
        construct_by_id=construct_by_id,
    )


def _validate_direct_previous_filing_binding_coverage(
    failures: list[str],
    *,
    prefix: str,
    classification: DependencyClassificationDefinition,
    direct_bindings: tuple[DataBindingDefinition, ...],
    construct_by_id: Mapping[str, ConstructDefinition],
) -> None:
    """Require a direct previous-filing treatment to cover targets and legal refs."""
    target_binding_ids = {
        binding_id
        for construct_id in classification.target_constructs
        if (construct := construct_by_id.get(construct_id)) is not None
        for binding_id in construct.bindings
    }
    missing_target_bindings = sorted({binding.id for binding in direct_bindings}.difference(target_binding_ids))
    if missing_target_bindings:
        failures.append(
            f"{prefix}: dependency classification {classification.id!r} does not target direct previous_filing "
            f"bindings {missing_target_bindings!r}",
        )

    required_legal_refs = {legal_ref for binding in direct_bindings for legal_ref in binding.legal_refs}
    missing_legal_refs = sorted(required_legal_refs.difference(classification.legal_refs))
    if missing_legal_refs:
        failures.append(
            f"{prefix}: dependency classification {classification.id!r} does not include direct previous_filing "
            f"legal refs {missing_legal_refs!r}",
        )


def _previous_filing_bindings_by_source(
    revision: ModeloRevision,
) -> dict[str, tuple[DataBindingDefinition, ...]]:
    """Group every direct previous-filing consumer by its canonical source modelo."""
    grouped: dict[str, list[DataBindingDefinition]] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.PREVIOUS_FILING:
            continue
        source_modelo = previous_filing_source_reference(binding).source_modelo
        grouped.setdefault(source_modelo, []).append(binding)
    return {source_modelo: tuple(bindings) for source_modelo, bindings in grouped.items()}


def _validate_previous_filing_classification_completeness(
    failures: list[str],
    *,
    prefix: str,
    classifications_by_source: Mapping[str, DependencyClassificationDefinition],
    previous_filing_bindings_by_source: Mapping[str, tuple[DataBindingDefinition, ...]],
    construct_by_id: Mapping[str, ConstructDefinition],
) -> None:
    """Require exactly one dependency-bearing classification for every direct carry.

    A classification is keyed by source modelo, the same canonical key the
    previous-filing resolver uses to project its treatment. Duplicate keys are
    rejected by the sibling duplicate check; this pass closes the missing and
    ``non_dependency`` cases that a per-classification validator cannot see.
    """
    for source_modelo in sorted(previous_filing_bindings_by_source):
        classification = classifications_by_source.get(source_modelo)
        if classification is None:
            failures.append(
                f"{prefix}: previous_filing source modelo {source_modelo!r} has no dependency classification",
            )
            continue
        if classification.treatment == "non_dependency":
            failures.append(
                f"{prefix}: previous_filing source modelo {source_modelo!r} cannot be classified as non_dependency",
            )
            continue
        if classification.treatment == "factual_evidence" and not classification.relation_refs:
            _validate_direct_previous_filing_binding_coverage(
                failures,
                prefix=prefix,
                classification=classification,
                direct_bindings=previous_filing_bindings_by_source[source_modelo],
                construct_by_id=construct_by_id,
            )


def validate_filing_schedule_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> list[str]:
    """Return filing-schedule reference and period-selector failures.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies the
    accepted period selector and filing-schedule declarations. Each schedule and
    profile condition must be legally/source grounded and may only name periods
    declared by the revision selector.
    """
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
