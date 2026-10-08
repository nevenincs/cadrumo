"""Validate independently accepted emitted filing bytes and official positions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from cadrumo.application.filing.producer_snapshot import (
    FilingProducerSnapshot,
)
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.period import Period
from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.ids import ModeloId, RevisionId
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.filing.schema import ModeloDraft
from cadrumo.domain.filing.software_identity import AeatProductSoftwareIdentity


@dataclass(frozen=True, slots=True)
class FilingExportOfficialOffsetProbe:
    """One generator-grounded literal field checked in production output."""

    record_id: str
    field_id: str


@dataclass(frozen=True, slots=True)
class FilingExportLiveProofEntry:
    """Inputs and independently recorded acceptance values for one revision."""

    modelo: ModeloId
    revision: RevisionId
    design_epoch: str
    filing_year: int
    period: Period
    draft: ModeloDraft
    producer_snapshot: FilingProducerSnapshot
    expected_payload_sha256: str
    expected_emitted_bytes: int
    official_offset_probes: tuple[FilingExportOfficialOffsetProbe, ...]
    prior_domiciliation_election: PriorDomiciliationElection | None = None
    product_software_identity: AeatProductSoftwareIdentity | None = None
    dictionary_values: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        """Refuse internally inconsistent or structurally empty acceptance input."""
        _validate_live_proof_coordinate(self)
        _validate_live_proof_acceptance(self)
        _validate_live_proof_probes(self)


def _validate_live_proof_coordinate(entry: FilingExportLiveProofEntry) -> None:
    if entry.period.filing_year != entry.filing_year:
        raise ValueError("filing export live proof period must belong to its filing year")
    if entry.draft.modelo != entry.modelo or entry.draft.period != entry.period:
        raise ValueError("filing export live proof draft identity must match its coordinate")
    if entry.producer_snapshot.modelo.value != entry.modelo:
        raise ValueError("filing export live proof producer modelo must match its coordinate")


def _validate_live_proof_acceptance(entry: FilingExportLiveProofEntry) -> None:
    if len(entry.expected_payload_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in entry.expected_payload_sha256
    ):
        raise ValueError("filing export live proof expected payload digest must be lowercase SHA-256")
    if entry.expected_emitted_bytes <= 0:
        raise ValueError("filing export live proof expected byte extent must be positive")


def _validate_live_proof_probes(entry: FilingExportLiveProofEntry) -> None:
    if not entry.official_offset_probes:
        raise ValueError("filing export live proof requires at least one official-offset probe")
    probe_identities = tuple((probe.record_id, probe.field_id) for probe in entry.official_offset_probes)
    if len(probe_identities) != len(set(probe_identities)):
        raise ValueError("filing export live proof official-offset probes must identify distinct fields")


def verify_filing_export_payload_acceptance(
    *,
    entry: FilingExportLiveProofEntry,
    layout: ExportLayoutDefinition,
    payload: bytes,
) -> None:
    """Re-hash emitted bytes and check generator-grounded official positions."""
    if sha256_hex(payload) != entry.expected_payload_sha256:
        raise RegistryValidationError("live export payload digest does not match acceptance evidence")
    if len(payload) != entry.expected_emitted_bytes:
        raise RegistryValidationError("live export payload extent does not match acceptance evidence")
    ordered = tuple(sorted(layout.records, key=lambda record: record.order))
    first = ordered[0]
    prefix_extent = layout.filing_envelope.prefix_extent if layout.filing_envelope is not None else 0
    checked_positions: set[int] = set()
    for probe in entry.official_offset_probes:
        _verify_live_export_probe(
            probe=probe,
            first_record=first,
            prefix_extent=prefix_extent,
            payload=payload,
            checked_positions=checked_positions,
        )


def _verify_live_export_probe(
    *,
    probe: FilingExportOfficialOffsetProbe,
    first_record: ExportRecordDefinition,
    prefix_extent: int,
    payload: bytes,
    checked_positions: set[int],
) -> None:
    field, offset, length, literal = _live_export_probe_field(probe, first_record)
    expected = _literal_bytes(field, literal=literal, encoding=first_record.encoding)
    start = prefix_extent + offset - 1
    field_positions = set(range(start, start + length))
    if checked_positions.intersection(field_positions):
        raise RegistryValidationError("official-offset probes must target distinct emitted byte positions")
    checked_positions.update(field_positions)
    if payload[start : start + length] != expected:
        raise RegistryValidationError(
            f"production export payload disagrees at official field {probe.record_id!r}/{probe.field_id!r}",
        )


def _live_export_probe_field(
    probe: FilingExportOfficialOffsetProbe,
    first_record: ExportRecordDefinition,
) -> tuple[ExportFieldDefinition, int, int, str]:
    if probe.record_id != str(first_record.id) or not first_record.required or first_record.repeat is not None:
        raise RegistryValidationError(
            "official-offset probe must target the first required non-repeating record",
        )
    field = next((item for item in first_record.fields if str(item.id) == probe.field_id), None)
    if field is None or field.offset is None or field.length is None or field.literal is None:
        raise RegistryValidationError("official-offset probe must target a positioned literal field")
    return field, field.offset, field.length, field.literal


def _literal_bytes(field: ExportFieldDefinition, *, literal: str, encoding: str) -> bytes:
    rendered = render_fixed_width_export_field(field, literal)
    return rendered.encode(encoding)
