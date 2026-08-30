"""Typed records for the local declaration export / verify lifecycle.

The CLI exposes two primitives the application layer must back end-to-end:

- modelo export writes an
  AEAT declaration file from a validated registry snapshot for an approved
  :class:`domain.filing.ModeloDraft` and reports the byte-level
  summary the operator needs to track the artefact (output path, draft
  identity, content hash, format).
- modelo export verification re-reads a previously
  exported file and confirms that its casilla payload still matches
  the approved draft. The verdict is a closed enum; the diff (if any)
  is reported as a tuple of mismatched casilla identifiers so the CLI
  can render a deterministic table.

The records are structured return values for renderers, persistence, and
JSON round trips. Runtime export requires registry-backed
:class:`domain.calculations.registry.ExportLayoutDefinition` records,
and verification parses payloads through
:func:`domain.calculations.registry.parse_export_payload`.

The records intentionally do not embed the AEAT submission lifecycle
(:mod:`domain.submission`) — local export and live submit are
separate concerns and live submit is permanently forbidden.

This module is the draft-level renderer. The work-unit export service in
:mod:`application.modelo._export` rebuilds an approved
:class:`domain.filing.ModeloDraft` from a
:class:`~CalculationRevision`, then delegates here to write
and verify the fichero-BOE bytes.

See Also:
    :func:`application.modelo._export.export_modelo_revision`
        Higher-level work-unit export service that replays a calculation
        revision before calling this draft renderer.
    :mod:`adapters.outbound.aeat.export`
        Outbound export-format adapter errors and fixed-width helper
        namespace.
    :class:`core.access_gate.LiveSubmitForbiddenError`
        Core refusal raised for every attempted live AEAT write.
    :mod:`domain.submission`
        Local-only submitted-state lifecycle, separate from file export.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol, overload

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import STRICT_FROZEN_HIDDEN_INPUT_CONFIG as _STRICT_FROZEN_HIDDEN
from ...core import ExportLayoutFormat, FilingProducerKey, Modelo, Period, PriorDomiciliationElection
from ...core.casilla_id import CasillaId
from ...core.product_identity import AeatProductSoftwareIdentity
from ...core.atomic_write import atomic_write_bytes
from ...core.hashing import hash_file, sha256_file, sha256_hex
from ...core.identity import ContentDigest
from ...core.logging import get_logger
from ...core.time import now
from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.export_parse import (
    parse_export_payload,
    xml_dictionary_entries,
)
from ...domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from ...domain.calculations.registry.ids import (
    BindingId,
    RecordId,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_exports import (
    ExportLayoutDefinition,
    FilingEnvelopeDefinition,
    FilingEnvelopePrefixFieldDeclaration,
    FilingEnvelopePrefixRole,
)
from ...domain.filing.errors import FilingExportError, FilingExportValidationError
from ...domain.filing.schema import ModeloCasillaProvenance, ModeloDraft, registry_schema_version
from ...domain.submission import ModeloDraftStatus
from ._envelope_modelo_policy import filing_envelope_modelo_policy
from ._export_parity import (
    assert_export_mirrors_manifest,
    assert_rate_boxes_account_for_total,
    assert_xml_declaration_aux_declared,
)
from ._export_producer import filing_producer_values as _filing_producer_values
from ._export_xml_dictionary import (
    expected_xml_dictionary_root_identity,
    read_xml_dictionary_root_identity,
    render_xml_dictionary_layout,
)
from ._m200_projection import build_m200_filing_projection_plan
from ._m296_projection import build_m296_filing_projection_plan
from ._producer_snapshot import (
    FilingProducerSnapshot,
)
from ._projection import (
    FilingProjectionPlan,
    FilingProjectionValue,
    FilingRecordRenderContext,
    build_m303_filing_projection_plan,
)
from ._record_renderer import (
    RecordRenderRow as _RecordRenderRow,
)
from ._record_renderer import (
    RenderedRecordOccurrence as _RenderedRecordOccurrence,
)
from ._record_renderer import (
    complementaria_page_marker as _complementaria_page_marker,
)
from ._record_renderer import (
    format_field as _format_field,
)
from ._record_renderer import (
    m303_complementaria_marker as _m303_complementaria_marker,
)
from ._record_renderer import (
    m303_no_activity_marker as _m303_no_activity_marker,
)
from ._record_renderer import (
    preflight_projection_plan as _preflight_projection_plan,
)
from ._record_renderer import (
    projection_field_value as _projection_field_value,
)
from ._record_renderer import (
    render_layout_records as _render_layout_records,
)
from ._record_renderer import (
    render_record as _render_record,
)
from .runtime import RegistryModeloSubview, RegistrySchemaAccessor, build_runtime_schema_provider

_logger = get_logger(__name__)

_SHA256_HEX_LENGTH = 64
"""Length of a hex-encoded SHA-256 digest used by export receipts."""


#: The AEAT constants every bundled variable-envelope design prints verbatim.
#:
#: Shared GRAMMAR rather than one modelo's literals: the discriminant ``"0"``,
#: the ``0000>`` record-type terminator, and the ``<AUX>`` pair are identical in
#: all thirty-five bundled 328-byte designs. A design that prints something else
#: -- Modelo 220's conditional ``(*)[A|E|I|0]`` discriminant is the known one --
#: is refused by the static generator's source-content check before its layout
#: can ever reach this renderer, so a divergent design cannot be emitted here
#: under a constant it does not declare.
_ENVELOPE_GRAMMAR_LITERALS: Mapping[FilingEnvelopePrefixRole, str] = {
    FilingEnvelopePrefixRole.OPENING_TAG: "<T",
    FilingEnvelopePrefixRole.DISCRIMINANT: "0",
    FilingEnvelopePrefixRole.RECORD_TYPE: "0000>",
    FilingEnvelopePrefixRole.AUX_OPENING_TAG: "<AUX>",
    FilingEnvelopePrefixRole.AUX_CLOSING_TAG: "</AUX>",
}

#: ``</T`` + three modelo + one discriminant + four year + two period + ``0000>``.
_ENVELOPE_CLOSER_EXTENT: int = 18

#: Roles whose emitted bytes are reserved blanks of the field's declared width.
_ENVELOPE_FILLER_ROLES: frozenset[FilingEnvelopePrefixRole] = frozenset(
    {
        FilingEnvelopePrefixRole.PRE_PROGRAM_FILLER,
        FilingEnvelopePrefixRole.BETWEEN_IDENTITIES_FILLER,
        FilingEnvelopePrefixRole.POST_DEVELOPER_FILLER,
    },
)


class FilingEnvelopeOccurrence(BaseModel):
    """One source-ordered occurrence emitted through the canonical record renderer."""

    model_config = _STRICT_FROZEN

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
    """Closed public authority required to render one modelo's filing envelope.

    Projection plans, body members, casilla maps, headers, and opaque bytes are
    intentionally absent.  The renderer derives them internally from the
    approved draft and snapshot-owned layout through the canonical resolver.

    The MODELO is not a field: it is read from the selected snapshot, which the
    validators below prove agrees with the draft, the producer snapshot, and the
    layout's owning revision. A second spelling of it here would be a fact that
    can drift from the authority that selected the layout.
    """

    model_config = _STRICT_FROZEN

    registry_snapshot: RegistrySnapshot
    layout: ExportLayoutDefinition
    draft: ModeloDraft
    producer_snapshot: FilingProducerSnapshot
    prior_domiciliation_election: PriorDomiciliationElection
    product_software_identity: AeatProductSoftwareIdentity

    @property
    def modelo(self) -> Modelo:
        """Return the one modelo the whole request is proved to agree on."""
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
    expected_schema_version = registry_schema_version(
        modelo=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
    )
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
    """Derive one envelope's relative closing identifier from the filing period.

    The single home for ``relative-closer-v1``: the same six semantics the
    prefix opens with -- tag, modelo, discriminant, year, period, record type --
    re-spelled as a closing tag. Declared once so the render path and the
    result's own byte proof cannot disagree about it.
    """
    discriminant = _ENVELOPE_GRAMMAR_LITERALS[FilingEnvelopePrefixRole.DISCRIMINANT]
    record_type = _ENVELOPE_GRAMMAR_LITERALS[FilingEnvelopePrefixRole.RECORD_TYPE]
    closer = f"</T{modelo.value}{discriminant}{period.filing_year:04d}{period.registry_token}{record_type}".encode(
        "ascii"
    )
    # A real guard rather than a restatement: the closer is built from the
    # period, so a period formatting to the wrong width is reachable, while the
    # ``closer_derivation`` member itself is unconstructible in any other value.
    if len(closer) != _ENVELOPE_CLOSER_EXTENT:
        raise FilingExportValidationError(
            f"filing-envelope closer must render to the declared {_ENVELOPE_CLOSER_EXTENT}-byte extent",
        )
    return closer


class FilingEnvelopeRenderResult(BaseModel):
    """Measured bytes and ordered occurrence evidence for one filing envelope."""

    model_config = _STRICT_FROZEN

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
                f"filing-envelope prefix must retain its declared {self.envelope.prefix_extent}-byte extent",
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


class DeclaracionExportFormat(StrEnum):
    """Closed catalogue of AEAT export formats.

    Attributes:
        FICHERO_BOE: Fixed-width "importar datos" payload defined by
            the AEAT *Diseño de registros* per modelo and validated
            through the registry.
    """

    FICHERO_BOE = "fichero-boe"
    XML_DICTIONARY = "xml-dictionary"


class DeclaracionVerifyVerdict(StrEnum):
    """Closed verdict the verify command surfaces to the operator.

    Attributes:
        MATCH: Every parser-covered casilla in the file equals the
            approved draft's casilla value. Check
            :attr:`DeclaracionVerifyResult.unchecked_casilla_ids` for
            draft casillas that the registry parser cannot re-read from
            the wire layout.
        DRIFT: At least one casilla diverges between the file and the
            approved draft. The CLI renders the per-casilla diff.
        MISSING: The file is unreadable, malformed, or does not cover
            the casillas the draft declares. No diff is computed.
    """

    MATCH = "match"
    DRIFT = "drift"
    MISSING = "missing"


class DeclaracionExportResult(BaseModel):
    """Receipt produced by exporting an approved draft to disk.

    The record is the structured-data return value of the
    modelo export command. It carries enough metadata
    for the operator to identify the artefact later, for the verify
    command to anchor its comparison, and for the audit log to record
    the export event without re-reading the file.

    Attributes:
        draft_id: The :class:`domain.filing.ModeloDraft` identity
            the export was generated from.
        modelo: AEAT modelo identifier.
        period: Typed filing period for the exported draft.
        format: The on-disk wire format (closed
            :class:`DeclaracionExportFormat`).
        output_path: Absolute path the file was written to.
        byte_size: Size of the written content in bytes. Bound to the
            artefact by :func:`assert_export_artifact_matches_receipt`, not
            merely asserted about it.
        file_sha256: Hex-encoded SHA-256 digest of the written bytes, bound
            to the artefact by the same check. Anchors the operator's later
            file-vs-draft comparison and the durable export bucket event.
        exported_at: UTC timestamp of when the file was written.
        narrative: Translation key for operator-facing summary.
        casilla_provenance: Regulatory grounding for the draft casillas
            represented by the selected registry export layout.

    See Also:
        :class:`DeclaracionVerifyResult`
            Verification record that re-reads the exported bytes and
            anchors the comparison by ``file_sha256``.
        :class:`domain.calculations.registry.ExportLayoutDefinition`
            Registry layout used to render the fixed-width payload.
    """

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    format: DeclaracionExportFormat
    output_path: Path
    byte_size: int = Field(ge=0)
    file_sha256: ContentDigest
    exported_at: datetime
    narrative: str
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)

    @field_validator("file_sha256")
    @classmethod
    def _validate_sha256_hex(cls, value: str) -> str:
        """Reject anything that is not a lowercase hex SHA-256 digest."""
        try:
            int(value, 16)
        except ValueError as exc:
            raise FilingExportValidationError("file_sha256 must be a hex-encoded digest") from exc
        if value != value.lower():
            raise FilingExportValidationError("file_sha256 must be lowercase hex")
        return value


class FilingExportConsumedResult(BaseModel):
    """Internal receipt for a validated payload delivered without a filesystem path."""

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    format: DeclaracionExportFormat
    byte_size: int = Field(gt=0)
    file_sha256: ContentDigest
    exported_at: datetime
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)

    @field_validator("file_sha256")
    @classmethod
    def _validate_sha256_hex(cls, value: str) -> str:
        if any(character not in "0123456789abcdef" for character in value):
            raise FilingExportValidationError("file_sha256 must be lowercase hexadecimal")
        return value


class FilingExportValidatedPayload(BaseModel):
    """Secret-bearing in-memory payload delivered only after export validation."""

    model_config = _STRICT_FROZEN_HIDDEN

    draft_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    period: Period
    format: DeclaracionExportFormat
    payload: bytes = Field(min_length=1)
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)


class FilingExportPayloadConsumer(Protocol):
    """Destination port for validated bytes that must not touch plaintext disk."""

    def consume_validated_payload(self, payload: FilingExportValidatedPayload) -> None:
        """Consume the payload synchronously before its in-memory owner returns."""


class DeclaracionVerifyResult(BaseModel):
    """Verdict produced by verifying an exported file against an approved draft.

    The verify command re-reads the file the export command wrote and
    compares its casilla payload against the approved
    :class:`domain.filing.ModeloDraft`. The verdict is the typed
    return value the CLI renders.

    Attributes:
        draft_id: The :class:`domain.filing.ModeloDraft` identity
            the file was compared against.
        file_path: Absolute path of the file that was verified.
        verdict: Closed :class:`DeclaracionVerifyVerdict`.
        mismatched_casilla_ids: Tuple of casilla identifiers whose value
            in the file differs from the approved draft. Empty when
            ``verdict is MATCH``; populated when ``verdict is DRIFT``;
            always empty when ``verdict is MISSING`` (the diff cannot
            be computed).
        unchecked_casilla_ids: Tuple of draft casilla identifiers that do
            not round-trip through the export parser because the wire
            schema exposes them as reserved constants or derived fields
            rather than deserialised currency casillas.
        mismatched_root_fields: Tuple of declaration-identity attribute names
            (``modelo``, ``ejercicio``, ``periodo``, ``versionxsd``, the XSD
            schema location) whose value in an XML-dictionary file differs
            from the draft the file is being verified against. Empty when
            ``verdict is MATCH``, and always empty for a layout whose format
            carries no root identity.
        file_sha256: Hex SHA-256 of the bytes the verifier read.
            Lets the audit trail prove the same file the export
            command wrote was the one verified, even if
            ``output_path`` was renamed in between.
        verified_at: UTC timestamp of when the verdict was produced.
        narrative: Translation key for operator-facing summary.
        casilla_provenance: Regulatory grounding for the draft
            casillas covered by the export parser/layout.
        mismatched_casilla_provenance: Regulatory grounding for the
            subset of ``mismatched_casilla_ids``.

    See Also:
        :func:`domain.calculations.registry.parse_export_payload`
            Registry parser used to compute parser-covered casillas.
        :class:`DeclaracionVerifyVerdict`
            Closed verdict enum rendered by the CLI.
        :class:`DeclaracionExportResult`
            Export receipt whose digest anchors later verification.
    """

    model_config = _STRICT_FROZEN

    draft_id: str = Field(min_length=1, max_length=128)
    file_path: Path
    verdict: DeclaracionVerifyVerdict
    mismatched_casilla_ids: tuple[CasillaId, ...] = ()
    unchecked_casilla_ids: tuple[CasillaId, ...] = ()
    mismatched_root_fields: tuple[str, ...] = ()
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)
    mismatched_casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)
    file_sha256: str | None = Field(default=None)
    verified_at: datetime
    narrative: str

    @field_validator("mismatched_casilla_ids", "unchecked_casilla_ids")
    @classmethod
    def _validate_casilla_ids(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        """Reject blank casilla identifiers; the CLI renders them verbatim."""
        for entry in value:
            if not entry or entry != entry.strip():
                raise FilingExportValidationError(
                    "casilla-id entries must be non-blank, untrimmed identifiers",
                )
        return value

    @field_validator("file_sha256")
    @classmethod
    def _validate_sha256_hex(cls, value: str | None) -> str | None:
        """Match :class:`DeclaracionExportResult` digest hygiene when present."""
        if value is None:
            return None
        if len(value) != _SHA256_HEX_LENGTH:
            raise FilingExportValidationError(f"file_sha256 must be {_SHA256_HEX_LENGTH} hex characters when provided")
        try:
            int(value, 16)
        except ValueError as exc:
            raise FilingExportValidationError("file_sha256 must be a hex-encoded digest") from exc
        if value != value.lower():
            raise FilingExportValidationError("file_sha256 must be lowercase hex")
        return value


@dataclass(frozen=True, slots=True)
class _PreparedExportDraft:
    provider: RegistrySchemaAccessor
    subview: RegistryModeloSubview
    registry_snapshot: RegistrySnapshot
    layout: ExportLayoutDefinition
    producer_values: Mapping[FilingProducerKey, object]
    prior_domiciliation_election: PriorDomiciliationElection
    renders_filing_envelope: bool


def _require_current_export_schema(draft: ModeloDraft, subview: RegistryModeloSubview) -> None:
    if draft.schema_version != subview.schema_version:
        raise FilingExportError(
            translated_message="application.filing.export.errors.draft_snapshot_stale",
            context={
                "modelo": draft.modelo,
                "draft_schema_version": draft.schema_version,
                "active_schema_version": subview.schema_version,
            },
        )


def _require_approved_export_draft(draft: ModeloDraft) -> None:
    if draft.status is not ModeloDraftStatus.APROBADO:
        raise FilingExportError(
            translated_message="application.filing.export.errors.draft_not_approved",
            context={
                "modelo": draft.modelo,
                "draft_status": draft.status.value,
                "required_status": ModeloDraftStatus.APROBADO.value,
            },
        )


def _select_export_layout(
    draft: ModeloDraft,
    *,
    subview: RegistryModeloSubview,
    registry_snapshot: RegistrySnapshot,
) -> ExportLayoutDefinition:
    if not subview.export_layout_ids:
        raise _export_layout_not_renderable_error(draft.modelo, None)
    layout = sorted(registry_snapshot.revision.export_layouts, key=lambda item: item.id)[0]
    _raise_if_export_layout_not_renderable(draft.modelo, layout)
    return layout


def _validate_export_options(
    *,
    modelo: Modelo,
    renders_filing_envelope: bool,
    renders_auxiliary_header: bool,
    dictionary_values: Mapping[str, object] | None,
    prior_domiciliation_election: PriorDomiciliationElection | None,
    product_software_identity: AeatProductSoftwareIdentity | None,
) -> PriorDomiciliationElection:
    """Admit exactly the options the SELECTED LAYOUT's composition needs.

    Keyed on whether the layout declares an envelope prefix -- a filing
    envelope or a total-less auxiliary header -- rather than on the modelo id:
    the product/software identity is required by the prefix itself, so every
    modelo whose layout carries one needs it and no modelo without one may pass
    it. The prior-domiciliation election is different -- it is one modelo's
    record applicability, so it stays a registered per-modelo policy rather than
    a property of the envelope.
    """
    if not renders_filing_envelope and not renders_auxiliary_header:
        if product_software_identity is not None:
            raise FilingExportValidationError(
                "product/software identity is only admitted for a layout that renders an envelope prefix",
            )
        return prior_domiciliation_election or PriorDomiciliationElection.KEEP
    if product_software_identity is None:
        raise FilingExportValidationError(
            "an envelope-prefix export requires explicit product/software identity authority",
        )
    if dictionary_values is not None:
        raise FilingExportValidationError("an envelope-prefix export does not admit XML dictionary values")
    if filing_envelope_modelo_policy(modelo).requires_prior_domiciliation_election and (
        prior_domiciliation_election is None
    ):
        raise FilingExportValidationError(
            f"Modelo {modelo.value} export requires an explicit prior-domiciliation election",
        )
    return prior_domiciliation_election or PriorDomiciliationElection.KEEP


def _prepare_export_draft(
    draft: ModeloDraft,
    *,
    producer_snapshot: FilingProducerSnapshot,
    dictionary_values: Mapping[str, object] | None,
    prior_domiciliation_election: PriorDomiciliationElection | None,
    product_software_identity: AeatProductSoftwareIdentity | None,
    schema_provider: RegistrySchemaAccessor | None,
) -> _PreparedExportDraft:
    provider = schema_provider or build_runtime_schema_provider(modelos=(draft.modelo,))
    subview = provider.get_subview(draft.modelo)
    registry_snapshot = provider.get_snapshot(draft.modelo)
    _require_current_export_schema(draft, subview)
    _require_approved_export_draft(draft)
    layout = _select_export_layout(draft, subview=subview, registry_snapshot=registry_snapshot)
    renders_filing_envelope = layout.filing_envelope is not None
    renders_auxiliary_header = layout.auxiliary_envelope_header is not None
    resolved_prior_domiciliation_election = _validate_export_options(
        modelo=Modelo(draft.modelo),
        renders_filing_envelope=renders_filing_envelope,
        renders_auxiliary_header=renders_auxiliary_header,
        dictionary_values=dictionary_values,
        prior_domiciliation_election=prior_domiciliation_election,
        product_software_identity=product_software_identity,
    )
    if producer_snapshot.modelo.value != draft.modelo:
        raise FilingExportValidationError("filing producer snapshot modelo does not match draft")
    return _PreparedExportDraft(
        provider=provider,
        subview=subview,
        registry_snapshot=registry_snapshot,
        layout=layout,
        producer_values=_filing_producer_values(producer_snapshot),
        prior_domiciliation_election=resolved_prior_domiciliation_election,
        renders_filing_envelope=renders_filing_envelope,
    )


def _render_prepared_export(
    draft: ModeloDraft,
    *,
    prepared: _PreparedExportDraft,
    producer_snapshot: FilingProducerSnapshot,
    dictionary_values: Mapping[str, object] | None,
    prior_domiciliation_election: PriorDomiciliationElection | None,
    product_software_identity: AeatProductSoftwareIdentity | None,
) -> bytes:
    if prepared.renders_filing_envelope:
        assert prior_domiciliation_election is not None
        assert product_software_identity is not None
        return render_filing_envelope(
            FilingEnvelopeRenderRequest(
                registry_snapshot=prepared.registry_snapshot,
                layout=prepared.layout,
                draft=draft,
                producer_snapshot=producer_snapshot,
                prior_domiciliation_election=prior_domiciliation_election,
                product_software_identity=product_software_identity,
            ),
        ).payload
    return _render_export_layout(
        prepared.layout,
        draft=draft,
        headers=prepared.producer_values,
        producer_snapshot=producer_snapshot,
        dictionary_values=dictionary_values,
        prior_domiciliation_election=prepared.prior_domiciliation_election,
        product_software_identity=product_software_identity,
        schema_provider=prepared.provider,
        registry_snapshot=prepared.registry_snapshot,
    )


def _validate_prepared_export(
    draft: ModeloDraft,
    *,
    prepared: _PreparedExportDraft,
    payload: bytes,
) -> tuple[ModeloCasillaProvenance, ...]:
    if not payload:
        raise FilingExportError(
            translated_message="application.filing.export.errors.rendered_payload_empty",
            context={
                "modelo": draft.modelo,
                "layout_id": prepared.layout.id,
                "layout_format": prepared.layout.format.value,
            },
        )
    casilla_provenance = _exported_casilla_provenance(
        prepared.layout,
        draft=draft,
        schema_provider=prepared.provider,
    )
    assert_xml_declaration_aux_declared(prepared.layout)
    assert_rate_boxes_account_for_total(prepared.subview.rate_box_partitions, draft=draft)
    if prepared.subview.completeness_manifest is not None:
        assert_export_mirrors_manifest(
            prepared.layout,
            draft=draft,
            headers=prepared.producer_values,
            prior_domiciliation_election=prepared.prior_domiciliation_election,
            schema_provider=prepared.provider,
            manifest=prepared.subview.completeness_manifest,
            casilla_metadata=prepared.subview.casilla_record_metadata,
        )
    return casilla_provenance


def _write_prepared_export(
    draft: ModeloDraft,
    *,
    output_path: Path,
    prepared: _PreparedExportDraft,
    payload: bytes,
    casilla_provenance: tuple[ModeloCasillaProvenance, ...],
) -> DeclaracionExportResult:
    atomic_write_bytes(output_path, payload)
    if not prepared.renders_filing_envelope:
        _verify_written_export(
            draft,
            file_path=output_path,
            schema_provider=prepared.provider,
        )
    receipt = DeclaracionExportResult(
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        format=_declaracion_export_format(prepared.layout),
        output_path=output_path,
        byte_size=len(payload),
        file_sha256=sha256_hex(payload),
        exported_at=now(),
        narrative="filing.export.written",
        casilla_provenance=casilla_provenance,
    )
    assert_export_artifact_matches_receipt(receipt, artifact_path=output_path)
    return receipt


def _consume_prepared_export(
    draft: ModeloDraft,
    *,
    prepared: _PreparedExportDraft,
    payload: bytes,
    casilla_provenance: tuple[ModeloCasillaProvenance, ...],
    payload_consumer: FilingExportPayloadConsumer,
) -> FilingExportConsumedResult:
    """Deliver validated bytes synchronously without materialising a plaintext file."""
    format_ = _declaracion_export_format(prepared.layout)
    payload_consumer.consume_validated_payload(
        FilingExportValidatedPayload(
            draft_id=draft.draft_id,
            modelo=draft.modelo,
            period=draft.period,
            format=format_,
            payload=payload,
            casilla_provenance=casilla_provenance,
        ),
    )
    return FilingExportConsumedResult(
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        format=format_,
        byte_size=len(payload),
        file_sha256=sha256_hex(payload),
        exported_at=now(),
        casilla_provenance=casilla_provenance,
    )


@overload
def export_draft(
    draft: ModeloDraft,
    *,
    output_path: Path,
    payload_consumer: None = None,
    producer_snapshot: FilingProducerSnapshot,
    dictionary_values: Mapping[str, object] | None = None,
    prior_domiciliation_election: PriorDomiciliationElection | None = None,
    product_software_identity: AeatProductSoftwareIdentity | None = None,
    schema_provider: RegistrySchemaAccessor | None = None,
) -> DeclaracionExportResult: ...
@overload
def export_draft(
    draft: ModeloDraft,
    *,
    output_path: None = None,
    payload_consumer: FilingExportPayloadConsumer,
    producer_snapshot: FilingProducerSnapshot,
    dictionary_values: Mapping[str, object] | None = None,
    prior_domiciliation_election: PriorDomiciliationElection | None = None,
    product_software_identity: AeatProductSoftwareIdentity | None = None,
    schema_provider: RegistrySchemaAccessor | None = None,
) -> FilingExportConsumedResult: ...
def export_draft(
    draft: ModeloDraft,
    *,
    output_path: Path | None = None,
    payload_consumer: FilingExportPayloadConsumer | None = None,
    producer_snapshot: FilingProducerSnapshot,
    dictionary_values: Mapping[str, object] | None = None,
    prior_domiciliation_election: PriorDomiciliationElection | None = None,
    product_software_identity: AeatProductSoftwareIdentity | None = None,
    schema_provider: RegistrySchemaAccessor | None = None,
) -> DeclaracionExportResult | FilingExportConsumedResult:
    """Write an approved draft to a local fichero-BOE file and return a receipt.

    The function selects the active registry
    :class:`~domain.calculations.registry.ExportLayoutDefinition`,
    renders its fixed-width records, writes only ``output_path``, and
    never contacts AEAT. Live submission is outside this surface and is
    refused by :class:`core.access_gate.LiveSubmitForbiddenError`.

    Args:
        draft: The :class:`ModeloDraft` to export; must be in ``APROBADO`` status.
        output_path: Destination path for ordinary filesystem export. Exactly
            one of this or ``payload_consumer`` is required.
        payload_consumer: Synchronous destination for validated in-memory bytes,
            used when plaintext output must not touch a filesystem.
        producer_snapshot: Complete typed filing facts consumed by registry producers.
        dictionary_values: Optional values addressed by the dictionary field id
            AEAT declares for them, each still carrying its own Python type.
            Read only by the ``xml_dictionary`` renderer, which is the only
            format addressing fields that way; the fixed-width renderer resolves
            its fields from ``headers`` and the layout's record definitions.
        prior_domiciliation_election: Typed M303 page-three election used by
            the shared Nota-3 DID page predicate. Required for Modelo 303;
            non-M303 exports carry no election authority.
        product_software_identity: Explicit reviewed AEAT product authority.
            Required for Modelo 303's DP30300 carrier and refused for every
            other modelo.
        schema_provider: Optional registry schema provider override.

    Returns:
        A :class:`DeclaracionExportResult` with the output path, digest,
        byte size, and casilla provenance for the exported declaration.

    See Also:
        :func:`verify_export`
            Re-read a local export file and compare parser-covered casillas
            against the approved draft.
        :func:`application.modelo._export.export_modelo_revision`
            Work-unit-facing export orchestration that supplies an approved
            draft reconstructed from a calculation revision.
        :func:`domain.calculations.registry.parse_export_payload`
            Registry parser used by the verification path.
    """
    if (output_path is None) == (payload_consumer is None):
        raise FilingExportValidationError("export requires exactly one payload destination")
    prepared = _prepare_export_draft(
        draft,
        producer_snapshot=producer_snapshot,
        dictionary_values=dictionary_values,
        prior_domiciliation_election=prior_domiciliation_election,
        product_software_identity=product_software_identity,
        schema_provider=schema_provider,
    )
    payload = _render_prepared_export(
        draft,
        prepared=prepared,
        producer_snapshot=producer_snapshot,
        dictionary_values=dictionary_values,
        prior_domiciliation_election=prior_domiciliation_election,
        product_software_identity=product_software_identity,
    )
    casilla_provenance = _validate_prepared_export(draft, prepared=prepared, payload=payload)
    if output_path is not None:
        return _write_prepared_export(
            draft,
            output_path=output_path,
            prepared=prepared,
            payload=payload,
            casilla_provenance=casilla_provenance,
        )
    if payload_consumer is None:
        raise FilingExportValidationError("export payload consumer is unavailable")
    return _consume_prepared_export(
        draft,
        prepared=prepared,
        payload=payload,
        casilla_provenance=casilla_provenance,
        payload_consumer=payload_consumer,
    )


def assert_export_artifact_matches_receipt(
    receipt: DeclaracionExportResult,
    *,
    artifact_path: Path,
) -> None:
    """Refuse an artefact whose bytes do not reproduce ``receipt``'s metadata.

    ``byte_size`` and ``file_sha256`` are measured from the payload the
    renderer holds, but they are *published* as facts about a file. Those are
    two different things, and nothing compared them: every field was
    individually well-formed -- a real digest over real bytes, a non-negative
    length -- so a receipt could truthfully describe a payload that is not the
    file it points at, and no shape constraint could see it. The pair is also
    copied into the durable ``MODELO_EXPORTED`` bucket event, where a wrong
    number outlives the artefact it describes.

    :class:`~application.export.TabularExportResult` answers the same question
    inside a model validator because that result *carries* its payload. A
    filing receipt carries a :class:`~pathlib.Path` instead, so the binding has
    to read the artefact -- which a frozen transport model must not do on every
    construction, including when one is rehydrated from JSON long after the
    file moved or was consumed by an atomic rename. Hence a check the writers
    call, not a validator the model runs.

    Both export writers route through here, each supplying the path it
    legitimately knows -- the draft renderer the file it just wrote, the
    work-unit service the destination it renamed into place -- so the binding
    is one invariant rather than two conventions.

    Args:
        receipt: The receipt whose declared metadata is being bound.
        artifact_path: The file the caller claims ``receipt`` describes.

    Raises:
        FilingExportError: The artefact is absent or unreadable, or its byte
            count or digest does not reproduce the receipt's declared values.
    """
    try:
        digest, byte_size = hash_file(artifact_path)
    except OSError as exc:
        raise FilingExportError(
            translated_message="application.filing.export.errors.receipt_artefact_unreadable",
            context={
                "artifact_path": str(artifact_path),
                "os_error_type": type(exc).__name__,
            },
        ) from exc
    if byte_size != receipt.byte_size:
        raise FilingExportError(
            translated_message="application.filing.export.errors.receipt_byte_size_mismatch",
            context={
                "artifact_path": str(artifact_path),
                "declared_byte_size": receipt.byte_size,
                "observed_byte_size": byte_size,
            },
        )
    if digest != receipt.file_sha256:
        raise FilingExportError(
            translated_message="application.filing.export.errors.receipt_digest_mismatch",
            context={
                "artifact_path": str(artifact_path),
                "declared_sha256": receipt.file_sha256,
                "observed_sha256": digest,
            },
        )


class ExportLayoutRenderabilityReason(StrEnum):
    """Closed machine reasons a registry layout cannot render declaration bytes.

    This enum is the single decision authority for export renderability. The
    prose projection below exists only to serve consumers outside this package
    that still read a rendered sentence; it maps this vocabulary and never
    decides anything itself.
    """

    NO_COMPLETE_EXPORT_LAYOUTS = "no_complete_export_layouts"
    XML_DICTIONARY_SOURCE_ABSENT = "xml_dictionary_source_absent"
    UNSUPPORTED_LAYOUT_FORMAT = "unsupported_layout_format"
    NO_EXPORT_RECORDS = "no_export_records"


def export_layout_renderability_reason_code(
    layout: ExportLayoutDefinition | None,
) -> ExportLayoutRenderabilityReason | None:
    """Return the closed reason ``layout`` cannot produce local declaration bytes."""
    if layout is None:
        return ExportLayoutRenderabilityReason.NO_COMPLETE_EXPORT_LAYOUTS
    if layout.format is ExportLayoutFormat.XML_DICTIONARY:
        if layout.dictionary_source_ref is None:
            return ExportLayoutRenderabilityReason.XML_DICTIONARY_SOURCE_ABSENT
        return None
    if layout.format is not ExportLayoutFormat.FIXED_WIDTH:
        return ExportLayoutRenderabilityReason.UNSUPPORTED_LAYOUT_FORMAT
    if not layout.records:
        return ExportLayoutRenderabilityReason.NO_EXPORT_RECORDS
    return None


def export_layout_renderability_reason(
    modelo: str,
    layout: ExportLayoutDefinition | None,
) -> str | None:
    """Return why ``layout`` cannot currently produce local declaration bytes.

    Retained as a rendered projection of
    :func:`export_layout_renderability_reason_code` for consumers outside this
    package that place the sentence in an operator payload. Those consumers are
    the remaining reason this projection exists.
    """
    if layout is None:
        return "the registry snapshot has no complete export_layouts definition"
    code = export_layout_renderability_reason_code(layout)
    if code is None:
        return None
    if code is ExportLayoutRenderabilityReason.XML_DICTIONARY_SOURCE_ABSENT:
        return f"XML dictionary export layout {layout.id!r} declares no dictionary source"
    if code is ExportLayoutRenderabilityReason.UNSUPPORTED_LAYOUT_FORMAT:
        return f"export layout {layout.id!r} uses unsupported format {layout.format!r}"
    return f"export layout {layout.id!r} declares no export records"


def _export_layout_not_renderable_error(
    modelo: str,
    layout: ExportLayoutDefinition | None,
) -> FilingExportError:
    """Return the typed refusal for a layout that cannot render declaration bytes."""
    code = export_layout_renderability_reason_code(layout)
    assert code is not None
    context: dict[str, object] = {"modelo": modelo, "reason_code": code.value}
    if layout is not None:
        context["layout_id"] = layout.id
        context["layout_format"] = layout.format.value
    return FilingExportError(
        translated_message="application.filing.export.errors.layout_not_renderable",
        context=context,
    )


def _raise_if_export_layout_not_renderable(modelo: str, layout: ExportLayoutDefinition) -> None:
    if export_layout_renderability_reason_code(layout) is not None:
        raise _export_layout_not_renderable_error(modelo, layout)


def verify_export(
    draft: ModeloDraft,
    *,
    file_path: Path,
    schema_provider: RegistrySchemaAccessor | None = None,
) -> DeclaracionVerifyResult:
    """Verify a local export file against an approved :class:`ModeloDraft`.

    The verifier parses the file through the draft's active registry
    export layout and compares parser-covered casillas against the
    draft. ``MATCH`` means the covered casillas agree; it does not imply
    every draft casilla was present on the wire. Draft casillas outside
    parser coverage are reported in
    :attr:`DeclaracionVerifyResult.unchecked_casilla_ids`.

    Returns:
        A :class:`DeclaracionVerifyResult` with a closed
        :class:`DeclaracionVerifyVerdict`, file digest when available,
        mismatched casillas, unchecked casillas, and provenance.

    See Also:
        :func:`export_draft`
            Write the local fichero-BOE artefact being verified.
        :func:`domain.calculations.registry.parse_export_payload`
            Registry parser used to read the file.
    """
    provider = schema_provider or build_runtime_schema_provider(modelos=(draft.modelo,))
    subview = provider.get_subview(draft.modelo)
    _require_current_verify_schema(draft, subview)
    if not subview.export_layout_ids:
        return _missing_registry_layout_verification(draft, file_path)
    return _verify_export_file(draft, file_path=file_path, provider=provider, subview=subview)


def _require_current_verify_schema(draft: ModeloDraft, subview: RegistryModeloSubview) -> None:
    if draft.schema_version != subview.schema_version:
        raise FilingExportError(
            translated_message="application.filing.export.errors.verify_draft_snapshot_stale",
            context={
                "modelo": draft.modelo,
                "draft_schema_version": draft.schema_version,
                "active_schema_version": subview.schema_version,
            },
        )


def _missing_verification_result(
    draft: ModeloDraft,
    *,
    file_path: Path,
    narrative: str,
    digest: str | None = None,
) -> DeclaracionVerifyResult:
    return DeclaracionVerifyResult(
        draft_id=draft.draft_id,
        file_path=file_path,
        verdict=DeclaracionVerifyVerdict.MISSING,
        file_sha256=digest,
        verified_at=now(),
        narrative=narrative,
    )


def _missing_registry_layout_verification(draft: ModeloDraft, file_path: Path) -> DeclaracionVerifyResult:
    try:
        digest = sha256_file(file_path) if file_path.exists() else None
    except OSError:
        _logger.warning("declaration export verification could not read %s", file_path, exc_info=True)
        digest = None
    return _missing_verification_result(
        draft,
        file_path=file_path,
        narrative="filing.export.missing_registry_layout",
        digest=digest,
    )


def _read_verification_payload(file_path: Path) -> bytes | None:
    try:
        return file_path.read_bytes()
    except OSError:
        _logger.warning("declaration export verification could not read %s", file_path, exc_info=True)
        return None


def _verify_export_file(
    draft: ModeloDraft,
    *,
    file_path: Path,
    provider: RegistrySchemaAccessor,
    subview: RegistryModeloSubview,
) -> DeclaracionVerifyResult:
    if not file_path.exists():
        return _missing_verification_result(
            draft,
            file_path=file_path,
            narrative="filing.export.missing_file",
        )
    payload = _read_verification_payload(file_path)
    if payload is None:
        return _missing_verification_result(
            draft,
            file_path=file_path,
            narrative="filing.export.missing_file",
        )
    digest = sha256_hex(payload)
    try:
        mismatched, checked = _mismatched_casilla_ids(
            subview.export_layouts[0],
            draft=draft,
            payload=payload,
            schema_provider=provider,
        )
    except RegistryValidationError:
        _logger.warning("declaration export verification could not parse %s", file_path, exc_info=True)
        return _missing_verification_result(
            draft,
            file_path=file_path,
            narrative="filing.export.malformed_file",
            digest=digest,
        )
    # Draft casillas the export parser never re-read: the wire layout
    # carries them as RESERVED literals or derived fields, so they round-
    # trip outside the deserialised-currency set. Surface them as
    # ``unchecked_casilla_ids`` so the verdict is honest about its coverage —
    # a MATCH does not mean every draft casilla was confirmed on disk.
    checked_set = set(checked)
    unchecked = tuple(sorted(value.casilla_id for value in draft.values if value.casilla_id not in checked_set))
    # An XML declaration identifies itself in its root attributes, and the
    # casilla comparison above reads only element text. A file whose casillas
    # all agree but whose modelo, ejercicio, periodo or XSD version name a
    # different declaration is not the artefact this draft produced, so
    # comparing values alone certified it as a MATCH.
    try:
        mismatched_root = _mismatched_root_fields(
            subview.export_layouts[0],
            draft=draft,
            payload=payload,
            schema_provider=provider,
        )
    except FilingExportValidationError:
        _logger.warning("declaration export verification could not read root identity of %s", file_path, exc_info=True)
        return _missing_verification_result(
            draft,
            file_path=file_path,
            narrative="filing.export.malformed_file",
            digest=digest,
        )
    return DeclaracionVerifyResult(
        draft_id=draft.draft_id,
        file_path=file_path,
        verdict=(
            DeclaracionVerifyVerdict.MATCH if not mismatched and not mismatched_root else DeclaracionVerifyVerdict.DRIFT
        ),
        mismatched_casilla_ids=mismatched,
        unchecked_casilla_ids=unchecked,
        mismatched_root_fields=mismatched_root,
        casilla_provenance=_provenance_for_casillas(draft, checked),
        mismatched_casilla_provenance=_provenance_for_casillas(draft, mismatched),
        file_sha256=digest,
        verified_at=now(),
        narrative="filing.export.verified",
    )


def _verify_written_export(
    draft: ModeloDraft,
    *,
    file_path: Path,
    schema_provider: RegistrySchemaAccessor,
) -> None:
    """Fail closed unless the just-written declaration re-parses as a match.

    The output has already crossed the atomic-write boundary when this check
    runs. This function deliberately does not remove it: the draft-level writer
    has no deletion policy, while the work-unit writer owns a sibling ``.tmp``
    path and removes that path when this :class:`FilingExportError` propagates.

    Args:
        draft: Approved draft whose bytes were rendered.
        file_path: Exact artefact path written by :func:`export_draft`.
        schema_provider: The same registry snapshot used by the renderer.

    Raises:
        FilingExportError: The real parser cannot read the artefact back as a
            :attr:`DeclaracionVerifyVerdict.MATCH`.
    """
    verification = verify_export(
        draft,
        file_path=file_path,
        schema_provider=schema_provider,
    )
    if verification.verdict is DeclaracionVerifyVerdict.MATCH:
        return
    raise FilingExportError(
        translated_message="application.filing.export.errors.post_write_verification_refused",
        context={
            "artifact_path": str(file_path),
            "verdict": verification.verdict.value,
            "mismatched_casilla_ids": tuple(verification.mismatched_casilla_ids),
            "mismatched_root_fields": tuple(verification.mismatched_root_fields),
        },
    )


def _declaracion_export_format(layout: ExportLayoutDefinition) -> DeclaracionExportFormat:
    if layout.format is ExportLayoutFormat.XML_DICTIONARY:
        return DeclaracionExportFormat.XML_DICTIONARY
    return DeclaracionExportFormat.FICHERO_BOE


def _render_export_layout(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    dictionary_values: Mapping[str, object] | None,
    prior_domiciliation_election: PriorDomiciliationElection,
    product_software_identity: AeatProductSoftwareIdentity | None,
    schema_provider: RegistrySchemaAccessor,
    registry_snapshot: RegistrySnapshot,
) -> bytes:
    if layout.format is ExportLayoutFormat.XML_DICTIONARY:
        return render_xml_dictionary_layout(
            layout,
            draft=draft,
            headers=dict(headers),
            dictionary_values=dictionary_values,
            schema_provider=schema_provider,
        )
    return _render_layout(
        layout,
        registry_snapshot=registry_snapshot,
        draft=draft,
        headers=headers,
        producer_snapshot=producer_snapshot,
        prior_domiciliation_election=prior_domiciliation_election,
        product_software_identity=product_software_identity,
    )


def _render_layout(
    layout: ExportLayoutDefinition,
    *,
    registry_snapshot: RegistrySnapshot,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    prior_domiciliation_election: PriorDomiciliationElection,
    product_software_identity: AeatProductSoftwareIdentity | None,
) -> bytes:
    if (
        draft.modelo == Modelo.M303.value
        and producer_snapshot.elections.prior_domiciliation is not prior_domiciliation_election
    ):
        raise FilingExportValidationError(
            "M303 prior-domiciliation election must match the immutable producer snapshot election",
        )
    occurrences = _render_layout_occurrences(
        layout,
        registry_snapshot=registry_snapshot,
        draft=draft,
        headers=headers,
        producer_snapshot=producer_snapshot,
        prior_domiciliation_election=prior_domiciliation_election,
    )
    auxiliary_header = layout.auxiliary_envelope_header
    if auxiliary_header is None:
        return b"".join(occurrence.payload for occurrence in occurrences)
    if product_software_identity is None:
        raise FilingExportValidationError(
            "an auxiliary-envelope-header export requires explicit product/software identity authority",
        )
    prefix = _render_declared_prefix(
        auxiliary_header.prefix_fields,
        prefix_extent=auxiliary_header.prefix_extent,
        modelo=Modelo(draft.modelo),
        period=draft.period,
        product_software_identity=product_software_identity,
    )
    return prefix + b"".join(occurrence.payload for occurrence in occurrences)


def _render_layout_occurrences(
    layout: ExportLayoutDefinition,
    *,
    registry_snapshot: RegistrySnapshot,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    prior_domiciliation_election: PriorDomiciliationElection,
) -> tuple[_RenderedRecordOccurrence, ...]:
    """Derive one projection plan and render every applicable record occurrence.

    This is the sole application resolver bridge used by ordinary fixed-width
    exports and by the DP30300 envelope facade.  It intentionally accepts no
    caller-authored plan, member collection, field map, or bytes.
    """
    if not any(candidate is layout for candidate in registry_snapshot.revision.export_layouts):
        raise FilingExportValidationError("filing renderer layout is not owned by the selected registry snapshot")
    projection_plan = _projection_plan_for_layout(
        layout,
        registry_snapshot=registry_snapshot,
        draft=draft,
        producer_snapshot=producer_snapshot,
    )
    projection_values = _preflight_projection_plan(projection_plan)
    casilla_values: dict[CasillaId, object] = {value.casilla_id: value.value for value in draft.values}
    binding_values: dict[tuple[BindingId, int | None], object] = {
        (value.binding_id, value.row_index): value.value for value in draft.binding_values
    }
    return _render_layout_records(
        layout,
        registry_snapshot=registry_snapshot,
        draft=draft,
        headers=headers,
        producer_snapshot=producer_snapshot,
        prior_domiciliation_election=prior_domiciliation_election,
        casilla_values=casilla_values,
        binding_values=binding_values,
        projection_plan=projection_plan,
        projection_values=projection_values,
    )


def render_filing_envelope(request: FilingEnvelopeRenderRequest) -> FilingEnvelopeRenderResult:
    """Render one modelo's variable envelope from the closed, validated request."""
    envelope = request.layout.filing_envelope
    if envelope is None:  # The request validator makes this unreachable; retain type narrowing at the public boundary.
        raise FilingExportValidationError("filing-envelope layout declaration is absent")
    headers = _filing_producer_values(request.producer_snapshot)
    rendered_occurrences = _render_layout_occurrences(
        request.layout,
        registry_snapshot=request.registry_snapshot,
        draft=request.draft,
        headers=headers,
        producer_snapshot=request.producer_snapshot,
        prior_domiciliation_election=request.prior_domiciliation_election,
    )
    occurrences = tuple(
        FilingEnvelopeOccurrence(
            record_id=item.record_id,
            occurrence=item.occurrence,
            payload=item.payload,
            payload_sha256=sha256_hex(item.payload),
        )
        for item in rendered_occurrences
    )
    _require_envelope_required_occurrences(request.layout, occurrences)
    prefix = _render_declared_prefix(
        envelope.prefix_fields,
        prefix_extent=envelope.prefix_extent,
        modelo=request.modelo,
        period=request.draft.period,
        product_software_identity=request.product_software_identity,
    )
    closer = envelope_closer_bytes(modelo=request.modelo, period=request.draft.period)
    payload = prefix + b"".join(item.payload for item in occurrences) + closer
    return FilingEnvelopeRenderResult(
        draft_id=request.draft.draft_id,
        revision_id=str(request.registry_snapshot.revision.id),
        layout_id=str(request.layout.id),
        modelo=request.modelo,
        period=request.draft.period,
        envelope=envelope,
        occurrences=occurrences,
        prefix=prefix,
        closer=closer,
        payload=payload,
        payload_sha256=sha256_hex(payload),
        total_length=len(payload),
    )


def _require_envelope_required_occurrences(
    layout: ExportLayoutDefinition,
    occurrences: tuple[FilingEnvelopeOccurrence, ...],
) -> None:
    present = {item.record_id for item in occurrences}
    missing = tuple(str(record.id) for record in layout.records if record.required and record.id not in present)
    if missing:
        raise FilingExportValidationError(
            f"filing-envelope required record families have no emitted occurrence: {missing!r}",
        )


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
                f"filing-envelope occurrences for {item.record_id!r} must be positive, contiguous, and uncollapsed",
            )
        next_occurrence[item.record_id] = expected_occurrence + 1
        last_family = family


def _render_declared_prefix(
    prefix_fields: Sequence[FilingEnvelopePrefixFieldDeclaration],
    *,
    prefix_extent: int,
    modelo: Modelo,
    period: Period,
    product_software_identity: AeatProductSoftwareIdentity,
) -> bytes:
    """Derive a source-declared envelope prefix from filing-instance authority.

    The ONE renderer for both prefix shapes: the variable envelope's prefix and
    the total-less auxiliary header's, which share the same declared grammar.
    """
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
        raise FilingExportValidationError(
            f"envelope prefix must render to its declared {prefix_extent}-byte extent",
        )
    return prefix


def _envelope_prefix_role_value(
    role: FilingEnvelopePrefixRole,
    *,
    length: int,
    modelo: Modelo,
    period: Period,
    product_software_identity: AeatProductSoftwareIdentity,
) -> str:
    """Resolve one prefix role's emitted text from typed filing authority.

    Every role resolves from exactly one authority: AEAT grammar constants, the
    selected modelo, the filing period, the product/software identity, or the
    field's own declared width. A role with no resolution refuses by name rather
    than emitting a plausible blank, so a design carrying a role this renderer
    cannot ground is visible instead of silently mis-filed.
    """
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
                f"filing-envelope prefix role {role.value!r} has no declared value authority",
            )


def render_envelope_prefix_field(
    role: FilingEnvelopePrefixRole,
    *,
    length: int,
    modelo: Modelo,
    period: Period,
    product_software_identity: AeatProductSoftwareIdentity,
) -> bytes:
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
            f"filing-envelope prefix role {role.value!r} renders to {len(payload)} bytes, expected {length}",
        )
    return payload


def _projection_plan_for_layout(
    layout: ExportLayoutDefinition,
    *,
    registry_snapshot: RegistrySnapshot,
    draft: ModeloDraft,
    producer_snapshot: FilingProducerSnapshot,
) -> FilingProjectionPlan:
    if draft.modelo == Modelo.M303.value:
        return build_m303_filing_projection_plan(
            registry_snapshot=registry_snapshot,
            layout=layout,
            producer_snapshot=producer_snapshot,
        )
    if draft.modelo == Modelo.M200.value:
        return build_m200_filing_projection_plan(
            registry_snapshot=registry_snapshot,
            layout=layout,
            producer_snapshot=producer_snapshot,
        )
    if draft.modelo == Modelo.M296.value:
        return build_m296_filing_projection_plan(
            registry_snapshot=registry_snapshot,
            layout=layout,
            producer_snapshot=producer_snapshot,
        )
    return FilingProjectionPlan(contexts=(), values=())


def _mismatched_casilla_ids(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    payload: bytes,
    schema_provider: RegistrySchemaAccessor,
) -> tuple[tuple[CasillaId, ...], tuple[CasillaId, ...]]:
    values = {value.casilla_id: value.value for value in draft.values}
    fields_by_identity = {(record.id, field.id): field for record in layout.records for field in record.fields}
    mismatched: list[CasillaId] = []
    checked: list[CasillaId] = []
    for parsed in parse_export_payload(
        layout,
        payload,
        source_root=schema_provider.source_root,
        sources=schema_provider.sources,
    ).casillas:
        if parsed.casilla_id is None:
            continue
        checked.append(parsed.casilla_id)
        expected = values.get(parsed.casilla_id)
        try:
            field = fields_by_identity[(parsed.record_id, parsed.field_id)]
            expected_wire = render_fixed_width_export_field(field, expected)
        except (KeyError, RegistryValidationError) as exc:
            raise FilingExportValidationError(
                f"export field {parsed.field_id!r} could not render its expected verification value",
            ) from exc
        if expected_wire != parsed.raw:
            mismatched.append(parsed.casilla_id)
    return tuple(dict.fromkeys(mismatched)), tuple(dict.fromkeys(checked))


def _mismatched_root_fields(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    payload: bytes,
    schema_provider: RegistrySchemaAccessor,
) -> tuple[str, ...]:
    """Return the root identity attributes that disagree with ``draft``.

    Only an ``xml_dictionary`` layout carries a self-identifying root; a
    fixed-width record has no such header, so the comparison is empty there
    rather than vacuously true.

    The expected values are rebuilt through the same
    :func:`~application.filing._export_xml_dictionary.expected_xml_dictionary_root_identity`
    contract the writer uses, so a future attribute added to the root is
    compared automatically instead of silently going unchecked.
    """
    if layout.format is not ExportLayoutFormat.XML_DICTIONARY:
        return ()
    expected = expected_xml_dictionary_root_identity(
        layout,
        draft=draft,
        schema_provider=schema_provider,
    )
    actual = read_xml_dictionary_root_identity(payload)
    return tuple(
        sorted(name for name, value in expected.items() if actual.get(name) != value),
    )


def _provenance_for_casillas(
    draft: ModeloDraft,
    casilla_ids: Iterable[CasillaId],
) -> tuple[ModeloCasillaProvenance, ...]:
    provenance_by_id = {entry.casilla_id: entry for entry in draft.casilla_provenance}
    return tuple(
        provenance_by_id[casilla_id] for casilla_id in dict.fromkeys(casilla_ids) if casilla_id in provenance_by_id
    )


def _exported_casilla_provenance(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    schema_provider: RegistrySchemaAccessor,
) -> tuple[ModeloCasillaProvenance, ...]:
    if layout.format is ExportLayoutFormat.XML_DICTIONARY:
        entries = xml_dictionary_entries(
            layout,
            source_root=schema_provider.source_root,
            sources=schema_provider.sources,
        )
        draft_casillas = {value.casilla_id for value in draft.values}
        return _provenance_for_casillas(
            draft,
            (
                entry.casilla_id
                for entry in entries
                if entry.casilla_id is not None and entry.casilla_id in draft_casillas
            ),
        )
    draft_casillas = {value.casilla_id for value in draft.values}
    layout_casillas = (
        field.casilla_id
        for record in sorted(layout.records, key=lambda item: item.order)
        for field in record.fields
        if field.kind == CasillaFieldKind.CASILLA
        and field.casilla_id is not None
        and field.casilla_id in draft_casillas
    )
    return _provenance_for_casillas(draft, layout_casillas)


__all__ = [
    "DeclaracionExportFormat",
    "DeclaracionExportResult",
    "DeclaracionVerifyResult",
    "DeclaracionVerifyVerdict",
    "FilingExportConsumedResult",
    "FilingExportPayloadConsumer",
    "FilingExportValidatedPayload",
    "FilingProjectionValue",
    "FilingRecordRenderContext",
    "_RecordRenderRow",
    "_complementaria_page_marker",
    "_format_field",
    "_m303_complementaria_marker",
    "_m303_no_activity_marker",
    "_preflight_projection_plan",
    "_projection_field_value",
    "_render_record",
    "assert_export_artifact_matches_receipt",
    "export_draft",
    "verify_export",
]
