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
- every string literal in production modules under ``aeat.adapters``,
  ``aeat.application``, ``aeat.core.errors``, and ``aeat.entrypoints``
  (AST-extracted, so comments cannot false-positive and ``next_action`` /
  write-policy / envelope-builder / adapter-refusal strings are all swept).

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

from ....application.operator_surface import HelpSurface, build_help_document
from ....core.errors._registry import ERROR_REGISTRY
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_AST_SCAN_ROOTS = (
    _PACKAGE_ROOT / "adapters",
    _PACKAGE_ROOT / "application",
    _PACKAGE_ROOT / "core" / "errors",
    _PACKAGE_ROOT / "entrypoints",
)

# ``aeat`` + a root family + a run of kebab-case tokens. A token is lowercase
# kebab-case OR a bare modelo code (three digits, e.g. ``100``/``303``), the
# only digit-leading command segments in the live tree (``aeat app live
# borrador 100 list``). Uppercase placeholders, ``--option`` forms, and
# ``<value>`` forms end the run, so only verb-path candidates (plus possibly
# lowercase argument VALUES, which the resolver tolerates past a leaf) are
# captured. Admitting the modelo code keeps a runnable ``... borrador 100 list``
# citation from terminating prematurely on the ``borrador`` group.
_CITATION_PATTERN = re.compile(r"\baeat (app|config)((?: (?:[a-z][a-z0-9-]*|\d{3}))*)")


@cache
def _root_command() -> click.Command:
    """Build the live Click tree once for the whole module."""
    return cast("click.Command", get_command(app))


def _is_group(command: click.Command) -> bool:
    """Return whether ``command`` is a structural group (not a runnable leaf).

    ``list_commands`` is the structural group marker; the vendored TyperGroup
    is not a guaranteed upstream ``click.Group`` subclass, so narrow by
    interface rather than isinstance — an isinstance check silently treats
    every group as a leaf (caught by ``test_scanner_flags_a_group_citation``).
    """
    return hasattr(command, "list_commands")


def _resolve_citation(tokens: tuple[str, ...]) -> tuple[str | None, bool]:
    """Walk ``tokens`` through the live tree.

    Returns ``(dead_token, terminates_on_group)``:

    - ``dead_token`` is the first token that does not resolve, or ``None`` when
      every token resolves. Tokens beyond a leaf command are positional
      argument values and are accepted.
    - ``terminates_on_group`` is ``True`` when the citation resolves cleanly but
      the final resolved command is a group (e.g. ``config repair integrity``),
      which is NOT runnable verbatim — the operator must pick a child or be
      pointed at ``... --help``.
    """
    command: click.Command = _root_command()
    context = click.Context(command, info_name="aeat")
    for token in tokens:
        if not _is_group(command):
            # Already at a leaf; remaining tokens are argument values.
            return None, False
        group = cast("click.Group", command)
        subcommand = group.get_command(context, token)
        if subcommand is None:
            return token, False
        context = click.Context(subcommand, info_name=token, parent=context)
        command = subcommand
    return None, _is_group(command)


@cache
def _root_option_names() -> frozenset[str]:
    """Long/short option strings declared on the root callback.

    Root-global options (``--language`` / ``--format`` / ``--profile`` /
    ``--help`` / etc.) are accepted on any leaf, so the option-validity check
    unions them with the resolved command's own params. Mirrors
    :func:`test_documented_command_conformance._root_option_names`.
    """
    names: set[str] = set()
    for param in _root_command().params:
        if getattr(param, "param_type_name", None) == "option":
            names.update(param.opts)
            names.update(param.secondary_opts)
    return frozenset(names)


def _command_option_names(command: click.Command) -> frozenset[str]:
    """Long/short option strings declared on ``command``.

    Mirrors :func:`test_documented_command_conformance._command_option_names`
    so the suggestion surface validates cited ``--option`` tokens against the
    same authoritative live-parameter set the how-to docs are checked against.
    """
    names: set[str] = set()
    for param in command.params:
        if getattr(param, "param_type_name", None) == "option":
            names.update(param.opts)
            names.update(param.secondary_opts)
    return frozenset(names)


# An ``--option`` / ``-o`` token in suggestion text. ``--help`` is always valid
# (it is a root global), so it never reaches the option-validity check; the
# pattern still captures it so the citation's trailing-help recovery works.
# A trailing ``=`` form (``--format=json``) is split to the bare option name.
_OPTION_TOKEN_PATTERN = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]*|-[a-zA-Z])(?=[\s=.,;)\]'\"]|$)")


def _resolve_leaf_command(tokens: tuple[str, ...]) -> click.Command | None:
    """Return the deepest live command the verb tokens resolve to, or ``None``.

    Walks group-by-group exactly like :func:`_resolve_citation` but returns the
    resolved command object (the leaf, or the deepest group) so its parameter
    set can be introspected. Returns ``None`` when any token fails to resolve —
    the dead-token check already reports that as a failure, so option validity
    is only evaluated on a citation whose verb path is sound.
    """
    command: click.Command = _root_command()
    context = click.Context(command, info_name="aeat")
    for token in tokens:
        if not _is_group(command):
            return command
        group = cast("click.Group", command)
        subcommand = group.get_command(context, token)
        if subcommand is None:
            return None
        context = click.Context(subcommand, info_name=token, parent=context)
        command = subcommand
    return command


def _cited_options_after(text: str, start: int) -> list[str]:
    """Extract ``--option`` tokens that belong to the citation ending at ``start``.

    Scans forward from the end of the matched verb path until the next ``aeat``
    citation begins or the text ends, so options trailing one suggested command
    are not mis-attributed to a later one. ``--help`` is dropped (a universal
    root global that is always runnable). ``--opt=value`` is reduced to the bare
    option name.
    """
    next_match = _CITATION_PATTERN.search(text, start)
    end = next_match.start() if next_match is not None else len(text)
    window = text[start:end]
    options: list[str] = []
    for match in _OPTION_TOKEN_PATTERN.finditer(window):
        name = match.group(1)
        if name == "--help":
            continue
        options.append(name)
    return options


def _iter_citations(text: str) -> Iterator[tuple[str, tuple[str, ...], bool, tuple[str, ...]]]:
    """Yield ``(cited_text, verb_tokens, has_trailing_help, cited_options)`` per citation.

    ``has_trailing_help`` records whether ``--help`` immediately follows the
    cited verb path in the source text. The citation regex stops at the first
    ``--option`` form, so a runnable ``aeat config repair integrity --help``
    citation parses as the bare-group token run; this flag recovers the
    operator-runnable distinction the regex drops.

    ``cited_options`` are the ``--option`` / ``-o`` tokens the regex drops,
    recovered from the text following the verb path (up to the next citation),
    so a suggestion can be validated against the resolved command's parameter
    set — catching a dead option (e.g. ``... split <id> --dry-run`` where
    ``split`` has no ``--dry-run``) the verb-only check could never see.
    """
    for match in _CITATION_PATTERN.finditer(text):
        remainder = text[match.end() :]
        has_trailing_help = bool(re.match(r"\s+--help\b", remainder))
        cited_options = tuple(_cited_options_after(text, match.end()))
        yield (
            match.group(0),
            (match.group(1), *match.group(2).split()),
            has_trailing_help,
            cited_options,
        )


def _dead_citations_in(text: str, *, origin: str, require_runnable_leaf: bool = False) -> list[str]:
    """Return instructive failure rows for every non-runnable citation in ``text``.

    A citation is dead when one of its tokens does not resolve in the live tree
    — always a failure.

    When ``require_runnable_leaf`` is set (the operator-suggestion surfaces:
    error-registry ``default_suggestion`` and curated help ``command`` fields,
    where the cited string IS the command the operator is told to run), a
    citation that resolves cleanly to a command GROUP with no trailing
    ``--help`` is ALSO a failure: a group is not executable verbatim
    (``Missing command``), so the operator is sent to a non-runnable line.
    ``<group> --help`` IS runnable and is accepted. The flag is OFF for the
    broad production-string-literal scan, where a bare ``aeat config google``
    is overwhelmingly a prose/docstring reference to a command *family*, not a
    runnable suggestion, and group-termination is legitimate there.

    The flag ALSO gates option validity: under ``require_runnable_leaf`` every
    cited ``--option`` must be a real parameter of the resolved command (or a
    root-global option), so a suggestion citing an option the target verb does
    not declare (e.g. ``... split <id> --dry-run`` where ``split`` carries only
    ``--yes``) is flagged. Option validity is scoped to the runnable-suggestion
    surfaces because reference prose can legitimately mention an option in the
    abstract; a runnable suggestion is the line the operator pastes verbatim.
    """
    failures: list[str] = []
    for cited, tokens, has_trailing_help, cited_options in _iter_citations(text):
        dead_token, terminates_on_group = _resolve_citation(tokens)
        if dead_token is not None:
            failures.append(f"{origin}: cites {cited!r} but {dead_token!r} does not resolve in the live CLI tree")
            continue
        if require_runnable_leaf and terminates_on_group and not has_trailing_help:
            failures.append(
                f"{origin}: cites {cited!r} which resolves to a command GROUP, not a runnable leaf; "
                "append a child command or cite '... --help' so the suggestion runs verbatim"
            )
        if require_runnable_leaf and cited_options:
            command = _resolve_leaf_command(tokens)
            if command is not None and not _is_group(command):
                valid_options = _command_option_names(command) | _root_option_names()
                for option in cited_options:
                    if option not in valid_options:
                        failures.append(
                            f"{origin}: cites {cited!r} with option {option!r}, which is not a parameter of "
                            f"'aeat {' '.join(tokens)}' (nor a root-global option)"
                        )
    return failures


def _count_citations(text: str) -> int:
    return sum(1 for _ in _iter_citations(text))


def _option_validity_failures(text: str, *, origin: str) -> list[str]:
    """Return only the option-validity failures for ``text`` under strict mode.

    A thin focused wrapper used by the anti-tautology proof so it asserts the
    option check in isolation from the verb-path and group-termination checks.
    """
    return [
        failure
        for failure in _dead_citations_in(text, origin=origin, require_runnable_leaf=True)
        if "with option" in failure
    ]


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
        failures.extend(_dead_citations_in(suggestion, origin=f"error code {code}", require_runnable_leaf=True))
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


# The runnable-suggestion fields: a string assigned to one of these — as a
# keyword argument (``suggestion=...``) or a dict value (``{"recovery": ...}``)
# — is a command the operator is told to run, so it MUST resolve to a runnable
# leaf, never a bare command group. Other literals (docstrings, ``cli_path=``
# path-root declarations, help-document heading/paragraph prose) name a command
# *family* in reference and legitimately terminate on a group; they stay under
# the dead-token check only.
_RUNNABLE_SUGGESTION_KEYS = frozenset({"suggestion", "recovery", "default_suggestion", "next_action"})


def _runnable_suggestion_node_ids(tree: ast.AST) -> set[int]:
    """Collect ``id()`` of every string ``Constant`` used as a runnable-suggestion value.

    Matches both ``suggestion="aeat ..."`` keyword arguments and
    ``{"recovery": "aeat ..."}`` / ``{"next_action": "aeat ..."}`` dict
    entries, where the operator is directed to run the cited command verbatim.
    """
    suggestion_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in _RUNNABLE_SUGGESTION_KEYS:
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                suggestion_ids.add(id(node.value))
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and key.value in _RUNNABLE_SUGGESTION_KEYS
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    suggestion_ids.add(id(value))
    return suggestion_ids


def test_production_string_literals_cite_live_commands() -> None:
    """Every ``aeat app/config`` literal in production modules stays live.

    AST extraction covers exactly the surfaces the pull/--file rule names as
    ungated: write-policy allowlists, ``next_action`` builders, envelope
    builders, and any future suggestion string a feature module grows.
    Comments cannot false-positive (they are not AST constants).

    Two checks per literal: every citation's tokens must resolve (dead-token
    check, all literals), and a literal assigned to a runnable-suggestion field
    (``suggestion=`` / ``recovery`` / ``default_suggestion`` / ``next_action``)
    must additionally resolve to a runnable LEAF — a bare command group with no
    trailing ``--help`` is not executable verbatim and fails. Reference prose
    (docstrings, ``cli_path=`` path roots, help headings) names a command
    family and legitimately terminates on a group, so the runnable-leaf check
    is scoped to the suggestion fields only.
    """
    failures: list[str] = []
    citation_count = 0
    for module_path in _iter_production_modules():
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        relative = module_path.relative_to(_PACKAGE_ROOT.parent).as_posix()
        suggestion_ids = _runnable_suggestion_node_ids(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                citation_count += _count_citations(node.value)
                failures.extend(
                    _dead_citations_in(
                        node.value,
                        origin=f"{relative}:{node.lineno}",
                        require_runnable_leaf=id(node) in suggestion_ids,
                    )
                )
    assert not failures, "\n".join(failures)
    assert citation_count >= 550, (
        f"only {citation_count} command citations found across production string literals; "
        "the extractor appears blind — the scan roots carried 760+ when adapters/ enrolled"
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


def test_scanner_flags_a_group_citation() -> None:
    """Anti-tautology proof for the group-termination rule.

    A citation that resolves to a command GROUP with no trailing ``--help`` is
    NOT runnable verbatim ('Missing command'); the scanner must flag it under
    ``require_runnable_leaf``. The same path with ``--help`` IS runnable and
    must pass. ``config repair integrity`` is a real group (children:
    ``objects``, ``registry``). A trailing ``.`` terminates the token run so
    the citation resolves exactly to the group.
    """
    group_cited = _dead_citations_in("aeat config repair integrity.", origin="synthetic", require_runnable_leaf=True)
    assert len(group_cited) == 1
    assert "GROUP" in group_cited[0]

    # The runnable help form on the same group is accepted even when strict.
    assert not _dead_citations_in(
        "aeat config repair integrity --help.", origin="synthetic", require_runnable_leaf=True
    )

    # A real runnable leaf under that group is accepted.
    assert not _dead_citations_in(
        "aeat config repair integrity objects.", origin="synthetic", require_runnable_leaf=True
    )

    # Without the strict flag, a bare group citation is tolerated (prose-family
    # references in docstrings legitimately terminate on a group).
    assert not _dead_citations_in("aeat config repair integrity.", origin="synthetic")


def test_scanner_flags_a_dead_option_citation() -> None:
    """Anti-tautology proof for the option-validity rule.

    A runnable suggestion that cites an ``--option`` the resolved leaf does NOT
    declare is flagged; the same leaf's REAL option passes. ``aeat app ledger
    split`` is a real leaf carrying ``--yes`` (the destructive-confirm flag) but
    NOT ``--dry-run`` (only ``remove`` / ``reset`` have a dry-run preview), so a
    suggestion steering the operator to ``... split <id> --dry-run`` sends them
    to a flag the command does not accept. This is the dead-option class the
    verb-only check could never see.
    """
    dead_option = _option_validity_failures(
        "Re-run aeat app ledger split TX123 --dry-run to preview.", origin="synthetic"
    )
    assert len(dead_option) == 1, dead_option
    assert "--dry-run" in dead_option[0]
    assert "split" in dead_option[0]

    # The real ``--yes`` flag on the same leaf passes.
    assert not _option_validity_failures("Re-run aeat app ledger split TX123 --yes to confirm.", origin="synthetic")

    # A leaf that genuinely has ``--dry-run`` (``remove``) accepts it.
    assert not _option_validity_failures(
        "Re-run aeat app ledger remove TX123 --dry-run to preview.", origin="synthetic"
    )

    # Root-global options (``--format`` / ``--language``) are valid on any leaf.
    assert not _option_validity_failures("Run aeat app ledger split TX123 --format json --yes.", origin="synthetic")

    # Option validity is OFF for reference prose (no strict flag), so an abstract
    # mention of an option does not false-positive.
    assert not _dead_citations_in("The aeat app ledger split verb has no --dry-run preview.", origin="synthetic")
