"""Lock the corpus / rule-engine alignment in CI.

Three invariants are enforced against the committed
``corpus/casillas/`` JSON and the
:mod:`aeat.domain.formulas` engine registry:

* Every formula declared in the rule-engine ruleset for a given
  ``(modelo, year)`` is reflected in the matching corpus record's
  ``references_rules`` tuple. A formula in the engine without a
  corpus link is a legal-traceability gap.
* Every ``references_rules`` entry in every corpus catalogue resolves
  to a real ``formula_id`` in the engine registry. A dangling pointer
  means the corpus claims a calculation that the engine cannot run.
* For every corpus record marked ``computed=True``, the matching
  engine formula's casilla refs equal the record's
  ``references_casillas`` tuple. A divergence means the corpus and
  the engine disagree on which casillas drive the calculation.

Two further sanity checks ensure every record carries authoritative
Spanish text on ``label`` and ``help`` and that intra-catalogue
``references_casillas`` resolve.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...core.config import PROJECT_ROOT
from ..formulas._formula import FormulaDefinition, iter_casilla_refs
from ..formulas._registry import get_registry
from . import load_casillas

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _collect_refs(formula: object) -> list[str]:
    seen: list[str] = []
    for casilla_id in iter_casilla_refs(formula):
        if casilla_id not in seen:
            seen.append(casilla_id)
    return seen


def _iter_corpus_files() -> list[Path]:
    return sorted((PROJECT_ROOT / "corpus" / "casillas").rglob("*.json"))


def _modelo_period_for(path: Path) -> tuple[str, str]:
    rel = path.relative_to(PROJECT_ROOT / "corpus" / "casillas")
    modelo = f"MODELO_{rel.parts[0].removeprefix('modelo_')}"
    period = path.stem
    return modelo, period


def test_every_engine_formula_has_corpus_link() -> None:
    """Every (modelo, year) formula must be referenced in the corpus."""
    registry = get_registry()
    rs_by_key: dict[tuple[str, int], list] = {}
    for rs in registry.rulesets:
        rs_by_key.setdefault((rs.modelo.value, rs.effective_from.year), []).append(rs)

    failures: list[str] = []

    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        modelo_code = modelo.removeprefix("MODELO_")
        year = int(period[:4])
        rulesets = rs_by_key.get((modelo_code, year), [])
        if not rulesets:
            continue

        catalogue = load_casillas(modelo, period)
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


def test_no_dangling_rule_references_in_corpus() -> None:
    """Every references_rules entry must resolve to an engine formula_id."""
    registry = get_registry()
    known_formula_ids = {f.formula_id for rs in registry.rulesets for f in rs.formulas}

    failures: list[str] = []

    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
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


def test_every_corpus_record_has_authoritative_label_and_help() -> None:
    """Every record's label and help must carry non-empty Spanish text."""
    failures: list[str] = []
    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
        for rec in catalogue.records:
            if not rec.label.get("es", "").strip():
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: empty label.es")
            if not rec.help.get("es", "").strip():
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: empty help.es")
    if failures:
        msg = "Corpus has records with empty authoritative content:\n" + "\n".join(f" - {f}" for f in failures)
        pytest.fail(msg)


def test_corpus_internal_casilla_refs_resolve() -> None:
    """Every references_casillas entry must point at another record in the same catalogue."""
    failures: list[str] = []
    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
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


def test_every_computed_record_has_at_least_one_rule_link() -> None:
    """A computed casilla must point at the rule formula that derives it."""
    failures: list[str] = []
    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
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


def test_computed_records_match_engine_formula_refs() -> None:
    """A corpus computed record's casilla refs must match the engine's primary formula."""
    registry = get_registry()
    # Map (modelo, year, casilla_id) -> the *primary* (non-summary) formula.
    primary_formula: dict[tuple[str, int, str], FormulaDefinition] = {}
    summary_formula: dict[tuple[str, int, str], FormulaDefinition] = {}
    for rs in registry.rulesets:
        target = summary_formula if rs.variant == "summary" else primary_formula
        for f in rs.formulas:
            target[(rs.modelo.value, rs.effective_from.year, f.casilla_id)] = f

    failures: list[str] = []

    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        modelo_code = modelo.removeprefix("MODELO_")
        year = int(period[:4])
        catalogue = load_casillas(modelo, period)

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


def test_corpus_record_modelo_and_period_match_path() -> None:
    """Every record's ``modelo`` and ``period`` must match the file path."""
    failures: list[str] = []
    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
        for rec in catalogue.records:
            if rec.modelo != modelo:
                failures.append(f"{path}: cas {rec.casilla_id} modelo={rec.modelo!r} != path {modelo!r}")
            if rec.period != period:
                failures.append(f"{path}: cas {rec.casilla_id} period={rec.period!r} != path {period!r}")
    if failures:
        pytest.fail("Corpus has modelo/period drift:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_no_self_references() -> None:
    """A casilla must not include its own id in ``references_casillas``."""
    failures: list[str] = []
    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
        for rec in catalogue.records:
            if rec.casilla_id in rec.references_casillas:
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: self-reference")
    if failures:
        pytest.fail("Corpus has self-referencing casillas:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_no_circular_references() -> None:
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

    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
        graph = {r.casilla_id: tuple(r.references_casillas) for r in catalogue.records}
        cyc = find_cycle(graph)
        if cyc:
            failures.append(f"{modelo} {period}: cycle {' -> '.join(cyc)}")
    if failures:
        pytest.fail("Corpus references_casillas contains cycles:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_inline_boe_ids_well_formed() -> None:
    """Every BOE-A-YYYY-NNN identifier in help must use a plausible year."""
    import re

    boe_re = re.compile(r"BOE-A-(\d{4})-\d+")
    failures: list[str] = []
    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
        for rec in catalogue.records:
            for value in rec.help.values():
                for m in boe_re.finditer(value):
                    year = int(m.group(1))
                    if year < 1968 or year > 2026:
                        failures.append(f"{modelo} {period} cas {rec.casilla_id}: implausible BOE year {m.group(0)}")
    if failures:
        pytest.fail("Corpus has malformed BOE identifiers:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_data_type_is_uniform_per_casilla() -> None:
    """A casilla's ``data_type`` must not drift across periods."""
    from collections import defaultdict

    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
        for rec in catalogue.records:
            seen[(modelo, rec.casilla_id)].add(rec.data_type.value)
    failures = [
        f"{modelo} cas {cid}: data_type drift = {sorted(types)}"
        for (modelo, cid), types in seen.items()
        if len(types) > 1
    ]
    if failures:
        pytest.fail("Corpus data_type drift:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_label_es_is_uniform_per_casilla() -> None:
    """A casilla's authoritative Spanish label must not drift across periods."""
    from collections import defaultdict

    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
        for rec in catalogue.records:
            seen[(modelo, rec.casilla_id)].add(rec.label["es"])
    failures = [
        f"{modelo} cas {cid}: label drift {sorted(labels)}"
        for (modelo, cid), labels in seen.items()
        if len(labels) > 1
    ]
    if failures:
        pytest.fail("Corpus label.es drift:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_references_rules_is_uniform_within_year() -> None:
    """All periods within a single fiscal year must agree on references_rules."""
    from collections import defaultdict

    seen: dict[tuple[str, str, str], set[tuple[str, ...]]] = defaultdict(set)
    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        year = period[:4]
        catalogue = load_casillas(modelo, period)
        for rec in catalogue.records:
            seen[(modelo, year, rec.casilla_id)].add(tuple(rec.references_rules))
    failures = [
        f"{modelo} {year} cas {cid}: references_rules drift = {sorted(variants)}"
        for (modelo, year, cid), variants in seen.items()
        if len(variants) > 1
    ]
    if failures:
        pytest.fail("Corpus references_rules drift within year:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_must_derive_validation_aligns_with_computed_flag() -> None:
    """``computed=True`` ↔ ``must_derive`` validation rule (both directions)."""
    failures: list[str] = []
    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
        for rec in catalogue.records:
            has_must_derive = any(v.rule == "must_derive" for v in rec.validation)
            if rec.computed and not has_must_derive:
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: computed but missing must_derive")
            if not rec.computed and has_must_derive:
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: must_derive on a non-computed record")
    if failures:
        pytest.fail("Corpus computed/validation drift:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_formula_presence_aligns_with_computed_flag() -> None:
    """``computed=True`` ↔ a non-null ``formula`` reference."""
    failures: list[str] = []
    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
        for rec in catalogue.records:
            if rec.computed and rec.formula is None:
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: computed but formula is None")
            if not rec.computed and rec.formula is not None:
                failures.append(f"{modelo} {period} cas {rec.casilla_id}: not computed but carries a formula")
    if failures:
        pytest.fail("Corpus formula/computed drift:\n" + "\n".join(f" - {f}" for f in failures))


def test_corpus_formula_expression_mentions_match_references_casillas() -> None:
    """Casilla IDs inside the rendered formula expression must match references_casillas exactly."""
    import re

    token_re = re.compile(r"\b(\d{2,5})\b(?!%)")
    failures: list[str] = []
    for path in _iter_corpus_files():
        modelo, period = _modelo_period_for(path)
        catalogue = load_casillas(modelo, period)
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
