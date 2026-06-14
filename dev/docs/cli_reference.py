"""CLI reference generator for the ``aeat`` command tree.

Materialises the full Click command tree from ``typer.main.get_command(app)``,
walks every group and leaf command (forcing lazy-module imports), and renders
per-family RST pages under ``docs/cli/``.  An ``index.rst`` page carries
navigation (the family grid, a where-to-go-next block) plus root-level
behaviour (global flags); companion pages carry the automation contract
(``automation.rst``: exit codes, TTY/JSON output) and the output-schema
registry (``schemas.rst``).

The generator is documentation tooling.  It lives under ``dev/docs`` and
introspects the production package from outside rather than being part of the
``aeat`` runtime package.

Language pinning
----------------
Help strings are ``tr()`` values resolved at module-import time and stored as
plain strings on the Typer objects, so the output language MUST be pinned to
``en`` *before* any CLI command module is imported.  Call
:func:`generate_cli_reference` from a subprocess with
``AEAT_OUTPUT_LANGUAGE=en`` in its environment (the clean guarantee — mirroring
the lazy-tree subprocess tests) or set the variable before importing
:mod:`aeat.entrypoints.cli`.

Fallback-surface guard
----------------------
The ``aeat`` CLI's :func:`_import_failure_surface` replaces a subtree with a
stub that emits ``cli.root.unavailable_app_help`` when an optional dependency
is missing.  :func:`generate_cli_reference` walks the entire tree and asserts
that no subtree carries that fallback help text, so a missing dependency causes
the generator to raise rather than silently emitting a degraded reference.

Accepted-surface contract
-------------------------
Only surfaces declared in
:data:`~aeat.application.operator_surface.ACCEPTED_ROOTS` are documented as
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
from typing import TYPE_CHECKING

from aeat.core.external_constants import UTF_8_ENCODING

if TYPE_CHECKING:
    import click

#: Sentinel text that the CLI's import-failure fallback emits (the rendered
#: ``cli.root.unavailable_app_help`` string). The generator walks the
#: materialised tree and raises when any command carries this marker so a
#: missing optional dependency surfaces as an error rather than a silently
#: degraded reference page. The marker is the distinctive full phrase rather
#: than the bare word "unavailable" so it cannot collide with a legitimately
#: sealed command whose help honestly says it is unavailable (e.g. the
#: apoderado ``check`` live-read verb).
_FALLBACK_MARKER: str = "not available in the current configuration"

#: Group-callback emit sites — keys registered under a group callback rather
#: than a leaf command.  These are excluded from the per-command reference
#: pages (they are group landing surfaces, not operator-invokable leaves) but
#: are listed on the output-schema registry page (``schemas.rst``).
_GROUP_CALLBACK_EMIT_KEYS: frozenset[str] = frozenset({"root.status", "root.app", "ledger.participation"})

#: Command-path normalisation rules that mirror the conformance-test normaliser
#: in :mod:`aeat.entrypoints.cli.test_json_schema_conformance`.
_APP_NAMESPACE_FLATTEN: frozenset[str] = frozenset({"ledger", "modelo", "overview", "registry", "review"})
_APP_NAMESPACE_PASSTHROUGH: frozenset[str] = frozenset({"live"})
_PATH_KEY_OVERRIDES: dict[str, str] = {
    "config.profile.history": "config.bucket.history",
}


# ---------------------------------------------------------------------------
# Internal helpers — tree materialisation
# ---------------------------------------------------------------------------


def _force_lazy_imports(app: object) -> None:
    """Materialise every lazily-registered subcommand reachable from ``app``.

    Args:
        app: The root :class:`typer.Typer` instance.
    """
    import typer

    from aeat.entrypoints.cli._command_suggestions import _LAZY_REGISTRY

    seen: set[int] = set()
    # TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
    # Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
    pending: list[typer.Typer] = [app]  # type: ignore[valid-type]
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        group_name = node.info.name or ""
        for lazy in _LAZY_REGISTRY.get(group_name, {}).values():
            lazy.load()
        for group in node.registered_groups:
            if group.typer_instance is not None:
                pending.append(group.typer_instance)


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _assert_no_fallback_surfaces(root: click.Command) -> None:  # type: ignore[name-defined]
    """Walk the tree and raise if any subtree is an import-failure fallback.

    The CLI's :func:`_import_failure_surface` helper replaces a missing
    optional dependency's subtree with a stub whose help text contains
    ``"unavailable"``.  A degraded reference is worse than a failed build.

    Args:
        root: The materialised root Click command (name must be set).

    Raises:
        RuntimeError: When any subtree carries the fallback marker text.
    """
    all_nodes = _collect_commands(root)
    degraded = [" ".join(path) for path, cmd in all_nodes.items() if _FALLBACK_MARKER in (cmd.help or "").lower()]
    if degraded:
        paths = ", ".join(degraded)
        # BROAD-EXCEPT-RATIONALE-SUBPROCESS-GUARD:
        # subprocess invocation failure surfaced as RuntimeError for operator
        # diagnostics; not on the operator-facing AeatError contract.
        raise RuntimeError(
            f"Import-failure fallback detected in CLI subtree(s): {paths}. "
            "Ensure all optional dependencies are installed before generating the reference.",
        )


# ---------------------------------------------------------------------------
# Internal helpers — command-path normalisation
# ---------------------------------------------------------------------------


def _normalise_command_path(path: tuple[str, ...]) -> str:
    """Project a Click leaf-command path onto the schema-registry key convention.

    Mirrors the normaliser in
    :mod:`aeat.entrypoints.cli.test_json_schema_conformance`.

    Args:
        path: Tuple of command name tokens from the root, e.g.
            ``("aeat", "app", "modelo", "work", "calculate")``.

    Returns:
        The dot-joined registry key, e.g. ``"modelo.work.calculate"``.
    """
    tokens = [token.replace("-", "_") for token in path]
    if tokens and tokens[0] == "aeat":
        tokens = tokens[1:]
    if len(tokens) >= 2 and tokens[0] == "app":
        head = tokens[1]
        if head in _APP_NAMESPACE_FLATTEN:
            tokens = tokens[1:]
        elif head in _APP_NAMESPACE_PASSTHROUGH:
            pass  # keep ``app.`` prefix
    normalised = ".".join(tokens)
    return _PATH_KEY_OVERRIDES.get(normalised, normalised)


# ---------------------------------------------------------------------------
# Internal helpers — tree walking
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
# Internal helpers — RST rendering
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
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _render_param_table(params: list[click.Parameter]) -> str:  # type: ignore[name-defined]
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
        kind = "Argument" if isinstance(param, click.Argument) else "Option"
        help_text = (param.help or "").strip() or "No description."
        req_label = "required" if required else "optional"
        sections.append(f"{opt_str}\n   *{kind}, {req_label}.* {help_text}\n")
    return "\n".join(sections) if sections else ""


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _render_command_section(
    path: tuple[str, ...],
    # TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click param annotation same as above
    cmd: click.Command,  # type: ignore[name-defined]
    schema_registry: dict[str, object],
) -> str:
    """Render the RST section for a single leaf command.

    Args:
        path: The full command path tuple, e.g. ``("aeat", "app", "modelo", "work", "calculate")``.
        cmd: The materialised Click command.
        schema_registry: The process-global schema registry for resolving
            the output schema, if any.

    Returns:
        A RST string describing the command.
    """
    full_path = " ".join(path)
    registry_key = _normalise_command_path(path)
    help_text = (cmd.help or "").strip() or "No description available."
    schema_cls = schema_registry.get(registry_key)

    parts: list[str] = []
    parts.append(_rst_heading(f"``{full_path}``", "~"))
    parts.append(f"{help_text}\n\n")
    parts.append(f"**Command path:** ``{full_path}``\n\n")
    parts.append(f"**Registry key:** ``{registry_key}``\n\n")

    param_table = _render_param_table(cmd.params)
    if param_table:
        parts.append("**Parameters**\n\n")
        parts.append(param_table)
        parts.append("\n")

    if schema_cls is not None:
        schema_name = f"{schema_cls.__module__}.{schema_cls.__name__}"
        parts.append("**Output schema**\n\n")
        parts.append(
            f"This command emits a ``SchemaEnvelope`` whose ``result`` field is"
            f" validated against ``{schema_name}``.\n\n",
        )
    else:
        parts.append("**Output schema**\n\n")
        parts.append(
            "This command emits a bare payload (not yet envelope-wrapped)."
            " Output structure is command-specific; consult ``--help`` for details.\n\n",
        )

    return "".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers — per-family page rendering
# ---------------------------------------------------------------------------


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _render_family_page(
    family_name: str,
    leaf_paths: list[tuple[str, ...]],
    schema_registry: dict[str, object],
    # TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
    # Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
    all_commands: dict[tuple[str, ...], click.Command],  # type: ignore[name-defined]
) -> str:
    """Render a full RST page for one top-level command family.

    Args:
        family_name: The family name, e.g. ``"config"`` or ``"app"``.
        leaf_paths: All leaf-command paths belonging to this family.
        schema_registry: The process-global schema registry.
        all_commands: Mapping from path tuple to Click command object for
            every node collected from the tree.

    Returns:
        The complete RST page content.
    """
    title = f"``aeat {family_name}`` — command reference"
    parts: list[str] = []
    parts.append(_rst_heading(title, "="))
    parts.append("\n")
    parts.append(
        f"This page documents every leaf command under ``aeat {family_name}``."
        f" Help strings are rendered in English; the CLI respects the active"
        f" output-language setting at runtime.\n\n",
    )

    for path in leaf_paths:
        cmd = all_commands.get(path)
        if cmd is None:
            continue
        parts.append(_render_command_section(path, cmd, schema_registry))

    return "".join(parts)


def _render_index_page(
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
    parts.append(_rst_heading("CLI reference", "="))
    parts.append("\n")
    parts.append(".. _cli-reference-start:\n\n")
    parts.append(
        "The ``aeat`` CLI exposes two top-level command families: ``config`` (local"
        " configuration, profile lifecycle, diagnostics) and ``app`` (operational tax"
        f" workflow). This reference documents all {total_leaf_count} leaf commands.\n\n",
    )
    parts.append(
        "Help strings are rendered in English. At runtime the CLI respects the active"
        " output-language setting (``--language`` / ``AEAT_OUTPUT_LANGUAGE``).\n\n",
    )
    parts.append(
        "Start with the family links below. Use the generated command-family pages"
        " for exact flags, arguments, registry keys, and output schemas; use this"
        " page for root-level behavior that applies across commands.\n\n",
    )

    parts.append(_rst_heading("Choose a command family", "-"))
    parts.append("\n")
    parts.append(".. grid:: 1 1 2 2\n")
    parts.append("   :gutter: 2\n")
    parts.append("   :class-container: aeat-route-grid\n\n")
    if "app" in family_names:
        parts.append("   .. grid-item-card:: ``aeat app``\n")
        parts.append("      :link: app\n")
        parts.append("      :link-type: doc\n")
        parts.append("      :class-card: aeat-route-card\n\n")
        parts.append("      Operational workflow commands: ledger work, modelos, filing")
        parts.append(" calendars, registry checks, live captures, and review queues.\n\n")
        parts.append("      +++\n")
        parts.append("      Open ``aeat app`` reference\n\n")
    if "config" in family_names:
        parts.append("   .. grid-item-card:: ``aeat config``\n")
        parts.append("      :link: config\n")
        parts.append("      :link-type: doc\n")
        parts.append("      :class-card: aeat-route-card\n\n")
        parts.append("      Local setup and maintenance commands: profiles, authentication,")
        parts.append(" Google integration, repair checks, and reset surfaces.\n\n")
        parts.append("      +++\n")
        parts.append("      Open ``aeat config`` reference\n\n")

    # Global flags
    parts.append(".. _cli-reference-global-flags:\n\n")
    parts.append(_rst_heading("Global flags", "-"))
    parts.append("\n")
    parts.append("These flags are accepted by the ``aeat`` root command and apply to every invocation.\n\n")
    global_flags = [
        ("``--language`` / ``--lang``", "Override the output language (``es``, ``en``, ``ca``, ``hu``)."),
        ("``--profile``", "Activate a named profile for this invocation."),
        ("``--version`` / ``-V``", "Print the package version and exit."),
        ("``--detail``", "Print extended version information including registry summary."),
        ("``--help`` / ``-h``", "Print the curated help document and exit."),
        ("``--format``", "Output format (``text`` or ``json``)."),
        ("``--quiet``", "Suppress informational output."),
        ("``--verbose``", "Enable verbose output."),
        ("``--debug``", "Enable debug-level logging."),
    ]
    for flag, desc in global_flags:
        parts.append(f"{flag}\n   {desc}\n\n")

    # Where to go next
    parts.append(_rst_heading("Where to go next", "-"))
    parts.append("\n")
    parts.append("* Open :doc:`app` for the operational workflow commands.\n")
    parts.append("* Open :doc:`config` for the local setup and maintenance commands.\n")
    parts.append("* Open :doc:`automation` for exit codes and the TTY/JSON output contract.\n")
    parts.append("* Open :doc:`schemas` for the JSON output-schema registry.\n")
    parts.append("* Open :doc:`/how-to/index` for task-focused guides.\n")
    parts.append("* Open :doc:`/tutorials/index` for step-by-step walkthroughs.\n\n")

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


def _render_automation_page() -> str:
    """Render the ``docs/cli/automation.rst`` page.

    Carries the exit-code table and the TTY/JSON output contract under the
    ``cli-reference-exit-codes`` and ``cli-reference-output-contract``
    anchors so existing cross-references keep resolving.

    Returns:
        The complete RST page content.
    """
    parts: list[str] = []
    parts.append(_rst_heading("Exit codes and output contract", "="))
    parts.append("\n")
    parts.append(
        "Use this page when scripting ``aeat`` invocations: it documents the"
        " process exit codes and the TTY/JSON output behavior shared by every"
        " command.\n\n",
    )

    # Exit codes
    parts.append(".. _cli-reference-exit-codes:\n\n")
    parts.append(_rst_heading("Exit codes", "-"))
    parts.append("\n")
    exit_code_table = [
        ("0", "Success."),
        ("1", "General error or refused operation."),
        ("2", "Invalid CLI usage (bad flag, missing argument)."),
        ("3", "Authentication required or credentials expired."),
        ("4", "Resource not found."),
        ("5", "Conflict or precondition failure."),
        ("6", "Validation error in user-supplied data."),
        ("7", "External service unavailable."),
        ("8", "Operation not permitted by policy."),
        ("9", "Unexpected internal error."),
        ("10", "Partial success (some items succeeded, some failed)."),
    ]
    parts.append(".. list-table::\n")
    parts.append("   :header-rows: 1\n")
    parts.append("   :widths: 10 90\n\n")
    parts.append("   * - Code\n")
    parts.append("     - Meaning\n")
    for code, meaning in exit_code_table:
        parts.append(f"   * - ``{code}``\n")
        parts.append(f"     - {meaning}\n")
    parts.append("\n")

    # TTY contract
    parts.append(".. _cli-reference-output-contract:\n\n")
    parts.append(_rst_heading("TTY and JSON output contract", "-"))
    parts.append("\n")
    parts.append(
        "When output is to a TTY the CLI emits human-readable rich text."
        " When ``--format json`` is passed (or when output is redirected) the CLI"
        " emits a single JSON document per invocation. Commands that have adopted the"
        " ``SchemaEnvelope`` wrap their result as"
        " ``{schema_version, command, result, warnings}``."
        " Commands not yet migrated emit their payload directly.\n\n",
    )

    return "".join(parts)


def _render_schemas_page(schema_registry: Mapping[str, object]) -> str:
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
    parts.append(_rst_heading("Output schema registry", "="))
    parts.append("\n")
    envelope_keys = sorted(k for k in schema_registry if k not in _GROUP_CALLBACK_EMIT_KEYS)
    group_keys = sorted(_GROUP_CALLBACK_EMIT_KEYS & set(schema_registry))
    parts.append(
        "This page is mainly for tooling authors. If you are running commands"
        " manually, the :doc:`family pages <index>` are usually the better entry"
        " point.\n\n",
    )
    parts.append(
        f"The following {len(envelope_keys)} command paths have a registered"
        f" ``OutputSchema``.  Group-callback surfaces"
        f" ({len(group_keys)} entries: {', '.join(f'``{k}``' for k in group_keys)})"
        f" are listed separately.\n\n",
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

    Imports :mod:`aeat.entrypoints.cli` in the calling process, forces every
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
    from aeat.core.config import override_settings

    with override_settings(aeat_output_language="en"):
        return _generate_cli_reference_loaded(docs_root)


def _generate_cli_reference_loaded(docs_root: Path) -> dict[str, str]:
    """Render the CLI reference after the caller has pinned output language."""
    import click
    from typer.main import get_command as _typer_get_command

    from aeat.application.operator_surface import ACCEPTED_ROOTS
    from aeat.core.i18n._render import clear_output_language_cache
    from aeat.core.json_contract import SCHEMA_REGISTRY

    clear_output_language_cache()

    # Import every payload module so their @register_schema decorators populate
    # SCHEMA_REGISTRY.  The CLI loads these lazily at dispatch time; the generator
    # must trigger them explicitly before inspecting the registry.
    from aeat.entrypoints.cli import (
        _app_live_payloads,
        _config_payloads,
        _ledger_payloads,
        _ledger_rule_payloads,
        _modelo_payloads,
        _modelo_payloads_m036,
        _overview_payloads,
        _payloads_modelo_reconcile,
        _registry_corpus_payloads,
        _registry_payloads,
        _review_payloads,
        _root_payloads,
        app,
    )
    from aeat.entrypoints.cli._config import (
        _google_payloads,
        _profile_censo_payloads,
    )

    payload_schema_modules = (
        _app_live_payloads,
        _config_payloads,
        _ledger_payloads,
        _ledger_rule_payloads,
        _modelo_payloads,
        _modelo_payloads_m036,
        _overview_payloads,
        _payloads_modelo_reconcile,
        _registry_corpus_payloads,
        _registry_payloads,
        _review_payloads,
        _root_payloads,
        _google_payloads,
        _profile_censo_payloads,
    )
    if not all(getattr(module, "__name__", "") for module in payload_schema_modules):
        raise RuntimeError("CLI payload schema modules failed to load")

    # Materialise every lazy subtree before the tree walk.
    _force_lazy_imports(app)

    root_cmd = _typer_get_command(app)
    root_cmd.name = app.info.name or "aeat"

    _assert_no_fallback_surfaces(root_cmd)

    # Collect every command node keyed by its path tuple using _collect_commands,
    # which builds paths correctly with the root name as the first element.
    all_nodes = _collect_commands(root_cmd)

    # Determine which top-level families are accepted.
    accepted_root_names = {r.name.value for r in ACCEPTED_ROOTS}

    # Identify leaf paths per family.
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

    # Sort leaves within each family.
    for family in leaf_paths_by_family:
        leaf_paths_by_family[family].sort()

    # Render pages.
    output_dir = docs_root / "cli"
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered: dict[str, str] = {}
    family_order = sorted(leaf_paths_by_family.keys())
    total_leaves = sum(len(v) for v in leaf_paths_by_family.values())

    for family in family_order:
        leaves = leaf_paths_by_family[family]
        content = _render_family_page(family, leaves, SCHEMA_REGISTRY, all_nodes)
        rel_path = f"cli/{family}.rst"
        rendered[rel_path] = content
        _write_text_if_changed(output_dir / f"{family}.rst", content)

    index_content = _render_index_page(
        family_names=family_order,
        total_leaf_count=total_leaves,
    )
    rendered["cli/index.rst"] = index_content
    _write_text_if_changed(output_dir / "index.rst", index_content)

    automation_content = _render_automation_page()
    rendered["cli/automation.rst"] = automation_content
    _write_text_if_changed(output_dir / "automation.rst", automation_content)

    schemas_content = _render_schemas_page(SCHEMA_REGISTRY)
    rendered["cli/schemas.rst"] = schemas_content
    _write_text_if_changed(output_dir / "schemas.rst", schemas_content)

    return rendered


def generate_cli_reference_in_subprocess(docs_root: Path) -> dict[str, str]:
    """Spawn a fresh interpreter with ``AEAT_OUTPUT_LANGUAGE=en`` and generate the reference.

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
    env = dict(os.environ)
    env["AEAT_OUTPUT_LANGUAGE"] = "en"

    code = textwrap.dedent(
        f"""
        from pathlib import Path
        from dev.docs.cli_reference import generate_cli_reference
        docs_root = Path({str(docs_root)!r})
        generate_cli_reference(docs_root)
        """,
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        # BROAD-EXCEPT-RATIONALE-SUBPROCESS-GUARD:
        # subprocess invocation failure surfaced as RuntimeError for operator
        # diagnostics; not on the operator-facing AeatError contract.
        raise RuntimeError(f"CLI reference generation subprocess failed (exit {result.returncode}):\n{result.stderr}")

    # Read back what the subprocess wrote.
    output_dir = docs_root / "cli"
    rendered: dict[str, str] = {}
    for rst_file in sorted(output_dir.glob("*.rst")):
        rel = f"cli/{rst_file.name}"
        rendered[rel] = rst_file.read_text(encoding=UTF_8_ENCODING)
    return rendered


def collect_live_leaf_paths_in_subprocess() -> list[str]:
    """Return all live leaf command paths by spawning a fresh interpreter.

    Guarantees that the CLI tree is materialised with ``AEAT_OUTPUT_LANGUAGE=en``
    before any CLI module is imported, mirroring the generation subprocess.

    Returns:
        A sorted list of normalised registry-key strings for every live leaf
        command (e.g. ``["config.auth.clear", "ledger.add", ...]``).

    Raises:
        RuntimeError: When the subprocess exits with a non-zero code,
            indicating that the CLI tree could not be materialised.
    """
    env = dict(os.environ)
    env["AEAT_OUTPUT_LANGUAGE"] = "en"

    code = textwrap.dedent(
        """
        import click
        from typer.main import get_command as _typer_get_command
        from aeat.entrypoints.cli import app
        from aeat.entrypoints.cli._command_suggestions import _LAZY_REGISTRY
        from dev.docs.cli_reference import (
            _force_lazy_imports,
            _collect_leaf_paths,
            _normalise_command_path,
        )

        _force_lazy_imports(app)
        root = _typer_get_command(app)
        root.name = app.info.name or 'aeat'
        leaves = _collect_leaf_paths(root)
        for path in sorted(set(_normalise_command_path(p) for p in leaves)):
            print(path)
        """,
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        # BROAD-EXCEPT-RATIONALE-SUBPROCESS-GUARD:
        # subprocess invocation failure surfaced as RuntimeError for operator
        # diagnostics; not on the operator-facing AeatError contract.
        raise RuntimeError(f"CLI leaf-path collection subprocess failed (exit {result.returncode}):\n{result.stderr}")
    return [line for line in result.stdout.splitlines() if line.strip()]


__all__ = [
    "collect_live_leaf_paths_in_subprocess",
    "generate_cli_reference",
    "generate_cli_reference_in_subprocess",
]
