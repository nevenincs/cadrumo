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

from ..._paths import REPO_ROOT

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


def _manifest_description(source_path: Path) -> str | None:
    """The value the generator BINDS to the manifest's own ``description`` key.

    Read from the emitted mapping rather than from the module's literals. A
    membership test over every string in the module is satisfied by the
    canonical sentence sitting anywhere at all - a docstring, a note, an
    argparse help string - so it stays green while the key the manifest is
    actually published under is renamed away. Only the binding decides what
    Scoop shows.

    ``None`` means the module binds no single such key, which is a failure to
    report rather than a description to compare.
    """
    bound = [
        value
        for node in ast.walk(ast.parse(source_path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values, strict=True)
        if isinstance(key, ast.Constant) and key.value == "description"
    ]
    if len(bound) != 1:
        return None
    single = bound[0]
    return single.value if isinstance(single, ast.Constant) and isinstance(single.value, str) else None


def test_root_pyproject_carries_the_canonical_description() -> None:
    """The PyPI package summary is exactly the canonical description."""
    assert _pyproject_description() == _CANONICAL_DESCRIPTION


def test_scoop_generator_carries_the_canonical_description() -> None:
    """The Scoop manifest's own ``description`` value IS the canonical sentence.

    Equality against the emitted binding, not membership in the module's
    literals. The published manifest shows the value bound to this key; the
    same sentence present elsewhere in the file is not the one Scoop reads.
    """
    described = _manifest_description(_REPO_ROOT / "packaging" / "scoop" / "generate.py")

    assert described is not None, "the Scoop generator binds no single `description` key to compare"
    assert described == _CANONICAL_DESCRIPTION


def test_a_renamed_description_key_is_refused(tmp_path: Path) -> None:
    """Teeth: the shape the retired membership test could not see.

    The generator keeps the canonical sentence verbatim and publishes it under
    a different key, so the manifest ships with no description at all. Both
    halves are asserted here: the retired form passes on this file, and the
    reader that replaced it reports nothing to compare.
    """
    source = tmp_path / "generate.py"
    source.write_text(
        f'def manifest() -> dict[str, object]:\n    return {{"summary": "{_CANONICAL_DESCRIPTION}"}}\n',
        encoding="utf-8",
    )

    assert _CANONICAL_DESCRIPTION in _string_literals(source)
    assert _manifest_description(source) is None


def test_homebrew_desc_is_the_canonical_leading_clause() -> None:
    """The terse Homebrew desc is the canonical description's leading clause."""
    literals = _string_literals(_REPO_ROOT / "packaging" / "homebrew" / "generate.py")
    assert any(f'desc "{_CANONICAL_HOMEBREW_DESC}"' in literal for literal in literals)
    # The terse Homebrew clause is the canonical sentence's capability phrase
    # (capitalised as a standalone desc), so it must appear within the full
    # canonical sentence — the two can never describe the product differently.
    assert _CANONICAL_HOMEBREW_DESC.lower() in _CANONICAL_DESCRIPTION.lower()
