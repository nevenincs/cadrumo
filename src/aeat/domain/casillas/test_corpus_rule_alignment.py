"""Lock the corpus ↔ rule-engine alignment in CI.

Three invariants are enforced:

1. Every formula declared in the rule-engine ruleset for a given
   ``(modelo, year)`` is reflected in the matching corpus record's
   ``references_rules`` tuple. A formula in the engine without a
   corpus link is a legal-traceability gap.

2. Every ``references_rules`` entry in every corpus catalogue resolves
   to a real ``formula_id`` in the engine registry. A dangling pointer
   means the corpus claims a calculation that the engine cannot run.

3. For every corpus record marked ``computed=True``, the matching
   engine formula's casilla refs equal the record's
   ``references_casillas`` tuple. A divergence means the corpus and
   the engine disagree on which casillas drive the calculation.
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
                failures.append(
                    f"{modelo} {period} cas {rec.casilla_id}: computed=True but no references_rules"
                )
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
