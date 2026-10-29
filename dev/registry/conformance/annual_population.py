"""Annual casilla population and export dictionary comparisons."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, NonNegativeInt

from cadrumo.core.export_layout_format import ExportLayoutFormat as _ExportLayoutFormat
from cadrumo.core.filing_year import FilingYear
from cadrumo.domain.calculations.registry.errors import RegistryValidationError as _RegistryValidationError
from cadrumo.domain.calculations.registry.export import (
    derive_export_layouts_from_bindings as _derive_export_layouts_from_bindings,
)
from cadrumo.domain.calculations.registry.export_xml_dictionary import xml_dictionary_entries as _xml_dictionary_entries
from cadrumo.domain.calculations.registry.ids import ModeloId as _ModeloId
from cadrumo.domain.calculations.registry.ids import RevisionId as _RevisionId
from cadrumo.domain.calculations.registry.schema import ModeloRevision as _ModeloRevision
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot as _RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition as _ExportLayoutDefinition
from cadrumo.domain.calculations.registry.schema_references import SourceReference as _SourceReference

from .coverage import CoverageAuthorityScope
from .model import ConformanceModel

type _MeasurementStatus = Literal["measured", "unsupported", "unmeasured"]

_XML_DICTIONARY_PARSER_ATTRIBUTES = ("field_id", "path", "data_type", "casilla_id")
_UNMEASURED_DICTIONARY_ATTRIBUTES = ("label", "data_type", "number", "segmento")


class DictionaryLayoutCasillaComparison(ConformanceModel):
    """One year-specific comparison against one declared export layout.

    The measured population is the set of non-internal registry casilla
    identities versus the set of non-null ``casilla_id`` values returned by
    :func:`xml_dictionary_entries`.  It is deliberately named a dictionary
    comparison: those identities are not asserted to be the printed-form
    population.

    ``unsupported`` means the source kind is known but this bounded
    comparator has no parser for it. ``unmeasured`` means the source contract
    was not available to run (for example, an unresolved source or omitted
    source root). Neither status is a zero or a clean result.
    """

    layout_id: str
    layout_format: str
    identity_measurement: _MeasurementStatus
    registry_casilla_count: NonNegativeInt
    registry_internal_only_count: NonNegativeInt
    printed_form_membership: _MeasurementStatus
    xsd_only_attributes: _MeasurementStatus
    dictionary_source_ref: str | None = None
    dictionary_entry_count: int | None = Field(default=None, ge=0)
    dictionary_casilla_count: int | None = Field(default=None, ge=0)
    missing_casilla_ids: tuple[str, ...] = ()
    extra_casilla_ids: tuple[str, ...] = ()
    parser_exposed_attributes: tuple[str, ...] = ()
    unmeasured_attributes: tuple[str, ...] = ()
    diagnostic: str | None = None

    @property
    def identity_divergence_count(self) -> int:
        """Number of missing or extra identities for this layout."""
        return len(self.missing_casilla_ids) + len(self.extra_casilla_ids)


class AnnualCasillaPopulationComparison(ConformanceModel):
    """Year-specific casilla/layout evidence for one authority-selected read.

    The caller supplies a filing :class:`RegistrySnapshot`, or -- from a static
    compiler consumer, whose non-filing revision projection must not reach this
    boundary -- the coordinate and compiled revision as explicit values.  This
    function never selects a latest or largest revision and never compares two
    annual revisions to one another.

    ``printed_form_membership`` is intentionally not derived from dictionary
    identities.  A declared BOE/form source is visible as ``unsupported``
    until an existing form parser contract can measure it.  Likewise,
    ``xsd_only_attributes`` stays ``unsupported`` when an XSD source is
    declared because the XML dictionary parser exposes no XSD-attribute
    mapping contract.
    """

    modelo: _ModeloId
    filing_year: FilingYear
    period: str
    law_selected_revision: _RevisionId
    identity_measurement: _MeasurementStatus
    printed_form_membership: _MeasurementStatus
    xsd_only_attributes: _MeasurementStatus
    layout_comparisons: tuple[DictionaryLayoutCasillaComparison, ...]
    printed_form_source_refs: tuple[str, ...] = ()
    xsd_source_refs: tuple[str, ...] = ()
    authority_scope: CoverageAuthorityScope = CoverageAuthorityScope.FILING

    @property
    def missing_casilla_ids(self) -> tuple[str, ...]:
        """Union of missing identities across the measured layouts."""
        return tuple(
            sorted(
                {casilla_id for comparison in self.layout_comparisons for casilla_id in comparison.missing_casilla_ids},
            ),
        )

    @property
    def extra_casilla_ids(self) -> tuple[str, ...]:
        """Union of extra identities across the measured layouts."""
        return tuple(
            sorted(
                {casilla_id for comparison in self.layout_comparisons for casilla_id in comparison.extra_casilla_ids},
            ),
        )

    @property
    def identity_divergence_count(self) -> int:
        """Total per-layout missing/extra identity findings."""
        return sum(comparison.identity_divergence_count for comparison in self.layout_comparisons)


@dataclass(frozen=True)
class _AnnualPopulationContext:
    """Selected revision facts shared by filing and inspection comparisons."""

    revision: _ModeloRevision
    layouts: tuple[_ExportLayoutDefinition, ...]
    modelo: _ModeloId
    filing_year: int
    period: str
    sources: Mapping[str, _SourceReference]
    authority_scope: CoverageAuthorityScope


def compare_annual_casilla_population(
    snapshot: _RegistrySnapshot,
    *,
    source_root: Path | None = None,
) -> AnnualCasillaPopulationComparison:
    """Compare one law-selected filing snapshot to its declared XML dictionaries.

    A filing snapshot carries its temporal boundary, its selected revision and
    its declared export layouts directly, so nothing else need be supplied.

    Static compiler consumers, which read through a non-filing revision
    projection rather than a snapshot, call
    :func:`compare_annual_casilla_population_for_revision` and pass that
    projection's facts explicitly. That split is deliberate: inspection
    authority is static-only and must not reach an application boundary, so
    this module names no inspection type and the dependency direction is
    inverted rather than the boundary census being widened to admit one.

    The identity comparison delegates source reading to the existing
    :func:`xml_dictionary_entries` parser.  It compares unique non-null
    dictionary ``casilla_id`` values with non-internal registry casilla ids;
    dictionary rows without an id and duplicate field rows remain reflected
    by ``dictionary_entry_count`` but are not fabricated into identities.

    Args:
        snapshot: Validated filing snapshot for one ``modelo``/year/period.
        source_root: Repository root containing the bundled official source
            corpus.  Omitting it leaves dictionary measurement explicitly
            ``unmeasured`` because the parser cannot resolve its source.
    """
    return _compare_annual_population(
        _AnnualPopulationContext(
            revision=snapshot.revision,
            layouts=snapshot.revision.export_layouts,
            modelo=snapshot.modelo.id,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
            sources=snapshot.sources,
            authority_scope=CoverageAuthorityScope.FILING,
        ),
        source_root=source_root,
    )


def compare_annual_casilla_population_for_revision(
    *,
    modelo: _ModeloId,
    revision: _ModeloRevision,
    filing_year: int,
    period: str,
    sources: Mapping[str, _SourceReference],
    source_root: Path | None = None,
) -> AnnualCasillaPopulationComparison:
    """Compare an explicitly-supplied revision read to its XML dictionaries.

    The entry point for static compiler consumers. Their revision projection
    retains no filing context and exposes no export layouts, so the coordinate
    and the already-selected compiled revision arrive as values from the same
    ``ValidatedRegistryAuthority``. Layouts are projected from the revision's
    bindings; no second selector or snapshot is constructed here.
    """
    return _compare_annual_population(
        _AnnualPopulationContext(
            revision=revision,
            layouts=_derive_export_layouts_from_bindings(revision),
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            sources=sources,
            authority_scope=CoverageAuthorityScope.INSPECTION_ONLY,
        ),
        source_root=source_root,
    )


def _compare_annual_population(
    selected: _AnnualPopulationContext,
    *,
    source_root: Path | None,
) -> AnnualCasillaPopulationComparison:

    registry_casillas = tuple(casilla for casilla in selected.revision.casillas if not casilla.internal_only)
    registry_ids = frozenset(str(casilla.id) for casilla in registry_casillas)
    form_source_refs = _source_refs_of_kind(selected.revision.source_refs, selected.sources, "form_spec")
    xsd_source_refs = _source_refs_of_kind(selected.revision.source_refs, selected.sources, "xsd")
    printed_form_status = _source_status(form_source_refs)
    xsd_status = _source_status(xsd_source_refs)

    comparisons = tuple(
        _compare_dictionary_layout(
            layout,
            registry_ids=registry_ids,
            registry_internal_only_count=len(selected.revision.casillas) - len(registry_casillas),
            printed_form_status=printed_form_status,
            xsd_status=xsd_status,
            sources=selected.sources,
            source_root=source_root,
        )
        for layout in selected.layouts
    )
    return AnnualCasillaPopulationComparison(
        modelo=selected.modelo,
        filing_year=selected.filing_year,
        period=selected.period,
        law_selected_revision=selected.revision.id,
        identity_measurement=_fold_measurement_status(
            tuple(comparison.identity_measurement for comparison in comparisons),
        ),
        printed_form_membership=printed_form_status,
        xsd_only_attributes=xsd_status,
        layout_comparisons=comparisons,
        printed_form_source_refs=form_source_refs,
        xsd_source_refs=xsd_source_refs,
        authority_scope=selected.authority_scope,
    )


def _compare_dictionary_layout(
    layout: _ExportLayoutDefinition,
    *,
    registry_ids: frozenset[str],
    registry_internal_only_count: int,
    printed_form_status: _MeasurementStatus,
    xsd_status: _MeasurementStatus,
    sources: Mapping[str, _SourceReference],
    source_root: Path | None,
) -> DictionaryLayoutCasillaComparison:
    """Measure one layout, keeping unsupported and unavailable sources visible."""
    source_ref = None if layout.dictionary_source_ref is None else str(layout.dictionary_source_ref)
    base: dict[str, object] = {
        "layout_id": str(layout.id),
        "layout_format": layout.format.value,
        "registry_casilla_count": len(registry_ids),
        "registry_internal_only_count": registry_internal_only_count,
        "printed_form_membership": printed_form_status,
        "xsd_only_attributes": xsd_status,
        "dictionary_source_ref": source_ref,
    }

    def measured(**fields: object) -> DictionaryLayoutCasillaComparison:
        return DictionaryLayoutCasillaComparison.model_validate({**base, **fields})

    if layout.format is not _ExportLayoutFormat.XML_DICTIONARY:
        return measured(
            identity_measurement="unsupported",
            diagnostic="dictionary comparator supports only xml_dictionary layouts",
        )
    if layout.dictionary_source_ref is None:
        return measured(
            identity_measurement="unmeasured",
            diagnostic="xml_dictionary layout has no dictionary source reference",
        )
    try:
        entries = _xml_dictionary_entries(
            layout,
            sources=sources,
            source_payloads=(
                None
                if source_root is None
                else {str(source.id): (source_root / source.corpus_path).read_bytes() for source in sources.values()}
            ),
        )
    except (_RegistryValidationError, OSError) as exc:
        return measured(
            identity_measurement="unmeasured",
            parser_exposed_attributes=_XML_DICTIONARY_PARSER_ATTRIBUTES,
            unmeasured_attributes=_UNMEASURED_DICTIONARY_ATTRIBUTES,
            diagnostic=f"{type(exc).__name__}: {exc}",
        )

    dictionary_ids = frozenset(str(entry.casilla_id) for entry in entries if entry.casilla_id is not None)
    return measured(
        identity_measurement="measured",
        dictionary_entry_count=len(entries),
        dictionary_casilla_count=len(dictionary_ids),
        missing_casilla_ids=tuple(sorted(registry_ids - dictionary_ids)),
        extra_casilla_ids=tuple(sorted(dictionary_ids - registry_ids)),
        parser_exposed_attributes=_XML_DICTIONARY_PARSER_ATTRIBUTES,
        unmeasured_attributes=_UNMEASURED_DICTIONARY_ATTRIBUTES,
    )


def _source_refs_of_kind(
    source_refs: Sequence[str],
    sources: Mapping[str, _SourceReference],
    kind: str,
) -> tuple[str, ...]:
    """Return resolved source ids of one declared kind in declaration order."""
    return tuple(
        source_ref
        for source_ref in (str(item) for item in source_refs)
        if (source := sources.get(source_ref)) is not None and source.kind == kind
    )


def _source_status(source_refs: Sequence[str]) -> _MeasurementStatus:
    """Classify a declared-but-unparsed official surface explicitly."""
    return "unsupported" if source_refs else "unmeasured"


def _fold_measurement_status(statuses: Sequence[_MeasurementStatus]) -> _MeasurementStatus:
    """Fold per-layout status without treating an empty set as measured."""
    if "measured" in statuses:
        return "measured"
    if "unsupported" in statuses:
        return "unsupported"
    return "unmeasured"
