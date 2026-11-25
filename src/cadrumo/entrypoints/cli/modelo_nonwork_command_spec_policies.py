"""Shared execution-policy declarations for non-work Modelo CommandSpecs."""

from __future__ import annotations

from cadrumo_client.commands.spec import ExecutionPolicySpec
from cadrumo_client.contracts.command_ports import CommandWriteRoute

METADATA = ExecutionPolicySpec(frozenset(("state-free",)), frozenset(("none",)), "metadata", CommandWriteRoute.NONE)

BROWSER_MODEL_WRITE = ExecutionPolicySpec(
    frozenset(("aeat", "browser", "registry", "encrypted-facts")),
    frozenset(("browser", "local-state", "network")),
    "external-io",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
)

CALCULATION_READ = ExecutionPolicySpec(
    frozenset(("calculation", "encrypted-facts")),
    frozenset(("none",)),
    "compute",
    CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
)

CALCULATION_WRITE = ExecutionPolicySpec(
    frozenset(("calculation", "encrypted-facts")),
    frozenset(("local-state",)),
    "compute",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
)

CRYPTO_FACT_FILE_WRITE = ExecutionPolicySpec(
    frozenset(("crypto", "encrypted-facts")),
    frozenset(("local-state",)),
    "local-io",
    CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
)

CRYPTO_PROFILE_WRITE = ExecutionPolicySpec(
    frozenset(("crypto", "encrypted-facts")),
    frozenset(("local-state",)),
    "local-io",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
)

CRYPTO_READ = ExecutionPolicySpec(
    frozenset(("crypto",)),
    frozenset(("none",)),
    "local-io",
    CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
)

INTERACTIVE_MODEL_WRITE = ExecutionPolicySpec(
    frozenset(("calculation", "encrypted-facts")),
    frozenset(("local-state",)),
    "interactive",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
)

MODEL_HANDOFF = ExecutionPolicySpec(
    frozenset(("encrypted-facts", "filing")),
    frozenset(("local-state",)),
    "compute",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=True,
)

MODEL_READ = ExecutionPolicySpec(
    frozenset(("encrypted-facts",)),
    frozenset(("none",)),
    "local-io",
    CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
)

MODEL_WRITE = ExecutionPolicySpec(
    frozenset(("encrypted-facts",)),
    frozenset(("local-state",)),
    "local-io",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
)

REGISTRY_MODEL_READ = ExecutionPolicySpec(
    frozenset(("registry", "encrypted-facts")),
    frozenset(("none",)),
    "local-io",
    CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
)

REGISTRY_READ = ExecutionPolicySpec(
    frozenset(("registry",)), frozenset(("none",)), "compute", CommandWriteRoute.NONE, destructive=False, handoff=False
)

__all__ = [
    "BROWSER_MODEL_WRITE",
    "CALCULATION_READ",
    "CALCULATION_WRITE",
    "CRYPTO_FACT_FILE_WRITE",
    "CRYPTO_PROFILE_WRITE",
    "CRYPTO_READ",
    "INTERACTIVE_MODEL_WRITE",
    "METADATA",
    "MODEL_HANDOFF",
    "MODEL_READ",
    "MODEL_WRITE",
    "REGISTRY_MODEL_READ",
    "REGISTRY_READ",
]
