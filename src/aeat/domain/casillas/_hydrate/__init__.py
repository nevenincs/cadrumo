from pathlib import Path

from ..models import CasillaCatalogue, CasillaRecord


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
    if not all_targets and modelo is None:
        raise ValueError("modelo is required unless all_targets=True")
    if not all_targets and year is None and period is None:
        raise ValueError("year or period is required unless all_targets=True")
    if write or root is not None:
        raise ValueError("casilla hydrate writes are disabled; migrate definitions through registry/aeat")

    catalogues: list[CasillaCatalogue] = []
    if all_targets:
        raise ValueError("casilla hydrate target discovery is disabled; use registry/aeat")
    else:
        assert modelo is not None
        catalogues.extend(materialize_catalogues(modelo=modelo, year=year, period=period))

    return tuple(catalogues)
