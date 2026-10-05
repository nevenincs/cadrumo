"""The Google OAuth Desktop client this installation signs in with.

Cadrumo has one Google client, owned by its publisher. Its metadata is public
installation data: it ships with the installation, is the same for every
profile, and is read from one place by :func:`load_installation_client`.
Nothing here is a profile record, and no command, setting or environment
variable can supply a different client.

A development checkout reads the same location through the same reader. The
developer places the development project's client file there; the file is
never committed.
"""

from __future__ import annotations

import json
from importlib.resources.abc import Traversable  # nosemgrep
from typing import Any, Final

from pydantic import BaseModel, ValidationError

from ....core.models import STRICT_FROZEN_CONFIG
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.resources.bundled_data import packaged_data
from .errors import (
    GoogleAuthClientMetadataUnavailableError,
    GoogleAuthPreconditionCondition,
    google_auth_no_action_verdict,
)
from .records import OAuthClient

INSTALLATION_CLIENT_DATA_PARTS: Final[tuple[str, ...]] = ("google", "oauth_client.json")
"""Location of the client file under the installation's bundled data root."""

# Google's client download is a few hundred bytes. The bound keeps a misplaced
# file from being read whole into memory before it is refused.
_CLIENT_METADATA_MAX_BYTES: Final[int] = 65_536


class _DesktopClientEnvelope(BaseModel):
    """The ``installed`` wrapper Google puts around a Desktop client download."""

    model_config = STRICT_FROZEN_CONFIG
    # ANY-RETURN-RATIONALE-GOOGLE-OAUTH-STAGING: irreducible Cloud Console JSON,
    # narrowed through the canonical OAuthClient before credential use.
    installed: dict[str, Any]


def installation_client_source() -> Traversable:
    """Return the one location this installation's client metadata is read from."""
    return packaged_data(*INSTALLATION_CLIENT_DATA_PARTS)


def load_installation_client() -> OAuthClient:
    """Read and validate this installation's Google OAuth Desktop client.

    Returns:
        The validated publisher client.

    Raises:
        :exc:`adapters.outbound.google.errors.GoogleAuthClientMetadataUnavailableError`:
            When the installation carries no client file, or carries one that
            is not a Google Desktop client. Neither is recoverable by the
            operator from inside the product.
    """
    source = installation_client_source()
    try:
        present = source.is_file()
    except OSError:
        present = False
    if not present:
        raise GoogleAuthClientMetadataUnavailableError(
            "this installation carries no Google client metadata",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.CLIENT_METADATA_AVAILABLE,
                facts={"client_metadata_present": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    client = _decode_desktop_client(source)
    if client is None:
        raise GoogleAuthClientMetadataUnavailableError(
            "this installation's Google client metadata is not a valid Desktop client",
            translated_message="adapters.google.installation_client.errors.client_metadata_invalid",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.CLIENT_METADATA_AVAILABLE,
                facts={"client_metadata_present": True, "client_metadata_valid": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    return client


def _decode_desktop_client(source: Traversable) -> OAuthClient | None:
    """Decode a Desktop client download, or return ``None`` when it is not one.

    The reason a file is refused is deliberately not carried out of here: the
    file holds the client secret, and a parser message can quote its input.
    """
    try:
        with source.open("rb") as stream:
            encoded = stream.read(_CLIENT_METADATA_MAX_BYTES + 1)
    except OSError:
        return None
    if len(encoded) > _CLIENT_METADATA_MAX_BYTES:
        return None
    try:
        envelope = _DesktopClientEnvelope.model_validate(json.loads(encoded.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
        return None
    fields = dict(envelope.installed)
    if isinstance(fields.get("redirect_uris"), list):
        fields["redirect_uris"] = tuple(fields["redirect_uris"])
    try:
        return OAuthClient.model_validate(fields)
    except ValidationError:
        return None


__all__ = [
    "INSTALLATION_CLIENT_DATA_PARTS",
    "installation_client_source",
    "load_installation_client",
]
