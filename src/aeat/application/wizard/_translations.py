"""Locale-coverage audit for wizard descriptor strings.

``audit_wizard_translations`` walks every :class:`Translatable` value
declared anywhere in :data:`WIZARD_FLOWS` (titles, prompts, helps,
choice labels and descriptions, plus the fixed error keys the runtime
raises) and returns the tuple of keys that fail to resolve in any of
the four locale catalogues.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...core.i18n import tr
from ._catalogue import WIZARD_FLOWS
from ._models import WizardFlow

_LOCALES: tuple[str, ...] = ("en", "es", "ca", "hu")

_FIXED_RUNTIME_KEYS: tuple[str, ...] = ("wizard.setup.errors.missing_required_flags",)


def _walk_keys(flows: Iterable[WizardFlow]) -> tuple[str, ...]:
    """Return every translation key referenced by ``flows``."""

    keys: list[str] = []
    for flow in flows:
        keys.append(str(flow.title))
        keys.append(str(flow.description))
        for section in flow.sections:
            keys.append(str(section.title))
            for question in section.questions:
                keys.append(str(question.prompt))
                if question.help is not None:
                    keys.append(str(question.help))
                for choice in question.choices:
                    keys.append(str(choice.label))
                    if choice.description is not None:
                        keys.append(str(choice.description))
    keys.extend(_FIXED_RUNTIME_KEYS)
    return tuple(keys)


def _resolves_in(locale: str, key: str) -> bool:
    """Return True when ``key`` resolves to something other than its raw form."""

    rendered = tr(key, locale=locale)
    return rendered != key


def audit_wizard_translations() -> tuple[str, ...]:
    """Return the keys that fail to resolve in any locale.

    A key is considered missing for a locale when ``tr(key,
    locale=...)`` returns the raw key itself (the python-i18n
    fallback behaviour).
    """

    keys = _walk_keys(WIZARD_FLOWS)
    missing: list[str] = []
    for key in keys:
        for locale in _LOCALES:
            if not _resolves_in(locale, key):
                missing.append(f"{locale}:{key}")
    return tuple(missing)


__all__ = ["audit_wizard_translations"]
