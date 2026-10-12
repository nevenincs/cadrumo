"""A runtime sign-in refusal reaches the operator with its typed reason intact."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....adapters.local_runtime.frontend_operation_client import RuntimeOperationFrontend
from ....application.runtime.profile_access import RuntimeAccessRefusal, RuntimeReply
from ....application.user_profile.access_contracts import AccessDenialCode
from ....application.user_profile.sign_in_refusals import SignInRefusal
from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.profile_session import ProfileSessionRefusalReason, ReceiptBindingRefusal
from .._profile_session_gate import raise_runtime_refusal, session_refusal_translation_key
from ..errors import CliRefusedBoundaryError, render_error_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _wire_refusal(code: AccessDenialCode, sign_in: SignInRefusal | None) -> RuntimeFrontendRefusedError:
    """Decode a runtime refusal from its wire bytes, as a client receives it."""
    reply = RuntimeAccessRefusal(
        request_id=uuid4(), runtime_boot_id=uuid4(), connection_id=uuid4(), code=code, sign_in=sign_in
    )
    decoded = RuntimeReply.model_validate_json(reply.model_dump_json()).root
    assert isinstance(decoded, RuntimeAccessRefusal)
    with pytest.raises(RuntimeFrontendRefusedError) as raised:
        RuntimeOperationFrontend._raise_wire_refusal(decoded)
    return raised.value


def _rendered(error: RuntimeFrontendRefusedError) -> dict[str, object]:
    with pytest.raises(CliRefusedBoundaryError) as refused:
        raise_runtime_refusal(error)
    payload = json.loads(render_error_payload(refused.value, as_json=True))
    error_payload = payload["error"]
    assert isinstance(error_payload, dict)
    return {str(key): value for key, value in error_payload.items()}


_CASES = (
    (
        AccessDenialCode.AUTHENTICATION_REQUIRED,
        SignInRefusal(reason="throttled", remaining_seconds=19),
        "errors.refused.refused_profile_login_throttled",
    ),
    (AccessDenialCode.PROFILE_LOCKED, None, "errors.refused.profile_locked"),
    (
        AccessDenialCode.AUTHENTICATION_REQUIRED,
        SignInRefusal(reason=ProfileSessionRefusalReason.ABSENT, binding=ReceiptBindingRefusal.GENERATION_CHANGED),
        "cli.config.errors.profile_session_signed_out",
    ),
    (
        AccessDenialCode.AUTHENTICATION_REQUIRED,
        SignInRefusal(reason=ProfileSessionRefusalReason.ABSENT, binding=ReceiptBindingRefusal.LOGIN_MISMATCH),
        "cli.config.errors.profile_session_login_mismatch",
    ),
    (
        AccessDenialCode.SESSION_EXPIRED,
        SignInRefusal(reason=ProfileSessionRefusalReason.EXPIRED_IDLE),
        "cli.config.errors.profile_session_expired",
    ),
    (
        AccessDenialCode.CUSTODY_CHANGED,
        SignInRefusal(reason=ProfileSessionRefusalReason.CUSTODY_CHANGED),
        "cli.config.errors.profile_session_custody_changed",
    ),
    (
        AccessDenialCode.AUTHENTICATION_REQUIRED,
        SignInRefusal(reason=ProfileSessionRefusalReason.ABSENT),
        "cli.config.errors.profile_session_absent",
    ),
)


@pytest.mark.parametrize(("code", "sign_in", "key"), _CASES)
def test_each_sign_in_refusal_keeps_its_own_message_and_wire_facts(
    code: AccessDenialCode, sign_in: SignInRefusal | None, key: str
) -> None:
    error = _wire_refusal(code, sign_in)
    with override_settings(cadrumo_output_language=OutputLanguage.EN):
        rendered = _rendered(error)
        expected = tr(key, locale="en", seconds=19)
    assert rendered["message"] == expected
    assert expected != key
    context = rendered["context"]
    assert isinstance(context, dict)
    # The desktop and scripts read the runtime's code and provenance, unchanged.
    assert context["reason"] == code.value
    if sign_in is not None:
        assert context["sign_in_reason"] == sign_in.reason
        if sign_in.binding is not None:
            assert context["sign_in_binding"] == sign_in.binding
        if sign_in.remaining_seconds is not None:
            # The envelope carries context values as text; the desktop parses the number back.
            assert context["seconds"] == str(sign_in.remaining_seconds)


def test_no_two_refusals_share_one_message() -> None:
    messages = {_rendered(_wire_refusal(code, sign_in))["message"] for code, sign_in, _key in _CASES}
    assert len(messages) == len(_CASES)


@pytest.mark.parametrize("language", tuple(OutputLanguage))
@pytest.mark.parametrize("binding", [None, *ReceiptBindingRefusal])
@pytest.mark.parametrize("reason", list(ProfileSessionRefusalReason))
def test_every_resume_refusal_is_translated_in_every_language(
    language: OutputLanguage, binding: ReceiptBindingRefusal | None, reason: ProfileSessionRefusalReason
) -> None:
    key = session_refusal_translation_key(reason, binding)
    assert tr(key, locale=language.value) != key


def test_an_unrelated_refusal_keeps_its_runtime_code() -> None:
    error = _wire_refusal(AccessDenialCode.OPERATION_DENIED, None)
    rendered = _rendered(error)
    assert rendered["message"] == AccessDenialCode.OPERATION_DENIED.value
