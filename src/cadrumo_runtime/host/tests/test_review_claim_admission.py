"""Parent attestations remain tied to live native HUMAN admission, never wire labels."""

import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.operation_access import OperationReviewClaim
from cadrumo_client.contracts.profile_access import AccessRefusal, SessionRequest

from .test_service_records import service_record_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native profile admission and workers"),
]


def test_parent_rechecks_every_attested_person_coordinate_and_refuses_retired_session(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path) as runtime:
        host = runtime.profiles._profiles[runtime.profile_id]
        connection = next(
            item for item in runtime.profiles._connections.values() if item.session_id == runtime.person_session_id
        )
        proof = host.review_person_attestation(connection)
        host._require_review_person(proof)
        for changed in (
            {"worker_id": uuid4()},
            {"runtime_boot_id": uuid4()},
            {"session_id": uuid4()},
            {"profile_binding": proof.profile_binding.model_copy(update={"custody_generation": 2})},
            {"profile_binding": proof.profile_binding.model_copy(update={"profile_id": uuid4()})},
            {"frontend": OperationFrontendProjection.EXTERNAL_CLIENT},
            {"source_ref": "forged-login"},
        ):
            with pytest.raises(ProfileAccessRefusedError):
                host._require_review_person(proof.model_copy(update=changed))
        # A person frontend label is insufficient when the admitted method is a key.
        original_method = connection.method
        connection.method = "api_key"
        try:
            with pytest.raises(ProfileAccessRefusedError) as key:
                host._require_review_person(proof)
            assert key.value.reason is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
        finally:
            connection.method = original_method
        runtime.human.session(
            SessionRequest(
                action="session_lock",
                request_id=uuid4(),
                profile_id=runtime.profile_id,
                session_id=runtime.person_session_id,
            ),
            deadline=time.monotonic() + 10,
        )
        with pytest.raises(ProfileAccessRefusedError):
            host._require_review_person(proof)


def test_public_claim_cannot_target_a_different_profile_with_an_existing_human_session(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path) as runtime:
        reference = OperationReviewProjectionReferenceV1(
            operation_id="a" * 64,
            interaction_id="b" * 64,
            revision=1,
            review_projection_schema=OperationSchemaIdentityV1(
                schema_id="config.provision.review",
                schema_version=1,
                schema_fingerprint="c" * 64,
            ),
            definition_contract_digest="d" * 64,
            expires_at=None,
        )
        reply = runtime.human.operation(
            OperationReviewClaim(
                request_id=uuid4(),
                profile_id=runtime.other_profile_id,
                session_id=runtime.person_session_id,
                reference=reference,
                reviewed_document_digest="e" * 64,
            ),
            deadline=time.monotonic() + 10,
        )
        assert isinstance(reply, AccessRefusal)
        assert reply.code is AccessDenialCode.PROFILE_MISMATCH
