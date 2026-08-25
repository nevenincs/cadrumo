"""Locale-coverage audit for wizard descriptor and CLI translation strings.

``audit_wizard_translations`` walks every :class:`Translatable` value
declared anywhere in :data:`WIZARD_FLOWS` (titles, prompts, helps,
choice labels and descriptions, plus the fixed error keys the runtime
raises) and the wizard-derived flag-help keys, returning the tuple of
keys that fail to resolve in any supported locale catalogue.

``audit_cli_translations`` runs the same locale-resolution sweep over
every ``cli.<group>.*`` translation key referenced at a ``tr(...)``
call site in any module under :mod:`cadrumo.entrypoints.cli`. The audit
treats a locale that returns the literal key text -- the python-i18n
fallback behaviour when a key is absent or its value mirrors the key
itself -- as a structured failure.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from ...core.directory_scan import scan_directory
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from .catalogue import WIZARD_FLOWS
from .models import WizardFlow, WizardQuestion

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
                keys.extend(_question_translation_keys(question, flow_id=flow.id))
        keys.append(f"cli.config.{flow.id}.help")
    keys.extend(_FIXED_RUNTIME_KEYS)
    return tuple(keys)


def _question_translation_keys(question: WizardQuestion, *, flow_id: str) -> tuple[str, ...]:
    """Return every translation key contributed by one wizard question.

    Covers the prompt, the optional help string, every choice's label
    and optional description, and the derived
    ``wizard.<flow>.flags.<id>.help`` key consumed by
    ``build_wizard_command`` for Typer flag descriptions.
    """
    keys: list[str] = [str(question.prompt)]
    if question.help is not None:
        keys.append(str(question.help))
    for choice in question.choices:
        keys.append(str(choice.label))
        if choice.description is not None:
            keys.append(str(choice.description))
    keys.append(f"wizard.{flow_id}.flags.{question.id}.help")
    return tuple(keys)


_UNRESOLVED_SENTINEL = "\x00aeat-wizard-translation-unresolved\x00"


def _resolves_in(locale: str, key: str) -> bool:
    """Return True when ``key`` resolves to a real translation.

    ``tr`` falls back to a humanised form of the key (not the raw
    key) when no translation exists, so a raw-key comparison can
    never detect a miss. Passing a sentinel ``default`` makes the
    miss unambiguous: an unresolved key renders exactly the
    sentinel, a resolved one renders its translation.
    """
    rendered = tr(key, locale=locale, default=_UNRESOLVED_SENTINEL)
    return rendered != _UNRESOLVED_SENTINEL


def audit_wizard_translations() -> tuple[str, ...]:
    """Return the keys that fail to resolve in any locale.

    A key is considered missing for a locale when ``tr(key,
    locale=...)`` returns the raw key itself (the python-i18n
    fallback behaviour).
    """
    keys = _walk_keys(WIZARD_FLOWS)
    missing: list[str] = []
    for key in keys:
        for locale in SUPPORTED_OUTPUT_LANGUAGES:
            if not _resolves_in(locale, key):
                missing.append(f"{locale}:{key}")
    return tuple(missing)


_CLI_KEY_PATTERN = re.compile(r"['\"](cli\.\w+(?:\.\w+)+)['\"]", re.UNICODE)


def _cli_entrypoints_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "entrypoints" / "cli"


def cli_keys_referenced_in_source() -> tuple[str, ...]:
    """Return every ``cli.<group>.*`` translation key referenced statically.

    Walks every ``.py`` module under :mod:`cadrumo.entrypoints.cli` and
    extracts literal ``cli.<group>.<rest>`` strings by regex. f-string
    interpolations that build keys at runtime (for example
    ``f"cli.config.{flow.id}.help"``) are not captured here; those keys
    are walked by :func:`audit_wizard_translations` through the wizard
    descriptor catalogue instead.
    """
    keys: set[str] = set()
    for module in scan_directory(_cli_entrypoints_root(), pattern="*.py", recursive=True):
        # Test modules cite translation-key prefixes in assertions
        # (e.g. `"cli.app.live.iva_wallet.acquisition.outcome"` used as a
        # leak-detection sentinel in `not in label` checks). Those are
        # introspection literals, not `tr()` call sites; auditing them
        # as required catalogue entries would fabricate dead translations.
        if module.name.startswith(("test_", "_test_")):
            continue
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
        for locale in SUPPORTED_OUTPUT_LANGUAGES:
            if not _resolves_in(locale, key):
                missing.append(f"{locale}:{key}")
    return tuple(missing)


__all__ = [
    "audit_cli_translations",
    "audit_wizard_translations",
    "cli_keys_referenced_in_source",
]
