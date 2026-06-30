"""CLI command for ``aeat app contract`` - the operator capability manifest.

Emits the operator-surface capability manifest: the backend-owned
:class:`~aeat.application.operator_surface.OperatorSurfaceContract` (the two-root
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
into :func:`~aeat.application.operator_surface.build_operator_surface_manifest`,
so the application layer never depends on this package.
"""

from __future__ import annotations

import importlib
import pkgutil

import typer

from ...application.operator_surface import (
    CommandSchemaRef,
    build_operator_surface_manifest,
)
from ...core.i18n import tr
from ...core.json_contract import ENVELOPE_SCHEMA_VERSION, SCHEMA_REGISTRY
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
    "aeat.entrypoints.cli",
    "aeat.entrypoints.cli._config",
)


def _ensure_result_schemas_registered() -> None:
    """Import every ``*_payloads`` module so ``SCHEMA_REGISTRY`` is complete.

    The CLI registers result schemas through module-level
    :func:`~aeat.entrypoints.cli._schemas.register_schema` decorators that only
    run when their payload module is imported. The manifest must reflect the
    whole registry, so this imports every payload module under the known payload
    packages before the projection is read. The ``payload`` substring match (not
    a strict ``_payloads`` suffix) is deliberate: the payload modules use three
    naming shapes - ``_<area>_payloads``, ``_payloads_<area>``, and
    ``_<area>_payloads_<variant>`` - and all must be loaded.
    """
    for package_name in _PAYLOAD_PACKAGES:
        package = importlib.import_module(package_name)
        for module_info in pkgutil.iter_modules(package.__path__):
            if "payload" in module_info.name and not module_info.ispkg:
                importlib.import_module(f"{package_name}.{module_info.name}")


def _command_schema_refs() -> tuple[CommandSchemaRef, ...]:
    """Project the populated ``SCHEMA_REGISTRY`` into manifest references."""
    _ensure_result_schemas_registered()
    return tuple(
        CommandSchemaRef(command=command, schema_name=schema.__name__)
        for command, schema in sorted(SCHEMA_REGISTRY.items())
    )


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
    :class:`~aeat.application.operator_surface.OperatorSurfaceManifest` from the
    cached contract and the CLI's registered result schemas, then surfaces it
    through :class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope` under the
    ``contract`` key. Read-only: no AEAT contact, no state mutation.
    """
    if ctx.invoked_subcommand is not None:
        return
    command_schemas = _command_schema_refs()
    manifest = build_operator_surface_manifest(
        envelope_schema_version=ENVELOPE_SCHEMA_VERSION,
        command_schemas=command_schemas,
    )
    result = ContractManifestResult.model_validate(manifest.model_dump(mode="json"))
    _emit_envelope(
        ctx,
        command="contract",
        result=result,
        lines=_render_contract_lines(manifest.contract, len(command_schemas)),
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
