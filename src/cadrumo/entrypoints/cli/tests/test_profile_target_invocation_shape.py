"""Invocation-shape regressions for optional profile read targets."""

from __future__ import annotations

import pytest

from .. import _has_explicit_profile_read_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "tokens",
    (
        ("--format", "json"),
        ("--language", "en"),
        ("--output-language=en",),
        ("--profile", "operator"),
        ("--event-type", "profile.activated"),
        ("--since", "2026-08-01T00:00:00+00:00"),
        ("--until=2026-08-10T00:00:00+00:00",),
        ("--object-id", "profile-record"),
        ("--actor=operator",),
    ),
)
def test_profile_read_option_values_are_not_mistaken_for_positional_targets(
    tokens: tuple[str, ...],
) -> None:
    assert not _has_explicit_profile_read_target(tokens)


@pytest.mark.parametrize(
    "tokens",
    (
        ("operator",),
        ("--language", "en", "operator"),
        ("--event-type=profile.activated", "operator"),
    ),
)
def test_profile_read_positional_target_is_detected_after_options(tokens: tuple[str, ...]) -> None:
    assert _has_explicit_profile_read_target(tokens)
