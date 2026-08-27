"""The public login interaction contract is frontend-neutral and canonical."""

from __future__ import annotations

import ast
import inspect

import pytest

from ....domain.user_profile.errors import ProfileNotFoundError
from ....tests.secure_sql import isolated_profile_storage_root
from ..login_interaction import (
    ProfileLoginAttempt,
    ProfileLoginChoice,
    attempt_profile_login,
    preselected_profile_login_id,
    profile_login_choices,
)
from ..login_session import logout_active_profile
from ..registration import register_profile_with_credentials

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSWORD = "login-interaction-operator-secret"  # noqa: S105 - synthetic test fixture


def _register(label: str) -> str:
    outcome = register_profile_with_credentials(
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        label=label,
        passphrase=_PASSWORD,
    )
    return outcome.bucket_id


def test_choices_are_stably_sorted_and_carry_only_chooser_data(tmp_path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        beta = _register("Beta Subject")
        alpha = _register("Alpha Subject")
        logout_active_profile()

        choices = profile_login_choices()

        assert choices == (
            ProfileLoginChoice(profile_id=alpha, label="Alpha Subject"),
            ProfileLoginChoice(profile_id=beta, label="Beta Subject"),
        )
        assert preselected_profile_login_id(None) is None


def test_named_preselection_uses_the_login_target_authority(tmp_path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register("Routing Subject")
        logout_active_profile()

        assert preselected_profile_login_id("Routing Subject") == profile_id
        assert preselected_profile_login_id(profile_id) == profile_id
        with pytest.raises(ProfileNotFoundError):
            preselected_profile_login_id("Routing Subjekt")


def test_attempt_projects_an_expected_refusal_without_a_frontend_exception(tmp_path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        attempt = attempt_profile_login("no-such-profile", _PASSWORD)

        assert isinstance(attempt, ProfileLoginAttempt)
        assert attempt.outcome is None
        assert attempt.refusal


def test_attempt_returns_the_real_login_outcome_after_unlocking(tmp_path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register("Unlocked Subject")
        logout_active_profile()

        attempt = attempt_profile_login(profile_id, _PASSWORD)

        assert attempt.refusal is None
        assert attempt.outcome is not None
        assert attempt.outcome.bucket_id == profile_id


def test_attempt_catches_only_the_enrolled_authentication_refusal_family() -> None:
    """Unrelated application errors remain outside the interaction-data boundary."""
    function = ast.parse(inspect.getsource(attempt_profile_login)).body[0]
    assert isinstance(function, ast.FunctionDef)
    handlers = [node for node in ast.walk(function) if isinstance(node, ast.ExceptHandler)]
    assert len(handlers) == 1
    caught = handlers[0].type
    assert isinstance(caught, ast.Tuple)
    assert {node.id for node in caught.elts if isinstance(node, ast.Name)} == {
        "ProfileAuthenticationRefusedError",
        "ProfileLoginThrottledError",
        "ProfileNotFoundError",
    }
