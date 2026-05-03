from .records import (
    CasillaRecord,
    _hydrate_censal,
    _hydrate_from_rulesets,
    _hydrate_manual,
    _hydrate_modelo_111
)
from .metadata import _source_url_for
from .data import (
    M232_CASILLAS,
    M369_CASILLAS,
    M720_CASILLAS,
    M190_CASILLAS,
    M193_CASILLAS,
    M347_CASILLAS,
    M349_CASILLAS,
    M840_CASILLAS
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

def run():
    """Run the deterministic corpus hydration generator."""
    from ..catalogue import CasillaCatalogue, save_casillas
    
    # Identify modelos and years
    modelos = ["130", "303", "100", "111", "036", "037", "232", "369", "720", "190", "193", "347", "349", "840"]
    years = [2024, 2025]
    
    for m in modelos:
        for y in years:
            records = hydrate_catalogue(m, y)
            if not records:
                continue
            
            # Group by period
            by_period = {}
            for r in records:
                by_period.setdefault(r.period, []).append(r)
            
            for period, period_records in by_period.items():
                cat = CasillaCatalogue(
                    modelo=f"MODELO_{m}",
                    period=period,
                    records=tuple(period_records)
                )
                save_casillas(cat)
