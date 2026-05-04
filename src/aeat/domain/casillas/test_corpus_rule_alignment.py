"""Lock non-authoritative casilla corpus structural integrity in CI.

Every committed casilla catalogue under ``corpus/casillas/`` must be
internally consistent. The registry, not this corpus, owns legal and
calculation alignment. These tests consume the shared
``corpus_catalogues`` fixture rather than re-walking the directory.

Invariants:

* Every record carries authoritative Spanish text on ``label`` /
  ``help``, intra-catalogue references resolve, the reference graph
  is acyclic, and structural shape is uniform within a year.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...core.config import PROJECT_ROOT
from .models import CasillaCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_Catalogues = tuple[tuple[Path, str, str, CasillaCatalogue], ...]


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


def test_corpus_directory_layout_matches_modelo_identifiers() -> None:
    """Every current ModeloCode identifier must have a corpus directory and vice versa."""
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

    The committed corpus is a reviewed surface. A record with either
    flag set here means unreviewed material leaked into the store.
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


def test_corpus_casilla_ids_match_extractor_for_extractor_backed_modelos() -> None:
    """Corpus ID coverage no longer treats extractor class maps as authority."""
    import importlib

    extractor_package = importlib.import_module("aeat.adapters.inbound.declaracion._extractors")
    assert not hasattr(extractor_package, "_REGISTERED_CLASSES")
    assert not hasattr(extractor_package, "_REGISTRY")


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
    to the enum requires the committed corpus to be updated in the
    same change.
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


def test_corpus_modelo_840_label_es_matches_extractor_text_labels() -> None:
    """M840 corpus labels must not depend on a Python extractor class map."""
    import importlib.util

    spec = importlib.util.find_spec("aeat.adapters.inbound.declaracion._extractors.modelo_840_v2025")
    assert spec is None
