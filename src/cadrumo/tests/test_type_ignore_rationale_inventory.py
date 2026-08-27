"""Inventory ratchet: every ``# type: ignore`` in production code must carry a rationale marker.

Rule
----
Every ``# type: ignore`` (with or without an ``[error-code]`` suffix) in a
non-test production module under ``src/cadrumo/`` must carry one of the following
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
This test AST-free line-walks **all** production Python files under ``src/cadrumo/``
(excluding test files: names starting with ``test_`` or ending with ``_test.py``).
For each ``# type: ignore`` line, it checks the same line and up to 3 preceding
lines for any of the recognised marker token prefixes.

If no marker is found, the site is recorded as ``(relative-posix-path, line-number)``.

The ratchet opened at the 99 pre-existing sites found when it was written and is
now empty: every suppression in the tree carries a rationale marker. New sites
must carry one too.

The enrolled set is asserted in BOTH directions. Subtracting it from the live
violations catches a new unmarked suppression; requiring every enrolled pair to
still BE a live violation catches the opposite drift, where a site is fixed or
moved and its entry stays behind as an exemption on a line number that now holds
something else.

Paydown
-------
To clean up a known-violating site:
1. Add a ``# TYPE-IGNORE-RATIONALE-<SLUG>: <one-line reason>`` comment on the
   ``# type: ignore`` line or in the 3 lines immediately above.
2. Remove the ``(path, lineno)`` entry from ``_KNOWN_VIOLATING_LINES``.
3. The test will then permanently lock that site at zero.

See Also:
    :func:`~tests._inventory.production_python_files`
        Shared production-file inventory walked by this suppression ratchet.
    :mod:`~tests.test_cast_rationale_inventory`
        Companion typed-boundary guard whose ``CAST-RATIONALE-*`` markers also
        satisfy historical type-ignore escape sites.
    :mod:`~tests.test_any_param_rationale_inventory`
        Parameter-level ``Any`` rationale ratchet mirroring the same
        enrollment pattern for parameter-level type escapes.

The type-ignore corpus paid down from 99 enrolled sites to zero; every
suppression in production must now carry a rationale marker.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

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
# Known pre-existing violating sites. The backlog opened at 99 and is now zero:
# every suppression in the tree carries a rationale marker.
#
# Each entry is (relative-posix-path-from-src/cadrumo/, 1-based line number).
# An entry here is a licence to leave one exact line unmarked, so the set is
# asserted in BOTH directions. Enrolling a site that is not a real unmarked
# suppression is what turns a paid-down backlog into a standing exemption at a
# line number that has since drifted onto unrelated code.
#
# DO NOT add new sites — add a rationale marker instead.
# ---------------------------------------------------------------------------
_KNOWN_VIOLATING_LINES: frozenset[tuple[str, int]] = frozenset[tuple[str, int]]()


def _unmarked_type_ignore_linenos(lines: Sequence[str]) -> list[int]:
    """Return 1-based line numbers of suppressions carrying no rationale marker.

    A marker counts when it sits on the suppression's own line or anywhere in
    the ``_CONTEXT_LINES`` immediately above it.
    """
    found: list[int] = []
    for i, line in enumerate(lines):
        if not _TYPE_IGNORE_RE.search(line):
            continue
        if any(m in line for m in _MARKER_TOKENS):
            continue
        start = max(0, i - _CONTEXT_LINES)
        if any(any(m in prev for m in _MARKER_TOKENS) for prev in lines[start:i]):
            continue
        found.append(i + 1)
    return found


def _collect_violations() -> list[tuple[str, int]]:
    """Walk all production files; return (rel_path, lineno) pairs lacking markers."""
    violations: list[tuple[str, int]] = []
    for path in production_python_files():
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        violations.extend(
            (aeat_relative(path), lineno) for lineno in _unmarked_type_ignore_linenos(source.splitlines())
        )
    return violations


def test_no_new_type_ignore_without_rationale() -> None:
    """New ``# type: ignore`` annotations must carry an inline rationale marker.

    This test uses a ratchet against ``_KNOWN_VIOLATING_LINES``:

    - Sites already in the ratchet are skipped (tracked for paydown).
    - Any site NOT in the ratchet must have a rationale marker on the same line
      or in the 3 lines immediately above.
    - New files or new suppressions are automatically
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


def test_ratchet_holds_no_entry_that_has_stopped_describing_a_violation() -> None:
    """Every enrolled site must still be a real unmarked suppression.

    The ratchet only ever subtracted its enrolled set from the live one, so an
    entry survived being fixed, moved, or deleted. All seven that were enrolled
    here had stopped describing anything: the backlog was fully paid down while
    the entries stayed, pointing at a blank line, at unrelated code, and in one
    case past the end of its file. That is not cosmetic. An enrolled pair is a
    licence to leave one exact line unmarked, so a stale entry is a standing
    exemption waiting for a new suppression to drift onto its line number.
    """
    stale = sorted(_KNOWN_VIOLATING_LINES - frozenset(_collect_violations()))

    assert not stale, (
        f"{len(stale)} ratchet entr(ies) no longer describe an unmarked suppression "
        "(the site was fixed, moved, or removed). Delete them: while enrolled they "
        "exempt whatever now occupies that line:\n  " + "\n  ".join(f"{rel}:{lineno}" for rel, lineno in stale)
    )


def test_scan_reads_a_non_empty_corpus() -> None:
    """A ratchet over zero files reports a clean tree without inspecting one."""
    files = production_python_files()
    assert len(files) > 500, f"expected the production corpus, scanned only {len(files)} files"


def test_suppression_pattern_discriminates() -> None:
    """Positive control: the pattern finds real suppressions and rejects prose.

    Asserted against the compiled pattern directly. A pattern that stopped
    matching would empty the violation list, and an empty list is precisely what
    the compliant tree this ratchet guards also produces.
    """
    token = "# type: " + "ignore"
    must_match = (f"value = untyped()  {token}", f"value = untyped()  {token}[attr-defined]", "x = y  #type:ignore")
    must_not_match = ("# the type is ignored downstream", "# typed: ignore", 'note = "type ignore"')

    for probe in must_match:
        assert _TYPE_IGNORE_RE.search(probe), f"pattern failed to match a real suppression: {probe!r}"
    for probe in must_not_match:
        assert not _TYPE_IGNORE_RE.search(probe), f"pattern wrongly matched prose: {probe!r}"


def test_detector_reports_an_unmarked_suppression_and_clears_a_marked_one() -> None:
    """The walk flags an unmarked suppression and honours both marker positions.

    Exercised over synthetic source so the control proves the detector fires
    rather than proving the tree is currently clean — the two are
    indistinguishable from the violation list alone.
    """
    token = "# type: " + "ignore"
    marker = "TYPE-IGNORE-RATIONALE-" + "PROBE"

    unmarked = [f"value = untyped()  {token}"]
    inline_marked = [f"value = untyped()  {token}  # {marker}: third-party stub gap"]
    block_marked = [f"# {marker}: third-party stub gap", "", f"value = untyped()  {token}"]
    out_of_range = [f"# {marker}: too far above", "", "", "", f"value = untyped()  {token}"]

    assert _unmarked_type_ignore_linenos(unmarked) == [1]
    assert _unmarked_type_ignore_linenos(inline_marked) == []
    assert _unmarked_type_ignore_linenos(block_marked) == []
    # The context window is bounded, so a marker beyond it must not launder the site.
    assert _unmarked_type_ignore_linenos(out_of_range) == [5]
