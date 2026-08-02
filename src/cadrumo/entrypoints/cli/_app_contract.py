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
import pkgutil

import typer
from pydantic import BaseModel, ConfigDict, Field

from ...application.operator_surface import (
    CommandSchemaRef,
    build_operator_surface_manifest,
)
from ...core.i18n import tr
from ...core.json_contract import ENVELOPE_SCHEMA_VERSION, SCHEMA_REGISTRY, Notice, NoticeSeverity
from ...core.logging import get_logger
from ._app_contract_payloads import ContractManifestResult
from ._common import _emit_envelope

logger = get_logger(__name__)

# The two package locations that own ``@register_schema``-decorated ``--json``
# result-payload modules. The registry populates lazily as the CLI dispatches
# into a subtree, so the manifest command force-loads every payload module first
# to enumerate the complete registered set. Limited to the payload directories
# so importing the manifest command never pulls the test tree.
_PAYLOAD_PACKAGES: tuple[str, ...] = (
    "cadrumo.entrypoints.cli",
    "cadrumo.entrypoints.cli._config",
)

# Result schemas normally live beside their CLI transport emitters and are
# found by the payload-package walk above. A small number are correctly owned
# below the application boundary, where their producers construct them. Keep
# those owners explicit rather than creating a CLI re-export merely to satisfy
# a filename-driven scanner. These imports occur only while building the
# capability manifest/MCP surface, never during command parsing or dispatch.
_LAZY_SCHEMA_OWNER_MODULES: tuple[str, ...] = (
    "cadrumo.application.wizard._results",
)


class SchemaModuleLoadFailure(BaseModel):
    """One payload module that failed to import during registry population.

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


def _ensure_result_schemas_registered(
    *,
    payload_packages: tuple[str, ...] | None = None,
) -> tuple[SchemaModuleLoadFailure, ...]:
    """Import every ``*_payloads`` module so ``SCHEMA_REGISTRY`` is complete.

    The CLI registers result schemas through module-level
    :func:`~entrypoints.cli._schemas.register_schema` decorators that only
    run when their payload module is imported. The manifest must reflect the
    whole registry, so this imports every payload module under the known payload
    packages before the projection is read. The ``payload`` substring match (not
    a strict ``_payloads`` suffix) is deliberate: the payload modules use three
    naming shapes - ``_<area>_payloads``, ``_payloads_<area>``, and
    ``_<area>_payloads_<variant>`` - and all must be loaded.

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
    for package_name in payload_packages or _PAYLOAD_PACKAGES:
        try:
            package = importlib.import_module(package_name)  # nosem
        except Exception as exc:
            failures.append(SchemaModuleLoadFailure(module=package_name, error=f"{type(exc).__name__}: {exc}"))
            continue
        for module_info in pkgutil.iter_modules(package.__path__):
            if "payload" in module_info.name and not module_info.ispkg:
                module_name = f"{package_name}.{module_info.name}"
                try:
                    importlib.import_module(module_name)  # nosem
                except Exception as exc:
                    failures.append(SchemaModuleLoadFailure(module=module_name, error=f"{type(exc).__name__}: {exc}"))
    for module_name in _LAZY_SCHEMA_OWNER_MODULES:
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


def command_schema_refs(*, payload_packages: tuple[str, ...] | None = None) -> tuple[CommandSchemaRef, ...]:
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
    _ensure_result_schemas_registered(payload_packages=payload_packages)
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
                default="Capability surface degraded: the result-schema module '{module}' failed to load "
                "({error}); the commands it registers are absent from this manifest. This is usually an "
                "unrelated in-flight code change, not a data problem.",
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
    through :class:`~entrypoints.cli._schemas.SchemaEnvelope` under the
    ``contract`` key. Read-only: no AEAT contact, no state mutation.
    """
    if ctx.invoked_subcommand is not None:
        return
    # Populate the registry resiliently: a broken payload module degrades the
    # manifest by one command and becomes a warning notice, never an opaque
    # crash of the grounding entry point (the command the operator rules read
    # first). Both calls walk an already-cached import set, so the second is a
    # near-no-op.
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
        tr("cli.contract.summary_heading", default="Operator surface manifest"),
        tr(
            "cli.contract.summary_roots",
            default="Roots: {roots}",
            roots=", ".join(getattr(root.name, "value", str(root.name)) for root in roots),
        ),
        tr(
            "cli.contract.summary_families",
            default="Command families: {count}",
            count=str(len(families)),
        ),
        tr(
            "cli.contract.summary_lifecycle",
            default="Modelo lifecycle: {steps}",
            steps=" -> ".join(getattr(step, "value", str(step)) for step in steps),
        ),
        tr(
            "cli.contract.summary_commands",
            default="Registered commands: {count}",
            count=str(command_count),
        ),
    ]
    return lines
