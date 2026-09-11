"""Detector-teeth tests for governed-fact catalogue validation."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue
from dev.registry.compiler.fact_validation import governed_fact_catalogue_failures
from dev.registry.compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _variant(
    variant_id: str,
    *,
    valid_from: date,
    valid_to: date | None = None,
    precedence_over: tuple[str, ...] = (),
    source_ref: str = "test-source",
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "variant_id": variant_id,
        "date_axis": "filing_period",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "payload": {"kind": "scalar", "value": "10", "unit": "EUR"} if payload is None else payload,
        "legal_refs": ("law",),
        "source_refs": (source_ref,),
        "source_citations": ({"source_ref": source_ref, "required_text": ("text",)},),
        "review_status": "pending_review",
        "ownership": "authored",
        "precedence_over": precedence_over,
    }


def _failures(*variants: dict[str, object]) -> tuple[str, ...]:
    fact = GovernedFact.model_validate({"fact_id": "test.rate", "family": "scalar", "variants": variants})
    return governed_fact_catalogue_failures(
        GovernedFactCatalogue(facts={fact.fact_id: fact}),
        legal_ref_ids={"law"},
        source_ref_ids={"test-source"},
    )


def test_validation_refuses_a_precedence_cycle() -> None:
    failures = _failures(
        _variant("rate.a", valid_from=date(2025, 1, 1), precedence_over=("rate.b",)),
        _variant("rate.b", valid_from=date(2025, 1, 1), precedence_over=("rate.a",)),
    )

    assert any("precedence graph contains a cycle" in failure for failure in failures)


def test_validation_refuses_an_unresolved_overlap() -> None:
    failures = _failures(
        _variant("rate.a", valid_from=date(2025, 1, 1)),
        _variant("rate.b", valid_from=date(2025, 6, 1)),
    )

    assert any("overlap without explicit precedence" in failure for failure in failures)


def test_validation_refuses_precedence_across_non_overlapping_coordinates() -> None:
    failures = _failures(
        _variant(
            "rate.a",
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 5, 31),
            precedence_over=("rate.b",),
        ),
        _variant("rate.b", valid_from=date(2025, 6, 1)),
    )

    assert any("precedence across non-overlapping coordinates" in failure for failure in failures)


def test_validation_accepts_an_acyclic_ordered_overlap() -> None:
    failures = _failures(
        _variant("rate.a", valid_from=date(2025, 1, 1), precedence_over=("rate.b",)),
        _variant("rate.b", valid_from=date(2025, 6, 1)),
    )

    assert failures == ()


@pytest.mark.parametrize(
    ("family", "payload"),
    (
        pytest.param("scalar", {"kind": "scalar", "value": "10", "unit": "EUR"}, id="scalar"),
        pytest.param(
            "bracket",
            {"kind": "bracket", "unit": "EUR", "brackets": ({"lower_bound": "0", "value": "1"},)},
            id="bracket",
        ),
        pytest.param("mapping", {"kind": "mapping", "entries": ({"key": "rate", "value": "1"},)}, id="mapping"),
        pytest.param("entity_set", {"kind": "entity_set", "entities": ("entity",)}, id="entity-set"),
        pytest.param("override", {"kind": "override", "override_code": "override", "value": "1"}, id="override"),
        pytest.param(
            "event",
            {"kind": "event", "event_date": date(2025, 1, 1), "event_code": "event"},
            id="event",
        ),
        pytest.param(
            "multi_output",
            {
                "kind": "multi_output",
                "bands": (
                    {
                        "lower_bound": "0",
                        "outputs": ({"name": "left", "value": "1"}, {"name": "right", "value": "2"}),
                    },
                ),
            },
            id="multi-output",
        ),
    ),
)
def test_validation_refuses_source_windows_outside_every_fact_family(
    family: str,
    payload: dict[str, object],
) -> None:
    """A cited source's declared applicability bounds every fact family, not a retired-provider list."""
    source = next(iter(load_shared_catalogues(bundled_path("registry", "aeat")).sources.values())).model_copy(
        update={"applies_from": date(2025, 1, 2), "applies_to": date(2025, 12, 30)}
    )
    source_ref = str(source.id)
    fact_id = f"test.{family}"
    variant = _variant(
        f"{fact_id}:window",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
        source_ref=source_ref,
        payload=payload,
    )
    fact = GovernedFact.model_validate({"fact_id": fact_id, "family": family, "variants": (variant,)})

    failures = governed_fact_catalogue_failures(
        GovernedFactCatalogue(facts={fact.fact_id: fact}),
        legal_ref_ids={"law"},
        source_ref_ids={source_ref},
        source_refs={source_ref: source},
    )

    assert f"starts before source {source_ref!r} applicability window" in "\n".join(failures)
    assert f"ends after source {source_ref!r} applicability window" in "\n".join(failures)


def test_facts_package_initializer_is_an_inert_namespace_marker() -> None:
    from cadrumo.domain.calculations.registry.facts import __dict__ as namespace

    assert "GovernedFact" not in namespace
    assert "ScalarFactPayload" not in namespace
