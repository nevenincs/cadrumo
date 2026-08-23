"""Typed authority for per-invocation root profile authentication."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import SecretStr

from ._bootstrap_exempt import is_bootstrap_exempt
from ._command_spec import CommandSpecNode, ProfileAuthenticationPosture
from ._config._secure_input import MachineSecretPayload


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


def profile_authentication_posture(node: CommandSpecNode) -> ProfileAuthenticationPosture:
    """Derive one leaf's root-gate posture from graph and exemption authority."""
    spec = node.spec
    if spec.kind != "leaf":
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
]
