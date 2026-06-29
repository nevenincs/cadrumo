"""Calculation-completeness and Diseño coverage record-design tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .. import calculation_closure_legal_refs
from ._record_design_support import (
    _committed_registry_tree,
    build_diseno_coverage_report,
    calculation_closure_record_design_metadata,
    derive_calculation_completeness_casillas,
    derive_diseno_coverage_casillas,
)

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
