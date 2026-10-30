"""The form options serve each offered method's facts, read from the election model.

A method is offered only when its required facts can each be stated as a single value,
and the facts served are exactly what the election accepts: building an election from
them succeeds, and leaving out any required one is refused.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetMethodFact
from cadrumo.application.actividad_asset.register_reads import method_facts_view
from cadrumo.domain.renta.actividad_asset.election import (
    ELECTION_REQUIRED_FACTS,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.election_facts import method_facts, method_is_statable
from cadrumo.domain.renta.actividad_asset.fact_leaves import FactKind
from cadrumo.domain.renta.actividad_asset.lifecycle import AssetKind

from .test_register import _operations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SAMPLES: dict[FactKind, Any] = {
    FactKind.TEXT: "reference-1",
    FactKind.DATE: date(2025, 3, 1).isoformat(),
    FactKind.AMOUNT: "100.00",
    FactKind.SHARE: "0.5",
    FactKind.WHOLE: 4,
    FactKind.FLAG: False,
    FactKind.DECIMAL: "8",
    FactKind.CLASS: "equipo-informacion-software",
}


def _sample(fact: ActivityAssetMethodFact) -> Any:
    return fact.tokens[0] if fact.kind is FactKind.CHOICE else _SAMPLES[fact.kind]


def _election(method: AmortizationMethod, skipped: tuple[str, ...] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"regime": DirectEstimationRegime.SIMPLIFIED, "method": method}
    for fact in method_facts_view(method).facts:
        if not (fact.required or fact.required_with_group) or fact.path == skipped:
            continue
        *parents, leaf = fact.path
        node = data
        for step in parents:
            node = node.setdefault(step, {})
        node[leaf] = _sample(fact)
    return data


_STATABLE = [method for method in AmortizationMethod if method_is_statable(method)]


@pytest.mark.parametrize("method", _STATABLE)
def test_an_election_built_from_the_required_facts_served_is_accepted(method: AmortizationMethod) -> None:
    election = ActivityAssetAmortizationElection.model_validate_json(json.dumps(_election(method)))

    assert election.method is method


@pytest.mark.parametrize("method", _STATABLE)
def test_leaving_out_any_required_fact_served_is_refused(method: AmortizationMethod) -> None:
    for fact in method_facts_view(method).facts:
        if fact.required:
            with pytest.raises(ValueError, match=r"requires|Field required|missing"):
                ActivityAssetAmortizationElection.model_validate_json(json.dumps(_election(method, skipped=fact.path)))


def test_a_method_needing_a_repeated_group_is_not_statable_and_the_others_are() -> None:
    assert {m for m in AmortizationMethod if not method_is_statable(m)} == {AmortizationMethod.APPROVED_PLAN}
    assert method_facts(AmortizationMethod.APPROVED_PLAN)[-1].kind is FactKind.ROWS


def test_every_fact_a_method_requires_is_served_for_it() -> None:
    for method, names in ELECTION_REQUIRED_FACTS.items():
        served = {fact.path[0] for fact in method_facts(method) if fact.required}
        assert served == set(names), method


def test_a_choice_names_its_family_and_tokens_and_a_class_names_none() -> None:
    by_path = {fact.path: fact for fact in method_facts_view(AmortizationMethod.SUM_OF_DIGITS).facts}

    order = by_path[("digit_order",)]
    assert (order.kind, order.token_family, order.tokens, order.required) == (
        FactKind.CHOICE,
        "digit_order",
        ("descending", "ascending"),
        True,
    )
    assert by_path[("authority_class_key",)].kind is FactKind.CLASS
    assert by_path[("authority_class_key",)].token_family is None


def test_an_optional_group_requires_its_own_facts_only_once_stated() -> None:
    by_path = {fact.path: fact for fact in method_facts_view(AmortizationMethod.LINEAR).facts}

    price = by_path[("used_original_price", "original_price")]
    assert (price.required, price.required_with_group) == (False, True)
    evidence = by_path[("used_original_price", "evidence_reference")]
    assert (evidence.required, evidence.required_with_group) == (False, False)
    assert by_path[("linear_coefficient",)].kind is FactKind.SHARE


def test_the_form_options_offer_only_methods_with_facts_a_form_can_state() -> None:
    operations, _ = _operations()

    options = operations.form_options(asset_kind=AssetKind.MATERIAL, tax_year=2025)

    assert AmortizationMethod.APPROVED_PLAN not in options.methods
    assert AmortizationMethod.ELECTRIC_VEHICLE_FREE in options.methods
    assert [entry.method for entry in options.method_facts] == list(options.methods)
    electric = next(entry for entry in options.method_facts if entry.method is AmortizationMethod.ELECTRIC_VEHICLE_FREE)
    assert [fact.path for fact in electric.facts if fact.required] == [("authority_class_key",)]
