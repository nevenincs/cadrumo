"""Contract tests for the pure installed-workbench generation assembler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ...core.period import Period
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ...domain.user_profile.values import ProfileSetupState, UserProfileRecord
from .. import workbench_generation as generation_module
from ..aeat_sync.workspace import AeatSyncWorkspaceProjectionV1
from ..ledger.workspace import (
    LedgerWorkspaceArea,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceProjectionV1,
    LedgerWorkspaceSource,
    LedgerWorkspaceStatus,
)
from ..modelo.declarations_calendar import DeclarationsCalendarProjectionV1
from ..modelo.declarations_workspace import DeclarationsWorkspaceProjectionV1
from ..modelo.workspace_models import ModeloWorkspaceProjectionV1
from ..overview.calendar_models import OverviewCalendar, OverviewCalendarRange
from ..overview.home import (
    HomeAccountSession,
    HomeAvailability,
    HomeDeclarationState,
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

def _ledger_projection_with_statuses(
    status: LedgerWorkspaceStatus,
    *,
    unmeasured: LedgerWorkspaceArea | None = None,
) -> LedgerWorkspaceProjectionV1:
    """A Ledger projection whose areas carry a chosen status, one optionally unmeasured."""
    return LedgerWorkspaceProjectionV1(
        bucket_id="bucket",
        areas=tuple(
            LedgerWorkspaceAreaStateV1(
                area=area,
                sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
                status=LedgerWorkspaceStatus.UNMEASURED if area is unmeasured else status,
                item_count=2,
            )
            for area in LedgerWorkspaceArea
        ),
        entries=(),
        review_transaction_ids=(),
        invoice_reconciliations=(),
        link_inconsistencies=(),
        affected_declarations=(),
    )


def test_home_refuses_its_ledger_zone_rather_than_publishing_an_unmeasured_zero() -> None:
    """An unmeasured Ledger area must not reach Home as the number nought.

    `LedgerWorkspaceAreaStateV1.item_count` is a plain integer, so an area that
    nobody measured reports 0 -- the same value a genuinely empty area reports.
    The Ledger workspace keeps them apart through `status`, rendering
    UNMEASURED as "Sin medir" rather than a digit. Home has no such room: its
    readiness block is four bare numbers, and a zero there reads as a finding.

    So the whole block refuses when ANY of its four areas is unmeasured, rather
    than publishing three real counts beside one fabricated one. Partial truth
    in a summary is indistinguishable from whole truth once rendered.
    """
    from ..overview.home import HomeLedgerReadiness
    from ..workbench_generation import _home_ledger_readiness

    measured = _ledger_projection_with_statuses(LedgerWorkspaceStatus.READY)
    readiness = _home_ledger_readiness(measured)
    assert isinstance(readiness, HomeLedgerReadiness)
    assert (readiness.entries, readiness.requiring_review) == (2, 2)

    for area in (
        LedgerWorkspaceArea.ENTRIES,
        LedgerWorkspaceArea.REVIEW,
        LedgerWorkspaceArea.CLASSIFICATION,
        LedgerWorkspaceArea.EVIDENCE,
    ):
        partial = _ledger_projection_with_statuses(
            LedgerWorkspaceStatus.READY, unmeasured=area
        )
        assert _home_ledger_readiness(partial) is None, (
            f"an unmeasured {area.value} area still produced a readiness block, so Home "
            f"renders a zero nobody measured"
        )

    assert _home_ledger_readiness(None) is None

def test_a_zone_awaiting_a_pull_is_never_captured_not_unavailable() -> None:
    """Home must not report absent remote data as a broken reader.

    AEAT notifications exist only once a pull has persisted a snapshot. Before
    that the reader is perfectly able to answer and the DATA is what is
    missing, which is exactly the distinction `no-silent-under-declaration`
    keeps: UNAVAILABLE says something is wrong, NEVER_CAPTURED says nothing has
    been fetched yet. Only the second tells the operator that a pull is the
    action that resolves the zone; the first sends them looking for a fault
    that does not exist.

    Asserted on the reason code as well as the availability, because a zone
    that carries the right state under a reason code naming a "reader
    unavailable" still tells the operator the wrong story wherever that code is
    rendered or logged.
    """
    from datetime import UTC, datetime

    from ..overview.home import HomeAccountSession, HomeAvailability, HomeSessionPosture, HomeZoneState
    from ..workbench_generation import _secure_profile_home_input

    observed_at = datetime(2026, 9, 4, tzinfo=UTC)
    home = _secure_profile_home_input(
        observed_at=observed_at,
        account_session=HomeAccountSession(posture=HomeSessionPosture.NO_PROFILE),
        agenda=None,
        agenda_evidence_state=HomeZoneState(
            availability=HomeAvailability.NEVER_CAPTURED,
            reason_code="workbench.home.agenda_evidence_never_pulled",
        ),
        ledger=None,
        declarations=None,
    )

    assert home.messages_state.availability is HomeAvailability.NEVER_CAPTURED, (
        "Home reports never-pulled AEAT notifications as an unavailable reader, "
        "which points the operator at a fault instead of at the pull"
    )
    assert home.messages_state.reason_code is not None
    assert "reader_unavailable" not in home.messages_state.reason_code, (
        f"the reason code {home.messages_state.reason_code!r} still blames the reader"
    )

def test_only_a_verified_calculation_reads_as_ready_on_home() -> None:
    """READY is the one Home state that must never be reached by inference.

    Telling an operator a declaration is ready to file when nobody verified it
    is a filing-grade harm, so the mapping errs in exactly one direction: the
    only calculation state that becomes READY is the one whose name says
    verified and complete. Every other state resolves to something that keeps
    work in front of them.

    The mapping is read from the domain's own vocabulary rather than invented
    for Home, and this asserts the whole table so a new calculation state
    cannot be added and silently default to anything.
    """
    from ..workbench_generation import _HOME_DECLARATION_STATES

    assert set(_HOME_DECLARATION_STATES) == set(CalculationRevisionState), (
        "a calculation state has no declared Home reading, so it would raise or "
        "default rather than being mapped deliberately"
    )

    ready = {
        state for state, home in _HOME_DECLARATION_STATES.items() if home is HomeDeclarationState.READY
    }
    assert ready == {CalculationRevisionState.VERIFICADO_COMPLETO}, (
        f"only a verified-complete calculation may read as READY on Home; found {sorted(ready)}"
    )

    assert _HOME_DECLARATION_STATES[CalculationRevisionState.BORRADOR] is (
        HomeDeclarationState.NEEDS_REVIEW
    ), "an unverified calculation must keep review in front of the operator"

def test_home_offers_ledger_work_only_when_there_is_some_and_never_for_an_unmeasured_area() -> None:
    """An offered action must correspond to work that exists and can be named.

    Two failure modes, both worse than an empty zone. Offering "classify"
    when the classification area holds zero entries sends the operator to an
    empty screen. Offering it when the area is UNMEASURED is the same mistake
    dressed as a fact: `item_count` is a plain integer, so an area nobody
    measured reports the same zero a finished one does.

    Also asserts the reason codes are Home's OWN declared vocabulary. A code
    with no `tui.home.reason.*` entry renders the degraded generic line, so an
    action invented to fill the zone would arrive unreadable.
    """
    from ..workbench_generation import _home_ledger_actions

    populated = _ledger_projection_with_statuses(LedgerWorkspaceStatus.NEEDS_ATTENTION)
    offered = _home_ledger_actions(populated)
    assert offered is not None
    assert {item.reason_code for item in offered} == {
        "ledger_classification_pending",
        "evidence_missing",
    }
    assert [item.rank for item in offered] == list(range(len(offered)))

    catalogue = _home_reason_keys_for_test()
    for item in offered:
        assert f"tui.home.reason.{item.reason_code}" in catalogue, (
            f"offered action reason {item.reason_code!r} has no copy, so Home degrades to its "
            f"generic line"
        )

    for area in (LedgerWorkspaceArea.CLASSIFICATION, LedgerWorkspaceArea.EVIDENCE):
        unmeasured = _ledger_projection_with_statuses(
            LedgerWorkspaceStatus.NEEDS_ATTENTION, unmeasured=area
        )
        assert _home_ledger_actions(unmeasured) is None, (
            f"an unmeasured {area.value} area still produced an offer, so Home invites the "
            f"operator to work nobody measured"
        )

    assert _home_ledger_actions(None) is None


def _home_reason_keys_for_test() -> frozenset[str]:
    """Every `tui.home.reason.*` key the Spanish catalogue declares."""
    import yaml

    root = Path(__file__).resolve().parents[2] / "locales" / "es" / "common.yml"
    raw = yaml.safe_load(root.read_text(encoding="utf-8"))
    reasons = raw["tui"]["home"]["reason"]
    return frozenset(f"tui.home.reason.{name}" for name in reasons)

def test_a_declaration_needing_review_is_offered_with_its_own_address() -> None:
    """A declaration-addressed action carries the declaration it is about.

    `declaration_needs_review` without an address is advice; with modelo,
    filing year and period it is a task the operator can act on, and Home
    renders that address beside the row. The action is the catalogue's
    `operator.modelo.work.revisions`, which takes the work unit id the resume
    already carries, so nothing is minted to fill the zone.

    Only NEEDS_REVIEW is offered. A verified, filed, draft or discarded
    declaration is not work the operator has been asked to do, and offering it
    would make the zone a list of everything rather than a list of what is
    outstanding.
    """
    from ..overview.home import HomeDeclarationResume
    from ..workbench_generation import _home_declaration_actions

    def _resume(state: HomeDeclarationState, unit: str) -> HomeDeclarationResume:
        return HomeDeclarationResume(
            work_unit_id=unit * 64,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "3T"),
            name=f"{unit}-declaration",
            state=state,
        )

    resumes = tuple(
        _resume(state, letter)
        for state, letter in (
            (HomeDeclarationState.NEEDS_REVIEW, "a"),
            (HomeDeclarationState.READY, "b"),
            (HomeDeclarationState.FILED, "c"),
            (HomeDeclarationState.DRAFT, "d"),
            (HomeDeclarationState.DISCARDED, "e"),
        )
    )
    offered = _home_declaration_actions(resumes)

    assert len(offered) == 1, (
        f"only a declaration needing review is outstanding work; got "
        f"{[item.reason_code for item in offered]}"
    )
    only = offered[0]
    assert only.reason_code == "declaration_needs_review"
    assert (only.modelo, only.filing_year) == ("303", 2026)
    assert only.period is not None, "an addressed action without its period cannot be acted on"
    assert only.action.action.action_id == "operator.modelo.work.revisions"

    assert _home_declaration_actions(None) == ()
