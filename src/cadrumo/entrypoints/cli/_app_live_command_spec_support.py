"""Shared immutable building blocks for live CommandSpec declarations."""

from __future__ import annotations

from typing import Final

from .command_spec import (
    CommandWriteRoute,
    ExecutionPolicySpec,
    InvocationSpec,
    ResultSchemaSpec,
    SchemaState,
)
from .command_spec import (
    translation_key as _key,
)

_METADATA_GROUP_INVOCATION: Final[InvocationSpec] = InvocationSpec(
    no_args_is_help=True,
    context_parameter=None,
)
_LEAF_INVOCATION: Final[InvocationSpec] = InvocationSpec(
    no_args_is_help=False,
    context_parameter="ctx",
)
_METADATA_POLICY: Final[ExecutionPolicySpec] = ExecutionPolicySpec(
    capabilities=frozenset(["state-free"]),
    side_effects=frozenset(["none"]),
    performance="metadata",
    write_route=CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
    live_write=False,
)
_ENCRYPTED_LOCAL_READ_POLICY: Final[ExecutionPolicySpec] = ExecutionPolicySpec(
    capabilities=frozenset(["encrypted-facts"]),
    side_effects=frozenset(["none"]),
    performance="local-io",
    write_route=CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
    live_write=False,
)
_PROFILE_BOUND_NETWORK_CAPTURE_POLICY: Final[ExecutionPolicySpec] = ExecutionPolicySpec(
    capabilities=frozenset(["encrypted-facts", "network"]),
    side_effects=frozenset(["local-state", "network"]),
    performance="external-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
    live_write=False,
)
NO_RESULT_SCHEMA: Final[ResultSchemaSpec] = ResultSchemaSpec(SchemaState.NOT_SUPPORTED)

__all__ = [
    "NO_RESULT_SCHEMA",
    "_ENCRYPTED_LOCAL_READ_POLICY",
    "_LEAF_INVOCATION",
    "_METADATA_GROUP_INVOCATION",
    "_METADATA_POLICY",
    "_PROFILE_BOUND_NETWORK_CAPTURE_POLICY",
    "_key",
]
