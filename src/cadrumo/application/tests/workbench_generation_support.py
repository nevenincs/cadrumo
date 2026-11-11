"""Profile, repository and input fixtures shared by the workbench generation tests."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from types import FrameType
from typing import Any, cast

import pytest

from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from .. import workbench_generation_calendar
from ..aeat_sync.workspace import AeatSyncWorkspaceProjectionV1
from ..auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from ..ledger.action_ports import LedgerActionPorts
from ..ledger.workspace import (
    LedgerWorkspaceProjectionV1,
)
from ..live.tests.unopened_live_ports import unopened_browser_session_factory, unopened_censal_fetch
from ..modelo.declarations_calendar import DeclarationsCalendarProjectionV1
from ..modelo.declarations_workspace_contracts import DeclarationsWorkspaceProjectionV1
from ..modelo.workspace_models import (
    ModeloWorkspaceProjectionV1,
)
from ..overview.calendar import build_overview_calendar
from ..overview.calendar_models import OverviewCalendar, OverviewCalendarRange
from ..overview.home import (
    HomeAccountSession,
    HomeAvailability,
    HomeProjectionInput,
    HomeSessionPosture,
    HomeZoneState,
)
from ..search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from ..user_profile.censal_operation import (
    build_censal_operation_definition,
)
from ..workbench_generation_contracts import (
    WorkbenchGenerationInputsV1,
    WorkbenchGenerationSourceResultV1,
)
from ..workbench_generation_reader import SecureProfileWorkbenchGenerationReadDoorV1
from .operator_scope_fakes import build_inward_operator_scope_ports_for_active_route

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()
YEAR = filing_year_envelope().horizon
NOW = datetime(YEAR, 9, 3, 10, 30, tzinfo=UTC)
PROFILE_ID = "11111111-1111-4111-8111-111111111111"


def censal_test_operation_definition():
    return build_censal_operation_definition(
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
        browser_session_factory=unopened_browser_session_factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        censal_fetch_port=unopened_censal_fetch,
        provider_preflight=lambda _profile_id, _operation: None,
    )


def profile_record(
    operation: PinnedAuthorityOperation, *, facts: tuple[UserProfileFact, ...] = ()
) -> UserProfileRecord:
    """Create the incomplete profile fixture under the operation's schema authority."""
    return create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=PROFILE_ID,
        setup_state=ProfileSetupState.INCOMPLETE,
        facts=facts,
    )


def declaration_work_unit(operation: PinnedAuthorityOperation) -> WorkUnit:
    """Create the one Modelo 130 declaration the profile holds in these fixtures."""
    period = Period.from_year_and_code(YEAR, "1T")
    revision_id = operation.snapshot("130", filing_year=YEAR, period="1T").revision.id
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=PROFILE_ID,
            modelo="130",
            filing_year=YEAR,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=PROFILE_ID,
        modelo="130",
        filing_year=YEAR,
        period=period,
        revision_id=revision_id,
        name="declaration",
        created_at=NOW,
        updated_at=NOW,
    )


def work_unit(operation: PinnedAuthorityOperation, modelo: str, filing_year: int, code: str) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, code)
    revision_id = operation.snapshot(modelo, filing_year=filing_year, period=code).revision.id
    """Create one local work unit for ``modelo`` under the pinned revision for that period."""
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=PROFILE_ID, modelo=modelo, filing_year=filing_year, period=period, revision_id=revision_id
        ),
        bucket_id=PROFILE_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"local {modelo}",
        created_at=NOW,
        updated_at=NOW,
    )


def calendar_builds(action: Callable[[], object]) -> int:
    """Count calls into the real calendar builder while ``action`` runs."""
    code = build_overview_calendar.__code__
    builds = 0
    previous = sys.getprofile()

    def observe(frame: FrameType, event: str, arg: object) -> None:
        nonlocal builds
        del arg
        if event == "call" and frame.f_code is code:
            builds += 1

    sys.setprofile(observe)
    try:
        action()
    finally:
        sys.setprofile(previous)
    return builds


@dataclass
class Repository[ValueT]:
    value: ValueT
    revisions: tuple[str, ...] = ("revision-1",)
    calls: int = 0

    def load(self, *_args: object) -> ValueT:
        self.calls += 1
        return self.value

    def load_revisioned(self, *, operation: PinnedAuthorityOperation | None = None) -> tuple[ValueT, str]:
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
        generated_at=NOW,
        account=HomeAccountSession(posture=HomeSessionPosture.NO_PROFILE),
        actions_state=zone("actions"),
        declarations_state=zone("declarations"),
        ledger_state=zone("ledger"),
        agenda_state=zone("agenda"),
        agenda_evidence_state=zone("agenda_evidence"),
        messages_state=zone("messages"),
    )


def admission(
    destination: str,
    state: WorkbenchDestinationAdmissionState = WorkbenchDestinationAdmissionState.NEVER_CAPTURED,
) -> WorkbenchDestinationAdmission:
    """Return a route admission matching its source-capture state."""
    return WorkbenchDestinationAdmission(
        destination=destination,
        state=state,
        reason_code=None if state is WorkbenchDestinationAdmissionState.AVAILABLE else f"{destination}.not_captured",
    )


def inputs(
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
        assembled_at=NOW,
        home=WorkbenchGenerationSourceResultV1.available(_home_input(), observed_at=NOW),
        ledger=ledger_result,
        declarations=declarations_result,
        declarations_calendar=declarations_calendar
        or WorkbenchGenerationSourceResultV1.never_captured(refusal="source.declarations_calendar"),
        aeat_sync=aeat_sync_result,
        modelo=modelo or WorkbenchGenerationSourceResultV1.never_captured(refusal="source.modelo"),
        ledger_admission=admission(
            "workbench.ledger", WorkbenchDestinationAdmissionState(ledger_result.availability.value)
        ),
        declarations_admission=admission(
            "workbench.declarations", WorkbenchDestinationAdmissionState(declarations_result.availability.value)
        ),
        aeat_sync_admission=admission(
            "workbench.aeat_sync", WorkbenchDestinationAdmissionState(aeat_sync_result.availability.value)
        ),
    )


def synthetic_transaction() -> object:
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
        booked_date=date(YEAR, 3, 1),
        value_date=date(YEAR, 3, 1),
        amount=Decimal("50.00"),
        currency="EUR",
        counterparty="Synthetic SL",
        description="synthetic row",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=NOW,
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


class ChangingLedgerStore:
    """A store whose second read differs from its first.

    The ledger repositories expose no revision handle the way the work-unit,
    calculation and filing catalogues do, so the guard compares the catalogues
    themselves. Returning a different one on the re-read is the mid-capture
    write it exists to catch, and the only way to show it is not comparing a
    value with itself.
    """

    def __init__(self, first: object, second: object) -> None:
        self._reads = [first, second]
        self.bucket_id = PROFILE_ID

    def load(self) -> object:
        return self._reads.pop(0) if len(self._reads) > 1 else self._reads[0]


class StableStore:
    """A store that answers the same catalogue however often it is asked."""

    def __init__(self, value: object) -> None:
        self._value = value
        self.bucket_id = PROFILE_ID

    def load(self) -> object:
        return self._value


class _EmptyAttachmentStore:
    """An attachment store holding no manifests."""

    @staticmethod
    def iter_manifests() -> tuple[()]:
        return ()


def ledger_ports(
    operation: PinnedAuthorityOperation,
    *,
    transactions: object,
    invoices: object,
) -> LedgerActionPorts:
    """Bind the ledger stores the door reads through the action ports."""
    from ...domain.buckets.event import BucketEventHistoryCatalogue
    from ...domain.usage_ratios.model import UsageRatioProfile

    return LedgerActionPorts(
        operation=operation,
        transaction_repository=cast(Any, transactions),
        bucket_event_repository=cast(Any, StableStore(BucketEventHistoryCatalogue())),
        invoice_repository=cast(Any, invoices),
        attachment_store=cast(Any, _EmptyAttachmentStore()),
        usage_ratio_profile=UsageRatioProfile(),
        usage_ratio_profile_loader=cast(Any, None),
        work_unit_repository=cast(Any, None),
        calculation_repository=cast(Any, None),
        purchase_invoice_evidence_records=(),
    )


def plain_generation_door(
    operation: PinnedAuthorityOperation,
    *,
    profile: Repository[UserProfileRecord],
    work_units: Repository[WorkUnitCatalogue] | None = None,
    revisions: Repository[CalculationRevisionCatalogue] | None = None,
    filings: Repository[ModeloRecordCatalogue] | None = None,
    bucket_events: object | None = None,
    **door_options: Any,
) -> SecureProfileWorkbenchGenerationReadDoorV1:
    return SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=PROFILE_ID,
        operation=operation,
        profile_repository=cast(Any, profile),
        work_unit_repository=cast(Any, work_units or Repository(WorkUnitCatalogue())),
        calculation_repository=cast(Any, revisions or Repository(CalculationRevisionCatalogue())),
        filing_repository=cast(Any, filings or Repository(ModeloRecordCatalogue())),
        clock=lambda: NOW,
        account_session_reader=lambda: HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE,
            profile_label="Perfil local",
            expires_at=NOW,
        ),
        bucket_event_repository=cast(Any, bucket_events),
        **door_options,
    )


def stub_empty_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the generation calendar build an empty schedule so a test isolates capture bracketing."""

    def empty_calendar(_profile: object, calendar_range: OverviewCalendarRange, **_kwargs: object) -> OverviewCalendar:
        return OverviewCalendar(range=calendar_range, entries=(), generated_at=NOW, evaluated_on=NOW.date())

    monkeypatch.setattr(workbench_generation_calendar, "build_overview_calendar", empty_calendar)
