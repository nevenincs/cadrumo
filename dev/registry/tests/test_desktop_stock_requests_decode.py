"""The requests the desktop Stock panel makes decode against the backend's own request contracts.

The frontend builds each stock book, movement and closing value request from what a person types
and the files the backend kept for them, through its form fields and request builders, judging its
choices by the vocabulary the options operation serves. The test runs those builders as they ship, on
typed drafts, and decodes the result with the request models the registered inventory operations
validate, then builds the domain operand a purchase or a closing value becomes inside the worker, so
a field the form states at the wrong place, or a fact it cannot state, fails here and not in the
window. The totals of a purchase are never sent: the backend adds them up, and the sums are checked
here against independently worked figures.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.inventory.registered_evidence_operation import (
    InventoryEvidenceAddProjection,
    InventoryEvidenceAddRequest,
)
from cadrumo.application.inventory.registered_options_operation import inventory_options
from cadrumo.application.inventory.registered_projections import (
    InventoryMovementProjection,
    InventoryRefusalProjection,
)
from cadrumo.application.inventory.registered_requests import (
    InventoryClosingValueRecordRequest,
    InventoryCorrectRequest,
    InventoryCreateRequest,
    InventoryDescribeRequest,
    InventoryMovementAddRequest,
    InventoryMovementCorrectRequest,
    InventoryMovementReverseRequest,
    InventoryRestoreRequest,
    InventoryRetireRequest,
)
from cadrumo.application.inventory.service import InventoryMovementCommand
from cadrumo.domain.contribuyente.inventory.corrections import inventory_refusal_key
from cadrumo.domain.contribuyente.inventory.records import MovementKind, MovementRecord, ValuationMethod
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FRONTEND = REPO_ROOT / "native" / "desktop" / "frontend"
_ENTRY = _FRONTEND / "tests" / "support" / "stockRequests.ts"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0

_BUNDLE_SCRIPT = """
const esbuild = require(process.argv[1]);
esbuild.buildSync({
  entryPoints: [process.argv[2]],
  outfile: process.argv[3],
  bundle: true,
  platform: "node",
  format: "cjs",
  tsconfig: process.argv[4],
  logLevel: "error",
});
"""

_BOOK = {"actividad_id": "Papelería y reprografía", "year": 2026}


def _mark(character: str) -> str:
    """The mark of a file's bytes: a lowercase hex SHA-256 is 64 characters."""
    return character * 64


def _kept(character: str, kind: str | None = None) -> dict[str, str]:
    """A file the backend kept: the reference it named it by and the mark it answered."""
    kept = {"reference": f"document-{_mark(character)}", "digest": _mark(character)}
    return kept if kind is None else {**kept, "kind": kind}


#: The files a purchase rests on, by slot.
_PROOFS = {
    "price": _kept("a", "purchase_invoice"),
    "cost_check": _kept("b"),
    "iva_check": _kept("c"),
}

#: A purchase of 100 units for 1000.00 with 210.00 of IVA, all of it deductible, and nothing else.
_PURCHASE = {
    "date": "2026-03-04",
    "kind": "purchase",
    "quantity": "100",
    "price": "1000.00",
    "iva": "210.00",
    "share": "100",
}

_DECIDED_AT = "2026-12-31T10:00:00.000Z"

#: A closing value worked out from the movements, with the file that shows it.
_CLOSING_DERIVED = {
    "values": {"authority": "movement_derived", "reason": "Checked against the year's movements"},
    "decision": {"authority_reconciliation": _kept("e", "authority_reconciliation")},
    "count": {},
    "prior": [],
}

#: One that rests on a count of the stock, with a file for each part of the count.
_CLOSING_COUNTED = {
    "values": {
        "authority": "physical_observation",
        "reason": "Counted on the last day of the year",
        "observed_on": "2026-12-31",
        "closing_value": "410.00",
        "basis": "fifo_acquisition_price",
    },
    "decision": {"authority_reconciliation": _kept("e", "authority_reconciliation")},
    "count": {
        "physical_count": _kept("f", "physical_count"),
        "acquisition_price_valuation": _kept("1", "acquisition_price_valuation"),
    },
    "prior": [],
}

#: Each scenario is what a person types and attaches in a form.
_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "book",
        "kind": "book",
        "year": 2026,
        "draft": {"name": "Papelería y reprografía", "method": "fifo", "opening": "410"},
    },
    {
        "id": "book_average",
        "kind": "book",
        "year": 2026,
        "draft": {"name": "Venta en línea de material de dibujo", "method": "coste_medio", "opening": "0"},
    },
    {
        "id": "opening_unit_cost",
        "kind": "movement",
        "book": _BOOK,
        "values": {"date": "2026-01-02", "kind": "opening", "quantity": "100", "unit_cost": "4.1"},
    },
    {
        "id": "opening_total_cost",
        "kind": "movement",
        "book": _BOOK,
        "values": {"date": "2026-01-02", "kind": "opening", "quantity": "100", "total_cost": "410"},
    },
    {
        "id": "sale",
        "kind": "movement",
        "book": _BOOK,
        "values": {"date": "2026-11-20", "kind": "cogs", "quantity": "60"},
    },
    {
        "id": "count",
        "kind": "movement",
        "book": _BOOK,
        "values": {"date": "2026-12-31", "kind": "count", "quantity": "2"},
    },
    {"id": "purchase", "kind": "movement", "book": _BOOK, "values": _PURCHASE, "proofs": _PROOFS},
    {
        # A freight cost of 100.00 with 21.00 of IVA, all deductible: the IVA deducted is
        # 231.00 and the total cost 1100.00.
        "id": "purchase_with_freight",
        "kind": "movement",
        "book": _BOOK,
        "values": _PURCHASE,
        "proofs": _PROOFS,
        "extras": [
            {
                "kind": "freight",
                "price": "100.00",
                "iva": "21.00",
                "share": "100",
                "proof": _kept("d", "transport_document"),
            },
        ],
    },
    {
        # Half of that freight's IVA deductible: 10.50 is deducted and 10.50 added to the cost,
        # and two costs make two files.
        "id": "purchase_with_two_costs",
        "kind": "movement",
        "book": _BOOK,
        "values": _PURCHASE,
        "proofs": _PROOFS,
        "extras": [
            {
                "kind": "freight",
                "price": "100.00",
                "iva": "21.00",
                "share": "50",
                "proof": _kept("d", "transport_document"),
            },
            {
                "kind": "insurance",
                "price": "40.00",
                "iva": "0.00",
                "share": "100",
                "proof": _kept("e", "insurance_document"),
            },
        ],
    },
    {
        "id": "purchase_without_a_file",
        "kind": "movement",
        "book": _BOOK,
        "values": _PURCHASE,
        "proofs": {"price": _PROOFS["price"], "cost_check": _PROOFS["cost_check"]},
    },
    {
        "id": "purchase_with_a_comma",
        "kind": "movement",
        "book": _BOOK,
        "values": {**_PURCHASE, "price": "1000,00"},
        "proofs": _PROOFS,
    },
    {
        "id": "describe",
        "kind": "describe",
        "book": _BOOK,
        "draft": {"label": "Papelería del centro", "description": "Papel, cuadernos y material de oficina"},
    },
    {
        "id": "describe_without_a_description",
        "kind": "describe",
        "book": _BOOK,
        "draft": {"label": "Papelería del centro", "description": ""},
    },
    {
        "id": "correct_opening",
        "kind": "correct",
        "book": _BOOK,
        "draft": {"reason": "keying_error", "opening": "380.00", "method": ""},
    },
    {
        "id": "correct_method",
        "kind": "correct",
        "book": _BOOK,
        "draft": {"reason": "source_document_corrected", "opening": "", "method": "pmp"},
    },
    {
        "id": "correct_both",
        "kind": "correct",
        "book": _BOOK,
        "draft": {"reason": "duplicate_entry", "opening": "400", "method": "coste_medio"},
    },
    {
        "id": "movement_correct",
        "kind": "movement_correct",
        "book": _BOOK,
        "target": "7d2e9f14-6a35-4c8b-b1e0-3a5c8d9f0b32",
        "reason": "source_document_corrected",
        "values": {"date": "2026-11-20", "kind": "cogs", "quantity": "50"},
    },
    {
        "id": "movement_correct_to_a_purchase",
        "kind": "movement_correct",
        "book": _BOOK,
        "target": "7d2e9f14-6a35-4c8b-b1e0-3a5c8d9f0b32",
        "reason": "operation_did_not_occur",
        "values": _PURCHASE,
        "proofs": _PROOFS,
    },
    {
        "id": "movement_reverse",
        "kind": "reverse",
        "book": _BOOK,
        "target": "7d2e9f14-6a35-4c8b-b1e0-3a5c8d9f0b32",
        "reason": "duplicate_entry",
    },
    {"id": "retire", "kind": "retire", "book": _BOOK, "reason": "activity_ceased"},
    {"id": "restore", "kind": "restore", "book": _BOOK},
    {
        "id": "movement_correct_without_a_reason",
        "kind": "movement_correct",
        "book": _BOOK,
        "target": "7d2e9f14-6a35-4c8b-b1e0-3a5c8d9f0b32",
        "reason": "",
        "values": {"date": "2026-11-20", "kind": "cogs", "quantity": "50"},
    },
    {
        "id": "retire_for_a_correction_reason",
        "kind": "retire",
        "book": _BOOK,
        "reason": "keying_error",
    },
    {
        "id": "nothing_typed",
        "kind": "movement",
        "book": _BOOK,
        "values": {},
    },
    {
        "id": "closing_derived",
        "kind": "closing",
        "book": _BOOK,
        "decision": "decision-1",
        "decidedAt": _DECIDED_AT,
        "draft": _CLOSING_DERIVED,
    },
    {
        "id": "closing_counted",
        "kind": "closing",
        "book": _BOOK,
        "decision": "decision-2",
        "decidedAt": _DECIDED_AT,
        "draft": _CLOSING_COUNTED,
    },
    {
        "id": "closing_with_prior_file",
        "kind": "closing",
        "book": _BOOK,
        "decision": "decision-3",
        "decidedAt": _DECIDED_AT,
        "draft": {**_CLOSING_DERIVED, "prior": [{"key": "p1", "proof": _kept("2", "")}]},
    },
    {
        "id": "closing_count_missing_a_file",
        "kind": "closing",
        "book": _BOOK,
        "decision": "decision-4",
        "decidedAt": _DECIDED_AT,
        "draft": {**_CLOSING_COUNTED, "count": {"physical_count": _kept("f", "physical_count")}},
    },
    {
        "id": "closing_with_nothing",
        "kind": "closing",
        "book": _BOOK,
        "decision": "decision-5",
        "decidedAt": _DECIDED_AT,
        "draft": {"values": {}, "decision": {}, "count": {}, "prior": []},
    },
    {"id": "evidence", "kind": "evidence", "token": "file-0123456789abcdef"},
]


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        raise AssertionError("node is needed to run the desktop request builders, and was not found")
    return node


def _bundle(tmp_path: Path) -> Path:
    esbuild = _FRONTEND / "node_modules" / "esbuild"
    assert esbuild.is_dir(), f"the desktop frontend's dependencies are not installed under {_FRONTEND}"
    out = tmp_path / "stockRequests.cjs"
    subprocess.run(  # noqa: S603 - fixed node program on repository files
        [
            _node(),
            "-e",
            _BUNDLE_SCRIPT,
            str(esbuild),
            str(_ENTRY),
            str(out),
            str(_FRONTEND / "tsconfig.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
        creationflags=_NO_WINDOW,
    )
    return out


def _options() -> dict[str, Any]:
    """What the options operation serves, with the role of each member: what the builders judge a request by."""
    return inventory_options(uuid4()).model_dump(mode="json")


def _run(bundle: Path, scenarios: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    done = subprocess.run(  # noqa: S603 - fixed node program on a bundle built above
        [_node(), str(bundle)],
        input=json.dumps({"options": _options(), "scenarios": scenarios}),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        creationflags=_NO_WINDOW,
    )
    return {item["id"]: item for item in json.loads(done.stdout)}


@pytest.fixture(scope="module")
def made(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, Any]]:
    return _run(_bundle(tmp_path_factory.mktemp("stock-requests")), _SCENARIOS)


def _movement(result: dict[str, Any]) -> InventoryMovementAddRequest:
    assert result["problems"] == {}, result["problems"]
    assert result["request"] is not None, "the form made no request from a complete draft"
    return InventoryMovementAddRequest.model_validate_json(
        json.dumps({"profile_id": str(uuid4()), **result["request"]})
    )


@pytest.mark.parametrize("name", ["book", "book_average"])
def test_a_book_request_the_form_makes_decodes_against_the_backend_contract(
    made: dict[str, dict[str, Any]], name: str
) -> None:
    result = made[name]
    assert result["request"] is not None
    request = InventoryCreateRequest.model_validate_json(json.dumps({"profile_id": str(uuid4()), **result["request"]}))

    assert request.year == 2026
    assert ValuationMethod(request.valuation_method) in set(ValuationMethod)
    drafted = next(scenario for scenario in _SCENARIOS if scenario["id"] == name)
    assert request.actividad_id == drafted["draft"]["name"]


@pytest.mark.parametrize("name", ["opening_unit_cost", "opening_total_cost", "sale", "count"])
def test_a_movement_other_than_a_purchase_decodes_and_states_no_cost_evidence(
    made: dict[str, dict[str, Any]], name: str
) -> None:
    request = _movement(made[name])

    assert request.acquisition_cost is None
    assert request.kind is not MovementKind.PURCHASE
    command = InventoryMovementCommand(
        movement_id=request.movement_id,
        movement_date=request.movement_date,
        kind=request.kind,
        quantity=Decimal(request.quantity.decimal),
        unit_cost=Decimal(request.unit_cost.decimal) if request.unit_cost is not None else None,
        taxable_base=Decimal(request.taxable_base.decimal) if request.taxable_base is not None else None,
    )
    assert command.acquisition_cost is None


def test_a_movement_reference_is_minted_by_the_window_and_is_never_the_same_twice(
    made: dict[str, dict[str, Any]],
) -> None:
    references = {_movement(made[name]).movement_id for name in ("opening_unit_cost", "sale", "count")}

    assert len(references) == 3
    for reference in references:
        assert str(UUID(reference)) == reference


@pytest.mark.parametrize("name", ["purchase", "purchase_with_freight", "purchase_with_two_costs"])
def test_a_purchase_request_decodes_and_becomes_the_domain_purchase_the_worker_stores(
    made: dict[str, dict[str, Any]], name: str
) -> None:
    request = _movement(made[name])

    assert request.kind is MovementKind.PURCHASE
    assert request.unit_cost is None
    assert request.taxable_base is None
    assert request.acquisition_cost is not None
    acquisition = request.acquisition_cost.to_domain()
    command = InventoryMovementCommand(
        movement_id=request.movement_id,
        movement_date=request.movement_date,
        kind=request.kind,
        quantity=Decimal(request.quantity.decimal),
        acquisition_cost=acquisition,
    )
    assert command.acquisition_cost is not None
    record = MovementRecord.from_purchase_acquisition(
        movement_id=request.movement_id,
        movement_date=request.movement_date,
        quantity=Decimal(request.quantity.decimal),
        acquisition_cost=acquisition,
    )
    assert record.capitalized_value == acquisition.total_acquisition_cost


def test_the_facts_the_form_states_reach_the_purchase_where_the_backend_reads_them(
    made: dict[str, dict[str, Any]],
) -> None:
    plain = _movement(made["purchase"]).acquisition_cost
    two = _movement(made["purchase_with_two_costs"]).acquisition_cost
    assert plain is not None
    assert two is not None

    assert Decimal(plain.consideration_excluding_iva.decimal) == Decimal("1000")
    assert Decimal(plain.consideration_deductible_iva_ratio.decimal) == Decimal("1")
    assert plain.attributable_cost_components == ()
    assert Decimal(two.consideration_deductible_iva_ratio.decimal) == Decimal("1")
    assert [component.kind.value for component in two.attributable_cost_components] == ["freight", "insurance"]
    assert two.attributable_cost_components[0].deductible_iva_ratio is not None
    assert Decimal(two.attributable_cost_components[0].deductible_iva_ratio.decimal) == Decimal("0.5")
    # One file per proof, each under the reference the backend named it by.
    references = [item.reference.reference for item in two.evidence]
    assert len(references) == len(set(references)) == 5
    assert all(
        reference == f"document-{item.content_digest}" for reference, item in zip(references, two.evidence, strict=True)
    )
    assert {item.evidence_kind.value for item in two.evidence} == {
        "purchase_invoice",
        "transport_document",
        "insurance_document",
        "attributable_cost_review",
        "iva_recoverability_review",
    }


@pytest.mark.parametrize("name", ["purchase", "purchase_with_freight", "purchase_with_two_costs"])
def test_a_purchase_states_none_of_its_totals(made: dict[str, dict[str, Any]], name: str) -> None:
    cost = made[name]["request"]["acquisition_cost"]

    for total in (
        "directly_attributable_cost_total",
        "nonrecoverable_iva_included",
        "recoverable_iva_excluded",
        "total_acquisition_cost",
    ):
        assert total not in cost


@pytest.mark.parametrize(
    ("name", "attributable", "recoverable", "nonrecoverable", "total"),
    [
        # Worked by hand: 1000 + 0 + 0.
        ("purchase", "0", "210", "0", "1000"),
        # 1000 + 100 freight, and the IVA of both (210 + 21) is all deductible.
        ("purchase_with_freight", "100", "231", "0", "1100"),
        # 1000 + 100 + 40; half of the freight's 21.00 of IVA stays in the cost: 1000 + 140 + 10.50.
        ("purchase_with_two_costs", "140", "220.5", "10.5", "1150.5"),
    ],
)
def test_the_backend_adds_up_the_totals_the_form_leaves_out(
    made: dict[str, dict[str, Any]],
    name: str,
    attributable: str,
    recoverable: str,
    nonrecoverable: str,
    total: str,
) -> None:
    request = _movement(made[name])
    assert request.acquisition_cost is not None

    acquisition = request.acquisition_cost.to_domain()

    assert acquisition.directly_attributable_cost_total == Decimal(attributable)
    assert acquisition.recoverable_iva_excluded == Decimal(recoverable)
    assert acquisition.nonrecoverable_iva_included == Decimal(nonrecoverable)
    assert acquisition.total_acquisition_cost == Decimal(total)


def test_every_reference_a_purchase_names_resolves_to_a_file_it_states(
    made: dict[str, dict[str, Any]],
) -> None:
    acquisition = _movement(made["purchase_with_two_costs"]).acquisition_cost
    assert acquisition is not None

    stated = {item.reference.reference for item in acquisition.evidence}
    named = {
        acquisition.completeness.consideration_evidence.reference,
        acquisition.completeness.attributable_cost_review_evidence.reference,
        acquisition.completeness.iva_recoverability_review_evidence.reference,
        *(
            reference.reference
            for component in acquisition.attributable_cost_components
            for reference in component.evidence_references
        ),
    }
    assert named <= stated


def test_a_correction_starts_from_what_the_inspect_read_serves_and_decodes(tmp_path: Path) -> None:
    """The purchase as the backend projects it for inspect, corrected through the real builders."""
    bundle = _bundle(tmp_path)
    first = _run(bundle, [scenario for scenario in _SCENARIOS if scenario["id"] == "purchase_with_two_costs"])
    request = _movement(first["purchase_with_two_costs"])
    assert request.acquisition_cost is not None
    record = MovementRecord.from_purchase_acquisition(
        movement_id=request.movement_id,
        movement_date=request.movement_date,
        quantity=Decimal(request.quantity.decimal),
        acquisition_cost=request.acquisition_cost.to_domain(),
    )
    served = InventoryMovementProjection.from_movement(record, with_acquisition_detail=True).model_dump(mode="json")

    corrected = _run(
        bundle,
        [
            {
                "id": "kept",
                "kind": "movement_correct_kept",
                "book": _BOOK,
                "target": request.movement_id,
                "reason": "keying_error",
                "movement": served,
            }
        ],
    )["kept"]

    again = _decoded(InventoryMovementCorrectRequest, corrected)
    assert again.acquisition_cost is not None
    before = request.acquisition_cost.to_domain()
    after = again.acquisition_cost.to_domain()
    assert after.total_acquisition_cost == before.total_acquisition_cost
    assert {item.content_digest for item in after.evidence} == {item.content_digest for item in before.evidence}
    assert [component.kind for component in after.attributable_cost_components] == [
        component.kind for component in before.attributable_cost_components
    ]
    assert [component.deductible_iva_ratio for component in after.attributable_cost_components] == [
        component.deductible_iva_ratio for component in before.attributable_cost_components
    ]


@pytest.mark.parametrize(
    ("name", "missing", "problem"),
    [
        ("purchase_without_a_file", "iva_check:file", None),
        ("purchase_with_a_comma", None, "price"),
        ("nothing_typed", "date", None),
    ],
)
def test_an_incomplete_or_refused_draft_makes_no_request_and_says_where(
    made: dict[str, dict[str, Any]], name: str, missing: str | None, problem: str | None
) -> None:
    result = made[name]

    assert result["request"] is None
    if missing is not None:
        assert missing in result["missing"]
    if problem is not None:
        assert problem in result["problems"]
        assert result["problems"][problem]["key"] == "comma_decimal"


# ---- Changes to a book ------------------------------------------------------------------


def _decoded[R: BaseModel](model: type[R], result: dict[str, Any]) -> R:
    """The request a form made, decoded by the contract the operation validates."""
    assert result["problems"] == {}, result["problems"]
    assert result["request"] is not None, "the form made no request from a complete draft"
    return model.model_validate_json(json.dumps({"profile_id": str(uuid4()), **result["request"]}))


def test_every_change_names_its_book_and_a_reference_minted_for_it(made: dict[str, dict[str, Any]]) -> None:
    ids = ("describe", "correct_opening", "movement_correct", "movement_reverse", "retire", "restore")
    models = (
        InventoryDescribeRequest,
        InventoryCorrectRequest,
        InventoryMovementCorrectRequest,
        InventoryMovementReverseRequest,
        InventoryRetireRequest,
        InventoryRestoreRequest,
    )

    decoded = [_decoded(model, made[name]) for name, model in zip(ids, models, strict=True)]

    for request in decoded:
        assert (request.actividad_id, request.year) == (_BOOK["actividad_id"], _BOOK["year"])
        assert str(UUID(request.correction_id)) == request.correction_id
    assert len({request.correction_id for request in decoded}) == len(decoded)


@pytest.mark.parametrize("name", ["describe", "describe_without_a_description"])
def test_a_description_is_stated_or_absent(made: dict[str, dict[str, Any]], name: str) -> None:
    request = _decoded(InventoryDescribeRequest, made[name])

    assert request.label == "Papelería del centro"
    assert (request.description is None) == (name == "describe_without_a_description")


@pytest.mark.parametrize(
    ("name", "opening", "method"),
    [
        ("correct_opening", Decimal("380"), None),
        ("correct_method", None, ValuationMethod.PMP),
        ("correct_both", Decimal("400"), ValuationMethod.COSTE_MEDIO),
    ],
)
def test_a_correction_states_what_changes_and_leaves_the_rest(
    made: dict[str, dict[str, Any]], name: str, opening: Decimal | None, method: ValuationMethod | None
) -> None:
    request = _decoded(InventoryCorrectRequest, made[name])

    assert (Decimal(request.opening_stock.decimal) if request.opening_stock is not None else None) == opening
    assert request.valuation_method == method


@pytest.mark.parametrize("name", ["movement_correct", "movement_correct_to_a_purchase"])
def test_a_corrected_movement_decodes_under_a_new_reference_and_names_the_one_it_replaces(
    made: dict[str, dict[str, Any]], name: str
) -> None:
    request = _decoded(InventoryMovementCorrectRequest, made[name])

    assert request.target_movement_id == "7d2e9f14-6a35-4c8b-b1e0-3a5c8d9f0b32"
    assert request.movement_id != request.target_movement_id
    assert str(UUID(request.movement_id)) == request.movement_id
    if request.kind is MovementKind.PURCHASE:
        assert request.unit_cost is None
        assert request.taxable_base is None
        assert request.acquisition_cost is not None
        request.acquisition_cost.to_domain()
    else:
        assert request.acquisition_cost is None


def test_a_reversal_and_a_retirement_state_their_reason(made: dict[str, dict[str, Any]]) -> None:
    reversal = _decoded(InventoryMovementReverseRequest, made["movement_reverse"])
    retirement = _decoded(InventoryRetireRequest, made["retire"])

    assert reversal.target_movement_id == "7d2e9f14-6a35-4c8b-b1e0-3a5c8d9f0b32"
    assert reversal.reason.value == "duplicate_entry"
    assert retirement.reason.value == "activity_ceased"
    _decoded(InventoryRestoreRequest, made["restore"])


@pytest.mark.parametrize("name", ["movement_correct_without_a_reason", "retire_for_a_correction_reason"])
def test_a_change_without_a_reason_of_its_own_kind_makes_no_request(made: dict[str, dict[str, Any]], name: str) -> None:
    assert made[name]["request"] is None
    assert "reason" in made[name]["missing"]


# ---- Closing values and the files behind them -------------------------------------------


def _closing(result: dict[str, Any]) -> InventoryClosingValueRecordRequest:
    return _decoded(InventoryClosingValueRecordRequest, result)


@pytest.mark.parametrize("name", ["closing_derived", "closing_counted", "closing_with_prior_file"])
def test_a_closing_value_request_decodes_against_the_backend_contract(
    made: dict[str, dict[str, Any]], name: str
) -> None:
    request = _closing(made[name])

    assert (request.actividad_id, request.year) == (_BOOK["actividad_id"], _BOOK["year"])
    facts = request.facts.to_domain(actividad_id=request.actividad_id, year=request.year)
    assert facts.decision_id == made[name]["request"]["facts"]["decision_id"]
    assert [item.role.value for item in facts.decision_evidence] == ["authority_reconciliation"]
    assert "fingerprint" not in json.dumps(made[name]["request"])


def test_a_closing_value_from_a_count_carries_the_count_and_both_its_files(made: dict[str, dict[str, Any]]) -> None:
    request = _closing(made["closing_counted"])
    count = request.facts.physical_count

    assert count is not None
    assert count.closing_value.decimal == "410"
    assert count.valuation_basis.value == "fifo_acquisition_price"
    assert [item.role.value for item in count.evidence] == ["physical_count", "acquisition_price_valuation"]
    assert _closing(made["closing_derived"]).facts.physical_count is None


def test_a_prior_closing_file_is_stated_as_the_backend_kept_it(made: dict[str, dict[str, Any]]) -> None:
    prior = _closing(made["closing_with_prior_file"]).facts.prior_evidence

    assert [item.reference.reference for item in prior] == [f"document-{_mark('2')}"]
    assert [item.content_digest for item in prior] == [_mark("2")]
    assert _closing(made["closing_derived"]).facts.prior_evidence == ()


def test_a_closing_value_keeps_the_reference_it_was_given(
    made: dict[str, dict[str, Any]],
) -> None:
    request = _closing(made["closing_derived"])

    assert request.facts.decision_id == "decision-1"
    assert "decided_at" not in type(request.facts).model_fields


@pytest.mark.parametrize(
    ("name", "missing"),
    [
        ("closing_count_missing_a_file", "count:acquisition_price_valuation:file"),
        ("closing_with_nothing", "authority"),
    ],
)
def test_an_incomplete_closing_value_makes_no_request_and_says_what_is_missing(
    made: dict[str, dict[str, Any]], name: str, missing: str
) -> None:
    assert made[name]["request"] is None
    assert missing in made[name]["missing"]


def test_the_request_that_has_the_backend_keep_a_file_decodes_once_the_host_names_the_folder(
    made: dict[str, dict[str, Any]], tmp_path: Path
) -> None:
    sent = made["evidence"]["request"]

    assert sent == {"source_path": "file-0123456789abcdef"}
    request = InventoryEvidenceAddRequest.model_validate_json(
        json.dumps({"profile_id": str(uuid4()), "source_directory": str(tmp_path), **sent})
    )
    assert request.source_path == "file-0123456789abcdef"


# ---- What the backend answers when a file is chosen, and what it serves of a kept one -----


def _stored(character: str) -> dict[str, Any]:
    digest = _mark(character)
    return InventoryEvidenceAddProjection(
        outcome="stored", profile_id=uuid4(), reference=f"document-{digest}", content_digest=digest
    ).model_dump(mode="json")


def _refused() -> dict[str, Any]:
    return InventoryEvidenceAddProjection(
        outcome="refused",
        profile_id=uuid4(),
        refusal=InventoryRefusalProjection(
            code="REFUSED_INVENTORY_SERVICE_INPUT",
            reason="evidence_file_not_admitted",
            reason_key=inventory_refusal_key("evidence_file_not_admitted"),
        ),
    ).model_dump(mode="json")


def test_a_kept_file_becomes_a_proof_and_a_refused_one_does_not(tmp_path: Path) -> None:
    done = _run(
        _bundle(tmp_path),
        [
            {"id": "stored", "kind": "evidence_result", "result": _stored("a"), "fileName": "factura.pdf"},
            {"id": "refused", "kind": "evidence_result", "result": _refused(), "fileName": "nota.docx"},
            {"id": "roles", "kind": "roles"},
        ],
    )

    assert done["stored"]["request"] == {
        "reference": f"document-{_mark('a')}",
        "kind": "",
        "digest": _mark("a"),
        "fileName": "factura.pdf",
    }
    assert done["refused"]["request"] is None
    # The refusal names its sentence by the key the backend serves, which the catalogue words.
    refusal = _refused()["refusal"]
    assert refusal["reason_key"] == "application.inventory.service.errors.evidence_file_not_admitted"
    assert refusal["reason_facts"] == []


def test_the_roles_the_options_serve_are_the_ones_the_forms_read(tmp_path: Path) -> None:
    roles = _run(_bundle(tmp_path), [{"id": "roles", "kind": "roles"}])["roles"]["request"]

    assert roles == {
        "cost_check": "attributable_cost_review",
        "iva_check": "iva_recoverability_review",
        "count_authority": "physical_observation",
        "purchase": "purchase",
    }
    served = {
        (family["family"], option["value"]): option["role"]
        for family in _options()["families"]
        for option in family["options"]
    }
    assert {value for (family, value), role in served.items() if role is not None} == set(roles.values())
    assert served[("movement_kind", "purchase")] == "purchase"


def test_a_purchase_as_inspect_serves_it_shows_the_names_of_the_files_it_knows(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    first = _run(bundle, [scenario for scenario in _SCENARIOS if scenario["id"] == "purchase"])
    request = _movement(first["purchase"])
    assert request.acquisition_cost is not None
    acquisition = request.acquisition_cost.to_domain()
    record = MovementRecord.from_purchase_acquisition(
        movement_id=request.movement_id,
        movement_date=request.movement_date,
        quantity=Decimal(request.quantity.decimal),
        acquisition_cost=acquisition,
    )
    invoice = next(item for item in acquisition.evidence if item.evidence_kind.value == "purchase_invoice")
    served = InventoryMovementProjection.from_movement(
        record, with_acquisition_detail=True, document_file_names={str(invoice.content_digest): "factura.pdf"}
    ).model_dump(mode="json")

    names = _run(bundle, [{"id": "names", "kind": "kept_names", "movement": served}])["names"]["request"]

    # Only the invoice is named; the checks have no name and read as kept.
    assert names == {"price": "factura.pdf", "cost_check": None, "iva_check": None}
    assert all(document["file_name"] in (None, "factura.pdf") for document in served["acquisition_detail"]["documents"])
