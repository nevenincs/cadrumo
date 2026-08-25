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
from .schema import ModeloRevision, ModeloScheduleDefinition, ProfilePredicateDefinition

__all__ = [
    "applicable_filing_schedules",
    "evaluate_profile_conditions",
    "profile_condition_matches",
]

_IVA_REGIME_PATH: Final[str] = "iva.regime"
_IRPF_ESTIMATION_REGIME_PATH: Final[str] = "irpf.estimation_regime"
_TAXPAYER_ENTITY_TYPE_PATH: Final[str] = "taxpayer.entity_type"
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


def _resolve_profile_fact(profile_facts: object, field: str) -> object:
    top_level_facts = _profile_fact_mapping(profile_facts)
    if top_level_facts is not None and field in top_level_facts:
        return top_level_facts[field]
    # Schema predicate path "iva.regime" maps to the TaxpayerProfile.iva_regime
    # attribute.  The dotted path form is what the TOML registry declares; the
    # attribute name is what the Python dataclass exposes without nesting.
    if field == _IVA_REGIME_PATH and hasattr(profile_facts, "iva_regime"):
        _attr = "iva_regime"
        observed: object = getattr(profile_facts, _attr)
        value: object = getattr(observed, "value", observed)
        return value
    if field == _IRPF_ESTIMATION_REGIME_PATH and hasattr(profile_facts, "irpf_estimation_regime"):
        _attr = "irpf_estimation_regime"
        observed = getattr(profile_facts, _attr)
        value = getattr(observed, "value", observed)
        return value
    # Schema predicate path "taxpayer.entity_type" maps to
    # TaxpayerProfile.entity_type.  The "taxpayer." prefix is the namespace used
    # in the registry TOML; the attribute is a flat field on the profile object.
    if field == _TAXPAYER_ENTITY_TYPE_PATH and hasattr(profile_facts, "entity_type"):
        _attr = "entity_type"
        return getattr(profile_facts, _attr)
    current: object = profile_facts
    for part in field.split("."):
        if current is None:
            return None
        current_mapping = _profile_fact_mapping(current)
        if current_mapping is not None:
            if part not in current_mapping:
                raise RegistryValidationError(f"profile facts missing {field!r}")
            current = current_mapping[part]
            continue
        if not hasattr(current, part):
            raise RegistryValidationError(f"profile facts missing {field!r}")
        current = getattr(current, part)
    return current


def _profile_fact_mapping(value: object) -> Mapping[str, object] | None:
    """Validate a profile mapping before using values from its dynamic boundary."""
    if not isinstance(value, Mapping):
        return None
    try:
        return _PROFILE_FACT_MAPPING_ADAPTER.validate_python(value)
    except ValidationError:
        return None
