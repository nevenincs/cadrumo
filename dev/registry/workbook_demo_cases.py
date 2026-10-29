"""Scenario coordinates for explicitly fictional registry workbooks."""

from dataclasses import dataclass
from decimal import Decimal

from cadrumo.core.authority_grade import RegistryAuthorityGrade


@dataclass(frozen=True)
class DemoCase:
    """A scenario coordinate; no form coordinates or copied fiscal formulas."""

    modelo: str
    revision: str
    result_casilla: str | None
    expected_result: Decimal | None
    filing_year: int = 2025
    authority_grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING
    period: str = "4T"


DEMO_CASES = (
    DemoCase("130", "2019-y-siguientes", "19", Decimal("6373")),
    DemoCase("303", "2022", "71", Decimal("1680"), filing_year=2022),
    DemoCase("303", "2023", "71", Decimal("1680"), filing_year=2023),
    DemoCase("303", "2024-hasta-08-y-2t", "71", Decimal("1680"), filing_year=2024, period="2T"),
    DemoCase("303", "2024-desde-09-y-3t", "71", Decimal("1680"), filing_year=2024),
    DemoCase("303", "2025", "71", Decimal("1680")),
    DemoCase("303", "2026-y-siguientes", "71", Decimal("1680"), filing_year=2026),
    DemoCase(
        "390",
        "2026",
        "iva.anual.resultado-liquidacion",
        Decimal("6720"),
        filing_year=2026,
        period="0A",
        authority_grade=RegistryAuthorityGrade.APPLICABILITY,
    ),
    DemoCase(
        "390", "2024", "iva.anual.sector-diferenciado-1.suma-deducciones", Decimal("900"), filing_year=2024, period="0A"
    ),
    DemoCase("390", "2025", "iva.anual.sector-diferenciado-1.suma-deducciones", Decimal("900"), period="0A"),
    DemoCase("349", "2020-y-siguientes", None, None),
    DemoCase("347", "2011-2024", None, None, filing_year=2024, period="0A"),
    DemoCase("347", "2025-y-siguientes", None, None, period="0A"),
    DemoCase("131", "2019-2023", "15", Decimal("580"), filing_year=2023),
    DemoCase("131", "2024", "15", Decimal("580"), filing_year=2024),
    DemoCase("131", "2025", "15", Decimal("580")),
    DemoCase("131", "2026", "15", Decimal("580"), filing_year=2026, period="2T"),
    DemoCase("131", "2026-3t-4t", "15", Decimal("580"), filing_year=2026),
    DemoCase("180", "2019-2022", "decl.retenciones-total", Decimal("3420"), filing_year=2022, period="0A"),
    DemoCase("180", "2023-y-siguientes", "decl.retenciones-total", Decimal("3420"), period="0A"),
    DemoCase("184", "2023-2024", None, None, filing_year=2024, period="0A"),
    DemoCase("184", "2025-y-siguientes", None, None, period="0A"),
    DemoCase("185", "2025-y-siguientes", None, None, filing_year=2026, period="03"),
    DemoCase("188", "2023-y-siguientes", None, None, period="0A", authority_grade=RegistryAuthorityGrade.APPLICABILITY),
    DemoCase(
        "189", "2022", None, None, filing_year=2022, period="0A", authority_grade=RegistryAuthorityGrade.APPLICABILITY
    ),
    DemoCase("189", "2023", None, None, filing_year=2023, period="0A"),
    DemoCase("189", "2024", None, None, filing_year=2024, period="0A"),
    DemoCase("189", "2025", None, None, period="0A"),
    DemoCase("193", "2022", "decl.retenciones-total", Decimal("570"), filing_year=2022, period="0A"),
    DemoCase("193", "2023", "decl.retenciones-total", Decimal("570"), filing_year=2023, period="0A"),
    DemoCase("193", "2024", "decl.retenciones-total", Decimal("570"), filing_year=2024, period="0A"),
    DemoCase("193", "2025-y-siguientes", "decl.retenciones-total", Decimal("570"), filing_year=2025, period="0A"),
    DemoCase("190", "2022", "decl.retenciones-total", Decimal("4200"), filing_year=2022, period="0A"),
    DemoCase("190", "2023", "decl.retenciones-total", Decimal("4200"), filing_year=2023, period="0A"),
    DemoCase("190", "2024", "decl.retenciones-total", Decimal("4200"), filing_year=2024, period="0A"),
    DemoCase("190", "2025-y-siguientes", "decl.retenciones-total", Decimal("4200"), period="0A"),
    DemoCase(
        "188", "2022", None, None, filing_year=2022, period="0A", authority_grade=RegistryAuthorityGrade.APPLICABILITY
    ),
    DemoCase("181", "2022-y-siguientes", None, None, period="0A", authority_grade=RegistryAuthorityGrade.APPLICABILITY),
    DemoCase("111", "2019-y-siguientes", "30", Decimal("1150")),
    DemoCase("115", "2019-y-siguientes", "05", Decimal("1900")),
    DemoCase("123", "2019-2023", "08", Decimal("1900"), filing_year=2023),
    DemoCase("123", "2024-y-siguientes", "14", Decimal("1900")),
    DemoCase("126", "2019-y-siguientes", "12", Decimal("1900"), authority_grade=RegistryAuthorityGrade.CALCULATION),
    DemoCase("128", "2019-y-siguientes", "07", Decimal("1900"), authority_grade=RegistryAuthorityGrade.CALCULATION),
    DemoCase("117", "2019-y-siguientes", "11", Decimal("2100"), authority_grade=RegistryAuthorityGrade.CALCULATION),
    DemoCase("216", "2024-y-siguientes", "21", Decimal("1800")),
    DemoCase(
        "122",
        "2017-y-siguientes",
        "resultado.a-ingresar",
        Decimal("300"),
        authority_grade=RegistryAuthorityGrade.APPLICABILITY,
        period="0A",
    ),
    DemoCase("136", "2022-2025", "07", Decimal("12000"), authority_grade=RegistryAuthorityGrade.CALCULATION),
    DemoCase(
        "136",
        "2026",
        "07",
        Decimal("12000"),
        filing_year=2026,
        authority_grade=RegistryAuthorityGrade.CALCULATION,
    ),
    DemoCase(
        "216",
        "2020-2023",
        "7",
        Decimal("1800"),
        filing_year=2023,
        authority_grade=RegistryAuthorityGrade.CALCULATION,
    ),
    DemoCase("145", "2012-01-31-y-siguientes", None, None, period="comunicacion"),
    DemoCase("232", "2018-y-siguientes", None, None, period="0A"),
    DemoCase("202", "2025-y-siguientes", "34", Decimal("19200"), period="1P"),
    DemoCase("202", "2019-2022", "34", Decimal("3200"), filing_year=2022, period="1P"),
    DemoCase("202", "2023-2024", "34", Decimal("3200"), filing_year=2024, period="1P"),
    DemoCase(
        "222",
        "2025-y-siguientes",
        "34",
        Decimal("19200"),
        authority_grade=RegistryAuthorityGrade.CALCULATION,
        period="1P",
    ),
    *(
        DemoCase(
            "222",
            str(year),
            "34",
            Decimal("3200"),
            filing_year=year,
            authority_grade=RegistryAuthorityGrade.CALCULATION,
            period="1P",
        )
        for year in (2022, 2023, 2024)
    ),
    *(
        DemoCase(
            "194",
            str(year),
            "03",
            Decimal("23.75"),
            filing_year=max(year, 2022),
            period="0A",
            authority_grade=RegistryAuthorityGrade.APPLICABILITY,
        )
        for year in (2019, 2023, 2024)
    ),
    DemoCase("156", "2003-y-siguientes", None, None, period="0A", authority_grade=RegistryAuthorityGrade.APPLICABILITY),
    DemoCase("308", "2019-y-siguientes", "decl.req-iva-devolver-17", Decimal("250.35"), period="0A"),
    DemoCase("309", "2023-y-siguientes", "decl.resultado-24", Decimal("210"), period="0A"),
    DemoCase("322", "2026-y-siguientes", "70", Decimal("1500"), filing_year=2026, period="12"),
    DemoCase(
        "309",
        "2018-2022",
        "decl.resultado-24",
        Decimal("210"),
        filing_year=2022,
        period="0A",
        authority_grade=RegistryAuthorityGrade.APPLICABILITY,
    ),
)
