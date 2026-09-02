"""Import-light execution policies owned by the config command specifications."""

from __future__ import annotations

from ..command_spec import Capability, ExecutionPolicySpec, PerformanceClass, SideEffect, WriteRoute


def _policy(
    capabilities: frozenset[Capability],
    side_effects: frozenset[SideEffect],
    performance: PerformanceClass,
    *,
    write_route: WriteRoute = "none",
    destructive: bool = False,
    handoff: bool = False,
) -> ExecutionPolicySpec:
    return ExecutionPolicySpec(
        capabilities=capabilities,
        side_effects=side_effects,
        performance=performance,
        write_route=write_route,
        destructive=destructive,
        handoff=handoff,
    )


STATE_FREE = _policy(frozenset({"state-free"}), frozenset({"none"}), "metadata")
LOCAL_READ = _policy(frozenset({"state-free"}), frozenset({"none"}), "local-io")
PROFILE_READ = _policy(frozenset({"profile-custody"}), frozenset({"none"}), "local-io")
ENCRYPTED_READ = _policy(frozenset({"encrypted-facts"}), frozenset({"none"}), "local-io")
PROFILE_WRITE = _policy(
    frozenset({"profile-custody"}), frozenset({"local-state"}), "local-io", write_route="profile-bound"
)
PROFILE_DESTRUCTIVE = _policy(
    frozenset({"profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="profile-bound",
    destructive=True,
)
ENCRYPTED_WRITE = _policy(
    frozenset({"encrypted-facts", "profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="profile-bound",
)
ENCRYPTED_DESTRUCTIVE = _policy(
    frozenset({"encrypted-facts", "profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="profile-bound",
    destructive=True,
)
BOOTSTRAP_WRITE = _policy(
    frozenset({"profile-custody"}), frozenset({"local-state"}), "local-io", write_route="bootstrap-root"
)
BOOTSTRAP_DESTRUCTIVE = _policy(
    frozenset({"profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="bootstrap-root",
    destructive=True,
)
GOOGLE_READ = _policy(frozenset({"google", "encrypted-facts"}), frozenset({"google"}), "external-io")
GOOGLE_WRITE = _policy(
    frozenset({"google", "encrypted-facts", "profile-custody"}),
    frozenset({"google", "local-state"}),
    "external-io",
    write_route="profile-bound",
)
GOOGLE_DESTRUCTIVE = _policy(
    frozenset({"google", "encrypted-facts", "profile-custody"}),
    frozenset({"google", "local-state"}),
    "external-io",
    write_route="profile-bound",
    destructive=True,
)
GOOGLE_HANDOFF = _policy(
    frozenset({"google", "encrypted-facts", "profile-custody", "filing"}),
    frozenset({"google", "local-state"}),
    "external-io",
    write_route="profile-bound",
    handoff=True,
)
CALCULATION_READ = _policy(frozenset({"calculation", "encrypted-facts"}), frozenset({"none"}), "compute")
REGISTRY_READ = _policy(frozenset({"calculation"}), frozenset({"none"}), "compute")
CALCULATION_WRITE = _policy(
    frozenset({"calculation", "encrypted-facts", "profile-custody"}),
    frozenset({"local-state"}),
    "compute",
    write_route="profile-bound",
)
GOOGLE_CALCULATION_READ = _policy(
    frozenset({"google", "calculation", "encrypted-facts"}), frozenset({"google"}), "external-io"
)
GOOGLE_CALCULATION_WRITE = _policy(
    frozenset({"google", "calculation", "encrypted-facts", "profile-custody"}),
    frozenset({"google", "local-state"}),
    "external-io",
    write_route="profile-bound",
)
GOOGLE_CALCULATION_HANDOFF = _policy(
    frozenset({"google", "calculation", "encrypted-facts", "profile-custody", "filing"}),
    frozenset({"google", "local-state"}),
    "external-io",
    write_route="profile-bound",
    handoff=True,
)
NETWORK_WRITE = _policy(frozenset({"network"}), frozenset({"network", "local-state"}), "external-io")
LIVE_PROFILE_WRITE = _policy(
    frozenset({"network", "encrypted-facts", "profile-custody"}),
    frozenset({"network", "local-state"}),
    "external-io",
    write_route="profile-bound",
)
BROWSER_CONNECTIVITY = _policy(frozenset({"browser"}), frozenset({"browser"}), "interactive")


__all__ = [
    "BOOTSTRAP_DESTRUCTIVE",
    "BOOTSTRAP_WRITE",
    "BROWSER_CONNECTIVITY",
    "CALCULATION_READ",
    "CALCULATION_WRITE",
    "ENCRYPTED_DESTRUCTIVE",
    "ENCRYPTED_READ",
    "ENCRYPTED_WRITE",
    "GOOGLE_CALCULATION_HANDOFF",
    "GOOGLE_CALCULATION_READ",
    "GOOGLE_CALCULATION_WRITE",
    "GOOGLE_DESTRUCTIVE",
    "GOOGLE_HANDOFF",
    "GOOGLE_READ",
    "GOOGLE_WRITE",
    "LIVE_PROFILE_WRITE",
    "LOCAL_READ",
    "NETWORK_WRITE",
    "PROFILE_DESTRUCTIVE",
    "PROFILE_READ",
    "PROFILE_WRITE",
    "REGISTRY_READ",
    "STATE_FREE",
]
