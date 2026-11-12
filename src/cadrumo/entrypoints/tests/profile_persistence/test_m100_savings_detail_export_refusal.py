"""A saver's return calculates and verifies, and its export is refused until the detail records can be written.

The official design writes each savings occurrence as a per-position detail record
under the interest and dividend boxes, and the export cannot write those records
yet. The refusal reads the calculation's own recorded occurrences, never a box
value, so a return with no savings occurrence exports as before.

Real encrypted store, real registered operations, real calculate, verify and export.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.modelo.export_contracts import (
    ModeloExportCommand,
    ModeloExportSavingsDetailRecordsUnwritableError,
)
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.contribuyente.inmueble_facts import facts_for_row
from cadrumo.domain.contribuyente.posicion_facts import POSICION_SECTION
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import TransactionCatalogue
from cadrumo.domain.transactions.tests.savings_link_rows import savings_row
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.tests.env_scope import ready_clave_settings

from .m130_m100_annual_support import (
    BUCKET_ID,
    OPERATOR_SCOPE_PORTS,
    TAX_ID,
    YEAR,
    export_revision_for_test,
    verify_revision_for_test,
)
from .renta_persona_support import (
    PAYER_A,
    PAYER_B,
    Persona,
    calculate_annual,
    record_certificate,
    register_refund_account,
    seed_profile,
    workflow_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

__all__ = ["secure_objects"]

_SALARIED = Persona(categories="trabajo")
_SAVER = Persona(categories="trabajo,capital_mobiliario")
_INTEREST = validated_casilla_id("0027")


@pytest.fixture
def bucket_id() -> str:
    return BUCKET_ID


def _deposit_facts() -> tuple[UserProfileFact, ...]:
    values = {
        "tipo": "deposito",
        "pagador_nif": PAYER_B,
        "pagador_nombre": "Banco Sintetico",
        "pais_origen": "ES",
        "porcentaje_titularidad": "100.00",
        "fecha_inicio": date(YEAR - 1, 1, 1).isoformat(),
    }
    return tuple(
        UserProfileFact(path=path, value=value) for path, value in facts_for_row(POSICION_SECTION, 0, values).items()
    )


def _seed_interest_row(objects: SecureObjectRepository) -> None:
    base = savings_row(provider_id="deposit-interest")
    row = savings_row(
        provider_id="deposit-interest",
        raw=base.raw.model_copy(update={"amount": Decimal("324.00"), "booked_date": date(YEAR, 6, 30)}),
        direction=TransactionDirection.INCOMING,
        posicion_ref="0",
        concepto_capital_mobiliario="intereses",
        business_classification=BusinessClassification.PERSONAL,
        classified_at=datetime(YEAR, 7, 1, 9, 0, tzinfo=UTC),
        classified_by="manual",
    )
    TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=objects).save(
        TransactionCatalogue.from_transactions((row,))
    )


def _calculate(
    persona: Persona, objects: SecureObjectRepository, directory: Path, operation: PinnedAuthorityOperation
) -> CalculationRevision:
    saver = persona is _SAVER
    seed_profile(persona, extra_facts=_deposit_facts() if saver else ())
    record_certificate(
        operation,
        directory=directory,
        payer=PAYER_A,
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion="3000.00",
        importe_integro="24000.00",
    )
    if saver:
        record_certificate(
            operation,
            directory=directory,
            payer=PAYER_B,
            income_class=RetencionSoportadaClase.CAPITAL_MOBILIARIO,
            retencion="76.00",
            importe_integro="400.00",
        )
        _seed_interest_row(objects)
    register_refund_account(objects)
    return calculate_annual(objects)


def _verify(revision: CalculationRevision, persona: Persona) -> None:
    report = verify_revision_for_test(
        revision.calculation_revision_id,
        actor="savings-export",
        workflow_profile=workflow_profile(persona),
        settings=ready_clave_settings(TAX_ID),
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )
    assert report.granted_verificado_completo is True, report.findings


def _export(revision: CalculationRevision, persona: Persona, objects: SecureObjectRepository, output: Path) -> None:
    receipt = export_revision_for_test(
        ModeloExportCommand(
            calculation_revision_id=revision.calculation_revision_id, output_path=output, actor="savings-export"
        ),
        workflow_profile=workflow_profile(persona),
        export_ports=modelo_export_ports_for_test(bucket_id=BUCKET_ID, taxpayer_tax_id=TAX_ID, secure_objects=objects),
    )
    assert receipt.byte_size == len(output.read_bytes())


def test_a_saver_calculates_and_verifies_and_the_export_is_refused_with_nothing_written(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    revision = _calculate(_SAVER, secure_objects, tmp_path, operation)
    assert Decimal(revision.casilla_values[_INTEREST]) == Decimal("400.00")
    _verify(revision, _SAVER)
    output = tmp_path / "modelo-100.xml"

    with pytest.raises(ModeloExportSavingsDetailRecordsUnwritableError) as refused:
        _export(revision, _SAVER, secure_objects, output)

    assert get_registered_error_code(refused.value).code == "REFUSED_MODELO_EXPORT_SAVINGS_DETAIL_RECORDS_UNWRITABLE"
    assert refused.value.translated_message == "application.modelo.errors.export_savings_detail_records_unwritable"
    assert (refused.value.context or {})["occurrence_count"] == 1
    assert not output.exists()


def test_a_return_without_savings_occurrences_exports_as_before(
    secure_objects: SecureObjectRepository, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    revision = _calculate(_SALARIED, secure_objects, tmp_path, operation)
    assert Decimal(revision.casilla_values[_INTEREST]) == Decimal("0")
    _verify(revision, _SALARIED)
    output = tmp_path / "modelo-100.xml"

    _export(revision, _SALARIED, secure_objects, output)

    assert output.read_bytes()
