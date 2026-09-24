"""Opt-in live application test for the AEAT justificante capture.

Gated by the ``aeat_live`` marker (deselected by default) and
``requires_live_enabled()`` (the ``CADRUMO_LIVE_TESTS_ENABLED`` opt-in). It
pulls a real signed justificante from the authenticated sede surface and
asserts structural, relational invariants only — never embedding the
operator's expediente ids, CSV handles, or PDF bytes into source-controlled
expectations.
"""

from __future__ import annotations

import asyncio
import hashlib

import pytest

from cadrumo.adapters.outbound.aeat.browser.factory import default_browser_session_factory
from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.adapter_composition import build_expedientes_ports
from cadrumo.entrypoints.cli.app_live_justificante_composition import (
    build_justificante_authenticity_verifier,
    build_justificante_capture_service,
    build_justificante_live_read_port,
    build_justificante_registration_ports,
)

from ....application.live.errors import LiveApplicationInputError
from ....application.live.expedientes import capture_expedientes
from ....application.live.justificante import (
    capture_justificante_snapshot,
)
from ....application.live.snapshot_base import SnapshotLifecycleState
from ....application.live.tests.operator_scope_fakes import build_inward_operator_scope_ports_for_active_route
from ....core.bucket_pointer import require_active_bucket_id
from ....core.period import Period
from ....tests.live_gate import requires_live_enabled

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_entrypoint]

# A quarterly modelo exercises the period-disambiguation path that the
# annual modelos cannot. The year is the prior calendar year, whose
# quarters are all filed by the time this test would run.
_LIVE_MODELO = "130"


async def _discover_filed_period(*, bucket_id: str, modelo: str, year: int) -> Period | None:
    snapshot = await capture_expedientes(
        bucket_id=bucket_id,
        modelo=modelo,
        year=year,
        ports=build_expedientes_ports(bucket_id=bucket_id),
        certificate_secret_backend_factory=build_certificate_secret_backend,
        browser_session_factory=default_browser_session_factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    for declaration in snapshot.declarations:
        if declaration.modelo == modelo:
            period = declaration.period
            assert period is None or isinstance(period, Period)
            return period
    return None


def test_live_justificante_capture_persists_and_is_retrievable() -> None:
    """Pull a real justificante for a filed period and verify it persists."""
    requires_live_enabled()

    from datetime import date

    bucket_id = require_active_bucket_id()
    year = date.today().year - 1

    period = asyncio.run(_discover_filed_period(bucket_id=bucket_id, modelo=_LIVE_MODELO, year=year))
    if period is None:
        pytest.fail(
            f"active profile {bucket_id!r} has no filed Modelo {_LIVE_MODELO} declaration "
            f"for {year}; file one (or adjust the live fixture year) before running this live test",
        )

    try:
        with bundled_indexed_authority().operation() as operation:
            persisted = asyncio.run(
                capture_justificante_snapshot(
                    bucket_id=bucket_id,
                    modelo=_LIVE_MODELO,
                    year=year,
                    period=period,
                    service=build_justificante_capture_service(bucket_id),
                    read_port=build_justificante_live_read_port(
                        build_certificate_secret_backend,
                        _OPERATOR_SCOPE_PORTS,
                        operation,
                    ),
                    registration_ports=build_justificante_registration_ports(),
                    verifier=build_justificante_authenticity_verifier(),
                ),
            )
    except LiveApplicationInputError as exc:
        pytest.fail(f"live justificante capture could not resolve/pull the receipt: {exc}")

    # Structural / relational assertions only.
    assert persisted.modelo == _LIVE_MODELO
    assert persisted.filing_year == year
    assert persisted.period == period
    assert persisted.state is SnapshotLifecycleState.ACTIVE
    assert persisted.source_kind == "aeat_sede_live_capture"
    # The pulled PDF is a real signed document and its content address holds.
    assert persisted.decoded_pdf_bytes().startswith(b"%PDF")
    assert hashlib.sha256(persisted.decoded_pdf_bytes()).hexdigest() == persisted.pdf_sha256

    # The persisted snapshot is retrievable as the ACTIVE capture for the period.
    service = build_justificante_capture_service(bucket_id)
    latest = max(
        (
            snapshot
            for snapshot in service.list_snapshots(filing_year=year)
            if snapshot.modelo == _LIVE_MODELO and snapshot.period == period
        ),
        key=lambda snapshot: snapshot.captured_at,
        default=None,
    )
    assert latest is not None
    assert latest.snapshot_id == persisted.snapshot_id
