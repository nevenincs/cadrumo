import pytest

from ...auth.models import AuthState

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_persisted_auth_state_has_the_auth_model_home() -> None:
    assert AuthState.__module__ == "cadrumo.application.auth.models"
