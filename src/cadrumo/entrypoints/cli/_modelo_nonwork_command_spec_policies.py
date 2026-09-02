"""Shared execution-policy declarations for non-work Modelo CommandSpecs."""

from __future__ import annotations

from .command_spec import CommandWriteRoute, ExecutionPolicySpec

_METADATA = ExecutionPolicySpec(frozenset(("state-free",)), frozenset(("none",)), "metadata", CommandWriteRoute.NONE)

_BROWSER_MODEL_WRITE = ExecutionPolicySpec(
    frozenset(("browser", "registry", "encrypted-facts")),
    frozenset(("browser", "local-state", "network")),
    "external-io",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
)

_CALCULATION_READ = ExecutionPolicySpec(
    frozenset(("calculation", "encrypted-facts")),
    frozenset(("none",)),
    "compute",
    CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
)

_CALCULATION_WRITE = ExecutionPolicySpec(
    frozenset(("calculation", "encrypted-facts")),
    frozenset(("local-state",)),
    "compute",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
)

_CRYPTO_FACT_FILE_WRITE = ExecutionPolicySpec(
    frozenset(("crypto", "encrypted-facts")),
    frozenset(("local-state",)),
    "local-io",
    CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
)

_CRYPTO_PROFILE_WRITE = ExecutionPolicySpec(
    frozenset(("crypto", "encrypted-facts")),
    frozenset(("local-state",)),
    "local-io",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
)

_CRYPTO_READ = ExecutionPolicySpec(
    frozenset(("crypto",)),
    frozenset(("none",)),
    "local-io",
    CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
)

_INTERACTIVE_MODEL_WRITE = ExecutionPolicySpec(
    frozenset(("calculation", "encrypted-facts")),
    frozenset(("local-state",)),
    "interactive",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
)

_MODEL_HANDOFF = ExecutionPolicySpec(
    frozenset(("encrypted-facts", "filing")),
    frozenset(("local-state",)),
    "compute",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=True,
)

_MODEL_READ = ExecutionPolicySpec(
    frozenset(("encrypted-facts",)),
    frozenset(("none",)),
    "local-io",
    CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
)

_MODEL_WRITE = ExecutionPolicySpec(
    frozenset(("encrypted-facts",)),
    frozenset(("local-state",)),
    "local-io",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
)

_REGISTRY_MODEL_READ = ExecutionPolicySpec(
    frozenset(("registry", "encrypted-facts")),
    frozenset(("none",)),
    "local-io",
    CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
)

_REGISTRY_READ = ExecutionPolicySpec(
    frozenset(("registry",)), frozenset(("none",)), "compute", CommandWriteRoute.NONE, destructive=False, handoff=False
)

__all__ = [
    "_BROWSER_MODEL_WRITE",
    "_CALCULATION_READ",
    "_CALCULATION_WRITE",
    "_CRYPTO_FACT_FILE_WRITE",
    "_CRYPTO_PROFILE_WRITE",
    "_CRYPTO_READ",
    "_INTERACTIVE_MODEL_WRITE",
    "_METADATA",
    "_MODEL_HANDOFF",
    "_MODEL_READ",
    "_MODEL_WRITE",
    "_REGISTRY_MODEL_READ",
    "_REGISTRY_READ",
]
