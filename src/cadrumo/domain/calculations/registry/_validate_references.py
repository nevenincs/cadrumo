"""Referential-integrity validation for registry snapshots.

Walks all 20 typed-ID reference fields across a :class:`RegistrySnapshot`
and raises :class:`~cadrumo.domain.calculations.registry.errors.RegistryValidationError`
for every dangling reference found in the :class:`ModeloRevision`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import RegistryValidationError
from ._ids import BindingId
from ._schema import InputKind, ModeloRevision
from ._validate_cross_domain_snapshot import (
    CROSS_DOMAIN_SNAPSHOT_CHECKS,
    check_cross_domain_snapshot_routing,
)
from ._validate_cross_domain_snapshot import (
    CrossDomainSnapshotCheck as CrossDomainSnapshotCheck,
)
from ._validate_cross_domain_snapshot import (
    register_cross_domain_snapshot_check as register_cross_domain_snapshot_check,
)
from ._validate_reference_checker import IdReferenceChecker as _IdReferenceChecker
from ._validate_reference_sections import (
    check_binding_selector_shapes,
    check_construct_refs,
    check_dependency_classification_refs,
    check_export_layout_refs,
)

_CROSS_DOMAIN_SNAPSHOT_CHECKS = CROSS_DOMAIN_SNAPSHOT_CHECKS

if TYPE_CHECKING:
    from ._schema import ExtractionProfileDefinition
    from ._snapshot import RegistrySnapshot


def _check_all_id_references(snapshot: RegistrySnapshot) -> None:
    """Assert every typed-ID reference in the snapshot points at an existing entity.

    Walks all 20 typed-ID reference fields across the snapshot's revision and
    raises :class:`RegistryValidationError` listing every dangling reference.
    This is an existence gate only -- it does not alter any field types.

    Casilla references are checked only against declared canonical
    ``casilla.id`` values; display numbers, form numbers, and export
    field identifiers are never alternate lookup keys at this boundary.
    """
    checker = _IdReferenceChecker(snapshot)
    revision = snapshot.revision

    checker.chk_legal_source_refs("modelo", snapshot.modelo.legal_refs, snapshot.modelo.source_refs)
    checker.chk_legal_source_refs("revision", revision.legal_refs, revision.source_refs)
    checker.chk_tuple("revision.orden_aplicabilidad", revision.orden_aplicabilidad, checker.legal_ids)

    _check_completeness_manifest_refs(checker, revision)
    _check_casilla_continuidad_evolution_refs(checker, revision)
    _check_casilla_refs(checker, revision)
    _check_formula_refs(checker, revision)
    _check_parameter_refs(checker, revision)
    _check_binding_refs(checker, revision)
    _check_relation_refs(checker, revision)
    _check_extraction_profile_refs(checker, revision)
    _check_cross_reference_refs(checker, revision)
    _check_workbook_parity_refs(checker, revision)
    _check_verification_expectation_refs(checker, revision)
    _check_verification_predicate_refs(checker, revision)
    _check_application_link_refs(checker, revision)
    _check_deadline_window_refs(checker, revision)
    _check_filing_schedule_refs(checker, revision)
    check_construct_refs(checker, revision)
    check_dependency_classification_refs(checker, revision)
    check_export_layout_refs(checker, revision)
    check_cross_domain_snapshot_routing(checker, snapshot)
    check_binding_selector_shapes(checker, revision)

    if checker.failures:
        raise RegistryValidationError(
            "referential integrity check failed:\n" + "\n".join(f" - {f}" for f in sorted(checker.failures)),
        )


def check_all_id_references(snapshot: RegistrySnapshot) -> None:
    """Run the public referential-integrity gate for a :class:`RegistrySnapshot`.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose revision references are checked.
    """
    _check_all_id_references(snapshot)


def _check_completeness_manifest_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    manifest = revision.completeness_manifest
    if manifest is None:
        return
    cp = "calculation_completeness_manifest"
    checker.chk(f"{cp}.source_ref", manifest.source_ref, checker.source_ids)
    checker.chk_legal_source_refs(cp, manifest.legal_refs, manifest.source_refs)


def _check_casilla_continuidad_evolution_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for evolution in revision.casilla_continuidad_evolutions:
        cp = f"casilla_continuidad_evolution {evolution.id}"
        checker.chk_legal_source_refs(cp, evolution.legal_refs, evolution.source_refs)


def _check_casilla_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for casilla in revision.casillas:
        cp = f"casilla {casilla.id}"
        checker.chk_opt(f"{cp}.formula", casilla.formula, checker.formula_ids)
        if casilla.input_kind == InputKind.BOUND:
            _check_bound_casilla_binding_coverage(checker, cp, casilla.binding)
            checker.chk_tuple(f"{cp}.alternate_bindings", casilla.alternate_bindings, checker.binding_ids)
        else:
            checker.chk_opt(f"{cp}.binding", casilla.binding, checker.binding_ids)
            checker.chk_tuple(f"{cp}.alternate_bindings", casilla.alternate_bindings, checker.binding_ids)
        checker.chk_tuple(f"{cp}.export_refs", casilla.export_refs, checker.export_field_ids)
        checker.chk_legal_source_refs(cp, casilla.legal_refs, casilla.source_refs)
        if casilla.constraints is not None:
            checker.chk_legal_source_refs(
                f"{cp}.constraints",
                casilla.constraints.legal_refs,
                casilla.constraints.source_refs,
            )
        for alias in casilla.aliases:
            checker.chk_legal_source_refs(
                f"{cp}.alias {alias.localization_key}",
                alias.legal_refs,
                alias.source_refs,
            )


def _check_bound_casilla_binding_coverage(
    checker: _IdReferenceChecker,
    field_path: str,
    binding: BindingId | None,
) -> None:
    if binding is None:
        checker.failures.append(
            f"{checker.prefix}: {field_path}.binding has no binding definition for input_kind='bound'",
        )
        return
    checker.chk(f"{field_path}.binding", binding, checker.binding_ids)


def _check_formula_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for formula in revision.formulas:
        fp = f"formula {formula.id}"
        checker.chk(f"{fp}.target_casilla_id", formula.target_casilla_id, checker.casilla_ids)
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
        # cross-model source_casilla_id values are checked at registry-validate time
        # instead of against this snapshot's casilla set.


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
                f"text-typed casilla targets must use match_strategy='named_label'",
            )


def _check_cross_reference_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for cross_ref in revision.live_cross_references:
        crp = f"cross_reference {cross_ref.id}"
        checker.chk_legal_source_refs(crp, cross_ref.legal_refs, cross_ref.source_refs)
        for pred in cross_ref.applicability_predicates:
            checker.chk_legal_source_refs(
                f"{crp}.applicability_predicates.{pred.field}",
                pred.legal_refs,
                pred.source_refs,
            )


def _check_workbook_parity_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for workbook in revision.workbook_parity_refs:
        wp = f"workbook_parity_ref {workbook.id}"
        checker.chk(f"{wp}.workbook_source", workbook.workbook_source, checker.source_ids)
        checker.chk_legal_source_refs(wp, workbook.legal_refs, workbook.source_refs)


def _check_verification_expectation_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for expectation in revision.verification_expectations:
        vep = f"verification_expectation {expectation.id}"
        checker.chk_tuple(f"{vep}.computed_casilla_ids", expectation.computed_casilla_ids, checker.casilla_ids)
        checker.chk_tuple(
            f"{vep}.reconcile_when_present_casilla_ids",
            expectation.reconcile_when_present_casilla_ids,
            checker.casilla_ids,
        )
        checker.chk_tuple(
            f"{vep}.externally_grounded_casilla_ids",
            expectation.externally_grounded_casilla_ids,
            checker.casilla_ids,
        )
        for total_kind, casilla_id in expectation.reconciliation_total_casilla_ids.items():
            checker.chk(f"{vep}.reconciliation_total_casilla_ids.{total_kind}", casilla_id, checker.casilla_ids)
        checker.chk_legal_source_refs(vep, expectation.legal_refs, expectation.source_refs)


def _check_verification_predicate_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for predicate in revision.verification_predicates:
        vpp = f"verification_predicate {predicate.predicate_id}"
        checker.chk_tuple(f"{vpp}.legal_refs", predicate.legal_refs, checker.legal_ids)


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
                f"{fsp}.profile_conditions.{condition.field}",
                condition.legal_refs,
                condition.source_refs,
            )
