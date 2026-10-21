"""The CLI keeps the runtime's post-sign-out access observation explicit."""

from __future__ import annotations

from uuid import UUID

import pytest

from cadrumo_client.contracts.sign_in import HumanSignedOut

from .. import custody

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _signed_out(access_remains: bool | None) -> HumanSignedOut:
    return HumanSignedOut(
        request_id=UUID(int=1),
        runtime_boot_id=UUID(int=2),
        connection_id=UUID(int=3),
        profile_id=UUID(int=4),
        session_ids=(),
        receipt_removed=True,
        keychain_removed=True,
        automation_enabled=True,
        automation_access_remains=access_remains,
    )


@pytest.mark.parametrize("access_remains", [True, False, None])
def test_logout_projection_preserves_remaining_access_without_inference(access_remains: bool | None) -> None:
    result = custody._config_logout_result(
        _signed_out(access_remains),
        logged_out_profile="Selected profile",
        already_logged_out=False,
    )

    payload = result.model_dump(mode="json")
    assert payload["automation_enabled"] is True
    assert payload["automation_access_remains"] is access_remains
    assert payload["automation_revoked"] is False


def test_logout_without_a_runtime_observation_keeps_access_unknown() -> None:
    result = custody._config_logout_result(
        None,
        logged_out_profile=None,
        already_logged_out=True,
    )

    payload = result.model_dump(mode="json")
    assert payload["automation_enabled"] is None
    assert payload["automation_access_remains"] is None
