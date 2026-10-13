"""A busy subject's refusal names the unsettled operation that holds it, in text and in JSON."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....adapters.local_runtime.frontend_operation_client import RuntimeOperationFrontend
from ....application.runtime.profile_access import RuntimeAccessRefusal, RuntimeReply
from ....application.user_profile.access_contracts import AccessDenialCode
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ..errors import render_error_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_HOLDER = "ab" * 32


def _received(code: AccessDenialCode, holder: str | None) -> RuntimeFrontendRefusedError:
    """Decode a runtime refusal from its wire bytes, as a client receives it."""
    reply = RuntimeAccessRefusal(
        request_id=uuid4(), runtime_boot_id=uuid4(), connection_id=uuid4(), code=code, holder_operation_id=holder
    )
    decoded = RuntimeReply.model_validate_json(reply.model_dump_json()).root
    assert isinstance(decoded, RuntimeAccessRefusal)
    with pytest.raises(RuntimeFrontendRefusedError) as raised:
        RuntimeOperationFrontend._raise_wire_refusal(decoded)
    return raised.value


def test_the_operation_holding_a_busy_subject_is_named_in_text_and_json() -> None:
    refused = _received(AccessDenialCode.SUBJECT_BUSY, _HOLDER)

    assert refused.holder_operation_id == _HOLDER
    assert _HOLDER in render_error_payload(refused, as_json=False)
    context = json.loads(render_error_payload(refused, as_json=True))["error"]["context"]
    assert context["reason"] == AccessDenialCode.SUBJECT_BUSY.value
    assert context["holder_operation_id"] == _HOLDER


def test_a_refusal_that_names_no_holder_renders_no_holder_line() -> None:
    refused = _received(AccessDenialCode.SUBJECT_BUSY, None)

    assert refused.holder_operation_id is None
    assert "holder_operation_id" not in json.loads(render_error_payload(refused, as_json=True))["error"]["context"]
    assert "Holder operation id" not in render_error_payload(refused, as_json=False)


def test_no_other_refusal_can_name_a_holder() -> None:
    with pytest.raises(ValidationError, match="only a busy subject"):
        RuntimeAccessRefusal(
            request_id=uuid4(),
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            code=AccessDenialCode.OPERATION_UNAVAILABLE,
            holder_operation_id=_HOLDER,
        )
    with pytest.raises(ValueError, match="only a busy subject"):
        ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE, holder_operation_id=_HOLDER)
