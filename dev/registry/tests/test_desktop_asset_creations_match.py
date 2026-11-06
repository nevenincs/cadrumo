"""The committed creation corpus is what the window's own form builders make of its drafts.

The register's recording answers a new element's plan, limits and forecasts for
each request committed under ``dev/fixtures/assets-register-scenario/creations.json``.
The window never works that plan out: its fixture installs the recorded answer and
refuses a request the corpus does not hold. So the corpus has to be the very request
the window sends. This test runs the shipped form fields and request builders on each
committed draft, through the frontend's own bundle under Node, and compares the result
with the committed request field by field. A draft or a builder that moves fails here,
loudly, instead of showing up in the window as a refused creation.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from cadrumo.application.actividad_asset.register_reads import register_years
from cadrumo.application.actividad_asset.tests.register_recording_support import (
    PAYMENT_PREFIX,
    committed_creations,
    committed_scenario,
    recorded_candidates,
    replayed_register,
    resolved_payments,
)
from cadrumo.application.ledger.entry_limits import ledger_entry_limits
from cadrumo.domain.renta.actividad_asset.lifecycle import AssetKind

from .desktop_request_support import bundle, run

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The option fields the form builders are drawn against, as the register serves them.
_DRAWN_FROM = (
    "methods",
    "method_facts",
    "acquisition_shapes",
    "declared_activities",
    "disposal_reasons",
    "basis_stages",
    "opening_statuses",
    "acquired_conditions",
    "further_acquisition_shapes",
)


@cache
def _committed() -> dict[str, dict[str, Any]]:
    return {made["id"]: made for made in committed_creations()}


@cache
def _payments() -> dict[str, str]:
    """The ledger's identifier for each payment the scenario names."""
    _operations, _today, payments = replayed_register(*committed_scenario())
    return {item["provider_id"]: item["transaction_id"] for item in payments}


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, Any]]:
    """What the window's builders make of every committed draft, keyed by its name."""
    operations, _today, _payments_read = replayed_register(*committed_scenario())
    year = operations.default_register_year(register_years(operations.list_elements()))
    options = json.loads(operations.form_options(asset_kind=AssetKind.MATERIAL, tax_year=year).model_dump_json())
    served: dict[str, Any] = {name: options[name] for name in _DRAWN_FROM}
    # No request builder reads the Modelo 130 periods, which the registry owns.
    served["m130_periods"] = []
    return run(
        bundle(Path(tmp_path_factory.mktemp("asset-creations"))),
        [
            {"id": made["id"], "kind": "create", "draft": resolved_payments(made["draft"], _payments())}
            for made in committed_creations()
        ],
        served=served,
        limits=json.loads(ledger_entry_limits().model_dump_json()),
        candidates=[json.loads(item.model_dump_json()) for item in recorded_candidates(operations)],
    )


@pytest.mark.parametrize("name", sorted(_committed()))
def test_a_committed_creation_is_the_request_the_form_builders_make(
    built: dict[str, dict[str, Any]], name: str
) -> None:
    made = _committed()[name]
    answer = built[name]

    assert answer["problems"] == {}, f"{name}: the form could not state its draft: {answer['problems']}"
    assert answer["request"] is not None, f"{name}: the form made no request from a complete draft"
    request = answer["request"]
    stated = {field: value for field, value in request["revision"].items() if field != "asset_id"}
    expected = resolved_payments(made["revision"], _payments())
    assert set(stated) == set(expected), f"{name}: the committed revision states other fields than the form does"
    for field in sorted(expected):
        assert stated[field] == expected[field], f"{name}: the committed {field} is not the one the form makes"
    assert request["descriptor"] == resolved_payments(made["descriptor"], _payments())
    assert set(request) == {"revision", "descriptor"}


def test_every_committed_creation_names_a_payment_the_scenario_holds() -> None:
    named = {
        value
        for made in committed_creations()
        for value in json.dumps(made).split('"')
        if value.startswith(PAYMENT_PREFIX)
    }

    assert named, "no committed creation names a payment, so the corpus tests no ledger acquisition"
    for reference in named:
        assert reference.removeprefix(PAYMENT_PREFIX) in _payments(), reference


def test_the_corpus_holds_a_creation_for_every_shape_the_window_can_send() -> None:
    committed = _committed()
    shapes = {made["revision"]["acquisition_shape"] for made in committed.values()}
    stages = {made["revision"]["basis"]["stage"] for made in committed.values()}

    assert shapes == {"primary_purchase", "acquired_outside_ledger"}
    assert "whole_property" in stages
    assert any(made["revision"].get("vehicle_affectation") is not None for made in committed.values())
    assert any(made["revision"]["opening_history"]["status"] == "missing" for made in committed.values())
    assert any(made["revision"].get("further_acquisitions") for made in committed.values())
    assert any(made["revision"]["amortization"].get("shift_hours_per_day") for made in committed.values())
    assert any(made["revision"]["amortization"].get("used_original_price") for made in committed.values())


@pytest.mark.parametrize("name", sorted(_committed()))
def test_a_committed_creation_states_no_asset_identity_of_its_own(name: str) -> None:
    made = _committed()[name]

    assert "asset_id" not in made["revision"], "the window mints the identity, so the corpus states none"
    assert made["revision"]["revision_number"] == 1
