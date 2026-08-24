"""Structural enrollment gate for regulatory cap runtime witnesses."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ..domain.tests import REGULATORY_CAP_WITNESSES
from . import aeat_relative, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SiteKey = tuple[str, str]
_BOUND_NAME_FRAGMENTS = (
    "CAP",
    "CEILING",
    "LIMIT",
    "LIMITE",
    "MAX_",
    "_MAX",
    "THRESHOLD",
    "TOPE",
    "MINIMO",
    "FLOOR",
)


def _bound_operand_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        name = node.id
    elif isinstance(node, ast.Attribute):
        name = node.attr
    else:
        return None
    return name if any(fragment in name.upper() for fragment in _BOUND_NAME_FRAGMENTS) else None


def _enclosing_function_by_line(tree: ast.AST) -> Mapping[int, str]:
    owner: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for child in ast.walk(node):
                lineno = getattr(child, "lineno", None)
                if lineno is not None:
                    owner[lineno] = node.name
    return owner


def _discovered_cap_sites() -> dict[_SiteKey, set[str]]:
    sites: dict[_SiteKey, set[str]] = {}
    for path, tree in production_ast_items():
        owner = _enclosing_function_by_line(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in {"min", "max"}:
                continue
            for arg in node.args:
                name = _bound_operand_name(arg)
                if name is not None:
                    key = (aeat_relative(Path(path)), owner.get(node.lineno, "<module>"))
                    sites.setdefault(key, set()).add(name)
    return sites


_NON_REGULATORY_EXEMPTIONS: Mapping[_SiteKey, str] = {
    ("application/operations/_supervisor.py", "await_terminal"): (
        "Supervisor polling backoff is a runtime scheduling bound, not a tax cap."
    ),
    ("adapters/outbound/google/_calc_sheets_apply.py", "_condition_for_constraint"): (
        "Spreadsheet validation presentation bounds are not tax limits."
    ),
    ("adapters/persistence/storage/attachment.py", "_merge_with_stored_manifest"): (
        "captured_at is a timestamp, not a regulatory cap."
    ),
    ("adapters/persistence/storage/master_key/_login_throttle.py", "_required_wait_seconds"): (
        "Authentication backoff is a security control, not a tax limit."
    ),
    ("llm/_client.py", "backoff_for"): ("Transport retry backoff is not a regulatory cap."),
    ("application/flows/_engine.py", "set_instance_count"): ("A form-authoring instance bound is not a tax cap."),
    ("application/flows/_engine.py", "_instance_count"): ("A form-authoring instance bound is not a tax cap."),
    ("application/flows/_engine.py", "_refresh_instance_counts"): ("A form-authoring instance bound is not a tax cap."),
    ("application/flows/_resume.py", "_seed_counts"): ("A form-authoring instance bound is not a tax cap."),
    ("application/user_profile/_section_rows.py", "next_section_row_index"): (
        "A non-negative row-index floor is not a tax cap."
    ),
}


def test_every_discovered_cap_site_is_enrolled() -> None:
    """Every cap-shaped production site has one witness or stated exemption."""
    discovered = _discovered_cap_sites()
    enrolled = set(REGULATORY_CAP_WITNESSES) | set(_NON_REGULATORY_EXEMPTIONS)
    unenrolled = sorted(key for key in discovered if key not in enrolled)
    if unenrolled:
        listed = "\n  ".join(
            f"{path}::{function}  bound={sorted(discovered[(path, function)])}" for path, function in unenrolled
        )
        raise AssertionError(f"{len(unenrolled)} unenrolled min/max cap site(s):\n  {listed}")


def test_no_enrolment_outlives_its_site() -> None:
    """A witness or exemption cannot outlive its production site."""
    discovered = set(_discovered_cap_sites())
    stale = sorted(
        key for key in (set(REGULATORY_CAP_WITNESSES) | set(_NON_REGULATORY_EXEMPTIONS)) if key not in discovered
    )
    if stale:
        listed = "\n  ".join(f"{path}::{function}" for path, function in stale)
        raise AssertionError(f"{len(stale)} stale cap enrolment(s):\n  {listed}")
