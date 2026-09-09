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
from ._verb_input_schema import (
    ResolvedVerbLeaf,
    SchemaResolutionError,
    VerbInputSchema,
    VerbLeafKind,
    VerbLeafResolutionFailure,
    VerbParameter,
    assert_schema_coverage,
    build_verb_input_schemas,
    cli_argv_for,
    cli_path_for_command_key,
    is_exposable_command,
)
from .command_spec import ArgumentSpec, CommandSpec, CommandSpecNode, DefaultKind, JsonType, OptionSpec, ParameterKind

__all__ = [
    "ArgumentSpec",
    "CommandExecutionPolicy",
    "CommandSpec",
    "CommandSpecNode",
    "DefaultKind",
    "JsonType",
    "MachineSecretPayloadMetadata",
    "OptionSpec",
    "ParameterKind",
    "ProfileAuthenticationContractMetadata",
    "ResolvedVerbLeaf",
    "SchemaResolutionError",
    "VerbInputSchema",
    "VerbLeafKind",
    "VerbLeafResolutionFailure",
    "VerbParameter",
    "assert_schema_coverage",
    "build_verb_input_schemas",
    "cli_argv_for",
    "cli_path_for_command_key",
    "command_registration_projection",
    "command_schema_refs",
    "command_schema_type",
    "command_schema_types",
    "is_exposable_command",
]
