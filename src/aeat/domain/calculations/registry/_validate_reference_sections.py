"""Specialized snapshot-reference section walkers.

Per-section walkers that traverse the typed-ID fields of a
:class:`ModeloRevision` and call into an ``IdReferenceChecker`` to
accumulate dangling-reference diagnostics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._validate_reference_checker import IdReferenceChecker

if TYPE_CHECKING:
    from ._schema import ModeloRevision


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


def check_construct_refs(checker: IdReferenceChecker, revision: ModeloRevision) -> None:
    for construct in revision.constructs:
        ctp = f"construct {construct.id}"
        for attr, id_set_name in _CONSTRUCT_MEMBER_AXES:
            checker.chk_tuple(f"{ctp}.{attr}", getattr(construct, attr), getattr(checker, id_set_name))
        checker.chk_legal_source_refs(ctp, construct.legal_refs, construct.source_refs)


def check_dependency_classification_refs(checker: IdReferenceChecker, revision: ModeloRevision) -> None:
    for classification in revision.dependency_classifications:
        dcp = f"dependency_classification {classification.id}"
        checker.chk_tuple(f"{dcp}.target_constructs", classification.target_constructs, checker.construct_ids)
        checker.chk_tuple(f"{dcp}.relation_refs", classification.relation_refs, checker.relation_ids)
        checker.chk_legal_source_refs(dcp, classification.legal_refs, classification.source_refs)


def check_algorithm_provider_refs(checker: IdReferenceChecker, revision: ModeloRevision) -> None:
    for provider in revision.algorithm_providers:
        avp = f"algorithm_provider {provider.id}"
        checker.chk_legal_source_refs(avp, provider.legal_refs, provider.source_refs)


def check_algorithm_binding_refs(checker: IdReferenceChecker, revision: ModeloRevision) -> None:
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
                    f"{checker.prefix}: {abp}.inputs.{input_name} references unknown id {input_id!r}",
                )
        for output_name, output_id in alg_binding.outputs.items():
            checker.chk(f"{abp}.outputs.{output_name}", output_id, checker.casilla_ids)
        checker.chk_tuple(f"{abp}.constants", alg_binding.constants, checker.parameter_ids)
        checker.chk_legal_source_refs(abp, alg_binding.legal_refs, alg_binding.source_refs)


def check_export_layout_refs(checker: IdReferenceChecker, revision: ModeloRevision) -> None:
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


def check_binding_selector_shapes(checker: IdReferenceChecker, revision: ModeloRevision) -> None:
    """Validate selectors for sources with a registered discriminated shape.

    Args:
        checker: The reference checker whose failures list accumulates
            any selector-shape validation errors found.
        revision: The :class:`ModeloRevision` whose binding selectors are
            validated.
    """
    from ._bindings import validate_binding_selector_shape

    for binding in revision.bindings:
        checker.failures.extend(f"{checker.prefix}: {fail}" for fail in validate_binding_selector_shape(binding))
