"""The installed withholding screen reaches the real producer through its own composition.

Nothing here builds a door or a lookup by hand: the screen comes from
:func:`compose_installed_withholding_screen` for an isolated runtime profile,
so the encrypted ledger read, the shared producer and the atomic service are
the ones the launcher composes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.withholding.installed import compose_installed_withholding_screen

from .test_screen import _click, _status
from .test_screen_payroll import (
    _PAYROLL_GROSS,
    _PAYROLL_IRPF,
    _PAYROLL_QUARTER,
    _fill_payroll,
    _inspection_text,
    _seed_payroll_payment,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]


@pytest.mark.asyncio
async def test_installed_screen_captures_payroll_through_the_composed_ledger_read_and_producer(
    tmp_path: Path,
) -> None:
    """The composed door resolves the stored payment and the shared producer persists it."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        transaction = _seed_payroll_payment(profile)
        screen = compose_installed_withholding_screen(bucket_id=profile.bucket_id, filing_year=2025)
        async with ScreenHostApp(screen).run_test(size=(160, 60)) as pilot:
            await pilot.pause()
            _fill_payroll(screen, "f" * 64)
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "refused: transaction_not_found"
            _fill_payroll(screen, transaction.transaction_id)
            await _click(pilot, screen, "#withholding-capture")
            assert _status(screen) == "captured"
            await _click(pilot, screen, "#withholding-inspect")
            assert "111 2T: 2 active projections" in _inspection_text(screen)
            pilot.app.exit(None)

        stored = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
            "111", _PAYROLL_QUARTER
        )

    assert len(stored) == 1
    assert stored[0].source_kind is BindingSourceKind.LEDGER_TRANSACTION
    assert stored[0].source_object_id == transaction.transaction_id
    assert (stored[0].taxable_base, stored[0].retencion_amount) == (_PAYROLL_GROSS, _PAYROLL_IRPF)
