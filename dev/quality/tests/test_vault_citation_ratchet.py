"""Gate: the vault-citation ratchet refuses in all four directions.

A ratchet that only ever sees a matching tree has not been shown able to refuse
a drifting one, so every direction is constructed here rather than pinned.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..vault_citation_ratchet import count_citations, evaluate, rule_slugs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SLUGS = frozenset({"aeat-architecture-boundaries", "no-silent-under-declaration"})


def _tree(tmp_path: Path, **modules: str) -> Path:
    """Write a miniature shipped tree and return its root."""
    root = tmp_path / "src"
    (root / "pkg").mkdir(parents=True)
    for name, source in modules.items():
        (root / "pkg" / f"{name}.py").write_text(source, encoding="utf-8")
    return root


def _baseline(tmp_path: Path, **counts: int) -> Path:
    """Write a baseline file and return its path."""
    path = tmp_path / "baseline.toml"
    body = "\n".join(f'"pkg/{name}.py" = {count}' for name, count in counts.items())
    path.write_text(f"[files]\n{body}\n", encoding="utf-8")
    return path


def test_the_shipped_rule_slugs_are_read_from_the_rule_sources() -> None:
    """Hardcoding the list would let a renamed rule slip past unnoticed."""
    slugs = rule_slugs()
    assert "aeat-architecture-boundaries" in slugs
    assert all(not slug.endswith(".builtin") for slug in slugs)


def test_a_slug_is_counted_only_inside_backticks(tmp_path: Path) -> None:
    """Bare words are domain vocabulary; counting them would argue with English.

    "the per-period no-silent-under-declaration warning" is a sentence about
    behaviour, not a citation of the rule that happens to share its name.
    """
    root = _tree(
        tmp_path,
        cited='"""Cites ``aeat-architecture-boundaries`` explicitly."""\n',
        prose='"""A no-silent-under-declaration warning, said in plain words."""\n',
    )
    counts = count_citations(root, _SLUGS)
    assert counts == {"pkg/cited.py": 1}


def test_a_file_that_newly_cites_a_slug_is_refused(tmp_path: Path) -> None:
    """The direction the rule actually needs enforced: no NEW citations."""
    root = _tree(tmp_path, fresh='"""Cites ``aeat-architecture-boundaries``."""\n')
    verdict = evaluate(root, _baseline(tmp_path))
    assert not verdict.ok
    assert verdict.added == {"pkg/fresh.py": 1}


def test_a_recorded_file_that_gains_a_citation_is_refused(tmp_path: Path) -> None:
    """Growth inside an already-indebted file must not pass unnoticed."""
    root = _tree(
        tmp_path,
        known='"""``aeat-architecture-boundaries`` and ``no-silent-under-declaration``."""\n',
    )
    verdict = evaluate(root, _baseline(tmp_path, known=1))
    assert not verdict.ok
    assert verdict.grown == {"pkg/known.py": (2, 1)}


def test_paid_down_debt_must_be_written_down(tmp_path: Path) -> None:
    """Otherwise the baseline keeps headroom the tree no longer needs.

    Recording a count higher than the tree carries would let a later edit add a
    citation back without the gate noticing, which is how a ratchet rusts.
    """
    root = _tree(tmp_path, known='"""Cites ``aeat-architecture-boundaries`` once."""\n')
    verdict = evaluate(root, _baseline(tmp_path, known=2))
    assert not verdict.ok
    assert verdict.shrunk == {"pkg/known.py": (1, 2)}


def test_a_spent_entry_must_be_removed(tmp_path: Path) -> None:
    """A file that carries none has no business holding a baseline line."""
    root = _tree(tmp_path, clean='"""No citation at all."""\n')
    verdict = evaluate(root, _baseline(tmp_path, clean=1))
    assert not verdict.ok
    assert verdict.spent == ("pkg/clean.py",)


def test_a_tree_matching_its_baseline_passes(tmp_path: Path) -> None:
    """The normal case, so the gate is not merely always-red."""
    root = _tree(tmp_path, known='"""Cites ``aeat-architecture-boundaries``."""\n')
    assert evaluate(root, _baseline(tmp_path, known=1)).ok


def test_a_slug_wrapped_in_a_sphinx_role_is_counted(tmp_path: Path) -> None:
    """A citation wearing symbol syntax is still a citation.

    The first pattern looked only for the literal ``slug`` form, so
    ``:func:`no-silent-under-declaration``` sat uncounted in shipped code --
    doubly wrong, because it also dresses a rule name as a Python function.
    """
    root = _tree(
        tmp_path,
        role='"""Required by :ref:`aeat-architecture-boundaries` for this path."""\n',
        func='"""Surfaces the advisory (:func:`no-silent-under-declaration`)."""\n',
    )
    assert count_citations(root, _SLUGS) == {"pkg/role.py": 1, "pkg/func.py": 1}


def test_a_slug_in_plain_prose_stays_uncounted_under_either_spelling(tmp_path: Path) -> None:
    """Widening to roles must not widen to bare words as well."""
    root = _tree(
        tmp_path,
        prose='"""Follows aeat-architecture-boundaries in spirit, said plainly."""\n',
    )
    assert count_citations(root, _SLUGS) == {}
