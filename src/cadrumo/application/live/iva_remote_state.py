"""IVA remote-state, compensation-history, and wallet live actions.

The module separates stored-evidence reads from live acquisition. Listing and
load helpers read encrypted local IVA compensation history, wallet decisions,
wallet observations, and acquisition manifests without contacting AEAT. Capture
helpers enforce the live-read gate, acquire an authenticated
:class:`~cadrumo.adapters.outbound.aeat.auth.AeatSession`,
then persist filed-history and wallet evidence before reconciliation consumes it.

Encrypted acquisition manifests are stored through the active bucket's
:class:`SecureObjectRepository` via the
typed manifest repository under
:data:`~cadrumo.adapters.persistence.storage.LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE`.
The manifest is redacted operational evidence of the acquisition attempt; it is
not a remote submission record.

See Also:
    :class:`~cadrumo.application.live.IvaRemoteStateStoredEvidenceReport`
        Stored-evidence report returned without a live AEAT read.
    :class:`~cadrumo.application.live.IvaRemoteStateAcquisitionReport`
        Combined read-only acquisition report for filed history and wallet
        surfaces.
    :func:`~cadrumo.application.live.session.active_verified_session`
        Shared read-only authenticated-session helper used by individual
        capture surfaces.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import ClassVar, override

from pydantic import BaseModel

from ...adapters.outbound.aeat.sede.declarations import open_declarations_register as _open_declarations_register
from ...adapters.outbound.aeat.sede.declarations import shared_playwright as _shared_playwright
from ...adapters.outbound.aeat.sede.declarations_schema import Declaracion as _Declaracion
from ...adapters.outbound.aeat.sede.iva_compensation_wallet import (
    PRE303_PRESENTATION_SERVICE_URL as _PRE303_PRESENTATION_SERVICE_URL,
)
from ...adapters.outbound.aeat.sede.iva_compensation_wallet import (
    fetch_iva_compensation_wallet as _fetch_iva_compensation_wallet,
)
from ...adapters.outbound.aeat.sede.observation_store import (
    FiledDeclaracionObservationStore as _FiledDeclaracionObservationStore,
)
from ...adapters.outbound.aeat.sede.schema import FiledDeclaracionObservation as _FiledDeclaracionObservation
from ...adapters.outbound.aeat.sede.schema import IvaCompensationWalletObservation as _IvaCompensationWalletObservation
from ...adapters.persistence.storage.envelope.secure_bound_repository import (
    SecureBoundRepository as _SecureBoundRepository,
)
from ...adapters.persistence.storage.runtime_repository import (
    secure_object_repository_for_active_bucket as _secure_object_repository_for_active_bucket,
)
from ...adapters.persistence.storage.secure_object_namespaces import (
    LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE as _LIVE_IVA_REMOTE_STATE_ACQUISITIONS_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository as _SecureObjectRepository
from ...application.auth.session_types import AeatSession as _AeatSession
from ...application.auth.sessions import AuthenticatedAeatSessionResult as _AuthenticatedAeatSessionResult
from ...application.auth.sessions import ensure_authenticated_aeat_session as _ensure_authenticated_aeat_session
from ...application.calculations._iva_wallet_reconciliation import (
    reconcile_modelo_303_iva_compensation as _reconcile_modelo_303_iva_compensation,
)
from ...application.calculations.iva_compensation_history import (
    IvaCompensationHistoryRepository as _IvaCompensationHistoryRepository,
)
from ...application.calculations.observations_repository import (
    CalculationObservationRepository as _CalculationObservationRepository,
)
from ...application.calculations.observations_repository import (
    IvaWalletDecisionRepository as _IvaWalletDecisionRepository,
)
from ...application.calculations.observations_repository import iva_wallet_decision_key as _iva_wallet_decision_key
from ...core.access_gate.gate import AeatAccessGate as _AeatAccessGate
from ...core.bucket_pointer import resolve_active_bucket_id as _resolve_active_bucket_id
from ...core.config import Settings as _Settings
from ...core.config import load_settings as _load_settings
from ...core.errors.hierarchy import CadrumoError as _CadrumoError
from ...core.hashing import sha256_hex as _sha256_hex
from ...core.identity import tax_id_identity_token as _tax_id_identity_token
from ...core.modelo import Modelo
from ...core.period import Period
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_location as _storage_location
from ...core.time.clock import now
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.iva_compensation.carry_forward import IvaCompensationCarryForwardLot as _IvaCompensationCarryForwardLot
from ...domain.iva_compensation.carry_forward import IvaCompensationPeriodState as _IvaCompensationPeriodState
from ...domain.iva_compensation.carry_forward import (
    build_iva_compensation_carry_forward_report as _build_iva_compensation_carry_forward_report,
)
from ...domain.iva_compensation.reconciliation import IvaCompensationAuthoritySource as _IvaCompensationAuthoritySource
from ...domain.iva_compensation.reconciliation import (
    IvaCompensationReconciliationDecision as _IvaCompensationReconciliationDecision,
)
from .errors import LiveApplicationError, LiveApplicationInputError, LiveIvaSurfaceTimeoutError
from .filed_data_capture import capture_report_path as _capture_report_path
from .filed_observation_persistence import latest_declarations_by_period as _latest_declarations_by_period
from .filed_observation_persistence import (
    persist_iva_compensation_history_observations_strict as _persist_iva_compensation_history_observations_strict,
)
from .remote_state_models import (
    IvaCompensationCarryForwardLotRow,
    IvaCompensationHistoryCaptureReport,
    IvaCompensationHistoryReport,
    IvaCompensationHistoryRow,
    IvaRemoteStateAcquisitionManifest,
    IvaRemoteStateAcquisitionReport,
    IvaRemoteStateAcquisitionSurfaceManifest,
    IvaRemoteStateStoredEvidenceReport,
    IvaWalletAuthorityDecisionRow,
    IvaWalletCaptureReport,
    LiveIvaReadOutcome,
    LiveIvaReadSurface,
    StoredIvaRemoteStateAcquisitionRow,
    StoredIvaWalletObservationRow,
)
from .remote_state_outcomes import auth_outcome as _auth_outcome
from .remote_state_outcomes import evidence_ref as _evidence_ref
from .remote_state_outcomes import surface_outcome as _surface_outcome
from .session import active_verified_session as _active_verified_session

# Deliberately not a ``sha256:`` value, so an absent filing subject stays
# distinguishable from every real pseudonymised one.
_ABSENT_TAXPAYER_REF = "absent"

# Bare directory names are read from the taxonomy and joined onto the
# operator-overridable live-state root.
_LIVE_STATE_IVA_WALLET_DIRNAME = Path(_storage_location(StorageCategory.LIVE_STATE_IVA_WALLET).subpath).name
_LIVE_STATE_IVA_REMOTE_STATE_DIRNAME = Path(
    _storage_location(StorageCategory.LIVE_STATE_IVA_REMOTE_STATE).subpath,
).name
_IVA_REMOTE_STATE_FILED_HISTORY_DIRNAME = Path(
    _storage_location(StorageCategory.LIVE_STATE_IVA_REMOTE_STATE_FILED_HISTORY).subpath,
).name
_IVA_REMOTE_STATE_WALLET_DIRNAME = Path(
    _storage_location(StorageCategory.LIVE_STATE_IVA_REMOTE_STATE_WALLET).subpath,
).name


class IvaRemoteStateAcquisitionManifestRepository(_SecureBoundRepository[IvaRemoteStateAcquisitionManifest]):
    """Repository for encrypted live IVA acquisition manifests.

    The repository stores redacted :class:`IvaRemoteStateAcquisitionManifest`
    payloads under the active profile bucket. Raw AEAT rows remain in their
    dedicated evidence stores.

    The namespace, sensitivity, schema version, and object-key grammar come
    from
    :data:`~cadrumo.adapters.persistence.storage.LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE`.
    The :class:`~cadrumo.adapters.persistence.storage.SecureBoundRepository` base
    writes each manifest through an
    :class:`~cadrumo.adapters.persistence.storage.Envelope` so acquisition ids and
    redacted surface summaries stay inside the encrypted secure-object store.
    """

    namespace: ClassVar[str] = _LIVE_IVA_REMOTE_STATE_ACQUISITIONS_STORAGE_NAMESPACE.namespace
    sensitivity: ClassVar = _LIVE_IVA_REMOTE_STATE_ACQUISITIONS_STORAGE_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = _LIVE_IVA_REMOTE_STATE_ACQUISITIONS_STORAGE_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = IvaRemoteStateAcquisitionManifest

    def __init__(self, *, objects: _SecureObjectRepository | None = None) -> None:
        """Initialise the repository, resolving the active bucket's secure-object store when no override is given."""
        super().__init__(objects=objects or _secure_object_repository_for_active_bucket())

    @override
    def extract_identifier(self, payload: IvaRemoteStateAcquisitionManifest) -> str:
        """Return the acquisition's stable string identifier."""
        return payload.acquisition_id


def list_iva_compensation_history(
    *,
    repository: _IvaCompensationHistoryRepository | None = None,
    decision_repository: _IvaWalletDecisionRepository | None = None,
    as_of_year: int | None = None,
) -> IvaCompensationHistoryReport:
    """List profile-local IVA compensation history and return an :class:`IvaCompensationHistoryReport`."""
    with _active_profile_storage_span():
        repo = repository if repository is not None else _IvaCompensationHistoryRepository()
        decision_repo = decision_repository if decision_repository is not None else _IvaWalletDecisionRepository()
        states = repo.list_periods()
        rows = tuple(_history_row(state) for state in states)
        resolved_as_of_year = as_of_year if as_of_year is not None else now().year
        carry_forward = _build_iva_compensation_carry_forward_report(states, as_of_year=resolved_as_of_year)
        authority_decisions = tuple(_authority_decision_row(decision) for decision in decision_repo.list_decisions())
        return IvaCompensationHistoryReport(
            row_count=len(rows),
            rows=rows,
            as_of_year=carry_forward.as_of_year,
            carry_forward_lot_count=len(carry_forward.lots),
            carry_forward_lots=tuple(_carry_forward_lot_row(lot) for lot in carry_forward.lots),
            unallocated_applied_amount=str(carry_forward.unallocated_applied_amount),
            authority_decision_count=len(authority_decisions),
            authority_decisions=authority_decisions,
        )


def load_iva_remote_state(
    *,
    as_of_year: int | None = None,
    wallet_store: _FiledDeclaracionObservationStore | None = None,
    repository: _IvaCompensationHistoryRepository | None = None,
    decision_repository: _IvaWalletDecisionRepository | None = None,
) -> IvaRemoteStateStoredEvidenceReport:
    """Reload stored remote IVA evidence from the active profile without contacting AEAT.

    Returns an :class:`IvaRemoteStateStoredEvidenceReport` with the
    stored compensation history, wallet observations, reconciliation decisions,
    and redacted acquisition manifests.
    """
    with _active_profile_storage_span():
        history = list_iva_compensation_history(
            repository=repository,
            decision_repository=decision_repository,
            as_of_year=as_of_year,
        )
        store = wallet_store if wallet_store is not None else _FiledDeclaracionObservationStore(Path("."))
        wallet_rows = tuple(
            _stored_wallet_observation_row(observation) for observation in store.list_iva_wallet_observations()
        )
        acquisition_rows = tuple(
            _stored_acquisition_manifest_row(manifest) for manifest in list_iva_remote_state_acquisition_manifests()
        )
        return IvaRemoteStateStoredEvidenceReport(
            history=history,
            wallet_observation_count=len(wallet_rows),
            wallet_observations=wallet_rows,
            acquisition_manifest_count=len(acquisition_rows),
            acquisition_manifests=acquisition_rows,
        )


@contextmanager
def _active_profile_storage_span():
    active_bucket_id = _resolve_active_bucket_id()
    if active_bucket_id is None:
        from ...adapters.persistence.storage.errors import StorageValidationError as _StorageValidationError

        raise _StorageValidationError(translated_message="errors.storage.runtime.not_ready")
    from ...adapters.persistence.storage.master_key.active_session import (
        active_bucket_session_serves as _active_bucket_session_serves,
    )

    # Reuse only a session already open for THIS bucket. Reusing on the mere
    # presence of a session would capture whichever bucket happened to be
    # bound and read the wrong profile's encrypted store under its key.
    if _active_bucket_session_serves(active_bucket_id):
        yield
        return
    from ...adapters.persistence.storage.errors import StorageValidationError as _StorageValidationError

    raise _StorageValidationError(translated_message="errors.storage.runtime.not_ready")


async def capture_iva_compensation_history(
    *,
    year_from: int,
    year_to: int,
    output_root: Path,
) -> IvaCompensationHistoryCaptureReport:
    """Capture filed Modelo 303s across years and return an :class:`IvaCompensationHistoryCaptureReport`."""
    if year_from > year_to:
        raise LiveApplicationInputError(
            translated_message="live.errors.year_range_invalid",
        )

    with _active_profile_storage_span():
        session, settings = await _active_verified_session()
        return await _capture_iva_compensation_history_with_session(
            session,
            settings=settings,
            year_from=year_from,
            year_to=year_to,
            output_root=output_root,
        )


async def _capture_iva_compensation_history_with_session(
    session: _AeatSession,
    *,
    settings: _Settings,
    year_from: int,
    year_to: int,
    output_root: Path,
    progress_context: dict[str, object] | None = None,
) -> IvaCompensationHistoryCaptureReport:
    """Capture filed Modelo 303s using an already-acquired AEAT session."""
    store = _FiledDeclaracionObservationStore(output_root)
    observation_paths: list[str] = []
    artefact_refs: list[str] = []
    observations_for_calculation: list[_FiledDeclaracionObservation] = []
    failed_declarations: list[str] = []
    casilla_count = 0

    async with (
        _shared_playwright(session) as playwright,
        _open_declarations_register(
            session,
            settings=settings,
            playwright=playwright,
        ) as register,
    ):
        for year in range(year_to, year_from - 1, -1):
            if progress_context is not None:
                progress_context.update(
                    {
                        "stage": "walk_declarations_register",
                        "modelo": Modelo.M303.value,
                        "ejercicio": year,
                    },
                )
            declarations = await register.walk(modelo=Modelo.M303.value, ejercicio=year)
            for declaration in _latest_declarations_by_period(declarations):
                if progress_context is not None:
                    progress_context.update(
                        {
                            "stage": "capture_declaration_observation",
                            "modelo": declaration.modelo,
                            "ejercicio": declaration.ejercicio,
                            "period": declaration.period.registry_token,
                        },
                    )
                try:
                    observation = await asyncio.wait_for(
                        register.capture_observation(
                            declaration,
                            artefact_sink=store.persist_artefact,
                        ),
                        timeout=settings.cadrumo_live_iva_declaration_capture_timeout_ms / 1000,
                    )
                except (TimeoutError, _CadrumoError, OSError) as exc:
                    failed_declarations.append(_failed_declaration_ref(declaration, exc))
                    continue
                manifest_path = store.persist_observation(observation)
                observation_paths.append(_capture_report_path(manifest_path, output_root=output_root))
                artefact_refs.extend(
                    storage_ref
                    for artefact in observation.artefacts
                    for storage_ref in (artefact.storage_ref,)
                    if storage_ref is not None
                )
                casilla_count += len(observation.casillas)
                observations_for_calculation.append(observation)

    return _iva_compensation_history_capture_report(
        output_root=output_root,
        year_from=year_from,
        year_to=year_to,
        observation_paths=tuple(observation_paths),
        artefact_refs=tuple(artefact_refs),
        casilla_count=casilla_count,
        observations_for_calculation=tuple(observations_for_calculation),
        failed_declarations=tuple(failed_declarations),
    )


def _iva_compensation_history_capture_report(
    *,
    output_root: Path,
    year_from: int,
    year_to: int,
    observation_paths: tuple[str, ...],
    artefact_refs: tuple[str, ...],
    casilla_count: int,
    observations_for_calculation: tuple[_FiledDeclaracionObservation, ...],
    failed_declarations: tuple[str, ...],
) -> IvaCompensationHistoryCaptureReport:
    calculation_observation_keys = _persist_iva_compensation_history_observations_strict(observations_for_calculation)
    reloaded = list_iva_compensation_history()

    return IvaCompensationHistoryCaptureReport(
        output_root=str(output_root),
        year_from=year_from,
        year_to=year_to,
        captured_count=len(observation_paths),
        observation_paths=observation_paths,
        artefact_refs=artefact_refs,
        casilla_count=casilla_count,
        calculation_observation_count=len(calculation_observation_keys),
        calculation_observation_keys=tuple(calculation_observation_keys),
        reloaded_history_count=reloaded.row_count,
        reloaded_rows=reloaded.rows,
        failed_declaration_count=len(failed_declarations),
        failed_declarations=failed_declarations,
    )


def _failed_declaration_ref(declaration: _Declaracion, exc: BaseException) -> str:
    return (
        f"modelo={declaration.modelo};ejercicio={declaration.ejercicio};"
        f"period={declaration.period.registry_token};failure_type={type(exc).__name__}"
    )


def _history_row(state: _IvaCompensationPeriodState) -> IvaCompensationHistoryRow:
    return IvaCompensationHistoryRow(
        year=state.filing_year,
        period=state.period,
        provenance=state.provenance,
        register_status=state.status,
        presented_at=state.presented_at,
        prior_pending_amount=_decimal_text(state.prior_pending_amount),
        applied_amount=_decimal_text(state.applied_amount),
        pending_for_later_amount=_decimal_text(state.pending_for_later_amount),
        period_result_amount=_decimal_text(state.period_result_amount),
        final_result_amount=_decimal_text(state.final_result_amount),
        generated_amount=str(state.generated_amount),
        available_end_amount=str(state.available_end_amount),
    )


def _carry_forward_lot_row(lot: _IvaCompensationCarryForwardLot) -> IvaCompensationCarryForwardLotRow:
    return IvaCompensationCarryForwardLotRow(
        taxpayer_ref=_taxpayer_ref(lot.taxpayer_nif),
        source_filing_year=lot.source_filing_year,
        source_period=lot.source_period,
        generated_amount=str(lot.generated_amount),
        applied_amount=str(lot.applied_amount),
        remaining_amount=str(lot.remaining_amount),
        age_years=lot.age_years,
        expiry_review_state=lot.expiry_review_state.value,
        source_observation_key=_evidence_ref(lot.source_observation_key),
    )


def _authority_decision_row(decision: _IvaCompensationReconciliationDecision) -> IvaWalletAuthorityDecisionRow:
    return IvaWalletAuthorityDecisionRow(
        taxpayer_ref=_taxpayer_ref(decision.taxpayer_nif),
        target_year=decision.target_year,
        target_period=decision.target_period,
        selected_authority=decision.selected_authority,
        selected_amount=_decimal_text(decision.selected_amount),
        wallet_amount=_decimal_text(decision.wallet_amount),
        local_recurrence_amount=_decimal_text(decision.local_recurrence_amount),
        override_amount=_decimal_text(decision.override_amount),
        divergence=decision.divergence,
        blocked=decision.blocked,
        stale_wallet=decision.stale_wallet,
        reason_identity=decision.reason_identity,
        operator_explanation=decision.operator_explanation,
        wallet_captured_at=decision.wallet_captured_at,
        decided_at=decision.decided_at,
        authority_sources=tuple(_authority_source_text(source) for source in decision.authority_sources),
    )


def _stored_wallet_observation_row(observation: _IvaCompensationWalletObservation) -> StoredIvaWalletObservationRow:
    return StoredIvaWalletObservationRow(
        taxpayer_ref=_taxpayer_ref(observation.taxpayer_nif),
        target_year=observation.target_year,
        target_period=observation.target_period,
        row_count=len(observation.rows),
        total_pending=str(observation.total_pending),
        captured_at=observation.captured_at,
        raw_sha256=observation.raw_sha256,
    )


def _stored_acquisition_manifest_row(
    manifest: IvaRemoteStateAcquisitionManifest,
) -> StoredIvaRemoteStateAcquisitionRow:
    return StoredIvaRemoteStateAcquisitionRow(
        acquisition_ref=_evidence_ref(manifest.acquisition_id),
        captured_at=manifest.captured_at,
        auth_status=manifest.auth.status.value,
        auth_outcome_mode=manifest.auth.outcome_mode.value,
        auth_failure_mode=manifest.auth.failure_mode.value if manifest.auth.failure_mode is not None else None,
        auth_failure_type=manifest.auth.failure_type,
        auth_diagnostic_ref=manifest.auth.diagnostic_ref,
        auth_provider_kind=manifest.auth.provider_kind,
        auth_reused_persisted_session=manifest.auth.reused_persisted_session,
        year_from=manifest.year_from,
        year_to=manifest.year_to,
        target_year=manifest.target_year,
        target_period=manifest.target_period,
        filed_history_succeeded=manifest.filed_history_succeeded,
        wallet_succeeded=manifest.wallet_succeeded,
        surfaces=tuple(_stored_acquisition_surface_text(surface) for surface in manifest.surfaces),
    )


def _stored_acquisition_surface_text(surface: IvaRemoteStateAcquisitionSurfaceManifest) -> str:
    parts = [surface.surface.value, f"status={surface.status.value}", f"outcome={surface.outcome_mode.value}"]
    if surface.failure_mode is not None:
        parts.append(f"failure_mode={surface.failure_mode.value}")
    if surface.failure_type is not None:
        parts.append(f"failure_type={surface.failure_type}")
    if surface.captured_count is not None:
        parts.append(f"captured={surface.captured_count}")
    if surface.calculation_observation_count is not None:
        parts.append(f"calculation_observations={surface.calculation_observation_count}")
    if surface.reloaded_history_count is not None:
        parts.append(f"reloaded_history={surface.reloaded_history_count}")
    if surface.wallet_row_count is not None:
        parts.append(f"wallet_rows={surface.wallet_row_count}")
    if surface.decision_ref is not None:
        parts.append(f"decision_ref={surface.decision_ref}")
    if surface.selected_authority is not None:
        parts.append(f"authority={surface.selected_authority}")
    if surface.divergence is not None:
        parts.append(f"divergence={surface.divergence}")
    if surface.blocked is not None:
        parts.append(f"blocked={surface.blocked}")
    return " ".join(parts)


def _authority_source_text(source: _IvaCompensationAuthoritySource) -> str:
    parts = [str(source.source_kind)]
    if source.source_modelo is not None:
        parts.append(f"modelo={source.source_modelo}")
    if source.source_filing_year is not None:
        parts.append(f"year={source.source_filing_year}")
    if source.source_periods:
        parts.append(f"periods={','.join(period.registry_token for period in source.source_periods)}")
    if source.amount is not None:
        parts.append(f"amount={source.amount}")
    parts.append(f"ref={_evidence_ref(source.source_locator)}")
    return " ".join(parts)


def _decimal_text(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _taxpayer_ref(taxpayer_nif: str | None) -> str:
    r"""Pseudonymise a filing subject's NIF into a CLI-safe reference.

    ``None`` is a legitimate domain value: a carry-forward lot inherits its
    subject from the source period state, which may itself declare none. The
    absent case returns an explicit marker rather than a digest, so it can
    never be read as a real subject nor collide with one -- hashing a
    stand-in would mint one stable ref that every subjectless row shared,
    making them look like the same taxpayer.

    A value that normalises to nothing takes the same exit, because it is the
    same fact one step later. The wallet observation's own guard is
    ``min_length=1`` on the RAW string, which admits ``" "`` and the ``\\xa0``
    that arrives from parsing an AEAT page; the canonical identity token then
    trims it to ``""``. Hashing that yields the sha256 of the empty string --
    one digest, worn by every blank row, and shaped exactly like a real
    subject's ref. The guard and the emptying live in different modules, so
    neither reads as wrong on its own.

    The aggregation package holds its own normalise-then-hash step for perceptor
    keys. This deliberately does not reuse it, and the reason is recorded so the
    two are not folded on the strength of looking alike: that one REFUSES a
    blank token, which is wrong here because a subjectless row is a legitimate
    domain value that must still project; and it returns the full digest, where
    this surface wants a short CLI-safe ref. The truncation width here is itself
    an identity contract -- two refs compare equal only if every producer cuts
    them identically -- so a shared function returning full hex would leave this
    site cutting locally regardless. What the two genuinely share is one
    expression over :func:`tax_id_identity_token` -- already the single identity
    authority both go through. The hashing spelling repeats; the identity rule
    does not.
    """
    if taxpayer_nif is None:
        return _ABSENT_TAXPAYER_REF
    token = _tax_id_identity_token(taxpayer_nif)
    if not token:
        return _ABSENT_TAXPAYER_REF
    digest = _sha256_hex(token.encode("utf-8"))
    return f"sha256:{digest[:12]}"


@dataclass(frozen=True, slots=True)
class _IvaWalletReconciliationObservation:
    taxpayer_nif: str
    target_year: int
    target_period: Period
    total_pending: Decimal
    source_url: object
    captured_at: datetime


def _wallet_reconciliation_observation(
    observation: _IvaCompensationWalletObservation,
) -> _IvaWalletReconciliationObservation:
    return _IvaWalletReconciliationObservation(
        taxpayer_nif=observation.taxpayer_nif,
        target_year=observation.target_year,
        target_period=observation.target_period,
        total_pending=observation.total_pending,
        source_url=observation.source_url,
        captured_at=observation.captured_at,
    )


def persist_and_reconcile_iva_compensation_wallet(
    observation: _IvaCompensationWalletObservation,
    *,
    output_root: Path,
    repository: _CalculationObservationRepository | None = None,
    decision_repository: _IvaWalletDecisionRepository | None = None,
    decided_at: datetime | None = None,
) -> IvaWalletCaptureReport:
    """Persist, reload, reconcile, and report one AEAT IVA wallet observation.

    The reload is intentional: downstream reconciliation must use evidence that
    actually survived the encrypted storage boundary, not only the in-memory
    result returned by the browser driver.

    Returns an :class:`IvaWalletCaptureReport`.
    """
    store = _FiledDeclaracionObservationStore(output_root)
    path = store.persist_iva_wallet_observation(observation)
    reloaded = store.load_iva_wallet_observation(path)
    if reloaded != observation:
        raise LiveApplicationError(
            translated_message="application.live.iva_wallet.errors.observation_reload_diverged",
            context={
                "target_year": observation.target_year,
                "target_period": observation.target_period.registry_token,
            },
        )
    snapshot = bundled_authority().snapshot(
        Modelo.M303.value,
        filing_year=reloaded.target_year,
        period=reloaded.target_period.registry_token,
    )
    reconciliation = _reconcile_modelo_303_iva_compensation(
        snapshot,
        taxpayer_nif=reloaded.taxpayer_nif,
        wallet=_wallet_reconciliation_observation(reloaded),
        repository=repository,
        decision_repository=decision_repository,
        decided_at=decided_at,
    )
    decision = reconciliation.decision
    decision_repo = (
        decision_repository
        if decision_repository is not None
        else _IvaWalletDecisionRepository(
            objects=repository.secure_object_repository if repository is not None else None,
        )
    )
    loaded_decision = decision_repo.load_decision(
        decision.taxpayer_nif,
        decision.target_period,
    )
    if loaded_decision != decision:
        raise LiveApplicationError(
            translated_message="application.live.iva_wallet.errors.decision_reload_diverged",
            context={"target_period": decision.target_period.registry_token},
        )
    return IvaWalletCaptureReport(
        taxpayer_ref=_taxpayer_ref(reloaded.taxpayer_nif),
        target_year=reloaded.target_year,
        target_period=reloaded.target_period,
        observation_path=str(path),
        decision_key=_iva_wallet_decision_key(decision.taxpayer_nif, decision.target_period),
        row_count=len(reloaded.rows),
        total_pending=str(reloaded.total_pending),
        selected_authority=decision.selected_authority,
        selected_amount=str(decision.selected_amount) if decision.selected_amount is not None else None,
        local_recurrence_amount=(
            str(decision.local_recurrence_amount) if decision.local_recurrence_amount is not None else None
        ),
        divergence=decision.divergence,
        blocked=decision.blocked,
        captured_at=reloaded.captured_at,
    )


def _assert_target_period_year(*, target_year: int, target_period: Period) -> None:
    if target_period.filing_year == target_year:
        return
    raise LiveApplicationInputError(
        translated_message="live.errors.target_period_year_mismatch",
        context={"target_year": str(target_year), "target_period_year": str(target_period.filing_year)},
    )


async def capture_iva_compensation_wallet(
    *,
    target_year: int,
    target_period: Period,
    taxpayer_nif: str | None = None,
    output_root: Path | None = None,
) -> IvaWalletCaptureReport:
    """Live-fetch AEAT's IVA compensation wallet and persist the observation.

    This is the operator-approved live path. It will acquire or reuse
    the configured AEAT session, including Cl@ve Móvil approval when
    the auth provider requires it. Under pytest, the shared live-read
    gate still requires the live-test opt-in before remote contact.

    Returns an :class:`IvaWalletCaptureReport`.
    """
    _assert_target_period_year(target_year=target_year, target_period=target_period)
    with _active_profile_storage_span():
        session, settings = await _active_verified_session(
            operation="live-iva-wallet-read",
            target_url=_PRE303_PRESENTATION_SERVICE_URL,
        )
        return await _capture_iva_compensation_wallet_with_session(
            session,
            settings=settings,
            target_year=target_year,
            target_period=target_period,
            taxpayer_nif=taxpayer_nif,
            output_root=output_root,
        )


async def _capture_iva_compensation_wallet_with_session(
    session: _AeatSession,
    *,
    settings: _Settings,
    target_year: int,
    target_period: Period,
    taxpayer_nif: str | None = None,
    output_root: Path | None = None,
    progress_context: dict[str, object] | None = None,
) -> IvaWalletCaptureReport:
    """Capture and persist the wallet with an already-acquired AEAT session."""
    _assert_target_period_year(target_year=target_year, target_period=target_period)
    if progress_context is not None:
        progress_context.update(
            {
                "stage": "fetch_iva_compensation_wallet",
                "target_year": target_year,
                "target_period": target_period.registry_token,
            },
        )
    observation: _IvaCompensationWalletObservation = await _fetch_iva_compensation_wallet(
        session,
        target_year=target_year,
        target_period=target_period,
        taxpayer_nif=taxpayer_nif,
        settings=settings,
    )
    store_root = (
        output_root if output_root is not None else settings.cadrumo_live_state_dir / _LIVE_STATE_IVA_WALLET_DIRNAME
    )
    return persist_and_reconcile_iva_compensation_wallet(observation, output_root=store_root)


async def capture_iva_remote_state(
    *,
    year_from: int,
    year_to: int,
    target_year: int,
    target_period: Period,
    taxpayer_nif: str | None = None,
    output_root: Path | None = None,
) -> IvaRemoteStateAcquisitionReport:
    """Acquire filed-history and wallet/cartera IVA state as one typed read-only operation.

    The operation reports each remote surface independently. A partial failure is
    captured as a redacted outcome and persisted in the acquisition manifest; a
    successful surface still persists and reloads its evidence before being
    reported.

    Returns an :class:`IvaRemoteStateAcquisitionReport` with the acquired
    state, compensation history, and any acquisition issues.
    """
    _assert_target_period_year(target_year=target_year, target_period=target_period)
    with _active_profile_storage_span():
        return await _capture_iva_remote_state_for_active_storage(
            year_from=year_from,
            year_to=year_to,
            target_year=target_year,
            target_period=target_period,
            taxpayer_nif=taxpayer_nif,
            output_root=output_root,
        )


async def _capture_iva_remote_state_for_active_storage(
    *,
    year_from: int,
    year_to: int,
    target_year: int,
    target_period: Period,
    taxpayer_nif: str | None = None,
    output_root: Path | None = None,
) -> IvaRemoteStateAcquisitionReport:
    """Run the combined read while the profile bucket session is active."""
    _assert_target_period_year(target_year=target_year, target_period=target_period)
    settings = _load_settings()
    async with _suppress_live_iva_playwright_cancellation_noise(
        drain_ms=settings.cadrumo_live_iva_cancellation_drain_ms,
        restore_on_exit=False,
    ):
        if year_from > year_to:
            raise LiveApplicationInputError(
                translated_message="live.errors.year_range_invalid",
            )

        _AeatAccessGate(settings).require_live_read()
        store_root = (
            output_root
            if output_root is not None
            else settings.cadrumo_live_state_dir / _LIVE_STATE_IVA_REMOTE_STATE_DIRNAME
        )
        filed_history: IvaCompensationHistoryCaptureReport | None = None
        wallet: IvaWalletCaptureReport | None = None
        auth_result: _AuthenticatedAeatSessionResult | None = None
        auth_error: BaseException | None = None
        filed_error: BaseException | None = None
        wallet_error: BaseException | None = None

        try:
            auth_result = await _ensure_authenticated_aeat_session(
                settings,
                operation="live-iva-remote-state-read",
                target_url=_PRE303_PRESENTATION_SERVICE_URL,
            )
        except (TimeoutError, _CadrumoError, OSError) as exc:
            auth_error = exc

        if auth_result is None:
            report = build_iva_remote_state_acquisition_report(
                output_root=store_root,
                year_from=year_from,
                year_to=year_to,
                target_year=target_year,
                target_period=target_period,
                auth_error=auth_error,
            )
            manifest = persist_iva_remote_state_acquisition_report(report)
            return report.model_copy(update={"acquisition_manifest_id": manifest.acquisition_id})

        session = auth_result.session

        try:
            filed_progress: dict[str, object] = {
                "stage": "not_started",
                "modelo": Modelo.M303.value,
                "year_from": year_from,
                "year_to": year_to,
            }
            filed_history = await _await_live_iva_surface(
                _capture_iva_compensation_history_by_year_with_session(
                    session,
                    settings=settings,
                    year_from=year_from,
                    year_to=year_to,
                    output_root=store_root / _IVA_REMOTE_STATE_FILED_HISTORY_DIRNAME,
                    progress_context=filed_progress,
                ),
                surface=LiveIvaReadSurface.FILED_HISTORY,
                timeout_ms=_filed_history_surface_timeout_ms(
                    settings,
                    year_from=year_from,
                    year_to=year_to,
                ),
                progress_context=filed_progress,
            )
        except (TimeoutError, _CadrumoError, OSError) as exc:
            filed_error = exc

        try:
            wallet_progress: dict[str, object] = {
                "stage": "not_started",
                "target_year": target_year,
                "target_period": target_period.registry_token,
            }
            wallet = await _await_live_iva_surface(
                _capture_iva_compensation_wallet_with_session(
                    session,
                    settings=settings,
                    target_year=target_year,
                    target_period=target_period,
                    taxpayer_nif=taxpayer_nif,
                    output_root=store_root / _IVA_REMOTE_STATE_WALLET_DIRNAME,
                    progress_context=wallet_progress,
                ),
                surface=LiveIvaReadSurface.WALLET_CARTERA,
                timeout_ms=settings.cadrumo_live_iva_surface_timeout_ms,
                progress_context=wallet_progress,
            )
        except (TimeoutError, _CadrumoError, OSError) as exc:
            wallet_error = exc

        report = build_iva_remote_state_acquisition_report(
            output_root=store_root,
            year_from=year_from,
            year_to=year_to,
            target_year=target_year,
            target_period=target_period,
            auth_result=auth_result,
            filed_history=filed_history,
            wallet=wallet,
            filed_history_error=filed_error,
            wallet_error=wallet_error,
        )
        manifest = persist_iva_remote_state_acquisition_report(report)
        return report.model_copy(update={"acquisition_manifest_id": manifest.acquisition_id})


def _filed_history_surface_timeout_ms(settings: _Settings, *, year_from: int, year_to: int) -> int:
    year_count = max(1, year_to - year_from + 1)
    return settings.cadrumo_live_iva_surface_timeout_ms * year_count


async def _capture_iva_compensation_history_by_year_with_session(
    session: _AeatSession,
    *,
    settings: _Settings,
    year_from: int,
    year_to: int,
    output_root: Path,
    progress_context: dict[str, object] | None = None,
) -> IvaCompensationHistoryCaptureReport:
    """Capture filed Modelo 303 history in year chunks and return one aggregate report."""
    yearly_reports: list[IvaCompensationHistoryCaptureReport] = []
    for year in range(year_to, year_from - 1, -1):
        if progress_context is not None:
            progress_context.update(
                {
                    "stage": "capture_year",
                    "modelo": Modelo.M303.value,
                    "ejercicio": year,
                    "year_from": year_from,
                    "year_to": year_to,
                },
            )
        report = await _capture_iva_compensation_history_with_session(
            session,
            settings=settings,
            year_from=year,
            year_to=year,
            output_root=output_root,
            progress_context=progress_context,
        )
        yearly_reports.append(report)
    return _aggregate_iva_compensation_history_reports(
        yearly_reports,
        output_root=output_root,
        year_from=year_from,
        year_to=year_to,
    )


def _aggregate_iva_compensation_history_reports(
    reports: list[IvaCompensationHistoryCaptureReport],
    *,
    output_root: Path,
    year_from: int,
    year_to: int,
) -> IvaCompensationHistoryCaptureReport:
    """Combine per-year filed-history capture reports into one command report."""
    reloaded = list_iva_compensation_history()
    return IvaCompensationHistoryCaptureReport(
        output_root=str(output_root),
        year_from=year_from,
        year_to=year_to,
        captured_count=sum(report.captured_count for report in reports),
        observation_paths=tuple(path for report in reports for path in report.observation_paths),
        artefact_refs=tuple(ref for report in reports for ref in report.artefact_refs),
        casilla_count=sum(report.casilla_count for report in reports),
        calculation_observation_count=sum(report.calculation_observation_count for report in reports),
        calculation_observation_keys=tuple(key for report in reports for key in report.calculation_observation_keys),
        reloaded_history_count=reloaded.row_count,
        reloaded_rows=reloaded.rows,
        failed_declaration_count=sum(report.failed_declaration_count for report in reports),
        failed_declarations=tuple(ref for report in reports for ref in report.failed_declarations),
    )


async def _await_live_iva_surface[T](
    awaitable: Awaitable[T],
    *,
    surface: LiveIvaReadSurface,
    timeout_ms: int,
    progress_context: Mapping[str, object] | None = None,
) -> T:
    """Bound one combined live IVA read surface with a typed timeout."""
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_ms / 1000)
    except TimeoutError as exc:
        raise LiveIvaSurfaceTimeoutError(
            f"live IVA {surface.value} read did not complete within {timeout_ms} ms",
            surface=surface.value,
            timeout_ms=timeout_ms,
            progress_context=progress_context,
        ) from exc


@asynccontextmanager
async def _suppress_live_iva_playwright_cancellation_noise(
    *,
    drain_ms: int = 0,
    restore_on_exit: bool = True,
):
    """Suppress Playwright loop noise caused by bounded live-surface cancellation."""
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()

    def handler(loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
        if _is_playwright_target_closed_context(context):
            return
        if previous_handler is not None:
            previous_handler(loop, context)
            return
        loop.default_exception_handler(context)

    loop.set_exception_handler(handler)
    try:
        yield
    finally:
        if drain_ms > 0:
            await asyncio.sleep(drain_ms / 1000)
        if restore_on_exit:
            loop.set_exception_handler(previous_handler)


def _is_playwright_target_closed_context(context: dict[str, object]) -> bool:
    exception = context.get("exception")
    if exception is None:
        return False
    name = type(exception).__name__
    message = str(exception)
    if name == "TargetClosedError" and "Target page, context or browser has been closed" in message:
        return True
    return bool(name == "Error" and "net::ERR_ABORTED" in message and "frame was detached" in message)


def build_iva_remote_state_acquisition_report(
    *,
    output_root: Path,
    year_from: int,
    year_to: int,
    target_year: int,
    target_period: Period,
    acquisition_manifest_id: str | None = None,
    auth_result: _AuthenticatedAeatSessionResult | None = None,
    auth_error: BaseException | None = None,
    filed_history: IvaCompensationHistoryCaptureReport | None = None,
    wallet: IvaWalletCaptureReport | None = None,
    filed_history_error: BaseException | None = None,
    wallet_error: BaseException | None = None,
) -> IvaRemoteStateAcquisitionReport:
    """Build the redacted combined :class:`IvaRemoteStateAcquisitionReport` from surface results."""
    auth = _auth_outcome(auth_result=auth_result, error=auth_error)
    outcomes = (
        _surface_outcome(
            LiveIvaReadSurface.FILED_HISTORY,
            report=filed_history,
            error=filed_history_error,
            auth=auth,
        ),
        _surface_outcome(
            LiveIvaReadSurface.WALLET_CARTERA,
            report=wallet,
            error=wallet_error,
            auth=auth,
        ),
    )
    return IvaRemoteStateAcquisitionReport(
        acquisition_manifest_id=acquisition_manifest_id,
        output_root=str(output_root),
        year_from=year_from,
        year_to=year_to,
        target_year=target_year,
        target_period=target_period,
        auth=auth,
        filed_history=filed_history,
        wallet=wallet,
        outcomes=outcomes,
    )


def persist_iva_remote_state_acquisition_report(
    report: IvaRemoteStateAcquisitionReport,
    *,
    captured_at: datetime | None = None,
    repository: IvaRemoteStateAcquisitionManifestRepository | None = None,
) -> IvaRemoteStateAcquisitionManifest:
    """Persist a redacted encrypted manifest for a live IVA acquisition report.

    Returns the persisted :class:`IvaRemoteStateAcquisitionManifest` with
    the acquisition id and redacted summary fields.
    """
    resolved_captured_at = captured_at if captured_at is not None else now()
    manifest = _iva_remote_state_acquisition_manifest(report, captured_at=resolved_captured_at)
    repo = repository if repository is not None else IvaRemoteStateAcquisitionManifestRepository()
    repo.save(manifest)
    return manifest


def load_iva_remote_state_acquisition_manifest(
    acquisition_id: str,
    *,
    repository: IvaRemoteStateAcquisitionManifestRepository | None = None,
) -> IvaRemoteStateAcquisitionManifest | None:
    """Load one encrypted live IVA acquisition manifest by id.

    Returns:
        :class:`IvaRemoteStateAcquisitionManifest` | None: The loaded manifest, or None.
    """
    repo = repository if repository is not None else IvaRemoteStateAcquisitionManifestRepository()
    return repo.load(acquisition_id)


def list_iva_remote_state_acquisition_manifests(
    *,
    repository: IvaRemoteStateAcquisitionManifestRepository | None = None,
) -> tuple[IvaRemoteStateAcquisitionManifest, ...]:
    """List encrypted live IVA acquisition manifests for the active profile.

    Returns a tuple of :class:`IvaRemoteStateAcquisitionManifest` records.
    """
    repo = repository if repository is not None else IvaRemoteStateAcquisitionManifestRepository()
    return tuple(sorted(repo.iter_records(), key=lambda item: item.captured_at, reverse=True))


def _iva_remote_state_acquisition_manifest(
    report: IvaRemoteStateAcquisitionReport,
    *,
    captured_at: datetime,
) -> IvaRemoteStateAcquisitionManifest:
    surfaces = tuple(_iva_remote_state_surface_manifest(report, outcome) for outcome in report.outcomes)
    manifest_seed = "|".join(
        (
            str(report.year_from),
            str(report.year_to),
            str(report.target_year),
            report.target_period.registry_token,
            captured_at.isoformat(),
            report.auth.model_dump_json(),
            *(surface.model_dump_json() for surface in surfaces),
        ),
    )
    digest = _sha256_hex(manifest_seed.encode("utf-8"))
    timestamp = captured_at.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    acquisition_id = (
        f"live-iva-acquisition:{report.target_year}:{report.target_period.registry_token}:{timestamp}:{digest}"
    )
    return IvaRemoteStateAcquisitionManifest(
        acquisition_id=acquisition_id,
        captured_at=captured_at,
        year_from=report.year_from,
        year_to=report.year_to,
        target_year=report.target_year,
        target_period=report.target_period,
        auth=report.auth,
        filed_history_succeeded=report.filed_history_succeeded,
        wallet_succeeded=report.wallet_succeeded,
        surfaces=surfaces,
    )


def _iva_remote_state_surface_manifest(
    report: IvaRemoteStateAcquisitionReport,
    outcome: LiveIvaReadOutcome,
) -> IvaRemoteStateAcquisitionSurfaceManifest:
    if outcome.surface is LiveIvaReadSurface.FILED_HISTORY:
        filed = report.filed_history
        return IvaRemoteStateAcquisitionSurfaceManifest(
            surface=outcome.surface,
            status=outcome.status,
            outcome_mode=outcome.outcome_mode,
            failure_mode=outcome.failure_mode,
            failure_type=outcome.failure_type,
            failure_context=outcome.failure_context,
            captured_count=outcome.captured_count,
            calculation_observation_count=outcome.calculation_observation_count,
            reloaded_history_count=filed.reloaded_history_count if filed is not None else None,
        )
    wallet = report.wallet
    return IvaRemoteStateAcquisitionSurfaceManifest(
        surface=outcome.surface,
        status=outcome.status,
        outcome_mode=outcome.outcome_mode,
        failure_mode=outcome.failure_mode,
        failure_type=outcome.failure_type,
        failure_context=outcome.failure_context,
        captured_count=outcome.captured_count,
        calculation_observation_count=outcome.calculation_observation_count,
        wallet_row_count=wallet.row_count if wallet is not None else None,
        decision_ref=_evidence_ref(wallet.decision_key) if wallet is not None else None,
        selected_authority=wallet.selected_authority if wallet is not None else None,
        divergence=wallet.divergence if wallet is not None else None,
        blocked=wallet.blocked if wallet is not None else None,
    )


__all__ = [
    "IvaRemoteStateAcquisitionManifestRepository",
    "build_iva_remote_state_acquisition_report",
    "capture_iva_compensation_history",
    "capture_iva_compensation_wallet",
    "capture_iva_remote_state",
    "list_iva_compensation_history",
    "list_iva_remote_state_acquisition_manifests",
    "load_iva_remote_state",
    "load_iva_remote_state_acquisition_manifest",
    "persist_and_reconcile_iva_compensation_wallet",
    "persist_iva_remote_state_acquisition_report",
]
