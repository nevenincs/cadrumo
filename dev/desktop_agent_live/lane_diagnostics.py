"""Read sign-in failures and provider readiness from desktop diagnostics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import cast


def sign_in_failures(events: Iterable[Mapping[str, object]]) -> list[tuple[int, str]]:
    """Each failed sign-in the desktop's diagnostics record, by sequence, as ``code`` or ``code (reason)``."""
    return sorted(failure for event in events if (failure := _sign_in_failure(event)) is not None)


def _sign_in_failure(event: Mapping[str, object]) -> tuple[int, str] | None:
    """Read one login failure without retaining unrelated diagnostics."""
    result, failure = event.get("helperResult"), event.get("failure")
    if event.get("kind") != "helper_result" or not isinstance(result, Mapping) or not isinstance(failure, Mapping):
        return None
    result_fields = cast(Mapping[str, object], result)
    failure_fields = cast(Mapping[str, object], failure)
    if result_fields.get("command") != "config.login":
        return None
    code = str(failure_fields.get("code") or "unknown")
    reason = result_fields.get("reason") or result_fields.get("code") or failure_fields.get("reason")
    sequence = int(cast(str | int | float, event.get("sequence") or 0))
    return sequence, f"{code} ({reason})" if reason else code


def lane_problems(lane: Mapping[str, object]) -> list[str]:
    """What keeps a provider lane from serving a run, as the agent column judges it; empty when it is ready."""
    health = cast(Mapping[str, object], lane.get("health") or {})
    problems = [
        f"{facet} {health.get(facet)}"
        for facet in ("configured", "transport", "catalog")
        if health.get(facet) != "available"
    ]
    if health.get("authentication") not in ("authenticated", "not_applicable"):
        problems.append(f"authentication {health.get('authentication')}")
    selectable_problem = _selectable_problem(health)
    if selectable_problem is not None:
        problems.append(selectable_problem)
    if lane.get("executable") is not True:
        problems.append("not executable")
    if lane.get("model_source") != "declared" and not cast(Mapping[str, object], lane.get("catalog") or {}).get(
        "models"
    ):
        problems.append("no models")
    return problems


def _selectable_problem(health: Mapping[str, object]) -> str | None:
    """Describe the provider selection refusal, when present."""
    if health.get("selectable") is True:
        return None
    return "not selectable" + (
        f" ({', '.join(cast(Iterable[str], health['reasons']))})" if health.get("reasons") else ""
    )


def ready_lanes(catalog: Mapping[str, object]) -> tuple[list[str], dict[str, list[str]]]:
    """The ready lanes in the order the agent column offers them, and what each other lane lacks.

    The column groups lanes by provider in the order they were served, the
    API before the command-line app, and starts on the first ready one.
    """
    served = [
        cast(Mapping[str, object], lane)
        for lane in cast(Iterable[object], catalog.get("providers") or ())
        if isinstance(lane, Mapping)
    ]
    providers = list(dict.fromkeys(str(lane.get("provider_id")) for lane in served))
    ordered = sorted(
        served,
        key=lambda lane: (providers.index(str(lane.get("provider_id"))), lane.get("transport") == "cli"),
    )
    ready: list[str] = []
    missing: dict[str, list[str]] = {}
    for lane in ordered:
        name = f"{lane.get('provider_id')}/{lane.get('transport')}"
        problems = lane_problems(lane)
        if problems:
            missing[name] = problems
        else:
            ready.append(name)
    return ready, missing
