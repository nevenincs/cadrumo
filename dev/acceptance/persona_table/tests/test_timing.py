"""The timing sidecar reads only the application's timing lines and never turns an unknown into a zero."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..cli_column.case import CaseSpec, record_case_timing
from ..timing import (
    COLLECTED_LOG,
    TIMING_FILE,
    DefinitionTiming,
    OperationTiming,
    RowTiming,
    TimingEvent,
    TimingRecord,
    TimingStage,
    case_record,
    collect_case_timing,
    definition_breakdown,
    join_operations,
    parse_timing_lines,
    read_timing_lines,
    summarize,
    write_timing_records,
)

_YEAR = 7

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ONE = "1" * 64
_TWO = "2" * 64
_DEFINITION_A = "modelo.calculation.run"
_DEFINITION_B = "ledger.entry.add"
_STAMP = "".join(["20", "26", "-11-15 10:00:00,00"])
_PREFIX = _STAMP + "0 [INFO] cadrumo.application.operations.lifecycle_timing: "
_SUFFIX = " | {}"
_PRIVATE = "private-canary-subject"


def _line(stage: str, epoch: int, operation: str, definition: str) -> str:
    """A timing line as the application formats it: the producer's message inside the file sink's layout."""
    message = f"operation timing stage={stage} epoch_ms={epoch} operation={operation} definition={definition}"
    return f"{_PREFIX}{message}{_SUFFIX}"


def _log(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def test_a_timing_line_in_the_file_sinks_layout_is_parsed() -> None:
    events = parse_timing_lines(_line("running", 1_700_000_000_123, _ONE, _DEFINITION_A))

    assert events == (TimingEvent(TimingStage.RUNNING, 1_700_000_000_123, _ONE, _DEFINITION_A),)


def test_a_log_with_other_lines_yields_only_the_timing_events() -> None:
    text = _log(
        f"{_PREFIX}starting up for {_PRIVATE}{_SUFFIX}",
        _line("admitted", 10, _ONE, _DEFINITION_A),
        f"{_STAMP}1 [ERROR] cadrumo.x: Traceback with {_PRIVATE}{_SUFFIX}",
        "operation timing stage=bogus epoch_ms=11 operation=abc definition=d",
        "operation timing stage=settled epoch_ms=notanumber operation=abc definition=d",
        _line("settled", 25, _ONE, _DEFINITION_A),
    )

    events = parse_timing_lines(text)

    assert [event.stage for event in events] == [TimingStage.ADMITTED, TimingStage.SETTLED]
    assert _PRIVATE not in repr(events)
    assert all(_PRIVATE not in event.line() for event in events)


def test_the_collected_event_line_is_the_producers_message_and_nothing_else() -> None:
    event = TimingEvent(TimingStage.ADMITTED, 5, _ONE, _DEFINITION_A)

    assert event.line() == f"operation timing stage=admitted epoch_ms=5 operation={_ONE} definition={_DEFINITION_A}"
    assert parse_timing_lines(event.line()) == (event,)


def test_a_complete_operation_has_a_queue_a_run_and_a_total() -> None:
    timings = join_operations(
        parse_timing_lines(
            _log(
                _line("admitted", 100, _ONE, _DEFINITION_A),
                _line("running", 130, _ONE, _DEFINITION_A),
                _line("settled", 200, _ONE, _DEFINITION_A),
            )
        )
    )

    timing = timings[(_ONE, _DEFINITION_A)]

    assert (timing.queue_ms, timing.run_ms, timing.total_ms, timing.duplicates) == (30, 70, 100, 0)


def test_a_missing_stage_leaves_its_durations_unknown_not_zero() -> None:
    timings = join_operations(
        parse_timing_lines(
            _log(_line("admitted", 100, _ONE, _DEFINITION_A), _line("settled", 160, _ONE, _DEFINITION_A))
        )
    )

    timing = timings[(_ONE, _DEFINITION_A)]

    assert timing.queue_ms is None
    assert timing.run_ms is None
    assert timing.total_ms == 60
    only_running = join_operations([TimingEvent(TimingStage.RUNNING, 5, _TWO, _DEFINITION_A)])[(_TWO, _DEFINITION_A)]
    assert (only_running.queue_ms, only_running.run_ms, only_running.total_ms) == (None, None, None)


def test_stages_out_of_order_are_unknown_and_equal_stages_are_a_true_zero() -> None:
    reversed_order = OperationTiming(admitted_ms=200, running_ms=100, settled_ms=150)
    instant = OperationTiming(admitted_ms=100, running_ms=100, settled_ms=100)

    assert (reversed_order.queue_ms, reversed_order.run_ms, reversed_order.total_ms) == (None, 50, None)
    assert (instant.queue_ms, instant.run_ms, instant.total_ms) == (0, 0, 0)


def test_a_repeated_stage_keeps_the_earliest_epoch_and_is_counted() -> None:
    timings = join_operations(
        parse_timing_lines(
            _log(
                _line("admitted", 100, _ONE, _DEFINITION_A),
                _line("settled", 300, _ONE, _DEFINITION_A),
                _line("settled", 250, _ONE, _DEFINITION_A),
                _line("settled", 400, _ONE, _DEFINITION_A),
            )
        )
    )

    timing = timings[(_ONE, _DEFINITION_A)]

    assert timing.settled_ms == 250
    assert timing.total_ms == 150
    assert timing.duplicates == 2


def test_operations_are_joined_by_operation_and_definition() -> None:
    timings = join_operations(
        parse_timing_lines(
            _log(
                _line("admitted", 100, _ONE, _DEFINITION_A),
                _line("admitted", 105, _TWO, _DEFINITION_B),
                _line("running", 110, _ONE, _DEFINITION_A),
                _line("settled", 190, _TWO, _DEFINITION_B),
                _line("settled", 160, _ONE, _DEFINITION_A),
            )
        )
    )

    assert set(timings) == {(_ONE, _DEFINITION_A), (_TWO, _DEFINITION_B)}
    assert timings[(_ONE, _DEFINITION_A)].total_ms == 60
    assert timings[(_TWO, _DEFINITION_B)].total_ms == 85
    assert timings[(_TWO, _DEFINITION_B)].running_ms is None


def _two_operations() -> dict[tuple[str, str], OperationTiming]:
    return {
        (_ONE, _DEFINITION_A): OperationTiming(100, 110, 160),
        (_TWO, _DEFINITION_B): OperationTiming(105, None, 190),
        ("3" * 64, _DEFINITION_B): OperationTiming(200, None, None),
    }


def test_a_summary_counts_operations_sums_the_totals_and_counts_the_incomplete() -> None:
    summary = summarize(_two_operations())

    assert summary == RowTiming(operations=3, total_ms=60 + 85, incomplete=1, duplicates=0)


def test_a_summary_of_chosen_operations_counts_a_requested_id_the_log_never_named_as_incomplete() -> None:
    summary = summarize(_two_operations(), [_ONE, "9" * 64])

    assert summary == RowTiming(operations=2, total_ms=60, incomplete=1, duplicates=0)


def test_a_summary_of_nothing_is_empty() -> None:
    assert summarize({}) == RowTiming(operations=0, total_ms=0, incomplete=0, duplicates=0)
    assert summarize(_two_operations(), []) == RowTiming()


def test_a_summary_adds_the_duplicates_of_the_chosen_operations() -> None:
    timings = {
        (_ONE, _DEFINITION_A): OperationTiming(1, 2, 3, duplicates=2),
        (_TWO, _DEFINITION_A): OperationTiming(duplicates=1),
    }

    assert summarize(timings).duplicates == 3
    assert summarize(timings, [_ONE]).duplicates == 2


def test_the_breakdown_is_per_definition_and_skips_unknown_totals_in_the_sum() -> None:
    breakdown = definition_breakdown(_two_operations())

    assert breakdown == {_DEFINITION_A: DefinitionTiming(1, 60), _DEFINITION_B: DefinitionTiming(2, 85)}
    assert definition_breakdown(_two_operations(), [_TWO]) == {_DEFINITION_B: DefinitionTiming(1, 85)}


def test_a_sidecar_record_is_one_json_object_per_row_key_with_a_breakdown() -> None:
    record = TimingRecord(
        persona="autonomo-alta-reciente",
        horizon=_YEAR + 1,
        timing=RowTiming(operations=2, total_ms=145, incomplete=1, duplicates=3),
        by_definition={_DEFINITION_B: DefinitionTiming(1, 85), _DEFINITION_A: DefinitionTiming(1, 60)},
        modelo="303",
        year=_YEAR,
        period="1T",
    )

    document = json.loads(record.to_json())

    assert document == {
        "persona": "autonomo-alta-reciente",
        "modelo": "303",
        "year": _YEAR,
        "period": "1T",
        "horizon": _YEAR + 1,
        "operations": 2,
        "total_ms": 145,
        "incomplete": 1,
        "duplicates": 3,
        "by_definition": {
            _DEFINITION_A: {"count": 1, "total_ms": 60},
            _DEFINITION_B: {"count": 1, "total_ms": 85},
        },
    }
    assert "\n" not in record.to_json()


def test_a_case_record_has_no_row_key_parts_and_the_cases_totals() -> None:
    record = case_record("p", _YEAR + 1, _two_operations(), None)

    document = json.loads(record.to_json())

    assert (document["modelo"], document["year"], document["period"]) == (None, None, None)
    assert (document["operations"], document["total_ms"], document["incomplete"]) == (3, 145, 1)


def test_the_sidecar_is_appended_as_json_lines(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "timing.jsonl"
    first = case_record("p", _YEAR + 1, _two_operations(), [_ONE])
    second = case_record("q", _YEAR, {}, None)

    write_timing_records(path, [first])
    write_timing_records(path, [second])

    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["persona"] for line in lines] == ["p", "q"]


def test_a_missing_or_unreadable_log_reads_as_none(tmp_path: Path) -> None:
    assert read_timing_lines(tmp_path / "absent.log") is None
    assert read_timing_lines(tmp_path) is None


def _storage_with_log(root: Path, current: str, rotated: str | None = None) -> Path:
    logs = root / "logs"
    logs.mkdir(parents=True)
    (logs / "cadrumo.log").write_text(current, encoding="utf-8")
    if rotated is not None:
        (logs / "cadrumo.log.1").write_text(rotated, encoding="utf-8")
    return root


def test_collection_keeps_only_timing_lines_from_the_log_and_its_rotation(tmp_path: Path) -> None:
    storage = _storage_with_log(
        tmp_path / "storage",
        _log(f"{_PREFIX}note {_PRIVATE}{_SUFFIX}", _line("settled", 160, _ONE, _DEFINITION_A)),
        _log(_line("admitted", 100, _ONE, _DEFINITION_A), f"{_PREFIX}older {_PRIVATE}{_SUFFIX}"),
    )
    case_dir = tmp_path / "case"

    collected = collect_case_timing(storage, case_dir, [_ONE])

    text = (case_dir / COLLECTED_LOG).read_text(encoding="utf-8")
    assert _PRIVATE not in text
    assert len(text.splitlines()) == 2
    assert collected.timings[(_ONE, _DEFINITION_A)].total_ms == 60
    assert collected.findings == ()


def test_collection_reports_a_missing_log_as_a_finding_without_failing(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()

    collected = collect_case_timing(storage, tmp_path / "case", [_ONE])

    assert collected.timings == {}
    assert len(collected.findings) == 1
    assert "no cadrumo.log" in collected.findings[0]
    assert not (tmp_path / "case" / COLLECTED_LOG).exists()


def test_collection_reports_a_log_without_timing_lines_and_ids_the_log_never_named(tmp_path: Path) -> None:
    empty = _storage_with_log(tmp_path / "empty", _log(f"{_PREFIX}note{_SUFFIX}"))
    partial = _storage_with_log(tmp_path / "partial", _log(_line("admitted", 1, _ONE, _DEFINITION_A)))

    none_found = collect_case_timing(empty, tmp_path / "case-empty", None)
    unnamed = collect_case_timing(partial, tmp_path / "case-partial", [_ONE, _TWO])

    assert none_found.findings == ("timing: cadrumo.log holds no timing lines",)
    assert unnamed.findings == ("timing: 2 operation(s) have no complete timing in the log",)


def _spec(tmp_path: Path) -> CaseSpec:
    return CaseSpec("t", "autonomo-alta-reciente", _YEAR + 1, tmp_path, tmp_path)


def test_a_case_writes_its_collected_log_and_one_sidecar_record(tmp_path: Path) -> None:
    storage = _storage_with_log(
        tmp_path / "storage",
        _log(_line("admitted", 100, _ONE, _DEFINITION_A), _line("settled", 160, _ONE, _DEFINITION_A)),
    )
    case_dir = tmp_path / "case"

    findings = record_case_timing(_spec(tmp_path), storage, case_dir)

    assert findings == ()
    assert (case_dir / COLLECTED_LOG).is_file()
    (line,) = (case_dir / TIMING_FILE).read_text(encoding="utf-8").splitlines()
    document = json.loads(line)
    assert (document["persona"], document["horizon"], document["operations"], document["total_ms"]) == (
        "autonomo-alta-reciente",
        _YEAR + 1,
        1,
        60,
    )


def test_a_case_without_a_log_reports_it_and_still_writes_no_failure(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()

    findings = record_case_timing(_spec(tmp_path), storage, tmp_path / "case")

    assert len(findings) == 1
    assert json.loads((tmp_path / "case" / TIMING_FILE).read_text(encoding="utf-8"))["operations"] == 0
