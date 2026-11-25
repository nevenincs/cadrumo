"""Gate: a registry profile key must not carry a filing year in its name.

A binding that reads ``incremento_guarderia_<year>`` ties the result to that
year: a projected year inherits the key of the edition it is projected from and
the profile either has no such key or silently reads another year's. The year
belongs to the resolver, not to the key. Supported years come only from the
registry support envelope.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from cadrumo.domain.calculations.registry.schema import ModeloDefinition

__all__ = ("YearInKeyFinding", "profile_key_year_findings", "years_named_in")

_DIGIT_RUN = re.compile(r"(?<![0-9])([0-9]{4})(?![0-9])")


@dataclass(frozen=True, slots=True)
class YearInKeyFinding:
    """A binding whose profile key names a supported filing year."""

    modelo: str
    edition: str
    binding_id: str
    profile_key: str

    @property
    def key(self) -> str:
        """Return the stable baseline key."""
        return f"year-in-profile-key|{self.modelo}|{self.edition}|{self.binding_id}|{self.profile_key}"


def years_named_in(text: str, years: Sequence[int]) -> tuple[int, ...]:
    """Return the supported years that appear as a whole four-digit token in ``text``."""
    return tuple(year for year in (int(token) for token in _DIGIT_RUN.findall(text)) if year in years)


def profile_key_year_findings(
    modelos: Iterable[ModeloDefinition], years: Sequence[int]
) -> tuple[YearInKeyFinding, ...]:
    """Return every binding whose profile key names a supported year."""
    found: list[YearInKeyFinding] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for binding in revision.bindings:
                profile_key = getattr(binding.provider, "profile_key", None)
                if isinstance(profile_key, str) and years_named_in(profile_key, years):
                    found.append(YearInKeyFinding(str(modelo.id), str(revision.id), str(binding.id), profile_key))
    return tuple(sorted(found, key=lambda item: item.key))
