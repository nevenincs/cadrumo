"""Typed records for the local declaration export / verify lifecycle.

The CLI exposes two primitives the application layer must back end-to-end:

- modelo export writes an
  AEAT declaration file from a validated registry snapshot for an approved
  :class:`domain.filing.schema.ModeloDraft` and reports the byte-level
  summary the operator needs to track the artefact (output path, draft
  identity, content hash, format).
- modelo export verification re-reads a previously
  exported file and confirms that its casilla payload still matches
  the approved draft. The verdict is a closed enum; the diff (if any)
  is reported as a tuple of mismatched casilla identifiers so the CLI
  can render a deterministic table.

The records are structured return values for renderers, persistence, and
JSON round trips. Runtime export requires registry-backed
:class:`domain.calculations.registry.schema_exports.ExportLayoutDefinition` records,
and verification parses payloads through
:func:`domain.calculations.registry.export_parse.parse_export_payload`.

The records intentionally do not embed the AEAT submission lifecycle
(:mod:`domain.submission`) — local export and live submit are
separate concerns and live submit is permanently forbidden.

This module is the draft-level renderer. The work-unit export service in
:mod:`application.modelo.export` rebuilds an approved
:class:`domain.filing.schema.ModeloDraft` from a
:class:`~CalculationRevision`, then delegates here to write
and verify the fichero-BOE bytes.

See Also:
    :func:`application.modelo.export.export_modelo_revision`
        Higher-level work-unit export service that replays a calculation
        revision before calling this draft renderer.
    :mod:`adapters.outbound.aeat.export`
        Outbound export-format adapter errors and fixed-width helper
        namespace.
    :class:`core.access_gate.errors.LiveSubmitForbiddenError`
        Core refusal raised for every attempted live AEAT write.
    :mod:`domain.submission`
        Local-only submitted-state lifecycle, separate from file export.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import overload

from ...core.atomic_write import atomic_write_bytes
from ...core.casilla_id import CasillaId
from ...core.export_layout_format import ExportLayoutFormat
from ...core.filing_producer_key import FilingProducerKey
from ...core.hashing import sha256_hex
from ...core.modelo import Modelo
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.time.clock import now
from ...domain.calculations.registry.export_shared_owner import canonical_export_layout
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import (
    BindingId,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_exports import (
    ExportLayoutDefinition,
)
from ...domain.filing.errors import (
    FilingExportDesignIntegrityError,
    FilingExportError,
    FilingExportIntegrityError,
    FilingExportValidationError,
)
from ...domain.filing.schema import ModeloCasillaProvenance, ModeloDraft
from ...domain.filing.software_identity import AeatProductSoftwareIdentity, aeat_aux_version
from ...domain.submission.models import ModeloDraftStatus
from .envelope_modelo_policy import filing_envelope_modelo_policy
from .export_envelope import (
    FilingEnvelopeOccurrence,
    FilingEnvelopeRenderRequest,
    FilingEnvelopeRenderResult,
    assemble_filing_envelope_payload,
    envelope_closer_bytes,
    render_declared_prefix,
)
from .export_parity import (
    assert_export_mirrors_manifest,
    assert_rate_boxes_account_for_total,
    assert_xml_declaration_aux_declared,
)
from .export_producer import filing_producer_values
from .export_producer_supply import require_supplied_producers
from .export_refusal_doors import ExportRefusalReason, export_design_terminal, export_input_decision
from .export_verification import (
    DeclaracionExportFormat,
    DeclaracionExportResult,
    FilingExportConsumedResult,
    FilingExportPayloadConsumer,
    FilingExportValidatedPayload,
    assert_export_artifact_matches_receipt,
    exported_casilla_provenance,
    verify_written_export,
)
from .export_xml_dictionary import refuse_incomplete_xml_dictionary_payload, render_xml_dictionary_layout
from .m200_projection import build_m200_filing_projection_plan
from .m296_projection import build_m296_filing_projection_plan
from .producer_snapshot import (
    FilingProducerSnapshot,
)
from .projection import (
    FilingProjectionPlan,
    FilingProjectionValue,
    FilingRecordRenderContext,
    build_m303_filing_projection_plan,
)
from .record_renderer import preflight_projection_plan, render_layout_records
from .record_types import RecordRenderRow, RenderedRecordOccurrence
from .runtime import RegistryModeloSubview, RegistrySchemaAccessor, build_runtime_schema_provider
from .shared_owner_refusal import refuse_written_shared_owners


@dataclass(frozen=True, slots=True)
class _PreparedExportDraft:
    provider: RegistrySchemaAccessor
    subview: RegistryModeloSubview
    registry_snapshot: RegistrySnapshot
    layout: ExportLayoutDefinition
    producer_values: Mapping[FilingProducerKey, object]
    prior_domiciliation_election: PriorDomiciliationElection
    renders_filing_envelope: bool
    xml_aux_version: str | None


def _require_current_export_schema(draft: ModeloDraft, subview: RegistryModeloSubview) -> None:
    if draft.schema_version != subview.schema_version:
        raise FilingExportIntegrityError(
            translated_message="errors.integrity.filing_export_draft_schema_mismatch",
            context={
                "modelo": draft.modelo,
                "draft_schema_version": draft.schema_version,
                "active_schema_version": subview.schema_version,
            },
        )


def _require_approved_export_draft(draft: ModeloDraft) -> None:
    if draft.status is not ModeloDraftStatus.APROBADO:
        raise FilingExportIntegrityError(
            translated_message="errors.integrity.filing_export_draft_unapproved",
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
        raise export_layout_not_renderable_error(draft.modelo, None)
    layout = canonical_export_layout(registry_snapshot.revision.export_layouts)
    if layout is None:
        raise export_layout_not_renderable_error(draft.modelo, None)
    _raise_if_export_layout_not_renderable(draft.modelo, layout)
    return layout


def _validate_export_options(
    *,
    modelo: Modelo,
    renders_filing_envelope: bool,
    renders_auxiliary_header: bool,
    requires_product_identity: bool,
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
        _require_identity_absent_without_prefix(product_software_identity)
        return _resolved_prior_domiciliation_election(prior_domiciliation_election)
    _validate_envelope_prefix_options(
        modelo=modelo,
        requires_product_identity=requires_product_identity,
        dictionary_values=dictionary_values,
        prior_domiciliation_election=prior_domiciliation_election,
        product_software_identity=product_software_identity,
    )
    return _resolved_prior_domiciliation_election(prior_domiciliation_election)


def _require_identity_absent_without_prefix(product_software_identity: AeatProductSoftwareIdentity | None) -> None:
    if product_software_identity is not None:
        raise FilingExportValidationError(
            "product/software identity is only admitted for a layout that renders an envelope prefix",
            translated_message="application.filing.export.errors.product_identity_not_admitted",
            precondition_verdict=export_design_terminal(ExportRefusalReason.ENVELOPE_OPTION_UNADMITTED),
        )


def _validate_envelope_prefix_options(
    *,
    modelo: Modelo,
    requires_product_identity: bool,
    dictionary_values: Mapping[str, object] | None,
    prior_domiciliation_election: PriorDomiciliationElection | None,
    product_software_identity: AeatProductSoftwareIdentity | None,
) -> None:
    _validate_envelope_identity_option(requires_product_identity, product_software_identity)
    if dictionary_values is not None:
        raise FilingExportValidationError(
            "an envelope-prefix export does not admit XML dictionary values",
            translated_message="application.filing.export.errors.dictionary_values_not_admitted",
            precondition_verdict=export_design_terminal(ExportRefusalReason.ENVELOPE_OPTION_UNADMITTED),
        )
    if (
        filing_envelope_modelo_policy(modelo).requiresprior_domiciliation_election
        and prior_domiciliation_election is None
    ):
        raise FilingExportValidationError(
            f"Modelo {modelo.value} export requires an explicit prior-domiciliation election",
            translated_message="application.filing.export.errors.prior_domiciliation_election_required",
            context={"modelo": modelo.value},
            precondition_verdict=export_input_decision(ExportRefusalReason.PRIOR_DOMICILIATION_ELECTION_UNSTATED),
        )


def _validate_envelope_identity_option(
    requires_product_identity: bool,
    product_software_identity: AeatProductSoftwareIdentity | None,
) -> None:
    if requires_product_identity and product_software_identity is None:
        raise FilingExportValidationError(
            "an envelope-prefix export requires explicit product/software identity authority",
            translated_message="application.filing.export.errors.product_identity_required",
            precondition_verdict=export_design_terminal(ExportRefusalReason.PRODUCT_IDENTITY_UNSUPPLIED),
        )
    if not requires_product_identity and product_software_identity is not None:
        raise FilingExportValidationError(
            "this envelope source declares no product/software identity slot",
            translated_message="application.filing.export.errors.product_identity_not_admitted",
            precondition_verdict=export_design_terminal(ExportRefusalReason.ENVELOPE_OPTION_UNADMITTED),
        )


def _resolved_prior_domiciliation_election(
    election: PriorDomiciliationElection | None,
) -> PriorDomiciliationElection:
    return election or PriorDomiciliationElection.KEEP


def _prepare_export_draft(
    draft: ModeloDraft,
    *,
    producer_snapshot: FilingProducerSnapshot,
    dictionary_values: Mapping[str, object] | None,
    prior_domiciliation_election: PriorDomiciliationElection | None,
    product_software_identity: AeatProductSoftwareIdentity | None,
    schema_provider: RegistrySchemaAccessor | None,
) -> _PreparedExportDraft:
    provider = schema_provider or build_runtime_schema_provider(
        modelos=(draft.modelo,),
        filing_year=draft.period.filing_year,
        period=draft.period,
    )
    subview = provider.get_subview(draft.modelo)
    registry_snapshot = provider.get_snapshot(draft.modelo)
    _require_current_export_schema(draft, subview)
    _require_approved_export_draft(draft)
    layout = _select_export_layout(draft, subview=subview, registry_snapshot=registry_snapshot)
    renders_filing_envelope = layout.filing_envelope is not None
    renders_auxiliary_header = layout.auxiliary_envelope_header is not None
    resolvedprior_domiciliation_election = _validate_export_options(
        modelo=Modelo(draft.modelo),
        renders_filing_envelope=renders_filing_envelope,
        renders_auxiliary_header=renders_auxiliary_header,
        requires_product_identity=(
            renders_auxiliary_header
            or (layout.filing_envelope is not None and layout.filing_envelope.product_identity_requirement is not None)
        ),
        dictionary_values=dictionary_values,
        prior_domiciliation_election=prior_domiciliation_election,
        product_software_identity=product_software_identity,
    )
    if producer_snapshot.modelo.value != draft.modelo:
        raise FilingExportDesignIntegrityError(
            "filing producer snapshot modelo does not match draft",
            translated_message="errors.integrity.filing_export_producer_snapshot_modelo_mismatch",
        )
    producer_values = filing_producer_values(producer_snapshot)
    require_supplied_producers(layout, producer_values, modelo=draft.modelo)
    return _PreparedExportDraft(
        provider=provider,
        subview=subview,
        registry_snapshot=registry_snapshot,
        layout=layout,
        producer_values=producer_values,
        prior_domiciliation_election=resolvedprior_domiciliation_election,
        renders_filing_envelope=renders_filing_envelope,
        xml_aux_version=aeat_aux_version() if layout.format is ExportLayoutFormat.XML_DICTIONARY else None,
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
        if prior_domiciliation_election is None:
            raise FilingExportIntegrityError(
                "a filing envelope renders only with a resolved prior domiciliation election",
                translated_message="errors.integrity.filing_export_envelope_election_unresolved",
            )
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
    return render_export_layout(
        prepared.layout,
        draft=draft,
        headers=prepared.producer_values,
        producer_snapshot=producer_snapshot,
        dictionary_values=dictionary_values,
        prior_domiciliation_election=prepared.prior_domiciliation_election,
        product_software_identity=product_software_identity,
        xml_aux_version=prepared.xml_aux_version,
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
        raise FilingExportIntegrityError(
            translated_message="application.filing.export.errors.rendered_payload_empty",
            context={
                "modelo": draft.modelo,
                "layout_id": prepared.layout.id,
                "layout_format": prepared.layout.format.value,
            },
        )
    casilla_provenance = exported_casilla_provenance(
        prepared.layout,
        draft=draft,
        schema_provider=prepared.provider,
    )
    if prepared.layout.format is ExportLayoutFormat.XML_DICTIONARY:
        if prepared.xml_aux_version is None:
            raise FilingExportIntegrityError(
                "XML dictionary export did not resolve its mandatory Aux/VERSION token",
                translated_message="errors.integrity.filing_export_xml_version_token_unresolved",
            )
        assert_xml_declaration_aux_declared(prepared.layout, aux_version=prepared.xml_aux_version)
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
    mutation_writer: Callable[[Callable[[], None]], None] | None = None,
) -> DeclaracionExportResult:
    if mutation_writer is None:
        atomic_write_bytes(output_path, payload)
    else:
        mutation_writer(lambda: atomic_write_bytes(output_path, payload))
    if not prepared.renders_filing_envelope:
        verify_written_export(
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
    mutation_writer: Callable[[Callable[[], None]], None] | None = None,
    states_whole_return: bool = False,
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
    mutation_writer: Callable[[Callable[[], None]], None] | None = None,
    states_whole_return: bool = False,
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
    mutation_writer: Callable[[Callable[[], None]], None] | None = None,
    states_whole_return: bool = False,
) -> DeclaracionExportResult | FilingExportConsumedResult:
    """Write an approved draft to a local fichero-BOE file and return a receipt.

    The function selects the active registry
    :class:`~domain.calculations.registry.schema_exports.ExportLayoutDefinition`,
    renders its fixed-width records, writes only ``output_path``, and
    never contacts AEAT. Live submission is outside this surface and is
    refused by :class:`core.access_gate.errors.LiveSubmitForbiddenError`.

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
        mutation_writer: Admit the actual atomic file write after rendering and validation.
        states_whole_return: The payload is a filer's whole return, so it is held to the
            required content of its official schema before reaching either destination.
            A bare draft render states only part of one and is judged on its values alone.

    Returns:
        A :class:`DeclaracionExportResult` with the output path, digest,
        byte size, and casilla provenance for the exported declaration.

    See Also:
        :func:`verify_export`
            Re-read a local export file and compare parser-covered casillas
            against the approved draft.
        :func:`application.modelo.export.export_modelo_revision`
            Work-unit-facing export orchestration that supplies an approved
            draft reconstructed from a calculation revision.
        :func:`domain.calculations.registry.export_parse.parse_export_payload`
            Registry parser used by the verification path.
    """
    if (output_path is None) == (payload_consumer is None):
        raise FilingExportDesignIntegrityError(
            "export requires exactly one payload destination",
            translated_message="errors.integrity.filing_export_payload_destination_count",
        )
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
    if states_whole_return:
        refuse_incomplete_xml_export(prepared.layout, draft=draft, payload=payload, schema_provider=prepared.provider)
    if output_path is not None:
        return _write_prepared_export(
            draft,
            output_path=output_path,
            prepared=prepared,
            payload=payload,
            casilla_provenance=casilla_provenance,
            mutation_writer=mutation_writer,
        )
    if payload_consumer is None:
        raise FilingExportDesignIntegrityError(
            "export payload consumer is unavailable",
            translated_message="errors.integrity.filing_export_payload_consumer_unavailable",
        )
    return _consume_prepared_export(
        draft,
        prepared=prepared,
        payload=payload,
        casilla_provenance=casilla_provenance,
        payload_consumer=payload_consumer,
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


def refuse_incomplete_xml_export(
    layout: ExportLayoutDefinition | None,
    *,
    draft: ModeloDraft,
    payload: bytes,
    schema_provider: RegistrySchemaAccessor,
) -> None:
    """Refuse a filer's rendered XML declaration that omits what its official XSD requires.

    A layout of another format carries no such schema and passes through.

    Args:
        layout: The layout the payload was rendered through, if the revision declares one.
        draft: The approved draft the payload states.
        payload: The rendered bytes.
        schema_provider: Resolves the layout's dictionary and XSD sources.

    Raises:
        ModeloApplicationError: Required content is absent.

    ``draft`` is the :class:`ModeloDraft`, the local modelo draft.
    """
    if layout is not None and layout.format is ExportLayoutFormat.XML_DICTIONARY:
        refuse_incomplete_xml_dictionary_payload(layout, draft=draft, payload=payload, schema_provider=schema_provider)


def refuse_xml_export_content(
    draft: ModeloDraft,
    *,
    dictionary_values: Mapping[str, object] | None,
    schema_provider: RegistrySchemaAccessor,
) -> None:
    """Refuse, without keeping any byte, what :func:`export_draft` would refuse in an XML return's content.

    Verification calls this before the draft is approved: the same render and the same
    required-content check answer, so it cannot grant a return the export then refuses.
    A layout of another format holds no such content and passes through.

    Args:
        draft: The draft the revision would export.
        dictionary_values: Values addressed by dictionary field id, as the export composes them.
        schema_provider: Resolves the layout's dictionary and XSD sources.

    Raises:
        ModeloApplicationError: A value breaks its schema, or required content is absent.
        FilingExportError: The declaration cannot be rendered at all.

    ``draft`` is the :class:`ModeloDraft`, the local modelo draft.
    """
    layout = _select_export_layout(
        draft,
        subview=schema_provider.get_subview(draft.modelo),
        registry_snapshot=schema_provider.get_snapshot(draft.modelo),
    )
    if layout.format is not ExportLayoutFormat.XML_DICTIONARY:
        return
    payload = render_xml_dictionary_layout(
        layout,
        draft=draft,
        headers={},
        aux_version=aeat_aux_version(),
        dictionary_values=dictionary_values,
        schema_provider=schema_provider,
    )
    refuse_incomplete_xml_export(layout, draft=draft, payload=payload, schema_provider=schema_provider)


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


def export_layout_not_renderable_error(
    modelo: str,
    layout: ExportLayoutDefinition | None,
) -> FilingExportError:
    """Return the typed refusal for a layout that cannot render declaration bytes."""
    code = export_layout_renderability_reason_code(layout)
    if code is None:
        raise FilingExportIntegrityError(
            f"modelo {modelo} export layout is not renderable and no reason code classifies why",
            translated_message="errors.integrity.filing_export_layout_unclassified",
            context={"modelo": modelo},
        )
    context: dict[str, object] = {"modelo": modelo, "reason_code": code.value}
    if layout is not None:
        context["layout_id"] = layout.id
        context["layout_format"] = layout.format.value
    return FilingExportError(
        translated_message="application.filing.export.errors.layout_not_renderable",
        context=context,
        precondition_verdict=export_design_terminal(ExportRefusalReason.LAYOUT_NOT_RENDERABLE),
    )


def _raise_if_export_layout_not_renderable(modelo: str, layout: ExportLayoutDefinition) -> None:
    if export_layout_renderability_reason_code(layout) is not None:
        raise export_layout_not_renderable_error(modelo, layout)


def _declaracion_export_format(layout: ExportLayoutDefinition) -> DeclaracionExportFormat:
    if layout.format is ExportLayoutFormat.XML_DICTIONARY:
        return DeclaracionExportFormat.XML_DICTIONARY
    return DeclaracionExportFormat.FICHERO_BOE


def render_export_layout(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    dictionary_values: Mapping[str, object] | None,
    prior_domiciliation_election: PriorDomiciliationElection,
    product_software_identity: AeatProductSoftwareIdentity | None,
    xml_aux_version: str | None,
    schema_provider: RegistrySchemaAccessor,
    registry_snapshot: RegistrySnapshot,
) -> bytes:
    """Render ``layout`` to export bytes, refusing shared cells and a missing XML Aux/VERSION token.

    ``draft`` is the :class:`ModeloDraft`, the local modelo draft.

    ``registry_snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    if layout.format is ExportLayoutFormat.XML_DICTIONARY:
        if xml_aux_version is None:
            raise FilingExportDesignIntegrityError(
                "XML dictionary export requires a canonical Aux/VERSION token",
                translated_message="errors.integrity.filing_export_xml_version_token_unresolved",
            )
        refuse_written_shared_owners(
            layout,
            registry_snapshot=registry_snapshot,
            casilla_values={value.casilla_id: value.value for value in draft.values},
        )
        return render_xml_dictionary_layout(
            layout,
            draft=draft,
            headers=dict(headers),
            aux_version=xml_aux_version,
            dictionary_values=dictionary_values,
            schema_provider=schema_provider,
        )
    return render_filing_layout(
        layout,
        registry_snapshot=registry_snapshot,
        draft=draft,
        headers=headers,
        producer_snapshot=producer_snapshot,
        prior_domiciliation_election=prior_domiciliation_election,
        product_software_identity=product_software_identity,
    )


def render_filing_layout(
    layout: ExportLayoutDefinition,
    *,
    registry_snapshot: RegistrySnapshot,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    producer_snapshot: FilingProducerSnapshot,
    prior_domiciliation_election: PriorDomiciliationElection,
    product_software_identity: AeatProductSoftwareIdentity | None,
) -> bytes:
    """Render one already-selected layout after enforcing immutable filing context.

    Core types:
    :class:`~cadrumo.domain.filing.schema.ModeloDraft`,
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
    """
    if (
        draft.modelo == form_for_role("iva.periodic")
        and producer_snapshot.elections.prior_domiciliation is not prior_domiciliation_election
    ):
        raise FilingExportValidationError(
            "M303 prior-domiciliation election must match the immutable producer snapshot election",
            translated_message="application.filing.export.errors.prior_domiciliation_election_differs",
            precondition_verdict=export_design_terminal(ExportRefusalReason.PRIOR_DOMICILIATION_ELECTION_DIFFERS),
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
            translated_message="application.filing.export.errors.product_identity_required",
            precondition_verdict=export_design_terminal(ExportRefusalReason.PRODUCT_IDENTITY_UNSUPPLIED),
        )
    prefix = render_declared_prefix(
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
) -> tuple[RenderedRecordOccurrence, ...]:
    """Derive one projection plan and render every applicable record occurrence.

    This is the sole application resolver bridge used by ordinary fixed-width
    exports and by the DP30300 envelope facade.  It intentionally accepts no
    caller-authored plan, member collection, field map, or bytes.
    """
    if not any(candidate is layout for candidate in registry_snapshot.revision.export_layouts):
        raise FilingExportDesignIntegrityError(
            "filing renderer layout is not owned by the selected registry snapshot",
            translated_message="errors.integrity.filing_export_layout_not_owned_by_snapshot",
        )
    projection_plan = _projection_plan_for_layout(
        layout,
        registry_snapshot=registry_snapshot,
        draft=draft,
        producer_snapshot=producer_snapshot,
    )
    projection_values = preflight_projection_plan(projection_plan)
    casilla_values: dict[CasillaId, object] = {value.casilla_id: value.value for value in draft.values}
    binding_values: dict[tuple[BindingId, int | None], object] = {
        (value.binding_id, value.row_index): value.value for value in draft.binding_values
    }
    refuse_written_shared_owners(layout, registry_snapshot=registry_snapshot, casilla_values=casilla_values)
    return render_layout_records(
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
        raise FilingExportDesignIntegrityError(
            "filing-envelope layout declaration is absent",
            translated_message="errors.integrity.filing_export_envelope_layout_absent",
        )
    headers = filing_producer_values(request.producer_snapshot)
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
    prefix = render_declared_prefix(
        envelope.prefix_fields,
        prefix_extent=envelope.prefix_extent,
        modelo=request.modelo,
        period=request.draft.period,
        product_software_identity=request.product_software_identity,
        declarant_tax_id=request.draft.subject_tax_id,
        envelope=envelope,
        casilla_values={item.casilla_id: item.value for item in request.draft.values},
    )
    closer = envelope_closer_bytes(modelo=request.modelo, period=request.draft.period, envelope=envelope)
    terminator, payload = assemble_filing_envelope_payload(
        envelope, prefix=prefix, occurrences=occurrences, closer=closer
    )
    return FilingEnvelopeRenderResult(
        draft_id=request.draft.draft_id,
        revision_id=request.registry_snapshot.revision.id,
        layout_id=request.layout.id,
        modelo=request.modelo,
        period=request.draft.period,
        envelope=envelope,
        occurrences=occurrences,
        prefix=prefix,
        closer=closer,
        terminator=terminator,
        payload=payload,
        payload_sha256=sha256_hex(payload),
        total_length=len(payload),
    )


def _require_envelope_required_occurrences(
    layout: ExportLayoutDefinition,
    occurrences: tuple[FilingEnvelopeOccurrence, ...],
) -> None:
    present = {item.record_id for item in occurrences}
    missing = tuple(record.id for record in layout.records if record.required and record.id not in present)
    if missing:
        raise FilingExportDesignIntegrityError(
            f"filing-envelope required record families have no emitted occurrence: {missing!r}",
            translated_message="errors.integrity.filing_export_envelope_records_unemitted",
            context={"records": ", ".join(map(str, missing))},
        )


def _projection_plan_for_layout(
    layout: ExportLayoutDefinition,
    *,
    registry_snapshot: RegistrySnapshot,
    draft: ModeloDraft,
    producer_snapshot: FilingProducerSnapshot,
) -> FilingProjectionPlan:
    if draft.modelo == form_for_role("iva.periodic"):
        return build_m303_filing_projection_plan(
            registry_snapshot=registry_snapshot,
            layout=layout,
            producer_snapshot=producer_snapshot,
        )
    if draft.modelo == form_for_role("sociedades.annual"):
        return build_m200_filing_projection_plan(
            registry_snapshot=registry_snapshot,
            layout=layout,
            producer_snapshot=producer_snapshot,
        )
    if draft.modelo == form_for_role("irnr.withholding_annual"):
        return build_m296_filing_projection_plan(
            registry_snapshot=registry_snapshot,
            layout=layout,
            producer_snapshot=producer_snapshot,
        )
    return FilingProjectionPlan(contexts=(), values=())


__all__ = [
    "FilingProjectionValue",
    "FilingRecordRenderContext",
    "RecordRenderRow",
    "export_draft",
    "preflight_projection_plan",
    "refuse_incomplete_xml_export",
    "refuse_xml_export_content",
    "render_export_layout",
    "render_filing_layout",
]
