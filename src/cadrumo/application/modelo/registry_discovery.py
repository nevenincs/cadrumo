"""Application Modelo registry discovery queries.

CLI discovery commands call this module instead of constructing
:class:`RegistryQueryService` or reading the registry authority directly. Each
query delegates to the central validated authority exposed by
``bundled_authority()`` and returns the domain query report unchanged.

The ``*_for_scope`` helpers accept a concrete :class:`~core.Period` and
pass its filing year plus bare registry token into the query service, so
revision selection stays inside the authority-backed registry layer.
"""

from __future__ import annotations

from datetime import date

from cadrumo.domain.calculations.registry.queries import RegistryQueryService
from cadrumo.domain.calculations.registry.query_reports import (
    ModeloBindingsReport,
    ModeloCasillaDetailReport,
    ModeloCasillasReport,
    ModeloDescribeReport,
    ModeloFormulasReport,
    ModeloListReport,
    ModeloSupportMatrixReport,
)

from ...core import Period, TaxDomain
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.schema_input_kind import InputKind


def _service() -> RegistryQueryService:
    return RegistryQueryService(bundled_authority())


def _refuse_unscoped_as_of(*, as_of: date | None, scoped_form: str) -> None:
    """Refuse an as_of argument on an unscoped discovery query, naming the scoped form.

    The unscoped path resolves the latest revision by period and cannot gate a
    point-in-time ``as_of`` against a revision's validity window; honouring it
    needs a filing year. Rather than accept-and-silently-ignore the argument
    (the accepted-parameter lie this contract closes), refuse it here at the
    operator-facing boundary and name the scoped query that does honour it.
    """
    if as_of is not None:
        raise RegistryValidationError(
            f"as_of is only honoured by the filing-year-scoped registry query; the unscoped "
            f"query resolves the latest revision by period and cannot apply a historical "
            f"boundary. Re-run {scoped_form} with an explicit filing year to honour as_of.",
        )


def declared_modelo_period_tokens(modelo: str | None) -> tuple[str, ...]:
    """Return every period token declared by any revision of one modelo."""
    if not modelo or not modelo.strip():
        return ()
    definition = bundled_authority().validate_modelo(modelo.strip())
    return tuple(
        sorted({token for revision in definition.revisions.values() for token in revision.period_selector.periods}),
    )


def registry_modelo_codes() -> tuple[str, ...]:
    """Return registry-backed modelo codes in authority order."""
    return tuple(row.code for row in _service().list_modelos().modelos)


def registry_support_matrix() -> ModeloSupportMatrixReport:
    """Return the registry-wide per-modelo support/capability matrix.

    Every :class:`~domain.calculations.registry.ModeloEntry` is derived
    directly from the loaded registry authority (calc-grade, manifest, export
    formats, extractor, declared casilla renames, declared deprecation
    decisions, and declared AEAT-portal cross-references) — never
    hand-maintained.
    """
    return _service().support_matrix()


def registry_list_modelos(*, year: int | None = None, domain: TaxDomain | None = None) -> ModeloListReport:
    """Return the registry modelo list report, optionally filtered by tax family."""
    return _service().list_modelos(year=year, domain=domain)


def registry_describe_modelo(
    modelo: str,
    *,
    period: str | None = None,
    as_of: date | None = None,
) -> ModeloDescribeReport:
    """Return the registry modelo description report."""
    _refuse_unscoped_as_of(as_of=as_of, scoped_form="registry_describe_modelo_for_scope")
    return _service().describe_modelo(modelo, period=period, as_of=as_of)


def registry_describe_modelo_for_scope(
    modelo: str,
    *,
    period: Period,
    as_of: date | None = None,
) -> ModeloDescribeReport:
    """Return the registry modelo description report for an exact :class:`Period`."""
    return _service().describe_modelo_for_scope(
        modelo,
        filing_year=period.filing_year,
        period=period.registry_token,
        as_of=as_of,
    )


def registry_describe_modelo_for_registry_scope(
    modelo: str,
    *,
    filing_year: int,
    period: str,
    as_of: date | None = None,
) -> ModeloDescribeReport:
    """Return a modelo description for an explicit filing-year registry scope."""
    return _service().describe_modelo_for_scope(
        modelo,
        filing_year=filing_year,
        period=period,
        as_of=as_of,
    )


def registry_casillas(
    modelo: str,
    *,
    period: str | None = None,
    as_of: date | None = None,
    input_kind: InputKind | None = None,
    required: bool | None = None,
    form_number: str | None = None,
) -> ModeloCasillasReport:
    """Return the registry casilla report."""
    _refuse_unscoped_as_of(as_of=as_of, scoped_form="registry_casillas_for_scope")
    return _service().casillas(
        modelo,
        period=period,
        as_of=as_of,
        input_kind=input_kind,
        required=required,
        form_number=form_number,
    )


def registry_casillas_for_scope(
    modelo: str,
    *,
    period: Period,
    as_of: date | None = None,
    input_kind: InputKind | None = None,
    required: bool | None = None,
    form_number: str | None = None,
) -> ModeloCasillasReport:
    """Return the registry casilla report for an exact :class:`Period`."""
    return _service().casillas_for_scope(
        modelo,
        filing_year=period.filing_year,
        period=period.registry_token,
        as_of=as_of,
        input_kind=input_kind,
        required=required,
        form_number=form_number,
    )


def registry_casillas_for_registry_scope(
    modelo: str,
    *,
    filing_year: int,
    period: str,
    as_of: date | None = None,
    input_kind: InputKind | None = None,
    required: bool | None = None,
    form_number: str | None = None,
) -> ModeloCasillasReport:
    """Return casillas for an explicit filing-year registry scope."""
    return _service().casillas_for_scope(
        modelo,
        filing_year=filing_year,
        period=period,
        as_of=as_of,
        input_kind=input_kind,
        required=required,
        form_number=form_number,
    )


def registry_casilla(
    modelo: str,
    casilla: str,
    *,
    period: str | None = None,
    as_of: date | None = None,
) -> ModeloCasillaDetailReport:
    """Return the single-casilla semantic detail report."""
    _refuse_unscoped_as_of(as_of=as_of, scoped_form="registry_casilla_for_registry_scope")
    return _service().casilla(modelo, casilla, period=period, as_of=as_of)


def registry_casilla_for_registry_scope(
    modelo: str,
    casilla: str,
    *,
    filing_year: int,
    period: str,
    as_of: date | None = None,
) -> ModeloCasillaDetailReport:
    """Return one casilla detail for an explicit filing-year registry scope."""
    return _service().casilla_for_scope(
        modelo,
        casilla,
        filing_year=filing_year,
        period=period,
        as_of=as_of,
    )


def registry_bindings(
    modelo: str,
    *,
    period: str | None = None,
    as_of: date | None = None,
) -> ModeloBindingsReport:
    """Return the registry bindings report for a modelo and optional period."""
    _refuse_unscoped_as_of(as_of=as_of, scoped_form="registry_bindings_for_year")
    return _service().bindings(modelo, period=period, as_of=as_of)


def registry_bindings_for_year(
    modelo: str,
    *,
    filing_year: int,
    as_of: date | None = None,
) -> ModeloBindingsReport:
    """Return the registry bindings report for a filing year."""
    return _service().bindings_for_year(modelo, filing_year=filing_year, as_of=as_of)


def registry_bindings_for_scope(
    modelo: str,
    *,
    period: Period,
    as_of: date | None = None,
) -> ModeloBindingsReport:
    """Return the registry bindings report for an exact :class:`Period`."""
    return _service().bindings_for_scope(
        modelo,
        filing_year=period.filing_year,
        period=period.registry_token,
        as_of=as_of,
    )


def registry_formulas(
    modelo: str,
    *,
    period: str | None = None,
    as_of: date | None = None,
) -> ModeloFormulasReport:
    """Return the registry formulas report."""
    _refuse_unscoped_as_of(as_of=as_of, scoped_form="registry_formulas_for_scope")
    return _service().formulas(modelo, period=period, as_of=as_of)


def registry_formulas_for_scope(
    modelo: str,
    *,
    period: Period,
    as_of: date | None = None,
) -> ModeloFormulasReport:
    """Return the registry formulas report for an exact :class:`Period`."""
    return _service().formulas_for_scope(
        modelo,
        filing_year=period.filing_year,
        period=period.registry_token,
        as_of=as_of,
    )


def registry_formulas_for_registry_scope(
    modelo: str,
    *,
    filing_year: int,
    period: str,
    as_of: date | None = None,
) -> ModeloFormulasReport:
    """Return formulas for an explicit filing-year registry scope."""
    return _service().formulas_for_scope(
        modelo,
        filing_year=filing_year,
        period=period,
        as_of=as_of,
    )


__all__ = [
    "declared_modelo_period_tokens",
    "registry_bindings",
    "registry_bindings_for_scope",
    "registry_bindings_for_year",
    "registry_casilla",
    "registry_casilla_for_registry_scope",
    "registry_casillas",
    "registry_casillas_for_registry_scope",
    "registry_casillas_for_scope",
    "registry_describe_modelo",
    "registry_describe_modelo_for_registry_scope",
    "registry_describe_modelo_for_scope",
    "registry_formulas",
    "registry_formulas_for_registry_scope",
    "registry_formulas_for_scope",
    "registry_list_modelos",
    "registry_modelo_codes",
    "registry_support_matrix",
]
