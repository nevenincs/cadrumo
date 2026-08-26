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

- Door reconfirmation: ``create_work_unit`` itself -- not just the
  ``resolve_registry_revision_for_work_target`` wrapper the one production
  caller (``ensure_modelo_work_unit_for_active_target``) routes through --
  refuses a syntactically valid, period-declared ``revision_id`` that is not
  the law-determined revision for its ``(modelo, filing_year, period)``. This
  closes the residual gap: a caller that reaches the persistence door directly
  (any of the ~90 direct callers found across the tree, nearly all tests)
  bypassing the one production wrapper could otherwise persist a work unit
  under the wrong year's norms with no signal.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import Period
from ....core.config import override_settings
from ....core.errors import resolve_error_message
from ....domain.modelos import (
    ModeloCode,
    WorkUnit,
    derive_work_unit_id,
    upsert_work_unit,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from .._action_errors import WorkUnitRevisionDivergenceError
from .._work_lifecycle import create_work_unit
from ..work_addressing import (
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="65c4334d-2458-4967-9e2f-5046012b4484") as profile:
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
            period=Period.from_year_and_code(2026, "1T"),
            registry_revision_id=None,
        )
        assert result == "2019-y-siguientes"

    def test_accepts_explicit_revision_that_matches_law_determined(self) -> None:
        """An explicit --revision equal to the law-determined revision is idempotent."""
        result = resolve_registry_revision_for_work_target(
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            registry_revision_id="2019-y-siguientes",
        )
        assert result == "2019-y-siguientes"

    def test_refuses_explicit_revision_that_diverges_from_law_determined(self) -> None:
        """An explicit --revision that is NOT the law-determined revision is refused.

        M303 has three revisions:
        - ``2022`` covers 2022
           - 2023, two 2024 epochs, and 2025 have distinct filing windows
        - ``2026-y-siguientes`` covers 2026-onwards

        For year 2026, period 1T the law-determined revision is ``2026-y-siguientes``.
        Supplying ``2022`` (a real revision that does NOT cover 2026)
        must be refused.
        """
        with pytest.raises(ModeloWorkRegistryYearMismatchError) as exc_info:
            resolve_registry_revision_for_work_target(
                modelo="303",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                registry_revision_id="2022",
            )
        # The refusal's prose lives in the locale catalogue and reaches the
        # operator through the renderer; str(exc) is only the message KEY, so
        # rendering is what these guidance claims must be asserted against.
        with override_settings(cadrumo_output_language="en"):
            msg = resolve_error_message(exc_info.value)
        # Must name the requested revision
        assert "2022" in msg
        # Must name the law-determined revision
        assert "2026-y-siguientes" in msg
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
                period=Period.from_year_and_code(2026, "1T"),
                registry_revision_id="2022",
            )
        # The refusal's prose lives in the locale catalogue and reaches the
        # operator through the renderer; str(exc) is only the message KEY, so
        # rendering is what these guidance claims must be asserted against.
        with override_settings(cadrumo_output_language="en"):
            msg = resolve_error_message(exc_info.value)
        assert "2022" in msg, "message must name the requested revision"
        assert "2026-y-siguientes" in msg, "message must name the law-determined revision"
        # Should direct operator to re-create without --revision
        assert "re-create" in msg.lower() or "--revision" in msg.lower() or "without" in msg.lower()

    def test_returns_correct_law_determined_revision_for_m303_2026(self) -> None:
        """Smoke test: M303 2026 1T resolves to the 2026-y-siguientes revision."""
        result = resolve_registry_revision_for_work_target(
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            registry_revision_id=None,
        )
        assert result == "2026-y-siguientes"

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
            period=Period.from_year_and_code(2026, "1T"),
            registry_revision_id=None,
        )
        assert law_determined == "esquema-union"

        # The hole: a revision covering the YEAR but not the PERIOD must be refused.
        with pytest.raises(ModeloWorkRegistryYearMismatchError) as exc_info:
            resolve_registry_revision_for_work_target(
                modelo="369",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                registry_revision_id="esquema-importacion",
            )
        # The refusal's prose lives in the locale catalogue and reaches the
        # operator through the renderer; str(exc) is only the message KEY, so
        # rendering is what these guidance claims must be asserted against.
        with override_settings(cadrumo_output_language="en"):
            msg = resolve_error_message(exc_info.value)
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

        For M303 2026 1T the current law-determined revision is ``2026-y-siguientes``.
        We pin ``revision_id=2022`` (a real registry revision,
        but one that covers 2022, not 2026).  After a hypothetical registry
        correction this is the shape a pre-gate unit would have.

        Note: We bypass ``create_work_unit`` deliberately.  The strengthened
        creation gate would refuse this unit; we are simulating the
        post-creation-correction scenario that the calc-time assertion guards.
        """
        stale_revision_id = "2022"
        work_unit_id = derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id=stale_revision_id,
        )
        return WorkUnit(
            work_unit_id=work_unit_id,  # type: WorkUnitId
            bucket_id=bucket_id,
            modelo=ModeloCode("303"),
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
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

        # The refusal's prose lives in the locale catalogue and reaches the
        # operator through the renderer; str(exc) is only the message KEY, so
        # rendering is what these guidance claims must be asserted against.
        with override_settings(cadrumo_output_language="en"):
            msg = resolve_error_message(exc_info.value)
        # Must name the work unit's stale revision
        assert "2022" in msg, "message must name the stale (pinned) revision"
        # Must name the current law-determined revision
        assert "2026-y-siguientes" in msg, "message must name the law-determined revision"
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
        correct_revision_id = "2026-y-siguientes"
        work_unit_id = derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id=correct_revision_id,
        )
        correct_unit = WorkUnit(
            work_unit_id=work_unit_id,  # type: WorkUnitId
            bucket_id=bucket_id,
            modelo=ModeloCode("303"),
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
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
    """``_calculate_input._revision_for_work_unit`` projects the shared assertion.

    ``_revision_for_work_unit`` is the operator-input-normalisation calc entry
    named alongside ``calculate_modelo_revision`` (D1 ruling 2). It loads a
    work unit, then projects the revision from the canonical snapshot resolver,
    so both calculate paths enforce one equality assertion.

    This path uses the default ``get_work_unit`` repository, so the stale unit is
    seeded through the default ``WorkUnitCatalogueRepository`` (which resolves to
    the same isolated store under ``isolated_runtime_profile``).
    """

    def test_revision_for_work_unit_refuses_stale_revision(
        self,
        work_unit_repo: tuple[str, WorkUnitCatalogueRepository],
    ) -> None:
        """``_revision_for_work_unit`` refuses when the unit's revision_id is stale.

        Uses M303 2026 1T: the law-determined revision is ``2026-y-siguientes``;
        the seeded unit pins the stale ``2022``.
        """
        from .._calculate_input import _revision_for_work_unit

        bucket_id, _ = work_unit_repo
        stale_revision_id = "2022"
        work_unit_id = derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id=stale_revision_id,
        )
        stale_unit = WorkUnit(
            work_unit_id=work_unit_id,  # type: WorkUnitId
            bucket_id=bucket_id,
            modelo=ModeloCode("303"),
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
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

        # The refusal's prose lives in the locale catalogue and reaches the
        # operator through the renderer; str(exc) is only the message KEY, so
        # rendering is what these guidance claims must be asserted against.
        with override_settings(cadrumo_output_language="en"):
            msg = resolve_error_message(exc_info.value)
        assert "2022" in msg, "message must name the stale (pinned) revision"
        assert "2026-y-siguientes" in msg, "message must name the law-determined revision"
        assert "re-create" in msg.lower()

    def test_revision_for_work_unit_passes_for_correctly_pinned_revision(
        self,
        work_unit_repo: tuple[str, WorkUnitCatalogueRepository],
    ) -> None:
        """``_revision_for_work_unit`` returns the revision when the unit is correctly pinned."""
        from .._calculate_input import _revision_for_work_unit

        bucket_id, _ = work_unit_repo
        correct_revision_id = "2026-y-siguientes"
        work_unit_id = derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id=correct_revision_id,
        )
        correct_unit = WorkUnit(
            work_unit_id=work_unit_id,  # type: WorkUnitId
            bucket_id=bucket_id,
            modelo=ModeloCode("303"),
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id=correct_revision_id,
            name="303-2026-1T",
            created_at=_T0,
            updated_at=_T0,
        )
        default_repo = WorkUnitCatalogueRepository()
        default_repo.save(upsert_work_unit(default_repo.load(), correct_unit))

        revision = _revision_for_work_unit(work_unit_id)
        assert revision.id == correct_revision_id


# ===========================================================================
# Door reconfirmation: create_work_unit itself, called directly
# ===========================================================================

_M303_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="censo.activity_start_date", value="2020-01-01"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


_DOOR_BUCKET_ID = "d1230300-0000-4000-8000-000000000399"


@pytest.fixture
def door_reconfirmation_repo(tmp_path: Path) -> Iterator[tuple[str, WorkUnitCatalogueRepository]]:
    """Yield an isolated bucket and work-unit repository, UUID-shaped for profile persistence."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_DOOR_BUCKET_ID) as profile:
        yield profile.bucket_id, WorkUnitCatalogueRepository(objects=profile.repository)


def _seed_m303_ready_profile(bucket_id: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=_M303_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
        ),
    )


class TestS03CreateWorkUnitDoorReconfirmation:
    """``create_work_unit`` re-confirms the law-determined revision itself.

    ``resolve_registry_revision_for_work_target`` (the sibling contract above) only guards
    callers that route through it. The population census for this gap found
    exactly one production caller doing so (``ensure_modelo_work_unit_for_active_target``)
    against roughly ninety direct ``create_work_unit`` call sites -- nearly all
    of them tests. A static gate confined to production call sites would be
    close to vacuous against that population; re-confirming inside
    ``create_work_unit`` itself protects every caller, present and future,
    regardless of how it reached the door.
    """

    def test_create_work_unit_refuses_a_revision_that_diverges_from_law_determined(
        self,
        door_reconfirmation_repo: tuple[str, WorkUnitCatalogueRepository],
    ) -> None:
        """A real, period-declared, but year-wrong revision id is refused at creation.

        Mirrors the sibling scenario one level down: ``2022`` is a
        real M303 revision declaring the ``1T`` period token, but it covers
        2022, not 2026. Calling ``create_work_unit`` directly -- the shape
        every one of the ~90 direct callers uses -- must refuse exactly as
        ``resolve_registry_revision_for_work_target`` would, not silently
        build a 2026 work unit under 2022 norms.
        """
        bucket_id, repo = door_reconfirmation_repo
        _seed_m303_ready_profile(bucket_id)

        with pytest.raises(ModeloWorkRegistryYearMismatchError) as exc_info:
            create_work_unit(
                bucket_id=bucket_id,
                modelo="303",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                revision_id="2022",
                repository=repo,
                clock=_T0,
            )
        # The refusal's prose lives in the locale catalogue and reaches the
        # operator through the renderer; str(exc) is only the message KEY, so
        # rendering is what these guidance claims must be asserted against.
        with override_settings(cadrumo_output_language="en"):
            msg = resolve_error_message(exc_info.value)
        assert "2022" in msg
        assert "2026-y-siguientes" in msg

        # No work unit was persisted for the refused key.
        stray_id = derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id="2022",
        )
        assert repo.load().get(stray_id) is None

    def test_create_work_unit_accepts_the_law_determined_revision(
        self,
        door_reconfirmation_repo: tuple[str, WorkUnitCatalogueRepository],
    ) -> None:
        """The correctly-resolved revision id still creates a work unit.

        Proves the door reconfirmation is not over-broad: the exact revision
        ``resolve_registry_revision_for_work_target`` would itself return for
        this ``(modelo, filing_year, period)`` triple must pass unchanged.
        """
        bucket_id, repo = door_reconfirmation_repo
        _seed_m303_ready_profile(bucket_id)

        unit = create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id="2026-y-siguientes",
            repository=repo,
            clock=_T0,
        )
        assert unit.revision_id == "2026-y-siguientes"
        assert repo.load().get(unit.work_unit_id) is not None
