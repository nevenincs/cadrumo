"""Suggestion-string command-citation conformance gate.

The CLI's instructive surface is wider than ``--help`` and the how-to docs:
error-registry ``default_suggestion`` fields, the curated operator help
documents, ``next_action`` builder strings, the runtime write-policy, and the
four locale catalogues all cite ``aeat app ...`` / ``aeat config ...``
invocations that an operator is told to run next. The pull/--file standard
rule (``aeat-cli-pull-and-file-standard``) records that NONE of these strings
were covered by a conformance gate: ``test_documented_command_conformance``
scans only the how-to docs, and ``test_json_schema_conformance`` only the
envelope ``command=`` identifiers, so "a verb rename MUST be swept by hand"
through every suggestion surface. A rename that misses one leaves a dead
operator instruction — the error path tells the operator to run a command
that no longer exists, which is a silent failure of the first instructive
surface.

This gate converts that hand-sweep obligation into CI enforcement. It walks
the REAL Click tree (``typer.main.get_command`` over the live ``aeat`` app —
no mocks, no fixture trees) and resolves every cited command path from:

- every registered :class:`ErrorCode` ``default_suggestion``;
- the curated operator help documents (root / config / app surfaces);
- every string literal in production modules under ``aeat.application``,
  ``aeat.core.errors``, and ``aeat.entrypoints`` (AST-extracted, so comments
  cannot false-positive and ``next_action`` / write-policy / envelope builder
  strings are all swept).

The four locale catalogues (``en``/``es``/``ca``/``hu``) carry the same class
of citations inside translated suggestion text and are the natural fourth
sweep; extending this gate over them is tracked as a follow-up (the catalogues
carried three locale-divergent dead citations when this gate landed, owned by
the locale-CLI workflow).

Citation grammar: ``aeat`` followed by a root family (``app`` / ``config``)
and a run of lowercase kebab-case tokens. Resolution walks group-by-group and
accepts trailing tokens once a leaf command is reached (they are arguments);
uppercase placeholders (``NAME``), options (``--file``), and ``<id>`` forms
terminate the token run by construction. Each suite asserts a minimum
citation count so a regression in the extractor cannot silently scan nothing,
and the scanner itself is proven against a synthetic dead citation.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import cast

import click
import pytest
from typer.main import get_command

import aeat
from aeat.application.operator_surface import HelpSurface, build_help_document
from aeat.core.errors._registry import ERROR_REGISTRY

from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PACKAGE_ROOT = Path(aeat.__file__).resolve().parent
_AST_SCAN_ROOTS = (
    _PACKAGE_ROOT / "application",
    _PACKAGE_ROOT / "core" / "errors",
    _PACKAGE_ROOT / "entrypoints",
)

# ``aeat`` + a root family + a run of lowercase kebab-case tokens. Uppercase
# placeholders, ``--option`` forms, and ``<value>`` forms end the run, so only
# verb-path candidates (plus possibly lowercase argument VALUES, which the
# resolver tolerates past a leaf) are captured.
_CITATION_PATTERN = re.compile(r"\baeat (app|config)((?: [a-z][a-z0-9-]*)*)")


@cache
def _root_command() -> click.Command:
    """Build the live Click tree once for the whole module."""
    return cast("click.Command", get_command(app))


def _first_dead_token(tokens: tuple[str, ...]) -> str | None:
    """Walk ``tokens`` through the live tree; return the first unresolvable one.

    Tokens beyond a leaf command are positional argument values and are
    accepted. A ``None`` return means the citation names a live command path.
    """
    command: click.Command = _root_command()
    context = click.Context(command, info_name="aeat")
    for token in tokens:
        if not hasattr(command, "list_commands"):
            return None
        # ``list_commands`` is the structural group marker; the vendored
        # TyperGroup is not a guaranteed upstream ``click.Group`` subclass, so
        # narrow by interface (cast) rather than isinstance — an isinstance
        # check silently treats every group as a leaf and accepts everything
        # (caught by test_scanner_flags_a_dead_citation at authoring time).
        group = cast("click.Group", command)
        subcommand = group.get_command(context, token)
        if subcommand is None:
            return token
        context = click.Context(subcommand, info_name=token, parent=context)
        command = subcommand
    return None


def _iter_citations(text: str) -> Iterator[tuple[str, tuple[str, ...]]]:
    """Yield ``(cited_text, verb_tokens)`` for every command citation in ``text``."""
    for match in _CITATION_PATTERN.finditer(text):
        yield match.group(0), (match.group(1), *match.group(2).split())


def _dead_citations_in(text: str, *, origin: str) -> list[str]:
    """Return instructive failure rows for every dead citation in ``text``."""
    failures: list[str] = []
    for cited, tokens in _iter_citations(text):
        dead_token = _first_dead_token(tokens)
        if dead_token is not None:
            failures.append(f"{origin}: cites {cited!r} but {dead_token!r} does not resolve in the live CLI tree")
    return failures


def _count_citations(text: str) -> int:
    return sum(1 for _ in _iter_citations(text))


def _iter_production_modules() -> Iterator[Path]:
    for scan_root in _AST_SCAN_ROOTS:
        for module_path in sorted(scan_root.rglob("*.py")):
            if "tests" in module_path.parts:
                continue
            yield module_path


def test_error_registry_suggestions_cite_live_commands() -> None:
    """Every registered ``default_suggestion`` names commands the tree mounts."""
    failures: list[str] = []
    citation_count = 0
    assert ERROR_REGISTRY, "error registry is empty — registration imports regressed"
    for code, entry in ERROR_REGISTRY.items():
        suggestion = entry.default_suggestion
        if not suggestion:
            continue
        citation_count += _count_citations(suggestion)
        failures.extend(_dead_citations_in(suggestion, origin=f"error code {code}"))
    assert not failures, "\n".join(failures)
    assert citation_count >= 150, (
        f"only {citation_count} command citations found across error-registry suggestions; "
        "the extractor appears blind — the registry carried 175+ when this gate landed"
    )


def test_operator_help_documents_cite_live_commands() -> None:
    """Every curated help row's ``command`` resolves in the live tree."""
    failures: list[str] = []
    citation_count = 0
    for surface in HelpSurface:
        rendered = build_help_document(surface).model_dump_json()
        citation_count += _count_citations(rendered)
        failures.extend(_dead_citations_in(rendered, origin=f"operator help surface {surface.value}"))
    assert not failures, "\n".join(failures)
    assert citation_count >= 60, (
        f"only {citation_count} command citations found across operator help documents; "
        "the extractor appears blind — the curated surface carried 100+ when this gate landed"
    )


def test_production_string_literals_cite_live_commands() -> None:
    """Every ``aeat app/config`` literal in production modules stays live.

    AST extraction covers exactly the surfaces the pull/--file rule names as
    ungated: write-policy allowlists, ``next_action`` builders, envelope
    builders, and any future suggestion string a feature module grows.
    Comments cannot false-positive (they are not AST constants).
    """
    failures: list[str] = []
    citation_count = 0
    for module_path in _iter_production_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        relative = module_path.relative_to(_PACKAGE_ROOT.parent).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                citation_count += _count_citations(node.value)
                failures.extend(_dead_citations_in(node.value, origin=f"{relative}:{node.lineno}"))
    assert not failures, "\n".join(failures)
    assert citation_count >= 500, (
        f"only {citation_count} command citations found across production string literals; "
        "the extractor appears blind — the scan roots carried 700+ when this gate landed"
    )


def test_scanner_flags_a_dead_citation() -> None:
    """Anti-tautology proof: the scanner reports a dead verb and passes a live one.

    If this test ever fails, every green result above is meaningless — the
    resolver would be accepting everything (or seeing nothing).
    """
    dead = _dead_citations_in(
        "Run aeat app modelo capture to refresh the state.",
        origin="synthetic",
    )
    assert len(dead) == 1
    assert "'capture'" in dead[0]

    # A retired multiplex-flag era verb on a live group is also caught.
    dead_leaf = _dead_citations_in("Use aeat app ledger refresh next.", origin="synthetic")
    assert len(dead_leaf) == 1
    assert "'refresh'" in dead_leaf[0]

    # The live canonical forms pass, and argument values past a leaf are tolerated.
    assert not _dead_citations_in("Run aeat app ledger import --file STATEMENT.csv.", origin="synthetic")
    assert not _dead_citations_in("Run aeat app modelo work calculate yourworkunit.", origin="synthetic")
