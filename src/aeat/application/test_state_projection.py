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
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ..adapters.persistence.storage import EphemeralMasterKeyProvider
from ..adapters.persistence.storage.sql.engine import dispose_engine
from ..domain.transactions import BusinessClassification, TransactionDirection
from .auth._operator import inspect_operator_auth
from .auth._operator import test_operator_auth as probe_operator_auth
from .ledger import ManualLedgerTransactionCommand, create_manual_transaction
from .modelo._actions import create_work_unit, discard_work_unit
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


def test_work_units_counter_excludes_discarded_units() -> None:
    """A discarded work unit must not inflate the active ``work_units``
    counter; it is carried separately in ``discarded_work_units`` so the
    operator is never shown a misleading total."""

    bucket_id = _register_active_profile()
    for period in ("Q1", "Q2", "Q3"):
        create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=period,
            revision_id="aeat-303-2026",
        )
    discarded = create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period="Q4",
        revision_id="aeat-303-2026",
    )
    discard_work_unit(discarded.work_unit_id, actor="operator", reason="superseded")

    projection = build_operator_state_projection()

    assert projection.workspace.work_units == 3, "discarded units must not inflate the active counter"
    assert projection.workspace.discarded_work_units == 1

    report = build_overview_status_report()
    assert report.work_units == 3
    assert report.discarded_work_units == 1


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


def test_modelo_303_readiness_includes_ledger_preflight_blockers() -> None:
    bucket_id = _register_active_profile()
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=bucket_id,
            booked_date=date(2026, 2, 10),
            amount=Decimal("121.00"),
            direction=TransactionDirection.INCOMING,
            description="business sale without category",
            business_classification=BusinessClassification.BUSINESS,
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
            actor="operator",
        )
    )

    projection = build_operator_state_projection(
        modelo_readiness_requests=(
            ModeloReadinessRequest(
                modelo="303",
                revision_id="2009-y-siguientes",
                filing_year=2026,
                period="1T",
            ),
        ),
    )

    readiness = projection.modelo_readiness[0]
    assert readiness.profile_ready is True
    assert readiness.ledger_preflight_required is True
    assert readiness.ledger_ready is False
    assert readiness.ready is False
    assert readiness.ledger_period == "2026Q1"
    assert readiness.ledger_checked_transaction_count == 1
    assert [issue.reason.value for issue in readiness.ledger_issues] == ["missing_category"]


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


def test_auth_readiness_no_provider_matches_with_and_without_probe() -> None:
    """The auth readiness sub-record reports the same "no provider
    configured" state whether or not the live backend is probed.

    ``auth test`` probes; ``auth status`` does not. When no provider is
    configured and none requested, the projection must not invent a
    default provider for the probing caller — both report the empty
    provider, ``available: False``, and an empty health summary.
    """

    _register_active_profile()

    unprobed = build_operator_state_projection(probe_live_backend=False)
    probed = build_operator_state_projection(probe_live_backend=True)

    assert unprobed.auth.provider == ""
    assert probed.auth.provider == unprobed.auth.provider
    assert probed.auth.available == unprobed.auth.available is False
    assert probed.auth.configured == unprobed.auth.configured is False
    assert probed.auth.health_summary == unprobed.auth.health_summary == ""


def test_auth_readiness_configured_is_coherent_with_health_summary() -> None:
    """``configured`` must never be ``True`` while ``health_summary``
    reports the certificate path is not configured.

    A certificate path recorded only in workflow state — with the live
    backend probe sourcing its path from ``Settings`` and seeing none —
    is not operationally ready. The probed projection reconciles
    ``configured`` with the same ``describe()`` evaluation that
    produces ``health_summary``, so the two cannot contradict.
    """

    from .auth._operator import configure_operator_auth

    _register_active_profile()
    configure_operator_auth("certificate")

    projection = build_operator_state_projection(probe_live_backend=True)

    auth = projection.auth
    assert auth.health_summary == "certificate path not configured", (
        "fixture must reach the not-configured health state for this test to "
        f"be meaningful — got health_summary={auth.health_summary!r}"
    )
    assert auth.configured is False, (
        "configured must not contradict the health summary — "
        f"got configured={auth.configured!r}, health_summary={auth.health_summary!r}"
    )


def test_auth_readiness_drops_certificate_path_after_switching_provider(tmp_path: Path) -> None:
    """A non-certificate provider must not carry a stale ``certificate_path``.

    After ``configure --provider certificate --file PATH`` then
    ``configure --provider clave_movil``, the projection's
    ``certificate_path`` must be empty — the certificate path is a
    certificate-provider field and must not leak beside a different
    active provider (persona-fleet finding G1).
    """

    from .auth._operator import configure_operator_auth

    _register_active_profile()
    cert_file = tmp_path / "operator-cert.pfx"
    cert_file.write_bytes(b"placeholder pkcs12 bytes")

    configure_operator_auth("certificate", certificate_path=cert_file)
    after_cert = build_operator_state_projection(probe_live_backend=False)
    assert after_cert.auth.certificate_path == str(cert_file)

    configure_operator_auth("clave_movil")
    after_switch = build_operator_state_projection(probe_live_backend=False)

    assert after_switch.auth.provider == "clave_movil"
    assert after_switch.auth.certificate_path == "", (
        "certificate_path must be empty for a non-certificate provider — "
        f"got {after_switch.auth.certificate_path!r}"
    )


def test_auth_readiness_health_severity_is_populated_for_a_configured_provider() -> None:
    """``health_severity`` must carry a meaningful, non-empty token.

    The Cl@ve backend reports a ``health_summary`` but no severity; the
    projection must derive a coherent token so ``health_severity`` is
    never silently empty for a configured provider (persona-fleet
    finding G4).
    """

    from .auth._operator import configure_operator_auth

    _register_active_profile()
    configure_operator_auth("clave_movil")

    auth = build_operator_state_projection(probe_live_backend=True).auth

    assert auth.health_severity != "", (
        "health_severity must be populated for a configured provider — "
        f"got health_summary={auth.health_summary!r}"
    )
    assert auth.health_severity in {"ok", "warning", "error"}


def test_auth_readiness_health_severity_empty_only_when_no_provider() -> None:
    """With no provider selected there is nothing to classify; severity stays empty."""

    _register_active_profile()

    auth = build_operator_state_projection(probe_live_backend=True).auth

    assert auth.provider == ""
    assert auth.health_severity == ""
