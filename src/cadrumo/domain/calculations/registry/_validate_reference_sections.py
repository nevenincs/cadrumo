"""Specialized snapshot-reference section walkers.

Per-section walkers that traverse the typed-ID fields of a
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` and call into an
:class:`~cadrumo.domain.calculations.registry.validate_reference_checker.IdReferenceChecker`
to accumulate dangling-reference diagnostics.

See Also:
    :func:`domain.calculations.registry._validate_references.check_all_id_references`
        Snapshot-level referential-integrity gate that invokes these walkers.
    :mod:`cadrumo.domain.calculations.registry.validate_reference_checker`
        Accumulator that owns the per-kind typed-id sets used here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._validate_reference_checker import IdReferenceChecker

if TYPE_CHECKING:
    from .schema import ModeloRevision


_CONSTRUCT_MEMBER_AXES: tuple[tuple[str, str], ...] = (
    ("casilla_ids", "casilla_ids"),
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
    ("filing_schedules", "filing_schedule_ids"),
    ("dependency_classifications", "dependency_classification_ids"),
)


def check_construct_refs(checker: IdReferenceChecker, revision: ModeloRevision) -> None:
    """Check construct member references for one revision.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    construct declarations. The
    :class:`~cadrumo.domain.calculations.registry.validate_reference_checker.IdReferenceChecker`
    supplies the typed member-id sets and legal/source-ref closure checks.
    """
    for construct in revision.constructs:
        ctp = f"construct {construct.id}"
        for attr, id_set_name in _CONSTRUCT_MEMBER_AXES:
            checker.chk_tuple(f"{ctp}.{attr}", getattr(construct, attr), getattr(checker, id_set_name))
        checker.chk_legal_source_refs(ctp, construct.legal_refs, construct.source_refs)


def check_dependency_classification_refs(checker: IdReferenceChecker, revision: ModeloRevision) -> None:
    """Check dependency-classification construct and relation refs.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    dependency classifications. The checker verifies target constructs,
    relation refs, and legal/source refs against the snapshot id sets.
    """
    for classification in revision.dependency_classifications:
        dcp = f"dependency_classification {classification.id}"
        checker.chk_tuple(f"{dcp}.target_constructs", classification.target_constructs, checker.construct_ids)
        checker.chk_tuple(f"{dcp}.relation_refs", classification.relation_refs, checker.relation_ids)
        checker.chk_legal_source_refs(dcp, classification.legal_refs, classification.source_refs)


def check_export_layout_refs(checker: IdReferenceChecker, revision: ModeloRevision) -> None:
    """Check export-layout record and field references for one revision.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    export layouts. The checker validates dictionary source refs, record
    positive-casilla gates, row-field casillas, field casilla/binding refs, and
    field legal/source refs.
    """
    for layout in revision.export_layouts:
        lyp = f"export_layout {layout.id}"
        checker.chk_legal_source_refs(lyp, layout.legal_refs, layout.source_refs)
        for source_ref in layout.source_refs:
            if source_ref in checker.provenance_only_source_ids:
                checker.failures.append(
                    f"{checker.prefix}: {lyp}.source_refs names {source_ref!r}, which the catalogue "
                    "declares provenance_only -- corpus evidence, not a layout authority",
                )
        if layout.dictionary_source_ref is not None:
            checker.chk(f"{lyp}.dictionary_source_ref", layout.dictionary_source_ref, checker.source_ids)
        for record in layout.records:
            rcp = f"{lyp}.record {record.id}"
            checker.chk_opt(
                f"{rcp}.requires_positive_casilla_id",
                record.requires_positive_casilla_id,
                checker.casilla_ids,
            )
            for row_field, casilla_id in record.row_field_casilla_ids.items():
                checker.chk(f"{rcp}.row_field_casilla_ids.{row_field}", casilla_id, checker.casilla_ids)
            for field in record.fields:
                efp = f"{rcp}.field {field.id}"
                checker.chk_opt(f"{efp}.endpoint_casilla_id", field.endpoint_casilla_id, checker.casilla_ids)
                checker.chk_opt(f"{efp}.binding", field.binding, checker.binding_ids)
                checker.chk_legal_source_refs(efp, field.legal_refs, field.source_refs)


def check_binding_selector_shapes(checker: IdReferenceChecker, revision: ModeloRevision) -> None:
    """Validate selectors for sources with a registered discriminated shape.

    Args:
        checker: The reference checker whose failures list accumulates
            any selector-shape validation errors found.
        revision: The
            :class:`~cadrumo.domain.calculations.registry.ModeloRevision` whose
            binding selectors are validated.
    """
    from .bindings import validate_binding_selector_shape

    for binding in revision.bindings:
        checker.failures.extend(f"{checker.prefix}: {fail}" for fail in validate_binding_selector_shape(binding))
