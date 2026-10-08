"""Installed TUI startup keeps refusal codes alongside localized manager guidance."""

import pytest

from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.config import override_settings
from ..installed_session import SESSION_INVENTORY_UNAVAILABLE, _runtime_session_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_startup_unavailable_names_manager(capsys: pytest.CaptureFixture[str]) -> None:
    with override_settings(cadrumo_output_language="es"):
        result = _runtime_session_refusal(RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE))
    assert result == SESSION_INVENTORY_UNAVAILABLE
    output = capsys.readouterr().err
    assert output.startswith("runtime_unavailable\n")
    assert "gestor" in output and "Cadrumo" in output


def test_other_startup_refusal_keeps_existing_output(capsys: pytest.CaptureFixture[str]) -> None:
    _runtime_session_refusal(RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME))
    assert capsys.readouterr().err == RuntimeRefusalCode.INVALID_FRAME.value + "\n"
