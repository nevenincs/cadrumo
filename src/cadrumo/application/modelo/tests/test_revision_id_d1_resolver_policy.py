"""Inward D1 resolver-policy tests for pinned revision identity.

These assertions exercise application-owned resolver projections directly.  The
profile-backed creation-door and storage tests live in the persistence adapter
suite; no repository is needed to prove that a supplied ``WorkUnit`` either
matches or diverges from the law-determined revision.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id

from ....domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    revision_covering,
    revision_serving_period,
)
from ..action_errors import WorkUnitRevisionDivergenceError
from ..calculate_input import revision_for_work_unit
from ..calculation_helpers import resolve_registry_snapshot_for_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_T0 = datetime(_YEAR, 6, 10, 10, 0, 0, tzinfo=UTC)
_CURRENT_REVISION = str(revision_serving_period("303", _YEAR, "1T").id)
_STALE_REVISION = str(revision_covering("303", filing_year_envelope().floor).id)
_CALC_BUCKET_ID = "65c4334d-2458-4967-9e2f-5046012b4484"


def _work_unit(*, revision_id: str) -> WorkUnit:
    """Build a deterministic in-memory work unit for resolver-policy tests."""
    period = Period.from_year_and_code(_YEAR, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_CALC_BUCKET_ID,
            modelo="303",
            filing_year=_YEAR,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_CALC_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"303-{_YEAR}-1T",
        created_at=_T0,
        updated_at=_T0,
    )


class TestCalcTimeRevisionAssertion:
    """The shared snapshot resolver enforces D1 revision equality."""

    def test_calc_time_assertion_refuses_stale_revision(self, authority_operation: PinnedAuthorityOperation) -> None:
        """A stale pinned revision is refused with actionable guidance."""
        stale_unit = _work_unit(revision_id=_STALE_REVISION)

        with pytest.raises(WorkUnitRevisionDivergenceError) as exc_info:
            resolve_registry_snapshot_for_work_unit(stale_unit, operation=authority_operation)

        with override_settings(cadrumo_output_language="en"):
            msg = resolve_error_message(exc_info.value)
        assert _STALE_REVISION in msg, "message must name the stale (pinned) revision"
        assert _CURRENT_REVISION in msg, "message must name the law-determined revision"
        assert "create the declaration again" in msg.lower(), (
            "message must tell the filer how to move to the current version"
        )

    def test_calc_time_assertion_passes_for_correctly_pinned_revision(
        self, authority_operation: PinnedAuthorityOperation
    ) -> None:
        """The law-determined pin passes the resolver assertion unchanged."""
        correct_revision_id = _CURRENT_REVISION
        correct_unit = _work_unit(revision_id=correct_revision_id)

        snapshot = resolve_registry_snapshot_for_work_unit(correct_unit, operation=authority_operation)

        assert snapshot.revision.id == correct_revision_id


class TestRevisionForWorkUnitAssertion:
    """The calculate-input projection preserves the shared D1 assertion."""

    def test_revision_for_work_unit_refuses_stale_revision(self, authority_operation: PinnedAuthorityOperation) -> None:
        """The calculation-input revision projection refuses a stale pin."""
        stale_unit = _work_unit(revision_id=_STALE_REVISION)

        with pytest.raises(WorkUnitRevisionDivergenceError) as exc_info:
            revision_for_work_unit(stale_unit, operation=authority_operation)

        with override_settings(cadrumo_output_language="en"):
            msg = resolve_error_message(exc_info.value)
        assert _STALE_REVISION in msg, "message must name the stale (pinned) revision"
        assert _CURRENT_REVISION in msg, "message must name the law-determined revision"
        assert "create the declaration again" in msg.lower(), (
            "message must tell the filer how to move to the current version"
        )

    def test_revision_for_work_unit_passes_for_correctly_pinned_revision(
        self, authority_operation: PinnedAuthorityOperation
    ) -> None:
        """The calculation-input revision projection accepts a correct pin."""
        correct_revision_id = _CURRENT_REVISION
        correct_unit = _work_unit(revision_id=correct_revision_id)

        revision = revision_for_work_unit(correct_unit, operation=authority_operation)

        assert revision.id == correct_revision_id
