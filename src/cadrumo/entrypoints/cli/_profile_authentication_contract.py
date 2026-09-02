"""Typed authority for per-invocation root profile authentication."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import SecretStr

from ._bootstrap_exempt import is_bootstrap_exempt
from .command_spec import CommandSpecNode, ProfileAuthenticationPosture, ProfileSecretSpec
from .config.secure_input import MachineSecretPayload


class ProfileAuthenticationSecrets(MachineSecretPayload):
    """Strict root payload used to authenticate one exact profile target."""

    profile_passphrase: SecretStr


@dataclass(frozen=True, slots=True)
class ProfileSecretSourceOptions:
    """Parse-only root option values; selection and reading belong to dispatch."""

    stdin: bool = False
    descriptor: int | None = None

    @property
    def supplied(self) -> bool:
        return self.stdin or self.descriptor is not None


def resolve_profile_secret_model(spec: ProfileSecretSpec) -> type[MachineSecretPayload]:
    """Resolve and prove exact parity between graph metadata and runtime model."""
    from ._command_target import resolve_deferred_target

    model = resolve_deferred_target(spec.model)
    if not isinstance(model, type) or not issubclass(model, MachineSecretPayload):
        raise TypeError("root profile-secret model must inherit MachineSecretPayload")
    if tuple(model.model_fields) != tuple(field.name for field in spec.fields):
        raise ValueError("root profile-secret model fields must exactly match command specification")
    return model


def root_profile_secret_model() -> type[MachineSecretPayload]:
    """Return the conformance-checked graph-owned root payload model."""
    from .command_specs import COMMAND_GRAPH

    spec = COMMAND_GRAPH.by_key()["root"].profile_secret
    if spec is None:
        raise RuntimeError("root command spec must declare a profile-secret contract")
    return resolve_profile_secret_model(spec)


def profile_authentication_posture(node: CommandSpecNode) -> ProfileAuthenticationPosture:
    """Derive one leaf's root-gate posture from graph and exemption authority."""
    spec = node.spec
    if spec.kind == "root" or (spec.kind != "leaf" and spec.invocation.terminal_behavior != "executable"):
        return ProfileAuthenticationPosture.NOT_APPLICABLE
    if spec.profile_authentication is ProfileAuthenticationPosture.SELF_AUTHENTICATING:
        return ProfileAuthenticationPosture.SELF_AUTHENTICATING
    operator_path = " ".join(node.path[1:])
    if is_bootstrap_exempt(operator_path):
        return ProfileAuthenticationPosture.NOT_APPLICABLE
    return ProfileAuthenticationPosture.RESUME_FALLBACK


__all__ = [
    "ProfileAuthenticationSecrets",
    "ProfileSecretSourceOptions",
    "profile_authentication_posture",
    "resolve_profile_secret_model",
    "root_profile_secret_model",
]
