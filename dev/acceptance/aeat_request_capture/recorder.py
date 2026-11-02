"""Count observed requests per flow, holding only redacted targets and closed verdicts."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final
from urllib.parse import quote, urlsplit

from cadrumo.domain.calculations.registry.remote_state_guard import RemoteStateGuardPolicy

from .guard_verdicts import ALLOW, guard_verdict
from .redaction import redact_target

SCHEMA: Final = "aeat-request-capture/1"
OUTSIDE_ANY_FLOW: Final = "(outside-any-flow)"
_METHOD_SHAPE: Final = re.compile(r"[A-Z]{1,16}")
_READ_METHODS: Final = frozenset({"GET", "HEAD"})


class CaptureLeakError(RuntimeError):
    """The report held a value it must never hold, so it was not written."""


@dataclass
class _Observed:
    count: int = 0
    placeholders: Counter[str] = field(default_factory=Counter)
    verdicts: defaultdict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    flow_allowed: int = 0
    flow_refused: int = 0


@dataclass
class _Flow:
    policy_ids: tuple[str, ...]
    outcome: str = "not-run"
    observed: dict[tuple[str, str, str, str], _Observed] = field(default_factory=dict)
    notification_detail_requests: int = 0


class CaptureRecorder:
    """Reduce each request to its aggregate at the moment it is observed."""

    def __init__(
        self,
        policies: Iterable[RemoteStateGuardPolicy],
        *,
        notification_detail_paths: Iterable[str] = (),
    ) -> None:
        """Bind the policies every request is evaluated against and the paths that must stay untouched."""
        self._policies = tuple(policies)
        self._detail_paths = frozenset(notification_detail_paths)
        self._flows: dict[str, _Flow] = {}
        self._current = OUTSIDE_ANY_FLOW

    @property
    def notification_detail_requests(self) -> int:
        """Return how many requests, in any flow, reached for an unread notification's detail."""
        return sum(flow.notification_detail_requests for flow in self._flows.values())

    def register_flow(self, flow_id: str, policy_ids: Sequence[str]) -> None:
        """Declare a planned flow, so one that never ran still appears in the report."""
        self._flows[flow_id] = _Flow(tuple(policy_ids))

    def begin_flow(self, flow_id: str) -> None:
        """Attribute the requests observed from now on to ``flow_id``."""
        self._current = flow_id

    def end_flow(self, flow_id: str, outcome: str) -> None:
        """Record how ``flow_id`` ended and stop attributing requests to it."""
        self._flows[flow_id].outcome = outcome
        self._current = OUTSIDE_ANY_FLOW

    def set_outcome(self, flow_id: str, outcome: str) -> None:
        """Record why a planned flow did not run."""
        self._flows[flow_id].outcome = outcome

    def is_notification_detail(self, url: str) -> bool:
        """Say whether ``url`` is the detail endpoint whose use would serve an unread notification."""
        try:
            return urlsplit(url).path in self._detail_paths
        except ValueError:
            return False

    def observe(self, source: str, method: str, url: str) -> None:
        """Evaluate one request against every policy, then keep only its redacted aggregate."""
        normalized = method.upper()
        guard_method = normalized if _METHOD_SHAPE.fullmatch(normalized) else "OTHER"
        target = redact_target(url)
        flow = self._flows.setdefault(self._current, _Flow(()))
        entry = flow.observed.setdefault((source, guard_method, target.host, target.path), _Observed())
        entry.count += 1
        entry.placeholders.update(target.placeholders)
        allowed_by_flow = False
        for policy in self._policies:
            verdict = guard_verdict(policy, guard_method, url)
            entry.verdicts[policy.id][verdict] += 1
            allowed_by_flow = allowed_by_flow or (verdict == ALLOW and policy.id in flow.policy_ids)
        if allowed_by_flow:
            entry.flow_allowed += 1
        else:
            entry.flow_refused += 1
        if self.is_notification_detail(url):
            flow.notification_detail_requests += 1

    def report(self) -> dict[str, object]:
        """Return the deduplicated per-flow counts and the declarations they call for."""
        flows: list[dict[str, object]] = []
        declarations: list[dict[str, object]] = []
        for flow_id, flow in self._flows.items():
            requests: list[dict[str, object]] = []
            placeholders: Counter[str] = Counter()
            for (source, method, host, path), entry in sorted(flow.observed.items()):
                placeholders.update(entry.placeholders)
                requests.append(
                    {
                        "source": source,
                        "method": method,
                        "host": host,
                        "path": path,
                        "count": entry.count,
                        "placeholders": dict(sorted(entry.placeholders.items())),
                        "flow_policies": {"allow": entry.flow_allowed, "refuse": entry.flow_refused},
                        "verdicts": {
                            policy_id: dict(sorted(answers.items())) for policy_id, answers in entry.verdicts.items()
                        },
                    },
                )
                if entry.flow_refused:
                    declarations.append(
                        {
                            "flow": flow_id,
                            "source": source,
                            "method": method,
                            "host": host,
                            "path": path,
                            "refused_count": entry.flow_refused,
                            "write_shaped_method": method not in _READ_METHODS,
                            "refusals": {
                                policy_id: dict(sorted(entry.verdicts[policy_id].items()))
                                for policy_id in flow.policy_ids
                                if policy_id in entry.verdicts
                            },
                        },
                    )
            flows.append(
                {
                    "flow": flow_id,
                    "outcome": flow.outcome,
                    "policies": list(flow.policy_ids),
                    "request_total": sum(entry.count for entry in flow.observed.values()),
                    "placeholders": dict(sorted(placeholders.items())),
                    "notification_detail_requests": flow.notification_detail_requests,
                    "requests": requests,
                },
            )
        return {
            "schema": SCHEMA,
            "notification_detail_requests": self.notification_detail_requests,
            "flows": flows,
            "declarations_needed": declarations,
        }


def report_bytes(report: Mapping[str, object], *, forbidden_values: Iterable[str] = ()) -> bytes:
    """Serialize ``report``, refusing when a known private value appears in the result."""
    body = json.dumps(report, indent=2, sort_keys=True).encode("utf-8")
    folded = body.lower()
    for value in forbidden_values:
        stripped = value.strip()
        if stripped and any(
            variant.lower().encode("utf-8") in folded for variant in (stripped, quote(stripped, safe=""))
        ):
            raise CaptureLeakError("A configured private value reached the capture report; nothing was written")
    return body + b"\n"


def write_report(report: Mapping[str, object], path: Path, *, forbidden_values: Iterable[str] = ()) -> None:
    """Write the checked report bytes to ``path``."""
    body = report_bytes(report, forbidden_values=forbidden_values)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
