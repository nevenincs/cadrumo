"""Real CLI proof that malformed input reaches the input-validation boundary."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Provide a real active storage runtime for command dispatch."""
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PROFILE_ID,
        label="CLI boundary profile",
    ) as profile:
        yield profile


def test_malformed_cli_input_surfaces_input_time_validation_boundary(
    runtime_profile: TestRuntimeProfile,
) -> None:
    """Bad command input fails before any profile record is interpreted."""
    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "add",
            "--date",
            "not-a-date",
            "--amount",
            "50.00",
            "--direction",
            "OUTGOING",
            "--description",
            "test entry",
        ],
    )

    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "no longer matches the expected schema" not in combined
    assert "config repair" not in combined


def test_an_unexpected_error_names_its_type_and_raising_frame_but_not_its_message() -> None:
    from ..errors import CliUnexpectedBoundaryError

    def fail() -> None:
        raise ValueError("timeout must be at most 120 seconds for https://x/?nif=X1234567L")

    with pytest.raises(ValueError) as raised:
        fail()
    boundary = CliUnexpectedBoundaryError(raised.value)

    assert boundary.context is not None
    assert boundary.context["exception_type"] == "ValueError"
    assert str(boundary.context["raised_at"]).endswith(":fail:" + str(fail.__code__.co_firstlineno + 1))
    assert "X1234567L" not in repr(boundary.context)
