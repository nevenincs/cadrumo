"""Cross-language honesty for the canonical profile-password refusal leaves."""

from __future__ import annotations

import pytest

from ....core.i18n._render import tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_CASES = (
    ("profile_password_too_few_scalars", {"minimum_scalars": 8, "scalar_count": 7}),
    ("profile_password_too_many_scalars", {"maximum_scalars": 256, "scalar_count": 257}),
    ("profile_password_too_many_utf8_bytes", {"maximum_utf8_bytes": 1024, "utf8_byte_count": 1025}),
    ("profile_password_contains_surrogate", {}),
    ("profile_authentication_refused", {}),
)


@pytest.mark.parametrize(("leaf", "context"), _CASES)
def test_profile_password_messages_are_complete_distinct_real_translations(
    leaf: str,
    context: dict[str, int],
) -> None:
    rendered = [tr(f"application.user_profile.errors.{leaf}", locale=locale, **context) for locale in _LOCALES]
    assert all(rendered)
    assert len(set(rendered)) == len(_LOCALES)
    assert all("{" not in message and "}" not in message for message in rendered)
    assert all("application.user_profile.errors" not in message for message in rendered)
