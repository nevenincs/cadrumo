"""Focused unit tests for the filing-schedule profile-predicate helpers.

`_schedules` exposes three pure helpers that gate which filing schedule
of a revision applies to a profile. Indirect coverage exists through
the cross-reference applicability and filing-schedule selection
integration tests, but the unsupported-op raise, the dotted-path
branching (dict vs object), and the mode-handling early-return paths
all lack direct unit tests. A regression in the dotted-path walker
would surface only as a registry-load failure on the committed corpus
— slow signal.

Tests here are structural / contract assertions on the helpers, not
calculation tautologies.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ..errors import RegistryValidationError
from ..schedules import (
    _resolve_profile_fact,
    evaluate_profile_conditions,
    profile_condition_matches,
)
from ..schema_verification import ProfilePredicateDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _condition(field: str, op: str, value: bool | int | str, explanation: str = "test") -> ProfilePredicateDefinition:
    return ProfilePredicateDefinition.model_validate(
        {
            "field": field,
            "op": op,
            "value": value,
            "explanation": explanation,
            "legal_refs": ("ley-35-2006:art-1",),
            "source_refs": ("aeat-renta-2025-manual-parte1",),
        },
    )


# ---------------------------------------------------------------------------
# profile_condition_matches
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("op", "actual", "expected"),
    (
        pytest.param("equals", "madrid", True, id="equals-match"),
        pytest.param("equals", "cataluna", False, id="equals-mismatch"),
        pytest.param("not_equals", "cataluna", True, id="not-equals-mismatch"),
        pytest.param("not_equals", "madrid", False, id="not-equals-match"),
    ),
)
def test_profile_condition_matches_operator_truth_table(op: str, actual: str, expected: bool) -> None:
    condition = _condition("residence_ccaa", op, "madrid")
    assert profile_condition_matches(condition, {"residence_ccaa": actual}) is expected


def test_profile_condition_matches_unsupported_op_raises() -> None:
    """The op field's Literal["equals", "not_equals"] schema annotation
    rejects unsupported values at construct-time. Forge the predicate
    via model_construct so the validator-bypass exercises the
    runtime-side defensive branch in profile_condition_matches."""
    condition = ProfilePredicateDefinition.model_construct(
        field="residence_ccaa",
        op="contains",  # intentional invalid op for branch coverage
        value="madrid",
        explanation="forged",
        legal_refs=("ley-35-2006:art-1",),
        source_refs=("aeat-renta-2025-manual-parte1",),
    )

    with pytest.raises(RegistryValidationError, match="unsupported op 'contains'"):
        profile_condition_matches(condition, {"residence_ccaa": "madrid"})


# ---------------------------------------------------------------------------
# _resolve_profile_fact
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("facts", "field", "expected"),
    [
        ({"age": 35}, "age", 35),
        ({"residence": {"ccaa": "madrid"}}, "residence.ccaa", "madrid"),
        (SimpleNamespace(age=35, residence=SimpleNamespace(ccaa="madrid")), "age", 35),
        (SimpleNamespace(age=35, residence=SimpleNamespace(ccaa="madrid")), "residence.ccaa", "madrid"),
    ],
    ids=("dict-single", "dict-nested", "object-single", "object-nested"),
)
def test_resolve_profile_fact_resolves_present_paths(facts: object, field: str, expected: object) -> None:
    assert _resolve_profile_fact(facts, field) == expected


def test_resolve_profile_fact_mixes_dict_then_object_traversal() -> None:
    """The walker dispatches per-segment, so a top-level dict can contain
    a nested object whose attribute is then resolved by getattr."""
    facts = {"residence": SimpleNamespace(ccaa="madrid")}
    assert _resolve_profile_fact(facts, "residence.ccaa") == "madrid"


def test_resolve_profile_fact_missing_dict_key_raises() -> None:
    with pytest.raises(RegistryValidationError, match="profile facts missing 'age'"):
        _resolve_profile_fact({"residence_ccaa": "madrid"}, "age")


def test_resolve_profile_fact_missing_object_attribute_raises() -> None:
    profile = SimpleNamespace(age=35, residence=SimpleNamespace(ccaa="madrid"))
    with pytest.raises(RegistryValidationError, match="profile facts missing 'name'"):
        _resolve_profile_fact(profile, "name")


def test_resolve_profile_fact_taxpayer_entity_type_special_case() -> None:
    """contract regression: the M202 filing schedule uses ``field = "taxpayer.entity_type"``
    but TaxpayerProfile exposes ``entity_type`` directly (no ``.taxpayer`` sub-attribute).
    Without the special case, ``_resolve_profile_fact(profile, "taxpayer.entity_type")``
    raises RegistryValidationError and M202 is absent from the calendar for all
    LEGAL_ENTITY profiles.

    The special case must resolve ``taxpayer.entity_type`` against the object's
    ``entity_type`` attribute, mirroring the ``iva.regime`` -> ``iva_regime`` pattern.
    """
    from ....deadlines.models import EntityType, IVARegime, TaxpayerProfile

    profile = TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        iva_regime=IVARegime.GENERAL,
    )
    result = _resolve_profile_fact(profile, "taxpayer.entity_type")
    assert result is EntityType.LEGAL_ENTITY


# ---------------------------------------------------------------------------
# evaluate_profile_conditions
# ---------------------------------------------------------------------------


def test_evaluate_profile_conditions_empty_returns_empty_tuple() -> None:
    """Empty conditions short-circuit before the mode check fires."""
    assert evaluate_profile_conditions((), {"residence_ccaa": "madrid"}, mode="all") == ()
    assert evaluate_profile_conditions((), {"residence_ccaa": "madrid"}, mode="any") == ()


def test_evaluate_profile_conditions_mode_all_with_all_matches_returns_explanations() -> None:
    conditions = (
        _condition("residence_ccaa", "equals", "madrid", explanation="resident in madrid"),
        _condition("age", "equals", 35, explanation="age 35"),
    )
    result = evaluate_profile_conditions(conditions, {"residence_ccaa": "madrid", "age": 35}, mode="all")

    assert result == ("resident in madrid", "age 35")


def test_evaluate_profile_conditions_mode_all_with_any_mismatch_returns_none() -> None:
    conditions = (
        _condition("residence_ccaa", "equals", "madrid"),
        _condition("age", "equals", 35),
    )
    result = evaluate_profile_conditions(conditions, {"residence_ccaa": "madrid", "age": 36}, mode="all")

    assert result is None


def test_evaluate_profile_conditions_mode_any_with_some_match_returns_only_matches() -> None:
    conditions = (
        _condition("residence_ccaa", "equals", "madrid", explanation="resident in madrid"),
        _condition("age", "equals", 99, explanation="age 99"),
    )
    result = evaluate_profile_conditions(conditions, {"residence_ccaa": "madrid", "age": 35}, mode="any")

    assert result == ("resident in madrid",)


def test_evaluate_profile_conditions_mode_any_with_no_match_returns_none() -> None:
    conditions = (
        _condition("residence_ccaa", "equals", "madrid"),
        _condition("age", "equals", 99),
    )
    result = evaluate_profile_conditions(conditions, {"residence_ccaa": "cataluna", "age": 35}, mode="any")

    assert result is None
