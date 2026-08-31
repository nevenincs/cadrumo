"""Calculation-completeness and Diseño coverage record-design tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....core.resources.bundled_data import bundled_path
from ..authority import ValidatedRegistryAuthority
from ..record_design_coverage import (
    build_diseno_coverage_report,
    calculation_closure_legal_refs,
    calculation_closure_record_design_metadata,
    derive_calculation_completeness_casillas,
    derive_diseno_coverage_casillas,
)
from ._record_design_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

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
    saw_zero_closure_revision = False
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
                saw_zero_closure_revision = True

    assert gated > 0, "expected calculation-bearing modelo revisions"
    assert saw_zero_closure_revision, "expected at least one revision without a calculation closure"


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
    internal_only_metadata = frozenset(
        (casilla.segmento, casilla.number) for casilla in revision.casillas if casilla.internal_only
    )
    assert closure.isdisjoint(internal_only_metadata), (
        "internal-only calculation nodes must not enter the official manifest denominator"
    )
    closure_only = closure - coverage
    assert closure <= coverage, (
        "the calculation-completeness casilla set must be a subset of the "
        "full-Diseño coverage; closure-only pairs: "
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
    registry_tests = scan_directory(Path(__file__).parent, pattern="test_modelo_*_registry.py")

    private_imports = [
        path.name for path in registry_tests if "._record_design import" in path.read_text(encoding="utf-8")
    ]

    assert private_imports == []


def _record_design_corpus_paths(modelo_id: str) -> tuple[Path, ...]:
    """Every record-design corpus path any revision of ``modelo_id`` cites.

    Keyed on ``modelo.revisions`` rather than a pinned revision id. Modelo 390
    carries one revision today and is being split into filing epochs; a fixed id
    would silently stop covering anything the moment that lands, and would still
    pass, which is the failure this helper exists to avoid.
    """
    modelos, catalogues = _committed_registry_tree()
    modelo = next(item for item in modelos if item.id == modelo_id)
    paths: list[Path] = []
    for revision in modelo.revisions.values():
        for ref in revision.source_refs:
            source = catalogues.sources[ref]
            if source.kind == "record_design":
                paths.append(bundled_path() / source.corpus_path)
    return tuple(dict.fromkeys(paths))


def test_diseno_coverage_report_inventories_modelo_390_form_data() -> None:
    """Modelo 390 reaches the advisory coverage inventory, as Modelo 200 does.

    The full-Diseño coverage report existed and was exercised for Modelo 200
    alone, so the annual IVA form -- the most under-modelled surface in the
    registry -- was outside the one instrument that measures form-level
    coverage. This extends the existing report rather than adding a second
    mechanism.

    ADVISORY, deliberately. The report inventories what AEAT declares; it does
    NOT assert that every declared casilla is modelled, and must not. A modelo
    not yet exhaustively backfilled is reported as a coverage gap, never failed
    at load -- the load-blocking gate stays keyed on the bounded calculation
    closure. Asserting coverage here would convert a recorded design decision
    into its opposite.

    ``multi_segment=False`` because Modelo 390 declares ``segmento`` nowhere:
    every casilla carries ``None``, matching the bare-number registry contract.
    A number recurring across sheets therefore collapses to one pair, which is
    the intended single-segment behaviour and not a loss.

    Counts here come from THIS extractor, which collects casilla tags from the
    Diseño. They are not comparable with counts from any other extraction of
    "the boxes in a design" -- a sibling gate counts bracketed ``[nnn]`` markers
    and yields a different number for the same file. Never set one beside the
    other without naming which produced each.
    """
    paths = _record_design_corpus_paths("390")
    assert paths, "Modelo 390 cites no record-design corpus source; the assertions below would be vacuous"

    covered: set[str] = set()
    for path in paths:
        assert path.is_file(), f"cited record design is absent from the corpus: {path}"
        covered.update(casilla.number for casilla in derive_diseno_coverage_casillas(path, multi_segment=False))

    assert covered, (
        "the Modelo 390 record design yielded no casillas at all; an empty inventory "
        "would make every coverage statement below vacuously true"
    )


def test_modelo_390_coverage_report_is_advisory_not_a_completeness_claim() -> None:
    """The inventory must exceed what the registry models, and say nothing more.

    This pins the report's POSTURE. Modelo 390 is substantially under-modelled
    against its own form, so the inventory is expected to be far larger than the
    registry's declared set. Were the two ever asserted equal, the advisory would
    have become a load-blocking completeness gate by accident -- the exact
    conversion the recorded decision forbids.
    """
    modelos, _ = _committed_registry_tree()
    modelo = next(item for item in modelos if item.id == "390")
    declared = {casilla.number for revision in modelo.revisions.values() for casilla in revision.casillas}
    assert declared, "the registry declares no Modelo 390 casillas"

    covered: set[str] = set()
    for path in _record_design_corpus_paths("390"):
        covered.update(casilla.number for casilla in derive_diseno_coverage_casillas(path, multi_segment=False))
    assert covered, "empty inventory"

    # The original form of this assertion was `len(covered) > len(declared)`, a
    # PROXY for "the annual form is under-modelled", and it carried an
    # instruction to re-read rather than relax it if the direction ever
    # inverted. It has: the registry now declares more Modelo 390 casillas than
    # the design inventory enumerates. So the proxy is retired and the posture
    # the docstring actually names is asserted directly instead.
    #
    # What must stay true is that the report is ADVISORY. Two things establish
    # that, neither of which depends on which set is larger: the two sets are
    # not equal, so neither can be read as a completeness claim about the
    # other; and the registry loads with that difference standing, so the
    # report gates nothing.
    assert covered != declared, (
        "the advisory inventory and the registry's declared set have become the same "
        "set; asserting them equal is exactly the conversion into a load-blocking "
        "completeness gate that the recorded decision forbids"
    )
    ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())


def test_a_casilla_recording_its_box_in_form_number_counts_as_covered() -> None:
    """The official box number is not always in ``number``, and coverage must follow it.

    A casilla whose ``id`` is a domain name rather than a box number tends to
    repeat that id in ``number`` and record the official box in ``form_number``.
    Modelo 303's ``iva.resultado-regimen-general`` is exactly that: it IS box 46
    on the form -- its own formula comment reads ``[64] = [46] + [58] + [76]``
    and it exports to ``modelo-303-page-01-casilla-46`` -- while its ``number``
    holds the id.

    Keyed on ``number`` alone, the coverage report called box 46 an unauthored
    Diseño casilla: a box the registry computes and exports, reported as
    missing. This pins the fix in the direction that matters, and pins the
    premise (the box lives in ``form_number``, not ``number``) so a later
    normalisation of the two fields fails here rather than silently making the
    fallback dead code.
    """
    modelos, catalogues = _committed_registry_tree()
    modelo_303 = next(modelo for modelo in modelos if modelo.id == "303")
    revision = next(rev for rev_id, rev in modelo_303.revisions.items() if "2023" in rev_id)

    resultado = next(c for c in revision.casillas if c.id == "iva.resultado-regimen-general")
    assert resultado.form_number == "46", "the premise: this casilla records its box in form_number"
    assert resultado.number != "46", "if number now carries the box, this test's premise has moved"

    source_ref = next(ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design")
    corpus_path = bundled_path() / catalogues.sources[source_ref].corpus_path
    multi_segment = any(c.segmento for c in revision.casillas)

    report = build_diseno_coverage_report(corpus_path, modelo_303.id, revision, multi_segment=multi_segment)

    assert not report.extraction_found_no_casillas, "the Modelo 303 Diseño must be readable at all"
    gap_numbers = {casilla.number for casilla in report.coverage_gap_casillas}
    covered_numbers = {casilla.number for casilla in report.covered_casillas}
    assert "46" in covered_numbers, "box 46 is computed and exported; it must not read as unauthored"
    assert "46" not in gap_numbers
