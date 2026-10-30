"""The requests the desktop Assets forms make decode against the backend's own request contracts.

The frontend builds each create and correct request from what a person types, through its form
fields and request builders. The test runs those builders as they ship, on typed drafts, and
decodes the result with the request models the registered operations validate, so a field the
form states at the wrong place, or a fact it cannot state, fails here and not in the window.
A correction is built against the revision the create request produced, and chained to it by
the history's own rules. The options the forms are drawn from, the facts of every method the
backend offers among them, come from the backend's own projection, so a method or fact it serves
that a form cannot state fails here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from cadrumo.application.actividad_asset.activity_asset_contracts import (
    ActivityAssetCorrectRequest,
    ActivityAssetCreateRequest,
)
from cadrumo.application.actividad_asset.history import ActivityAssetHistory
from cadrumo.application.actividad_asset.operation_dtos import (
    ActivityAssetDisposalSnapshot,
    ActivityAssetRevisionSnapshot,
)
from cadrumo.application.actividad_asset.register_reads import method_facts_view
from cadrumo.core.tipos_actividad import TipoActividad
from cadrumo.domain.renta.actividad_asset.disposal import ActivityAssetDisposal, ActivityAssetDisposalReason
from cadrumo.domain.renta.actividad_asset.election import AmortizationMethod
from cadrumo.domain.renta.actividad_asset.election_facts import method_is_statable
from cadrumo.domain.renta.actividad_asset.lifecycle import REGISTERABLE_ACQUISITION_SHAPES, AcquisitionShape
from cadrumo.domain.renta.actividad_asset.vehicle_affectation import VehicleCategory, VehiclePrivateUse
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FRONTEND = REPO_ROOT / "native" / "desktop" / "frontend"
_ENTRY = _FRONTEND / "tests" / "support" / "assetRequests.ts"
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

_NEW = {
    "asset_kind": "material",
    "name": "Sierra de cinta",
    "serial_number": "SC-0412",
    "acquisition_shape": "primary_purchase",
    "in_service_date": "2026-06-15",
    "acquired_condition": "new",
    "basis_stage": "business_allocated",
    "basis_amount": "900.00",
    "non_deductible_iva": "0.00",
    "prior_allocation_provenance": "allocation booked in the ledger",
    "opening_status": "known",
    "opening_amount": "0.00",
    "method": "linear",
    "amortization.authority_class_key": "maquinaria",
}

#: Each scenario is the draft a person types, over the common one.
_CREATE: dict[str, dict[str, str]] = {
    "linear": {},
    "linear_elected_coefficient": {"amortization.linear_coefficient": "10"},
    "linear_used_known_price": {
        "acquired_condition": "used",
        "amortization.used_original_price.determination": "known",
        "amortization.used_original_price.original_price": "1500.00",
        "amortization.used_original_price.evidence_reference": "invoice of the seller",
    },
    "linear_used_expert_valuation": {
        "acquired_condition": "used",
        "amortization.used_original_price.determination": "expert_valuation",
        "amortization.used_original_price.original_price": "1500.00",
        "amortization.used_original_price.evidence_reference": "valuation report of the appraiser",
    },
    "opening_amount_known": {"opening_amount": "500.00", "opening_through": "2026", "opening_method": "linear"},
    "opening_missing": {"opening_status": "missing", "opening_amount": ""},
    "taxpayer_owned_basis": {"basis_stage": "taxpayer_owned", "business_use_share": "60"},
    "constant_percentage": {"method": "constant_percentage", "amortization.linear_coefficient": "10"},
    "sum_of_digits": {
        "method": "sum_of_digits",
        "amortization.sum_of_digits_period_years": "8",
        "amortization.digit_order": "descending",
    },
    "low_value_free": {
        "method": "low_value_free",
        "amortization.authority_class_key": "",
        "basis_amount": "250.00",
        "amortization.low_value.election_reference": "election recorded with the purchase",
        "amortization.low_value.new_material_evidence_reference": "purchase invoice",
    },
    "research_development_free": {
        "method": "research_development_free",
        "amortization.authority_class_key": "maquinaria",
        "amortization.research_development_evidence_reference": "technical report",
    },
    "intangible_linear": {"asset_kind": "intangible", "amortization.authority_class_key": "intangible-software"},
    "intangible_goodwill": {
        "asset_kind": "intangible",
        "method": "goodwill",
        "amortization.authority_class_key": "",
    },
}

_STATED_FACTS = {
    "text": "reference-123",
    "date": "2026-02-01",
    "whole": "8",
    "flag": "yes",
    "amount": "1000.00",
    "share": "10",
    "decimal": "16",
}

_VEHICLE = {
    "vehicle_declared": "yes",
    "vehicle_category": "passenger_car",
    "vehicle_private_use": "none",
    "vehicle_in_books": "yes",
    "vehicle_evidence": "Libro registro de bienes de inversión",
    "vehicle_propulsion": "bev",
}

_PROPERTY = {
    "basis_stage": "whole_property",
    "basis_amount": "1000.00",
    "construction_cost": "800.00",
    "land_cost": "200.00",
    "ownership_mode": "sole",
    "ownership_share": "100",
    "office_area": "30",
    "total_area": "100",
}

_OUTSIDE = {
    "acquisition_shape": "acquired_outside_ledger",
    "declared_acquisition_date": "2024-11-05",
    "declared_activity": "A05",
    "acquisition_reference": "Factura 2024-118",
}


def _offered_methods() -> list[AmortizationMethod]:
    """The methods the backend offers: those whose required facts a form can state as single values."""
    return [method for method in AmortizationMethod if method_is_statable(method)]


def _required_facts(method: AmortizationMethod) -> dict[str, str]:
    """A draft that states, for a method, each fact the backend says it requires."""
    draft: dict[str, str] = {"method": method.value, "amortization.authority_class_key": ""}
    for fact in method_facts_view(method).facts:
        if not fact.required:
            continue
        key = "amortization." + ".".join(fact.path)
        draft[key] = {
            "choice": fact.tokens[0] if fact.tokens else "",
            "class": "maquinaria",
        }.get(fact.kind.value) or _STATED_FACTS[fact.kind.value]
    return draft


#: Every method the backend offers, with the facts it requires.
_METHODS: dict[str, dict[str, str]] = {
    f"method_{method.value}": _required_facts(method) for method in _offered_methods()
}

#: Facts the forms could not state, and the way an element comes to the register.
_STATED: dict[str, dict[str, str]] = {
    "outside_ledger": _OUTSIDE,
    "whole_property_sole": _PROPERTY,
    "whole_property_fractional": {
        **_PROPERTY,
        "ownership_mode": "fractional_direct",
        "ownership_share": "50",
    },
    "vehicle": _VEHICLE,
    "multi_shift_hours": {"amortization.shift_hours_per_day": "16"},
}

#: Each correction changes what the person edits in the revision of the linear creation.
_CORRECT: dict[str, dict[str, str]] = {
    "basis": {"basis_amount": "1000.00"},
    "in_service_date": {"in_service_date": "2026-07-01"},
    "stage": {"basis_stage": "taxpayer_owned", "business_use_share": "75"},
    "method_with_class_kept": {"method": "constant_percentage", "amortization.linear_coefficient": "10"},
    "opening": {"opening_amount": "300.00", "opening_through": "2026", "opening_method": "linear"},
    "elected_coefficient": {"amortization.linear_coefficient": "9"},
    "vehicle_declared": _VEHICLE,
    "shift_hours": {"amortization.shift_hours_per_day": "16"},
    "residual_value": {"residual_value": "10.00"},
}


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        raise AssertionError("node is needed to run the desktop request builders, and was not found")
    return node


def _bundle(tmp_path: Path) -> Path:
    esbuild = _FRONTEND / "node_modules" / "esbuild"
    assert esbuild.is_dir(), f"the desktop frontend's dependencies are not installed under {_FRONTEND}"
    out = tmp_path / "assetRequests.cjs"
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


def _served() -> dict[str, Any]:
    """What the backend serves with the options of a form: the shapes, activities and each method's facts."""
    methods = _offered_methods()
    return {
        "methods": [method.value for method in methods],
        "method_facts": [json.loads(method_facts_view(method).model_dump_json()) for method in methods],
        "acquisition_shapes": [shape.value for shape in REGISTERABLE_ACQUISITION_SHAPES],
        "declared_activities": [activity.value for activity in TipoActividad],
    }


def _run(bundle: Path, scenarios: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    done = subprocess.run(  # noqa: S603 - fixed node program on a bundle built above
        [_node(), str(bundle)],
        input=json.dumps({"served": _served(), "scenarios": scenarios}),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        creationflags=_NO_WINDOW,
    )
    return {item["id"]: item for item in json.loads(done.stdout)}


def _decode_create(made: dict[str, Any]) -> ActivityAssetCreateRequest:
    assert made["problems"] == {}, made["problems"]
    assert made["request"] is not None, "the form made no request from a complete draft"
    return ActivityAssetCreateRequest.model_validate_json(json.dumps({"profile_id": str(uuid4()), **made["request"]}))


@pytest.fixture(scope="module")
def created(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, dict[str, Any]]]:
    bundle = _bundle(tmp_path_factory.mktemp("asset-requests"))
    drafts = {**_CREATE, **_METHODS, **_STATED}
    scenarios = [{"id": name, "kind": "create", "draft": {**_NEW, **changes}} for name, changes in drafts.items()]
    return bundle, _run(bundle, scenarios)


@pytest.mark.parametrize("name", sorted({**_CREATE, **_METHODS, **_STATED}))
def test_a_create_request_the_form_makes_decodes_against_the_backend_contract(
    created: tuple[Path, dict[str, dict[str, Any]]], name: str
) -> None:
    request = _decode_create(created[1][name])

    revision = request.revision.to_domain()
    assert revision.revision_number == 1
    assert revision.asset_id == created[1][name]["request"]["revision"]["asset_id"]
    assert request.descriptor.name == "Sierra de cinta"
    assert len(revision.revision_id) == 64


def test_the_facts_the_form_states_reach_the_revision_where_the_backend_reads_them(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    used = _decode_create(created[1]["linear_used_expert_valuation"]).revision.to_domain()
    owned = _decode_create(created[1]["taxpayer_owned_basis"]).revision.to_domain()
    opening = _decode_create(created[1]["opening_amount_known"]).revision.to_domain()
    digits = _decode_create(created[1]["sum_of_digits"]).revision.to_domain()
    elected = _decode_create(created[1]["linear_elected_coefficient"]).revision.to_domain()

    assert used.amortization.used_original_price is not None
    assert used.amortization.used_original_price.determination.value == "expert_valuation"
    assert used.amortization.used_original_price.original_price == Decimal("1500.00")
    assert owned.basis.business_use_share is not None
    assert owned.basis.business_use_share == Decimal("0.6")
    assert opening.opening_history.covered_through_tax_year == 2026
    assert opening.opening_history.accumulated_amount == Decimal("500.00")
    assert digits.amortization.sum_of_digits_period_years == 8
    assert digits.amortization.digit_order is not None
    assert elected.amortization.linear_coefficient == Decimal("0.1")


@pytest.mark.parametrize("name", sorted(_CORRECT))
def test_a_correct_request_the_form_makes_decodes_and_chains_to_the_revision_it_supersedes(
    created: tuple[Path, dict[str, dict[str, Any]]], name: str
) -> None:
    bundle, made = created
    first = _decode_create(made["linear"]).revision.to_domain()
    base = {
        "revision": ActivityAssetRevisionSnapshot.from_domain(first).model_dump(mode="json"),
        "revision_id": first.revision_id,
    }
    claim_id = "e" * 64
    result = _run(
        bundle,
        [
            {
                "id": name,
                "kind": "correct",
                "base": base,
                "changes": _CORRECT[name],
                "supersede": [claim_id],
            },
        ],
    )[name]
    assert result["problems"] == {}, result["problems"]
    assert result["request"] is not None

    request = ActivityAssetCorrectRequest.model_validate_json(
        json.dumps({"profile_id": str(uuid4()), **result["request"]}),
    )
    second = request.revision.to_domain()
    assert second.revision_number == 2
    assert second.supersedes_revision_id == first.revision_id
    assert [claim.supersedes_claim_id for claim in request.superseding_claims] == [claim_id]
    ActivityAssetHistory().append_revision(first).append_revision(second)


def _revision_of(made: dict[str, Any], name: str) -> Any:
    return _decode_create(made[name]).revision.to_domain()


def test_every_method_the_backend_offers_is_stated_by_the_form_with_the_facts_it_requires(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    for method in _offered_methods():
        revision = _revision_of(created[1], f"method_{method.value}")
        assert revision.amortization.method is method
        for fact in method_facts_view(method).facts:
            if not fact.required:
                continue
            stated: Any = revision.amortization
            for step in fact.path:
                stated = getattr(stated, step)
            assert stated is not None, (method.value, fact.path)


def test_an_element_bought_outside_the_ledger_names_its_document_date_and_activity_and_no_purchase(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    revision = _revision_of(created[1], "outside_ledger")

    assert revision.acquisition_shape is AcquisitionShape.ACQUIRED_OUTSIDE_LEDGER
    assert revision.acquisition.observed_transaction_id is None
    assert revision.acquisition.observed_lineage_event_id is None
    assert revision.acquisition.evidence_fingerprint is None
    assert revision.acquisition.invoice_evidence_id == "Factura 2024-118"
    assert revision.further_acquisitions == ()
    assert revision.declared_acquisition_date == date(2024, 11, 5)
    assert revision.declared_activity == TipoActividad("A05")
    ledger = created[1]["linear"]["request"]["revision"]
    assert ledger["acquisition"]["observed_transaction_id"] is not None
    assert "declared_activity" not in ledger


def test_a_whole_property_and_a_vehicle_and_the_hours_of_a_shift_reach_the_revision(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    sole = _revision_of(created[1], "whole_property_sole").basis
    shared = _revision_of(created[1], "whole_property_fractional").basis
    driven = _revision_of(created[1], "vehicle").vehicle_affectation
    hours = _revision_of(created[1], "multi_shift_hours").amortization.shift_hours_per_day

    assert sole.is_property is True
    assert (sole.construction_cost, sole.land_cost) == (Decimal("800.00"), Decimal("200.00"))
    assert sole.ownership_share == Decimal("1")
    assert (sole.office_area, sole.total_area) == (Decimal("30"), Decimal("100"))
    assert shared.ownership_share == Decimal("0.5")
    assert driven is not None
    assert driven.category is VehicleCategory.PASSENGER_CAR
    assert driven.private_use is VehiclePrivateUse.NONE
    assert driven.recorded_in_activity_books is True
    assert driven.electric_propulsion is not None
    assert hours == Decimal("16")
    assert _revision_of(created[1], "linear").basis.is_property is False
    assert _revision_of(created[1], "linear").vehicle_affectation is None


def _chain(
    created: tuple[Path, dict[str, dict[str, Any]]], *, disposal: ActivityAssetDisposal | None = None
) -> dict[str, Any]:
    """The base a correction stands on: the linear creation, with a baja when one is given."""
    first = _decode_create(created[1]["linear"]).revision.to_domain()
    current = first.with_disposal(disposal) if disposal is not None else first
    return {
        "first": first,
        "current": current,
        "base": {
            "revision": ActivityAssetRevisionSnapshot.from_domain(current).model_dump(mode="json"),
            "revision_id": current.revision_id,
        },
    }


_SALE = ActivityAssetDisposal(
    disposal_date=date(2026, 9, 30),
    reason=ActivityAssetDisposalReason.SALE,
    proceeds=Decimal("500.00"),
    transmission_costs=Decimal("10.00"),
)


def test_a_correction_of_an_element_with_a_baja_keeps_the_baja(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    chain = _chain(created, disposal=_SALE)
    result = _run(
        created[0],
        [
            {
                "id": "kept",
                "kind": "correct",
                "base": chain["base"],
                "changes": {"basis_amount": "1000.00"},
                "supersede": [],
            },
        ],
    )["kept"]
    assert result["problems"] == {}
    request = ActivityAssetCorrectRequest.model_validate_json(
        json.dumps({"profile_id": str(uuid4()), **result["request"]}),
    )
    corrected = request.revision.to_domain()

    assert corrected.disposal == _SALE
    assert corrected.out_of_service_date == _SALE.boundary
    assert corrected.basis.basis_amount == Decimal("1000.00")
    ActivityAssetHistory().append_revision(chain["first"]).append_revision(chain["current"]).append_revision(corrected)


def test_a_baja_is_changed_by_stating_another_and_removed_by_stating_none(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    chain = _chain(created, disposal=_SALE)
    moved = ActivityAssetDisposal(
        disposal_date=date(2026, 6, 30),
        reason=ActivityAssetDisposalReason.SALE,
        proceeds=Decimal("500.00"),
        transmission_costs=Decimal("10.00"),
    )
    made = _run(
        created[0],
        [
            {
                "id": "change",
                "kind": "baja",
                "base": chain["base"],
                "disposal": json.loads(ActivityAssetDisposalSnapshot.from_domain(moved).model_dump_json()),
            },
            {"id": "removal", "kind": "baja", "base": chain["base"], "disposal": None},
        ],
    )

    def decoded(name: str) -> Any:
        request = ActivityAssetCorrectRequest.model_validate_json(
            json.dumps({"profile_id": str(uuid4()), **made[name]["request"]}),
        )
        assert request.superseding_claims == ()
        return request.revision.to_domain()

    changed = decoded("change")
    removed = decoded("removal")
    assert changed.disposal == moved
    assert changed.out_of_service_date == moved.boundary
    assert removed.disposal is None
    assert removed.out_of_service_date is None
    for revision in (changed, removed):
        assert revision.supersedes_revision_id == chain["current"].revision_id
        ActivityAssetHistory().append_revision(chain["first"]).append_revision(chain["current"]).append_revision(
            revision
        )


def test_the_fixture_the_forms_are_drawn_against_serves_what_the_backend_serves(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    fixture = _run(created[0], [{"id": "fixture", "kind": "fixture"}])["fixture"]
    backend = {
        method.value: json.loads(method_facts_view(method).model_dump_json())["facts"] for method in AmortizationMethod
    }

    assert {item["method"]: item["facts"] for item in fixture["facts"]} == backend
    assert fixture["shapes"] == [shape.value for shape in REGISTERABLE_ACQUISITION_SHAPES]
    assert fixture["activities"] == [activity.value for activity in TipoActividad]
