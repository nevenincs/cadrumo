"""Tests for the lazy re-export verification gate.

`dev.quality.module_test_reach` listed `dev/quality/shims.py` as unreached. It
backs ``just verify-shims`` and answers one question: do the public names a
re-export surface promises actually resolve?

It reported nine modules verified while asserting something about one. Measured
against the live tree, eight of the nine declared modules had an EMPTY
``__all__`` - the package-inertness work emptied those initialisers, as the
architecture requires - and an empty ``__all__`` iterates no names, so each
contributed no assertion and the run still printed nine. A module with no
surface left is a stale declaration, not a passing one.

The predicate is driven over constructed module objects rather than over the
live tree. That is deliberate: a case pinned to whichever packages currently
carry a surface would fail as soon as the inertness work reaches another one,
which is the direction this project is moving.
"""

from __future__ import annotations

import types

import pytest

from ..shims import _LAZY_REEXPORT_MODULES, _module_failures, main

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _module(name: str, **attributes: object) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def _failures_for(module: types.ModuleType, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Run the real predicate against a constructed module registered by name."""
    import sys

    monkeypatch.setitem(sys.modules, module.__name__, module)
    return _module_failures(module.__name__)


def test_a_surface_whose_names_resolve_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The supported case: every promised name is reachable."""
    module = _module("constructed.resolving", __all__=["Alpha", "Bravo"], Alpha=1, Bravo=2)

    assert _failures_for(module, monkeypatch) == []


def test_an_empty_surface_is_reported_as_a_stale_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The defect: this iterated no names and counted as a verified module.

    Eight of nine declared modules were in exactly this state, so the gate's
    headline number was eight parts claim and one part measurement.
    """
    module = _module("constructed.emptied", __all__=[])

    failures = _failures_for(module, monkeypatch)

    assert failures
    assert "asserts nothing" in failures[0]


def test_a_missing_all_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """A module with no ``__all__`` promises nothing and cannot be verified."""
    module = _module("constructed.silent")

    assert "missing __all__" in _failures_for(module, monkeypatch)[0]


def test_a_name_that_does_not_resolve_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """The failure the gate exists for: a promise the package cannot keep."""
    module = _module("constructed.broken", __all__=["Present", "Absent"], Present=1)

    failures = _failures_for(module, monkeypatch)

    assert len(failures) == 1
    assert "Absent" in failures[0]


def test_a_non_string_member_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """``__all__`` is a list of names; anything else is a malformed declaration."""
    module = _module("constructed.malformed", __all__=["Fine", 7], Fine=1)

    failures = _failures_for(module, monkeypatch)

    assert any("non-string" in failure for failure in failures)


def test_a_string_all_is_rejected_rather_than_iterated_by_character(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare string is iterable, so without the guard each CHARACTER became a name."""
    module = _module("constructed.stringy", __all__="Alpha")

    assert "not an iterable of names" in _failures_for(module, monkeypatch)[0]


def test_a_module_that_cannot_be_imported_is_a_finding_not_a_traceback() -> None:
    """A retired or renamed declaration must name itself.

    The import was unguarded, so a module removed from the tree ended the gate
    in a traceback rather than a line saying which declaration had gone stale.
    """
    failures = _module_failures("cadrumo.a_module_that_was_never_published")

    assert len(failures) == 1
    assert "cannot be imported" in failures[0]


def test_the_declared_list_still_names_a_live_surface() -> None:
    """The list must not empty out silently.

    If the last entry ever loses its surface, the gate would verify nothing and
    still exit 0 - the same shape as the defect above, one level up.
    """
    assert _LAZY_REEXPORT_MODULES


def test_the_live_gate_passes() -> None:
    """Driven end to end over the real tree, since the list is now truthful."""
    assert main() == 0
