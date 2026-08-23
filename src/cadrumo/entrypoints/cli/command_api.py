"""Typed public command-contract API for operator and harness consumers.

This module is the supported cross-package boundary for immutable CommandSpec
projections.  It contains no command handlers and does not materialise Typer.
"""

from __future__ import annotations

from ._command_policy import CommandExecutionPolicy
from ._command_schema import command_schema_refs, command_schema_type, command_schema_types
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

__all__ = [
    "DECLARED_UNIMPLEMENTED_SURFACES",
    "CommandExecutionPolicy",
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
    "command_schema_refs",
    "command_schema_type",
    "command_schema_types",
    "is_exposable_command",
]
