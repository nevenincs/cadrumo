"""CLI-surface projection compiler for the docs search index.

Projects the immutable production ``aeat`` command graph into strict search
records the offline docs search and the Ctrl-K command palette surface as
first-class results: one
:class:`~dev.docs.terminology._cli_projection.CliSurfaceRecord` per leaf
command and one
:class:`~dev.docs.terminology._cli_projection.CliOptionRecord` per option
or argument. Each record carries the help text resolved into all four
output languages (es / en / ca / hu) and a target anchor into the
generated CLI reference page.

The records extend the shared
:class:`~dev.docs.terminology._search_record.SearchRecordBase` authored by
the sibling casilla-projection compiler, reusing the ``kind`` discriminator
(``SearchRecordKind.CLI``) and the four-language localised-description map
so all record kinds serialise to one homogeneous index payload.

House pattern
-------------
The command inventory is projected from the same immutable specifications
used to compile the runtime. Translation keys are resolved once per language
in a fresh subprocess with ``CADRUMO_OUTPUT_LANGUAGE=<lang>``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from typing import TypedDict, cast

from pydantic import Field

from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, UTF_8_ENCODING, OutputLanguage

from ..cli_reference import cli_reference_page_for_command
from ._search_record import SearchRecordBase, SearchRecordKind

__all__ = [
    "CliOptionRecord",
    "CliProjectionStats",
    "CliSurfaceRecord",
    "project_cli_search_records",
]


class _ParamPayload(TypedDict):
    """One command parameter as emitted by the language-pinned walk subprocess."""

    option_names: list[str]
    is_argument: bool
    required: bool
    help: str


class _CommandPayload(TypedDict):
    """One leaf command as emitted by the language-pinned walk subprocess."""

    path: list[str]
    family: str
    help: str
    params: list[_ParamPayload]


class CliSurfaceRecord(SearchRecordBase):
    """A search record for one live ``aeat`` leaf command.

    Identity is the full command path (e.g. ``aeat app modelo calculate``).
    The four-language ``descriptions`` map carries the command's help text
    resolved in es / en / ca / hu; ``target`` is the generated CLI-reference
    page anchor a palette card jumps to.
    """

    kind: SearchRecordKind = SearchRecordKind.CLI
    #: The full command path from the root, e.g. ``aeat app ledger add``.
    command_path: str = Field(min_length=1, max_length=240)
    #: The normalised schema-registry key, e.g. ``ledger.add``.
    registry_key: str = Field(min_length=1, max_length=240)
    #: The top-level command family (``app`` or ``config``).
    family: str = Field(min_length=1, max_length=64)
    #: The CLI-reference page anchor, e.g.
    #: ``cli/app/ledger.html#aeat-app-ledger-add``.
    target: str = Field(min_length=1, max_length=320)


class CliOptionRecord(SearchRecordBase):
    """A search record for one option or argument of a leaf command.

    Identity is the owning command path plus the option's surface name(s).
    The four-language ``descriptions`` map carries the option help resolved
    in es / en / ca / hu; ``target`` is the owning command's CLI-reference
    anchor (options render within their command's section).
    """

    kind: SearchRecordKind = SearchRecordKind.CLI
    #: The owning command path, e.g. ``aeat app ledger add``.
    command_path: str = Field(min_length=1, max_length=240)
    #: The option surface name(s), e.g. ``("--amount",)`` or ``("modelo",)``
    #: for a positional argument.
    option_names: tuple[str, ...] = Field(min_length=1)
    #: ``True`` for a positional argument, ``False`` for an option flag.
    is_argument: bool = False
    #: Whether the parameter is required.
    required: bool = False
    #: The owning command's CLI-reference anchor (shared with its
    #: :class:`CliSurfaceRecord`).
    target: str = Field(min_length=1, max_length=320)


@dataclass(frozen=True, slots=True)
class CliProjectionStats:
    """Counts for one CLI projection run."""

    command_records: int
    option_records: int
    #: Commands whose help text was identical across all four languages
    #: (a missing-translation signal, not an error).
    commands_untranslated: int


# ---------------------------------------------------------------------------
# Target-anchor derivation (mirrors the CLI-reference page layout)
# ---------------------------------------------------------------------------


def _command_anchor(command_path: str) -> str:
    r"""Return the Sphinx section-slug anchor for a command heading.

    ``dev/docs/cli_reference.py`` renders each leaf command as an RST section
    whose heading is the command path wrapped in double backticks (the page it
    lands on is decided by :func:`cli_reference_page_for_command`, not by this
    slug). Sphinx derives the in-page anchor by lower-casing the heading text
    and joining its alphanumeric runs with hyphens, so ``aeat app ledger add``
    becomes ``aeat-app-ledger-add``.

    Args:
        command_path: The full space-joined command path.

    Returns:
        The slugified anchor fragment (no leading ``#``).
    """
    slug_chars: list[str] = []
    previous_hyphen = True
    for char in command_path.lower():
        if char.isalnum():
            slug_chars.append(char)
            previous_hyphen = False
        elif not previous_hyphen:
            slug_chars.append("-")
            previous_hyphen = True
    return "".join(slug_chars).strip("-")


def _command_target(command_path: tuple[str, ...]) -> str:
    """Return the CLI-reference page anchor for a command.

    The page is resolved through :func:`cli_reference_page_for_command`, the
    single routing authority the CLI-reference generator itself renders against,
    so a deep link always lands on the page that carries the command's section:
    a group page (``cli/app/ledger.html``) for a grouped command, the family
    landing page (``cli/config.html``) for a leaf mounted directly on the
    family. Deriving the page here rather than hardcoding ``cli/<family>.html``
    is what keeps this in lock-step with a future page-layout change.

    Args:
        command_path: The full command path tuple including the leading
            executable token, e.g. ``("aeat", "app", "ledger", "add")``.

    Returns:
        A page+anchor string, e.g. ``cli/app/ledger.html#aeat-app-ledger-add``.
    """
    page_stem = cli_reference_page_for_command(command_path)
    return f"{page_stem}.html#{_command_anchor(' '.join(command_path))}"


# ---------------------------------------------------------------------------
# Per-language tree walk (subprocess, language-pinned)
# ---------------------------------------------------------------------------

_WALK_PROGRAM = textwrap.dedent(
    """
    import json
    from cadrumo.core.i18n import tr
    from cadrumo.entrypoints.cli.command_api import ArgumentSpec, DefaultKind, command_spec_nodes

    commands = []
    for node in command_spec_nodes():
        if node.spec.kind != "leaf":
            continue
        params = []
        for param in node.spec.parameters:
            params.append({
                "option_names": [param.name] if isinstance(param, ArgumentSpec) else list(param.declarations),
                "is_argument": isinstance(param, ArgumentSpec),
                "required": param.default.kind is DefaultKind.REQUIRED,
                "help": "" if param.help_key is None else tr(param.help_key.value),
            })
        commands.append({
            "path": list(node.path),
            "family": node.path[1],
            "help": tr(node.spec.help_key.value),
            "params": params,
        })
    print(json.dumps(commands))
    """,
)


def _walk_tree_for_language(language: OutputLanguage) -> list[_CommandPayload]:
    """Project the command graph in one language via a fresh subprocess.

    Pins ``CADRUMO_OUTPUT_LANGUAGE`` to ``language`` before resolving the
    specification translation keys in the subprocess.

    Args:
        language: The output language to resolve help strings in.

    Returns:
        A list of per-command payloads (path, family, help, params).

    Raises:
        RuntimeError: When the subprocess exits non-zero.
    """
    env = dict(os.environ)
    env["CADRUMO_OUTPUT_LANGUAGE"] = language.value

    result = subprocess.run(
        [sys.executable, "-c", _WALK_PROGRAM],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        encoding=UTF_8_ENCODING,
    )
    if result.returncode != 0:
        # BROAD-EXCEPT-RATIONALE-SUBPROCESS-GUARD:
        # subprocess invocation failure surfaced as RuntimeError for build
        # diagnostics; not on the operator-facing CadrumoError contract.
        raise RuntimeError(
            f"CLI tree walk subprocess failed for language {language.value!r} "
            f"(exit {result.returncode}):\n{result.stderr}",
        )
    parsed: object = json.loads(result.stdout)
    if not isinstance(parsed, list):
        raise RuntimeError(f"CLI tree walk produced a non-list payload for {language.value!r}")
    return [_coerce_command_payload(item) for item in parsed]


def _coerce_command_payload(item: object) -> _CommandPayload:
    """Coerce one decoded JSON object into a typed :class:`_CommandPayload`.

    The subprocess writes the shape deterministically (it is our own
    program), so this is a narrow, total coercion rather than a tolerant
    parser: a structurally wrong payload is a build-time bug worth raising on.
    """
    if not isinstance(item, dict):
        raise RuntimeError(f"CLI tree walk produced a non-object command entry: {item!r}")
    entry = cast("dict[str, object]", item)
    raw_params = entry["params"]
    if not isinstance(raw_params, list):
        raise RuntimeError("CLI tree walk command entry has a non-list 'params'")
    params: list[_ParamPayload] = [_coerce_param_payload(raw_param) for raw_param in raw_params]
    raw_path = entry["path"]
    if not isinstance(raw_path, list):
        raise RuntimeError("CLI tree walk command entry has a non-list 'path'")
    return _CommandPayload(
        path=[str(token) for token in raw_path],
        family=str(entry["family"]),
        help=str(entry["help"]),
        params=params,
    )


def _coerce_param_payload(raw_param: object) -> _ParamPayload:
    """Coerce one decoded JSON parameter object into a typed :class:`_ParamPayload`."""
    if not isinstance(raw_param, dict):
        raise RuntimeError("CLI tree walk produced a non-object parameter entry")
    param = cast("dict[str, object]", raw_param)
    raw_names = param["option_names"]
    if not isinstance(raw_names, list):
        raise RuntimeError("CLI tree walk parameter entry has a non-list 'option_names'")
    return _ParamPayload(
        option_names=[str(name) for name in raw_names],
        is_argument=bool(param["is_argument"]),
        required=bool(param["required"]),
        help=str(param["help"]),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def project_cli_search_records() -> tuple[
    tuple[CliSurfaceRecord, ...],
    tuple[CliOptionRecord, ...],
    CliProjectionStats,
]:
    """Project the command graph into command and option search records.

    Projects the immutable specifications once per output language (es / en /
    ca / hu) in language-pinned subprocesses and merges the four passes into
    one record per command and one record per option, each carrying its
    four-language help.

    The Spanish pass is the structural authority: the command and option
    inventory (paths, families, option names, required flags) is taken from
    the ``es`` walk, and the other three languages contribute only their
    help text. A language whose help text equals the Spanish text is treated
    as having no distinct translation for that surface and is omitted from
    the ``descriptions`` map rather than duplicating the Spanish string --
    ``es`` is always present (the invariant).

    Returns:
        A ``(command_records, option_records, stats)`` triple. Command
        records are sorted by ``command_path``; option records are sorted by
        ``(command_path, option_names)``.
    """
    languages = tuple(OutputLanguage(code) for code in SUPPORTED_OUTPUT_LANGUAGES)
    per_language = {language: _walk_tree_for_language(language) for language in languages}

    # The Spanish pass is the structural authority. Index every other pass by
    # command path so help text can be aligned across languages.
    spanish = per_language[OutputLanguage.ES]
    by_language: dict[OutputLanguage, dict[tuple[str, ...], _CommandPayload]] = {
        language: {tuple(entry["path"]): entry for entry in commands} for language, commands in per_language.items()
    }

    command_records: list[CliSurfaceRecord] = []
    option_records: list[CliOptionRecord] = []
    untranslated_commands = 0

    for entry in spanish:
        path = tuple(entry["path"])
        command_path = " ".join(path)
        family = entry["family"]
        target = _command_target(path)
        registry_key = ".".join(path[1:] if path[:1] == ("aeat",) else path)

        command_help = _command_help_map(path, by_language)
        if len(command_help) == 1:
            untranslated_commands += 1
        command_records.append(
            CliSurfaceRecord(
                kind=SearchRecordKind.CLI,
                descriptions=command_help,
                command_path=command_path,
                registry_key=registry_key,
                family=family,
                target=target,
            ),
        )

        for index, param in enumerate(entry["params"]):
            option_help = _option_help_map(path, index, by_language)
            option_records.append(
                CliOptionRecord(
                    kind=SearchRecordKind.CLI,
                    descriptions=option_help,
                    command_path=command_path,
                    option_names=tuple(param["option_names"]),
                    is_argument=param["is_argument"],
                    required=param["required"],
                    target=target,
                ),
            )

    command_records.sort(key=lambda record: record.command_path)
    option_records.sort(key=lambda record: (record.command_path, record.option_names))

    stats = CliProjectionStats(
        command_records=len(command_records),
        option_records=len(option_records),
        commands_untranslated=untranslated_commands,
    )
    return tuple(command_records), tuple(option_records), stats


def _command_help_map(
    path: tuple[str, ...],
    by_language: dict[OutputLanguage, dict[tuple[str, ...], _CommandPayload]],
) -> dict[OutputLanguage, str]:
    """Build the four-language description map for a command's help text.

    ``es`` is the invariant -- always present, falling back to the command's
    own final path token when the help is empty. A non-Spanish language is
    included only when it carries help text that DIFFERS from the Spanish
    text: an identical string means the surface is untranslated in that
    language, and duplicating it would inflate the index without adding a
    distinct match.
    """
    spanish_entry = by_language[OutputLanguage.ES].get(path)
    spanish_help = spanish_entry["help"] if spanish_entry is not None else ""
    descriptions: dict[OutputLanguage, str] = {OutputLanguage.ES: spanish_help or path[-1]}
    for language, indexed in by_language.items():
        if language is OutputLanguage.ES:
            continue
        entry = indexed.get(path)
        if entry is None:
            continue
        text = entry["help"]
        if text and text != spanish_help:
            descriptions[language] = text
    return descriptions


def _option_help_map(
    path: tuple[str, ...],
    index: int,
    by_language: dict[OutputLanguage, dict[tuple[str, ...], _CommandPayload]],
) -> dict[OutputLanguage, str]:
    """Build the four-language description map for one option's help text.

    Options are aligned by positional index within their command's
    parameter list (the list order is stable across passes because every
    pass walks the same tree). ``es`` is the invariant -- falling back to the
    option's first surface name when its help is empty; a non-Spanish
    language contributes only when its help text differs from the Spanish.
    """
    spanish_param = _param_at(by_language[OutputLanguage.ES].get(path), index)
    spanish_help = spanish_param["help"] if spanish_param is not None else ""
    spanish_name = ""
    if spanish_param is not None and spanish_param["option_names"]:
        spanish_name = spanish_param["option_names"][0]
    descriptions: dict[OutputLanguage, str] = {OutputLanguage.ES: spanish_help or spanish_name or "option"}
    for language, indexed in by_language.items():
        if language is OutputLanguage.ES:
            continue
        param = _param_at(indexed.get(path), index)
        if param is None:
            continue
        text = param["help"]
        if text and text != spanish_help:
            descriptions[language] = text
    return descriptions


def _param_at(command: _CommandPayload | None, index: int) -> _ParamPayload | None:
    """Return the parameter at ``index`` of ``command``, or ``None`` if absent."""
    if command is None:
        return None
    params = command["params"]
    if index >= len(params):
        return None
    return params[index]
