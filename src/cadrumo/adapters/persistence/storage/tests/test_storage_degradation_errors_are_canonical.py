"""The storage-degradation error set has one definition that extenders compose.

Nine modules each spelled the tuple out. Seven carried the same three errors and
two extended it with their own persistence errors, so the base set was restated
nine times while genuinely differing in two places.

That shape is the hazard this gate protects. Adding a fourth error the engine
should degrade on means editing every copy, and the copy nobody edits keeps
raising where its siblings now report an incomplete source. The failure is
silent in exactly the direction `no-silent-under-declaration` forbids: a caller
that does not degrade produces a total rather than an advisory.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from ..errors import (
    STORAGE_DEGRADATION_ERRORS,
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parents[4]
_NAME: Final[str] = "STORAGE_DEGRADATION_ERRORS"


def test_the_canonical_set_is_what_it_claims() -> None:
    """Pin the members, so the scan below cannot pass over a hollowed-out tuple."""
    assert (
        ClassificationError,
        DecryptionError,
        EnvelopeVersionError,
    ) == STORAGE_DEGRADATION_ERRORS


def test_every_member_is_catchable_as_an_exception() -> None:
    """A member that is not an exception type would make every `except` silently miss."""
    assert STORAGE_DEGRADATION_ERRORS
    for member in STORAGE_DEGRADATION_ERRORS:
        assert isinstance(member, type)
        assert issubclass(member, BaseException)


def _restates_the_set(path: Path) -> bool:
    """True when a module builds the tuple from literals instead of composing it.

    Composition -- ``(*STORAGE_DEGRADATION_ERRORS, LocalError)`` -- is allowed and
    is how the two legitimate extenders declare their extra errors. What is not
    allowed is restating the base members, because that is the copy that drifts.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != _NAME:
            continue
        rendered = ast.unparse(node.value)
        if _NAME not in rendered:
            return True
    return False


def test_no_module_restates_the_degradation_set() -> None:
    """`errors` owns the set; consumers import it and extenders compose it."""
    modules = [path for path in _PACKAGE_ROOT.rglob("*.py") if "tests" not in path.parts and path.name != "errors.py"]

    assert len(modules) > 500, (
        f"only {len(modules)} modules were enumerated; the scan collapsed, so an empty "
        "result below would mean 'nothing was searched' rather than 'no restatements exist'"
    )

    offenders = sorted(path.relative_to(_PACKAGE_ROOT).as_posix() for path in modules if _restates_the_set(path))

    assert offenders == [], (
        "module(s) restate the storage-degradation error set instead of importing or "
        f"composing the canonical tuple: {offenders}"
    )
