"""Referential-integrity validation for registry snapshots."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._errors import RegistryValidationError
from ._schema import ModeloRevision
from ._validate_cross_domain_snapshot import (
    _CROSS_DOMAIN_SNAPSHOT_CHECKS as _CROSS_DOMAIN_SNAPSHOT_CHECKS,
)
from ._validate_cross_domain_snapshot import (
    CrossDomainSnapshotCheck as CrossDomainSnapshotCheck,
)
from ._validate_cross_domain_snapshot import (
    check_cross_domain_snapshot_routing,
)
from ._validate_cross_domain_snapshot import (
    register_cross_domain_snapshot_check as register_cross_domain_snapshot_check,
)
from ._validate_reference_checker import IdReferenceChecker as _IdReferenceChecker

if TYPE_CHECKING:
    from ._schema import ExtractionProfileDefinition
    from ._snapshot import RegistrySnapshot


def _check_all_id_references(snapshot: RegistrySnapshot) -> None:
    """Assert every typed-ID reference in the snapshot points at an existing entity.

    Walks all 21 typed-ID reference fields across the snapshot's revision and
    raises :class:`RegistryValidationError` listing every dangling reference.
    This is an existence gate only -- it does not alter any field types.

    For union fields declared as ``TypedId | str`` (where the bare-``str``
    arm is a legacy escape), the value is treated as a candidate typed-ID
    and checked regardless of which arm is active.
    """
    checker = _IdReferenceChecker(snapshot)
    revision = snapshot.revision

    checker.chk_legal_source_refs("modelo", snapshot.modelo.legal_refs, snapshot.modelo.source_refs)
    checker.chk_legal_source_refs("revision", revision.legal_refs, revision.source_refs)

    _check_casilla_refs(checker, revision)
    _check_formula_refs(checker, revision)
    _check_parameter_refs(checker, revision)
    _check_binding_refs(checker, revision)
    _check_relation_refs(checker, revision)
    _check_extraction_profile_refs(checker, revision)
    _check_cross_reference_refs(checker, revision)
    _check_workbook_parity_refs(checker, revision)
    _check_verification_expectation_refs(checker, revision)
    _check_application_link_refs(checker, revision)
    _check_deadline_window_refs(checker, revision)
    _check_filing_schedule_refs(checker, revision)
    _check_support_removal_decision_refs(checker, revision)
    _check_construct_refs(checker, revision)
    _check_dependency_classification_refs(checker, revision)
    _check_algorithm_provider_refs(checker, revision)
    _check_algorithm_binding_refs(checker, revision)
    _check_export_layout_refs(checker, revision)
    check_cross_domain_snapshot_routing(checker, snapshot)
    _check_binding_selector_shapes(checker, revision)

    if checker.failures:
        raise RegistryValidationError(
            "referential integrity check failed:\n" + "\n".join(f" - {f}" for f in sorted(checker.failures))
        )


def _check_casilla_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for casilla in revision.casillas:
        cp = f"casilla {casilla.id}"
        checker.chk_opt(f"{cp}.formula", casilla.formula, checker.formula_ids)
        if casilla.input_kind == "bound":
            _check_bound_casilla_binding_coverage(checker, cp, casilla.binding)
        else:
            checker.chk_opt(f"{cp}.binding", casilla.binding, checker.binding_ids)
        checker.chk_tuple(f"{cp}.export_refs", casilla.export_refs, checker.export_field_ids)
        checker.chk_legal_source_refs(cp, casilla.legal_refs, casilla.source_refs)
        if casilla.constraints is not None:
            checker.chk_legal_source_refs(
                f"{cp}.constraints", casilla.constraints.legal_refs, casilla.constraints.source_refs
            )


def _check_bound_casilla_binding_coverage(checker: _IdReferenceChecker, field_path: str, binding: str | None) -> None:
    if binding is None:
        checker.failures.append(
            f"{checker.prefix}: {field_path}.binding has no binding definition for input_kind='bound'"
        )
        return
    checker.chk(f"{field_path}.binding", binding, checker.binding_ids)


def _check_formula_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for formula in revision.formulas:
        fp = f"formula {formula.id}"
        checker.chk(f"{fp}.target", formula.target, checker.casilla_ids)
        checker.chk_legal_source_refs(fp, formula.legal_refs, formula.source_refs)
        for citation in formula.source_citations:
            checker.chk(f"{fp}.source_citations.{citation.source_ref}", citation.source_ref, checker.source_ids)


def _check_parameter_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for parameter in revision.parameters:
        pp = f"parameter {parameter.id}"
        checker.chk_legal_source_refs(pp, parameter.legal_refs, parameter.source_refs)
        for citation in parameter.source_citations:
            checker.chk(f"{pp}.source_citations.{citation.source_ref}", citation.source_ref, checker.source_ids)


def _check_binding_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for binding in revision.bindings:
        bp = f"binding {binding.id}"
        checker.chk_legal_source_refs(bp, binding.legal_refs, binding.source_refs)
        for citation in binding.source_citations:
            checker.chk(f"{bp}.source_citations.{citation.source_ref}", citation.source_ref, checker.source_ids)


def _check_relation_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for relation in revision.relations:
        rp = f"relation {relation.id}"
        checker.chk(f"{rp}.target_binding", relation.target_binding, checker.binding_ids)
        checker.chk_legal_source_refs(rp, relation.legal_refs, relation.source_refs)
        # source_output is CasillaId | str; cross-model outputs are not in this
        # snapshot's casilla set -- checked at registry-validate time instead.


def _check_extraction_profile_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for profile in revision.extraction_profiles:
        ep = f"extraction_profile {profile.id}"
        target_ids = tuple(t.casilla_id for t in profile.target_casillas)
        checker.chk_tuple(f"{ep}.target_casillas", target_ids, checker.casilla_ids)
        checker.chk_legal_source_refs(ep, profile.legal_refs, profile.source_refs)
        if profile.surface == "declaracion_pdf":
            _check_text_casilla_strategy(checker, ep, profile)


def _check_text_casilla_strategy(
    checker: _IdReferenceChecker,
    ep: str,
    profile: ExtractionProfileDefinition,
) -> None:
    """Enforce that a declaracion_pdf profile targeting a text-typed casilla uses named_label.

    A ``data_type = "text"`` casilla is never printed as a numeric identifier on the
    PDF — the generic numeric regex cannot match it.  Any profile targeting such a
    casilla without the ``named_label`` strategy is a silent-extraction stub and must
    fail the snapshot-build gate.
    """
    for target in profile.target_casillas:
        data_type = checker.casilla_data_types.get(target.casilla_id)
        if data_type == "text" and target.match_strategy != "named_label":
            checker.failures.append(
                f"{checker.prefix}: {ep} targets casilla {target.casilla_id!r} "
                f"(data_type='text') but uses match_strategy={target.match_strategy!r}; "
                f"text-typed casilla targets must use match_strategy='named_label'"
            )


def _check_cross_reference_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for cross_ref in revision.live_cross_references:
        crp = f"cross_reference {cross_ref.id}"
        checker.chk_legal_source_refs(crp, cross_ref.legal_refs, cross_ref.source_refs)
        for pred in cross_ref.applicability_predicates:
            checker.chk_legal_source_refs(
                f"{crp}.applicability_predicates.{pred.field}", pred.legal_refs, pred.source_refs
            )


def _check_workbook_parity_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for workbook in revision.workbook_parity_refs:
        wp = f"workbook_parity_ref {workbook.id}"
        checker.chk(f"{wp}.workbook_source", workbook.workbook_source, checker.source_ids)
        checker.chk_legal_source_refs(wp, workbook.legal_refs, workbook.source_refs)


def _check_verification_expectation_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for expectation in revision.verification_expectations:
        vep = f"verification_expectation {expectation.id}"
        checker.chk_tuple(f"{vep}.computed_casillas", expectation.computed_casillas, checker.casilla_ids)
        for total_kind, casilla_id in expectation.reconciliation_totals.items():
            checker.chk(f"{vep}.reconciliation_totals.{total_kind}", casilla_id, checker.casilla_ids)
        checker.chk_legal_source_refs(vep, expectation.legal_refs, expectation.source_refs)


def _check_application_link_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for link in revision.application_links:
        lp = f"application_link {link.id}"
        checker.chk_legal_source_refs(lp, link.legal_refs, link.source_refs)


def _check_deadline_window_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for window in revision.deadline_windows:
        dwp = f"deadline_window {window.id}"
        checker.chk_legal_source_refs(dwp, window.legal_refs, window.source_refs)
        for condition in window.applicability_conditions:
            checker.chk_legal_source_refs(
                f"{dwp}.applicability_conditions.{condition.field}",
                condition.legal_refs,
                condition.source_refs,
            )


def _check_filing_schedule_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for schedule in revision.filing_schedules:
        fsp = f"filing_schedule {schedule.id}"
        checker.chk_legal_source_refs(fsp, schedule.legal_refs, schedule.source_refs)
        for condition in schedule.profile_conditions:
            checker.chk_legal_source_refs(
                f"{fsp}.profile_conditions.{condition.field}", condition.legal_refs, condition.source_refs
            )


def _check_support_removal_decision_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for decision in revision.support_removal_decisions:
        dp = f"support_removal_decision {decision.id}"
        checker.chk_legal_source_refs(dp, decision.legal_refs, decision.source_refs)


_CONSTRUCT_MEMBER_AXES: tuple[tuple[str, str], ...] = (
    ("casillas", "casilla_ids"),
    ("formulas", "formula_ids"),
    ("parameters", "parameter_ids"),
    ("bindings", "binding_ids"),
    ("relations", "relation_ids"),
    ("export_layouts", "export_layout_ids"),
    ("extraction_profiles", "extraction_profile_ids"),
    ("live_cross_references", "cross_reference_ids"),
    ("workbook_parity_refs", "workbook_parity_ids"),
    ("verification_expectations", "verification_expectation_ids"),
    ("application_links", "application_link_ids"),
    ("deadline_windows", "deadline_window_ids"),
    ("support_removal_decisions", "support_removal_decision_ids"),
    ("dependency_classifications", "dependency_classification_ids"),
)


def _check_construct_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for construct in revision.constructs:
        ctp = f"construct {construct.id}"
        for attr, id_set_name in _CONSTRUCT_MEMBER_AXES:
            checker.chk_tuple(f"{ctp}.{attr}", getattr(construct, attr), getattr(checker, id_set_name))
        checker.chk_legal_source_refs(ctp, construct.legal_refs, construct.source_refs)


def _check_dependency_classification_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for classification in revision.dependency_classifications:
        dcp = f"dependency_classification {classification.id}"
        checker.chk_tuple(f"{dcp}.target_constructs", classification.target_constructs, checker.construct_ids)
        checker.chk_tuple(f"{dcp}.relation_refs", classification.relation_refs, checker.relation_ids)
        checker.chk_legal_source_refs(dcp, classification.legal_refs, classification.source_refs)


def _check_algorithm_provider_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for provider in revision.algorithm_providers:
        avp = f"algorithm_provider {provider.id}"
        checker.chk_legal_source_refs(avp, provider.legal_refs, provider.source_refs)


def _check_algorithm_binding_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    provider_ids = {p.id for p in revision.algorithm_providers}
    resolvable_ids = checker.casilla_ids | checker.binding_ids | checker.parameter_ids | checker.relation_ids
    for alg_binding in revision.algorithm_bindings:
        abp = f"algorithm_binding {alg_binding.id}"
        if alg_binding.provider not in provider_ids:
            checker.failures.append(f"{checker.prefix}: {abp}.provider references unknown id {alg_binding.provider!r}")
        # target is CasillaId | str; treat as CasillaId candidate.
        checker.chk(f"{abp}.target", alg_binding.target, checker.casilla_ids)
        for input_name, input_id in alg_binding.inputs.items():
            if input_id not in resolvable_ids:
                checker.failures.append(
                    f"{checker.prefix}: {abp}.inputs.{input_name} references unknown id {input_id!r}"
                )
        for output_name, output_id in alg_binding.outputs.items():
            checker.chk(f"{abp}.outputs.{output_name}", output_id, checker.casilla_ids)
        checker.chk_tuple(f"{abp}.constants", alg_binding.constants, checker.parameter_ids)
        checker.chk_legal_source_refs(abp, alg_binding.legal_refs, alg_binding.source_refs)


def _check_export_layout_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for layout in revision.export_layouts:
        lyp = f"export_layout {layout.id}"
        checker.chk_legal_source_refs(lyp, layout.legal_refs, layout.source_refs)
        if layout.dictionary_source_ref is not None:
            checker.chk(f"{lyp}.dictionary_source_ref", layout.dictionary_source_ref, checker.source_ids)
        for record in layout.records:
            rcp = f"{lyp}.record {record.id}"
            checker.chk_opt(f"{rcp}.requires_positive_casilla", record.requires_positive_casilla, checker.casilla_ids)
            for field in record.fields:
                efp = f"{rcp}.field {field.id}"
                checker.chk_opt(f"{efp}.casilla", field.casilla, checker.casilla_ids)
                checker.chk_opt(f"{efp}.binding", field.binding, checker.binding_ids)
                checker.chk_legal_source_refs(efp, field.legal_refs, field.source_refs)


def _check_binding_selector_shapes(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    """Per-source selector-shape validation.

    Every binding whose source appears in the discriminated selector
    registry must satisfy the strict pydantic model declared for that
    source. Sources without a registered typed selector are accepted
    unchanged — the discriminator is incremental; new typed selectors
    land alongside their handler updates and are registered in
    ``_BINDING_SELECTOR_REGISTRY``.
    """
    from ._bindings import validate_binding_selector_shape

    for binding in revision.bindings:
        checker.failures.extend(f"{checker.prefix}: {fail}" for fail in validate_binding_selector_shape(binding))
