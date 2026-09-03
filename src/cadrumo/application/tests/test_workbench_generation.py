"""Contract tests for the pure installed-workbench generation assembler."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ..aeat_sync.workspace import AeatSyncWorkspaceProjectionV1
from ..ledger.workspace import LedgerWorkspaceProjectionV1
from ..modelo.declarations_workspace import DeclarationsWorkspaceProjectionV1
from ..modelo.workspace_models import ModeloWorkspaceProjectionV1
from ..overview.home import (
    HomeAccountSession,
    HomeAvailability,
    HomeProjectionInput,
    HomeSessionPosture,
    HomeZoneState,
)
from ..search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from ..workbench_generation import (
    CallableWorkbenchGenerationReadDoorV1,
    WorkbenchGenerationAvailability,
    WorkbenchGenerationInputsV1,
    WorkbenchGenerationSourceResultV1,
    assemble_workbench_generation,
    assemble_workbench_generation_from,
)


_NOW = datetime(2026, 9, 3, 10, 30, tzinfo=UTC)


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


def _admission(destination: str) -> WorkbenchDestinationAdmission:
    """Return a route admission independent from source-capture state."""
    return WorkbenchDestinationAdmission(
        destination=destination,
        state=WorkbenchDestinationAdmissionState.AVAILABLE,
    )


def _inputs(
    *,
    ledger: WorkbenchGenerationSourceResultV1[LedgerWorkspaceProjectionV1] | None = None,
    declarations: WorkbenchGenerationSourceResultV1[DeclarationsWorkspaceProjectionV1] | None = None,
    aeat_sync: WorkbenchGenerationSourceResultV1[AeatSyncWorkspaceProjectionV1] | None = None,
    modelo: WorkbenchGenerationSourceResultV1[tuple[ModeloWorkspaceProjectionV1, ...]] | None = None,
) -> WorkbenchGenerationInputsV1:
    """Build the typed input bundle using only explicit missing source results."""
    return WorkbenchGenerationInputsV1(
        assembled_at=_NOW,
        home=WorkbenchGenerationSourceResultV1.available(_home_input(), observed_at=_NOW),
        ledger=ledger or WorkbenchGenerationSourceResultV1.never_captured(refusal="source.ledger"),
        declarations=declarations or WorkbenchGenerationSourceResultV1.never_captured(refusal="source.declarations"),
        aeat_sync=aeat_sync or WorkbenchGenerationSourceResultV1.never_captured(refusal="source.aeat_sync"),
        modelo=modelo or WorkbenchGenerationSourceResultV1.never_captured(refusal="source.modelo"),
        ledger_admission=_admission("workbench.ledger"),
        declarations_admission=_admission("workbench.declarations"),
        aeat_sync_admission=_admission("workbench.aeat_sync"),
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


def test_generation_projects_home_and_never_turns_missing_areas_into_empty() -> None:
    """Missing production loaders remain explicit refusals in every output area."""
    generation = assemble_workbench_generation(_inputs())

    assert generation.home.projection is not None
    assert generation.home.availability is WorkbenchGenerationAvailability.AVAILABLE
    assert generation.ledger.projection is None
    assert generation.declarations.projection is None
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
    assert generation.search.refusal == "source.aeat_down"


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
    assert "value" not in generation.model_fields
    assert all(
        "value" not in type(getattr(generation, name)).model_fields
        for name in ("home", "ledger", "declarations", "aeat_sync", "modelo", "search")
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
