"""Locale-coverage audit for wizard descriptor strings.

``audit_wizard_translations`` walks every :class:`Translatable` value
declared anywhere in :data:`WIZARD_FLOWS` (titles, prompts, helps,
choice labels and descriptions, plus the fixed error keys the runtime
raises) and the wizard-derived flag-help keys, returning the tuple of
keys that fail to resolve in any of the four locale catalogues.

``audit_cli_config_translations`` runs the same locale-resolution
sweep over every ``cli.config.*`` translation key referenced in
``src/aeat/entrypoints/cli/_config.py`` (statically extracted from
the source). Both audits are exercised by the test suite.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

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
                # Each question contributes a wizard.<flow>.flags.<id>.help
                # key consumed by build_wizard_command's Typer flag derivation.
                keys.append(f"wizard.{flow.id}.flags.{question.id}.help")
        keys.append(f"cli.config.{flow.id}.help")
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


_CLI_CONFIG_KEY_PATTERN = re.compile(r"['\"](cli\.config(?:\.[A-Za-z0-9_]+)+)['\"]")


def _config_module_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "entrypoints" / "cli" / "_config.py"


def cli_config_keys_referenced_in_source() -> tuple[str, ...]:
    """Return every ``cli.config.*`` translation key referenced by ``_config.py``.

    Extracted statically by regex over the source. ``f`` strings that
    interpolate the flow id (``f"cli.config.{flow.id}.help"``) are not
    captured by this regex; those keys are walked by
    :func:`audit_wizard_translations` instead.
    """

    source = _config_module_path().read_text(encoding="utf-8")
    return tuple(sorted({match.group(1) for match in _CLI_CONFIG_KEY_PATTERN.finditer(source)}))


def audit_cli_config_translations() -> tuple[str, ...]:
    """Return the ``cli.config.*`` keys that fail to resolve in any locale."""

    missing: list[str] = []
    for key in cli_config_keys_referenced_in_source():
        for locale in _LOCALES:
            if not _resolves_in(locale, key):
                missing.append(f"{locale}:{key}")
    return tuple(missing)


__all__ = [
    "audit_cli_config_translations",
    "audit_wizard_translations",
    "cli_config_keys_referenced_in_source",
]
