"""Contract tests for the pure installed-workbench generation assembler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ...domain.user_profile.values import ProfileSetupState, UserProfileRecord
from .. import workbench_generation as generation_module
from ..aeat_sync.workspace import AeatSyncWorkspaceProjectionV1
from ..ledger.workspace import LedgerWorkspaceProjectionV1
from ..modelo.declarations_calendar import DeclarationsCalendarProjectionV1
from ..modelo.declarations_workspace import DeclarationsWorkspaceProjectionV1
from ..modelo.workspace_models import ModeloWorkspaceProjectionV1
from ..overview.calendar_models import OverviewCalendar, OverviewCalendarRange
from ..overview.home import (
    HomeAccountSession,
    HomeAvailability,
    HomeProjectionInput,
    HomeSessionPosture,
    HomeZoneState,
)
from ..overview.tests.calendar_test_support import modelo_record
from ..search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from ..workbench_generation import (
    CallableWorkbenchGenerationReadDoorV1,
    InstalledWorkbenchGenerationProviderV1,
    SecureProfileWorkbenchGenerationReadDoorV1,
    WorkbenchGenerationAvailability,
    WorkbenchGenerationInputsV1,
    WorkbenchGenerationSourceResultV1,
    assemble_workbench_generation,
    assemble_workbench_generation_from,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 9, 3, 10, 30, tzinfo=UTC)
_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


@dataclass
class _Repository[ValueT]:
    value: ValueT
    revisions: tuple[str, ...] = ("revision-1",)
    calls: int = 0

    def load(self, *_args: object) -> ValueT:
        self.calls += 1
        return self.value

    def load_revisioned(self) -> tuple[ValueT, str]:
        self.calls += 1
        index = min(self.calls - 1, len(self.revisions) - 1)
        return self.value, self.revisions[index]


def _home_input() -> HomeProjectionInput:
    """Return a safe Home input with every optional source explicitly absent."""

    def zone(name: str) -> HomeZoneState:
        return HomeZoneState(
            availability=HomeAvailability.NEVER_CAPTURED,
            reason_code=f"source.{name}",
        )

    return HomeProjectionInput(
        generated_at=_NOW,
        account=HomeAccountSession(posture=HomeSessionPosture.NO_PROFILE),
        actions_state=zone("actions"),
        declarations_state=zone("declarations"),
        ledger_state=zone("ledger"),
        agenda_state=zone("agenda"),
        agenda_evidence_state=zone("agenda_evidence"),
        messages_state=zone("messages"),
    )


def _admission(
    destination: str,
    state: WorkbenchDestinationAdmissionState = WorkbenchDestinationAdmissionState.NEVER_CAPTURED,
) -> WorkbenchDestinationAdmission:
    """Return a route admission matching its source-capture state."""
    return WorkbenchDestinationAdmission(
        destination=destination,
        state=state,
        reason_code=None if state is WorkbenchDestinationAdmissionState.AVAILABLE else f"{destination}.not_captured",
    )


def _inputs(
    *,
    ledger: WorkbenchGenerationSourceResultV1[LedgerWorkspaceProjectionV1] | None = None,
    declarations: WorkbenchGenerationSourceResultV1[DeclarationsWorkspaceProjectionV1] | None = None,
    declarations_calendar: WorkbenchGenerationSourceResultV1[DeclarationsCalendarProjectionV1] | None = None,
    aeat_sync: WorkbenchGenerationSourceResultV1[AeatSyncWorkspaceProjectionV1] | None = None,
    modelo: WorkbenchGenerationSourceResultV1[tuple[ModeloWorkspaceProjectionV1, ...]] | None = None,
) -> WorkbenchGenerationInputsV1:
    """Build the typed input bundle using only explicit missing source results."""
    ledger_result = ledger or WorkbenchGenerationSourceResultV1.never_captured(refusal="source.ledger")
    declarations_result = declarations or WorkbenchGenerationSourceResultV1.never_captured(
        refusal="source.declarations"
    )
    aeat_sync_result = aeat_sync or WorkbenchGenerationSourceResultV1.never_captured(refusal="source.aeat_sync")
    return WorkbenchGenerationInputsV1(
        assembled_at=_NOW,
        home=WorkbenchGenerationSourceResultV1.available(_home_input(), observed_at=_NOW),
        ledger=ledger_result,
        declarations=declarations_result,
        declarations_calendar=declarations_calendar
        or WorkbenchGenerationSourceResultV1.never_captured(refusal="source.declarations_calendar"),
        aeat_sync=aeat_sync_result,
        modelo=modelo or WorkbenchGenerationSourceResultV1.never_captured(refusal="source.modelo"),
        ledger_admission=_admission(
            "workbench.ledger", WorkbenchDestinationAdmissionState(ledger_result.availability.value)
        ),
        declarations_admission=_admission(
            "workbench.declarations", WorkbenchDestinationAdmissionState(declarations_result.availability.value)
        ),
        aeat_sync_admission=_admission(
            "workbench.aeat_sync", WorkbenchDestinationAdmissionState(aeat_sync_result.availability.value)
        ),
    )


def test_source_result_rejects_confident_absence_and_preserves_known_empty() -> None:
    """An observed empty collection is distinct from a source never read."""
    known_empty = WorkbenchGenerationSourceResultV1[tuple[int, ...]].available((), observed_at=_NOW)
    never_captured = WorkbenchGenerationSourceResultV1[tuple[int, ...]].never_captured(refusal="source.never")

    assert known_empty.value == ()
    assert known_empty.availability is WorkbenchGenerationAvailability.AVAILABLE
    assert never_captured.value is None
    assert never_captured.availability is WorkbenchGenerationAvailability.NEVER_CAPTURED
    with pytest.raises(ValidationError, match="requires a value"):
        WorkbenchGenerationSourceResultV1[tuple[int, ...]](
            availability=WorkbenchGenerationAvailability.AVAILABLE,
            observed_at=_NOW,
        )


def test_generation_inputs_reject_admission_source_contradictions() -> None:
    """A route cannot claim availability that its defining source does not have."""
    payload = _inputs().model_dump()
    payload["ledger_admission"] = _admission(
        "workbench.ledger", WorkbenchDestinationAdmissionState.AVAILABLE
    ).model_dump()
    with pytest.raises(ValidationError, match=r"workbench\.ledger admission must match"):
        WorkbenchGenerationInputsV1.model_validate(payload)


def test_secure_profile_provider_brackets_repository_capture_and_refuses_missing_loaders() -> None:
    """The production door verifies real local authorities without fake fixtures."""

    profile = _Repository(UserProfileRecord(profile_id=_PROFILE_ID, setup_state=ProfileSetupState.INCOMPLETE))
    work_units = _Repository(WorkUnitCatalogue())
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())

    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        profile_repository=cast(Any, profile),
        work_unit_repository=cast(Any, work_units),
        calculation_repository=cast(Any, revisions),
        filing_repository=cast(Any, filings),
        clock=lambda: _NOW,
        account_session_reader=lambda: HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE,
            profile_label="Perfil local",
            expires_at=_NOW,
        ),
    )

    generation = InstalledWorkbenchGenerationProviderV1(door)()

    assert profile.calls == 2
    assert work_units.calls == 2
    assert revisions.calls == 2
    assert filings.calls == 2
    assert generation.declarations.projection is not None
    assert generation.declarations_calendar.projection is not None
    assert generation.declarations_calendar.projection.sources[0].availability is HomeAvailability.UNAVAILABLE
    assert (
        generation.declarations_calendar.projection.sources[0].reason_code
        == "workbench.calendar.taxpayer_model_undeclared"
    )
    assert generation.ledger.availability is WorkbenchGenerationAvailability.UNAVAILABLE
    assert generation.aeat_sync.availability is WorkbenchGenerationAvailability.UNAVAILABLE
    assert generation.modelo.availability is WorkbenchGenerationAvailability.UNAVAILABLE
    assert generation.search.availability is WorkbenchGenerationAvailability.UNAVAILABLE


def test_secure_profile_provider_refuses_a_generation_changed_during_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cross-repository capture is never published after a revision changes."""
    profile = _Repository(UserProfileRecord(profile_id=_PROFILE_ID, setup_state=ProfileSetupState.INCOMPLETE))
    work_units = _Repository(WorkUnitCatalogue(), revisions=("work-1", "work-2"))
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())

    def empty_calendar(_profile: object, calendar_range: object, **_kwargs: object) -> OverviewCalendar:
        return OverviewCalendar(range=calendar_range, entries=(), generated_at=_NOW)  # type: ignore[arg-type]

    monkeypatch.setattr(generation_module, "build_overview_calendar", empty_calendar)
    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        profile_repository=cast(Any, profile),
        work_unit_repository=cast(Any, work_units),
        calculation_repository=cast(Any, revisions),
        filing_repository=cast(Any, filings),
        clock=lambda: _NOW,
        account_session_reader=lambda: HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE,
            profile_label="Perfil local",
            expires_at=_NOW,
        ),
    )

    with pytest.raises(RuntimeError, match="changed during capture"):
        door.read_workbench_generation_inputs()


def _synthetic_transaction() -> object:
    """One real, wholly invented ledger row.

    Real because the guard compares canonical catalogues and a stand-in would
    not survive validation; invented because a review of the guard must never
    depend on an operator's actual ledger.
    """
    from decimal import Decimal

    from ...domain.transactions.enums import TransactionDirection
    from ...domain.transactions.models import Transaction
    from ...domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

    raw = RawTransaction(
        provider_transaction_id="row-capture-guard",
        booked_date=date(2026, 3, 1),
        value_date=date(2026, 3, 1),
        amount=Decimal("50.00"),
        currency="EUR",
        counterparty="Synthetic SL",
        description="synthetic row",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"Concepto": "synthetic row"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "group_label": None,
        }
    )


class _ChangingLedgerStore:
    """A store whose second read differs from its first.

    The ledger repositories expose no revision handle the way the work-unit,
    calculation and filing catalogues do, so the guard compares the catalogues
    themselves. Returning a different one on the re-read is the mid-capture
    write it exists to catch, and the only way to show it is not comparing a
    value with itself.
    """

    def __init__(self, first: object, second: object) -> None:
        self._reads = [first, second]
        self.bucket_id = _PROFILE_ID

    def load(self) -> object:
        return self._reads.pop(0) if len(self._reads) > 1 else self._reads[0]


class _StableStore:
    """A store that answers the same catalogue however often it is asked."""

    def __init__(self, value: object) -> None:
        self._value = value
        self.bucket_id = _PROFILE_ID

    def load(self) -> object:
        return self._value


def test_secure_profile_provider_refuses_a_ledger_written_during_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ledger write between the two reads refuses the whole generation.

    The guard was total when it was written; it stopped being so when Ledger
    arrived, because the door began reading two stores it never re-checked. A
    generation could then carry a Ledger snapshot from a different instant
    than its Declarations with nothing to detect it.
    """
    from ...domain.invoices.models import InvoiceCatalogue
    from ...domain.transactions.models import TransactionCatalogue

    profile = _Repository(UserProfileRecord(profile_id=_PROFILE_ID, setup_state=ProfileSetupState.INCOMPLETE))
    work_units = _Repository(WorkUnitCatalogue())
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())

    def empty_calendar(_profile: object, calendar_range: object, **_kwargs: object) -> OverviewCalendar:
        return OverviewCalendar(range=calendar_range, entries=(), generated_at=_NOW)  # type: ignore[arg-type]

    monkeypatch.setattr(generation_module, "build_overview_calendar", empty_calendar)
    written = TransactionCatalogue.model_validate([_synthetic_transaction()])
    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        profile_repository=cast(Any, profile),
        work_unit_repository=cast(Any, work_units),
        calculation_repository=cast(Any, revisions),
        filing_repository=cast(Any, filings),
        clock=lambda: _NOW,
        account_session_reader=lambda: HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE,
            profile_label="Perfil local",
            expires_at=_NOW,
        ),
        transaction_repository=cast(Any, _ChangingLedgerStore(TransactionCatalogue(), written)),
        invoice_repository=cast(Any, _StableStore(InvoiceCatalogue())),
    )

    with pytest.raises(RuntimeError, match="changed during capture"):
        door.read_workbench_generation_inputs()


def test_a_quiet_ledger_publishes_its_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard must not refuse a capture nothing wrote during."""
    from ...domain.invoices.models import InvoiceCatalogue
    from ...domain.transactions.models import TransactionCatalogue

    profile = _Repository(UserProfileRecord(profile_id=_PROFILE_ID, setup_state=ProfileSetupState.INCOMPLETE))
    work_units = _Repository(WorkUnitCatalogue())
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())

    def empty_calendar(_profile: object, calendar_range: object, **_kwargs: object) -> OverviewCalendar:
        return OverviewCalendar(range=calendar_range, entries=(), generated_at=_NOW)  # type: ignore[arg-type]

    monkeypatch.setattr(generation_module, "build_overview_calendar", empty_calendar)
    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        profile_repository=cast(Any, profile),
        work_unit_repository=cast(Any, work_units),
        calculation_repository=cast(Any, revisions),
        filing_repository=cast(Any, filings),
        clock=lambda: _NOW,
        account_session_reader=lambda: HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE,
            profile_label="Perfil local",
            expires_at=_NOW,
        ),
        transaction_repository=cast(Any, _StableStore(TransactionCatalogue())),
        invoice_repository=cast(Any, _StableStore(InvoiceCatalogue())),
    )

    inputs = door.read_workbench_generation_inputs()

    assert inputs.ledger.value is not None


def test_calendar_evidence_scope_preserves_available_empty_for_historical_filing() -> None:
    """A prior-year filing is outside the query, not orphaned or never captured."""
    historical = modelo_record()
    schedule = OverviewCalendar(
        range=OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
        entries=(),
        generated_at=_NOW,
    )

    scoped = generation_module._scope_filing_records((historical,), schedule)

    assert scoped == ()


def test_generation_projects_home_and_never_turns_missing_areas_into_empty() -> None:
    """Missing production loaders remain explicit refusals in every output area."""
    generation = assemble_workbench_generation(_inputs())

    assert generation.home.projection is not None
    assert generation.home.availability is WorkbenchGenerationAvailability.AVAILABLE
    assert generation.ledger.projection is None
    assert generation.declarations.projection is None
    assert generation.declarations_calendar.projection is None
    assert generation.aeat_sync.projection is None
    assert generation.modelo.projection is None
    assert generation.search.projection is None
    assert generation.search.availability is WorkbenchGenerationAvailability.NEVER_CAPTURED
    assert generation.search.refusal == "source.ledger"


def test_generation_search_refusal_preserves_mixed_source_unavailability() -> None:
    """A single unavailable source prevents a falsely empty search snapshot."""
    generation = assemble_workbench_generation(
        _inputs(aeat_sync=WorkbenchGenerationSourceResultV1.unavailable(refusal="source.aeat_down"))
    )

    assert generation.search.projection is None
    assert generation.search.availability is WorkbenchGenerationAvailability.UNAVAILABLE
    assert generation.search.refusal == "source.ledger"


def test_generation_accepts_stale_value_without_collapsing_it_to_available() -> None:
    """A stale preloaded value remains available to the caller as stale evidence."""
    stale = WorkbenchGenerationSourceResultV1[tuple[int, ...]].stale(
        (1, 2),
        observed_at=_NOW,
        refusal="source.stale",
    )

    assert stale.value == (1, 2)
    assert stale.availability is WorkbenchGenerationAvailability.STALE
    assert stale.refusal == "source.stale"


def test_input_admissions_must_name_the_installed_search_destinations() -> None:
    """Search cannot be assembled against a different destination authority."""
    values = _inputs().model_dump()
    values["declarations_admission"] = _admission("workbench.ledger")
    with pytest.raises(ValidationError, match=r"workbench\.declarations"):
        WorkbenchGenerationInputsV1.model_validate(values)


def test_read_door_is_injected_and_invoked_once() -> None:
    """The application boundary reads one caller-owned bundle exactly once."""
    calls = 0
    inputs = _inputs()

    def read() -> WorkbenchGenerationInputsV1:
        nonlocal calls
        calls += 1
        return inputs

    generation = assemble_workbench_generation_from(CallableWorkbenchGenerationReadDoorV1(read))

    assert calls == 1
    assert generation.assembled_at == _NOW


def test_output_has_no_source_value_field_or_input_wrapper() -> None:
    """Output serialization contains only projection results, never source inputs."""
    generation = assemble_workbench_generation(_inputs())
    payload = generation.model_dump_json()

    assert "value" not in WorkbenchGenerationInputsV1.model_fields
    assert "value" not in type(generation).model_fields
    assert all(
        "value" not in type(getattr(generation, name)).model_fields
        for name in (
            "home",
            "ledger",
            "declarations",
            "declarations_calendar",
            "aeat_sync",
            "modelo",
            "search",
        )
    )
    assert '"value"' not in payload
    assert "WorkbenchGenerationSourceResultV1" not in repr(generation)


def test_source_and_projection_result_models_are_frozen_and_closed() -> None:
    """Both sides reject mutation and undeclared fields at their boundary."""
    source = WorkbenchGenerationSourceResultV1[tuple[int, ...]].never_captured(refusal="source.never")
    with pytest.raises(ValidationError):
        WorkbenchGenerationSourceResultV1[tuple[int, ...]](
            availability=WorkbenchGenerationAvailability.NEVER_CAPTURED,
            refusal="source.never",
            unexpected=True,
        )
    with pytest.raises(ValidationError):
        source.availability = WorkbenchGenerationAvailability.UNAVAILABLE  # type: ignore[misc]


@dataclass(frozen=True)
class _Door:
    """Structural read-door implementation for the protocol contract."""

    inputs: WorkbenchGenerationInputsV1

    def read_workbench_generation_inputs(self) -> WorkbenchGenerationInputsV1:
        return self.inputs


def test_structural_read_door_is_accepted() -> None:
    """Composition accepts a typed protocol implementation without a frontend."""
    generation = assemble_workbench_generation_from(_Door(_inputs()))
    assert generation.home.projection is not None
