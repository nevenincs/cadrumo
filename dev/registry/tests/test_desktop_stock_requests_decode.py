"""The requests the desktop Stock panel makes decode against the backend's own request contracts.

The frontend builds each stock book and movement request from what a person types and attaches,
through its form fields and request builders. The test runs those builders as they ship, on typed
drafts, and decodes the result with the request models the registered inventory operations
validate, then builds the domain operand a purchase becomes inside the worker, so a field the form
states at the wrong place, or a fact it cannot state, fails here and not in the window.
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

from cadrumo.application.inventory.registered_requests import (
    InventoryCreateRequest,
    InventoryMovementAddRequest,
)
from cadrumo.application.inventory.service import InventoryMovementCommand
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


#: The files a purchase rests on, by slot.
_PROOFS = {
    "price": {"kind": "purchase_invoice", "digest": _mark("a")},
    "cost_check": {"digest": _mark("b")},
    "iva_check": {"digest": _mark("c")},
}

#: A purchase of 100 units for 1000.00 with 210.00 of IVA, all of it deductible, and nothing else.
_PURCHASE = {
    "date": "2026-03-04",
    "kind": "purchase",
    "quantity": "100",
    "price": "1000.00",
    "iva": "210.00",
    "share": "100",
    "extra_total": "0",
    "recoverable": "210.00",
    "unrecoverable": "0",
    "total": "1000.00",
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
        "values": {**_PURCHASE, "extra_total": "100", "recoverable": "231", "total": "1100"},
        "proofs": _PROOFS,
        "extras": [
            {
                "kind": "freight",
                "price": "100.00",
                "iva": "21.00",
                "share": "100",
                "proof": {"kind": "transport_document", "digest": _mark("d")},
            },
        ],
    },
    {
        # Half of that freight's IVA deductible: 10.50 is deducted and 10.50 added to the cost,
        # and two costs make two files.
        "id": "purchase_with_two_costs",
        "kind": "movement",
        "book": _BOOK,
        "values": {
            **_PURCHASE,
            "extra_total": "140",
            "recoverable": "220.5",
            "unrecoverable": "10.5",
            "total": "1150.5",
        },
        "proofs": _PROOFS,
        "extras": [
            {
                "kind": "freight",
                "price": "100.00",
                "iva": "21.00",
                "share": "50",
                "proof": {"kind": "transport_document", "digest": _mark("d")},
            },
            {
                "kind": "insurance",
                "price": "40.00",
                "iva": "0.00",
                "share": "100",
                "proof": {"kind": "insurance_document", "digest": _mark("e")},
            },
        ],
    },
    {
        # The person's own figures, which the backend refuses and the form does not judge.
        "id": "purchase_totals_disagree",
        "kind": "movement",
        "book": _BOOK,
        "values": {**_PURCHASE, "total": "1234.00"},
        "proofs": _PROOFS,
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
        "id": "nothing_typed",
        "kind": "movement",
        "book": _BOOK,
        "values": {},
    },
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


def _run(bundle: Path, scenarios: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    done = subprocess.run(  # noqa: S603 - fixed node program on a bundle built above
        [_node(), str(bundle)],
        input=json.dumps(scenarios),
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
    assert Decimal(two.attributable_cost_components[0].deductible_iva_ratio.decimal) == Decimal("0.5")
    assert Decimal(two.total_acquisition_cost.decimal) == Decimal("1150.5")
    # One file per proof, each under a reference of its own.
    references = [item.reference.reference for item in two.evidence]
    assert len(references) == len(set(references)) == 5
    assert {item.evidence_kind.value for item in two.evidence} == {
        "purchase_invoice",
        "transport_document",
        "insurance_document",
        "attributable_cost_review",
        "iva_recoverability_review",
    }


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


def test_totals_that_disagree_with_the_figures_are_the_backends_to_refuse(
    made: dict[str, dict[str, Any]],
) -> None:
    request = _movement(made["purchase_totals_disagree"])

    assert request.acquisition_cost is not None
    with pytest.raises(ValueError, match="total_acquisition_cost"):
        request.acquisition_cost.to_domain()


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
