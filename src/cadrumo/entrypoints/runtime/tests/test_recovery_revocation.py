"""Recovery cleanup facts survive the runtime owner and strict reply envelope."""

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import ReceiptDeletion
from cadrumo.application.runtime.access_management import RuntimeProfileResumed
from cadrumo.application.runtime.profile_access import RuntimeReply
from cadrumo.application.user_profile.automation_lifecycle_service import AutomationResumeReceipt
from cadrumo.application.user_profile.session_retirement import SessionRetirementKind
from cadrumo.entrypoints.runtime.access_management import RuntimeLifecycleOwner
from cadrumo.entrypoints.runtime.profile_host import ProfileConnection, RuntimeProfileHost

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "deletion,receipt_removed,keychain_removed",
    [
        (ReceiptDeletion.NOT_REQUIRED, True, True),
        (ReceiptDeletion.DELETED, True, True),
        (ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED, True, False),
        (ReceiptDeletion.RECEIPT_RETAINED, False, False),
    ],
)
def test_recovery_preserves_physical_cleanup_outcome(
    deletion: ReceiptDeletion, receipt_removed: bool, keychain_removed: bool
) -> None:
    retired = []

    def revoke(*, kind: SessionRetirementKind) -> tuple[ReceiptDeletion, tuple[()]]:
        retired.append(kind)
        return deletion, ()

    # Explicit owner-result fault port; strict production wire encoding/decoding
    # must retain partial deletion rather than inventing complete cleanup.
    owner = RuntimeLifecycleOwner(
        host=cast(RuntimeProfileHost, SimpleNamespace(revoke_human_sign_in=revoke)),
        connection=cast(ProfileConnection, object()),
        validate=lambda _connection, _host: None,
        lock_changed=lambda _profile: None,
    )
    result = owner.revoke_human_sign_in()
    assert retired == [SessionRetirementKind.REVOKED]
    reply = RuntimeProfileResumed(
        request_id=uuid4(),
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        receipt=AutomationResumeReceipt(
            request_id=uuid4(),
            profile_id=uuid4(),
            revision=None,
            lock_generation=1,
            reactivated_grants=frozenset(),
            human_sign_in_revocation=result,
        ),
    )
    decoded = RuntimeReply.model_validate_json(reply.model_dump_json()).root
    assert isinstance(decoded, RuntimeProfileResumed)
    assert decoded.receipt.human_sign_in_revocation is not None
    assert decoded.receipt.human_sign_in_revocation.receipt_removed is receipt_removed
    assert decoded.receipt.human_sign_in_revocation.keychain_removed is keychain_removed


def test_older_recovery_reply_does_not_claim_sign_in_cleanup() -> None:
    receipt = AutomationResumeReceipt(
        request_id=uuid4(),
        profile_id=uuid4(),
        revision=None,
        lock_generation=1,
        reactivated_grants=frozenset(),
    )
    assert receipt.human_sign_in_revocation is None
