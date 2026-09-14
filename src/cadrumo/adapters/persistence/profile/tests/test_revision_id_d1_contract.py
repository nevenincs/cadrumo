"""Profile-persistence tests for the D1 reconcile-and-assert contract (period-revision-resolution decision).

Covers:

- Creation gate: ``law_selected_revision_for_work_target`` refuses an
  explicit ``--revision`` that diverges from the law-determined revision with an
  instructive message naming both the requested and law-determined revision.

- Door reconfirmation: ``create_work_unit`` itself -- not just the
  ``law_selected_revision_for_work_target`` wrapper the one production
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

from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.core.period import Period
from cadrumo.domain.modelos.work_unit import derive_work_unit_id
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.modelo.work_addressing import (
    ModeloWorkRegistryYearMismatchError,
    law_selected_revision_for_work_target,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_T0 = datetime(2026, 6, 10, 10, 0, 0, tzinfo=UTC)

# ===========================================================================
# Creation gate strengthened to resolver-equality
# ===========================================================================


class TestS01CreationGate:
    """``law_selected_revision_for_work_target`` must enforce resolver-equality."""

    def test_returns_law_determined_revision_when_no_explicit_revision_given(self) -> None:
        """Without an explicit revision the resolver picks the law-determined one."""
        # M130 2026 1T -> only one revision: 2019-y-siguientes
        result = law_selected_revision_for_work_target(
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            requested_revision_id=None,
        )
        assert result == "2019-y-siguientes"

    def test_accepts_explicit_revision_that_matches_law_determined(self) -> None:
        """An explicit --revision equal to the law-determined revision is idempotent."""
        result = law_selected_revision_for_work_target(
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            requested_revision_id="2019-y-siguientes",
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
            law_selected_revision_for_work_target(
                modelo="303",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                requested_revision_id="2022",
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
            law_selected_revision_for_work_target(
                modelo="303",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                requested_revision_id="2022",
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
        result = law_selected_revision_for_work_target(
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            requested_revision_id=None,
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
        law_determined = law_selected_revision_for_work_target(
            modelo="369",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            requested_revision_id=None,
        )
        assert law_determined == "esquema-union"

        # The hole: a revision covering the YEAR but not the PERIOD must be refused.
        with pytest.raises(ModeloWorkRegistryYearMismatchError) as exc_info:
            law_selected_revision_for_work_target(
                modelo="369",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                requested_revision_id="esquema-importacion",
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

    ``law_selected_revision_for_work_target`` (the sibling contract above) only guards
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
        ``law_selected_revision_for_work_target`` would, not silently
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
        ``law_selected_revision_for_work_target`` would itself return for
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
