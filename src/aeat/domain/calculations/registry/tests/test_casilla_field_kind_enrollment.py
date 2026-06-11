"""Real-behavior enrollment test: every former bare-string CasillaFieldKind site
now uses the enum.  The test greps the affected source files for surviving bare
``"draft"`` / ``"binding"`` / ``"casilla"`` comparison or assignment patterns
and fails loudly if any are found.

Only comparison and model-copy assignment contexts are targeted; TOML fixture
strings and docstrings are not false-positives because they don't reach runtime
field.kind comparisons.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# ---------------------------------------------------------------------------
# Paths of the files that carried bare-string kind usages (contract).
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[6]

_AFFECTED_FILES: list[Path] = [
    _REPO_ROOT / "src/aeat/adapters/outbound/aeat/sede/_declarations.py",
    _REPO_ROOT / "src/aeat/domain/user_profile/_registry_contract.py",
    _REPO_ROOT / "src/aeat/application/filing/_export.py",
    _REPO_ROOT / "src/aeat/domain/calculations/registry/_export.py",
]

# Patterns that indicate a surviving bare-string comparison or assignment that
# should have been replaced with the CasillaFieldKind enum:
#   field.kind == "draft"
#   field.kind != "draft"
#   field.kind == "binding"
#   field.kind == "casilla"
#   case "draft":
#   case "binding":
#   case "casilla":
#   "kind": "draft"   (dict-literal assignment)
#   "kind": "binding"
#   "kind": "casilla"
#   kind="draft"      (keyword-argument)
#   kind="binding"
#   kind="casilla"

_BARE_PATTERNS: list[re.Pattern[str]] = [
    # Comparison operators
    re.compile(r"""\.kind\s*[!=]=\s*["'](draft|binding|casilla)["']"""),
    # match/case arms
    re.compile(r"""^\s*case\s+["'](draft|binding|casilla)["']\s*:""", re.MULTILINE),
    # dict-literal "kind" key assignment
    re.compile(r""""kind"\s*:\s*["'](draft|binding|casilla)["']"""),
    # keyword argument kind=
    re.compile(r"""\bkind\s*=\s*["'](draft|binding|casilla)["']"""),
]


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Return (line_number, line_text) pairs for every bare-string hit.

    Comment-only lines (stripped line starts with ``#``) are excluded because
    they carry doc text, not runtime comparisons.
    """
    hits: list[tuple[int, str]] = []
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue  # skip comment lines — only runtime expressions matter
        for pattern in _BARE_PATTERNS:
            if pattern.search(line):
                hits.append((lineno, line.rstrip()))
                break  # one hit per line is enough
    return hits


def test_no_bare_kind_strings_survive_in_affected_files() -> None:
    """Fail if any affected file still compares field.kind to a bare string."""
    failures: list[str] = []
    for path in _AFFECTED_FILES:
        assert path.exists(), f"Expected source file missing: {path}"
        hits = _scan_file(path)
        for lineno, line in hits:
            failures.append(f"{path.relative_to(_REPO_ROOT)}:{lineno}: {line}")

    if failures:
        joined = "\n  ".join(failures)
        raise AssertionError(
            f"Bare CasillaFieldKind string(s) still present in affected files:\n  {joined}\n"
            "Replace each with the corresponding CasillaFieldKind.<MEMBER> enum value.",
        )
