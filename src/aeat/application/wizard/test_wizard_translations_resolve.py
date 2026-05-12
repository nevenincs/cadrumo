"""Locale-coverage gate for the wizard descriptor.

``audit_wizard_translations`` walks every ``Translatable`` referenced
by :data:`WIZARD_FLOWS` (plus the fixed runtime error keys) and
asserts every key resolves to non-empty content in every locale.
"""

from __future__ import annotations

import pytest

from aeat.application.wizard._translations import audit_wizard_translations

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_every_wizard_translation_resolves_in_every_locale() -> None:
    missing = audit_wizard_translations()
    assert missing == ()
