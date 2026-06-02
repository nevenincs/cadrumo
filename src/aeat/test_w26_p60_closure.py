"""W26.P60 closure verification: S672+S673 paydown + S674 hard-deferred markers.

Assertions
----------
1. S672 paydown: 3 allowlist entries removed (borrador_100:276, censo:337, conftest:15).
2. S673 paydown: 1 allowlist entry removed (_modelo.py:1575).
3. Allowlist size is exactly 7 (11 original - 3 S672 - 1 S673).
4. S674 hard-deferred: TYPE-IGNORE-RATIONALE-HARD-DEFERRED- marker present within 3
   lines of each of the 7 named sites.
5. The ratchet test itself passes (no new unguarded type: ignore sites).
"""

from __future__ import annotations

import os
import pathlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent
_HARD_DEFERRED_TOKEN = "TYPE-IGNORE-RATIONALE-HARD-DEFERRED-"
_CONTEXT = 3


def _lines(rel: str) -> list[str]:
    return (_SRC_ROOT / pathlib.Path(rel.replace("/", os.sep))).read_text(
        encoding="utf-8"
    ).splitlines()


def _marker_present_near(lines: list[str], lineno: int) -> bool:
    """Return True if HARD-DEFERRED token appears on lineno or within _CONTEXT lines above."""
    idx = lineno - 1  # 0-based
    window = lines[max(0, idx - _CONTEXT) : idx + 1]
    return any(_HARD_DEFERRED_TOKEN in line for line in window)


# ---------------------------------------------------------------------------
# S672 + S673 paydown assertions
# ---------------------------------------------------------------------------

def test_s672_borrador100_entry_removed() -> None:
    """borrador_100.py:276 must not be in the ratchet allowlist (marker added)."""
    from .test_type_ignore_rationale_inventory import _KNOWN_VIOLATING_LINES

    assert ("application/live/_borrador_100.py", 276) not in _KNOWN_VIOLATING_LINES, (
        "S672: borrador_100.py:276 still in allowlist; remove after adding OVERRIDE-COVARIANT-RETURN marker"
    )


def test_s672_censo_entry_removed() -> None:
    """censo.py:337 must not be in the ratchet allowlist (marker added)."""
    from .test_type_ignore_rationale_inventory import _KNOWN_VIOLATING_LINES

    assert ("application/live/_censo.py", 337) not in _KNOWN_VIOLATING_LINES, (
        "S672: censo.py:337 still in allowlist; remove after adding OVERRIDE-COVARIANT-RETURN marker"
    )


def test_s672_conftest_entry_removed() -> None:
    """conftest.py:15 type: ignore must be gone and entry removed from allowlist."""
    from .test_type_ignore_rationale_inventory import _KNOWN_VIOLATING_LINES

    assert ("domain/calculations/registry/conftest.py", 15) not in _KNOWN_VIOLATING_LINES, (
        "S672: conftest.py:15 still in allowlist; remove after erasing the type: ignore"
    )
    # Confirm no type: ignore remains at that file
    lines = _lines("domain/calculations/registry/conftest.py")
    for line in lines:
        assert "type: ignore" not in line, (
            f"conftest.py still contains a type: ignore: {line!r}"
        )


def test_s673_modelo_entry_removed() -> None:
    """_modelo.py:1575 must not be in the ratchet allowlist (definition annotated)."""
    from .test_type_ignore_rationale_inventory import _KNOWN_VIOLATING_LINES

    assert ("entrypoints/cli/_modelo.py", 1575) not in _KNOWN_VIOLATING_LINES, (
        "S673: _modelo.py:1575 still in allowlist; remove after annotating definition param"
    )


def test_allowlist_size_is_7() -> None:
    """Allowlist must be exactly 7 after S672 (3 removed) and S673 (1 removed)."""
    from .test_type_ignore_rationale_inventory import _KNOWN_VIOLATING_LINES

    size = len(_KNOWN_VIOLATING_LINES)
    assert size == 7, (
        f"Expected allowlist size 7 (11 original - 3 S672 - 1 S673); got {size}. "
        f"Entries: {sorted(_KNOWN_VIOLATING_LINES)}"
    )


# ---------------------------------------------------------------------------
# S674 hard-deferred marker presence assertions
# ---------------------------------------------------------------------------

def test_s674_snapshot_base_marker() -> None:
    """_snapshot_base.py line 512 (Envelope specialization) carries HARD-DEFERRED marker."""
    lines = _lines("application/live/_snapshot_base.py")
    # The type: ignore is on the Envelope[self._payload_model] line
    type_ignore_lineno = next(
        i + 1
        for i, line in enumerate(lines)
        if "Envelope[self._payload_model]" in line and "type: ignore" in line
    )
    assert _marker_present_near(lines, type_ignore_lineno), (
        f"_snapshot_base.py:{type_ignore_lineno}: missing HARD-DEFERRED marker within {_CONTEXT} lines"
    )


@pytest.mark.parametrize(
    "snippet",
    [
        "profile=profile",
        "return draft",
        "walk_expedientes_tree",
        "fetch_notifications_query",
    ],
)
def test_s674_adapters_markers(snippet: str) -> None:
    """Each _adapters.py type: ignore site carries a HARD-DEFERRED marker."""
    lines = _lines("application/workflow/_adapters.py")
    matching = [
        i + 1
        for i, line in enumerate(lines)
        if snippet in line and ("type: ignore" in line or _HARD_DEFERRED_TOKEN in line)
    ]
    assert matching, f"_adapters.py: no line found containing {snippet!r}"
    # Find the type: ignore line (may be on same line or following line)
    for lineno in matching:
        window_start = max(0, lineno - 1 - _CONTEXT)
        window = lines[window_start : lineno]
        if any(_HARD_DEFERRED_TOKEN in l for l in window):
            return
        # Also check the line itself
        if _HARD_DEFERRED_TOKEN in lines[lineno - 1]:
            return
    raise AssertionError(
        f"_adapters.py: HARD-DEFERRED marker missing near lines containing {snippet!r} "
        f"(found at lines {matching})"
    )


def test_s674_event_marker() -> None:
    """_event.py __iter__ override carries HARD-DEFERRED marker."""
    lines = _lines("domain/buckets/_event.py")
    type_ignore_lineno = next(
        i + 1
        for i, line in enumerate(lines)
        if "__iter__" in line and "type: ignore" in line
    )
    assert _marker_present_near(lines, type_ignore_lineno), (
        f"_event.py:{type_ignore_lineno}: missing HARD-DEFERRED marker within {_CONTEXT} lines"
    )


def test_s674_app_live_marker() -> None:
    """_app_live.py _borrador_row splat carries HARD-DEFERRED marker."""
    lines = _lines("entrypoints/cli/_app_live.py")
    type_ignore_lineno = next(
        i + 1
        for i, line in enumerate(lines)
        if "_borrador_row(record)" in line and "type: ignore" in line
    )
    assert _marker_present_near(lines, type_ignore_lineno), (
        f"_app_live.py:{type_ignore_lineno}: missing HARD-DEFERRED marker within {_CONTEXT} lines"
    )


# ---------------------------------------------------------------------------
# Ratchet green-pass assertion
# ---------------------------------------------------------------------------

def test_ratchet_passes() -> None:
    """The main ratchet test must report zero new violations."""
    from .test_type_ignore_rationale_inventory import _KNOWN_VIOLATING_LINES, _collect_violations

    current = frozenset(_collect_violations())
    new_violations = current - _KNOWN_VIOLATING_LINES
    assert not new_violations, (
        f"{len(new_violations)} unguarded type: ignore site(s) outside the allowlist: "
        + ", ".join(f"{r}:{n}" for r, n in sorted(new_violations))
    )
