"""A frozen document clock never reaches the leases, permits and sessions the runtime mints."""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_operation_contracts import (
    ProfileFieldMutationOperationRequest,
    ProfileMutationOperationProjection,
)
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection
from cadrumo.core.time.clock import frozen_clock, wall_now
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.profile_mutations import run_profile_mutation
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from .served_runtime import SyntheticLogin, serving_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def _baseline(profile_id: object) -> tuple[int, str]:
    _, decode = profile_authority_contexts()
    authenticate_profile_for_invocation(
        name=str(profile_id),
        passphrase_callback=lambda: PROFILE_INPUT,
        profile_decode_context=decode,
    )
    try:
        record = ProfileRecordRepository.for_current_session(str(profile_id), profile_decode_context=decode).load(
            str(profile_id)
        )
        return record.record_revision, record.content_digest
    finally:
        close_active_bucket_session()


def test_a_past_document_instant_still_submits_through_a_freshly_minted_session(tmp_path: Path) -> None:
    """Sign-in and a profile-bound submit succeed while every host connection reads a past document instant."""
    document_instant = (wall_now() - timedelta(days=400)).replace(microsecond=0)
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[0][0].binding.profile_id
        revision, digest = _baseline(profile_id)
        endpoint = WindowsEndpoint(storage_root=root)
        installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        native = MemoryNativePort()
        with (
            serving_runtime(
                endpoint,
                root,
                capture_login=lambda _channel: SyntheticLogin("frozen-document-clock-login"),
                secret_store=lambda: native,
                drain_seconds=15,
                document_instant=document_instant,
            ) as served,
            frozen_clock(document_instant),
        ):
            before = wall_now()
            client = asyncio.run(
                FrontendClient.open(served.launch, profile_id=profile_id, frontend=OperationFrontendProjection.TUI)
            )
            with client:
                admitted = client.login_password(bytearray(PROFILE_INPUT.encode()))
                expires_at = admitted.status.session_expires_at
                assert expires_at is not None
                assert expires_at > before
                completed = run_profile_mutation(
                    client,
                    ProfileFieldMutationOperationRequest(
                        profile_id=profile_id,
                        expected_revision=revision,
                        expected_content_digest=digest,
                        path=PROFILE_OUTPUT_LANGUAGE_PATH,
                        value="ca",
                    ),
                    timeout=60,
                )
                assert completed.effect is OperationEffect.UPDATED
                assert type(completed.projection) is ProfileMutationOperationProjection
                assert completed.projection.record_revision > revision
