"""The output-language value contract and the options that carry it.

Every executable that renders translated output accepts the same language
choice; the tax CLI and the runtime executable each restated these
declarations, so one module now defines them.
"""

from __future__ import annotations

from .parameters import OptionSpec
from .shared_contracts import DeferredTarget, ParameterDefault, TranslationKey, ValueContract

__all__ = ["OUTPUT_LANGUAGE_OPTION", "OUTPUT_LANGUAGE_VALUE", "ROOT_LANGUAGE_OPTION"]

OUTPUT_LANGUAGE_VALUE = ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage"))
"""The deferred ``OutputLanguage`` value contract."""

OUTPUT_LANGUAGE_OPTION = OptionSpec(
    name="output_language",
    declarations=("--output-language", "--language"),
    value=OUTPUT_LANGUAGE_VALUE,
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.auth.output_language_help"),
)
"""The optional per-leaf output-language override."""

ROOT_LANGUAGE_OPTION = OptionSpec(
    name="language",
    declarations=("--language", "--lang"),
    value=OUTPUT_LANGUAGE_VALUE,
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.root.language_help"),
    eager=True,
)
"""The eager executable-root language option, read before subcommands render help."""
