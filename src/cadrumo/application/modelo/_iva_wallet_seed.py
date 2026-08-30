"""Application facade for Modelo 303 IVA wallet seed and override operations.

This module resolves the active bucket to a taxpayer NIF, validates the
operator-supplied amount, and then delegates the persistence write to the
calculation layer. Seed and correction flows write
:class:`~cadrumo.domain.iva_compensation.IvaCompensationPeriodState` records through
``seed_iva_compensation_period`` / ``correct_iva_compensation_period``; override
flows persist an
:class:`~cadrumo.domain.iva_compensation.reconciliation.IvaCompensationReconciliationDecision`
through ``reconcile_modelo_303_iva_compensation``. Every mutation appends a typed
bucket event via :class:`~adapters.persistence.profile.buckets.BucketEventHistoryRepository`.

The facade is intentionally above the pure writers. It can scan work units and
calculation revisions before changing an opening carry-forward basis, so
:func:`correct_iva_compensation_period_for_bucket` and
:func:`record_iva_compensation_override_for_bucket` refuse changes once a sealed
Modelo 303 revision has consumed that basis.

See Also:
    :mod:`cadrumo.application.calculations.iva_compensation_history`
    Single-writer seed and correction primitives for local IVA compensation
    history.
    :mod:`cadrumo.application.calculations._iva_wallet_reconciliation`
    Reconciliation service that turns wallet/local/override evidence into a
    persisted Modelo 303 prior-compensation decision.
    :mod:`cadrumo.application.modelo._iva_wallet_gate`
    Calculation/export gate that replays the persisted wallet decision before a
    Modelo 303 revision is allowed to use the binding.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.iva_compensation.carry_forward import IvaCompensationPeriodState, iva_compensation_period_sort_key
from ...domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ...domain.modelos.calculation_revision import SEALED_REVISION_STATES
from ...domain.modelos.errors import ModeloError
from ..calculations import correct_iva_compensation_period, seed_iva_compensation_period
from ._iva_wallet_gate import taxpayer_nif_for_bucket
from ._preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario


class ModeloIvaWalletSeedError(ModeloError):
    """Base class for Modelo IVA wallet seed, correction, and override errors."""

    def __init__(
        self,
        *,
        translated_message: str,
        context: dict[str, object] | None = None,
        precondition_failure: ModeloPreconditionFailure | None = None,
    ) -> None:
        super().__init__(
            translated_message,
            translated_message=translated_message,
            context=context,
        )
        self._precondition_failure = precondition_failure

    @property
    def terminal_precondition_verdict(self):
        """Expose the application-owned refusal without adding CLI recovery prose."""
        failure = self._precondition_failure
        return None if failure is None else failure.verdict


class ModeloIvaWalletSeedNoTaxpayerError(ModeloIvaWalletSeedError):
    """Raised when the selected bucket cannot provide a taxpayer NIF.

    The seed facade uses :func:`cadrumo.application.modelo._iva_wallet_gate.taxpayer_nif_for_bucket`
    so the same bucket/profile identity authority feeds seed, correction, override,
    and persisted-decision replay paths.
    """


class ModeloIvaWalletSeedNegativeAmountError(ModeloIvaWalletSeedError):
    """Raised when an operator supplies a negative seed, correction, or override amount."""


class ModeloIvaWalletCorrectionNoRecordError(ModeloIvaWalletSeedError):
    """Raised when a correction targets a period that has no seeded record yet.

    Correction re-writes an existing opening balance; an absent period is a
    seed, not a correction. The refusal carries this factual distinction only.
    """


def _missing_taxpayer_error(*, bucket_id: str, subject_leaf_key: str) -> ModeloIvaWalletSeedNoTaxpayerError:
    """Return the closed application outcome when no taxpayer identity is available."""
    return ModeloIvaWalletSeedNoTaxpayerError(
        translated_message="application.modelo.iva_wallet.seed_no_nif",
        context={"bucket_id": bucket_id},
        precondition_failure=build_modelo_precondition_failure_for_scenario(
            subject_leaf_key=subject_leaf_key,
            scenario_id=f"{subject_leaf_key}.taxpayer_identity_missing",
            evidence_id="modelo.iva_wallet.taxpayer",
            evidence_values={"bucket_id": bucket_id, "taxpayer_identity_available": False},
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        ),
    )


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


class ModeloIvaWalletOverrideSealedError(ModeloIvaWalletSeedError):
    """Raised when an override targets a period a filed Modelo 303 already consumed.

    A sealed (``VERIFICADO_COMPLETO`` / ``PRESENTADO`` / ``PRESENTADO_SUPERSEDIDO``)
    Modelo 303 revision at or after the period carries that period's compensación
    forward as its *compensación pendiente de periodos anteriores*. Recording an
    override would silently change the basis of a return the operator has already
    filed — the same filed-immutability risk the correction guard and the ledger
    restore guard enforce — so the override is refused with the offending revision
    named.
    """


class ModeloIvaWalletOverrideFreshWalletError(ModeloIvaWalletSeedError):
    """Raised when an override would overrule fresh AEAT wallet evidence.

    When a non-blocked ``aeat_wallet`` reconciliation decision already resolves the
    period, the live AEAT wallet/cartera is the authority for
    ``iva.compensacion-pendiente-periodos-anteriores`` (AEAT box 110). An
    operator-asserted override must not silently overrule fresh AEAT evidence, so
    the override is refused.
    """


def _require_non_negative_wallet_amount(amount: Decimal) -> None:
    """Refuse a negative opening, correction, or operator-override amount."""
    if amount < Decimal("0"):
        raise ModeloIvaWalletSeedNegativeAmountError(
            translated_message="application.modelo.iva_wallet.seed_negative_amount",
            context={"amount": str(amount)},
        )


def seed_iva_compensation_period_for_bucket(
    *,
    bucket_id: str,
    period: Period,
    amount: Decimal,
) -> IvaCompensationPeriodState:
    """Seed local IVA compensation history for the bucket taxpayer.

    Returns an :class:`~cadrumo.domain.iva_compensation.IvaCompensationPeriodState`
    stored by :func:`cadrumo.application.calculations.seed_iva_compensation_period`.
    The stored state represents an operator-declared opening carry-forward
    balance for a Modelo 303 period that predates local history. It is not a live
    AEAT wallet observation and it does not by itself authorize a Modelo 303
    calculation; the wallet reconciliation/gate path still owns the effective
    ``modelo-303-compensacion-pendiente-anteriores`` decision.

    See Also:
        :func:`cadrumo.application.calculations.seed_iva_compensation_period`
        Pure single-writer primitive that stores the seeded period state.
        :func:`cadrumo.application.modelo._iva_wallet_gate.resolve_iva_compensation_decision_for_calculation`
        Gate-side resolver that requires a persisted decision before applying
        the prior-compensation binding.
    """
    _require_non_negative_wallet_amount(amount)
    taxpayer_nif = taxpayer_nif_for_bucket(bucket_id)
    if taxpayer_nif is None:
        raise _missing_taxpayer_error(bucket_id=bucket_id, subject_leaf_key="modelo.iva_wallet.seed")
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
    from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository

    seeded_key = (period.filing_year, iva_compensation_period_sort_key(period))
    work_units = WorkUnitCatalogueRepository(bucket_id=bucket_id).load()
    revisions = CalculationRevisionCatalogueRepository(bucket_id=bucket_id).load()
    candidates: list[tuple[tuple[int, tuple[int, str]], str, str, int, str]] = []
    for revision in revisions.values():
        if revision.state not in SEALED_REVISION_STATES:
            continue
        work_unit = work_units.work_units.get(revision.work_unit_id)
        if work_unit is None or work_unit.bucket_id != bucket_id:
            continue
        if work_unit.modelo != Modelo.M303.value:
            continue
        consuming_key = (work_unit.period.filing_year, iva_compensation_period_sort_key(work_unit.period))
        if consuming_key < seeded_key:
            continue
        candidates.append(
            (
                (work_unit.period.filing_year, iva_compensation_period_sort_key(work_unit.period)),
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

    Returns the corrected
    :class:`~cadrumo.domain.iva_compensation.IvaCompensationPeriodState`.

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
      :func:`~cadrumo.application.calculations.correct_iva_compensation_period`
      primitive (no parallel write path), which refuses to fabricate a record
      where none exists (re-raised as
      :class:`ModeloIvaWalletCorrectionNoRecordError`);
    - emits a :attr:`~cadrumo.domain.buckets.BucketEventType.MODELO_IVA_WALLET_CORRECTED`
      audit event carrying the operator ``reason`` and the before/after amounts.

    The local app never files; correcting the wallet basis touches no AEAT write
    surface.

    See Also:
        :func:`cadrumo.application.calculations.correct_iva_compensation_period`
        Single-writer primitive that replaces the stored seed after this facade's
        filed-basis guard passes.
        :class:`cadrumo.domain.buckets.BucketEventType`
        Declares the ``MODELO_IVA_WALLET_CORRECTED`` audit event emitted here.
    """
    _require_non_negative_wallet_amount(amount)
    taxpayer_nif = taxpayer_nif_for_bucket(bucket_id)
    if taxpayer_nif is None:
        raise _missing_taxpayer_error(bucket_id=bucket_id, subject_leaf_key="modelo.iva_wallet.correct")

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
    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...core.time import now
    from ...domain.buckets.event import BucketEventObjectType, BucketEventType
    from ...domain.buckets.event_repository import emit_bucket_event

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
    # Through the shared emitter: the history is a singleton row, so the
    # load-append-save this replaced discarded any event another writer
    # committed in between, and content-addressed survivors leave no gap to
    # notice it.
    emit_bucket_event(
        repository=BucketEventHistoryRepository(),
        bucket_id=bucket_id,
        event_type=BucketEventType.MODELO_IVA_WALLET_CORRECTED,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=object_id,
        payload=payload,
        payload_version=1,
    )


def record_iva_compensation_override_for_bucket(
    *,
    bucket_id: str,
    period: Period,
    amount: Decimal,
    reason: str,
    evidence_locator: str,
) -> IvaCompensationReconciliationDecision:
    """Record an explicit taxpayer override for Modelo 303 prior compensation.

    Returns the persisted
    :class:`~cadrumo.domain.iva_compensation.reconciliation.IvaCompensationReconciliationDecision`
    with the ``taxpayer_override`` source.

    The Modelo 303 reconciliation refuses to AUTO-apply a seeded or local-recurrence
    prior-compensation balance when no live AEAT wallet evidence is available; the
    decision is blocked pending an explicit taxpayer override. This is the
    operator-facing recorder of that override. It:

    - resolves the bucket's taxpayer NIF (refusing when absent, like seed/correct);
    - refuses a negative amount (like seed/correct);
    - **guards the filed basis** (:class:`ModeloIvaWalletOverrideSealedError`):
      refuses when a sealed (already-filed) Modelo 303 revision at or after the
      period has already consumed that period's compensación basis — recording an
      override would silently change a filed return, the filed-immutability risk the
      correction guard and the ledger restore guard enforce;
    - **does not overrule fresh AEAT evidence**
      (:class:`ModeloIvaWalletOverrideFreshWalletError`): refuses when a non-blocked
      ``aeat_wallet`` decision already resolves the period;
    - builds an :class:`~cadrumo.domain.iva_compensation.IvaCompensationOverride` and
      drives :func:`~cadrumo.application.calculations.reconcile_modelo_303_iva_compensation`
      with ``persist=True`` to store a non-blocking ``taxpayer_override`` decision
      keyed by period through the single decision repository; a subsequent
      ``work calculate`` reads it and applies the amount to
      ``iva.compensacion-pendiente-periodos-anteriores``;
    - emits a ``MODELO_IVA_WALLET_OVERRIDE_RECORDED`` audit event.

    ``reason`` and ``evidence_locator`` are operator-asserted audit metadata: they
    are recorded for the operator's own audit trail and are NOT verified by the app
    to point at real evidence. The override is the taxpayer asserting, under their
    own responsibility, a figure the app cannot otherwise corroborate locally.

    The local app never files; recording an override touches no AEAT write surface
    and does not relax the dependent-period verify gate, which still requires
    official external evidence before a dependent period can be filed.

    NOTE: the persisted decision is currently NOT re-reconciled when later evidence
    for the period arrives (the broader sticky-decision behaviour in
    ``resolve_iva_compensation_decision_for_calculation``); recording an override
    therefore takes precedence for the period until explicitly re-recorded or
    corrected. That re-reconciliation is tracked as a separate follow-up.

    See Also:
        :func:`cadrumo.application.calculations.reconcile_modelo_303_iva_compensation`
        Persists the non-blocking taxpayer-override wallet decision consumed by
        later Modelo 303 calculations.
        :class:`cadrumo.application.calculations.IvaWalletDecisionRepository`
        Repository used to detect an existing fresh AEAT-wallet decision before
        allowing an override.
        :func:`cadrumo.application.modelo._iva_wallet_gate.require_persisted_iva_compensation_decision_matches_revision`
        Replay gate that ensures exported/filed revisions still match the
        persisted decision.
    """
    _require_non_negative_wallet_amount(amount)
    taxpayer_nif = taxpayer_nif_for_bucket(bucket_id)
    if taxpayer_nif is None:
        raise _missing_taxpayer_error(bucket_id=bucket_id, subject_leaf_key="modelo.iva_wallet.override")

    blocker = _sealed_modelo_303_blocker_for_period(bucket_id=bucket_id, period=period)
    if blocker is not None:
        work_unit_id, revision_id, blocker_year, blocker_period = blocker
        raise ModeloIvaWalletOverrideSealedError(
            translated_message="application.modelo.iva_wallet.override_sealed_blocked",
            context={
                "filing_year": period.filing_year,
                "period": period.registry_token,
                "blocking_work_unit_id": work_unit_id,
                "blocking_calculation_revision_id": revision_id,
                "blocking_filing_year": blocker_year,
                "blocking_period": blocker_period,
            },
        )

    from ..calculations import IvaWalletDecisionRepository, reconcile_modelo_303_iva_compensation

    existing = IvaWalletDecisionRepository().load_decision(taxpayer_nif, period)
    if existing is not None and not existing.blocked and str(existing.selected_authority) == "aeat_wallet":
        raise ModeloIvaWalletOverrideFreshWalletError(
            translated_message="application.modelo.iva_wallet.override_fresh_wallet_blocked",
            context={
                "filing_year": period.filing_year,
                "period": period.registry_token,
            },
        )

    from ...core.time import now
    from ...domain.iva_compensation.reconciliation import IvaCompensationOverride

    snapshot = bundled_authority().snapshot(
        Modelo.M303.value,
        filing_year=period.filing_year,
        period=period.registry_token,
    )
    override = IvaCompensationOverride(
        amount=amount,
        operator_explanation=reason,
        evidence_locator=evidence_locator,
        recorded_at=now(),
    )
    report = reconcile_modelo_303_iva_compensation(
        snapshot,
        taxpayer_nif=taxpayer_nif,
        wallet=None,
        override=override,
        persist=True,
    )

    _emit_iva_wallet_override_event(
        bucket_id=bucket_id,
        taxpayer_nif=taxpayer_nif,
        period=period,
        amount=amount,
        reason=reason,
        evidence_locator=evidence_locator,
    )

    return report.decision


def _emit_iva_wallet_override_event(
    *,
    bucket_id: str,
    taxpayer_nif: str,
    period: Period,
    amount: Decimal,
    reason: str,
    evidence_locator: str,
) -> None:
    """Append the ``MODELO_IVA_WALLET_OVERRIDE_RECORDED`` audit event for an override."""
    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...core.time import now
    from ...domain.buckets.event import BucketEventObjectType, BucketEventType
    from ...domain.buckets.event_repository import emit_bucket_event

    occurred_at = now()
    object_id = f"303:{period.filing_year}:{period.registry_token}"
    payload = {
        "taxpayer_nif": taxpayer_nif,
        "filing_year": str(period.filing_year),
        "period": period.registry_token,
        "amount": str(amount),
        "reason": reason,
        "evidence_locator": evidence_locator,
    }
    # Through the shared emitter: the history is a singleton row, so the
    # load-append-save this replaced discarded any event another writer
    # committed in between, and content-addressed survivors leave no gap to
    # notice it.
    emit_bucket_event(
        repository=BucketEventHistoryRepository(),
        bucket_id=bucket_id,
        event_type=BucketEventType.MODELO_IVA_WALLET_OVERRIDE_RECORDED,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=object_id,
        payload=payload,
        payload_version=1,
    )


__all__ = [
    "ModeloIvaWalletCorrectionNoRecordError",
    "ModeloIvaWalletCorrectionSealedError",
    "ModeloIvaWalletOverrideFreshWalletError",
    "ModeloIvaWalletOverrideSealedError",
    "ModeloIvaWalletSeedError",
    "ModeloIvaWalletSeedNegativeAmountError",
    "ModeloIvaWalletSeedNoTaxpayerError",
    "correct_iva_compensation_period_for_bucket",
    "record_iva_compensation_override_for_bucket",
    "seed_iva_compensation_period_for_bucket",
]
