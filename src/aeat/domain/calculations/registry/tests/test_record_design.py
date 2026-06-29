"""Tests for read-only AEAT record-design workbook extraction."""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .....core.resources import bundled_path
from .. import (
    CasillaFieldKind,
    RecordDesignSheet,
    build_snapshot,
    calculation_closure_legal_refs,
    load_registry_tree,
    resolve_export_layout,
)
from .._binding_selector_utils import BindingFixedExportSelector, binding_export_selector
from .._record_design import (
    build_diseno_coverage_report,
    calculation_closure_record_design_metadata,
    derive_calculation_completeness_casillas,
    derive_diseno_coverage_casillas,
    extract_record_design,
    extract_record_design_pdf,
    extract_record_design_pdf_bytes,
)
from .._schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_131_WORKBOOK_ROOT = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_131", "files")
_MODELO_131_CURRENT = _MODELO_131_WORKBOOK_ROOT / "01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx"
_RECORD_DESIGN_ROOT = bundled_path("corpus", "aeat_official", "disenos_registro")


@cache
def _committed_registry_tree():
    return load_registry_tree(bundled_path("registry", "aeat"))


@cache
def _official_record_design_sheets(path: Path) -> tuple[RecordDesignSheet, ...]:
    return extract_record_design(path)


def _official_record_designs(paths: tuple[Path, ...]) -> dict[Path, tuple[RecordDesignSheet, ...]]:
    # The PDF path is backed by pypdfium2; keep corpus parsing serial to
    # avoid native-library crashes while still deduplicating repeated reads.
    return {path: _official_record_design_sheets(path) for path in paths}


def _modelo_131_snapshot(*, filing_year: int, period: str = "1T"):
    modelos, catalogues = _committed_registry_tree()
    modelo = next(item for item in modelos if item.id == "131")
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=filing_year, period=period)


def test_modelo_131_current_record_design_exposes_dpa_and_did_records() -> None:
    sheets = {sheet.name: sheet for sheet in _official_record_design_sheets(_MODELO_131_CURRENT)}

    assert tuple(sheets) == ("Pág. 0", "Pág. 1", "DPA", "DID")
    assert len(sheets["Pág. 1"].fields) == 71
    assert sheets["Pág. 1"].total_positions == 831
    assert len(sheets["DPA"].fields) == 69
    assert sheets["DPA"].total_positions == 598
    assert len(sheets["DID"].fields) == 7
    assert sheets["DID"].total_positions == 257

    dpa_activity = sheets["DPA"].fields[5]
    assert dpa_activity.offset == 13
    assert dpa_activity.length == 4
    assert "Epigrafe IAE" in dpa_activity.description

    direct_debit_iban = sheets["DID"].fields[4]
    assert direct_debit_iban.offset == 12
    assert direct_debit_iban.length == 34
    assert direct_debit_iban.description == "Domiciliación - IBAN"


def test_modelo_840_record_design_pdf_reuses_record_design_sheet_model() -> None:
    sheets = {
        sheet.name: sheet for sheet in _official_record_design_sheets(_record_design_pdf("modelo_840", "orden-hac"))
    }

    page_one = sheets["Pág. 1"]
    assert len(page_one.fields) == 106
    assert page_one.total_positions == 1132
    assert page_one.fields[0].offset == 1
    assert page_one.fields[0].length == 9
    assert page_one.fields[0].type_code == "An"
    assert page_one.fields[0].description.startswith("Inicio del identificador de modelo")
    assert page_one.fields[-1].offset == 1131
    assert page_one.fields[-1].length == 2
    assert page_one.fields[-1].description == "Salto de línea. Constante CRLF."


def test_generated_compact_record_design_pdf_round_trips_from_path_and_bytes(tmp_path: Path) -> None:
    pdf_path = tmp_path / "compact-record-design.pdf"
    _write_pdf_lines(
        pdf_path,
        (
            "Pág 1 DISEÑO DE REGISTRO 01/12/2003",
            "Nº Posic. Lon Tipo Descripción Validación Contenido",
            "1 1 3 An Inicio del identificador de modelo.",
            "2 4 2 Num Ejercicio.",
            "3 6 5 An Nombre.",
            "4 11 An Salto de línea. Constante CRLF.",
        ),
    )

    from_path = extract_record_design_pdf(pdf_path)
    from_bytes = extract_record_design_pdf_bytes(pdf_path.read_bytes(), source_label=pdf_path.name)

    assert from_bytes == from_path
    sheet = from_path[0]
    assert sheet.name == "Pág. 1"
    assert sheet.total_positions == 12
    assert [(field.ordinal, field.offset, field.length, field.type_code) for field in sheet.fields] == [
        (1, 1, 3, "An"),
        (2, 4, 2, "Num"),
        (3, 6, 5, "An"),
        (4, 11, 2, "An"),
    ]


def test_generated_narrative_record_design_pdf_preserves_content_and_split_titles(tmp_path: Path) -> None:
    pdf_path = tmp_path / "narrative-record-design.pdf"
    _write_pdf_lines(
        pdf_path,
        (
            "Tipo de registro 1: Registro de Declarante",
            "POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS",
            "1 Numérico TIPO DE REGISTRO.",
            "Constante número '1'.",
            "2-4 Numérico MODELO DECLARACIÓN",
            "5-8 Numérico EJERCICIO",
            "9-17 Alfanumérico NIF DEL DECLARANTE",
            "18-57 Alfanumérico APELLIDOS Y NOMBRE,",
            "RAZÓN SOCIAL DEL DECLARANTE.",
            "Se consignará el primer apellido y nombre completo.",
            "58 Alfabético TIPO DE SOPORTE.",
            "59-107 Alfanumérico PERSONA CON QUIEN RELACIONARSE",
            "108-500 -------- BLANCOS",
        ),
    )

    sheet = extract_record_design_pdf(pdf_path)[0]

    assert sheet.name == "Tipo 1 - Registro De Declarante"
    assert sheet.total_positions == 500
    assert len(sheet.fields) == 8
    name_field = next(field for field in sheet.fields if field.offset == 18)
    assert name_field.length == 40
    assert name_field.description == "APELLIDOS Y NOMBRE, RAZÓN SOCIAL DEL DECLARANTE."
    assert name_field.content == "Se consignará el primer apellido y nombre completo."
    assert sheet.fields[-1].type_code == "Blancos"
    assert sheet.fields[-1].length == 393


def test_generated_record_design_pdf_rejects_inverted_position_ranges(tmp_path: Path) -> None:
    pdf_path = tmp_path / "bad-record-design.pdf"
    _write_pdf_lines(
        pdf_path,
        (
            "Tipo de registro 1: Registro de Declarante",
            "POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS",
            "1 Numérico TIPO DE REGISTRO.",
            "4-3 Numérico MODELO DECLARACIÓN",
        ),
    )

    with pytest.raises(ValueError, match="inverted position range 4-3"):
        extract_record_design_pdf(pdf_path)


def test_modelo_190_record_design_pdf_extracts_narrative_type_one_and_two_records() -> None:
    sheets = {
        sheet.name: sheet
        for sheet in _official_record_design_sheets(_record_design_pdf("modelo_190", "orden-hac-1431"))
    }

    declarante = sheets["Tipo 1 - Registro De Declarante"]
    perceptor = sheets["Tipo 2 - Registro De Perceptor"]
    assert declarante.total_positions == 500
    assert perceptor.total_positions == 500
    assert [(field.offset, field.length, field.type_code) for field in declarante.fields[:4]] == [
        (1, 1, "Numérico"),
        (2, 3, "Numérico"),
        (5, 4, "Numérico"),
        (9, 9, "Alfanumérico"),
    ]
    assert declarante.fields[4].offset == 18
    assert declarante.fields[4].length == 40
    assert "SOCIAL DEL DECLARANTE" in declarante.fields[4].description
    assert declarante.fields[-2].offset == 226
    assert declarante.fields[-2].length == 262
    assert declarante.fields[-2].type_code == "Blancos"
    assert declarante.fields[-1].offset == 488
    assert declarante.fields[-1].length == 13
    assert perceptor.fields[0].description == "TIPO DE REGISTRO."


def test_modelo_193_record_design_pdf_preserves_split_field_titles_across_lines() -> None:
    sheets = {
        sheet.name: sheet
        for sheet in _official_record_design_sheets(_record_design_pdf("modelo_193", "orden-hac-1430"))
    }
    declarante = sheets["Tipo 1 - Registro De Declarante"]

    name_field = next(field for field in declarante.fields if field.offset == 18)
    assert name_field.length == 40
    assert name_field.description == "APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL DECLARANTE."
    assert name_field.content is not None
    assert "persona física" in name_field.content


def test_modelo_347_record_design_pdf_keeps_distinct_type_two_layouts() -> None:
    sheets = _official_record_design_sheets(_record_design_pdf("modelo_347", "orden-hac-1431"))

    assert [sheet.name for sheet in sheets] == [
        "Tipo 1 - Registro De Declarante",
        "Tipo 2 - Registro De Declarado",
        "Tipo 2 - Registro De Inmueble",
    ]
    assert [sheet.total_positions for sheet in sheets] == [500, 500, 500]
    declarado, inmueble = sheets[1], sheets[2]
    assert declarado.fields[4].description == "NIF DEL DECLARADO"
    assert inmueble.fields[4].description == "NIF DEL ARRENDATARIO"
    assert declarado.fields[-1].offset == 306
    assert inmueble.fields[-1].offset == 334


def test_modelo_347_positional_chart_pdf_extracts_reviewable_record_data() -> None:
    sheets = _official_record_design_sheets(_record_design_pdf("modelo_347", "2008-y-2009"))

    assert [sheet.name for sheet in sheets] == [
        "Tipo 1 - Registro De Declarante",
        "Tipo 2 - Registro De Declarado",
        "Tipo 2 - Registro De Inmueble",
    ]
    assert [sheet.total_positions for sheet in sheets] == [500, 500, 500]
    declarante, declarado, inmueble = sheets
    assert len(declarante.fields) == 20
    assert declarante.fields[17].offset == 391
    assert declarante.fields[17].description == "NIF. DEL REPRESENTANTE LEGAL"
    assert declarante.fields[17].type_code == "No consta en gráfico"
    assert declarado.fields[4].description == "N.I.F. DECLARADO"
    assert declarado.fields[-1].offset == 130
    assert declarado.fields[-1].length == 371
    assert inmueble.fields[12].offset == 116
    assert inmueble.fields[12].length == 25
    assert inmueble.fields[12].description == "REFERENCIA CATASTRAL"
    assert inmueble.fields[27].description == "CODIGO POSTAL"
    assert all(
        field.content == "Extracted from visual record-design chart geometry."
        for sheet in sheets
        for field in sheet.fields
    )


def test_generated_non_table_pdf_does_not_activate_visual_chart_fallback(tmp_path: Path) -> None:
    pdf_path = tmp_path / "non-record-design.pdf"
    _write_pdf_lines(
        pdf_path,
        (
            "MODELO 347 REGISTRO DE TIPO 1 REGISTRO DE DECLARANTE",
            "This page names one record heading but has no position ruler or record field geometry.",
        ),
    )

    with pytest.raises(ValueError, match="did not contain parseable field rows"):
        extract_record_design_pdf(pdf_path)


def test_record_design_pdf_corpus_is_discovered_and_parseable() -> None:
    pdfs = _record_design_pdf_files()

    parsed = {path.relative_to(_RECORD_DESIGN_ROOT): sheets for path, sheets in _official_record_designs(pdfs).items()}

    assert pdfs
    assert all(parsed.values())
    assert sum(len(sheet.fields) for sheets in parsed.values() for sheet in sheets) > len(pdfs)


def test_registered_record_design_sources_are_discovered_and_parseable() -> None:
    _, catalogues = _committed_registry_tree()
    sources = {
        source_id: bundled_path() / source.corpus_path
        for source_id, source in catalogues.sources.items()
        if source.kind == "record_design"
    }

    source_items = tuple(sorted(sources.items()))
    parsed_by_path = _official_record_designs(tuple(path for _source_id, path in source_items))
    parsed = {source_id: parsed_by_path[path] for source_id, path in source_items}

    assert sources
    assert all(parsed.values())
    assert {path.suffix.lower() for path in sources.values()} >= {".pdf", ".xls", ".xlsx"}
    assert sum(len(sheet.fields) for sheets in parsed.values() for sheet in sheets) > len(sources)


# ---------------------------------------------------------------------------
# Calculation-completeness manifest drift + full-Diseño coverage advisory
# (off-load-path)
# ---------------------------------------------------------------------------
#
# Two off-load-path concerns, neither on the snapshot-build hot path:
#
# - The load-blocking calculation-completeness gate in RegistryValidator
#   compares a revision's declared casillas against a checked-in
#   calculation-completeness manifest. The drift test below re-derives
#   each checked-in manifest from its corpus Diseño (the calculation
#   closure intersected with the Diseño) and fails CI if a manifest has
#   drifted from the corpus it claims to be derived from.
#
# - The full-Diseño coverage report is an *advisory* inventory: it
#   extracts every casilla AEAT declares in a Diseño — accounting-
#   statement data-entry fields included — and surfaces form-level
#   coverage as information, never as a load-blocking gate. It is the
#   counterpart to the bounded calculation-completeness gate.


def _modelo_200_record_design_corpus_path() -> Path:
    """Return the corpus path of the Modelo 200 record-design Diseño."""
    modelos, catalogues = _committed_registry_tree()
    modelo_200 = next(modelo for modelo in modelos if modelo.id == "200")
    revision = next(iter(modelo_200.revisions.values()))
    source_ref = next(ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design")
    return bundled_path() / catalogues.sources[source_ref].corpus_path


def test_calculation_completeness_manifests_match_their_calculation_surface() -> None:
    """Every checked-in calculation-completeness manifest still matches its closure.

    For each checked-in calculation-completeness manifest, re-run the
    off-load-path derivation — the modelo's calculation closure keyed on
    canonical ``casilla.id`` and carrying reviewed ``(segmento, number)``
    metadata — and assert the derived casilla set still equals the
    manifest's enumerated set. A divergence means the calculation surface
    changed without a manifest refresh, or the manifest was hand-edited
    away from the registry — both are CI failures.

    The derivation is *vocabulary-agnostic*: only Modelo 200's casilla
    numbers are five-digit AEAT Diseño tags, so the manifest is derived
    from the modelo's calculation surface keyed on canonical
    ``casilla.id`` and carrying the registry metadata each closure casilla
    declares. For a multi-segment modelo the derived
    segments are additionally verified against the official AEAT Diseño
    de Registros corpus — the Diseño remains authoritative on which
    record segment carries each number — by passing the corpus path to
    the derivation.

    A modelo's ``record_design`` source corpus is parsed only for the
    multi-segment Diseño verification; a single-segment modelo's manifest
    is registry-keyed and needs no corpus parse.
    """
    modelos, catalogues = _committed_registry_tree()

    discovered = sorted(
        (modelo.id, revision.id)
        for modelo in modelos
        for revision in modelo.revisions.values()
        if revision.completeness_manifest is not None
    )

    checked = 0
    for modelo in modelos:
        for revision in modelo.revisions.values():
            manifest = revision.completeness_manifest
            if manifest is None:
                continue
            multi_segment = any(casilla.segmento is not None for casilla in manifest.casillas)
            diseno_path: Path | None = None
            if multi_segment:
                record_design_refs = [
                    ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design"
                ]
                assert record_design_refs, (
                    f"modelo {modelo.id} revision {revision.id}: a multi-segment "
                    "calculation-completeness manifest requires a record_design "
                    "source to verify its record segments"
                )
                diseno_path = bundled_path() / catalogues.sources[record_design_refs[0]].corpus_path
            derived = frozenset(
                (casilla.casilla_id, casilla.segmento, casilla.number)
                for casilla in derive_calculation_completeness_casillas(
                    revision,
                    modelo.id,
                    multi_segment=multi_segment,
                    diseno_path=diseno_path,
                )
            )
            missing_ids = sorted(casilla for casilla in derived if casilla[0] is None)
            assert not missing_ids, (
                f"modelo {modelo.id} revision {revision.id}: derived manifest rows "
                f"lack canonical casilla ids: {missing_ids!r}"
            )
            assert derived == manifest.manifest_keys(), (
                f"modelo {modelo.id} revision {revision.id}: calculation-completeness "
                "manifest has drifted from the registry calculation surface; "
                "manifest-only casillas: "
                f"{sorted(manifest.manifest_keys() - derived, key=lambda item: (item[0], item[1] or '', item[2]))}; "
                "closure-only casillas: "
                f"{sorted(derived - manifest.manifest_keys(), key=lambda item: (item[0], item[1] or '', item[2]))}"
            )
            checked += 1

    # Discovery sanity: every discovered manifest is machine-checked.
    # Guards against the re-verification loop silently skipping a manifest.
    assert checked == len(discovered)
    assert checked > 0, "expected at least one calculation-completeness manifest"


def test_calculation_completeness_manifest_legal_refs_match_calculation_closure() -> None:
    """Every checked-in completeness manifest carries exactly its closure refs."""
    modelos, _catalogues = _committed_registry_tree()

    checked = 0
    offenders: dict[tuple[str, str], dict[str, list[str]]] = {}
    for modelo in modelos:
        for revision in modelo.revisions.values():
            manifest = revision.completeness_manifest
            if manifest is None:
                continue
            closure_refs = calculation_closure_legal_refs(revision, modelo.id)
            manifest_refs = set(manifest.legal_refs)
            if manifest_refs != closure_refs:
                offenders[(modelo.id, revision.id)] = {
                    "manifest_only": sorted(manifest_refs - closure_refs),
                    "closure_only": sorted(closure_refs - manifest_refs),
                }
            checked += 1

    assert not offenders
    assert checked > 0, "expected at least one calculation-completeness manifest"


def test_calculation_completeness_gate_is_live_for_every_calculation_bearing_modelo() -> None:
    """Every modelo with a calculation closure carries a manifest; the gate is live.

    The calculation-completeness gate is per-modelo: it enforces a
    revision only once that revision declares a ``completeness_manifest``.
    This test proves the gate is live for the whole calculation-bearing
    corpus: every modelo revision whose calculation closure is non-empty
    declares a manifest, and every modelo revision whose closure is empty
    (no formulas, no verification expectations — no calculation surface)
    declares none.

    A modelo whose closure had a genuinely missing or ungrounded casilla
    could not carry a passing manifest; this assertion would then fail,
    surfacing the gap rather than masking it.
    """
    modelos, _ = _committed_registry_tree()

    gated = 0
    dormant = 0
    for modelo in modelos:
        for revision in modelo.revisions.values():
            closure = calculation_closure_record_design_metadata(revision, modelo.id)
            manifest = revision.completeness_manifest
            if closure:
                assert manifest is not None, (
                    f"modelo {modelo.id} revision {revision.id}: has a calculation "
                    f"closure of {len(closure)} casillas but declares no "
                    "completeness_manifest; the gate is not live for it"
                )
                gated += 1
            else:
                assert manifest is None, (
                    f"modelo {modelo.id} revision {revision.id}: declares a "
                    "completeness_manifest but has an empty calculation closure"
                )
                dormant += 1

    assert gated > 0, "expected calculation-bearing modelo revisions"
    # Dormant (no calculation closure, no completeness_manifest) revisions:
    # Modelo 308, 347, 360, 840 (informative declarations) and Modelo 721 (crypto
    # data-fidelity, no calc). Modelo 714 (patrimonio) is now calculation-bearing:
    # its cuota-íntegra escala (Ley 19/1991 art. 30) is computed and
    # carries a completeness_manifest, so it is gated, not dormant. The remaining
    # M714 downstream chain (límite conjunto, cuota a ingresar) stays manual but
    # is not part of the calculation closure. Empirically enumerated.
    assert dormant == 5


def test_diseno_coverage_report_inventories_modelo_200_form_data() -> None:
    """The full-Diseño coverage extraction is an advisory inventory, not a gate.

    Exercises `derive_diseno_coverage_casillas` — the full-Diseño
    extraction — directly against the Modelo 200 2024 corpus Diseño. The
    coverage report inventories every casilla AEAT declares on the form,
    accounting-statement data-entry fields included; it surfaces
    form-level coverage as advisory information and never reds the load.

    The extraction must be load-bearing: it surfaces the Modelo 200
    Liquidación cuota-chain casillas under the `DP200014` record segment,
    and the same number recurring across record segments produces more
    segment-qualified pairs than distinct bare numbers — the
    multi-segment contract.
    """
    corpus_path = _modelo_200_record_design_corpus_path()

    coverage = derive_diseno_coverage_casillas(corpus_path, multi_segment=True)

    coverage_pairs = frozenset((casilla.segmento, casilla.number) for casilla in coverage)
    dp200014 = {number for segmento, number in coverage_pairs if segmento == "DP200014"}
    assert {"00552", "00558", "00562"} <= dp200014, (
        "the Modelo 200 Liquidación cuota-chain casillas must surface in the "
        f"full-Diseño coverage report under the DP200014 segment; got {sorted(dp200014)}"
    )
    distinct_numbers = {number for _, number in coverage_pairs}
    assert len(coverage_pairs) > len(distinct_numbers), (
        "the multi-segment Modelo 200 coverage report must carry more "
        "segment-qualified pairs than distinct bare numbers"
    )


def test_calculation_closure_bounds_the_full_diseno_coverage() -> None:
    """The calculation closure is a strict subset of the full-Diseño coverage.

    The refocused gate is keyed on the bounded calculation closure, not
    on full-Diseño coverage. This test proves the bound is real: the
    Modelo 200 calculation-completeness derivation (closure intersected
    with the Diseño) yields strictly fewer ``(segmento, number)`` pairs
    than the full-Diseño coverage report, because Modelo 200's Diseño is
    overwhelmingly accounting-statement data-entry fields that feed no
    calculation. A modelo can therefore clear the load-blocking gate
    without an exhaustive full-form backfill — the design intent of the
    contract amendment.
    """
    modelos, _ = _committed_registry_tree()
    modelo_200 = next(modelo for modelo in modelos if modelo.id == "200")
    revision = next(iter(modelo_200.revisions.values()))
    corpus_path = _modelo_200_record_design_corpus_path()

    coverage = frozenset(
        (casilla.segmento, casilla.number)
        for casilla in derive_diseno_coverage_casillas(corpus_path, multi_segment=True)
    )
    closure = frozenset(
        (casilla.segmento, casilla.number)
        for casilla in derive_calculation_completeness_casillas(
            revision,
            modelo_200.id,
            multi_segment=True,
            diseno_path=corpus_path,
        )
    )
    # The closure may legitimately contain app-internal computed casillas
    # (e.g. the LIS art. 26.1 BIN-compensation ceiling materialised as
    # ``DP200014:bin-aplicada-maxima``) that AEAT publishes as formulas
    # rather than as form-record fields. Such casillas declare
    # ``internal_only = true`` at the registry source and are intentionally
    # absent from the full Diseño coverage; subtract them from the closure
    # before asserting the bound, so the gate's claim remains "every
    # *exported* closure casilla appears in the Diseño" rather than the
    # over-extended "every closure casilla appears in the Diseño".
    internal_only_metadata = frozenset(
        (casilla.segmento, casilla.number) for casilla in revision.casillas if casilla.internal_only
    )
    exported_closure = closure - internal_only_metadata
    closure_only = exported_closure - coverage
    assert exported_closure <= coverage, (
        "the calculation-completeness casilla set (minus internal_only ceilings) "
        "must be a subset of the full-Diseño coverage; closure-only pairs: "
        + ", ".join(
            f"({segmento!r}, {number!r})"
            for segmento, number in sorted(closure_only, key=lambda pair: (pair[0] or "", pair[1]))
        )
    )
    assert len(closure) < len(coverage), (
        "the calculation closure must be strictly bounded below the full-Diseño "
        f"coverage; closure has {len(closure)} pairs, coverage has {len(coverage)}"
    )


def test_diseno_coverage_report_is_an_advisory_inventory_not_a_load_gate() -> None:
    """The full-Diseño coverage report inventories form data without redding the load.

    `build_diseno_coverage_report` compares a modelo revision's declared
    casillas against the full AEAT Diseño de Registros casilla set and
    returns a `DisenoCoverageReport`: the total Diseño casilla count, the
    subset the registry covers, and the coverage-gap subset the registry
    has not yet authored. The report is produced off the snapshot-build
    load path and is purely advisory — a coverage gap is information for
    follow-up authoring, never a load failure.

    The report is exercised against the Modelo 200 2024 corpus Diseño. Its
    three casilla sets must partition the full Diseño coverage: covered
    plus gap equals the full Diseño set, and covered and gap are disjoint.
    The gap is non-empty because Modelo 200's Diseño is overwhelmingly
    accounting-statement data-entry fields, the deliberate counterpart to
    the bounded calculation-completeness gate that *is* enforced at load.

    Building the report must not raise: an advisory inventory never reds a
    load, so the same Modelo 200 that clears the load-blocking
    calculation-completeness gate is freely inventoried here.
    """
    modelos, _ = _committed_registry_tree()
    modelo_200 = next(modelo for modelo in modelos if modelo.id == "200")
    revision = next(iter(modelo_200.revisions.values()))
    corpus_path = _modelo_200_record_design_corpus_path()

    report = build_diseno_coverage_report(corpus_path, modelo_200.id, revision, multi_segment=True)

    assert report.modelo_id == "200"
    assert report.revision_id == revision.id

    diseno = frozenset((c.segmento, c.number) for c in report.diseno_casillas)
    covered = frozenset((c.segmento, c.number) for c in report.covered_casillas)
    gap = frozenset((c.segmento, c.number) for c in report.coverage_gap_casillas)

    assert covered | gap == diseno, (
        "the coverage report must partition the full Diseño set into covered and gap casillas"
    )
    assert covered & gap == frozenset(), "a Diseño casilla is either covered or a gap, never both"
    assert report.covered_count + report.coverage_gap_count == report.diseno_casilla_count
    assert report.coverage_gap_count > 0, (
        "the Modelo 200 Diseño carries accounting-statement data-entry fields "
        "outside the registry's calculation surface; the advisory report must "
        "surface them as a coverage gap"
    )


def test_modelo_registry_tests_use_public_record_design_dispatcher() -> None:
    registry_tests = sorted(Path(__file__).parent.glob("test_modelo_*_registry.py"))

    private_imports = [
        path.name for path in registry_tests if "._record_design import" in path.read_text(encoding="utf-8")
    ]

    assert private_imports == []


@pytest.mark.parametrize(
    ("workbook_name", "expected_sheets"),
    (
        ("05-131-ejercicios-2019-a-2023-116-kb-xlsx.xlsx", ("Pág. 0", "Pág. 1")),
        ("06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx", ("Pág. 0", "Pág. 1", "DPA", "DID")),
        ("07-131-ejercicios-2025-actualizado-11-12-25-179-kb-xlsx.xlsx", ("Pág. 0", "Pág. 1", "DPA", "DID")),
        ("01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx", ("Pág. 0", "Pág. 1", "DPA", "DID")),
    ),
)
def test_modelo_131_record_design_revision_shapes_are_read_from_official_workbooks(
    workbook_name: str,
    expected_sheets: tuple[str, ...],
) -> None:
    sheets = _official_record_design_sheets(_MODELO_131_WORKBOOK_ROOT / workbook_name)

    assert tuple(sheet.name for sheet in sheets) == expected_sheets


@pytest.mark.parametrize(
    "workbook_name",
    (
        "06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx",
        "07-131-ejercicios-2025-actualizado-11-12-25-179-kb-xlsx.xlsx",
    ),
)
def test_modelo_131_recent_record_designs_share_coordinates_but_not_source_text(workbook_name: str) -> None:
    current = {sheet.name: sheet for sheet in _official_record_design_sheets(_MODELO_131_CURRENT)}
    candidate = {
        sheet.name: sheet for sheet in _official_record_design_sheets(_MODELO_131_WORKBOOK_ROOT / workbook_name)
    }

    for sheet_name in ("Pág. 1", "DPA", "DID"):
        current_fields = current[sheet_name].fields
        candidate_fields = candidate[sheet_name].fields

        assert candidate[sheet_name].total_positions == current[sheet_name].total_positions
        assert [(field.offset, field.length) for field in candidate_fields] == [
            (field.offset, field.length) for field in current_fields
        ]

    assert any(
        candidate_field.description != current_field.description
        for sheet_name in ("Pág. 1", "DPA")
        for candidate_field, current_field in zip(
            candidate[sheet_name].fields,
            current[sheet_name].fields,
            strict=True,
        )
    )


@pytest.mark.parametrize(
    ("filing_year", "workbook_name", "source_ref"),
    (
        (2024, "06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx", "aeat-dr-131-2024"),
        (2025, "07-131-ejercicios-2025-actualizado-11-12-25-179-kb-xlsx.xlsx", "aeat-dr-131-2025"),
        (2026, "01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx", "aeat-dr-131-2026"),
    ),
)
def test_modelo_131_registry_bindings_cover_official_structured_records(
    filing_year: int,
    workbook_name: str,
    source_ref: str,
) -> None:
    snapshot = _modelo_131_snapshot(filing_year=filing_year)
    sheets = {sheet.name: sheet for sheet in _official_record_design_sheets(_MODELO_131_WORKBOOK_ROOT / workbook_name)}

    official_fields = {
        (sheet_name, field.offset, field.length, "integer" if field.type_code == "Num" else "text")
        for sheet_name in ("DPA", "DID")
        for field in sheets[sheet_name].fields
        if _is_structured_input_field(field.description)
    }
    registry_bindings = [
        (binding, selector)
        for binding, selector in _fixed_export_selectors(snapshot.revision.bindings)
        if selector.record in {"DPA", "DID"}
    ]
    registry_fields = {
        (
            selector.record,
            selector.offset,
            selector.length,
            selector.data_type,
        )
        for _binding, selector in registry_bindings
    }

    assert registry_fields == official_fields
    assert all(source_ref in binding.source_refs for binding, _selector in registry_bindings)
    assert all("rd-439-2007:art-110" in binding.legal_refs for binding, _selector in registry_bindings)


def test_modelo_131_2024_dpa_territorial_reduction_fields_carry_specific_legal_basis() -> None:
    snapshot = _modelo_131_snapshot(filing_year=2024, period="4T")
    sheets = {
        sheet.name: sheet
        for sheet in _official_record_design_sheets(
            _MODELO_131_WORKBOOK_ROOT / "06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx",
        )
    }
    bindings = {
        (selector.offset, selector.length): binding
        for binding, selector in _fixed_export_selectors(snapshot.revision.bindings)
        if selector.record == "DPA"
    }

    for field in sheets["DPA"].fields:
        binding = bindings.get((field.offset, field.length))
        if binding is None:
            continue
        if "Lorca" in field.description:
            assert "orden-hfp-1359-2023:da-5" in binding.legal_refs
        if "Reducción" in field.description and "Palma" in field.description:
            assert "orden-hfp-1359-2023:da-6" in binding.legal_refs
        if "DANA" in field.description:
            assert "real-decreto-ley-7-2024:art-11" in binding.legal_refs


@pytest.mark.parametrize(
    ("filing_year", "workbook_name"),
    (
        (2024, "06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx"),
        (2025, "07-131-ejercicios-2025-actualizado-11-12-25-179-kb-xlsx.xlsx"),
        (2026, "01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx"),
    ),
)
def test_modelo_131_registry_bindings_cover_official_page_one_structured_fields(
    filing_year: int,
    workbook_name: str,
) -> None:
    snapshot = _modelo_131_snapshot(filing_year=filing_year)
    page = next(
        sheet
        for sheet in _official_record_design_sheets(_MODELO_131_WORKBOOK_ROOT / workbook_name)
        if sheet.name == "Pág. 1"
    )

    official_fields = {
        (
            field.offset,
            field.length,
            _page_one_data_type(field.offset, field.type_code),
        )
        for field in page.fields
        if _is_page_one_structured_input_field(field.description)
    }
    registry_fields = {
        (
            selector.offset,
            selector.length,
            selector.data_type,
        )
        for _binding, selector in _fixed_export_selectors(snapshot.revision.bindings)
        if selector.record == "page_1"
    }

    assert registry_fields == official_fields


@pytest.mark.parametrize(
    ("filing_year", "workbook_name", "palma_legal_ref"),
    (
        (
            2024,
            "06-131-ejercicios-2024-actualizado-13-12-24-180-kb-xlsx.xlsx",
            "real-decreto-ley-4-2024:art-3",
        ),
        (
            2025,
            "07-131-ejercicios-2025-actualizado-11-12-25-179-kb-xlsx.xlsx",
            "real-decreto-ley-13-2025:art-2",
        ),
    ),
)
def test_modelo_131_page_one_la_palma_fields_are_year_scoped(
    filing_year: int,
    workbook_name: str,
    palma_legal_ref: str,
) -> None:
    snapshot = _modelo_131_snapshot(filing_year=filing_year)
    page = next(
        sheet
        for sheet in _official_record_design_sheets(_MODELO_131_WORKBOOK_ROOT / workbook_name)
        if sheet.name == "Pág. 1"
    )
    bindings = {
        (selector.offset, selector.length): (binding, selector)
        for binding, selector in _fixed_export_selectors(snapshot.revision.bindings)
        if selector.record == "page_1"
    }

    for field in page.fields:
        if "Palma" not in field.description or not _is_page_one_structured_input_field(field.description):
            continue
        binding, selector = bindings[(field.offset, field.length)]
        if "RENTAS OBTENIDAS" in field.description or "Deducción por rentas obtenidas" in field.description:
            assert selector.field is not None
            assert "la-palma" in selector.field
        assert palma_legal_ref in binding.legal_refs


def test_modelo_131_current_page_one_agrarian_fields_preserve_territorial_meaning() -> None:
    snapshot = _modelo_131_snapshot(filing_year=2026)
    page = next(sheet for sheet in _official_record_design_sheets(_MODELO_131_CURRENT) if sheet.name == "Pág. 1")
    descriptions = {(field.offset, field.length): field.description for field in page.fields}

    for _binding, selector in _fixed_export_selectors(snapshot.revision.bindings):
        if selector.record != "page_1":
            continue
        offset = selector.offset
        if offset not in {424, 434, 448, 458}:
            continue
        description = descriptions[(offset, selector.length)]
        assert selector.field is not None
        field_name = selector.field
        if "RENTAS OBTENIDAS EN CEUTA" in description:
            assert "ceuta-melilla" in field_name
        else:
            assert "ceuta-melilla" not in field_name


@pytest.mark.parametrize("filing_year", [2024, 2025, 2026])
def test_modelo_131_export_records_derive_fields_from_reviewed_bindings(filing_year: int) -> None:
    snapshot = _modelo_131_snapshot(filing_year=filing_year)
    layout = resolve_export_layout(snapshot).layout
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}

    for record in layout.records:
        if record.binding_record is None:
            continue
        expected = {
            binding.id: selector
            for binding, selector in _fixed_export_selectors(bindings.values())
            if selector.record == record.binding_record
        }
        derived = {field.binding: field for field in record.fields if field.kind is CasillaFieldKind.BINDING}

        assert expected
        assert set(derived) == set(expected)
        assert all(
            derived[binding_id].offset == selector.offset for binding_id, selector in expected.items()
        )
        assert all(
            derived[binding_id].length == selector.length for binding_id, selector in expected.items()
        )
        assert all(
            derived[binding_id].data_type == selector.data_type for binding_id, selector in expected.items()
        )


@pytest.mark.parametrize("filing_year", [2023, 2024, 2025, 2026])
def test_modelo_131_submitted_file_profiles_target_exported_casillas(filing_year: int) -> None:
    snapshot = _modelo_131_snapshot(filing_year=filing_year)
    layout = resolve_export_layout(snapshot).layout
    profile = next(
        item
        for item in snapshot.revision.extraction_profiles
        if item.surface == "export_record" and "submitted_file" in item.accepted_artefact_kinds
    )

    exported_casillas = {
        field.casilla_id
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None
    }

    assert {t.casilla_id for t in profile.target_casillas} <= exported_casillas


def _is_structured_input_field(description: str) -> bool:
    if description in {
        "Inicio del identificador de modelo y página.",
        "Modelo.",
        "Página.",
        "Fin de identificador de modelo.",
        "Indicador de página complementaria.",
        "Indicador de fin de registro",
    }:
        return False
    return "RESERVADO" not in description.upper()


def _is_page_one_structured_input_field(description: str) -> bool:
    if description in {
        "Inicio del identificador de modelo y página.",
        "Modelo.",
        "Página.",
        "Fin de identificador de modelo.",
        "Indicador de página complementaria.",
        "Tipo de autoliquidación",
        "Declarante (1) - Nif",
        "Declarante (1) - Apellidos",
        "Declarante (1) - Nombre (solo personas físicas)",
        "Devengo (2) - Ejercicio",
        "Devengo (2) - Período",
        "Indicador de fin de registro",
    }:
        return False
    if "RESERVADO" in description.upper():
        return False
    return "[" not in description and "]" not in description


def _page_one_data_type(offset: int, type_code: str) -> str:
    if offset in {109, 613, 692}:
        return "boolean"
    if offset in {360, 374, 424, 434, 448, 458, 472, 614}:
        return "money"
    if type_code in {"N"}:
        return "money"
    if type_code == "An":
        return "text"
    if offset in {359, 556}:
        return "integer"
    return "decimal"


def _fixed_export_selectors(
    bindings: Iterable[DataBindingDefinition],
) -> tuple[tuple[DataBindingDefinition, BindingFixedExportSelector], ...]:
    members: list[tuple[DataBindingDefinition, BindingFixedExportSelector]] = []
    for binding in bindings:
        selector = binding_export_selector(binding)
        if isinstance(selector, BindingFixedExportSelector):
            members.append((binding, selector))
    return tuple(members)


def _record_design_pdf_files() -> tuple[Path, ...]:
    return tuple(sorted(_RECORD_DESIGN_ROOT.glob("modelo_*/files/*.pdf")))


def _record_design_pdf(*path_parts: str) -> Path:
    matches = [path for path in _record_design_pdf_files() if all(part in path.as_posix() for part in path_parts)]
    assert len(matches) == 1, f"expected one record-design PDF for {path_parts!r}, found {matches!r}"
    return matches[0]


def _write_pdf_lines(path: Path, lines: tuple[str, ...]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setFont("Helvetica", 8)
    y = A4[1] - 36
    for line in lines:
        if y < 36:
            pdf.showPage()
            pdf.setFont("Helvetica", 8)
            y = A4[1] - 36
        pdf.drawString(36, y, line)
        y -= 12
    pdf.save()
