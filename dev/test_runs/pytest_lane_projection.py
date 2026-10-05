"""Classify accumulated lane evidence without conflating blocked, incomplete and failed runs."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .signal_values import _HOTSPOT_LIMIT, _top


def _lane_envelope(name: str, data: dict[str, object] | None) -> dict[str, object]:
    """Project a missing, blocked or completed lane without conflating their outcomes."""
    if data is None:
        return {"name": name, "result": "not_run"}
    if data["skipped"]:
        blocked_by = data["blocked_by"]
        assert isinstance(blocked_by, tuple)
        return {
            "blocked_by": list(blocked_by),
            "classification": "blocked_by_preflight",
            "kind": data["kind"],
            "name": name,
            "reason": data["skip_reason"],
            "result": "blocked",
        }
    evidence = _lane_evidence(data)
    phase = _lane_phase(
        evidence.internal_error,
        evidence.summaryless_failure,
        evidence.kind,
        evidence.collection_failure,
        evidence.load_failure,
    )
    classification = _lane_classification(
        evidence.internal_error,
        evidence.summaryless_failure,
        evidence.kind,
        evidence.collection_failure,
        evidence.load_failure,
        data,
    )
    return {
        "name": name,
        "result": "passed" if data["status"] == 0 else "failed",
        "classification": classification,
        "exit_status": data["status"],
        "duration_seconds": data["seconds"],
        "kind": evidence.kind,
        "role": data["role"],
        "summary": dict(sorted(evidence.counts.items())),
        "failed_test_identities": len(evidence.failed_nodes),
        "top_affected_files": _top(evidence.files),
        "root_causes": [
            {"count": count, "exception": cause[0], "message": cause[1], "phase": phase}
            for cause, count in sorted(evidence.root_causes.items(), key=lambda item: (-item[1], item[0]))[
                :_HOTSPOT_LIMIT
            ]
        ],
    }


def _lane_phase(
    internal_error: bool, summaryless_failure: bool, kind: str, collection_failure: bool, load_failure: bool
) -> str:
    """Keep tool, collection, load and execution phase precedence."""
    return (
        "tool"
        if internal_error or (summaryless_failure and kind not in {"collection", "load"})
        else "collection"
        if collection_failure
        else "load"
        if load_failure
        else "execution"
    )


def _lane_classification(
    internal_error: bool,
    summaryless_failure: bool,
    kind: str,
    collection_failure: bool,
    load_failure: bool,
    data: dict[str, object],
) -> str:
    """Keep failure class precedence separate from the lane phase."""
    return (
        "tool_failure"
        if internal_error or (summaryless_failure and kind != "collection" and (not load_failure))
        else "collection_failure"
        if collection_failure
        else "load_failure"
        if load_failure
        else "clean"
        if data["status"] == 0
        else "blocking_findings"
    )


def _lane_collection_failure(internal_error: bool, summaryless_failure: bool, kind: str, counts: Counter[str]) -> bool:
    """Require collection-only errors or an explicit failed collection lane."""
    return bool(
        not internal_error
        and (
            (summaryless_failure and kind == "collection")
            or (counts["error"] and (not (counts["passed"] or counts["failed"])))
        )
    )


def _summaryless_collection_failure(data: dict[str, object]) -> bool:
    """Recognize the original summaryless collection failed predicate."""
    return data["status"] not in (None, 0) and (not data["counts"]) and (data["kind"] == "collection")


def _summaryless_tool_failure(data: dict[str, object]) -> bool:
    """Recognize the original summaryless tool failed predicate."""
    return (
        data["status"] not in (None, 0)
        and (not data["counts"])
        and (data["kind"] != "collection")
        and (not (data["kind"] == "load" and bool(data["root_causes"])))
    )


def _summaryless_load_failure(data: dict[str, object]) -> bool:
    """Recognize the original summaryless load failed predicate."""
    return (
        data["status"] not in (None, 0)
        and (not data["counts"])
        and (data["kind"] == "load")
        and bool(data["root_causes"])
    )


def _lane_tool_failed(data: dict[str, object]) -> bool:
    """Count an internal failure even when the lane produced terminal counts."""
    return bool(data["internal_error"]) or (
        data["status"] not in (None, 0)
        and (not data["counts"])
        and (data["kind"] != "collection")
        and (not (data["kind"] == "load" and bool(data["root_causes"])))
    )


def _only_collection_errors(errors: int, passed: int, failures: int) -> bool:
    return bool(errors and not (passed or failures))


@dataclass(frozen=True)
class _LaneEvidence:
    """Typed terminal lane facts and their failure predicates."""

    counts: Counter[str]
    failed_nodes: set[tuple[str, str]]
    root_causes: Counter[tuple[str, str]]
    files: Counter[str]
    internal_error: bool
    kind: str
    summaryless_failure: bool
    collection_failure: bool
    load_failure: bool


def _lane_evidence(data: dict[str, object]) -> _LaneEvidence:
    """Narrow the accumulated state before rendering its terminal lane evidence."""
    counts = data["counts"]
    failed_nodes = data["failed_nodes"]
    root_causes = data["root_causes"]
    assert isinstance(counts, Counter)
    assert isinstance(failed_nodes, set)
    assert isinstance(root_causes, Counter)
    files = Counter(file for _, file in failed_nodes)
    internal_error = bool(data["internal_error"])
    kind = str(data["kind"])
    summaryless_failure = data["status"] not in (None, 0) and not counts
    collection_failure = _lane_collection_failure(internal_error, summaryless_failure, kind, counts)
    load_failure = not internal_error and summaryless_failure and kind == "load" and bool(root_causes)
    return _LaneEvidence(
        counts,
        failed_nodes,
        root_causes,
        files,
        internal_error,
        kind,
        summaryless_failure,
        collection_failure,
        load_failure,
    )
