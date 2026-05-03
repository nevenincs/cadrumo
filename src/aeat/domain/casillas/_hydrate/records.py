from typing import Any, cast

from aeat.core.errors import AmbiguousPeriodError, MissingRulesetError
from aeat.core.logging import get_logger
from aeat.domain.formulas import FiscalPeriod, Quarter, Ruleset, get_registry
from aeat.domain.modelos import ModeloCode

from .constants import _HTTP_URL_ADAPTER, REVIEWED_AT, REVIEWED_BY
from .data import CENSAL_CASILLAS, M111_AUGMENT
from .formulas import _collect_casilla_refs, _render_operand
from .metadata import (
    _record_from_ruleset_casilla,
    _section_for_casilla,
    _source_url_for,
    _supported_language_codes,
    _validation_for,
)
from .models import CasillaRecord, FormulaReference, _Casilla

_logger = get_logger(__name__)

def _section_for(modelo: str) -> str:
    if modelo in {"100", "200"}:
        return "Liquidación"
    if modelo in {"303", "390"}:
        return "IVA"
    if modelo in {"036", "037"}:
        return "Censo"
    return "General"

def _get_ruleset_periods(modelo: str, year: int) -> list[str]:
    registry = get_registry()
    code = ModeloCode(modelo)
    out: set[str] = set()
    for r in registry.rulesets:
        if r.modelo == code:
            if r.effective_from.year <= year and (r.effective_to is None or r.effective_to.year >= year):
                # We assume standard periods for now or derive from ruleset_id if possible
                # The hydrate logic seems to expect "1T", "0A" etc.
                if "summary" in r.ruleset_id:
                    out.add("0A")
                elif "303" in r.ruleset_id or "130" in r.ruleset_id or "131" in r.ruleset_id:
                     out.update({"1T", "2T", "3T", "4T"})
                else:
                     out.add("0A")
    return sorted(list(out))

def _get_ruleset(modelo: str, year: int, period_id: str) -> Ruleset | None:
    registry = get_registry()
    code = ModeloCode(modelo)
    quarter = None
    if period_id.endswith("T"):
        quarter = Quarter(f"Q{period_id[0]}")

    period = FiscalPeriod(year=year, quarter=quarter)
    variant = "default"
    if modelo == "100" and period_id == "0A":
        variant = "summary"

    try:
        return registry.resolve(modelo=code, period=period, variant=variant)
    except (MissingRulesetError, AmbiguousPeriodError):
        _logger.debug("no ruleset for modelo=%s period_id=%s year=%s variant=%s", modelo, period_id, year, variant)
        return None

def _canonical_period(year: int, period_id: str) -> str:
    if period_id == "0A":
        return str(year)
    if period_id.endswith("T"):
        return f"{year}Q{period_id[0]}"
    if period_id.endswith("M"):
        # e.g. "1M" -> "2025-01"
        return f"{year}-{period_id[:-1].zfill(2)}"
    return f"{year}{period_id}"

def _hydrate_from_rulesets(modelo: str, year: int) -> list[CasillaRecord]:
    records: list[CasillaRecord] = []
    periods = _get_ruleset_periods(modelo, year)
    source_url = _source_url_for(modelo, year)
    for period_id in periods:
        ruleset = _get_ruleset(modelo, year, period_id)
        if ruleset is None:
            continue
        period = _canonical_period(year, period_id)
        formulas_by_id = {f.casilla_id: f.formula for f in ruleset.formulas}
        for cdef in ruleset.casillas:
            formula_expression: str | None = None
            formula_refs: tuple[str, ...] = ()
            references_rules: tuple[str, ...] = ()
            node = formulas_by_id.get(cdef.casilla_id)
            if node is not None:
                formula_expression = _render_operand(node)
                formula_refs = tuple(_collect_casilla_refs(node))
            casilla_to_rules = getattr(ruleset, "casilla_to_rules", None)
            if casilla_to_rules is not None:
                references_rules = tuple(casilla_to_rules.get(cdef.casilla_id, []))
            section = _section_for_casilla(modelo, cdef.casilla_id)
            records.append(
                _record_from_ruleset_casilla(
                    modelo=modelo,
                    period=period,
                    cdef=cdef,
                    formula_expression=formula_expression,
                    formula_refs=formula_refs,
                    references_rules=references_rules,
                    source_url=source_url,
                    section=section,
                )
            )
    return records

def _hydrate_censal(modelo: str, year: int) -> list[CasillaRecord]:
    records: list[CasillaRecord] = []
    languages = _supported_language_codes()
    source_url = _source_url_for(modelo, year)
    period = _canonical_period(year, "0A")
    for c in CENSAL_CASILLAS:
        labels = c.label_for_languages(languages)
        helps = c.help_for_languages(languages)
        records.append(
            CasillaRecord(
                synthetic=False,
                modelo=f"MODELO_{modelo}",
                period=period,
                casilla_id=c.casilla_id,
                label=cast(Any, labels),
                help=cast(Any, helps),
                data_type=c.data_type,
                select_options=c.select_options,
                required=False,
                computed=c.computed,
                formula=None,
                references_casillas=(),
                references_rules=(),
                validation=_validation_for(modelo, c.casilla_id, c.computed),
                source_manual_url=_HTTP_URL_ADAPTER.validate_python(source_url),
                source_page=1,
                source_section=c.section or "Censo",
                definition_reviewed_by=REVIEWED_BY,
                definition_reviewed_at=REVIEWED_AT,
                llm_draft_provenance=None,
            )
        )
    return records

def _hydrate_manual(modelo: str, year: int, data: tuple[_Casilla, ...], period_id: str = "0A") -> list[CasillaRecord]:
    records: list[CasillaRecord] = []
    languages = _supported_language_codes()
    source_url = _source_url_for(modelo, year)
    period = _canonical_period(year, period_id)
    for c in data:
        labels = c.label_for_languages(languages)
        helps = c.help_for_languages(languages)
        formula_obj = None
        if c.formula_expression:
            formula_obj = FormulaReference(
                expression=c.formula_expression,
                references_casillas=c.formula_refs
            )
        records.append(
            CasillaRecord(
                synthetic=False,
                modelo=f"MODELO_{modelo}",
                period=period,
                casilla_id=c.casilla_id,
                label=cast(Any, labels),
                help=cast(Any, helps),
                data_type=c.data_type,
                select_options=c.select_options,
                required=False,
                computed=c.computed,
                formula=formula_obj,
                references_casillas=c.formula_refs,
                references_rules=c.references_rules,
                validation=_validation_for(modelo, c.casilla_id, c.computed),
                source_manual_url=_HTTP_URL_ADAPTER.validate_python(source_url),
                source_page=1,
                source_section=c.section or "General",
                definition_reviewed_by=REVIEWED_BY,
                definition_reviewed_at=REVIEWED_AT,
                llm_draft_provenance=None,
            )
        )
    return records

def _hydrate_modelo_111(year: int) -> list[CasillaRecord]:
    # 1. Start with ruleset-driven records
    records = _hydrate_from_rulesets("111", year)

    # 2. Augment and add manual ones from M111_AUGMENT
    languages = _supported_language_codes()
    for period_id in ("1T", "2T", "3T", "4T"):
        period = _canonical_period(year, period_id)
        for augment in M111_AUGMENT:
            # Find existing record for this (casilla, period)
            existing = next((r for r in records if r.casilla_id == augment.casilla_id and r.period == period), None)

            if existing:
                existing.label = cast(Any, augment.label_for_languages(languages))
                existing.help = cast(Any, augment.help_for_languages(languages))
                if augment.section:
                    existing.source_section = augment.section
            else:
                # Add new record if not in ruleset
                labels = augment.label_for_languages(languages)
                helps = augment.help_for_languages(languages)
                records.append(
                    CasillaRecord(
                        synthetic=False,
                        modelo="MODELO_111",
                        period=period,
                        casilla_id=augment.casilla_id,
                        label=cast(Any, labels),
                        help=cast(Any, helps),
                        data_type=augment.data_type,
                        select_options=augment.select_options,
                        required=False,
                        computed=augment.computed,
                        formula=None,
                        references_casillas=(),
                        references_rules=(),
                        validation=_validation_for("111", augment.casilla_id, augment.computed),
                        source_manual_url=_HTTP_URL_ADAPTER.validate_python(_source_url_for("111", year)),
                        source_page=1,
                        source_section=augment.section or "General",
                        definition_reviewed_by=REVIEWED_BY,
                        definition_reviewed_at=REVIEWED_AT,
                        llm_draft_provenance=None,
                    )
                )
    return sorted(records, key=lambda r: (r.period, r.casilla_id))
