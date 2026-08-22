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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, get_args

if TYPE_CHECKING:
    from ...application.operator_surface import CommandSchemaRef

CommandCapability = Literal[
    "state-free",
    "local-storage",
    "registry",
    "profile-custody",
    "encrypted-facts",
    "network",
    "browser",
    "google",
    "calculation",
    "filing",
    "crypto",
    "subprocess",
]
"""Authority families a command may enter while it executes.

``state-free`` is an affirmative declaration that a node needs none of the
other authorities. ``local-storage`` covers application-local files such as
telemetry that are neither profile custody nor encrypted taxpayer facts.
``subprocess`` declares child-process inspection or control independently of
network and browser authority. The remaining values are composable. Capability
implications keep registrations concise while preserving the full import
boundary used by gates.
"""

CommandSideEffectClass = Literal["none", "local-state", "network", "browser", "google"]
"""Observable effects an invocation is permitted to cause."""

CommandPerformanceClass = Literal["metadata", "local-io", "compute", "external-io", "interactive"]
"""Host-independent workload lane used to select calibrated command budgets."""

_COMMAND_CAPABILITIES = frozenset(get_args(CommandCapability))
_COMMAND_SIDE_EFFECT_CLASSES = frozenset(get_args(CommandSideEffectClass))
_COMMAND_PERFORMANCE_CLASSES = frozenset(get_args(CommandPerformanceClass))

_IMPLIED_CAPABILITIES: dict[CommandCapability, frozenset[CommandCapability]] = {
    "encrypted-facts": frozenset({"profile-custody"}),
    "browser": frozenset({"network"}),
    "google": frozenset({"network"}),
    "calculation": frozenset({"registry"}),
    "filing": frozenset({"registry"}),
}


@dataclass(frozen=True, slots=True)
class CommandCapabilityClass:
    """Minimal execution contract attached to a live command node.

    The record describes authorities, effects, and the workload lane without
    importing an owning command module. It deliberately carries no command
    path: the live command authority owns paths, and reconciliation joins the
    two exact sets rather than maintaining another verb inventory here.
    """

    capabilities: frozenset[CommandCapability]
    side_effects: frozenset[CommandSideEffectClass]
    performance: CommandPerformanceClass

    def __post_init__(self) -> None:
        """Reject contradictory or untyped metadata at its declaration site."""
        unknown_capabilities = self.capabilities - _COMMAND_CAPABILITIES
        if unknown_capabilities:
            raise ValueError(f"unknown command capabilities: {sorted(unknown_capabilities)}")
        unknown_effects = self.side_effects - _COMMAND_SIDE_EFFECT_CLASSES
        if unknown_effects:
            raise ValueError(f"unknown command side effects: {sorted(unknown_effects)}")
        if self.performance not in _COMMAND_PERFORMANCE_CLASSES:
            raise ValueError(f"unknown command performance class: {self.performance}")
        if "state-free" in self.capabilities and self.capabilities != frozenset({"state-free"}):
            raise ValueError("state-free cannot be combined with authority-bearing capabilities")
        if not self.capabilities:
            raise ValueError("command capabilities must explicitly declare state-free or an authority")
        if not self.side_effects:
            raise ValueError("command side effects must explicitly declare none or an effect")
        if "none" in self.side_effects and self.side_effects != frozenset({"none"}):
            raise ValueError("the none side-effect class cannot be combined with effects")

        expanded = self.expanded_capabilities
        required_by_effect: dict[CommandSideEffectClass, CommandCapability] = {
            "network": "network",
            "browser": "browser",
            "google": "google",
        }
        for effect, required in required_by_effect.items():
            if effect in self.side_effects and required not in expanded:
                raise ValueError(f"the {effect} side effect requires the {required} capability")
        if self.capabilities == frozenset({"state-free"}) and self.side_effects != frozenset({"none"}):
            raise ValueError("state-free commands must be effect-free")

    @property
    def expanded_capabilities(self) -> frozenset[CommandCapability]:
        """Return the transitive authority set used by import/capability gates."""
        expanded = set(self.capabilities)
        pending = list(self.capabilities)
        while pending:
            capability = pending.pop()
            for implied in _IMPLIED_CAPABILITIES.get(capability, ()):
                if implied not in expanded:
                    expanded.add(implied)
                    pending.append(implied)
        return frozenset(expanded)


@dataclass(frozen=True, slots=True)
class SchemaModuleLoadFailure:
    """One declared result-schema module that failed to populate the registry.

    Carried so the projection can DEGRADE GRACEFULLY: a single broken payload
    module (typically an unrelated in-flight refactor that trips a transitive
    import) must not crash the whole capability surface — the operator reads
    the capability manifest FIRST, so it is the one surface that must survive a
    broken peer module and NAME what failed rather than raising an opaque
    internal error.
    """

    module: str
    error: str


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
    from ..schema_surface import RESULT_SCHEMA_MODULES

    failures: list[SchemaModuleLoadFailure] = []
    for module_name in RESULT_SCHEMA_MODULES:
        try:
            importlib.import_module(module_name)  # nosem
        except Exception as exc:
            failures.append(SchemaModuleLoadFailure(module=module_name, error=f"{type(exc).__name__}: {exc}"))
    return tuple(failures)


def _project_registry() -> tuple[CommandSchemaRef, ...]:
    """Project the currently-populated ``SCHEMA_REGISTRY`` into manifest references."""
    from ...application.operator_surface import CommandSchemaRef
    from ...core.json_contract import SCHEMA_REGISTRY

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


__all__ = [
    "CommandCapability",
    "CommandCapabilityClass",
    "CommandPerformanceClass",
    "CommandSideEffectClass",
    "SchemaModuleLoadFailure",
    "command_schema_refs",
]
