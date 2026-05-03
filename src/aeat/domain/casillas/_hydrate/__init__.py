from pathlib import Path

from ...modelos import ModeloCode, get_modelo
from ..models import CasillaCatalogue, CasillaRecord

_IRPF_MANUAL_URL = (
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-{year}.html"
)
_IVA_MANUAL_URL = (
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/iva-{year}.html"
)
_SOCIEDADES_MANUAL_URL = (
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/"
    "sociedades-{year}.html"
)
_CATEGORY_MANUAL_URL = {
    "irpf": _IRPF_MANUAL_URL,
    "iva": _IVA_MANUAL_URL,
    "retenciones": _IRPF_MANUAL_URL,
    "sociedades": _SOCIEDADES_MANUAL_URL,
}
_INFORMATIVA_MANUAL_OVERRIDES = {
    "232": _SOCIEDADES_MANUAL_URL,
    "347": _IVA_MANUAL_URL,
    "349": _IVA_MANUAL_URL,
}


def _upstream_modelos(modelo: str) -> tuple[str, ...]:
    upstream: list[str] = []
    for code in ModeloCode:
        meta = get_modelo(code.value)
        if meta.caps_into is not None and meta.caps_into.value == modelo:
            upstream.append(code.value)
    return tuple(sorted(upstream))


def _source_url_for(modelo: str, year: int) -> str:
    """Return the reviewed source URL formerly used by hydrate alignment tests."""
    meta = get_modelo(modelo)
    template = _CATEGORY_MANUAL_URL.get(meta.category.value)
    if template is not None:
        return template.format(year=year)
    if meta.category.value == "informativa":
        for upstream_code in _upstream_modelos(modelo):
            upstream_meta = get_modelo(upstream_code)
            upstream_template = _CATEGORY_MANUAL_URL.get(upstream_meta.category.value)
            if upstream_template is not None:
                return upstream_template.format(year=year)
        if meta.caps_into is not None:
            downstream_meta = get_modelo(meta.caps_into.value)
            downstream_template = _CATEGORY_MANUAL_URL.get(downstream_meta.category.value)
            if downstream_template is not None:
                return downstream_template.format(year=year)
        override = _INFORMATIVA_MANUAL_OVERRIDES.get(modelo)
        if override is not None:
            return override.format(year=year)
    for citation in meta.legal_basis:
        url = getattr(citation, "url", None)
        if url is not None:
            return str(url).split("#", 1)[0]
    return _IRPF_MANUAL_URL.format(year=year)


def hydrate_catalogue(modelo: str, year: int) -> list[CasillaRecord]:
    """Reject legacy casilla projection from rulesets/manual tables."""

    raise ValueError(f"casilla hydrate is disabled for modelo {modelo} year {year}; use registry/aeat")


def materialize_catalogues(
    *,
    modelo: str,
    year: int | None = None,
    period: str | None = None,
) -> tuple[CasillaCatalogue, ...]:
    """Build catalogue projections for one explicit modelo target."""
    if year is None:
        if period is None:
            raise ValueError("year or period is required")
        year = int(period[:4])

    records = hydrate_catalogue(modelo, year)
    if period is not None:
        records = [record for record in records if record.period == period]
    if not records:
        return ()

    by_period: dict[str, list[CasillaRecord]] = {}
    for record in records:
        by_period.setdefault(record.period, []).append(record)

    return tuple(
        CasillaCatalogue(
            modelo=f"MODELO_{modelo}",
            period=target_period,
            records=tuple(period_records),
        )
        for target_period, period_records in sorted(by_period.items())
    )


def run(
    *,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    write: bool = False,
    all_targets: bool = False,
    root: Path | None = None,
) -> tuple[CasillaCatalogue, ...]:
    """Build deterministic corpus projections without repository writes.

    The legacy write path is disabled. Filing-grade casilla definitions now
    belong in the central registry and reviewed TOML data, not in generated
    corpus projections.
    """
    from ...modelos import MODELO_REGISTRY

    if not all_targets and modelo is None:
        raise ValueError("modelo is required unless all_targets=True")
    if not all_targets and year is None and period is None:
        raise ValueError("year or period is required unless all_targets=True")
    if write or root is not None:
        raise ValueError("casilla hydrate writes are disabled; migrate definitions through registry/aeat")

    catalogues: list[CasillaCatalogue] = []
    if all_targets:
        for code in MODELO_REGISTRY:
            for target_year in (2024, 2025, 2026):
                catalogues.extend(materialize_catalogues(modelo=code.value, year=target_year))
    else:
        assert modelo is not None
        catalogues.extend(materialize_catalogues(modelo=modelo, year=year, period=period))

    return tuple(catalogues)
