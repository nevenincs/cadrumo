"""Receipt proof limits and denial translation for frontend sign-in."""

from typing import Final

from cadrumo.core.profile_session import ProfileSessionRefusalReason

from ..contracts.access_refusals import AccessDenialCode
from ..contracts.automation_codes import AutomationCustodyCode
from ..contracts.sign_in_outcomes import ProfileReceiptRefusedError
from .frontend_client_contracts import FrontendRefusedError

_CONNECTION_RECEIPT_REFUSALS: Final[dict[str, ProfileSessionRefusalReason]] = {
    # The runtime deleted a receipt that no longer signs this login in.
    AccessDenialCode.AUTHENTICATION_REQUIRED.value: ProfileSessionRefusalReason.ABSENT,
    # The denial does not distinguish idle from absolute expiry.
    AccessDenialCode.SESSION_EXPIRED.value: ProfileSessionRefusalReason.EXPIRED_IDLE,
    AccessDenialCode.CUSTODY_CHANGED.value: ProfileSessionRefusalReason.CUSTODY_CHANGED,
    AutomationCustodyCode.CREDENTIAL_REJECTED.value: ProfileSessionRefusalReason.TAMPERED,
}


RECEIPT_PROOF_ATTEMPTS: Final = 3


def receipt_refusal(error: FrontendRefusedError) -> ProfileReceiptRefusedError | None:
    """Translate a runtime denial of a presented receipt into the receipt refusal callers handle, if it is one."""
    reason = (
        error.sign_in.reason
        if error.sign_in is not None and isinstance(error.sign_in.reason, ProfileSessionRefusalReason)
        else _CONNECTION_RECEIPT_REFUSALS.get(error.reason)
    )
    if reason is None:
        return None
    return ProfileReceiptRefusedError(reason, binding=None if error.sign_in is None else error.sign_in.binding)
