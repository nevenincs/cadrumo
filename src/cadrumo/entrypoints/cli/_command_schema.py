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
import json
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import TYPE_CHECKING, Literal, cast, get_args

if TYPE_CHECKING:
    from ...application.operator_surface import CommandSchemaRef
    from ._command_policy import CommandExecutionPolicy, CommandWriteRouteScope

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

CommandParameterKind = Literal["argument", "option"]
CommandJsonType = Literal["string", "integer", "number", "boolean"]
CommandParameterDefault = bool | int | float | str | tuple[bool | int | float | str | None, ...] | None


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


@dataclass(frozen=True, slots=True)
class CommandParameterMetadata:
    """Immutable operator-facing parameter declaration."""

    name: str
    kind: CommandParameterKind
    cli_flag: str
    off_flag: str
    json_type: CommandJsonType
    required: bool
    is_flag: bool
    multiple: bool
    choices: tuple[str, ...]
    default: CommandParameterDefault
    help: str


@dataclass(frozen=True, slots=True)
class CommandPolicyMetadata:
    """Immutable serialization of one callback-attached execution policy."""

    capabilities: frozenset[CommandCapability]
    side_effects: frozenset[CommandSideEffectClass]
    performance: CommandPerformanceClass
    write_route: Literal["none", "profile-bound", "bootstrap-root"]
    destructive: bool
    handoff: bool
    live_write: bool


@dataclass(frozen=True, slots=True)
class CommandRegistrationMetadata:
    """Import-light registration projection for one result-schema identity.

    The generated payload is an acceleration index, not a second authority:
    each row carries the materialized callback source identity and the parity
    gate regenerates the complete projection from Click and the result-schema
    decorators.  Runtime discovery therefore reads parameters, localized help,
    hidden/deprecation flags, and execution policy without importing a handler
    subtree.
    """

    command: str
    schema_name: str
    schema_owner: str
    schema_source_sha256: str
    cli_path: tuple[str, ...] | None
    parameters_by_language: tuple[tuple[str, tuple[CommandParameterMetadata, ...] | None], ...]
    help_by_language: tuple[tuple[str, str], ...]
    hidden: bool | None
    deprecated: bool | str | None
    policy: CommandPolicyMetadata | None
    handler_owner: str | None
    source_sha256: str | None

    @property
    def help(self) -> dict[str, str]:
        """Return the localized help projection as a fresh mapping."""
        return dict(self.help_by_language)

    @property
    def parameters(self) -> dict[str, tuple[CommandParameterMetadata, ...] | None]:
        """Return localized parameter declarations as a fresh mapping."""
        return dict(self.parameters_by_language)


_REGISTRATION_METADATA_RESOURCE = "command_registration_metadata.v1.json"


@dataclass(frozen=True, slots=True)
class LiveNodeRegistrationMetadata:
    """One generated root/group/leaf identity from the complete live census."""

    path: tuple[str, ...]
    kind: Literal["root", "group", "leaf"]
    loader_owner: str | None
    handler_owner: str
    source_sha256: str | None
    policy: CommandPolicyMetadata | None


@dataclass(frozen=True, slots=True)
class CommandRegistrationProjection:
    """Complete cached generated projection for discovery and parity gates."""

    commands: tuple[CommandRegistrationMetadata, ...]
    nodes: tuple[LiveNodeRegistrationMetadata, ...]


def _policy_metadata(record: dict[str, object] | None) -> CommandPolicyMetadata | None:
    if record is None:
        return None
    return CommandPolicyMetadata(
        capabilities=frozenset(cast("list[CommandCapability]", record["capabilities"])),
        side_effects=frozenset(cast("list[CommandSideEffectClass]", record["side_effects"])),
        performance=cast("CommandPerformanceClass", record["performance"]),
        write_route=cast("CommandWriteRouteScope", record["write_route"]),
        destructive=cast("bool", record["destructive"]),
        handoff=cast("bool", record["handoff"]),
        live_write=cast("bool", record["live_write"]),
    )


def _parameter_metadata(record: dict[str, object]) -> CommandParameterMetadata:
    default = record["default"]
    if isinstance(default, list):
        default = tuple(default)
    return CommandParameterMetadata(
        name=cast("str", record["name"]),
        kind=cast("CommandParameterKind", record["kind"]),
        cli_flag=cast("str", record["cli_flag"]),
        off_flag=cast("str", record["off_flag"]),
        json_type=cast("CommandJsonType", record["json_type"]),
        required=cast("bool", record["required"]),
        is_flag=cast("bool", record["is_flag"]),
        multiple=cast("bool", record["multiple"]),
        choices=tuple(cast("list[str]", record["choices"])),
        default=cast("CommandParameterDefault", default),
        help=cast("str", record["help"]),
    )


@cache
def command_registration_projection() -> CommandRegistrationProjection:
    """Read and validate the generated command contract exactly once."""
    payload = json.loads(files(__package__).joinpath(_REGISTRATION_METADATA_RESOURCE).read_text(encoding="utf-8"))
    if payload.get("format_version") != 1:
        raise ValueError("unsupported command registration metadata format")
    rows = tuple(
        CommandRegistrationMetadata(
            command=row["command"],
            schema_name=row["schema_name"],
            schema_owner=row["schema_owner"],
            schema_source_sha256=row["schema_source_sha256"],
            cli_path=tuple(row["cli_path"]) if row["cli_path"] is not None else None,
            parameters_by_language=tuple(
                sorted(
                    (
                        language,
                        tuple(_parameter_metadata(parameter) for parameter in parameters)
                        if parameters is not None
                        else None,
                    )
                    for language, parameters in row["parameters_by_language"].items()
                )
            ),
            help_by_language=tuple(sorted(row["help_by_language"].items())),
            hidden=row["hidden"],
            deprecated=row["deprecated"],
            policy=_policy_metadata(row["policy"]),
            handler_owner=row["handler_owner"],
            source_sha256=row["source_sha256"],
        )
        for row in payload["commands"]
    )
    identities = tuple(row.command for row in rows)
    if identities != tuple(sorted(identities)) or len(set(identities)) != len(identities):
        raise ValueError("command registration metadata identities must be unique and sorted")
    nodes = tuple(
        LiveNodeRegistrationMetadata(
            path=tuple(row["path"]),
            kind=row["kind"],
            loader_owner=row["loader_owner"],
            handler_owner=row["handler_owner"],
            source_sha256=row["source_sha256"],
            policy=_policy_metadata(row["policy"]),
        )
        for row in payload["nodes"]
    )
    paths = tuple(node.path for node in nodes)
    if paths != tuple(sorted(paths)) or len(set(paths)) != len(paths):
        raise ValueError("live-node registration metadata paths must be unique and sorted")
    return CommandRegistrationProjection(commands=rows, nodes=nodes)


def command_registration_metadata() -> tuple[CommandRegistrationMetadata, ...]:
    """Return the cached immutable command registration rows."""
    return command_registration_projection().commands


@cache
def command_registration_policy(command: str) -> CommandExecutionPolicy:
    """Rebuild one callback policy from its import-light registration row.

    The return annotation stays opaque here to keep the capability taxonomy
    independent of its policy wrapper and avoid a module cycle.
    """
    from ._command_policy import CommandExecutionPolicy

    try:
        row = next(row for row in command_registration_metadata() if row.command == command)
    except StopIteration as error:
        raise LookupError(f"unknown command registration identity: {command}") from error
    policy = row.policy
    if policy is None:
        raise LookupError(f"command registration has no execution policy: {command}")
    classification = CommandCapabilityClass(
        capabilities=policy.capabilities,
        side_effects=policy.side_effects,
        performance=policy.performance,
    )
    return CommandExecutionPolicy(
        classification=classification,
        write_route=policy.write_route,
        destructive=policy.destructive,
        handoff=policy.handoff,
        live_write=policy.live_write,
    )


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


def _materialized_command_schema_refs() -> tuple[CommandSchemaRef, ...]:
    """Materialize result-schema owners for the generation/parity boundary."""
    _ensure_result_schemas_registered()
    return _project_registry()


@cache
def command_schema_refs() -> tuple[CommandSchemaRef, ...]:
    """Project result schemas from import-light registration metadata.

    Discards the per-module load failures - the consumers that need only the
    command set proceed with whatever schemas loaded, unbroken by a single bad
    module. A consumer that must report the failures reads them separately via
    :func:`_ensure_result_schemas_registered`.

    Returns:
        One :class:`CommandSchemaRef` per registered command, sorted by
        command name.
    """
    from ...application.operator_surface import CommandSchemaRef

    return tuple(
        CommandSchemaRef(command=row.command, schema_name=row.schema_name)
        for row in command_registration_metadata()
        if row.cli_path is not None
    )


__all__ = [
    "CommandCapability",
    "CommandCapabilityClass",
    "CommandParameterMetadata",
    "CommandPerformanceClass",
    "CommandPolicyMetadata",
    "CommandRegistrationMetadata",
    "CommandRegistrationProjection",
    "CommandSideEffectClass",
    "LiveNodeRegistrationMetadata",
    "SchemaModuleLoadFailure",
    "command_registration_metadata",
    "command_registration_policy",
    "command_registration_projection",
    "command_schema_refs",
]
