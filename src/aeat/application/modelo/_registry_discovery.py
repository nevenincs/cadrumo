"""Application facades for modelo registry discovery queries."""

from __future__ import annotations

from datetime import date

from ...core.resources import resources
from ...domain.calculations.registry import InputKind, RegistryQueryService


def _service() -> RegistryQueryService:
    return RegistryQueryService(resources().modelos.authority)


def declared_modelo_period_tokens(modelo: str | None) -> tuple[str, ...]:
    """Return every registry-declared period token for one modelo."""
    if not modelo or not modelo.strip():
        return ()
    definition = resources().modelos.authority.validate_modelo(modelo.strip())
    return tuple(
        sorted({token for revision in definition.revisions.values() for token in revision.period_selector.periods}),
    )


def registry_modelo_codes() -> tuple[str, ...]:
    """Return modelo codes in registry order."""
    return tuple(str(modelo.id) for modelo in _service()._authority.modelos)


def registry_list_modelos(*, year: int | None = None):
    """Return the registry modelo list report."""
    return _service().list_modelos(year=year)


def registry_describe_modelo(modelo: str, *, period: str | None = None, as_of: date | None = None):
    """Return the registry modelo description report."""
    return _service().describe_modelo(modelo, period=period, as_of=as_of)


def registry_casillas(
    modelo: str,
    *,
    period: str | None = None,
    as_of: date | None = None,
    input_kind: InputKind | None = None,
    required: bool | None = None,
    form_number: str | None = None,
):
    """Return the registry casilla report."""
    return _service().casillas(
        modelo,
        period=period,
        as_of=as_of,
        input_kind=input_kind,
        required=required,
        form_number=form_number,
    )


def registry_bindings(modelo: str, *, period: str | None = None, as_of: date | None = None):
    """Return the registry bindings report for a modelo and optional period."""
    return _service().bindings(modelo, period=period, as_of=as_of)


def registry_bindings_for_year(modelo: str, *, filing_year: int, as_of: date | None = None):
    """Return the registry bindings report for a filing year."""
    return _service().bindings_for_year(modelo, filing_year=filing_year, as_of=as_of)


def registry_bindings_for_scope(modelo: str, *, filing_year: int, period: str, as_of: date | None = None):
    """Return the registry bindings report for an exact filing scope."""
    return _service().bindings_for_scope(modelo, filing_year=filing_year, period=period, as_of=as_of)


def registry_formulas(modelo: str, *, period: str | None = None, as_of: date | None = None):
    """Return the registry formulas report."""
    return _service().formulas(modelo, period=period, as_of=as_of)


__all__ = [
    "declared_modelo_period_tokens",
    "registry_bindings",
    "registry_bindings_for_scope",
    "registry_bindings_for_year",
    "registry_casillas",
    "registry_describe_modelo",
    "registry_formulas",
    "registry_list_modelos",
    "registry_modelo_codes",
]
