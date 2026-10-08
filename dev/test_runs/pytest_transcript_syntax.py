"""Read declared pytest and lane transcript syntax and normalize typed root-cause signatures."""

from __future__ import annotations

import json
import re
from typing import Final

from dev._paths import REPO_ROOT

from .signal_values import _is_json_object

_PYTEST_SUMMARY_RE: Final[re.Pattern[str]] = re.compile(
    r"^=+\s*(?P<summary>.+?)\s+in\s+(?P<duration>\d+(?:\.\d+)?)s"
    r"(?:\s+\(\d+:\d{2}:\d{2}\))?\s*=+$"
)


_PYTEST_COUNT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<count>\d+)\s+(?:tests?\s+)?(?P<outcome>collected|passed|failed|errors?|skipped|deselected|"
    r"xfailed|xpassed|warnings?)\b"
)


_TEST_IDENTITY_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:FAILED|ERROR) (?P<node>(?P<file>[^\s:]+\.py)(?:::[^\s]+)?)"
)


_ROOT_CAUSE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:E\s+)?(?P<type>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):\s*(?P<message>.+)$"
)


_REGISTRY_LOAD_FAILURE_RE: Final[re.Pattern[str]] = re.compile(
    r"^registry-runtime-load\s+status=failed\s+loadable=false\s+detail="
    r"(?P<type>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)):\s*(?P<message>.+)$"
)


_PYTEST_OUTCOME_KEYS: Final[dict[str, str]] = {
    "collected": "collected",
    "passed": "passed",
    "failed": "failed",
    "error": "error",
    "errors": "error",
    "skipped": "skipped",
    "deselected": "deselected",
    "xfailed": "xfailed",
    "xpassed": "xpassed",
    "warning": "warning",
    "warnings": "warning",
}


def _normalize_root_cause(message: str) -> str:
    """Remove checkout and run-specific identity from a root-cause signature."""
    normalized = message.replace(str(REPO_ROOT), "<repo>").replace(REPO_ROOT.as_posix(), "<repo>")
    normalized = re.sub(r"[\\/]\.logs[\\/]test-runs[\\/][^\\/\s]+[\\/][^\\/\s]+", "/.logs/test-runs/<run>", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _lane_marker(text: str) -> dict[str, object] | None:
    """Recognize only the three declared lane event kinds in valid JSON objects."""
    marker: dict[str, object] | None = None
    if text.startswith("{"):
        try:
            candidate = json.loads(text)
        except json.JSONDecodeError:
            candidate = None
        if _is_json_object(candidate) and candidate.get("event") in {
            "lane_started",
            "lane_finished",
            "lane_skipped",
        }:
            marker = candidate
    return marker
