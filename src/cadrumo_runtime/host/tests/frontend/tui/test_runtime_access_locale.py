"""The profile access screen has real labels in every supported language."""

from __future__ import annotations

import pytest

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_KEYS = (
    "tui.runtime_access.title",
    "tui.runtime_access.sessions",
    "tui.runtime_access.sessions_empty",
    "tui.runtime_access.deny_kind",
    "tui.runtime_access.deny_target",
    "tui.runtime_access.deny_key",
    "tui.runtime_access.deny_grant",
    "tui.runtime_access.deny_all",
    "tui.runtime_access.lock_current",
    "tui.runtime_access.lock_profile",
    "tui.runtime_access.resume_password",
    "tui.runtime_access.resume_grants",
    "tui.runtime_access.resume",
    "tui.runtime_access.refresh",
    "tui.runtime_access.close",
    "tui.runtime_access.busy",
    "tui.runtime_access.refused",
    "tui.runtime_access.completed",
    "tui.runtime_access.invalid_target",
    "tui.runtime_access.invalid_grants",
    "tui.runtime_access.access_lost",
)


@pytest.mark.parametrize("locale", tuple(OutputLanguage))
def test_runtime_access_screen_keys_render_without_fallback(locale: OutputLanguage) -> None:
    for key in _KEYS:
        value = tr(key, locale=locale)
        assert value and value != key
