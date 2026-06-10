"""Real-behaviour tests for the D1 reconcile-and-assert contract (period-revision-resolution decision).

Covers:

- Creation gate: ``resolve_registry_revision_for_work_target`` refuses an
  explicit ``--revision`` that diverges from the law-determined revision with an
  instructive message naming both the requested and law-determined revision.

- Calc-time assertion: the equality assertion
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
# Fixture: real isolated profile for the calc-time-assertion test (real repository needed)
# -------------------------------------------------------------------


@pytest.fixture
def work_unit_repo(tmp_path: Path) -> Iterator[tuple[str, WorkUnitCatalogueRepository]]:
    """Yield an isolated bucket and work-unit repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="d1-contract-test") as profile:
        yield profile.bucket_id, WorkUnitCatalogueRepository(objects=profile.repository)


# ===========================================================================
# Creation gate strengthened to resolver-equality
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

    def test_refuses_revision_that_covers_year_but_not_period(self) -> None:
        """The PRECISE D1 hole: a revision that COVERS the filing year but NOT the period.

        This is the exact divergence the period-revision-resolution D1 decision describes
        and the reason the old year-only ``_revision_covers_year`` check was a hole:
        a revision covering the year but a *different period* passed the old guard and
        created a unit whose identity claimed one revision while calculation silently
        computed under another.

        M369 (OSS/IOSS) has three revisions that all cover year 2021-onwards but with
        DISJOINT period sets:
        - ``esquema-union`` -> quarterly tokens (1T..4T)
        - ``esquema-importacion`` -> monthly tokens (01..12)
        - ``esquema-exterior`` -> EXT-1T..EXT-4T

        For year 2026, period 1T the law-determined revision is ``esquema-union``.
        ``esquema-importacion`` COVERS year 2026 (valid 2021-onwards) but its period
        set is 01..12, NOT 1T.

        The OLD year-only check would have WRONGLY ACCEPTED ``esquema-importacion``
        (it covers 2026); the NEW resolver-equality check, which delegates to
        ``select_revision(..., revision_id=...)``, REFUSES it because the year+period
        narrowing finds no covering revision for that id.  This test therefore fails
        under the old year-only implementation and passes only under the new
        resolver-equality implementation — proving the fix closes the actual D1 hole.
        """
        # Sanity-anchor the law-determined revision for the period.
        law_determined = resolve_registry_revision_for_work_target(
            modelo="369",
            filing_year=2026,
            period="1T",
            registry_revision_id=None,
        )
        assert law_determined == "esquema-union"

        # The hole: a revision covering the YEAR but not the PERIOD must be refused.
        with pytest.raises(ModeloWorkRegistryYearMismatchError) as exc_info:
            resolve_registry_revision_for_work_target(
                modelo="369",
                filing_year=2026,
                period="1T",
                registry_revision_id="esquema-importacion",
            )
        msg = str(exc_info.value)
        assert "esquema-importacion" in msg, "message must name the requested (year-covering) revision"
        assert "esquema-union" in msg, "message must name the law-determined revision for the period"
        assert "law" in msg.lower() or "fixed by" in msg.lower()


# ===========================================================================
# Calc-time assertion on revision divergence
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
        creation gate would refuse this unit; we are simulating the
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
            work_unit_id=work_unit_id,  # type: WorkUnitId
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
            work_unit_id=work_unit_id,  # type: WorkUnitId
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


# ===========================================================================
# Defense-in-depth: calc-time assertion in _revision_for_work_unit
# ===========================================================================


class TestS02RevisionForWorkUnitAssertion:
    """``_calculate_input._revision_for_work_unit`` must also assert revision identity.

    ``_revision_for_work_unit`` is the operator-input-normalisation calc entry
    named alongside ``calculate_modelo_revision`` (D1 ruling 2).  It loads a
    WorkUnit and resolves a snapshot from its year + period, so it must carry the
    same equality assertion (closing ruling 2 "both ends").

    This path uses the default ``get_work_unit`` repository, so the stale unit is
    seeded through the default ``WorkUnitCatalogueRepository`` (which resolves to
    the same isolated store under ``isolated_runtime_profile``).
    """

    def test_revision_for_work_unit_refuses_stale_revision(
        self,
        work_unit_repo: tuple[str, WorkUnitCatalogueRepository],
    ) -> None:
        """``_revision_for_work_unit`` refuses when the unit's revision_id is stale.

        Uses M303 2026 1T: the law-determined revision is ``2023-y-siguientes``;
        the seeded unit pins the stale ``2009-y-siguientes``.
        """
        from .._calculate_input import _revision_for_work_unit

        bucket_id, _ = work_unit_repo
        stale_revision_id = "2009-y-siguientes"
        work_unit_id = derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period="1T",
            revision_id=stale_revision_id,
        )
        stale_unit = WorkUnit(
            work_unit_id=work_unit_id,  # type: WorkUnitId
            bucket_id=bucket_id,
            modelo=ModeloCode("303"),
            filing_year=2026,
            period="1T",
            revision_id=stale_revision_id,
            name="303-2026-1T",
            created_at=_T0,
            updated_at=_T0,
        )
        # Seed via the DEFAULT repository so the inner get_work_unit() finds it.
        default_repo = WorkUnitCatalogueRepository()
        default_repo.save(upsert_work_unit(default_repo.load(), stale_unit))

        with pytest.raises(WorkUnitRevisionDivergenceError) as exc_info:
            _revision_for_work_unit(work_unit_id)

        msg = str(exc_info.value)
        assert "2009-y-siguientes" in msg, "message must name the stale (pinned) revision"
        assert "2023-y-siguientes" in msg, "message must name the law-determined revision"
        assert "re-create" in msg.lower()

    def test_revision_for_work_unit_passes_for_correctly_pinned_revision(
        self,
        work_unit_repo: tuple[str, WorkUnitCatalogueRepository],
    ) -> None:
        """``_revision_for_work_unit`` returns the revision when the unit is correctly pinned."""
        from .._calculate_input import _revision_for_work_unit

        bucket_id, _ = work_unit_repo
        correct_revision_id = "2023-y-siguientes"
        work_unit_id = derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period="1T",
            revision_id=correct_revision_id,
        )
        correct_unit = WorkUnit(
            work_unit_id=work_unit_id,  # type: WorkUnitId
            bucket_id=bucket_id,
            modelo=ModeloCode("303"),
            filing_year=2026,
            period="1T",
            revision_id=correct_revision_id,
            name="303-2026-1T",
            created_at=_T0,
            updated_at=_T0,
        )
        default_repo = WorkUnitCatalogueRepository()
        default_repo.save(upsert_work_unit(default_repo.load(), correct_unit))

        revision = _revision_for_work_unit(work_unit_id)
        assert revision.id == correct_revision_id
