"""Modelo 145 local communication record creation and read-back.

This module owns the bucket-local record lifecycle for the Modelo 145 payer
communication workflow. It validates operator-provided casilla values against
the active registry revision, persists the local record, renders the official
export layout, and records delivery/completion transitions without creating an
AEAT filing path.

See Also:
    :mod:`~application.modelo`
        Public facade that re-exports these Modelo 145 record DTOs and service
        functions.
    :func:`~application.modelo.build_m145_communication_service_contract`
        Registry-backed ownership contract that refuses filing-like surfaces.
    :class:`~application.modelo.M145CommunicationCreateCommand`
        Strict create-command DTO consumed by
        :func:`~application.modelo.create_m145_communication_record`.
    :class:`~application.modelo.M145CommunicationRecord`
        Persisted bucket-local communication record handled by this module.
    :class:`~application.modelo.M145CommunicationValidationResult`
        Validation result returned before export and on explicit validation.
    :class:`~domain.calculations.registry.ModeloRevision`
        Registry revision whose casillas, legal refs, source refs, and export
        layouts ground every record and rendered payload.
    :class:`~domain.calculations.registry.RegistrySnapshot`
        Snapshot wrapper resolved before create, validate, and export work.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.storage import M145_COMMUNICATION_RECORD_NAMESPACE
from ...core import STRICT_FROZEN_CONFIG, CasillaId, ExportLayoutFormat, validated_casilla_id_map
from ...core.decimal import coerce_decimal_strict
from ...core.errors import resolve_error_message
from ...core.hashing import content_hash_hex, sha256_hex
from ...core.identity import BucketId, IdentityError, validate_spanish_tax_id
from ...core.logging import get_logger
from ...core.money import round_to_cents
from ...core.resources import resources
from ...core.time import now
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepositoryProtocol,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.calculations.registry import (
    CasillaDefinition,
    CasillaFieldKind,
    ExportFieldDefinition,
    ExportRecordDefinition,
    RegistrySnapshot,
    casillas_by_id,
    resolve_export_layout,
    undeclared_casilla_ids,
)
from ...domain.modelos import ModeloError
from ..live import SecureSnapshotRepository
from ._m145_communication import (
    M145_COMMUNICATION_MODELO,
    M145_COMMUNICATION_SERVICE_OWNER,
    build_m145_communication_service_contract,
)
from ._revision_persistence import emit_modelo_bucket_event as _emit_bucket_event

_HEX_64_PATTERN = r"^[0-9a-f]{64}$"
_FOUR_DIGIT_YEAR_PATTERN = re.compile(r"^\d{4}$")
_ISO_DATE_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
_AEAT_DATE_PATTERN = re.compile(r"^(0[1-9]|[12]\d|3[01])(0[1-9]|1[0-2])\d{4}$")
_LINE_ENDINGS: Mapping[str, bytes] = {"none": b"", "lf": b"\n", "crlf": b"\r\n"}
_M145_COMMUNICATION_EVENT_ACTOR = M145_COMMUNICATION_SERVICE_OWNER
_LOGGER = get_logger(__name__)

M145CommunicationRecordId = Annotated[
    str,
    Field(min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
M145CommunicationFieldValue = Annotated[str, Field(max_length=512)]


class M145CommunicationServiceError(ModeloError):
    """Base error for Modelo 145 local communication service failures."""


class M145CommunicationRecordNotFoundError(M145CommunicationServiceError, KeyError):
    """Raised when a Modelo 145 communication record lookup targets no record."""


class M145CommunicationRecordAmbiguousError(M145CommunicationServiceError, KeyError):
    """Raised when a Modelo 145 communication record prefix matches multiple records."""


class M145CommunicationRecordValidationError(M145CommunicationServiceError, ValueError):
    """Raised when a Modelo 145 communication operation is blocked by validation."""


class M145CommunicationRecordExportError(M145CommunicationServiceError, ValueError):
    """Raised when a Modelo 145 communication export cannot be rendered."""


class M145CommunicationRecordTransitionError(M145CommunicationServiceError, ValueError):
    """Raised when a Modelo 145 communication state transition is not allowed."""


class M145CommunicationPeriod(StrEnum):
    """Registry-backed local communication period tokens for Modelo 145."""

    COMMUNICATION = "comunicacion"
    VARIATION = "variacion"


class M145CommunicationRecordState(StrEnum):
    """Creation-state vocabulary for local Modelo 145 communication records."""

    CREATED = "created"
    DELIVERED_TO_PAYER = "delivered_to_payer"
    LOCALLY_COMPLETED = "locally_completed"


class M145CommunicationValidationIssueKind(StrEnum):
    """Closed issue vocabulary for Modelo 145 local communication validation."""

    REVISION_MISMATCH = "revision_mismatch"
    SOURCE_AUTHORITY_MISMATCH = "source_authority_mismatch"
    UNDECLARED_CASILLA = "undeclared_casilla"
    MISSING_REQUIRED = "missing_required"
    INVALID_VALUE = "invalid_value"
    MISSING_SOURCE_AUTHORITY = "missing_source_authority"
    UNSUPPORTED_DATA_TYPE = "unsupported_data_type"


class M145CommunicationValidationIssue(BaseModel):
    """One registry-backed validation issue for a local communication record."""

    model_config = STRICT_FROZEN_CONFIG

    kind: M145CommunicationValidationIssueKind
    casilla_id: CasillaId | None = None
    data_type: str | None = None
    message: str = Field(min_length=1, max_length=512)
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


class M145CommunicationValidationResult(BaseModel):
    """Registry-backed validation result for one local communication record."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: str = "1"
    communication_record_id: M145CommunicationRecordId
    bucket_id: BucketId
    service_owner: str = Field(
        default=M145_COMMUNICATION_SERVICE_OWNER,
        pattern=r"^cadrumo\.application\.modelo$",
    )
    modelo: str = Field(default=M145_COMMUNICATION_MODELO, pattern=r"^145$")
    communication_year: int = Field(ge=2012, le=2099)
    period_token: M145CommunicationPeriod
    revision_id: str = Field(min_length=1)
    valid: bool
    issue_count: int = Field(ge=0)
    issues: tuple[M145CommunicationValidationIssue, ...]
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


class M145CommunicationExportResult(BaseModel):
    """Registry-layout export payload for one local communication record."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: str = "1"
    communication_record_id: M145CommunicationRecordId
    bucket_id: BucketId
    service_owner: str = Field(
        default=M145_COMMUNICATION_SERVICE_OWNER,
        pattern=r"^cadrumo\.application\.modelo$",
    )
    modelo: str = Field(default=M145_COMMUNICATION_MODELO, pattern=r"^145$")
    communication_year: int = Field(ge=2012, le=2099)
    period_token: M145CommunicationPeriod
    revision_id: str = Field(min_length=1)
    export_layout_id: str = Field(min_length=1)
    encoding: str = Field(min_length=1)
    record_count: int = Field(ge=1)
    byte_length: int = Field(ge=1)
    payload_sha256: str = Field(min_length=64, max_length=64, pattern=_HEX_64_PATTERN)
    payload: bytes
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


class M145CommunicationCreateCommand(BaseModel):
    """Operator request to create a local Modelo 145 payer communication record."""

    model_config = STRICT_FROZEN_CONFIG

    communication_year: int = Field(ge=2012, le=2099)
    period_token: M145CommunicationPeriod = M145CommunicationPeriod.COMMUNICATION
    field_values: dict[CasillaId, M145CommunicationFieldValue] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=512)

    @field_validator("field_values", mode="before")
    @classmethod
    def _validate_field_value_keys(cls, value: object) -> object:
        if isinstance(value, Mapping):
            return validated_casilla_id_map(
                dict(value.items()),
                surface="m145 communication field_values",
            )
        return value


class M145CommunicationRecord(BaseModel):
    """Persisted bucket-local Modelo 145 communication record."""

    model_config = STRICT_FROZEN_CONFIG

    communication_record_id: M145CommunicationRecordId
    bucket_id: BucketId
    service_owner: str = Field(
        default=M145_COMMUNICATION_SERVICE_OWNER,
        pattern=r"^cadrumo\.application\.modelo$",
    )
    modelo: str = Field(default=M145_COMMUNICATION_MODELO, pattern=r"^145$")
    communication_year: int = Field(ge=2012, le=2099)
    period_token: M145CommunicationPeriod
    revision_id: str = Field(min_length=1)
    state: M145CommunicationRecordState = M145CommunicationRecordState.CREATED
    field_values: dict[CasillaId, M145CommunicationFieldValue] = Field(min_length=1)
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    created_at: datetime
    delivered_to_payer_at: datetime | None = None
    locally_completed_at: datetime | None = None
    note: str | None = Field(default=None, max_length=512)

    @property
    def snapshot_id(self) -> str:
        return self.communication_record_id

    @model_validator(mode="after")
    def _validate_local_transition_state(self) -> M145CommunicationRecord:
        delivered_at = self.delivered_to_payer_at
        completed_at = self.locally_completed_at
        if delivered_at is not None and delivered_at < self.created_at:
            raise ValueError("delivered_to_payer_at must not precede created_at")
        if completed_at is not None and completed_at < self.created_at:
            raise ValueError("locally_completed_at must not precede created_at")
        if delivered_at is not None and completed_at is not None and completed_at < delivered_at:
            raise ValueError("locally_completed_at must not precede delivered_to_payer_at")
        match self.state:
            case M145CommunicationRecordState.CREATED:
                if delivered_at is not None or completed_at is not None:
                    raise ValueError("created Modelo 145 communication records cannot carry transition timestamps")
            case M145CommunicationRecordState.DELIVERED_TO_PAYER:
                if delivered_at is None:
                    raise ValueError("delivered Modelo 145 communication records require delivered_to_payer_at")
                if completed_at is not None:
                    raise ValueError("delivered Modelo 145 communication records cannot carry locally_completed_at")
            case M145CommunicationRecordState.LOCALLY_COMPLETED:
                if delivered_at is None or completed_at is None:
                    raise ValueError(
                        "locally completed Modelo 145 communication records require delivery and completion timestamps",
                    )
        return self


def _period_value(period_token: M145CommunicationPeriod | str) -> str:
    if isinstance(period_token, M145CommunicationPeriod):
        return period_token.value
    return M145CommunicationPeriod(period_token).value


def derive_m145_communication_record_id(
    *,
    bucket_id: BucketId,
    communication_year: int,
    period_token: M145CommunicationPeriod | str,
    revision_id: str,
    field_values: Mapping[str, str],
) -> M145CommunicationRecordId:
    """Return the content-addressed id for a Modelo 145 communication record."""
    canonical_values = dict(sorted((str(key), str(value)) for key, value in field_values.items()))
    return content_hash_hex(
        {
            "bucket_id": str(bucket_id).strip(),
            "modelo": M145_COMMUNICATION_MODELO,
            "communication_year": communication_year,
            "period_token": _period_value(period_token),
            "revision_id": revision_id,
            "field_values": canonical_values,
        },
    )


def m145_communication_record_object_key(bucket_id: str, communication_record_id: str) -> str:
    return f"m145-communication:{bucket_id}:{communication_record_id}"


def _m145_communication_record_not_found(communication_record_id: str) -> KeyError:
    _LOGGER.warning(
        "m145 communication record lookup missing communication_record_id=%s",
        communication_record_id,
    )
    return M145CommunicationRecordNotFoundError(
        f"Modelo 145 communication record {communication_record_id!r} not found",
        context={"communication_record_id": communication_record_id},
    )


def _m145_communication_record_ambiguous_prefix(
    communication_record_id: str,
    full_ids: tuple[str, ...],
) -> KeyError:
    _LOGGER.warning(
        "m145 communication record lookup ambiguous communication_record_id=%s match_count=%d",
        communication_record_id,
        len(full_ids),
    )
    return M145CommunicationRecordAmbiguousError(
        f"Modelo 145 communication record prefix {communication_record_id!r} is ambiguous; matches {list(full_ids)!r}",
        context={"communication_record_id": communication_record_id, "match_count": len(full_ids)},
    )


def _m145_communication_record_repository(bucket_id: BucketId):
    return SecureSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=M145CommunicationRecord,
        namespace_definition=M145_COMMUNICATION_RECORD_NAMESPACE,
        object_key=m145_communication_record_object_key,
        not_found_factory=_m145_communication_record_not_found,
        ambiguous_prefix_factory=_m145_communication_record_ambiguous_prefix,
        domain_label="m145_communication_record",
    )


def _snapshot_for_command(command: M145CommunicationCreateCommand):
    return _snapshot_for_scope(
        communication_year=command.communication_year,
        period_token=command.period_token,
    )


def _snapshot_for_scope(
    *,
    communication_year: int,
    period_token: M145CommunicationPeriod,
) -> RegistrySnapshot:
    contract = build_m145_communication_service_contract(filing_year=communication_year)

    snapshot = resources().modelos.authority.snapshot(
        M145_COMMUNICATION_MODELO,
        filing_year=communication_year,
        period=period_token.value,
    )
    contract_surfaces = frozenset(contract.surfaces)
    declared_surfaces = frozenset(str(link.surface) for link in snapshot.revision.application_links)
    if declared_surfaces != contract_surfaces:
        got = tuple(sorted(declared_surfaces))
        expected = tuple(sorted(contract_surfaces))
        _LOGGER.error(
            "m145 communication record contract mismatch expected_surfaces=%s declared_surfaces=%s",
            expected,
            got,
        )
        raise M145CommunicationRecordValidationError(
            f"Modelo 145 communication record expected surfaces {expected!r}; got {got!r}",
            context={"expected_surfaces": expected, "declared_surfaces": got},
        )
    return snapshot


def list_m145_communication_records(*, bucket_id: BucketId) -> tuple[M145CommunicationRecord, ...]:
    """Return every local Modelo 145 communication record in one bucket."""
    records = _m145_communication_record_repository(bucket_id).list_snapshots()
    return tuple(sorted(records, key=lambda record: (record.created_at, record.communication_record_id)))


def read_m145_communication_record(
    communication_record_id: str,
    *,
    bucket_id: BucketId,
) -> M145CommunicationRecord:
    """Return one Modelo 145 communication record by id or unambiguous prefix."""
    return _m145_communication_record_repository(bucket_id).resolve(communication_record_id)


def _m145_communication_event_payload(
    record: M145CommunicationRecord,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    payload = {
        "communication_record_id": record.communication_record_id,
        "modelo": record.modelo,
        "communication_year": str(record.communication_year),
        "period": record.period_token.value,
        "revision_id": record.revision_id,
        "state": record.state.value,
    }
    if extra is not None:
        payload.update(extra)
    return payload


def _emit_m145_communication_event(
    record: M145CommunicationRecord,
    *,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None,
    payload: Mapping[str, str] | None = None,
) -> BucketEvent:
    repository = bucket_event_repository or BucketEventHistoryRepository()
    return _emit_bucket_event(
        repository=repository,
        bucket_id=record.bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.COMMUNICATION_RECORD,
        object_id=record.communication_record_id,
        payload=_m145_communication_event_payload(record, payload),
    )


def _issue(
    kind: M145CommunicationValidationIssueKind,
    message: str,
    *,
    casilla: CasillaDefinition | None = None,
    casilla_id: CasillaId | None = None,
    legal_refs: tuple[str, ...] = (),
    source_refs: tuple[str, ...] = (),
) -> M145CommunicationValidationIssue:
    return M145CommunicationValidationIssue(
        kind=kind,
        casilla_id=casilla.id if casilla is not None else casilla_id,
        data_type=casilla.data_type if casilla is not None else None,
        message=message,
        legal_refs=tuple(str(ref) for ref in (casilla.legal_refs if casilla is not None else legal_refs)),
        source_refs=tuple(str(ref) for ref in (casilla.source_refs if casilla is not None else source_refs)),
    )


def _value_shape_issue(casilla: CasillaDefinition, value: str) -> str | None:
    stripped = value.strip()
    if not stripped:
        return "value must not be blank"
    match casilla.data_type:
        case "text":
            return None
        case "nif":
            try:
                validate_spanish_tax_id(stripped)
            except IdentityError as exc:
                return resolve_error_message(exc)
            return None
        case "year":
            if not _FOUR_DIGIT_YEAR_PATTERN.fullmatch(stripped):
                return "value must be a four-digit year"
            return None
        case "date":
            if not (_ISO_DATE_PATTERN.fullmatch(stripped) or _AEAT_DATE_PATTERN.fullmatch(stripped)):
                return "value must be ISO yyyy-mm-dd or AEAT ddmmaaaa"
            return None
        case "integer":
            if not stripped.isdecimal():
                return "value must contain only decimal digits"
            return None
        case "money":
            try:
                coerce_decimal_strict(stripped)
            except (InvalidOperation, ValueError) as exc:
                return f"value is not a valid decimal amount: {type(exc).__name__}"
            return None
        case _:
            return None


def _constraint_issue(casilla: CasillaDefinition, value: str) -> str | None:
    if casilla.constraints is None:
        return None
    text_issue = casilla.constraints.violates_text(value)
    if text_issue is not None:
        return text_issue
    if casilla.data_type not in {"integer", "money"}:
        return None
    try:
        numeric = coerce_decimal_strict(value)
    except (InvalidOperation, ValueError):
        return None
    return casilla.constraints.violates(numeric)


def validate_m145_communication_record(
    communication_record_id: str,
    *,
    bucket_id: BucketId,
) -> M145CommunicationValidationResult:
    """Validate one persisted Modelo 145 communication record against registry authority."""
    record = read_m145_communication_record(communication_record_id, bucket_id=bucket_id)
    snapshot = _snapshot_for_scope(
        communication_year=record.communication_year,
        period_token=record.period_token,
    )
    revision = snapshot.revision
    revision_legal_refs = tuple(sorted(str(ref) for ref in revision.legal_refs))
    revision_source_refs = tuple(sorted(str(ref) for ref in revision.source_refs))
    issues: list[M145CommunicationValidationIssue] = []

    if record.revision_id != revision.id:
        issues.append(
            _issue(
                M145CommunicationValidationIssueKind.REVISION_MISMATCH,
                f"record revision {record.revision_id!r} does not match active registry revision {revision.id!r}",
                legal_refs=revision_legal_refs,
                source_refs=revision_source_refs,
            ),
        )
    authority_refs_match = (
        tuple(sorted(record.legal_refs)) == revision_legal_refs
        and tuple(sorted(record.source_refs)) == revision_source_refs
    )
    if not authority_refs_match:
        issues.append(
            _issue(
                M145CommunicationValidationIssueKind.SOURCE_AUTHORITY_MISMATCH,
                "record authority refs do not match the active registry revision authority refs",
                legal_refs=revision_legal_refs,
                source_refs=revision_source_refs,
            ),
        )

    casillas = casillas_by_id(revision)
    unknown = tuple(sorted(undeclared_casilla_ids(revision, record.field_values)))
    for casilla_id in unknown:
        issues.append(
            _issue(
                M145CommunicationValidationIssueKind.UNDECLARED_CASILLA,
                f"casilla {casilla_id!r} is not declared by registry revision {revision.id!r}",
                casilla_id=casilla_id,
                legal_refs=revision_legal_refs,
                source_refs=revision_source_refs,
            ),
        )

    for casilla in sorted(casillas.values(), key=lambda item: item.id):
        value = record.field_values.get(casilla.id)
        if casilla.required and (value is None or not value.strip()):
            issues.append(
                _issue(
                    M145CommunicationValidationIssueKind.MISSING_REQUIRED,
                    f"required casilla {casilla.id!r} is missing",
                    casilla=casilla,
                ),
            )
        if value is None:
            continue
        if not casilla.legal_refs or not casilla.source_refs:
            issues.append(
                _issue(
                    M145CommunicationValidationIssueKind.MISSING_SOURCE_AUTHORITY,
                    f"casilla {casilla.id!r} lacks registry legal/source authority",
                    casilla=casilla,
                ),
            )
        value_issue = _value_shape_issue(casilla, value)
        if value_issue is not None:
            issues.append(
                _issue(
                    M145CommunicationValidationIssueKind.INVALID_VALUE,
                    f"casilla {casilla.id!r} {value_issue}",
                    casilla=casilla,
                ),
            )
        if value_issue is None and casilla.data_type not in {"date", "integer", "money", "nif", "text", "year"}:
            issues.append(
                _issue(
                    M145CommunicationValidationIssueKind.UNSUPPORTED_DATA_TYPE,
                    f"casilla {casilla.id!r} uses unsupported data_type {casilla.data_type!r}",
                    casilla=casilla,
                ),
            )
        constraint_issue = _constraint_issue(casilla, value.strip())
        if constraint_issue is not None:
            issues.append(
                _issue(
                    M145CommunicationValidationIssueKind.INVALID_VALUE,
                    f"casilla {casilla.id!r} {constraint_issue}",
                    casilla=casilla,
                ),
            )

    result_issues = tuple(issues)
    return M145CommunicationValidationResult(
        communication_record_id=record.communication_record_id,
        bucket_id=record.bucket_id,
        communication_year=record.communication_year,
        period_token=record.period_token,
        revision_id=revision.id,
        valid=not result_issues,
        issue_count=len(result_issues),
        issues=result_issues,
        legal_refs=revision_legal_refs,
        source_refs=revision_source_refs,
    )


def _validation_issue_summary(result: M145CommunicationValidationResult) -> str:
    issue_kinds = tuple(issue.kind.value for issue in result.issues)
    return ", ".join(issue_kinds)


def _export_record_length(record: ExportRecordDefinition) -> int:
    fields_with_offsets = tuple(
        field for field in record.fields if field.offset is not None and field.length is not None
    )
    if not fields_with_offsets:
        raise M145CommunicationRecordExportError(
            f"Modelo 145 export record {record.id!r} declares no fixed-width fields",
            context={"export_record_id": record.id, "reason": "no_fixed_width_fields"},
        )
    return max((field.offset or 0) + (field.length or 0) - 1 for field in fields_with_offsets)


def _pad_character(field: ExportFieldDefinition) -> str:
    match field.padding:
        case "left_zero":
            return "0"
        case "left_space" | "right_space":
            return " "
        case "none":
            return ""
        case _:
            raise M145CommunicationRecordExportError(
                f"Modelo 145 export field {field.id!r} uses unsupported padding {field.padding!r}",
                context={"export_field_id": field.id, "padding": field.padding, "reason": "unsupported_padding"},
            )


def _encode_fixed_width_value(value: str, *, field: ExportFieldDefinition, encoding: str) -> bytes:
    if field.length is None:
        raise M145CommunicationRecordExportError(
            f"Modelo 145 export field {field.id!r} lacks a fixed length",
            context={"export_field_id": field.id, "reason": "missing_length"},
        )
    try:
        raw = value.encode(encoding)
    except UnicodeEncodeError as exc:
        raise M145CommunicationRecordExportError(
            f"Modelo 145 export field {field.id!r} contains characters not encodable as {encoding!r}",
            context={"export_field_id": field.id, "encoding": encoding, "reason": "encoding"},
        ) from exc
    if len(raw) > field.length:
        raise M145CommunicationRecordExportError(
            f"Modelo 145 export field {field.id!r} overflows length {field.length}; "
            f"encoded value needs {len(raw)} bytes",
            context={
                "export_field_id": field.id,
                "length": field.length,
                "encoded_length": len(raw),
                "reason": "overflow",
            },
        )
    pad_character = _pad_character(field)
    if not pad_character:
        if len(raw) != field.length:
            raise M145CommunicationRecordExportError(
                f"Modelo 145 export field {field.id!r} must encode exactly {field.length} bytes; got {len(raw)}",
                context={
                    "export_field_id": field.id,
                    "length": field.length,
                    "encoded_length": len(raw),
                    "reason": "exact_length",
                },
            )
        return raw
    pad = pad_character.encode(encoding)
    padding = pad * (field.length - len(raw))
    match field.justification:
        case "left":
            return raw + padding
        case "right":
            return padding + raw
        case "none":
            if padding:
                raise M145CommunicationRecordExportError(
                    f"Modelo 145 export field {field.id!r} cannot pad with justification='none'",
                    context={"export_field_id": field.id, "reason": "unsupported_justification"},
                )
            return raw
        case _:
            raise M145CommunicationRecordExportError(
                f"Modelo 145 export field {field.id!r} uses unsupported justification {field.justification!r}",
                context={
                    "export_field_id": field.id,
                    "justification": field.justification,
                    "reason": "unsupported_justification",
                },
            )


def _money_export_digits(value: str, *, field: ExportFieldDefinition) -> str:
    if not value.strip():
        return ""
    amount = coerce_decimal_strict(value.strip())
    if amount < 0 and not field.signed:
        raise M145CommunicationRecordExportError(
            f"Modelo 145 export field {field.id!r} cannot encode a negative amount",
            context={"export_field_id": field.id, "reason": "negative_amount"},
        )
    cents = int(round_to_cents(abs(amount)) * Decimal("100"))
    return str(cents)


def _field_export_text(
    field: ExportFieldDefinition,
    *,
    record: M145CommunicationRecord,
) -> str:
    match field.kind:
        case CasillaFieldKind.LITERAL:
            return field.literal or ""
        case CasillaFieldKind.FILLER:
            return ""
        case CasillaFieldKind.CASILLA:
            if field.casilla_id is None:
                raise M145CommunicationRecordExportError(
                    f"Modelo 145 export field {field.id!r} has no casilla id",
                    context={"export_field_id": field.id, "reason": "missing_casilla"},
                )
            value = record.field_values.get(field.casilla_id, "")
            match field.data_type:
                case "money":
                    return _money_export_digits(value, field=field)
                case "integer":
                    return str(int(value.strip())) if value.strip() else ""
                case "text":
                    return value
                case _:
                    raise M145CommunicationRecordExportError(
                        f"Modelo 145 export field {field.id!r} uses unsupported data_type {field.data_type!r}",
                        context={"export_field_id": field.id, "data_type": field.data_type, "reason": "data_type"},
                    )
        case _:
            raise M145CommunicationRecordExportError(
                f"Modelo 145 export field {field.id!r} uses unsupported kind {field.kind!r}",
                context={"export_field_id": field.id, "kind": str(field.kind), "reason": "field_kind"},
            )


def _render_m145_export_record(record_definition: ExportRecordDefinition, record: M145CommunicationRecord) -> bytes:
    encoding = record_definition.encoding
    total_length = _export_record_length(record_definition)
    payload = bytearray(b" " * total_length)
    for field in sorted(
        record_definition.fields,
        key=lambda item: (-1 if item.offset is None else item.offset, item.id),
    ):
        if field.offset is None or field.length is None:
            raise M145CommunicationRecordExportError(
                f"Modelo 145 export field {field.id!r} lacks fixed-width coordinates",
                context={"export_field_id": field.id, "reason": "missing_coordinates"},
            )
        text = _field_export_text(field, record=record)
        encoded = _encode_fixed_width_value(text, field=field, encoding=encoding)
        start = field.offset - 1
        payload[start : start + field.length] = encoded
    return bytes(payload) + _LINE_ENDINGS[record_definition.line_ending]


def export_m145_communication_record(
    communication_record_id: str,
    *,
    bucket_id: BucketId,
    actor: str = _M145_COMMUNICATION_EVENT_ACTOR,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
) -> M145CommunicationExportResult:
    """Render one Modelo 145 communication record through the registry export layout."""
    validation = validate_m145_communication_record(communication_record_id, bucket_id=bucket_id)
    if not validation.valid:
        _LOGGER.warning(
            "m145 communication record export refused communication_record_id=%s issue_count=%d",
            validation.communication_record_id,
            validation.issue_count,
        )
        raise M145CommunicationRecordValidationError(
            "Modelo 145 communication record cannot be exported until validation passes; "
            f"issues: {_validation_issue_summary(validation)}",
            context={
                "communication_record_id": validation.communication_record_id,
                "issue_count": validation.issue_count,
                "issue_kinds": tuple(issue.kind.value for issue in validation.issues),
            },
        )
    record = read_m145_communication_record(communication_record_id, bucket_id=bucket_id)
    snapshot = _snapshot_for_scope(
        communication_year=record.communication_year,
        period_token=record.period_token,
    )
    resolved_layout = resolve_export_layout(snapshot)
    layout = resolved_layout.layout
    if layout.format is not ExportLayoutFormat.FIXED_WIDTH:
        raise M145CommunicationRecordExportError(
            f"Modelo 145 export layout {layout.id!r} uses unsupported format {layout.format!r}",
            context={"export_layout_id": layout.id, "format": layout.format, "reason": "unsupported_format"},
        )
    records = tuple(sorted(layout.records, key=lambda item: item.order))
    if not records:
        raise M145CommunicationRecordExportError(
            f"Modelo 145 export layout {layout.id!r} declares no records",
            context={"export_layout_id": layout.id, "reason": "no_records"},
        )
    encodings = {record_definition.encoding for record_definition in records}
    if len(encodings) != 1:
        raise M145CommunicationRecordExportError(
            f"Modelo 145 export layout {layout.id!r} declares mixed encodings: {sorted(encodings)!r}",
            context={"export_layout_id": layout.id, "encodings": tuple(sorted(encodings)), "reason": "encodings"},
        )
    payload = b"".join(_render_m145_export_record(record_definition, record) for record_definition in records)
    result = M145CommunicationExportResult(
        communication_record_id=record.communication_record_id,
        bucket_id=record.bucket_id,
        communication_year=record.communication_year,
        period_token=record.period_token,
        revision_id=record.revision_id,
        export_layout_id=layout.id,
        encoding=records[0].encoding,
        record_count=len(records),
        byte_length=len(payload),
        payload_sha256=sha256_hex(payload),
        payload=payload,
        legal_refs=tuple(sorted(str(ref) for ref in layout.legal_refs)),
        source_refs=tuple(sorted(str(ref) for ref in layout.source_refs)),
    )
    _emit_m145_communication_event(
        record,
        event_type=BucketEventType.MODELO_145_COMMUNICATION_EXPORTED,
        occurred_at=now(),
        actor=actor,
        bucket_event_repository=bucket_event_repository,
        payload={
            "export_layout_id": result.export_layout_id,
            "payload_sha256": result.payload_sha256,
            "byte_length": str(result.byte_length),
            "record_count": str(result.record_count),
        },
    )
    _LOGGER.info(
        "m145 communication record exported communication_record_id=%s export_layout_id=%s byte_length=%d",
        record.communication_record_id,
        result.export_layout_id,
        result.byte_length,
    )
    return result


def _m145_communication_record_with_updates(
    record: M145CommunicationRecord,
    **updates: object,
) -> M145CommunicationRecord:
    payload = record.model_dump()
    payload.update(updates)
    return M145CommunicationRecord.model_validate(payload)


def mark_m145_communication_record_delivered_to_payer(
    communication_record_id: str,
    *,
    bucket_id: BucketId,
    actor: str = _M145_COMMUNICATION_EVENT_ACTOR,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
) -> M145CommunicationRecord:
    """Mark one valid local communication record as delivered to the payer."""
    repository = _m145_communication_record_repository(bucket_id)
    record = repository.resolve(communication_record_id)
    if record.state in {
        M145CommunicationRecordState.DELIVERED_TO_PAYER,
        M145CommunicationRecordState.LOCALLY_COMPLETED,
    }:
        _LOGGER.debug(
            "m145 communication record delivery reused state communication_record_id=%s state=%s",
            record.communication_record_id,
            record.state.value,
        )
        return record
    validation = validate_m145_communication_record(record.communication_record_id, bucket_id=bucket_id)
    if not validation.valid:
        _LOGGER.warning(
            "m145 communication record delivery refused communication_record_id=%s issue_count=%d",
            record.communication_record_id,
            validation.issue_count,
        )
        raise M145CommunicationRecordValidationError(
            "Modelo 145 communication record cannot be marked delivered to payer until validation passes; "
            f"issues: {_validation_issue_summary(validation)}",
            context={
                "communication_record_id": record.communication_record_id,
                "issue_count": validation.issue_count,
                "issue_kinds": tuple(issue.kind.value for issue in validation.issues),
            },
        )
    transitioned_at = now()
    transitioned = _m145_communication_record_with_updates(
        record,
        state=M145CommunicationRecordState.DELIVERED_TO_PAYER,
        delivered_to_payer_at=transitioned_at,
    )
    repository.save(transitioned)
    _emit_m145_communication_event(
        transitioned,
        event_type=BucketEventType.MODELO_145_COMMUNICATION_DELIVERED_TO_PAYER,
        occurred_at=transitioned_at,
        actor=actor,
        bucket_event_repository=bucket_event_repository,
    )
    _LOGGER.info(
        "m145 communication record delivered_to_payer communication_record_id=%s",
        transitioned.communication_record_id,
    )
    return transitioned


def mark_m145_communication_record_locally_completed(
    communication_record_id: str,
    *,
    bucket_id: BucketId,
    actor: str = _M145_COMMUNICATION_EVENT_ACTOR,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
) -> M145CommunicationRecord:
    """Mark one payer-delivered local communication record as locally completed."""
    repository = _m145_communication_record_repository(bucket_id)
    record = repository.resolve(communication_record_id)
    if record.state is M145CommunicationRecordState.LOCALLY_COMPLETED:
        _LOGGER.debug(
            "m145 communication record completion reused state communication_record_id=%s state=%s",
            record.communication_record_id,
            record.state.value,
        )
        return record
    if record.state is not M145CommunicationRecordState.DELIVERED_TO_PAYER:
        _LOGGER.warning(
            "m145 communication record completion refused communication_record_id=%s state=%s",
            record.communication_record_id,
            record.state.value,
        )
        raise M145CommunicationRecordTransitionError(
            "Modelo 145 communication record must be delivered to payer before local completion",
            context={"communication_record_id": record.communication_record_id, "state": record.state.value},
        )
    transitioned_at = now()
    transitioned = _m145_communication_record_with_updates(
        record,
        state=M145CommunicationRecordState.LOCALLY_COMPLETED,
        locally_completed_at=transitioned_at,
    )
    repository.save(transitioned)
    _emit_m145_communication_event(
        transitioned,
        event_type=BucketEventType.MODELO_145_COMMUNICATION_LOCALLY_COMPLETED,
        occurred_at=transitioned_at,
        actor=actor,
        bucket_event_repository=bucket_event_repository,
    )
    _LOGGER.info(
        "m145 communication record locally_completed communication_record_id=%s",
        transitioned.communication_record_id,
    )
    return transitioned


def create_m145_communication_record(
    command: M145CommunicationCreateCommand,
    *,
    bucket_id: BucketId,
    actor: str = _M145_COMMUNICATION_EVENT_ACTOR,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
) -> M145CommunicationRecord:
    """Persist a bucket-local Modelo 145 communication record.

    Creation stores the operator-provided registry casilla values as a local
    payer communication record. It validates that every value is keyed by a
    casilla declared in the active Modelo 145 registry revision, persists the
    local record, and emits the communication-created bucket event.
    """
    snapshot = _snapshot_for_command(command)
    field_values = dict(sorted(command.field_values.items()))
    unknown = tuple(sorted(undeclared_casilla_ids(snapshot.revision, field_values)))
    if unknown:
        _LOGGER.warning(
            "m145 communication record create refused unknown_casilla_count=%d",
            len(unknown),
        )
        raise M145CommunicationRecordValidationError(
            f"Modelo 145 communication record contains undeclared casilla ids: {unknown!r}",
            context={"unknown_casilla_count": len(unknown), "unknown_casillas": unknown},
        )

    record_id = derive_m145_communication_record_id(
        bucket_id=bucket_id,
        communication_year=command.communication_year,
        period_token=command.period_token,
        revision_id=snapshot.revision.id,
        field_values=field_values,
    )
    repository = _m145_communication_record_repository(bucket_id)
    if repository.exists(record_id):
        _LOGGER.debug(
            "m145 communication record create reused existing communication_record_id=%s",
            record_id,
        )
        return repository.load(record_id)

    record = M145CommunicationRecord(
        communication_record_id=record_id,
        bucket_id=bucket_id,
        communication_year=command.communication_year,
        period_token=command.period_token,
        revision_id=snapshot.revision.id,
        field_values=field_values,
        legal_refs=tuple(sorted(str(ref) for ref in snapshot.revision.legal_refs)),
        source_refs=tuple(sorted(str(ref) for ref in snapshot.revision.source_refs)),
        created_at=now(),
        note=command.note,
    )
    repository.save(record)
    _emit_m145_communication_event(
        record,
        event_type=BucketEventType.MODELO_145_COMMUNICATION_CREATED,
        occurred_at=record.created_at,
        actor=actor,
        bucket_event_repository=bucket_event_repository,
    )
    _LOGGER.info(
        "m145 communication record created communication_record_id=%s communication_year=%d period=%s",
        record.communication_record_id,
        record.communication_year,
        record.period_token.value,
    )
    return record


__all__ = [
    "M145CommunicationCreateCommand",
    "M145CommunicationExportResult",
    "M145CommunicationFieldValue",
    "M145CommunicationPeriod",
    "M145CommunicationRecord",
    "M145CommunicationRecordAmbiguousError",
    "M145CommunicationRecordExportError",
    "M145CommunicationRecordId",
    "M145CommunicationRecordNotFoundError",
    "M145CommunicationRecordState",
    "M145CommunicationRecordTransitionError",
    "M145CommunicationRecordValidationError",
    "M145CommunicationServiceError",
    "M145CommunicationValidationIssue",
    "M145CommunicationValidationIssueKind",
    "M145CommunicationValidationResult",
    "create_m145_communication_record",
    "derive_m145_communication_record_id",
    "export_m145_communication_record",
    "list_m145_communication_records",
    "m145_communication_record_object_key",
    "mark_m145_communication_record_delivered_to_payer",
    "mark_m145_communication_record_locally_completed",
    "read_m145_communication_record",
    "validate_m145_communication_record",
]
