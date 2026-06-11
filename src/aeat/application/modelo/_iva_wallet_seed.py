"""Application facade for Modelo IVA wallet seed and correction operations.

This module uses :class:`IvaCompensationPeriodState` for seeding and correcting
the IVA compensation history. Every mutation appends a typed audit event via
:class:`BucketEventHistoryRepository`. :func:`correct_iva_compensation_period_for_bucket`
guards the correction against a sealed (already-filed) Modelo 303 revision that
consumed the seeded compensation basis, reusing the same
:class:`~aeat.domain.modelos._calculation_revision.CalculationRevisionState`
sealed-state set the ledger restore guard enforces.
"""

from __future__ import annotations

from decimal import Decimal

from ...core import Modelo, Period
from ...domain.iva_compensation import IvaCompensationPeriodState
from ...domain.modelos._calculation_revision import CalculationRevisionState
from ...domain.modelos._errors import ModeloError
from ..calculations import correct_iva_compensation_period, seed_iva_compensation_period
from ._iva_wallet_gate import taxpayer_nif_for_bucket

#: Sealed (already-filed) revision states that consume the IVA compensation
#: basis. A correction of a seeded period whose carry-forward fed any sealed
#: Modelo 303 filing would silently change a filed return's basis, so the guard
#: refuses it. This mirrors the ledger restore guard's blocking-state set.
_SEALED_REVISION_STATES = frozenset(
    {
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
    },
)


def _period_order_key(period: Period) -> tuple[int, str]:
    """Order a filing period within its year for the at-or-after seed guard.

    Quarterly tokens (``1T``..``4T``) sort by quarter, monthly tokens by month,
    the annual ``0A`` token last. The exact ordering only needs to be monotone
    within a year so a sealed Modelo 303 at the seeded period or any later one
    is recognised as having consumed the seeded carry-forward basis.
    """
    upper = period.registry_token
    if upper.endswith("T") and upper[:-1].isdigit():
        return (int(upper[:-1]), upper)
    if upper.isdigit():
        return (int(upper), upper)
    if upper == "0A":
        return (99, upper)
    return (100, upper)


class ModeloIvaWalletSeedError(ModeloError):
    """Base class for Modelo IVA wallet seed application errors."""

    def __init__(self, *, translated_message: str, context: dict[str, object] | None = None) -> None:
        super().__init__(
            translated_message,
            translated_message=translated_message,
            context=context,
        )


class ModeloIvaWalletSeedNoTaxpayerError(ModeloIvaWalletSeedError):
    """Raised when the selected bucket cannot provide a taxpayer NIF."""


class ModeloIvaWalletSeedNegativeAmountError(ModeloIvaWalletSeedError):
    """Raised when a seed amount is negative."""


class ModeloIvaWalletCorrectionNoRecordError(ModeloIvaWalletSeedError):
    """Raised when a correction targets a period that has no seeded record yet.

    Correction re-writes an existing opening balance; an absent period is a
    seed, not a correction. The refusal surfaces the seed-first guidance so the
    operator runs ``iva-wallet seed`` before ``iva-wallet correct``.
    """


class ModeloIvaWalletCorrectionSealedError(ModeloIvaWalletSeedError):
    """Raised when correcting a seed that an already-filed Modelo 303 consumed.

    A sealed (``VERIFICADO_COMPLETO`` / ``PRESENTADO`` /
    ``PRESENTADO_SUPERSEDIDO``) Modelo 303 revision at or after the seeded
    period carries the seeded compensation forward as its
    *compensación pendiente de periodos anteriores*. Re-writing that basis would
    silently change the input basis of a return the operator has already filed
    at sede — the same filed-immutability risk the ledger restore guard
    enforces — so the correction is refused with the offending revision named.
    """


def seed_iva_compensation_period_for_bucket(
    *,
    bucket_id: str,
    period: Period,
    amount: Decimal,
) -> IvaCompensationPeriodState:
    """Seed IVA compensation history and return an :class:`IvaCompensationPeriodState`."""
    if amount < Decimal("0"):
        raise ModeloIvaWalletSeedNegativeAmountError(
            translated_message="application.modelo.iva_wallet.seed_negative_amount",
            context={"amount": str(amount)},
        )
    taxpayer_nif = taxpayer_nif_for_bucket(bucket_id)
    if taxpayer_nif is None:
        raise ModeloIvaWalletSeedNoTaxpayerError(
            translated_message="application.modelo.iva_wallet.seed_no_nif",
            context={"bucket_id": bucket_id},
        )
    return seed_iva_compensation_period(
        taxpayer_nif=taxpayer_nif,
        period=period,
        amount=amount,
    )


def _sealed_modelo_303_blocker_for_period(
    *,
    bucket_id: str,
    period: Period,
) -> tuple[str, str, int, str] | None:
    """Return the first sealed Modelo 303 revision at or after the seeded period.

    The seed for ``(filing_year, period)`` is the opening carry-forward lot the
    FIFO projection feeds into every later Modelo 303 period's prior-compensation
    casilla. A sealed revision for the seeded period itself or any later one has
    therefore consumed the seeded basis, so the correction must be refused. The
    scan reuses the work-unit and calculation-revision catalogues — the same
    sources the ledger finalized-modelo guard reads — and returns
    ``(work_unit_id, calculation_revision_id, filing_year, period)`` of the
    offending revision, or ``None`` when no sealed Modelo 303 consumed the seed.
    """
    from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
    from ...domain.modelos._repository import WorkUnitCatalogueRepository

    seeded_key = (period.filing_year, _period_order_key(period))
    work_units = WorkUnitCatalogueRepository(bucket_id=bucket_id).load()
    revisions = CalculationRevisionCatalogueRepository(bucket_id=bucket_id).load()
    candidates: list[tuple[tuple[int, tuple[int, str]], str, str, int, str]] = []
    for revision in revisions.values():
        if revision.state not in _SEALED_REVISION_STATES:
            continue
        work_unit = work_units.work_units.get(revision.work_unit_id)
        if work_unit is None or work_unit.bucket_id != bucket_id:
            continue
        if work_unit.modelo != Modelo.M303.value:
            continue
        consuming_key = (work_unit.period.filing_year, _period_order_key(work_unit.period))
        if consuming_key < seeded_key:
            continue
        candidates.append(
            (
                (work_unit.period.filing_year, _period_order_key(work_unit.period)),
                work_unit.work_unit_id,
                revision.calculation_revision_id,
                work_unit.filing_year,
                work_unit.period.registry_token,
            ),
        )
    if not candidates:
        return None
    _, work_unit_id, revision_id, blocker_year, blocker_period = min(candidates, key=lambda item: item[0])
    return work_unit_id, revision_id, blocker_year, blocker_period


def correct_iva_compensation_period_for_bucket(
    *,
    bucket_id: str,
    period: Period,
    amount: Decimal,
    reason: str,
) -> IvaCompensationPeriodState:
    """Correct a wrong opening IVA compensation balance, guarded and audited.

    Returns the corrected :class:`IvaCompensationPeriodState`.

    The seed verb is one-shot: it refuses to overwrite an existing record, so a
    wrong opening carry-forward balance for a pre-history period is otherwise
    unrecoverable. This is the deliberate correction path. It:

    - resolves the bucket's taxpayer NIF (refusing when absent, like seed);
    - refuses a negative amount (like seed);
    - **guards the filed basis**: refuses when a sealed (already-filed) Modelo
      303 revision at or after the seeded period consumed the seeded
      compensation — re-writing such a basis would silently change an
      already-filed return, the same filed-immutability risk the ledger restore
      guard enforces (:class:`ModeloIvaWalletCorrectionSealedError`);
    - delegates the write to the single-writer
      :func:`~aeat.application.calculations.correct_iva_compensation_period`
      primitive (no parallel write path), which refuses to fabricate a record
      where none exists (re-raised as
      :class:`ModeloIvaWalletCorrectionNoRecordError`);
    - emits a :attr:`~aeat.domain.buckets.BucketEventType.MODELO_IVA_WALLET_CORRECTED`
      audit event carrying the operator ``reason`` and the before/after amounts.

    The local app never files; correcting the wallet basis touches no AEAT write
    surface.
    """
    if amount < Decimal("0"):
        raise ModeloIvaWalletSeedNegativeAmountError(
            translated_message="application.modelo.iva_wallet.seed_negative_amount",
            context={"amount": str(amount)},
        )
    taxpayer_nif = taxpayer_nif_for_bucket(bucket_id)
    if taxpayer_nif is None:
        raise ModeloIvaWalletSeedNoTaxpayerError(
            translated_message="application.modelo.iva_wallet.seed_no_nif",
            context={"bucket_id": bucket_id},
        )

    from ..calculations import IvaCompensationHistoryRepository

    repository = IvaCompensationHistoryRepository()
    existing = repository.load_period(period)
    if existing is None:
        raise ModeloIvaWalletCorrectionNoRecordError(
            translated_message="application.modelo.iva_wallet.correct_no_record",
            context={"filing_year": period.filing_year, "period": period.registry_token},
        )

    blocker = _sealed_modelo_303_blocker_for_period(
        bucket_id=bucket_id,
        period=period,
    )
    if blocker is not None:
        work_unit_id, revision_id, blocker_year, blocker_period = blocker
        raise ModeloIvaWalletCorrectionSealedError(
            translated_message="application.modelo.iva_wallet.correct_sealed_blocked",
            context={
                "filing_year": period.filing_year,
                "period": period.registry_token,
                "blocking_work_unit_id": work_unit_id,
                "blocking_calculation_revision_id": revision_id,
                "blocking_filing_year": blocker_year,
                "blocking_period": blocker_period,
            },
        )

    state = correct_iva_compensation_period(
        taxpayer_nif=taxpayer_nif,
        period=period,
        amount=amount,
        repository=repository,
    )

    _emit_iva_wallet_corrected_event(
        bucket_id=bucket_id,
        taxpayer_nif=taxpayer_nif,
        period=period,
        previous_amount=existing.available_end_amount,
        new_amount=state.available_end_amount,
        reason=reason,
    )

    return state


def _emit_iva_wallet_corrected_event(
    *,
    bucket_id: str,
    taxpayer_nif: str,
    period: Period,
    previous_amount: Decimal,
    new_amount: Decimal,
    reason: str,
) -> None:
    """Append the ``MODELO_IVA_WALLET_CORRECTED`` audit event for a correction."""
    from ...core.time import now
    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )

    occurred_at = now()
    object_id = f"303:{period.filing_year}:{period.registry_token}"
    payload = {
        "taxpayer_nif": taxpayer_nif,
        "filing_year": str(period.filing_year),
        "period": period.registry_token,
        "previous_amount": str(previous_amount),
        "new_amount": str(new_amount),
        "reason": reason,
    }
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=BucketEventType.MODELO_IVA_WALLET_CORRECTED,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=object_id,
        payload=payload,
    )
    catalogue_repo = BucketEventHistoryRepository()
    next_catalogue = append_bucket_event(
        catalogue_repo.load(),
        BucketEvent(
            event_id=event_id,
            bucket_id=bucket_id,
            event_type=BucketEventType.MODELO_IVA_WALLET_CORRECTED,
            occurred_at=occurred_at,
            actor="operator",
            object_type=BucketEventObjectType.WORK_UNIT,
            object_id=object_id,
            payload_version=1,
            payload=payload,
        ),
    )
    catalogue_repo.save(next_catalogue)


__all__ = [
    "ModeloIvaWalletCorrectionNoRecordError",
    "ModeloIvaWalletCorrectionSealedError",
    "ModeloIvaWalletSeedError",
    "ModeloIvaWalletSeedNegativeAmountError",
    "ModeloIvaWalletSeedNoTaxpayerError",
    "correct_iva_compensation_period_for_bucket",
    "seed_iva_compensation_period_for_bucket",
]
