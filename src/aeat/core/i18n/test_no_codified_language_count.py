"""Lock the "no codified language count" rule in CI.

The supported language set is owned by :class:`aeat.core.i18n.Language`
and is open-ended. Identifiers that bake in a specific count
(``trilingual``, ``quadlingual``, ``bilingual``, ``two_lingual``,
``three_lingual`` …) become brittle every time the enum gains or
loses a code. This test scans the source tree and fails fast if
anyone re-introduces a count token.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


# Project root resolves to the repo root regardless of where pytest is invoked.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SRC_ROOT = _REPO_ROOT / "src"
_TESTS_ROOT = _REPO_ROOT / "tests"

# Forbidden tokens — match counts encoded as "(count)lingual" or
# "(count)_lingual", both standalone words and word-internal.
_FORBIDDEN_RE = re.compile(
    r"\b(?:bi|tri|quad|penta|hexa|two|three|four|five|six|seven|eight)_?lingual\b",
    re.IGNORECASE,
)


_SELF = Path(__file__).resolve()


def _iter_source_files() -> list[Path]:
    files: list[Path] = []
    for root in (_SRC_ROOT, _TESTS_ROOT):
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            if path.resolve() == _SELF:
                # The test itself spells out the forbidden tokens to
                # match against; exempt it from the self-scan.
                continue
            files.append(path)
    return files


_VAULT_PATH_RE = re.compile(r"\.vault/[\w./-]+")


def test_no_codified_language_count_in_python_sources() -> None:
    """No Python source under ``src/`` or ``tests/`` may carry a count-coded "lingual" token.

    The neutral term is "multilingual"; per-language behaviour comes
    from iterating :class:`Language`. Use this rule when refactoring:
    if a function name or docstring spelled the count, rename it.

    Matches that fall inside a ``.vault/`` file-path reference are
    ignored — the vault asset filenames are owned by ``vaultspec``
    and rename via the vault CLI, not by source-tree edits.
    """
    failures: list[str] = []
    for path in _iter_source_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        # Mask out .vault/... path references so a comment referring
        # to a vault filename doesn't trip the rule.
        scrubbed = _VAULT_PATH_RE.sub(lambda m: "_" * len(m.group(0)), text)
        for match in _FORBIDDEN_RE.finditer(scrubbed):
            line_no = text.count("\n", 0, match.start()) + 1
            failures.append(f"{path.relative_to(_REPO_ROOT)}:{line_no}: {match.group(0)!r}")
    if failures:
        pytest.fail(
            "Codified language counts detected in Python sources (use 'multilingual'):\n"
            + "\n".join(f" - {f}" for f in failures)
        )
