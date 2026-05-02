"""Hydrate corpus/casillas/* for every modelo and supported period.

Runs once: writes complete CasillaCatalogue JSON files for every
modelo/year/period the project supports (2023-2026). Sources:

- Modelos with a ruleset under ``aeat.domain.formulas._rulesets``
  (100/111/115/123/130/131/180/200/202/303/390) hydrate directly from
  the engine ruleset's ``CasillaDefinition`` tuples and ``FormulaDefinition``
  tuples — the canonical, BOE-grounded source already curated for the
  calc engine. Cross-link the corpus' ``references_rules`` to each
  formula's ``formula_id`` so the docs and the engine stay in lock-step.

- Modelos whose extractor exposes ``casilla_ids`` / ``text_casilla_ids``
  (190/193/347/349/840) and modelos extracted via named fields
  (036/037/232/369/720) are hydrated from the curated trilingual data
  inside this script — sourced from BOE Órdenes and AEAT Manuales
  Prácticos for the supported period.

The script is idempotent: re-running it overwrites every JSON file with
the deterministic generated payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.config import PROJECT_ROOT
from ..formulas._casilla import CasillaDefinition
from ..formulas._formula import (
    AddFormula,
    BracketsFormula,
    ClampPositiveFormula,
    DivFormula,
    FormulaCasillaRef,
    Literal,
    MaxFormula,
    MinFormula,
    MulFormula,
    ParamRef,
    PercentFormula,
    RoundFormula,
    SubFormula,
)
from ..formulas._ruleset import Ruleset
from ..modelos import ModeloCadence, get_modelo
from . import CasillaDataType
from .catalogue import save_casillas
from .models import (
    CasillaCatalogue,
    CasillaRecord,
    FormulaReference,
    SelectOption,
    ValidationRuleReference,
)

CORPUS_ROOT = PROJECT_ROOT / "corpus" / "casillas"
REVIEWED_BY = "human-codex"
REVIEWED_AT = date(2026, 5, 1)

YEARS = (2023, 2024, 2025, 2026)


# ---------------------------------------------------------------------
# Manual practical URLs per modelo / year — official AEAT Sede sources.
# ---------------------------------------------------------------------

IRPF_MANUAL_URL = (
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-{year}.html"
)
IVA_MANUAL_URL = (
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/iva-{year}.html"
)
SOCIEDADES_MANUAL_URL = "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/sociedades-{year}.html"
BOE_036_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2007-9659"
BOE_840_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2003-17472"
BOE_232_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2017-10042"
BOE_720_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2013-954"
BOE_369_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2021-10049"
BOE_347_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2003-17004"
BOE_349_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2010-5098"
BOE_190_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-1997-25776"
BOE_193_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2011-19396"


# ---------------------------------------------------------------------
# Formula tree → human-readable expression.
# ---------------------------------------------------------------------


def _format_decimal(value: Decimal) -> str:
    """Render a Decimal as a compact decimal literal (no trailing zeros)."""
    s = format(value.normalize(), "f")
    if "." in s and "e" not in s.lower():
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _render_param_value(param_id: str, params: dict[str, Decimal] | None) -> str:
    """Return the parameter's resolved value as a percent / decimal string.

    Renders rates that look like ``0.21`` as ``21%`` and other small
    fractions similarly so the resulting expression reads naturally
    (``21% * 07`` rather than ``0.21 * 07``).
    """
    if not params or param_id not in params:
        return param_id
    value = params[param_id]
    if Decimal("0") < value < Decimal("1") and abs(value) >= Decimal("0.0001"):
        pct = value * Decimal(100)
        return f"{_format_decimal(pct)}%"
    return _format_decimal(value)


def _render_operand(node: object, *, params: dict[str, Decimal] | None = None) -> str:
    if isinstance(node, FormulaCasillaRef):
        return node.casilla_id
    if isinstance(node, Literal):
        v = node.value
        if isinstance(v, Decimal):
            return _format_decimal(v)
        return str(v)
    if isinstance(node, ParamRef):
        return _render_param_value(node.param_id, params)
    if isinstance(node, RoundFormula):
        return _render_operand(node.operands[0], params=params)
    if isinstance(node, AddFormula):
        return "(" + " + ".join(_render_operand(o, params=params) for o in node.operands) + ")"
    if isinstance(node, SubFormula):
        return (
            "("
            + _render_operand(node.operands[0], params=params)
            + " - "
            + _render_operand(node.operands[1], params=params)
            + ")"
        )
    if isinstance(node, MulFormula):
        return "(" + " * ".join(_render_operand(o, params=params) for o in node.operands) + ")"
    if isinstance(node, DivFormula):
        return (
            "("
            + _render_operand(node.operands[0], params=params)
            + " / "
            + _render_operand(node.operands[1], params=params)
            + ")"
        )
    if isinstance(node, MaxFormula):
        return "max(" + ", ".join(_render_operand(o, params=params) for o in node.operands) + ")"
    if isinstance(node, MinFormula):
        return "min(" + ", ".join(_render_operand(o, params=params) for o in node.operands) + ")"
    if isinstance(node, ClampPositiveFormula):
        return "max(0, " + _render_operand(node.operands[0], params=params) + ")"
    if isinstance(node, PercentFormula):
        rate, base = node.operands
        return "(" + _render_operand(rate, params=params) + " * " + _render_operand(base, params=params) + ")"
    if isinstance(node, BracketsFormula):
        return "brackets(" + _render_operand(node.operands[0], params=params) + ")"
    return repr(node)


def _collect_casilla_refs(node: object) -> list[str]:
    seen: list[str] = []

    def walk(n: object) -> None:
        if isinstance(n, FormulaCasillaRef):
            if n.casilla_id not in seen:
                seen.append(n.casilla_id)
            return
        if hasattr(n, "operands"):
            for op in n.operands:
                walk(op)

    walk(node)
    return seen


# ---------------------------------------------------------------------
# Period iterators per cadence.
# ---------------------------------------------------------------------


def _periods_for(cadence: ModeloCadence, year: int) -> list[str]:
    if cadence == ModeloCadence.QUARTERLY:
        return [f"{year}Q{q}" for q in range(1, 5)]
    if cadence == ModeloCadence.MONTHLY:
        return [f"{year}-{m:02d}" for m in range(1, 13)]
    return [str(year)]  # ANNUAL, AD_HOC


# ---------------------------------------------------------------------
# Trilingual help dictionaries for non-ruleset modelos.
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class _Casilla:
    casilla_id: str
    label_es: str
    label_en: str
    label_hu: str
    help_es: str
    help_en: str
    help_hu: str
    data_type: CasillaDataType = CasillaDataType.CURRENCY_EUR
    computed: bool = False
    formula_expression: str | None = None
    formula_refs: tuple[str, ...] = ()
    references_rules: tuple[str, ...] = ()
    section: str = ""
    select_options: tuple[SelectOption, ...] | None = None


# ----- Modelo 036 / 037 (declaración censal) ------------------------
# Fields chosen reflect the principal actos that almost every autónomo
# encounters; numbered casillas come from Orden EHA/1274/2007 Anexo I/II.

CENSAL_CASILLAS: tuple[_Casilla, ...] = (
    _Casilla(
        casilla_id="100",
        label_es="Solicitud de alta en el censo de empresarios",
        label_en="Request to enrol in the census of business operators",
        label_hu="Bejelentkezés a vállalkozói nyilvántartásba",
        help_es="Marque esta casilla para comunicar el inicio de la actividad económica.",
        help_en="Tick this box to report the start of the economic activity.",
        help_hu="Jelölje be a gazdasági tevékenység megkezdésének bejelentéséhez.",
        data_type=CasillaDataType.BOOLEAN,
        section="A. Causas de presentación",
    ),
    _Casilla(
        casilla_id="120",
        label_es="Modificación de datos relativos al IVA",
        label_en="Update of VAT-related data",
        label_hu="Az ÁFA-adatok módosítása",
        help_es="Marque para modificar los datos relativos al régimen de IVA.",
        help_en="Tick this box when changing the VAT regime data.",
        help_hu="Jelölje be az ÁFA-rendszer adatainak módosításához.",
        data_type=CasillaDataType.BOOLEAN,
        section="A. Causas de presentación",
    ),
    _Casilla(
        casilla_id="150",
        label_es="Baja en el censo de empresarios",
        label_en="Removal from the census of business operators",
        label_hu="Kijelentkezés a vállalkozói nyilvántartásból",
        help_es="Marque esta casilla para comunicar el cese de la actividad económica.",
        help_en="Tick this box to report the cessation of the economic activity.",
        help_hu="Jelölje be a gazdasági tevékenység megszüntetésének bejelentéséhez.",
        data_type=CasillaDataType.BOOLEAN,
        section="A. Causas de presentación",
    ),
    _Casilla(
        casilla_id="402",
        label_es="Régimen general del IVA",
        label_en="General VAT regime",
        label_hu="Általános ÁFA-rendszer",
        help_es="Marque si tributa por el régimen general del IVA (LIVA art. 90/91).",
        help_en="Tick if you fall under the general VAT regime (Spanish VAT Act art. 90/91).",
        help_hu="Jelölje be, ha az általános ÁFA-rendszer alá tartozik (LIVA 90/91. cikk).",
        data_type=CasillaDataType.BOOLEAN,
        section="C. Régimen IVA",
    ),
    _Casilla(
        casilla_id="403",
        label_es="Régimen simplificado del IVA",
        label_en="Simplified VAT regime",
        label_hu="Egyszerűsített ÁFA-rendszer",
        help_es="Marque si tributa por el régimen simplificado del IVA.",
        help_en="Tick if you fall under the simplified VAT regime.",
        help_hu="Jelölje be, ha az egyszerűsített ÁFA-rendszer alá tartozik.",
        data_type=CasillaDataType.BOOLEAN,
        section="C. Régimen IVA",
    ),
    _Casilla(
        casilla_id="510",
        label_es="Régimen de estimación directa del IRPF",
        label_en="Direct estimation IRPF regime",
        label_hu="Közvetlen becslésű IRPF-rendszer",
        help_es="Marque si tributa el rendimiento de la actividad por estimación directa (LIRPF art. 28).",
        help_en="Tick if you compute business income under the direct estimation regime (LIRPF art. 28).",
        help_hu="Jelölje be, ha közvetlen becsléssel állapítja meg a jövedelmét (LIRPF 28. cikk).",
        data_type=CasillaDataType.BOOLEAN,
        section="D. Régimen IRPF",
    ),
    _Casilla(
        casilla_id="608",
        label_es="Régimen de estimación objetiva del IRPF (módulos)",
        label_en="Objective estimation (modules) IRPF regime",
        label_hu="Objektív becslésű IRPF-rendszer (modulok)",
        help_es="Marque si tributa por estimación objetiva (Orden HFP/1359/2023, módulos).",
        help_en="Tick if you fall under the objective-estimation (modules) regime.",
        help_hu="Jelölje be, ha objektív becsléssel adózik (modulok).",
        data_type=CasillaDataType.BOOLEAN,
        section="D. Régimen IRPF",
    ),
    _Casilla(
        casilla_id="700",
        label_es="Epígrafe IAE",
        label_en="IAE heading (economic-activities tax)",
        label_hu="IAE tevékenységi kód",
        help_es="Código de epígrafe del Impuesto sobre Actividades Económicas que clasifica la actividad.",
        help_en="Heading code of the Spanish economic-activities tax that classifies the activity.",
        help_hu="A spanyol gazdasági-tevékenység-adó tevékenységi kódja.",
        data_type=CasillaDataType.TEXT,
        section="E. Actividades económicas",
    ),
    _Casilla(
        casilla_id="800",
        label_es="Fecha de efectos",
        label_en="Effective date",
        label_hu="Hatálybalépés dátuma",
        help_es="Fecha desde la que produce efectos la presente declaración censal.",
        help_en="Date from which this census declaration takes effect.",
        help_hu="A bejelentés hatálybalépésének dátuma.",
        data_type=CasillaDataType.DATE,
        section="F. Datos finales",
    ),
)


# ----- Modelo 232 (operaciones vinculadas) --------------------------

M232_CASILLAS: tuple[_Casilla, ...] = (
    _Casilla(
        casilla_id="01",
        label_es="N.º registros — operaciones con personas o entidades vinculadas",
        label_en="Number of related-party transaction records",
        label_hu="Kapcsolt felekkel folytatott ügyletek rekordjainak száma",
        help_es="Total de registros de operaciones con personas o entidades vinculadas declarados en el modelo (Cuadro I, art. 18 LIS).",
        help_en="Total related-party operation records declared in the form (Cuadro I, art. 18 LIS).",
        help_hu="A bejelentésben szereplő kapcsolt-fél ügyletek rekordjainak száma (I. táblázat, LIS 18. cikk).",
        data_type=CasillaDataType.INTEGER,
        section="Cuadro I. Operaciones con personas o entidades vinculadas",
    ),
    _Casilla(
        casilla_id="02",
        label_es="N.º registros — operaciones con activos intangibles (art. 23 LIS)",
        label_en="Number of intangible-asset transaction records (LIS art. 23)",
        label_hu="Immateriális eszközökkel kapcsolatos ügyletek rekordjainak száma",
        help_es="Total de registros de operaciones con activos intangibles que se han acogido al beneficio fiscal del art. 23 LIS.",
        help_en="Total intangible-asset operation records that benefit from the LIS art. 23 incentive.",
        help_hu="Az LIS 23. cikke szerinti kedvezményt igénylő ügyletek rekordjainak száma.",
        data_type=CasillaDataType.INTEGER,
        section="Cuadro II. Operaciones con activos intangibles",
    ),
    _Casilla(
        casilla_id="03",
        label_es="N.º registros — operaciones con paraísos fiscales",
        label_en="Number of tax-haven transaction records",
        label_hu="Adóparadicsomokkal folytatott ügyletek rekordjainak száma",
        help_es="Total de registros de operaciones realizadas con países o territorios calificados como paraísos fiscales.",
        help_en="Total operation records with countries classified as tax havens.",
        help_hu="Az adóparadicsomnak minősített országokkal folytatott ügyletek rekordjainak száma.",
        data_type=CasillaDataType.INTEGER,
        section="Cuadro III. Operaciones con paraísos fiscales",
    ),
)


# ----- Modelo 369 (OSS / IOSS) --------------------------------------

M369_CASILLAS: tuple[_Casilla, ...] = (
    _Casilla(
        casilla_id="01",
        label_es="Total bases imponibles",
        label_en="Total taxable bases",
        label_hu="Összes adóalap",
        help_es="Suma de las bases imponibles declaradas para cada Estado miembro de consumo y tipo aplicable.",
        help_en="Sum of taxable bases declared for each Member State of consumption and applicable rate.",
        help_hu="A bejelentett adóalapok összege fogyasztási tagállam és alkalmazandó kulcs szerint.",
        section="Resumen",
    ),
    _Casilla(
        casilla_id="02",
        label_es="Total cuotas IVA devengadas",
        label_en="Total output VAT",
        label_hu="Összes felszámított ÁFA",
        help_es="Suma de las cuotas de IVA devengadas en los Estados miembros de consumo en el régimen OSS / IOSS.",
        help_en="Sum of output VAT due in the Member States of consumption under OSS / IOSS.",
        help_hu="A fogyasztási tagállamokban felszámított ÁFA összege OSS / IOSS rendszerben.",
        section="Resumen",
    ),
    _Casilla(
        casilla_id="03",
        label_es="Total a ingresar",
        label_en="Total payable",
        label_hu="Fizetendő összeg",
        help_es="Importe total que debe ingresarse al erario español, equivalente a la suma de cuotas devengadas (no se admiten deducciones en este régimen).",
        help_en="Total amount payable to the Spanish treasury — equal to the output VAT sum (deductions are not allowed under this regime).",
        help_hu="A spanyol kincstárnak fizetendő teljes összeg, ami megegyezik a felszámított ÁFA-val (e rendszerben levonás nem alkalmazható).",
        section="Resumen",
    ),
)


# ----- Modelo 720 (bienes y derechos en el extranjero) ---------------

M720_CASILLAS: tuple[_Casilla, ...] = (
    _Casilla(
        casilla_id="01",
        label_es="N.º registros — clave C (cuentas en entidades financieras)",
        label_en="Records — key C (accounts in financial institutions)",
        label_hu="Rekordok — C kulcs (külföldi pénzintézeti számlák)",
        help_es="Total de cuentas en entidades financieras situadas en el extranjero declaradas (clave C, DA 18ª LGT).",
        help_en="Total accounts at foreign financial institutions declared (key C, DA 18 LGT).",
        help_hu="A bejelentett külföldi pénzintézeti számlák száma (C kulcs, LGT 18. kiegészítő rendelkezés).",
        data_type=CasillaDataType.INTEGER,
        section="Resumen — clave C",
    ),
    _Casilla(
        casilla_id="02",
        label_es="N.º registros — clave V (valores, seguros, rentas)",
        label_en="Records — key V (securities, insurance, annuities)",
        label_hu="Rekordok — V kulcs (értékpapírok, biztosítások, járadékok)",
        help_es="Total de valores, seguros y rentas situados en el extranjero declarados (clave V).",
        help_en="Total securities, insurance contracts and annuities held abroad (key V).",
        help_hu="A bejelentett külföldi értékpapírok, biztosítások és járadékok száma (V kulcs).",
        data_type=CasillaDataType.INTEGER,
        section="Resumen — clave V",
    ),
    _Casilla(
        casilla_id="03",
        label_es="N.º registros — clave I (bienes inmuebles en el extranjero)",
        label_en="Records — key I (foreign real estate)",
        label_hu="Rekordok — I kulcs (külföldi ingatlanok)",
        help_es="Total de bienes inmuebles y derechos sobre ellos situados en el extranjero declarados (clave I).",
        help_en="Total foreign real estate and rights thereon declared (key I).",
        help_hu="A bejelentett külföldi ingatlanok és ingatlanjogok száma (I kulcs).",
        data_type=CasillaDataType.INTEGER,
        section="Resumen — clave I",
    ),
)


# ----- Modelo 111 augmentation casillas ------------------------------
# The 111 ruleset only encodes the casillas that participate in
# formulas (03, 06, 08, 09, 11, 12, 15, 18, 28, 29, 30). The extractor
# consumes the full Apartados-I..VI block, so we add the user-input
# perceptor / percepción rows that the ruleset omits.

M111_AUGMENT: tuple[_Casilla, ...] = (
    _Casilla(
        casilla_id="01",
        label_es="N.º perceptores — rendimientos del trabajo",
        label_en="Recipients — work income",
        label_hu="Munkajövedelem-kedvezményezettek",
        help_es="Número de perceptores con rendimientos del trabajo en el trimestre.",
        help_en="Number of recipients of work income in the quarter.",
        help_hu="A negyedévben munkajövedelemben részesülők száma.",
        data_type=CasillaDataType.INTEGER,
        section="Apartado I — Rendimientos del trabajo",
    ),
    _Casilla(
        casilla_id="02",
        label_es="Importe de las percepciones — rendimientos del trabajo",
        label_en="Perceptions amount — work income",
        label_hu="Munkajövedelem összege",
        help_es="Suma de las percepciones íntegras satisfechas por rendimientos del trabajo en el trimestre.",
        help_en="Sum of gross perceptions paid as work income in the quarter.",
        help_hu="A negyedévben munkajövedelemként kifizetett bruttó jövedelmek összege.",
        section="Apartado I — Rendimientos del trabajo",
    ),
    _Casilla(
        casilla_id="04",
        label_es="N.º perceptores — actividades económicas",
        label_en="Recipients — business income",
        label_hu="Vállalkozói-jövedelem kedvezményezettek",
        help_es="Número de perceptores con rendimientos de actividades económicas en el trimestre.",
        help_en="Number of recipients of business income in the quarter.",
        help_hu="A negyedévben vállalkozói jövedelemben részesülők száma.",
        data_type=CasillaDataType.INTEGER,
        section="Apartado II — Actividades económicas",
    ),
    _Casilla(
        casilla_id="05",
        label_es="Importe de las percepciones — actividades económicas",
        label_en="Perceptions amount — business income",
        label_hu="Vállalkozói jövedelem összege",
        help_es="Suma de las percepciones íntegras satisfechas por actividades económicas en el trimestre.",
        help_en="Sum of gross perceptions paid as business income in the quarter.",
        help_hu="A negyedévi vállalkozói bruttó jövedelmek összege.",
        section="Apartado II — Actividades económicas",
    ),
    _Casilla(
        casilla_id="07",
        label_es="N.º perceptores — premios",
        label_en="Recipients — prizes",
        label_hu="Nyeremény-kedvezményezettek",
        help_es="Número de perceptores de premios sujetos a retención (LIRPF art. 101.7).",
        help_en="Number of prize recipients subject to withholding (LIRPF art. 101.7).",
        help_hu="A nyereményadó-köteles kedvezményezettek száma.",
        data_type=CasillaDataType.INTEGER,
        section="Apartado III — Premios",
    ),
    _Casilla(
        casilla_id="10",
        label_es="N.º perceptores — ganancias patrimoniales",
        label_en="Recipients — capital gains",
        label_hu="Vagyonnyereség-kedvezményezettek",
        help_es="Número de perceptores con ganancias patrimoniales por aprovechamientos forestales en montes públicos.",
        help_en="Number of recipients of capital gains from forestry on public lands.",
        help_hu="Az állami erdőkben elért vagyonnyereségben részesülők száma.",
        data_type=CasillaDataType.INTEGER,
        section="Apartado IV — Ganancias patrimoniales",
    ),
    _Casilla(
        casilla_id="13",
        label_es="N.º perceptores — contraprestaciones en especie",
        label_en="Recipients — in-kind perceptions",
        label_hu="Természetbeni jövedelmek kedvezményezettjei",
        help_es="Número de perceptores de contraprestaciones en especie en el trimestre.",
        help_en="Number of in-kind perception recipients in the quarter.",
        help_hu="A természetbeni juttatásban részesülők száma a negyedévben.",
        data_type=CasillaDataType.INTEGER,
        section="Apartado V — Contraprestaciones en especie",
    ),
    _Casilla(
        casilla_id="14",
        label_es="Valoración percepciones — contraprestaciones en especie",
        label_en="Valuation — in-kind perceptions",
        label_hu="Természetbeni juttatások értéke",
        help_es="Valor fiscal de las contraprestaciones en especie satisfechas en el trimestre.",
        help_en="Tax-valuation of in-kind perceptions paid in the quarter.",
        help_hu="A természetbeni juttatások adóértéke a negyedévben.",
        section="Apartado V — Contraprestaciones en especie",
    ),
    _Casilla(
        casilla_id="16",
        label_es="N.º perceptores — cesión de derechos de imagen",
        label_en="Recipients — image-rights assignment",
        label_hu="Képmás-jog átruházás kedvezményezettjei",
        help_es="Número de perceptores por imputación de rentas por cesión de derechos de imagen (LIRPF art. 92).",
        help_en="Number of recipients of imputed image-rights income (LIRPF art. 92).",
        help_hu="Képmás-jog jövedelemben részesülők száma.",
        data_type=CasillaDataType.INTEGER,
        section="Apartado VI — Cesión derechos imagen",
    ),
    _Casilla(
        casilla_id="17",
        label_es="Importe percepciones — cesión de derechos de imagen",
        label_en="Perceptions amount — image rights",
        label_hu="Képmás-jog jövedelem",
        help_es="Suma de las imputaciones de rentas por cesión de derechos de imagen en el trimestre.",
        help_en="Sum of imputed image-rights income in the quarter.",
        help_hu="Képmás-jog átruházás miatti jövedelmek negyedévi összege.",
        section="Apartado VI — Cesión derechos imagen",
    ),
)


# ----- Modelo 190 (resumen anual retenciones IRPF) -------------------

M190_CASILLAS: tuple[_Casilla, ...] = (
    _Casilla(
        casilla_id="01",
        label_es="N.º perceptores — rendimientos del trabajo",
        label_en="Recipients — work income",
        label_hu="Munkajövedelem-kedvezményezettek",
        help_es="Total acumulado anual de perceptores con rendimientos del trabajo (LIRPF art. 17).",
        help_en="Annual cumulative number of recipients of work income (LIRPF art. 17).",
        help_hu="Munkajövedelem-kedvezményezettek éves száma (LIRPF 17. cikk).",
        data_type=CasillaDataType.INTEGER,
        section="Apartado I — Rendimientos del trabajo",
    ),
    _Casilla(
        casilla_id="02",
        label_es="Importe percepciones — rendimientos del trabajo",
        label_en="Perceptions amount — work income",
        label_hu="Munkajövedelem összege",
        help_es="Suma anual de las percepciones íntegras satisfechas por rendimientos del trabajo.",
        help_en="Annual sum of gross perceptions paid as work income.",
        help_hu="A munkajövedelemként kifizetett bruttó jövedelmek éves összege.",
        section="Apartado I — Rendimientos del trabajo",
    ),
    _Casilla(
        casilla_id="03",
        label_es="Retenciones — rendimientos del trabajo",
        label_en="Withholdings — work income",
        label_hu="Munkajövedelem-levonás",
        help_es="Suma anual de las retenciones e ingresos a cuenta practicados sobre rendimientos del trabajo.",
        help_en="Annual sum of withholdings and payments on account on work income.",
        help_hu="Munkajövedelem után visszatartott és befizetett összegek éves összege.",
        section="Apartado I — Rendimientos del trabajo",
    ),
    _Casilla(
        casilla_id="04",
        label_es="N.º perceptores — actividades económicas",
        label_en="Recipients — business income",
        label_hu="Vállalkozói-jövedelem kedvezményezettek",
        help_es="Total acumulado anual de perceptores con rendimientos de actividades económicas.",
        help_en="Annual cumulative number of recipients of business income.",
        help_hu="Vállalkozói jövedelemben részesülő személyek éves száma.",
        data_type=CasillaDataType.INTEGER,
        section="Apartado II — Actividades económicas",
    ),
    _Casilla(
        casilla_id="05",
        label_es="Importe percepciones — actividades económicas",
        label_en="Perceptions amount — business income",
        label_hu="Vállalkozói jövedelem összege",
        help_es="Suma anual de las percepciones íntegras satisfechas por actividades económicas.",
        help_en="Annual sum of gross perceptions paid as business income.",
        help_hu="Vállalkozási jövedelem éves bruttó összege.",
        section="Apartado II — Actividades económicas",
    ),
    _Casilla(
        casilla_id="06",
        label_es="Retenciones — actividades económicas",
        label_en="Withholdings — business income",
        label_hu="Vállalkozói-jövedelem levonás",
        help_es="Suma anual de las retenciones practicadas a profesionales y actividades económicas (15%/7%).",
        help_en="Annual sum of withholdings on professionals and business activities (15% / 7%).",
        help_hu="Szakemberek és vállalkozók után visszatartott összegek éves összege (15% / 7%).",
        section="Apartado II — Actividades económicas",
    ),
    _Casilla(
        casilla_id="07",
        label_es="N.º perceptores — premios",
        label_en="Recipients — prizes",
        label_hu="Nyeremény-kedvezményezettek",
        help_es="Total anual de perceptores de premios sujetos a retención (LIRPF art. 101.7).",
        help_en="Annual number of recipients of prizes subject to withholding (LIRPF art. 101.7).",
        help_hu="A levonás alá eső nyereményekben részesülők éves száma.",
        data_type=CasillaDataType.INTEGER,
        section="Apartado III — Premios",
    ),
    _Casilla(
        casilla_id="08",
        label_es="Importe percepciones — premios",
        label_en="Perceptions amount — prizes",
        label_hu="Nyeremény összege",
        help_es="Suma anual de los premios satisfechos sometidos a retención.",
        help_en="Annual sum of taxable prizes paid.",
        help_hu="A levonás alá eső nyeremények éves összege.",
        section="Apartado III — Premios",
    ),
    _Casilla(
        casilla_id="09",
        label_es="Retenciones — premios",
        label_en="Withholdings — prizes",
        label_hu="Nyeremény-levonás",
        help_es="Suma anual de las retenciones practicadas sobre premios al tipo fijo del 19%.",
        help_en="Annual sum of withholdings on prizes at the fixed 19% rate.",
        help_hu="A nyeremények után 19%-os fix kulccsal levont összegek éves összege.",
        section="Apartado III — Premios",
    ),
    _Casilla(
        casilla_id="10",
        label_es="N.º perceptores — ganancias patrimoniales (aprovechamientos forestales)",
        label_en="Recipients — capital gains (forestry)",
        label_hu="Erdészeti vagyonnyereség-kedvezményezettek",
        help_es="Total anual de perceptores de ganancias derivadas de aprovechamientos forestales en montes públicos.",
        help_en="Annual number of recipients of forestry-derived capital gains on public lands.",
        help_hu="Az állami erdőkben elért vagyonnyereségben részesülők éves száma.",
        data_type=CasillaDataType.INTEGER,
        section="Apartado IV — Ganancias patrimoniales",
    ),
    _Casilla(
        casilla_id="11",
        label_es="Importe percepciones — ganancias patrimoniales (aprovechamientos forestales)",
        label_en="Perceptions amount — forestry capital gains",
        label_hu="Erdészeti vagyonnyereség összege",
        help_es="Suma anual de las percepciones por aprovechamientos forestales en montes públicos.",
        help_en="Annual sum of forestry capital gains on public lands.",
        help_hu="Az erdészeti vagyonnyereségek éves összege.",
        section="Apartado IV — Ganancias patrimoniales",
    ),
    _Casilla(
        casilla_id="12",
        label_es="Retenciones — ganancias patrimoniales",
        label_en="Withholdings — capital gains",
        label_hu="Vagyonnyereség-levonás",
        help_es="Suma anual de las retenciones practicadas sobre ganancias patrimoniales por aprovechamientos forestales (19%).",
        help_en="Annual sum of withholdings on forestry-related capital gains (19%).",
        help_hu="Az erdészeti vagyonnyereségek után 19%-kal levont összegek éves összege.",
        section="Apartado IV — Ganancias patrimoniales",
    ),
    _Casilla(
        casilla_id="13",
        label_es="N.º perceptores — contraprestaciones en especie",
        label_en="Recipients — in-kind perceptions",
        label_hu="Természetbeni-jövedelem kedvezményezettek",
        help_es="Total anual de perceptores de retribuciones en especie sujetas a ingreso a cuenta.",
        help_en="Annual number of recipients of in-kind perceptions subject to a payment on account.",
        help_hu="A természetbeni juttatásban részesülők éves száma.",
        data_type=CasillaDataType.INTEGER,
        section="Apartado V — Contraprestaciones en especie",
    ),
    _Casilla(
        casilla_id="14",
        label_es="Valoración percepciones — contraprestaciones en especie",
        label_en="Valuation — in-kind perceptions",
        label_hu="Természetbeni juttatások értéke",
        help_es="Suma anual del valor fiscal de las contraprestaciones en especie satisfechas.",
        help_en="Annual sum of the tax-valuation of in-kind perceptions paid.",
        help_hu="A természetbeni juttatások adóértékének éves összege.",
        section="Apartado V — Contraprestaciones en especie",
    ),
    _Casilla(
        casilla_id="15",
        label_es="Ingresos a cuenta — contraprestaciones en especie",
        label_en="Payments on account — in-kind",
        label_hu="Természetbeni-előlegek",
        help_es="Suma anual de los ingresos a cuenta practicados sobre contraprestaciones en especie.",
        help_en="Annual sum of payments on account on in-kind perceptions.",
        help_hu="Természetbeni juttatásokra alkalmazott éves előlegek összege.",
        section="Apartado V — Contraprestaciones en especie",
    ),
    _Casilla(
        casilla_id="16",
        label_es="N.º perceptores — cesión de derechos de imagen",
        label_en="Recipients — image-rights assignment",
        label_hu="Képmás-jog átruházás kedvezményezettek",
        help_es="Total anual de perceptores por imputación de rentas por cesión de derechos de imagen (LIRPF art. 92).",
        help_en="Annual number of recipients of imputed image-rights income (LIRPF art. 92).",
        help_hu="Képmás-jog átruházás miatti beszámított jövedelmekben részesülők éves száma.",
        data_type=CasillaDataType.INTEGER,
        section="Apartado VI — Cesión derechos imagen",
    ),
    _Casilla(
        casilla_id="17",
        label_es="Importe percepciones — cesión de derechos de imagen",
        label_en="Perceptions amount — image rights",
        label_hu="Képmás-jog átruházás jövedelme",
        help_es="Suma anual de las imputaciones de rentas por cesión de derechos de imagen.",
        help_en="Annual sum of imputed image-rights income.",
        help_hu="Képmás-jog átruházás miatti éves jövedelem összege.",
        section="Apartado VI — Cesión derechos imagen",
    ),
    _Casilla(
        casilla_id="18",
        label_es="Retenciones — cesión de derechos de imagen",
        label_en="Withholdings — image rights",
        label_hu="Képmás-jog átruházás levonás",
        help_es="Suma anual de las retenciones e ingresos a cuenta por imputación de rentas por cesión de derechos de imagen.",
        help_en="Annual sum of withholdings on imputed image-rights income.",
        help_hu="Képmás-jog jövedelemre alkalmazott éves levonás összege.",
        section="Apartado VI — Cesión derechos imagen",
    ),
    _Casilla(
        casilla_id="19",
        label_es="Total perceptores",
        label_en="Total recipients",
        label_hu="Összes kedvezményezett",
        help_es="Suma global de perceptores declarados en el modelo 190.",
        help_en="Global sum of recipients declared in form 190.",
        help_hu="A 190-es nyomtatványban szereplő összes kedvezményezett.",
        data_type=CasillaDataType.INTEGER,
        computed=True,
        formula_expression="(01 + 04 + 07 + 10 + 13 + 16)",
        formula_refs=("01", "04", "07", "10", "13", "16"),
        section="Resumen — Totales",
    ),
    _Casilla(
        casilla_id="20",
        label_es="Total percepciones",
        label_en="Total perceptions",
        label_hu="Összes jövedelem",
        help_es="Suma global de las percepciones íntegras declaradas en el modelo 190.",
        help_en="Global sum of gross perceptions declared in form 190.",
        help_hu="A 190-es nyomtatványban szereplő bruttó jövedelmek összege.",
        computed=True,
        formula_expression="(02 + 05 + 08 + 11 + 14 + 17)",
        formula_refs=("02", "05", "08", "11", "14", "17"),
        section="Resumen — Totales",
    ),
    _Casilla(
        casilla_id="21",
        label_es="Total retenciones e ingresos a cuenta",
        label_en="Total withholdings and payments on account",
        label_hu="Összes levonás és előleg",
        help_es="Suma global de las retenciones e ingresos a cuenta declarados en el modelo 190.",
        help_en="Global sum of withholdings and payments on account declared in form 190.",
        help_hu="A 190-es nyomtatványban szereplő levonások és előlegek összege.",
        computed=True,
        formula_expression="(03 + 06 + 09 + 12 + 15 + 18)",
        formula_refs=("03", "06", "09", "12", "15", "18"),
        section="Resumen — Totales",
    ),
)


# ----- Modelo 193 (resumen anual capital mobiliario) -----------------

M193_CASILLAS: tuple[_Casilla, ...] = (
    _Casilla(
        casilla_id="01",
        label_es="N.º total perceptores",
        label_en="Total recipients",
        label_hu="Összes kedvezményezett",
        help_es="Total acumulado anual de perceptores de rendimientos del capital mobiliario sujetos a retención (LIRPF art. 25).",
        help_en="Annual cumulative number of recipients of investment income subject to withholding (LIRPF art. 25).",
        help_hu="Tőkejövedelemben részesülők éves száma.",
        data_type=CasillaDataType.INTEGER,
        section="Resumen anual",
    ),
    _Casilla(
        casilla_id="02",
        label_es="Base retenciones",
        label_en="Withholding base",
        label_hu="Levonási alap",
        help_es="Suma anual de las bases sujetas a retención sobre rendimientos del capital mobiliario.",
        help_en="Annual sum of bases subject to withholding on investment income.",
        help_hu="A tőkejövedelmek éves levonási alapjának összege.",
        section="Resumen anual",
    ),
    _Casilla(
        casilla_id="03",
        label_es="Retenciones e ingresos a cuenta",
        label_en="Withholdings and payments on account",
        label_hu="Levonások és előlegek",
        help_es="Suma anual de las retenciones e ingresos a cuenta practicadas al tipo del 19% (LIRPF art. 101.4).",
        help_en="Annual sum of withholdings and payments on account at the 19% rate (LIRPF art. 101.4).",
        help_hu="A tőkejövedelmekre alkalmazott 19%-os éves levonás összege.",
        section="Resumen anual",
    ),
)


# ----- Modelo 347 (operaciones con terceros >3.005,06 €) -------------

M347_CASILLAS: tuple[_Casilla, ...] = (
    _Casilla(
        casilla_id="01",
        label_es="N.º total declarados",
        label_en="Total declared parties",
        label_hu="Összes bejelentett fél",
        help_es="Número de personas o entidades respecto de las cuales se ha realizado declaración por superar 3.005,06 € (Orden EHA/3012/2008).",
        help_en="Number of parties for which a declaration is filed because the threshold of €3,005.06 was exceeded.",
        help_hu="A 3 005,06 €-os küszöb átlépése miatt bejelentett személyek száma.",
        data_type=CasillaDataType.INTEGER,
        section="Resumen",
    ),
    _Casilla(
        casilla_id="02",
        label_es="Importe total anual de operaciones declaradas",
        label_en="Annual total of declared operations",
        label_hu="A bejelentett ügyletek éves teljes összege",
        help_es="Suma agregada anual de las operaciones con terceros declaradas en el modelo 347.",
        help_en="Aggregate annual sum of third-party operations declared on form 347.",
        help_hu="A 347. nyomtatványban bejelentett ügyletek éves összege.",
        section="Resumen",
    ),
    _Casilla(
        casilla_id="03",
        label_es="N.º total registros — cobros en metálico",
        label_en="Records — cash payments received",
        label_hu="Készpénzes-bevétel rekordok",
        help_es="Número de registros declarados respecto de cobros en metálico superiores a 6.000 € (art. 7 RGAT).",
        help_en="Records declared for cash receipts exceeding €6,000 (RGAT art. 7).",
        help_hu="6 000 € feletti készpénzes bevétel rekordjainak száma.",
        data_type=CasillaDataType.INTEGER,
        section="Resumen — Metálico",
    ),
    _Casilla(
        casilla_id="04",
        label_es="Importe total — cobros en metálico",
        label_en="Total cash payments received",
        label_hu="Készpénzes-bevétel összege",
        help_es="Suma anual de los cobros en metálico superiores a 6.000 € declarados.",
        help_en="Annual sum of cash receipts exceeding €6,000 declared.",
        help_hu="A 6 000 € feletti készpénzes bevételek éves összege.",
        section="Resumen — Metálico",
    ),
)


# ----- Modelo 349 (operaciones intracomunitarias) --------------------

M349_CASILLAS: tuple[_Casilla, ...] = (
    _Casilla(
        casilla_id="01",
        label_es="N.º total operadores intracomunitarios",
        label_en="Intra-Community operators",
        label_hu="Közösségi gazdasági szereplők",
        help_es="Número de operadores intracomunitarios declarados en el período (entregas y/o adquisiciones, LIVA art. 25 y 26).",
        help_en="Number of intra-Community operators declared in the period (supplies and/or acquisitions, Spanish VAT Act arts. 25-26).",
        help_hu="A bejelentett közösségi szereplők száma az időszakban (LIVA 25-26. cikk).",
        data_type=CasillaDataType.INTEGER,
        section="Resumen",
    ),
    _Casilla(
        casilla_id="02",
        label_es="Importe total operaciones",
        label_en="Total operation amount",
        label_hu="Ügyletek teljes összege",
        help_es="Importe total de las operaciones intracomunitarias declaradas (entregas + adquisiciones + servicios).",
        help_en="Total amount of intra-Community operations declared (supplies + acquisitions + services).",
        help_hu="A közösségi ügyletek teljes összege.",
        section="Resumen",
    ),
    _Casilla(
        casilla_id="03",
        label_es="N.º operadores con rectificaciones",
        label_en="Operators with rectifications",
        label_hu="Helyesbítéssel érintett szereplők",
        help_es="Operadores cuyas operaciones se rectifican respecto de períodos anteriores.",
        help_en="Operators whose operations are rectifying earlier periods.",
        help_hu="Korábbi időszakok helyesbítésében érintett szereplők száma.",
        data_type=CasillaDataType.INTEGER,
        section="Resumen — Rectificaciones",
    ),
    _Casilla(
        casilla_id="04",
        label_es="Importe rectificaciones",
        label_en="Rectifications amount",
        label_hu="Helyesbítések összege",
        help_es="Importe total de las rectificaciones declaradas en el período (signo positivo = aumento).",
        help_en="Total amount of rectifications declared in the period (positive sign = increase).",
        help_hu="Az időszakban bejelentett helyesbítések teljes összege (pozitív jel = növekedés).",
        section="Resumen — Rectificaciones",
    ),
)


# ----- Modelo 840 (IAE — text casillas) ------------------------------

M840_CASILLAS: tuple[_Casilla, ...] = (
    _Casilla(
        casilla_id="14",
        label_es="Ejercicio",
        label_en="Tax year",
        label_hu="Adóév",
        help_es="Ejercicio al que se refiere la declaración del IAE.",
        help_en="Tax year covered by the IAE declaration.",
        help_hu="Az IAE-bevallás vonatkozó adóéve.",
        data_type=CasillaDataType.TEXT,
        section="Datos generales",
    ),
    _Casilla(
        casilla_id="15",
        label_es="Causa de presentación",
        label_en="Filing cause",
        label_hu="Bejelentés oka",
        help_es="Acto censal que motiva la declaración: alta, variación o baja en el Impuesto sobre Actividades Económicas.",
        help_en="Census act prompting the declaration: enrolment, change, or removal in the IAE.",
        help_hu="A bejelentést indokoló esemény: beiratkozás, módosítás vagy kijelentkezés.",
        data_type=CasillaDataType.TEXT,
        section="Datos generales",
    ),
    _Casilla(
        casilla_id="33",
        label_es="Clase de cuota",
        label_en="Quota class",
        label_hu="Adóosztály",
        help_es="Clase de cuota del IAE: municipal, provincial o nacional.",
        help_en="IAE quota class: municipal, provincial or national.",
        help_hu="IAE-adóosztály: önkormányzati, tartományi vagy országos.",
        data_type=CasillaDataType.TEXT,
        section="Cuota",
    ),
    _Casilla(
        casilla_id="34",
        label_es="Tipo de actividad",
        label_en="Activity type",
        label_hu="Tevékenység típusa",
        help_es="Tipo de actividad: empresarial, profesional o artística.",
        help_en="Activity type: business, professional or artistic.",
        help_hu="Tevékenység típusa: vállalkozói, szakmai vagy művészi.",
        data_type=CasillaDataType.TEXT,
        section="Actividad",
    ),
    _Casilla(
        casilla_id="37",
        label_es="Grupo o epígrafe",
        label_en="Group or heading",
        label_hu="Csoport vagy tételszám",
        help_es="Grupo o epígrafe del IAE asignado a la actividad económica del sujeto pasivo.",
        help_en="IAE group or heading assigned to the taxpayer's economic activity.",
        help_hu="A tevékenységhez rendelt IAE-csoport vagy tételszám.",
        data_type=CasillaDataType.TEXT,
        section="Actividad",
    ),
    _Casilla(
        casilla_id="38",
        label_es="Municipio",
        label_en="Municipality",
        label_hu="Település",
        help_es="Municipio en el que se ejerce la actividad declarada.",
        help_en="Municipality where the declared activity is carried out.",
        help_hu="A tevékenység végzésének helye szerinti település.",
        data_type=CasillaDataType.TEXT,
        section="Localización",
    ),
    _Casilla(
        casilla_id="40",
        label_es="Provincia",
        label_en="Province",
        label_hu="Tartomány",
        help_es="Provincia en la que se ejerce la actividad declarada.",
        help_en="Province where the declared activity is carried out.",
        help_hu="A tevékenység végzésének helye szerinti tartomány.",
        data_type=CasillaDataType.TEXT,
        section="Localización",
    ),
    _Casilla(
        casilla_id="62",
        label_es="Fecha de efectos",
        label_en="Effective date",
        label_hu="Hatálybalépés dátuma",
        help_es="Fecha desde la que produce efectos la presente declaración del IAE.",
        help_en="Date from which this IAE declaration takes effect.",
        help_hu="A bejelentés hatálybalépésének dátuma.",
        data_type=CasillaDataType.TEXT,
        section="Datos finales",
    ),
)


# ---------------------------------------------------------------------
# Help text fallback when the ruleset only provides a label.
# ---------------------------------------------------------------------


_SOURCE_LABEL = {
    "ley": "Ley",
    "real_decreto": "RD",
    "orden_ministerial": "Orden",
    "reglamento": "Reglamento",
    "manual_practico": "Manual práctico",
    "boe": "BOE",
}


def _legal_hint(legal_basis: tuple) -> str:
    """Render a compact ``(Ley art. 91, BOE-A-1992-28740)``-style hint.

    Source words are capitalised (``Ley`` not ``ley``) and Spanish stays
    canonical so the legal pointer reads correctly in any language.
    """
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


_CROSS_MODELO = {
    "180": ("M115", "Resumen anual que consolida los datos trimestrales del modelo 115."),
    "190": ("M111", "Resumen anual que consolida los datos trimestrales del modelo 111."),
    "193": ("M123", "Resumen anual que consolida los datos trimestrales del modelo 123."),
    "390": ("M303", "Resumen anual que consolida los datos trimestrales del modelo 303."),
    "100": ("M130/M131", "Declaración anual del IRPF; recoge los pagos fraccionados de los modelos 130 y 131."),
    "200": ("M202", "Declaración anual del Impuesto sobre Sociedades; recoge los pagos fraccionados del modelo 202."),
}


def _cross_modelo_hint(modelo: str) -> str:
    """Return a short Spanish note pointing at the upstream modelo, if any."""
    if modelo not in _CROSS_MODELO:
        return ""
    _, note = _CROSS_MODELO[modelo]
    return f" {note}"


def _help_from_label(
    label: dict[str, str],
    notes_es: str | None,
    *,
    formula_expression: str | None = None,
    legal_hint: str = "",
    cross_modelo_hint: str = "",
) -> dict[str, str]:
    """Return a trilingual help body distinct from the label.

    Priority:
      1. ``notes_es`` (engine-author note in Spanish) — paired with the
         English / Hungarian labels for cross-lingual context.
      2. Computed casillas: append a formula reminder so the help
         carries calculation provenance.
      3. Otherwise: re-use the label trilingually as a stable fallback.

    The ``legal_hint`` (``(Base legal: …)``) is appended to every variant
    so the corpus carries the BOE / law / orden grounding inline,
    matching what the rule engine's ``LegalCitation`` already encodes.
    """
    suffix_es = f" Se calcula como {formula_expression}." if formula_expression else ""
    legal_es = legal_hint
    legal_en = legal_hint.replace("Base legal:", "Legal basis:") if legal_hint else ""
    legal_hu = legal_hint.replace("Base legal:", "Jogalap:") if legal_hint else ""
    cross_es = cross_modelo_hint
    cross_en = cross_modelo_hint.replace(
        "Resumen anual que consolida los datos trimestrales del modelo",
        "Annual summary that consolidates the quarterly data of form",
    ).replace(
        "Declaración anual del IRPF; recoge los pagos fraccionados de los modelos",
        "Annual IRPF declaration; consolidates the fractional payments of forms",
    ).replace(
        "Declaración anual del Impuesto sobre Sociedades; recoge los pagos fraccionados del modelo",
        "Annual Corporate Income Tax declaration; consolidates the fractional payments of form",
    )
    cross_hu = cross_modelo_hint.replace(
        "Resumen anual que consolida los datos trimestrales del modelo",
        "Éves összefoglaló, amely az alábbi modell negyedéves adatait konszolidálja:",
    ).replace(
        "Declaración anual del IRPF; recoge los pagos fraccionados de los modelos",
        "Éves IRPF-bevallás; az alábbi modellek részletfizetéseit foglalja össze:",
    ).replace(
        "Declaración anual del Impuesto sobre Sociedades; recoge los pagos fraccionados del modelo",
        "Éves társasági adó bevallás; az alábbi modell részletfizetéseit foglalja össze:",
    )
    if notes_es:
        return {
            "es": notes_es + suffix_es + cross_es + legal_es,
            "en": label.get("en", label["es"])
            + (f" Computed as {formula_expression}." if formula_expression else "")
            + cross_en
            + legal_en,
            "hu": label.get("hu", label["es"])
            + (f" Számítás: {formula_expression}." if formula_expression else "")
            + cross_hu
            + legal_hu,
        }
    if formula_expression:
        return {
            "es": f"{label['es']}. Se calcula como {formula_expression}.{cross_es}{legal_es}",
            "en": f"{label.get('en', label['es'])}. Computed as {formula_expression}.{cross_en}{legal_en}",
            "hu": f"{label.get('hu', label['es'])}. Számítás: {formula_expression}.{cross_hu}{legal_hu}",
        }
    if legal_hint or cross_modelo_hint:
        return {
            "es": label["es"] + cross_es + legal_es,
            "en": label.get("en", label["es"]) + cross_en + legal_en,
            "hu": label.get("hu", label["es"]) + cross_hu + legal_hu,
        }
    return {
        "es": label["es"],
        "en": label.get("en", label["es"]),
        "hu": label.get("hu", label["es"]),
    }


# ---------------------------------------------------------------------
# Source URLs.
# ---------------------------------------------------------------------


def _source_url_for(modelo: str, year: int) -> str:
    if modelo in {"100", "111", "115", "123", "130", "131", "180", "190", "193"}:
        return IRPF_MANUAL_URL.format(year=year)
    if modelo in {"303", "390", "347", "349", "369"}:
        return IVA_MANUAL_URL.format(year=year)
    if modelo in {"200", "202", "232"}:
        return SOCIEDADES_MANUAL_URL.format(year=year)
    if modelo in {"036", "037"}:
        return BOE_036_URL
    if modelo == "720":
        return BOE_720_URL
    if modelo == "840":
        return BOE_840_URL
    return IRPF_MANUAL_URL.format(year=year)


def _section_for(modelo: str) -> str:
    return {
        "100": "Cuota a ingresar / devolver",
        "111": "Liquidación",
        "115": "Liquidación",
        "123": "Liquidación",
        "130": "I. Actividades económicas",
        "131": "I. Actividades en estimación objetiva",
        "180": "Resumen anual",
        "190": "Resumen anual",
        "193": "Resumen anual",
        "200": "Liquidación (página 14)",
        "202": "Liquidación",
        "232": "Resumen",
        "303": "Liquidación",
        "347": "Resumen",
        "349": "Resumen",
        "369": "Resumen",
        "390": "Resumen anual",
        "036": "Datos censales",
        "037": "Datos censales",
        "720": "Resumen",
        "840": "Datos generales",
    }.get(modelo, "")


def _section_for_casilla(modelo: str, casilla_id: str) -> str:
    """Return a finer-grained section name based on the form structure."""
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
            return "IVA deducible y resultado régimen general"
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


# ---------------------------------------------------------------------
# Records from a Ruleset.
# ---------------------------------------------------------------------


def _validation_for(modelo: str, casilla_id: str, computed: bool) -> tuple[ValidationRuleReference, ...]:
    """Return validation rules locked at the casilla level.

    Conservative seed: every monetary casilla cannot be a free-form
    sentinel; computed casillas should derive (no manual override
    contracts), and certain casillas have hard bounds rooted in the
    AEAT instructions.
    """
    rules: list[ValidationRuleReference] = []
    if computed:
        rules.append(
            ValidationRuleReference(
                rule="must_derive",
                value=True,
                description="Computed casilla — value must be derived by the rule engine, not user-supplied.",
            )
        )
    # Modelo 130 / 131 quarterly clamps
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
    label = dict(cdef.label)
    legal_hint = _legal_hint(cdef.legal_basis)
    help_text = _help_from_label(
        label,
        cdef.notes_es,
        formula_expression=formula_expression,
        legal_hint=legal_hint,
        cross_modelo_hint=_cross_modelo_hint(modelo),
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
        label=label,
        help=help_text,
        data_type=cdef.data_type,
        select_options=None,
        required=False,
        computed=computed,
        formula=formula_obj,
        references_casillas=tuple(formula_refs),
        references_rules=tuple(references_rules),
        validation=_validation_for(modelo, cdef.casilla_id, computed),
        source_manual_url=source_url,
        source_page=1,
        source_section=section,
        definition_reviewed_by=REVIEWED_BY,
        definition_reviewed_at=REVIEWED_AT,
        llm_draft_provenance=None,
    )


def _records_from_ruleset(
    *,
    modelo: str,
    period: str,
    ruleset: Ruleset,
    source_url: str,
    extra_rulesets: list[Ruleset] | None = None,
    link_formulas: bool = True,
) -> list[CasillaRecord]:
    formula_by_casilla = {f.casilla_id: f for f in ruleset.formulas}
    extra_formula_ids: dict[str, list[str]] = {}
    for extra in extra_rulesets or ():
        for f in extra.formulas:
            extra_formula_ids.setdefault(f.casilla_id, []).append(f.formula_id)
    # Resolve parameter values active on the ruleset's effective_from.
    params_resolved: dict[str, Decimal] = {}
    try:
        for param_id in ruleset.parameters.entries.keys():
            params_resolved[param_id] = ruleset.parameters.resolve(param_id, on=ruleset.effective_from)
    except Exception:
        params_resolved = {}
    records: list[CasillaRecord] = []

    for cdef in ruleset.casillas:
        f = formula_by_casilla.get(cdef.casilla_id)
        if link_formulas and f is not None:
            inner = f.formula.operands[0] if isinstance(f.formula, RoundFormula) else f.formula
            expr = _render_operand(inner, params=params_resolved)
            refs = tuple(_collect_casilla_refs(f.formula))
            rules_ref: tuple[str, ...] = (f.formula_id,) + tuple(extra_formula_ids.get(cdef.casilla_id, ()))
            computed = cdef.computed
        elif f is not None:
            # Schema-only fallback (cross-year): keep the casilla but
            # drop the formula cross-link to avoid attaching a different
            # year's ``formula_id`` to this period.
            expr = None
            refs = ()
            rules_ref = ()
            computed = False
        else:
            expr = None
            refs = ()
            rules_ref = tuple(extra_formula_ids.get(cdef.casilla_id, ())) if link_formulas else ()
            computed = cdef.computed
        section = _section_for_casilla(modelo, cdef.casilla_id)
        records.append(
            _record_from_ruleset_casilla(
                modelo=modelo,
                period=period,
                cdef=cdef,
                formula_expression=expr,
                formula_refs=refs,
                references_rules=rules_ref,
                source_url=source_url,
                section=section,
                computed_override=computed,
            )
        )
    return records


# ---------------------------------------------------------------------
# Records from manual _Casilla data.
# ---------------------------------------------------------------------


def _record_from_manual(
    *,
    modelo: str,
    period: str,
    c: _Casilla,
    source_url: str,
) -> CasillaRecord:
    formula_obj = (
        FormulaReference(expression=c.formula_expression, references_casillas=c.formula_refs)
        if c.formula_expression
        else None
    )
    cross = _cross_modelo_hint(modelo)
    cross_en = cross.replace(
        "Resumen anual que consolida los datos trimestrales del modelo",
        "Annual summary that consolidates the quarterly data of form",
    ).replace(
        "Declaración anual del IRPF; recoge los pagos fraccionados de los modelos",
        "Annual IRPF declaration; consolidates the fractional payments of forms",
    ).replace(
        "Declaración anual del Impuesto sobre Sociedades; recoge los pagos fraccionados del modelo",
        "Annual Corporate Income Tax declaration; consolidates the fractional payments of form",
    )
    cross_hu = cross.replace(
        "Resumen anual que consolida los datos trimestrales del modelo",
        "Éves összefoglaló, amely az alábbi modell negyedéves adatait konszolidálja:",
    ).replace(
        "Declaración anual del IRPF; recoge los pagos fraccionados de los modelos",
        "Éves IRPF-bevallás; az alábbi modellek részletfizetéseit foglalja össze:",
    ).replace(
        "Declaración anual del Impuesto sobre Sociedades; recoge los pagos fraccionados del modelo",
        "Éves társasági adó bevallás; az alábbi modell részletfizetéseit foglalja össze:",
    )
    return CasillaRecord(
        synthetic=False,
        modelo=f"MODELO_{modelo}",
        period=period,
        casilla_id=c.casilla_id,
        label={"es": c.label_es, "en": c.label_en, "hu": c.label_hu},
        help={
            "es": c.help_es + cross,
            "en": c.help_en + cross_en,
            "hu": c.help_hu + cross_hu,
        },
        data_type=c.data_type,
        select_options=c.select_options,
        required=False,
        computed=c.computed,
        formula=formula_obj,
        references_casillas=c.formula_refs,
        references_rules=c.references_rules,
        validation=_validation_for(modelo, c.casilla_id, c.computed),
        source_manual_url=source_url,
        source_page=1,
        source_section=c.section or _section_for(modelo),
        definition_reviewed_by=REVIEWED_BY,
        definition_reviewed_at=REVIEWED_AT,
        llm_draft_provenance=None,
    )


# ---------------------------------------------------------------------
# Per-modelo generators.
# ---------------------------------------------------------------------


def _ruleset_for(modelo: str, year: int) -> Ruleset | None:
    """Return the primary ruleset matching (modelo, year) exactly.

    Returns None when no year-exact ruleset is registered. Fallback to
    a different year is intentionally NOT done here — see
    :func:`_schema_ruleset_for` for the schema fallback chain. The
    caller cross-links a corpus record to ``formula_id``s only when the
    year matches; using a different-year ruleset would attach a 2025
    ``formula_id`` to a 2023 fiscal-period catalogue, which is a
    legal-traceability lie.
    """
    import importlib

    if modelo in {"190", "193", "347", "349"}:
        return None
    if modelo in {"036", "037", "232", "369", "720", "840"}:
        return None

    candidates: list[str] = [f"aeat.domain.formulas._rulesets.modelo_{modelo}_{year}"]
    for mod_path in candidates:
        try:
            mod = importlib.import_module(mod_path)
        except ModuleNotFoundError:
            continue
        return getattr(mod, "RULESET", None)
    return None


def _schema_ruleset_for(modelo: str, year: int) -> Ruleset | None:
    """Return a ruleset whose ``casillas`` (labels, IDs, types) cover this year.

    For years where the engine has no year-specific ruleset (e.g., M303
    in 2023), fall back to the closest available ruleset's casilla
    schema so the corpus still represents the form structure. Formulas
    are NOT inherited across years; only labels / IDs / data types.
    """
    import importlib

    exact = _ruleset_for(modelo, year)
    if exact is not None:
        return exact

    if modelo in {"190", "193", "347", "349"}:
        return None
    if modelo in {"036", "037", "232", "369", "720", "840"}:
        return None

    fallback_years: list[int] = []
    if year < 2024:
        fallback_years = [2024, 2025, 2026]
    elif year > 2026:
        fallback_years = [2026, 2025, 2024]
    else:
        fallback_years = [year + 1, year - 1, 2025]
    for fallback_year in fallback_years:
        try:
            mod = importlib.import_module(f"aeat.domain.formulas._rulesets.modelo_{modelo}_{fallback_year}")
        except ModuleNotFoundError:
            continue
        return getattr(mod, "RULESET", None)
    return None


def _additional_rulesets_for(modelo: str, year: int) -> list[Ruleset]:
    """Return secondary rulesets (e.g., summary variants) that share the modelo + year.

    Their formulas augment the corpus' ``references_rules`` for shared casilla IDs.
    """
    import importlib

    extras: list[Ruleset] = []
    if modelo == "100" and year == 2025:
        try:
            mod = importlib.import_module("aeat.domain.formulas._rulesets.modelo_100_summary_2025")
        except ModuleNotFoundError:
            pass
        else:
            rs = getattr(mod, "RULESET", None)
            if rs is not None:
                extras.append(rs)
    return extras


def generate_records(modelo: str, period: str, year: int) -> list[CasillaRecord]:
    src = _source_url_for(modelo, year)

    schema_ruleset = _schema_ruleset_for(modelo, year)
    if schema_ruleset is not None:
        # Cross-link formulas only when the year matches the ruleset's
        # effective year — otherwise we'd attach a 2025 ``formula_id``
        # to a 2023 fiscal-period catalogue, which is a legal lie.
        primary_ruleset = _ruleset_for(modelo, year)
        extras = _additional_rulesets_for(modelo, year) if primary_ruleset is not None else []
        records = _records_from_ruleset(
            modelo=modelo,
            period=period,
            ruleset=schema_ruleset,
            source_url=src,
            extra_rulesets=extras,
            link_formulas=primary_ruleset is not None,
        )
        if modelo == "111":
            existing_ids = {r.casilla_id for r in records}
            for c in M111_AUGMENT:
                if c.casilla_id not in existing_ids:
                    records.append(_record_from_manual(modelo=modelo, period=period, c=c, source_url=src))
            records.sort(key=lambda r: int(r.casilla_id))
        return records

    if modelo in {"036", "037"}:
        return [_record_from_manual(modelo=modelo, period=period, c=c, source_url=src) for c in CENSAL_CASILLAS]
    if modelo == "232":
        return [_record_from_manual(modelo=modelo, period=period, c=c, source_url=BOE_232_URL) for c in M232_CASILLAS]
    if modelo == "369":
        return [_record_from_manual(modelo=modelo, period=period, c=c, source_url=BOE_369_URL) for c in M369_CASILLAS]
    if modelo == "720":
        return [_record_from_manual(modelo=modelo, period=period, c=c, source_url=BOE_720_URL) for c in M720_CASILLAS]
    if modelo == "190":
        return [_record_from_manual(modelo=modelo, period=period, c=c, source_url=BOE_190_URL) for c in M190_CASILLAS]
    if modelo == "193":
        return [_record_from_manual(modelo=modelo, period=period, c=c, source_url=BOE_193_URL) for c in M193_CASILLAS]
    if modelo == "347":
        return [_record_from_manual(modelo=modelo, period=period, c=c, source_url=BOE_347_URL) for c in M347_CASILLAS]
    if modelo == "349":
        return [_record_from_manual(modelo=modelo, period=period, c=c, source_url=BOE_349_URL) for c in M349_CASILLAS]
    if modelo == "840":
        return [_record_from_manual(modelo=modelo, period=period, c=c, source_url=BOE_840_URL) for c in M840_CASILLAS]

    raise SystemExit(f"no generator for modelo {modelo}")


# ---------------------------------------------------------------------
# Driver.
# ---------------------------------------------------------------------


# The canonical set of supported modelos is owned by the ModeloCode
# enum; we derive the iteration order from there so this list never
# drifts when a new modelo lands.
from ..modelos import ModeloCode as _ModeloCode  # noqa: E402

ALL_MODELOS: tuple[str, ...] = tuple(sorted(code.value for code in _ModeloCode))


def _save_with_retry(catalogue: CasillaCatalogue, *, attempts: int = 5) -> None:
    """Save the catalogue, retrying on transient OS errors.

    Windows occasionally raises ``OSError: [Errno 22] Invalid argument``
    when an indexer / antivirus / vaultspec-rag holds the file briefly.
    Sleep+retry handles the common transient case without masking real
    permission errors.
    """
    import time

    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            save_casillas(catalogue)
            return
        except OSError as exc:
            last_exc = exc
            if attempt == attempts:
                raise
            time.sleep(0.2 * attempt)
    if last_exc is not None:
        raise last_exc


def _extractor_casilla_ids(modelo: str) -> set[str]:
    """Return the union of every registered extractor's declared casilla IDs for a modelo.

    Pulls from :class:`GenericDeclaracionExtractor` ``casilla_ids`` and
    ``text_casilla_ids`` ClassVars so the hydrate generator does not
    shadow lists that already live on the extractor classes.
    """
    from ...adapters.inbound.declaracion._extractors import _REGISTERED_CLASSES

    out: set[str] = set()
    for cls in _REGISTERED_CLASSES:
        if cls.template_revision.modelo != modelo:
            continue
        out.update(getattr(cls, "casilla_ids", ()))
        out.update(getattr(cls, "text_casilla_ids", ()))
    return out


def _assert_manual_data_tracks_extractors() -> None:
    """Loud-fail if the curated manual ``_Casilla`` tuples drift from the extractor IDs.

    The extractor classes (e.g. :class:`Modelo190V2025Extractor`) own
    the canonical casilla-id set for modelos that lack a rule-engine
    ruleset. The hydrate script's curated tuples carry trilingual
    label / help / data_type which the extractor does not. To avoid
    shadowing, we never declare a casilla in the curated tuple that
    the extractor doesn't declare and vice versa.
    """
    pairs = [
        ("190", M190_CASILLAS),
        ("193", M193_CASILLAS),
        ("347", M347_CASILLAS),
        ("349", M349_CASILLAS),
        ("840", M840_CASILLAS),
    ]
    failures: list[str] = []
    for modelo, manual in pairs:
        manual_ids = {c.casilla_id for c in manual}
        extractor_ids = _extractor_casilla_ids(modelo)
        missing = extractor_ids - manual_ids
        extra = manual_ids - extractor_ids
        if missing:
            failures.append(f"M{modelo}: extractor declares ids missing from manual data: {sorted(missing)}")
        if extra:
            failures.append(f"M{modelo}: manual data declares ids not in extractor: {sorted(extra)}")
    if failures:
        raise RuntimeError(
            "hydrate manual data drifted from extractor casilla IDs:\n" + "\n".join(f" - {f}" for f in failures)
        )


def run() -> None:
    _assert_manual_data_tracks_extractors()
    written = 0
    for modelo in ALL_MODELOS:
        meta = get_modelo(modelo)
        cadence = meta.cadence

        years = list(YEARS)
        if modelo == "100":
            years = [2021, 2022, 2023, 2024, 2025, 2026]

        for year in years:
            for period in _periods_for(cadence, year):
                records = generate_records(modelo, period, year)
                catalogue = CasillaCatalogue(
                    modelo=f"MODELO_{modelo}",
                    period=period,
                    records=tuple(records),
                )
                _save_with_retry(catalogue)
                written += 1
    print(f"wrote {written} casilla catalogues to {CORPUS_ROOT}")


if __name__ == "__main__":
    run()
