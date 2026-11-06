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

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.errors import RegistryError
from ....domain.renta.actividad_asset.disposal import ActivityAssetDisposal, ActivityAssetDisposalReason
from ....domain.renta.actividad_asset.election import DirectEstimationRegime
from ....domain.renta.actividad_asset.errors import ActividadAssetError
from ....domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from ....domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from ....domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from ....domain.transactions.models import Transaction
from ...calculations.actividad_asset_schedule import forecast_activity_asset_charge
from ..activity_asset_read_models import (
    NO_TABLE_MINIMUM_REASON_KEY,
    OPENING_REMEDY_REASON_KEYS,
    ActivityAssetFormOptionsView,
    ActivityAssetListRow,
    remedy_field_key,
)
from ..disposal_calculation import project_disposal_calculation
from ..fact_wording import timeline_field_paths
from ..operation_dtos import (
    ActivityAssetCorrectionRevisionSnapshot,
    ActivityAssetRevisionSnapshot,
)
from ..operations import ActivityAssetOperations
from ..register_reads import TABLE_BOUND_METHODS, register_years
from ..schedule_walk import NOT_APPLICABLE_ABSENCES
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
#: The day after each Modelo 130 quarter's last day, as a month and a day of the tax year.
_QUARTER_BOUNDARIES: Final = ((4, 1), (7, 1), (10, 1), (1, 1))


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: a scenario file is a JSON object")
    return value


CREATIONS: Final = SCENARIO / "creations.json"
_FRAMES: Final = frozenset({"scenario.json", CREATIONS.name})
PAYMENT_PREFIX: Final = "ledger-payment:"


def committed_scenario() -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """The scenario's frame and its elements, in file-name order."""
    elements = tuple(_read(path) for path in sorted(SCENARIO.glob("*.json")) if path.name not in _FRAMES)
    for element in elements:
        if element["asset_id"] + ".json" not in {path.name for path in SCENARIO.glob("*.json")}:
            raise ValueError(f"{element['asset_id']}: an element's file is named after it")
    return _read(SCENARIO / "scenario.json"), elements


def committed_creations() -> tuple[dict[str, Any], ...]:
    """The elements the window's new-element form makes, each with its draft and its request.

    The draft is the one a person types over the corpus's shared base; the request
    is what the form's own builders make of it. A ledger payment is named by the
    provider the scenario calls it by, since the identifier the ledger mints for
    it is content-derived and moves whenever the payment's facts move.
    """
    corpus = _read(CREATIONS)
    base = corpus["base"]
    made = tuple({**item, "draft": {**base, **item["draft"]}} for item in corpus["creations"])
    names = [item["id"] for item in made]
    if len(set(names)) != len(names):
        raise ValueError("a creation is committed twice under one name")
    return made


def resolved_payments(value: Any, payments: dict[str, str]) -> Any:
    """Name every payment a committed creation refers to by the identifier the ledger minted.

    Args:
        value: Committed creation data, at any depth.
        payments: The ledger's identifier for each provider the scenario names.

    Returns:
        The same data with every ``ledger-payment:<provider>`` replaced.
    """
    if isinstance(value, dict):
        return {name: resolved_payments(item, payments) for name, item in value.items()}
    if isinstance(value, list):
        return [resolved_payments(item, payments) for item in value]
    if isinstance(value, str) and value.startswith(PAYMENT_PREFIX):
        provider = value.removeprefix(PAYMENT_PREFIX)
        if provider not in payments:
            raise ValueError(f"{provider}: no payment of the scenario is named so")
        return payments[provider]
    return value


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
        input_classification=facts.get("input_classification"),
        purchase_invoice_evidence_id=facts.get("purchase_invoice_evidence_id"),
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
) -> tuple[ActivityAssetOperations, date, tuple[dict[str, Any], ...]]:
    """Replay every element's steps into a fresh register standing on the scenario's day.

    Returns:
        The register, the day it stands on, and every ledger payment it was given
        under the name the scenario calls it by, owned or loose.
    """
    today = date.fromisoformat(frame["today"])
    owned = {element["asset_id"]: _payment(element["asset_id"], element["purchase"]) for element in elements}
    loose = {payment["provider_id"]: _payment(payment["provider_id"], payment) for payment in frame["payments"]}
    repository = MemoryRepository()
    operations = ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(*owned.values(), *loose.values()),
        forecast_operation=_published_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime(frame["modality"]),
        register_authority=memory_register_authority(today=today),
    )
    for element in elements:
        _replay_element(operations, repository, element, owned[element["asset_id"]].transaction_id)
    payments = tuple(
        {
            "provider_id": provider_id,
            "asset_id": asset_id,
            "transaction_id": row.transaction_id,
            "description": row.raw.description,
        }
        for asset_id, provider_id, row in (
            *((element_id, element_id, row) for element_id, row in owned.items()),
            *((None, provider_id, row) for provider_id, row in loose.items()),
        )
    )
    return operations, today, payments


def _dump(value: Any) -> Any:
    if isinstance(value, tuple | list):
        return [_dump(item) for item in value]
    return value.model_dump(mode="json")


def _asked_spans(row: dict[str, Any]) -> tuple[tuple[date, date], ...]:
    """Every span the window can ask a charge for out of one plan row.

    A dotación covers a span the plan leaves open. The Modelo 130 handoff asks
    for the part of such a span that falls inside a quarter, so each open span
    is also asked for clipped at each quarter's boundary. The quarters come from
    the periods the registry serves; the charge of every span is the register's.
    """
    asked: set[tuple[date, date]] = set()
    for interval in row["claimable_intervals"]:
        start = date.fromisoformat(interval["covered_from"])
        end = date.fromisoformat(interval["covered_until"])
        asked.add((start, end))
        for month, day in _QUARTER_BOUNDARIES:
            boundary = date(row["tax_year"], month, day) if month > 1 else date(row["tax_year"] + 1, 1, 1)
            if start < boundary < end:
                asked.add((start, boundary))
    return tuple(sorted(asked))


def _forecasts(operations: ActivityAssetOperations, asset_id: str, plan: list[dict[str, Any]]) -> dict[str, Any]:
    offered: dict[str, Any] = {}
    for row in plan:
        for start, end in _asked_spans(row):
            try:
                charge = operations.forecast(asset_id=asset_id, covered_from=start, covered_until=end)
            except ActividadAssetError:
                continue
            offered[f"{start.isoformat()}/{end.isoformat()}"] = charge.model_dump(mode="json")
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


def _creation(frame: dict[str, Any], elements: tuple[dict[str, Any], ...], made: dict[str, Any]) -> dict[str, Any]:
    """What the register answers for one creation the window's form makes.

    Each creation is replayed into a register of its own, standing on the
    scenario's day with the scenario's elements and payments, so one creation
    never sees another and the element it makes is numbered as the only new one.
    """
    operations, today, payments = replayed_register(frame, elements)
    named = {item["provider_id"]: item["transaction_id"] for item in payments}
    revision = resolved_payments({**made["revision"], "asset_id": made["id"]}, named)
    descriptor = resolved_payments(made["descriptor"], named)
    snapshot = ActivityAssetRevisionSnapshot.model_validate_json(json.dumps(revision))
    operations.create(
        snapshot.to_domain(),
        ActivityAssetDescriptorFacts.model_validate(descriptor),
        recorded_at=datetime.combine(today, datetime.min.time()),
        origin=_ORIGIN_CREATE,
    )
    row = next(item for item in operations.list_elements() if item.asset_id == made["id"])
    return {"id": made["id"], "draft": made["draft"], "list": row.model_dump(mode="json")} | _element(
        operations, made["id"], today
    )


def recorded_candidates(operations: ActivityAssetOperations) -> tuple[Any, ...]:
    """The payments the register offers, read under a pinned generation.

    Reading a payment's non-deductible IVA resolves the art. 106 input vocabulary,
    which refuses an unpinned scope the way the operation host pins one.
    """
    with bundled_indexed_authority().operation():
        return operations.acquisition_candidates()


def _answered_years(rows: tuple[ActivityAssetListRow, ...], documents: dict[str, dict[str, Any]]) -> tuple[int, ...]:
    """Every tax year the register answers for, projected years included.

    The register reads a projected year as well as an authored one, and a form
    asks the options of any year its plan reaches, so the recording spans both
    axes of the list row and every year a recorded plan names. Recording only
    the readable years left the projected ones refused by the window's fixtures.
    """
    answered = {year for row in rows for year in (*row.years, *row.projected_years)}
    answered.update(row["tax_year"] for element in documents.values() for row in element["rows"])
    return tuple(sorted(answered))


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
    operations, today, payments = replayed_register(frame, elements)
    rows = operations.list_elements()
    years = register_years(rows)
    documents = {row.asset_id: _element(operations, row.asset_id, today) for row in rows}
    register = {
        "_note": NOTE,
        "today": today.isoformat(),
        "list": _dump(rows),
        "years": list(years),
        "default_year": operations.default_register_year(years),
        "candidates": _dump(recorded_candidates(operations)),
        "payments": list(payments),
        "form_options": _form_options(operations, _answered_years(rows, documents)),
        "vocabulary": {
            "table_bound_methods": sorted(method.value for method in TABLE_BOUND_METHODS),
            "timeline_fact_paths": list(timeline_field_paths()),
            "not_applicable_absences": sorted(absence.value for absence in NOT_APPLICABLE_ABSENCES),
            "remedy_field_keys": {key: remedy_field_key(key) for key in sorted(OPENING_REMEDY_REASON_KEYS)},
            "no_table_minimum_key": NO_TABLE_MINIMUM_REASON_KEY,
        },
    }
    register["creations"] = [_creation(frame, elements, made) for made in committed_creations()]
    return {"register": register, **{name: {"_note": NOTE, **element} for name, element in documents.items()}}
