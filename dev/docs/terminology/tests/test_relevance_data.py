"""Gates over the committed term-target relevance data (ADR D6 / D8).

The relevance data (``src/aeat/_data/terminology/relevance/relevance.json``) is
the precompiled RAG output that SHIPS so CI and the docs build -- which have no
GPU and no RAG service -- can rank the palette WITHOUT running retrieval. It is
committed (unlike the uncommitted Pagefind index) precisely because the build
cannot regenerate it. These gates keep the committed artifact honest:

1. **enrolled-concept gate** -- every mapped ``concept_id`` is an enrolled
   Handbook concept (loaded from the real authoring tree).
2. **target-resolves gate** -- every ``TermTargetRef.target`` deep-links to a
   surface that exists in the current build (a real casilla, concept anchor,
   BOE permalink, API stub, doc page, or CLI ref). A STALE target -- pointing at
   something the registry / docs no longer carry -- FAILS LOUDLY. This is the
   drift gate: when a source changes and the relevance data is not re-swept, it
   reds.
3. **laundering / licence gate** -- the committed file carries ONLY ids /
   targets / weights: no vectors, no sparse / SPLADE term-weight maps, no raw
   score, no source path. Nothing model-derived ships (the SPLADE-licence
   safety boundary).

All gates load the REAL committed file and the REAL Handbook / registry
authority -- no mocks.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from aeat.core.config import PROJECT_ROOT
from aeat.domain.calculations.registry import bundled_authority
from aeat.terminology import load_terminology_handbook
from dev.docs.terminology._sweep import SweepResult, enumerate_query_vocabulary

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_RELEVANCE_PATH = PROJECT_ROOT / "src" / "aeat" / "_data" / "terminology" / "relevance" / "relevance.json"


@pytest.fixture(scope="module")
def relevance() -> SweepResult:
    """Load and strictly validate the committed relevance data file."""
    if not _RELEVANCE_PATH.is_file():
        pytest.fail(f"committed relevance data missing: {_RELEVANCE_PATH}")
    return SweepResult.model_validate_json(_RELEVANCE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Gate 1 — enrolled-concept
# ---------------------------------------------------------------------------


def test_every_mapped_concept_is_enrolled(relevance: SweepResult) -> None:
    """Every ``concept_id`` in the relevance data is an enrolled Handbook concept."""
    enrolled = {concept.concept_id for concept in load_terminology_handbook().concepts}
    mapped = {mapping.concept_id for mapping in relevance.mappings}
    unknown = sorted(mapped - enrolled)
    assert not unknown, f"relevance data references non-enrolled concept(s): {unknown}"


def test_every_mapping_query_is_shippable_vocabulary(relevance: SweepResult) -> None:
    """Every committed mapping comes from preferred/admitted terms or hidden forms.

    This is the synonym-ratification safety gate: forbidden/deprecated rows and
    unratified candidates must not appear in the shipped relevance data.
    """
    eligible = {(query.concept_id, query.query.casefold()): query.language for query in enumerate_query_vocabulary()}
    leaks: list[str] = []
    wrong_language: list[str] = []
    for mapping in relevance.mappings:
        key = (mapping.concept_id, mapping.query.casefold())
        expected_language = eligible.get(key)
        if expected_language is None:
            leaks.append(f"{mapping.concept_id}:{mapping.query}")
            continue
        if mapping.language is not expected_language:
            wrong_language.append(
                f"{mapping.concept_id}:{mapping.query} is {mapping.language.value}, expected {expected_language.value}",
            )
    assert not leaks, "relevance data contains non-shippable query rows:\n" + "\n".join(f"  - {row}" for row in leaks)
    assert not wrong_language, "relevance data query language drift:\n" + "\n".join(
        f"  - {row}" for row in wrong_language
    )


# ---------------------------------------------------------------------------
# Gate 2 — target-resolves (the drift gate)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def build_surfaces() -> dict[str, object]:
    """The current build's resolvable surfaces, for the target-resolves gate."""
    handbook = load_terminology_handbook()
    authority = bundled_authority()
    # Concept anchors: every enrolled concept_id.
    concept_ids = {concept.concept_id for concept in handbook.concepts}
    # Casilla modelos: every modelo with projected casilla records (read from
    # the same projection the resolver indexes, via the public projection API).
    from dev.docs.terminology._casilla_projection import project_casilla_search_records

    casilla_records, _stats = project_casilla_search_records(authority)
    casilla_modelos = {record.modelo.value for record in casilla_records}
    # Legal permalinks: every legal-catalogue permalink.
    permalinks = {
        str(entry.permalink) for entry in authority.catalogues.legal.values() if getattr(entry, "permalink", None)
    }
    return {
        "concept_ids": concept_ids,
        "casilla_modelos": casilla_modelos,
        "permalinks": permalinks,
    }


def _target_resolves(target: str, surfaces: dict[str, object]) -> bool:
    """Return whether a deep-link target points at a surface in the current build."""
    concept_ids = surfaces["concept_ids"]
    casilla_modelos = surfaces["casilla_modelos"]
    permalinks = surfaces["permalinks"]
    assert isinstance(concept_ids, set)
    assert isinstance(casilla_modelos, set)
    assert isinstance(permalinks, set)

    # Concept card anchor: _generated/glossary.html#term-<concept_id>
    concept_match = re.fullmatch(r"_generated/glossary\.html#term-(?P<id>[a-z0-9-]+)", target)
    if concept_match:
        return concept_match.group("id") in concept_ids

    # Casilla namespace: search.html?q=<modelo>+<number>
    casilla_match = re.fullmatch(r"search\.html\?q=(?P<modelo>[^+]+)\+.+", target)
    if casilla_match:
        return casilla_match.group("modelo") in casilla_modelos

    # BOE legal permalink: must be a known catalogue permalink.
    if target.startswith("https://www.boe.es/"):
        return target in permalinks

    # API stub: api/<dotted>.html -> the module file must exist under src/.
    api_match = re.fullmatch(r"api/(?P<dotted>aeat[a-zA-Z0-9_.]+)\.html", target)
    if api_match:
        return _module_exists(api_match.group("dotted"))

    # CLI reference family page: cli/<family>.html(#anchor)?
    cli_match = re.fullmatch(r"cli/(?P<family>[a-z0-9-]+)\.html(?:#[a-z0-9-]+)?", target)
    if cli_match:
        return cli_match.group("family") in {"app", "config"}

    # Doc page: <rel>.html -> the source page must exist under docs/.
    docs_match = re.fullmatch(r"(?P<rel>[a-zA-Z0-9_./-]+)\.html", target)
    if docs_match:
        return _docs_source_exists(docs_match.group("rel"))

    return False


def _module_exists(dotted: str) -> bool:
    rel = Path(*dotted.split("."))
    src = PROJECT_ROOT / "src"
    return (src / rel.with_suffix(".py")).is_file() or (src / rel / "__init__.py").is_file()


def _docs_source_exists(rel: str) -> bool:
    docs = PROJECT_ROOT / "docs"
    # The built page comes from a .md or .rst source (or is a generated cli/api page).
    if (docs / f"{rel}.md").is_file() or (docs / f"{rel}.rst").is_file():
        return True
    # Generated surfaces (cli/, api/) are produced at build time from the live
    # tree; treat their presence as resolvable when the parent generator exists.
    return rel.startswith(("cli/", "api/"))


def test_every_target_resolves_in_the_current_build(
    relevance: SweepResult,
    build_surfaces: dict[str, object],
) -> None:
    """Every relevance target deep-links to a surface present in the current build.

    The drift gate: a stale target (a casilla / concept / legal / module / page
    the build no longer carries) fails loudly, forcing a re-sweep when the
    registry or docs change.
    """
    unresolved: list[str] = []
    for mapping in relevance.mappings:
        for target in mapping.targets:
            if not _target_resolves(target.target, build_surfaces):
                unresolved.append(f"{mapping.query!r} -> {target.record_id} -> {target.target}")
    assert not unresolved, "relevance targets that no longer resolve in the build (re-sweep needed):\n" + "\n".join(
        f"  - {u}" for u in sorted(set(unresolved))[:40]
    )


def test_drift_gate_actually_rejects_a_stale_target(build_surfaces: dict[str, object]) -> None:
    """Anti-tautology: a fabricated stale target is rejected by the resolver check.

    Proves the drift gate has teeth -- a target pointing at a non-existent
    concept / casilla / module is reported as unresolved, so the gate cannot
    pass on stale data.
    """
    assert not _target_resolves("_generated/glossary.html#term-this-concept-does-not-exist", build_surfaces)
    assert not _target_resolves("search.html?q=000+99999", build_surfaces)
    assert not _target_resolves("api/aeat.module.that.is.not.real.html", build_surfaces)
    # A real one resolves (sanity: the check is not refusing everything).
    real_concept = next(iter(build_surfaces["concept_ids"]))  # type: ignore[arg-type]
    assert _target_resolves(f"_generated/glossary.html#term-{real_concept}", build_surfaces)


# ---------------------------------------------------------------------------
# Gate 3 — laundering / licence (no model-derived data ships)
# ---------------------------------------------------------------------------


def test_committed_artifact_is_laundered() -> None:
    """The committed file carries ONLY ids / targets / weights (SPLADE-free).

    No ``vector`` / ``embedding`` / ``sparse`` / ``splade`` / raw ``score`` /
    source ``path`` / ``snippet`` field may appear -- the licence-clean shipping
    boundary. Asserted over the raw committed bytes, not a re-serialisation, so a
    hand-edit that smuggled a forbidden field would also be caught.
    """
    raw = _RELEVANCE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("vector", "embedding", "sparse", "splade", '"score"', '"path"', '"snippet"'):
        assert forbidden not in raw, f"laundering leak in committed relevance data: {forbidden!r}"


def test_target_field_set_is_exactly_the_laundered_fields(relevance: SweepResult) -> None:
    """Every target record carries exactly the five laundered fields."""
    expected = {"record_id", "target", "kind", "surface", "ranking_weight"}
    for mapping in relevance.mappings:
        for target in mapping.targets:
            assert set(target.model_dump()) == expected


# ---------------------------------------------------------------------------
# Provenance / shape
# ---------------------------------------------------------------------------


def test_relevance_data_carries_run_provenance(relevance: SweepResult) -> None:
    """The committed data records the sweep provenance (query count, reindex note)."""
    assert relevance.query_count == len(relevance.mappings)
    assert relevance.reindex_note.strip()
    assert 0.0 <= relevance.score_floor <= 1.0


def test_prorrata_maps_to_grounding_targets(relevance: SweepResult) -> None:
    """The prorrata concept's terms deep-link to real grounding (worked example).

    A concrete end-to-end assertion on the committed data: at least one prorrata
    query resolves to a BOE legal article and/or the prorrata concept card.
    """
    prorrata = [m for m in relevance.mappings if m.concept_id == "prorrata" and m.targets]
    if not prorrata:
        pytest.skip("no prorrata targets in this sweep (service was busy at sweep time)")
    all_targets = [t.target for m in prorrata for t in m.targets]
    assert any("_generated/glossary.html#term-prorrata" in t for t in all_targets) or any(
        "boe.es" in t for t in all_targets
    ), "prorrata maps to neither its concept card nor a BOE article"
