"""``cli-tree.json`` help-projection generator for the ``aeat`` command tree.

This is the build-time projection consumed by the ``cli-sequence`` frontend
widget: a gitignored
``cli-tree.json`` discovery catalogue keyed by command path, fetched once per
page so hovering or focusing a tokenised verb opens a popover carrying that
path's live ``--help``. The same nodes also expose value-free machine-secret
payload contracts and profile-authentication posture for automation. The
projection is regenerated on every build and never committed — the same
Pagefind commit-boundary discipline that governs the RST reference
(``dev/docs/cli_reference.py``) extended to a JSON discovery asset.

The generator projects the same immutable command graph as the reference. It visits every
authored node — groups and leaves alike — so a group token and a leaf token
both resolve to help, and emits one typed :class:`CliCommandNode` per node.

Language pinning
----------------
Help strings are ``tr()`` values resolved at module-import time, so the output
language MUST be pinned to ``en`` *before* any CLI command module is imported.
:func:`build_cli_tree_in_subprocess` is the clean guarantee (a fresh
interpreter with ``CADRUMO_OUTPUT_LANGUAGE=en`` in its environment); the
in-process :func:`build_cli_tree` is for callers that already pin the language
in their own context (mirroring
:func:`~dev.docs.cli_reference.generate_cli_reference`).

Lookup surface
--------------
:func:`load_cli_tree`, :func:`resolve_command_path`, and
:func:`assert_documented_paths_present` are the projection's consumer surface.
A documented command path that does not resolve raises
:class:`CliTreePathNotFoundError`, which lists the nearest candidates — this is
the "free conformance gate" ruling D5 predicts: a documented path missing from
the live projection is a hard failure.
"""

from __future__ import annotations

import difflib
import json
import subprocess
import sys
import textwrap
from collections.abc import Iterable, Sequence
from enum import StrEnum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel as _BaseModel
from pydantic import Field, RootModel, StringConstraints

from cadrumo.core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.entrypoints.cli.command_api import (
    MachineSecretPayloadMetadata,
    ProfileAuthenticationContractMetadata,
)

from .cli_reference import _reference_subprocess_environment

if TYPE_CHECKING:
    import click

__all__ = [
    "CLI_TREE_STATIC_RELPATH",
    "CliCommandNode",
    "CliParam",
    "CliTree",
    "CliTreePathNotFoundError",
    "CliTreePathsNotFoundError",
    "ParamKind",
    "assert_documented_paths_present",
    "build_cli_tree",
    "build_cli_tree_in_subprocess",
    "default_cli_tree_path",
    "load_cli_tree",
    "resolve_command_path",
    "serialise_cli_tree",
    "write_cli_tree",
]

#: Relative path, from the documentation root, of the emitted projection. It
#: lands under ``_static`` so Sphinx copies it into the built site's
#: ``_static/`` directory, making it a same-origin fetch for the widget (no
#: external request). The file itself is gitignored.
CLI_TREE_STATIC_RELPATH = Path("_static") / "cli-tree.json"


class ParamKind(StrEnum):
    """Closed set of CLI parameter kinds in the projection."""

    #: A positional ``click.Argument``.
    ARGUMENT = "argument"
    #: A ``click.Option`` (a ``--flag`` / ``-f`` parameter).
    OPTION = "option"


class CliParam(_BaseModel):
    """One parameter of a command: its flag spellings, kind, and help.

    ``names`` are the option spellings (``["--file"]``, ``["--kind", "-k"]``)
    for an option, or a single positional metavar-style name for an argument.
    """

    model_config = _STRICT_FROZEN

    names: tuple[Annotated[str, StringConstraints(min_length=1)], ...] = Field(min_length=1)
    kind: ParamKind
    required: bool
    help: str


class CliCommandNode(_BaseModel):
    """A single node (group or leaf) in the projected command tree.

    ``path`` is the full command path including the leading executable token
    (``("aeat", "app", "modelo", "calculate")``). ``kind`` distinguishes a
    group (a command that dispatches subcommands) from a leaf (an invokable
    verb). ``usage`` is a deterministic single-line usage synopsis. Secret
    metadata describes only public shape and transport constraints; it never
    includes invocation values, examples, or persisted credential facts.
    """

    model_config = _STRICT_FROZEN

    path: tuple[Annotated[str, StringConstraints(min_length=1)], ...] = Field(min_length=1)
    kind: Annotated[str, StringConstraints(pattern=r"^(group|leaf)$")]
    help: str
    usage: str
    params: tuple[CliParam, ...] = Field(default=())
    machine_secret_payloads: tuple[MachineSecretPayloadMetadata, ...] = Field(default=())
    profile_authentication: Annotated[
        str,
        StringConstraints(pattern=r"^(not-applicable|resume-fallback|self-authenticating)$"),
    ] = "not-applicable"
    profile_authentication_contract: ProfileAuthenticationContractMetadata | None = None


class CliTree(RootModel[dict[str, CliCommandNode]]):
    """The full projection: a mapping from command-path key to its node.

    The key is the command path joined by single spaces, including the leading
    executable token (``"aeat app modelo calculate"``). This is exactly the key
    a tokenised verb token carries, so the widget and the P07 tokeniser resolve
    hover help by the same string.
    """

    def node_for(self, key: str) -> CliCommandNode | None:
        """Return the node for a space-joined path ``key``, or ``None``."""
        return self.root.get(key)

    @property
    def keys(self) -> tuple[str, ...]:
        """Every command-path key in the projection, sorted."""
        return tuple(sorted(self.root))


class CliTreePathNotFoundError(LookupError):
    """Raised when a documented command path is absent from the projection.

    This is the ruling-D5 conformance gate: a docs page citing a verb path that
    the live CLI tree does not expose is a hard build failure. The message
    lists the nearest projection keys so the author sees the likely fix (a
    typo, a renamed verb, a dropped ``app`` namespace segment).
    """

    def __init__(self, path_key: str, candidates: Sequence[str]) -> None:
        self.path_key = path_key
        self.candidates = tuple(candidates)
        hint = f" Nearest: {', '.join(self.candidates)}." if self.candidates else ""
        super().__init__(f"Command path {path_key!r} is not present in the cli-tree projection.{hint}")


class CliTreePathsNotFoundError(LookupError):
    """Raised by the batch gate when one or more documented paths are absent.

    Accumulating, mirroring the engine's parser / comparison / discovery
    convention: :func:`assert_documented_paths_present` collects every
    :class:`CliTreePathNotFoundError` across the whole documented set and raises
    ONE error enumerating each missing path with its nearest candidates, so an
    author sees the entire worklist in one pass rather than fixing them one
    build failure at a time.
    """

    def __init__(self, errors: Sequence[CliTreePathNotFoundError]) -> None:
        self.errors = tuple(errors)
        self.path_keys = tuple(error.path_key for error in self.errors)
        detail = "; ".join(
            f"{error.path_key!r} (nearest: {', '.join(error.candidates) or 'none'})" for error in self.errors
        )
        super().__init__(
            f"{len(self.errors)} documented command path(s) absent from the cli-tree projection: {detail}.",
        )


# ---------------------------------------------------------------------------
# Projection construction
# ---------------------------------------------------------------------------


def _path_key(path: tuple[str, ...]) -> str:
    """Return the space-joined projection key for a command ``path`` tuple."""
    return " ".join(path)


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _is_group(cmd: click.Command) -> bool:  # type: ignore[name-defined]
    """Return whether ``cmd`` dispatches subcommands (a group) or is a leaf."""
    import click

    return isinstance(cmd, click.Group) or hasattr(cmd, "list_commands")


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Parameter at this annotation site under the TYPE_CHECKING import guard.
def _argument_metavar(param: click.Parameter) -> str:  # type: ignore[name-defined]
    """Return a deterministic metavar token for a positional argument.

    Synthesised locally rather than via ``Argument.make_metavar`` (whose
    signature requires a live context in current Click) so the projection is
    stable and context-free: ``NAME`` when required, ``[NAME]`` when optional,
    with a trailing ``...`` when the argument is variadic.
    """
    base = (param.name or "arg").upper()
    if getattr(param, "nargs", 1) == -1:
        base = f"{base}..."
    return base if param.required else f"[{base}]"


# TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING: click stubs do not expose
# Command/Parameter at this annotation site under the TYPE_CHECKING import guard.
def _build_cli_tree_loaded() -> CliTree:
    """Project the immutable command graph to a :class:`CliTree`.

    Assumes the caller has already pinned ``CADRUMO_OUTPUT_LANGUAGE=en`` (either
    via :func:`build_cli_tree`'s ``override_settings`` context or a subprocess
    environment) so ``tr()`` help strings resolve to English.
    """
    from cadrumo.core.i18n import clear_output_language_cache, tr
    from cadrumo.entrypoints.cli.command_api import (
        ArgumentSpec,
        DefaultKind,
        command_registration_projection,
        command_spec_nodes,
    )

    clear_output_language_cache()

    registration = command_registration_projection()
    metadata_by_path = {
        ("aeat", *(row.cli_path or ())): row
        for row in registration.commands
        if row.cli_path is not None
    }
    projection: dict[str, CliCommandNode] = {}
    for node in command_spec_nodes():
        params = tuple(
            CliParam(
                names=(parameter.name,)
                if isinstance(parameter, ArgumentSpec)
                else parameter.declarations,
                kind=ParamKind.ARGUMENT if isinstance(parameter, ArgumentSpec) else ParamKind.OPTION,
                required=parameter.default.kind is DefaultKind.REQUIRED,
                help="" if parameter.help_key is None else tr(parameter.help_key.value),
            )
            for parameter in node.spec.parameters
        )
        usage = " ".join(node.path)
        if any(p.kind is ParamKind.OPTION for p in params):
            usage += " [OPTIONS]"
        if node.spec.kind != "leaf":
            usage += " COMMAND [ARGS]..."
        metadata = metadata_by_path.get(node.path)
        projection[_path_key(node.path)] = CliCommandNode(
            path=node.path,
            kind="leaf" if node.spec.kind == "leaf" else "group",
            help=tr(node.spec.help_key.value),
            usage=usage,
            params=params,
            machine_secret_payloads=() if metadata is None else metadata.machine_secret_payloads,
            profile_authentication=(
                "not-applicable" if metadata is None else metadata.profile_authentication
            ),
            profile_authentication_contract=(
                registration.profile_authentication_contract if node.spec.kind == "root" else None
            ),
        )
    return CliTree(projection)


def build_cli_tree() -> CliTree:
    """Build the projection in-process, pinning the output language to English.

    Mirrors :func:`~dev.docs.cli_reference.generate_cli_reference`: use this
    only when the CLI modules have not already been imported under a different
    language. Otherwise use :func:`build_cli_tree_in_subprocess`.
    """
    from cadrumo.core.config import override_settings

    with override_settings(cadrumo_output_language="en"):
        return _build_cli_tree_loaded()


def build_cli_tree_in_subprocess() -> CliTree:
    """Build the projection in a fresh ``CADRUMO_OUTPUT_LANGUAGE=en`` interpreter.

    The clean guarantee that ``tr()`` resolves to English: a fresh subprocess
    sees the pinned language before any CLI module is imported. The child prints
    the canonical JSON to stdout; the parent validates it back into a
    :class:`CliTree`.

    Raises:
        RuntimeError: When the subprocess exits non-zero (a materialisation
            failure, e.g. a detected import-failure fallback surface).
    """
    code = textwrap.dedent(
        """
        from dev.docs.cli_tree import _build_cli_tree_loaded, serialise_cli_tree
        import sys
        sys.stdout.write(serialise_cli_tree(_build_cli_tree_loaded()))
        """,
    )
    with TemporaryDirectory(prefix="cadrumo-cli-tree-") as storage_root:
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
        raise RuntimeError(f"cli-tree projection subprocess failed (exit {result.returncode}):\n{result.stderr}")
    return CliTree.model_validate_json(result.stdout)


# ---------------------------------------------------------------------------
# Serialisation and emission
# ---------------------------------------------------------------------------


def serialise_cli_tree(tree: CliTree) -> str:
    """Return the canonical JSON text for ``tree``.

    Sorted keys and stable two-space indentation make the artifact
    deterministic and byte-diffable; a trailing newline keeps it POSIX-clean.
    """
    payload = tree.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def default_cli_tree_path(docs_root: Path) -> Path:
    """Return the emission path for the projection under ``docs_root``."""
    return docs_root / CLI_TREE_STATIC_RELPATH


def write_cli_tree(output_path: Path, *, in_subprocess: bool = True) -> CliTree:
    """Build the projection and write it to ``output_path`` if it changed.

    Args:
        output_path: Destination file (typically
            :func:`default_cli_tree_path`).
        in_subprocess: Use the clean subprocess language guarantee (default).
            Pass ``False`` only when the caller already pins the language.

    Returns:
        The built :class:`CliTree`.
    """
    tree = build_cli_tree_in_subprocess() if in_subprocess else build_cli_tree()
    content = serialise_cli_tree(tree)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not (output_path.is_file() and output_path.read_text(encoding=UTF_8_ENCODING) == content):
        output_path.write_text(content, encoding=UTF_8_ENCODING, newline="\n")
    return tree


# ---------------------------------------------------------------------------
# Consumer lookup surface (tokeniser / widget gate)
# ---------------------------------------------------------------------------


def load_cli_tree(path: Path) -> CliTree:
    """Load and validate a serialised projection from ``path``."""
    return CliTree.model_validate_json(path.read_text(encoding=UTF_8_ENCODING))


def _normalise_lookup_key(path: str | Sequence[str]) -> str:
    """Return the space-joined projection key for a path tuple or string."""
    if isinstance(path, str):
        return " ".join(path.split())
    return " ".join(str(token) for token in path)


def resolve_command_path(tree: CliTree, path: str | Sequence[str]) -> CliCommandNode:
    """Resolve a documented command ``path`` to its projection node.

    ``path`` is either a space-joined string (``"aeat app modelo calculate"``)
    or a token sequence (``("aeat", "app", "modelo", "calculate")``). A leading
    ``aeat`` executable token is accepted with or without; both spellings
    resolve to the same node.

    Raises:
        CliTreePathNotFoundError: When no node matches, carrying the nearest
            candidate keys.
    """
    key = _normalise_lookup_key(path)
    node = tree.node_for(key)
    if node is None and not key.startswith("aeat "):
        node = tree.node_for(f"aeat {key}")
    if node is not None:
        return node
    candidates = difflib.get_close_matches(key, tree.root.keys(), n=3, cutoff=0.4)
    raise CliTreePathNotFoundError(key, candidates)


def assert_documented_paths_present(tree: CliTree, documented_paths: Iterable[str | Sequence[str]]) -> None:
    """Assert every documented command path resolves in ``tree``.

    Accumulating: every absent path is collected and one
    :class:`CliTreePathsNotFoundError` is raised enumerating the whole worklist
    with each path's nearest candidates — the build-failing conformance gate
    ruling D5 describes, surfaced in one pass. Callers wanting a single-path
    check use :func:`resolve_command_path`, which raises the singular
    :class:`CliTreePathNotFoundError`.
    """
    errors: list[CliTreePathNotFoundError] = []
    for path in documented_paths:
        try:
            resolve_command_path(tree, path)
        except CliTreePathNotFoundError as error:
            errors.append(error)
    if errors:
        raise CliTreePathsNotFoundError(errors)
