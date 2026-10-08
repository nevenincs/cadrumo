"""The Drive mirror reports an ended Google sign-in as a typed refusal."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from .....application.export.managed_artifact_ports import ArtifactCreationReceipt, ManagedArtifactKind
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...google.artifact_receipt_store import GoogleArtifactReceiptStore
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


def test_the_probe_raises_sign_in_required_rather_than_reporting_drive_unreachable(tmp_path: Path) -> None:
    """The probe encodes storage conditions in its report; an ended sign-in is not one of them."""
    profile_id = UUID("3d2a9c41-7f5e-4b0a-9c1d-5e8f7a6b4c32")
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(profile_id)) as profile,
        token_endpoint(status=400, body=ENDED_GRANT_RESPONSE) as endpoint,
    ):
        receipts = GoogleArtifactReceiptStore(profile.repository, profile_id=profile_id)
        receipts.record(
            ArtifactCreationReceipt(
                profile_id=profile_id,
                root_folder_id="synthetic-root-folder",
                artifact_id="synthetic-root-folder",
                parent_id=None,
                creation_id=UUID(int=1),
                kind=ManagedArtifactKind.ROOT,
            )
        )
        provider = GoogleDriveProvider(
            credentials=credentials_needing_refresh(endpoint.url, client_id=SYNTHETIC_CLIENT_ID),
            root_folder_id="synthetic-root-folder",
            vault_folder_name="cadrumo-vault",
            receipts=receipts,
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
