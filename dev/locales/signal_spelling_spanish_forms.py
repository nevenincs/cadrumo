"""Finite Spanish forms missing from the pinned spelling dictionary.

Agreement and number rules apply only to reviewed native stems. They never
remove arbitrary suffixes or accents from unknown words.
"""

# Reviewed tú imperatives observed in Spanish operator prose. Each entry is the
# stem as written before one enclitic (including its required accent), not a
# license to strip suffixes from arbitrary dictionary words. RAE describes the
# attachment and accentuation of these pronouns in its orthography:
# https://www.rae.es/diccionario-estudiante/docs/ortografia.pdf
_SPANISH_DIRECT_OBJECT_IMPERATIVES = frozenset(
    {
        "acóta",
        "actíva",
        "actualíza",
        "adminístra",
        "adjúnta",
        "alinéa",
        "apláza",
        "apruéba",
        # https://dle.rae.es/asociar
        "asócia",
        "reinténta",
        # https://dle.rae.es/renovar
        "renuéva",
        "lísta",
        "archíva",
        "anóta",
        "apórta",
        "calcúla",
        "clasifíca",
        "combína",
        "comuníca",
        "concília",
        "configúra",
        "confírma",
        "consérva",
        "cópia",
        "declára",
        "desactíva",
        "descárga",
        "desígna",
        "edíta",
        "elimína",
        "elíge",
        "enuméra",
        "establéce",
        "examína",
        "exclúye",
        "expórta",
        "gestióna",
        "guía",
        "impórta",
        "instála",
        "inicialíza",
        "introdúce",
        "investíga",
        "manten",
        "modifíca",
        "muéstra",
        "márca",
        "nómbra",
        "omíte",
        "presénta",
        "previsualíza",
        "proporcióna",
        "quíta",
        "reanúda",
        "recompíla",
        "reconstrúye",
        "regenéra",
        "regístra",
        "repíte",
        "respónde",
        "resuélve",
        "restáura",
        "revóca",
        "revísa",
        "rastréa",
        "sálta",
        "sepára",
        "termína",
        "tráta",
        "vacía",
        "vincúla",
    }
)
# These observed infinitives retain their original stress with one clitic.
# They are deliberately separate from the accented imperative stems above.
_SPANISH_DIRECT_OBJECT_INFINITIVES = frozenset(
    {
        "configurar",
        "descartar",
        "indexar",
        "juntar",
        "ofrecer",
        "previsualizar",
        "rastrear",
        "recargar",
        "reconciliar",
        "reejecutar",
        # https://dle.rae.es/revertir
        "revertir",
        "sobrescribir",
    }
)
# The observed gerund has a different stress pattern from an imperative.
_SPANISH_DIRECT_OBJECT_GERUNDS = frozenset({"replicándo"})
# Only these reviewed imperative stems additionally take an indirect object.
_SPANISH_INDIRECT_OBJECT_IMPERATIVES = frozenset({"indíca", "quíta"})
_SPANISH_DIRECT_OBJECT_CLITICS = ("lo", "la", "los", "las")


def is_reviewed_spanish_enclitic(word: str) -> bool:
    """Recognize one pronoun on a reviewed verb form, preserving its accent."""
    # Sentence-initial capitalization is grammatical; do not casefold the
    # entire token, which would admit arbitrary internal capitalization.
    word = word[:1].lower() + word[1:]
    if word == "autentícate":
        return True
    if any(word == stem + clitic for stem in _SPANISH_INDIRECT_OBJECT_IMPERATIVES for clitic in ("le", "les")):
        return True
    return any(
        word.endswith(clitic)
        and (
            word[: -len(clitic)] in _SPANISH_DIRECT_OBJECT_IMPERATIVES
            or word[: -len(clitic)] in _SPANISH_DIRECT_OBJECT_INFINITIVES
            or word[: -len(clitic)] in _SPANISH_DIRECT_OBJECT_GERUNDS
        )
        for clitic in _SPANISH_DIRECT_OBJECT_CLITICS
    )


# Observed technical adjectives: typed data, intra-community transactions,
# stale/malformed state, countersigned records and atomic writes. Agreement
# changes gender and number, but does not change the reviewed lexical stem.
# https://www.bizkaia.eus/fitxategiak/05/ogasuna/ereduak/Argitaratu/349CasInst.PDF
# https://www3.agenciatributaria.gob.es/static_files/Sede/Agencia_Tributaria/Planificacion/Plan_estrategico_2024_2027/Adenda_2026_PLAN_OBJETIVOS.pdf
# https://docs.python.org/es/3.11/tutorial/modules.html
# https://docs.python.org/es/3.13/whatsnew/3.2.html
# https://docs.python.org/es/3.13/using/windows.html
# https://docs.cloud.google.com/monitoring/api/troubleshooting?hl=es-419
_AGREEMENT_STEMS = frozenset(
    {
        "tipad",
        "intracomunitari",
        "desactualizad",
        "malformad",
        "contrafirmad",
        "atómic",
        "precalculad",
        "recalculad",
        "recapitulativ",
        # https://learn.microsoft.com/es-es/sql/t-sql/statements/alter-database-transact-sql-set-hadr
        "desincronizad",
    }
)
_NUMBER_ENDINGS = {
    "editable": "s",
    "instalable": "s",
    "reintento": "s",
    # https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/guia-practica-cumplimentacion-modelo-censal-036/capitulo-09-retenciones-ingresos-cuenta/modelo-117.html
    "reembolso": "s",
    # https://www.udep.edu.pe/castellanoactual/resolvedor-resolvista-resolvente/
    "resolvedor": "es",
    # https://redcol.minciencias.gov.co/Record/EDOCUR2_6bdb4ce8b394921fe1d85d6584b1b724/Description
    "automatizable": "s",
    "subpaquete": "s",
    # https://learn.microsoft.com/es-es/windows/win32/shell/about-user-profiles
    "subcarpeta": "s",
    # Native dictionary and official tax, statistical, transport and legal use:
    # https://dle.rae.es/tabulaci%C3%B3n
    # https://dle.rae.es/descartable
    # https://dle.rae.es/enchufable
    # https://dle.rae.es/ratio
    # https://www.ine.es/jaxi/Tabla.htm?L=0&tpx=20412
    # https://boe.es/diario_boe/txt.php?id=BOE-A-2006-18205
    # https://boe.es/buscar/doc.php?id=BOE-A-2021-18811
    # https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2019/capitulo-6-rendimientos-actividades-economicas-generales/elementos-patrimoniales-afectos-actividad-economica/traspaso-elementos-patrimoniales-empresarial-personal.html
    # https://boe.es/diario_boe/txt.php?id=BOE-B-2010-29037
    "tabulación": "es",
    "descartable": "s",
    "enchufable": "s",
    "ratio": "s",
    "percentil": "es",
    "subcontratación": "es",
    "achatarramiento": "s",
    "desafectación": "es",
    "regenerable": "s",
    "subcomando": "s",
    "reanudable": "s",
    "auditable": "s",
    "contrafirmante": "s",
    "exigibilidad": "es",
    "sobrescritura": "s",
}
# https://docs.python.org/es/3/tutorial/inputoutput.html
_INFINITIVES = frozenset({"previsualizar", "contrafirmar", "deserializar"})
# Closed, reviewed conjugations of technical verbs in the documentation. Prefix
# re- is not stripped from arbitrary words, so unrelated accents stay checked.
# https://www.rae.es/sites/default/files/principales_novedades_de_la_ortografia_de_la_lengua_espanola.pdf
# https://docs.python.org/es/3.11/tutorial/modules.html
# https://docs.python.org/es/3.11/library/json.html
# https://dle.rae.es/calcular ; https://dle.rae.es/clasificar
# https://developer.mozilla.org/es/docs/Learn_web_development/Core/Frameworks_libraries/React_getting_started
# https://developer.mozilla.org/es/docs/Learn_web_development/Core/Structuring_content/Debugging_HTML
# https://doclib.siemens-healthineers.com/rest/v1/view?document-id=841490
_TECHNICAL_VERB_FORMS = frozenset(
    {
        "recompila",
        "serializa",
        "recalculando",
        "recalcules",
        "reclasifica",
        "reclasificas",
        "renderice",
        "renderizó",
        "reescanea",
        # https://learn.microsoft.com/es-es/azure/virtual-network/virtual-network-optimize-network-bandwidth
        "reconectando",
        # https://dle.rae.es/sobreestimar
        "sobreestima",
    }
)


def is_reviewed_spanish_form(word: str) -> bool:
    """Recognize finite native forms while retaining stress and case checks."""
    word = word[:1].lower() + word[1:]
    return (
        is_reviewed_spanish_enclitic(word)
        or any(word == stem + ending for stem in _AGREEMENT_STEMS for ending in ("o", "a", "os", "as"))
        or any(word in (stem, stem + ending) for stem, ending in _NUMBER_ENDINGS.items())
        or word in _INFINITIVES
        or word in _TECHNICAL_VERB_FORMS
        or word == "atómicamente"
    )
