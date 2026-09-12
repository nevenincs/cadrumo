"""Editions and modelos a corpus run is told not to touch.

A campaign tool decides what it *can* do from the corpus. What it *may* do is a
separate judgement the corpus cannot carry: an edition whose grounding another
lane is adjudicating is perfectly liftable and still must not be lifted here,
because two lanes writing one edition is how a campaign loses work. This module
is where that judgement is stated, once, for every tool that walks the corpus.

An exclusion names a whole modelo or one of its editions, and always carries the
reason it was made. The reason is part of the exclusion rather than a property
of the run: a campaign file groups several unrelated judgements, and a single
run-wide reason would make one of them stand for all.

:data:`FROZEN_MODELOS` is the structural half of the same idea. Those modelos
are excluded from every run whether or not anyone passes a flag, because a
freeze that depends on the operator remembering a flag is not a freeze.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

__all__ = [
    "FROZEN_MODELOS",
    "FROZEN_REASON",
    "Exclusion",
    "ExclusionSet",
    "collect_exclusions",
    "excluded_editions",
    "frozen_exclusions",
    "parse_exclusion",
    "parse_exclusions_file",
]

#: Modelos no corpus tool may plan under, flags or no flags. They are another
#: lane's adjudication surface; lift here by hand-off only.
FROZEN_MODELOS: Final[tuple[str, ...]] = ("100", "200")

FROZEN_REASON: Final = "frozen: another lane's adjudication surface; lift here by hand-off only"

#: The reason recorded for an exclusion the operator named without giving one.
DEFAULT_EXCLUSION_REASON: Final = "excluded by the operator for this run"


class MalformedExclusionError(ValueError):
    """An exclusion the tool will not guess the meaning of."""


@dataclass(frozen=True, slots=True)
class Exclusion:
    """One withheld modelo or edition, and why it is withheld.

    An empty ``edition`` withholds the whole modelo. The distinction is kept
    rather than expanded into every edition the modelo happens to carry today,
    so a modelo exclusion keeps holding when an edition is added to it.
    """

    modelo: str
    edition: str
    reason: str

    @property
    def target(self) -> str:
        """The exclusion as the operator named it."""
        return f"{self.modelo}/{self.edition}" if self.edition else self.modelo

    def render(self) -> str:
        """The report line for this exclusion."""
        return f"excluded: {self.target} reason={self.reason}"


@dataclass(frozen=True, slots=True)
class ExclusionSet:
    """Every exclusion of one run, answered per modelo and per edition."""

    exclusions: tuple[Exclusion, ...]

    def excludes_modelo(self, modelo: str) -> bool:
        """Whether the whole modelo is withheld."""
        return any(item.modelo == modelo and not item.edition for item in self.exclusions)

    def editions_of(self, modelo: str) -> tuple[str, ...]:
        """The individually withheld editions of this modelo, in the order they were named."""
        return tuple(item.edition for item in self.exclusions if item.modelo == modelo and item.edition)

    def excludes(self, modelo: str, edition: str) -> bool:
        """Whether this edition is withheld, by its own name or by its modelo's."""
        return self.excludes_modelo(modelo) or edition in self.editions_of(modelo)

    def render_lines(self) -> list[str]:
        """Every exclusion as a report line, so a run states what it declined to look at."""
        return [item.render() for item in self.exclusions]

    def as_json(self) -> list[dict[str, str]]:
        """Every exclusion as report JSON."""
        return [{"target": item.target, "reason": item.reason} for item in self.exclusions]


def frozen_exclusions() -> tuple[Exclusion, ...]:
    """The structural exclusions every run carries."""
    return tuple(Exclusion(modelo=modelo, edition="", reason=FROZEN_REASON) for modelo in FROZEN_MODELOS)


def parse_exclusion(text: str, reason: str) -> Exclusion:
    """Parse one ``<modelo>`` or ``<modelo>/<edition>`` exclusion.

    A trailing separator with no edition is refused rather than read as the
    whole modelo: widening an exclusion on a typo is safe for the corpus but
    silently drops work the operator meant to plan.
    """
    modelo, separator, edition = text.strip().partition("/")
    if not modelo.strip() or (separator and not edition.strip()):
        raise MalformedExclusionError(f"malformed exclusion {text!r}: expected '<modelo>' or '<modelo>/<edition>'")
    return Exclusion(modelo=modelo.strip(), edition=edition.strip(), reason=reason)


def parse_exclusions_file(path: Path) -> tuple[Exclusion, ...]:
    """Parse an exclusions file: one ``<modelo>`` or ``<modelo>/<edition>`` per line.

    A ``#`` comment line states the reason for the entries that follow it, up to
    the next comment line, which is how a campaign file keeps each group's
    judgement beside the entries it was made about. An entry before any comment
    carries the default reason. Blank lines are ignored and duplicates collapse
    in first-seen order.
    """
    found: dict[tuple[str, str], Exclusion] = {}
    reason = DEFAULT_EXCLUSION_REASON
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            comment = line.lstrip("#").strip()
            if comment:
                reason = comment.removeprefix("reason:").strip()
            continue
        try:
            item = parse_exclusion(line, reason)
        except MalformedExclusionError as exc:
            raise MalformedExclusionError(f"{path}:{number}: {exc}") from exc
        found.setdefault((item.modelo, item.edition), item)
    if not found:
        raise MalformedExclusionError(f"{path}: names no exclusion")
    return tuple(found.values())


def collect_exclusions(
    *,
    modelos: Sequence[str] = (),
    editions: Sequence[str] = (),
    reason: str = DEFAULT_EXCLUSION_REASON,
    path: Path | None = None,
) -> ExclusionSet:
    """Assemble one run's exclusions from the flags, the file, and the frozen modelos.

    The frozen modelos come first and are never overridden by a later entry, so
    a campaign file cannot un-freeze one by naming it with a softer reason.
    """
    found: dict[tuple[str, str], Exclusion] = {(item.modelo, item.edition): item for item in frozen_exclusions()}
    named: Iterable[Exclusion] = (
        *(parse_exclusion(text, reason) for text in modelos),
        *(parse_exclusion(text, reason) for text in editions),
        *(parse_exclusions_file(path) if path is not None else ()),
    )
    for item in named:
        found.setdefault((item.modelo, item.edition), item)
    return ExclusionSet(exclusions=tuple(found.values()))


def excluded_editions(exclusions: ExclusionSet, modelo: str) -> Mapping[str, str]:
    """The withheld editions of one modelo, mapped to the reason each was withheld."""
    return {item.edition: item.reason for item in exclusions.exclusions if item.modelo == modelo and item.edition}
