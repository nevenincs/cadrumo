"""The scenario register the desktop's Assets fixtures show, replayed through the real register.

The window holds no register figure of its own: its fixtures read each element's list
row, plan, limits, advisories, history, revisions, forecasts and baja figures from a
recording of what the register answers. The scenario's facts are committed under
``dev/fixtures/assets-register-scenario``: the day the scenario stands on, the ledger
payments no element owns, and one file per element with its purchase and the steps
recorded against it (creation, claims, corrections), each at its own time. The
producer and the test both replay them here through :class:`ActivityAssetOperations`
over the published authority, so every figure is the register's.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    NO_TABLE_MINIMUM_REASON_KEY,
    OPENING_REMEDY_REASON_KEYS,
    ActivityAssetFormOptionsView,
    remedy_field_key,
)
from cadrumo.application.actividad_asset.disposal_calculation import project_disposal_calculation
from cadrumo.application.actividad_asset.fact_wording import timeline_field_paths
from cadrumo.application.actividad_asset.operation_dtos import (
    ActivityAssetCorrectionRevisionSnapshot,
    ActivityAssetRevisionSnapshot,
)
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.application.actividad_asset.register_reads import register_years
from cadrumo.application.actividad_asset.schedule_walk import NOT_APPLICABLE_ABSENCES
from cadrumo.application.calculations.actividad_asset_schedule import forecast_activity_asset_charge
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.renta.actividad_asset.disposal import ActivityAssetDisposal, ActivityAssetDisposalReason
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetError
from cadrumo.domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from cadrumo.domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from cadrumo.domain.transactions.models import Transaction

from .ledger_support import MemoryLedger, acquisition_transaction
from .register_support import MemoryRepository, memory_register_authority

_REPOSITORY: Final = Path(__file__).resolve().parents[5]
SCENARIO: Final = _REPOSITORY / "dev/fixtures/assets-register-scenario"
NOTE: Final = (
    "What the activity-asset register answers for the scenario register the Assets fixtures show: each "
    "element's list row, plan, limits, advisories, history, revisions, forecasts and baja figures, and the "
    "register's years, payments and form options. Written by scripts/assets_register.py from "
    "dev/fixtures/assets-register-scenario."
)
_ORIGIN_CREATE: Final = "ledger.actividad-asset.create"
_ORIGIN_CLAIM: Final = "ledger.actividad-asset.claim"
_ORIGIN_CORRECT: Final = "ledger.actividad-asset.correct"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: a scenario file is a JSON object")
    return value


def committed_scenario() -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """The scenario's frame and its elements, in file-name order."""
    elements = tuple(_read(path) for path in sorted(SCENARIO.glob("*.json")) if path.name != "scenario.json")
    for element in elements:
        if element["asset_id"] + ".json" not in {path.name for path in SCENARIO.glob("*.json")}:
            raise ValueError(f"{element['asset_id']}: an element's file is named after it")
    return _read(SCENARIO / "scenario.json"), elements


def _payment(provider_id: str, facts: dict[str, Any]) -> Transaction:
    base = facts.get("taxable_base")
    iva = facts.get("iva_amount")
    if "amount" in facts:
        amount = Decimal(facts["amount"])
    elif base is not None and iva is not None:
        amount = Decimal(base) + Decimal(iva)
    else:
        raise ValueError(f"{provider_id}: a payment states its amount, or its base and its IVA")
    return acquisition_transaction(
        provider_id=provider_id,
        amount=amount,
        taxable_base=None if base is None else Decimal(base),
        iva_amount=None if iva is None else Decimal(iva),
        currency=facts.get("currency", "EUR"),
        booked_date=date.fromisoformat(facts["booked_date"]),
        description=facts.get("description", provider_id),
    )


def _published_forecast(
    revision: ActivityAssetRevision,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None = None,
) -> ScheduledAmortizationCharge:
    with bundled_indexed_authority().operation() as operation:
        return forecast_activity_asset_charge(
            revision,
            modelo_100_revision=operation.revision_for_context("100", filing_year=covered_from.year, period="0A"),
            authority_generation=operation.pin().logical_generation,
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            taxpayer_workforce=lambda: (),
            legal_reference=operation.legal_reference,
            requested_free_amount=requested_free_amount,
        )


def _revision(asset_id: str, stated: dict[str, Any], *, transaction_id: str, supersedes: str | None) -> dict[str, Any]:
    acquisition = {**stated["acquisition"], "observed_transaction_id": transaction_id}
    return {**stated, "asset_id": asset_id, "acquisition": acquisition, "supersedes_revision_id": supersedes}


def _append_undescribed(repository: MemoryRepository, revision: ActivityAssetRevision, at: datetime) -> None:
    """Record an element as one kept before elements carried a description: its revision alone."""
    repository.apply(lambda history: history.append_revision(revision, recorded_at=at, origin=_ORIGIN_CREATE))


def _replay_element(
    operations: ActivityAssetOperations,
    repository: MemoryRepository,
    element: dict[str, Any],
    transaction_id: str,
) -> None:
    asset_id = element["asset_id"]
    for step in element["steps"]:
        at = datetime.fromisoformat(step["recorded_at"])
        if "revision" in step:
            snapshot = ActivityAssetRevisionSnapshot.model_validate_json(
                json.dumps(_revision(asset_id, step["revision"], transaction_id=transaction_id, supersedes=None))
            )
            if "create" in step:
                operations.create(
                    snapshot.to_domain(),
                    ActivityAssetDescriptorFacts.model_validate(step["create"]),
                    recorded_at=at,
                    origin=_ORIGIN_CREATE,
                )
            else:
                _append_undescribed(repository, snapshot.to_domain(), at)
        elif "claim" in step:
            claim = step["claim"]
            free = claim.get("requested_free_amount")
            covered_from = date.fromisoformat(claim["covered_from"])
            through = date.fromisoformat(claim["covered_through"])
            forecast = operations.forecast(
                asset_id=asset_id,
                covered_from=covered_from,
                covered_until=date.fromordinal(through.toordinal() + 1),
                requested_free_amount=None if free is None else Decimal(free),
            )
            operations.record_claim(forecast, creating_operation=_ORIGIN_CLAIM, recorded_at=at)
        elif "correct" in step:
            current = operations.inspect(asset_id)[-1]
            snapshot = ActivityAssetCorrectionRevisionSnapshot.model_validate_json(
                json.dumps(
                    _revision(asset_id, step["correct"], transaction_id=transaction_id, supersedes=current.revision_id)
                )
            )
            operations.correct(snapshot.to_domain(), recorded_at=at, origin=_ORIGIN_CORRECT)
        else:
            raise ValueError(f"{asset_id}: a step creates, claims or corrects")


def replayed_register(
    frame: dict[str, Any], elements: tuple[dict[str, Any], ...]
) -> tuple[ActivityAssetOperations, date]:
    """Replay every element's steps into a fresh register standing on the scenario's day."""
    today = date.fromisoformat(frame["today"])
    owned = {element["asset_id"]: _payment(element["asset_id"], element["purchase"]) for element in elements}
    loose = tuple(_payment(payment["provider_id"], payment) for payment in frame["payments"])
    repository = MemoryRepository()
    operations = ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(*owned.values(), *loose),
        forecast_operation=_published_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime(frame["modality"]),
        register_authority=memory_register_authority(today=today),
    )
    for element in elements:
        _replay_element(operations, repository, element, owned[element["asset_id"]].transaction_id)
    return operations, today


def _dump(value: Any) -> Any:
    if isinstance(value, tuple | list):
        return [_dump(item) for item in value]
    return value.model_dump(mode="json")


def _forecasts(operations: ActivityAssetOperations, asset_id: str, plan: list[dict[str, Any]]) -> dict[str, Any]:
    offered: dict[str, Any] = {}
    for row in plan:
        for interval in row["claimable_intervals"]:
            key = f"{interval['covered_from']}/{interval['covered_until']}"
            try:
                charge = operations.forecast(
                    asset_id=asset_id,
                    covered_from=date.fromisoformat(interval["covered_from"]),
                    covered_until=date.fromisoformat(interval["covered_until"]),
                )
            except ActividadAssetError:
                continue
            offered[key] = charge.model_dump(mode="json")
    return offered


def _disposal(operations: ActivityAssetOperations, asset_id: str, today: date) -> dict[str, Any] | None:
    recorded = operations.inspect(asset_id)[-1].disposal
    stated = (
        None
        if recorded is not None
        else ActivityAssetDisposal(
            disposal_date=today,
            reason=ActivityAssetDisposalReason.SALE,
            proceeds=Decimal("0"),
            transmission_costs=Decimal("0"),
        )
    )
    try:
        disposal, calculation = operations.disposal_calculation(asset_id, stated)
    except ActividadAssetError:
        return None
    return project_disposal_calculation(disposal, calculation).model_dump(mode="json")


def _element(operations: ActivityAssetOperations, asset_id: str, today: date) -> dict[str, Any]:
    plan = _dump(operations.plan(asset_id))
    return {
        "rows": plan,
        "limits": operations.plan_limits(asset_id).model_dump(mode="json"),
        "advisories": _dump(operations.plan_advisories(asset_id)),
        "events": _dump(operations.timeline(asset_id)),
        "revisions": [
            {
                "revision": ActivityAssetRevisionSnapshot.from_domain(revision).model_dump(mode="json"),
                "revision_id": revision.revision_id,
            }
            for revision in operations.inspect(asset_id)
        ],
        "forecasts": _forecasts(operations, asset_id, plan),
        "disposal": _disposal(operations, asset_id, today),
    }


def _form_options(operations: ActivityAssetOperations, years: tuple[int, ...]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for kind in AssetKind:
        for year in years:
            try:
                view: ActivityAssetFormOptionsView = operations.form_options(asset_kind=kind, tax_year=year)
            except RegistryError:
                continue
            options.append({"asset_kind": kind.value, "tax_year": year, "options": view.model_dump(mode="json")})
    return options


def recording(frame: dict[str, Any], elements: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    """What the register answers for the scenario, one document for the register and one per element."""
    operations, today = replayed_register(frame, elements)
    rows = operations.list_elements()
    years = register_years(rows)
    register = {
        "_note": NOTE,
        "today": today.isoformat(),
        "list": _dump(rows),
        "years": list(years),
        "default_year": operations.default_register_year(years),
        "candidates": _dump(operations.acquisition_candidates()),
        "form_options": _form_options(operations, years),
        "vocabulary": {
            "timeline_fact_paths": list(timeline_field_paths()),
            "not_applicable_absences": sorted(absence.value for absence in NOT_APPLICABLE_ABSENCES),
            "remedy_field_keys": {key: remedy_field_key(key) for key in sorted(OPENING_REMEDY_REASON_KEYS)},
            "no_table_minimum_key": NO_TABLE_MINIMUM_REASON_KEY,
        },
    }
    documents = {"register": register}
    for row in rows:
        documents[row.asset_id] = {"_note": NOTE, **_element(operations, row.asset_id, today)}
    return documents
