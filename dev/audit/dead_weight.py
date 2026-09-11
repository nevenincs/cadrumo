"""Combine duplication and dead-code observations into one advisory signal."""

from __future__ import annotations

import json

from dev._paths import REPO_ROOT
from dev.exit_codes import ADVISORY_BROKEN, OK

from .dead_code import DeadCodeOutcome, run_dead_code_scan
from .duplication import DuplicationOutcome, run_duplication_scan


def main() -> int:
    """Run both dead-weight scanners and emit their single structured result."""
    duplication = run_duplication_scan(REPO_ROOT)
    dead_code = run_dead_code_scan(REPO_ROOT)

    unavailable = (
        duplication.outcome is DuplicationOutcome.UNAVAILABLE
        or dead_code.outcome is DeadCodeOutcome.ERROR
    )
    has_findings = (
        duplication.outcome is DuplicationOutcome.CLONES
        or dead_code.outcome is DeadCodeOutcome.FINDINGS
    )
    outcome = "unavailable" if unavailable else "findings" if has_findings else "clean"
    duplication_available = duplication.outcome is not DuplicationOutcome.UNAVAILABLE
    dead_code_available = dead_code.outcome is not DeadCodeOutcome.ERROR
    duplication_rate = round(float(duplication.duplicated_pct or 0) / 100, 8)
    dead_code_rate = (
        round(len(dead_code.findings) / dead_code.modules_offered, 8)
        if dead_code.modules_offered
        else 0.0
    )
    headline = (
        "dead weight: "
        f"{duplication.clone_count} duplication clone(s); "
        f"{len(dead_code.findings)} dead-code finding(s)"
    )
    if unavailable:
        headline += "; one or more scanners unavailable"
    elif has_findings:
        headline += " (advisory)"
    else:
        headline += " across both scanners"

    print(
        json.dumps(
            {
                "outcome": outcome,
                "headline": headline,
                "summary": {
                    "duplication": {
                        "result": (
                            "unavailable"
                            if duplication.outcome is DuplicationOutcome.UNAVAILABLE
                            else "findings"
                            if duplication.outcome is DuplicationOutcome.CLONES
                            else "clean"
                        ),
                        "available": duplication_available,
                        "findings_total": duplication.clone_count,
                        "scanned_total": duplication.files_analyzed,
                        "rate": duplication_rate,
                    },
                    "dead_code": {
                        "result": (
                            "unavailable"
                            if dead_code.outcome is DeadCodeOutcome.ERROR
                            else "findings"
                            if dead_code.outcome is DeadCodeOutcome.FINDINGS
                            else "clean"
                        ),
                        "available": dead_code_available,
                        "findings_total": len(dead_code.findings),
                        "scanned_total": dead_code.modules_offered,
                        "rate": dead_code_rate,
                        "high_confidence": dead_code.count_by_confidence.get("high (>=80%)", 0),
                        "moderate_confidence": dead_code.count_by_confidence.get(
                            "moderate (<80%)", 0
                        ),
                    },
                },
                "details": {
                    "duplication": {
                        "outcome": duplication.outcome.value,
                        "reason": duplication.reason,
                        "clones": [group.render() for group in duplication.groups],
                    },
                    "dead_code": {
                        "outcome": dead_code.outcome.value,
                        "reason": dead_code.reason,
                        "findings": [
                            {
                                "path": finding.path,
                                "line": finding.line,
                                "message": finding.message,
                                "confidence": finding.confidence,
                            }
                            for finding in dead_code.findings
                        ],
                    },
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return ADVISORY_BROKEN if unavailable else OK


if __name__ == "__main__":
    raise SystemExit(main())
