"""Host-owned native profile effects requested by the AEAT CLI."""

from __future__ import annotations

from cadrumo.application.bucket_maintenance.contracts import BucketDeletionAssessment
from cadrumo_client.commands.errors import CliRefusedBoundaryError


def delete_profile(assessment: BucketDeletionAssessment) -> str:
    """Delegate the complete existing transaction without holding client locks."""
    from uuid import UUID

    from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

    from .profile_client import open_cli_profile_client

    if assessment.fingerprint is None:
        raise CliRefusedBoundaryError("custody_changed")
    client = open_cli_profile_client(UUID(assessment.bucket_id))
    try:
        try:
            completed = client.delete_profile(assessment.fingerprint)
        except FrontendRefusedError as error:
            raise CliRefusedBoundaryError(error.reason, context=error.context) from error
    except BaseException as primary:
        try:
            client.close()
        except Exception:
            primary.add_note("Profile client cleanup did not complete.")
        raise
    else:
        client.close()
    return completed.receipt.completed_at.isoformat()
