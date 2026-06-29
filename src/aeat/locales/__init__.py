"""Locale-catalogue maintenance facade for YAML and modelo translations.

The package keeps the four runtime catalogues (``en``, ``es``, ``ca``, ``hu``)
in sync with codebase translation keys and enforces inter-locale parity. The
developer CLI (``python -m aeat.locales``) owns edits through ``set``,
``remove``, ``scaffold``, ``scaffold --check``, and ``audit`` commands; the
catalogue YAML is CLI-maintained, not hand-edited.

Modelo schema-local translations are handled by the same facade through
``modelo`` subcommands and the :class:`~aeat.locales.ModeloLocaleManager`
record set. Those TOML-backed translations stay separate from the runtime YAML
catalogues while sharing the same drift-reporting discipline.

Major declarations:

* :class:`~aeat.locales.LocaleManager` loads, scaffolds, checks, and audits the
  runtime locale catalogues.
* :class:`~aeat.locales.ModeloLocaleManager` manages schema-local modelo
  translation files and coverage reports.
* :class:`~aeat.locales.StrictUniqueKeyLoader` rejects duplicate YAML keys at
  parse time.
* :class:`~aeat.locales.LocaleError` and
  :class:`~aeat.locales.ModeloLocaleError` report maintenance failures.
"""

from __future__ import annotations

from ._modelo_manager import (
    ModeloLocaleCoverageRecord,
    ModeloLocaleDriftKind,
    ModeloLocaleDriftRecord,
    ModeloLocaleError,
    ModeloLocaleFieldKind,
    ModeloLocaleFileTarget,
    ModeloLocaleInventoryKey,
    ModeloLocaleManager,
    ModeloLocaleScope,
    ModeloLocaleTranslationFile,
)
from .manager import LocaleError, LocaleManager, StrictUniqueKeyLoader

__all__ = [
    "LocaleError",
    "LocaleManager",
    "ModeloLocaleCoverageRecord",
    "ModeloLocaleDriftKind",
    "ModeloLocaleDriftRecord",
    "ModeloLocaleError",
    "ModeloLocaleFieldKind",
    "ModeloLocaleFileTarget",
    "ModeloLocaleInventoryKey",
    "ModeloLocaleManager",
    "ModeloLocaleScope",
    "ModeloLocaleTranslationFile",
    "StrictUniqueKeyLoader",
]
