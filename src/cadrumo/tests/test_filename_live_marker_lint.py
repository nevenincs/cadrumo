"""Filename-scope lint: ``test_live_*`` modules declare their live intent.

A module whose filename begins with ``test_live_`` reads, at a glance, as a
test of an AEAT live surface. This ratchet keeps that signal honest: every
``test_live_*.py`` module present on disk MUST either carry the
``aeat_live`` execution marker (it genuinely contacts a live AEAT surface and
is gated behind the opt-in) OR carry a banner comment of the form
``# INTENTIONAL: <scope> because <reason>`` declaring, in the author's words,
why the module is unit/integration despite the ``live`` filename (it exercises
the local read verbs, the oracle contract, or the CLI surface wiring without
touching AEAT).

The check is AST- and token-backed; it does not import the inspected modules.
It is the filename-scope companion to the marker-integrity ratchet, which
governs the marker taxonomy itself.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Iterator
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory
from .inventory import REPO_ROOT, SRC_CADRUMO

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LIVE_EXECUTION_MARKER = "aeat_live"
_INTENT_BANNER = re.compile(r"#\s*INTENTIONAL:\s*\w[\w-]*\s+because\s+\S")


def _module_marker_names(source: str, filename: str) -> frozenset[str]:
    """Return the marker names declared by a module-level ``pytestmark``.

    Accepts the ``pytestmark = [pytest.mark.<name>, ...]`` list/tuple shape as
    well as a single-marker assignment. Returns an empty set when no such
    assignment exists.
    """
    tree = ast.parse(source, filename=filename)
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "pytestmark":
            return frozenset(_marker_names_from_value(node.value))
    return frozenset[str]()


def _marker_names_from_value(value: ast.expr) -> Iterator[str]:
    elements = value.elts if isinstance(value, ast.List | ast.Tuple) else (value,)
    for element in elements:
        name = _marker_name(element)
        if name is not None:
            yield name


def _marker_name(element: ast.expr) -> str | None:
    """Return the ``<name>`` in a ``pytest.mark.<name>`` attribute or call."""
    attr_chain = element.func if isinstance(element, ast.Call) else element
    if not isinstance(attr_chain, ast.Attribute):
        return None
    mark_attr = attr_chain.value
    if (
        isinstance(mark_attr, ast.Attribute)
        and mark_attr.attr == "mark"
        and isinstance(mark_attr.value, ast.Name)
        and mark_attr.value.id == "pytest"
    ):
        return attr_chain.attr
    return None


def _has_intent_banner(source: str) -> bool:
    """Return True when a real ``# INTENTIONAL: ... because ...`` comment exists."""
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT and _INTENT_BANNER.search(token.string):
                return True
    except tokenize.TokenError:  # pragma: no cover - defensive against partial source
        return False
    return False


def _live_filename_violation(path: Path) -> str | None:
    """Return a violation string when a ``test_live_*`` module lacks live intent."""
    source = path.read_text(encoding="utf-8")
    if _LIVE_EXECUTION_MARKER in _module_marker_names(source, str(path)):
        return None
    if _has_intent_banner(source):
        return None
    try:
        display = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        display = path.name
    return (
        f"{display}: a test_live_*.py module must carry the "
        f"pytest.mark.{_LIVE_EXECUTION_MARKER} execution marker, or an "
        "'# INTENTIONAL: <scope> because <reason>' banner comment explaining "
        "why it is not a live test"
    )


def _live_prefixed_test_modules() -> list[Path]:
    """Return every ``test_live_*.py`` module present on disk under ``src/cadrumo``.

    The scan is a filesystem glob and deliberately does not consult git, so an
    untracked module is in scope, matching how the companion marker-integrity
    ratchet discovers its own scan set. In a worktree where several
    agents hold uncommitted work at once, a mis-declared ``test_live_*`` module
    is caught before it is committed rather than after. The cost is that a red
    here may name a file absent at HEAD, so triage starts with
    ``git status --short -- <file>``: an untracked path is a peer's work in
    progress, not a regression.
    """
    return sorted(
        path
        for path in scan_directory(SRC_CADRUMO, pattern="test_live_*.py", recursive=True)
        if path.name != "__init__.py"
    )


_LIVE_MODULES = _live_prefixed_test_modules()


def test_discovery_found_live_prefixed_modules() -> None:
    """Guardrail: the walker must discover at least one ``test_live_*`` module."""
    assert _LIVE_MODULES, "no test_live_*.py modules discovered - glob root or layout changed"


def test_every_live_prefixed_module_declares_live_scope_or_intent() -> None:
    """Every ``test_live_*`` module resolves to a live marker or an intent banner."""
    violations = [violation for path in _LIVE_MODULES if (violation := _live_filename_violation(path)) is not None]
    assert not violations, "test_live_* filename intent violations:\n" + "\n".join(violations)


def test_lint_flags_live_module_without_marker_or_banner(tmp_path: Path) -> None:
    """A ``test_live_*`` module with neither the live marker nor a banner is flagged."""
    offender = tmp_path / "test_live_offender.py"
    offender.write_text(
        "import pytest\n\npytestmark = [pytest.mark.unit, pytest.mark.hex_core]\n\n\ndef test_x() -> None:\n    pass\n",
        encoding="utf-8",
    )
    assert _live_filename_violation(offender) is not None


def test_lint_accepts_live_marked_module(tmp_path: Path) -> None:
    """The ``aeat_live`` execution marker satisfies the filename intent rule."""
    compliant = tmp_path / "test_live_marked.py"
    compliant.write_text(
        "import pytest\n\n"
        "pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]\n\n\n"
        "def test_x() -> None:\n    pass\n",
        encoding="utf-8",
    )
    assert _live_filename_violation(compliant) is None


def test_lint_rejects_aeat_live_lookalike_attribute(tmp_path: Path) -> None:
    """Only ``pytest.mark.aeat_live`` satisfies the filename intent rule."""
    offender = tmp_path / "test_live_lookalike.py"
    offender.write_text(
        "class Marker:\n"
        "    aeat_live = object()\n\n"
        "pytestmark = [Marker.aeat_live]\n\n\n"
        "def test_x() -> None:\n    pass\n",
        encoding="utf-8",
    )
    assert _live_filename_violation(offender) is not None


def test_lint_accepts_intent_banner(tmp_path: Path) -> None:
    """A non-live module with an intent banner comment satisfies the rule."""
    compliant = tmp_path / "test_live_bannered.py"
    compliant.write_text(
        "import pytest\n\n"
        "# INTENTIONAL: unit because it exercises local wiring without contacting AEAT.\n"
        "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]\n\n\n"
        "def test_x() -> None:\n    pass\n",
        encoding="utf-8",
    )
    assert _live_filename_violation(compliant) is None


def test_intent_banner_in_docstring_string_does_not_satisfy_rule(tmp_path: Path) -> None:
    """The banner must be a real comment, not incidental text in a string."""
    offender = tmp_path / "test_live_stringly.py"
    offender.write_text(
        '"""INTENTIONAL: unit because this is only a docstring, not a comment."""\n'
        "import pytest\n\npytestmark = [pytest.mark.unit, pytest.mark.hex_core]\n\n\n"
        "def test_x() -> None:\n    pass\n",
        encoding="utf-8",
    )
    assert _live_filename_violation(offender) is not None
