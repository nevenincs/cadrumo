"""Behavioral coverage for the metadata-invocation contract."""

from __future__ import annotations

import pytest

from ..cli_metadata import is_metadata_invocation

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ((), False),
        (("app", "overview", "--help"), True),
        (("--version",), True),
        (("--helpful",), False),
    ],
)
def test_metadata_invocation_recognises_only_canonical_help_and_version_tokens(
    arguments: tuple[str, ...], expected: bool
) -> None:
    assert is_metadata_invocation(arguments) is expected
