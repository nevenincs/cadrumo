"""A revoked request never reaches native process creation."""

from pathlib import Path

import pytest

from ..auth_attempt import AuthAttempt

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_revoked_attempt_closes_without_creating_a_process_or_profile(tmp_path: Path) -> None:
    attempt = AuthAttempt(
        provider="example",
        lane="example_cli",
        executable=tmp_path / "absent.exe",
        arguments=(),
        directory=tmp_path / "absent",
        environment={},
        valid=lambda: False,
    )
    attempt.close()
    assert not attempt.active
    assert attempt.observe() == {"attempt_id": attempt.id, "provider": "example_cli", "event": "cancelled"}
    assert list(tmp_path.iterdir()) == []
