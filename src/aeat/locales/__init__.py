"""Locale-catalogue maintenance: the ``aeat.locales`` manager and CLI.

Keeps the four locale catalogues (``en``, ``es``, ``ca``, ``hu``) in sync
with the codebase's translation keys and enforces inter-locale parity. The
CLI (``python -m aeat.locales``) exposes ``set`` and ``remove`` for
individual string leaves, ``scaffold`` (align the catalogues with the
concrete ``tr`` keys), ``scaffold --check`` (the drift gate), and ``audit``
(a codebase-to-locale health report). The catalogue YAML is maintained
through the CLI, never hand-edited.

Major declarations:

* :class:`LocaleManager` — loads, scaffolds, checks, and audits the locale
  catalogues.
* :class:`StrictUniqueKeyLoader` — the YAML loader that rejects duplicate
  keys at parse time.
* :class:`LocaleError` — raised on locale-catalogue maintenance failures.
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
