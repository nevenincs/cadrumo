from pathlib import Path

from ..models import CasillaCatalogue
from .data import (
    M190_CASILLAS,
    M193_CASILLAS,
    M232_CASILLAS,
    M347_CASILLAS,
    M349_CASILLAS,
    M369_CASILLAS,
    M720_CASILLAS,
    M840_CASILLAS,
)
from .metadata import _source_url_for as _source_url_for
from .records import (
    CasillaRecord,
    _hydrate_censal,
    _hydrate_from_rulesets,
    _hydrate_manual,
    _hydrate_modelo_111,
)


def hydrate_catalogue(modelo: str, year: int) -> list[CasillaRecord]:
    if modelo in {"036", "037"}:
        return _hydrate_censal(modelo, year)
    if modelo == "111":
        return _hydrate_modelo_111(year)
    if modelo == "232":
        return _hydrate_manual(modelo, year, M232_CASILLAS)
    if modelo == "369":
        return _hydrate_manual(modelo, year, M369_CASILLAS, period_id="1T")
    if modelo == "720":
        return _hydrate_manual(modelo, year, M720_CASILLAS)
    if modelo == "190":
        return _hydrate_manual(modelo, year, M190_CASILLAS)
    if modelo == "193":
        return _hydrate_manual(modelo, year, M193_CASILLAS)
    if modelo == "347":
        return _hydrate_manual(modelo, year, M347_CASILLAS)
    if modelo == "349":
        return _hydrate_manual(modelo, year, M349_CASILLAS, period_id="1M")
    if modelo == "840":
        return _hydrate_manual(modelo, year, M840_CASILLAS)
    return _hydrate_from_rulesets(modelo, year)


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
    """Build, and optionally persist, deterministic corpus projections.

    The default is check-only. Repository writes require ``write=True``
    and an explicit target, or ``all_targets=True`` for the exceptional
    full-tree materialization case.
    """
    from ...modelos import MODELO_REGISTRY
    from ..catalogue import save_casillas

    if not all_targets and modelo is None:
        raise ValueError("modelo is required unless all_targets=True")
    if not all_targets and year is None and period is None:
        raise ValueError("year or period is required unless all_targets=True")
    if write and root is None:
        raise ValueError("write requires an explicit root")

    catalogues: list[CasillaCatalogue] = []
    if all_targets:
        for code in MODELO_REGISTRY:
            for target_year in (2024, 2025, 2026):
                catalogues.extend(materialize_catalogues(modelo=code.value, year=target_year))
    else:
        assert modelo is not None
        catalogues.extend(materialize_catalogues(modelo=modelo, year=year, period=period))

    if write:
        for catalogue in catalogues:
            save_casillas(catalogue, root=root)
    return tuple(catalogues)
