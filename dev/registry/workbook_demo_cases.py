"""Scenario coordinates for explicitly fictional registry workbooks.

A scenario names its edition by position among the Modelo's editions in the
pinned authority, oldest first, and is filed for the newest supported year that
edition serves. The authority says which revision that is and which years it
covers; nothing here writes a revision id or a year.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from functools import cache

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from .compiler.authority import compiled_bundled_authority


def supported_horizon_year() -> int:
    """The newest filing year the pinned authority supports."""
    with bundled_indexed_authority().operation() as operation:
        return operation.supported_filing_years().horizon


@cache
def edition_ids(modelo_id: str) -> tuple[str, ...]:
    """Every edition (revision id) the pinned authority carries for ``modelo_id``, oldest first."""
    with bundled_indexed_authority().operation() as operation:
        editions = operation.modelo_directory(modelo_id).revisions
        return tuple(str(item.id) for item in sorted(editions, key=lambda item: (item.valid_from, str(item.id))))


def edition_id(modelo_id: str, position: int) -> str:
    """The edition at ``position`` among the Modelo's editions, oldest first."""
    return edition_ids(modelo_id)[position]


def oldest_edition_id(modelo_id: str) -> str:
    """The Modelo's oldest edition."""
    return edition_ids(modelo_id)[0]


def newest_edition_id(modelo_id: str) -> str:
    """The Modelo's newest edition."""
    return edition_ids(modelo_id)[-1]


def edition_declares(modelo_id: str, revision_id: str, casilla_id: str) -> bool:
    """Whether the edition's design declares the casilla."""
    with bundled_indexed_authority().operation() as operation:
        return any(str(item.id) == casilla_id for item in operation.revision(modelo_id, revision_id).casillas)


def has_differentiated_sectors(modelo_id: str, revision_id: str) -> bool:
    """Whether the edition's design carries the annual summary of deductions by differentiated sector."""
    return edition_declares(modelo_id, revision_id, "iva.anual.sector-diferenciado-1.suma-deducciones")


@dataclass(frozen=True)
class TemplateEdition:
    """The edition a fictional template preview is built from."""

    revision_id: str
    source_ref: str
    period: str


def template_edition(modelo_id: str, year: int, *, preferred_period: str = "0A") -> TemplateEdition:
    """The edition whose period selector serves ``year``, with its design source and a period it serves.

    The year may lie below the support floor: the registry's own sources carry
    those editions, and no filing-year admission is involved.
    """
    modelo = compiled_bundled_authority().modelo(modelo_id)
    (revision,) = (item for item in modelo.revisions.values() if item.period_selector.includes_year(year))
    (source_ref,) = (str(ref) for ref in revision.source_refs if str(ref).startswith(f"aeat-dr-{modelo_id}-"))
    served = tuple(str(token) for token in revision.period_selector.periods_for_year(year))
    period = preferred_period if preferred_period in served else served[0]
    return TemplateEdition(revision_id=str(revision.id), source_ref=source_ref, period=period)


def newest_historical_year(modelo_id: str) -> int:
    """The last year of the Modelo's newest edition that ended before the support floor."""
    with bundled_indexed_authority().operation() as operation:
        floor = operation.supported_filing_years().floor
    modelo = compiled_bundled_authority().modelo(modelo_id)
    ended = [
        item.period_selector.year_to
        for item in modelo.revisions.values()
        if item.period_selector.year_to is not None and item.period_selector.year_to < floor
    ]
    return max(ended)


@dataclass(frozen=True)
class DemoCase:
    """A scenario coordinate; no form coordinates or copied fiscal formulas."""

    modelo: str
    revision: str
    result_casilla: str | None
    expected_result: Decimal | None
    filing_year: int = field(default_factory=supported_horizon_year)
    authority_grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING
    period: str = "4T"


@dataclass(frozen=True)
class _Spec:
    """One demonstrated edition: its position among the Modelo's editions, oldest first."""

    modelo: str
    edition: int
    result_casilla: str | None
    expected_result: Decimal | None
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING
    period: str = "4T"


_SPECS = (
    _Spec("130", 0, "19", Decimal("6373")),
    _Spec("303", 0, "71", Decimal("1680")),
    _Spec("303", 1, "71", Decimal("1680")),
    _Spec("303", 2, "71", Decimal("1680"), period="2T"),
    _Spec("303", 3, "71", Decimal("1680")),
    _Spec("303", 4, "71", Decimal("1680")),
    _Spec("303", 6, "71", Decimal("1680")),
    _Spec(
        "390",
        5,
        "iva.anual.resultado-liquidacion",
        Decimal("6720"),
        grade=RegistryAuthorityGrade.APPLICABILITY,
        period="0A",
    ),
    _Spec("390", 3, "iva.anual.sector-diferenciado-1.suma-deducciones", Decimal("900"), period="0A"),
    _Spec("390", 4, "iva.anual.sector-diferenciado-1.suma-deducciones", Decimal("900"), period="0A"),
    _Spec("349", 0, None, None),
    _Spec("347", 0, None, None, period="0A"),
    _Spec("347", 1, None, None, period="0A"),
    _Spec("131", 0, "15", Decimal("580")),
    _Spec("131", 1, "15", Decimal("580")),
    _Spec("131", 2, "15", Decimal("580")),
    _Spec("131", 3, "15", Decimal("580"), period="2T"),
    _Spec("131", 4, "15", Decimal("580")),
    _Spec("180", 0, "decl.retenciones-total", Decimal("3420"), period="0A"),
    _Spec("180", 1, "decl.retenciones-total", Decimal("3420"), period="0A"),
    _Spec("184", 4, None, None, period="0A"),
    _Spec("184", 5, None, None, period="0A"),
    _Spec("185", 1, None, None, period="03"),
    _Spec("188", 1, None, None, grade=RegistryAuthorityGrade.APPLICABILITY, period="0A"),
    _Spec("189", 0, None, None, grade=RegistryAuthorityGrade.APPLICABILITY, period="0A"),
    _Spec("189", 1, None, None, period="0A"),
    _Spec("189", 2, None, None, period="0A"),
    _Spec("189", 3, None, None, period="0A"),
    _Spec("193", 0, "decl.retenciones-total", Decimal("570"), period="0A"),
    _Spec("193", 1, "decl.retenciones-total", Decimal("570"), period="0A"),
    _Spec("193", 2, "decl.retenciones-total", Decimal("570"), period="0A"),
    _Spec("193", 3, "decl.retenciones-total", Decimal("570"), period="0A"),
    _Spec("190", 0, "decl.retenciones-total", Decimal("4200"), period="0A"),
    _Spec("190", 1, "decl.retenciones-total", Decimal("4200"), period="0A"),
    _Spec("190", 2, "decl.retenciones-total", Decimal("4200"), period="0A"),
    _Spec("190", 3, "decl.retenciones-total", Decimal("4200"), period="0A"),
    _Spec("188", 0, None, None, grade=RegistryAuthorityGrade.APPLICABILITY, period="0A"),
    _Spec("181", 0, None, None, grade=RegistryAuthorityGrade.APPLICABILITY, period="0A"),
    _Spec("111", 0, "30", Decimal("1150")),
    _Spec("115", 0, "05", Decimal("1900")),
    _Spec("123", 0, "08", Decimal("1900")),
    _Spec("123", 1, "14", Decimal("1900")),
    _Spec("126", 0, "12", Decimal("1900"), grade=RegistryAuthorityGrade.CALCULATION),
    _Spec("128", 0, "07", Decimal("1900"), grade=RegistryAuthorityGrade.CALCULATION),
    _Spec("117", 0, "11", Decimal("2100"), grade=RegistryAuthorityGrade.CALCULATION),
    _Spec("216", 1, "21", Decimal("1800")),
    _Spec("122", 0, "resultado.a-ingresar", Decimal("300"), grade=RegistryAuthorityGrade.APPLICABILITY, period="0A"),
    _Spec("136", 0, "07", Decimal("12000"), grade=RegistryAuthorityGrade.CALCULATION),
    _Spec("136", 1, "07", Decimal("12000"), grade=RegistryAuthorityGrade.CALCULATION),
    _Spec("216", 0, "7", Decimal("1800"), grade=RegistryAuthorityGrade.CALCULATION),
    _Spec("145", 0, None, None, period="comunicacion"),
    _Spec("232", 1, None, None, period="0A"),
    _Spec("202", 2, "34", Decimal("19200"), period="1P"),
    _Spec("202", 0, "34", Decimal("3200"), period="1P"),
    _Spec("202", 1, "34", Decimal("3200"), period="1P"),
    _Spec("222", 3, "34", Decimal("19200"), grade=RegistryAuthorityGrade.CALCULATION, period="1P"),
    _Spec("222", 0, "34", Decimal("3200"), grade=RegistryAuthorityGrade.CALCULATION, period="1P"),
    _Spec("222", 1, "34", Decimal("3200"), grade=RegistryAuthorityGrade.CALCULATION, period="1P"),
    _Spec("222", 2, "34", Decimal("3200"), grade=RegistryAuthorityGrade.CALCULATION, period="1P"),
    _Spec("194", 0, "03", Decimal("23.75"), grade=RegistryAuthorityGrade.APPLICABILITY, period="0A"),
    _Spec("194", 1, "03", Decimal("23.75"), grade=RegistryAuthorityGrade.APPLICABILITY, period="0A"),
    _Spec("194", 2, "03", Decimal("23.75"), grade=RegistryAuthorityGrade.APPLICABILITY, period="0A"),
    _Spec("156", 0, None, None, grade=RegistryAuthorityGrade.APPLICABILITY, period="0A"),
    _Spec("308", 3, "decl.req-iva-devolver-17", Decimal("250.35"), period="0A"),
    _Spec("309", 3, "decl.resultado-24", Decimal("210"), period="0A"),
    _Spec("322", 3, "70", Decimal("1500"), period="12"),
    _Spec("309", 2, "decl.resultado-24", Decimal("210"), grade=RegistryAuthorityGrade.APPLICABILITY, period="0A"),
)


def _demo_cases(specs: tuple[_Spec, ...]) -> tuple[DemoCase, ...]:
    """Resolve each spec's edition and filing year against the pinned authority."""
    cases: list[DemoCase] = []
    with bundled_indexed_authority().operation() as operation:
        support = operation.supported_filing_years()
        for spec in specs:
            revision_id = edition_id(spec.modelo, spec.edition)
            revision = operation.revision(spec.modelo, revision_id)
            year = next(year for year in reversed(support.years) if revision.period_selector.includes_year(year))
            cases.append(
                DemoCase(
                    spec.modelo,
                    revision_id,
                    spec.result_casilla,
                    spec.expected_result,
                    filing_year=year,
                    authority_grade=spec.grade,
                    period=spec.period,
                )
            )
    return tuple(cases)


DEMO_CASES = _demo_cases(_SPECS)
