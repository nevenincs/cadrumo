"""Canonical spreadsheet composition handoffs, without live provider calls."""

from __future__ import annotations

from decimal import Decimal
from typing import NoReturn
from uuid import UUID

import pytest

from ...adapters.outbound.google.calc_sheets_pull import compute_from_pull
from ...adapters.outbound.google.calc_sheets_pull_records import (
    MetadataMatchState,
    PullMetadata,
    PullResult,
    RowSetCellEdit,
    RowSetEdit,
)
from ...adapters.outbound.storage.errors import OutboundStorageConflictError
from ...application.modelo.modelo_spreadsheet_operation_contracts import ModeloSpreadsheetPullRequest
from ...application.operations.public_period import PublicPeriod
from ...application.storage.calc_sheets.engine import collect_row_sets, registry_sha
from ...core.config import override_settings
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.schema import RegistrySnapshot
from ..modelo_spreadsheet_operation_composition import (
    _pull_facts,
    _snapshot_mismatch_refusal,
    build_modelo_spreadsheet_operation_ports,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


def _foreign_asset(*, row_index: int) -> RowSetEdit:
    return RowSetEdit(
        grouping="per_foreign_asset",
        cells=(
            RowSetCellEdit(binding="modelo-720-asset-row-class", row_index=row_index, value="C"),
            RowSetCellEdit(binding="modelo-720-asset-row-country", row_index=row_index, value="CH"),
            RowSetCellEdit(binding="modelo-720-asset-row-currency", row_index=row_index, value="CHF"),
            RowSetCellEdit(
                binding="modelo-720-asset-row-identifier", row_index=row_index, value=f"synthetic-asset-{row_index}"
            ),
            RowSetCellEdit(binding="modelo-720-asset-row-acquisition-date", row_index=row_index, value="2020-01-15"),
            RowSetCellEdit(binding="modelo-720-asset-row-valuation", row_index=row_index, value=Decimal("120000")),
        ),
    )


def _pull(snapshot: RegistrySnapshot, rows: tuple[RowSetEdit, ...]) -> PullResult:
    return PullResult(
        spreadsheet_id="synthetic-workbook",
        operator_edits=(),
        binding_edits=(),
        relation_edits=(),
        row_set_edits=rows,
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=sum(len(row.cells) for row in rows),
        metadata=PullMetadata(
            modelo_id=snapshot.modelo.id,
            revision_id=snapshot.revision.id,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
            engine_version="synthetic-test",
            registry_sha="a" * 64,
        ),
    )


def test_complete_pull_assembly_preserves_every_populated_block_and_observation(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot = authority_operation.snapshot("720", filing_year=2025, period="0A")
    rows = (_foreign_asset(row_index=1), _foreign_asset(row_index=2), RowSetEdit(grouping="per_foreign_asset"))
    pulled = _pull(snapshot, rows)
    facts = _pull_facts(pulled, snapshot, assemble_observations=True)
    assert facts.row_set_edits_populated == 2 and facts.row_set_cells_populated == 12
    assert facts.assembled_observation_count == 2
    assert tuple(row.observations[0].source_id for row in facts.assembled_groupings) == (
        "detalle:per_foreign_asset:row-1",
        "detalle:per_foreign_asset:row-2",
    )
    observations = tuple(row.model_dump(mode="json")["observations"][0] for row in facts.assembled_groupings)
    assert observations[0]["valuation_amount"] == "120000"
    assert observations[1]["asset_identifier"] == "synthetic-asset-2"
    unassembled = _pull_facts(pulled, snapshot, assemble_observations=False)
    assert unassembled.row_set_edits == facts.row_set_edits
    assert unassembled.assembled_groupings == () and unassembled.assembled_observation_count == 0


def test_complete_pull_rejects_collision_between_distinct_blocks(authority_operation: PinnedAuthorityOperation) -> None:
    snapshot = authority_operation.snapshot("720", filing_year=2025, period="0A")
    with pytest.raises(RegistryValidationError) as refused:
        _pull_facts(
            _pull(snapshot, (_foreign_asset(row_index=1), _foreign_asset(row_index=1))),
            snapshot,
            assemble_observations=True,
        )
    assert refused.value.translated_message == "application.calculations.row_set.errors.row_assembly_failed"
    assert refused.value.context == {
        "row_index": 1,
        "validation_error_type": "row_set_ingress",
        "validation_error_detail": "row_ownership_collision",
        "grouping": "per_foreign_asset",
        "first_row_set_index": 0,
        "second_row_set_index": 1,
    }


def test_complete_pull_rejects_substitution_from_another_declared_grouping(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot = authority_operation.snapshot("349", filing_year=2025, period="1T")
    first, second = collect_row_sets(snapshot.revision)
    row = RowSetEdit(
        grouping=first.grouping, cells=(RowSetCellEdit(binding=second.columns[0].binding, row_index=1, value="DE"),)
    )
    with pytest.raises(RegistryValidationError) as refused:
        _pull_facts(_pull(snapshot, (row,)), snapshot, assemble_observations=True)
    assert refused.value.translated_message == "application.calculations.row_set.errors.row_assembly_failed"
    assert refused.value.context is not None
    assert refused.value.context["validation_error_detail"] == "caller_binding_substitution"
    assert refused.value.context["declared_grouping"] == second.grouping


def test_port_construction_is_lazy_and_denied_admission_precedes_credentials(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def credentials(*, profile: str) -> NoReturn:
        calls.append("credentials")
        pytest.fail("refused provider admission must prevent credential discovery")

    def root(*, profile: str, settings: object) -> str:
        assert profile == str(_PROFILE)
        calls.append("root")
        return "synthetic-drive-root"

    def denied() -> NoReturn:
        calls.append("admission")
        raise PermissionError("synthetic provider refusal")

    monkeypatch.setattr("cadrumo.adapters.outbound.storage.factory.build_google_credentials", credentials)
    monkeypatch.setattr("cadrumo.adapters.outbound.storage.factory.resolve_required_drive_root_folder_id", root)
    with override_settings(cadrumo_active_profile=str(_PROFILE)):
        ports = build_modelo_spreadsheet_operation_ports(profile_id=_PROFILE, operation=authority_operation)
        assert calls == []
        request = ModeloSpreadsheetPullRequest(
            profile_id=_PROFILE,
            modelo="130",
            period=PublicPeriod(filing_year=2026, code="1T"),
            spreadsheet_id="synthetic-workbook",
        )
        with pytest.raises(PermissionError, match="synthetic provider refusal"):
            ports.pull(request, admit_provider=denied)
    assert calls == ["root", "admission"]


def test_actual_snapshot_guard_translates_only_reviewed_binding_facts(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    snapshot = authority_operation.snapshot("720", filing_year=2025, period="0A")
    pulled = _pull(snapshot, ()).model_copy(update={"metadata_match": MetadataMatchState.STALE})
    with pytest.raises(OutboundStorageConflictError) as raised:
        compute_from_pull(snapshot, pulled)
    error = raised.value
    assert error.context is not None
    error.context["credential"] = "SECRET-CREDENTIAL"
    error.context["cell_value"] = "SECRET-CELL-VALUE"
    detail = _snapshot_mismatch_refusal(error, snapshot, "synthetic-workbook")
    assert detail.condition == "google.calc_sheets.pull.snapshot_aligned" and detail.snapshot_aligned is False
    assert (
        detail.metadata_match == "stale"
        and detail.snapshot_modelo == snapshot.modelo.id
        and detail.snapshot_revision == snapshot.revision.id
    )
    assert detail.workbook_engine_version == "synthetic-test"
    assert detail.snapshot_registry_sha == registry_sha(snapshot)
    assert "SECRET-" not in detail.model_dump_json()
    with pytest.raises(OutboundStorageConflictError):
        _snapshot_mismatch_refusal(error, snapshot, "another-workbook")
    with pytest.raises(OutboundStorageConflictError):
        _snapshot_mismatch_refusal(
            OutboundStorageConflictError("SECRET-GENERIC-CONFLICT"), snapshot, "synthetic-workbook"
        )
