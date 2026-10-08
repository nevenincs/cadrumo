"""Publisher Google Desktop OAuth configuration for runtime and build tooling."""

from __future__ import annotations

from importlib.resources.abc import Traversable  # nosemgrep
from typing import Final

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .resources.bundled_data import packaged_data

INSTALLATION_CLIENT_DATA_PARTS: Final[tuple[str, ...]] = ("google", "oauth_client.json")
CLIENT_METADATA_MAX_BYTES: Final[int] = 65_536


def installation_client_source() -> Traversable:
    """Locate publisher metadata provisioned into the installed distribution."""
    return packaged_data(*INSTALLATION_CLIENT_DATA_PARTS)


def _installed_client_json() -> SecretStr | None:
    """Read bounded installed metadata, retaining invalid content as a refusal.

    Absence is distinct from malformed or unreadable content. An empty secret
    represents invalid installed bytes without retaining oversized input or
    allowing decoder errors to disclose any credential text.
    """
    source = installation_client_source()
    try:
        if not source.is_file():
            return None
    except OSError:
        return None
    try:
        with source.open("rb") as stream:
            encoded = stream.read(CLIENT_METADATA_MAX_BYTES + 1)
        if len(encoded) > CLIENT_METADATA_MAX_BYTES:
            return SecretStr("")
        return SecretStr(encoded.decode("utf-8"))
    except (OSError, UnicodeDecodeError):
        return SecretStr("")


class GoogleOAuthClientSettings(BaseSettings):
    """The shared Google client field without storage or profile initialization.

    Runtime reads process environment and installed resources only. Build tools
    may explicitly supply ``_env_file`` for their development provisioning file.
    """

    model_config = SettingsConfigDict(env_ignore_empty=True, extra="ignore")

    cadrumo_google_oauth_client_json: SecretStr | None = Field(
        default_factory=_installed_client_json,
        description=(
            "Publisher Google Desktop OAuth client download as complete installed-envelope JSON. "
            "Provision through the development environment or CI secret; installed builds fall back "
            "to their bundled client metadata. Never use a web client or user token."
        ),
    )
