"""Cadrumo's command-line interface (CLI), provided by the ``aeat`` executable.

The command tree exposes two top-level namespaces:

- ``aeat config`` — local configuration, on-ramp wizard, diagnostics.
- ``aeat app`` — operational tax work: overview, ledger, modelo,
  registry, and review.

Every command in this package is a thin transport over the backend application
programming interface (API).
The handler bodies parse argv, call into
``cadrumo.application`` / ``cadrumo.domain``, and render the typed result.
No business logic lives in the CLI layer: validation, mutation,
schema-decision, and persistence all live behind the imported
application functions and pydantic records.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import typer
from typer._click.core import Command as _TyCommand

if TYPE_CHECKING:
    # Type-checking-only: gives static consumers of the lazy `command_schema_refs`
    # re-export (below, via `__getattr__`) its real signature without paying the
    # eager registry-parse import cost at runtime -- this line never executes.
    from ._command_schema import command_schema_refs as command_schema_refs
    from ._command_schema import command_schema_type as command_schema_type
    from ._command_schema import command_schema_types as command_schema_types
    from ._modelo_rendering import calculation_revision_lines, calculation_revision_payload
    from ._verb_input_schema import VerbInputSchema as VerbInputSchema
    from ._verb_input_schema import cli_path_for_command_key as cli_path_for_command_key
    from ._verb_input_schema import is_exposable_command as is_exposable_command
    from .command_spec import CommandSpec
    from .config.google import OAuthClientPayload as OAuthClientPayload
from ._stdio import _disable_rich_cli_rendering as _disable_rich_cli_rendering
from ._stdio import configure_stdio_for_utf8 as _configure_stdio_for_utf8

# Force UTF-8 on stdout / stderr before any echo, log, or Rich console
# instantiation. Default Windows terminals expose cp1252; emoji,
# CJK, the U+2192 arrow used by the review queue, and the § sign
# in some IVA citations all crash typer.echo on cp1252. See
# :mod:`._stdio` for the rationale.
_configure_stdio_for_utf8()

# Disable Typer/Click's Rich-based help, error, and traceback rendering
# for every Typer() app in the command tree (module-level, read live by
# every render call — see :func:`._stdio._disable_rich_cli_rendering`).
# Plain text keeps option/argument tables readable regardless of the
# invoking terminal's real width.
_disable_rich_cli_rendering()

from ...core.cli_metadata import is_metadata_invocation as _is_metadata_invocation
from ...core.product_identity import PRODUCT_IDENTITY as _PRODUCT_IDENTITY
from ...core.storage_taxonomy import StorageCategory as _StorageCategory
from ...core.storage_taxonomy_locations import storage_location as _storage_location
from ._command_policy import CommandExecutionPolicy as _CommandExecutionPolicy
from ._command_runtime import build_command_app as _build_command_app
from ._common import attach_cli_policy_verdict, resolve_cli_precondition_action
from ._framework_localisation import (
    localise_help_section_headers as _localise_help_section_headers,
)
from ._framework_localisation import (
    localise_typer_parse_error_messages as _localise_typer_parse_error_messages,
)
from ._operator_surface_reconciliation import current_operator_surface_reconciliation
from .command_specs import COMMAND_GRAPH as _COMMAND_GRAPH
from .errors import decorate_typer_app as _decorate_typer_app
from .language_argv import apply_language_argv_to_environment as _apply_language_argv_to_environment

CommandExecutionPolicy = _CommandExecutionPolicy

# The command tree is assembled lazily: each leaf command module pulls
# the application layer and, transitively, the ~0.6 s registry parse.
# Importing every module just to build the Cadrumo app object made
# ``aeat --version`` and ``aeat --help`` pay that cost even though they
# never dispatch into a subcommand. Modules are imported by their
# :class:`_LazySubcommand` loader only when an operator actually invokes
# something in the owning subtree (see :mod:`._command_suggestions`).
# ``--version`` / ``--help`` / the bare landing surface short-circuit
# in the callbacks below before any subcommand is resolved.

# ---------------------------------------------------------------------
# Root app + callback
# ---------------------------------------------------------------------


app = _build_command_app(_COMMAND_GRAPH)
_decorate_typer_app(app)
command_graph = _COMMAND_GRAPH


def full_command_tree() -> _TyCommand:
    """Materialise the immutable production command graph as a Click tree."""
    from typer.main import get_command

    root = get_command(app)
    root.name = app.info.name or _PRODUCT_IDENTITY.cli_executable
    return root


def _declared_execution_policy_for_cli_path(
    cli_path: tuple[str, ...],
) -> _CommandExecutionPolicy:
    declared = _COMMAND_GRAPH.resolve_path((_PRODUCT_IDENTITY.cli_executable, *cli_path))
    return _execution_policy_from_spec(declared)


def _execution_policy_from_spec(spec: CommandSpec) -> _CommandExecutionPolicy:
    from ._command_schema import CommandCapabilityClass

    declared = spec.policy
    return _CommandExecutionPolicy(
        classification=CommandCapabilityClass(
            declared.capabilities,
            declared.side_effects,
            declared.performance,
        ),
        write_route=declared.write_route,
        destructive=declared.destructive,
        handoff=declared.handoff,
        live_write=declared.live_write,
    )


def command_execution_policy_for_cli_path(
    cli_path: tuple[str, ...],
) -> _CommandExecutionPolicy:
    """Return CommandSpec-owned policy for one live path.

    The concrete policy type remains owned by the CLI command graph. This
    facade keeps cross-distribution consumers on the public entrypoint boundary
    without importing the complete command tree.
    """
    return _declared_execution_policy_for_cli_path(cli_path)


def command_search_terms(command_key: str) -> tuple[str, ...]:
    """Return spec-authored semantic search terms for one command key."""
    spec = _COMMAND_GRAPH.by_schema_identity().get(command_key) or _COMMAND_GRAPH.by_key().get(command_key)
    if spec is None:
        raise LookupError(f"unknown command key: {command_key!r}")
    return spec.search_terms


#: The per-verb input-schema projection re-exported from this facade. The module
#: walks the live command tree and pulls in the operator-action catalogue, so it
#: stays off the eager import path with the other lazy re-exports below.
_VERB_INPUT_SCHEMA_EXPORTS: frozenset[str] = frozenset(
    {
        "DECLARED_UNIMPLEMENTED_SURFACES",
        "JsonType",
        "ResolvedVerbLeaf",
        "SchemaResolutionError",
        "VerbInputSchema",
        "VerbLeafKind",
        "VerbLeafResolutionFailure",
        "VerbParamKind",
        "VerbParameter",
        "assert_schema_coverage",
        "build_verb_input_schemas",
        "cli_argv_for",
        "cli_path_for_command_key",
        "is_exposable_command",
    }
)


def __getattr__(name: str) -> object:
    """Lazily resolve re-exported names without importing heavy submodules eagerly.

    ``_command_schema``, ``config.google``, and ``_modelo_rendering`` are
    kept off the eager import path precisely so constructing the Cadrumo CLI
    app object never pulls the registry-dependent command tree; a
    top-level ``from ._command_schema import command_schema_refs`` (and
    siblings) would defeat that and reintroduce the startup cost
    :mod:`._stdio` / the lazy command-tree gate guard against.
    """
    if name in {"command_schema_refs", "command_schema_type", "command_schema_types"}:
        from . import _command_schema

        return getattr(_command_schema, name)
    if name in _VERB_INPUT_SCHEMA_EXPORTS:
        from . import _verb_input_schema

        return getattr(_verb_input_schema, name)
    if name == "OAuthClientPayload":
        from .config.google import OAuthClientPayload

        return OAuthClientPayload
    if name in ("calculation_revision_lines", "calculation_revision_payload"):
        from . import _modelo_rendering

        return getattr(_modelo_rendering, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main() -> None:
    """Console-script entry point.

    Pins ``prog_name`` so Typer's usage lines say ``aeat`` even when the
    launcher is ``aeat.EXE`` on Windows.

    An explicit ``--language`` / ``--lang`` flag is promoted to
    ``CADRUMO_OUTPUT_LANGUAGE`` here, before the lazily imported subcommand modules
    render their ``tr(...)``-bound help, so the flag genuinely localises help
    text (see :mod:`._language_argv`).
    The Rich ``--help`` section headers are then rebound to the same resolved
    locale (see :func:`_localise_help_section_headers`).
    """
    import sys

    arguments = sys.argv[1:]
    metadata_invocation = _is_metadata_invocation(arguments)
    if _apply_language_argv_to_environment(arguments) is not None:
        # load_settings() holds a process-wide Settings singleton cached by
        # the active-profile pointer, not by env var (core/config.py,
        # _constructed_settings), so the CADRUMO_OUTPUT_LANGUAGE write above is
        # invisible to it once that singleton already exists -- any tr() call
        # that resolved a language before this point (an eager Settings()
        # build during import, for instance) would otherwise keep serving
        # that stale language for the rest of the process, including to
        # _localise_help_section_headers() below. reset_settings_cache() is
        # the sanctioned way to make a process-environment change observed
        # (see its docstring); the same pairing already exists in
        # test_flow_tui_app.py for a language change mid-session.
        from ...core.config import reset_settings_cache

        reset_settings_cache()
    _localise_help_section_headers()
    _localise_typer_parse_error_messages()
    # Route the Cl@ve auth-wait progress banner (which carries the AEAT
    # verification code the operator must confirm in their Cl@ve app) to
    # stderr, so a headless operator sees it during the wait instead of
    # having to read the runtime log. stderr keeps the stdout JSON envelope
    # pure; the code is non-secret operator guidance, not a credential.
    progress_sink = nullcontext()
    if not metadata_invocation:
        try:
            _refuse_former_product_state_at_startup()
        except typer.Exit as exit_request:
            raise SystemExit(exit_request.exit_code) from None
        from ...adapters.outbound.aeat.operator_progress import operator_progress_sink

        progress_sink = operator_progress_sink(_emit_operator_progress)
    with _metadata_state_isolation(arguments), progress_sink:
        app(prog_name=_PRODUCT_IDENTITY.cli_executable)


def _refuse_former_product_state_at_startup() -> None:
    """Route a refused retired ``aeat`` state root through the typed CLI error boundary."""
    from ...application.profile_preconditions import (
        FormerProductDetectionScope,
        former_product_state_verdict,
    )
    from ...core.config import Settings
    from ...core.config_state_root import FormerProductStateError
    from ...core.errors.hierarchy import ActiveProfilePointerError
    from .errors import CliRefusedBoundaryError, _emit_error_and_exit, project_cli_boundary_error

    try:
        Settings()
    except FormerProductStateError as error:
        _emit_error_and_exit(
            attach_cli_policy_verdict(
                CliRefusedBoundaryError(str(error)),
                verdict=former_product_state_verdict(
                    FormerProductDetectionScope.STARTUP,
                ),
            )
        )
    except ActiveProfilePointerError as error:
        _emit_error_and_exit(project_cli_boundary_error(error, _refuse_former_product_state_at_startup))


@contextmanager
def _metadata_state_isolation(arguments: list[str]) -> Generator[None]:
    """Keep help and version imports off an operator's retired ``aeat`` state root.

    Lazy subgroup construction can import modules that instantiate Settings.
    Metadata invocations therefore run against a temporary Cadrumo root and
    database before those imports occur. Normal commands never enter this
    scope and continue to refuse a retired ``aeat`` state root in normal operation.
    """
    if not _is_metadata_invocation(arguments):
        yield
        return

    keys = ("CADRUMO_LOCAL_STORAGE_ROOT", "CADRUMO_DATABASE_URL")
    saved = {key: os.environ.get(key) for key in keys}
    # Declared exception to the "every tempfile call passes dir=" storage
    # provenance discipline: there is no "destination" to anchor on here.
    # This scope exists so a --help/--version invocation runs against a
    # throwaway root instead of the operator's real one, which may be
    # retired or broken -- isolation FROM a root, not production NEAR one.
    # Anchoring dir= on anything derived from the real root (even a pure,
    # no-I/O computation like the platform user-data directory) reintroduces
    # the dependency this scope exists to sever, and could break --help on
    # exactly the broken-root case it is meant to survive. The OS-default
    # temp root is the correct home, not a gap. The FILENAME joined onto it
    # is a different axis: `storage_location` is a pure dict lookup with no
    # settings/I-O dependency, and `cadrumo.core` is already fully imported
    # above (`_PRODUCT_IDENTITY`), so reading the taxonomy's declared
    # root-fallback-database subpath here costs nothing extra and tracks a
    # future rename instead of drifting from it.
    with TemporaryDirectory(prefix="cadrumo-cli-metadata-") as temporary_root:
        root = Path(temporary_root)
        os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root)
        database_filename = _storage_location(_StorageCategory.ROOT_FALLBACK_DATABASE).subpath
        os.environ["CADRUMO_DATABASE_URL"] = f"sqlite:///{(root / database_filename).as_posix()}"
        try:
            yield
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _emit_operator_progress(progress: object) -> None:
    """Write an operator progress banner to stderr, keeping stdout pure."""
    from ...core.operator_progress import OperatorProgress

    if not isinstance(progress, OperatorProgress):
        raise TypeError(f"progress must be OperatorProgress, got {type(progress).__name__}")
    typer.echo(progress.render(), err=True)


__all__ = [
    "DECLARED_UNIMPLEMENTED_SURFACES",
    "CommandExecutionPolicy",
    "JsonType",
    "OAuthClientPayload",
    "ResolvedVerbLeaf",
    "SchemaResolutionError",
    "VerbInputSchema",
    "VerbLeafKind",
    "VerbLeafResolutionFailure",
    "VerbParamKind",
    "VerbParameter",
    "app",
    "assert_schema_coverage",
    "build_verb_input_schemas",
    "calculation_revision_lines",
    "calculation_revision_payload",
    "cli_argv_for",
    "cli_path_for_command_key",
    "command_execution_policy_for_cli_path",
    "command_graph",
    "command_schema_refs",
    "command_schema_type",
    "command_schema_types",
    "command_search_terms",
    "current_operator_surface_reconciliation",
    "is_exposable_command",
    "main",
    "resolve_cli_precondition_action",
]
