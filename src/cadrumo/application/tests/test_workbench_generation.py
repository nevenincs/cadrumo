"""Contract tests for the pure installed-workbench generation assembler."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.filing_record import ModeloRecordCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ...domain.user_profile.values import (
    UserProfileFact,
)
from .. import workbench_generation_calendar as calendar_module
from ..aeat_sync.workspace import AeatSyncWorkspaceProjectionError
from ..modelo.work_addressing import ModeloExactWorkUnitTarget
from ..modelo.workspace_models import (
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceStaticInspectionResultV1,
)
from ..modelo.workspace_schema import resolve_static_inspection_result
from ..operations.registry import OperationPublicContractSetV1
from ..overview.calendar_models import OverviewCalendarRange
from ..overview.home import (
    HomeAvailability,
)
from ..search.workbench import WorkbenchDestinationAdmissionState
from ..user_profile.censal_operation import (
    build_censal_operation_registration,
)
from ..workbench_generation import (
    InstalledWorkbenchGenerationProviderV1,
)
from ..workbench_generation_contracts import (
    WorkbenchGenerationAvailability,
    WorkbenchGenerationInputsV1,
    WorkbenchGenerationSourceResultV1,
)
from .workbench_generation_support import (
    NOW,
    PROFILE_ID,
    Repository,
    StableStore,
    admission,
    censal_test_operation_definition,
    declaration_work_unit,
    inputs,
    ledger_ports,
    plain_generation_door,
    profile_record,
    stub_empty_calendar,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_installed_calendar_reaches_latest_completed_filing_year() -> None:
    """The TUI calendar can select quarterly work from the completed tax year."""
    assert calendar_module.calendar_query_range(date(2026, 9, 21)) == OverviewCalendarRange(
        from_date=date(2025, 1, 1),
        to_date=date(2026, 12, 31),
    )


def test_source_result_rejects_confident_absence_and_preserves_known_empty() -> None:
    """An observed empty collection is distinct from a source never read."""
    known_empty = WorkbenchGenerationSourceResultV1[tuple[int, ...]].available((), observed_at=NOW)
    never_captured = WorkbenchGenerationSourceResultV1[tuple[int, ...]].never_captured(refusal="source.never")

    assert known_empty.value == ()
    assert known_empty.availability is WorkbenchGenerationAvailability.AVAILABLE
    assert never_captured.value is None
    assert never_captured.availability is WorkbenchGenerationAvailability.NEVER_CAPTURED
    with pytest.raises(ValidationError, match="requires a value"):
        WorkbenchGenerationSourceResultV1[tuple[int, ...]](
            availability=WorkbenchGenerationAvailability.AVAILABLE,
            observed_at=NOW,
        )


def test_generation_inputs_reject_admission_source_contradictions() -> None:
    """A route cannot claim availability that its defining source does not have."""
    payload = inputs().model_dump()
    payload["ledger_admission"] = admission(
        "workbench.ledger", WorkbenchDestinationAdmissionState.AVAILABLE
    ).model_dump()
    with pytest.raises(ValidationError, match=r"workbench\.ledger admission must match"):
        WorkbenchGenerationInputsV1.model_validate(payload)


def test_secure_profile_provider_brackets_repository_capture_and_refuses_missing_loaders(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The production door verifies real local authorities without fake fixtures."""

    profile = Repository(profile_record(authority_operation))
    work_units = Repository(WorkUnitCatalogue())
    revisions = Repository(CalculationRevisionCatalogue())
    filings = Repository(ModeloRecordCatalogue())

    door = plain_generation_door(
        authority_operation,
        profile=profile,
        work_units=work_units,
        revisions=revisions,
        filings=filings,
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


def test_secure_profile_provider_contains_rejected_declarations_projection(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """An invalid declaration identity refuses its row while retaining its healthy neighbour."""
    unit = declaration_work_unit(authority_operation)
    duplicate_address = unit.model_copy(update={"work_unit_id": "a" * 64})
    profile = Repository(profile_record(authority_operation))
    work_units = Repository(
        WorkUnitCatalogue.model_construct(
            work_units={unit.work_unit_id: unit, duplicate_address.work_unit_id: duplicate_address}
        )
    )
    revisions = Repository(CalculationRevisionCatalogue())
    filings = Repository(ModeloRecordCatalogue())
    door = plain_generation_door(
        authority_operation,
        profile=profile,
        work_units=work_units,
        revisions=revisions,
        filings=filings,
    )

    generation = InstalledWorkbenchGenerationProviderV1(door)()

    assert generation.home.projection is not None
    projection = generation.declarations.projection
    assert projection is not None
    assert len(projection.declarations) == 2
    healthy, refused = projection.declarations
    assert healthy.work_unit_id == unit.work_unit_id
    assert healthy.summary is not None and healthy.summary.state.value == "draft"
    assert refused.work_unit_id == duplicate_address.work_unit_id
    assert refused.summary is not None and refused.summary.state.value == "unreadable"
    assert all(row.summary is not None and row.summary.result is None for row in projection.declarations)
    assert all(zone.availability.value == "stale" for zone in projection.zones if zone.item_count is not None)


def test_secure_profile_modelo_source_carries_each_work_unit_s_projection(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The Modelo source names every work unit the profile holds, through the reader it is given."""
    unit = declaration_work_unit(authority_operation)
    profile = Repository(profile_record(authority_operation))
    work_units = Repository(WorkUnitCatalogue.model_construct(work_units={unit.work_unit_id: unit}))
    revisions = Repository(CalculationRevisionCatalogue())
    filings = Repository(ModeloRecordCatalogue())

    exact_target = ModeloWorkspaceExactWorkUnitTargetV1(
        target=ModeloExactWorkUnitTarget(work_unit_id=unit.work_unit_id, bucket_id=unit.bucket_id)
    )
    static_result = resolve_static_inspection_result(
        exact_target,
        bucket_id=PROFILE_ID,
        catalogue_repository=cast(Any, work_units),
        authority=authority_operation,
        output_language=OutputLanguage.ES,
    )
    assert isinstance(static_result, ModeloWorkspaceStaticInspectionResultV1)
    door = plain_generation_door(
        authority_operation,
        profile=profile,
        work_units=work_units,
        revisions=revisions,
        filings=filings,
        modelo_projection_reader=lambda _unit: static_result.projection,
    )

    generation = InstalledWorkbenchGenerationProviderV1(door)()

    assert generation.modelo.availability is WorkbenchGenerationAvailability.AVAILABLE
    assert generation.modelo.projection is not None
    assert [projection.target.work_unit_id for projection in generation.modelo.projection] == [unit.work_unit_id]


def test_secure_profile_aeat_sync_reader_contains_a_validation_error(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A malformed AEAT Sync row refuses its source with the projector reason."""
    from ...domain.invoices.catalogue import InvoiceCatalogue
    from ...domain.transactions.models import TransactionCatalogue
    from ..aeat_sync.workspace_reader import read_local_aeat_sync_workspace_projection

    profile = Repository(
        profile_record(
            authority_operation,
            facts=(
                UserProfileFact(path="identity.tax_id", value="00000000T"),
                UserProfileFact(path="contact.fiscal_address", value="x" * 257),
            ),
        )
    )
    work_units = Repository(WorkUnitCatalogue())
    revisions = Repository(CalculationRevisionCatalogue())
    filings = Repository(ModeloRecordCatalogue())
    contracts = OperationPublicContractSetV1.build(
        (build_censal_operation_registration(censal_test_operation_definition()).contract,)
    )
    with pytest.raises(ValidationError):
        read_local_aeat_sync_workspace_projection(
            bucket_id=PROFILE_ID,
            subject_key="00000000T",
            observed_at=NOW,
            filings=(),
            operation_contracts=contracts,
            censo_values={"contact.fiscal_address": "x" * 257},
        )
    door = plain_generation_door(
        authority_operation,
        profile=profile,
        work_units=work_units,
        revisions=revisions,
        filings=filings,
        operation_contracts=contracts,
        ledger_action_ports=ledger_ports(
            authority_operation,
            transactions=StableStore(TransactionCatalogue()),
            invoices=StableStore(InvoiceCatalogue()),
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

    profile = Repository(profile_record(authority_operation))
    work_units = Repository(WorkUnitCatalogue())
    revisions = Repository(CalculationRevisionCatalogue())
    filings = Repository(ModeloRecordCatalogue())
    contracts = OperationPublicContractSetV1.build(
        (build_censal_operation_registration(censal_test_operation_definition()).contract,)
    )
    with pytest.raises(AeatSyncWorkspaceProjectionError, match="subject key cannot be blank"):
        read_local_aeat_sync_workspace_projection(
            bucket_id=PROFILE_ID,
            subject_key=" ",
            observed_at=NOW,
            filings=(),
            operation_contracts=contracts,
            censo_values={},
        )
    door = plain_generation_door(
        authority_operation,
        profile=profile,
        work_units=work_units,
        revisions=revisions,
        filings=filings,
        operation_contracts=contracts,
    )

    projection, refusal = door._read_aeat_sync(
        " ",
        observed_at=NOW,
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
    profile = Repository(profile_record(authority_operation))
    work_units = Repository(WorkUnitCatalogue(), revisions=("work-1", "work-2"))
    revisions = Repository(CalculationRevisionCatalogue())
    filings = Repository(ModeloRecordCatalogue())

    stub_empty_calendar(monkeypatch)
    door = plain_generation_door(
        authority_operation,
        profile=profile,
        work_units=work_units,
        revisions=revisions,
        filings=filings,
    )

    with pytest.raises(InternalInvariantError, match="changed during capture"):
        door.read_workbench_generation_inputs()
