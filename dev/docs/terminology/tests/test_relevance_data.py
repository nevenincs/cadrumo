"""Gates over the committed term-target relevance data.

The relevance data (``dev/docs/terminology/relevance/relevance.json``) is
the precompiled RAG output that is COMMITTED so CI and the docs build -- which
have no GPU and no RAG service -- can rank the palette WITHOUT running
retrieval. It is read from the repository checkout by the docs harness and by
no runtime consumer, so it lives under ``dev/`` rather than in the shipped
``_data`` tree. It is
committed (unlike the uncommitted Pagefind index) precisely because the build
cannot regenerate it. These gates keep the committed artifact honest:

1. **enrolled-concept gate** -- every mapped ``concept_id`` is an enrolled
   Handbook concept (loaded from the real authoring tree).
2. **target-resolves gate** -- every ``TermTargetRef.target`` deep-links to a
   surface that exists in the current build (a real casilla, concept anchor,
   generated legal-reference page/anchor, API stub, doc page, or CLI ref). A
   STALE target -- pointing at something the registry / docs no longer carry --
   FAILS LOUDLY. Legal ids and targets are checked against the same generated
   projection the injector emits; BOE links are typed provenance, never targets.
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
from typing import TypedDict

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority

from ...._paths import REPO_ROOT
from ...terminology_handbook import load_terminology_handbook
from .._search_record import SearchRecordKind
from .._sweep import SweepResult, enumerate_query_vocabulary

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

# Dev tooling runs from a source checkout by definition, so it owns its own
# repo-root anchor. Production code has no repository concept and must never
# export one (see cadrumo.core._config_state_root for the runtime data root).
_REPO_ROOT = REPO_ROOT

_RELEVANCE_PATH = _REPO_ROOT / "dev" / "docs" / "terminology" / "relevance" / "relevance.json"
_PARSEABLE_CASILLA_RECORD_ID_RE = re.compile(r"^casilla:[^:]+:.+")


class _BuildSurfaces(TypedDict):
    """Resolvable target inventories for the committed relevance drift gate."""

    concept_targets: set[str]
    casilla_modelos: set[str]
    casilla_targets_by_record_id: dict[str, str]
    legal_targets_by_record_id: dict[str, str]
    cli_targets: set[str]


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
def build_surfaces() -> _BuildSurfaces:
    """The current build's resolvable surfaces, for the target-resolves gate."""
    handbook = load_terminology_handbook()
    authority = bundled_authority()
    # Concept anchors: project the same approved cards that feed the search
    # surface. Sphinx derives the anchor from the glossary headword, not from
    # the concept id (for example, ``AEAT`` -> ``term-AEAT``).
    # Casilla modelos: every modelo with projected casilla records (read from
    # the same projection the resolver indexes, via the public projection API).
    from .._casilla_projection import project_casilla_search_records
    from .._cli_projection import project_cli_search_records
    from .._concept_cards import project_concept_cards
    from .._legal_projection import project_legal_search_records
    from .._unified_record import to_search_record

    concept_cards, _concept_stats = project_concept_cards(handbook)
    concept_targets = {to_search_record(card).target for card in concept_cards if card.is_approved}
    casilla_records, _stats = project_casilla_search_records(authority)
    unified_casillas = tuple(to_search_record(record) for record in casilla_records)
    casilla_modelos = {unified.metadata.modelo for unified in unified_casillas if unified.metadata.modelo is not None}
    casilla_targets_by_record_id = {unified.id: unified.target for unified in unified_casillas}
    # Legal targets: the exact record-id -> target inventory emitted by the
    # registry-backed legal projection consumed by Pagefind injection. The
    # projection owns the generated page/anchor target; its typed BOE
    # permalink is destination provenance and is intentionally not indexed.
    legal_records = project_legal_search_records(_REPO_ROOT)
    legal_targets_by_record_id = {record.record_id: record.target for record in legal_records}
    # CLI targets: every live leaf command's real generated page+anchor, from
    # the same projection (`_cli_projection.py`) that is the sole producer of
    # committed CLI-kind relevance targets. A family-shaped regular expression
    # cannot tell a real command anchor from a fabricated one; membership in
    # this real, live-generated inventory can.
    cli_commands, _cli_options, _cli_stats = project_cli_search_records()
    cli_targets = {record.target for record in cli_commands}
    return {
        "concept_targets": concept_targets,
        "casilla_modelos": casilla_modelos,
        "casilla_targets_by_record_id": casilla_targets_by_record_id,
        "legal_targets_by_record_id": legal_targets_by_record_id,
        "cli_targets": cli_targets,
    }


def _target_resolves(target: str, surfaces: _BuildSurfaces) -> bool:
    """Return whether a deep-link target points at a surface in the current build."""
    concept_targets = surfaces["concept_targets"]
    casilla_modelos = surfaces["casilla_modelos"]
    legal_targets = set(surfaces["legal_targets_by_record_id"].values())
    cli_targets = surfaces["cli_targets"]
    # Concept card anchor: generated from the approved glossary headword.
    concept_match = re.fullmatch(r"_generated/glossary\.html#term-[A-Za-z0-9-]+", target)
    if concept_match:
        return target in concept_targets

    # Casilla namespace: the per-modelo reference page plus the casilla anchor
    # (_generated/casillas/<modelo>.html#casilla-<slug>). The query-string
    # hand-off is retired; the target is now a real page+anchor.
    casilla_match = re.fullmatch(r"_generated/casillas/(?P<modelo>[A-Za-z0-9-]+)\.html#casilla-[a-z0-9-]+", target)
    if casilla_match:
        return casilla_match.group("modelo") in casilla_modelos

    # Generated legal-reference page/anchor: membership in the renderer-owned
    # inventory is required. Direct BOE URLs are provenance, never targets.
    if target.startswith("_generated/legal/"):
        return target in legal_targets
    if target.startswith("https://www.boe.es/"):
        return False

    # API stub: api/<dotted>.html -> the module file must exist under src/.
    api_match = re.fullmatch(r"api/(?P<dotted>cadrumo[a-zA-Z0-9_.]+)\.html", target)
    if api_match:
        return _module_exists(api_match.group("dotted"))

    # CLI reference page+anchor: must be a real live leaf command's target
    # exactly as `_cli_projection.py` generates it -- a family-shaped
    # regular expression cannot tell a real command anchor
    # (cli/app/ledger.html#aeat-app-ledger-add) from a fabricated one
    # (cli/app/not-real.html); real membership can.
    if target.startswith("cli/"):
        return target in cli_targets

    # Doc page: <rel>.html -> the source page must exist under docs/.
    docs_match = re.fullmatch(r"(?P<rel>[a-zA-Z0-9_./-]+)\.html", target)
    if docs_match:
        return _docs_source_exists(docs_match.group("rel"))

    return False


def _module_exists(dotted: str) -> bool:
    rel = Path(*dotted.split("."))
    src = _REPO_ROOT / "src"
    return (src / rel.with_suffix(".py")).is_file() or (src / rel / "__init__.py").is_file()


def _docs_source_exists(rel: str) -> bool:
    docs = _REPO_ROOT / "docs"
    # The built page comes from a .md or .rst source (or is a generated cli/api page).
    if (docs / f"{rel}.md").is_file() or (docs / f"{rel}.rst").is_file():
        return True
    if (docs / rel / "index.md").is_file() or (docs / rel / "index.rst").is_file():
        return True
    # Generated surfaces (cli/, api/) are produced at build time from the live
    # tree; treat their presence as resolvable when the parent generator exists.
    return rel.startswith(("cli/", "api/"))


def test_every_target_resolves_in_the_current_build(
    relevance: SweepResult,
    build_surfaces: _BuildSurfaces,
) -> None:
    """Every relevance target deep-links to a surface present in the current build.

    The drift gate: a stale target (a casilla / concept / legal / module / page
    the build no longer carries) fails loudly, forcing a re-sweep when the
    registry or docs change. Legal ids must also be emitted by the canonical
    projection, and their targets must match it exactly.
    """
    unresolved: list[str] = []
    for mapping in relevance.mappings:
        for target in mapping.targets:
            if target.record_id.startswith("legal:"):
                expected_target = build_surfaces["legal_targets_by_record_id"].get(target.record_id)
                if expected_target is None:
                    unresolved.append(
                        f"{mapping.query!r} -> {target.record_id} is not an emitted legal record id",
                    )
                elif target.surface != "legal":
                    unresolved.append(
                        f"{mapping.query!r} -> {target.record_id} has surface {target.surface!r}, expected 'legal'",
                    )
                elif target.kind is not SearchRecordKind.LEGAL:
                    unresolved.append(
                        f"{mapping.query!r} -> {target.record_id} has kind {target.kind.value!r}, expected 'legal'",
                    )
                elif target.target != expected_target:
                    unresolved.append(
                        f"{mapping.query!r} -> {target.record_id} target {target.target!r}, "
                        f"expected {expected_target!r}",
                    )
                continue
            if target.surface == "legal" or target.target.startswith("https://www.boe.es/"):
                unresolved.append(f"{mapping.query!r} -> non-canonical legal target {target.target}")
                continue
            if not _target_resolves(target.target, build_surfaces):
                unresolved.append(f"{mapping.query!r} -> {target.record_id} -> {target.target}")
    assert not unresolved, "relevance targets that no longer resolve in the build (re-sweep needed):\n" + "\n".join(
        f"  - {u}" for u in sorted(set(unresolved))[:40]
    )


def test_casilla_targets_use_current_canonical_record_ids(
    relevance: SweepResult,
    build_surfaces: _BuildSurfaces,
) -> None:
    """Every shipped casilla target must match the current opaque projection.

    The search record id is an opaque dedupe token. A shipped casilla target
    must not encode a second parseable ``modelo:casilla`` reference; the
    canonical identity is carried only by the projected record metadata.
    """
    projected = build_surfaces["casilla_targets_by_record_id"]
    stale: list[str] = []
    parseable: list[str] = []
    for mapping in relevance.mappings:
        for target in mapping.targets:
            if target.kind is not SearchRecordKind.CASILLA:
                continue
            if _PARSEABLE_CASILLA_RECORD_ID_RE.fullmatch(target.record_id):
                parseable.append(f"{mapping.query!r} -> {target.record_id}")
            expected_target = projected.get(target.record_id)
            if expected_target is None:
                stale.append(f"{mapping.query!r} -> {target.record_id} is not a current projected casilla record id")
                continue
            if target.target != expected_target:
                stale.append(
                    f"{mapping.query!r} -> {target.record_id} target {target.target!r}, expected {expected_target!r}",
                )
    assert not parseable, "casilla relevance record ids must be opaque, not parseable references:\n" + "\n".join(
        f"  - {row}" for row in parseable[:40]
    )
    assert not stale, "casilla relevance targets are not canonical current casilla.id projections:\n" + "\n".join(
        f"  - {row}" for row in stale[:40]
    )


def test_drift_gate_actually_rejects_a_stale_target(build_surfaces: _BuildSurfaces) -> None:
    """Anti-tautology: a fabricated stale target is rejected by the resolver check.

    Proves the drift gate has teeth -- a target pointing at a non-existent
    concept / casilla / legal page / module is reported as unresolved, so the
    gate cannot pass on stale data or direct BOE targets.
    """
    assert not _target_resolves("_generated/glossary.html#term-this-concept-does-not-exist", build_surfaces)
    assert not _target_resolves("_generated/casillas/000.html#casilla-99999", build_surfaces)
    assert not _target_resolves("_generated/legal/not-a-real-document.html#legal-not-real", build_surfaces)
    assert not _target_resolves("https://www.boe.es/buscar/act.php?id=BOE-A-not-a-target", build_surfaces)
    assert not _target_resolves("api/cadrumo.module.that.is.not.real.html", build_surfaces)
    # A real one resolves (sanity: the check is not refusing everything).
    real_concept_target = next(iter(build_surfaces["concept_targets"]))
    assert _target_resolves(real_concept_target, build_surfaces)
    real_legal_target = next(iter(build_surfaces["legal_targets_by_record_id"].values()))
    assert _target_resolves(real_legal_target, build_surfaces)


def test_a_fabricated_cli_page_or_anchor_is_rejected(build_surfaces: _BuildSurfaces) -> None:
    """A CLI deep link that merely matches the family shape but names no real command is refused.

    Reproduces the audit finding: a family-shaped regular expression alone
    accepted a fabricated page (`cli/app/not-real.html`) and a fabricated
    anchor on an otherwise-real family page
    (`cli/config/not-real.html#bogus`). Real membership in the live-generated
    CLI target inventory refuses both.
    """
    assert not _target_resolves("cli/app/not-real.html", build_surfaces)
    assert not _target_resolves("cli/config/not-real.html#bogus", build_surfaces)
    # A real page with a fabricated anchor is refused too, not merely a
    # fabricated page: the anchor half of the check has teeth on its own.
    real_cli_target = next(iter(build_surfaces["cli_targets"]))
    real_page = real_cli_target.split("#", 1)[0]
    assert not _target_resolves(f"{real_page}#this-anchor-does-not-exist", build_surfaces)
    # A completely fabricated family is refused (never resolves even by
    # accident of the startswith('cli/') check).
    assert not _target_resolves("cli/not-a-real-family.html", build_surfaces)


def test_a_real_grouped_and_direct_cli_command_target_resolves(build_surfaces: _BuildSurfaces) -> None:
    """Both CLI page shapes -- a grouped verb page and a direct family leaf -- resolve.

    Sanity companion to the fabrication-refusal test above: the tightened
    check is not refusing every CLI target, only fabricated ones. Covers
    both page shapes `cli_reference_page_for_command` emits: a grouped
    command page (`cli/app/<group>.html#...`) and a leaf mounted directly on
    a family root (`cli/config.html#...`, no intervening group segment).
    """
    cli_targets = build_surfaces["cli_targets"]
    assert cli_targets, "the live CLI tree must carry at least one command"
    grouped = [target for target in cli_targets if re.fullmatch(r"cli/[a-z0-9-]+/[a-z0-9-]+\.html#[a-z0-9-]+", target)]
    direct = [target for target in cli_targets if re.fullmatch(r"cli/[a-z0-9-]+\.html#[a-z0-9-]+", target)]
    assert grouped, "the live tree must carry at least one grouped command for this gate to bite"
    assert direct, "the live tree must carry at least one direct family-root command for this gate to bite"
    assert _target_resolves(grouped[0], build_surfaces)
    assert _target_resolves(direct[0], build_surfaces)


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
    query resolves to an exact generated legal article and/or the prorrata
    concept card. BOE provenance is checked on the real resolved record, not in
    this laundered five-field artifact.
    """
    prorrata = [m for m in relevance.mappings if m.concept_id == "prorrata" and m.targets]
    assert prorrata, "prorrata relevance data must ship at least one grounding target; re-run the sweep"
    all_targets = [t.target for m in prorrata for t in m.targets]
    expected_legal_targets = {
        "_generated/legal/boe-a-1992-28740.html#legal-ley-37-1992-art-102",
        "_generated/legal/boe-a-1992-28740.html#legal-ley-37-1992-art-104",
    }
    assert any("_generated/glossary.html#term-prorrata" in t for t in all_targets) or any(
        t in expected_legal_targets for t in all_targets
    ), "prorrata maps to neither its concept card nor an exact generated legal article"
