"""Locale-coverage audit for wizard descriptor and CLI translation strings.

``audit_wizard_translations`` walks every :class:`Translatable` value
declared anywhere in :data:`WIZARD_FLOWS` (titles, prompts, helps,
choice labels and descriptions, plus the fixed error keys the runtime
raises) and the wizard-derived flag-help keys, returning the tuple of
keys that fail to resolve in any of the four locale catalogues.

``audit_cli_translations`` runs the same locale-resolution sweep over
every ``cli.<group>.*`` translation key referenced at a ``tr(...)``
call site in any module under :mod:`aeat.entrypoints.cli`. The audit
treats a locale that returns the literal key text -- the python-i18n
fallback behaviour when a key is absent or its value mirrors the key
itself -- as a structured failure.
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


_CLI_KEY_PATTERN = re.compile(r"['\"](cli\.[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)['\"]")


def _cli_entrypoints_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "entrypoints" / "cli"


def cli_keys_referenced_in_source() -> tuple[str, ...]:
    """Return every ``cli.<group>.*`` translation key referenced statically.

    Walks every ``.py`` module under :mod:`aeat.entrypoints.cli` and
    extracts literal ``cli.<group>.<rest>`` strings by regex. f-string
    interpolations that build keys at runtime (for example
    ``f"cli.config.{flow.id}.help"``) are not captured here; those keys
    are walked by :func:`audit_wizard_translations` through the wizard
    descriptor catalogue instead.
    """

    keys: set[str] = set()
    for module in _cli_entrypoints_root().rglob("*.py"):
        source = module.read_text(encoding="utf-8")
        for match in _CLI_KEY_PATTERN.finditer(source):
            keys.add(match.group(1))
    return tuple(sorted(keys))


def audit_cli_translations() -> tuple[str, ...]:
    """Return the ``cli.*`` keys that fail to resolve in any locale.

    A failure means the locale catalogue either omits the key or stores
    the literal key text as the value, both of which surface as raw key
    strings in operator-facing help output.
    """

    missing: list[str] = []
    for key in cli_keys_referenced_in_source():
        for locale in _LOCALES:
            if not _resolves_in(locale, key):
                missing.append(f"{locale}:{key}")
    return tuple(missing)


__all__ = [
    "audit_cli_translations",
    "audit_wizard_translations",
    "cli_keys_referenced_in_source",
]
