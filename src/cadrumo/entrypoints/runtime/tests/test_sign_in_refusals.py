"""Detailed sign-in refusals survive strict wire decoding and frontend translation."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.frontend_operation_client import RuntimeOperationFrontend
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeReply
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.sign_in_refusals import SignInRefusal
from cadrumo.core.profile_session import ProfileSessionRefusalReason, ReceiptBindingRefusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("reason", [*ProfileSessionRefusalReason, "throttled"])
def test_sign_in_detail_survives_wire_and_frontend(reason: ProfileSessionRefusalReason | str) -> None:
    detail = SignInRefusal.model_validate(
        {"reason": reason, "remaining_seconds": 19 if reason == "throttled" else None}
    )
    reply = RuntimeAccessRefusal(
        request_id=uuid4(),
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        code=AccessDenialCode.AUTHENTICATION_REQUIRED,
        sign_in=detail,
    )
    decoded = RuntimeReply.model_validate_json(reply.model_dump_json()).root
    assert isinstance(decoded, RuntimeAccessRefusal)
    with pytest.raises(RuntimeFrontendRefusedError) as raised:
        RuntimeOperationFrontend._raise_wire_refusal(decoded)
    assert raised.value.sign_in == detail
    assert raised.value.context is not None
    assert raised.value.context["sign_in_reason"] == reason
    if reason == "throttled":
        assert raised.value.context["seconds"] == 19


@pytest.mark.parametrize("binding", list(ReceiptBindingRefusal))
def test_binding_refusal_is_not_collapsed_to_absence(binding: ReceiptBindingRefusal) -> None:
    reply = RuntimeAccessRefusal(
        request_id=uuid4(),
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        code=AccessDenialCode.AUTHENTICATION_REQUIRED,
        sign_in=SignInRefusal(reason=ProfileSessionRefusalReason.ABSENT, binding=binding),
    )
    with pytest.raises(RuntimeFrontendRefusedError) as raised:
        RuntimeOperationFrontend._raise_wire_refusal(reply)
    assert raised.value.sign_in is not None and raised.value.sign_in.binding is binding
    assert raised.value.context is not None and raised.value.context["sign_in_binding"] == binding


@pytest.mark.parametrize("reason,seconds", [("throttled", None), ("throttled", -1), ("absent", 19)])
def test_inconsistent_sign_in_detail_refuses(reason: str, seconds: int | None) -> None:
    with pytest.raises(ValidationError):
        SignInRefusal.model_validate({"reason": reason, "remaining_seconds": seconds})
