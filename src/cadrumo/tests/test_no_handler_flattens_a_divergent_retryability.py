"""No storage or custody handler translates away a subclass's retryability.

``retryable`` is the instruction this CLI's operator -- an autonomous agent --
acts on. Several error families publish one answer on a parent and the opposite
on a child, deliberately: the subclassing exists so established handlers keep
catching both. That same subclassing is what makes the answer easy to lose.

A handler that catches the PARENT and re-raises some other error type applies
one answer to both cases. Registration did exactly that: it caught
``ProfileCustodyTransactionConflictError`` (retryable, a re-read wins) and
translated it and its permanent ``ProfileCustodyDuplicateLabelError`` subclass
into a single non-retryable refusal, so a transient loss told the agent the name
it had just chosen was taken. It would not retry; it would rename a profile that
did not exist.

The check pairs the live error registry with the source: the divergent parent /
child pairs are computed from registered retryability and real subclassing, and
the handlers are read from the AST. Nothing is hand-listed, so a new error class
enrols itself.

Two shapes are deliberately NOT reported, and both were measured before being
excluded rather than assumed:

- Re-raising the SAME type that was caught (``except X: raise X(...)``) narrows
  a message without changing the answer, and the one such site in scope catches
  a conflict around a bounded file read that cannot produce the subclass at all.
- The Google-auth and outbound-storage surfaces under ``entrypoints/cli`` carry
  this shape at roughly thirty sites, and whether those codes should be
  retryable at all belongs to those surfaces. Gating them here would make this
  test answer a question it does not own.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .inventory import SRC_CADRUMO

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The packages covered by this check.
_SCOPED_PACKAGES = ("application/user_profile", "adapters/persistence/storage")

#: A boundary that applies one answer to two opposite situations.
_FLATTENING_SAMPLE = (
    "def register():\n"
    "    try:\n"
    "        publish()\n"
    "    except ProfileCustodyTransactionConflictError as exc:\n"
    "        raise ProfileRegistrationError('taken') from exc\n"
)

#: The same boundary with the permanent case routed ahead of the transient one.
_ROUTED_SAMPLE = (
    "def register():\n"
    "    try:\n"
    "        publish()\n"
    "    except ProfileCustodyDuplicateLabelError as exc:\n"
    "        raise ProfileRegistrationError('taken') from exc\n"
    "    except ProfileCustodyTransactionConflictError as exc:\n"
    "        raise ProfileRegistrationConflictError('lost a race') from exc\n"
)


def _caught_names(handler: ast.ExceptHandler) -> set[str]:
    """Return the error names one ``except`` clause catches."""
    if isinstance(handler.type, ast.Name):
        return {handler.type.id}
    if isinstance(handler.type, ast.Tuple):
        return {element.id for element in handler.type.elts if isinstance(element, ast.Name)}
    return set()


def _raised_names(handler: ast.ExceptHandler) -> set[str]:
    """Return the error names one ``except`` clause constructs and raises."""
    raised: set[str] = set()
    for inner in ast.walk(handler):
        if isinstance(inner, ast.Raise) and isinstance(inner.exc, ast.Call):
            target = inner.exc.func
            name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", None)
            if name:
                raised.add(name)
    return raised


def _flattening_handlers(tree: ast.AST, divergent: dict[str, set[str]]) -> list[tuple[int, str, list[str]]]:
    """Return handlers that translate a parent without routing its divergent children."""
    offenders: list[tuple[int, str, list[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        already_routed: set[str] = set()
        for handler in node.handlers:
            caught = _caught_names(handler)
            translates_to = _raised_names(handler) - caught
            for name in sorted(caught):
                if name in divergent and translates_to:
                    unrouted = sorted(divergent[name] - already_routed)
                    if unrouted:
                        offenders.append((handler.lineno, name, unrouted))
            already_routed |= caught
    return offenders


def _scoped_modules() -> list[Path]:
    """Return the production modules covered by this check."""
    modules: list[Path] = []
    for package in _SCOPED_PACKAGES:
        root = SRC_CADRUMO / Path(package)
        modules.extend(path for path in root.rglob("*.py") if "tests" not in path.parts and path.name != "conftest.py")
    return modules


def test_the_scan_reaches_the_scoped_packages() -> None:
    """ANTI-VACUITY: an empty module list produces an empty offender list."""
    assert len(_scoped_modules()) > 50


def test_the_detector_reports_a_flattening_boundary() -> None:
    """ANTI-TAUTOLOGY: proven on source carrying the shape, no tracked file touched."""
    divergent = {"ProfileCustodyTransactionConflictError": {"ProfileCustodyDuplicateLabelError"}}

    assert _flattening_handlers(ast.parse(_FLATTENING_SAMPLE), divergent) == [
        (4, "ProfileCustodyTransactionConflictError", ["ProfileCustodyDuplicateLabelError"])
    ]


def test_the_detector_accepts_a_routed_boundary() -> None:
    """The other direction: routing the subclass first must not be reported.

    A detector that flagged the corrected shape too would be reverted, and the
    gate lost with it.
    """
    divergent = {"ProfileCustodyTransactionConflictError": {"ProfileCustodyDuplicateLabelError"}}

    assert _flattening_handlers(ast.parse(_ROUTED_SAMPLE), divergent) == []
