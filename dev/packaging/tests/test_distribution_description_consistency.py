"""Pin the reconciled distribution descriptions to one canonical source.

The ungoverned metadata description tier (root ``pyproject.toml``, the Scoop
manifest, the Homebrew formula) was reconciled on 2026-07-19 to a single
README-derived canonical sentence (operator-approved). Nothing previously
guarded these metadata strings, so they had drifted independently. This
gate asserts they stay reconciled: the canonical sentence lives verbatim in the
PyPI package summary and the Scoop generator, and the Homebrew ``desc`` (kept
terse per Homebrew's style guide) is the canonical's leading clause.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = REPO_ROOT


def _string_literals(source_path: Path) -> list[str]:
    """Every string-literal value in a module, adjacent literals concatenated.

    Parsing rather than raw-text matching is what makes the gate robust: the
    Python parser merges adjacent string literals (the Scoop description is
    written as three wrapped literals) into one constant, and it exposes the
    literal segments of an f-string (the Homebrew formula is one big f-string)
    as their own constants.
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    literals: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.append(node.value)
    return literals


# The operator-approved canonical short description (README H1 + lede, compressed).
_CANONICAL_DESCRIPTION = (
    "Cadrumo is a deterministic Spanish tax calculation CLI "
    "that turns local financial records into checked, exportable modelo filing "
    "artifacts. Independent software; not affiliated with AEAT."
)
# Homebrew's `desc` is deliberately terse (style guide: <=80 chars, no period,
# no article prefix); it is the canonical sentence's leading capability clause.
_CANONICAL_HOMEBREW_DESC = "Deterministic Spanish tax calculation CLI"


def _pyproject_description() -> str:
    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["description"])


def test_root_pyproject_carries_the_canonical_description() -> None:
    """The PyPI package summary is exactly the canonical description."""
    assert _pyproject_description() == _CANONICAL_DESCRIPTION


def test_scoop_generator_carries_the_canonical_description() -> None:
    """The Scoop manifest generator embeds the canonical description verbatim."""
    literals = _string_literals(_REPO_ROOT / "packaging" / "scoop" / "generate.py")
    assert _CANONICAL_DESCRIPTION in literals


def test_homebrew_desc_is_the_canonical_leading_clause() -> None:
    """The terse Homebrew desc is the canonical description's leading clause."""
    literals = _string_literals(_REPO_ROOT / "packaging" / "homebrew" / "generate.py")
    assert any(f'desc "{_CANONICAL_HOMEBREW_DESC}"' in literal for literal in literals)
    # The terse Homebrew clause is the canonical sentence's capability phrase
    # (capitalised as a standalone desc), so it must appear within the full
    # canonical sentence — the two can never describe the product differently.
    assert _CANONICAL_HOMEBREW_DESC.lower() in _CANONICAL_DESCRIPTION.lower()
