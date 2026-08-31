"""Official-source proof for the M303 exonerado-390 annual endpoints."""

from __future__ import annotations

import re
from collections import Counter

import pytest

from .....core.filing_producer_key import FilingProducerKey
from .....core.resources import bundled_path
from .._validate import RegistryValidator
from ..corpus_catalogue import resolve_record_design_binary
from ..loader import load_catalogue_file
from ..record_design import extract_record_design
from ..schema_input_kind import InputKind
from ..snapshot import build_snapshot
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ENDPOINTS = frozenset(
    {
        "79",
        "80",
        "81",
        "83",
        "84",
        "86",
        "88",
        "89",
        "90",
        "91",
        "92",
        "93",
        "94",
        "95",
        "96",
        "97",
        "98",
        "99",
        "107",
        "125",
        "126",
        "127",
        "128",
    }
)
_TERRITORY_RATIOS = frozenset({"89", "90", "91", "92", "107"})
_LEGAL_REFS = frozenset({"rd-1624-1992:art-71", "orden-eha-3786-2008:art-1"})
_DESIGNS = (
    ("2023", "aeat-dr-303-2023", 2023, "2023", "4T"),
    ("2024-hasta-08-y-2t", "aeat-dr-303-2024-early", 2024, "2024-early", "2T"),
    ("2024-desde-09-y-3t", "aeat-dr-303-2024-late", 2024, "2024-late", "4T"),
    ("2025", "aeat-dr-303-2025", 2025, "2025", "4T"),
    ("2026-y-siguientes", "aeat-dr-303-2026", 2026, "2026", "4T"),
)
_CASILLA_TAG = re.compile(r"\[(\d{1,3})\]")


@pytest.mark.parametrize(("revision_id", "source_ref", "filing_year", "design_epoch", "period"), _DESIGNS)
def test_real_official_binary_and_registry_agree_on_the_exact_exonerado_endpoint_set(
    revision_id: str,
    source_ref: str,
    filing_year: int,
    design_epoch: str,
    period: str,
) -> None:
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    resolved = resolve_record_design_binary(
        source_root,
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
    )
    extracted = extract_record_design(resolved.path).accept_partial()
    declaration_sheet = next(item for item in extracted if item.name == "DP30301")
    sheet = next(item for item in extracted if item.name == "DP30304")
    exoneration_flags = tuple(
        field
        for field in declaration_sheet.fields
        if "sujeto pasivo exonerado de la declaración-resumen anual" in field.description.casefold()
        and "390" in field.description
    )
    assert len(exoneration_flags) == 1
    assert not _CASILLA_TAG.findall(exoneration_flags[0].description)

    official_fields = {}
    official_unnumbered_fields = []
    for field in sheet.fields:
        if "exonerados de la declaración-resumen anual" not in field.description.casefold():
            continue
        tags = _CASILLA_TAG.findall(field.description)
        if tags and tags[-1] in _ENDPOINTS:
            official_fields[tags[-1]] = field
        elif not tags:
            official_unnumbered_fields.append(field)

    assert frozenset(official_fields) == _ENDPOINTS
    assert len(official_unnumbered_fields) == 13
    activity_fields = tuple(
        field
        for field in official_unnumbered_fields
        if "código de actividad" in field.description.casefold() or "epígrafe iae" in field.description.casefold()
    )
    third_party_marker_fields = tuple(
        field
        for field in official_unnumbered_fields
        if "declaración anual de operaciones" in field.description.casefold()
        and "terceras personas" in field.description.casefold()
    )
    assert len(activity_fields) == 12
    assert len(third_party_marker_fields) == 1
    assert all(official_fields[number].length == 5 for number in _TERRITORY_RATIOS)
    assert all(official_fields[number].length == 17 for number in _ENDPOINTS - _TERRITORY_RATIOS)

    modelo, registry_catalogues = _committed_modelo("303")
    snapshot = build_snapshot(
        modelo,
        registry_catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period=period,
    )
    assert snapshot.revision.id == revision_id
    declared_unit = tuple(
        casilla
        for casilla in snapshot.revision.casillas
        if tuple(casilla.section) == ("iva", "exonerado_390", "resumen_anual")
    )
    endpoints = tuple(casilla for casilla in declared_unit if casilla.id in _ENDPOINTS)
    assert declared_unit == endpoints
    assert frozenset(str(casilla.id) for casilla in endpoints) == _ENDPOINTS
    assert all(casilla.number == str(casilla.id) for casilla in endpoints)
    assert all(casilla.input_kind == InputKind.MANUAL for casilla in endpoints)
    assert all(casilla.required is False for casilla in endpoints)
    assert all(casilla.binding is None and casilla.formula is None for casilla in endpoints)
    # Each endpoint exports to exactly one field on DP30304 -- the same sheet
    # this test reads above to build `official_fields`, and whose numbered field
    # set it asserts equals `_ENDPOINTS`. This previously asserted the endpoints
    # carry NO export refs, which contradicted that evidence: a box AEAT prints
    # on the record design belongs in the fichero. The export wiring has since
    # landed for all six revisions, so the assertion is inverted to the property
    # the design actually supports.
    assert all(len(casilla.export_refs) == 1 for casilla in endpoints)
    assert all("dp30304" in str(casilla.export_refs[0]).casefold() for casilla in endpoints)
    assert all(frozenset(str(ref) for ref in casilla.legal_refs) == _LEGAL_REFS for casilla in endpoints)
    assert all(
        frozenset(str(ref) for ref in casilla.source_refs) == frozenset({source_ref, "aeat-modelo-303-procedure"})
        for casilla in endpoints
    )
    assert all((casilla.data_type == "ratio") == (str(casilla.id) in _TERRITORY_RATIOS) for casilla in endpoints)


def test_exonerado_endpoints_are_unique_canonical_manual_homes_without_parallel_producers() -> None:
    modelo, catalogues = _committed_modelo("303")
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)

    for _revision_id, _source_ref, filing_year, _design_epoch, period in _DESIGNS:
        revision = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=filing_year,
            period=period,
        ).revision
        endpoint_rows = tuple(casilla for casilla in revision.casillas if casilla.id in _ENDPOINTS)
        assert Counter(str(casilla.id) for casilla in endpoint_rows) == Counter({item: 1 for item in _ENDPOINTS})
        assert Counter(casilla.semantic_role for casilla in endpoint_rows) == Counter(
            {f"m303_exonerado_390_{item}": 1 for item in _ENDPOINTS}
        )
        assert {str(formula.target_casilla_id) for formula in revision.formulas}.isdisjoint(_ENDPOINTS)
        assert {
            str(relation.source_casilla_id) for relation in revision.relations if relation.source_casilla_id is not None
        }.isdisjoint(_ENDPOINTS)
        # No PARALLEL producer on the export axis either: each endpoint owns
        # exactly one export field and no two endpoints share one. This asserted
        # that the revision had no export layouts at all and that the endpoints
        # carried no export refs, which was true only while modelo 303's export
        # layouts were unauthored; it is the absence of the feature, not the
        # uniqueness this test is named for.
        endpoint_refs = [ref for casilla in endpoint_rows for ref in casilla.export_refs]
        assert len(endpoint_refs) == len(endpoint_rows)
        assert len(set(endpoint_refs)) == len(endpoint_refs)

    exonerado_producer_tokens = {member.value for member in FilingProducerKey if "exonerado_390" in member.value}
    assert exonerado_producer_tokens == {FilingProducerKey.M303_EXONERADO_390_APPLICABLE.value}
