"""CLI reference generator for the ``aeat`` command tree.

Projects the immutable production command graph and renders
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
Help strings are resolved from each authored command specification, so the output language MUST be pinned to
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

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import UTF_8_ENCODING, OutputLanguage
from cadrumo.entrypoints.cli.command_api import command_spec_for_path, command_spec_nodes

from ._locale_chrome import docs_chrome

if TYPE_CHECKING:
    pass

#: Group-callback emit sites - keys registered under a group callback rather
#: than a leaf command.  These are excluded from the per-command reference
#: pages (they are group landing surfaces, not operator-invokable leaves) but
#: are listed on the output-schema registry page (``schemas.rst``).
_GROUP_CALLBACK_EMIT_KEYS: frozenset[str] = frozenset(
    node.spec.result_schema.identity
    for node in command_spec_nodes()
    if node.spec.kind == "group" and node.spec.result_schema.identity is not None
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
# Internal graph-projection helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Internal helpers - command-path normalisation
# ---------------------------------------------------------------------------


def _normalise_command_path(path: tuple[str, ...]) -> str:
    """Return the result identity authored for an exact command-graph path."""
    rooted = path if path[:1] == ("aeat",) else ("aeat", *path)
    identity = command_spec_for_path(rooted).result_schema.identity
    if identity is None:
        raise LookupError(f"command path has no result identity: {path!r}")
    return identity


# ---------------------------------------------------------------------------
# Internal helpers - tree walking
# ---------------------------------------------------------------------------


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _rst_heading(text: str, char: str) -> str:
    return f"{text}\n{char * len(text)}\n"


def _render_graph_command(language: OutputLanguage, path: tuple[str, ...], spec: object) -> str:
    """Render one authored command specification without runtime tree inspection."""
    from cadrumo.core.i18n import tr
    from cadrumo.entrypoints.cli.command_api import ArgumentSpec, CommandSpec

    if not isinstance(spec, CommandSpec):
        raise TypeError("CLI reference received a non-CommandSpec node")
    parts = [_rst_heading(" ".join(path), "-"), "\n", tr(spec.help_key.value), "\n\n"]
    if spec.parameters:
        parts.append(docs_chrome("docs.cli.command.parameters_heading", language) + "\n\n")
    for parameter in spec.parameters:
        is_argument = isinstance(parameter, ArgumentSpec)
        declaration = parameter.name if is_argument else " / ".join(parameter.declarations)
        required = parameter.default.kind.value == "required"

        # The help key NAMES the operator-facing sentence rather than being it. Emitting
        # the key put dotted identifiers such as ``cli.ledger.add.description_help`` on
        # every parameter of every page of the published reference.
        described = (
            tr(parameter.help_key.value)
            if parameter.help_key
            else docs_chrome("docs.cli.command.no_description", language)
        )

        # Argument-versus-option and required-versus-optional are four authored strings,
        # not one English word in parentheses: this reference is rendered once per
        # language, and a hardcoded "required" is the only untranslated text on the page.
        kind = "argument" if is_argument else "option"
        state = "required" if required else "optional"
        classification = docs_chrome(f"docs.cli.param.{kind}_{state}", language)

        parts.append(f"{declaration}\n   {described}\n   {classification}\n\n")
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
        schema_registry: The immutable CommandSpec-derived schema projection.

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
    """Render graph-authored per-family RST pages under ``docs_root/cli/``.

    Projects the immutable command graph, then
    renders one RST page per top-level family plus an ``index.rst`` and the
    companion ``automation.rst`` and ``schemas.rst`` pages.

    This function pins the output-language setting to English before resolving
    specification translation keys. The subprocess entry point :func:`main`
    provides a clean interpreter boundary.

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
    """Render the CLI reference directly from the immutable command graph."""
    from cadrumo.core.i18n._render import clear_output_language_cache
    from cadrumo.entrypoints.cli.command_api import command_schema_types

    from .build import docs_build_language

    language = docs_build_language(os.environ)
    clear_output_language_cache()
    output_dir = docs_root / "cli"
    output_dir.mkdir(parents=True, exist_ok=True)
    leaves = tuple(node for node in command_spec_nodes() if node.spec.kind == "leaf")
    families = sorted({node.path[1] for node in leaves})
    rendered: dict[str, str] = {}
    for family in families:
        family_nodes = tuple(node for node in leaves if node.path[1] == family)
        groups = sorted({node.path[2] for node in family_nodes if len(node.path) > 3})
        direct = tuple(node for node in family_nodes if len(node.path) == 3)
        # The family landing page is the reader's entry into a whole command family,
        # and it rendered as a bare bullet list of links: the raw family token as its
        # title, no orientation, no heading over the direct commands, and no way back
        # to the index. Every string below already existed, authored in four locales,
        # and went unused -- which is also why it kept being pruned as an unused key.
        family_parts = [
            _rst_heading(docs_chrome("docs.cli.family.title", language, command=family), "="),
            "\n",
            docs_chrome("docs.cli.family.intro", language, family=family) + "\n\n",
        ]
        if direct:
            family_parts.append(
                _rst_heading(docs_chrome("docs.cli.family.direct_commands_heading", language), "-") + "\n"
            )
            family_parts.append(docs_chrome("docs.cli.family.direct_commands_intro", language, family=family) + "\n\n")
        family_parts.extend(_render_graph_command(language, node.path, node.spec) for node in direct)
        if groups:
            family_parts.append(_rst_heading(docs_chrome("docs.cli.family.choose_group_heading", language), "-") + "\n")
        for group in groups:
            group_nodes = tuple(node for node in family_nodes if len(node.path) > 3 and node.path[2] == group)
            content = (
                _rst_heading(f"{family} {group}", "=")
                + "\n"
                + "".join(_render_graph_command(language, node.path, node.spec) for node in group_nodes)
            )
            rel = f"cli/{family}/{group}.rst"
            rendered[rel] = content
            (output_dir / family).mkdir(parents=True, exist_ok=True)
            _write_text_if_changed(output_dir / family / f"{group}.rst", content)
            family_parts.append(
                "* "
                + docs_chrome(
                    "docs.cli.family.group_link_line",
                    language,
                    target=f"{family}/{group}",
                    family=family,
                    group=group,
                )
                + "\n"
            )
        if groups:
            family_parts.extend(("\n.. toctree::\n", "   :hidden:\n\n"))
            family_parts.extend(f"   {family}/{group}\n" for group in groups)
        if groups or direct:
            family_parts.append("\n" + docs_chrome("docs.cli.family.index_link_line", language) + "\n")
        family_content = "".join(family_parts)
        rel = f"cli/{family}.rst"
        rendered[rel] = family_content
        _write_text_if_changed(output_dir / f"{family}.rst", family_content)
    index = _render_index_page(language, family_names=families, total_leaf_count=len(leaves))
    rendered["cli/index.rst"] = index
    _write_text_if_changed(output_dir / "index.rst", index)
    automation = _render_automation_page(language)
    rendered["cli/automation.rst"] = automation
    _write_text_if_changed(output_dir / "automation.rst", automation)
    schemas = _render_schemas_page(language, command_schema_types())
    rendered["cli/schemas.rst"] = schemas
    _write_text_if_changed(output_dir / "schemas.rst", schemas)
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

    Guarantees that the command graph is projected with
    ``CADRUMO_OUTPUT_LANGUAGE=en``, mirroring the generation subprocess.

    Returns:
        A sorted list of normalised registry-key strings for every live leaf
        command (e.g. ``["config.auth.clear", "ledger.add", ...]``).

    Raises:
        RuntimeError: When the subprocess exits with a non-zero code,
            indicating that the command graph could not be projected.
    """
    code = textwrap.dedent(
        """
        from cadrumo.entrypoints.cli.command_api import command_spec_nodes

        for node in command_spec_nodes():
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
