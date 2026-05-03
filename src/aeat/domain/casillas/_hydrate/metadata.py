from __future__ import annotations
from typing import cast, TYPE_CHECKING
from decimal import Decimal
from aeat.core.i18n import Translatable
from aeat.domain.modelos import ModeloCadence, get_modelo, ModeloCode
from .models import CasillaRecord, FormulaReference, ValidationRuleReference, _Casilla
from .constants import (
    IRPF_MANUAL_URL, IVA_MANUAL_URL, SOCIEDADES_MANUAL_URL,
    _HTTP_URL_ADAPTER, REVIEWED_BY, REVIEWED_AT
)
from .lemmas import _es_to_ca_via_lemmas, _hu_restore_diacritics
from .formulas import _render_operand, _collect_casilla_refs

if TYPE_CHECKING:
    from aeat.domain.formulas._ruleset import Ruleset
    from aeat.domain.formulas._casilla import CasillaDefinition

_SOURCE_LABEL = {
    "ley": "Ley",
    "real_decreto": "RD",
    "orden_ministerial": "Orden",
    "reglamento": "Reglamento",
    "manual_practico": "Manual práctico",
    "boe": "BOE",
}

def _legal_hint(legal_basis: tuple) -> str:
    if not legal_basis:
        return ""
    parts: list[str] = []
    for c in legal_basis:
        src = getattr(c, "source", None)
        article = getattr(c, "article", None)
        url = getattr(c, "url", None)
        boe_id = ""
        url_str = str(url) if url is not None else ""
        if "BOE-A-" in url_str:
            boe_id = url_str.split("id=", 1)[-1].split("&", 1)[0]
        bits: list[str] = []
        if src is not None:
            raw = getattr(src, "value", str(src))
            bits.append(_SOURCE_LABEL.get(raw, raw.replace("_", " ").title()))
        if article:
            bits.append(f"art. {article}")
        if boe_id:
            bits.append(boe_id)
        if bits:
            parts.append(", ".join(bits))
    if not parts:
        return ""
    return " (Base legal: " + "; ".join(parts) + ".)"

def _upstream_modelos(modelo: str) -> tuple[str, ...]:
    upstream: list[str] = []
    for code in ModeloCode:
        meta = get_modelo(code.value)
        if meta.caps_into is not None and meta.caps_into.value == modelo:
            upstream.append(code.value)
    return tuple(sorted(upstream))

_CROSS_MODELO_PHRASING_DEFAULT: dict[str, dict[str, str]] = {
    "es": {
        "separator": " y ",
        "modelo_word": "modelo",
        "lead": "Resumen anual que consolida los datos trimestrales del",
    },
    "en": {"separator": " and ", "modelo_word": "form", "lead": "Annual summary consolidating the quarterly data of"},
    "ca": {"separator": " i ", "modelo_word": "model", "lead": "Resum anual que consolida les dades trimestrals del"},
    "hu": {
        "separator": " és ",
        "modelo_word_suffix": "-os modell",
        "lead": "Éves összefoglaló, amely az alábbi modell negyedéves adatait foglalja össze:",
    },
}

_CROSS_MODELO_PHRASING_M100: dict[str, dict[str, str]] = {
    "es": {
        "separator": " y ",
        "modelo_word": "modelo",
        "lead": "Declaración anual del IRPF; recoge los pagos fraccionados de los",
    },
    "en": {
        "separator": " and ",
        "modelo_word": "form",
        "lead": "Annual IRPF declaration; consolidates the fractional payments of",
    },
    "ca": {
        "separator": " i ",
        "modelo_word": "model",
        "lead": "Declaració anual de l'IRPF; recull els pagaments fraccionats dels",
    },
    "hu": {
        "separator": " és ",
        "modelo_word_suffix": "-os modell",
        "lead": "Éves IRPF-bevallás; az alábbi modellek részletfizetéseit foglalja össze:",
    },
}

_CROSS_MODELO_PHRASING_M200: dict[str, dict[str, str]] = {
    "es": {
        "separator": " y ",
        "modelo_word": "modelo",
        "lead": "Declaración anual del Impuesto sobre Sociedades; recoge los pagos fraccionados del",
    },
    "en": {
        "separator": " and ",
        "modelo_word": "form",
        "lead": "Annual Corporate Income Tax declaration; consolidates the fractional payments of",
    },
    "ca": {
        "separator": " i ",
        "modelo_word": "model",
        "lead": "Declaració anual de l'Impost sobre Societats; recull els pagaments fraccionats del",
    },
    "hu": {
        "separator": " és ",
        "modelo_word_suffix": "-os modell",
        "lead": "Éves társasági adó bevallás; az alábbi modell részletfizetéseit foglalja össze:",
    },
}

def _supported_language_codes() -> tuple[str, ...]:
    from aeat.core.i18n import Language
    return tuple(lang.value for lang in Language)

def _expand_label_to_supported_languages(label: dict[str, str]) -> dict[str, str]:
    es = label.get("es", "")
    out = dict(label)
    for lang in _supported_language_codes():
        if lang not in out or not out[lang]:
            if lang == "ca":
                out[lang] = _es_to_ca_via_lemmas(es)
            else:
                out[lang] = es
        elif lang == "hu":
            out[lang] = _hu_restore_diacritics(out[lang])
    return out

def _format_modelo_token(lang: str, table: dict[str, dict[str, str]], modelo: str) -> str:
    spec = table[lang]
    if "modelo_word_suffix" in spec:
        return f"{modelo}{spec['modelo_word_suffix']}"
    return f"{spec['modelo_word']} {modelo}"

def _cross_modelo_hint_for_languages(modelo: str) -> dict[str, str]:
    upstream = _upstream_modelos(modelo)
    languages = _supported_language_codes()
    if not upstream:
        return {lang: "" for lang in languages}
    table = _CROSS_MODELO_PHRASING_DEFAULT
    if modelo == "100":
        table = _CROSS_MODELO_PHRASING_M100
    elif modelo == "200":
        table = _CROSS_MODELO_PHRASING_M200
    out: dict[str, str] = {}
    for lang in languages:
        if lang not in table:
            out[lang] = ""
            continue
        spec = table[lang]
        joined = spec["separator"].join(_format_modelo_token(lang, table, m) for m in upstream)
        out[lang] = f" {spec['lead']} {joined}."
    return out

_FORMULA_CLAUSE_PREFIX: dict[str, str] = {
    "es": " Se calcula como ",
    "en": " Computed as ",
    "ca": " Es calcula com ",
    "hu": " Számítás: ",
}

_LEGAL_HINT_LABEL: dict[str, str] = {
    "es": "Base legal:",
    "en": "Legal basis:",
    "ca": "Base legal:",
    "hu": "Jogalap:",
}

def _help_from_label(
    label: dict[str, str],
    notes_es: str | None,
    *,
    formula_expression: str | None = None,
    legal_hint: str = "",
    cross_modelo_hints: dict[str, str] | None = None,
) -> dict[str, str]:
    languages = _supported_language_codes()
    cross_hints: dict[str, str] = cross_modelo_hints or {lang: "" for lang in languages}
    label_es = label.get("es", "")
    out: dict[str, str] = {}
    for lang in languages:
        if label.get(lang):
            lang_label = _hu_restore_diacritics(label[lang]) if lang == "hu" else label[lang]
        elif lang == "ca":
            lang_label = _es_to_ca_via_lemmas(label_es)
        else:
            lang_label = label_es
        formula_clause = ""
        if formula_expression:
            prefix = _FORMULA_CLAUSE_PREFIX.get(lang, _FORMULA_CLAUSE_PREFIX["en"])
            suffix = "." if not prefix.endswith(": ") else ""
            formula_clause = f"{prefix}{formula_expression}{suffix}"
        legal_clause = ""
        if legal_hint:
            legal_clause = legal_hint.replace("Base legal:", _LEGAL_HINT_LABEL.get(lang, "Base legal:"))
            if lang == "ca":
                legal_clause = _es_to_ca_via_lemmas(legal_clause)
        cross_clause = cross_hints.get(lang, "")
        if lang == "es" and notes_es:
            out["es"] = notes_es + formula_clause + cross_clause + legal_clause
        elif lang != "es" and notes_es:
            out[lang] = lang_label + formula_clause + cross_clause + legal_clause
        elif formula_expression:
            out[lang] = f"{lang_label}.{formula_clause}{cross_clause}{legal_clause}"
        elif legal_hint or any(cross_hints.values()):
            out[lang] = lang_label + cross_clause + legal_clause
        else:
            out[lang] = lang_label
    return out

_CATEGORY_MANUAL_URL: dict[str, str] = {
    "irpf": IRPF_MANUAL_URL,
    "iva": IVA_MANUAL_URL,
    "retenciones": IRPF_MANUAL_URL,
    "sociedades": SOCIEDADES_MANUAL_URL,
}

_INFORMATIVA_MANUAL_OVERRIDES: dict[str, str] = {
    "232": SOCIEDADES_MANUAL_URL,
    "347": IVA_MANUAL_URL,
    "349": IVA_MANUAL_URL,
}

def _source_url_for(modelo: str, year: int) -> str:
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
    for cit in meta.legal_basis:
        url = getattr(cit, "url", None)
        if url is not None:
            url_str = str(url)
            return url_str.split("#", 1)[0]
    return IRPF_MANUAL_URL.format(year=year)

def _section_for_casilla(modelo: str, casilla_id: str) -> str:
    from .records import _section_for
    if modelo == "130":
        cid = int(casilla_id)
        if cid <= 7:
            return "I. Actividades económicas en estimación directa"
        if cid <= 11:
            return "II. Actividades agrícolas, ganaderas, forestales y pesqueras"
        if cid <= 14:
            return "III. Total liquidación trimestral (apartados I + II)"
        if cid == 15:
            return "Resultados negativos de trimestres anteriores"
        if cid == 16:
            return "Deducción por adquisición de vivienda habitual"
        if cid <= 19:
            return "Resultado final"
    if modelo == "131":
        cid = int(casilla_id)
        if cid in {1}:
            return "I. Actividades en estimación objetiva (datos base)"
        if cid in {2, 3, 4, 7}:
            return "II. Actividades en estimación objetiva (sin datos base)"
        if cid in {5, 6}:
            return "III. Actividades agrícolas, ganaderas, forestales y pesqueras"
        if cid in {8, 9, 10}:
            return "IV. Total liquidación tras retenciones e ingresos a cuenta"
        if cid in {11, 12, 13}:
            return "V. Resultado tras minoraciones y deducciones"
        if cid in {14, 15}:
            return "VI. Resultado a ingresar"
    if modelo == "111":
        cid = int(casilla_id)
        if 1 <= cid <= 3:
            return "I. Rendimientos del trabajo"
        if 4 <= cid <= 6:
            return "II. Actividades económicas"
        if 7 <= cid <= 9:
            return "III. Premios"
        if 10 <= cid <= 12:
            return "IV. Ganancias patrimoniales — aprovechamientos forestales"
        if 13 <= cid <= 15:
            return "V. Contraprestaciones en especie"
        if 16 <= cid <= 18:
            return "VI. Cesión de derechos de imagen"
        if cid in {28, 29, 30}:
            return "Liquidación"
    if modelo == "190":
        cid = int(casilla_id)
        if 1 <= cid <= 3:
            return "Apartado I — Rendimientos del trabajo"
        if 4 <= cid <= 6:
            return "Apartado II — Actividades económicas"
        if 7 <= cid <= 9:
            return "Apartado III — Premios"
        if 10 <= cid <= 12:
            return "Apartado IV — Ganancias patrimoniales (aprovechamientos forestales)"
        if 13 <= cid <= 15:
            return "Apartado V — Contraprestaciones en especie"
        if 16 <= cid <= 18:
            return "Apartado VI — Cesión derechos imagen"
        if 19 <= cid <= 21:
            return "Resumen — Totales"
    if modelo == "115":
        cid = int(casilla_id)
        if cid == 1:
            return "Datos generales"
        if 2 <= cid <= 5:
            return "Datos relativos a la liquidación"
        if cid == 6:
            return "Resultado a ingresar"
    if modelo == "123":
        cid = int(casilla_id)
        if cid in {1, 2, 3}:
            return "I. Total perceptores (dividendos / otras rentas)"
        if cid in {4, 5, 6}:
            return "II. Base retenciones (dividendos / otras rentas)"
        if cid in {7, 8, 9}:
            return "III. Total retenciones e ingresos a cuenta"
        if cid in {10, 11}:
            return "IV. Resultado a ingresar"
    if modelo == "303":
        cid_int = int(casilla_id)
        if 1 <= cid_int <= 9:
            return "IVA devengado — Régimen general (operaciones interiores)"
        if 28 <= cid_int <= 45:
            return "IVA deducible and resultado régimen general"
        if 46 <= cid_int <= 63:
            return "Régimen simplificado"
        if cid_int in {64, 65, 66}:
            return "Resultado de la liquidación — atribución al Estado"
        if cid_int in {67, 69, 71}:
            return "Resultado de la autoliquidación"
    if modelo == "390":
        cid_int = int(casilla_id)
        if cid_int in {1, 4}:
            return "Apartado 1 — Datos estadísticos (1T)"
        if cid_int in {95, 96, 100, 101, 104, 105}:
            return "Apartado 3 — Régimen general anual"
        if cid_int in {108, 109}:
            return "Apartados 4-5 — Otros regímenes"
        if cid_int in {190, 191, 192, 193}:
            return "Apartado 6 — Resultado anual"
        if cid_int == 662:
            return "Apartado 7 — Regularización bienes de inversión"
    if modelo == "180":
        cid = int(casilla_id)
        if cid in {1, 2}:
            return "Resumen anual — Bases"
        if cid in {3, 4}:
            return "Resumen anual — Retenciones e ingresos a cuenta"
    if modelo == "202":
        cid = int(casilla_id)
        if cid in {16, 17, 18}:
            return "Apartado A — Cuota íntegra"
        if cid in {27, 28, 30}:
            return "Apartado B — Bonificaciones, retenciones, pagos previos"
        if cid in {32, 33, 34}:
            return "Apartado C — Resultado y mínimo a ingresar"
    if modelo == "200":
        if casilla_id in {"00547", "00550", "00552", "00558", "00560", "00562"}:
            return "Página 14 — Liquidación cuota íntegra"
        if casilla_id in {"00582", "00592"}:
            return "Página 14 — Cuota líquida"
        if casilla_id in {"00599", "00601", "00603", "00605", "00611"}:
            return "Página 14 — Cuota diferencial"
        if casilla_id in {"00615", "00619", "00621"}:
            return "Página 14 — Líquido a ingresar / devolver"
    return _section_for(modelo)

def _validation_for(modelo: str, casilla_id: str, computed: bool) -> tuple[ValidationRuleReference, ...]:
    rules: list[ValidationRuleReference] = []
    if computed:
        rules.append(
            ValidationRuleReference(
                rule="must_derive",
                value=True,
                description="Computed casilla — value must be derived by the rule engine, not user-supplied.",
            )
        )
    if modelo == "130" and casilla_id in {"04", "07", "11", "12", "14", "17", "19"}:
        rules.append(
            ValidationRuleReference(
                rule="non_negative",
                value=0,
                description="RIRPF art. 110: pago fraccionado y resultado parcial no pueden ser negativos.",
            )
        )
    if modelo == "131" and casilla_id in {"04", "06", "07", "10", "13", "15"}:
        rules.append(
            ValidationRuleReference(
                rule="non_negative",
                value=0,
                description="RIRPF art. 110.1: instrumentos de estimación objetiva siempre ≥ 0.",
            )
        )
    if modelo == "303" and casilla_id in {"02", "05", "08"}:
        rules.append(
            ValidationRuleReference(
                rule="constant",
                value={"02": 4, "05": 10, "08": 21}[casilla_id],
                description="LIVA arts. 90/91: tipo IVA constante (régimen general).",
            )
        )
    if modelo == "303" and casilla_id == "65":
        rules.append(
            ValidationRuleReference(
                rule="default",
                value=100,
                description="Atribución al Estado por defecto = 100% (sin atribución foral País Vasco/Navarra).",
            )
        )
    if modelo == "390" and casilla_id in {"192", "193"}:
        rules.append(
            ValidationRuleReference(
                rule="non_negative",
                value=0,
                description="LIVA art. 164 + RIVA art. 71.7: total a ingresar / a devolver son magnitudes no-negativas.",
            )
        )
    if modelo == "200" and casilla_id == "00558":
        rules.append(
            ValidationRuleReference(
                rule="whole_percent",
                value=True,
                description="LIS arts. 29-30: tipo de gravamen impreso como entero porcentual (e.g. 25 = 25%).",
            )
        )
    if modelo == "202" and casilla_id == "17":
        rules.append(
            ValidationRuleReference(
                rule="whole_percent",
                value=True,
                description="LIS art. 40.3: tipo aplicable impreso como entero porcentual (e.g. 17 = 17%).",
            )
        )
    if modelo == "111" and casilla_id == "30":
        rules.append(
            ValidationRuleReference(
                rule="non_negative",
                value=0,
                description="Resultado a ingresar mensual/trimestral debe ser ≥ 0 (LIRPF arts. 99-101).",
            )
        )
    if modelo == "115" and casilla_id == "06":
        rules.append(
            ValidationRuleReference(
                rule="non_negative",
                value=0,
                description="Resultado a ingresar trimestral debe ser ≥ 0 (RIRPF art. 100.1).",
            )
        )
    if modelo == "180" and casilla_id == "03":
        rules.append(
            ValidationRuleReference(
                rule="equals_19_percent_of",
                value="02",
                description="RIRPF art. 100.1: total retenciones = 19% de la base de retención (modelo 180 anual).",
            )
        )
    return tuple(rules)

def _record_from_ruleset_casilla(
    *,
    modelo: str,
    period: str,
    cdef: CasillaDefinition,
    formula_expression: str | None,
    formula_refs: tuple[str, ...],
    references_rules: tuple[str, ...],
    source_url: str,
    section: str,
    computed_override: bool | None = None,
) -> CasillaRecord:
    raw_label = dict(cdef.label)
    label = _expand_label_to_supported_languages(raw_label)
    legal_hint = _legal_hint(cdef.legal_basis)
    help_text = _help_from_label(
        label,
        cdef.notes_es,
        formula_expression=formula_expression,
        legal_hint=legal_hint,
        cross_modelo_hints=_cross_modelo_hint_for_languages(modelo),
    )

    formula_obj = (
        FormulaReference(expression=formula_expression, references_casillas=formula_refs)
        if formula_expression
        else None
    )

    computed = cdef.computed if computed_override is None else computed_override

    return CasillaRecord(
        synthetic=False,
        modelo=f"MODELO_{modelo}",
        period=period,
        casilla_id=cdef.casilla_id,
        label=cast(Translatable, label),
        help=cast(Translatable, help_text),
        data_type=cdef.data_type,
        select_options=None,
        required=False,
        computed=computed,
        formula=formula_obj,
        references_casillas=tuple(formula_refs),
        references_rules=tuple(references_rules),
        validation=_validation_for(modelo, cdef.casilla_id, computed),
        source_manual_url=_HTTP_URL_ADAPTER.validate_python(source_url),
        source_page=1,
        source_section=section,
        definition_reviewed_by=REVIEWED_BY,
        definition_reviewed_at=REVIEWED_AT,
        llm_draft_provenance=None,
    )
