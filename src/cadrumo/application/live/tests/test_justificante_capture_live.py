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

from ....core import Period
from ....core.bucket_pointer import require_active_bucket_id
from ....tests.live_gate import requires_live_enabled
from ..errors import LiveApplicationInputError
from ..expedientes import capture_expedientes
from ..justificante import (
    JustificanteCaptureSnapshotService,
    SnapshotLifecycleState,
    capture_justificante_snapshot,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_application]

# A quarterly modelo exercises the period-disambiguation path that the
# annual modelos cannot. The year is the prior calendar year, whose
# quarters are all filed by the time this test would run.
_LIVE_MODELO = "130"


async def _discover_filed_period(*, bucket_id: str, modelo: str, year: int) -> Period | None:
    snapshot = await capture_expedientes(bucket_id=bucket_id, modelo=modelo, year=year)
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
        persisted = asyncio.run(
            capture_justificante_snapshot(
                bucket_id=bucket_id,
                modelo=_LIVE_MODELO,
                year=year,
                period=period,
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
    service = JustificanteCaptureSnapshotService(bucket_id=bucket_id)
    latest = service.latest_for_work_unit(modelo=_LIVE_MODELO, filing_year=year, period=period)
    assert latest is not None
    assert latest.snapshot_id == persisted.snapshot_id
