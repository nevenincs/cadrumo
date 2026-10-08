"""Observable API admission from the canonical, completed enrollment fixture."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Unpack
from uuid import UUID, uuid4

from click.testing import Result

from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.persistence.storage.custody.automation_retirement import retire_profile_automation
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import administration_subject, changed
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.custody.tests.portable_password_custody import portable_password_custody
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.automation_enrollment import EnrollmentProposal, EnrollmentStage

from .cli_runner import ClickInvokeKwargs, invoke_cached_cli
from .portable_human_cli_runtime import portable_human_cli_runtime


@dataclass(frozen=True)
class PortableApiCliRuntime:
    """An exact opaque reference backed by a real completed test enrollment."""

    profile_id: UUID
    credential_reference: UUID
    grant_id: UUID
    key_id: UUID
    proposal: EnrollmentProposal

    def invoke(self, args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
        """Preserve leaf stdin; prove the enrolled key on each fresh CLI connection."""
        return invoke_cached_cli(
            [
                "--profile",
                str(self.profile_id),
                "--profile-auth-method",
                "api-key",
                "--profile-credential-ref",
                str(self.credential_reference),
                *args,
            ],
            **kwargs,
        )


@contextmanager
def portable_api_cli_runtime(tmp_path: Path) -> Iterator[PortableApiCliRuntime]:
    """Use the native API fixture's real request/approval/delivery/possession flow.

    Only OS credential storage and transport are synthetic. No enrollment stage
    is fabricated and no HUMAN session is used as API admission.
    """
    with portable_password_custody(), isolated_profile_storage_root(tmp_path=tmp_path) as root:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        # The canonical endpoint constructor computes identity without listening.
        import sys

        from cadrumo.adapters.local_runtime.posix_endpoint import PosixRuntimeEndpoint
        from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint

        endpoint = (
            WindowsRuntimeEndpoint(storage_root=root)
            if sys.platform == "win32"
            else PosixRuntimeEndpoint(storage_root=root)
        )
        try:
            os_owner = owner_id()
            installation = runtime_installation(
                storage_root=root, os_owner_id=os_owner, storage_identity=endpoint.storage_identity
            )
            with administration_subject(
                tmp_path, os_owner_id=os_owner, installation_id=installation.installation_id
            ) as subject:
                assert subject.store.root == root
                requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
                subject.owner.requesting = requester
                subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
                    requester=requester, secrets_store=subject.client_native
                )
                request_id = uuid4()
                subject.service.request(request_id, subject.proposal)
                approval = subject.approve(request_id)
                record = next(
                    item for item in subject.store.enrollment_state().requests if item.request_id == request_id
                )
                assert record.stage is EnrollmentStage.COMPLETE
                assert subject.owner.delivery.endpoint.possession(record) is not None
                assert approval.credential_reference is not None and approval.key_id is not None
                assert subject.proposal.key_expires_at is not None
                assert datetime.now(UTC) < subject.proposal.key_expires_at <= subject.proposal.expires_at
                profile_id = subject.store.binding.profile_id
                try:
                    with portable_human_cli_runtime(
                        storage_root=root,
                        profile_id=profile_id,
                        label="Enrollment tests",
                        native_store=subject.native,
                        os_owner_id=os_owner,
                        client_native_store=subject.client_native,
                    ):
                        yield PortableApiCliRuntime(
                            profile_id,
                            approval.credential_reference,
                            approval.grant_id,
                            approval.key_id,
                            subject.proposal,
                        )
                finally:
                    assert retire_profile_automation(root=root, profile_id=profile_id, secrets_store=subject.native)
                    assert subject.native.items == {}
                    # These client items are wholly memory owned by this fixture.
                    subject.client_native.items.clear()
        finally:
            endpoint.close()
