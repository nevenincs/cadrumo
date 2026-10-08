"""Provision publisher Desktop OAuth metadata into distribution build inputs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal, overload

from pydantic import Field, SecretStr

from cadrumo.core.config_google import (
    CLIENT_METADATA_MAX_BYTES,
    INSTALLATION_CLIENT_DATA_PARTS,
    GoogleOAuthClientSettings,
)
from cadrumo.core.config_google_client import decode_desktop_client

GOOGLE_OAUTH_ENV = next(iter(GoogleOAuthClientSettings.model_fields)).upper()
GOOGLE_OAUTH_RESOURCE = "/".join(("src", "cadrumo", "_data", *INSTALLATION_CLIENT_DATA_PARTS))


@overload
def build_client_json(root: Path, *, required: Literal[True] = True) -> SecretStr: ...


@overload
def build_client_json(root: Path, *, required: Literal[False]) -> SecretStr | None: ...


def build_client_json(root: Path, *, required: bool = True) -> SecretStr | None:
    """Resolve explicit build settings without borrowing another installation's client.

    Process environment takes precedence over the checkout's canonical dotenv.
    The root's embedded or ignored development resource supplies the final fallback.
    Errors deliberately omit parser details and credential values.
    """
    embedded = root / GOOGLE_OAUTH_RESOURCE

    def embedded_client() -> SecretStr | None:
        if not embedded.is_file():
            return None
        try:
            with embedded.open("rb") as stream:
                raw = stream.read(CLIENT_METADATA_MAX_BYTES + 1)
            return SecretStr(raw.decode("utf-8"))
        except (OSError, UnicodeError):
            raise ValueError("Invalid packaged Google Desktop OAuth configuration") from None

    # Init values normally beat environment in BaseSettings. A local subclass
    # changes only the fallback factory, retaining the shared field and source order.
    class BuildSettings(GoogleOAuthClientSettings):
        cadrumo_google_oauth_client_json: SecretStr | None = Field(default_factory=embedded_client)

    try:
        selected = BuildSettings(_env_file=root / "env/.env").cadrumo_google_oauth_client_json
    except ValueError:
        raise ValueError(f"Invalid {GOOGLE_OAUTH_ENV} build configuration") from None
    if selected is None:
        if not required:
            return None
        raise ValueError(f"Set {GOOGLE_OAUTH_ENV} in the build environment or env/.env before packaging")
    _validate_client(selected.get_secret_value())
    return selected


def _validate_client(encoded: str) -> None:
    """Reject incomplete/non-Desktop build input before producing an artifact."""
    if decode_desktop_client(encoded) is None:
        raise ValueError(f"Invalid {GOOGLE_OAUTH_ENV}: expected a complete Google Desktop client download")


def client_build_identity(source_identity: str, client: SecretStr) -> str:
    """Bind reusable product output to selected credentials without storing them."""
    return hashlib.sha256(
        source_identity.encode("ascii") + b"\0" + client.get_secret_value().encode("utf-8")
    ).hexdigest()


def stage_build_client(root: Path, client: SecretStr) -> Path:
    """Write validated configuration into an artifact tree or ignored development resource."""
    _validate_client(client.get_secret_value())
    target = root / GOOGLE_OAUTH_RESOURCE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(client.get_secret_value(), encoding="utf-8", newline="")
    return target
