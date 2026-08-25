import pytest

from .. import AuthState

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_persisted_auth_state_is_workflow_owned() -> None:
    assert AuthState.__module__ == "cadrumo.application._workflow_auth_models"
