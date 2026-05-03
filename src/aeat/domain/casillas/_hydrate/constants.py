from datetime import date
from pydantic import AnyHttpUrl, TypeAdapter
from aeat.core.config import PROJECT_ROOT

CORPUS_ROOT = PROJECT_ROOT / "corpus" / "casillas"
REVIEWED_BY = "human-codex"
REVIEWED_AT = date(2026, 5, 1)

_HTTP_URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAdapter(AnyHttpUrl)
YEARS = (2023, 2024, 2025, 2026)

IRPF_MANUAL_URL = (
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-{year}.html"
)
IVA_MANUAL_URL = (
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/iva-{year}.html"
)
SOCIEDADES_MANUAL_URL = "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/sociedades-{year}.html"
