"""Real-behaviour tests for the D1 reconcile-and-assert contract (period-revision-resolution ADR).

Covers:

- **S01** — creation gate: ``resolve_registry_revision_for_work_target`` refuses an
  explicit ``--revision`` that diverges from the law-determined revision with an
  instructive message naming both the requested and law-determined revision.

- **S02** — calc-time assertion: the equality assertion
  ``snapshot.revision.id == work_unit.revision_id`` fires when the registry's
  law-mapping has been corrected after unit creation (simulated by constructing a
  ``WorkUnit`` whose ``revision_id`` does not match the current law-determined
  revision) and refuses with an instructive message directing re-creation.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._ids import WorkUnitId
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests.secure_sql import isolated_runtime_profile
from .._action_errors import WorkUnitRevisionDivergenceError
from .._work_addressing import (
    ModeloWorkRegistryYearMismatchError,
    resolve_registry_revision_for_work_target,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 6, 10, 10, 0, 0, tzinfo=UTC)

# -------------------------------------------------------------------
# Fixture: real isolated profile for S02 test (needs real repository)
# -------------------------------------------------------------------


@pytest.fixture
def work_unit_repo(tmp_path: Path) -> Iterator[tuple[str, WorkUnitCatalogueRepository]]:
    """Yield an isolated bucket and work-unit repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="d1-contract-test") as profile:
        yield profile.bucket_id, WorkUnitCatalogueRepository(objects=profile.repository)


# ===========================================================================
# S01 — creation gate strengthened to resolver-equality
# ===========================================================================


class TestS01CreationGate:
    """``resolve_registry_revision_for_work_target`` must enforce resolver-equality."""

    def test_returns_law_determined_revision_when_no_explicit_revision_given(self) -> None:
        """Without an explicit revision the resolver picks the law-determined one."""
        # M130 2026 1T -> only one revision: 2019-y-siguientes
        result = resolve_registry_revision_for_work_target(
            modelo="130",
            filing_year=2026,
            period="1T",
            registry_revision_id=None,
        )
        assert result == "2019-y-siguientes"

    def test_accepts_explicit_revision_that_matches_law_determined(self) -> None:
        """An explicit --revision equal to the law-determined revision is idempotent."""
        result = resolve_registry_revision_for_work_target(
            modelo="130",
            filing_year=2026,
            period="1T",
            registry_revision_id="2019-y-siguientes",
        )
        assert result == "2019-y-siguientes"

    def test_refuses_explicit_revision_that_diverges_from_law_determined(self) -> None:
        """An explicit --revision that is NOT the law-determined revision is refused.

        M303 has two revisions:
        - ``2009-y-siguientes`` covers 2009-2022
        - ``2023-y-siguientes`` covers 2023-onwards

        For year 2026, period 1T the law-determined revision is ``2023-y-siguientes``.
        Supplying ``2009-y-siguientes`` (a real revision that does NOT cover 2026)
        must be refused.
        """
        with pytest.raises(ModeloWorkRegistryYearMismatchError) as exc_info:
            resolve_registry_revision_for_work_target(
                modelo="303",
                filing_year=2026,
                period="1T",
                registry_revision_id="2009-y-siguientes",
            )
        msg = str(exc_info.value)
        # Must name the requested revision
        assert "2009-y-siguientes" in msg
        # Must name the law-determined revision
        assert "2023-y-siguientes" in msg
        # Must state the binding is fixed by law
        assert "law" in msg.lower() or "fixed by" in msg.lower()

    def test_refusal_message_is_instructive_and_names_both_revisions(self) -> None:
        """The refusal message must name requested, law-determined, and the re-create instruction.

        Validates the CLI-boundary instructive-refusal mandate from
        ``aeat-architecture-boundaries``.
        """
        with pytest.raises(ModeloWorkRegistryYearMismatchError) as exc_info:
            resolve_registry_revision_for_work_target(
                modelo="303",
                filing_year=2026,
                period="1T",
                registry_revision_id="2009-y-siguientes",
            )
        msg = str(exc_info.value)
        assert "2009-y-siguientes" in msg, "message must name the requested revision"
        assert "2023-y-siguientes" in msg, "message must name the law-determined revision"
        # Should direct operator to re-create without --revision
        assert "re-create" in msg.lower() or "--revision" in msg.lower() or "without" in msg.lower()

    def test_returns_correct_law_determined_revision_for_m303_2026(self) -> None:
        """Smoke test: M303 2026 1T resolves to the 2023-y-siguientes revision."""
        result = resolve_registry_revision_for_work_target(
            modelo="303",
            filing_year=2026,
            period="1T",
            registry_revision_id=None,
        )
        assert result == "2023-y-siguientes"


# ===========================================================================
# S02 — calc-time assertion on revision divergence
# ===========================================================================


class TestS02CalcTimeAssertion:
    """The D1 calc-time assertion must fire when ``snapshot.revision.id != work_unit.revision_id``.

    The divergence scenario is: a work unit was persisted when the law-mapping said
    revision X, then the registry was corrected so the law-mapping now says revision Y.
    We simulate this by constructing a ``WorkUnit`` directly with a ``revision_id``
    that does not match the current law-determined revision for the same
    ``(modelo, filing_year, period)`` triple.
    """

    def _stale_work_unit(self, bucket_id: str) -> WorkUnit:
        """Construct a WorkUnit whose revision_id is stale (no longer law-determined).

        For M303 2026 1T the current law-determined revision is ``2023-y-siguientes``.
        We pin ``revision_id=2009-y-siguientes`` (a real registry revision,
        but one that covers 2009-2022, not 2026).  After a hypothetical registry
        correction this is the shape a pre-gate unit would have.

        Note: We bypass ``create_work_unit`` deliberately.  The strengthened
        creation gate (S01) would refuse this unit; we are simulating the
        post-creation-correction scenario that the calc-time assertion guards.
        """
        stale_revision_id = "2009-y-siguientes"
        work_unit_id = derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period="1T",
            revision_id=stale_revision_id,
        )
        return WorkUnit(
            work_unit_id=WorkUnitId(work_unit_id),
            bucket_id=bucket_id,
            modelo=ModeloCode("303"),
            filing_year=2026,
            period="1T",
            revision_id=stale_revision_id,
            name="303-2026-1T",
            created_at=_T0,
            updated_at=_T0,
        )

    def test_calc_time_assertion_refuses_stale_revision(
        self,
        work_unit_repo: tuple[str, WorkUnitCatalogueRepository],
    ) -> None:
        """``calculate_modelo_revision`` must refuse when the work unit's revision_id
        does not match the law-determined revision for its (modelo, filing_year, period).

        The refusal error must name both the pinned revision and the law-determined one.
        """
        from .._calculation_helpers import resolve_registry_snapshot_for_work_unit

        bucket_id, repo = work_unit_repo
        stale_unit = self._stale_work_unit(bucket_id)

        # Persist the stale unit so a realistic DB-loaded scenario is exercised.
        repo.save(upsert_work_unit(repo.load(), stale_unit))

        with pytest.raises(WorkUnitRevisionDivergenceError) as exc_info:
            resolve_registry_snapshot_for_work_unit(stale_unit)

        msg = str(exc_info.value)
        # Must name the work unit's stale revision
        assert "2009-y-siguientes" in msg, "message must name the stale (pinned) revision"
        # Must name the current law-determined revision
        assert "2023-y-siguientes" in msg, "message must name the law-determined revision"
        # Must direct operator to re-create the work unit
        assert "re-create" in msg.lower() or "recreate" in msg.lower() or "re-create" in msg

    def test_calc_time_assertion_passes_for_correctly_pinned_revision(
        self,
        work_unit_repo: tuple[str, WorkUnitCatalogueRepository],
    ) -> None:
        """``resolve_registry_snapshot_for_work_unit`` must NOT raise when the work
        unit's revision_id matches the law-determined revision.

        This is the normal (non-divergence) path; the assertion must be silent.
        """
        from .._calculation_helpers import resolve_registry_snapshot_for_work_unit

        bucket_id, repo = work_unit_repo
        correct_revision_id = "2023-y-siguientes"
        work_unit_id = derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period="1T",
            revision_id=correct_revision_id,
        )
        correct_unit = WorkUnit(
            work_unit_id=WorkUnitId(work_unit_id),
            bucket_id=bucket_id,
            modelo=ModeloCode("303"),
            filing_year=2026,
            period="1T",
            revision_id=correct_revision_id,
            name="303-2026-1T",
            created_at=_T0,
            updated_at=_T0,
        )
        repo.save(upsert_work_unit(repo.load(), correct_unit))

        # Must not raise
        snapshot = resolve_registry_snapshot_for_work_unit(correct_unit)
        assert snapshot.revision.id == correct_revision_id
