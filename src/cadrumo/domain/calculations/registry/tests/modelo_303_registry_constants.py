"""Modelo 303 registry constants shared by the published-authority and authored-source test families."""

from __future__ import annotations

from collections.abc import Callable
from functools import cache

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....tests.aeat_literal_fixtures import aeat_host
from ..authority import bundled_indexed_authority
from ..schema import ModeloRevision
from ..schema_base import PublishingAuthority, RegistrySourceKind
from ..schema_references import SourceReference, TemporalProjectionDirection
from ..temporal import RevisionSelectionMetadata, revision_temporal_resolution
from .authored_editions import authored_revisions, filing_year_envelope

WWW1_HOST = aeat_host("www1")
WWW6_HOST = aeat_host("www6")


M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores"
)
M303_COMPENSACION_APLICADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
M303_POSTERIOR_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-pendiente-periodos-posteriores")
M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
M303_GENERADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
M303_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")
M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_M303_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-volumen-con-derecho")
_M303_PRORRATA_VOLUMEN_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-volumen-total")
_M303_PRORRATA_PORCENTAJE_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-porcentaje")
M303_BIENES_INVERSION_REGULARIZACION_CASILLA: CasillaId = validated_casilla_id("43")
M303_BIENES_INVERSION_REGULARIZACION_BINDING = "modelo-303-bienes-inversion-regularizacion-casilla-43"
M303_PRORRATA_REGULARIZACION_CASILLA: CasillaId = validated_casilla_id("44")
M303_PRORRATA_REGULARIZACION_BINDING = "modelo-303-prorrata-regularizacion-casilla-44"
M303_PRORRATA_REGULARIZACION_SOURCE_CASILLAS: tuple[CasillaId, ...] = (
    _M303_PRORRATA_VOLUMEN_CON_DERECHO_CASILLA,
    _M303_PRORRATA_VOLUMEN_TOTAL_CASILLA,
    _M303_PRORRATA_PORCENTAJE_CASILLA,
)
M303_PRORRATA_REGULARIZACION_SOURCE_PERIOD_SELECTION = "filer_liquidation_cadence"
# The extraction-profile targets of the oldest authored design, which predates the prorrata and special-regime boxes.
_M303_EARLIEST_RECORD_DESIGN_LEGAL_REFS = frozenset(
    {
        "ley-37-1992:art-88",
        "ley-37-1992:art-90",
        "ley-37-1992:art-91",
        "ley-37-1992:art-92",
        "ley-37-1992:art-94",
        "ley-37-1992:art-95",
        "orden-eha-3786-2008:art-1",
        "rd-1624-1992:art-71",
    }
)
_M303_CURRENT_RECORD_DESIGN_LEGAL_REFS = frozenset(
    {
        "ley-37-1992:art-88",
        "ley-37-1992:art-90",
        "ley-37-1992:art-91",
        "ley-37-1992:art-92",
        "ley-37-1992:art-94",
        "ley-37-1992:art-95",
        "ley-37-1992:art-99",
        "ley-37-1992:art-115",
        "ley-37-1992:art-116",
        "ley-37-1992:art-122",
        "ley-37-1992:art-123",
        "ley-37-1992:art-124",
        "orden-eha-3786-2008:art-1",
        "rd-1624-1992:art-29",
        "rd-1624-1992:art-30",
        "rd-1624-1992:art-71",
    }
)
M303_RECORD_DESIGN_LAYOUT_MODIFICATION_LEGAL_REF = "orden-hac-819-2024:art-unico"


def _supported_editions() -> tuple[RevisionSelectionMetadata, ...]:
    """Return the 303 editions the support envelope selects for some authored coordinate, oldest first.

    Every period any edition serves is asked for in every supported exercise; an
    edition counts when the canonical temporal resolution reports the coordinate
    as authored by it rather than projected onto it.
    """
    envelope = filing_year_envelope()
    authored = authored_revisions("303")
    periods = sorted(
        {
            period
            for revision in authored
            for year in envelope.years
            for period in revision.period_selector.periods_for_year(year)
        }
    )
    selected: set[str] = set()
    with bundled_indexed_authority().operation() as operation:
        support = operation.supported_filing_years()
        for year in envelope.years:
            for period in periods:
                revision = operation.revision_for_context("303", filing_year=year, period=period)
                resolution = revision_temporal_resolution(revision, filing_year=year, period=period, support=support)
                if resolution.projection_direction is TemporalProjectionDirection.AUTHORED:
                    selected.add(str(revision.id))
    return tuple(revision for revision in authored if str(revision.id) in selected)


M303_SUPPORTED_EDITIONS = _supported_editions()
M303_SUPPORTED_EDITION_IDS = tuple(str(revision.id) for revision in M303_SUPPORTED_EDITIONS)
_EARLIEST_EDITION_ID = str(authored_revisions("303")[0].id)


@cache
def _cited_sources() -> tuple[SourceReference, ...]:
    """Return every source any supported 303 edition cites, so a selection never reads one edition's own answer."""
    cited = sorted({ref for revision in M303_SUPPORTED_EDITIONS for ref in _edition(str(revision.id)).source_refs})
    with bundled_indexed_authority().operation() as operation:
        return tuple(operation.source_reference(ref) for ref in cited)


def _edition(revision_id: str) -> ModeloRevision:
    with bundled_indexed_authority().operation() as operation:
        return operation.revision("303", revision_id)


def _covering_source(revision_id: str, predicate: Callable[[SourceReference], bool]) -> str:
    """Return the one cited source that satisfies ``predicate`` and whose applicability covers the edition's start."""
    start = next(revision.valid_from for revision in M303_SUPPORTED_EDITIONS if str(revision.id) == revision_id)
    (source,) = (
        source
        for source in _cited_sources()
        if predicate(source)
        and source.applies_from is not None
        and source.applies_from <= start
        and (source.applies_to is None or start <= source.applies_to)
    )
    return source.id


def m303_record_design_source(revision_id: str) -> str:
    """Return the AEAT diseño de registro whose applicability window opens the edition."""
    return _covering_source(revision_id, lambda source: source.kind is RegistrySourceKind.RECORD_DESIGN)


def m303_annual_orden_source(revision_id: str) -> str:
    """Return the BOE annual Orden whose single-exercise window governs the edition."""
    return _covering_source(
        revision_id,
        lambda source: (
            source.kind is RegistrySourceKind.INSTRUCTIONS
            and source.authority is PublishingAuthority.BOE
            and source.applies_to is not None
        ),
    )


def m303_extraction_profile_target_legal_refs(revision_id: str) -> frozenset[str]:
    """Return the legal references the declaration extraction profile's target boxes carry in one edition."""
    if revision_id == _EARLIEST_EDITION_ID:
        return _M303_EARLIEST_RECORD_DESIGN_LEGAL_REFS
    return _M303_CURRENT_RECORD_DESIGN_LEGAL_REFS
