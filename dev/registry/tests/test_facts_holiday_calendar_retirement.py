"""Direct-fact coverage for the retired legal-holiday calendar adapter."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from shutil import copy2

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import EventFactQuery, resolve_governed_fact
from cadrumo.domain.calculations.registry.facts.schema import (
    EventFactPayload,
    FactSelector,
    GovernedFactCatalogue,
)
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.deadlines.festivos import (
    HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
    HOLIDAY_EVENT_FACT_ID,
)

from ..compiler.fact_loader import load_governed_facts
from ..compiler.fact_providers import FACT_PROVIDER_REGISTRATIONS
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FACT_IDS = frozenset((HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID, HOLIDAY_EVENT_FACT_ID))
_AUTHORITY_DIGEST = "b" * 64
_LEGAL_REF = "ley-39-2015:art-30.5"

# This independent master is the published contract: every día inhábil of the
# Secretaría de Estado de Función Pública resolutions for 2024-2026, extracted
# from boe.es separately from the facts under test, with each national fiesta
# that falls on a weekend and without sub-territorial days such as the Val
# d'Aran swap of 26 December.
_SOURCE_2024 = (
    "boe-dias-inhabiles-age-2024",
    "resolucion-sefp-2023-11-16-dias-inhabiles-2024:anexo",
    "https://www.boe.es/buscar/doc.php?id=BOE-A-2023-23637",
)
_SOURCE_2025 = (
    "boe-dias-inhabiles-age-2025",
    "resolucion-sefp-2024-12-16-dias-inhabiles-2025:anexo",
    "https://www.boe.es/buscar/doc.php?id=BOE-A-2024-26935",
)
_SOURCE_2026 = (
    "boe-dias-inhabiles-age-2026",
    "resolucion-sefp-2025-11-18-dias-inhabiles-2026:anexo",
    "https://www.boe.es/buscar/doc.php?id=BOE-A-2025-23702",
)

_PUBLICATION_MASTER = {
    "holiday-calendar-publication:2024": (date(2024, 1, 1), date(2024, 12, 31), *_SOURCE_2024),
    "holiday-calendar-publication:2025": (date(2025, 1, 1), date(2025, 12, 31), *_SOURCE_2025),
    "holiday-calendar-publication:2026": (date(2026, 1, 1), date(2026, 12, 31), *_SOURCE_2026),
}

_EVENT_MASTER = {
    "2024-01-01:national:es": (date(2024, 1, 1), "national", None, "A\u00f1o Nuevo", *_SOURCE_2024),
    "2024-01-06:national:es": (date(2024, 1, 6), "national", None, "Epifan\u00eda del Se\u00f1or", *_SOURCE_2024),
    "2024-02-13:ccaa:es-ex": (date(2024, 2, 13), "ccaa", "ES-EX", "Martes de Carnaval", *_SOURCE_2024),
    "2024-02-28:ccaa:es-an": (date(2024, 2, 28), "ccaa", "ES-AN", "D\u00eda de Andaluc\u00eda", *_SOURCE_2024),
    "2024-03-01:ccaa:es-ib": (date(2024, 3, 1), "ccaa", "ES-IB", "D\u00eda de les Illes Balears", *_SOURCE_2024),
    "2024-03-19:ccaa:es-mc": (date(2024, 3, 19), "ccaa", "ES-MC", "San Jos\u00e9", *_SOURCE_2024),
    "2024-03-19:ccaa:es-vc": (date(2024, 3, 19), "ccaa", "ES-VC", "San Jos\u00e9", *_SOURCE_2024),
    "2024-03-28:ccaa:es-an": (date(2024, 3, 28), "ccaa", "ES-AN", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-ar": (date(2024, 3, 28), "ccaa", "ES-AR", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-as": (date(2024, 3, 28), "ccaa", "ES-AS", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-cb": (date(2024, 3, 28), "ccaa", "ES-CB", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-ce": (date(2024, 3, 28), "ccaa", "ES-CE", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-cl": (date(2024, 3, 28), "ccaa", "ES-CL", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-cm": (date(2024, 3, 28), "ccaa", "ES-CM", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-cn": (date(2024, 3, 28), "ccaa", "ES-CN", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-ex": (date(2024, 3, 28), "ccaa", "ES-EX", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-ga": (date(2024, 3, 28), "ccaa", "ES-GA", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-ib": (date(2024, 3, 28), "ccaa", "ES-IB", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-mc": (date(2024, 3, 28), "ccaa", "ES-MC", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-md": (date(2024, 3, 28), "ccaa", "ES-MD", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-ml": (date(2024, 3, 28), "ccaa", "ES-ML", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-nc": (date(2024, 3, 28), "ccaa", "ES-NC", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-pv": (date(2024, 3, 28), "ccaa", "ES-PV", "Jueves Santo", *_SOURCE_2024),
    "2024-03-28:ccaa:es-ri": (date(2024, 3, 28), "ccaa", "ES-RI", "Jueves Santo", *_SOURCE_2024),
    "2024-03-29:national:es": (date(2024, 3, 29), "national", None, "Viernes Santo", *_SOURCE_2024),
    "2024-04-01:ccaa:es-cb": (date(2024, 4, 1), "ccaa", "ES-CB", "Lunes de Pascua", *_SOURCE_2024),
    "2024-04-01:ccaa:es-ct": (date(2024, 4, 1), "ccaa", "ES-CT", "Lunes de Pascua", *_SOURCE_2024),
    "2024-04-01:ccaa:es-ib": (date(2024, 4, 1), "ccaa", "ES-IB", "Lunes de Pascua", *_SOURCE_2024),
    "2024-04-01:ccaa:es-nc": (date(2024, 4, 1), "ccaa", "ES-NC", "Lunes de Pascua", *_SOURCE_2024),
    "2024-04-01:ccaa:es-pv": (date(2024, 4, 1), "ccaa", "ES-PV", "Lunes de Pascua", *_SOURCE_2024),
    "2024-04-01:ccaa:es-ri": (date(2024, 4, 1), "ccaa", "ES-RI", "Lunes de Pascua", *_SOURCE_2024),
    "2024-04-01:ccaa:es-vc": (date(2024, 4, 1), "ccaa", "ES-VC", "Lunes de Pascua", *_SOURCE_2024),
    "2024-04-23:ccaa:es-ar": (date(2024, 4, 23), "ccaa", "ES-AR", "San Jorge/D\u00eda de Arag\u00f3n", *_SOURCE_2024),
    "2024-04-23:ccaa:es-cl": (date(2024, 4, 23), "ccaa", "ES-CL", "Fiesta de Castilla y Le\u00f3n", *_SOURCE_2024),
    "2024-05-01:national:es": (date(2024, 5, 1), "national", None, "Fiesta del Trabajo", *_SOURCE_2024),
    "2024-05-02:ccaa:es-md": (date(2024, 5, 2), "ccaa", "ES-MD", "Fiesta de la Comunidad de Madrid", *_SOURCE_2024),
    "2024-05-17:ccaa:es-ga": (date(2024, 5, 17), "ccaa", "ES-GA", "D\u00eda de las Letras Gallegas", *_SOURCE_2024),
    "2024-05-30:ccaa:es-cm": (date(2024, 5, 30), "ccaa", "ES-CM", "Corpus Christi", *_SOURCE_2024),
    "2024-05-30:ccaa:es-cn": (date(2024, 5, 30), "ccaa", "ES-CN", "D\u00eda de Canarias", *_SOURCE_2024),
    "2024-05-31:ccaa:es-cm": (date(2024, 5, 31), "ccaa", "ES-CM", "D\u00eda de Castilla-La Mancha", *_SOURCE_2024),
    "2024-06-10:ccaa:es-ri": (
        date(2024, 6, 10),
        "ccaa",
        "ES-RI",
        "Lunes siguiente al D\u00eda de La Rioja",
        *_SOURCE_2024,
    ),
    "2024-06-17:ccaa:es-ce": (date(2024, 6, 17), "ccaa", "ES-CE", "Fiesta del Sacrificio-Eidul Adha", *_SOURCE_2024),
    "2024-06-17:ccaa:es-ml": (date(2024, 6, 17), "ccaa", "ES-ML", "Fiesta del Sacrificio-Aid Al Adha", *_SOURCE_2024),
    "2024-06-24:ccaa:es-ct": (date(2024, 6, 24), "ccaa", "ES-CT", "San Juan", *_SOURCE_2024),
    "2024-06-24:ccaa:es-vc": (date(2024, 6, 24), "ccaa", "ES-VC", "San Juan", *_SOURCE_2024),
    "2024-07-25:ccaa:es-cb": (
        date(2024, 7, 25),
        "ccaa",
        "ES-CB",
        "Santiago Ap\u00f3stol/D\u00eda Nacional de Galicia",
        *_SOURCE_2024,
    ),
    "2024-07-25:ccaa:es-ga": (
        date(2024, 7, 25),
        "ccaa",
        "ES-GA",
        "Santiago Ap\u00f3stol/D\u00eda Nacional de Galicia",
        *_SOURCE_2024,
    ),
    "2024-07-25:ccaa:es-md": (
        date(2024, 7, 25),
        "ccaa",
        "ES-MD",
        "Santiago Ap\u00f3stol/D\u00eda Nacional de Galicia",
        *_SOURCE_2024,
    ),
    "2024-07-25:ccaa:es-nc": (
        date(2024, 7, 25),
        "ccaa",
        "ES-NC",
        "Santiago Ap\u00f3stol/D\u00eda Nacional de Galicia",
        *_SOURCE_2024,
    ),
    "2024-07-25:ccaa:es-pv": (
        date(2024, 7, 25),
        "ccaa",
        "ES-PV",
        "Santiago Ap\u00f3stol/D\u00eda Nacional de Galicia",
        *_SOURCE_2024,
    ),
    "2024-08-05:ccaa:es-ce": (date(2024, 8, 5), "ccaa", "ES-CE", "Nuestra Se\u00f1ora de \u00c1frica", *_SOURCE_2024),
    "2024-08-15:national:es": (date(2024, 8, 15), "national", None, "Asunci\u00f3n de la Virgen", *_SOURCE_2024),
    "2024-09-09:ccaa:es-as": (
        date(2024, 9, 9),
        "ccaa",
        "ES-AS",
        "Lunes siguiente al D\u00eda de Asturias",
        *_SOURCE_2024,
    ),
    "2024-09-11:ccaa:es-ct": (date(2024, 9, 11), "ccaa", "ES-CT", "Fiesta Nacional de Catalu\u00f1a", *_SOURCE_2024),
    "2024-10-09:ccaa:es-vc": (date(2024, 10, 9), "ccaa", "ES-VC", "D\u00eda de la Comunitat Valenciana", *_SOURCE_2024),
    "2024-10-12:national:es": (date(2024, 10, 12), "national", None, "Fiesta Nacional de Espa\u00f1a", *_SOURCE_2024),
    "2024-11-01:national:es": (date(2024, 11, 1), "national", None, "Todos los Santos", *_SOURCE_2024),
    "2024-12-06:national:es": (
        date(2024, 12, 6),
        "national",
        None,
        "D\u00eda de la Constituci\u00f3n Espa\u00f1ola",
        *_SOURCE_2024,
    ),
    "2024-12-09:ccaa:es-an": (
        date(2024, 12, 9),
        "ccaa",
        "ES-AN",
        "Lunes siguiente a la Inmaculada Concepci\u00f3n",
        *_SOURCE_2024,
    ),
    "2024-12-09:ccaa:es-ar": (
        date(2024, 12, 9),
        "ccaa",
        "ES-AR",
        "Lunes siguiente a la Inmaculada Concepci\u00f3n",
        *_SOURCE_2024,
    ),
    "2024-12-09:ccaa:es-as": (
        date(2024, 12, 9),
        "ccaa",
        "ES-AS",
        "Lunes siguiente a la Inmaculada Concepci\u00f3n",
        *_SOURCE_2024,
    ),
    "2024-12-09:ccaa:es-cl": (
        date(2024, 12, 9),
        "ccaa",
        "ES-CL",
        "Lunes siguiente a la Inmaculada Concepci\u00f3n",
        *_SOURCE_2024,
    ),
    "2024-12-09:ccaa:es-ex": (
        date(2024, 12, 9),
        "ccaa",
        "ES-EX",
        "Lunes siguiente a la Inmaculada Concepci\u00f3n",
        *_SOURCE_2024,
    ),
    "2024-12-09:ccaa:es-mc": (
        date(2024, 12, 9),
        "ccaa",
        "ES-MC",
        "Lunes siguiente a la Inmaculada Concepci\u00f3n",
        *_SOURCE_2024,
    ),
    "2024-12-09:ccaa:es-ml": (
        date(2024, 12, 9),
        "ccaa",
        "ES-ML",
        "Lunes siguiente a la Inmaculada Concepci\u00f3n",
        *_SOURCE_2024,
    ),
    "2024-12-25:national:es": (date(2024, 12, 25), "national", None, "Natividad del Se\u00f1or", *_SOURCE_2024),
    "2025-01-01:national:es": (date(2025, 1, 1), "national", None, "A\u00f1o Nuevo", *_SOURCE_2025),
    "2025-01-06:national:es": (date(2025, 1, 6), "national", None, "Epifan\u00eda del Se\u00f1or", *_SOURCE_2025),
    "2025-02-28:ccaa:es-an": (date(2025, 2, 28), "ccaa", "ES-AN", "D\u00eda de Andaluc\u00eda", *_SOURCE_2025),
    "2025-03-19:ccaa:es-mc": (date(2025, 3, 19), "ccaa", "ES-MC", "San Jos\u00e9", *_SOURCE_2025),
    "2025-03-19:ccaa:es-vc": (date(2025, 3, 19), "ccaa", "ES-VC", "San Jos\u00e9", *_SOURCE_2025),
    "2025-03-31:ccaa:es-ml": (date(2025, 3, 31), "ccaa", "ES-ML", "Fiesta del Eid Fitr", *_SOURCE_2025),
    "2025-04-17:ccaa:es-an": (date(2025, 4, 17), "ccaa", "ES-AN", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-ar": (date(2025, 4, 17), "ccaa", "ES-AR", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-as": (date(2025, 4, 17), "ccaa", "ES-AS", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-cb": (date(2025, 4, 17), "ccaa", "ES-CB", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-ce": (date(2025, 4, 17), "ccaa", "ES-CE", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-cl": (date(2025, 4, 17), "ccaa", "ES-CL", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-cm": (date(2025, 4, 17), "ccaa", "ES-CM", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-cn": (date(2025, 4, 17), "ccaa", "ES-CN", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-ex": (date(2025, 4, 17), "ccaa", "ES-EX", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-ga": (date(2025, 4, 17), "ccaa", "ES-GA", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-ib": (date(2025, 4, 17), "ccaa", "ES-IB", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-mc": (date(2025, 4, 17), "ccaa", "ES-MC", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-md": (date(2025, 4, 17), "ccaa", "ES-MD", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-ml": (date(2025, 4, 17), "ccaa", "ES-ML", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-nc": (date(2025, 4, 17), "ccaa", "ES-NC", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-pv": (date(2025, 4, 17), "ccaa", "ES-PV", "Jueves Santo", *_SOURCE_2025),
    "2025-04-17:ccaa:es-ri": (date(2025, 4, 17), "ccaa", "ES-RI", "Jueves Santo", *_SOURCE_2025),
    "2025-04-18:national:es": (date(2025, 4, 18), "national", None, "Viernes Santo", *_SOURCE_2025),
    "2025-04-21:ccaa:es-ct": (date(2025, 4, 21), "ccaa", "ES-CT", "Lunes de Pascua", *_SOURCE_2025),
    "2025-04-21:ccaa:es-nc": (date(2025, 4, 21), "ccaa", "ES-NC", "Lunes de Pascua", *_SOURCE_2025),
    "2025-04-21:ccaa:es-pv": (date(2025, 4, 21), "ccaa", "ES-PV", "Lunes de Pascua", *_SOURCE_2025),
    "2025-04-21:ccaa:es-ri": (date(2025, 4, 21), "ccaa", "ES-RI", "Lunes de Pascua", *_SOURCE_2025),
    "2025-04-21:ccaa:es-vc": (date(2025, 4, 21), "ccaa", "ES-VC", "Lunes de Pascua", *_SOURCE_2025),
    "2025-04-23:ccaa:es-ar": (date(2025, 4, 23), "ccaa", "ES-AR", "San Jorge/D\u00eda de Arag\u00f3n", *_SOURCE_2025),
    "2025-04-23:ccaa:es-cl": (date(2025, 4, 23), "ccaa", "ES-CL", "Fiesta de Castilla y Le\u00f3n", *_SOURCE_2025),
    "2025-05-01:national:es": (date(2025, 5, 1), "national", None, "Fiesta del Trabajo", *_SOURCE_2025),
    "2025-05-02:ccaa:es-md": (date(2025, 5, 2), "ccaa", "ES-MD", "Fiesta de la Comunidad de Madrid", *_SOURCE_2025),
    "2025-05-30:ccaa:es-cn": (date(2025, 5, 30), "ccaa", "ES-CN", "D\u00eda de Canarias", *_SOURCE_2025),
    "2025-06-06:ccaa:es-ce": (date(2025, 6, 6), "ccaa", "ES-CE", "Fiesta del Sacrificio - Eidul Adha", *_SOURCE_2025),
    "2025-06-06:ccaa:es-ml": (date(2025, 6, 6), "ccaa", "ES-ML", "Fiesta del Sacrificio - Aid Al Adha", *_SOURCE_2025),
    "2025-06-09:ccaa:es-mc": (date(2025, 6, 9), "ccaa", "ES-MC", "D\u00eda de la Regi\u00f3n de Murcia", *_SOURCE_2025),
    "2025-06-09:ccaa:es-ri": (date(2025, 6, 9), "ccaa", "ES-RI", "D\u00eda de la Rioja", *_SOURCE_2025),
    "2025-06-19:ccaa:es-cm": (date(2025, 6, 19), "ccaa", "ES-CM", "Fiesta del Corpus Christi", *_SOURCE_2025),
    "2025-06-24:ccaa:es-ct": (date(2025, 6, 24), "ccaa", "ES-CT", "San Juan", *_SOURCE_2025),
    "2025-06-24:ccaa:es-vc": (date(2025, 6, 24), "ccaa", "ES-VC", "San Juan", *_SOURCE_2025),
    "2025-07-25:ccaa:es-ga": (
        date(2025, 7, 25),
        "ccaa",
        "ES-GA",
        "Santiago Ap\u00f3stol/D\u00eda Nacional de Galicia",
        *_SOURCE_2025,
    ),
    "2025-07-25:ccaa:es-md": (
        date(2025, 7, 25),
        "ccaa",
        "ES-MD",
        "Santiago Ap\u00f3stol/D\u00eda Nacional de Galicia",
        *_SOURCE_2025,
    ),
    "2025-07-25:ccaa:es-nc": (
        date(2025, 7, 25),
        "ccaa",
        "ES-NC",
        "Santiago Ap\u00f3stol/D\u00eda Nacional de Galicia",
        *_SOURCE_2025,
    ),
    "2025-07-25:ccaa:es-pv": (
        date(2025, 7, 25),
        "ccaa",
        "ES-PV",
        "Santiago Ap\u00f3stol/D\u00eda Nacional de Galicia",
        *_SOURCE_2025,
    ),
    "2025-07-28:ccaa:es-cb": (
        date(2025, 7, 28),
        "ccaa",
        "ES-CB",
        "D\u00eda de las Instituciones de Cantabria",
        *_SOURCE_2025,
    ),
    "2025-08-05:ccaa:es-ce": (date(2025, 8, 5), "ccaa", "ES-CE", "Nuestra Se\u00f1ora de \u00c1frica", *_SOURCE_2025),
    "2025-08-15:national:es": (date(2025, 8, 15), "national", None, "Asunci\u00f3n de la Virgen", *_SOURCE_2025),
    "2025-09-08:ccaa:es-as": (date(2025, 9, 8), "ccaa", "ES-AS", "D\u00eda de Asturias", *_SOURCE_2025),
    "2025-09-08:ccaa:es-ex": (date(2025, 9, 8), "ccaa", "ES-EX", "D\u00eda de Extremadura", *_SOURCE_2025),
    "2025-09-11:ccaa:es-ct": (date(2025, 9, 11), "ccaa", "ES-CT", "Fiesta Nacional de Catalu\u00f1a", *_SOURCE_2025),
    "2025-09-15:ccaa:es-cb": (date(2025, 9, 15), "ccaa", "ES-CB", "La Bien Aparecida", *_SOURCE_2025),
    "2025-10-09:ccaa:es-vc": (date(2025, 10, 9), "ccaa", "ES-VC", "D\u00eda de la Comunitat Valenciana", *_SOURCE_2025),
    "2025-10-13:ccaa:es-an": (
        date(2025, 10, 13),
        "ccaa",
        "ES-AN",
        "Lunes siguiente al d\u00eda de la Fiesta Nacional de Espa\u00f1a",
        *_SOURCE_2025,
    ),
    "2025-10-13:ccaa:es-ar": (
        date(2025, 10, 13),
        "ccaa",
        "ES-AR",
        "Lunes siguiente al d\u00eda de la Fiesta Nacional de Espa\u00f1a",
        *_SOURCE_2025,
    ),
    "2025-10-13:ccaa:es-as": (
        date(2025, 10, 13),
        "ccaa",
        "ES-AS",
        "Lunes siguiente al d\u00eda de la Fiesta Nacional de Espa\u00f1a",
        *_SOURCE_2025,
    ),
    "2025-10-13:ccaa:es-cl": (
        date(2025, 10, 13),
        "ccaa",
        "ES-CL",
        "Lunes siguiente al d\u00eda de la Fiesta Nacional de Espa\u00f1a",
        *_SOURCE_2025,
    ),
    "2025-10-13:ccaa:es-ex": (
        date(2025, 10, 13),
        "ccaa",
        "ES-EX",
        "Lunes siguiente al d\u00eda de la Fiesta Nacional de Espa\u00f1a",
        *_SOURCE_2025,
    ),
    "2025-11-01:national:es": (date(2025, 11, 1), "national", None, "Todos los Santos", *_SOURCE_2025),
    "2025-12-06:national:es": (
        date(2025, 12, 6),
        "national",
        None,
        "D\u00eda de la Constituci\u00f3n Espa\u00f1ola",
        *_SOURCE_2025,
    ),
    "2025-12-08:national:es": (date(2025, 12, 8), "national", None, "Inmaculada Concepci\u00f3n", *_SOURCE_2025),
    "2025-12-25:national:es": (date(2025, 12, 25), "national", None, "Natividad del Se\u00f1or", *_SOURCE_2025),
    "2025-12-26:ccaa:es-ib": (date(2025, 12, 26), "ccaa", "ES-IB", "San Esteban", *_SOURCE_2025),
    "2026-01-01:national:es": (date(2026, 1, 1), "national", None, "A\u00f1o Nuevo", *_SOURCE_2026),
    "2026-01-06:national:es": (date(2026, 1, 6), "national", None, "Epifan\u00eda del Se\u00f1or", *_SOURCE_2026),
    "2026-03-02:ccaa:es-ib": (
        date(2026, 3, 2),
        "ccaa",
        "ES-IB",
        "Lunes siguiente al D\u00eda de les Illes Balears",
        *_SOURCE_2026,
    ),
    "2026-03-19:ccaa:es-ga": (date(2026, 3, 19), "ccaa", "ES-GA", "San Jos\u00e9", *_SOURCE_2026),
    "2026-03-19:ccaa:es-mc": (date(2026, 3, 19), "ccaa", "ES-MC", "San Jos\u00e9", *_SOURCE_2026),
    "2026-03-19:ccaa:es-nc": (date(2026, 3, 19), "ccaa", "ES-NC", "San Jos\u00e9", *_SOURCE_2026),
    "2026-03-19:ccaa:es-pv": (date(2026, 3, 19), "ccaa", "ES-PV", "San Jos\u00e9", *_SOURCE_2026),
    "2026-03-19:ccaa:es-vc": (date(2026, 3, 19), "ccaa", "ES-VC", "San Jos\u00e9", *_SOURCE_2026),
    "2026-03-20:ccaa:es-ml": (date(2026, 3, 20), "ccaa", "ES-ML", "Fiesta del Eid Fitr", *_SOURCE_2026),
    "2026-04-02:ccaa:es-an": (date(2026, 4, 2), "ccaa", "ES-AN", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-ar": (date(2026, 4, 2), "ccaa", "ES-AR", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-as": (date(2026, 4, 2), "ccaa", "ES-AS", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-cb": (date(2026, 4, 2), "ccaa", "ES-CB", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-ce": (date(2026, 4, 2), "ccaa", "ES-CE", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-cl": (date(2026, 4, 2), "ccaa", "ES-CL", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-cm": (date(2026, 4, 2), "ccaa", "ES-CM", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-cn": (date(2026, 4, 2), "ccaa", "ES-CN", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-ex": (date(2026, 4, 2), "ccaa", "ES-EX", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-ga": (date(2026, 4, 2), "ccaa", "ES-GA", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-ib": (date(2026, 4, 2), "ccaa", "ES-IB", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-mc": (date(2026, 4, 2), "ccaa", "ES-MC", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-md": (date(2026, 4, 2), "ccaa", "ES-MD", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-ml": (date(2026, 4, 2), "ccaa", "ES-ML", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-nc": (date(2026, 4, 2), "ccaa", "ES-NC", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-pv": (date(2026, 4, 2), "ccaa", "ES-PV", "Jueves Santo", *_SOURCE_2026),
    "2026-04-02:ccaa:es-ri": (date(2026, 4, 2), "ccaa", "ES-RI", "Jueves Santo", *_SOURCE_2026),
    "2026-04-03:national:es": (date(2026, 4, 3), "national", None, "Viernes Santo", *_SOURCE_2026),
    "2026-04-06:ccaa:es-cm": (date(2026, 4, 6), "ccaa", "ES-CM", "Lunes de Pascua", *_SOURCE_2026),
    "2026-04-06:ccaa:es-ct": (date(2026, 4, 6), "ccaa", "ES-CT", "Lunes de Pascua", *_SOURCE_2026),
    "2026-04-06:ccaa:es-ib": (date(2026, 4, 6), "ccaa", "ES-IB", "Lunes de Pascua", *_SOURCE_2026),
    "2026-04-06:ccaa:es-nc": (date(2026, 4, 6), "ccaa", "ES-NC", "Lunes de Pascua", *_SOURCE_2026),
    "2026-04-06:ccaa:es-pv": (date(2026, 4, 6), "ccaa", "ES-PV", "Lunes de Pascua", *_SOURCE_2026),
    "2026-04-06:ccaa:es-ri": (date(2026, 4, 6), "ccaa", "ES-RI", "Lunes de Pascua", *_SOURCE_2026),
    "2026-04-06:ccaa:es-vc": (date(2026, 4, 6), "ccaa", "ES-VC", "Lunes de Pascua", *_SOURCE_2026),
    "2026-04-23:ccaa:es-ar": (date(2026, 4, 23), "ccaa", "ES-AR", "San Jorge/D\u00eda de Arag\u00f3n", *_SOURCE_2026),
    "2026-04-23:ccaa:es-cl": (date(2026, 4, 23), "ccaa", "ES-CL", "Fiesta de Castilla y Le\u00f3n", *_SOURCE_2026),
    "2026-05-01:national:es": (date(2026, 5, 1), "national", None, "Fiesta del Trabajo", *_SOURCE_2026),
    "2026-05-27:ccaa:es-ce": (date(2026, 5, 27), "ccaa", "ES-CE", "Fiesta Sacrificio-Eidul Adha", *_SOURCE_2026),
    "2026-05-27:ccaa:es-ml": (date(2026, 5, 27), "ccaa", "ES-ML", "Fiesta Sacrificio-Aid al Adha", *_SOURCE_2026),
    "2026-06-04:ccaa:es-cm": (date(2026, 6, 4), "ccaa", "ES-CM", "Corpus Christi", *_SOURCE_2026),
    "2026-06-09:ccaa:es-mc": (date(2026, 6, 9), "ccaa", "ES-MC", "D\u00eda de la Regi\u00f3n de Murcia", *_SOURCE_2026),
    "2026-06-09:ccaa:es-ri": (date(2026, 6, 9), "ccaa", "ES-RI", "D\u00eda de la Rioja", *_SOURCE_2026),
    "2026-06-24:ccaa:es-ct": (date(2026, 6, 24), "ccaa", "ES-CT", "San Juan", *_SOURCE_2026),
    "2026-06-24:ccaa:es-ga": (date(2026, 6, 24), "ccaa", "ES-GA", "San Juan", *_SOURCE_2026),
    "2026-06-24:ccaa:es-vc": (date(2026, 6, 24), "ccaa", "ES-VC", "San Juan", *_SOURCE_2026),
    "2026-07-28:ccaa:es-cb": (
        date(2026, 7, 28),
        "ccaa",
        "ES-CB",
        "D\u00eda de las Instituciones de Cantabria",
        *_SOURCE_2026,
    ),
    "2026-08-05:ccaa:es-ce": (date(2026, 8, 5), "ccaa", "ES-CE", "Nuestra Se\u00f1ora de \u00c1frica", *_SOURCE_2026),
    "2026-08-15:national:es": (date(2026, 8, 15), "national", None, "Asunci\u00f3n de la Virgen", *_SOURCE_2026),
    "2026-09-02:ccaa:es-ce": (date(2026, 9, 2), "ccaa", "ES-CE", "D\u00eda de Ceuta", *_SOURCE_2026),
    "2026-09-08:ccaa:es-as": (date(2026, 9, 8), "ccaa", "ES-AS", "D\u00eda de Asturias", *_SOURCE_2026),
    "2026-09-08:ccaa:es-ex": (date(2026, 9, 8), "ccaa", "ES-EX", "D\u00eda de Extremadura", *_SOURCE_2026),
    "2026-09-11:ccaa:es-ct": (date(2026, 9, 11), "ccaa", "ES-CT", "Fiesta Nacional de Catalu\u00f1a", *_SOURCE_2026),
    "2026-09-15:ccaa:es-cb": (date(2026, 9, 15), "ccaa", "ES-CB", "La Bien Aparecida", *_SOURCE_2026),
    "2026-10-09:ccaa:es-vc": (date(2026, 10, 9), "ccaa", "ES-VC", "D\u00eda de la Comunitat Valenciana", *_SOURCE_2026),
    "2026-10-12:national:es": (date(2026, 10, 12), "national", None, "Fiesta Nacional de Espa\u00f1a", *_SOURCE_2026),
    "2026-11-02:ccaa:es-an": (
        date(2026, 11, 2),
        "ccaa",
        "ES-AN",
        "D\u00eda siguiente a Todos los Santos",
        *_SOURCE_2026,
    ),
    "2026-11-02:ccaa:es-ar": (
        date(2026, 11, 2),
        "ccaa",
        "ES-AR",
        "D\u00eda siguiente a Todos los Santos",
        *_SOURCE_2026,
    ),
    "2026-11-02:ccaa:es-as": (
        date(2026, 11, 2),
        "ccaa",
        "ES-AS",
        "D\u00eda siguiente a Todos los Santos",
        *_SOURCE_2026,
    ),
    "2026-11-02:ccaa:es-cl": (
        date(2026, 11, 2),
        "ccaa",
        "ES-CL",
        "D\u00eda siguiente a Todos los Santos",
        *_SOURCE_2026,
    ),
    "2026-11-02:ccaa:es-cm": (
        date(2026, 11, 2),
        "ccaa",
        "ES-CM",
        "D\u00eda siguiente a Todos los Santos",
        *_SOURCE_2026,
    ),
    "2026-11-02:ccaa:es-cn": (
        date(2026, 11, 2),
        "ccaa",
        "ES-CN",
        "D\u00eda siguiente a Todos los Santos",
        *_SOURCE_2026,
    ),
    "2026-11-02:ccaa:es-ex": (
        date(2026, 11, 2),
        "ccaa",
        "ES-EX",
        "D\u00eda siguiente a Todos los Santos",
        *_SOURCE_2026,
    ),
    "2026-11-02:ccaa:es-md": (
        date(2026, 11, 2),
        "ccaa",
        "ES-MD",
        "D\u00eda siguiente a Todos los Santos",
        *_SOURCE_2026,
    ),
    "2026-11-02:ccaa:es-nc": (
        date(2026, 11, 2),
        "ccaa",
        "ES-NC",
        "D\u00eda siguiente a Todos los Santos",
        *_SOURCE_2026,
    ),
    "2026-12-07:ccaa:es-an": (
        date(2026, 12, 7),
        "ccaa",
        "ES-AN",
        "Lunes siguiente al D\u00eda de la Constituci\u00f3n Espa\u00f1ola",
        *_SOURCE_2026,
    ),
    "2026-12-07:ccaa:es-ar": (
        date(2026, 12, 7),
        "ccaa",
        "ES-AR",
        "Lunes siguiente al D\u00eda de la Constituci\u00f3n Espa\u00f1ola",
        *_SOURCE_2026,
    ),
    "2026-12-07:ccaa:es-as": (
        date(2026, 12, 7),
        "ccaa",
        "ES-AS",
        "Lunes siguiente al D\u00eda de la Constituci\u00f3n Espa\u00f1ola",
        *_SOURCE_2026,
    ),
    "2026-12-07:ccaa:es-cb": (
        date(2026, 12, 7),
        "ccaa",
        "ES-CB",
        "Lunes siguiente al D\u00eda de la Constituci\u00f3n Espa\u00f1ola",
        *_SOURCE_2026,
    ),
    "2026-12-07:ccaa:es-cl": (
        date(2026, 12, 7),
        "ccaa",
        "ES-CL",
        "Lunes siguiente al D\u00eda de la Constituci\u00f3n Espa\u00f1ola",
        *_SOURCE_2026,
    ),
    "2026-12-07:ccaa:es-ex": (
        date(2026, 12, 7),
        "ccaa",
        "ES-EX",
        "Lunes siguiente al D\u00eda de la Constituci\u00f3n Espa\u00f1ola",
        *_SOURCE_2026,
    ),
    "2026-12-07:ccaa:es-mc": (
        date(2026, 12, 7),
        "ccaa",
        "ES-MC",
        "Lunes siguiente al D\u00eda de la Constituci\u00f3n Espa\u00f1ola",
        *_SOURCE_2026,
    ),
    "2026-12-07:ccaa:es-md": (
        date(2026, 12, 7),
        "ccaa",
        "ES-MD",
        "Lunes siguiente al D\u00eda de la Constituci\u00f3n Espa\u00f1ola",
        *_SOURCE_2026,
    ),
    "2026-12-07:ccaa:es-ml": (
        date(2026, 12, 7),
        "ccaa",
        "ES-ML",
        "Lunes siguiente al D\u00eda de la Constituci\u00f3n Espa\u00f1ola",
        *_SOURCE_2026,
    ),
    "2026-12-07:ccaa:es-ri": (
        date(2026, 12, 7),
        "ccaa",
        "ES-RI",
        "Lunes siguiente al D\u00eda de la Constituci\u00f3n Espa\u00f1ola",
        *_SOURCE_2026,
    ),
    "2026-12-08:national:es": (date(2026, 12, 8), "national", None, "Inmaculada Concepci\u00f3n", *_SOURCE_2026),
    "2026-12-25:national:es": (date(2026, 12, 25), "national", None, "Natividad del Se\u00f1or", *_SOURCE_2026),
}


def _catalogue(facts_dir: Path | None = None) -> GovernedFactCatalogue:
    root = facts_dir or bundled_path("registry", "aeat", "facts")
    facts = load_governed_facts(root)
    return GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts if fact.fact_id in _FACT_IDS})


def _publication_semantics(catalogue: GovernedFactCatalogue) -> dict[str, tuple[date, date, str, str, str]]:
    fact = catalogue.facts[HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID]
    result: dict[str, tuple[date, date, str, str, str]] = {}
    for variant in fact.variants:
        assert isinstance(variant.payload, EventFactPayload)
        outputs = {output.name: output.value for output in variant.payload.outputs}
        valid_from = variant.valid_from
        valid_to = variant.valid_to
        assert valid_from is not None
        assert valid_to is not None
        boe_ref = outputs["boe_ref"]
        boe_url = outputs["boe_url"]
        assert isinstance(boe_ref, str)
        assert isinstance(boe_url, str)
        assert variant.date_axis is DateAxis.SUBMISSION_DATE
        assert variant.payload.event_date == valid_from
        assert _LEGAL_REF in variant.legal_refs
        assert variant.source_refs == (variant.source_citations[0].source_ref,)
        assert variant.source_citations[0].required_text
        assert variant.ownership.value == "authored"
        result[variant.variant_id] = (
            valid_from,
            valid_to,
            variant.source_refs[0],
            boe_ref,
            boe_url,
        )
    return result


def _event_semantics(catalogue: GovernedFactCatalogue) -> dict[str, tuple[date, str, str | None, str, str, str, str]]:
    fact = catalogue.facts[HOLIDAY_EVENT_FACT_ID]
    result: dict[str, tuple[date, str, str | None, str, str, str, str]] = {}
    for variant in fact.variants:
        assert isinstance(variant.payload, EventFactPayload)
        selectors = {selector.name: selector.value for selector in variant.selectors}
        outputs = {output.name: output.value for output in variant.payload.outputs}
        valid_from = variant.valid_from
        valid_to = variant.valid_to
        assert valid_from is not None
        assert valid_to is not None
        jurisdiction = selectors["jurisdiction"]
        ccaa_code = selectors.get("ccaa_code")
        name = outputs["name"]
        boe_ref = outputs["boe_ref"]
        boe_url = outputs["boe_url"]
        assert isinstance(jurisdiction, str)
        assert ccaa_code is None or isinstance(ccaa_code, str)
        assert isinstance(name, str)
        assert isinstance(boe_ref, str)
        assert isinstance(boe_url, str)
        assert variant.date_axis is DateAxis.SUBMISSION_DATE
        assert valid_to == valid_from == variant.payload.event_date
        assert variant.payload.event_code == "public_holiday"
        assert _LEGAL_REF in variant.legal_refs
        assert variant.source_refs == (variant.source_citations[0].source_ref,)
        assert variant.source_citations[0].required_text
        assert variant.ownership.value == "authored"
        result[variant.variant_id] = (
            valid_from,
            jurisdiction,
            ccaa_code,
            name,
            variant.source_refs[0],
            boe_ref,
            boe_url,
        )
    return result


def _assert_exact_master(catalogue: GovernedFactCatalogue) -> None:
    assert _publication_semantics(catalogue) == _PUBLICATION_MASTER
    assert _event_semantics(catalogue) == _EVENT_MASTER


def test_authored_holiday_facts_match_the_complete_publication_and_event_master() -> None:
    """Every supported publication and event retains its direct semantic record."""
    catalogue = _catalogue()
    _assert_exact_master(catalogue)

    publication_fact = catalogue.facts[HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID]
    for publication in publication_fact.variants:
        assert publication.valid_from is not None
        resolved = resolve_governed_fact(
            catalogue,
            EventFactQuery(
                fact_id=HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=date(publication.valid_from.year, 7, 1),
            ),
            authority_digest=_AUTHORITY_DIGEST,
            support=committed_supported_filing_years(),
        )
        assert resolved.variant_id == publication.variant_id

    event_fact = catalogue.facts[HOLIDAY_EVENT_FACT_ID]
    for event in event_fact.variants:
        assert event.valid_from is not None
        resolved = resolve_governed_fact(
            catalogue,
            EventFactQuery(
                fact_id=HOLIDAY_EVENT_FACT_ID,
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=event.valid_from,
                selectors=event.selectors,
            ),
            authority_digest=_AUTHORITY_DIGEST,
            support=committed_supported_filing_years(),
        )
        assert resolved.variant_id == event.variant_id


def test_a_same_count_holiday_substitution_breaks_the_direct_fact_master(tmp_path: Path) -> None:
    """Mutation bite: matching the old row count cannot mask a changed event."""
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    source = bundled_path("registry", "aeat", "facts", "0067-public-holiday.toml")
    target = facts_dir / source.name
    copy2(source, target)

    original = target.read_text(encoding="utf-8")
    mutated = original.replace(
        'value = "Fiesta de la Comunidad de Madrid"',
        'value = "Fiesta de la Comunidad de Murcia"',
        1,
    )
    assert mutated != original, "the same-count mutation target was not found"
    target.write_text(mutated, encoding="utf-8")

    catalogue = _catalogue(facts_dir)
    assert len(_event_semantics(catalogue)) == len(_EVENT_MASTER)
    with pytest.raises(AssertionError):
        assert _event_semantics(catalogue) == _EVENT_MASTER


def test_removing_a_direct_holiday_variant_breaks_its_exact_query(tmp_path: Path) -> None:
    """Mutation bite: a deleted direct fact cannot be masked by any adapter."""
    facts_dir = tmp_path / "facts"
    facts_dir.mkdir()
    source = bundled_path("registry", "aeat", "facts", "0067-public-holiday.toml")
    target = facts_dir / source.name
    copy2(source, target)

    original = target.read_text(encoding="utf-8")
    marker = '[[fact.variants]]\nvariant_id = "2025-05-02:ccaa:es-md"'
    start = original.index(marker)
    next_variant = original.index("[[fact.variants]]", start + len(marker))
    target.write_text(original[:start] + original[next_variant:], encoding="utf-8")

    catalogue = _catalogue(facts_dir)
    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        resolve_governed_fact(
            catalogue,
            EventFactQuery(
                fact_id=HOLIDAY_EVENT_FACT_ID,
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=date(2025, 5, 2),
                selectors=(
                    FactSelector(name="jurisdiction", value="ccaa"),
                    FactSelector(name="ccaa_code", value="ES-MD"),
                ),
            ),
            authority_digest=_AUTHORITY_DIGEST,
            support=committed_supported_filing_years(),
        )


def test_holiday_adapter_and_raw_calendar_census_are_empty() -> None:
    """Retirement is atomic: no raw calendar compiler, directory, or provider survives."""
    registry_root = bundled_path("registry", "aeat")
    repository_root = Path(__file__).resolve().parents[3]

    assert not tuple((registry_root / "calendars").glob("festivos-*.toml"))
    assert not (repository_root / "dev" / "registry" / "compiler" / "holidays.py").exists()
    assert "legal-holiday-calendars" not in {registration.provider_id for registration in FACT_PROVIDER_REGISTRATIONS}
