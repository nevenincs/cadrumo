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
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.actividad_asset.activity_asset_contracts import (
    ActivityAssetCorrectRequest,
    ActivityAssetCreateRequest,
    ActivityAssetFilingHandoffRequest,
    ActivityAssetForecastRequest,
)
from cadrumo.application.actividad_asset.activity_asset_read_models import (
    ActivityAssetBasisStageOption,
    ActivityAssetConditionOption,
    ActivityAssetOpeningStatusOption,
    activity_asset_label_key,
)
from cadrumo.application.actividad_asset.fact_wording import token_family
from cadrumo.application.actividad_asset.history import ActivityAssetHistory
from cadrumo.application.actividad_asset.operation_dtos import (
    ActivityAssetDisposalSnapshot,
    ActivityAssetRevisionSnapshot,
)
from cadrumo.application.actividad_asset.register_reads import method_facts_view
from cadrumo.application.ledger.entry_limits import ledger_entry_limits
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.tipos_actividad import TipoActividad
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.renta.actividad_asset.disposal import (
    ADMITTED_DISPOSAL_REASONS,
    ActivityAssetDisposal,
    ActivityAssetDisposalReason,
)
from cadrumo.domain.renta.actividad_asset.election import ACQUIRED_CONDITION_FACTS, AmortizationMethod
from cadrumo.domain.renta.actividad_asset.election_facts import method_is_statable
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    BASIS_STAGE_FACTS,
    FURTHER_ACQUISITION_SHAPES,
    OPENING_STATUS_FACTS,
    REGISTERABLE_ACQUISITION_SHAPES,
    AcquisitionShape,
    AssetBasisStage,
)
from cadrumo.domain.renta.actividad_asset.vehicle_affectation import VehicleCategory, VehiclePrivateUse
from dev.paths import REPO_ROOT

from .desktop_asset_payments import CANDIDATE, LATER_PAYMENT
from .desktop_request_support import bundle, run

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon


def _on(month: int, day: int, *, years_back: int = 0) -> date:
    return date(_YEAR - years_back, month, day)


_REVISIONS = REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos" / "100" / "revisions"

_NEW = {
    "asset_kind": "material",
    "name": "Sierra de cinta",
    "serial_number": "SC-0412",
    "acquisition_shape": "primary_purchase",
    "in_service_date": _on(6, 15).isoformat(),
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
    "linear_elected_coefficient": {"amortization.linear_coefficient": "0.1"},
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
    "opening_amount_known": {"opening_amount": "500.00", "opening_through": str(_YEAR), "opening_method": "linear"},
    "opening_missing": {"opening_status": "missing", "opening_amount": ""},
    "taxpayer_owned_basis": {"basis_stage": "taxpayer_owned", "business_use_share": "0.6"},
    "constant_percentage": {"method": "constant_percentage", "amortization.linear_coefficient": "0.1"},
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
    "date": _on(2, 1).isoformat(),
    "whole": "8",
    "flag": "yes",
    "amount": "1000.00",
    "share": "10",
    "decimal": "16",
}

#: A table class the registry classes as able to hold a vehicle, which the form asks a declaration of.
_VEHICLE_CLASS = {"amortization.authority_class_key": "transporte-externo"}

_VEHICLE = {
    **_VEHICLE_CLASS,
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
    "ownership_share": "1",
    "office_area": "30",
    "total_area": "100",
}

_OUTSIDE = {
    "acquisition_shape": "acquired_outside_ledger",
    "declared_acquisition_date": _on(11, 5, years_back=2).isoformat(),
    "declared_activity": "A05",
    "acquisition_reference": f"Factura {_YEAR - 2}-118",
}

_OUTSIDE_WITH_LATER_PAYMENT: dict[str, str] = {
    **_OUTSIDE,
    "further_purchase": str(LATER_PAYMENT["transaction_id"]),
    "further_shape": "split_payment",
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
    "outside_ledger_with_later_payment": _OUTSIDE_WITH_LATER_PAYMENT,
    "whole_property_sole": _PROPERTY,
    "whole_property_fractional": {
        **_PROPERTY,
        "ownership_mode": "fractional_direct",
        "ownership_share": "0.5",
    },
    "vehicle": _VEHICLE,
    "multi_shift_hours": {"amortization.shift_hours_per_day": "16"},
}

#: Each correction changes what the person edits in the revision of the linear creation.
_CORRECT: dict[str, dict[str, str]] = {
    "basis": {"basis_amount": "1000.00"},
    "in_service_date": {"in_service_date": _on(7, 1).isoformat()},
    "stage": {"basis_stage": "taxpayer_owned", "business_use_share": "0.75"},
    "method_with_class_kept": {"method": "constant_percentage", "amortization.linear_coefficient": "0.1"},
    "opening": {"opening_amount": "300.00", "opening_through": str(_YEAR), "opening_method": "linear"},
    "elected_coefficient": {"amortization.linear_coefficient": "0.09"},
    "vehicle_declaration": _VEHICLE,
    "shift_hours": {"amortization.shift_hours_per_day": "16"},
    "residual_value": {"residual_value": "10.00"},
}


def _served() -> dict[str, Any]:
    """What the backend serves with the options of a form: the shapes, activities and each method's facts."""
    methods = _offered_methods()
    return {
        "methods": [method.value for method in methods],
        "method_facts": [json.loads(method_facts_view(method).model_dump_json()) for method in methods],
        "acquisition_shapes": [shape.value for shape in REGISTERABLE_ACQUISITION_SHAPES],
        "declared_activities": [activity.value for activity in TipoActividad],
        "disposal_reasons": [
            {
                "reason": reason.value,
                "label_key": activity_asset_label_key(token_family(ActivityAssetDisposalReason), reason),
            }
            for reason in ADMITTED_DISPOSAL_REASONS
        ],
        "basis_stages": [
            json.loads(
                ActivityAssetBasisStageOption(
                    stage=stage, facts=facts, is_property=stage is AssetBasisStage.WHOLE_PROPERTY
                ).model_dump_json()
            )
            for stage, facts in BASIS_STAGE_FACTS.items()
        ],
        "opening_statuses": [
            json.loads(ActivityAssetOpeningStatusOption(status=status, facts=facts).model_dump_json())
            for status, facts in OPENING_STATUS_FACTS.items()
        ],
        "acquired_conditions": [
            json.loads(ActivityAssetConditionOption(condition=condition, facts=facts).model_dump_json())
            for condition, facts in ACQUIRED_CONDITION_FACTS.items()
        ],
        "further_acquisition_shapes": [shape.value for shape in FURTHER_ACQUISITION_SHAPES],
        # The Modelo 130 periods come from the published registry, which no request builder reads.
        "m130_periods": [],
    }


def _run(bundle: Path, scenarios: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return run(
        bundle,
        scenarios,
        served=_served(),
        limits=json.loads(ledger_entry_limits().model_dump_json()),
        candidates=[CANDIDATE, LATER_PAYMENT],
    )


def _decode_create(made: dict[str, Any]) -> ActivityAssetCreateRequest:
    assert made["problems"] == {}, made["problems"]
    assert made["request"] is not None, "the form made no request from a complete draft"
    return ActivityAssetCreateRequest.model_validate_json(json.dumps({"profile_id": str(uuid4()), **made["request"]}))


@pytest.fixture(scope="module")
def created(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, dict[str, Any]]]:
    built = bundle(tmp_path_factory.mktemp("asset-requests"))
    drafts = {**_CREATE, **_METHODS, **_STATED}
    scenarios = [{"id": name, "kind": "create", "draft": {**_NEW, **changes}} for name, changes in drafts.items()]
    return built, _run(built, scenarios)


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
    assert opening.opening_history.covered_through_tax_year == _YEAR
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
    # The request states no number and always states its baja; the backend numbers the revision.
    assert "revision_number" not in result["request"]["revision"]
    assert "disposal" in result["request"]["revision"]
    assert request.revision.revision_number is None
    second = request.revision.to_domain(revision_number=first.revision_number + 1)
    assert second.revision_number == 2
    assert second.supersedes_revision_id == first.revision_id
    assert [claim.supersedes_claim_id for claim in request.superseding_claims] == [claim_id]
    ActivityAssetHistory().append_revision(first).append_revision(second)


def test_a_correct_request_that_leaves_its_baja_out_is_refused_and_null_removes_it(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    first = _decode_create(created[1]["linear"]).revision.to_domain()
    base = {
        "revision": ActivityAssetRevisionSnapshot.from_domain(first).model_dump(mode="json"),
        "revision_id": first.revision_id,
    }
    result = _run(
        created[0],
        [{"id": "residual", "kind": "correct", "base": base, "changes": _CORRECT["residual_value"], "supersede": []}],
    )["residual"]
    sent = json.loads(json.dumps({"profile_id": str(uuid4()), **result["request"]}))
    assert sent["revision"]["disposal"] is None
    ActivityAssetCorrectRequest.model_validate_json(json.dumps(sent))

    del sent["revision"]["disposal"]
    with pytest.raises(ValidationError, match="disposal"):
        ActivityAssetCorrectRequest.model_validate_json(json.dumps(sent))


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
    assert revision.acquisition.invoice_evidence_id == f"Factura {_YEAR - 2}-118"
    assert revision.further_acquisitions == ()
    assert revision.declared_acquisition_date == _on(11, 5, years_back=2)
    assert revision.declared_activity == TipoActividad("A05")
    ledger = created[1]["linear"]["request"]["revision"]
    assert ledger["acquisition"]["observed_transaction_id"] is not None
    assert "declared_activity" not in ledger


def test_an_element_bought_outside_the_ledger_can_own_a_later_ledger_payment(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    revision = _revision_of(created[1], "outside_ledger_with_later_payment")

    assert revision.acquisition_shape is AcquisitionShape.ACQUIRED_OUTSIDE_LEDGER
    assert revision.acquisition.observed_transaction_id is None
    (later,) = revision.further_acquisitions
    assert later.shape is AcquisitionShape.SPLIT_PAYMENT
    assert later.lineage.observed_transaction_id == LATER_PAYMENT["transaction_id"]
    assert later.lineage.invoice_evidence_id == ""
    assert later.lineage.evidence_fingerprint is None
    assert revision.acquisition_transaction_ids == (LATER_PAYMENT["transaction_id"],)


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
    disposal_date=_on(9, 30),
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
    corrected = request.revision.to_domain(revision_number=chain["current"].revision_number + 1)

    assert corrected.disposal == _SALE
    assert corrected.out_of_service_date == _SALE.boundary
    assert corrected.basis.basis_amount == Decimal("1000.00")
    ActivityAssetHistory().append_revision(chain["first"]).append_revision(chain["current"]).append_revision(corrected)


def test_a_baja_is_changed_by_stating_another_and_removed_by_stating_none(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    chain = _chain(created, disposal=_SALE)
    moved = ActivityAssetDisposal(
        disposal_date=_on(6, 30),
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
        return request.revision.to_domain(revision_number=chain["current"].revision_number + 1)

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
    # The fixture is drawn against the options the backend serves for a kind and
    # a year, so it holds the facts of the methods those options offer. A method
    # no form can state, or one the options enrol for no kind, is never drawn.
    drawn = {item["method"] for item in fixture["facts"]}
    backend = {
        method.value: json.loads(method_facts_view(method).model_dump_json())["facts"]
        for method in _offered_methods()
        if method.value in drawn
    }

    assert drawn, "the fixture draws no method"
    assert drawn <= {method.value for method in _offered_methods()}

    assert {item["method"]: item["facts"] for item in fixture["facts"]} == backend
    assert fixture["shapes"] == [shape.value for shape in REGISTERABLE_ACQUISITION_SHAPES]
    assert fixture["activities"] == [activity.value for activity in TipoActividad]


def _forecast(made: dict[str, Any]) -> ActivityAssetForecastRequest:
    assert made["request"] is not None, "the form made no forecast request from a complete span"
    return ActivityAssetForecastRequest.model_validate_json(json.dumps({"profile_id": str(uuid4()), **made["request"]}))


def test_a_forecast_the_form_makes_states_the_last_day_covered_and_decodes_to_the_boundary_after_it(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    made = _run(
        created[0],
        [
            {
                "id": "half",
                "kind": "forecast",
                "draft": {"covered_from": _on(1, 1).isoformat(), "covered_through": _on(6, 30).isoformat()},
                "supersedes": None,
            },
            {
                "id": "incomplete",
                "kind": "forecast",
                "draft": {"covered_from": _on(1, 1).isoformat()},
                "supersedes": None,
            },
        ],
    )

    sent = made["half"]["request"]
    assert "covered_until" not in sent
    assert sent["covered_through"] == _on(6, 30).isoformat()
    decoded = _forecast(made["half"])
    assert decoded.covered_through == _on(6, 30)
    assert decoded.exclusive_end() == _on(7, 1)
    assert made["incomplete"]["request"] is None


def test_a_handoff_for_a_year_alone_sends_no_modelo_130_period_and_a_chosen_quarter_sends_it(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    made = _run(
        created[0],
        [
            {"id": "year", "kind": "handoff", "year": _YEAR, "period": ""},
            {"id": "quarter", "kind": "handoff", "year": _YEAR, "period": "2T"},
        ],
    )

    assert made["year"]["request"] == {"tax_year": _YEAR, "output_language": "es"}
    alone = ActivityAssetFilingHandoffRequest.model_validate_json(
        json.dumps({"profile_id": str(uuid4()), **made["year"]["request"]}),
    )
    chosen = ActivityAssetFilingHandoffRequest.model_validate_json(
        json.dumps({"profile_id": str(uuid4()), **made["quarter"]["request"]}),
    )
    assert alone.m130_period is None
    assert chosen.m130_period == "2T"
    assert chosen.output_language is OutputLanguage.ES


def test_the_reasons_a_baja_form_offers_are_the_ones_the_backend_serves_each_worded_by_its_key(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    served = _served()["disposal_reasons"]
    made = _run(
        created[0],
        [
            {"id": "material", "kind": "baja_fields", "asset_kind": "material"},
            {"id": "intangible", "kind": "baja_fields", "asset_kind": "intangible"},
        ],
    )

    assert served
    assert [item["reason"] for item in served] == [reason.value for reason in ADMITTED_DISPOSAL_REASONS]
    assert ActivityAssetDisposalReason.DONATION.value not in {item["reason"] for item in served}
    for name in ("material", "intangible"):
        assert made[name]["reasons"] == served


def _registry_vehicle_classes() -> dict[str, bool]:
    """The registry's own classification of the classes a material element can be a restricted vehicle in."""
    import tomllib

    (owner,) = (
        path
        for path in sorted(_REVISIONS.glob("*/parameters/0001-declarations.toml"))
        if "clase-vehiculo-restringido" in path.read_text(encoding="utf-8")
    )
    document = tomllib.loads(owner.read_text(encoding="utf-8"))
    parameters = {
        parameter["id"]: parameter for parameter in document["revisions"][owner.parent.parent.name]["parameters"]
    }
    prefix = "renta-actividad-inmovilizado-amortizacion-"
    flags = {
        entry["key"]: entry["value"] == "1"
        for entry in parameters[f"{prefix}clase-vehiculo-restringido"]["keyed_brackets"]
    }
    admits = {
        entry["key"]: entry["value"] == "1" for entry in parameters[f"{prefix}clase-admite-material"]["keyed_brackets"]
    }
    tabled = {entry["key"] for entry in parameters[f"{prefix}normal-coeficiente-lineal-maximo"]["keyed_brackets"]}
    return {key: flag for key, flag in flags.items() if admits.get(key, False) and key in tabled}


def test_the_vehicle_declaration_is_stated_only_for_a_class_that_requires_one_and_never_asked_as_a_question(
    created: tuple[Path, dict[str, dict[str, Any]]],
) -> None:
    expected = _registry_vehicle_classes()
    made = _run(
        created[0],
        [
            {"id": "material", "kind": "vehicle_fields", "asset_kind": "material"},
            {"id": "intangible", "kind": "vehicle_fields", "asset_kind": "intangible"},
        ],
    )

    assert any(expected.values()), "no class can hold a vehicle, so nothing was compared"
    assert not all(expected.values())
    assert made["material"]["drawn"] == expected
    assert not any(made["intangible"]["drawn"].values())
