"""Unavailable CLI refusals preserve their wire code and name the manager."""

import json

import pytest

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....core.config import override_settings
from ..errors import CliRefusedBoundaryError, render_error_payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("language,word", [("en", "manager"), ("es", "gestor"), ("ca", "gestor"), ("hu", "kezelő")])
@pytest.mark.parametrize("kind", ["transport", "frontend", "cli"])
def test_unavailable_refusal_names_manager_in_text_and_json(language: str, word: str, kind: str) -> None:
    code = RefusalCode.UNAVAILABLE.value
    error = {
        "transport": RefusalError(RefusalCode.UNAVAILABLE),
        "frontend": FrontendRefusedError(code),
        "cli": CliRefusedBoundaryError(code, context={"reason": code}),
    }[kind]
    with override_settings(cadrumo_output_language=language):
        document = json.loads(render_error_payload(error, as_json=True))
        text = render_error_payload(error, as_json=False)
    remedy = document["error"]["context"]["remedy"]
    assert word in remedy and "Cadrumo" in remedy
    assert remedy in text
    assert "{" not in remedy


def test_unrelated_refusal_does_not_suggest_manager_recovery() -> None:
    document = json.loads(render_error_payload(RefusalError(RefusalCode.INVALID_FRAME), as_json=True))
    assert "remedy" not in (document["error"]["context"] or {})
