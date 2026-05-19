"""Filing schedule selection from registry profile predicates."""

from __future__ import annotations

from collections.abc import Mapping

from ._errors import RegistryValidationError
from ._schema import ModeloScheduleDefinition, ModeloRevision, ProfilePredicateDefinition

__all__ = [
    "applicable_filing_schedules",
    "evaluate_profile_conditions",
    "profile_condition_matches",
]


def applicable_filing_schedules(
    revision: ModeloRevision,
    profile_facts: Mapping[str, object] | object,
    *,
    period: str | None = None,
) -> tuple[ModeloScheduleDefinition, ...]:
    """Return filing schedules whose profile predicates match the supplied facts."""

    matched: list[ModeloScheduleDefinition] = []
    for schedule in revision.filing_schedules:
        if period is not None and period not in schedule.periods:
            continue
        if evaluate_profile_conditions(
            schedule.profile_conditions,
            profile_facts,
            mode=schedule.profile_condition_mode,
        ):
            matched.append(schedule)
    return tuple(matched)


def evaluate_profile_conditions(
    conditions: tuple[ProfilePredicateDefinition, ...],
    profile_facts: Mapping[str, object] | object,
    *,
    mode: str,
) -> tuple[str, ...] | None:
    if not conditions:
        return ()
    explanations: list[str] = []
    for condition in conditions:
        if profile_condition_matches(condition, profile_facts):
            explanations.append(condition.explanation)
            continue
        if mode == "all":
            return None
    if mode == "any" and not explanations:
        return None
    return tuple(explanations)


def profile_condition_matches(
    condition: ProfilePredicateDefinition,
    profile_facts: Mapping[str, object] | object,
) -> bool:
    observed = _resolve_profile_fact(profile_facts, condition.field)
    if condition.op == "equals":
        return observed == condition.value
    if condition.op == "not_equals":
        return observed != condition.value
    raise RegistryValidationError(f"profile condition uses unsupported op {condition.op!r}")


def _mapping_get(m: Mapping, key: str) -> object:
    """Access a Mapping with a string key using iteration to avoid Unknown key issues."""
    for k, v in m.items():
        if k == key:
            return v
    return None


def _resolve_profile_fact(profile_facts: object, field: str) -> object:
    if isinstance(profile_facts, Mapping) and field in profile_facts:
        return _mapping_get(profile_facts, field)
    if field == "iva.regime" and hasattr(profile_facts, "iva_regime"):
        _attr = "iva_regime"
        return getattr(profile_facts, _attr)
    current: object = profile_facts
    for part in field.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                raise RegistryValidationError(f"profile facts missing {field!r}")
            current = _mapping_get(current, part)
            continue
        if not hasattr(current, part):
            raise RegistryValidationError(f"profile facts missing {field!r}")
        current = getattr(current, part)
    return current
