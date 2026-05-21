"""Modelo declaration export: write a verified-complete or filed
calculation revision to a local AEAT-compatible file.

`export_modelo_revision` accepts a calculation revision id, builds and
approves a :class:`aeat.domain.filing.ModeloDraft` from the revision's
captured inputs, then writes a fichero-BOE-formatted artefact to the
operator-supplied output path via the existing
:func:`aeat.application.filing.export_draft` helper. A
``MODELO_EXPORTED`` event is appended to the bucket-event-history
catalogue.

The service is local-only: it never contacts AEAT and never invokes
``require_live_read``. Export is fundamentally an offline operation
that produces a file the operator presents through sede.agenciatributaria.gob.es
themselves.

The CLI verb ``aeat app modelo export`` (per the app-modelo-shape ADR
canonical tree) is a thin delegate over this service.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ...core.i18n import tr
from ...domain import filing as filing_domain
from ...domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.deadlines import TaxpayerProfile
from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ...domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
)
from ...domain.modelos._errors import ModeloError, ModeloExportError
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.modelos._work_unit import WorkUnit
from ...domain.period import (
    PeriodValidationError,
    parse_canonical_period,
    period_end_date,
    period_start_date,
)
from ..calculations import IvaWalletDecisionRepository
from ..filing import (
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    export_draft,
    filing_profile_from_taxpayer,
)
from ._actions import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    WorkUnitNotFoundError,
    _emit_bucket_event,
    _raise_if_persisted_iva_compensation_decision_blocks_work_unit,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

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


class ModeloExportCrossBucketRefusedError(ModeloError):
    """Raised when the addressed revision's parent work unit belongs to
    a bucket other than the active profile bucket.

    Bucket events must scope to the active bucket; allowing the service
    to emit into a foreign bucket would let any caller pollute another
    operator's history. Locks the safety gate from the
    bucket-event-history ADR.
    """


class ModeloExportNoActiveBucketError(ModeloError):
    """Raised when no active profile bucket is configured.

    Export needs an active bucket because the resulting MODELO_EXPORTED
    event is scoped to a bucket id and the work-unit lookup is
    bucket-bound.
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

    calculation_revision_id: str = Field(min_length=1, max_length=128)
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
        period: Canonical period string (e.g. ``"2026Q1"``).
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

    calculation_revision_id: str = Field(min_length=1, max_length=128)
    work_unit_id: str = Field(min_length=1, max_length=128)
    bucket_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=1990, le=2200)
    period: str = Field(min_length=1, max_length=16)
    output_path: Path
    byte_size: int = Field(ge=0)
    file_sha256: str = Field(min_length=64, max_length=64)
    format: str = Field(min_length=1)
    exported_at: datetime
    actor: str = Field(min_length=1, max_length=128)
    bucket_event_id: str = Field(min_length=1, max_length=128)
    casilla_provenance: tuple[filing_domain.ModeloCasillaProvenance, ...] = Field(default_factory=tuple)


def _load_revision_for_export(
    calculation_revision_id: str,
    *,
    repo: CalculationRevisionCatalogueRepository,
) -> CalculationRevision:
    revisions = repo.load()
    revision = revisions.get(calculation_revision_id)
    if revision is None:
        raise CalculationRevisionNotFoundError(
            f"no calculation revision with id={calculation_revision_id!r}",
        )
    if revision.state not in {
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
    }:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{revision.state.value!r}; only verified-complete or filed "
            f"revisions can be exported",
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
            f"export needs the operator name from the active profile bucket "
            f"{bucket_id!r}, but no profile is persisted; run "
            f"`aeat config profile` to populate identity.surnames and identity.name"
        ) from exc
    facts = record_to_path_values(record)
    surnames = (facts.get(_PROFILE_SURNAMES_PATH) or "").strip()
    name = (facts.get(_PROFILE_NAME_PATH) or "").strip()
    missing = [
        path
        for path, value in ((_PROFILE_SURNAMES_PATH, surnames), (_PROFILE_NAME_PATH, name))
        if not value
    ]
    if missing:
        raise ModeloExportError(
            f"export requires the operator name on the active profile, but "
            f"profile fact(s) {', '.join(missing)} are not set; populate them via "
            f"`aeat config profile` before exporting a modelo declaration"
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
    filing_year: int,
    registry_period: str,
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
    period_start = period_start_date(filing_year, registry_period)
    period_end = period_end_date(filing_year, registry_period)
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


def _resolve_export_period(work_unit: WorkUnit) -> tuple[int, str, str]:
    """Return ``(filing_year, registry_period, canonical_period)`` for export.

    Work units persist either the registry-native period token
    (``"4T"``, ``"0A"``, ``"03"``) or an already-canonical token
    (``"2026Q1"``, ``"2026-03"``, ``"2026A"``). The two downstream
    consumers want different shapes: ``build_runtime_schema_provider``
    resolves the registry snapshot by the registry-native period,
    while ``build_draft`` parses a canonical token. This helper
    normalises whichever shape the work unit carries into both.

    Raises:
        ModeloExportError: When the work unit's period token cannot
            be mapped to a registry period.
    """

    period = work_unit.period
    if len(period) == 2 and period.endswith("T") and period[0].isdigit():
        canonical = f"{work_unit.filing_year}Q{period[0]}"
    elif period == "0A":
        canonical = f"{work_unit.filing_year}A"
    elif len(period) == 2 and period.isdigit():
        canonical = f"{work_unit.filing_year}-{period}"
    else:
        canonical = period
    try:
        filing_year, registry_period = parse_canonical_period(canonical)
    except PeriodValidationError as exc:
        raise ModeloExportError(
            f"work unit {work_unit.work_unit_id!r} carries period {period!r} "
            f"which cannot be mapped to a registry filing period: {exc}",
        ) from exc
    return filing_year, registry_period, canonical


def export_modelo_revision(
    command: ModeloExportCommand,
    *,
    workflow_profile: TaxpayerProfile,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    clock: datetime | None = None,
) -> ModeloExportResult:
    """Export a verified-complete or filed calculation revision to disk.

    Local-only: never contacts AEAT. Re-builds the filing draft from
    the revision's captured ``inputs_snapshot`` and
    ``binding_overrides`` so the exported file reflects the same legal
    casilla map that would be filed.

    Emits ``MODELO_EXPORTED`` into the bucket-event-history catalogue
    with the calculation revision id, work unit id, output path,
    byte size, and file digest captured in the payload.
    """

    from ..workflow._persistence import workflow_state_repository

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    active_bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    if active_bucket_id is None:
        raise ModeloExportNoActiveBucketError(
            tr("application.modelo.errors.export_no_active_bucket"),
        )

    revision = _load_revision_for_export(command.calculation_revision_id, repo=cr_repo)
    work_unit = wu_repo.load().get(revision.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"calculation revision {command.calculation_revision_id!r} references missing "
            f"work_unit_id={revision.work_unit_id!r}",
        )
    if work_unit.bucket_id != active_bucket_id:
        raise ModeloExportCrossBucketRefusedError(
            f"work unit {work_unit.work_unit_id!r} belongs to bucket "
            f"{work_unit.bucket_id!r} but the active profile bucket is "
            f"{active_bucket_id!r}; switch profile before exporting",
        )
    _raise_if_persisted_iva_compensation_decision_blocks_work_unit(
        work_unit,
        repository=iva_compensation_decision_repository,
    )

    now = clock or datetime.now(UTC)
    filing_year, registry_period, canonical_period = _resolve_export_period(work_unit)
    schema_provider = build_runtime_schema_provider(
        filing_year=filing_year,
        period=registry_period,
        modelos=(work_unit.modelo,),
    )
    inputs: filing_domain.ModeloInputs = {
        **dict(revision.inputs_snapshot),
        **dict(revision.binding_overrides),
    }

    try:
        draft = build_draft(
            modelo=work_unit.modelo,
            period=canonical_period,
            profile=filing_profile_from_taxpayer(workflow_profile),
            inputs=inputs,
            schema_provider=schema_provider,
        )
        approved = approve_draft(
            draft,
            bucket_id=work_unit.bucket_id,
            approved_by=command.actor,
            schema_provider=schema_provider,
            approved_at=now,
        )
    except filing_domain.FilingExportError as exc:
        raise ModeloExportError(
            f"could not approve draft for calculation_revision_id="
            f"{command.calculation_revision_id!r}: {exc}",
        ) from exc

    # Atomic-rename: write the fichero-BOE artefact to a sibling .tmp
    # path, append the MODELO_EXPORTED event, and only rename into the
    # operator-visible output path after the event commits. A crash
    # between the file write and the event persistence leaves only the
    # .tmp file, which carries no provenance and is safe to discard.
    headers = _compose_export_headers(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        filing_year=filing_year,
        registry_period=registry_period,
    )
    tmp_output = command.output_path.with_name(command.output_path.name + ".tmp")
    try:
        receipt = export_draft(approved, output_path=tmp_output, headers=headers)
    except filing_domain.FilingExportError as exc:
        if tmp_output.exists():
            tmp_output.unlink()
        raise ModeloExportError(
            f"could not export calculation_revision_id={command.calculation_revision_id!r} "
            f"to {command.output_path!s}: {exc}",
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
        "period": work_unit.period,
    }
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
        if tmp_output.exists():
            tmp_output.unlink()
        raise
    tmp_output.replace(command.output_path)

    return ModeloExportResult(
        calculation_revision_id=command.calculation_revision_id,
        work_unit_id=work_unit.work_unit_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        output_path=command.output_path,
        byte_size=receipt.byte_size,
        file_sha256=receipt.file_sha256,
        format=receipt.format.value,
        exported_at=now,
        actor=command.actor,
        bucket_event_id=event.event_id,
        casilla_provenance=receipt.casilla_provenance,
    )


__all__ = [
    "ModeloExportCommand",
    "ModeloExportCrossBucketRefusedError",
    "ModeloExportNoActiveBucketError",
    "ModeloExportResult",
    "export_modelo_revision",
]
