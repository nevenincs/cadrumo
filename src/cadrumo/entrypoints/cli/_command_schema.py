"""Projection of the CLI's registered ``--json`` result schemas.

The CLI registers result schemas through module-level
:func:`~core.json_contract.register_schema` decorators that run only when their
owning payload module is imported. This module owns the one canonical way to
populate that registry and project it into
:class:`~application.operator_surface.CommandSchemaRef` records: the
entrypoint-layer half of the operator capability manifest, which
:func:`~application.operator_surface.build_operator_surface_manifest` composes
with the backend-owned
:class:`~application.operator_surface.OperatorSurfaceContract`.

There is no CLI verb over this projection. The capability manifest is a plain
Python surface: consumers — the tool-exposure server, conformance gates,
documentation generators — call :func:`command_schema_refs` directly, and the
function is re-exported from the package facade
(``cadrumo.entrypoints.cli.command_schema_refs``) for cross-package callers.

The projection stays in the entrypoints layer because the schema registry is
the CLI's own JSON contract; the application layer never depends on this
package.
"""

from __future__ import annotations

import importlib

from pydantic import BaseModel, ConfigDict, Field

from ...application.operator_surface import CommandSchemaRef
from ...core.json_contract import SCHEMA_REGISTRY
from ..schema_surface import RESULT_SCHEMA_MODULES


class SchemaModuleLoadFailure(BaseModel):
    """One declared result-schema module that failed to populate the registry.

    Carried so the projection can DEGRADE GRACEFULLY: a single broken payload
    module (typically an unrelated in-flight refactor that trips a transitive
    import) must not crash the whole capability surface — the operator reads
    the capability manifest FIRST, so it is the one surface that must survive a
    broken peer module and NAME what failed rather than raising an opaque
    internal error.
    """

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    module: str = Field(min_length=1)
    error: str = Field(min_length=1)


def _ensure_result_schemas_registered() -> tuple[SchemaModuleLoadFailure, ...]:
    """Import each canonical result-schema owner so ``SCHEMA_REGISTRY`` is complete.

    The projection imports the one canonical declaration from
    :mod:`entrypoints.schema_surface`; it never infers owners from package
    contents or filenames.

    RESILIENT: each payload module import is isolated in its own ``try`` so a
    single broken module contributes ONE :class:`SchemaModuleLoadFailure` and
    the walk continues loading the rest. Nothing here raises for a per-module
    failure - the caller decides how to surface the failures. A broken payload
    module thus degrades the manifest by exactly one command, never crashes the
    whole surface.

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
    command set proceed with whatever schemas loaded, unbroken by a single bad
    module. A consumer that must report the failures reads them separately via
    :func:`_ensure_result_schemas_registered`.

    Returns:
        One :class:`CommandSchemaRef` per registered command, sorted by
        command name.
    """
    _ensure_result_schemas_registered()
    return _project_registry()


__all__ = ["SchemaModuleLoadFailure", "command_schema_refs"]
