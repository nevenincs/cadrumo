"""Contract tests for the pure installed-workbench generation assembler."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import OutputLanguage
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from .. import workbench_generation as generation_module
from ..aeat_sync.workspace import AeatSyncWorkspaceProjectionError, AeatSyncWorkspaceProjectionV1
from ..auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from ..ledger.action_ports import LedgerActionPorts
from ..ledger.workspace import (
    LedgerWorkspaceArea,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceProjectionV1,
    LedgerWorkspaceSource,
    LedgerWorkspaceStatus,
)
from ..live.tests.unopened_live_ports import unopened_browser_session_factory, unopened_censal_fetch
from ..modelo.declarations_calendar import DeclarationsCalendarProjectionV1
from ..modelo.declarations_workspace import DeclarationsWorkspaceProjectionV1
from ..modelo.work_addressing import ModeloExactWorkUnitTarget
from ..modelo.workspace import graded_snapshot_refusal, resolve_static_inspection_result
from ..modelo.workspace_models import (
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceProjectionV1,
    ModeloWorkspaceRefusalCode,
)
from ..operations.registry import OperationPublicContractSetV1
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
from ..user_profile.censal_operation import (
    build_censal_operation_definition,
    build_censal_operation_registration,
)
from ..workbench_generation import (
    InstalledWorkbenchGenerationProviderV1,
    ModeloWorkspaceProjectedReadV1,
    SecureProfileWorkbenchGenerationReadDoorV1,
    WorkbenchGenerationAvailability,
    WorkbenchGenerationInputsV1,
    WorkbenchGenerationSourceResultV1,
    assemble_workbench_generation,
    assemble_workbench_generation_from,
)
from ._operator_scope_fakes import build_inward_operator_scope_ports_for_active_route

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 9, 3, 10, 30, tzinfo=UTC)
_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


def test_installed_calendar_reaches_latest_completed_filing_year() -> None:
    """The TUI calendar can select quarterly work from the completed tax year."""
    assert generation_module._calendar_query_range(date(2026, 9, 21)) == OverviewCalendarRange(
        from_date=date(2025, 1, 1),
        to_date=date(2026, 12, 31),
    )


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Pin one published generation for the production workbench door."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _test_censal_operation_definition():
    return build_censal_operation_definition(
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
        browser_session_factory=unopened_browser_session_factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        censal_fetch_port=unopened_censal_fetch,
    )


def _profile_record(
    operation: PinnedAuthorityOperation, *, facts: tuple[UserProfileFact, ...] = ()
) -> UserProfileRecord:
    """Create the incomplete profile fixture under the operation's schema authority."""
    return create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.INCOMPLETE,
        facts=facts,
    )


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


def test_secure_profile_provider_brackets_repository_capture_and_refuses_missing_loaders(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The production door verifies real local authorities without fake fixtures."""

    profile = _Repository(_profile_record(authority_operation))
    work_units = _Repository(WorkUnitCatalogue())
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())

    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        operation=authority_operation,
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
    assert generation.modelo_graded_refusals.availability is WorkbenchGenerationAvailability.UNAVAILABLE
    assert generation.search.availability is WorkbenchGenerationAvailability.UNAVAILABLE


def test_secure_profile_provider_contains_rejected_declarations_projection(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A contradictory declaration catalogue refuses only its workspace source."""
    period = Period.from_year_and_code(2026, "1T")
    revision_id = authority_operation.snapshot("130", filing_year=2026, period="1T").revision.id
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_PROFILE_ID,
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_PROFILE_ID,
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id=revision_id,
        name="declaration",
        created_at=_NOW,
        updated_at=_NOW,
    )
    duplicate_address = unit.model_copy(update={"work_unit_id": "a" * 64})
    profile = _Repository(_profile_record(authority_operation))
    work_units = _Repository(
        WorkUnitCatalogue.model_construct(
            work_units={unit.work_unit_id: unit, duplicate_address.work_unit_id: duplicate_address}
        )
    )
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())
    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        operation=authority_operation,
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

    assert generation.home.projection is not None
    assert generation.declarations.projection is None
    assert generation.declarations.availability is WorkbenchGenerationAvailability.UNAVAILABLE
    assert generation.declarations.refusal == "workbench.declarations.snapshot_projector_unavailable"
    assert generation.declarations_admission.state is WorkbenchDestinationAdmissionState.UNAVAILABLE


def test_secure_profile_modelo_graded_refusal_travels_beside_its_projection(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A GRADED_SNAPSHOT refusal for one work unit reaches the generation, keyed by its identity.

    The projection itself is never dropped on that refusal -- STATIC_INSPECTION
    remains a valid secondary view for every taxpayer-facing refusal code the
    graded resolver returns -- so this proves both halves travel: the Modelo
    source still names the unit, and the refusal map explains why its
    projection is the static fallback rather than the requested graded one.
    """
    period = Period.from_year_and_code(2026, "1T")
    revision_id = authority_operation.snapshot("130", filing_year=2026, period="1T").revision.id
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_PROFILE_ID,
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_PROFILE_ID,
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id=revision_id,
        name="declaration",
        created_at=_NOW,
        updated_at=_NOW,
    )
    profile = _Repository(_profile_record(authority_operation))
    work_units = _Repository(WorkUnitCatalogue.model_construct(work_units={unit.work_unit_id: unit}))
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())

    exact_target = ModeloWorkspaceExactWorkUnitTargetV1(
        target=ModeloExactWorkUnitTarget(work_unit_id=unit.work_unit_id, bucket_id=unit.bucket_id)
    )
    static_result = resolve_static_inspection_result(
        exact_target,
        bucket_id=_PROFILE_ID,
        catalogue_repository=cast(Any, work_units),
        authority=authority_operation,
        output_language=OutputLanguage.ES,
    )
    refusal = graded_snapshot_refusal(
        ModeloWorkspaceRefusalCode.CALCULATION_UNAVAILABLE,
        requested_target=exact_target,
        selected_target=static_result.projection.target,
        capability=ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION,
        reconsideration_condition="calculate this work unit, then request a graded snapshot again",
        facts=(),
        evidence=(),
        source_disposition=None,
        recovery_action=None,
    ).refusal

    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        operation=authority_operation,
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
        modelo_projection_reader=lambda _unit: ModeloWorkspaceProjectedReadV1(
            projection=static_result.projection, graded_refusal=refusal
        ),
    )

    generation = InstalledWorkbenchGenerationProviderV1(door)()

    assert generation.modelo.availability is WorkbenchGenerationAvailability.AVAILABLE
    assert generation.modelo.projection is not None
    assert [projection.target.work_unit_id for projection in generation.modelo.projection] == [unit.work_unit_id]
    assert generation.modelo_graded_refusals.availability is WorkbenchGenerationAvailability.AVAILABLE
    assert generation.modelo_graded_refusals.projection == {str(unit.work_unit_id): refusal}


def test_secure_profile_modelo_reader_with_no_refusal_leaves_the_refusal_map_empty(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A work unit admitted at its requested grade has no entry, not a ``None`` one."""
    period = Period.from_year_and_code(2026, "1T")
    revision_id = authority_operation.snapshot("130", filing_year=2026, period="1T").revision.id
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_PROFILE_ID,
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_PROFILE_ID,
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id=revision_id,
        name="declaration",
        created_at=_NOW,
        updated_at=_NOW,
    )
    profile = _Repository(_profile_record(authority_operation))
    work_units = _Repository(WorkUnitCatalogue.model_construct(work_units={unit.work_unit_id: unit}))
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())

    exact_target = ModeloWorkspaceExactWorkUnitTargetV1(
        target=ModeloExactWorkUnitTarget(work_unit_id=unit.work_unit_id, bucket_id=unit.bucket_id)
    )
    static_result = resolve_static_inspection_result(
        exact_target,
        bucket_id=_PROFILE_ID,
        catalogue_repository=cast(Any, work_units),
        authority=authority_operation,
        output_language=OutputLanguage.ES,
    )

    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        operation=authority_operation,
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
        modelo_projection_reader=lambda _unit: ModeloWorkspaceProjectedReadV1(projection=static_result.projection),
    )

    generation = InstalledWorkbenchGenerationProviderV1(door)()

    assert generation.modelo.projection is not None
    assert generation.modelo_graded_refusals.availability is WorkbenchGenerationAvailability.AVAILABLE
    assert generation.modelo_graded_refusals.projection == {}


def test_secure_profile_aeat_sync_reader_contains_a_validation_error(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A malformed AEAT Sync row refuses its source with the projector reason."""
    from ...domain.invoices.models import InvoiceCatalogue
    from ...domain.transactions.models import TransactionCatalogue
    from ..aeat_sync.workspace_reader import read_local_aeat_sync_workspace_projection

    profile = _Repository(
        _profile_record(
            authority_operation,
            facts=(
                UserProfileFact(path="identity.tax_id", value="00000000T"),
                UserProfileFact(path="contact.fiscal_address", value="x" * 257),
            ),
        )
    )
    work_units = _Repository(WorkUnitCatalogue())
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())
    contracts = OperationPublicContractSetV1.build(
        (build_censal_operation_registration(_test_censal_operation_definition()).contract,)
    )
    with pytest.raises(ValidationError):
        read_local_aeat_sync_workspace_projection(
            bucket_id=_PROFILE_ID,
            subject_key="00000000T",
            observed_at=_NOW,
            filings=(),
            operation_contracts=contracts,
            censo_values={"contact.fiscal_address": "x" * 257},
        )
    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        operation=authority_operation,
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
        operation_contracts=contracts,
        ledger_action_ports=_ledger_ports(
            authority_operation,
            transactions=_StableStore(TransactionCatalogue()),
            invoices=_StableStore(InvoiceCatalogue()),
        ),
        modelo_projection_reader=lambda _unit: pytest.fail("the empty catalogue must not invoke the Modelo reader"),
    )

    generation = InstalledWorkbenchGenerationProviderV1(door)()

    assert generation.home.projection is not None
    assert generation.home.availability is WorkbenchGenerationAvailability.AVAILABLE
    assert generation.aeat_sync.projection is None
    assert generation.aeat_sync.availability is WorkbenchGenerationAvailability.UNAVAILABLE
    assert generation.aeat_sync.refusal == "workbench.aeat_sync.snapshot_projector_unavailable"
    assert generation.aeat_sync_admission.state is WorkbenchDestinationAdmissionState.UNAVAILABLE
    assert generation.aeat_sync_admission.reason_code == generation.aeat_sync.refusal
    assert generation.search.projection is None
    assert generation.search.availability is WorkbenchGenerationAvailability.UNAVAILABLE
    assert generation.search.refusal == generation.aeat_sync.refusal


def test_secure_profile_aeat_sync_reader_contains_a_named_projection_error(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A malformed subject reaches the real projector and is contained at the door."""
    from ..aeat_sync.workspace_reader import read_local_aeat_sync_workspace_projection

    profile = _Repository(_profile_record(authority_operation))
    work_units = _Repository(WorkUnitCatalogue())
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())
    contracts = OperationPublicContractSetV1.build(
        (build_censal_operation_registration(_test_censal_operation_definition()).contract,)
    )
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="subject key cannot be blank"):
        read_local_aeat_sync_workspace_projection(
            bucket_id=_PROFILE_ID,
            subject_key=" ",
            observed_at=_NOW,
            filings=(),
            operation_contracts=contracts,
            censo_values={},
        )
    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        operation=authority_operation,
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
        operation_contracts=contracts,
    )

    projection, refusal = door._read_aeat_sync(
        " ",
        observed_at=_NOW,
        filings=(),
        custody_count=None,
        censo_values={},
    )

    assert projection is None
    assert refusal == "workbench.aeat_sync.snapshot_projector_unavailable"


def test_secure_profile_provider_refuses_a_generation_changed_during_capture(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A cross-repository capture is never published after a revision changes."""
    profile = _Repository(_profile_record(authority_operation))
    work_units = _Repository(WorkUnitCatalogue(), revisions=("work-1", "work-2"))
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())

    def empty_calendar(_profile: object, calendar_range: object, **_kwargs: object) -> OverviewCalendar:
        return OverviewCalendar(range=calendar_range, entries=(), generated_at=_NOW, evaluated_on=_NOW.date())  # type: ignore[arg-type]

    monkeypatch.setattr(generation_module, "build_overview_calendar", empty_calendar)
    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        operation=authority_operation,
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

    with pytest.raises(InternalInvariantError, match="changed during capture"):
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


class _EmptyAttachmentStore:
    """An attachment store holding no manifests."""

    @staticmethod
    def iter_manifests() -> tuple[()]:
        return ()


def _ledger_ports(
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
        bucket_event_repository=cast(Any, _StableStore(BucketEventHistoryCatalogue())),
        invoice_repository=cast(Any, invoices),
        attachment_store=cast(Any, _EmptyAttachmentStore()),
        usage_ratio_profile=UsageRatioProfile(),
        usage_ratio_profile_loader=cast(Any, None),
        work_unit_repository=cast(Any, None),
        calculation_repository=cast(Any, None),
        purchase_invoice_evidence_records=(),
    )


def test_secure_profile_provider_refuses_a_ledger_written_during_capture(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A ledger write between the two reads refuses the whole generation.

    The guard was total when it was written; it stopped being so when Ledger
    arrived, because the door began reading two stores it never re-checked. A
    generation could then carry a Ledger snapshot from a different instant
    than its Declarations with nothing to detect it.
    """
    from ...domain.invoices.models import InvoiceCatalogue
    from ...domain.transactions.models import TransactionCatalogue

    profile = _Repository(_profile_record(authority_operation))
    work_units = _Repository(WorkUnitCatalogue())
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())

    def empty_calendar(_profile: object, calendar_range: object, **_kwargs: object) -> OverviewCalendar:
        return OverviewCalendar(range=calendar_range, entries=(), generated_at=_NOW, evaluated_on=_NOW.date())  # type: ignore[arg-type]

    monkeypatch.setattr(generation_module, "build_overview_calendar", empty_calendar)
    written = TransactionCatalogue.model_validate([_synthetic_transaction()])
    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        operation=authority_operation,
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
        ledger_action_ports=_ledger_ports(
            authority_operation,
            transactions=_ChangingLedgerStore(TransactionCatalogue(), written),
            invoices=_StableStore(InvoiceCatalogue()),
        ),
    )

    with pytest.raises(InternalInvariantError, match="changed during capture"):
        door.read_workbench_generation_inputs()


def test_a_quiet_ledger_publishes_its_generation(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The guard must not refuse a capture nothing wrote during."""
    from ...domain.invoices.models import InvoiceCatalogue
    from ...domain.transactions.models import TransactionCatalogue

    profile = _Repository(_profile_record(authority_operation))
    work_units = _Repository(WorkUnitCatalogue())
    revisions = _Repository(CalculationRevisionCatalogue())
    filings = _Repository(ModeloRecordCatalogue())

    def empty_calendar(_profile: object, calendar_range: object, **_kwargs: object) -> OverviewCalendar:
        return OverviewCalendar(range=calendar_range, entries=(), generated_at=_NOW, evaluated_on=_NOW.date())  # type: ignore[arg-type]

    monkeypatch.setattr(generation_module, "build_overview_calendar", empty_calendar)
    door = SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        operation=authority_operation,
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
        ledger_action_ports=_ledger_ports(
            authority_operation,
            transactions=_StableStore(TransactionCatalogue()),
            invoices=_StableStore(InvoiceCatalogue()),
        ),
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
        evaluated_on=_NOW.date(),
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
        partial = _ledger_projection_with_statuses(LedgerWorkspaceStatus.READY, unmeasured=area)
        assert _home_ledger_readiness(partial) is None, (
            f"an unmeasured {area.value} area still produced a readiness block, so Home renders a zero nobody measured"
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

    ready = {state for state, home in _HOME_DECLARATION_STATES.items() if home is HomeDeclarationState.READY}
    assert ready == {CalculationRevisionState.VERIFICADO_COMPLETO}, (
        f"only a verified-complete calculation may read as READY on Home; found {sorted(ready)}"
    )

    assert _HOME_DECLARATION_STATES[CalculationRevisionState.BORRADOR] is (HomeDeclarationState.NEEDS_REVIEW), (
        "an unverified calculation must keep review in front of the operator"
    )


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
            f"offered action reason {item.reason_code!r} has no copy, so Home degrades to its generic line"
        )

    for area in (LedgerWorkspaceArea.CLASSIFICATION, LedgerWorkspaceArea.EVIDENCE):
        unmeasured = _ledger_projection_with_statuses(LedgerWorkspaceStatus.NEEDS_ATTENTION, unmeasured=area)
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
        f"only a declaration needing review is outstanding work; got {[item.reason_code for item in offered]}"
    )
    only = offered[0]
    assert only.reason_code == "declaration_needs_review"
    assert (only.modelo, only.filing_year) == ("303", 2026)
    assert only.period is not None, "an addressed action without its period cannot be acted on"
    assert only.action.action.action_id == "operator.modelo.work.revisions"

    assert _home_declaration_actions(None) == ()


def test_only_a_blocking_dependency_finding_reads_as_a_blocked_declaration() -> None:
    """`blocked_dependency` is produced from the domain's own word, or not at all.

    `CROSS_PERIOD_DEPENDENCY_UNCLEAN` names the condition Home's
    `blocked_dependency` describes, so that one code is grounded. The other two
    Home declares are deliberately unproduced: nothing in
    `ModeloVerificationFindingKind` names evidence, and routing
    `blocked_review` to BLOCKING_RULE or MISSING_REQUIRED_CASILLA would be a
    guess wearing a finding's clothes.

    Severity and completeness both gate it. An ADVISORY finding of the same
    kind is information rather than a blocker, and a report that is not BLOCKED
    has nothing outstanding -- offering either as blocked work would send the
    operator at something nothing is waiting on.
    """
    from ...domain.calculations.registry.tests.published_authority import published_snapshot
    from ...domain.modelos.verification_report import (
        ModeloVerificationFinding,
        ModeloVerificationFindingKind,
        ModeloVerificationFindingSeverity,
        VerificationCompletenessStatus,
        VerificationReport,
        VerificationReportCatalogue,
        derive_verification_report_id,
    )
    from ..workbench_generation import _dependency_blocked_revisions

    def _catalogue(
        kind: ModeloVerificationFindingKind,
        severity: ModeloVerificationFindingSeverity,
        status: VerificationCompletenessStatus,
    ) -> VerificationReportCatalogue:
        findings = (
            ModeloVerificationFinding(
                kind=kind,
                severity=severity,
                message_locale_key="application.modelo.findings.cross_period_dependency",
                legal_refs=("ley-37-1992:art-99",),
            ),
        )
        report = VerificationReport(
            # Content-addressed: the id is DERIVED from the report's own facts,
            # so it is computed here rather than invented, which also means a
            # fixture cannot drift from the identity the domain would assign.
            verification_report_id=derive_verification_report_id(
                calculation_revision_id="b" * 64,
                completeness_status=status,
                findings=findings,
                verified_by="operator",
            ),
            calculation_revision_id="b" * 64,
            registry_snapshot_ref=published_snapshot("303", filing_year=2026, period="1T").snapshot_ref,
            completeness_status=status,
            findings=findings,
            run_at=datetime(2026, 9, 4, tzinfo=UTC),
            verified_by="operator",
            granted_verificado_completo=False,
        )
        return VerificationReportCatalogue(reports={report.verification_report_id: report})

    blocked = _catalogue(
        ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
        ModeloVerificationFindingSeverity.BLOCKING,
        VerificationCompletenessStatus.BLOCKED,
    )
    assert _dependency_blocked_revisions(blocked) == frozenset({"b" * 64})

    warning = _catalogue(
        ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN,
        ModeloVerificationFindingSeverity.WARNING,
        VerificationCompletenessStatus.BLOCKED,
    )
    assert _dependency_blocked_revisions(warning) == frozenset(), (
        "a WARNING dependency finding is information, not a blocker"
    )

    other_kind = _catalogue(
        ModeloVerificationFindingKind.BLOCKING_RULE,
        ModeloVerificationFindingSeverity.BLOCKING,
        VerificationCompletenessStatus.BLOCKED,
    )
    assert _dependency_blocked_revisions(other_kind) == frozenset(), (
        "only the dependency finding kind may read as blocked_dependency; another kind "
        "reaching it would be a guess about what the operator is blocked on"
    )

    assert _dependency_blocked_revisions(None) == frozenset()


def _plain_generation_door(
    operation: PinnedAuthorityOperation,
    *,
    profile: _Repository[UserProfileRecord],
    work_units: _Repository[WorkUnitCatalogue] | None = None,
    bucket_events: object | None = None,
) -> SecureProfileWorkbenchGenerationReadDoorV1:
    return SecureProfileWorkbenchGenerationReadDoorV1(
        profile_id=_PROFILE_ID,
        operation=operation,
        profile_repository=cast(Any, profile),
        work_unit_repository=cast(Any, work_units or _Repository(WorkUnitCatalogue())),
        calculation_repository=cast(Any, _Repository(CalculationRevisionCatalogue())),
        filing_repository=cast(Any, _Repository(ModeloRecordCatalogue())),
        clock=lambda: _NOW,
        account_session_reader=lambda: HomeAccountSession(
            posture=HomeSessionPosture.ACTIVE,
            profile_label="Perfil local",
            expires_at=_NOW,
        ),
        bucket_event_repository=cast(Any, bucket_events),
    )


def test_an_incomplete_profile_publishes_reasoned_zones_instead_of_failing(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A profile the taxpayer projection refuses must not stop the workbench.

    Declaring one IVA fact claims the whole IVA block, and the projection then
    refuses until the rest of that block is answered. The operator reached this
    state by editing one field, so the generation serves every zone it can and
    names the missing paths on the zones that need the projection.
    """
    record = _profile_record(
        authority_operation,
        facts=(UserProfileFact(path="iva.regime", value="GENERAL"),),
    )

    generation = InstalledWorkbenchGenerationProviderV1(
        _plain_generation_door(authority_operation, profile=_Repository(record))
    )()

    assert generation.home.availability is WorkbenchGenerationAvailability.AVAILABLE
    home = generation.home.projection
    assert home is not None
    assert home.agenda_state.availability is HomeAvailability.UNAVAILABLE
    assert home.agenda_state.reason_code == "workbench.home.taxpayer_profile_incomplete"
    assert "iva.m303_regime_composition" in home.agenda_state.missing_profile_paths
    assert "iva.redeme_enrolled" in home.agenda_state.missing_profile_paths
    calendar = generation.declarations_calendar.projection
    assert calendar is not None
    assert calendar.entries == ()
    assert {source.reason_code for source in calendar.sources} == {"workbench.home.taxpayer_profile_incomplete"}
    assert generation.declarations.projection is not None


def test_an_undeclared_taxpayer_model_leaves_the_agenda_unavailable(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """No taxpayer model means no schedule, which is not the same as no dates."""
    generation = InstalledWorkbenchGenerationProviderV1(
        _plain_generation_door(authority_operation, profile=_Repository(_profile_record(authority_operation)))
    )()

    home = generation.home.projection
    assert home is not None
    assert home.agenda_state.availability is HomeAvailability.UNAVAILABLE
    assert home.agenda_state.reason_code == "workbench.calendar.taxpayer_model_undeclared"
    assert home.agenda == ()


def test_the_filing_history_reads_the_bucket_event_log(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A bound event log makes the filing history observable, not permanently unavailable."""
    from ...domain.buckets.event import BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType
    from ...domain.buckets.event_repository import build_bucket_event
    from ..modelo.declarations_workspace import DeclarationsLifecycleKind, DeclarationsWorkspaceZone

    period = Period.from_year_and_code(2026, "1T")
    revision_id = authority_operation.snapshot("130", filing_year=2026, period="1T").revision.id
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_PROFILE_ID,
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_PROFILE_ID,
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id=revision_id,
        name="declaration",
        created_at=_NOW,
        updated_at=_NOW,
    )
    created = build_bucket_event(
        bucket_id=_PROFILE_ID,
        event_type=BucketEventType.MODELO_WORK_UNIT_CREATED,
        occurred_at=_NOW,
        actor="operator",
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=unit.work_unit_id,
        payload={"modelo": "130", "filing_year": "2026", "period": "1T"},
        payload_version=1,
    )
    unrelated = build_bucket_event(
        bucket_id=_PROFILE_ID,
        event_type=BucketEventType.MODELO_EXPORTED,
        occurred_at=_NOW,
        actor="operator",
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=unit.work_unit_id,
        payload={"modelo": "130"},
        payload_version=1,
    )
    events = BucketEventHistoryCatalogue(events={created.event_id: created, unrelated.event_id: unrelated})

    generation = InstalledWorkbenchGenerationProviderV1(
        _plain_generation_door(
            authority_operation,
            profile=_Repository(_profile_record(authority_operation)),
            work_units=_Repository(WorkUnitCatalogue(work_units={unit.work_unit_id: unit})),
            bucket_events=_Repository(events),
        )
    )()

    declarations = generation.declarations.projection
    assert declarations is not None
    history = next(zone for zone in declarations.zones if zone.zone is DeclarationsWorkspaceZone.FILING_HISTORY)
    assert history.reason_code is None
    assert [row.kind for row in declarations.lifecycle] == [DeclarationsLifecycleKind.CREATED]
