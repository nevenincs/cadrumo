"""Synthetic documents using the semantic census structures observed at AEAT."""

from __future__ import annotations

from html import escape

from ......core.config import Settings
from ..._html import parse_html

PATHS = Settings.external_constants().aeat.sede_paths


def table_document(heading: str, columns: tuple[str, ...], values: tuple[str, ...]) -> str:
    """Create one synthetic record without depending on production label maps."""
    headers = "".join(f"<th>{escape(column)}</th>" for column in columns)
    cells = "".join(f"<td>{escape(value)}</td>" for value in values)
    return f"<h1>{heading}</h1><table><thead><tr>{headers}</tr></thead><tbody><tr>{cells}</tr></tbody></table>"


ACTIVITIES_HTML = table_document(
    "Relación de Actividades",
    ("Sección", "Epígrafe", "Denominación", "Estado", "F.Inicio", "F.Baja", "Locales", "Num.Ref."),
    ("Profesional", "999", "ACTIVIDAD SINTÉTICA", "Alta", "01/01/2024", "", "", "SYNTHETIC-1"),
)
OBLIGATIONS_HTML = table_document(
    "Obligaciones tributarias",
    ("Descripción de la obligación", "Periodicidad", "F. Alta Efec.", "F. Baja Efec.", "F. Ult. Modif.", "Estado"),
    ("OBLIGACIÓN SINTÉTICA", "Trimestral", "01/01/2024", "", "01/01/2024", "Alta"),
)
TAX_HTML = """
<h1>Situación tributaria</h1>
<fieldset><legend>Impuesto sobre el Valor Añadido</legend>
<ul><li><span class="ASWeb_multi_idioma">C) Regímenes aplicables</span></li></ul>
<ul><li><span class="ASWeb_multi_idioma">Alta</span></li>
<li><span class="ASWeb_multi_idioma">Baja</span></li>
<li><span class="ASWeb_multi_idioma">Fecha</span></li></ul>
<ul><li class="ancho_5">510</li><li class="fondo_medio"><strong>X</strong></li>
<li class="fondo_medio">&nbsp;</li><li><span class="ASWeb_multi_idioma">General</span></li>
<li>511</li><li class="fondo_medio">01/01/2024</li></ul>
</fieldset>
"""
for _title in (
    "Impuesto sobre la Renta de las Personas Físicas",
    "Impuesto sobre Sociedades",
    "Impuesto sobre la Renta de No Residentes",
    "Régimen fiscal especial del Título II de la ley 49/2002",
    "Retenciones e ingresos a cuenta",
    "Otros Impuestos",
    "Regímenes Especiales Comercio Intracomunitario (Ventas a Distancia y No Sujeción art. 14 Ley I.V.A.)",
):
    TAX_HTML += f"""<fieldset><legend>{_title}</legend><ul>
    <li><span class="ASWeb_multi_idioma">Opción sintética</span></li>
    <li data-censal-value="">&nbsp;</li></ul></fieldset>"""


def consultation_documents(landing: str) -> dict[str, str]:
    """Attach current consultation controls to an existing synthetic identity page."""
    soup = parse_html(landing)
    destinations = {
        "Mis Actividades Económicas": PATHS.censal_actividades_entry,
        "Mi Situación Tributaria": PATHS.censal_situacion_tributaria,
        "Mis Obligaciones": PATHS.censal_obligaciones,
    }
    for anchor in soup.select("a"):
        target = destinations.get(anchor.get_text(" ", strip=True))
        if target is not None:
            anchor.attrs = {"onclick": f"window.open('{target}');return false;"}
    return {
        PATHS.censal_datos: str(soup),
        PATHS.censal_actividades: ACTIVITIES_HTML,
        PATHS.censal_situacion_tributaria: TAX_HTML,
        PATHS.censal_obligaciones: OBLIGATIONS_HTML,
    }
