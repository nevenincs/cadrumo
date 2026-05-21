"""Referential-integrity validation for registry snapshots."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ._errors import RegistryValidationError
from ._schema import ModeloRevision

if TYPE_CHECKING:
    from ._snapshot import RegistrySnapshot

class _IdReferenceChecker:
    """Accumulates dangling typed-ID reference diagnostics for one snapshot.

    Holds the per-kind ID sets and a failures buffer so the per-kind
    walkers below can stay focused on their own field paths instead of
    juggling closure state.
    """

    __slots__ = (
        "application_link_ids",
        "binding_ids",
        "casilla_ids",
        "construct_ids",
        "cross_reference_ids",
        "deadline_window_ids",
        "dependency_classification_ids",
        "export_field_ids",
        "export_layout_ids",
        "extraction_profile_ids",
        "failures",
        "formula_ids",
        "legal_ids",
        "parameter_ids",
        "prefix",
        "relation_ids",
        "source_ids",
        "support_removal_decision_ids",
        "verification_expectation_ids",
        "workbook_parity_ids",
    )

    def __init__(self, snapshot: RegistrySnapshot) -> None:
        revision = snapshot.revision
        self.prefix = f"snapshot modelo {snapshot.modelo.id} revision {revision.id}"
        self.failures: list[str] = []
        self.casilla_ids = {c.id for c in revision.casillas}
        self.formula_ids = {f.id for f in revision.formulas}
        self.parameter_ids = {p.id for p in revision.parameters}
        self.binding_ids = {b.id for b in revision.bindings}
        self.relation_ids = {r.id for r in revision.relations}
        self.export_layout_ids = {lay.id for lay in revision.export_layouts}
        self.export_field_ids = {
            field.id for lay in revision.export_layouts for rec in lay.records for field in rec.fields
        }
        self.extraction_profile_ids = {p.id for p in revision.extraction_profiles}
        self.cross_reference_ids = {cr.id for cr in revision.live_cross_references}
        self.workbook_parity_ids = {w.id for w in revision.workbook_parity_refs}
        self.verification_expectation_ids = {e.id for e in revision.verification_expectations}
        self.application_link_ids = {lk.id for lk in revision.application_links}
        self.deadline_window_ids = {dw.id for dw in revision.deadline_windows}
        self.support_removal_decision_ids = {d.id for d in revision.support_removal_decisions}
        self.construct_ids = {c.id for c in revision.constructs}
        self.dependency_classification_ids = {dc.id for dc in revision.dependency_classifications}
        self.legal_ids = set(snapshot.legal)
        self.source_ids = set(snapshot.sources)

    def chk(self, field_path: str, value: str, id_set: set[str]) -> None:
        if value not in id_set:
            self.failures.append(f"{self.prefix}: {field_path} references unknown id {value!r}")

    def chk_opt(self, field_path: str, value: str | None, id_set: set[str]) -> None:
        if value is not None and value not in id_set:
            self.failures.append(f"{self.prefix}: {field_path} references unknown id {value!r}")

    def chk_tuple(self, field_path: str, values: tuple[str, ...], id_set: set[str]) -> None:
        for value in values:
            if value not in id_set:
                self.failures.append(f"{self.prefix}: {field_path} references unknown id {value!r}")

    def chk_legal_source_refs(self, owner: str, legal_refs: tuple[str, ...], source_refs: tuple[str, ...]) -> None:
        """Single-call helper for the (legal_refs, source_refs) pair every record carries."""
        self.chk_tuple(f"{owner}.legal_refs", legal_refs, self.legal_ids)
        self.chk_tuple(f"{owner}.source_refs", source_refs, self.source_ids)


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
    _check_cross_domain_snapshot_routing(checker, snapshot)
    _check_binding_selector_shapes(checker, revision)

    if checker.failures:
        raise RegistryValidationError(
            "referential integrity check failed:\n" + "\n".join(f" - {f}" for f in sorted(checker.failures))
        )


def _check_casilla_refs(checker: _IdReferenceChecker, revision: ModeloRevision) -> None:
    for casilla in revision.casillas:
        cp = f"casilla {casilla.id}"
        checker.chk_opt(f"{cp}.formula", casilla.formula, checker.formula_ids)
        checker.chk_opt(f"{cp}.binding", casilla.binding, checker.binding_ids)
        checker.chk_tuple(f"{cp}.export_refs", casilla.export_refs, checker.export_field_ids)
        checker.chk_legal_source_refs(cp, casilla.legal_refs, casilla.source_refs)
        if casilla.constraints is not None:
            checker.chk_legal_source_refs(
                f"{cp}.constraints", casilla.constraints.legal_refs, casilla.constraints.source_refs
            )


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
        checker.chk_tuple(f"{ep}.target_casillas", profile.target_casillas, checker.casilla_ids)
        checker.chk_legal_source_refs(ep, profile.legal_refs, profile.source_refs)


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
            checker.failures.append(
                f"{checker.prefix}: {abp}.provider references unknown id {alg_binding.provider!r}"
            )
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


class CrossDomainSnapshotCheck(Protocol):
    """Snapshot-time referential-integrity check owned by a peer domain.

    A peer domain (for example :mod:`aeat.domain.renta`) may need to
    assert that the casilla ids it routes to are real casillas on a
    registry snapshot. The registry must not import the peer domain
    directly — that reverses the dependency direction the restructure
    ADR fixes (defect F7, Wave 2 P04). Instead the peer domain
    registers a :class:`CrossDomainSnapshotCheck` via
    :func:`register_cross_domain_snapshot_check`; the registry calls
    every registered check at snapshot-build time without naming the
    peer.

    A check receives the modelo id and the snapshot's casilla id set
    and returns a list of failure strings (empty when consistent).
    """

    def __call__(self, modelo_id: str, casilla_ids: frozenset[str]) -> list[str]: ...


_CROSS_DOMAIN_SNAPSHOT_CHECKS: list[CrossDomainSnapshotCheck] = []


def register_cross_domain_snapshot_check(check: CrossDomainSnapshotCheck) -> None:
    """Register a peer-domain snapshot referential-integrity check.

    Idempotent: registering the same callable twice is a no-op so a
    peer-domain module re-imported in a fresh interpreter (or under
    test reload) does not stack duplicate checks.
    """

    if check not in _CROSS_DOMAIN_SNAPSHOT_CHECKS:
        _CROSS_DOMAIN_SNAPSHOT_CHECKS.append(check)


def _check_cross_domain_snapshot_routing(checker: _IdReferenceChecker, snapshot: RegistrySnapshot) -> None:
    """Run every registered peer-domain referential-integrity check.

    The registry depends on the abstract :class:`CrossDomainSnapshotCheck`
    Protocol only. Concrete checks (such as the renta first-slice
    routing gate) are injected by their owning domain at import time
    via :func:`register_cross_domain_snapshot_check`.

    Modelo 100 has a known-required cross-domain gate -- the renta
    first-slice routing referential-integrity check owned by
    :mod:`aeat.domain.renta`. That check registers itself only as an
    import side effect of the ``renta`` package. A ``build_snapshot``
    caller that never imports ``renta`` would otherwise validate an
    M100 snapshot with the gate silently absent. Rather than skip a
    known-required gate, fail loudly so the missing registration
    surfaces at snapshot build instead of as a later runtime KeyError.
    """

    casilla_ids = frozenset(checker.casilla_ids)
    if snapshot.modelo.id == "100" and not _CROSS_DOMAIN_SNAPSHOT_CHECKS:
        checker.failures.append(
            f"{checker.prefix}: modelo 100 requires the renta first-slice "
            "routing cross-domain snapshot check, but no cross-domain checks "
            "are registered -- import aeat.domain.renta at the composition "
            "point that builds the snapshot so register_cross_domain_snapshot_check "
            "runs before validation"
        )
    for check in _CROSS_DOMAIN_SNAPSHOT_CHECKS:
        for failure in check(snapshot.modelo.id, casilla_ids):
            checker.failures.append(f"{checker.prefix}: {failure}")


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
        checker.failures.extend(
            f"{checker.prefix}: {fail}" for fail in validate_binding_selector_shape(binding)
        )
