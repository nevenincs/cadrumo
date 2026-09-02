"""Canonical filing-envelope contracts and declared prefix mechanics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, Field, model_validator

from ...core.hashing import sha256_hex
from ...core.identity import ContentDigest
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.product_identity import AeatProductSoftwareIdentity
from ...domain.calculations.registry.ids import RecordId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_exports import (
    ExportLayoutDefinition,
    FilingEnvelopeDefinition,
    FilingEnvelopePrefixFieldDeclaration,
    FilingEnvelopePrefixRole,
)
from ...domain.filing.errors import FilingExportValidationError
from ...domain.filing.schema import ModeloDraft, registry_schema_version
from ...domain.submission.models import ModeloDraftStatus
from ._envelope_modelo_policy import filing_envelope_modelo_policy
from .producer_snapshot import FilingProducerSnapshot

_ENVELOPE_GRAMMAR_LITERALS: Mapping[FilingEnvelopePrefixRole, str] = {
    FilingEnvelopePrefixRole.OPENING_TAG: "<T",
    FilingEnvelopePrefixRole.DISCRIMINANT: "0",
    FilingEnvelopePrefixRole.RECORD_TYPE: "0000>",
    FilingEnvelopePrefixRole.AUX_OPENING_TAG: "<AUX>",
    FilingEnvelopePrefixRole.AUX_CLOSING_TAG: "</AUX>",
}
_ENVELOPE_CLOSER_EXTENT: int = 18
_ENVELOPE_FILLER_ROLES: frozenset[FilingEnvelopePrefixRole] = frozenset(
    {
        FilingEnvelopePrefixRole.PRE_PROGRAM_FILLER,
        FilingEnvelopePrefixRole.BETWEEN_IDENTITIES_FILLER,
        FilingEnvelopePrefixRole.POST_DEVELOPER_FILLER,
    },
)


class FilingEnvelopeOccurrence(BaseModel):
    """One source-ordered occurrence emitted through the canonical record renderer."""

    model_config = STRICT_FROZEN_CONFIG

    record_id: RecordId
    occurrence: int = Field(gt=0)
    payload: bytes = Field(min_length=1)
    payload_sha256: ContentDigest

    @model_validator(mode="after")
    def _require_payload_digest(self) -> FilingEnvelopeOccurrence:
        if self.payload_sha256 != sha256_hex(self.payload):
            raise ValueError("filing-envelope occurrence digest must be derived from its emitted bytes")
        return self


class FilingEnvelopeRenderRequest(BaseModel):
    """Closed authority required to render one modelo's filing envelope."""

    model_config = STRICT_FROZEN_CONFIG

    registry_snapshot: RegistrySnapshot
    layout: ExportLayoutDefinition
    draft: ModeloDraft
    producer_snapshot: FilingProducerSnapshot
    prior_domiciliation_election: PriorDomiciliationElection
    product_software_identity: AeatProductSoftwareIdentity

    @property
    def modelo(self) -> Modelo:
        """Return the modelo named by the registry snapshot."""
        return Modelo(self.registry_snapshot.modelo.id)

    @model_validator(mode="after")
    def _require_one_coherent_filing_instance(self) -> FilingEnvelopeRenderRequest:
        snapshot = self.registry_snapshot
        _validate_envelope_filing_draft(self.draft, snapshot)
        _validate_envelope_filing_snapshot(self.draft, snapshot)
        _validate_envelope_filing_layout(self.layout, snapshot)
        _validate_envelope_filing_producer(self.draft, snapshot, self.producer_snapshot)
        policy = filing_envelope_modelo_policy(self.modelo)
        if policy.requires_prior_domiciliation_election and (
            self.producer_snapshot.elections.prior_domiciliation is not self.prior_domiciliation_election
        ):
            raise ValueError("filing-envelope election must match the immutable producer snapshot election")
        policy.validate_applicability(
            period=self.draft.period,
            registry_snapshot=snapshot,
            layout=self.layout,
            producer_snapshot=self.producer_snapshot,
        )
        return self


def _validate_envelope_filing_draft(draft: ModeloDraft, snapshot: RegistrySnapshot) -> None:
    if draft.modelo != snapshot.modelo.id:
        raise ValueError("filing-envelope draft modelo must match the selected registry snapshot")
    if draft.status is not ModeloDraftStatus.APROBADO:
        raise ValueError("filing-envelope rendering requires an approved draft")


def _validate_envelope_filing_snapshot(draft: ModeloDraft, snapshot: RegistrySnapshot) -> None:
    if snapshot.filing_period is None:
        raise ValueError("filing-envelope rendering requires a concrete registry snapshot period")
    if snapshot.filing_period != draft.period:
        raise ValueError("filing-envelope draft period must match the selected registry snapshot")
    if (
        draft.snapshot_ref.modelo != snapshot.modelo.id
        or draft.snapshot_ref.revision_id != snapshot.revision.id
        or draft.snapshot_ref.modelo_year != snapshot.filing_year
        or draft.snapshot_ref.period != snapshot.period
    ):
        raise ValueError("filing-envelope draft snapshot reference must match the selected registry snapshot")
    expected_schema_version = registry_schema_version(modelo=snapshot.modelo.id, revision_id=snapshot.revision.id)
    if draft.schema_version != expected_schema_version:
        raise ValueError("filing-envelope draft schema marker must match the selected registry revision")


def _validate_envelope_filing_layout(layout: ExportLayoutDefinition, snapshot: RegistrySnapshot) -> None:
    if not any(candidate is layout for candidate in snapshot.revision.export_layouts):
        raise ValueError("filing-envelope layout must be owned by the selected registry snapshot")
    envelope = layout.filing_envelope
    if envelope is None:
        raise ValueError("filing-envelope layout must carry a typed envelope declaration")
    if envelope.source_ref not in snapshot.revision.source_refs:
        raise ValueError("filing-envelope source must belong to the selected registry revision")
    try:
        source = snapshot.sources[envelope.source_ref]
    except KeyError as exc:
        raise ValueError("filing-envelope source is absent from the selected registry snapshot") from exc
    if source.sha256 != envelope.source_sha256:
        raise ValueError("filing-envelope source SHA-256 must match the selected registry snapshot source")


def _validate_envelope_filing_producer(
    draft: ModeloDraft,
    snapshot: RegistrySnapshot,
    producer_snapshot: FilingProducerSnapshot,
) -> None:
    if producer_snapshot.modelo.value != snapshot.modelo.id:
        raise ValueError("filing-envelope producer snapshot must be the selected snapshot's modelo")
    if producer_snapshot.taxpayer_tax_id != draft.subject_tax_id:
        raise ValueError("filing-envelope producer taxpayer must match the approved draft subject")


def envelope_closer_bytes(*, modelo: Modelo, period: Period) -> bytes:
    """Derive the declared relative closing identifier."""
    discriminant = _ENVELOPE_GRAMMAR_LITERALS[FilingEnvelopePrefixRole.DISCRIMINANT]
    record_type = _ENVELOPE_GRAMMAR_LITERALS[FilingEnvelopePrefixRole.RECORD_TYPE]
    closer = f"</T{modelo.value}{discriminant}{period.filing_year:04d}{period.registry_token}{record_type}".encode(
        "ascii"
    )
    if len(closer) != _ENVELOPE_CLOSER_EXTENT:
        raise FilingExportValidationError(
            f"filing-envelope closer must render to the declared {_ENVELOPE_CLOSER_EXTENT}-byte extent"
        )
    return closer


class FilingEnvelopeRenderResult(BaseModel):
    """Measured bytes and ordered occurrence evidence for one filing envelope."""

    model_config = STRICT_FROZEN_CONFIG

    draft_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    layout_id: str = Field(min_length=1)
    modelo: Modelo
    period: Period
    envelope: FilingEnvelopeDefinition
    occurrences: tuple[FilingEnvelopeOccurrence, ...]
    prefix: bytes = Field(min_length=1)
    closer: bytes = Field(min_length=1)
    payload: bytes = Field(min_length=1)
    payload_sha256: ContentDigest
    total_length: int = Field(gt=0)

    @model_validator(mode="after")
    def _require_exact_envelope_byte_derivation(self) -> FilingEnvelopeRenderResult:
        _require_envelope_occurrence_order(self.envelope, self.occurrences)
        if len(self.prefix) != self.envelope.prefix_extent:
            raise ValueError(
                f"filing-envelope prefix must retain its declared {self.envelope.prefix_extent}-byte extent"
            )
        if self.closer != envelope_closer_bytes(modelo=self.modelo, period=self.period):
            raise ValueError("filing-envelope closer must be derived from the selected modelo and filing period")
        body = b"".join(item.payload for item in self.occurrences)
        if self.payload != self.prefix + body + self.closer:
            raise ValueError("filing-envelope payload must be the exact prefix, occurrences, and closer bytes")
        if self.payload_sha256 != sha256_hex(self.payload):
            raise ValueError("filing-envelope payload digest must be derived from emitted bytes")
        if self.total_length != len(self.payload):
            raise ValueError("filing-envelope total must be derived from emitted bytes")
        return self


def _require_envelope_occurrence_order(
    envelope: FilingEnvelopeDefinition,
    occurrences: tuple[FilingEnvelopeOccurrence, ...],
) -> None:
    """Preserve zero/one/many record families in reviewed layout order."""
    declaration_order = {record_id: index for index, record_id in enumerate(envelope.body_record_ids)}
    last_family = -1
    next_occurrence: dict[RecordId, int] = {}
    for item in occurrences:
        try:
            family = declaration_order[item.record_id]
        except KeyError as exc:
            raise ValueError(f"filing envelope emitted an undeclared record family {item.record_id!r}") from exc
        if family < last_family:
            raise ValueError("filing-envelope occurrences must retain reviewed record-family order")
        expected_occurrence = next_occurrence.get(item.record_id, 1)
        if item.occurrence != expected_occurrence:
            raise ValueError(
                f"filing-envelope occurrences for {item.record_id!r} must be positive, contiguous, and uncollapsed"
            )
        next_occurrence[item.record_id] = expected_occurrence + 1
        last_family = family


def render_declared_prefix(
    prefix_fields: Sequence[FilingEnvelopePrefixFieldDeclaration],
    *,
    prefix_extent: int,
    modelo: Modelo,
    period: Period,
    product_software_identity: AeatProductSoftwareIdentity,
) -> bytes:
    """Render the declared prefix fields to their exact byte extent, or raise."""
    prefix = b"".join(
        render_envelope_prefix_field(
            field.role,
            length=field.length,
            modelo=modelo,
            period=period,
            product_software_identity=product_software_identity,
        )
        for field in prefix_fields
    )
    if len(prefix) != prefix_extent:
        raise FilingExportValidationError(f"envelope prefix must render to its declared {prefix_extent}-byte extent")
    return prefix


def _envelope_prefix_role_value(
    role: FilingEnvelopePrefixRole,
    *,
    length: int,
    modelo: Modelo,
    period: Period,
    product_software_identity: AeatProductSoftwareIdentity,
) -> str:
    if (literal := _ENVELOPE_GRAMMAR_LITERALS.get(role)) is not None:
        return literal
    if role in _ENVELOPE_FILLER_ROLES:
        return " " * length
    match role:
        case FilingEnvelopePrefixRole.MODELO:
            return modelo.value
        case FilingEnvelopePrefixRole.FILING_YEAR:
            return f"{period.filing_year:04d}"
        case FilingEnvelopePrefixRole.PERIOD:
            return period.registry_token
        case FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG:
            return (
                f"{_ENVELOPE_GRAMMAR_LITERALS[FilingEnvelopePrefixRole.OPENING_TAG]}"
                f"{modelo.value}"
                f"{_ENVELOPE_GRAMMAR_LITERALS[FilingEnvelopePrefixRole.DISCRIMINANT]}"
                f"{period.filing_year:04d}{period.registry_token}"
                f"{_ENVELOPE_GRAMMAR_LITERALS[FilingEnvelopePrefixRole.RECORD_TYPE]}"
            )
        case FilingEnvelopePrefixRole.PROGRAM_IDENTIFIER:
            return product_software_identity.program_identifier
        case FilingEnvelopePrefixRole.DEVELOPER_TAX_ID:
            return str(product_software_identity.developer_tax_id)
        case _:
            raise FilingExportValidationError(
                f"filing-envelope prefix role {role.value!r} has no declared value authority"
            )


def render_envelope_prefix_field(
    role: FilingEnvelopePrefixRole,
    *,
    length: int,
    modelo: Modelo,
    period: Period,
    product_software_identity: AeatProductSoftwareIdentity,
) -> bytes:
    """Render one declared prefix field's ASCII value to its declared byte length, or raise."""
    value = _envelope_prefix_role_value(
        role,
        length=length,
        modelo=modelo,
        period=period,
        product_software_identity=product_software_identity,
    )
    try:
        payload = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise FilingExportValidationError(f"filing-envelope prefix role {role.value!r} is not ASCII") from exc
    if len(payload) != length:
        raise FilingExportValidationError(
            f"filing-envelope prefix role {role.value!r} renders to {len(payload)} bytes, expected {length}"
        )
    return payload
