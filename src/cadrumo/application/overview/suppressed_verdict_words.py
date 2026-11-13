"""The sentence the calendar serves for each obligation it holds off its schedule.

A suppressed calendar row keeps the verdict the calendar reached. Two verdicts
positively exclude the obligation: ``NOT_APPLICABLE`` and
``ATTRIBUTION_PASS_THROUGH`` say the taxpayer's declared model files something
else, or nothing of its own. ``INCOMPLETE`` says the calendar could not decide
from the stored facts, which is neither owed nor excluded. Each verdict has one
locale key here, and every frontend reads the sentence the worker renders in
its own language instead of wording a tax meaning of its own.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...domain.calculations.registry.applicability_models import ApplicabilityVerdict

__all__ = [
    "EXCLUDING_VERDICTS",
    "suppressed_verdict_words",
]

_VERDICT_LOCALE_KEYS: Final[Mapping[ApplicabilityVerdict, str]] = MappingProxyType(
    {
        ApplicabilityVerdict.NOT_APPLICABLE: "workspace.declarations.calendar.suppressed.verdict.not_applicable",
        ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH: (
            "workspace.declarations.calendar.suppressed.verdict.attribution_pass_through"
        ),
        ApplicabilityVerdict.INCOMPLETE: "workspace.declarations.calendar.suppressed.verdict.incomplete",
    }
)
"""The sentence of each verdict under which the calendar holds an obligation off its schedule."""

EXCLUDING_VERDICTS: Final[frozenset[ApplicabilityVerdict]] = frozenset(
    verdict for verdict in _VERDICT_LOCALE_KEYS if verdict is not ApplicabilityVerdict.INCOMPLETE
)
"""The verdicts that positively say the obligation is not owed."""


def suppressed_verdict_words(verdict: ApplicabilityVerdict, language: OutputLanguage) -> str:
    """Return the verdict's sentence in ``language``; a verdict that suppresses nothing has none."""
    key = _VERDICT_LOCALE_KEYS.get(verdict)
    if key is None:
        raise ValueError("only an obligation held off the calendar's schedule has verdict words")
    return tr(key, locale=language.value)
