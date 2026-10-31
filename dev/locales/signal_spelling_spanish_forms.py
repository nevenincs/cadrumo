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
        "reinténta",
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
        "rastrear",
        "recargar",
        "reconciliar",
        "reejecutar",
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
_AGREEMENT_STEMS = frozenset({"tipad", "intracomunitari", "desactualizad", "malformad", "contrafirmad", "atómic"})
_NUMBER_ENDINGS = {
    "subcomando": "s",
    "reanudable": "s",
    "auditable": "s",
    "contrafirmante": "s",
    "exigibilidad": "es",
    "sobrescritura": "s",
}
_INFINITIVES = frozenset({"previsualizar", "contrafirmar"})


def is_reviewed_spanish_form(word: str) -> bool:
    """Recognize finite native forms while retaining stress and case checks."""
    word = word[:1].lower() + word[1:]
    return (
        is_reviewed_spanish_enclitic(word)
        or any(word == stem + ending for stem in _AGREEMENT_STEMS for ending in ("o", "a", "os", "as"))
        or any(word in (stem, stem + ending) for stem, ending in _NUMBER_ENDINGS.items())
        or word in _INFINITIVES
        or word == "atómicamente"
    )
