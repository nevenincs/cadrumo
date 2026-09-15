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

from ....core.i18n.render import tr
from ..models import WizardFlow
from .registry_setup_flow_support import registry_setup_flow as registry_setup_flow

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SUPPORTED_LOCALES: tuple[str, ...] = ("en", "es", "ca", "hu")


def test_wizard_flow_description_key_resolves(*, registry_setup_flow: WizardFlow) -> None:
    """Assert each wizard flow description key resolves to a real string.

    A self-referencing placeholder (resolved == key) means the key is
    absent from the catalogue — this would render as the raw dotted key
    in the CLI ``--help`` output.
    """
    flow_description_keys = frozenset({f"wizard.{registry_setup_flow.id}.description"})
    for key in sorted(flow_description_keys):
        for locale in _SUPPORTED_LOCALES:
            resolved = tr(key, locale=locale)
            assert resolved != key, (
                f"Wizard flow description key {key!r} is absent from the {locale!r} catalogue "
                f"(resolved to self-referencing placeholder {resolved!r}). "
                f"Add a translation for {key!r} in the {locale!r} catalogue."
            )
            assert resolved, f"Wizard flow description key {key!r} resolved to empty string in {locale!r}."
