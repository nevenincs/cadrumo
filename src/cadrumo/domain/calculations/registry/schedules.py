"""Filing schedule selection from registry profile predicates.

Evaluates the profile conditions declared on filing schedules of a
:class:`ModeloRevision` against a profile facts mapping and returns only
the schedules whose predicates are satisfied.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from pydantic import ConfigDict, TypeAdapter, ValidationError

from .errors import RegistryValidationError
from .schema import ModeloRevision
from .schema_deadlines import ModeloScheduleDefinition
from .schema_verification import ProfilePredicateDefinition, ProfilePredicateOp

__all__ = [
    "applicable_filing_schedules",
    "evaluate_profile_conditions",
    "profile_condition_matches",
]

_IVA_REGIME_PATH: Final[str] = "iva.regime"
_IRPF_ESTIMATION_REGIME_PATH: Final[str] = "irpf.estimation_regime"
_TAXPAYER_ENTITY_TYPE_PATH: Final[str] = "taxpayer.entity_type"
_PROFILE_ATTRIBUTE_FACTS: Final[dict[str, tuple[str, bool]]] = {
    _IVA_REGIME_PATH: ("iva_regime", True),
    _IRPF_ESTIMATION_REGIME_PATH: ("irpf_estimation_regime", True),
    _TAXPAYER_ENTITY_TYPE_PATH: ("entity_type", False),
}
_PROFILE_FACT_MAPPING_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(
    dict[str, object],
    config=ConfigDict(strict=True),
)


def applicable_filing_schedules(
    revision: ModeloRevision,
    profile_facts: Mapping[str, object] | object,
    *,
    period: str | None = None,
) -> tuple[ModeloScheduleDefinition, ...]:
    """Return :class:`ModeloScheduleDefinition` items whose profile predicates match the supplied facts.

    Args:
        revision: The :class:`ModeloRevision` whose filing schedules to evaluate.
        profile_facts: Profile facts (mapping or aggregate) consulted by each
            schedule's :class:`ProfilePredicateDefinition` set.
        period: Optional period token; when supplied, schedules whose
            ``periods`` set excludes it are filtered out before predicate
            evaluation.
    """
    matched: list[ModeloScheduleDefinition] = []
    for schedule in revision.filing_schedules:
        if period is not None and period not in schedule.periods:
            continue
        if (
            evaluate_profile_conditions(
                schedule.profile_conditions,
                profile_facts,
                mode=schedule.profile_condition_mode,
            )
            is not None
        ):
            matched.append(schedule)
    return tuple(matched)


def evaluate_profile_conditions(
    conditions: tuple[ProfilePredicateDefinition, ...],
    profile_facts: Mapping[str, object] | object,
    *,
    mode: str,
) -> tuple[str, ...] | None:
    """Return matched predicate explanations, or ``None`` when the profile fails."""
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
    """Return whether one declared predicate matches the supplied profile facts."""
    observed = _resolve_profile_fact(profile_facts, condition.field)
    if condition.op == ProfilePredicateOp.EQUALS:
        return observed == condition.value
    if condition.op == ProfilePredicateOp.NOT_EQUALS:
        return observed != condition.value
    raise RegistryValidationError(f"profile condition uses unsupported op {str(condition.op)!r}")


def _resolve_direct_profile_fact(profile_facts: object, field: str) -> tuple[bool, object]:
    """Resolve a predicate from a validated top-level mapping when present."""
    top_level_facts = _profile_fact_mapping(profile_facts)
    if top_level_facts is None or field not in top_level_facts:
        return False, None
    return True, top_level_facts[field]


def _resolve_profile_attribute_fact(profile_facts: object, field: str) -> tuple[bool, object]:
    """Resolve registry dotted paths exposed as flat profile attributes."""
    attribute_specification = _PROFILE_ATTRIBUTE_FACTS.get(field)
    if attribute_specification is None:
        return False, None
    attribute_name, unwrap_enum = attribute_specification
    if not hasattr(profile_facts, attribute_name):
        return False, None
    observed: object = getattr(profile_facts, attribute_name)
    return True, getattr(observed, "value", observed) if unwrap_enum else observed


def _resolve_profile_fact_part(current: object, part: str, field: str) -> object:
    """Resolve one mapping or attribute segment, retaining the canonical refusal."""
    current_mapping = _profile_fact_mapping(current)
    if current_mapping is not None:
        if part not in current_mapping:
            raise RegistryValidationError(f"profile facts missing {field!r}")
        return current_mapping[part]
    if not hasattr(current, part):
        raise RegistryValidationError(f"profile facts missing {field!r}")
    return getattr(current, part)


def _resolve_profile_fact_path(profile_facts: object, field: str) -> object:
    """Resolve a dotted profile path after known flat forms have been tried."""
    current: object = profile_facts
    for part in field.split("."):
        if current is None:
            return None
        current = _resolve_profile_fact_part(current, part, field)
    return current


def _resolve_profile_fact(profile_facts: object, field: str) -> object:
    """Resolve one declared schedule predicate against mapping or profile facts."""
    found, observed = _resolve_direct_profile_fact(profile_facts, field)
    if found:
        return observed
    found, observed = _resolve_profile_attribute_fact(profile_facts, field)
    if found:
        return observed
    return _resolve_profile_fact_path(profile_facts, field)


def _profile_fact_mapping(value: object) -> Mapping[str, object] | None:
    """Validate a profile mapping before using values from its dynamic boundary."""
    if not isinstance(value, Mapping):
        return None
    try:
        return _PROFILE_FACT_MAPPING_ADAPTER.validate_python(value)
    except ValidationError:
        return None
