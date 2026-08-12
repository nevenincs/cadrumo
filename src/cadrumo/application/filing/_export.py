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
:class:`domain.modelos.CalculationRevision`, then delegates here to write
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

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import (
    CasillaId,
    ExportLayoutFormat,
    FilingProducerKey,
    FilingProjectionRef,
    Period,
    PriorDomiciliationElection,
    ProrrataEspecialTransitionKind,
)
from ...core.atomic_write import atomic_write_bytes
from ...core.decimal import coerce_decimal
from ...core.hashing import hash_file, sha256_file, sha256_hex
from ...core.logging import get_logger
from ...core.time import now
from ...domain.calculations.registry import (
    BindingId,
    CasillaFieldKind,
    ExportComputedKey,
    ExportDraftAttribute,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    RecordId,
    RegistrySnapshot,
    RegistryValidationError,
    export_fields_overlap,
    parse_export_payload,
    render_fixed_width_export_field,
    xml_dictionary_entries,
)
from ...domain.deadlines import M303RegimeComposition, M303TaxTerritory, ModeloIVAProfile
from ...domain.filing import (
    FilingExportError,
    FilingExportValidationError,
    ModeloCasillaProvenance,
    ModeloDraft,
)
from ...domain.iva import derive_sepa_marca, is_last_filing_period_of_year
from ...domain.submission import ModeloDraftStatus
from ._export_parity import (
    assert_export_mirrors_manifest,
    assert_rate_boxes_account_for_total,
    assert_xml_declaration_aux_declared,
    did_page_suppressed,
)
from ._export_xml_dictionary import (
    expected_xml_dictionary_root_identity,
    read_xml_dictionary_root_identity,
    render_xml_dictionary_layout,
)
from ._m303_export_applicability import validate_m303_export_applicability
from ._producer_snapshot import (
    ChargeAccountSelection,
    FilingProducerSnapshot,
    M303InsolvencyFilingSubtype,
    Modelo111ProfileFacts,
    RefundAccountSelection,
)
from ._projection import (
    FilingProjectionPlan,
    FilingProjectionValue,
    FilingRecordRenderContext,
    build_m303_filing_projection_plan,
)
from .runtime import RegistrySchemaAccessor, build_runtime_schema_provider

_logger = get_logger(__name__)

_SHA256_HEX_LENGTH = 64
"""Length of a hex-encoded SHA-256 digest used by export receipts."""


@dataclass(frozen=True)
class _RecordRenderRow:
    row_index: int | None
    active_binding_ids: frozenset[BindingId]


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
    file_sha256: str = Field(min_length=_SHA256_HEX_LENGTH, max_length=_SHA256_HEX_LENGTH)
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


def _filing_producer_values(snapshot: FilingProducerSnapshot) -> dict[FilingProducerKey, object]:
    """Resolve every canonical producer identity from one immutable snapshot."""
    identity = snapshot.taxpayer_identity
    amendment = snapshot.amendment_evidence
    iva_profile = snapshot.model_profile if isinstance(snapshot.model_profile, ModeloIVAProfile) else None
    m303_facts = snapshot.m303_filing_facts
    m303_period = m303_facts.period if m303_facts is not None else None
    m303_is_final_period = is_last_filing_period_of_year(m303_period) if m303_period is not None else False
    insolvency = m303_facts.insolvency if m303_facts is not None else None
    values: dict[FilingProducerKey, object] = {
        FilingProducerKey.PRESENTER_TAX_ID: str(snapshot.presenter.tax_id),
        FilingProducerKey.FILING_RESULT_DISPOSITION: snapshot.elections.result_disposition.value,
        FilingProducerKey.TAXPAYER_LEGAL_NAME: identity.legal_name,
        FilingProducerKey.TAXPAYER_GIVEN_NAME: identity.given_name,
        FilingProducerKey.TAXPAYER_SURNAMES: identity.surnames,
        FilingProducerKey.TAXPAYER_FULL_NAME: identity.full_name,
        FilingProducerKey.AMENDMENT_IS_RECTIFICATIVA: amendment.is_rectificativa if amendment else None,
        FilingProducerKey.AMENDMENT_IS_COMPLEMENTARIA: amendment.is_complementaria if amendment else None,
        FilingProducerKey.AMENDMENT_ORIGINAL_AEAT_RECEIPT: amendment.original_aeat_receipt if amendment else None,
        FilingProducerKey.SELECTED_ACCOUNT_IBAN: None,
        FilingProducerKey.SELECTED_ACCOUNT_SWIFT_BIC: None,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_NAME: None,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_ADDRESS: None,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_CITY: None,
        FilingProducerKey.SELECTED_ACCOUNT_BANK_COUNTRY_CODE: None,
        FilingProducerKey.PRIOR_DOMICILIATION_ACTION: (
            "X" if snapshot.elections.prior_domiciliation is PriorDomiciliationElection.CANCEL_OR_MODIFY else None
        ),
        FilingProducerKey.M303_REDEME_ENROLLED: (
            _m303_yes_no(iva_profile.redeme_enrolled) if iva_profile is not None else None
        ),
        FilingProducerKey.M303_EXCLUSIVELY_FORAL: (
            "1"
            if iva_profile is not None and iva_profile.tax_territory is M303TaxTerritory.FORAL
            else "2"
            if iva_profile is not None
            else None
        ),
        FilingProducerKey.M303_REGIME_COMPOSITION_CODE: (
            {
                M303RegimeComposition.SIMPLIFIED: "1",
                M303RegimeComposition.MIXED: "2",
                M303RegimeComposition.GENERAL: "3",
            }[iva_profile.regime_composition]
            if iva_profile is not None
            else None
        ),
        FilingProducerKey.M303_JOINT_RETURN_ELECTED: (
            _m303_yes_no(m303_facts.joint_return_elected) if m303_facts is not None else None
        ),
        FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED: (
            _m303_yes_no(iva_profile.cash_accounting_regime_enrolled) if iva_profile is not None else None
        ),
        FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS: (
            _m303_yes_no(m303_facts.supplier_regime.recipient_of_cash_accounting_operations)
            if m303_facts is not None
            else None
        ),
        FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION: (
            _m303_yes_no(m303_facts.prorrata_transition.transition is ProrrataEspecialTransitionKind.OPCION)
            if m303_facts is not None and m303_facts.prorrata_transition.is_applicable
            else None
        ),
        FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION: (
            _m303_yes_no(m303_facts.prorrata_transition.transition is ProrrataEspecialTransitionKind.REVOCACION)
            if m303_facts is not None and m303_facts.prorrata_transition.is_applicable
            else None
        ),
        FilingProducerKey.M303_INSOLVENCY_DECLARED: (
            "1" if insolvency is not None else "2" if m303_facts is not None else None
        ),
        FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE: (
            insolvency.judicial_order_date.strftime("%d%m%Y") if insolvency is not None else None
        ),
        FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE: (
            {
                M303InsolvencyFilingSubtype.PRE_ORDER: "1",
                M303InsolvencyFilingSubtype.POST_ORDER: "2",
            }[insolvency.subtype]
            if insolvency is not None
            else None
        ),
        FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED: (
            _m303_yes_no(iva_profile.voluntary_sii_enrolled) if iva_profile is not None else None
        ),
        FilingProducerKey.M303_EXONERADO_390_APPLICABLE: (
            _m303_yes_no(m303_facts.exonerado_390.applicable)
            if m303_facts is not None and m303_is_final_period
            else "0"
            if m303_facts is not None
            else None
        ),
        FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED: (
            _m303_yes_no(iva_profile.hydrocarbon_deposit_advance_payment_deduction_entitled)
            if iva_profile is not None and m303_period is not None and _m303_a30_entitlement_applicable(m303_period)
            else "0"
            if iva_profile is not None and m303_period is not None
            else None
        ),
        FilingProducerKey.M111_COLEGIO_CONCERTADO: (
            snapshot.model_profile.colegio_concertado
            if isinstance(snapshot.model_profile, Modelo111ProfileFacts)
            else None
        ),
    }
    selected = snapshot.selected_account
    if isinstance(selected, (ChargeAccountSelection, RefundAccountSelection)):
        values[FilingProducerKey.SELECTED_ACCOUNT_IBAN] = selected.account.iban
    if isinstance(selected, RefundAccountSelection):
        values.update(
            {
                FilingProducerKey.SELECTED_ACCOUNT_SWIFT_BIC: selected.account.swift_bic,
                FilingProducerKey.SELECTED_ACCOUNT_BANK_NAME: selected.account.bank_name,
                FilingProducerKey.SELECTED_ACCOUNT_BANK_ADDRESS: selected.account.bank_address,
                FilingProducerKey.SELECTED_ACCOUNT_BANK_CITY: selected.account.bank_city,
                FilingProducerKey.SELECTED_ACCOUNT_BANK_COUNTRY_CODE: selected.account.bank_country_code,
            },
        )
    if iva_profile is not None and iva_profile.tax_territory is M303TaxTerritory.FORAL:
        values.update(
            {
                FilingProducerKey.M303_REDEME_ENROLLED: "2",
                FilingProducerKey.M303_EXCLUSIVELY_FORAL: "1",
                FilingProducerKey.M303_REGIME_COMPOSITION_CODE: "3",
                FilingProducerKey.M303_JOINT_RETURN_ELECTED: "2",
                FilingProducerKey.M303_CASH_ACCOUNTING_REGIME_ENROLLED: "2",
                FilingProducerKey.M303_RECIPIENT_OF_CASH_ACCOUNTING_OPERATIONS: "2",
                FilingProducerKey.M303_PRORRATA_SPECIAL_OPTION: (
                    "2" if m303_facts is not None and m303_facts.prorrata_transition.is_applicable else None
                ),
                FilingProducerKey.M303_PRORRATA_SPECIAL_REVOCATION: (
                    "2" if m303_facts is not None and m303_facts.prorrata_transition.is_applicable else None
                ),
                FilingProducerKey.M303_INSOLVENCY_DECLARED: None,
                FilingProducerKey.M303_INSOLVENCY_JUDICIAL_ORDER_DATE: None,
                FilingProducerKey.M303_INSOLVENCY_FILING_SUBTYPE: None,
                FilingProducerKey.M303_VOLUNTARY_SII_ENROLLED: "2",
                FilingProducerKey.M303_EXONERADO_390_APPLICABLE: "2",
                FilingProducerKey.M303_HYDROCARBON_DEPOSIT_ADVANCE_PAYMENT_DEDUCTION_ENTITLED: "2",
            },
        )
    if set(values) != set(FilingProducerKey):
        raise FilingExportValidationError("filing producer resolver is not exhaustive")
    return values


def _m303_yes_no(value: bool) -> str:
    """Project DP30301's exact Num1 convention: 1 = SI, 2 = NO."""
    return "1" if value else "2"


def _m303_a30_entitlement_applicable(period: Period) -> bool:
    return period.registry_token.isdigit() and int(period.registry_token) >= 2


def export_draft(
    draft: ModeloDraft,
    *,
    output_path: Path,
    producer_snapshot: FilingProducerSnapshot,
    dictionary_values: Mapping[str, object] | None = None,
    prior_domiciliation_election: PriorDomiciliationElection = PriorDomiciliationElection.KEEP,
    schema_provider: RegistrySchemaAccessor | None = None,
) -> DeclaracionExportResult:
    """Write an approved draft to a local fichero-BOE file and return a receipt.

    The function selects the active registry
    :class:`~domain.calculations.registry.ExportLayoutDefinition`,
    renders its fixed-width records, writes only ``output_path``, and
    never contacts AEAT. Live submission is outside this surface and is
    refused by :class:`core.access_gate.LiveSubmitForbiddenError`.

    Args:
        draft: The :class:`ModeloDraft` to export; must be in ``APROBADO`` status.
        output_path: Destination path for the fichero-BOE bytes.
        producer_snapshot: Complete typed filing facts consumed by registry producers.
        dictionary_values: Optional values addressed by the dictionary field id
            AEAT declares for them, each still carrying its own Python type.
            Read only by the ``xml_dictionary`` renderer, which is the only
            format addressing fields that way; the fixed-width renderer resolves
            its fields from ``headers`` and the layout's record definitions.
        prior_domiciliation_election: Typed M303 page-three election used by
            the shared Nota-3 DID page predicate.
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
    provider = schema_provider or build_runtime_schema_provider(modelos=(draft.modelo,))
    subview = provider.get_subview(draft.modelo)
    registry_snapshot = provider.get_snapshot(draft.modelo)
    if draft.schema_version != subview.schema_version:
        raise FilingExportError("declaration export requires a draft built from the active registry snapshot")
    if draft.status is not ModeloDraftStatus.APROBADO:
        raise FilingExportError("declaration export requires an approved draft")
    if not subview.export_layout_ids:
        raise FilingExportError(_missing_export_layout_message(draft.modelo))
    layout = sorted(registry_snapshot.revision.export_layouts, key=lambda item: item.id)[0]
    if draft.modelo == "303":
        validate_m303_export_applicability(
            period=draft.period,
            registry_snapshot=registry_snapshot,
            layout=layout,
            producer_snapshot=producer_snapshot,
        )
    _raise_if_export_layout_not_renderable(draft.modelo, layout)
    if producer_snapshot.modelo.value != draft.modelo:
        raise FilingExportValidationError("filing producer snapshot modelo does not match draft")
    producer_values = _filing_producer_values(producer_snapshot)
    payload = _render_export_layout(
        layout,
        draft=draft,
        headers=producer_values,
        producer_snapshot=producer_snapshot,
        dictionary_values=dictionary_values,
        prior_domiciliation_election=prior_domiciliation_election,
        schema_provider=provider,
        registry_snapshot=registry_snapshot,
    )
    if not payload:
        raise FilingExportError(f"modelo {draft.modelo!r} export layout {layout.id!r} rendered an empty payload")
    casilla_provenance = _exported_casilla_provenance(layout, draft=draft, schema_provider=provider)
    # Unconditional, unlike the manifest gate below: a layout without a
    # completeness manifest still must not write a declaration missing its
    # mandatory identity block.
    assert_xml_declaration_aux_declared(layout)
    # Unconditional for the same reason, and transport-independent: a rate
    # breakdown that does not reach its own declared total is false in either
    # encoding, so this one is not scoped to the fixed-width blank-slot case
    # below.
    assert_rate_boxes_account_for_total(subview.rate_box_partitions, draft=draft)
    if subview.completeness_manifest is not None:
        assert_export_mirrors_manifest(
            layout,
            draft=draft,
            headers=producer_values,
            prior_domiciliation_election=prior_domiciliation_election,
            schema_provider=provider,
            manifest=subview.completeness_manifest,
            casilla_metadata=subview.casilla_record_metadata,
        )
    atomic_write_bytes(output_path, payload)
    digest = sha256_hex(payload)
    receipt = DeclaracionExportResult(
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        format=_declaracion_export_format(layout),
        output_path=output_path,
        byte_size=len(payload),
        file_sha256=digest,
        exported_at=now(),
        narrative="filing.export.written",
        casilla_provenance=casilla_provenance,
    )
    assert_export_artifact_matches_receipt(receipt, artifact_path=output_path)
    return receipt


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
            f"declaration export receipt names an unreadable artefact {str(artifact_path)!r}: {exc}",
        ) from exc
    if byte_size != receipt.byte_size:
        raise FilingExportError(
            f"declaration export receipt declares byte size {receipt.byte_size} "
            f"but artefact {str(artifact_path)!r} holds {byte_size} bytes",
        )
    if digest != receipt.file_sha256:
        raise FilingExportError(
            f"declaration export receipt declares sha256 {receipt.file_sha256} "
            f"but artefact {str(artifact_path)!r} hashes to {digest}",
        )


def export_layout_renderability_reason(
    modelo: str,
    layout: ExportLayoutDefinition | None,
) -> str | None:
    """Return why ``layout`` cannot currently produce local declaration bytes."""
    if layout is None:
        return "the registry snapshot has no complete export_layouts definition"
    if layout.format is ExportLayoutFormat.XML_DICTIONARY:
        if layout.dictionary_source_ref is None:
            return f"XML dictionary export layout {layout.id!r} declares no dictionary source"
        return None
    if layout.format is not ExportLayoutFormat.FIXED_WIDTH:
        return f"export layout {layout.id!r} uses unsupported format {layout.format!r}"
    if not layout.records:
        return f"export layout {layout.id!r} declares no export records"
    return None


def _raise_if_export_layout_not_renderable(modelo: str, layout: ExportLayoutDefinition) -> None:
    reason = export_layout_renderability_reason(modelo, layout)
    if reason is not None:
        raise FilingExportError(_export_layout_not_renderable_message(modelo, reason))


def _missing_export_layout_message(modelo: str) -> str:
    reason = export_layout_renderability_reason(modelo, None)
    assert reason is not None
    return _export_layout_not_renderable_message(modelo, reason)


def _export_layout_not_renderable_message(modelo: str, reason: str) -> str:
    return (
        f"modelo {modelo!r} local declaration export is unsupported: {reason}. "
        "Calculation, verification, and local filing surfaces may exist for this modelo, "
        "but this command cannot produce an AEAT-compatible export file and does not certify legal correctness."
    )


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
    if draft.schema_version != subview.schema_version:
        raise FilingExportError("declaration verify requires a draft built from the active registry snapshot")
    if not subview.export_layout_ids:
        digest = sha256_file(file_path) if file_path.exists() else None
        return DeclaracionVerifyResult(
            draft_id=draft.draft_id,
            file_path=file_path,
            verdict=DeclaracionVerifyVerdict.MISSING,
            file_sha256=digest,
            verified_at=now(),
            narrative="filing.export.missing_registry_layout",
        )
    if not file_path.exists():
        return DeclaracionVerifyResult(
            draft_id=draft.draft_id,
            file_path=file_path,
            verdict=DeclaracionVerifyVerdict.MISSING,
            verified_at=now(),
            narrative="filing.export.missing_file",
        )
    payload = file_path.read_bytes()
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
        return DeclaracionVerifyResult(
            draft_id=draft.draft_id,
            file_path=file_path,
            verdict=DeclaracionVerifyVerdict.MISSING,
            file_sha256=digest,
            verified_at=now(),
            narrative="filing.export.malformed_file",
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
        return DeclaracionVerifyResult(
            draft_id=draft.draft_id,
            file_path=file_path,
            verdict=DeclaracionVerifyVerdict.MISSING,
            file_sha256=digest,
            verified_at=now(),
            narrative="filing.export.malformed_file",
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
    )


def _render_layout(
    layout: ExportLayoutDefinition,
    *,
    registry_snapshot: RegistrySnapshot,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    prior_domiciliation_election: PriorDomiciliationElection = PriorDomiciliationElection.KEEP,
) -> bytes:
    if not any(candidate is layout for candidate in registry_snapshot.revision.export_layouts):
        raise FilingExportValidationError("filing renderer layout is not owned by the selected registry snapshot")
    projection_plan = (
        build_m303_filing_projection_plan(
            registry_snapshot=registry_snapshot,
            layout=layout,
            producer_snapshot=producer_snapshot,
        )
        if draft.modelo == "303"
        else FilingProjectionPlan(contexts=(), values=())
    )
    projection_values = _preflight_projection_plan(projection_plan)
    chunks: list[bytes] = []
    casilla_values: dict[CasillaId, object] = {value.casilla_id: value.value for value in draft.values}
    binding_values: dict[tuple[BindingId, int | None], object] = {
        (value.binding_id, value.row_index): value.value for value in draft.binding_values
    }
    for record in sorted(layout.records, key=lambda item: item.order):
        if did_page_suppressed(
            record,
            draft=draft,
            headers=headers,
            prior_domiciliation_election=prior_domiciliation_election,
        ):
            continue
        if record.repeat == "projection_rows":
            render_rows = tuple(
                (_RecordRenderRow(row_index=None, active_binding_ids=frozenset()), context)
                for context in projection_plan.contexts
                if context.record is record
            )
        else:
            render_rows = tuple(
                (
                    row,
                    FilingRecordRenderContext(
                        registry_snapshot=registry_snapshot,
                        layout=layout,
                        record=record,
                        occurrence=occurrence,
                    ),
                )
                for occurrence, row in enumerate(_record_render_rows(record, binding_values), 1)
            )
        for row, context in render_rows:
            _guard_record_export(record, casilla_values=casilla_values)
            text = _render_record(
                record,
                draft=draft,
                producer_values=headers,
                producer_snapshot=producer_snapshot,
                casilla_values=casilla_values,
                binding_values=binding_values,
                row=row,
                render_context=context,
                projection_values=projection_values,
            )
            if record.line_ending == "crlf":
                text += "\r\n"
            elif record.line_ending == "lf":
                text += "\n"
            chunks.append(text.encode(record.encoding))
    return b"".join(chunks)


def _record_render_rows(
    record: ExportRecordDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
) -> tuple[_RecordRenderRow, ...]:
    if record.repeat != "binding_rows":
        if record.binding_record is not None and not _record_has_binding_value(record, binding_values):
            return ()
        return (_RecordRenderRow(row_index=None, active_binding_ids=frozenset()),)
    binding_fields = _record_binding_fields(record)
    row_indexes = sorted(
        {
            row_index
            for binding_id, row_index in binding_values
            if row_index is not None
            and any(field.binding == binding_id for field in binding_fields)
            and _is_active_binding_value(binding_values[(binding_id, row_index)])
        },
    )
    rows: list[_RecordRenderRow] = []
    for row_index in row_indexes:
        active_fields = tuple(
            field
            for field in binding_fields
            if field.binding is not None and _is_active_binding_value(binding_values.get((field.binding, row_index)))
        )
        for group in _compatible_binding_field_groups(active_fields):
            rows.append(
                _RecordRenderRow(
                    row_index=row_index,
                    active_binding_ids=frozenset(field.binding for field in group if field.binding is not None),
                ),
            )
    return tuple(rows)


type _ProjectionAddress = tuple[RecordId, int, FilingProjectionRef]


def _preflight_projection_plan(plan: FilingProjectionPlan) -> dict[_ProjectionAddress, object]:
    """Prove an exact admitted/produced projection bijection before any bytes."""
    context_addresses = tuple((context.record.id, context.occurrence) for context in plan.contexts)
    duplicate_contexts = tuple(address for address, count in Counter(context_addresses).items() if count > 1)
    if duplicate_contexts:
        raise FilingExportValidationError(
            f"filing projection plan contains duplicate record occurrences: {duplicate_contexts!r}",
        )
    expected_fields: dict[_ProjectionAddress, ExportFieldDefinition] = {}
    for context in plan.contexts:
        for field in context.record.fields:
            if field.kind is not CasillaFieldKind.PROJECTION or field.projection_ref is None:
                continue
            address = (context.record.id, context.occurrence, field.projection_ref)
            if address in expected_fields:
                raise FilingExportValidationError(f"filing layout admits duplicate projection address {address!r}")
            expected_fields[address] = field
    produced_addresses = tuple((value.record_id, value.occurrence, value.projection_ref) for value in plan.values)
    duplicate_values = tuple(address for address, count in Counter(produced_addresses).items() if count > 1)
    if duplicate_values:
        raise FilingExportValidationError(
            f"filing projectors produced duplicate projection addresses: {duplicate_values!r}",
        )
    expected = frozenset(expected_fields)
    actual = frozenset(produced_addresses)
    if actual != expected:
        missing = tuple(sorted(repr(address) for address in expected - actual))
        extraneous = tuple(sorted(repr(address) for address in actual - expected))
        raise FilingExportValidationError(
            f"filing projection plan is not an exact layout bijection; missing={missing!r}, extraneous={extraneous!r}",
        )
    values: dict[_ProjectionAddress, object] = {
        address: value.value for address, value in zip(produced_addresses, plan.values, strict=True)
    }
    for address, field in expected_fields.items():
        _format_field(field, values[address])
    return values


def _record_binding_fields(record: ExportRecordDefinition) -> tuple[ExportFieldDefinition, ...]:
    return tuple(
        field for field in record.fields if field.kind == CasillaFieldKind.BINDING and field.binding is not None
    )


def _is_active_binding_value(value: object) -> bool:
    return value is not None and value != ""


def _compatible_binding_field_groups(
    fields: tuple[ExportFieldDefinition, ...],
) -> tuple[tuple[ExportFieldDefinition, ...], ...]:
    groups: list[list[ExportFieldDefinition]] = []
    for field in sorted(fields, key=lambda item: (item.offset or 0, str(item.id))):
        for group in groups:
            if not any(export_fields_overlap(field, existing) for existing in group):
                group.append(field)
                break
        else:
            groups.append([field])
    return tuple(tuple(group) for group in groups)


def _record_has_binding_value(
    record: ExportRecordDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
) -> bool:
    binding_ids = {field.binding for field in _record_binding_fields(record)}
    return any(
        binding_id in binding_ids and value not in {None, ""} for (binding_id, _), value in binding_values.items()
    )


def _guard_record_export(record: ExportRecordDefinition, *, casilla_values: dict[CasillaId, object]) -> None:
    if record.requires_positive_casilla_id is None:
        return
    raw = casilla_values.get(record.requires_positive_casilla_id)
    amount = coerce_decimal(raw, default=Decimal("0")) or Decimal("0")
    if amount <= 0:
        raise FilingExportValidationError(
            f"export record {record.id!r} requires positive casilla {record.requires_positive_casilla_id!r}",
        )


def _render_record(
    record: ExportRecordDefinition,
    *,
    draft: ModeloDraft,
    producer_values: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row: _RecordRenderRow,
    render_context: FilingRecordRenderContext,
    projection_values: Mapping[_ProjectionAddress, object],
) -> str:
    positioned = all(field.offset is not None for field in record.fields)
    if not positioned:
        return "".join(
            _render_field(
                field,
                draft=draft,
                headers=producer_values,
                producer_snapshot=producer_snapshot,
                casilla_values=casilla_values,
                binding_values=binding_values,
                row_index=row.row_index,
                render_context=render_context,
                projection_values=projection_values,
            )
            for field in record.fields
            if _field_is_active_for_row(field, row)
        )
    length = max((field.offset or 0) + (field.length or 0) - 1 for field in record.fields)
    buffer = [" "] * length
    for field in sorted(record.fields, key=lambda item: item.offset or 0):
        if not _field_is_active_for_row(field, row):
            continue
        if field.offset is None:
            raise FilingExportValidationError(f"export field {field.id!r} must declare offset")
        rendered = _render_field(
            field,
            draft=draft,
            headers=producer_values,
            producer_snapshot=producer_snapshot,
            casilla_values=casilla_values,
            binding_values=binding_values,
            row_index=row.row_index,
            render_context=render_context,
            projection_values=projection_values,
        )
        start = field.offset - 1
        end = start + len(rendered)
        if any(char != " " for char in buffer[start:end]):
            raise FilingExportError(f"export field {field.id!r} overlaps another field")
        buffer[start:end] = rendered
    return "".join(buffer)


def _field_is_active_for_row(field: ExportFieldDefinition, row: _RecordRenderRow) -> bool:
    if not row.active_binding_ids:
        return True
    if field.kind != CasillaFieldKind.BINDING:
        return True
    return field.binding in row.active_binding_ids


def _render_field(
    field: ExportFieldDefinition,
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row_index: int | None,
    render_context: FilingRecordRenderContext,
    projection_values: Mapping[_ProjectionAddress, object],
) -> str:
    if field.length is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare length")
    raw = _field_value(
        field,
        draft=draft,
        headers=headers,
        producer_snapshot=producer_snapshot,
        casilla_values=casilla_values,
        binding_values=binding_values,
        row_index=row_index,
        render_context=render_context,
        projection_values=projection_values,
    )
    return _format_field(field, raw)


def _field_value(
    field: ExportFieldDefinition,
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    casilla_values: dict[CasillaId, object],
    binding_values: dict[tuple[BindingId, int | None], object],
    row_index: int | None,
    render_context: FilingRecordRenderContext,
    projection_values: Mapping[_ProjectionAddress, object],
) -> object:
    match field.kind:
        case CasillaFieldKind.LITERAL:
            return field.literal
        case CasillaFieldKind.FILLER:
            return ""
        case CasillaFieldKind.CASILLA:
            return _casilla_field_value(field, casilla_values)
        case CasillaFieldKind.BINDING:
            return _binding_field_value(field, binding_values, row_index)
        case CasillaFieldKind.HEADER:
            return _header_field_value(field, headers)
        case CasillaFieldKind.PROJECTION:
            return _projection_field_value(field, render_context, projection_values)
        case CasillaFieldKind.DRAFT:
            return _draft_value(field, draft)
        case CasillaFieldKind.COMPUTED:
            return _computed_field_value(field, draft, producer_snapshot)
        case _:
            raise FilingExportError(f"unsupported export field kind {field.kind!r}")


def _casilla_field_value(field: ExportFieldDefinition, casilla_values: dict[CasillaId, object]) -> object:
    if field.casilla_id is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare casilla_id")
    return casilla_values.get(field.casilla_id)


def _binding_field_value(
    field: ExportFieldDefinition,
    binding_values: dict[tuple[BindingId, int | None], object],
    row_index: int | None,
) -> object:
    if field.binding is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare binding")
    return binding_values.get((field.binding, row_index))


def _projection_field_value(
    field: ExportFieldDefinition,
    context: FilingRecordRenderContext,
    values: Mapping[_ProjectionAddress, object],
) -> object:
    if field.projection_ref is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare projection_ref")
    address = (context.record.id, context.occurrence, field.projection_ref)
    try:
        return values[address]
    except KeyError as exc:
        raise FilingExportValidationError(f"export projection address {address!r} has no preflighted value") from exc


def _header_field_value(field: ExportFieldDefinition, headers: Mapping[FilingProducerKey, object]) -> object:
    if field.producer_key is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare producer_key")
    value = headers.get(field.producer_key)
    if field.required and (value is None or (isinstance(value, str) and not value.strip())):
        raise FilingExportValidationError(f"export producer {field.producer_key!r} is required")
    return value.strip() if isinstance(value, str) else value


def _envelope_closing_tag(draft: ModeloDraft, snapshot: FilingProducerSnapshot) -> str:
    del snapshot
    year = str(draft.period.filing_year)
    period_code = draft.period.registry_token
    return f"</T{draft.modelo}0{year}{period_code}0000>"


def _draft_filing_year(draft: ModeloDraft) -> str:
    return str(draft.period.filing_year)


def _draft_period_code(draft: ModeloDraft) -> str:
    return draft.period.registry_token


def _draft_period_start_date(draft: ModeloDraft) -> str:
    return draft.period.start_date.strftime("%d%m%Y")


def _draft_period_end_date(draft: ModeloDraft) -> str:
    return draft.period.end_date.strftime("%d%m%Y")


def _sepa_marca(draft: ModeloDraft, snapshot: FilingProducerSnapshot) -> str | None:
    del draft
    selected = snapshot.selected_account
    if isinstance(selected, ChargeAccountSelection):
        return None
    if not isinstance(selected, RefundAccountSelection):
        raise FilingExportValidationError("SEPA marker requires a selected refund account")
    return derive_sepa_marca(
        iban=selected.account.iban,
        bank_country_code=selected.account.bank_country_code,
    ).value


_COMPUTED_VALUE_PRODUCERS: Mapping[
    ExportComputedKey,
    Callable[[ModeloDraft, FilingProducerSnapshot], str | None],
] = {
    ExportComputedKey.ENVELOPE_CLOSING_TAG: _envelope_closing_tag,
    ExportComputedKey.SEPA_MARCA: _sepa_marca,
}

_DRAFT_VALUE_PRODUCERS: Mapping[ExportDraftAttribute, Callable[[ModeloDraft], str]] = {
    ExportDraftAttribute.FILING_YEAR: _draft_filing_year,
    ExportDraftAttribute.PERIOD_CODE: _draft_period_code,
    ExportDraftAttribute.PERIOD_START_DATE: _draft_period_start_date,
    ExportDraftAttribute.PERIOD_END_DATE: _draft_period_end_date,
}


def _computed_field_value(
    field: ExportFieldDefinition,
    draft: ModeloDraft,
    producer_snapshot: FilingProducerSnapshot,
) -> str | None:
    if field.computed_key is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare computed_key")
    return _COMPUTED_VALUE_PRODUCERS[field.computed_key](draft, producer_snapshot)


def _draft_value(field: ExportFieldDefinition, draft: ModeloDraft) -> str:
    if field.draft_attribute is None:
        raise FilingExportValidationError(f"export field {field.id!r} must declare draft_attribute")
    return _DRAFT_VALUE_PRODUCERS[field.draft_attribute](draft)


def _format_field(field: ExportFieldDefinition, value: object) -> str:
    try:
        return render_fixed_width_export_field(field, value)
    except RegistryValidationError as exc:
        raise FilingExportValidationError(f"export field {field.id!r} cannot render its fixed-width value") from exc


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
    "FilingProjectionValue",
    "FilingRecordRenderContext",
    "assert_export_artifact_matches_receipt",
    "export_draft",
    "verify_export",
]
