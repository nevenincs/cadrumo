"""Typed public command-contract API for operator and harness consumers.

This module is the supported cross-package boundary for immutable CommandSpec
projections.  It contains no command handlers and does not materialise Typer.
"""

from __future__ import annotations

from ._command_policy import CommandExecutionPolicy
from ._command_schema import (
    MachineSecretPayloadMetadata,
    ProfileAuthenticationContractMetadata,
    command_registration_projection,
    command_schema_refs,
    command_schema_type,
    command_schema_types,
)
from ._command_spec import ArgumentSpec, CommandSpec, CommandSpecNode, DefaultKind, OptionSpec
from ._command_specs import COMMAND_GRAPH
from ._verb_input_schema import (
    DECLARED_UNIMPLEMENTED_SURFACES,
    JsonType,
    ResolvedVerbLeaf,
    SchemaResolutionError,
    VerbInputSchema,
    VerbLeafKind,
    VerbLeafResolutionFailure,
    VerbParameter,
    VerbParamKind,
    assert_schema_coverage,
    build_verb_input_schemas,
    cli_argv_for,
    cli_path_for_command_key,
    is_exposable_command,
)


def command_spec_nodes() -> tuple[CommandSpecNode, ...]:
    """Return the immutable, path-derived production command projection."""
    return COMMAND_GRAPH.nodes()


def command_spec_for_path(path: tuple[str, ...]) -> CommandSpec:
    """Resolve one exact operator path from the production command graph."""
    return COMMAND_GRAPH.resolve_path(path)

__all__ = [
    "DECLARED_UNIMPLEMENTED_SURFACES",
    "ArgumentSpec",
    "CommandExecutionPolicy",
    "CommandSpec",
    "CommandSpecNode",
    "DefaultKind",
    "JsonType",
    "MachineSecretPayloadMetadata",
    "OptionSpec",
    "ProfileAuthenticationContractMetadata",
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
    "command_registration_projection",
    "command_schema_refs",
    "command_schema_type",
    "command_schema_types",
    "command_spec_for_path",
    "command_spec_nodes",
    "is_exposable_command",
]
