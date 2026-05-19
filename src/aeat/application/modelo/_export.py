"""Modelo declaration export: write a verified-complete or filed
calculation revision to a local AEAT-compatible file.

`export_modelo_revision` accepts a calculation revision id, builds and
approves a :class:`aeat.domain.filing.FilingDraft` from the revision's
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

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
from ...domain.deadlines import AutonomoProfile
from ...domain.filing import FilingExportError, FilingExportValidationError
from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos._errors import ModeloError, ModeloExportError
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ..filing import (
    approve_draft,
    build_draft,
    build_runtime_schema_provider,
    filing_profile_from_autonomo,
)
from ._actions import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    WorkUnitNotFoundError,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


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
            revision to export. Must be in ``VERIFIED_COMPLETE`` or
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
    :class:`aeat.application.filing.DeclarationExportResult` (already a
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
        CalculationRevisionState.VERIFIED_COMPLETE,
        CalculationRevisionState.FILED,
        CalculationRevisionState.FILED_SUPERSEDED,
    }:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{revision.state.value!r}; only verified-complete or filed "
            f"revisions can be exported",
        )
    return revision


def export_modelo_revision(
    command: ModeloExportCommand,
    *,
    workflow_profile: AutonomoProfile,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
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
            "no active profile bucket; run `aeat config profile create NAME` before exporting a modelo revision",
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

    now = clock or datetime.now(UTC)
    schema_provider = build_runtime_schema_provider(
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        modelos=(work_unit.modelo,),
    )
    inputs: dict[str, object] = {
        **dict(revision.inputs_snapshot),
        **dict(revision.binding_overrides),
    }

    try:
        draft = build_draft(
            modelo=work_unit.modelo,
            period=work_unit.period,
            profile=filing_profile_from_autonomo(workflow_profile),
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
    except (FilingExportError, FilingExportValidationError) as exc:
        raise ModeloExportError(
            f"could not approve draft for calculation_revision_id="
            f"{command.calculation_revision_id!r}: {exc}",
        ) from exc

    # Atomic-rename: write the fichero-BOE artefact to a sibling .tmp
    # path, append the MODELO_EXPORTED event, and only rename into the
    # operator-visible output path after the event commits. A crash
    # between the file write and the event persistence leaves only the
    # .tmp file, which carries no provenance and is safe to discard.
    headers = {"tax_id": str(workflow_profile.tax_id)}
    tmp_output = command.output_path.with_name(command.output_path.name + ".tmp")
    try:
        receipt = export_draft(approved, output_path=tmp_output, headers=headers)
    except (FilingExportError, FilingExportValidationError) as exc:
        if tmp_output.exists():
            tmp_output.unlink()
        raise ModeloExportError(
            f"could not export calculation_revision_id={command.calculation_revision_id!r} "
            f"to {command.output_path!s}: {exc}",
        ) from exc

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
    event_id = derive_bucket_event_id(
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_EXPORTED,
        occurred_at=now,
        actor=command.actor,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id=command.calculation_revision_id,
        payload=event_payload,
    )
    next_catalogue = append_bucket_event(
        bv_repo.load(),
        BucketEvent(
            event_id=event_id,
            bucket_id=work_unit.bucket_id,
            event_type=BucketEventType.MODELO_EXPORTED,
            occurred_at=now,
            actor=command.actor,
            object_type=BucketEventObjectType.CALCULATION_REVISION,
            object_id=command.calculation_revision_id,
            payload_version=1,
            payload=event_payload,
        ),
    )
    try:
        SecureObjectRepository().save_many((bv_repo.to_secure_object_write(next_catalogue),))
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
        bucket_event_id=event_id,
    )


__all__ = [
    "ModeloExportCommand",
    "ModeloExportCrossBucketRefusedError",
    "ModeloExportNoActiveBucketError",
    "ModeloExportResult",
    "export_modelo_revision",
]
