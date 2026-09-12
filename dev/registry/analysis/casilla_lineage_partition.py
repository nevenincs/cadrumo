"""Lineage totality partitioned by modelo, so a modelo it cannot load is reported, never dropped.

:func:`~cadrumo.domain.calculations.registry.casilla_lineage_totality.lineage_totality`
judges whatever corpus it is handed. Handed a corpus that is missing a modelo,
it says nothing about that modelo: the modelo's unresolved rows are not
uncovered, because they are not in the corpus, and the ledger entries naming
them read as stale, because nothing needs them. Both answers are wrong in the
same direction -- towards green -- and a modelo that will not compile is exactly
when they are given.

Partitioning makes that state sayable. The corpus is compiled one modelo at a
time, as the seeder compiles it, so one modelo that will not load stops only
itself. The modelos that loaded are JUDGED. The modelos that did not are
UNJUDGED and are named in the report. Ledger entries naming an unjudged modelo
are WITHHELD: neither counted as covering a row nor reported stale, because this
run saw no corpus to judge them against.

A report is then in one of three states, and only the first is green:

- ``total`` -- every modelo judged, every unresolved row covered, no entry stale;
- ``partial_with_unjudged`` -- everything judged came out total, but at least one
  modelo could not be judged at all;
- ``not_total`` -- some judged row is uncovered or some judged entry is stale.

``partial_with_unjudged`` is never green. An unjudged modelo is an absence of
evidence, and the ledger's carried entries for it are assertions about a corpus
state this run never saw.
"""

from __future__ import annotations

import collections
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.casilla_lineage_totality import (
    CasillaRowKey,
    lineage_totality,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler.loader_cache import discover_modelo_sources
from .casilla_lineage_seed import load_corpus

__all__ = [
    "LineageTotalityState",
    "PartitionedTotalityReport",
    "load_partitioned_corpus",
    "partitioned_lineage_totality",
]

_SHOWN = 20


class LineageTotalityState(StrEnum):
    """The three answers a partitioned totality judgement can give."""

    TOTAL = "total"
    PARTIAL_WITH_UNJUDGED = "partial_with_unjudged"
    NOT_TOTAL = "not_total"


@dataclass(frozen=True, slots=True)
class PartitionedTotalityReport:
    """What the judged modelos came out at, and which modelos could not be judged."""

    uncovered: tuple[CasillaRowKey, ...]
    stale: tuple[CasillaRowKey, ...]
    judged: tuple[str, ...]
    unjudged: tuple[str, ...]
    withheld: tuple[CasillaRowKey, ...]

    @property
    def state(self) -> LineageTotalityState:
        """The report's state; a judged failure outranks an unjudged modelo, and both are non-green."""
        if self.uncovered or self.stale:
            return LineageTotalityState.NOT_TOTAL
        return LineageTotalityState.PARTIAL_WITH_UNJUDGED if self.unjudged else LineageTotalityState.TOTAL

    @property
    def is_green(self) -> bool:
        """Whether the corpus was judged whole and came out total. Partial is never green."""
        return self.state is LineageTotalityState.TOTAL

    def describe(self) -> str:
        """The whole judgement in prose, naming every unjudged modelo on every run."""
        lines = [
            f"lineage totality: {self.state} over {len(self.judged)} judged modelo(s)",
            f"unjudged modelos: {list(self.unjudged)}",
        ]
        if self.unjudged:
            lines.append(
                f"{len(self.withheld)} ledger refusal(s) withheld from judgement because their modelo "
                "could not be loaded; they are neither counted as covering a row nor reported stale"
            )
        reported = (
            ("unresolved rows the ledger does not name", self.uncovered),
            ("ledger refusals whose row no longer needs one", self.stale),
        )
        for label, keys in reported:
            if keys:
                lines.append(_describe(label, keys))
        return "\n".join(lines)


def _describe(label: str, keys: tuple[CasillaRowKey, ...]) -> str:
    by_modelo = collections.Counter(key.modelo for key in keys)
    shown = "\n  ".join(f"{key.modelo} {key.revision} {key.casilla}" for key in keys[:_SHOWN])
    return f"{len(keys)} {label} by modelo {dict(sorted(by_modelo.items()))}; first {_SHOWN}:\n  {shown}"


def partitioned_lineage_totality(
    loaded: Mapping[str, ModeloDefinition],
    unjudged: Mapping[str, str],
    exceptions: Collection[CasillaRowKey],
) -> PartitionedTotalityReport:
    """Judge the loaded modelos against the exceptions that name them, and report the rest.

    ``unjudged`` maps each modelo that could not be loaded to the reason. An
    exception naming an unjudged modelo is withheld; an exception naming a
    modelo that is neither loaded nor unjudged is a claim about a modelo the
    corpus does not hold at all, and stays in the judgement so it reads stale.
    """
    withheld = tuple(sorted(key for key in exceptions if key.modelo in unjudged))
    remaining = {key for key in exceptions if key.modelo not in unjudged}
    report = lineage_totality(loaded.values(), remaining)
    return PartitionedTotalityReport(
        uncovered=report.uncovered,
        stale=report.stale,
        judged=tuple(sorted(loaded)),
        unjudged=tuple(sorted(unjudged)),
        withheld=withheld,
    )


def load_partitioned_corpus() -> tuple[dict[str, ModeloDefinition], dict[str, str]]:
    """Compile the bundled corpus one modelo at a time, returning what loaded and what did not."""
    loaded, failures = load_corpus(discover_modelo_sources(bundled_path("registry", "aeat", "modelos")))
    return loaded, {failure.modelo: failure.reason for failure in failures}
