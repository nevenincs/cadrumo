"""A Modelo 347 calculated from the invoice book names what it could not fill, and shows no figure it does not hold.

The 2025 record design fills CÓDIGO PROVINCIA (pos. 77-78) of a resident
declarado from its domicilio fiscal, which an invoice records only inside a
free-text address. The person states it once for the counterparty; until then
the calculation leaves it without content and names each counterpart on its
own line, with one of its invoices to open. The cash amount (pos. 101-115) is
owed only when a declarado paid more than 6.000 EUR in cash, which the invoices
do not record, so the filer is asked to check it, not told that something is
missing. The paper signature date has no figure until the filer signs, so it is
empty, never a zero.
"""

from __future__ import annotations

import pytest

from cadrumo.adapters.persistence.profile.counterparty_establishment import CounterpartyEstablishmentRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.counterparty_establishment import record_counterparty_provincia
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.work_form_field_vocabulary import ModeloFormCasillaAddressV1
from cadrumo.application.modelo.work_form_findings import ModeloFormAttention
from cadrumo.application.modelo.work_form_issue_lines import form_issue_lines
from cadrumo.application.modelo.work_form_models import ModeloWorkForm
from cadrumo.application.modelo.work_form_service import load_modelo_work_form
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.entrypoints.tests.profile_persistence.test_modelo_347_declarado_rows import (
    _BUCKET_ID,
    _T1,
    _ledger,
    _records,
    _work_unit,
    secure_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

__all__ = ["secure_objects"]

_PROVINCIA = "contraparte.provincia-codigo"
_METALICO = "contraparte.importe-metalico"
_SIGNATURE_DATE = "firma-fecha"
_SPANISH_DECLARADOS = ("B00015016", "B00015057")


def _calculated_form(secure_objects: SecureObjectRepository) -> tuple[ModeloWorkForm, CalculationRevision]:
    invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoices.save(build_invoice_catalogue(_ledger().invoices))
    work_units = WorkUnitCatalogueRepository(objects=secure_objects)
    unit = _work_unit(work_units)
    calculations = CalculationRevisionCatalogueRepository(objects=secure_objects)
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=work_units,
        calculation_repository=calculations,
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        invoice_repository=invoices,
    ) as ports:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            unit.work_unit_id, ports=ports, clock=_T1
        ).revision
    with bundled_indexed_authority().operation() as operation:
        form = load_modelo_work_form(
            unit.bucket_id,
            unit.modelo,
            unit.filing_year,
            unit.period,
            operation=operation,
            work_unit_repository=work_units,
            calculation_repository=calculations,
            verification_repository=VerificationReportCatalogueRepository(objects=secure_objects),
            admission=None,
            language=OutputLanguage.ES,
        ).form
    return form, revision


def _invoice_ids_of(party: str) -> set[str]:
    return {invoice.invoice_id for invoice in _ledger().invoices if invoice.counterparty_tax_id == party}


def test_each_gap_the_invoices_leave_is_named_and_only_the_missing_one_classes_as_missing(
    secure_objects: SecureObjectRepository,
) -> None:
    form, _revision = _calculated_form(secure_objects)

    assert all(note.casilla_id is not None for note in form.calculation_notes)
    provincia = [note for note in form.calculation_notes if note.casilla_id == _PROVINCIA]
    assert all(note.attention is ModeloFormAttention.MISSING for note in provincia)
    assert sorted(dict(note.fact.values)["party"] for note in provincia if note.fact is not None) == [
        "CLIENTE GRANDE SL (B00015057)",
        "PROVEEDOR GRANDE SL (B00015016)",
    ]
    (metalico,) = (note for note in form.calculation_notes if note.casilla_id == _METALICO)
    assert metalico.attention is ModeloFormAttention.CHECK

    whole_declaration = tr("workspace.modelo.issues.where.declaration", locale=OutputLanguage.ES.value)
    lines = [line for line in form_issue_lines(form, OutputLanguage.ES) if line.from_calculation]
    assert lines
    for line in lines:
        assert line.where != whole_declaration
        assert "{" not in line.message and "{" not in line.action
    missing = [line for line in lines if line.level is ModeloFormAttention.MISSING]
    assert len(missing) == len(_SPANISH_DECLARADOS)
    for party in _SPANISH_DECLARADOS:
        (line,) = (line for line in missing if party in line.message)
        assert line.invoice_id in _invoice_ids_of(party)


def test_a_provincia_stated_for_the_counterparty_fills_its_record_and_leaves_only_the_other_named(
    secure_objects: SecureObjectRepository,
) -> None:
    stated, unstated = _SPANISH_DECLARADOS
    record_counterparty_provincia(
        bucket_id=_BUCKET_ID,
        tax_identifier=stated,
        provincia_code="08",
        asserted_by="operator",
        repository=CounterpartyEstablishmentRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
    )

    form, revision = _calculated_form(secure_objects)

    provincias = {record["nif"]: record["provincia-codigo"] for record in _records(revision.row_binding_values)}
    assert provincias == {stated: "08", unstated: ""}, provincias
    (missing,) = (
        line
        for line in form_issue_lines(form, OutputLanguage.ES)
        if line.from_calculation and line.level is ModeloFormAttention.MISSING
    )
    assert unstated in missing.message
    assert stated not in missing.message
    assert missing.invoice_id in _invoice_ids_of(unstated)


def test_the_paper_signature_date_holds_no_figure_until_the_filer_signs(
    secure_objects: SecureObjectRepository,
) -> None:
    form, _revision = _calculated_form(secure_objects)

    (signature_date,) = (
        field
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1) and field.address.casilla_id == _SIGNATURE_DATE
    )
    assert signature_date.value is None
