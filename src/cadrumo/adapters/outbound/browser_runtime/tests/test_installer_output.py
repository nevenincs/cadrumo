"""Tolerant reading of the vendor installer's output for a failure's cause."""

from __future__ import annotations

import pytest

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..installer_output import classify_installer_output

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize(
    ("lines", "expected"),
    (
        (["Error: EACCES: permission denied, mkdir '/pw'"], (DependencyFailureCategory.NO_PERMISSION, False)),
        (["server returned code 429 body ''"], (DependencyFailureCategory.HOST_UNREACHABLE, True)),
        (["server returned code 404 body ''"], (DependencyFailureCategory.UNEXPECTED, False)),
        (["Error: read ECONNRESET"], (DependencyFailureCategory.HOST_UNREACHABLE, True)),
        (
            ["Error: self-signed certificate in certificate chain"],
            (DependencyFailureCategory.SECURE_CONNECTION_FAILED, False),
        ),
        (["Failed to download, caused by Download failure, code=1"], (None, False)),
    ),
)
def test_failure_causes_map_to_closed_categories(
    lines: list[str], expected: tuple[DependencyFailureCategory | None, bool]
) -> None:
    assert classify_installer_output(lines) == expected
