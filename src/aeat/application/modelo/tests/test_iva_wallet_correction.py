"""Real-behavior tests for the guarded IVA wallet correction path.

Authority: the operator-surface decision D7 (read-back /
correction baseline); CRUD-matrix audit finding F-05 (IVA wallet seed-once, no
correction path).

``iva-wallet seed`` is one-shot — it refuses to overwrite an existing record —
so a wrong opening compensation balance is otherwise unrecoverable.
``correct_iva_compensation_period_for_bucket`` is the deliberate correction
path. It delegates the write to the single-writer
``correct_iva_compensation_period`` primitive (no parallel write), emits a
``MODELO_IVA_WALLET_CORRECTED`` audit event carrying the operator reason, and
**guards the filed basis**: it refuses when a sealed (already-filed) Modelo 303
revision at or after the seeded period has consumed the seeded compensation —
the same filed-immutability risk the ledger restore guard enforces.

These tests drive the production persistence path end to end on a real isolated
bucket: a real encrypted ``IvaCompensationHistoryRepository`` write, a real
profile with ``identity.tax_id``, a real sealed ``CalculationRevision`` in the
work-unit / revision catalogues.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests.secure_sql import isolated_profile_storage_root
from ...calculations import IvaCompensationHistoryRepository
from ...user_profile._orchestration import profile_create_storage_span
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository
from .. import (
    ModeloIvaWalletCorrectionNoRecordError,
    ModeloIvaWalletCorrectionSealedError,
    ModeloIvaWalletSeedNegativeAmountError,
    correct_iva_compensation_period_for_bucket,
    seed_iva_compensation_period_for_bucket,
)
from .._iva_wallet_gate import taxpayer_nif_for_bucket

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "operator"
_SEED_YEAR = 2024
_SEED_PERIOD = "4T"


@pytest.fixture(autouse=True)
def _runtime(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id=_BUCKET_ID),
        )
        yield


def _taxpayer_nif() -> str:
    nif = taxpayer_nif_for_bucket(_BUCKET_ID)
    assert nif is not None
    return nif


def _seed(amount: Decimal) -> None:
    seed_iva_compensation_period_for_bucket(
        bucket_id=_BUCKET_ID,
        filing_year=_SEED_YEAR,
        period=_SEED_PERIOD,
        amount=amount,
    )


def _persist_sealed_303(*, filing_year: int, period: str, state: CalculationRevisionState) -> None:
    from datetime import UTC, datetime

    when = datetime(2026, 1, 2, tzinfo=UTC)
    typed_period = Period.from_year_and_code(filing_year, period)
    work_unit_revision_marker = f"sealed-{filing_year}-{period}"
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=filing_year,
        period=typed_period,
        revision_id=work_unit_revision_marker,
    )
    casilla_values = {"iva.compensacion-pendiente-periodos-anteriores": Decimal("1000.00")}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values=casilla_values,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=filing_year,
        period=typed_period,
        revision_id=work_unit_revision_marker,
        name=f"303-{filing_year}-{period}",
        created_at=when,
        updated_at=when,
    )
    audit_metadata: dict[str, object] = {}
    if state in {
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
    }:
        audit_metadata["verified_at"] = when
        audit_metadata["verified_by"] = "tester"
    if state in {CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO}:
        audit_metadata["filed_at"] = when
        audit_metadata["filed_by"] = "tester"
    if state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO:
        audit_metadata["superseded_at"] = when
    revision_fields: dict[str, object] = {
        "calculation_revision_id": revision_id,
        "work_unit_id": work_unit_id,
        "state": state,
        "inputs_snapshot": {},
        "binding_overrides": {},
        "casilla_values": casilla_values,
        "created_at": when,
        "updated_at": when,
        **audit_metadata,
    }
    # model_validate (not **splat) so the dict[str, object] audit_metadata does
    # not redden the type checker on every field; validators run identically.
    revision = CalculationRevision.model_validate(revision_fields)
    wu_repo = WorkUnitCatalogueRepository()
    wu_repo.save(upsert_work_unit(wu_repo.load(), work_unit))
    rev_repo = CalculationRevisionCatalogueRepository()
    rev_repo.save(upsert_calculation_revision(rev_repo.load(), revision))


def test_correction_overwrites_balance_and_emits_audit_event() -> None:
    """Correcting a seeded period changes the stored balance and emits the audit event."""
    _seed(Decimal("500.00"))

    state = correct_iva_compensation_period_for_bucket(
        bucket_id=_BUCKET_ID,
        filing_year=_SEED_YEAR,
        period=_SEED_PERIOD,
        amount=Decimal("1200.50"),
        reason="typo in opening balance",
    )

    assert state.available_end_amount == Decimal("1200.50")
    persisted = IvaCompensationHistoryRepository().load_period(_SEED_YEAR, _SEED_PERIOD)
    assert persisted is not None
    assert persisted.available_end_amount == Decimal("1200.50")
    assert persisted.taxpayer_nif == _taxpayer_nif()

    catalogue = BucketEventHistoryRepository().load()
    corrected = [
        event for event in catalogue.events.values() if event.event_type is BucketEventType.MODELO_IVA_WALLET_CORRECTED
    ]
    assert len(corrected) == 1
    payload = dict(corrected[0].payload)
    assert payload["reason"] == "typo in opening balance"
    assert payload["previous_amount"] == "500.00"
    assert payload["new_amount"] == "1200.50"
    assert payload["filing_year"] == str(_SEED_YEAR)
    assert payload["period"] == _SEED_PERIOD


def test_correction_refuses_when_no_record_exists() -> None:
    """Correcting a period with no seeded record refuses (seed first)."""
    with pytest.raises(ModeloIvaWalletCorrectionNoRecordError):
        correct_iva_compensation_period_for_bucket(
            bucket_id=_BUCKET_ID,
            filing_year=_SEED_YEAR,
            period=_SEED_PERIOD,
            amount=Decimal("100.00"),
            reason="no record yet",
        )


def test_correction_refuses_negative_amount() -> None:
    """A negative corrected amount is refused, mirroring the seed guard."""
    _seed(Decimal("500.00"))
    with pytest.raises(ModeloIvaWalletSeedNegativeAmountError):
        correct_iva_compensation_period_for_bucket(
            bucket_id=_BUCKET_ID,
            filing_year=_SEED_YEAR,
            period=_SEED_PERIOD,
            amount=Decimal("-1.00"),
            reason="negative",
        )


@pytest.mark.parametrize(
    "sealed_state",
    [
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
    ],
)
def test_correction_refused_when_sealed_303_consumed_the_seed(
    sealed_state: CalculationRevisionState,
) -> None:
    """A sealed Modelo 303 at or after the seeded period blocks the correction.

    The seed for (2024, 4T) feeds the carry-forward of every later Modelo 303
    period. A sealed revision for a 2025 1T Modelo 303 has consumed that basis,
    so correcting the 2024 4T seed would silently change an already-filed
    return — refused, with the offending revision named.
    """
    _seed(Decimal("500.00"))
    _persist_sealed_303(filing_year=2025, period="1T", state=sealed_state)

    with pytest.raises(ModeloIvaWalletCorrectionSealedError) as excinfo:
        correct_iva_compensation_period_for_bucket(
            bucket_id=_BUCKET_ID,
            filing_year=_SEED_YEAR,
            period=_SEED_PERIOD,
            amount=Decimal("1200.50"),
            reason="should be blocked",
        )

    context = excinfo.value.context or {}
    assert context["blocking_filing_year"] == 2025
    assert context["blocking_period"] == "1T"
    # The stored balance is unchanged: the guard fired before any write.
    persisted = IvaCompensationHistoryRepository().load_period(_SEED_YEAR, _SEED_PERIOD)
    assert persisted is not None
    assert persisted.available_end_amount == Decimal("500.00")
    # No audit event was emitted for the refused correction.
    catalogue = BucketEventHistoryRepository().load()
    corrected = [
        event for event in catalogue.events.values() if event.event_type is BucketEventType.MODELO_IVA_WALLET_CORRECTED
    ]
    assert corrected == []


def test_correction_allowed_when_only_a_draft_303_exists() -> None:
    """A non-sealed (BORRADOR) Modelo 303 does not block the correction.

    Anti-tautology counterpart to the sealed-guard test: a draft revision has
    not been filed, so it has not consumed the seeded basis and the correction
    proceeds. If the guard fired on a draft it would over-block legitimate
    corrections.
    """
    _seed(Decimal("500.00"))
    _persist_sealed_303(filing_year=2025, period="1T", state=CalculationRevisionState.BORRADOR)

    state = correct_iva_compensation_period_for_bucket(
        bucket_id=_BUCKET_ID,
        filing_year=_SEED_YEAR,
        period=_SEED_PERIOD,
        amount=Decimal("1200.50"),
        reason="draft does not block",
    )

    assert state.available_end_amount == Decimal("1200.50")
