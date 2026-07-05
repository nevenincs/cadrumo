"""Modelo 145 local communication record creation and read-back."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from ...adapters.persistence.storage import M145_COMMUNICATION_RECORD_NAMESPACE
from ...core import STRICT_FROZEN_CONFIG, CasillaId, validated_casilla_id_map
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId
from ...core.time import now
from ...domain.calculations.registry import undeclared_casilla_ids
from ._m145_communication import (
    M145_COMMUNICATION_MODELO,
    M145_COMMUNICATION_SERVICE_OWNER,
    build_m145_communication_service_contract,
)

_HEX_64_PATTERN = r"^[0-9a-f]{64}$"

M145CommunicationRecordId = Annotated[
    str,
    Field(min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
M145CommunicationFieldValue = Annotated[str, Field(max_length=512)]


class M145CommunicationPeriod(StrEnum):
    """Registry-backed local communication period tokens for Modelo 145."""

    COMMUNICATION = "comunicacion"
    VARIATION = "variacion"


class M145CommunicationRecordState(StrEnum):
    """Creation-state vocabulary for local Modelo 145 communication records."""

    CREATED = "created"


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
            return validated_casilla_id_map(value, surface="m145 communication field_values")
        return value


class M145CommunicationRecord(BaseModel):
    """Persisted bucket-local Modelo 145 communication record."""

    model_config = STRICT_FROZEN_CONFIG

    communication_record_id: M145CommunicationRecordId
    bucket_id: BucketId
    service_owner: str = Field(
        default=M145_COMMUNICATION_SERVICE_OWNER,
        pattern=r"^aeat\.application\.modelo$",
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
    note: str | None = Field(default=None, max_length=512)

    @property
    def snapshot_id(self) -> str:
        return self.communication_record_id


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
    return KeyError(f"Modelo 145 communication record {communication_record_id!r} not found")


def _m145_communication_record_ambiguous_prefix(
    communication_record_id: str,
    full_ids: tuple[str, ...],
) -> KeyError:
    return KeyError(
        f"Modelo 145 communication record prefix {communication_record_id!r} "
        f"is ambiguous; matches {list(full_ids)!r}",
    )


def _m145_communication_record_repository(bucket_id: BucketId):
    from ..live import SecureSnapshotRepository

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
    contract = build_m145_communication_service_contract(filing_year=command.communication_year)
    from ...core.resources import resources

    snapshot = resources().modelos.authority.snapshot(
        M145_COMMUNICATION_MODELO,
        filing_year=command.communication_year,
        period=command.period_token.value,
    )
    contract_surfaces = frozenset(contract.surfaces)
    declared_surfaces = frozenset(str(link.surface) for link in snapshot.revision.application_links)
    if declared_surfaces != contract_surfaces:
        got = tuple(sorted(declared_surfaces))
        expected = tuple(sorted(contract_surfaces))
        raise ValueError(f"Modelo 145 communication record expected surfaces {expected!r}; got {got!r}")
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


def create_m145_communication_record(
    command: M145CommunicationCreateCommand,
    *,
    bucket_id: BucketId,
) -> M145CommunicationRecord:
    """Persist a bucket-local Modelo 145 communication record.

    Creation stores the operator-provided registry casilla values as a local
    payer communication record. It validates that every value is keyed by a
    casilla declared in the active Modelo 145 registry revision, but leaves
    required-field/type validation, export rendering, local state transitions,
    and bucket-event emission to the later plan steps that own those behaviors.
    """
    snapshot = _snapshot_for_command(command)
    field_values = dict(sorted(command.field_values.items()))
    unknown = tuple(sorted(undeclared_casilla_ids(snapshot.revision, field_values)))
    if unknown:
        raise ValueError(f"Modelo 145 communication record contains undeclared casilla ids: {unknown!r}")

    record_id = derive_m145_communication_record_id(
        bucket_id=bucket_id,
        communication_year=command.communication_year,
        period_token=command.period_token,
        revision_id=snapshot.revision.id,
        field_values=field_values,
    )
    repository = _m145_communication_record_repository(bucket_id)
    if repository.exists(record_id):
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
    return record


__all__ = [
    "M145CommunicationCreateCommand",
    "M145CommunicationFieldValue",
    "M145CommunicationPeriod",
    "M145CommunicationRecord",
    "M145CommunicationRecordId",
    "M145CommunicationRecordState",
    "create_m145_communication_record",
    "derive_m145_communication_record_id",
    "list_m145_communication_records",
    "m145_communication_record_object_key",
    "read_m145_communication_record",
]
