"""Reviewability ratchet for the development registry modules.

The workbook-parity backend is the one dev module large enough to need a
ratchet. It carried one while it lived in the shipped registry package; the
move to ``dev/registry/parity/`` left the ratchet behind pointing at a path
that no longer exists, so it raised ``FileNotFoundError`` instead of measuring
anything. The ratchet belongs beside the module it reviews.

It does not live in ``test_workbook_parity.py`` next door: that module drives
LibreOffice and is marked ``external_tool``, so the default lane holds it out.
A line-count ratchet needs no external tool and would lose its teeth there.

The baseline is pinned to the module's exact current length, matching the
convention of the registry-package ratchet it descends from: slack is this
gate's failure mode, because a ceiling above actual is silent permission to
grow into the gap. Raising it is a reviewed decision whose reasoning belongs in
the commit that makes it. Read what a delta is made of first -- a module that
grew only by explaining itself has become easier to review, not harder.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WORKBOOK_PARITY_MODULE = Path(__file__).parent.parent / "parity" / "_workbook_parity.py"
_WORKBOOK_PARITY_MODULE_LINE_BASELINE = 1_399


def test_workbook_parity_module_does_not_grow_past_reviewed_baseline() -> None:
    assert _WORKBOOK_PARITY_MODULE.is_file(), (
        f"{_WORKBOOK_PARITY_MODULE} is missing: the ratchet is pointing at a moved or deleted module"
    )
    line_count = len(_WORKBOOK_PARITY_MODULE.read_text(encoding="utf-8").splitlines())

    assert line_count <= _WORKBOOK_PARITY_MODULE_LINE_BASELINE, (
        f"{_WORKBOOK_PARITY_MODULE.name}: {line_count} lines exceeds reviewed baseline "
        f"{_WORKBOOK_PARITY_MODULE_LINE_BASELINE}"
    )
