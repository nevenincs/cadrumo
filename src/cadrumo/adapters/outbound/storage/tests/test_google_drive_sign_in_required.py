"""The Drive mirror reports an ended Google sign-in as a typed refusal."""

from __future__ import annotations

import pytest

from ...google.errors import GoogleAuthPreconditionCondition, GoogleAuthSignInRequiredError
from ...google.tests.installation_client_support import SYNTHETIC_CLIENT_ID
from ...google.tests.token_endpoint_server import (
    ENDED_GRANT_RESPONSE,
    SYNTHETIC_REFRESH_VALUE,
    credentials_needing_refresh,
    token_endpoint,
)
from .._google_drive import GoogleDriveProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_the_probe_raises_sign_in_required_rather_than_reporting_drive_unreachable() -> None:
    """The probe encodes storage conditions in its report; an ended sign-in is not one of them."""
    with token_endpoint(status=400, body=ENDED_GRANT_RESPONSE) as endpoint:
        provider = GoogleDriveProvider(
            credentials=credentials_needing_refresh(endpoint.url, client_id=SYNTHETIC_CLIENT_ID),
            root_folder_id="synthetic-root-folder",
            vault_folder_name="cadrumo-vault",
        )

        with pytest.raises(GoogleAuthSignInRequiredError) as refused:
            provider.probe(read_only=True)

    error = refused.value
    assert error.code.code == "REFUSED_GOOGLE_SIGN_IN_REQUIRED"
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == GoogleAuthPreconditionCondition.GRANT_ACTIVE.value
    assert dict(verdict.evidence[0].values) == {"grant_active": False}
    assert SYNTHETIC_REFRESH_VALUE not in "\n".join((str(error), repr(error.context)))
    assert [request["grant_type"] for request in endpoint.grant_requests] == [["refresh_token"]]
