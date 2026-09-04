"""The pre-pull AEAT Sync reading, and the three local answers it must keep apart.

A local source this session READ and found empty is not the same fact as a local
source it never read, and neither is the same as the AEAT side nobody has pulled.
The row model carries three states for exactly that reason, and this proves the
reader spends all three rather than collapsing the first two.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ...operations.registry import OperationPublicContractSetV1
from ...user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION,
    build_censal_operation_registration,
)
from ..workspace import (
    AeatSyncOverviewArea,
    AeatSyncSourceState,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceSource,
)
from ..workspace_reader import read_local_aeat_sync_workspace_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "00000000-0000-4000-8000-000000000001"
_SUBJECT = "00000001R"
_NOW = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)


def _unrelated_contracts() -> OperationPublicContractSetV1:
    """A real registered operation that is NOT any AEAT pull.

    The contract set cannot be empty, so the absence being proven -- that no
    pull action is offered without its own operation -- needs a set that is
    populated yet contains nothing this workspace could act on.
    """
    return OperationPublicContractSetV1.build(
        (build_censal_operation_registration(CENSAL_OPERATION_DEFINITION).contract,)
    )


def _projection(*, contracts: OperationPublicContractSetV1 | None = None):
    return read_local_aeat_sync_workspace_projection(
        bucket_id=_BUCKET,
        subject_key=_SUBJECT,
        observed_at=_NOW,
        filings=(),
        operation_contracts=contracts if contracts is not None else _unrelated_contracts(),
    )


def _overview_row(projection, area: AeatSyncOverviewArea):
    return next(row for row in projection.overview if row.area is area)


def test_a_read_and_empty_local_filing_catalogue_is_absent_not_unobserved() -> None:
    """An observed zero must not be reported as a source nobody read.

    The door loads the filing catalogue on every capture. When it holds
    nothing, that is a fact about the profile, and saying NOT_OBSERVED instead
    would describe the reader rather than the records.
    """
    row = _overview_row(_projection(), AeatSyncOverviewArea.FILED_DECLARATIONS)

    assert row.local_state is AeatSyncSourceState.ABSENT
    assert row.local_observed_at == _NOW


def test_evidence_comparison_reports_its_local_side_as_read_too() -> None:
    """Evidence comparison declares local.filings and must not claim it is unread."""
    row = _overview_row(_projection(), AeatSyncOverviewArea.EVIDENCE_COMPARISON)

    assert row.local_state is AeatSyncSourceState.ABSENT
    assert row.local_observed_at == _NOW


def test_an_area_with_no_local_reader_stays_genuinely_unobserved() -> None:
    """Notifications have no local reader here, so ABSENT would be the lie."""
    row = _overview_row(_projection(), AeatSyncOverviewArea.NOTIFICATIONS)

    assert row.local_state is AeatSyncSourceState.NOT_OBSERVED
    assert row.local_observed_at is None


def test_the_three_local_answers_remain_distinguishable_in_one_projection() -> None:
    """The whole point: read-and-empty, never-read, and the unpulled AEAT side.

    A reader that collapsed any pair would still satisfy each single-area
    assertion above by accident, so this asserts they differ from each other.
    """
    projection = _projection()
    census = _overview_row(projection, AeatSyncOverviewArea.CENSUS)
    filed = _overview_row(projection, AeatSyncOverviewArea.FILED_DECLARATIONS)
    notifications = _overview_row(projection, AeatSyncOverviewArea.NOTIFICATIONS)

    assert census.local_state is AeatSyncSourceState.PRESENT
    assert filed.local_state is AeatSyncSourceState.ABSENT
    assert notifications.local_state is AeatSyncSourceState.NOT_OBSERVED
    assert len({census.local_state, filed.local_state, notifications.local_state}) == 3
    assert {row.aeat_state for row in projection.overview} == {AeatSyncSourceState.NOT_OBSERVED}


def test_the_source_observation_agrees_with_the_row_it_backs() -> None:
    """A row claiming an observed zero needs a source that says it observed one.

    These are published side by side; the defect this catches is the projection
    contradicting itself -- an available source with a zero count beside a row
    reporting that same source as never observed.
    """
    projection = _projection()
    filed_zone = next(zone for zone in projection.zones if zone.zone.value == "filed_declarations")
    local = next(source for source in filed_zone.sources if source.source is AeatSyncWorkspaceSource.LOCAL_FILINGS)

    assert local.availability is AeatSyncWorkspaceAvailability.AVAILABLE
    assert local.item_count == 0
    assert _overview_row(projection, AeatSyncOverviewArea.FILED_DECLARATIONS).local_state is (
        AeatSyncSourceState.ABSENT
    )


def test_no_pull_action_is_offered_without_its_registered_operation() -> None:
    """A pull the session cannot perform must not appear as an offer.

    The contract set here holds one real registered operation -- the censal
    review -- and no AEAT pull. The census row may therefore legitimately offer
    its own operation; what must never appear is a filed-history pull, because
    nothing in this session could carry it out.
    """
    projection = _projection()
    offered = {str(action.action_id) for row in projection.overview for action in row.supported_actions}
    operations = {str(item) for row in projection.overview for item in row.supported_operations}

    assert "operator.live.filed.pull_all" not in offered
    assert "live.filed-history.pull" not in operations
