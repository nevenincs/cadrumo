"""Inspect protected candidate custody in enrollment fixtures before activation."""

from pydantic import SecretBytes

from ....application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ..enrollment_client import NativeEnrollmentClient


def read_delivered_credential(client: NativeEnrollmentClient) -> SecretBytes:
    offer = client._offer
    if offer is None:
        raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
    return client._store.read(
        credential_reference=offer.credential_reference,
        grant_id=offer.grant_id,
        key_id=offer.key_id,
        review_digest=offer.review_digest,
    )
