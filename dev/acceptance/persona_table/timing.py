"""Operation timing read back from the application's diagnostic log, kept as a sidecar of the table.

The application writes one line per committed operation transition, ``operation timing stage=<stage>
epoch_ms=<int> operation=<id> definition=<id>``, with stages ``admitted``, ``running`` and ``settled``. The lines are
best effort: the log is asynchronous and rotating, so a stage can be missing, and ``running`` means the initial
RUNNING commit, not worker readiness. This module reads only those lines and keeps only the operation id, the
definition id, the stage and the epoch milliseconds; every other log line is dropped at the parse. A duration is
``None`` when a stage is missing or the stages are out of order, never zero for "unknown".

The sidecar is a ``timing.jsonl`` file of its own. It is never part of a table row, so ``rows.jsonl`` and the tools
that compare rows are not touched by it.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

TIMING_FILE = "timing.jsonl"
"""The sidecar file name, beside a case's other logs."""
COLLECTED_LOG = "cadrumo.log.collected"
"""The timing lines of a case's storage log, and nothing else of it."""
_LOG_RELATIVE = Path("logs") / "cadrumo.log"
_ROTATED_RELATIVE = Path("logs") / "cadrumo.log.1"
_LINE = re.compile(
    r"operation timing stage=(?P<stage>admitted|running|settled) epoch_ms=(?P<epoch>\d+)"
    r" operation=(?P<operation>[A-Za-z0-9_-]+) definition=(?P<definition>\S+)"
)

OperationKey = tuple[str, str]
"""An operation id and the definition it ran, which together name one timed operation."""


class TimingStage(StrEnum):
    """The committed transitions the application observes."""

    ADMITTED = "admitted"
    RUNNING = "running"
    SETTLED = "settled"


@dataclass(frozen=True, slots=True)
class TimingEvent:
    """One timing line: a stage of one operation at one epoch millisecond."""

    stage: TimingStage
    epoch_ms: int
    operation: str
    definition: str

    def line(self) -> str:
        """The event in the producer's own words, which is all a collected log holds."""
        return (
            f"operation timing stage={self.stage.value} epoch_ms={self.epoch_ms}"
            f" operation={self.operation} definition={self.definition}"
        )


@dataclass(frozen=True, slots=True)
class OperationTiming:
    """The stages one operation was seen at and the durations they allow."""

    admitted_ms: int | None = None
    running_ms: int | None = None
    settled_ms: int | None = None
    duplicates: int = 0
    """Stage lines beyond the first of a stage; the earliest epoch is the one kept."""

    @property
    def queue_ms(self) -> int | None:
        """Admitted to running."""
        return _between(self.admitted_ms, self.running_ms)

    @property
    def run_ms(self) -> int | None:
        """Running to settled."""
        return _between(self.running_ms, self.settled_ms)

    @property
    def total_ms(self) -> int | None:
        """Admitted to settled."""
        return _between(self.admitted_ms, self.settled_ms)


@dataclass(frozen=True, slots=True)
class RowTiming:
    """What a set of operations took: how many, how long in all, and how many could not be timed."""

    operations: int = 0
    total_ms: int = 0
    """The sum of ``total_ms`` over the operations that have one."""
    incomplete: int = 0
    """Operations with no complete, ordered admitted-to-settled timing."""
    duplicates: int = 0


@dataclass(frozen=True, slots=True)
class DefinitionTiming:
    """The operations of one definition and the sum of their total durations."""

    count: int = 0
    total_ms: int = 0


@dataclass(frozen=True, slots=True)
class TimingRecord:
    """One sidecar object: a row key, its timing and the per-definition breakdown.

    A row key part is ``None`` when the timing is the whole case's rather than one return's.
    """

    persona: str
    horizon: int
    timing: RowTiming
    by_definition: Mapping[str, DefinitionTiming] = field(default_factory=dict)
    modelo: str | None = None
    year: int | None = None
    period: str | None = None

    def to_json(self) -> str:
        """The record as one JSON line."""
        document = {
            "persona": self.persona,
            "modelo": self.modelo,
            "year": self.year,
            "period": self.period,
            "horizon": self.horizon,
            "operations": self.timing.operations,
            "total_ms": self.timing.total_ms,
            "incomplete": self.timing.incomplete,
            "duplicates": self.timing.duplicates,
            "by_definition": {
                name: {"count": item.count, "total_ms": item.total_ms}
                for name, item in sorted(self.by_definition.items())
            },
        }
        return json.dumps(document, ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class CaseTiming:
    """What collecting a case's timing found: the joined operations and the findings to report."""

    timings: Mapping[OperationKey, OperationTiming] = field(default_factory=dict)
    findings: tuple[str, ...] = ()


def _between(start: int | None, end: int | None) -> int | None:
    if start is None or end is None or end < start:
        return None
    return end - start


def parse_timing_lines(text: str) -> tuple[TimingEvent, ...]:
    """The timing events in ``text``; every other line is ignored and none of its text is kept."""
    events: list[TimingEvent] = []
    for line in text.splitlines():
        found = _LINE.search(line)
        if found is None:
            continue
        events.append(
            TimingEvent(TimingStage(found["stage"]), int(found["epoch"]), found["operation"], found["definition"])
        )
    return tuple(events)


def join_operations(events: Iterable[TimingEvent]) -> Mapping[OperationKey, OperationTiming]:
    """One timing per (operation, definition); a repeated stage keeps its earliest epoch and counts as a duplicate."""
    seen: dict[OperationKey, dict[TimingStage, int]] = defaultdict(dict)
    repeats: dict[OperationKey, int] = defaultdict(int)
    for event in events:
        key = (event.operation, event.definition)
        stages = seen[key]
        if event.stage in stages:
            repeats[key] += 1
            stages[event.stage] = min(stages[event.stage], event.epoch_ms)
        else:
            stages[event.stage] = event.epoch_ms
    return {
        key: OperationTiming(
            stages.get(TimingStage.ADMITTED),
            stages.get(TimingStage.RUNNING),
            stages.get(TimingStage.SETTLED),
            repeats[key],
        )
        for key, stages in seen.items()
    }


def _selected(
    timings: Mapping[OperationKey, OperationTiming], operation_ids: Collection[str] | None
) -> tuple[Mapping[OperationKey, OperationTiming], int]:
    """The timings of ``operation_ids`` (all when ``None``) and how many requested ids the log never named."""
    if operation_ids is None:
        return timings, 0
    wanted = set(operation_ids)
    chosen = {key: timing for key, timing in timings.items() if key[0] in wanted}
    return chosen, len(wanted - {key[0] for key in chosen})


def summarize(
    timings: Mapping[OperationKey, OperationTiming], operation_ids: Collection[str] | None = None
) -> RowTiming:
    """How many operations ``operation_ids`` name (all when ``None``), their summed total and how many are incomplete.

    A requested id the log never named is an operation without a timing, so it is counted as incomplete.
    """
    chosen, unseen = _selected(timings, operation_ids)
    totals = [timing.total_ms for timing in chosen.values()]
    return RowTiming(
        operations=len(chosen) + unseen,
        total_ms=sum(total for total in totals if total is not None),
        incomplete=sum(1 for total in totals if total is None) + unseen,
        duplicates=sum(timing.duplicates for timing in chosen.values()),
    )


def definition_breakdown(
    timings: Mapping[OperationKey, OperationTiming], operation_ids: Collection[str] | None = None
) -> Mapping[str, DefinitionTiming]:
    """The operation count and summed total duration of each definition among ``operation_ids`` (all when ``None``)."""
    chosen, _unseen = _selected(timings, operation_ids)
    counts: dict[str, int] = defaultdict(int)
    sums: dict[str, int] = defaultdict(int)
    for (_operation, definition), timing in chosen.items():
        counts[definition] += 1
        sums[definition] += timing.total_ms or 0
    return {definition: DefinitionTiming(counts[definition], sums[definition]) for definition in counts}


def read_timing_lines(path: Path) -> str | None:
    """The text of the log at ``path``, or ``None`` when it is missing, mid-rotation or unreadable."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def collect_case_timing(storage_root: Path, case_log_dir: Path, operation_ids: Collection[str] | None) -> CaseTiming:
    """Copy the timing lines of a case's storage log into ``case_log_dir`` and join them by operation.

    ``storage_root`` is the case's reported storage root, whose ``logs/cadrumo.log`` (and a rotated
    ``cadrumo.log.1``, if present) are read. The collected file holds the parsed timing events and no other text.
    An absent log is a finding, never an error, and never changes a stage result. ``operation_ids`` only limits
    what the returned findings count: the collected file always holds every timing line, since a case's root is
    its own.
    """
    texts = [read_timing_lines(storage_root / relative) for relative in (_ROTATED_RELATIVE, _LOG_RELATIVE)]
    present = [text for text in texts if text is not None]
    if not present:
        return CaseTiming(findings=("timing: no cadrumo.log under the case storage root",))
    events = parse_timing_lines("\n".join(present))
    findings: list[str] = []
    try:
        case_log_dir.mkdir(parents=True, exist_ok=True)
        (case_log_dir / COLLECTED_LOG).write_text(
            "".join(f"{event.line()}\n" for event in events), encoding="utf-8", newline="\n"
        )
    except OSError:
        findings.append("timing: the collected timing log could not be written")
    timings = join_operations(events)
    if not events:
        findings.append("timing: cadrumo.log holds no timing lines")
    elif operation_ids is not None:
        missing = summarize(timings, operation_ids).incomplete
        if missing:
            findings.append(f"timing: {missing} operation(s) have no complete timing in the log")
    return CaseTiming(timings, tuple(findings))


def case_record(
    persona: str, horizon: int, timings: Mapping[OperationKey, OperationTiming], operation_ids: Collection[str] | None
) -> TimingRecord:
    """The case-wide sidecar record: no modelo, year or period, since the operations are not attributed to one."""
    return TimingRecord(
        persona, horizon, summarize(timings, operation_ids), definition_breakdown(timings, operation_ids)
    )


def write_timing_records(path: Path, records: Sequence[TimingRecord]) -> None:
    """Append ``records`` to the sidecar at ``path`` as JSON lines; the sidecar is best effort and never raises."""
    if not records:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(record.to_json() + "\n")
    except OSError:
        return
