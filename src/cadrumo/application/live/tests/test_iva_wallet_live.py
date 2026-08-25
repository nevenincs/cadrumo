"""Opt-in live application workflow test for the AEAT IVA wallet capture.

The ``"iva-wallet"`` literal joined onto ``cadrumo_live_state_dir`` mirrors
``StorageCategory.LIVE_STATE_IVA_WALLET``'s declared subpath
(``live-state/iva-wallet``). ``LIVE_STATE`` is operator-overridable, so this
member -- like the ``SECRETS_MASTER_KEY`` family -- carries no
``settings_field`` and is not safe to resolve via ``storage_path`` directly;
production (``application/live/_iva_remote_state.py``) reads the same bare
leaf names off the accessor-derived root, and this test mirrors that
sanctioned pattern rather than a taxonomy-accessor call.
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from ....adapters.outbound.aeat.sede import FiledDeclaracionObservationStore
from ....core import Period
from ....core.bucket_pointer import require_active_bucket_id
from ....core.config import load_settings
from ....core.resources import resources
from ....tests.live_gate import requires_live_enabled
from ...calculations import IvaWalletDecisionRepository
from ...modelo import ModeloIvaWalletReconciliationBlocked
from ...modelo import apply_iva_compensation_decision_binding as _apply_iva_compensation_decision_binding
from ...user_profile import ProfileRecordRepository, record_to_path_values
from .. import capture_iva_compensation_wallet

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_application]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"iva-wallet"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""


def test_live_iva_wallet_capture_persists_reconciles_and_feeds_local_guard() -> None:
    """Pull the real AEAT wallet and verify persisted reconciliation locally.

    The assertions are structural and relational. They never embed the
    operator's wallet rows or amounts into source-controlled expectations.
    """

    requires_live_enabled()
    bucket_id = require_active_bucket_id()
    taxpayer_nif = _active_profile_tax_id(bucket_id)
    if taxpayer_nif is None:
        pytest.fail(f"active profile {bucket_id!r} has no identity.tax_id")

    today = date.today()
    target_year = today.year
    target_period = _quarter_period(today.month)
    target_filing_period = Period.from_year_and_code(target_year, target_period)
    settings = load_settings()
    report = asyncio.run(
        capture_iva_compensation_wallet(
            target_year=target_year,
            target_period=target_filing_period,
            output_root=settings.cadrumo_live_state_dir / "iva-wallet",
        ),
    )
    observation = FiledDeclaracionObservationStore(
        settings.cadrumo_live_state_dir / "iva-wallet",
    ).load_iva_wallet_observation(Path(report.observation_path))
    decision = IvaWalletDecisionRepository().load_decision(taxpayer_nif, target_filing_period)
    history = IvaWalletDecisionRepository().load_decision_history(taxpayer_nif, target_filing_period)

    if decision is None:
        pytest.fail("live IVA wallet capture did not persist a reconciliation decision")
    if not any(item == decision for item in history):
        pytest.fail("live IVA wallet capture did not append immutable decision history")
    if observation.taxpayer_nif != taxpayer_nif:
        pytest.fail("live IVA wallet observation taxpayer did not match active profile")
    if observation.target_year != target_year or observation.target_period != target_period:
        pytest.fail("live IVA wallet observation target period did not match requested period")
    if decision.wallet_amount != observation.total_pending:
        pytest.fail("live IVA wallet decision did not bind the observed wallet amount")
    if Decimal(report.total_pending) != observation.total_pending:
        pytest.fail("live IVA wallet report did not match the persisted observation")

    backend_bindings: dict[str, Decimal] = {}
    revision = (
        resources()
        .modelos.authority.snapshot(
            "303",
            filing_year=target_year,
            period=target_period,
        )
        .revision
    )
    if decision.blocked:
        with pytest.raises(ModeloIvaWalletReconciliationBlocked):
            _apply_iva_compensation_decision_binding(
                "303",
                target_year,
                target_filing_period,
                bucket_id=bucket_id,
                revision=revision,
                taxpayer_nif=taxpayer_nif,
                casilla_inputs={},
                backend_casilla_inputs={},
                caller_binding_values={},
                backend_binding_values=backend_bindings,
                decision=decision,
            )
        return

    _apply_iva_compensation_decision_binding(
        "303",
        target_year,
        target_filing_period,
        bucket_id=bucket_id,
        revision=revision,
        taxpayer_nif=taxpayer_nif,
        casilla_inputs={},
        backend_casilla_inputs={},
        caller_binding_values={},
        backend_binding_values=backend_bindings,
        decision=decision,
    )
    if backend_bindings.get("modelo-303-compensacion-pendiente-anteriores") != decision.selected_amount:
        pytest.fail("live IVA wallet decision did not feed the local Modelo 303 guard")


def _active_profile_tax_id(bucket_id: str) -> str | None:
    record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
    value = record_to_path_values(record).get("identity.tax_id")
    return value.strip().upper() if value is not None and value.strip() else None


def _quarter_period(month: int) -> str:
    return f"{((month - 1) // 3) + 1}T"
