"""Probe the bundled registry authority for a per-modelo capability matrix.

This module composes existing registry-authority introspection; it does not
re-implement registry loading, calc-closure derivation, or export-layout
parsing. Every capability below is read directly off the loaded
:class:`~domain.calculations.registry.ModeloDefinition` /
:class:`~domain.calculations.registry.ModeloRevision` records, or derived
via the existing :func:`~domain.calculations.registry.calculation_closure_casilla_ids`
helper.

Coverage honesty (``no-silent-under-declaration``): a modelo missing a
capability reports an explicit gap (``False`` / empty tuple), never a
fabricated positive.

See Also:
    :class:`~domain.calculations.registry.ModeloEntry`
        Production support-matrix row carrying the expanded registry query
        surface.
    :func:`~domain.calculations.registry.build_support_matrix`
        Domain builder used by the production query service.
    :func:`~application.modelo.registry_support_matrix`
        Application facade exposed to the operator CLI.
    :mod:`~dev.registry.matrix.cli`
        Developer command that renders these probe rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from aeat.domain.calculations.registry import (
    ModeloDefinition,
    ModeloRevision,
    ValidatedRegistryAuthority,
    bundled_authority,
    calculation_closure_casilla_ids,
)

__all__ = [
    "ModeloCapabilityRow",
    "build_capability_matrix",
    "render_matrix_table",
]

_COLUMN_HEADERS: tuple[str, ...] = (
    "modelo",
    "revisions",
    "latest_revision",
    "calc_grade",
    "manifest",
    "fixed_width",
    "xml_dict",
    "extractor",
)


def _latest_revision(modelo: ModeloDefinition) -> ModeloRevision:
    """Return the revision with the most recent ``valid_from`` for ``modelo``.

    A modelo always declares at least one revision
    (``ModeloDefinition._validate_revisions`` enforces this at load time),
    so the max is always well-defined.
    """
    return max(modelo.revisions.values(), key=lambda revision: revision.valid_from)


@dataclass(frozen=True, slots=True)
class ModeloCapabilityRow:
    """One modelo's probed capability coverage, keyed off its latest revision.

    Attributes:
        modelo_id: The three-digit AEAT modelo identifier.
        revision_count: Number of registry revisions declared for this modelo.
        latest_revision_id: The id of the revision this row's capabilities are
            probed against (the revision with the most recent ``valid_from``).
        latest_revision_valid_from: That revision's applicability start date.
        calc_grade: Whether the latest revision's calculation closure
            (:func:`~domain.calculations.registry.calculation_closure_casilla_ids`)
            is non-empty — i.e. the revision has at least one formula, binding,
            or verification-expectation operand wiring the calculation engine
            traverses. ``False`` marks a data-fidelity / informative-only
            revision with no calc chain (by design, not necessarily a gap).
        has_completeness_manifest: Whether the latest revision declares a
            calculation-completeness manifest.
        has_fixed_width_export: Whether the latest revision registers a
            ``fixed_width`` (fichero-BOE) export layout.
        has_xml_dictionary_export: Whether the latest revision registers an
            ``xml_dictionary`` export layout.
        has_extractor: Whether the latest revision registers at least one
            extraction profile (PDF/justificante parsing back into casilla
            values).
        extraction_profile_count: Count of extraction profiles on the latest
            revision (0 when ``has_extractor`` is ``False``).
    """

    modelo_id: str
    revision_count: int
    latest_revision_id: str
    latest_revision_valid_from: date
    calc_grade: bool
    has_completeness_manifest: bool
    has_fixed_width_export: bool
    has_xml_dictionary_export: bool
    has_extractor: bool
    extraction_profile_count: int = field(default=0)


def _row_for_modelo(modelo: ModeloDefinition) -> ModeloCapabilityRow:
    revision = _latest_revision(modelo)
    closure = calculation_closure_casilla_ids(revision, modelo.id)
    export_formats = {layout.format for layout in revision.export_layouts}
    return ModeloCapabilityRow(
        modelo_id=modelo.id,
        revision_count=len(modelo.revisions),
        latest_revision_id=revision.id,
        latest_revision_valid_from=revision.valid_from,
        calc_grade=bool(closure),
        has_completeness_manifest=revision.completeness_manifest is not None,
        has_fixed_width_export="fixed_width" in export_formats,
        has_xml_dictionary_export="xml_dictionary" in export_formats,
        has_extractor=bool(revision.extraction_profiles),
        extraction_profile_count=len(revision.extraction_profiles),
    )


def build_capability_matrix(authority: ValidatedRegistryAuthority | None = None) -> tuple[ModeloCapabilityRow, ...]:
    """Probe every registry-loadable modelo and return its capability row.

    Args:
        authority: The registry authority to probe. Defaults to
            :func:`~domain.calculations.registry.bundled_authority`, the
            package-bundled registry tree.

    Returns:
        Every modelo's :class:`ModeloCapabilityRow`, sorted by ``modelo_id``.
    """
    resolved_authority = authority if authority is not None else bundled_authority()
    rows = (_row_for_modelo(modelo) for modelo in resolved_authority.modelos)
    return tuple(sorted(rows, key=lambda row: row.modelo_id))


def _mark(value: bool) -> str:
    return "Y" if value else "-"


def render_matrix_table(rows: tuple[ModeloCapabilityRow, ...]) -> str:
    """Render ``rows`` as a fixed-width human-readable table.

    Returns:
        A multi-line string: a header row, a separator, one line per modelo,
        and a summary line with per-column totals.
    """
    lines = [
        f"{'modelo':>6}  {'revs':>4}  {'latest':<20}  {'calc':>4}  {'manifest':>8}  "
        f"{'boe':>3}  {'xml':>3}  {'extractor':>9}",
    ]
    lines.append("-" * len(lines[0]))
    for row in rows:
        lines.append(
            f"{row.modelo_id:>6}  {row.revision_count:>4}  {row.latest_revision_id:<20}  "
            f"{_mark(row.calc_grade):>4}  {_mark(row.has_completeness_manifest):>8}  "
            f"{_mark(row.has_fixed_width_export):>3}  {_mark(row.has_xml_dictionary_export):>3}  "
            f"{_mark(row.has_extractor):>9}",
        )
    total = len(rows)
    calc_grade_count = sum(1 for row in rows if row.calc_grade)
    manifest_count = sum(1 for row in rows if row.has_completeness_manifest)
    fixed_width_count = sum(1 for row in rows if row.has_fixed_width_export)
    xml_dictionary_count = sum(1 for row in rows if row.has_xml_dictionary_export)
    extractor_count = sum(1 for row in rows if row.has_extractor)
    lines.append("-" * len(lines[0]))
    lines.append(
        f"{total} modelos: calc-grade={calc_grade_count} manifest={manifest_count} "
        f"fichero-BOE={fixed_width_count} xml_dictionary={xml_dictionary_count} "
        f"extractor={extractor_count}",
    )
    return "\n".join(lines)
