"""Lazily-resolved :class:`SensitivityClass` DIAGNOSTIC redaction rule set.

The :func:`diagnostic_rules` helper resolves the DIAGNOSTIC-class rule
set lazily on first call so the observability package does not pull
:mod:`cadrumo.adapters.persistence.storage` (which triggers Alembic plugin
discovery and emits INFO log lines on stderr at import time) into every
CLI command's import chain. The cost of resolving the rule set once is
negligible compared with one-time Alembic discovery.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..classification.policies import RedactionRule


# Cached at module scope after first resolution so repeated emits do not
# re-import the redaction substrate.
_DIAGNOSTIC_RULES: tuple[RedactionRule, ...] | None = None


def diagnostic_rules() -> tuple[RedactionRule, ...]:
    """Return the DIAGNOSTIC-class default rule set, resolved on first call.

    Cached at module scope after first resolution so repeated emits do
    not re-import the redaction substrate.

    Returns:
        A tuple of :class:`RedactionRule` instances for the
        ``DIAGNOSTIC`` sensitivity class.
    """
    global _DIAGNOSTIC_RULES
    if _DIAGNOSTIC_RULES is None:
        from ..classification.policies import SensitivityClass
        from ..redaction.rules import default_rules_for_class

        _DIAGNOSTIC_RULES = default_rules_for_class(SensitivityClass.DIAGNOSTIC)
    return _DIAGNOSTIC_RULES
