"""Lock the corpus / rule-engine alignment in CI.

Every committed casilla catalogue under ``corpus/casillas/`` must be
internally consistent and aligned with the rule engine's registry.
The 13+ invariants below are enforced over a single session-scoped
parse of every catalogue (see ``conftest.py``); each test consumes
the shared ``corpus_catalogues`` / ``engine_registry`` fixtures
rather than re-walking the directory.

Invariants:

* Every formula declared in the rule-engine ruleset for a given
  ``(modelo, year)`` is reflected in the matching corpus record's
  ``references_rules`` tuple.
* Every ``references_rules`` entry resolves to a real
  ``formula_id`` in the engine registry.
* For every corpus record marked ``computed=True``, the matching
  engine formula's casilla refs equal the record's
  ``references_casillas`` tuple.
* Every record carries authoritative Spanish text on ``label`` /
  ``help``, intra-catalogue references resolve, the reference graph
  is acyclic, and structural shape is uniform within a year.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...core.config import PROJECT_ROOT
from ..formulas._formula import FormulaDefinition, iter_casilla_refs
from ..formulas._registry import RulesetRegistry
from . import load_casillas
from .models import CasillaCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_Catalogues = tuple[tuple[Path, str, str, CasillaCatalogue], ...]


def _collect_refs(formula: object) -> list[str]:
    seen: list[str] = []
    for casilla_id in iter_casilla_refs(formula):
        if casilla_id not in seen:
            seen.append(casilla_id)
    return seen


def test_every_engine_formula_has_corpus_link(
    corpus_catalogues: _Catalogues,
    engine_registry: RulesetRegistry,
) -> None:
    """Every (modelo, year) formula must be referenced in the corpus."""
    rs_by_key: dict[tuple[str, int], list] = {}
    for rs in engine_registry.rulesets:
        rs_by_key.setdefault((rs.modelo.value, rs.effective_from.year), []).append(rs)

    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        modelo_code = modelo.removeprefix("MODELO_")
        year = int(period[:4])
        rulesets = rs_by_key.get((modelo_code, year), [])
        if not rulesets:
            continue
        by_id = {r.casilla_id: r for r in catalogue.records}
        for rs in rulesets:
            for f in rs.formulas:
                rec = by_id.get(f.casilla_id)
                if rec is None:
                    failures.append(
                        f"{modelo} {period} cas {f.casilla_id}: corpus has no record but engine "
                        f"defines formula {f.formula_id!r}"
                    )
                    continue
                if f.formula_id not in rec.references_rules:
                    failures.append(
                        f"{modelo} {period} cas {f.casilla_id}: corpus references_rules missing "
                        f"engine formula {f.formula_id!r} (got {list(rec.references_rules)})"
                    )

    if failures:
        msg = "Corpus is missing rule-engine cross-links:\n" + "\n".join(f" - {f}" for f in failures)
        pytest.fail(msg)


def test_no_dangling_rule_references_in_corpus(
    corpus_catalogues: _Catalogues,
    engine_registry: RulesetRegistry,
) -> None:
    """Every references_rules entry must resolve to an engine formula_id."""
    known_formula_ids = {f.formula_id for rs in engine_registry.rulesets for f in rs.formulas}

    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            for ref in rec.references_rules:
                if ref not in known_formula_ids:
                    failures.append(
                        f"{modelo} {period} cas {rec.casilla_id}: dangling references_rules "
                        f"entry {ref!r} (no matching formula in engine registry)"
                    )

    if failures:
        msg = "Corpus has dangling rule-engine references:\n" + "\n".join(f" - {f}" for f in failures)
        pytest.fail(msg)


def test_every_corpus_record_has_authoritative_label_and_help(
    corpus_catalogues: _Catalogues,
) -> None:
    """Every record's label and help must carry non-empty Spanish text."""
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            if not rec.label.get("es", "").strip():
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: empty label.es")
            if not rec.help.get("es", "").strip():
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: empty help.es")
    if failures:
        msg = "Corpus has records with empty authoritative content:\n" + "\n".join(f" - {f}" for f in failures)
        pytest.fail(msg)


def test_corpus_internal_casilla_refs_resolve(corpus_catalogues: _Catalogues) -> None:
    """Every references_casillas entry must point at another record in the same catalogue."""
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        ids = {r.casilla_id for r in catalogue.records}
        for rec in catalogue.records:
            for ref in rec.references_casillas:
                if ref not in ids:
                    failures.append(
                        f"{modelo} {period} cas {rec.casilla_id}: references_casillas points "
                        f"at non-existent casilla {ref!r}"
                    )
    if failures:
        msg = "Corpus has dangling intra-catalogue references:\n" + "\n".join(f" - {f}" for f in failures)
        pytest.fail(msg)


def test_every_computed_record_has_at_least_one_rule_link(corpus_catalogues: _Catalogues) -> None:
    """A computed casilla must point at the rule formula that derives it."""
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            if rec.computed and not rec.references_rules:
                # Modelo 190 totals (19/20/21) aggregate manually-curated input
                # rows and have no engine-side formula; allow them by exception.
                if modelo == "MODELO_190" and rec.casilla_id in {"19", "20", "21"}:
                    continue
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: computed=True but no references_rules")
    if failures:
        msg = "Computed corpus records missing rule links:\n" + "\n".join(f" - {f}" for f in failures)
        pytest.fail(msg)


def test_computed_records_match_engine_formula_refs(
    corpus_catalogues: _Catalogues,
    engine_registry: RulesetRegistry,
) -> None:
    """A corpus computed record's casilla refs must match the engine's primary formula."""
    primary_formula: dict[tuple[str, int, str], FormulaDefinition] = {}
    summary_formula: dict[tuple[str, int, str], FormulaDefinition] = {}
    for rs in engine_registry.rulesets:
        target = summary_formula if rs.variant == "summary" else primary_formula
        for f in rs.formulas:
            target[(rs.modelo.value, rs.effective_from.year, f.casilla_id)] = f

    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        modelo_code = modelo.removeprefix("MODELO_")
        year = int(period[:4])
        for rec in catalogue.records:
            if not rec.computed:
                continue
            key = (modelo_code, year, rec.casilla_id)
            f = primary_formula.get(key) or summary_formula.get(key)
            if f is None:
                # Some corpus computed records aggregate manual data
                # (e.g. modelo 190 totals). Skip if no engine formula.
                continue
            engine_refs = _collect_refs(f.formula)
            corpus_refs = list(rec.references_casillas)
            if corpus_refs != engine_refs:
                failures.append(
                    f"{modelo} {period} cas {rec.casilla_id}: references_casillas mismatch — "
                    f"corpus={corpus_refs} engine={engine_refs}"
                )

    if failures:
        msg = "Corpus references_casillas diverge from engine:\n" + "\n".join(f" - {f}" for f in failures)
        pytest.fail(msg)


def test_corpus_record_modelo_and_period_match_path(corpus_catalogues: _Catalogues) -> None:
    """Every record's ``modelo`` and ``period`` must match the file path."""
    failures: list[str] = []
    for path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            if rec.modelo != modelo:
                failures.append(f"{path}: cas {rec.casilla_id} modelo={rec.modelo!r} != path {modelo!r}")
            if rec.period != period:
                failures.append(f"{path}: cas {rec.casilla_id} period={rec.period!r} != path {period!r}")
    if failures:
        pytest.fail("Corpus has modelo/period drift:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_no_self_references(corpus_catalogues: _Catalogues) -> None:
    """A casilla must not include its own id in ``references_casillas``."""
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            if rec.casilla_id in rec.references_casillas:
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: self-reference")
    if failures:
        pytest.fail("Corpus has self-referencing casillas:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_no_circular_references(corpus_catalogues: _Catalogues) -> None:
    """The casilla reference graph must be acyclic per catalogue."""
    failures: list[str] = []

    def find_cycle(graph: dict[str, tuple[str, ...]]) -> list[str] | None:
        color = {n: "white" for n in graph}
        parent: dict[str, str | None] = {n: None for n in graph}

        def dfs(start: str) -> list[str] | None:
            stack: list[tuple[str, int]] = [(start, 0)]
            while stack:
                node, idx = stack.pop()
                if idx == 0:
                    color[node] = "gray"
                neighbors = graph.get(node, ())
                if idx < len(neighbors):
                    stack.append((node, idx + 1))
                    nb = neighbors[idx]
                    if nb not in color:
                        continue
                    if color[nb] == "gray":
                        cycle = [nb]
                        cur: str | None = node
                        while cur is not None and cur != nb:
                            cycle.append(cur)
                            cur = parent[cur]
                        cycle.append(nb)
                        return list(reversed(cycle))
                    if color[nb] == "white":
                        parent[nb] = node
                        stack.append((nb, 0))
                else:
                    color[node] = "black"
            return None

        for n in graph:
            if color[n] == "white":
                cyc = dfs(n)
                if cyc:
                    return cyc
        return None

    for _path, modelo, period, catalogue in corpus_catalogues:
        graph = {r.casilla_id: tuple(r.references_casillas) for r in catalogue.records}
        cyc = find_cycle(graph)
        if cyc:
            failures.append(f"{modelo} {period}: cycle {' -> '.join(cyc)}")
    if failures:
        pytest.fail("Corpus references_casillas contains cycles:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_inline_boe_ids_well_formed(corpus_catalogues: _Catalogues) -> None:
    """Every BOE-A-YYYY-NNN identifier in help must use a plausible year."""
    import re

    boe_re = re.compile(r"BOE-A-(\d{4})-\d+")
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            for value in rec.help.values():
                if not isinstance(value, str):
                    continue
                for m in boe_re.finditer(value):
                    year = int(m.group(1))
                    if year < 1968 or year > 2026:
                        failures.append(f"{modelo} {period} cas {rec.casilla_id}: implausible BOE year {m.group(0)}")
    if failures:
        pytest.fail("Corpus has malformed BOE identifiers:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_data_type_is_uniform_per_casilla(corpus_catalogues: _Catalogues) -> None:
    """A casilla's ``data_type`` must not drift across periods."""
    from collections import defaultdict

    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for _path, modelo, _period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            seen[(modelo, rec.casilla_id)].add(rec.data_type.value)
    failures = [
        f"{modelo} cas {cid}: data_type drift = {sorted(types)}"
        for (modelo, cid), types in seen.items()
        if len(types) > 1
    ]
    if failures:
        pytest.fail("Corpus data_type drift:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_label_es_is_uniform_per_casilla(corpus_catalogues: _Catalogues) -> None:
    """A casilla's authoritative Spanish label must not drift across periods."""
    from collections import defaultdict

    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for _path, modelo, _period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            seen[(modelo, rec.casilla_id)].add(rec.label["es"])
    failures = [
        f"{modelo} cas {cid}: label drift {sorted(labels)}" for (modelo, cid), labels in seen.items() if len(labels) > 1
    ]
    if failures:
        pytest.fail("Corpus label.es drift:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_references_rules_is_uniform_within_year(corpus_catalogues: _Catalogues) -> None:
    """All periods within a single fiscal year must agree on references_rules."""
    from collections import defaultdict

    seen: dict[tuple[str, str, str], set[tuple[str, ...]]] = defaultdict(set)
    for _path, modelo, period, catalogue in corpus_catalogues:
        year = period[:4]
        for rec in catalogue.records:
            seen[(modelo, year, rec.casilla_id)].add(tuple(rec.references_rules))
    failures = [
        f"{modelo} {year} cas {cid}: references_rules drift = {sorted(variants)}"
        for (modelo, year, cid), variants in seen.items()
        if len(variants) > 1
    ]
    if failures:
        pytest.fail("Corpus references_rules drift within year:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_must_derive_validation_aligns_with_computed_flag(corpus_catalogues: _Catalogues) -> None:
    """``computed=True`` ↔ ``must_derive`` validation rule (both directions)."""
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            has_must_derive = any(v.rule == "must_derive" for v in rec.validation)
            if rec.computed and not has_must_derive:
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: computed but missing must_derive")
            if not rec.computed and has_must_derive:
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: must_derive on a non-computed record")
    if failures:
        pytest.fail("Corpus computed/validation drift:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_formula_presence_aligns_with_computed_flag(corpus_catalogues: _Catalogues) -> None:
    """``computed=True`` ↔ a non-null ``formula`` reference."""
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            if rec.computed and rec.formula is None:
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: computed but formula is None")
            if not rec.computed and rec.formula is not None:
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: not computed but carries a formula")
    if failures:
        pytest.fail("Corpus formula/computed drift:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_formula_expression_mentions_match_references_casillas(corpus_catalogues: _Catalogues) -> None:
    """Casilla IDs inside the rendered formula expression must match references_casillas exactly."""
    import re

    token_re = re.compile(r"\b(\d{2,5})\b(?!%)")
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        catalogue_ids = {r.casilla_id for r in catalogue.records}
        for rec in catalogue.records:
            if rec.formula is None:
                continue
            mentioned = sorted({tok for tok in token_re.findall(rec.formula.expression) if tok in catalogue_ids})
            declared = sorted(set(rec.references_casillas))
            if mentioned != declared:
                failures.append(
                    f"{modelo} {period} cas {rec.casilla_id}: expr {rec.formula.expression!r} "
                    f"mentions {mentioned} but declared refs are {declared}"
                )
    if failures:
        pytest.fail("Corpus formula expression vs refs drift:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_directory_layout_matches_modelo_registry() -> None:
    """Every ModeloCode must have a corpus directory and vice versa."""
    from ..modelos import ModeloCode

    corpus_root = PROJECT_ROOT / "corpus" / "casillas"
    corpus_dirs = {p.name.removeprefix("modelo_").upper() for p in corpus_root.iterdir() if p.is_dir()}
    enum_codes = {code.value for code in ModeloCode}

    missing_dirs = enum_codes - corpus_dirs
    extra_dirs = corpus_dirs - enum_codes
    failures: list[str] = []
    if missing_dirs:
        failures.append(f"ModeloCode entries without a corpus directory: {sorted(missing_dirs)}")
    if extra_dirs:
        failures.append(f"corpus directories without a ModeloCode entry: {sorted(extra_dirs)}")
    if failures:
        pytest.fail("Corpus / ModeloCode coverage mismatch:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_committed_records_are_canonical_not_drafts(corpus_catalogues: _Catalogues) -> None:
    """No record may carry ``synthetic=True`` or ``llm_draft_provenance``.

    The committed corpus is the human-reviewed canonical surface; LLM
    draft payloads are temp-file only via :func:`write_extract_draft`
    / :func:`write_translate_draft`. A record with either flag set
    here means an unreviewed draft leaked into the canonical store.
    """
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            if rec.synthetic:
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: synthetic=True in canonical corpus")
            if rec.llm_draft_provenance is not None:
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: carries LLM draft provenance")
    if failures:
        pytest.fail("Corpus contains non-canonical records:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_casilla_id_set_matches_engine_ruleset(
    corpus_catalogues: _Catalogues,
    engine_registry: RulesetRegistry,
) -> None:
    """For each (modelo, year), the corpus' casilla IDs must be a superset of the engine ruleset's IDs.

    The corpus may carry additional manually-curated user-input casillas
    that the engine does not formula-derive (e.g., the M111 augmentation
    perceptor / percepción rows). What it must NOT do is omit any ID
    the engine declares — that would mean the engine derives a casilla
    the corpus has no record of.
    """
    rs_by_key: dict[tuple[str, int], list] = {}
    for rs in engine_registry.rulesets:
        rs_by_key.setdefault((rs.modelo.value, rs.effective_from.year), []).append(rs)

    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        modelo_code = modelo.removeprefix("MODELO_")
        year = int(period[:4])
        rulesets = rs_by_key.get((modelo_code, year), [])
        if not rulesets:
            continue
        engine_ids = {c.casilla_id for rs in rulesets for c in rs.casillas}
        corpus_ids = {r.casilla_id for r in catalogue.records}
        missing = engine_ids - corpus_ids
        if missing:
            failures.append(f"{modelo} {period}: engine ruleset declares casillas not in corpus: {sorted(missing)}")
    if failures:
        pytest.fail("Corpus is missing casillas that the engine declares:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_casilla_ids_match_extractor_for_non_ruleset_modelos() -> None:
    """For modelos without a rule engine ruleset (190 / 193 / 347 / 349 / 840),
    the corpus casilla ID set must exactly match the registered extractor's
    ``casilla_ids ∪ text_casilla_ids``.

    Catches drift between the curated multilingual label/help data in
    :mod:`aeat.domain.casillas._hydrate` and the canonical extractor IDs.
    """
    from ...adapters.inbound.declaracion._extractors import _REGISTERED_CLASSES

    failures: list[str] = []
    for non_ruleset_modelo in ("190", "193", "347", "349", "840"):
        extractor_ids: set[str] = set()
        for cls in _REGISTERED_CLASSES:
            if cls.template_revision.modelo != non_ruleset_modelo:
                continue
            extractor_ids.update(getattr(cls, "casilla_ids", ()))
            extractor_ids.update(getattr(cls, "text_casilla_ids", ()))
        if not extractor_ids:
            continue

        # Pick the latest period as the representative catalogue.
        modelo = f"MODELO_{non_ruleset_modelo}"
        candidates = sorted((PROJECT_ROOT / "corpus" / "casillas" / modelo.lower()).glob("*.json"))
        if not candidates:
            failures.append(f"{modelo}: no corpus catalogues on disk")
            continue
        catalogue = load_casillas(modelo, candidates[-1].stem)
        corpus_ids = {r.casilla_id for r in catalogue.records}
        missing = extractor_ids - corpus_ids
        extra = corpus_ids - extractor_ids
        if missing:
            failures.append(f"{modelo}: extractor IDs missing from corpus: {sorted(missing)}")
        if extra:
            failures.append(f"{modelo}: corpus IDs not declared by extractor: {sorted(extra)}")
    if failures:
        pytest.fail("Corpus drifted from extractor canonical IDs:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_references_rules_have_no_duplicates(corpus_catalogues: _Catalogues) -> None:
    """``references_rules`` must be dedup'd per record."""
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            if len(rec.references_rules) != len(set(rec.references_rules)):
                failures.append(
                    f"{modelo} {period} cas {rec.casilla_id}: duplicate references_rules {list(rec.references_rules)}"
                )
    if failures:
        pytest.fail("Corpus has duplicate references_rules:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_references_casillas_have_no_duplicates(corpus_catalogues: _Catalogues) -> None:
    """``references_casillas`` must be dedup'd per record."""
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            if len(rec.references_casillas) != len(set(rec.references_casillas)):
                failures.append(
                    f"{modelo} {period} cas {rec.casilla_id}: duplicate references_casillas {list(rec.references_casillas)}"
                )
    if failures:
        pytest.fail("Corpus has duplicate references_casillas:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_cross_modelo_hints_match_engine_caps_into() -> None:
    """Annual summary modelos must mention every modelo whose ``caps_into`` resolves to them.

    The engine's :class:`ModeloMetadata.caps_into` field encodes the
    upstream relationship (e.g., M130 caps into M100). The corpus help
    body for an annual modelo must mention each upstream modelo so the
    cross-modelo dependency is visible to Kent inline.
    """
    from ..modelos import ModeloCode, get_modelo

    upstream_by_modelo: dict[str, set[str]] = {}
    for code in ModeloCode:
        meta = get_modelo(code.value)
        if meta.caps_into is not None:
            upstream_by_modelo.setdefault(meta.caps_into.value, set()).add(code.value)

    failures: list[str] = []
    for downstream, upstream_set in upstream_by_modelo.items():
        modelo = f"MODELO_{downstream}"
        # Pick the latest year's catalogue.
        candidates = sorted((PROJECT_ROOT / "corpus" / "casillas" / modelo.lower()).glob("*.json"))
        if not candidates:
            continue
        catalogue = load_casillas(modelo, candidates[-1].stem)
        if not catalogue.records:
            continue
        # Sample help.es of any single record (the cross-modelo hint
        # is appended uniformly).
        help_es = catalogue.records[0].help["es"]
        for upstream in upstream_set:
            if f"modelo {upstream}" not in help_es:
                failures.append(
                    f"{modelo}: help body does not mention upstream M{upstream} "
                    f"(engine caps_into={sorted(upstream_set)})"
                )
    if failures:
        pytest.fail(
            "Corpus cross-modelo hint missing engine caps_into upstream:\n" + "\n".join(f" - {f}" for f in failures)
        )


def test_corpus_within_year_periods_share_structural_shape(corpus_catalogues: _Catalogues) -> None:
    """Every period within a single fiscal year must agree on each casilla's structure.

    Snapshots ``(data_type, computed, references_casillas, references_rules,
    validation rule names)`` per ``(modelo, year, casilla_id)`` across
    every period file (Q1-Q4 / M01-M12 / annual). Drift between
    periods of the same year is a structural integrity failure.
    """
    from collections import defaultdict

    snapshots: dict[tuple[str, str, str], set[tuple]] = defaultdict(set)
    for _path, modelo, period, catalogue in corpus_catalogues:
        year = period[:4]
        if "Q" not in period and "-" not in period:
            continue
        for rec in catalogue.records:
            snap = (
                rec.data_type.value,
                rec.computed,
                tuple(rec.references_casillas),
                tuple(rec.references_rules),
                tuple(v.rule for v in rec.validation),
            )
            snapshots[(modelo, year, rec.casilla_id)].add(snap)
    failures = [
        f"{modelo} {year} cas {cid}: {len(shapes)} differing shapes"
        for (modelo, year, cid), shapes in snapshots.items()
        if len(shapes) > 1
    ]
    if failures:
        pytest.fail("Within-year period shape drift:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_label_and_help_carry_every_supported_language(corpus_catalogues: _Catalogues) -> None:
    """Every record's ``label`` and ``help`` must include every code from :class:`Language`.

    The Translatable contract is open-ended; the corpus mirrors the
    engine's :class:`aeat.core.i18n.Language` enum. Adding a language
    to the enum auto-widens the corpus on the next hydrate run; this
    test fires before the next hydrate if a language is added but
    not propagated.
    """
    from ...core.i18n import Language

    expected = {lang.value for lang in Language}
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            for field in ("label", "help"):
                container = getattr(rec, field)
                missing = expected - set(container.keys())
                if missing:
                    failures.append(
                        f"{modelo} {period} cas {rec.casilla_id} {field}: missing languages {sorted(missing)}"
                    )
                    break  # one report per record is enough
    if failures:
        pytest.fail("Corpus label / help missing supported languages:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_help_and_label_carry_no_dev_process_leakage(corpus_catalogues: _Catalogues) -> None:
    """User-facing strings must not leak engineering metadata.

    The corpus' label / help is operator-facing; it must not contain
    development-process tokens (``wave``, ``phase``, ``cycle``,
    ``iteration``, ``WIP``, ``EPIC``, ``sub-EPIC``, ``Tier-L``,
    ``restructure``, ``TBD``, ``FIXME``, ``audit finding``,
    ``Stream A`` / ``Track A``) that belong to commit messages, not
    to the AEAT domain language operators read.
    """
    import re

    forbidden = re.compile(
        r"\b(wave|phase|cycle|iteration|wip|EPIC|sub-EPIC|Tier[- ]?L|"
        r"restructure|TBD|FIXME|audit\s+finding|Stream\s+[ABC]|Track\s+[AB])\b",
        re.IGNORECASE,
    )
    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        for rec in catalogue.records:
            for field in ("label", "help"):
                container = getattr(rec, field)
                for lang in ("es", "en", "hu"):
                    value = container.get(lang, "")
                    if forbidden.search(value):
                        failures.append(
                            f"{modelo} {period} cas {rec.casilla_id} {field}.{lang}: dev-process leakage in {value[:80]!r}"
                        )
    if failures:
        pytest.fail(
            "Corpus leaks dev-process tokens into user-facing strings:\n" + "\n".join(f" - {f}" for f in failures)
        )


def test_corpus_source_manual_url_matches_hydrate_resolver(corpus_catalogues: _Catalogues) -> None:
    """Every record's ``source_manual_url`` must agree with ``_source_url_for(modelo, year)``.

    Catches drift between the canonical ``ModeloMetadata.category /
    caps_into``-driven URL resolver in the hydrate generator and the
    committed corpus on disk. If a future PR hardcodes a fresh URL
    in a corpus JSON without going through the resolver, this test
    fires.
    """
    from ._hydrate import _source_url_for

    failures: list[str] = []
    for _path, modelo, period, catalogue in corpus_catalogues:
        modelo_code = modelo.removeprefix("MODELO_")
        year = int(period[:4])
        expected = _source_url_for(modelo_code, year)
        for rec in catalogue.records:
            actual = str(rec.source_manual_url) if rec.source_manual_url is not None else ""
            if actual.rstrip("/") != expected.rstrip("/"):
                failures.append(
                    f"{modelo} {period} cas {rec.casilla_id}: source_manual_url={actual!r} != resolver {expected!r}"
                )
                break  # one mismatch per file is enough
    if failures:
        pytest.fail("Corpus source_manual_url drift from hydrate resolver:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_modelo_840_label_es_matches_extractor_text_labels() -> None:
    """M840 corpus ``label.es`` must agree (modulo accents) with the extractor's ``text_labels`` map.

    The extractor's ``text_labels`` is the canonical Spanish-label
    source for the M840 text-casilla set; it carries an ASCII-folded
    form of each label so the PDF-extraction regex stays robust against
    accent rendering quirks. The corpus carries the proper-accent
    Spanish; comparison is therefore accent-insensitive.
    """
    import unicodedata

    from ...adapters.inbound.declaracion._extractors.modelo_840_v2025 import Modelo840V2025Extractor

    def _ascii_fold(text: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()

    text_labels = Modelo840V2025Extractor.text_labels
    catalogue = load_casillas("MODELO_840", "2025")
    by_id = {r.casilla_id: r for r in catalogue.records}
    failures: list[str] = []
    for cid, expected_label in text_labels.items():
        rec = by_id.get(cid)
        if rec is None:
            failures.append(f"M840 cas {cid}: missing in corpus (extractor labels {expected_label!r})")
            continue
        # Ignore accents and "de" connector ("Causa presentacion" vs "Causa de presentación").
        corpus_folded = _ascii_fold(rec.label["es"]).replace(" de ", " ")
        extractor_folded = _ascii_fold(expected_label).replace(" de ", " ")
        if corpus_folded != extractor_folded:
            failures.append(f"M840 cas {cid}: corpus label.es {rec.label['es']!r} != extractor {expected_label!r}")
    if failures:
        pytest.fail("M840 corpus drifted from extractor text_labels:\n" + "\n".join(f" - {f}" for f in failures))
