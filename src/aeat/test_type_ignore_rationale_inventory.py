"""Inventory ratchet: every ``# type: ignore`` in production code must carry a rationale marker.

Rule
----
Every ``# type: ignore`` (with or without an ``[error-code]`` suffix) in a
non-test production module under ``src/aeat/`` must carry one of the following
marker token prefixes either INLINE on the same line OR within 3 lines
immediately preceding:

- ``TYPE-IGNORE-RATIONALE-``  — primary marker for type-system suppression
- ``CAST-RATIONALE-``         — W6/W18 cast escape-hatch markers (covers type-ignore semantically)
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
``_KNOWN_VIOLATING_LINES`` for paydown in a subsequent wave.

Structural prevention (W26.P55)
---------------------------------
This test AST-free line-walks **all** production Python files under ``src/aeat/``
(excluding test files: names starting with ``test_`` or ending with ``_test.py``).
For each ``# type: ignore`` line, it checks the same line and up to 3 preceding
lines for any of the recognised marker token prefixes.

If no marker is found, the site is recorded as ``(relative-posix-path, line-number)``.

The ratchet records the 99 pre-existing sites found at W26.P55 authoring time.
New sites must either carry a rationale marker or be accompanied by a ratchet
expansion PR with a documented reason.

Paydown
-------
To clean up a known-violating site:
1. Add a ``# TYPE-IGNORE-RATIONALE-<SLUG>: <one-line reason>`` comment on the
   ``# type: ignore`` line or in the 3 lines immediately above.
2. Remove the ``(path, lineno)`` entry from ``_KNOWN_VIOLATING_LINES``.
3. The test will then permanently lock that site at zero.
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent

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

# How many lines before the ``# type: ignore`` line are inspected for markers.
_CONTEXT_LINES = 3

_TYPE_IGNORE_RE = re.compile(r"#\s*type:\s*ignore")

# ---------------------------------------------------------------------------
# Known pre-existing violating sites (W26.P55 backlog — 99 sites).
# Each entry is (relative-posix-path-from-src/aeat/, 1-based line number).
# DO NOT add new sites — add a rationale marker instead.
# Remove an entry after adding its marker to lock that site at zero.
# ---------------------------------------------------------------------------
_KNOWN_VIOLATING_LINES: frozenset[tuple[str, int]] = frozenset(
    {
        ("adapters/inbound/declaracion/_parser.py", 519),
        ("adapters/outbound/aeat/sede/_renta_web_open.py", 158),
        ("adapters/outbound/aeat/sede/_renta_web_open.py", 194),
        ("adapters/outbound/aeat/sede/_renta_web_open.py", 218),
        ("adapters/persistence/storage/envelope/_envelope.py", 158),
        ("application/auth/_sessions.py", 68),
        ("application/auth/_sessions.py", 69),
        ("application/calculations/_iva_wallet_reconciliation.py", 196),
        ("application/diagnostics.py", 307),
        ("application/diagnostics.py", 354),
        ("application/invoices/_importing.py", 126),
        ("application/invoices/_importing.py", 128),
        ("application/invoices/_importing.py", 132),
        ("application/ledger/_actions.py", 2252),
        ("application/ledger/_actions.py", 2267),
        ("application/live/_borrador_100.py", 276),
        ("application/live/_censo.py", 337),
        ("application/live/_snapshot_base.py", 511),
        ("application/modelo/_actions.py", 3216),
        ("application/modelo/_actions.py", 3238),
        ("application/repair_integrity.py", 219),
        ("application/repair_integrity.py", 227),
        ("application/workflow/_adapters.py", 105),
        ("application/workflow/_adapters.py", 110),
        ("application/workflow/_adapters.py", 144),
        ("application/workflow/_adapters.py", 151),
        ("diagnostics/_identity_placement.py", 1028),
        ("domain/buckets/_event.py", 307),
        ("domain/calculations/registry/_loader.py", 109),
        ("domain/calculations/registry/_schema.py", 1385),
        ("domain/calculations/registry/_schema.py", 1397),
        ("domain/calculations/registry/conftest.py", 15),
        ("domain/profile/_descendant_facts.py", 207),
        ("entrypoints/cli/_app_live.py", 1062),
        ("entrypoints/cli/_app_live.py", 1088),
        ("entrypoints/cli/_app_live.py", 1176),
        ("entrypoints/cli/_app_live.py", 1362),
        ("entrypoints/cli/_app_live.py", 1392),
        ("entrypoints/cli/_app_live.py", 1456),
        ("entrypoints/cli/_app_live.py", 1509),
        ("entrypoints/cli/_app_live.py", 1561),
        ("entrypoints/cli/_app_live.py", 1637),
        ("entrypoints/cli/_app_live.py", 1681),
        ("entrypoints/cli/_config/_google_payloads.py", 214),
        ("entrypoints/cli/_config/_profile_census_payloads.py", 47),
        ("entrypoints/cli/_config/_profile_census_payloads.py", 57),
        ("entrypoints/cli/_config_payloads.py", 277),
        ("entrypoints/cli/_config_payloads.py", 288),
        ("entrypoints/cli/_config_payloads.py", 299),
        ("entrypoints/cli/_config_payloads.py", 412),
        ("entrypoints/cli/_config_payloads.py", 434),
        ("entrypoints/cli/_config_payloads.py", 446),
        ("entrypoints/cli/_config_payloads.py", 498),
        ("entrypoints/cli/_config_payloads.py", 528),
        ("entrypoints/cli/_doc_reference.py", 90),
        ("entrypoints/cli/_doc_reference.py", 104),
        ("entrypoints/cli/_doc_reference.py", 167),
        ("entrypoints/cli/_doc_reference.py", 168),
        ("entrypoints/cli/_doc_reference.py", 199),
        ("entrypoints/cli/_doc_reference.py", 263),
        ("entrypoints/cli/_doc_reference.py", 291),
        ("entrypoints/cli/_doc_reference.py", 348),
        ("entrypoints/cli/_doc_reference.py", 526),
        ("entrypoints/cli/_modelo.py", 892),
        ("entrypoints/cli/_modelo.py", 894),
        ("entrypoints/cli/_modelo.py", 896),
        ("entrypoints/cli/_modelo.py", 915),
        ("entrypoints/cli/_modelo.py", 1573),
        ("entrypoints/cli/_modelo.py", 3112),
        ("entrypoints/cli/_modelo.py", 3113),
        ("entrypoints/cli/_modelo.py", 3114),
        ("entrypoints/cli/_modelo.py", 3150),
        ("entrypoints/cli/_modelo.py", 3151),
        ("entrypoints/cli/_modelo.py", 3152),
        ("entrypoints/cli/_modelo.py", 5780),
        ("entrypoints/cli/_modelo.py", 5781),
        ("entrypoints/cli/_modelo.py", 5782),
        ("entrypoints/cli/_registry_payloads.py", 90),
        ("entrypoints/cli/_registry_payloads.py", 109),
        ("entrypoints/cli/_registry_payloads.py", 126),
        ("entrypoints/cli/_registry_payloads.py", 142),
        ("entrypoints/cli/_root_payloads.py", 26),
        ("entrypoints/cli/_root_payloads.py", 33),
        ("entrypoints/cli/_stdio.py", 142),
    }
)


def _collect_violations() -> list[tuple[str, int]]:
    """Walk all production files; return (rel_path, lineno) pairs lacking markers."""
    violations: list[tuple[str, int]] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        name = path.name
        if name.startswith("test_") or name.endswith("_test.py"):
            continue
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
            if any(
                any(m in prev for m in _MARKER_TOKENS) for prev in lines[start:i]
            ):
                continue
            rel = path.relative_to(_SRC_ROOT).as_posix()
            violations.append((rel, lineno))
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
        lines = "\n  ".join(
            f"{rel}:{lineno}" for rel, lineno in sorted(new_violations)
        )
        raise AssertionError(
            f"{len(new_violations)} new type-ignore drift site(s) found without a rationale marker:\n"
            f"  {lines}\n\n"
            "Add one of the following marker tokens on the # type: ignore line or in the 3 lines above:\n"
            "  # TYPE-IGNORE-RATIONALE-<LABEL>: <reason>\n"
            "  # CAST-RATIONALE-<LABEL>: <reason>  (if a cast escape)\n"
            "  # ANY-RETURN-RATIONALE-<LABEL>: <reason>  (if a return-type escape)\n"
            "Do NOT add to _KNOWN_VIOLATING_LINES — add a marker instead.\n"
            f"Ratchet holds {len(_KNOWN_VIOLATING_LINES)} pre-existing sites for paydown."
        )
