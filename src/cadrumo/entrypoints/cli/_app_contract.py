"""CLI command for ``aeat app contract`` - the operator capability manifest.

Emits the operator-surface capability manifest: the backend-owned
:class:`~application.operator_surface.OperatorSurfaceContract` (the two-root
command tree, each command family's intent and mutability, the modelo
``CALCULATE -> VERIFY -> FILE`` lifecycle, and the source-kind taxonomy) together
with the CLI's registered ``--json`` result-schema references. This is the
read-only capability catalogue an LLM operator reads up front instead of
scraping ``--help``, and the natural source a tool-exposure server consumes for
its tool list.

The command is a child of ``app`` (the CLI root surface is pinned to ``config``
and ``app``; this adds no third root). It never contacts AEAT and mutates no
stored state. The ``command_schemas`` half of the manifest is the CLI's own
JSON-contract registry, an entrypoint-layer concern enumerated here and injected
into :func:`~application.operator_surface.build_operator_surface_manifest`,
so the application layer never depends on this package.
"""

from __future__ import annotations

import importlib

import typer
from pydantic import BaseModel, ConfigDict, Field

from ...application.operator_surface import (
    CommandSchemaRef,
    build_operator_surface_manifest,
)
from ...core.i18n import tr
from ...core.json_contract import ENVELOPE_SCHEMA_VERSION, SCHEMA_REGISTRY, Notice, NoticeSeverity
from ...core.logging import get_logger
from ..schema_surface import RESULT_SCHEMA_MODULES
from ._app_contract_payloads import ContractManifestResult
from ._common import _emit_envelope

logger = get_logger(__name__)


class SchemaModuleLoadFailure(BaseModel):
    """One declared result-schema module that failed to populate the registry.

    Carried so the contract command can DEGRADE GRACEFULLY: a single broken
    payload module (typically an unrelated in-flight refactor that trips a
    transitive import) must not crash the whole capability surface — the
    operator rules mandate reading the contract FIRST, so it is the one command
    that must survive a broken peer module and NAME what failed rather than
    emitting an opaque internal error.
    """

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    module: str = Field(min_length=1)
    error: str = Field(min_length=1)


def _ensure_result_schemas_registered() -> tuple[SchemaModuleLoadFailure, ...]:
    """Import each canonical result-schema owner so ``SCHEMA_REGISTRY`` is complete.

    The CLI registers result schemas through module-level
    :func:`~core.json_contract.register_schema` decorators that only
    run when their owning module is imported. The manifest imports the one
    canonical declaration from :mod:`entrypoints.schema_surface`; it never
    infers owners from package contents or filenames.

    RESILIENT: each payload module import is isolated in its own ``try`` so a
    single broken module contributes ONE :class:`SchemaModuleLoadFailure` and
    the walk continues loading the rest. Nothing here raises for a per-module
    failure - the caller decides how to surface the failures (the contract
    command turns each into a ``warning`` notice; the MCP tool builder simply
    proceeds with the schemas that did load). A broken payload module thus
    degrades the manifest by exactly one command, never crashes the whole
    surface.

    Returns:
        The load failures, empty when every payload module imported cleanly.
    """
    failures: list[SchemaModuleLoadFailure] = []
    for module_name in RESULT_SCHEMA_MODULES:
        try:
            importlib.import_module(module_name)  # nosem
        except Exception as exc:
            failures.append(SchemaModuleLoadFailure(module=module_name, error=f"{type(exc).__name__}: {exc}"))
    return tuple(failures)


def _project_registry() -> tuple[CommandSchemaRef, ...]:
    """Project the currently-populated ``SCHEMA_REGISTRY`` into manifest references."""
    return tuple(
        CommandSchemaRef(command=command, schema_name=schema.__name__)
        for command, schema in sorted(SCHEMA_REGISTRY.items())
    )


def command_schema_refs() -> tuple[CommandSchemaRef, ...]:
    """Populate the registry (resiliently) and project it into manifest references.

    Discards the per-module load failures - the consumers that need only the
    command set (the MCP tool builder, conformance tests) proceed with whatever
    schemas loaded, unbroken by a single bad module. The contract command reads
    the failures separately via :func:`_ensure_result_schemas_registered` to
    surface them as notices.

    Returns:
        One :class:`CommandSchemaRef` per registered command, sorted by
        command name.
    """
    _ensure_result_schemas_registered()
    return _project_registry()


def _schema_load_notices(failures: tuple[SchemaModuleLoadFailure, ...]) -> list[Notice]:
    """One ``warning`` notice per payload module that failed to load."""
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code="contract.schema_module_load_failed",
            message=tr(
                "cli.contract.schema_module_load_failed",
                module=failure.module,
                error=failure.error,
            ),
            context={"module": failure.module, "error": failure.error},
        )
        for failure in failures
    ]


app = typer.Typer(
    name="contract",
    help=tr("cli.contract.app_help"),
    no_args_is_help=False,
    invoke_without_command=True,
)


@app.callback()
def _contract_root(ctx: typer.Context) -> None:
    """Emit the operator-surface capability manifest.

    Builds the
    :class:`~application.operator_surface.OperatorSurfaceManifest` from the
    cached contract and the CLI's registered result schemas, then surfaces it
    through :class:`~core.json_contract.SchemaEnvelope` under the
    ``contract`` key. Read-only: no AEAT contact, no state mutation.
    """
    if ctx.invoked_subcommand is not None:
        return
    # Populate the registry from its canonical owner declaration. A broken
    # declared module becomes a typed warning notice rather than an opaque crash
    # of the grounding entry point. Both calls reuse Python's import cache.
    load_failures = _ensure_result_schemas_registered()
    command_schemas = _project_registry()
    manifest = build_operator_surface_manifest(
        envelope_schema_version=ENVELOPE_SCHEMA_VERSION,
        command_schemas=command_schemas,
    )
    result = ContractManifestResult.model_validate(manifest.model_dump(mode="python"))
    _emit_envelope(
        ctx,
        command="contract",
        result=result,
        lines=_render_contract_lines(manifest.contract, len(command_schemas)),
        notices=_schema_load_notices(load_failures),
    )
    raise typer.Exit()


def _render_contract_lines(contract: object, command_count: int) -> list[str]:
    """Render a concise human summary of the manifest for text mode.

    The JSON envelope is the contract; this terminal summary names the roots,
    the mounted command-family count, the lifecycle, and the registered command
    count so a human reader gets orientation without parsing the JSON.
    """
    families = getattr(contract, "command_families", ())
    lifecycle = getattr(contract, "lifecycle", None)
    steps = getattr(lifecycle, "steps", ()) if lifecycle is not None else ()
    roots = getattr(contract, "roots", ())
    lines = [
        tr("cli.contract.summary_heading"),
        tr(
            "cli.contract.summary_roots",
            roots=", ".join(getattr(root.name, "value", str(root.name)) for root in roots),
        ),
        tr(
            "cli.contract.summary_families",
            count=str(len(families)),
        ),
        tr(
            "cli.contract.summary_lifecycle",
            steps=" -> ".join(getattr(step, "value", str(step)) for step in steps),
        ),
        tr(
            "cli.contract.summary_commands",
            count=str(command_count),
        ),
    ]
    return lines
