"""The registered export result carries a lossless strict fichero-BOE receipt."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.modelo.export_contracts import (
    ModeloExportCommand,
    ModeloExportResult,
    ModeloIvaWalletDecisionProvenance,
)
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....application.calculations.observations_repository import PriorDomiciliationElectionProjection
from ....application.operations.error_detail import build_operation_error_detail
from ....application.operations.models import OperationIdentity, OperationTerminalReceipt
from ....application.operations.operation_definition import OperationDefinition
from ....application.operations.registry import OperationPublicDefinitionRegistrationV1, OperationRegistry
from ....core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ....core.modelo_export_artefact import ModeloExportArtefact
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....core.payment_election import PaymentElection
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ....domain.calculations.registry.tax_id_format import SubjectTaxId
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.filing.errors import FilingExportValidationError, FilingExportValueOverflowError
from ....domain.filing.schema import ModeloCasillaProvenance
from ....domain.filing.software_identity import AeatSoftwareIdentityGrade
from ....domain.modelos.errors import ModeloExportError, ModeloExportValueOverflowError
from ...filing.errors import ModeloApplicationError
from ...filing.record_field_renderer import format_field
from ..calculation_summary_pdf_ports import CalculationSummaryCertifier, CalculationSummaryPdfRequest
from ..export import export_write_failure
from ..export_operation import build_modelo_export_definition, build_modelo_export_registration
from ..export_ports import ModeloExportPorts
from ..export_projection import (
    ModeloExportCompleteness,
    ModeloExportEvidenceStatus,
    ModeloExportPublicResultV3,
    ModeloFicheroBoePublicReceipt,
)
from ..operation_shared import MODELO_EXPORT_OPERATION_DEFINITION_ID
from ..review_package_signing_ports import ReviewPackageSigningKeypairCapability
from ..work_export_contracts import ModeloExportSettledResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REVISION_ID = "a" * 64
_WORK_UNIT_ID = "b" * 64
_BASELINE_FILING_ID = "c" * 64
_FILE_DIGEST = "d" * 64
_AT = datetime(1980, 9, 26, 8, 30, tzinfo=UTC)
_FILING_YEAR = filing_year_envelope().horizon


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_a_box_refusal_keeps_its_message_and_context_at_the_export_boundary(locale: str) -> None:
    """The boundary preserves filing's refusal without replacing it by a disk error."""
    context = {"box": "fixture-box", "limit": "3", "observed": 4}
    refusal = ModeloApplicationError(
        translated_message="application.filing.export.errors.xml_value_too_long", context=context
    )
    command = ModeloExportCommand.model_construct(calculation_revision_id="revision-1")

    failure = export_write_failure(command, refusal)

    assert isinstance(failure, ModeloExportError)
    assert failure.translated_message == refusal.translated_message
    assert failure.context == {"calculation_revision_id": "revision-1", **context}
    message = resolve_error_message(failure, locale=locale)
    assert "fixture-box" in message
    assert "3" in message
    assert "xml_value" not in message
    assert "cause" not in failure.context


@pytest.mark.parametrize("locale", ["es", "ca", "en", "hu"])
def test_a_shared_cell_refusal_reaches_the_operator_naming_its_boxes(locale: str) -> None:
    context = {
        "modelo": "fixture-modelo",
        "casilla_ids": "fixture-box",
        "target_cells": {"fixture-box": ["fixture-layout.sheet-a.f1", "fixture-layout.sheet-b.f2"]},
    }
    refusal = FilingExportValidationError(
        translated_message="application.filing.export.errors.shared_casilla_cells_unadjudicated", context=context
    )
    command = ModeloExportCommand.model_construct(calculation_revision_id="revision-1")

    failure = export_write_failure(command, refusal)

    assert failure.translated_message == refusal.translated_message
    assert failure.context == {"calculation_revision_id": "revision-1", **context}
    message = resolve_error_message(failure, locale=locale)
    assert "fixture-box" in message
    assert "shared_casilla_cells" not in message


def test_another_export_failure_keeps_the_generic_message_and_its_cause() -> None:
    command = ModeloExportCommand.model_construct(calculation_revision_id="revision-1")

    failure = export_write_failure(command, ModeloApplicationError("a layout invariant broke"))

    assert failure.translated_message == "application.modelo.errors.export_draft_write_failed"
    assert failure.context == {"calculation_revision_id": "revision-1", "cause": "a layout invariant broke"}


def _m347_declarado_record() -> ExportRecordDefinition:
    """The shipped Modelo 347 counterparty record, as the published registry serves it."""
    snapshot = published_snapshot("347", filing_year=_FILING_YEAR, period="0A")
    records = [
        record
        for layout in snapshot.revision.export_layouts
        for record in layout.records
        if record.record_type == "declarado"
    ]
    assert len(records) == 1
    return records[0]


def _m347_declarado_field(record: ExportRecordDefinition, *, binding: str) -> ExportFieldDefinition:
    fields = [field for field in record.fields if field.binding == binding]
    assert len(fields) == 1
    return fields[0]


@pytest.mark.parametrize("locale", ["es", "ca", "en", "hu"])
def test_a_counterparty_name_wider_than_its_record_slot_is_refused_naming_it(locale: str) -> None:
    """DR347 type-2 record, positions 36-75: "APELLIDOS Y NOMBRE, RAZON SOCIAL O DENOMINACION DEL DECLARADO".

    The design gives the name forty positions and states no abbreviation rule,
    so a longer name is refused, never cut, and the refusal names it.
    """
    record = _m347_declarado_record()
    field = _m347_declarado_field(record, binding="modelo-347-contraparte-row-nombre")
    assert (field.offset, field.length) == (36, 40)
    name = "Comunidad de Propietarios Calle Ficticia 12"
    command = ModeloExportCommand.model_construct(calculation_revision_id="revision-1")

    with pytest.raises(FilingExportValueOverflowError) as overflow:
        format_field(field, name)
    failure = export_write_failure(command, overflow.value.in_record(record.record_type))

    assert isinstance(failure, ModeloExportValueOverflowError)
    registered = get_registered_error_code(failure)
    assert (registered.code, registered.category) == ("REFUSED_MODELO_EXPORT_VALUE_OVERFLOW", ErrorCategory.REFUSED)
    message = resolve_error_message(failure, locale=locale)
    for shown in (name, "36-75", "declarado", str(len(name)), "40"):
        assert shown in message
    detail = build_operation_error_detail(failure)
    assert detail is not None
    assert detail.error_code == "REFUSED_MODELO_EXPORT_VALUE_OVERFLOW"
    assert detail.refusal_words is not None
    assert name not in detail.refusal_words
    assert "field_value" not in {entry.key for entry in detail.context}
    for shown in (field.id, "40"):
        assert shown in detail.refusal_words


def test_an_amount_wider_than_its_record_slot_is_refused_by_its_slot_alone() -> None:
    record = _m347_declarado_record()
    money = next(field for field in record.fields if field.data_type == "money")
    length = money.length
    assert length is not None
    command = ModeloExportCommand.model_construct(calculation_revision_id="revision-1")

    with pytest.raises(FilingExportValueOverflowError) as overflow:
        format_field(money, Decimal("1" + "0" * length))
    failure = export_write_failure(command, overflow.value.in_record(record.record_type))

    assert isinstance(failure, ModeloExportValueOverflowError)
    assert get_registered_error_code(failure).code == "REFUSED_MODELO_EXPORT_VALUE_OVERFLOW"
    assert failure.context is not None
    assert "field_value" not in failure.context
    message = resolve_error_message(failure, locale="es")
    assert money.id in message
    assert str(length) in message


def _canonical_receipt(
    *,
    include_prior_proof: bool,
    include_wallet_provenance: bool,
    include_elections: bool,
    completeness_unverified: bool,
) -> ModeloExportResult:
    """Build real canonical domain values for both full and neutral receipts."""
    prior_election = (
        PriorDomiciliationElection.CANCEL_OR_MODIFY if include_prior_proof else PriorDomiciliationElection.KEEP
    )
    prior = PriorDomiciliationElectionProjection(
        election=prior_election,
        baseline_filing_record_id=_BASELINE_FILING_ID if include_prior_proof else None,
        baseline_evidence_reference_id="aeat-evidence-reference" if include_prior_proof else None,
        baseline_result_disposition=ResultDisposition.DOMICILIACION if include_prior_proof else None,
        baseline_source_header_locator="fichero-boe:header:tipo-declaracion" if include_prior_proof else None,
    )
    wallet = (
        ModeloIvaWalletDecisionProvenance(
            decision_ref=f"sha256:{'e' * 64}",
            selected_authority="official_observation",
            divergence="none",
            target_year=_FILING_YEAR - 1,
            target_period=Period.from_year_and_code(_FILING_YEAR - 1, "4T"),
            authority_source_kinds=("aeat_capture", "app_filing"),
            authority_source_refs=(f"sha256:{'f' * 64}",),
        )
        if include_wallet_provenance
        else None
    )
    return ModeloExportResult(
        calculation_revision_id=_REVISION_ID,
        work_unit_id=_WORK_UNIT_ID,
        bucket_id="5aa00000-0000-4000-8000-0000000000aa",
        modelo="303",
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, "1T"),
        output_path=Path("C:/tax exports/modelo-303.fichero-boe"),
        byte_size=18_432,
        file_sha256=_FILE_DIGEST,
        format="fichero-boe",
        exported_at=_AT,
        actor="gestoria operator",
        bucket_event_id="modelo-export-event-42",
        resolved_result_disposition=(
            ResultDisposition.DOMICILIACION if include_elections else ResultDisposition.INGRESO
        ),
        payment_election=PaymentElection.DOMICILIACION if include_elections else None,
        refund_election=RefundElection.DEVOLVER if include_elections else None,
        prior_domiciliation_election=prior,
        casilla_provenance=(
            ModeloCasillaProvenance(
                casilla_id="303.resultado-final",
                formula_id="m303.resultado-final",
                legal_refs=("ley-37-1992:art-116",),
                source_refs=("aeat-303-diseno-2026",),
            ),
        ),
        iva_wallet_decision_provenance=wallet,
        local_evidence_status="local_export_not_official_aeat_filing_evidence",
        official_evidence_message="The operator must submit this local export through AEAT.",
        completeness_unverified=completeness_unverified,
        software_identity_grade=AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK if include_elections else None,
    )


def test_fichero_boe_receipt_roundtrips_complete_canonical_receipt() -> None:
    canonical = _canonical_receipt(
        include_prior_proof=True,
        include_wallet_provenance=True,
        include_elections=True,
        completeness_unverified=True,
    )

    projected = ModeloFicheroBoePublicReceipt.from_result(canonical)
    restored_projection = ModeloFicheroBoePublicReceipt.model_validate_json(projected.model_dump_json())

    assert restored_projection == projected
    assert restored_projection.to_result() == canonical
    assert restored_projection.period.filing_year == canonical.period.filing_year
    assert restored_projection.period.code == canonical.period.registry_token
    assert restored_projection.output_path == str(canonical.output_path)
    assert restored_projection.payment_election is PaymentElection.DOMICILIACION
    assert restored_projection.refund_election is RefundElection.DEVOLVER
    assert restored_projection.prior_domiciliation_election.to_provenance() == canonical.prior_domiciliation_election
    assert restored_projection.iva_wallet_decision_provenance is not None
    assert (
        restored_projection.iva_wallet_decision_provenance.to_provenance() == canonical.iva_wallet_decision_provenance
    )
    assert restored_projection.casilla_provenance == canonical.casilla_provenance
    assert restored_projection.completeness_unverified
    assert restored_projection.to_result().completeness_advisory_message == canonical.completeness_advisory_message
    assert restored_projection.software_identity_grade is AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK


def test_fichero_boe_receipt_preserves_neutral_optional_provenance() -> None:
    canonical = _canonical_receipt(
        include_prior_proof=False,
        include_wallet_provenance=False,
        include_elections=False,
        completeness_unverified=False,
    )

    projected = ModeloFicheroBoePublicReceipt.from_result(canonical)
    restored = ModeloFicheroBoePublicReceipt.model_validate_json(projected.model_dump_json())

    assert restored.to_result() == canonical
    assert restored.prior_domiciliation_election.to_provenance() == canonical.prior_domiciliation_election
    assert restored.prior_domiciliation_election.baseline_filing_record_id is None
    assert restored.iva_wallet_decision_provenance is None
    assert restored.payment_election is None
    assert restored.refund_election is None
    assert not restored.completeness_unverified
    assert restored.software_identity_grade is None


def _unused_ports_factory(
    *,
    bucket_id: str,
    m303_rectificativa_taxpayer_tax_id: SubjectTaxId,
    operation: PinnedAuthorityOperation,
    mutation_writer: Callable[[Callable[[], None]], None] | None = None,
) -> ModeloExportPorts:
    del bucket_id, m303_rectificativa_taxpayer_tax_id, operation, mutation_writer
    raise AssertionError("registration must not construct export ports")


def _unused_signing_keypair(
    *, bucket_id: str, mutation_writer: Callable[[Callable[[], None]], None] | None = None
) -> ReviewPackageSigningKeypairCapability:
    del bucket_id, mutation_writer
    raise AssertionError("registration must not open the signing key")


def _unused_pdf_writer(request: CalculationSummaryPdfRequest, /, *, certify: CalculationSummaryCertifier) -> bytes:
    del request, certify
    raise AssertionError("registration must not draw a summary")


def _export_registration() -> tuple[OperationDefinition, OperationPublicDefinitionRegistrationV1]:
    definition = build_modelo_export_definition(
        export_ports_factory=_unused_ports_factory,
        signing_keypair_capability_factory=_unused_signing_keypair,
        calculation_summary_pdf_writer=_unused_pdf_writer,
    )
    return definition, build_modelo_export_registration(definition)


def test_export_registration_binds_v3_to_the_public_wire_model() -> None:
    definition, registration = _export_registration()
    OperationRegistry(definitions=(definition,), public_registrations=(registration,))

    assert definition.result_type is ModeloExportSettledResult
    assert registration.contract.result_schema is not None
    assert registration.contract.result_schema.schema_id == "modelo.export.result"
    assert registration.contract.result_schema.schema_version == 3
    result_binding = next(
        binding for binding in registration.schema_bindings if binding.identity.schema_id == "modelo.export.result"
    )
    assert result_binding.model_type is ModeloExportPublicResultV3


@pytest.mark.parametrize("fault", [None, "subject", "effect", "terminal"])
def test_export_projection_carries_the_complete_fichero_boe_receipt(fault: str | None) -> None:
    canonical = _canonical_receipt(
        include_prior_proof=True,
        include_wallet_provenance=True,
        include_elections=True,
        completeness_unverified=True,
    )
    _, registration = _export_registration()
    projector = registration.result_projector
    assert projector is not None
    terminal = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="e" * 64,
            definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
            subject_ref="f" * 64 if fault == "subject" else _WORK_UNIT_ID,
        ),
        revision=4,
        condition=OperationTerminalCondition.FAILED if fault == "terminal" else OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UNKNOWN if fault == "effect" else OperationEffect.UPDATED,
        settled_at=_AT,
        result_ref="f" * 64,
    )

    if fault is not None:
        with pytest.raises(ValueError, match="export result contradicts"):
            projector(ModeloExportSettledResult(fichero_boe=canonical), terminal)
        return
    projected = projector(ModeloExportSettledResult(fichero_boe=canonical), terminal)
    assert isinstance(projected, ModeloExportPublicResultV3)
    restored = ModeloExportPublicResultV3.model_validate_json(projected.model_dump_json())

    assert restored.artefact is ModeloExportArtefact.FICHERO_BOE
    assert restored.evidence_status is ModeloExportEvidenceStatus.LOCAL_EXPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE
    assert restored.completeness is ModeloExportCompleteness.UNVERIFIED
    assert restored.fichero_boe is not None
    assert restored.fichero_boe.to_result() == canonical


def test_export_public_result_refuses_a_receipt_that_does_not_match_its_artefact() -> None:
    canonical = _canonical_receipt(
        include_prior_proof=False,
        include_wallet_provenance=False,
        include_elections=False,
        completeness_unverified=False,
    )
    summary = {
        "calculation_revision_id": _REVISION_ID,
        "export_format": "fichero-boe",
        "output_path": str(canonical.output_path),
        "byte_size": canonical.byte_size,
        "file_sha256": _FILE_DIGEST,
        "software_identity_grade": None,
        "evidence_status": ModeloExportEvidenceStatus.LOCAL_EXPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE,
        "completeness": ModeloExportCompleteness.NOT_FLAGGED,
    }

    with pytest.raises(ValueError, match="carries exactly its receipt"):
        ModeloExportPublicResultV3.model_validate({**summary, "artefact": ModeloExportArtefact.FICHERO_BOE})
    with pytest.raises(ValueError, match="carries exactly its receipt"):
        ModeloExportPublicResultV3.model_validate(
            {
                **summary,
                "artefact": ModeloExportArtefact.CALCULATION_REPORT_CSV,
                "fichero_boe": ModeloFicheroBoePublicReceipt.from_result(canonical),
            }
        )
