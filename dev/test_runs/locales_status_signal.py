"""Decode locale status observations while distinguishing unreadable or partial output."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Final

from dev._paths import UTF_8

from .pytest_transcript_syntax import _normalize_root_cause
from .signal_values import _is_json_object, _write_json_lines

_LOCALES_STATUS_SIGNAL: Final[str] = "locales-status"


_LOCALE_EXCEPTION_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:[|│]\s*)?(?:E\s+)?(?P<type>(?:[A-Za-z_][A-Za-z0-9_]*\.)*"
    r"[A-Z][A-Za-z0-9_]*(?:Error|Exception|Failure|Group|Interrupt|Exit))"
    r"(?::\s*(?P<message>.*))?$"
)


_LOCALE_ERROR_MESSAGE_LIMIT: Final[int] = 512


def _locale_failure_category(exception_type: str, message: str) -> str:
    """Classify a locale child failure into one actionable operational bucket."""
    haystack = f"{exception_type} {message}".casefold()
    if "authorityartifact" in haystack or "authority artifact" in haystack:
        return "authority_artifact"
    if _contains_failure_token(haystack, ("modulenotfound", "importerror", "no module named", "cannot import")):
        return "import"
    if "syntaxerror" in haystack or "indentationerror" in haystack:
        return "source_syntax"
    if _contains_failure_token(haystack, ("spellingtool", "hunspell", "spylls", "dictionary")):
        return "locale_dependency"
    if _contains_failure_token(haystack, ("filenotfound", "permissionerror", "notadirectory", "oserror", "ioerror")):
        return "filesystem"
    if _contains_failure_token(haystack, ("jsondecode", "json payload", "payload")):
        return "payload"
    return "child_process"


def _locale_traceback_error(lines: list[str], decode_error: str | None) -> dict[str, str]:
    """Extract one bounded exception identity while leaving the full log intact."""
    for index in range(len(lines) - 1, -1, -1):
        candidate = lines[index].strip().lstrip("|│").strip()
        match = _LOCALE_EXCEPTION_RE.fullmatch(candidate)
        if match is None:
            continue
        exception_type = match.group("type")
        message_parts = _locale_message_parts(match, lines[index + 1 :])
        message = _normalize_root_cause(" ".join(part for part in message_parts if part))
        if not message:
            message = f"locale status child terminated with {exception_type}"
        return {
            "category": _locale_failure_category(exception_type, message),
            "type": exception_type,
            "message": message[:_LOCALE_ERROR_MESSAGE_LIMIT],
        }

    if decode_error:
        message = _normalize_root_cause(decode_error)
        return {
            "category": "payload",
            "type": "JSONDecodeError",
            "message": message[:_LOCALE_ERROR_MESSAGE_LIMIT],
        }
    return {
        "category": "child_process",
        "type": "ChildProcessError",
        "message": "locale status child produced no structured JSON payload",
    }


class _LocalesStatusSignalProcessor:
    """Reduce the complete locale audit payload to a stable advisory envelope."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self._decoded: dict[str, object] | None = None
        self._decode_error: str | None = None

    def consume(self, line: str) -> None:
        self.lines.append(line)

    def _payload(self) -> dict[str, object] | None:
        if self._decoded is not None or self._decode_error is not None:
            return self._decoded
        try:
            decoded = _validated_locale_payload("".join(self.lines))
        except (json.JSONDecodeError, ValueError) as exc:
            # The child normally emits one compact JSON line.  A warning or
            # progress line before it must not turn an otherwise valid report
            # into an unavailable one, so retry each line after the strict
            # whole-stream parse.  Every candidate still goes through the
            # locale payload shape checks above.
            self._decode_error = str(exc)
            for line in reversed(self.lines):
                candidate = _locale_payload_candidate(line)
                if candidate is None:
                    continue
                self._decoded = candidate
                self._decode_error = None
                return candidate
            return None
        self._decoded = decoded
        return decoded

    def effective_exit_status(self, child_exit_status: int) -> int:
        """Normalize every unusable locale report to the operational-failure code."""
        if child_exit_status != 127 and self._payload() is None:
            return 7
        return child_exit_status

    def envelope(
        self,
        *,
        label: str,
        run_dir: Path,
        log_path: Path,
        exit_status: int,
        started: datetime,
        finished: datetime,
    ) -> dict[str, object]:
        decoded = self._payload()
        error: dict[str, str] | None = None
        if decoded is None:
            error = _locale_traceback_error(self.lines, self._decode_error)
            summary = {
                "inventory": {"available": False, "closed": False, "processor_failures": 1},
                "translation_backlog": {
                    "exact": False,
                    "unique_keys_to_translate": None,
                    "cells_to_translate": None,
                },
            }
            details = {
                "processor_error": f"{error['type']}: {error['message']}",
                "root_cause": error,
            }
            outcome = "unavailable"
            headline = f"Locale status unavailable: {error['category']} ({error['type']}); inspect the run log."
        else:
            summary = decoded["summary"]
            details = decoded["details"]
            assert isinstance(summary, dict)
            assert isinstance(details, dict)
            outcome = str(decoded["outcome"])
            headline = str(decoded.get("headline", "Locale status produced no headline."))
        report_path = run_dir / "artifacts" / "locale-status.json"
        backlog_path = run_dir / "artifacts" / "locale-backlog.jsonl"
        findings_path = run_dir / "artifacts" / "locale-findings.jsonl"
        report_path.write_text(
            json.dumps(
                {
                    "details": details,
                    "run_id": run_dir.name,
                    "schema_version": 1,
                    "summary": summary,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding=UTF_8,
            newline="\n",
        )
        _write_json_lines(backlog_path, details.get("backlog", []))
        _write_json_lines(findings_path, details.get("findings", []))
        blocking = label == "check-locales"
        classification, result = _locale_run_classification(exit_status, outcome, blocking)
        return {
            "classification": classification,
            "command": label,
            "duration_seconds": round((finished - started).total_seconds(), 3),
            "event": "run_finished",
            "exit_status": exit_status,
            "finished_at": finished.isoformat(),
            "headline": headline,
            "posture": "blocking" if blocking else "advisory",
            "result": result,
            "run_id": run_dir.name,
            "run_outputs": {
                "artifacts": str(run_dir / "artifacts"),
                "backlog": str(backlog_path),
                "findings": str(findings_path),
                "log": str(log_path),
                "metadata": str(run_dir / "run.json"),
                "report": str(report_path),
            },
            "schema_version": 1,
            "started_at": started.isoformat(),
            **({"error": error} if error is not None else {}),
            **_compact_locale_summary(summary),
        }


def _compact_locale_summary(summary: dict[str, object]) -> dict[str, object]:
    """Keep every locale domain visible without repeating non-actionable zeros."""
    projected = dict(summary)
    raw_domains = summary.get("domains")
    if not isinstance(raw_domains, list):
        return projected
    complete: list[str] = []
    work: list[dict[str, object]] = []
    always = {"domain", "state", "required_keys", "keys_to_translate", "to_translate"}
    for raw_row in raw_domains:
        _compact_locale_domain_row(raw_row, complete, work, always)
    projected["domains"] = {"work": work, "complete": sorted(complete)}
    return projected


def _contains_failure_token(haystack: str, tokens: tuple[str, ...]) -> bool:
    return any(token in haystack for token in tokens)


def _locale_message_parts(match: re.Match[str], continuations: list[str]) -> list[str]:
    """Read exception continuation lines up to the next traceback or exception boundary."""
    message_parts: list[str] = [match.group("message") or ""]
    for continuation in continuations:
        text = continuation.strip().lstrip("|│").strip()
        if not text:
            continue
        if (
            text.startswith(("Traceback (", "File ", "During handling of", "The above exception"))
            or _LOCALE_EXCEPTION_RE.fullmatch(text) is not None
        ):
            break
        message_parts.append(text)
    return message_parts


def _validated_locale_payload(raw: str) -> dict[str, object]:
    """Decode the exact locale payload shape, preserving the first refusal reason."""
    decoded = json.loads(raw)
    if not _is_json_object(decoded):
        raise ValueError("locale status payload is not a JSON object")
    if decoded.get("outcome") not in {"backlog", "complete"}:
        raise ValueError("locale status payload has an unknown outcome")
    if not isinstance(decoded.get("summary"), dict):
        raise ValueError("locale status payload has no summary object")
    if not isinstance(decoded.get("details"), dict):
        raise ValueError("locale status payload has no details object")
    return decoded


def _locale_payload_candidate(line: str) -> dict[str, object] | None:
    """Ignore one malformed candidate while retaining strict whole-stream failure evidence."""
    try:
        return _validated_locale_payload(line)
    except (json.JSONDecodeError, ValueError):
        return None


def _locale_run_classification(exit_status: int, outcome: str, blocking: bool) -> tuple[str, str]:
    """Keep unavailable, backlog and complete outcomes distinct for blocking and advisory commands."""
    if exit_status in {7, 127} or outcome == "unavailable":
        classification = "tool_failure"
        result = "unavailable"
    elif outcome == "backlog":
        classification = "blocking_findings" if blocking else "advisory_findings"
        result = "failed" if blocking else "backlog"
    else:
        classification = "clean"
        result = "passed" if blocking else "complete"
    return classification, result


def _compact_locale_domain_row(
    raw_row: object, complete: list[str], work: list[dict[str, object]], always: set[str]
) -> None:
    """Compact locale domain row."""
    if not isinstance(raw_row, dict):
        return
    if raw_row.get("state") == "complete":
        complete.append(str(raw_row.get("domain", "unassigned")))
        return
    row = {str(key): value for key, value in raw_row.items() if key in always or (value is not None and value != 0)}
    by_locale = row.get("to_translate_by_locale")
    if isinstance(by_locale, dict) and not any(int(value) for value in by_locale.values()):
        row.pop("to_translate_by_locale")
    work.append(row)
