"""Validate the publisher Google Desktop client supplied by core settings.

Development and CI provision the complete Google download through the secret
setting; installed distributions carry its generated fallback resource. This
is installation identity, never a profile credential or an operator prompt.
"""

from __future__ import annotations

from ....core.config import load_settings
from ....core.config_google_client import OAuthClient, decode_desktop_client
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from .errors import (
    GoogleAuthClientMetadataUnavailableError,
    GoogleAuthPreconditionCondition,
    google_auth_no_action_verdict,
)


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
    configured = load_settings().cadrumo_google_oauth_client_json
    if configured is None:
        raise GoogleAuthClientMetadataUnavailableError(
            "this installation carries no Google client metadata",
            precondition_verdict=google_auth_no_action_verdict(
                condition=GoogleAuthPreconditionCondition.CLIENT_METADATA_AVAILABLE,
                facts={"client_metadata_present": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    client = decode_desktop_client(configured.get_secret_value())
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
