"""Modelo declaration export: write a verified-complete or filed calculation revision to a local AEAT-compatible file.

``export_modelo_revision`` accepts a :class:`CalculationRevision` id, builds
and approves a :class:`ModeloDraft` from the revision's captured inputs, then writes
a fichero-BOE-formatted artefact to the operator-supplied output path. A
``MODELO_EXPORTED`` event is appended to the :class:`BucketEventHistoryRepository`.

The service is local-only: it never contacts AEAT and never invokes
``require_live_read``. Export is fundamentally an offline operation
that produces a file the operator presents through sede.agenciatributaria.gob.es
themselves.

The CLI verb ``aeat app modelo export`` is a thin delegate over this
service.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...core.hashing import sha256_hex
from ...core.identity import BucketId
from ...core.logging import get_logger
from ...core.time import now as _utc_now
from ...domain import filing as filing_domain
from ...domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.deadlines import TaxpayerProfile
from ...domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from ...domain.modelos import (
    ModeloRecordCatalogueRepository,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepository,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ...domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
)
from ...domain.modelos._errors import ModeloError, ModeloExportError
from ...domain.modelos._ids import CalculationRevisionId, WorkUnitId
from ...domain.modelos._protocols import CalculationRevisionCatalogueRepositoryProtocol
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.modelos._work_unit import WorkUnit
from ...domain.period import (
    PeriodValidationError,
    period_end_date,
    period_start_date,
)
from ..calculations import (
    CalculationObservationRepository,
    CrossPeriodExpectedMemberSet,
    IvaWalletDecisionRepository,
)
from ..filing import (
    ModeloDraft,
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    export_draft,
    filing_profile_from_taxpayer,
)
from . import _iva_wallet_gate
from ._action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    WorkUnitNotFoundError,
)
from ._revision_persistence import emit_bucket_event as _emit_bucket_event
from ._verification_actions import _cross_period_expected_member_sets_from_profile, _require_cross_period_clean_state

#: AEAT-assigned program-identifier code stamped into the optional
#: ``program_version`` export header. AEAT requires a 4-character
#: software code on the fichero-BOE envelope; this is the single
#: sourced value the export path emits. It is intentionally distinct
#: from the package ``__version__`` — AEAT program codes are assigned
#: per submission tool, not per release.
_PROGRAM_VERSION_CODE = "A001"

#: Plain (non-amendment) declaration type. AEAT fichero-BOE layouts
#: encode an ordinary autoliquidación as type ``"I"``; complementarias
#: and sustitutivas carry their own marker headers alongside.
_DECLARATION_TYPE_ORDINARY = "I"

#: Canonical user-profile fact paths for the operator's legal name.
_PROFILE_SURNAMES_PATH = "identity.surnames"
_PROFILE_NAME_PATH = "identity.name"
_LOGGER = get_logger(__name__)
_require_persisted_iva_compensation_decision_matches_revision = (
    _iva_wallet_gate.require_persisted_iva_compensation_decision_matches_revision
)


class ModeloIvaWalletDecisionProvenance(BaseModel):
    """Redacted audit join for the Modelo 303 IVA wallet authority decision.

    This intentionally excludes taxpayer identifiers, wallet amounts, and local
    recurrence amounts. The fingerprint lets audits join back to encrypted
    secure-object storage without copying live fiscal values into export events
    or result payloads.
    """

    model_config = _STRICT_FROZEN

    decision_ref: str = Field(min_length=71, max_length=71)
    selected_authority: str = Field(min_length=1, max_length=64)
    divergence: str = Field(min_length=1, max_length=64)
    target_year: int = Field(ge=2000, le=2099)
    target_period: Period
    authority_source_kinds: tuple[str, ...] = Field(default_factory=tuple)
    authority_source_refs: tuple[str, ...] = Field(default_factory=tuple)


class ModeloExportCrossBucketRefusedError(ModeloError):
    """Raised when the addressed revision's parent work unit belongs to a bucket other than the active profile bucket.

    Bucket events must scope to the active bucket; allowing the service
    to emit into a foreign bucket would let any caller pollute another
    operator's history.
    """


class ModeloExportNoActiveBucketError(ModeloError):
    """Raised when no active profile bucket is configured.

    Export needs an active bucket because the resulting MODELO_EXPORTED
    event is scoped to a bucket id and the work-unit lookup is
    bucket-bound.
    """


class ModeloExportEvidenceMissingError(ModeloExportError):
    """Raised when a ledger-derived revision lacks exportable evidence."""


class ModeloExportOutputPathError(ModeloExportError):
    """Raised when the operator-supplied ``--output`` path cannot receive the artefact.

    Validated up front, before any fichero-BOE bytes are written, so an
    unusable destination (empty path, an existing directory, a missing or
    unwritable parent directory) is refused with a typed, operator-facing
    message instead of surfacing a raw ``OSError`` traceback from the
    atomic-rename write — and crucially before any cleartext financial
    bytes touch disk.
    """


class ModeloExportCommand(BaseModel):
    """Strict input contract for ``export_modelo_revision``.

    Attributes:
        calculation_revision_id: SHA-256 hex id of the calculation
            revision to export. Must be in ``VERIFICADO_COMPLETO`` or
            ``FILED`` state.
        output_path: Absolute or working-directory-relative path to
            write the fichero-BOE artefact. Parent directories are
            created if missing.
        actor: Operator identifier captured into the
            ``MODELO_EXPORTED`` event payload and used as the draft
            ``approved_by`` field for the transient export draft.
    """

    model_config = _STRICT_FROZEN

    calculation_revision_id: CalculationRevisionId
    output_path: Path
    actor: str = Field(min_length=1, max_length=128)


class ModeloExportResult(BaseModel):
    """Receipt produced by ``export_modelo_revision``.

    Composes the lower-level
    :class:`aeat.application.filing.DeclaracionExportResult` (already a
    byte-level receipt of the written file) with the work-unit-level
    identity the operator addresses.

    Attributes:
        calculation_revision_id: The exported revision id.
        work_unit_id: The parent work unit's id.
        bucket_id: The bucket the work unit lives in (always equal to
            the active profile bucket at export time).
        modelo: AEAT modelo identifier.
        filing_year: AEAT filing year.
        period: Filing period as a typed :class:`~aeat.core.Period` value.
        output_path: Absolute path the file was written to.
        byte_size: Size of the written file in bytes.
        file_sha256: Hex-encoded SHA-256 of the written bytes.
        format: Wire format string (currently always ``"fichero-boe"``).
        exported_at: UTC timestamp of the write.
        actor: Operator identifier captured into the event.
        bucket_event_id: Id of the ``MODELO_EXPORTED`` event appended
            to the catalogue.
        casilla_provenance: Regulatory grounding for casillas covered
            by the exported fichero-BOE layout.
    """

    model_config = _STRICT_FROZEN

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    bucket_id: BucketId
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=1990, le=2200)
    period: Period
    output_path: Path
    byte_size: int = Field(ge=0)
    file_sha256: str = Field(min_length=64, max_length=64)
    format: str = Field(min_length=1)
    exported_at: datetime
    actor: str = Field(min_length=1, max_length=128)
    bucket_event_id: str = Field(min_length=1, max_length=128)
    casilla_provenance: tuple[filing_domain.ModeloCasillaProvenance, ...] = Field(default_factory=tuple)
    iva_wallet_decision_provenance: ModeloIvaWalletDecisionProvenance | None = None


def _sha256_ref(value: str) -> str:
    return f"sha256:{sha256_hex(value.encode('utf-8'))}"


def _validate_output_path(output_path: Path) -> None:
    """Refuse an unusable ``--output`` destination before writing any bytes.

    A clean typed refusal here is the only safe place to reject a bad
    destination: once the atomic-rename write has run, real fichero-BOE
    financial bytes already exist in the sibling ``.tmp`` file, and a
    late ``OSError`` at ``Path.replace`` would both surface a raw
    traceback and (without the cleanup guard) strand those cleartext
    bytes on disk.

    Raises:
        ModeloExportOutputPathError: When the path is empty, names an
            existing directory, or its parent directory is missing or
            not a directory.
    """
    raw = str(output_path).strip()
    if not raw or raw == ".":
        raise ModeloExportOutputPathError(
            translated_message="application.modelo.errors.export_output_path_invalid",
            context={"output_path": raw or "(empty)", "reason": "path is empty"},
        )
    if output_path.is_dir():
        raise ModeloExportOutputPathError(
            translated_message="application.modelo.errors.export_output_path_invalid",
            context={"output_path": str(output_path), "reason": "path is an existing directory"},
        )
    parent = output_path.parent
    if not parent.exists():
        raise ModeloExportOutputPathError(
            translated_message="application.modelo.errors.export_output_path_invalid",
            context={"output_path": str(output_path), "reason": "parent directory does not exist"},
        )
    if not parent.is_dir():
        raise ModeloExportOutputPathError(
            translated_message="application.modelo.errors.export_output_path_invalid",
            context={"output_path": str(output_path), "reason": "parent path is not a directory"},
        )


def _discard_tmp_output_after_failure(tmp_output: Path, *, stage: str) -> None:
    """Best-effort cleanup that never masks the original export failure."""
    if not tmp_output.exists():
        return
    try:
        tmp_output.unlink()
    except OSError as exc:
        _LOGGER.debug(
            "modelo export temporary output cleanup failed stage=%s error_type=%s",
            stage,
            type(exc).__name__,
            exc_info=True,
        )


def _iva_wallet_decision_export_provenance(
    decision: IvaCompensationReconciliationDecision | None,
) -> ModeloIvaWalletDecisionProvenance | None:
    if decision is None:
        return None
    return ModeloIvaWalletDecisionProvenance(
        decision_ref=_sha256_ref(decision.model_dump_json()),
        selected_authority=str(decision.selected_authority),
        divergence=str(decision.divergence),
        target_year=decision.target_year,
        target_period=decision.target_period,
        authority_source_kinds=tuple(str(source.source_kind) for source in decision.authority_sources),
        authority_source_refs=tuple(_sha256_ref(source.source_locator) for source in decision.authority_sources),
    )


def _raise_if_ledger_export_evidence_missing(revision: CalculationRevision) -> None:
    """Refuse ledger-derived exports that lack bundled evidence or a reference."""
    if not revision.source_transaction_ids:
        return
    if revision.ledger_filing_evidence is not None:
        return
    if revision.ledger_filing_snapshot is not None:
        return
    raise ModeloExportEvidenceMissingError(
        "ledger-derived export requires ledger_filing_evidence or ledger_filing_snapshot",
        translated_message="application.modelo.errors.export_ledger_evidence_missing",
        context={"calculation_revision_id": revision.calculation_revision_id},
    )


def _load_revision_for_export(
    calculation_revision_id: str,
    *,
    repo: CalculationRevisionCatalogueRepositoryProtocol,
) -> CalculationRevision:
    revisions = repo.load()
    revision = revisions.get(calculation_revision_id)
    if revision is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    if revision.state not in {
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
    }:
        raise CalculationRevisionStateError(
            translated_message="application.modelo.errors.export_revision_state_refused",
            context={"calculation_revision_id": calculation_revision_id, "state": revision.state.value},
        )
    return revision


def _operator_name_facts(bucket_id: str) -> tuple[str, str]:
    """Return ``(surnames, name)`` from the active bucket's persisted profile.

    The operator's legal name is not carried on the deadline-engine
    :class:`TaxpayerProfile` (which holds only ``tax_id``); it lives in
    the schema-driven user-profile fact catalogue under the canonical
    ``identity.surnames`` / ``identity.name`` paths. Export needs both
    because every modelo fichero-BOE envelope declares ``surnames`` and
    ``name`` as required header fields.

    Args:
        bucket_id: The active profile bucket id whose persisted profile
            facts are read for the operator name.

    Returns:
        A ``(surnames, name)`` tuple of non-blank strings.

    Raises:
        ModeloExportError: When the active bucket has no persisted
            profile, or the profile omits either name fact. The export
            cannot fabricate a placeholder name — the operator must
            populate the profile first.
    """
    from ...domain.user_profile import ProfileNotFoundError
    from ..user_profile import UserProfileLifecycleRepository
    from ..user_profile._projections import record_to_path_values

    try:
        record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
    except ProfileNotFoundError as exc:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_operator_profile_missing",
        ) from exc
    facts = record_to_path_values(record)
    surnames = (facts.get(_PROFILE_SURNAMES_PATH) or "").strip()
    name = (facts.get(_PROFILE_NAME_PATH) or "").strip()
    missing = [path for path, value in ((_PROFILE_SURNAMES_PATH, surnames), (_PROFILE_NAME_PATH, name)) if not value]
    if missing:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_operator_name_missing",
            context={"missing": missing},
        )
    return surnames, name


def _ddmmaaaa(value: date) -> str:
    """Render a date as the AEAT ``ddmmaaaa`` fixed-width header token."""
    return f"{value.day:02d}{value.month:02d}{value.year:04d}"


def _compose_export_headers(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    period: Period,
) -> dict[str, str]:
    """Compose the full fichero-BOE export header dict for a revision.

    Supplies every header key the modelo export layouts may declare as
    required (``declaration_type``, ``surnames``, ``name``,
    ``fecha_inicio_periodo``, ``fecha_fin_periodo``) plus the optional
    keys export can source cleanly (``tax_id``, ``presenter_nif``,
    ``program_version``, ``devengo_start_date``, and the complementaria
    triple when the revision is an amendment).

    ``_header_field_value`` only raises when a key is both declared
    ``required`` by the layout and missing, so over-supplying optional
    keys is safe — the renderer ignores headers a layout never reads.
    """
    surnames, name = _operator_name_facts(work_unit.bucket_id)
    try:
        period_start = (
            period.start_date
            if period.has_date_span()
            else period_start_date(
                period.filing_year,
                period.registry_token,
            )
        )
        period_end = (
            period.end_date
            if period.has_date_span()
            else period_end_date(
                period.filing_year,
                period.registry_token,
            )
        )
    except PeriodValidationError as exc:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_period_unmappable",
            context={"work_unit_id": work_unit.work_unit_id, "period": period.registry_token},
        ) from exc
    tax_id = str(workflow_profile.tax_id)

    # A complementaria / sustitutiva still files as declaration type
    # "I" in the fichero-BOE envelope; the amendment is signalled by
    # the dedicated ``complementaria`` marker header, not by a distinct
    # declaration_type code.
    headers: dict[str, str] = {
        "declaration_type": _DECLARATION_TYPE_ORDINARY,
        "surnames": surnames,
        "name": name,
        "fecha_inicio_periodo": _ddmmaaaa(period_start),
        "fecha_fin_periodo": _ddmmaaaa(period_end),
        "devengo_start_date": _ddmmaaaa(period_start),
        "tax_id": tax_id,
        "presenter_nif": tax_id,
        "program_version": _PROGRAM_VERSION_CODE,
    }

    if revision.amendment_kind is not None:
        headers["complementaria"] = (
            "true" if revision.amendment_kind is CalculationRevisionAmendmentKind.COMPLEMENTARIA else "false"
        )
        headers["complementaria_page"] = headers["complementaria"]
        if revision.amends_filing_record_id is not None:
            headers["justificante_anterior"] = revision.amends_filing_record_id
            headers["previous_justificante"] = revision.amends_filing_record_id

    return headers


def _resolve_work_unit_period(work_unit: WorkUnit) -> Period:
    """Return the typed :class:`~aeat.core.Period` carried by the work unit."""
    if work_unit.period.filing_year != work_unit.filing_year:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_period_unmappable",
            context={"work_unit_id": work_unit.work_unit_id, "period": work_unit.period.registry_token},
        )
    return work_unit.period


def _approve_export_draft(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    actor: str,
    approved_at: datetime,
) -> tuple[Period, ModeloDraft]:
    period = _resolve_work_unit_period(work_unit)
    schema_provider = build_runtime_schema_provider(
        filing_year=period.filing_year,
        period=period,
        modelos=(work_unit.modelo,),
    )
    inputs: filing_domain.ModeloInputs = {
        **dict(revision.inputs_snapshot),
        **dict(revision.binding_overrides),
    }
    try:
        draft = build_draft(
            modelo=work_unit.modelo,
            period=period,
            profile=filing_profile_from_taxpayer(workflow_profile),
            inputs=inputs,
            schema_provider=schema_provider,
        )
        approved = approve_draft(
            draft,
            bucket_id=work_unit.bucket_id,
            approved_by=actor,
            schema_provider=schema_provider,
            approved_at=approved_at,
        )
    except filing_domain.FilingExportError as exc:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_approval_failed",
            context={"calculation_revision_id": revision.calculation_revision_id},
        ) from exc
    return period, approved


def export_modelo_revision(
    command: ModeloExportCommand,
    *,
    workflow_profile: TaxpayerProfile,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    calculation_observation_repository: CalculationObservationRepository | None = None,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    clock: datetime | None = None,
) -> ModeloExportResult:
    """Export a verified-complete or filed calculation revision to disk.

    ``workflow_profile`` is the :class:`TaxpayerProfile` used to compose the
    filing draft headers.

    Local-only: never contacts AEAT. Re-builds the filing draft from
    the revision's captured ``inputs_snapshot`` and
    ``binding_overrides`` so the exported file reflects the same legal
    casilla map that would be filed.

    Emits ``MODELO_EXPORTED`` into the bucket-event-history catalogue
    with the calculation revision id, work unit id, output path,
    byte size, and file digest captured in the payload.

    Returns:
        :class:`ModeloExportResult`: The export result.
    """
    from ...core import resolve_active_bucket_id

    active_bucket_id = resolve_active_bucket_id()
    if active_bucket_id is None:
        raise ModeloExportNoActiveBucketError(
            translated_message="application.modelo.errors.export_no_active_bucket",
        )

    # Validate the destination before touching the catalogue or writing any
    # bytes: an unusable --output (empty, existing directory, missing parent)
    # is a clean typed refusal here, never a raw OSError traceback at the
    # late atomic-rename — and never after cleartext financial bytes exist.
    _validate_output_path(command.output_path)

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    obs_repo = calculation_observation_repository or CalculationObservationRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    revision = _load_revision_for_export(command.calculation_revision_id, repo=cr_repo)
    _raise_if_ledger_export_evidence_missing(revision)
    work_unit = wu_repo.load().get(revision.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": revision.work_unit_id},
        )
    if work_unit.bucket_id != active_bucket_id:
        raise ModeloExportCrossBucketRefusedError(
            translated_message="application.modelo.errors.export_cross_bucket_refused",
            context={"work_unit_id": work_unit.work_unit_id},
        )
    iva_wallet_decision = _require_persisted_iva_compensation_decision_matches_revision(
        work_unit,
        revision,
        repository=iva_compensation_decision_repository,
    )
    _require_cross_period_clean_state(
        work_unit,
        observation_repository=obs_repo,
        filing_repository=fr_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        iva_compensation_decision=iva_wallet_decision,
        expected_member_sets=_cross_period_expected_member_sets_from_profile(
            workflow_profile,
            cross_period_expected_member_sets,
        ),
        taxpayer_tax_id=workflow_profile.tax_id,
        activity_start_date=workflow_profile.activity_start_date,
    )
    iva_wallet_provenance = _iva_wallet_decision_export_provenance(iva_wallet_decision)

    now = clock or _utc_now()
    export_period, approved = _approve_export_draft(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        actor=command.actor,
        approved_at=now,
    )

    # Atomic-rename: write the fichero-BOE artefact to a sibling .tmp
    # path, append the MODELO_EXPORTED event, and only rename into the
    # operator-visible output path after the event commits. A crash
    # between the file write and the event persistence leaves only the
    # .tmp file, which carries no provenance and is safe to discard.
    headers = _compose_export_headers(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        period=export_period,
    )
    tmp_output = command.output_path.with_name(command.output_path.name + ".tmp")
    try:
        receipt = export_draft(approved, output_path=tmp_output, headers=headers)
    except filing_domain.FilingExportError as exc:
        _discard_tmp_output_after_failure(tmp_output, stage="draft-write")
        # Surface the underlying FilingExportError cause in the typed context
        # (cli-notices-are-the-only-diagnostic-channel: structured provenance
        # rides on context). The generic write-failed message otherwise masks
        # structural causes the operator must act on — most importantly a modelo
        # whose registry snapshot declares no export layout (e.g. Modelo 202 has
        # no Diseño de Registros authored, so a verified-complete revision cannot
        # be written to fichero-BOE), which reads as a misleading disk/IO failure.
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_write_failed",
            context={
                "calculation_revision_id": command.calculation_revision_id,
                "cause": str(exc),
            },
        ) from exc

    # Route through the shared ``_emit_bucket_event`` helper every
    # other modelo service uses rather than re-implementing the
    # derive / append / save sequence inline. The helper performs a
    # single-catalogue ``save_many`` write (via
    # ``BucketEventHistoryRepository.save``), which is exactly what
    # export needs — there is no second persisted record to bundle,
    # so the multi-write co-transactional pattern does not apply here.
    # The atomic-rename ordering is preserved: the event commits inside
    # the helper before ``tmp_output.replace`` runs, and a failure in
    # the helper unwinds the .tmp file before propagating.
    event_payload = {
        "calculation_revision_id": command.calculation_revision_id,
        "work_unit_id": work_unit.work_unit_id,
        "output_path": str(command.output_path),
        "byte_size": str(receipt.byte_size),
        "file_sha256": receipt.file_sha256,
        "format": receipt.format.value,
        "modelo": work_unit.modelo,
        "filing_year": str(work_unit.filing_year),
        "period": work_unit.period.registry_token,
    }
    if iva_wallet_provenance is not None:
        event_payload.update(
            {
                "iva_wallet_decision_ref": iva_wallet_provenance.decision_ref,
                "iva_wallet_selected_authority": iva_wallet_provenance.selected_authority,
                "iva_wallet_divergence": iva_wallet_provenance.divergence,
                "iva_wallet_target_year": str(iva_wallet_provenance.target_year),
                "iva_wallet_target_period": iva_wallet_provenance.target_period.registry_token,
                "iva_wallet_authority_source_kinds": ",".join(iva_wallet_provenance.authority_source_kinds),
                "iva_wallet_authority_source_refs": ",".join(iva_wallet_provenance.authority_source_refs),
            },
        )
    try:
        event = _emit_bucket_event(
            repository=bv_repo,
            bucket_id=work_unit.bucket_id,
            event_type=BucketEventType.MODELO_EXPORTED,
            occurred_at=now,
            actor=command.actor,
            object_type=BucketEventObjectType.CALCULATION_REVISION,
            object_id=command.calculation_revision_id,
            payload=event_payload,
        )
    except Exception:
        _discard_tmp_output_after_failure(tmp_output, stage="bucket-event")
        raise

    # Defence in depth: even though _validate_output_path refused an
    # existing-directory / unwritable destination up front, a concurrent
    # change to the destination (a TOCTOU race) can still make this atomic
    # rename fail with an OSError. Sensitive fichero-BOE bytes already exist
    # in tmp_output at this point, so any failure here MUST remove them
    # (sensitive-financial-data-secure-storage) and surface a typed refusal
    # rather than a raw traceback that strands cleartext financial data.
    try:
        tmp_output.replace(command.output_path)
    except OSError as exc:
        _discard_tmp_output_after_failure(tmp_output, stage="atomic-rename")
        raise ModeloExportOutputPathError(
            translated_message="application.modelo.errors.export_output_path_invalid",
            context={"output_path": str(command.output_path), "reason": str(exc)},
        ) from exc

    return ModeloExportResult(
        calculation_revision_id=command.calculation_revision_id,
        work_unit_id=work_unit.work_unit_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=export_period,
        output_path=command.output_path,
        byte_size=receipt.byte_size,
        file_sha256=receipt.file_sha256,
        format=receipt.format.value,
        exported_at=now,
        actor=command.actor,
        bucket_event_id=event.event_id,
        casilla_provenance=receipt.casilla_provenance,
        iva_wallet_decision_provenance=iva_wallet_provenance,
    )


__all__ = [
    "ModeloExportCommand",
    "ModeloExportCrossBucketRefusedError",
    "ModeloExportEvidenceMissingError",
    "ModeloExportNoActiveBucketError",
    "ModeloExportOutputPathError",
    "ModeloExportResult",
    "ModeloIvaWalletDecisionProvenance",
    "_raise_if_ledger_export_evidence_missing",
    "export_modelo_revision",
]
