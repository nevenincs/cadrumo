"""CLI reference generator for the ``aeat`` command tree.

Materialises the full Click command tree from ``typer.main.get_command(app)``,
walks every group and leaf command (forcing lazy-module imports), and renders
the reference organised by major verb group under ``docs/cli/``. Each
top-level family (``app``, ``config``) gets a landing page
(``docs/cli/app.rst``) that is navigation only - a grid linking to each major
verb group's own page, plus any command mounted directly on the family root
with no intervening group. Each verb group gets its own page
(``docs/cli/app/ledger.rst``) that OPENS with that group's real ``--help``
rendering (usage, description, options, subcommand summary - Click's classic
formatter, not Typer's Rich styling, so the text is byte-stable across
machines; see :func:`_captured_help_text`), then walks its subtree: every leaf
command gets a full section, and every nested subgroup (``ledger rule``,
``ledger invoice catalogue``) gets its own captured ``--help`` block before its
children, recursively. The top ``index.rst`` page carries navigation (the
top-level family grid, a where-to-go-next block) plus root-level behaviour
(global flags); companion pages carry the automation contract
(``automation.rst``: exit codes, TTY/JSON output) and the output-schema
registry (``schemas.rst``).

The generator is documentation tooling.  It lives under ``dev/docs`` and
introspects the production package from outside rather than being part of the
``cadrumo`` runtime package.

Language pinning
----------------
Help strings are ``tr()`` values resolved at module-import time and stored as
plain strings on the Typer objects, so the output language MUST be pinned to
``en`` *before* any CLI command module is imported.  Call
:func:`generate_cli_reference` from a subprocess with
``CADRUMO_OUTPUT_LANGUAGE=en`` in its environment (the clean guarantee - mirroring
the lazy-tree subprocess tests) or set the variable before importing
:mod:`cadrumo.entrypoints.cli`.

Accepted-surface contract
-------------------------
Only surfaces declared in
:data:`~cadrumo.application.operator_surface.ACCEPTED_ROOTS` are documented as
live commands.  A command name that is not mounted under an accepted root
simply does not exist; typing it yields Click's standard "No such command".
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from cadrumo.core import scan_directory
from cadrumo.core.external_constants import UTF_8_ENCODING, OutputLanguage
from cadrumo.entrypoints.cli._command_specs import COMMAND_GRAPH
from cadrumo.entrypoints.schema_surface import normalise_cli_path_to_schema_key

from ._locale_chrome import docs_chrome

if TYPE_CHECKING:
    import click

#: Group-callback emit sites - keys registered under a group callback rather
#: than a leaf command.  These are excluded from the per-command reference
#: pages (they are group landing surfaces, not operator-invokable leaves) but
#: are listed on the output-schema registry page (``schemas.rst``).
_GROUP_CALLBACK_EMIT_KEYS: frozenset[str] = frozenset(
    spec.result_schema.identity
    for spec in COMMAND_GRAPH.specs
    if spec.kind == "group" and spec.result_schema.identity is not None
)

#: Command-path normalisation rules that mirror the conformance-test normaliser
#: in :mod:`cadrumo.entrypoints.cli.test_json_schema_conformance`.
#: Deterministic wrap width for a captured group ``--help`` block, pinned via
#: ``max_content_width`` (see :func:`_captured_help_text`) so the rendered
#: reference is byte-stable across machines.
_GROUP_HELP_WIDTH: int = 100

#: RST section-underline characters keyed by tree depth relative to a verb-group
#: page's own title (depth 0). A node's heading character is determined by its
#: depth alone - never by whether it is a group or a leaf - so a direct leaf
#: command and a nested subgroup at the same depth render as RST siblings.
_HEADING_CHARS_BY_DEPTH: tuple[str, ...] = ("=", "-", "^", "~", '"', "'")


def _heading_char_for_depth(depth: int) -> str:
    """Return the RST underline character for tree ``depth``, clamped to the table."""
    return _HEADING_CHARS_BY_DEPTH[min(depth, len(_HEADING_CHARS_BY_DEPTH) - 1)]


# ---------------------------------------------------------------------------
# Page-routing authority - the single source of "which page renders a command"
# ---------------------------------------------------------------------------
#
# The reference is organised into per-family and per-verb-group pages. Both the
# page-writing loop in :func:`_generate_cli_reference_loaded` and the search
# projection (``dev/docs/terminology/_cli_projection.py``, which deep-links each
# command record) must agree on the exact page a given command lands on. These
# two helpers plus :func:`cli_reference_page_for_command` are that one authority:
# a layout change (family page -> group page, as happened once and stranded every
# projected deep link on a bare landing page) is made here and both consumers
# follow. Do not re-derive the mapping in a consumer.


def _family_index_page_stem(family: str) -> str:
    """Return the doc-page stem for a family's landing page, e.g. ``cli/config``.

    A command mounted directly on the family root (no intervening verb group)
    renders inline on this page.
    """
    return f"cli/{family}"


def _verb_group_page_stem(family: str, group: str) -> str:
    """Return the doc-page stem for a verb group's page, e.g. ``cli/app/ledger``.

    The whole subtree of ``group`` (its leaf commands and any nested subgroups,
    recursively) renders on this single page.
    """
    return f"cli/{family}/{group}"


def cli_reference_page_for_command(command_path: tuple[str, ...]) -> str:
    """Return the doc-page stem that renders the leaf command at ``command_path``.

    This is the routing authority :func:`_generate_cli_reference_loaded` renders
    against, shared with the search-index projection so a deep link always lands
    on the page that actually carries the command's section. It mirrors the
    generator's split exactly: a leaf mounted directly on a family (path length
    3, e.g. ``aeat config login``) renders on the family index page
    (``cli/config``); a leaf under a verb group (length >= 4, e.g.
    ``aeat app ledger add`` or the deeper ``aeat app ledger evidence add``)
    renders on that group's own page (``cli/app/ledger``), keyed on the group
    segment ``command_path[2]`` - because a group page renders its entire
    subtree, however deep.

    Args:
        command_path: The full command path tuple including the leading
            executable token, e.g. ``("aeat", "app", "ledger", "add")``.

    Returns:
        The ``.html``-less doc-page stem (e.g. ``cli/app/ledger``), with no
        leading slash and no anchor fragment.

    Raises:
        ValueError: When ``command_path`` is too short to name a leaf command
            (fewer than three tokens: executable, family, command).
    """
    if len(command_path) < 3:
        raise ValueError(
            f"command_path {command_path!r} is too short to name a leaf command "
            "(expected at least ('aeat', <family>, <command>))",
        )
    family = command_path[1]
    if len(command_path) == 3:
        return _family_index_page_stem(family)
    return _verb_group_page_stem(family, command_path[2])


def _reference_subprocess_environment(storage_root: Path) -> dict[str, str]:
    """Return a clean environment for an ``aeat`` CLI-reference subprocess.

    Cadrumo language and local-storage settings are pinned after ambient
    Cadrumo product and AEAT authority settings are removed.

    Args:
        storage_root: Isolated Cadrumo local-storage root for the subprocess.
    """
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith(("CADRUMO_", "AEAT_"))}
    environment["CADRUMO_OUTPUT_LANGUAGE"] = "en"
    environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(storage_root)
    return environment


# ---------------------------------------------------------------------------
# Internal helpers - tree materialisation
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Internal helpers - command-path normalisation
# ---------------------------------------------------------------------------


_normalise_command_path = normalise_cli_path_to_schema_key


# ---------------------------------------------------------------------------
# Internal helpers - tree walking
# ---------------------------------------------------------------------------


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _collect_commands(
    root: click.Command,  # type: ignore[name-defined]
    # TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click return-type annotation same as above
) -> dict[tuple[str, ...], click.Command]:  # type: ignore[name-defined]
    """Recursively collect every reachable command node keyed by its path tuple.

    The returned mapping includes both groups and leaf commands.  The root
    command itself is stored at a one-element tuple ``(root.name,)``.

    Args:
        root: The materialised root Click command (name must be set).

    Returns:
        A mapping from path tuple to Click command for every reachable node.
    """
    import click

    result: dict[tuple[str, ...], click.Command] = {}

    def _walk(cmd: click.Command, path: tuple[str, ...]) -> None:
        result[path] = cmd
        if isinstance(cmd, click.Group) or hasattr(cmd, "list_commands"):
            with click.Context(cmd, info_name=cmd.name or None) as ctx:
                for child_name in cmd.list_commands(ctx):
                    child = cmd.get_command(ctx, child_name)
                    if child is not None:
                        _walk(child, (*path, child_name))

    root_name = root.name or "aeat"
    _walk(root, (root_name,))
    return result


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _is_group(cmd: click.Command) -> bool:  # type: ignore[name-defined]
    """Return whether ``cmd`` dispatches subcommands (a group) rather than being a leaf."""
    import click

    return isinstance(cmd, click.Group) or hasattr(cmd, "list_commands")


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _collect_leaf_paths(
    root: click.Command,  # type: ignore[name-defined]
) -> list[tuple[str, ...]]:
    """Return every leaf-command path reachable from ``root``.

    Args:
        root: The materialised root Click command (name must be set).

    Returns:
        A sorted list of path tuples for every leaf (non-group) command.
    """
    import click

    all_nodes = _collect_commands(root)
    leaves = [
        path for path, cmd in all_nodes.items() if not (isinstance(cmd, click.Group) or hasattr(cmd, "list_commands"))
    ]
    return sorted(leaves)


# ---------------------------------------------------------------------------
# Internal helpers - RST rendering
# ---------------------------------------------------------------------------


def _rst_heading(text: str, char: str) -> str:
    """Return a two-line RST heading.

    Args:
        text: The heading text.
        char: The underline character (e.g. ``"="``, ``"-"``).

    Returns:
        The RST heading string including a trailing newline.
    """
    return f"{text}\n{char * len(text)}\n"


def _rst_code(text: str, language: str = "text") -> str:
    """Return a RST code block.

    Args:
        text: The content to display verbatim.
        language: The Pygments lexer name.

    Returns:
        The RST ``.. code-block::`` directive string.
    """
    indented = textwrap.indent(text, "   ")
    return f".. code-block:: {language}\n\n{indented}\n"


def _rst_field_list(items: list[tuple[str, str]]) -> str:
    """Return a RST field list.

    Args:
        items: Sequence of ``(field_name, field_value)`` pairs.

    Returns:
        The RST field-list string.
    """
    lines = []
    for field, value in items:
        lines.append(f":{field}: {value}")
    return "\n".join(lines) + "\n" if lines else ""


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Parameter at this annotation site under the TYPE_CHECKING import guard.
def _is_click_argument(param: click.Parameter) -> bool:  # type: ignore[name-defined]
    """Return whether ``param`` is a positional argument.

    Discriminates on Click's ``param_type_name`` rather than ``isinstance`` on
    ``click.Argument``: Typer wraps positionals in ``TyperArgument``, which is
    NOT a ``click.Argument`` subclass, so an ``isinstance`` check silently
    mislabels every Typer positional as an option in the rendered reference.
    """
    return getattr(param, "param_type_name", "") == "argument"


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _render_param_table(language: OutputLanguage, params: list[click.Parameter]) -> str:  # type: ignore[name-defined]
    """Render a RST definition-list for command parameters.

    Args:
        params: The Click parameter list from a command.

    Returns:
        RST text describing each parameter, or an empty string when there
        are no parameters.
    """
    import click

    sections: list[str] = []
    for param in params:
        if isinstance(param, click.Context):
            continue
        opts = getattr(param, "opts", None) or [param.name]
        opt_str = ", ".join(f"``{o}``" for o in opts)
        required = getattr(param, "required", False)
        # The kind and its required-ness are ONE authored string per combination,
        # never two composed fragments: Spanish and Catalan inflect the adjective
        # for the noun's gender, so "Opción" takes "obligatoria" where
        # "Argumento" takes "obligatorio". Composing them would produce
        # agreement errors no English-shaped template can express.
        #
        # Each key is spelled out inside its own docs_chrome call rather than
        # selected into a variable: the locale scanner reads call sites, and a
        # key it cannot see is one scaffold deletes.
        if _is_click_argument(param):
            label = (
                docs_chrome("docs.cli.param.argument_required", language)
                if required
                else docs_chrome("docs.cli.param.argument_optional", language)
            )
        else:
            label = (
                docs_chrome("docs.cli.param.option_required", language)
                if required
                else docs_chrome("docs.cli.param.option_optional", language)
            )
        help_text = (param.help or "").strip() or docs_chrome("docs.cli.command.no_description", language)
        sections.append(f"{opt_str}\n   *{label}* {help_text}\n")
    return "\n".join(sections) if sections else ""


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _captured_help_text(
    path: tuple[str, ...],
    cmd: click.Command,  # type: ignore[name-defined]
) -> str:
    """Return the real ``--help`` rendering for the group at ``path``.

    Calls Click's base :meth:`~click.Command.format_help` directly on ``cmd`` -
    bypassing Typer's Rich-based override (``TyperCommand``/``TyperGroup`` both
    subclass the real ``click.Command`` and override ``format_help`` to render
    through Rich) - so the captured usage/description/options/commands text is
    the classic plain-text rendering: deterministic across machines, unlike
    Rich's box-drawing style, which auto-detects the host console's legacy/VT
    capability and therefore differs between an interactive terminal and a
    subprocess with no attached console. This is still the command's genuine
    ``--help`` content (usage line, description, options, subcommand summary),
    only without Rich's decorative panel styling.

    Args:
        path: The full command path tuple including the leading executable
            token, e.g. ``("aeat", "app", "ledger")``.
        cmd: The materialised Click command at ``path``.

    Returns:
        The captured help text, right-stripped of trailing newlines.
    """
    import click

    # Both `terminal_width` and `max_content_width` are pinned: Click's
    # `Context.make_formatter` uses `width=self.terminal_width` verbatim, and an
    # unset `terminal_width` falls back to `shutil.get_terminal_size()` - which
    # is itself environment-dependent (a real console vs. a subprocess with none
    # attached) - so pinning only `max_content_width` (a ceiling) is not enough
    # to make the wrap width deterministic across machines.
    ctx = click.Context(
        cmd,
        info_name=" ".join(path),
        terminal_width=_GROUP_HELP_WIDTH,
        max_content_width=_GROUP_HELP_WIDTH,
    )
    formatter = ctx.make_formatter()
    click.Command.format_help(cmd, ctx, formatter)
    return formatter.getvalue().rstrip("\n")


def _rst_help_block(help_text: str) -> str:
    """Return a RST code block carrying a captured ``--help`` rendering verbatim."""
    return _rst_code(help_text, language="text") + "\n"


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _render_command_section(
    language: OutputLanguage,
    path: tuple[str, ...],
    # TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click param annotation same as above
    cmd: click.Command,  # type: ignore[name-defined]
    schema_registry: dict[str, object],
    heading_char: str = "~",
) -> str:
    """Render the RST section for a single leaf command.

    Args:
        path: The full command path tuple, e.g. ``("aeat", "app", "modelo", "work", "calculate")``.
        cmd: The materialised Click command.
        schema_registry: The process-global schema registry for resolving
            the output schema, if any.
        heading_char: The RST underline character for this command's heading,
            chosen by the caller to match its depth in the surrounding page.

    Returns:
        A RST string describing the command.
    """
    full_path = " ".join(path)
    registry_key = _normalise_command_path(path)
    help_text = (cmd.help or "").strip() or docs_chrome("docs.cli.command.no_description_available", language)
    schema_cls = schema_registry.get(registry_key)

    parts: list[str] = []
    parts.append(_rst_heading(f"``{full_path}``", heading_char))
    parts.append(f"{help_text}\n\n")
    parts.append(f"**{docs_chrome('docs.cli.command.path_label', language)}:** ``{full_path}``\n\n")
    parts.append(f"**{docs_chrome('docs.cli.command.registry_key_label', language)}:** ``{registry_key}``\n\n")

    param_table = _render_param_table(language, cmd.params)
    if param_table:
        parts.append(f"**{docs_chrome('docs.cli.command.parameters_heading', language)}**\n\n")
        parts.append(param_table)
        parts.append("\n")

    schema_heading = docs_chrome("docs.cli.command.output_schema_heading", language)
    if schema_cls is not None:
        schema_name = f"{schema_cls.__module__}.{schema_cls.__name__}"
        parts.append(f"**{schema_heading}**\n\n")
        parts.append(docs_chrome("docs.cli.command.schema_envelope_note", language, schema=schema_name) + "\n\n")
    else:
        parts.append(f"**{schema_heading}**\n\n")
        parts.append(docs_chrome("docs.cli.command.bare_payload_note", language) + "\n\n")

    return "".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers - per-verb-group page rendering
# ---------------------------------------------------------------------------


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _render_group_children(
    language: OutputLanguage,
    path: tuple[str, ...],
    cmd: click.Command,  # type: ignore[name-defined]
    schema_registry: dict[str, object],
    depth: int,
) -> str:
    """Recursively render every child of the group at ``path``.

    A child that is itself a group gets its own heading plus a captured
    ``--help`` block, then recurses; a leaf child gets the standard command
    section. Both are rendered at the SAME heading depth (siblings), because
    the heading character is chosen from ``depth`` alone
    (:func:`_heading_char_for_depth`), never from the leaf/group distinction.

    Args:
        path: The command path tuple of the group being expanded.
        cmd: The materialised Click group command.
        schema_registry: The process-global schema registry.
        depth: The RST heading depth of ``path``'s direct children.

    Returns:
        RST text for every child of ``cmd``, recursing into nested groups.
    """
    import click

    parts: list[str] = []
    full_path = " ".join(path)
    with click.Context(cmd, info_name=full_path) as ctx:
        child_names = sorted(cmd.list_commands(ctx))
        for name in child_names:
            child = cmd.get_command(ctx, name)
            if child is None:
                continue
            child_path = (*path, name)
            if _is_group(child):
                parts.append(_rst_heading(f"``{' '.join(child_path)}``", _heading_char_for_depth(depth)))
                parts.append("\n")
                parts.append(_rst_help_block(_captured_help_text(child_path, child)))
                parts.append(_render_group_children(language, child_path, child, schema_registry, depth + 1))
            else:
                parts.append(
                    _render_command_section(
                        language,
                        child_path,
                        child,
                        schema_registry,
                        heading_char=_heading_char_for_depth(depth),
                    ),
                )
    return "".join(parts)


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _render_verb_group_page(
    language: OutputLanguage,
    group_path: tuple[str, ...],
    group_cmd: click.Command,  # type: ignore[name-defined]
    schema_registry: dict[str, object],
) -> str:
    """Render a full RST page for one major verb group (e.g. ``aeat app ledger``).

    The page opens with the group's own rendered ``--help`` output (the exact
    usage/description/options/commands text an operator sees at the terminal),
    then walks its subtree: every leaf command gets a full section
    (description, parameters, output schema), and every nested subgroup (e.g.
    ``ledger rule``, ``ledger invoice catalogue``) gets its own captured
    ``--help`` block before its children, recursively.

    Args:
        group_path: The full command path tuple, e.g. ``("aeat", "app", "ledger")``.
        group_cmd: The materialised Click group command.
        schema_registry: The process-global schema registry.

    Returns:
        The complete RST page content.
    """
    full_path = " ".join(group_path)
    parts: list[str] = []
    parts.append(_rst_heading(docs_chrome("docs.cli.family.title", language, command=f"``{full_path}``"), "="))
    parts.append("\n")
    parts.append(_rst_help_block(_captured_help_text(group_path, group_cmd)))
    parts.append(_render_group_children(language, group_path, group_cmd, schema_registry, depth=1))
    return "".join(parts)


def _render_family_index_page(
    language: OutputLanguage,
    family_name: str,
    group_names: list[str],
    direct_leaf_paths: list[tuple[str, ...]],
    schema_registry: dict[str, object],
    # TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
    # Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
    all_commands: dict[tuple[str, ...], click.Command],  # type: ignore[name-defined]
) -> str:
    """Render the landing page for one top-level command family.

    The page is navigation, not a command dump: a grid linking to each major
    verb group's own page (which leads with that group's rendered ``--help``),
    plus any commands mounted directly on the family root with no intervening
    group (``aeat config check``, ``aeat config login``, ...).

    Args:
        family_name: The family name, e.g. ``"config"`` or ``"app"``.
        group_names: Ordered verb-group names mounted directly under the family
            (e.g. ``["overview", "ledger", "live", ...]``).
        direct_leaf_paths: Command paths mounted directly under the family root
            with no intervening group.
        schema_registry: The process-global schema registry.
        all_commands: Mapping from path tuple to Click command object for
            every node collected from the tree.

    Returns:
        The complete RST page content.
    """
    title = docs_chrome("docs.cli.family.title", language, command=f"``aeat {family_name}``")
    parts: list[str] = []
    parts.append(_rst_heading(title, "="))
    parts.append("\n")
    parts.append(docs_chrome("docs.cli.family.intro", language, family=family_name) + "\n\n")
    parts.append(docs_chrome("docs.cli.index.english_help_note", language) + "\n\n")

    if group_names:
        parts.append(_rst_heading(docs_chrome("docs.cli.family.choose_group_heading", language), "-"))
        parts.append("\n")
        parts.append(".. grid:: 1 1 2 2\n")
        parts.append("   :gutter: 2\n")
        parts.append("   :class-container: cadrumo-route-grid\n\n")
        for group_name in group_names:
            group_cmd = all_commands.get(("aeat", family_name, group_name))
            summary = (getattr(group_cmd, "help", None) or "").strip() or docs_chrome(
                "docs.cli.command.group_fallback", language
            )
            parts.append(f"   .. grid-item-card:: ``aeat {family_name} {group_name}``\n")
            parts.append(f"      :link: {family_name}/{group_name}\n")
            parts.append("      :link-type: doc\n")
            parts.append("      :class-card: cadrumo-route-card\n\n")
            parts.append(f"      {summary}\n\n")
            parts.append("      +++\n")
            open_link = docs_chrome(
                "docs.cli.family.open_group_link",
                language,
                family=family_name,
                group=group_name,
            )
            parts.append(f"      {open_link}\n\n")

    if direct_leaf_paths:
        parts.append(_rst_heading(docs_chrome("docs.cli.family.direct_commands_heading", language), "-"))
        parts.append("\n")
        parts.append(docs_chrome("docs.cli.family.direct_commands_intro", language, family=family_name) + "\n\n")
        for path in direct_leaf_paths:
            cmd = all_commands.get(path)
            if cmd is None:
                continue
            parts.append(_render_command_section(language, path, cmd, schema_registry, heading_char="^"))

    parts.append(_rst_heading(docs_chrome("docs.cli.index.where_next_heading", language), "-"))
    parts.append("\n")
    for group_name in group_names:
        group_line = docs_chrome(
            "docs.cli.family.group_link_line",
            language,
            target=f"{family_name}/{group_name}",
            family=family_name,
            group=group_name,
        )
        parts.append(f"* {group_line}\n")
    parts.append("* " + docs_chrome("docs.cli.family.index_link_line", language) + "\n\n")

    parts.append(".. toctree::\n")
    parts.append("   :maxdepth: 1\n")
    parts.append("   :hidden:\n\n")
    for group_name in group_names:
        parts.append(f"   {family_name}/{group_name}\n")
    parts.append("\n")

    return "".join(parts)


def _render_index_page(
    language: OutputLanguage,
    family_names: list[str],
    total_leaf_count: int,
) -> str:
    """Render the ``docs/cli/index.rst`` page.

    The index carries navigation (the family grid, a where-to-go-next block)
    and root-level behaviour (global flags).  Exit codes, the TTY/JSON output
    contract, and the output-schema registry live on the companion
    ``automation`` and ``schemas`` pages.

    Args:
        family_names: Ordered list of top-level family names (e.g. ``["config", "app"]``).
        total_leaf_count: The total number of documented leaf commands.

    Returns:
        The complete RST index content.
    """
    parts: list[str] = []
    parts.append(_rst_heading(docs_chrome("docs.cli.index.title", language), "="))
    parts.append("\n")
    parts.append(".. _cli-reference-start:\n\n")
    parts.append(docs_chrome("docs.cli.index.intro", language, count=total_leaf_count) + "\n\n")
    parts.append(docs_chrome("docs.cli.index.english_help_note", language) + "\n\n")
    parts.append(docs_chrome("docs.cli.index.start_here", language) + "\n\n")

    parts.append(_rst_heading(docs_chrome("docs.cli.index.choose_family_heading", language), "-"))
    parts.append("\n")
    parts.append(".. grid:: 1 1 2 2\n")
    parts.append("   :gutter: 2\n")
    parts.append("   :class-container: cadrumo-route-grid\n\n")
    if "app" in family_names:
        parts.append("   .. grid-item-card:: ``aeat app``\n")
        parts.append("      :link: app\n")
        parts.append("      :link-type: doc\n")
        parts.append("      :class-card: cadrumo-route-card\n\n")
        parts.append("      " + docs_chrome("docs.cli.index.app_card", language) + "\n\n")
        parts.append("      +++\n")
        parts.append("      " + docs_chrome("docs.cli.index.open_family_link", language, family="app") + "\n\n")
    if "config" in family_names:
        parts.append("   .. grid-item-card:: ``aeat config``\n")
        parts.append("      :link: config\n")
        parts.append("      :link-type: doc\n")
        parts.append("      :class-card: cadrumo-route-card\n\n")
        parts.append("      " + docs_chrome("docs.cli.index.config_card", language) + "\n\n")
        parts.append("      +++\n")
        parts.append("      " + docs_chrome("docs.cli.index.open_family_link", language, family="config") + "\n\n")

    # Global flags
    parts.append(".. _cli-reference-global-flags:\n\n")
    parts.append(_rst_heading(docs_chrome("docs.cli.index.global_flags_heading", language), "-"))
    parts.append("\n")
    parts.append(docs_chrome("docs.cli.index.global_flags_intro", language) + "\n\n")
    global_flags = [
        ("``--language`` / ``--lang``", docs_chrome("docs.cli.index.flag_language", language)),
        ("``--profile``", docs_chrome("docs.cli.index.flag_profile", language)),
        ("``--version`` / ``-V``", docs_chrome("docs.cli.index.flag_version", language)),
        ("``--detail``", docs_chrome("docs.cli.index.flag_detail", language)),
        ("``--help`` / ``-h``", docs_chrome("docs.cli.index.flag_help", language)),
        ("``--format``", docs_chrome("docs.cli.index.flag_format", language)),
        ("``--quiet``", docs_chrome("docs.cli.index.flag_quiet", language)),
        ("``--verbose``", docs_chrome("docs.cli.index.flag_verbose", language)),
        ("``--debug``", docs_chrome("docs.cli.index.flag_debug", language)),
    ]
    for flag, desc in global_flags:
        parts.append(f"{flag}\n   {desc}\n\n")

    # Where to go next
    parts.append(_rst_heading(docs_chrome("docs.cli.index.where_next_heading", language), "-"))
    parts.append("\n")
    # One call per line rather than a loop over a key tuple: the locale scanner
    # matches a literal key inside the accessor call, so a key that only ever
    # appears in a collection is invisible to it and scaffold prunes it.
    parts.append("* " + docs_chrome("docs.cli.index.next_app", language) + "\n")
    parts.append("* " + docs_chrome("docs.cli.index.next_config", language) + "\n")
    parts.append("* " + docs_chrome("docs.cli.index.next_automation", language) + "\n")
    parts.append("* " + docs_chrome("docs.cli.index.next_schemas", language) + "\n")
    parts.append("* " + docs_chrome("docs.cli.index.next_howto", language) + "\n")
    parts.append("\n")

    # toctree
    parts.append(".. toctree::\n")
    parts.append("   :maxdepth: 1\n")
    parts.append("   :hidden:\n\n")
    for name in family_names:
        parts.append(f"   {name}\n")
    parts.append("   automation\n")
    parts.append("   schemas\n")
    parts.append("\n")

    return "".join(parts)


def _render_automation_page(language: OutputLanguage) -> str:
    """Render the ``docs/cli/automation.rst`` page.

    Carries the exit-code table and the TTY/JSON output contract under the
    ``cli-reference-exit-codes`` and ``cli-reference-output-contract``
    anchors so existing cross-references keep resolving.

    Returns:
        The complete RST page content.
    """
    parts: list[str] = []
    parts.append(_rst_heading(docs_chrome("docs.cli.automation.title", language), "="))
    parts.append("\n")
    parts.append(docs_chrome("docs.cli.automation.intro", language) + "\n\n")

    # Exit codes
    parts.append(".. _cli-reference-exit-codes:\n\n")
    parts.append(_rst_heading(docs_chrome("docs.cli.automation.exit_codes_heading", language), "-"))
    parts.append("\n")
    exit_code_table = [
        ("0", docs_chrome("docs.cli.automation.exit_success", language)),
        ("1", docs_chrome("docs.cli.automation.exit_general", language)),
        ("2", docs_chrome("docs.cli.automation.exit_usage", language)),
        ("3", docs_chrome("docs.cli.automation.exit_auth", language)),
        ("4", docs_chrome("docs.cli.automation.exit_not_found", language)),
        ("5", docs_chrome("docs.cli.automation.exit_conflict", language)),
        ("6", docs_chrome("docs.cli.automation.exit_validation", language)),
        ("7", docs_chrome("docs.cli.automation.exit_unavailable", language)),
        ("8", docs_chrome("docs.cli.automation.exit_forbidden", language)),
        ("9", docs_chrome("docs.cli.automation.exit_internal", language)),
        ("10", docs_chrome("docs.cli.automation.exit_partial", language)),
    ]
    parts.append(".. list-table::\n")
    parts.append("   :header-rows: 1\n")
    parts.append("   :widths: 10 90\n\n")
    parts.append("   * - " + docs_chrome("docs.cli.automation.table_code_header", language) + "\n")
    parts.append("     - " + docs_chrome("docs.cli.automation.table_meaning_header", language) + "\n")
    for code, meaning in exit_code_table:
        parts.append(f"   * - ``{code}``\n")
        parts.append(f"     - {meaning}\n")
    parts.append("\n")

    # TTY contract
    parts.append(".. _cli-reference-output-contract:\n\n")
    parts.append(_rst_heading(docs_chrome("docs.cli.automation.output_contract_heading", language), "-"))
    parts.append("\n")
    parts.append(
        docs_chrome(
            "docs.cli.automation.output_contract_body",
            language,
            envelope="{schema_version, command, result, warnings}",
        )
        + "\n\n",
    )

    return "".join(parts)


def _render_schemas_page(language: OutputLanguage, schema_registry: Mapping[str, object]) -> str:
    """Render the ``docs/cli/schemas.rst`` page.

    Carries the output-schema registry listing under the
    ``cli-reference-output-schemas`` anchor so existing cross-references
    keep resolving.

    Args:
        schema_registry: The process-global schema registry.

    Returns:
        The complete RST page content.
    """
    parts: list[str] = []
    parts.append(".. _cli-reference-output-schemas:\n\n")
    parts.append(_rst_heading(docs_chrome("docs.cli.schemas.title", language), "="))
    parts.append("\n")
    envelope_keys = sorted(k for k in schema_registry if k not in _GROUP_CALLBACK_EMIT_KEYS)
    group_keys = sorted(_GROUP_CALLBACK_EMIT_KEYS & set(schema_registry))
    parts.append(docs_chrome("docs.cli.schemas.tooling_note", language) + "\n\n")
    group_entries = docs_chrome(
        "docs.cli.schemas.group_entries",
        language,
        count=len(group_keys),
        keys=", ".join(f"``{k}``" for k in group_keys),
    )
    parts.append(
        docs_chrome("docs.cli.schemas.summary", language, count=len(envelope_keys), groups=group_entries) + "\n\n",
    )
    for key in envelope_keys:
        schema_cls = schema_registry[key]
        schema_name = (
            f"{schema_cls.__module__}.{schema_cls.__name__}" if isinstance(schema_cls, type) else repr(schema_cls)
        )
        parts.append(f"* ``{key}`` → ``{schema_name}``\n")
    parts.append("\n")

    return "".join(parts)


def _write_text_if_changed(path: Path, content: str) -> None:
    """Write ``content`` only when it differs from the file already on disk.

    Args:
        path: Destination path.
        content: Text to persist using the project UTF-8 encoding.
    """
    if path.is_file() and path.read_text(encoding=UTF_8_ENCODING) == content:
        return
    # Force LF so generated pages are byte-identical across platforms; the
    # default newline translation emits CRLF on Windows.
    path.write_text(content, encoding=UTF_8_ENCODING, newline="\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_cli_reference(docs_root: Path) -> dict[str, str]:
    """Materialise the CLI tree and render per-family RST pages under ``docs_root/cli/``.

    Imports :mod:`cadrumo.entrypoints.cli` in the calling process, forces every
    lazy subcommand to load, asserts no fallback surface is present, then
    renders one RST page per top-level family plus an ``index.rst`` and the
    companion ``automation.rst`` and ``schemas.rst`` pages.

    This function pins the output-language setting to English before importing the
    CLI tree so that ``tr()`` keys resolve to English strings for deterministic
    reference output. The subprocess entry point :func:`main` provides a clean
    interpreter boundary for callers that cannot guarantee the CLI has not already
    been imported.

    Args:
        docs_root: The project documentation root (the directory that contains
            ``index.rst``).  A ``cli/`` subdirectory is created or overwritten.

    Returns:
        A mapping from relative path (e.g. ``"cli/index.rst"``) to rendered
        RST content, mirroring what was written to disk.
    """
    from cadrumo.core.config import override_settings

    with override_settings(cadrumo_output_language="en"):
        return _generate_cli_reference_loaded(docs_root)


def _generate_cli_reference_loaded(docs_root: Path) -> dict[str, str]:
    """Render the CLI reference after the caller has pinned output language.

    Two languages are in play and they are not the same one. The CLI's own help
    text is captured in English, pinned by ``CADRUMO_OUTPUT_LANGUAGE`` before any
    command module imports, because it is the command surface rendered as
    evidence. The page's own words follow ``CADRUMO_DOCS_LANGUAGE``, so a Spanish
    reader gets Spanish headings and labels around that English help, and the
    page says so.
    """
    import click

    from cadrumo.application.operator_surface import ACCEPTED_ROOTS
    from cadrumo.core.i18n._render import clear_output_language_cache

    # Function-local: dev.docs.build imports this module, so a module-level
    # import would close the cycle. The target is the owning module's public
    # name, read exactly as if it were a top-level import.
    from .build import docs_build_language

    language = docs_build_language(os.environ)

    clear_output_language_cache()

    from cadrumo.entrypoints.cli import full_command_tree
    from cadrumo.entrypoints.cli._command_runtime import resolve_deferred_target

    schema_registry = {
        identity: resolve_deferred_target(spec.result_schema.target)
        for identity, spec in COMMAND_GRAPH.by_schema_identity().items()
        if spec.result_schema.target is not None
    }

    root_cmd = full_command_tree()

    # Collect every command node keyed by its path tuple using _collect_commands,
    # which builds paths correctly with the root name as the first element.
    all_nodes = _collect_commands(root_cmd)

    # Determine which top-level families are accepted, and the canonical
    # verb ordering each root surface declares for its own children.
    accepted_root_names = {r.name.value for r in ACCEPTED_ROOTS}
    required_children_by_family = {r.name.value: r.required_children for r in ACCEPTED_ROOTS}

    # Identify leaf paths per family (used only for the top index page's total
    # leaf count; the per-group pages below walk the tree directly).
    leaf_paths_by_family: dict[str, list[tuple[str, ...]]] = {}
    for path, cmd in sorted(all_nodes.items()):
        if isinstance(cmd, click.Group) or hasattr(cmd, "list_commands"):
            continue
        # path = ("aeat", family, ...)
        if len(path) < 2:
            continue
        family = path[1]
        if family not in accepted_root_names:
            continue
        leaf_paths_by_family.setdefault(family, []).append(path)

    # Render pages.
    output_dir = docs_root / "cli"
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered: dict[str, str] = {}
    family_order = sorted(leaf_paths_by_family.keys())
    total_leaves = sum(len(v) for v in leaf_paths_by_family.values())

    for family in family_order:
        family_path = ("aeat", family)
        family_cmd = all_nodes[family_path]
        with click.Context(family_cmd, info_name=" ".join(family_path)) as family_ctx:
            child_names = set(family_cmd.list_commands(family_ctx))
        required_order = required_children_by_family.get(family, ())
        ordered_names = [name for name in required_order if name in child_names]
        ordered_names.extend(sorted(child_names - set(ordered_names)))

        group_names: list[str] = []
        direct_leaf_paths: list[tuple[str, ...]] = []
        for name in ordered_names:
            child_path = (*family_path, name)
            child_cmd = all_nodes[child_path]
            if _is_group(child_cmd):
                group_names.append(name)
            else:
                direct_leaf_paths.append(child_path)

        group_dir = output_dir / family
        if group_names:
            group_dir.mkdir(parents=True, exist_ok=True)
        for group_name in group_names:
            group_path = (*family_path, group_name)
            group_cmd = all_nodes[group_path]
            group_content = _render_verb_group_page(language, group_path, group_cmd, schema_registry)
            rel_path = f"{_verb_group_page_stem(family, group_name)}.rst"
            rendered[rel_path] = group_content
            _write_text_if_changed(group_dir / f"{group_name}.rst", group_content)

        index_page_content = _render_family_index_page(
            language,
            family,
            group_names,
            direct_leaf_paths,
            schema_registry,
            all_nodes,
        )
        rel_path = f"{_family_index_page_stem(family)}.rst"
        rendered[rel_path] = index_page_content
        _write_text_if_changed(output_dir / f"{family}.rst", index_page_content)

    index_content = _render_index_page(
        language,
        family_names=family_order,
        total_leaf_count=total_leaves,
    )
    rendered["cli/index.rst"] = index_content
    _write_text_if_changed(output_dir / "index.rst", index_content)

    automation_content = _render_automation_page(language)
    rendered["cli/automation.rst"] = automation_content
    _write_text_if_changed(output_dir / "automation.rst", automation_content)

    schemas_content = _render_schemas_page(language, schema_registry)
    rendered["cli/schemas.rst"] = schemas_content
    _write_text_if_changed(output_dir / "schemas.rst", schemas_content)

    return rendered


def generate_cli_reference_in_subprocess(docs_root: Path) -> dict[str, str]:
    """Spawn a fresh interpreter with ``CADRUMO_OUTPUT_LANGUAGE=en`` and generate the reference.

    This is the clean guarantee that ``tr()`` resolves to English strings: a
    fresh subprocess sees the pinned language before any CLI module is imported,
    so every ``help=tr(...)`` call stores the English string in the Typer
    object.  After the subprocess writes the pages the parent reads them back
    and returns them as a dict.

    Args:
        docs_root: Absolute path to the documentation root directory.

    Returns:
        A mapping from relative path (e.g. ``"cli/index.rst"``) to RST content.

    Raises:
        RuntimeError: When the subprocess exits with a non-zero code, indicating
            a generation failure (e.g. a fallback surface was detected).
    """
    code = textwrap.dedent(
        f"""
        from pathlib import Path
        from dev.docs.cli_reference import generate_cli_reference
        docs_root = Path({str(docs_root)!r})
        generate_cli_reference(docs_root)
        """,
    )

    with TemporaryDirectory(prefix="cadrumo-cli-reference-") as storage_root:
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=_reference_subprocess_environment(Path(storage_root)),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    if result.returncode != 0:
        # BROAD-EXCEPT-RATIONALE-SUBPROCESS-GUARD:
        # subprocess invocation failure surfaced as RuntimeError for operator
        # diagnostics; not on the operator-facing CadrumoError contract.
        raise RuntimeError(f"CLI reference generation subprocess failed (exit {result.returncode}):\n{result.stderr}")

    # Read back what the subprocess wrote. Recursive (`rglob`, not `glob`)
    # because per-verb-group pages live in family subdirectories
    # (``cli/app/ledger.rst``), not only flat under ``cli/``.
    output_dir = docs_root / "cli"
    rendered: dict[str, str] = {}
    for rst_file in scan_directory(output_dir, pattern="*.rst", recursive=True):
        rel = f"cli/{rst_file.relative_to(output_dir).as_posix()}"
        rendered[rel] = rst_file.read_text(encoding=UTF_8_ENCODING)
    return rendered


def collect_live_leaf_paths_in_subprocess() -> list[str]:
    """Return all live leaf command paths by spawning a fresh interpreter.

    Guarantees that the CLI tree is materialised with ``CADRUMO_OUTPUT_LANGUAGE=en``
    before any CLI module is imported, mirroring the generation subprocess.

    Returns:
        A sorted list of normalised registry-key strings for every live leaf
        command (e.g. ``["config.auth.clear", "ledger.add", ...]``).

    Raises:
        RuntimeError: When the subprocess exits with a non-zero code,
            indicating that the CLI tree could not be materialised.
    """
    code = textwrap.dedent(
        """
        from cadrumo.entrypoints.cli._command_specs import COMMAND_GRAPH

        for node in COMMAND_GRAPH.nodes():
            if node.spec.kind == "leaf":
                path = node.path[1:] if node.path[:1] == ("aeat",) else node.path
                print(".".join(path))
        """,
    )

    with TemporaryDirectory(prefix="cadrumo-cli-reference-") as storage_root:
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=_reference_subprocess_environment(Path(storage_root)),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    if result.returncode != 0:
        # BROAD-EXCEPT-RATIONALE-SUBPROCESS-GUARD:
        # subprocess invocation failure surfaced as RuntimeError for operator
        # diagnostics; not on the operator-facing CadrumoError contract.
        raise RuntimeError(f"CLI leaf-path collection subprocess failed (exit {result.returncode}):\n{result.stderr}")
    return [line for line in result.stdout.splitlines() if line.strip()]


__all__ = [
    "cli_reference_page_for_command",
    "collect_live_leaf_paths_in_subprocess",
    "generate_cli_reference",
    "generate_cli_reference_in_subprocess",
]
