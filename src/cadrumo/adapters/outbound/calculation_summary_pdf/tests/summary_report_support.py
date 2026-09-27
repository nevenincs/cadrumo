"""Synthetic calculation reports and a fixed signing key for summary PDF tests.

The report is built directly from the typed report models rather than from a
calculation, because the subject here is the PDF: every row shape a summary must
lay out is present on purpose -- a figure, a proven zero, an absent value and a
not-applicable one; an input, a computed figure, a subtotal and a result; a
semantic casilla number wider than its column; a label long enough to wrap; and
text that needs Hungarian and Catalan letters. Every identity is synthetic.

The key is derived from a fixed seed so two processes produce the same summary
bytes. It is test material, never a real profile key.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from .....application.modelo.calculation_report import (
    CalculationReportRowRole,
    CalculationReportValueState,
    ModeloCalculationReport,
    ModeloCalculationReportHeader,
    ModeloCalculationReportRow,
    local_calculation_report_notice,
)
from .....application.modelo.calculation_report_document import (
    CalculationReportDocument,
    CalculationSummaryPdfRendering,
    serialize_calculation_report,
)
from .....application.modelo.review_package_signing import ReviewPackageSigningKeypair
from .....core.calculation_report_format import CalculationReportDocumentFormat
from .....core.external_constants import OutputLanguage
from .....core.period import Period
from .....domain.calculations.registry.schema_input_kind import InputKind
from .....domain.calculations.registry.schema_references import RegistrySnapshotRef
from .....domain.filing.schema import ModeloValueKind
from .....domain.filing.software_identity import AeatSoftwareIdentityGrade
from .....domain.modelos.calculation_revision import CalculationRevisionState
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.verification_report import VerificationCompletenessStatus
from ..summary_container import write_calculation_summary_pdf

BUCKET_ID = "33333333-3333-4333-8333-333333333333"
EXPORTED_AT = datetime(2026, 7, 20, 9, 30, tzinfo=UTC)
TAXPAYER_TAX_ID = "00000002W"
TAXPAYER_NAME = "Őrs Güell Núñez"
CALCULATION_REVISION_ID = "1" * 64
WORK_UNIT_ID = "2" * 64
VERIFICATION_REPORT_ID = "3" * 64
GENERATION = "4" * 64
LONG_CASILLA_NUMBER = "saldo-negativo-fin-periodo"
MEASURED_VALUE = Decimal("1234567.89")
RESULT_VALUE = Decimal("-2750.40")


def synthetic_keypair(seed: str = "calculation-summary-profile") -> ReviewPackageSigningKeypair:
    """Return a deterministic synthetic Ed25519 keypair named by ``seed``."""
    private = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(seed.encode("utf-8")).digest())
    return ReviewPackageSigningKeypair(
        bucket_id=BUCKET_ID,
        private_key_hex=private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex(),
        public_key_hex=private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
        created_at=EXPORTED_AT,
    )


def _row(
    casilla_id: str,
    *,
    label: str,
    section: str,
    role: CalculationReportRowRole,
    state: CalculationReportValueState,
    value: Decimal | int | bool | None,
    number: str | None = None,
) -> ModeloCalculationReportRow:
    return ModeloCalculationReportRow(
        casilla_id=casilla_id,
        number=number or casilla_id,
        section_path=(section,),
        label=label,
        semantic_role=None,
        declared_input_kind=InputKind.COMPUTED if role is not CalculationReportRowRole.INPUT else InputKind.MANUAL,
        row_role=role,
        formula_id=None,
        realised_kind=ModeloValueKind.EMPTY if state is CalculationReportValueState.ABSENT else ModeloValueKind.LITERAL,
        value_state=state,
        value=value,
        legal_refs=("ley-37-1992:art-164",),
        source_refs=("aeat-modelo-303-instructions",),
    )


def synthetic_report_rows() -> tuple[ModeloCalculationReportRow, ...]:
    """Return one row of every shape a summary lays out, across three sections."""
    value = CalculationReportValueState.VALUE
    return (
        _row(
            "01",
            label="Base imponible del régimen general al tipo del 21 por ciento, incluidas las operaciones",
            section="iva_devengado",
            role=CalculationReportRowRole.INPUT,
            state=value,
            value=MEASURED_VALUE,
        ),
        _row("02", label="Tipo", section="iva_devengado", role=CalculationReportRowRole.INPUT, state=value, value=21),
        _row(
            "03",
            label="Cuota",
            section="iva_devengado",
            role=CalculationReportRowRole.COMPUTED,
            state=value,
            value=Decimal("0.00"),
        ),
        _row(
            "04",
            label="Adquisiciones intracomunitarias",
            section="iva_devengado",
            role=CalculationReportRowRole.INPUT,
            state=CalculationReportValueState.ABSENT,
            value=None,
        ),
        _row(
            "05",
            label="Cuotas a compensar de periodos anteriores",
            section="iva_devengado",
            role=CalculationReportRowRole.INPUT,
            state=CalculationReportValueState.NOT_APPLICABLE,
            value=None,
        ),
        _row(
            "27",
            label="Total cuota devengada",
            section="resultado",
            role=CalculationReportRowRole.SUBTOTAL,
            state=value,
            value=Decimal("259259.26"),
        ),
        _row(
            "71",
            label="Resultado de la liquidación",
            section="resultado",
            role=CalculationReportRowRole.RESULT,
            state=value,
            value=RESULT_VALUE,
        ),
        _row(
            "carry",
            label="Saldo negativo trasladable a periodos posteriores",
            section="computed_carry_forward",
            role=CalculationReportRowRole.INFORMATIONAL,
            state=value,
            value=True,
            number=LONG_CASILLA_NUMBER,
        ),
    )


def synthetic_report(
    language: OutputLanguage = OutputLanguage.ES,
    *,
    authority_logical_generation: str = GENERATION,
    rows: tuple[ModeloCalculationReportRow, ...] | None = None,
) -> ModeloCalculationReport:
    """Return the synthetic Modelo 303 report in ``language``."""
    report_rows = synthetic_report_rows() if rows is None else rows
    return ModeloCalculationReport(
        header=ModeloCalculationReportHeader(
            modelo=ModeloCode("303"),
            filing_year=2026,
            period=Period.from_year_and_code(2026, "2T"),
            taxpayer_tax_id=TAXPAYER_TAX_ID,
            taxpayer_name=TAXPAYER_NAME,
            calculation_revision_id=CALCULATION_REVISION_ID,
            calculation_revision_state=CalculationRevisionState.VERIFICADO_COMPLETO,
            work_unit_id=WORK_UNIT_ID,
            verification_report_id=VERIFICATION_REPORT_ID,
            verification_outcome=VerificationCompletenessStatus.COMPLETE,
            filing_record_id=None,
            registry_snapshot_ref=RegistrySnapshotRef(
                modelo="303",
                revision_id="2023-y-siguientes",
                modelo_year=2026,
                period="2T",
            ),
            authority_logical_generation=authority_logical_generation,
            software_identity_grade=AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK,
            report_language=language,
            exported_at=EXPORTED_AT,
            row_count=len(report_rows),
            local_calculation_notice=local_calculation_report_notice(language),
        ),
        rows=report_rows,
    )


def render_summary(
    report: ModeloCalculationReport,
    *,
    keypair: ReviewPackageSigningKeypair | None = None,
) -> CalculationReportDocument:
    """Render ``report`` as a summary PDF through the one serialiser entry point."""
    return serialize_calculation_report(
        report,
        document_format=CalculationReportDocumentFormat.PDF,
        pdf_rendering=CalculationSummaryPdfRendering(
            writer=write_calculation_summary_pdf,
            keypair=synthetic_keypair() if keypair is None else keypair,
        ),
    )


__all__ = [
    "BUCKET_ID",
    "CALCULATION_REVISION_ID",
    "EXPORTED_AT",
    "GENERATION",
    "LONG_CASILLA_NUMBER",
    "MEASURED_VALUE",
    "RESULT_VALUE",
    "TAXPAYER_NAME",
    "TAXPAYER_TAX_ID",
    "VERIFICATION_REPORT_ID",
    "WORK_UNIT_ID",
    "render_summary",
    "synthetic_keypair",
    "synthetic_report",
    "synthetic_report_rows",
]
