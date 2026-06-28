"""Inventory ratchet: every ``# type: ignore`` in production code must carry a rationale marker.

Rule
----
Every ``# type: ignore`` (with or without an ``[error-code]`` suffix) in a
non-test production module under ``src/aeat/`` must carry one of the following
marker token prefixes either INLINE on the same line OR within 3 lines
immediately preceding:

- ``TYPE-IGNORE-RATIONALE-``  — primary marker for type-system suppression
- ``CAST-RATIONALE-``         — historical cast escape-hatch markers
  (covers type-ignore semantically)
- ``ANY-RETURN-RATIONALE-``   — return-type escape markers
- ``KWARGS-ANY-RATIONALE-``   — kwargs/param Any escape markers
- ``ADAPTER-INTERNAL-ALIAS-RATIONALE-``  — third-party untyped resource aliases
- ``BROAD-EXCEPT-RATIONALE-``     — broad-except escape markers
- ``LOGGING-STDLIB-RATIONALE-``   — stdlib logging integration markers
- ``MACHINE-FORMAT-RATIONALE-``   — machine-format escape markers
- ``ALT-FINGERPRINT-RATIONALE-``  — alternate fingerprint algorithm markers

Convention (G7 standing review gate)
--------------------------------------
Every ``# type: ignore`` in production code must carry a
``TYPE-IGNORE-RATIONALE-<scope>`` token within 3 lines, or be enrolled in
``_KNOWN_VIOLATING_LINES`` for direct follow-up remediation.

Structural prevention (ratchet history)
---------------------------------
This test AST-free line-walks **all** production Python files under ``src/aeat/``
(excluding test files: names starting with ``test_`` or ending with ``_test.py``).
For each ``# type: ignore`` line, it checks the same line and up to 3 preceding
lines for any of the recognised marker token prefixes.

If no marker is found, the site is recorded as ``(relative-posix-path, line-number)``.

The ratchet records the 99 pre-existing sites found at ratchet history authoring time.
New sites must either carry a rationale marker or be accompanied by a ratchet
expansion with a documented reason.

Paydown
-------
To clean up a known-violating site:
1. Add a ``# TYPE-IGNORE-RATIONALE-<SLUG>: <one-line reason>`` comment on the
   ``# type: ignore`` line or in the 3 lines immediately above.
2. Remove the ``(path, lineno)`` entry from ``_KNOWN_VIOLATING_LINES``.
3. The test will then permanently lock that site at zero.
"""

from __future__ import annotations

import re

import pytest

from ._inventory import aeat_relative, production_python_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Recognised rationale marker token prefixes (any one satisfies the rule).
_MARKER_TOKENS: tuple[str, ...] = (
    "TYPE-IGNORE-RATIONALE-",
    "CAST-RATIONALE-",
    "ANY-RETURN-RATIONALE-",
    "KWARGS-ANY-RATIONALE-",
    "ADAPTER-INTERNAL-ALIAS-RATIONALE-",
    "BROAD-EXCEPT-RATIONALE-",
    "LOGGING-STDLIB-RATIONALE-",
    "MACHINE-FORMAT-RATIONALE-",
    "ALT-FINGERPRINT-RATIONALE-",
)

# How many lines before the type-ignore line are inspected for markers.
_CONTEXT_LINES = 3

_TYPE_IGNORE_RE = re.compile(r"#\s*type:\s*ignore")

# ---------------------------------------------------------------------------
# Known pre-existing violating sites (ratchet history backlog — 99 sites).
# Each entry is (relative-posix-path-from-src/aeat/, 1-based line number).
# DO NOT add new sites — add a rationale marker instead.
# Remove an entry after adding its marker to lock that site at zero.
# ---------------------------------------------------------------------------
_KNOWN_VIOLATING_LINES: frozenset[tuple[str, int]] = frozenset(
    {
        # Historical paydowns removed 28 entries, then 3 entries, then
        # 1 entry; 7 remain.
        ("application/live/_snapshot_base.py", 511),
        ("application/workflow/_adapters.py", 105),
        ("application/workflow/_adapters.py", 110),
        ("application/workflow/_adapters.py", 144),
        ("application/workflow/_adapters.py", 151),
        ("domain/buckets/_event.py", 307),
        ("entrypoints/cli/_app_live.py", 1681),
    },
)


def _collect_violations() -> list[tuple[str, int]]:
    """Walk all production files; return (rel_path, lineno) pairs lacking markers."""
    violations: list[tuple[str, int]] = []
    for path in production_python_files():
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if not _TYPE_IGNORE_RE.search(line):
                continue
            lineno = i + 1  # 1-based
            # Check inline on the same line first.
            if any(m in line for m in _MARKER_TOKENS):
                continue
            # Check up to _CONTEXT_LINES preceding lines.
            start = max(0, i - _CONTEXT_LINES)
            if any(any(m in prev for m in _MARKER_TOKENS) for prev in lines[start:i]):
                continue
            violations.append((aeat_relative(path), lineno))
    return violations


def test_no_new_type_ignore_without_rationale() -> None:
    """New ``# type: ignore`` annotations must carry an inline rationale marker.

    This test uses a ratchet against ``_KNOWN_VIOLATING_LINES``:

    - Sites already in the ratchet are skipped (tracked for paydown).
    - Any site NOT in the ratchet must have a rationale marker on the same line
      or in the 3 lines immediately above.
    - New files or new suppressions added by any campaign are automatically
      covered — no exclusion registration required.

    To remediate a known-violating site: add a marker comment (preferred) or
    resolve the underlying type error, then remove the entry from
    ``_KNOWN_VIOLATING_LINES``.  The test will then lock that site at zero.

    Accepted marker token prefixes (any one is sufficient):
      TYPE-IGNORE-RATIONALE-<LABEL>
      CAST-RATIONALE-<LABEL>
      ANY-RETURN-RATIONALE-<LABEL>
      KWARGS-ANY-RATIONALE-<LABEL>
      ADAPTER-INTERNAL-ALIAS-RATIONALE-<LABEL>
      BROAD-EXCEPT-RATIONALE-<LABEL>
      LOGGING-STDLIB-RATIONALE-<LABEL>
      MACHINE-FORMAT-RATIONALE-<LABEL>
      ALT-FINGERPRINT-RATIONALE-<LABEL>
    """
    current_violations = frozenset(_collect_violations())
    new_violations = current_violations - _KNOWN_VIOLATING_LINES

    if new_violations:
        lines = "\n  ".join(f"{rel}:{lineno}" for rel, lineno in sorted(new_violations))
        raise AssertionError(
            f"{len(new_violations)} new type-ignore drift site(s) found without a rationale marker:\n"
            f"  {lines}\n\n"
            "Add one of the following marker tokens on the # type: ignore line or in the 3 lines above:\n"
            "  # TYPE-IGNORE-RATIONALE-<LABEL>: <reason>\n"
            "  # CAST-RATIONALE-<LABEL>: <reason>  (if a cast escape)\n"
            "  # ANY-RETURN-RATIONALE-<LABEL>: <reason>  (if a return-type escape)\n"
            "Do NOT add to _KNOWN_VIOLATING_LINES — add a marker instead.\n"
            f"Ratchet holds {len(_KNOWN_VIOLATING_LINES)} pre-existing sites for paydown.",
        )
