"""A Modelo 347 calculated from the invoice book names what it could not fill, and shows no figure it does not hold.

The 2025 record design fills CÓDIGO PROVINCIA (pos. 77-78) of a resident
declarado from its domicilio fiscal, which an invoice records only inside a
free-text address, so the calculation leaves it without content and says so
for each counterpart. The cash amount (pos. 101-115) is owed only when a
declarado paid more than 6.000 EUR in cash, which the invoices do not record,
so the filer is asked to check it, not told that something is missing. The
paper signature date has no figure until the filer signs, so it is empty,
never a zero.
"""

from __future__ import annotations

import pytest

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.work_form_findings import ModeloFormAttention
from cadrumo.application.modelo.work_form_issue_lines import form_issue_lines
from cadrumo.application.modelo.work_form_models import ModeloFormCasillaAddressV1, ModeloWorkForm
from cadrumo.application.modelo.work_form_service import load_modelo_work_form
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.entrypoints.tests.profile_persistence.test_modelo_347_declarado_rows import (
    _BUCKET_ID,
    _T1,
    _ledger,
    _work_unit,
    secure_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

__all__ = ["secure_objects"]

_PROVINCIA = "contraparte.provincia-codigo"
_METALICO = "contraparte.importe-metalico"
_SIGNATURE_DATE = "firma-fecha"
_SPANISH_DECLARADOS = ("B00015016", "B00015057")


def _calculated_form(secure_objects: SecureObjectRepository) -> ModeloWorkForm:
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
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(unit.work_unit_id, ports=ports, clock=_T1)
    with bundled_indexed_authority().operation() as operation:
        return load_modelo_work_form(
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


def test_each_gap_the_invoices_leave_is_named_and_only_the_missing_one_classes_as_missing(
    secure_objects: SecureObjectRepository,
) -> None:
    form = _calculated_form(secure_objects)
    notes = {note.casilla_id: note for note in form.calculation_notes}

    assert all(note.casilla_id is not None for note in form.calculation_notes)
    provincia = notes[_PROVINCIA]
    assert provincia.attention is ModeloFormAttention.MISSING
    assert provincia.fact is not None
    assert dict(provincia.fact.values)["parties"] == ", ".join(_SPANISH_DECLARADOS)
    metalico = notes[_METALICO]
    assert metalico.attention is ModeloFormAttention.CHECK

    whole_declaration = tr("workspace.modelo.issues.where.declaration", locale=OutputLanguage.ES.value)
    lines = [line for line in form_issue_lines(form, OutputLanguage.ES) if line.from_calculation]
    assert lines
    for line in lines:
        assert line.where != whole_declaration
        assert "{" not in line.message and "{" not in line.action
    (provincia_line,) = (line for line in lines if line.level is ModeloFormAttention.MISSING)
    for party in _SPANISH_DECLARADOS:
        assert party in provincia_line.message


def test_the_paper_signature_date_holds_no_figure_until_the_filer_signs(
    secure_objects: SecureObjectRepository,
) -> None:
    form = _calculated_form(secure_objects)

    (signature_date,) = (
        field
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1) and field.address.casilla_id == _SIGNATURE_DATE
    )
    assert signature_date.value is None
