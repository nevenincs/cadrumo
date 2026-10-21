"""Shared typed root profile-authentication inputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import cast
from uuid import UUID

from pydantic import SecretStr, model_validator

from cadrumo_client.commands.secure_input import MachineSecretPayload


class ProfileAuthenticationSecrets(MachineSecretPayload):
    """Strict root payload used to authenticate one exact profile target."""

    profile_passphrase: SecretStr | None = None
    api_key: SecretStr | None = None

    @model_validator(mode="after")
    def exactly_one_credential(self) -> ProfileAuthenticationSecrets:
        """Require one and only one root authentication credential."""
        if (self.profile_passphrase is None) == (self.api_key is None):
            raise ValueError("root profile authentication requires exactly one credential field")
        return self


class ProfileAuthenticationMethod(StrEnum):
    """The declared root credential kind; this token is public metadata only."""

    PASSWORD = auto()
    API_KEY = "api-key"


@dataclass(frozen=True, slots=True)
class ProfileSecretSourceOptions:
    """Parse-only root option values; selection and reading belong to dispatch."""

    stdin: bool = False
    descriptor: int | None = None
    method: ProfileAuthenticationMethod = ProfileAuthenticationMethod.PASSWORD
    credential_reference: UUID | None = None

    def __post_init__(self) -> None:
        """Validate the selected root secret source and reference."""
        if not isinstance(self.method, ProfileAuthenticationMethod):
            raise TypeError("root profile authentication requires a known method")
        if self.credential_reference is not None and not isinstance(self.credential_reference, UUID):
            raise TypeError("root profile credential reference must be a UUID")

    @property
    def supplied(self) -> bool:
        """Return whether this invocation supplied a root credential source."""
        return self.stdin or self.descriptor is not None or self.credential_reference is not None


def parsed_root_profile_source(ctx: object) -> ProfileSecretSourceOptions:
    """Read the parsed root authentication selection for one invocation."""
    find_root = getattr(ctx, "find_root", None)
    if not callable(find_root):
        raise TypeError("profile-authentication context has no root")
    root = find_root()
    ensure_object = getattr(root, "ensure_object", None)
    if not callable(ensure_object):
        raise TypeError("profile-authentication root has no object context")
    state = cast(dict[str, object], ensure_object(dict))
    value = state.get("profile_secret_source")
    if value is None:
        return ProfileSecretSourceOptions()
    if not isinstance(value, ProfileSecretSourceOptions):
        raise TypeError("root profile-secret source has an invalid type")
    return value


__all__ = [
    "ProfileAuthenticationMethod",
    "ProfileAuthenticationSecrets",
    "ProfileSecretSourceOptions",
    "parsed_root_profile_source",
]
