"""Core revision record-section validation helpers.

Validates the primary record sections declared on a
:class:`~domain.calculations.registry.ModeloRevision`: casillas, formulas,
parameters, bindings, and extraction profiles. Each validator checks local
reference closure plus legal/source grounding through
:class:`~domain.calculations.registry._validate_evidence.EvidenceValidator`.

See Also:
    :func:`~domain.calculations.registry._validate_revision_sections.validate_revision_definition`
        Per-revision dispatcher that invokes these record-section validators.
    :mod:`~domain.calculations.registry._validate_formulas`
        Formula-expression validation used by the formula section.
    :mod:`~domain.calculations.registry._validate_extraction_profiles`
        Extraction-profile artefact and specimen gates used by this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ._binding_selector_utils import selector_as_dict
from ._bindings import (
    is_layout_binding_selector,
    validate_binding_selector_shape,
)
from ._ids import BindingId, CasillaId, RelationId
from ._schema import DataBindingDefinition, FormulaDefinition, LegalReference, ModeloRevision, SourceReference
from ._validate_evidence import EvidenceValidator
from ._validate_extraction_profiles import (
    validate_bbox_anchor_consistency,
    validate_declaracion_pdf_round_trip_gate,
    validate_declaracion_pdf_specimen_gate,
    validate_dotted_callable,
    validate_extraction_profile_artefacts,
)
from ._validate_formulas import validate_formula_expression
from ._validate_helpers import missing_refs
from ._validate_revision_identity import duplicates
from ._validate_revision_rules import validate_dated_values

_CASILLA_METADATA_SOURCE_TIERS = ("official_source_guidance", "layout_authority")


def validate_casilla_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    formulas: Mapping[str, FormulaDefinition],
    bindings: set[BindingId],
    export_field_ids: set[str],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append casilla metadata, formula, binding, and export-ref failures.

    The :class:`~domain.calculations.registry.ModeloRevision` supplies
    :class:`~domain.calculations.registry.CasillaDefinition` rows. Each
    casilla, constraint, and alias must be legally/source grounded; formula,
    binding, alternate-binding, and export-field references must point at ids in
    the shared revision-validation context.
    """
    for casilla in revision.casillas:
        owner = f"casilla {casilla.id}"
        failures.extend(missing_refs(prefix, owner, casilla.legal_refs, legal_refs, "legal"))
        failures.extend(missing_refs(prefix, owner, casilla.source_refs, source_refs, "source"))
        failures.extend(
            evidence.require_any_source_tier(prefix, owner, casilla.source_refs, _CASILLA_METADATA_SOURCE_TIERS)
        )
        if casilla.constraints is not None:
            constraint_owner = f"casilla {casilla.id} constraints"
            failures.extend(
                missing_refs(prefix, constraint_owner, casilla.constraints.legal_refs, legal_refs, "legal"),
            )
            failures.extend(
                missing_refs(prefix, constraint_owner, casilla.constraints.source_refs, source_refs, "source"),
            )
            failures.extend(
                evidence.require_any_source_tier(
                    prefix,
                    constraint_owner,
                    casilla.constraints.source_refs,
                    _CASILLA_METADATA_SOURCE_TIERS,
                ),
            )
        for alias in casilla.aliases:
            alias_owner = f"casilla {casilla.id} alias {alias.label!r}"
            failures.extend(missing_refs(prefix, alias_owner, alias.legal_refs, legal_refs, "legal"))
            failures.extend(missing_refs(prefix, alias_owner, alias.source_refs, source_refs, "source"))
            failures.extend(
                evidence.require_any_source_tier(
                    prefix,
                    alias_owner,
                    alias.source_refs,
                    _CASILLA_METADATA_SOURCE_TIERS,
                ),
            )
        if casilla.formula is not None and casilla.formula not in formulas:
            failures.append(f"{prefix}: casilla {casilla.id!r} references unknown formula {casilla.formula!r}")
        if (
            casilla.formula is not None
            and casilla.formula in formulas
            and formulas[casilla.formula].target_casilla_id != casilla.id
        ):
            failures.append(
                f"{prefix}: casilla {casilla.id!r} references formula {casilla.formula!r} "
                f"targeting {formulas[casilla.formula].target_casilla_id!r}",
            )
        if casilla.binding is not None and casilla.binding not in bindings:
            failures.append(f"{prefix}: casilla {casilla.id!r} references unknown binding {casilla.binding!r}")
        for binding in casilla.alternate_bindings:
            if binding not in bindings:
                failures.append(
                    f"{prefix}: casilla {casilla.id!r} references unknown alternate binding {binding!r}",
                )
        for export_ref in casilla.export_refs:
            if export_ref not in export_field_ids:
                failures.append(f"{prefix}: casilla {casilla.id!r} references unknown export field {export_ref!r}")


def validate_formula_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    casillas: set[CasillaId],
    bindings: set[BindingId],
    parameters: set[str],
    relations: set[RelationId],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append formula reference, evidence, citation, and duplicate-target failures.

    The :class:`~domain.calculations.registry.ModeloRevision` supplies
    :class:`~domain.calculations.registry.FormulaDefinition` rows. Each
    formula must cite official-source guidance, target a declared
    :class:`~domain.calculations.registry.CasillaId`, and contain only
    expression references accepted by
    :func:`~domain.calculations.registry._validate_formulas.validate_formula_expression`.
    """
    for formula in revision.formulas:
        owner = f"formula {formula.id}"
        failures.extend(missing_refs(prefix, owner, formula.legal_refs, legal_refs, "legal"))
        failures.extend(missing_refs(prefix, owner, formula.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(prefix, owner, formula.source_refs, "official_source_guidance"))
        failures.extend(
            evidence.validate_source_citations(
                prefix,
                owner,
                formula.source_refs,
                formula.source_citations,
                "official_source_guidance",
            ),
        )
        if formula.target_casilla_id not in casillas:
            failures.append(f"{prefix}: formula {formula.id!r} targets unknown casilla {formula.target_casilla_id!r}")
        failures.extend(
            validate_formula_expression(
                prefix,
                formula.id,
                formula.expression,
                casillas=casillas,
                bindings=bindings,
                parameters=parameters,
                relations=relations,
            ),
        )

    for target in sorted(duplicates([formula.target_casilla_id for formula in revision.formulas])):
        failures.append(f"{prefix}: duplicate formula target {target!r}")


def validate_parameter_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append parameter reference, citation, and dated-value failures.

    The :class:`~domain.calculations.registry.ModeloRevision` supplies
    :class:`~domain.calculations.registry.ParameterDefinition` rows. Each
    parameter must carry known legal/source refs, official-source citations, and
    valid dated-value windows.
    """
    for parameter in revision.parameters:
        owner = f"parameter {parameter.id}"
        failures.extend(missing_refs(prefix, owner, parameter.legal_refs, legal_refs, "legal"))
        failures.extend(missing_refs(prefix, owner, parameter.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(prefix, owner, parameter.source_refs, "official_source_guidance"))
        failures.extend(
            evidence.validate_source_citations(
                prefix,
                owner,
                parameter.source_refs,
                parameter.source_citations,
                "official_source_guidance",
            ),
        )
        failures.extend(validate_dated_values(prefix, parameter.id, parameter.values))


def validate_binding_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append binding selector-shape, reference, and evidence failures.

    The :class:`~domain.calculations.registry.ModeloRevision` supplies
    :class:`~domain.calculations.registry.DataBindingDefinition` rows.
    Selectors are validated through the single binding-selector contract; layout
    bindings require layout-authority evidence, while other bindings require
    official-source guidance and source citations.
    """
    for binding in revision.bindings:
        failures.extend(f"{prefix}: {fail}" for fail in validate_binding_selector_shape(binding))
    for binding in revision.bindings:
        owner = f"binding {binding.id}"
        failures.extend(missing_refs(prefix, owner, binding.legal_refs, legal_refs, "legal"))
        failures.extend(missing_refs(prefix, owner, binding.source_refs, source_refs, "source"))
        if _is_layout_binding(binding):
            failures.extend(evidence.require_source_tier(prefix, owner, binding.source_refs, "layout_authority"))
        else:
            failures.extend(
                evidence.require_source_tier(prefix, owner, binding.source_refs, "official_source_guidance"),
            )
            failures.extend(
                evidence.validate_source_citations(
                    prefix,
                    owner,
                    binding.source_refs,
                    binding.source_citations,
                    "official_source_guidance",
                ),
            )
    # The per-source op/fact invariants for every family (invoice, counterpart,
    # the four ledger families, the four detail-record families, withholding, and
    # previous_filing) are run by the single ``validate_binding_selector_shape``
    # dispatch loop above. The prior separate try/except per-family calls here
    # were a redundant second validation path; one path now covers every family.


def _is_layout_binding(binding: DataBindingDefinition) -> bool:
    """Layout-binding predicate, delegated to the typed manual_input shape."""
    return is_layout_binding_selector(selector_as_dict(binding))


def validate_extraction_profile_section(
    failures: list[str],
    *,
    prefix: str,
    modelo_id: str,
    revision: ModeloRevision,
    casillas: set[CasillaId],
    exported_casillas: set[CasillaId],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
    corpus_root: Path | None = None,
) -> None:
    """Append extraction-profile reference, artefact, and specimen failures.

    The :class:`~domain.calculations.registry.ModeloRevision` supplies
    :class:`~domain.calculations.registry._schema_extraction.ExtractionProfileDefinition`
    rows. Each profile must target declared/exported casillas as required,
    declare layout-authority evidence, use a dotted parser callable, and satisfy
    bundled justificante PDF specimen/round-trip gates when a corpus root is
    available.
    """
    for profile in revision.extraction_profiles:
        owner = f"extraction profile {profile.id}"
        failures.extend(missing_refs(prefix, owner, profile.legal_refs, legal_refs, "legal"))
        failures.extend(missing_refs(prefix, owner, profile.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(prefix, owner, profile.source_refs, "layout_authority"))
        failures.extend(validate_dotted_callable(prefix, owner, profile.parser))
        target_casilla_ids = tuple(t.casilla_id for t in profile.target_casillas)
        for casilla_id in target_casilla_ids:
            if casilla_id not in casillas:
                failures.append(f"{prefix}: {owner} references unknown casilla {casilla_id!r}")
        if profile.surface == "export_record" or "submitted_file" in profile.accepted_artefact_kinds:
            missing_exported_casillas = sorted(set(target_casilla_ids).difference(exported_casillas))
            if missing_exported_casillas:
                failures.append(
                    f"{prefix}: export_record extraction profile {profile.id!r} targets casillas without "
                    f"export fields {missing_exported_casillas!r}",
                )
        failures.extend(validate_extraction_profile_artefacts(prefix, profile))
        for target in profile.target_casillas:
            failures.extend(validate_bbox_anchor_consistency(prefix, target))
        if corpus_root is not None:
            failures.extend(validate_declaracion_pdf_specimen_gate(prefix, modelo_id, profile, corpus_root))
            failures.extend(validate_declaracion_pdf_round_trip_gate(prefix, modelo_id, profile, corpus_root))
