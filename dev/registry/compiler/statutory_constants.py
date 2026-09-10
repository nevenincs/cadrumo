"""Transitional governed-fact adapter for statutory Python declarations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from cadrumo.core.revision_review import RevisionReviewStatus
from cadrumo.domain.calculations.registry.facts.schema import (
    FactOwnership,
    GovernedFact,
    GovernedFactFamily,
    GovernedFactVariant,
    MappingFactEntry,
    MappingFactPayload,
    ScalarFactPayload,
)
from cadrumo.domain.calculations.registry.loader_cache import toml_file_fingerprint
from cadrumo.domain.calculations.registry.schema_base import DateAxis, SourceCitation

STATUTORY_CONSTANTS_PROVIDER_ID = "statutory-constants"
STATUTORY_CONSTANTS_PROVIDER_DIRECTORY = "statutory"
_SOURCE_BY_LEGAL_REF = {
    "rd-1065-2007:art-33": "boe-rd-1065-2007-statutory-facts",
    "ley-37-1992:art-108": "boe-liva-art-108-statutory-facts",
    "rdl-2-2004:art-82": "boe-rdl-2-2004-art-82-statutory-facts",
    "ley-35-2006:art-7": "boe-lirpf-statutory-facts",
    "ley-35-2006:art-20": "boe-lirpf-statutory-facts",
    "ley-35-2006:art-52-2021": "boe-lirpf-statutory-facts",
    "ley-35-2006:art-58": "boe-lirpf-statutory-facts",
    "ley-35-2006:art-61-norma-4": "boe-lirpf-statutory-facts",
    "ley-35-2006:art-81": "boe-lirpf-statutory-facts",
    "ley-35-2006:art-96": "boe-lirpf-statutory-facts",
    "ley-35-2006:dt-12": "boe-lirpf-statutory-facts",
    "ley-27-2014:art-40-3": "boe-lis-art-40-statutory-facts",
    "ley-19-1994:art-75": "boe-ley-19-1994-art-75-statutory-facts",
    "madrid-dl-1-2010:art-4": "aeat-madrid-birth-adoption-statutory-facts",
    "ley-44-2015:art-14": "boe-ley-44-2015-art-14-statutory-facts",
    "ley-39-2015:art-43.2": "boe-ley-39-2015-art-43-statutory-facts",
}
_CITATION_TEXT_BY_SYMBOL = {
    "M347_THRESHOLD_EUR": "3.005,06 euros durante el año natural",
    "M347_CLAVE_C_THRESHOLD_EUR": "300,51 euros durante el mismo periodo",
    "IVA_BIEN_ESCASO_VALOR_UMBRAL_EUR": "valor de adquisición sea inferior a quinientas mil pesetas",
    "MODELO_840_IAE_CIFRA_NEGOCIOS_EXEMPTION_THRESHOLD_EUR": "inferior a 1.000.000 de euros",
    "ART_7P_EXEMPTION_CAP_EUR": "límite máximo de 60.100 euros anuales",
    "MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR": "1.500 euros anuales",
    "WORK_INCOME_GENERAL_DECLARATION_LIMIT_EUR": "22.000 euros anuales",
    "MODELO_202_ART_40_3_INCN_THRESHOLD_EUR": "6 millones de euros durante los 12 meses anteriores",
    "MODELO_100_ART_20_TRABAJO_REDUCCION_RNT_CEILING_EUR": "19.747,5 euros",
    "MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR": "1.500 euros anuales",
    "REBECA_MARITIME_EXEMPTION_FRACTION": "renta exenta el 50 por 100",
    "DEDUCCION_MATERNIDAD_MENSUAL_EUR": "forma proporcional al número de meses",
    "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR": "1.200 euros anuales",
    "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR": "150 euros",
    "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR": "1.200 euros anuales",
    "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR": "1 de enero de 2023",
    "DEDUCCION_MATERNIDAD_COTIZACIONES_CEILING_RETIRED_FILING_YEAR": "1 de enero de 2023",
    "MINIMO_DESCENDIENTE_MAX_AGE": "menor de veinticinco años",
    "MINIMO_MENOR_TRES_MAX_AGE": "menor de tres años",
    "CUSTODIA_COMPARTIDA_PRORRATA_FACTOR": "por partes iguales",
    "ART_81_1_ENTRY_WINDOW_YEARS": "durante los tres años siguientes",
    "NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS": "Ámbito temporal de aplicación de la deducción",
    "DT12_RESCATE_REDUCCION_RATE": "reducción del 40 por ciento",
    "DT12_GENERAL_WINDOW_FOLLOWING_YEARS": "dos ejercicios siguientes",
    "DT12_TRANSITIONAL_CONTINGENCIA_FIRST_YEAR": "ejercicios 2011 a 2014",
    "DT12_TRANSITIONAL_CONTINGENCIA_LAST_YEAR": "ejercicios 2011 a 2014",
    "DT12_TRANSITIONAL_WINDOW_FOLLOWING_YEARS": "octavo ejercicio siguiente",
    "DT12_CLIFF_LAST_YEAR": "31 de diciembre de 2018",
    "SAL_RESERVA_DOTACION_RATE": "diez por ciento del beneficio líquido",
    "SAL_RESERVA_CAPITAL_MULTIPLE": "doble del capital social",
    "DEHU_RECHAZO_TACITO_DIAS_NATURALES": "diez días naturales",
}

_DATE_AXIS_BY_SYMBOL = {
    "IVA_BIEN_ESCASO_VALOR_UMBRAL_EUR": DateAxis.TRANSACTION_DATE,
    "REBECA_MARITIME_EXEMPTION_FRACTION": DateAxis.DEVENGO_DATE,
    "DEHU_RECHAZO_TACITO_DIAS_NATURALES": DateAxis.SUBMISSION_DATE,
}
_VALUE_BY_SYMBOL: dict[str, str | int | Decimal | bool | date] = {
    "M347_THRESHOLD_EUR": Decimal("3005.06"),
    "M347_CLAVE_C_THRESHOLD_EUR": Decimal("300.51"),
    "IVA_BIEN_ESCASO_VALOR_UMBRAL_EUR": Decimal("3005.06"),
    "MODELO_840_IAE_CIFRA_NEGOCIOS_EXEMPTION_THRESHOLD_EUR": Decimal("1000000.00"),
    "ART_7P_EXEMPTION_CAP_EUR": Decimal("60100"),
    "MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR": Decimal("1500"),
    "WORK_INCOME_GENERAL_DECLARATION_LIMIT_EUR": Decimal("22000"),
    "MODELO_202_ART_40_3_INCN_THRESHOLD_EUR": Decimal("6000000"),
    "MODELO_100_ART_20_TRABAJO_REDUCCION_RNT_CEILING_EUR": Decimal("19747.50"),
    "MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR": Decimal("1500"),
    "REBECA_MARITIME_EXEMPTION_FRACTION": Decimal("0.50"),
    "DEDUCCION_MATERNIDAD_MENSUAL_EUR": 100,
    "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR": 1200,
    "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR": 150,
    "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR": 1350,
    "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR": 2023,
    "DEDUCCION_MATERNIDAD_COTIZACIONES_CEILING_RETIRED_FILING_YEAR": 2023,
    "MINIMO_DESCENDIENTE_MAX_AGE": 25,
    "MINIMO_MENOR_TRES_MAX_AGE": 3,
    "CUSTODIA_COMPARTIDA_PRORRATA_FACTOR": Decimal("0.5"),
    "ART_81_1_ENTRY_WINDOW_YEARS": 3,
    "NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS": 2,
    "DT12_RESCATE_REDUCCION_RATE": Decimal("0.40"),
    "DT12_GENERAL_WINDOW_FOLLOWING_YEARS": 2,
    "DT12_TRANSITIONAL_CONTINGENCIA_FIRST_YEAR": 2011,
    "DT12_TRANSITIONAL_CONTINGENCIA_LAST_YEAR": 2014,
    "DT12_TRANSITIONAL_WINDOW_FOLLOWING_YEARS": 8,
    "DT12_CLIFF_LAST_YEAR": 2018,
    "SAL_RESERVA_DOTACION_RATE": Decimal("0.10"),
    "SAL_RESERVA_CAPITAL_MULTIPLE": Decimal("2"),
    "DEHU_RECHAZO_TACITO_DIAS_NATURALES": 10,
}
_REDUCED_MULTIPLE_PAYER_LIMIT_BY_YEAR = {
    2019: Decimal("14000"),
    2020: Decimal("14000"),
    2021: Decimal("14000"),
    2022: Decimal("14000"),
    2023: Decimal("15000"),
    2024: Decimal("15876"),
    2025: Decimal("15876"),
    2026: Decimal("15876"),
}


@dataclass(frozen=True, slots=True)
class _ScalarSpec:
    symbol: str
    fact_id: str
    unit: str
    legal_ref: str
    valid_from: date


_LIRPF_START = date(2007, 1, 1)
_SCALAR_SPECS = (
    _ScalarSpec(
        "M347_THRESHOLD_EUR", "m347-counterparty-declaration-threshold", "eur", "rd-1065-2007:art-33", date(2008, 1, 1)
    ),
    _ScalarSpec(
        "M347_CLAVE_C_THRESHOLD_EUR",
        "m347-clave-c-beneficiary-declaration-threshold",
        "eur",
        "rd-1065-2007:art-33",
        date(2008, 1, 1),
    ),
    _ScalarSpec(
        "IVA_BIEN_ESCASO_VALOR_UMBRAL_EUR",
        "iva-bien-inversion-escaso-valor-threshold",
        "eur",
        "ley-37-1992:art-108",
        date(1993, 1, 1),
    ),
    _ScalarSpec(
        "MODELO_840_IAE_CIFRA_NEGOCIOS_EXEMPTION_THRESHOLD_EUR",
        "iae-cifra-negocios-exemption-threshold",
        "eur",
        "rdl-2-2004:art-82",
        date(2004, 3, 10),
    ),
    _ScalarSpec("ART_7P_EXEMPTION_CAP_EUR", "lirpf-art-7p-exemption-cap", "eur", "ley-35-2006:art-7", _LIRPF_START),
    _ScalarSpec(
        "MULTIPLE_PAGADORES_SECONDARY_THRESHOLD_EUR",
        "lirpf-multiple-pagadores-secondary-threshold",
        "eur",
        "ley-35-2006:art-96",
        _LIRPF_START,
    ),
    _ScalarSpec(
        "WORK_INCOME_GENERAL_DECLARATION_LIMIT_EUR",
        "lirpf-work-income-general-declaration-limit",
        "eur",
        "ley-35-2006:art-96",
        _LIRPF_START,
    ),
    _ScalarSpec(
        "MODELO_202_ART_40_3_INCN_THRESHOLD_EUR",
        "lis-art-40-3-incn-threshold",
        "eur",
        "ley-27-2014:art-40-3",
        date(2015, 1, 1),
    ),
    _ScalarSpec(
        "MODELO_100_ART_20_TRABAJO_REDUCCION_RNT_CEILING_EUR",
        "lirpf-art-20-trabajo-reduccion-rnt-ceiling",
        "eur",
        "ley-35-2006:art-20",
        date(2024, 1, 1),
    ),
    _ScalarSpec(
        "MODELO_100_ART_52_INDIVIDUAL_SUBLIMIT_EUR",
        "lirpf-art-52-individual-contribution-sublimit",
        "eur",
        "ley-35-2006:art-52-2021",
        date(2021, 1, 1),
    ),
    _ScalarSpec(
        "REBECA_MARITIME_EXEMPTION_FRACTION",
        "rebeca-maritime-exemption-fraction",
        "ratio",
        "ley-19-1994:art-75",
        date(1994, 7, 8),
    ),
    _ScalarSpec(
        "DEDUCCION_MATERNIDAD_MENSUAL_EUR",
        "lirpf-art-81-maternity-monthly-amount",
        "eur",
        "ley-35-2006:art-81",
        _LIRPF_START,
    ),
    _ScalarSpec(
        "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR",
        "lirpf-art-81-maternity-annual-cap",
        "eur",
        "ley-35-2006:art-81",
        _LIRPF_START,
    ),
    _ScalarSpec(
        "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR",
        "lirpf-art-81-maternity-post-birth-enrollment-increment",
        "eur",
        "ley-35-2006:art-81",
        date(2023, 1, 1),
    ),
    _ScalarSpec(
        "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR",
        "lirpf-art-81-maternity-post-birth-enrollment-annual-cap",
        "eur",
        "ley-35-2006:art-81",
        date(2023, 1, 1),
    ),
    _ScalarSpec(
        "DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR",
        "lirpf-art-81-maternity-post-birth-enrollment-effective-year",
        "year",
        "ley-35-2006:art-81",
        date(2023, 1, 1),
    ),
    _ScalarSpec(
        "DEDUCCION_MATERNIDAD_COTIZACIONES_CEILING_RETIRED_FILING_YEAR",
        "lirpf-art-81-contribution-ceiling-retired-effective-year",
        "year",
        "ley-35-2006:art-81",
        date(2023, 1, 1),
    ),
    _ScalarSpec(
        "MINIMO_DESCENDIENTE_MAX_AGE",
        "lirpf-art-58-descendant-ordinary-maximum-age",
        "years",
        "ley-35-2006:art-58",
        _LIRPF_START,
    ),
    _ScalarSpec(
        "MINIMO_MENOR_TRES_MAX_AGE", "lirpf-art-58-under-three-maximum-age", "years", "ley-35-2006:art-58", _LIRPF_START
    ),
    _ScalarSpec(
        "CUSTODIA_COMPARTIDA_PRORRATA_FACTOR",
        "lirpf-art-61-shared-custody-proration-factor",
        "ratio",
        "ley-35-2006:art-61-norma-4",
        _LIRPF_START,
    ),
    _ScalarSpec(
        "ART_81_1_ENTRY_WINDOW_YEARS",
        "lirpf-art-81-adoption-entry-window-years",
        "years",
        "ley-35-2006:art-81",
        _LIRPF_START,
    ),
    _ScalarSpec(
        "NACIMIENTO_ADOPCION_APPLICABILITY_FOLLOWING_PERIODS",
        "madrid-birth-adoption-following-periods",
        "filing_periods",
        "madrid-dl-1-2010:art-4",
        date(2023, 1, 1),
    ),
    _ScalarSpec(
        "DT12_RESCATE_REDUCCION_RATE",
        "lirpf-dt12-rescate-reduction-rate",
        "ratio",
        "ley-35-2006:dt-12",
        date(2015, 1, 1),
    ),
    _ScalarSpec(
        "DT12_GENERAL_WINDOW_FOLLOWING_YEARS",
        "lirpf-dt12-general-window-following-years",
        "years",
        "ley-35-2006:dt-12",
        date(2015, 1, 1),
    ),
    _ScalarSpec(
        "DT12_TRANSITIONAL_CONTINGENCIA_FIRST_YEAR",
        "lirpf-dt12-transitional-contingency-first-year",
        "year",
        "ley-35-2006:dt-12",
        date(2015, 1, 1),
    ),
    _ScalarSpec(
        "DT12_TRANSITIONAL_CONTINGENCIA_LAST_YEAR",
        "lirpf-dt12-transitional-contingency-last-year",
        "year",
        "ley-35-2006:dt-12",
        date(2015, 1, 1),
    ),
    _ScalarSpec(
        "DT12_TRANSITIONAL_WINDOW_FOLLOWING_YEARS",
        "lirpf-dt12-transitional-window-following-years",
        "years",
        "ley-35-2006:dt-12",
        date(2015, 1, 1),
    ),
    _ScalarSpec("DT12_CLIFF_LAST_YEAR", "lirpf-dt12-cliff-last-year", "year", "ley-35-2006:dt-12", date(2015, 1, 1)),
    _ScalarSpec(
        "SAL_RESERVA_DOTACION_RATE",
        "sal-special-reserve-allocation-rate",
        "ratio",
        "ley-44-2015:art-14",
        date(2015, 11, 15),
    ),
    _ScalarSpec(
        "SAL_RESERVA_CAPITAL_MULTIPLE",
        "sal-special-reserve-capital-multiple",
        "multiple",
        "ley-44-2015:art-14",
        date(2015, 11, 15),
    ),
    _ScalarSpec(
        "DEHU_RECHAZO_TACITO_DIAS_NATURALES",
        "dehu-tacit-rejection-natural-days",
        "natural_days",
        "ley-39-2015:art-43.2",
        date(2016, 10, 2),
    ),
)


def compile_statutory_constant_facts(registry_root: Path) -> tuple[GovernedFact, ...]:
    """Project governed constants without changing their current public authority."""
    del registry_root
    facts = [_scalar_fact(spec) for spec in _SCALAR_SPECS]
    schedule = _REDUCED_MULTIPLE_PAYER_LIMIT_BY_YEAR
    facts.append(
        GovernedFact(
            fact_id="lirpf-work-income-multiple-pagadores-reduced-limit",
            family=GovernedFactFamily.MAPPING,
            variants=(
                GovernedFactVariant(
                    variant_id="lirpf-work-income-multiple-pagadores-reduced-limit:2019-2026",
                    date_axis=DateAxis.FILING_PERIOD,
                    valid_from=date(2019, 1, 1),
                    valid_to=date(2026, 12, 31),
                    payload=MappingFactPayload(
                        entries=tuple(MappingFactEntry(key=year, value=value) for year, value in schedule.items()),
                    ),
                    legal_refs=("ley-35-2006:art-96",),
                    source_refs=(_SOURCE_BY_LEGAL_REF["ley-35-2006:art-96"],),
                    source_citations=(
                        SourceCitation(
                            source_ref=_SOURCE_BY_LEGAL_REF["ley-35-2006:art-96"],
                            required_text=("15.876 euros",),
                        ),
                    ),
                    review_status=RevisionReviewStatus.AGENT_REVIEWED,
                    ownership=FactOwnership.GENERATED,
                ),
            ),
        ),
    )
    return tuple(facts)


def collect_statutory_constant_fingerprints(registry_root: Path) -> tuple[tuple[str, int, int, str], ...]:
    """Fingerprint the Python declaration source that feeds this adapter."""
    del registry_root
    return (toml_file_fingerprint(Path(__file__).resolve()),)


def reset_statutory_constant_provider() -> None:
    """Reset hook for an adapter with no provider-local cache."""


def _scalar_fact(spec: _ScalarSpec) -> GovernedFact:
    value = _VALUE_BY_SYMBOL[spec.symbol]
    if not isinstance(value, (str, int, Decimal, bool, date)):
        raise TypeError(f"statutory constant {spec.symbol} is not a scalar fact atom")
    return GovernedFact(
        fact_id=spec.fact_id,
        family=GovernedFactFamily.SCALAR,
        variants=(
            GovernedFactVariant(
                variant_id=f"{spec.fact_id}:{spec.valid_from.isoformat()}",
                date_axis=_DATE_AXIS_BY_SYMBOL.get(spec.symbol, DateAxis.FILING_PERIOD),
                valid_from=spec.valid_from,
                payload=ScalarFactPayload(value=value, unit=spec.unit),
                legal_refs=(spec.legal_ref,),
                source_refs=(_SOURCE_BY_LEGAL_REF[spec.legal_ref],),
                source_citations=(_citation(spec),),
                review_status=RevisionReviewStatus.AGENT_REVIEWED,
                ownership=FactOwnership.GENERATED,
            ),
        ),
    )


def _citation(spec: _ScalarSpec) -> SourceCitation:
    return SourceCitation(
        source_ref=_SOURCE_BY_LEGAL_REF[spec.legal_ref],
        required_text=(_CITATION_TEXT_BY_SYMBOL[spec.symbol],),
    )
