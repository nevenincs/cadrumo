"""Real-behavior checks for the non-calculation binding disposition.

The disposition is the one way an author may tell the compiler that a binding
with no typed calculation consumer is intentional. Two things therefore have to
hold at once: the disposition must be impossible to author emptily, and it must
move the row from the unreferenced advisory onto its own reported line rather
than out of the report. Both are exercised here against real schema models and
the real compiler advisory, on revisions built in memory so no committed
registry file is read or written.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.core.aggregation import BindingAggregation, BindingAggregationOp
from cadrumo.domain.calculations.registry.binding_temporal import (
    AllRevisionContexts,
    NonCalculation,
    binding_applies_to_period,
)
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

from ..validate_bindings import informational_binding_ids, unreferenced_binding_advisories

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-37-1992:art-75"
_SOURCE_REF = "aeat-test-source-001"
_PROVIDER = {
    "kind": "manual_input",
    "casilla_id": "62",
    "data_type": "money",
}


def _binding(binding_id: str, *, applicability: object) -> BindingDefinition:
    """Build one binding carrying the applicability member under test."""
    return BindingDefinition(
        id=binding_id,
        provider=_PROVIDER,
        value={"data_type": "money", "channel": "decimal"},
        aggregation=BindingAggregation(op=BindingAggregationOp.COPY),
        applicability=applicability,
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )


def _revision(*bindings: BindingDefinition) -> ModeloRevision:
    """Build a revision whose only declarations are the bindings under test."""
    return ModeloRevision(
        id="test-revision",
        localization_key="test.schema.revision.test-revision.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("1T",)),
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
        bindings=bindings,
    )


def test_non_calculation_refuses_a_blank_consumed_by() -> None:
    """A disposition that names no consumer is an author silencing an orphan."""
    with pytest.raises(ValidationError, match="consumed_by"):
        NonCalculation(reason="informational_total", consumed_by="   ")


def test_non_calculation_refuses_a_missing_consumed_by() -> None:
    """``consumed_by`` is required, so the field cannot be omitted either."""
    with pytest.raises(ValidationError, match="consumed_by"):
        NonCalculation.model_validate({"kind": "non_calculation", "reason": "informational_total"})


def test_non_calculation_refuses_an_empty_string_consumed_by() -> None:
    """The empty string is refused by the length bound before the validator runs."""
    with pytest.raises(ValidationError, match="consumed_by"):
        NonCalculation(reason="informational_total", consumed_by="")


def test_non_calculation_refuses_an_unclassed_reason() -> None:
    """The reason vocabulary is closed; an unnamed class is not a disposition."""
    with pytest.raises(ValidationError):
        NonCalculation.model_validate(
            {"kind": "non_calculation", "reason": "because-i-said-so", "consumed_by": "some report"},
        )


def test_non_calculation_carries_the_retired_box_revision() -> None:
    """A retired box is traceable to the edition that retired it."""
    member = NonCalculation(
        reason="informational_total",
        box_retired_in="2023",
        consumed_by="modelo-390 annual informational handoff",
    )

    assert member.box_retired_in == "2023"
    assert binding_applies_to_period(member, "1T") is False


def test_advisory_skips_a_dispositioned_binding_and_counts_it_instead() -> None:
    """The disposition moves a row between two reported lines, never out of both."""
    orphan = _binding("test.binding.orphan", applicability=AllRevisionContexts())
    dispositioned = _binding(
        "test.binding.informational",
        applicability=NonCalculation(
            reason="informational_total",
            box_retired_in="2023",
            consumed_by="modelo-390 annual informational handoff",
        ),
    )
    revision = _revision(orphan, dispositioned)

    advisories = unreferenced_binding_advisories(prefix="modelo test revision test-revision", revision=revision)
    informational = informational_binding_ids(revision)

    assert [advisory for advisory in advisories if "test.binding.informational" in advisory] == []
    assert any("test.binding.orphan" in advisory for advisory in advisories)
    assert informational == ("test.binding.informational",)


def test_an_undispositioned_orphan_is_not_counted_as_informational() -> None:
    """The informational line counts dispositions, not every unreferenced row."""
    revision = _revision(_binding("test.binding.orphan", applicability=AllRevisionContexts()))

    assert informational_binding_ids(revision) == ()
    assert len(unreferenced_binding_advisories(prefix="modelo test revision test-revision", revision=revision)) == 1
