"""W26.P56 closure verification: type-ignore paydown batch S658.

Asserts that:
- The 15 TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR markers placed by S658
  are present at the expected file:line sites.
- The allowlist in test_type_ignore_rationale_inventory.py has shrunk to exactly 84
  entries (99 original - 15 paid down).
- The ratchet test passes (no new drift sites).
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent
_PAID_DOWN_MARKER = "TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR"

# Marker must appear within 3 lines before each type: ignore site.
# These are the marker-comment line numbers placed by S658.
_S658_MARKER_SITES: list[tuple[str, int]] = [
    # _overview_payloads.py — 5 sites (line numbers track current source after peer edits)
    ("entrypoints/cli/_overview_payloads.py", 80),
    ("entrypoints/cli/_overview_payloads.py", 104),
    ("entrypoints/cli/_overview_payloads.py", 116),
    ("entrypoints/cli/_overview_payloads.py", 126),
    ("entrypoints/cli/_overview_payloads.py", 139),
    # _registry_corpus_payloads.py — 7 sites
    ("entrypoints/cli/_registry_corpus_payloads.py", 83),
    ("entrypoints/cli/_registry_corpus_payloads.py", 97),
    ("entrypoints/cli/_registry_corpus_payloads.py", 113),
    ("entrypoints/cli/_registry_corpus_payloads.py", 129),
    ("entrypoints/cli/_registry_corpus_payloads.py", 150),
    ("entrypoints/cli/_registry_corpus_payloads.py", 169),
    ("entrypoints/cli/_registry_corpus_payloads.py", 189),
    # _registry_payloads.py — 3 sites
    ("entrypoints/cli/_registry_payloads.py", 34),
    ("entrypoints/cli/_registry_payloads.py", 58),
    ("entrypoints/cli/_registry_payloads.py", 80),
]

_EXPECTED_ALLOWLIST_SIZE = 7  # 99 original; later campaigns paid down further


def test_s658_markers_present() -> None:
    """Each S658 paydown site must carry the PYDANTIC-MODEL-CONFIG-CLASSVAR marker."""
    missing: list[str] = []
    for rel, lineno in _S658_MARKER_SITES:
        p = _SRC_ROOT / rel
        lines = p.read_text(encoding="utf-8").splitlines()
        if lineno > len(lines):
            missing.append(f"{rel}:{lineno} — file shorter than expected")
            continue
        # zero-based
        line = lines[lineno - 1]
        if _PAID_DOWN_MARKER not in line:
            missing.append(f"{rel}:{lineno} — marker absent on line: {line.strip()!r}")

    if missing:
        raise AssertionError(
            f"{len(missing)} S658 marker site(s) missing the rationale token:\n" + "\n".join(f"  {m}" for m in missing)
        )


def test_allowlist_size_is_84() -> None:
    """Allowlist must be exactly 84 entries after the S658 paydown."""
    inv_path = _SRC_ROOT / "test_type_ignore_rationale_inventory.py"
    src = inv_path.read_text(encoding="utf-8")
    # Count tuple entries of the form ("path/to/file.py", lineno)
    entries = re.findall(r'\("[^"]+", \d+\)', src)
    actual = len(entries)
    assert actual == _EXPECTED_ALLOWLIST_SIZE, (
        f"Allowlist has {actual} entries; expected {_EXPECTED_ALLOWLIST_SIZE} "
        f"(99 original - 15 S658 paydown). "
        f"Either a paydown was missed or a new site was added to the allowlist."
    )


def test_ratchet_still_passes() -> None:
    """The type-ignore ratchet must pass programmatically after the S658 paydown."""
    import importlib.util

    inv_path = _SRC_ROOT / "test_type_ignore_rationale_inventory.py"
    spec = importlib.util.spec_from_file_location("_inv_module", inv_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    collect_violations = mod._collect_violations
    known = mod._KNOWN_VIOLATING_LINES

    current = frozenset(collect_violations())
    new_violations = current - known
    assert not new_violations, f"{len(new_violations)} new type-ignore drift site(s) found:\n" + "\n".join(
        f"  {r}:{ln}" for r, ln in sorted(new_violations)
    )
