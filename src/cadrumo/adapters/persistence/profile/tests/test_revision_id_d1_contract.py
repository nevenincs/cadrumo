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

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.ready_profile_support import seed_ready_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.work_addressing import (
    ModeloWorkRegistryYearMismatchError,
    law_selected_revision_for_work_target,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    open_ended_revision,
    revision_serving_period,
    split_exercise_revisions,
)
from cadrumo.domain.modelos.work_unit import derive_work_unit_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_YEAR = filing_year_envelope().horizon
_T0 = datetime(_YEAR, 6, 10, 10, 0, 0, tzinfo=UTC)

# Modelo 303 splits one exercise between two designs at a period boundary: the
# early design serves 1T, the late one 2T onwards. The oldest authored design
# is a real revision declaring 1T that covers none of the split exercise.
_M303_EARLY, _M303_LATE = split_exercise_revisions("303", early_period="1T", late_period="2T")
_M303_SPLIT_YEAR = _M303_EARLY.valid_from.year
_M303_OLDEST = authored_revisions("303")[0]
_M130_REVISION_ID = revision_serving_period("130", _YEAR, "1T").id

# ===========================================================================
# Creation gate strengthened to resolver-equality
# ===========================================================================


class TestS01CreationGate:
    """``law_selected_revision_for_work_target`` must enforce resolver-equality."""

    def test_returns_law_determined_revision_when_no_explicit_revision_given(
        self, *, operation: PinnedAuthorityOperation
    ) -> None:
        """Without an explicit revision the resolver picks the law-determined one."""
        # M130 authors a single design serving 1T of the year.
        result = law_selected_revision_for_work_target(
            modelo="130",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, "1T"),
            requested_revision_id=None,
            operation=operation,
        )
        assert result == _M130_REVISION_ID

    def test_accepts_explicit_revision_that_matches_law_determined(
        self, *, operation: PinnedAuthorityOperation
    ) -> None:
        """An explicit --revision equal to the law-determined revision is idempotent."""
        result = law_selected_revision_for_work_target(
            modelo="130",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, "1T"),
            requested_revision_id=_M130_REVISION_ID,
            operation=operation,
        )
        assert result == _M130_REVISION_ID

    def test_refuses_explicit_revision_that_diverges_from_law_determined(
        self, *, operation: PinnedAuthorityOperation
    ) -> None:
        """An explicit --revision that is NOT the law-determined revision is refused.

        M303 authors several revisions, and one exercise is split between an
        early design (serving 1T) and a late design (serving 2T onwards).

        For that exercise, period 1T the law-determined revision is the early design.
        Supplying the oldest authored revision (a real revision that does NOT
        cover that exercise) must be refused.
        """
        with pytest.raises(ModeloWorkRegistryYearMismatchError) as exc_info:
            law_selected_revision_for_work_target(
                modelo="303",
                filing_year=_M303_SPLIT_YEAR,
                period=Period.from_year_and_code(_M303_SPLIT_YEAR, "1T"),
                requested_revision_id=_M303_OLDEST.id,
                operation=operation,
            )
        # The refusal's prose lives in the locale catalogue and reaches the
        # operator through the renderer; str(exc) is only the message KEY, so
        # rendering is what these guidance claims must be asserted against.
        with override_settings(cadrumo_output_language="en"):
            msg = resolve_error_message(exc_info.value)
        # Must name the requested revision
        assert _M303_OLDEST.id in msg
        # Must name the law-determined revision
        assert _M303_EARLY.id in msg
        # Must state the binding is fixed by law
        assert "law" in msg.lower() or "fixed by" in msg.lower()

    @pytest.mark.parametrize("axis", ["requested", "stored"])
    def test_mismatch_retains_public_captured_coordinates(
        self, *, axis: str, operation: PinnedAuthorityOperation
    ) -> None:
        """Both assertion axes carry finite facts through the recorded error boundary."""
        from cadrumo.application.operations.error_detail import build_operation_error_detail

        with pytest.raises(ModeloWorkRegistryYearMismatchError) as raised:
            law_selected_revision_for_work_target(
                modelo="303",
                filing_year=_M303_SPLIT_YEAR,
                period=Period.from_year_and_code(_M303_SPLIT_YEAR, "1T"),
                requested_revision_id=_M303_OLDEST.id if axis == "requested" else None,
                stored_revision_id=_M303_OLDEST.id if axis == "stored" else None,
                operation=operation,
            )
        expected = {
            "axis": axis,
            "requested_revision": _M303_OLDEST.id,
            "law_revision": _M303_EARLY.id,
            "modelo": "303",
            "year": _M303_SPLIT_YEAR,
            "period": "1T",
        }
        assert raised.value.context == expected
        detail = build_operation_error_detail(raised.value)
        assert detail is not None
        assert detail.error_code == "REFUSED_MODELO_WORK_REGISTRY_YEAR_MISMATCH"
        assert {entry.key: entry.value for entry in detail.context} == {
            key: str(value) for key, value in expected.items()
        }
        assert "law-determined" not in detail.model_dump_json()

    def test_refusal_message_is_instructive_and_names_both_revisions(
        self, *, operation: PinnedAuthorityOperation
    ) -> None:
        """The refusal message must name requested, law-determined, and the re-create instruction.

        Validates the CLI-boundary instructive-refusal mandate from
        ``aeat-architecture-boundaries``.
        """
        with pytest.raises(ModeloWorkRegistryYearMismatchError) as exc_info:
            law_selected_revision_for_work_target(
                modelo="303",
                filing_year=_M303_SPLIT_YEAR,
                period=Period.from_year_and_code(_M303_SPLIT_YEAR, "1T"),
                requested_revision_id=_M303_OLDEST.id,
                operation=operation,
            )
        # The refusal's prose lives in the locale catalogue and reaches the
        # operator through the renderer; str(exc) is only the message KEY, so
        # rendering is what these guidance claims must be asserted against.
        with override_settings(cadrumo_output_language="en"):
            msg = resolve_error_message(exc_info.value)
        assert _M303_OLDEST.id in msg, "message must name the requested revision"
        assert _M303_EARLY.id in msg, "message must name the law-determined revision"
        # Should direct operator to re-create without --revision
        assert "re-create" in msg.lower() or "--revision" in msg.lower() or "without" in msg.lower()

    def test_returns_correct_law_determined_revision_for_the_open_ended_m303_design(
        self, *, operation: PinnedAuthorityOperation
    ) -> None:
        """Smoke test: the open-ended design's first 4T resolves to its own revision."""
        # The first exercise of the open-ended Modelo 303 revision the registry authors.
        design_exercise = open_ended_revision("303").valid_from.year
        result = law_selected_revision_for_work_target(
            modelo="303",
            filing_year=design_exercise,
            period=Period.from_year_and_code(design_exercise, "4T"),
            requested_revision_id=None,
            operation=operation,
        )
        assert result == f"{design_exercise}-y-siguientes"

    def test_refuses_revision_that_covers_year_but_not_period(self, *, operation: PinnedAuthorityOperation) -> None:
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

        For 1T the law-determined revision is ``esquema-union``.
        ``esquema-importacion`` COVERS the year (valid 2021-onwards) but its period
        set is 01..12, NOT 1T.

        The OLD year-only check would have WRONGLY ACCEPTED ``esquema-importacion``
        (it covers the year); the NEW resolver-equality check, which delegates to
        ``select_revision(..., revision_id=...)``, REFUSES it because the year+period
        narrowing finds no covering revision for that id.  This test therefore fails
        under the old year-only implementation and passes only under the new
        resolver-equality implementation — proving the fix closes the actual D1 hole.
        """
        # Sanity-anchor the law-determined revision for the period.
        law_determined = law_selected_revision_for_work_target(
            modelo="369",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, "1T"),
            requested_revision_id=None,
            operation=operation,
        )
        assert law_determined == "esquema-union"

        # The hole: a revision covering the YEAR but not the PERIOD must be refused.
        with pytest.raises(ModeloWorkRegistryYearMismatchError) as exc_info:
            law_selected_revision_for_work_target(
                modelo="369",
                filing_year=_YEAR,
                period=Period.from_year_and_code(_YEAR, "1T"),
                requested_revision_id="esquema-importacion",
                operation=operation,
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

_DOOR_BUCKET_ID = "d1230300-0000-4000-8000-000000000399"


@pytest.fixture
def door_reconfirmation_repo(tmp_path: Path) -> Iterator[tuple[str, WorkUnitCatalogueRepository]]:
    """Yield an isolated bucket and work-unit repository, UUID-shaped for profile persistence."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_DOOR_BUCKET_ID) as profile:
        yield profile.bucket_id, WorkUnitCatalogueRepository(objects=profile.repository)


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
        self, door_reconfirmation_repo: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
    ) -> None:
        """A real, period-declared, but year-wrong revision id is refused at creation.

        Mirrors the sibling scenario one level down: the oldest
        authored M303 revision declares the ``1T`` period token, but it covers
        an earlier exercise than the one requested. Calling ``create_work_unit`` directly -- the shape
        every one of the ~90 direct callers uses -- must refuse exactly as
        ``law_selected_revision_for_work_target`` would, not silently
        build a work unit under an earlier exercise's norms.
        """
        bucket_id, repo = door_reconfirmation_repo
        seed_ready_profile(bucket_id=bucket_id, at=_T0)

        with pytest.raises(ModeloWorkRegistryYearMismatchError) as exc_info:
            create_work_unit(
                bucket_id=bucket_id,
                modelo="303",
                filing_year=_M303_SPLIT_YEAR,
                period=Period.from_year_and_code(_M303_SPLIT_YEAR, "1T"),
                revision_id=_M303_OLDEST.id,
                ports=WorkLifecyclePorts(
                    work_unit_repository=repo,
                    bucket_event_repository=BucketEventHistoryRepository(),
                ),
                clock=_T0,
                operation=operation,
            )
        # The refusal's prose lives in the locale catalogue and reaches the
        # operator through the renderer; str(exc) is only the message KEY, so
        # rendering is what these guidance claims must be asserted against.
        with override_settings(cadrumo_output_language="en"):
            msg = resolve_error_message(exc_info.value)
        assert _M303_OLDEST.id in msg
        assert _M303_EARLY.id in msg

        # No work unit was persisted for the refused key.
        stray_id = derive_work_unit_id(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=_M303_SPLIT_YEAR,
            period=Period.from_year_and_code(_M303_SPLIT_YEAR, "1T"),
            revision_id=_M303_OLDEST.id,
        )
        assert repo.load().get(stray_id) is None

    def test_create_work_unit_accepts_the_law_determined_revision(
        self, door_reconfirmation_repo: tuple[str, WorkUnitCatalogueRepository], *, operation: PinnedAuthorityOperation
    ) -> None:
        """The correctly-resolved revision id still creates a work unit.

        Proves the door reconfirmation is not over-broad: the exact revision
        ``law_selected_revision_for_work_target`` would itself return for
        this ``(modelo, filing_year, period)`` triple must pass unchanged.
        """
        bucket_id, repo = door_reconfirmation_repo
        seed_ready_profile(bucket_id=bucket_id, at=_T0)

        unit = create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=_M303_SPLIT_YEAR,
            period=Period.from_year_and_code(_M303_SPLIT_YEAR, "1T"),
            revision_id=_M303_EARLY.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=repo,
                bucket_event_repository=BucketEventHistoryRepository(),
            ),
            clock=_T0,
            operation=operation,
        )
        assert unit.revision_id == _M303_EARLY.id
        assert repo.load().get(unit.work_unit_id) is not None
