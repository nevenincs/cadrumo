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
from collections.abc import Collection, Generator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from functools import cache
from typing import TYPE_CHECKING

from ...core.cli_metadata import is_metadata_invocation as _is_metadata_invocation
from ...core.product_identity import PRODUCT_IDENTITY as _PRODUCT_IDENTITY
from ...core.storage_environment import STORAGE_ROOT, storage_directory
from ...core.type_guards import is_object_collection, is_object_dict
from .command_specs import COMMAND_GRAPH as _COMMAND_GRAPH

if TYPE_CHECKING:
    import typer

    from cadrumo_client.commands.spec import CommandSpec

    from ._command_policy import CommandExecutionPolicy

# Importing this module costs the declarative command graph and nothing else.
# Typer, the error boundary, the locale catalogues and every command module are
# loaded when the app is first built or a command first runs: ``aeat --help``
# and the import-only consumers of this module must not pay for a dispatch they
# never make. Each subtree is materialized by its :class:`LazySubcommand`
# loader only when an operator invokes something in it (see
# :mod:`.command_suggestions`).


@cache
def cli_app() -> typer.Typer:
    """Build the root Typer app from the command graph, once per process."""
    from cadrumo_client.commands.compiler import build_command_app
    from cadrumo_client.commands.stdio import configure_stdio_for_utf8, disable_rich_cli_rendering

    from ._terminal_errors import run_standalone_with_error_contract
    from .command_lifecycle import dispatch_cli_behavior
    from .errors import decorate_typer_app

    # UTF-8 streams before any echo: default Windows consoles expose cp1252,
    # on which the review queue's arrow and IVA citations' section sign crash
    # typer.echo (see :mod:`cadrumo_client.commands.stdio`). Plain-text help keeps option tables
    # readable whatever the terminal's real width.
    configure_stdio_for_utf8()
    disable_rich_cli_rendering()
    app = build_command_app(
        _COMMAND_GRAPH,
        dispatcher=dispatch_cli_behavior,
        standalone_error_runner=run_standalone_with_error_contract,
    )
    decorate_typer_app(app)
    return app


def _declared_execution_policy_for_cli_path(
    cli_path: tuple[str, ...],
) -> CommandExecutionPolicy:
    declared = _COMMAND_GRAPH.resolve_path((_PRODUCT_IDENTITY.cli_executable, *cli_path))
    return _execution_policy_from_spec(declared)


def _execution_policy_from_spec(spec: CommandSpec) -> CommandExecutionPolicy:
    from cadrumo_client.contracts.command_ports import CommandCapabilityClass

    from ._command_policy import CommandExecutionPolicy

    declared = spec.policy
    return CommandExecutionPolicy(
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
) -> CommandExecutionPolicy:
    """Return CommandSpec-owned policy for one live path.

    The concrete policy type remains owned by the CLI command graph. This
    facade keeps cross-distribution consumers on the public entrypoint boundary
    without importing the complete command tree.
    """
    return _declared_execution_policy_for_cli_path(cli_path)


def main() -> None:
    """Console-script entry point.

    Pins ``prog_name`` so Typer's usage lines say ``aeat`` even when the
    launcher is ``aeat.EXE`` on Windows.

    An explicit ``--language`` / ``--lang`` flag is promoted to
    ``CADRUMO_OUTPUT_LANGUAGE`` here, before the lazily imported subcommand modules
    render their ``tr(...)``-bound help, so the flag genuinely localises help
    text (see :mod:`.language_argv`).
    The Rich ``--help`` section headers are then rebound to the same resolved
    locale (see :func:`cadrumo.entrypoints.cli._framework_localisation.localise_help_section_headers`).
    """
    import sys

    import typer

    from cadrumo_client.commands.stdio import configure_stdio_for_utf8
    from cadrumo_client.logging import register_client_logging_namespace

    from ._framework_localisation import localise_help_section_headers, localise_typer_parse_error_messages
    from .language_argv import apply_language_argv_to_environment

    register_client_logging_namespace()
    configure_stdio_for_utf8()
    arguments = sys.argv[1:]
    if arguments == ["--cadrumo-command-surface"]:
        _emit_command_surface_manifest()
        return
    metadata_invocation = _is_metadata_invocation(arguments)
    if apply_language_argv_to_environment(arguments) is not None:
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
    localise_help_section_headers()
    localise_typer_parse_error_messages()
    # Route the Cl@ve auth-wait progress banner (which carries the AEAT
    # verification code the operator must confirm in their Cl@ve app) to
    # stderr, so a headless operator sees it during the wait instead of
    # having to read the runtime log. stderr keeps the stdout JSON envelope
    # pure; the code is non-secret operator guidance, not a credential.
    progress_sink = nullcontext()
    with _pointer_repair_scope(arguments):
        if not metadata_invocation:
            try:
                _admit_authority_at_startup()
            except typer.Exit as exit_request:
                raise SystemExit(exit_request.exit_code) from None
            from ...core.operator_progress import operator_progress_sink

            progress_sink = operator_progress_sink(_emit_operator_progress)
        with _metadata_state_isolation(arguments), progress_sink:
            cli_app()(prog_name=_PRODUCT_IDENTITY.cli_executable)


def _pointer_repair_scope(arguments: list[str]) -> AbstractContextManager[None]:
    """Let the declared pointer-repair leaf start while the pointer it repairs is corrupt.

    Admission composes settings, and settings composition reads the active-profile
    pointer, so without this the command a corrupt pointer's refusal recommends
    would be refused by that same corruption before it could parse.
    """
    leaf = _COMMAND_GRAPH.resolve_invocation(arguments)
    if leaf is None or not leaf.repairs_active_profile_pointer:
        return nullcontext()
    from ...core.bucket_pointer import corrupt_pointer_reads_as_unselected

    return corrupt_pointer_reads_as_unselected()


def _admit_authority_at_startup() -> None:
    """Admit the shipped authority through the typed CLI error boundary.

    Storage is not provisioned here: a command provisions it at dispatch, once
    parsing has accepted it, so help, a bare group and a parse-time refusal
    write nothing.
    """
    from cadrumo_client.commands.errors import CliRefusedBoundaryError

    from ...application.cli_provisioning import admit_cli_authority
    from ...application.profile_preconditions import (
        FormerProductDetectionScope,
        former_product_state_verdict,
    )
    from ...core.config_state_root import FormerProductStateError
    from ...core.errors.hierarchy import ActiveProfilePointerError, CadrumoError
    from .common import attach_cli_policy_verdict
    from .errors import emit_error_and_exit, project_cli_boundary_error

    try:
        admit_cli_authority()
    except FormerProductStateError as error:
        emit_error_and_exit(
            attach_cli_policy_verdict(
                CliRefusedBoundaryError(str(error)),
                verdict=former_product_state_verdict(
                    FormerProductDetectionScope.STARTUP,
                ),
            )
        )
    except ActiveProfilePointerError as error:
        emit_error_and_exit(project_cli_boundary_error(error, _admit_authority_at_startup))
    except CadrumoError as error:
        emit_error_and_exit(project_cli_boundary_error(error, _admit_authority_at_startup))


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

    keys = (STORAGE_ROOT.variable, "CADRUMO_DATABASE_URL")
    saved = {key: os.environ.get(key) for key in keys}
    # Metadata commands still isolate themselves from the operator's active
    # database, while their throwaway files follow the configured Cadrumo temp
    # directory instead of the OS-wide temp directory.
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from ...core.errors.hierarchy import InternalInvariantError
    from ...core.storage_taxonomy import StorageCategory
    from ...core.storage_taxonomy_locations import storage_location

    temporary_location = storage_location(StorageCategory.TEMPORARY_FILES)
    if temporary_location.settings_field is None:
        raise InternalInvariantError("temporary storage location must declare its environment setting")
    temporary_base = storage_directory(
        temporary_location.settings_field.upper(),
        temporary_location.relative_path().as_posix(),
    )
    temporary_base.mkdir(parents=True, exist_ok=True, mode=0o700)
    with TemporaryDirectory(prefix="cadrumo-cli-metadata-", dir=temporary_base) as temporary_root:
        root = Path(temporary_root)
        os.environ[STORAGE_ROOT.variable] = str(root)
        database_filename = storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath
        os.environ["CADRUMO_DATABASE_URL"] = f"sqlite:///{(root / database_filename).as_posix()}"
        try:
            yield
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


async def _emit_operator_progress(progress: object) -> None:
    """Write an in-process operator progress banner to stderr, keeping stdout pure."""
    import typer

    from ...core.operator_progress import OperatorProgress

    if not isinstance(progress, OperatorProgress):
        raise TypeError(f"progress must be OperatorProgress, got {type(progress).__name__}")
    typer.echo(progress.render(), err=True)


def _jsonable_command_surface_value(value: object) -> object:
    """Project command-surface records onto a process-safe JSON value.

    The external client distribution is a separately shipped outer composition root.  It
    receives this projection by launching the CLI process; it must not import
    this entrypoint package merely to inspect the command graph.  The helper is
    intentionally local to the CLI transport: the application port owns the
    wire records, while this root owns the graph-specific dataclass projection.
    """
    from dataclasses import fields, is_dataclass
    from enum import Enum

    from pydantic import BaseModel

    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _jsonable_command_surface_value(getattr(value, field.name)) for field in fields(value)}
    if is_object_dict(value):
        return {str(key): _jsonable_command_surface_value(item) for key, item in value.items()}
    if is_object_collection(value):
        return _jsonable_command_surface_collection(value)
    if isinstance(value, BaseModel):
        return _jsonable_command_surface_value(value.model_dump(mode="json"))
    return value


def _emit_command_surface_manifest() -> None:
    """Emit the graph-owned Tax command surface through its process interface.

    External command consumers invoke the installed ``aeat`` executable and
    read this closed JSON projection. The graph, result schemas, policies and
    input projections remain authoritative in the Tax CLI composition root;
    consumers read its process output without importing the entrypoint.
    """
    import json

    import typer

    from .command_schema import command_registration_projection, command_schema_refs, command_schema_type
    from .operator_surface_reconciliation import recorded_command_operation_join
    from .verb_input_schema import build_verb_input_schemas, is_exposable_command

    references = command_schema_refs()
    command_keys = tuple(reference.command for reference in references)
    input_schemas = build_verb_input_schemas(command_keys)
    policies: dict[str, dict[str, object]] = {}
    result_schemas: dict[str, object] = {}
    search_terms: dict[str, tuple[str, ...]] = {}
    for reference in references:
        key = reference.command
        schema = input_schemas[key]
        policy = _declared_execution_policy_for_cli_path(schema.cli_path)
        policies[key] = {
            "cli_path": schema.cli_path,
            "capabilities": tuple(sorted(policy.classification.capabilities)),
            "side_effects": tuple(sorted(policy.classification.side_effects)),
            "performance": policy.classification.performance,
            "write_route": policy.write_route,
            "destructive": policy.destructive,
            "handoff": policy.handoff,
            "live_write": policy.live_write,
        }
        result_schemas[key] = command_schema_type(key).model_json_schema()
        spec = _COMMAND_GRAPH.by_schema_identity().get(key)
        if spec is None:
            raise LookupError(f"unknown command schema identity: {key}")
        search_terms[key] = spec.search_terms

    payload = {
        "command_operations": recorded_command_operation_join().model_dump(mode="json"),
        "command_schemas": tuple(reference.model_dump(mode="json") for reference in references),
        "global_flags": _command_surface_global_flags(),
        "exposable_commands": tuple(
            reference.command for reference in references if is_exposable_command(reference.command)
        ),
        "input_schemas": {key: schema.model_dump(mode="json") for key, schema in input_schemas.items()},
        "result_schemas": result_schemas,
        "policies": policies,
        "search_terms": search_terms,
        "registration_projection": _jsonable_command_surface_value(command_registration_projection()),
    }
    typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


__all__ = [
    "cli_app",
    "command_execution_policy_for_cli_path",
    "main",
]


def _command_surface_global_flags() -> tuple[str, ...]:
    """Enumerate every root option declaration in command-graph order."""
    return tuple(
        option
        for parameter in _COMMAND_GRAPH.root().parameters
        for option in getattr(parameter, "declarations", ())
        if isinstance(option, str) and option.startswith("-")
    )


def _jsonable_command_surface_collection(value: Collection[object]) -> list[object]:
    """Preserve ordered collections and the existing stable spelling order for sets."""
    items = (_jsonable_command_surface_value(item) for item in value)
    return sorted(items, key=str) if isinstance(value, (set, frozenset)) else list(items)
