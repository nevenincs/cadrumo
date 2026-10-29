"""Retain census identity and consultation rows in their rendered source order."""

from textual.widgets import DataTable

from ....application.user_profile.censal_observation import CensalConsultation, CensalObservation, CensalSection


def populate_census_evidence_rows(table: DataTable[str], observation: CensalObservation) -> None:
    """Append every captured field and consultation cell, including explicit empty sections."""
    _identity_rows(table, observation)
    for consultation in observation.consultations:
        for section in consultation.sections:
            _section_rows(table, consultation, section)


def _identity_rows(table: DataTable[str], observation: CensalObservation) -> None:
    for group, record in (
        ("Datos Identificativos", observation.identity),
        ("Domicilio Fiscal", observation.domicilio_fiscal),
        ("Domicilio de Notificación", observation.domicilio_notificacion),
    ):
        for field, value in record.model_dump(mode="json").items():
            table.add_row(group, field.replace("_", " "), "" if value is None else str(value))


def _section_rows(table: DataTable[str], consultation: CensalConsultation, section: CensalSection) -> None:
    area = section.title
    if consultation.activity_row_index is not None:
        area = f"{area} · Actividad {consultation.activity_row_index + 1}"
    if not section.rows:
        table.add_row(area, "", "")
    for index, row in enumerate(section.rows, start=1):
        for cell in row.cells:
            role = "Casilla" if cell.role == "casilla" else None
            field = " · ".join(filter(None, (str(index), row.label, cell.column, role)))
            table.add_row(area, field, cell.text or "")
