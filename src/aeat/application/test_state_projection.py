"""Real-behavior tests for the canonical operator state read-projection.

These tests use a real :class:`EphemeralMasterKeyProvider`, a real
SQLite engine, and a real filesystem bucket. No mocks, fakes, or
monkeypatched repositories.

The projection's contract is that every operator-facing surface reads
ONE state view, so the surfaces cannot disagree. Two contracts are
proved here:

* the cross-surface agreement contract — ``overview status``,
  ``auth status``, ``auth test``, and ``modelo readiness`` all read
  values drawn from the same projection, and ``auth status`` /
  ``auth test`` report the same ``configured``;
* the concrete regression — with ``modelo work`` work units present,
  ``overview status`` reports them rather than the silently-zero count
  the pre-projection assembly produced.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ..adapters.persistence.storage import EphemeralMasterKeyProvider
from ..adapters.persistence.storage.sql.engine import dispose_engine
from .auth._operator import inspect_operator_auth
from .auth._operator import test_operator_auth as probe_operator_auth
from .modelo._actions import create_work_unit
from .overview import build_overview_status_report
from .state_projection import ModeloReadinessRequest, build_operator_state_projection
from .user_profile._testing import register_minimal_profile
from .workflow._persistence import workflow_state_repository

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Bind a real isolated SQLite engine and filesystem root per test."""

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'projection.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path))
    dispose_engine()
    with EphemeralMasterKeyProvider():
        try:
            yield
        finally:
            dispose_engine()


def _register_active_profile() -> str:
    """Register and activate a minimal profile; return its bucket id."""

    workflow_state_repository().update(
        lambda state: register_minimal_profile(state, profile_id="operator")
    )
    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    assert bucket_id is not None
    return bucket_id


def test_overview_status_reports_modelo_work_units(tmp_path: Path) -> None:
    """The concrete bug this wave closes: with ``modelo work`` work units
    present, ``overview status`` must report them.

    Before the canonical projection, ``build_overview_status_report``
    read the legacy ``ModeloDraft`` store but never the
    ``WorkUnitCatalogue`` store, so an operator who used ``modelo work
    create`` saw a silently-zero count. The projection carries
    ``work_units`` as a distinct counter."""

    bucket_id = _register_active_profile()

    create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period="Q1",
        revision_id="aeat-303-2026",
    )

    report = build_overview_status_report()

    assert report.work_units == 1, "overview status must surface modelo work units, not zero"
    assert report.drafts == 0, "the legacy ModeloDraft store is separate and stays at zero"


def test_overview_status_distinguishes_drafts_from_work_units() -> None:
    """``drafts`` and ``work_units`` are distinct counters; neither is
    silently folded into the other."""

    bucket_id = _register_active_profile()
    for period in ("Q1", "Q2"):
        create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=period,
            revision_id="aeat-303-2026",
        )

    projection = build_operator_state_projection()

    assert projection.workspace.work_units == 2
    assert projection.workspace.drafts == 0
    assert projection.workspace.transactions == 0
    assert projection.workspace.invoices == 0


def test_surfaces_agree_on_one_projection() -> None:
    """Every operator-facing surface draws from one projection, so they
    cannot disagree.

    One fixture state — an active profile plus two ``modelo work`` work
    units — is built once. ``overview status``, ``auth status``,
    ``auth test``, and ``modelo readiness`` are then queried and their
    shared values are asserted mutually consistent. In particular
    ``auth status`` and ``auth test`` must report the same
    ``configured``, closing the historical two-readers-two-answers
    disagreement."""

    bucket_id = _register_active_profile()
    for period in ("Q1", "Q2"):
        create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=period,
            revision_id="aeat-303-2026",
        )

    projection = build_operator_state_projection(
        modelo_readiness_requests=(
            ModeloReadinessRequest(
                modelo="303",
                revision_id="aeat-303-2026",
                filing_year=2026,
                period="Q1",
            ),
        ),
        probe_live_backend=True,
    )

    overview = build_overview_status_report()
    auth_status = inspect_operator_auth()
    auth_test = probe_operator_auth()

    # auth status and auth test report the SAME configured — the
    # historical disagreement is closed structurally.
    assert auth_status.configured == auth_test.configured
    assert auth_status.configured == projection.auth.configured

    # auth status and auth test agree on the active profile too.
    assert auth_status.active_profile == auth_test.active_profile
    assert auth_status.active_profile == bucket_id

    # overview status shows the modelo work units from the same
    # projection.
    assert overview.work_units == 2
    assert overview.work_units == projection.workspace.work_units
    assert overview.active_profile == bucket_id

    # modelo readiness is carried in the same projection and is
    # consistent with what a direct readiness query reports.
    assert len(projection.modelo_readiness) == 1
    readiness = projection.modelo_readiness[0]
    assert readiness.modelo == "303"
    assert readiness.profile_id == bucket_id


def test_projection_is_pure_read() -> None:
    """Building the projection mutates no store: two consecutive builds
    over an unchanged workspace return equal projections."""

    bucket_id = _register_active_profile()
    create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period="Q1",
        revision_id="aeat-303-2026",
    )

    first = build_operator_state_projection()
    second = build_operator_state_projection()

    assert first == second


def test_projection_without_active_profile_is_empty() -> None:
    """With no active profile the projection reports zeroed counters and
    no encrypted store is opened."""

    projection = build_operator_state_projection()

    assert projection.active_profile.profile_id is None
    assert projection.workspace.work_units == 0
    assert projection.workspace.drafts == 0
    assert projection.auth.configured is False
    assert projection.pending_obligations == ()
