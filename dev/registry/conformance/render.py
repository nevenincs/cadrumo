"""Render conformance reports and coverage as operator-facing text."""

from __future__ import annotations

import json
from typing import cast

from .manager import (
    COORDINATE_CLASSIFICATIONS,
    NOT_MEASURED,
    ConformanceCoordinateMatrix,
    ConformanceReport,
    CoverageReport,
    RevisionConformancePayload,
)


def render_report(report: ConformanceReport) -> str:
    """Render the conformance report as greppable ``key=value`` rows."""
    lines = [_conformance_summary_line(report)]
    lines.extend(_conformance_census_lines(report))
    lines.extend(_conformance_row_lines(report))
    lines.extend(_annual_matrix_lines(report))
    lines.extend(_oracle_gap_lines(report))
    lines.extend(_unused_axis_lines(report))
    lines.extend(_locale_unavailable_lines(report))
    lines.append(_reading_note(report))
    return "\n".join(lines)


def _conformance_summary_line(report: ConformanceReport) -> str:
    return _kv_line(
        "summary",
        registry_validated=report.registry_validated,
        revisions=report.revision_count,
        modelos=report.modelo_count,
        engineered_by_declared=report.engineered_by_declared_count,
        independent_check_coverage=report.independent_check_coverage,
        reconciled_casillas=report.reconciled_casillas,
        independently_checked_casillas=report.independently_checked_casillas,
        reconciles_nothing_rows=report.reconciles_nothing_row_count,
        grounding_findings=report.grounding_finding_count,
        modelo_scope_classification_findings=report.modelo_scope_classification_finding_count,
        required_coverage_gap_rows=report.required_coverage_gap_row_count,
        coverage_unmeasured_rows=report.coverage_unmeasured_row_count,
        unattributed_oracle_payloads=len(report.unattributed_oracle_payloads),
        unmatched_oracle_evidence=len(report.unmatched_oracle_evidence),
        bundled_oracle_payloads=report.bundled_oracle_payload_count,
        scope_diagnostics=report.scope_diagnostic_count,
        unattributed_scope_diagnostics=report.unattributed_scope_diagnostic_count,
        locale_unavailable_modelos=len(report.locale_unavailable_modelos),
    )


def _conformance_census_lines(report: ConformanceReport) -> list[str]:
    return [
        _kv_line("census", review_status=status, revisions=count)
        for status, count in sorted(report.review_status_census.items())
    ]


def _conformance_row_lines(report: ConformanceReport) -> list[str]:
    return [_conformance_row_line(row) for row in report.rows]


def _conformance_row_line(row: RevisionConformancePayload) -> str:
    fields: dict[str, object] = {
        "modelo": row.modelo,
        "revision": row.revision,
        "registry_validated": row.registry_validated,
        "review_status": row.review_status,
        "engineered_by": row.engineered_by,
        # Named EXACTLY as the payload names it, and carrying exactly what the
        # payload carries. No bare reviewer column is emitted here: the joined
        # form contains the name, so nothing is lost by omitting it.
        "reviewed_by_attribution": row.reviewed_by_attribution,
        "reviewed_at": row.reviewed_at,
        "reviewed_against": row.reviewed_against,
        "calc_grade": row.calc_grade,
        "casillas": row.casillas,
        "formulas": row.formulas,
        "bindings": row.bindings,
        "verification_expectations": row.verification_expectations,
        "extraction_profiles": row.extraction_profiles,
        "completeness_manifest": row.completeness_manifest,
        "fixed_width_export": row.fixed_width_export,
        "xml_dictionary_export": row.xml_dictionary_export,
        "reconciled_casillas": row.reconciled_casillas,
        "declared_grounded_casillas": row.declared_grounded_casillas,
        "independently_checked_casillas": row.independently_checked_casillas,
        "independent_check_coverage": row.independent_check_coverage,
        "grounding_findings": row.grounding_findings,
        "required_coverage_gap_tiers": row.required_coverage_gap_tiers,
        "model_law_authority_scope": row.model_law_authority_scope,
        "modelo_calculation_class": row.modelo_calculation_class,
        "modelo_tax_domain": row.modelo_tax_domain,
        "modelo_scope_classification_findings": row.modelo_scope_classification_findings,
        "scope_diagnostics": row.scope_diagnostics,
        "latest_revision_probed": row.latest_revision_probed,
        "support_probe_describes_this_revision": row.support_probe_describes_this_revision,
    }
    fields.update(_locale_row_fields(row))
    fields.update(_construct_evidence_row_fields(row))
    return _kv_line("row", **fields)


def _locale_row_fields(row: RevisionConformancePayload) -> dict[str, object]:
    locale = row.locale
    return {
        "locale_audited_locales": None if locale is None else len(locale.audited_locales),
        "locale_labels_required_per_locale": None if locale is None else locale.labels_required_per_locale,
        "locale_labels_translated": None if locale is None else locale.labels_translated,
        "locale_complete_locales": None if locale is None else locale.complete_locales,
        "locale_stale_keys": None if locale is None else locale.stale_keys,
    }


def _construct_evidence_row_fields(row: RevisionConformancePayload) -> dict[str, object]:
    evidence = row.construct_evidence
    return {
        "construct_evidence_rows": None if evidence is None else len(evidence.rows),
        "construct_evidence_gaps": None if evidence is None else len(evidence.gaps),
        "construct_evidence_filing_gaps": None if evidence is None else len(evidence.filing_gaps),
        "construct_evidence_inspection_gaps": None if evidence is None else len(evidence.inspection_gaps),
        "construct_evidence_authority_scope": row.construct_evidence_authority_scope,
        "casilla_provenance_traces": len(row.casilla_provenance),
    }


def _annual_matrix_lines(report: ConformanceReport) -> list[str]:
    matrix = report.annual_matrix
    lines = [
        _kv_line(
            "annual_matrix",
            registry_validated=report.registry_validated,
            measured=matrix is not None,
            coordinates=None if matrix is None else len(matrix.coordinates),
        ),
    ]
    if matrix is None:
        return lines
    lines.extend(_annual_coordinate_lines(matrix))
    lines.extend(_annual_schema_layout_lines(matrix))
    lines.extend(_annual_classification_lines(matrix))
    return lines


def _annual_coordinate_lines(matrix: ConformanceCoordinateMatrix) -> list[str]:
    return [
        _kv_line(
            "annual_coordinate",
            modelo=coordinate.modelo,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            law_selected_revision=coordinate.law_selected_revision,
            authority_scope=coordinate.authority_scope,
            classification=coordinate.classification,
            provisional=coordinate.provisional,
            schema_identity_measurement=coordinate.schema_comparison.identity_measurement,
            schema_printed_form_membership=coordinate.schema_comparison.printed_form_membership,
            schema_xsd_only_attributes=coordinate.schema_comparison.xsd_only_attributes,
            schema_identity_divergence_count=coordinate.schema_comparison.identity_divergence_count,
        )
        for coordinate in matrix.coordinates
    ]


def _annual_schema_layout_lines(matrix: ConformanceCoordinateMatrix) -> list[str]:
    return [
        _kv_line(
            "annual_schema_layout",
            modelo=coordinate.modelo,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            law_selected_revision=coordinate.law_selected_revision,
            authority_scope=coordinate.authority_scope,
            layout_id=layout.layout_id,
            layout_format=layout.layout_format,
            identity_measurement=layout.identity_measurement,
            registry_casilla_count=layout.registry_casilla_count,
            dictionary_entry_count=layout.dictionary_entry_count,
            dictionary_casilla_count=layout.dictionary_casilla_count,
            identity_divergence_count=layout.identity_divergence_count,
            missing_casilla_ids=layout.missing_casilla_ids,
            extra_casilla_ids=layout.extra_casilla_ids,
            printed_form_membership=layout.printed_form_membership,
            xsd_only_attributes=layout.xsd_only_attributes,
            dictionary_source_ref=layout.dictionary_source_ref,
            parser_exposed_attributes=layout.parser_exposed_attributes,
            unmeasured_attributes=layout.unmeasured_attributes,
            diagnostic=layout.diagnostic,
        )
        for coordinate in matrix.coordinates
        for layout in coordinate.schema_comparison.layout_comparisons
    ]


def _annual_classification_lines(matrix: ConformanceCoordinateMatrix) -> list[str]:
    return [
        _kv_line(
            "annual_coordinate_classification",
            classification=classification,
            count=matrix.classification_census[classification],
        )
        for classification in COORDINATE_CLASSIFICATIONS
    ]


def _oracle_gap_lines(report: ConformanceReport) -> list[str]:
    return [
        _kv_line("oracle_gap", kind="unattributed_payload", corpus=item.corpus, payload=item.payload_name, gap=item.gap)
        for item in report.unattributed_oracle_payloads
    ] + [
        _kv_line("oracle_gap", kind="unmatched_evidence", corpus=item.corpus, payload=item.payload_name, gap=item.gap)
        for item in report.unmatched_oracle_evidence
    ]


def _unused_axis_lines(report: ConformanceReport) -> list[str]:
    return [
        _kv_line("unused_axis", axis=axis, population=report.declared_axis_population.get(axis, 0))
        for axis in report.unused_declared_axes
    ]


def _locale_unavailable_lines(report: ConformanceReport) -> list[str]:
    return [_kv_line("locale_unavailable", modelo=modelo) for modelo in report.locale_unavailable_modelos]


def render_coverage(coverage: CoverageReport) -> str:
    """Render the per-axis coverage report as greppable ``key=value`` rows."""
    lines = [
        _kv_line(
            "summary",
            registry_validated=coverage.registry_validated,
            revisions=coverage.revision_count,
            modelos=coverage.modelo_count,
            axes=len(coverage.rows),
        ),
    ]
    for row in coverage.rows:
        # The caveat key is OMITTED when absent rather than rendered as n/a: an
        # axis needing no caveat has not "failed to measure" one, and n/a is
        # reserved for a measurement nobody took.
        fields: dict[str, object] = {
            "axis": row.axis,
            "scope": row.scope,
            "measured": row.measured,
            "population": row.population,
            "fraction": row.fraction,
        }
        if row.caveat is not None:
            fields["caveat"] = row.caveat
        lines.append(_kv_line("axis", **fields))
    lines.append(
        f"note {NOT_MEASURED} means NOT MEASURED or NO CLAIM MADE, never zero; "
        "every independent-check figure is coverage of independent checking, never correctness",
    )
    return "\n".join(lines)


def vacuity_warning(report: ConformanceReport) -> str | None:
    """Return the warning record for a screen that composed nothing, or :data:`None`.

    The screens keep their zero exit — refusal belongs to ``audit`` — but an
    empty render that said nothing would be indistinguishable from a clean
    registry, which is the false-green shape this whole surface exists to
    remove. A record line rather than prose, so a caller greps it.
    """
    if report.rows:
        return None
    return (
        'warning rows=0 detail="composed no revision rows at all; every count above is vacuous '
        'and describes the read, not the registry"'
    )


def _reading_note(report: ConformanceReport) -> str:
    """Return the standing reading note every rendered report ends with."""
    degraded = (
        ""
        if report.registry_validated
        else (
            " DEGRADED READ: rows are stamped registry_validated=false and the evidence-tier coverage, "
            "and support-probe axes were not consulted at all."
        )
    )
    return (
        f"note {NOT_MEASURED} means NOT MEASURED or NO CLAIM MADE, never zero, while '-' is a real "
        "empty list; independent_check_coverage is coverage of independent checking, never "
        "correctness; modelo_scope_classification_findings repeats across a modelo's revision rows "
        f"and must not be summed over rows.{degraded}"
    )


def _kv_line(record: str, **fields: object) -> str:
    """Render one greppable ``record key=value ...`` line."""
    parts = [record]
    parts.extend(f"{key}={_render_value(value)}" for key, value in fields.items())
    return " ".join(parts)


def _render_value(value: object) -> str:
    """Render one field value, keeping absence distinct from zero."""
    if value is None:
        return NOT_MEASURED
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, tuple):
        return _render_tuple_value(cast(tuple[object, ...], value))
    return _render_text_value(str(value))


def _render_tuple_value(items: tuple[object, ...]) -> str:
    """Render tuple-valued fields as comma-separated values or a true empty list."""
    return ",".join(str(item) for item in items) if items else "-"


def _render_text_value(text: str) -> str:
    """Quote text values that would otherwise break the key-value row format."""
    if not text or any(character in text for character in ' \t"='):
        return json.dumps(text)
    return text
