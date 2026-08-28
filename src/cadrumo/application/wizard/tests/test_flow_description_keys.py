"""contract: Wizard flow description key inventory test.

Asserts that every registered wizard flow carries a locale key
``wizard.{flow.id}.description`` that resolves to a non-trivial string
in all four supported catalogues.

The ``build_wizard_command`` function sets ``__doc__`` via
``tr(f"wizard.{flow.id}.description")`` at module-init time; this test
locks the static inventory so a missing key is caught before runtime.
"""

from __future__ import annotations

import pytest

from ....core.i18n import tr
from ..catalogue import WIZARD_FLOWS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SUPPORTED_LOCALES: tuple[str, ...] = ("en", "es", "ca", "hu")

_FLOW_DESCRIPTION_KEYS: frozenset[str] = frozenset(f"wizard.{flow.id}.description" for flow in WIZARD_FLOWS)


def test_wizard_flow_description_key_resolves() -> None:
    """Assert each wizard flow description key resolves to a real string.

    A self-referencing placeholder (resolved == key) means the key is
    absent from the catalogue — this would render as the raw dotted key
    in the CLI ``--help`` output.
    """
    for key in sorted(_FLOW_DESCRIPTION_KEYS):
        for locale in _SUPPORTED_LOCALES:
            resolved = tr(key, locale=locale)
            assert resolved != key, (
                f"Wizard flow description key {key!r} is absent from the {locale!r} catalogue "
                f"(resolved to self-referencing placeholder {resolved!r}). "
                f"Add a translation for {key!r} in the {locale!r} catalogue."
            )
            assert resolved, f"Wizard flow description key {key!r} resolved to empty string in {locale!r}."
