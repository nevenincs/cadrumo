"""The served words a refusal's action projection carries, in the language the projection names."""

from __future__ import annotations

from ....application.operator_actions.served_actions import ACTION_WORDS_LOCALE_KEYS, NO_RECOVERY_WORDS_LOCALE_KEYS
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....core.operator_action_enums import NoRecoveryOutcome


def _catalogue_words(key: str, language: str) -> str:
    words = lookup_translation(key, locale=OutputLanguage(language).value)
    assert words is not None, f"{language} has no words for {key}"
    return words


def served_action_words(action_id: str, language: str) -> dict[str, object]:
    """The words and language a resolved action of ``action_id`` carries when served in ``language``."""
    return {
        "action_words": _catalogue_words(ACTION_WORDS_LOCALE_KEYS[action_id], language),
        "action_words_language": language,
    }


def served_no_recovery_words(outcome: NoRecoveryOutcome, language: str) -> dict[str, object]:
    """The sentence a refusal without a way out carries when served in ``language``."""
    return {
        "no_recovery_words": _catalogue_words(NO_RECOVERY_WORDS_LOCALE_KEYS[outcome], language),
        "no_recovery_words_language": language,
    }
