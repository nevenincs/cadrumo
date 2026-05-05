"""CLI-facing re-export of the shared i18n rendering primitives.

The actual implementation lives in :mod:`aeat.core.i18n` so application
and adapter layers can render translatable keys without depending on
the CLI entrypoints.
"""

from __future__ import annotations

from ...core.i18n import output_language, tr

__all__ = ["output_language", "tr"]
