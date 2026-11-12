"""A served way out routes through the TUI's admitted registries, or is unroutable; it never submits."""

from __future__ import annotations

import pytest

from ...navigation import TuiActionCandidateV1
from ...operations.destination import OPERATION_FOCUS_KEY, OPERATIONS_DESTINATION
from ..routing import route_refusal_way
from ..served import ServedRefusalV1, refusal_ways
from .refusal_fixtures import (
    ATTEST_PRIOR_VALUE,
    CREATE_WORK,
    REVIEW_LEDGER,
    attest_alternative,
    destinations,
    operations,
    primary_verdict,
    review_alternative,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_an_action_whose_command_is_a_registered_operation_opens_that_operation() -> None:
    (way,) = refusal_ways(ServedRefusalV1(verdict=primary_verdict(CREATE_WORK)))
    entry = operations().entry("modelo.work.create")
    assert entry is not None

    intent = route_refusal_way(way, destinations=destinations(), operations=operations())

    assert intent is not None
    assert intent.kind == "follow"
    assert intent.target_command_key == "modelo.work.create"
    assert intent.target.destination == OPERATIONS_DESTINATION
    assert intent.target.focus.semantic_key == OPERATION_FOCUS_KEY
    assert intent.target.focus.restore_token == entry.focus_token
    assert [binding.argument_name for binding in intent.argument_bindings] == ["modelo"]
    assert intent.missing_argument_names == ()


def test_missing_arguments_open_the_destination_form_for_them() -> None:
    (way,) = refusal_ways(ServedRefusalV1(verdict=primary_verdict(CREATE_WORK, missing_year=True)))

    intent = route_refusal_way(way, destinations=destinations(), operations=operations())

    assert intent is not None
    assert intent.kind == "form"
    assert intent.missing_argument_names == ("year",)
    assert intent.target.destination == OPERATIONS_DESTINATION


def test_an_action_routes_by_the_target_operations_the_verdict_served() -> None:
    (way,) = refusal_ways(ServedRefusalV1(verdict=primary_verdict(ATTEST_PRIOR_VALUE)))
    assert way.target_operation_ids == ("modelo.edit.apply", "modelo.edit.preflight", "modelo.work.form")
    first_held = next(entry for entry in map(operations().entry, way.target_operation_ids) if entry is not None)

    intent = route_refusal_way(way, destinations=destinations(), operations=operations())

    assert intent is not None
    assert intent.target.focus.restore_token == first_held.focus_token


def test_an_action_whose_served_operations_the_catalogue_does_not_hold_is_unroutable() -> None:
    verdict = primary_verdict(ATTEST_PRIOR_VALUE).model_copy(
        update={"target_operation_ids": ("unregistered.operation",)}
    )
    (way,) = refusal_ways(ServedRefusalV1(verdict=verdict))
    assert operations().entry("unregistered.operation") is None

    assert route_refusal_way(way, destinations=destinations(), operations=operations()) is None


def test_an_operation_is_unroutable_while_the_operations_destination_is_not_admitted() -> None:
    (way,) = refusal_ways(ServedRefusalV1(verdict=primary_verdict(CREATE_WORK)))

    closed = destinations(unavailable=frozenset({OPERATIONS_DESTINATION}))

    assert route_refusal_way(way, destinations=closed, operations=operations()) is None
    assert route_refusal_way(way, destinations=destinations(), operations=None) is None


def test_a_destination_that_admits_the_action_as_a_candidate_is_preferred() -> None:
    (way,) = refusal_ways(ServedRefusalV1(verdict=primary_verdict(ATTEST_PRIOR_VALUE)))
    candidate = TuiActionCandidateV1(action_candidate_id=ATTEST_PRIOR_VALUE, destination="workbench.declarations")

    intent = route_refusal_way(way, destinations=destinations(action_candidates=(candidate,)), operations=operations())

    assert intent is not None
    assert intent.target.destination == "workbench.declarations"
    assert intent.target.action_candidate_id == ATTEST_PRIOR_VALUE
    assert intent.target_command_key == "modelo.work.attest_prior_value"


def test_alternatives_route_independently_in_served_order() -> None:
    verdict = primary_verdict(CREATE_WORK, attest_alternative(), review_alternative())
    ways = refusal_ways(ServedRefusalV1(verdict=verdict))

    intents = [route_refusal_way(way, destinations=destinations(), operations=operations()) for way in ways]

    assert [way.action_id for way in ways] == [CREATE_WORK, ATTEST_PRIOR_VALUE, REVIEW_LEDGER]
    assert [None if intent is None else intent.target_command_key for intent in intents] == [
        "modelo.work.create",
        "modelo.work.attest_prior_value",
        "ledger.review",
    ]
