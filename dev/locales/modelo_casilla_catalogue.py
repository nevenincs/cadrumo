"""Delta-keyed maintenance of the Modelo casilla locale surface.

The registry stores Modelo editions as deltas: an edition states only the rows
that changed, and inherited rows resolve their text through the key chain the
loader enrols on every casilla -- the row's own occurrence key, the key of the
edition that stated it, then its lineage (``continuidad_id``) key. The casilla
locale catalogue follows the same discipline:

- a value is stored once, at the least specific key of the chains that read it
  that still yields the same resolved text in every locale;
- a key no chain reads, a null leaf, and a value whose removal changes no
  resolution are all delete targets;
- help text generated from the label carries nothing of its own and is removed;
- a translation is authored only for Spanish text that has none; Spanish text
  already translated elsewhere in the same lineage is carried, not retyped.

Everything here reads the published authority and the runtime resolution rule
(:func:`~cadrumo.domain.calculations.registry.modelo_localization.modelo_localization_source`)
through the ``cadrumo`` package only, so the check measures exactly what
operators are served. Writes go through :class:`~dev.locales.manager.LocaleManager`.
"""

from __future__ import annotations

import re
import shutil
import time
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import yaml

from cadrumo.core.atomic_write import atomic_write_text
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.modelo_localization import (
    encode_modelo_locale_segment,
    modelo_localization_source,
)

from ._casilla_keys import is_delta_keyed_leaf, is_lineage_key
from ._paths import LOCALES_DIR, PENDING_CASILLA_INSTALL_DIR
from .manager import LocaleManager, _flatten_raw_locale_leaves, discover_locale_codes

__all__ = [
    "SOURCE_TRUNCATED_SPANISH",
    "CasillaOccurrence",
    "CatalogueFindings",
    "CollapsePlan",
    "CollapseResult",
    "CollapseVerificationError",
    "ModeloCasillaCatalogue",
    "casilla_occurrences",
    "edition_text_gaps",
    "load_casilla_values",
    "repeated_edition_text",
    "resume_install",
]

SOURCE_LOCALE: Final = "es"
_FIELDS: Final = ("label", "help")
#: Help renderings generated from the label; they state nothing the label does not.
_DERIVED_HELP: Final = (
    re.compile(r"^Indique o revise «.*» para completar esta autoliquidación\.$", re.S),
    re.compile(r"^Consulte la información correspondiente a la casilla: .*$", re.S),
    re.compile(r"^Información fiscal sobre .*de la casilla .*$", re.S),
    re.compile(r"^Información de la casilla\b.*$", re.S),
    re.compile(r"^Dato del modelo \S+, ejercicio \S+.*$", re.S),
)
_REVISION_SCOPED: Final = re.compile(r"^modelo\.schema\.(?P<modelo>[^.]+)\.revision\.(?P<revision>[^.]+)\.")
#: Scaffold renderings standing in for a label that was never authored. Help text may
#: legitimately open with its box number, so only labels are judged.
_PLACEHOLDER: Final = re.compile(
    r"^(?:Casilla|Casella|Box)\s+\S+:\s|^Casella . informaci"
    r"|^(?:Casilla|Casella|Box)\b[^—]{0,40}—|^[^—]{0,40}\brovat\s+—"
    r"|^(?:Informació fiscal de la casella|Tax information for this field|Az űrlap adóadata)\.?$",
    re.IGNORECASE,
)

#: A value that a length limit cut mid-text and closed with an ellipsis.
_TRUNCATED: Final = re.compile(r"\S\s?(?:\.\.\.|…)\s*$")
#: "N por 100" and "N por ciento" state the rate "N%"; the words carry no content.
_PERCENT_WORDS: Final = re.compile(r"\s*por\s*(?:100|ciento)(?![0-9])", re.IGNORECASE)
#: An ordinal a translation spells out states the same number as the Spanish digit.
_SPELLED_NUMBERS: Final[dict[str, int]] = {
    # English
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    # Catalan
    "primera": 1,
    "primer": 1,
    "segona": 2,
    "segon": 2,
    "tercera": 3,
    "tercer": 3,
    "quarta": 4,
    "quart": 4,
    "cinquena": 5,
    "cinquè": 5,
    "sisena": 6,
    "sisè": 6,
    "setena": 7,
    "setè": 7,
    "vuitena": 8,
    "vuitè": 8,
    "novena": 9,
    "novè": 9,
    "desena": 10,
    "desè": 10,
    # Hungarian
    "első": 1,
    "második": 2,
    "harmadik": 3,
    "negyedik": 4,
    "ötödik": 5,
    "hatodik": 6,
    "hetedik": 7,
    "nyolcadik": 8,
    "kilencedik": 9,
    "tizedik": 10,
    # Cardinals a translation writes as words for a count the Spanish gives as a digit.
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "un": 1,
    "dos": 2,
    "tres": 3,
    "quatre": 4,
    "cinc": 5,
    "sis": 6,
    "set": 7,
    "vuit": 8,
    "nou": 9,
    "deu": 10,
    "egy": 1,
    "kettő": 2,
    "két": 2,
    "három": 3,
    "négy": 4,
    "öt": 5,
    "hat": 6,
    "hét": 7,
    "nyolc": 8,
    "kilenc": 9,
    "tíz": 10,
}
_WORD_TOKEN: Final = re.compile(r"[^\W\d_]+")
#: ">=" and "<=" write the comparison the Spanish sets with the symbol itself.
_ASCII_COMPARISON: Final[dict[str, str]] = {">=": "≥", "<=": "≤"}
#: A thousands separator is typography: 60.000, 60,000 and 60 000 state one amount.
_THOUSANDS: Final = re.compile(r"\b\d{1,3}(?:[.,\u00a0 ]\d{3})+\b")
#: The legal content a label states: box references, amounts and comparison symbols.
_CONTENT_TOKEN: Final = re.compile(r"\[[0-9][^\]]{0,11}\]|\d+|[≤≥]")
#: Repeated spaces, or whitespace opening or closing a value; line breaks are authored.
_IRREGULAR_WHITESPACE: Final = re.compile(r"[ \t]{2,}|^\s|\s$")
#: The words an official label loses when AEAT shortens it, which carry no legal meaning.
_SPANISH_FUNCTION_WORDS: Final[frozenset[str]] = frozenset(
    [
        "a",
        "al",
        "con",
        "de",
        "del",
        "el",
        "en",
        "la",
        "las",
        "los",
        "para",
        "por",
        "que",
        "se",
        "su",
        "sus",
        "un",
        "una",
        "y",
    ]
)
#: The separators AEAT composes a long label from: heading, regime, year, state of the amount.
#: A dash also subtracts one box from another, which :func:`_segments` keeps whole, and a full
#: stop also abbreviates a word, so a sentence break is read only between a word and a capital.
_SEGMENT: Final = re.compile(r"\s+-\s+|(?<=[^\W\dA-Z_])\.\s+(?=[A-ZÁÀÂÄÉÈÊËÍÏÎÓÒÔÖŐÚÙÛÜŰÑÇ])")
#: What tells a composed segment from an operand: a segment states words, an operand a box.
_SEGMENT_PROSE: Final = re.compile(r"[^\W\d_]{3,}")
#: Spanish texts whose official record design is itself cut short with an ellipsis;
#: the catalogue mirrors the source, and a translation of them may end the same way.
SOURCE_TRUNCATED_SPANISH: Final[frozenset[str]] = frozenset(
    {
        # Modelo 714 design, box [35].
        "Liquidación - Límite cuota íntegra - Parte cuotas íntegras IRPF, saldo positivo ganancias y pérdidas "
        "patrimoniales...",
        # Modelo 100 box [1908]: the design names a different annex in each edition
        # (B.8, B.9, B.11), so the completed text would differ between editions that
        # share this key. The registry refuses that divergence until a casilla
        # continuity evolution declares it, so the shared text stays cut short.
        "Por inversión en adquisición de acciones y participaciones sociales como consecuencia de acuerdos de "
        "constitución de sociedades o ampliación de capital en las sociedades mercantiles (importe de la ...",
    }
)
#: Per locale, the marks a word-by-word glossary pass leaves: Hungarian suffix
#: alternations standing alone, and Spanish function words left untranslated.
_GLOSSARY_ARTIFACT: Final[dict[str, re.Pattern[str]]] = {
    "hu": re.compile(
        r"-(?:ban/-ben|nak/-nek|ra/-re|ról/-ről|ba/-be|val/-vel|tól/-től|hoz/-hez|ból/-ből|ként)\b"
        r"|\ba\(z\) [a-záéíóöőúüű]+ -|\b(?:Aplicado|esta)\b"
    ),
    "en": re.compile(r"\b(?:Aplicado|esta|otros|otras|excepto|según|cuyo|cuya)\b"),
    "ca": re.compile(r"\b(?:Aplicado|esta|otros|otras|excepto|según|cuyo|cuya)\b"),
}


@dataclass(frozen=True, slots=True)
class CasillaOccurrence:
    """One casilla in one materialised edition, with its published key chain."""

    modelo: str
    revision: str
    casilla: str
    number: str
    continuidad_id: str | None
    inherited_from: str | None
    label_chain: tuple[str, ...]
    carries_help: bool = True
    """Casillas carry label and help; a construct carries only its title, read as its label."""

    def chain(self, field_name: str) -> tuple[str, ...]:
        """Return the ordered chain for ``label`` or ``help``."""
        if field_name == "label":
            return self.label_chain
        if not self.carries_help:
            return ()
        return tuple(f"{key.removesuffix('.label')}.help" for key in self.label_chain)


def casilla_occurrences() -> tuple[CasillaOccurrence, ...]:
    """Enumerate every casilla and construct occurrence of the published generation.

    A construct is carried as an occurrence whose label chain is its title chain,
    so both delta-keyed surfaces share one resolution, collapse and audit.
    """
    found: list[CasillaOccurrence] = []
    with bundled_indexed_authority().operation() as operation:
        for modelo_id in operation.modelo_ids():
            for metadata in operation.modelo_directory(modelo_id).revisions:
                revision = operation.revision(modelo_id, str(metadata.id))
                found.extend(
                    CasillaOccurrence(
                        modelo=str(modelo_id),
                        revision=str(metadata.id),
                        casilla=str(casilla.id),
                        number=str(casilla.number),
                        continuidad_id=None if casilla.continuidad_id is None else str(casilla.continuidad_id),
                        inherited_from=None if casilla.inherited_from is None else str(casilla.inherited_from),
                        label_chain=tuple(casilla.localization_keys),
                    )
                    for casilla in revision.casillas
                )
                found.extend(
                    CasillaOccurrence(
                        modelo=str(modelo_id),
                        revision=str(metadata.id),
                        casilla=f"construct:{construct.id}",
                        number="",
                        continuidad_id=None,
                        inherited_from=None,
                        label_chain=tuple(construct.localization_keys),
                        carries_help=False,
                    )
                    for construct in revision.constructs
                )
    return tuple(found)


type Values = dict[str, dict[str, str | None]]
"""``values[locale][key]`` for every casilla leaf present in a catalogue."""


def load_casilla_values(locales_dir: Path = LOCALES_DIR) -> Values:
    """Read every casilla leaf of every locale's Modelo schema shards."""
    values: Values = {}
    for locale in sorted(discover_locale_codes(locales_dir)):
        leaves: dict[str, str | None] = {}
        for shard in sorted((locales_dir / locale / "modelo" / "schema").glob("*.yml")):
            raw = yaml.safe_load(shard.read_text(encoding="utf-8")) or {}
            for key, value in _flatten_raw_locale_leaves(raw).items():
                if is_delta_keyed_leaf(key):
                    leaves[key] = None if value is None else str(value)
        values[locale] = leaves
    return values


_EDITION_TEXT: Final = re.compile(r"^modelo\.schema\.(?P<modelo>[^.]+)\.revision\.[^.]+\.field\.label$")
#: Scaffold renderings standing in for revision or construct text that was never authored.
_EDITION_TEXT_PLACEHOLDER: Final = re.compile(r"^(?:Casilla|Casella)\s*—|—\s*(?:tax|informaci|adóügyi)")


def edition_text_gaps(locales_dir: Path = LOCALES_DIR) -> dict[str, tuple[str, ...]]:
    """Return, per locale, revision labels that are null or a scaffold placeholder.

    A revision label is edition-specific text with no inheritance chain, so every
    declared revision needs its own authored value in every locale. Construct
    titles are delta-keyed and judged through resolution with casilla labels.
    """
    gaps: dict[str, tuple[str, ...]] = {}
    for locale, labels in _edition_labels(locales_dir).items():
        gaps[locale] = tuple(
            sorted(
                key
                for key, value in labels.items()
                if value is None or _EDITION_TEXT_PLACEHOLDER.search(value) is not None
            )
        )
    return gaps


def repeated_edition_text(locales_dir: Path = LOCALES_DIR) -> dict[str, tuple[str, ...]]:
    """Return, per locale, revision labels one modelo repeats across editions.

    A revision label names its own edition, so two editions of a modelo cannot
    carry the same label: the repeated text describes the period of one of them
    and misdescribes the others. Unlike a casilla label, it inherits nothing, so
    the repetition is a copy to re-author rather than a collapse target.
    """
    repeated: dict[str, tuple[str, ...]] = {}
    for locale, labels in _edition_labels(locales_dir).items():
        by_text: dict[tuple[str, str], list[str]] = defaultdict(list)
        for key, value in labels.items():
            match = _EDITION_TEXT.match(key)
            if value is not None and match is not None:
                by_text[(match.group("modelo"), value)].append(key)
        repeated[locale] = tuple(sorted(key for keys in by_text.values() if len(keys) > 1 for key in keys))
    return repeated


def _edition_labels(locales_dir: Path) -> dict[str, dict[str, str | None]]:
    """Return, per locale, every revision-label leaf of the Modelo schema shards."""
    labels: dict[str, dict[str, str | None]] = {}
    for locale in sorted(discover_locale_codes(locales_dir)):
        found: dict[str, str | None] = {}
        for shard in sorted((locales_dir / locale / "modelo" / "schema").glob("*.yml")):
            raw = yaml.safe_load(shard.read_text(encoding="utf-8")) or {}
            for key, value in _flatten_raw_locale_leaves(raw).items():
                if _EDITION_TEXT.match(key):
                    found[key] = None if value is None else str(value)
        labels[locale] = found
    return labels


#: Per (locale, modelo, translation), Spanish wordings a reviewer found equivalent, so one
#: translation is correct for all of them: an abbreviation, a typo, punctuation or a synonym.
#: Never widened by modelo or prefix; each entry names the difference the reviewer saw.
#: Per locale, composed segments a reviewer found to need more than one rendering, with the
#: reason the context forces it. Each entry names one segment; never a modelo or a prefix.
#: Per locale, renderings a reviewer found to state two Spanish segments correctly, with the
#: difference seen: an official typo, an abbreviation, or two spellings of one province.
REVIEWED_SHARED_SEGMENTS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "Acquirer": ("Adquirente and the official misspelling Adquiriente"),
        "Address": ("Domicilio, and the bilingual Domicilio / Address of the same box"),
        "Adjustments for the tax year": ("Correcciones and the official misspelling Correciones"),
        (
            "Amortization of intangible fixed assets and goodwill (art. 12.2 LIS) and amortization "
            "under Transitional Provision 13.1 LIS"
        ): ("one edition cites the transitional provision as art. DT 13a.1, the other as DT 13a.1"),
        (
            "Amount excluded for capital or equity increases by set-off of claims not integrated into "
            "the tax base (art. 17.2 LIS)"
        ): ("no integrado en la base imponible, restated as que no se integren por aplicacion del art. 17.2"),
        "Amount payable": ("A ingresar states what the box holds and Importe a ingresar names its amount, for one box"),
        "Bizkaia": ("the Basque and Castilian spellings of one province"),
        "Chartered provincial councils and Navarre": ("D. Forales abbreviates Diputaciones Forales"),
        "Country code": ("Codigo de pais, abbreviated in one edition and given with its English gloss in another"),
        "Credit of R&D&I deductions due to insufficient tax liability": (
            "insuf. cuota abbreviates por insuficiencia de cuota"
        ),
        "Decreases": ("Disminuciones and the official misspellings Diminuciones and Disminuciones with a stray accent"),
        "Deductible VAT on intra-Community acquisitions of current goods": (
            "adquisiciones intracomunitarias corrientes abbreviates the same box"
        ),
        "Deduction still outstanding": (
            "pendiente de aplicacion and pendiente de aplicar state one thing, a deduction not yet taken"
        ),
        "Gipuzkoa": ("the Basque and Castilian spellings of one province"),
        "Income and expenses recognized in equity": (
            "imputados al patrimonio neto, restated as reconocidos en patrimonio neto"
        ),
        "Legal name": ("razon social and denominacion social name one thing, the registered name of a company"),
        (
            "Part integrated into the tax base at liability level for debt-relief or deferral "
            "arrangements (cooperatives only)"
        ): ("op. abbreviates operaciones"),
        "Postcode": ("C. Postal abbreviates Codigo postal, which one edition also capitalises"),
        "Postcode (ZIP)": ("C. Postal abbreviates Codigo postal, whose ZIP note one edition brackets"),
        "Province, region or state": (
            "the same wording, its parts separated by slashes in one edition and by words in the other"
        ),
        "Reduction of income from certain intangible assets (art. 23 LIS)": (
            "ingresos, restated as rentas for the same art. 23 LIS reduction"
        ),
        "Result of the previous return (supplementary)": ("complementaria and the official plural complementarias"),
        "Street name": ("Nombre de la via, written out as via publica and capitalised in other editions"),
        "Surnames and first name or company name": (
            "razon social and denominacion social name one thing, the registered name of a company"
        ),
        "Surnames or company name": (
            "Denominacion Social and Razon social, with the official o accented in one edition"
        ),
        "Taxation by territory": ("por razon de territorio, shortened to por territorio"),
    },
    "ca": {
        "1r fraccionament": ("1er and 1o spell the same first instalment"),
        "Adquirent": ("Adquirente and the official misspelling Adquiriente"),
        "Altres 1a": ("1a and the ordinal 1a written with a superscript"),
        "Altres 2a": ("2a and the ordinal 2a written with a superscript"),
        "Altres 3a": ("3a and the ordinal 3a written with a superscript"),
        "Altres 4a": ("4a and the ordinal 4a written with a superscript"),
        "Altres 5a": ("5a and the ordinal 5a written with a superscript"),
        "Altres diferències d'imputació temporal d'ingressos i despeses (art. 11 LIS)": (
            "imputac. abbreviates imputacion"
        ),
        "Codi de país": ("Codigo de pais, abbreviated in one edition and given with its English gloss in another"),
        "Correccions de l'exercici": ("Correcciones and the official misspelling Correciones"),
        "Correu electrònic": ("E-mail and Email spell one word"),
        "Diputacions Forals i Navarra": ("D. Forales abbreviates Diputaciones Forales"),
        "Disminucions": (
            "Disminuciones and the official misspellings Diminuciones and Disminuciones with a stray accent"
        ),
        "Domicili": ("Domicilio, and the bilingual Domicilio / Address of the same box"),
        "IVA deduïble en operacions interiors de béns d'inversió": ("ops abbreviates operaciones"),
        (
            "Import exclòs per operacions d'augment de capital o fons propis per compensació de crèdits "
            "no integrat en la base imposable (art. 17.2 LIS)"
        ): ("no integrado en la base imponible, restated as que no se integren por aplicacion del art. 17.2"),
        (
            "Part integrada en la base imposable a nivell de quota per operacions de quitament o espera "
            "(només cooperatives)"
        ): ("op. abbreviates operaciones"),
    },
    "hu": {
        "1. részletfizetés": ("1er fraccionamiento and 1er. pago fraccionado name the same first instalment"),
        "A korábbi bevallás eredménye (kiegészítő)": ("complementaria and the official plural complementarias"),
        "Adóalap": ("Base is the column heading for the Base imponible the row states"),
        "Az adóalapba adóösszeg szintjén beszámított rész adósságelengedési ügyletek után (csak szövetkezetek)": (
            "op. abbreviates operaciones"
        ),
        "Bizkaia": ("the Basque and Castilian spellings of one province"),
        "Csökkentett adóalap": (
            "base liquidable is the base imponible after its reductions, which the other names directly"
        ),
        "Csökkenések": (
            "Disminuciones and the official misspellings Diminuciones and Disminuciones with a stray accent"
        ),
        "Cégnév": ("razon social and denominacion social name one thing, the registered name of a company"),
        "Cím": ("Domicilio, and the bilingual Domicilio / Address of the same box"),
        "E-mail": ("E-mail and Email spell one word"),
        "E-mail cím": ("Correo electronico, given as Direccion de correo electronico in another edition"),
        "Egyéb 1.": ("1a and the ordinal 1a written with a superscript"),
        "Egyéb 2.": ("2a and the ordinal 2a written with a superscript"),
        "Egyéb 3.": ("3a and the ordinal 3a written with a superscript"),
        "Egyéb 4.": ("4a and the ordinal 4a written with a superscript"),
        "Egyéb 5.": ("5a and the ordinal 5a written with a superscript"),
        "Fizetendő összeg": (
            "A ingresar states what the box holds and Importe a ingresar names its amount, for one box"
        ),
        "Gipuzkoa": ("the Basque and Castilian spellings of one province"),
        "Helység": ("Localidad, written Localidad/Poblacion in another edition"),
        "Irányítószám": ("C. Postal abbreviates Codigo postal, which one edition also capitalises"),
        "Irányítószám (ZIP)": ("C. Postal abbreviates Codigo postal, whose ZIP note one edition brackets"),
        "K+F+i levonások jóváírása elégtelen adókötelezettség miatt": (
            "insuf. cuota abbreviates por insuficiencia de cuota"
        ),
        (
            "Követelés-beszámítással történő tőke- vagy sajáttőke-emelés miatt kizárt, az adóalapba be "
            "nem számított összeg (LIS 17.2. cikk)"
        ): ("no integrado en la base imponible, restated as que no se integren por aplicacion del art. 17.2"),
        "Közterület neve": ("Nombre de la via, written out as via publica and capitalised in other editions"),
        "Külföldi cím": ("Direccion en el extranjero and Domicilio extranjero name one address"),
        "Külön jogállású tartományi tanácsok és Navarra": ("D. Forales abbreviates Diputaciones Forales"),
        "Még érvényesíthető levonás": (
            "pendiente de aplicacion and pendiente de aplicar state one thing, a deduction not yet taken"
        ),
        "Országkód": ("Codigo de pais, abbreviated in one edition and given with its English gloss in another"),
        "Saját tőkében elszámolt bevételek és ráfordítások": (
            "imputados al patrimonio neto, restated as reconocidos en patrimonio neto"
        ),
        "Tartomány, régió vagy állam": (
            "the same wording, its parts separated by slashes in one edition and by words in the other"
        ),
        "Vezetéknév vagy cégnév": ("Denominacion Social and Razon social, with the official o accented in one edition"),
        "Vezetéknév és utónév vagy cégnév": (
            "razon social and denominacion social name one thing, the registered name of a company"
        ),
        "Évi korrekciók": ("Correcciones and the official misspelling Correciones"),
    },
}


REVIEWED_SEGMENT_RENDERINGS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "Cuota": "the amount of the IVA, of the recargo or of a fee, named by the label it sits in",
    },
    "ca": {
        "NIF": "the acronym as a field tag, and the number named in full where the label stands alone",
    },
}


REVIEWED_SHARED_TRANSLATIONS: Final[dict[tuple[str, str, str], str]] = {
    (
        "ca",
        "100",
        "IVA suportat (per exemple, recàrrec d'equivalència i/o compensació d'agricultura, ramaderia i pesca)",
    ): "one edition misspells por ejemplo as por ejermplo",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlete miatt (ezt az összeget vigye át a B.6. melléklet [1130] rovatába)",
    ): "alquiler, arrendamiento and el arrendamiento de la vivienda habitual name one letting",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlete miatt (ezt az összeget vigye át a B.8. melléklet [1130] rovatába)",
    ): "alquiler, arrendamiento and el arrendamiento de la vivienda habitual name one letting",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlete miatt, 36 évesnél fiatalabb adózók számára (ezt az "
        "összeget vigye át a B.6. melléklet [1130] rovatába)",
    ): "alquiler, arrendamiento and el arrendamiento de la vivienda habitual name one letting",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlete miatt, 36 évesnél fiatalabb adózók számára (ezt az "
        "összeget vigye át a B.8. melléklet [1130] rovatába)",
    ): "alquiler, arrendamiento and el arrendamiento de la vivienda habitual name one letting",
    (
        "hu",
        "100",
        "Új vagy nemrég alakult jogalanyok részvényeinek vagy üzletrészeinek megszerzésébe "
        "történő befektetés miatt (ezt az összeget vigye át a B.7. melléklet [1136] rovatába)",
    ): "acciones o participaciones sociales, written with y in another edition",
    (
        "hu",
        "100",
        "Új vagy nemrég alakult jogalanyok részvényeinek vagy üzletrészeinek megszerzésébe "
        "történő befektetés miatt (ezt az összeget vigye át a B.8. melléklet [1136] rovatába)",
    ): "acciones o participaciones sociales, written with y in another edition",
    (
        "en",
        "100",
        "For illness expenses",
    ): "number (gasto / gastos)",
    (
        "en",
        "100",
        "Amount applied in the tax year",
    ): "synonym (aplicado / que se aplica)",
    (
        "hu",
        "100",
        "Gyermek születése vagy örökbefogadása után",
    ): "number (un hijo / hijos)",
    (
        "en",
        "100",
        "Cadastral reference (property 1)",
    ): "punctuation/synonym (inmueble / vivienda, missing space before the parenthesis)",
    (
        "ca",
        "100",
        "Fill/Filla 1 (*): NIF/NIE",
    ): "synonym (word order variant of the same field)",
    (
        "ca",
        "100",
        "Fill/Filla 2 (*): NIF/NIE",
    ): "synonym (word order variant of the same field)",
    (
        "ca",
        "100",
        (
            "Per arrendament d'habitatge habitual per contribuents menors de 36 anys (import de la "
            "casella [1130] de l'annex B.9)"
        ),
    ): "punctuation (preposition de / en)",
    (
        "ca",
        "100",
        "Per obligació de presentar la declaració de l'IRPF per raó de tenir més d'un pagador",
    ): "synonym (en razon de / por razon de)",
    (
        "ca",
        "100",
        "Referència cadastral 1",
    ): "typo (castastral / catastral)",
    (
        "ca",
        "100",
        "Referència cadastral 2",
    ): "typo (castastral / catastral)",
    (
        "ca",
        "100",
        "Referència cadastral 3",
    ): "typo (castastral / catastral)",
    (
        "ca",
        "100",
        "Referència cadastral 4",
    ): "typo (castastral / catastral)",
    (
        "ca",
        "202",
        (
            "Informació addicional (5) - Import de renda exempta de les entitats que apliquen el règim "
            "fiscal especial del Cap. XIV del Tít. VII LIS"
        ),
    ): "punctuation/typo (de/del, Tit./Tit.)",
    (
        "ca",
        "202",
        (
            "Informació addicional (5) - Import exclòs per operacions d'augment de capital o fons "
            "propis per compensació de crèdits no integrat en la base imposable (art. 17.2 LIS)"
        ),
    ): "synonym (rewording, same concept)",
    (
        "ca",
        "202",
        (
            "Informació addicional (5) - Part integrada en la base imposable a nivell de quota per "
            "operacions de quitament o espera (només cooperatives)"
        ),
    ): "abbreviation (op. / operaciones)",
    (
        "ca",
        "322",
        "Codi d'activitat - Altres 1a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Codi d'activitat - Altres 2a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Codi d'activitat - Altres 3a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Codi d'activitat - Altres 4a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Codi d'activitat - Altres 5a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Epígraf IAE - Altres 1a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Epígraf IAE - Altres 2a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Epígraf IAE - Altres 3a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Epígraf IAE - Altres 4a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "ca",
        "322",
        "Epígraf IAE - Altres 5a",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "en",
        "100",
        "Cadastral reference 1",
    ): "typo (castastral / catastral)",
    (
        "en",
        "100",
        "Cadastral reference 2",
    ): "typo (castastral / catastral)",
    (
        "en",
        "100",
        "Cadastral reference 3",
    ): "typo (castastral / catastral)",
    (
        "en",
        "100",
        "Cadastral reference 4",
    ): "typo (castastral / catastral)",
    (
        "en",
        "100",
        "For a large family",
    ): "synonym (por / para)",
    (
        "en",
        "100",
        "For donations for ecological purposes",
    ): "synonym (donaciones / donativos)",
    (
        "en",
        "100",
        "For education expenses",
    ): "synonym (gastos educativos / gastos de educacion)",
    (
        "en",
        "100",
        (
            "For investment in shares of entities listed on the growth-companies segment of the "
            "Alternative Stock Market (amount from box [1142] of Annex B.11)"
        ),
    ): "synonym (Bursatil / Bolsista)",
    (
        "en",
        "100",
        (
            "For investment in the acquisition of shares or company units of newly or recently created "
            "entities (amount from box [1136] of Annex B.11)"
        ),
    ): "punctuation/typo (o/y conjunction, stray parenthesis, capitalization)",
    (
        "en",
        "100",
        "For rental of the habitual residence (amount from box [1130] of annex B.9)",
    ): "synonym (arrendamiento / alquiler)",
    (
        "en",
        "100",
        "For rental of the habitual residence (this amount is transferred to box [1130] of annex B.9)",
    ): "synonym (arrendamiento / alquiler, article variant)",
    (
        "en",
        "100",
        ("For rental of the habitual residence for taxpayers under 36 years old (amount from box [1130] of annex B.9)"),
    ): "punctuation (preposition de / en)",
    (
        "en",
        "100",
        "For single-parent families",
    ): "synonym (por / para)",
    (
        "en",
        "100",
        "For taxpayers with a disability",
    ): "synonym (con discapacidad / afectados por discapacidad)",
    (
        "en",
        "100",
        "For the international adoption of children",
    ): "synonym (rewording, same concept)",
    (
        "en",
        "100",
        "For the lease of a primary residence (this amount is carried to box [1130] of Annex B.11)",
    ): "punctuation (added article el)",
    (
        "en",
        "100",
        (
            "For the lease of a primary residence for taxpayers under 36 years old (amount from box "
            "[1130] of Annex B.11)"
        ),
    ): "punctuation (preposition de / en)",
    (
        "en",
        "100",
        (
            "For the lease of a primary residence linked to certain debt-for-property settlement "
            "transactions (amount from box [1170] of Annex B.12)"
        ),
    ): "punctuation (added article el)",
    (
        "en",
        "100",
        "For the purchase of school supplies",
    ): "synonym (compra / adquisicion)",
    (
        "en",
        "100",
        "For the purchase of textbooks and school supplies",
    ): "punctuation (added article la)",
    (
        "en",
        "100",
        'If you do not have a cadastral reference, mark this box with an "X"',
    ): "punctuation (quote style)",
    (
        "en",
        "100",
        "Number of days",
    ): "abbreviation (Numero / No)",
    (
        "en",
        "100",
        "Payments on account passed on",
    ): "abbreviation (Ing. / Ingr.)",
    (
        "en",
        "100",
        "Reduction for income from artistic activities obtained exceptionally",
    ): "typo (artisticas / artisticos)",
    (
        "en",
        "100",
        "Social Security contribution account code",
    ): "punctuation (missing de)",
    (
        "en",
        "100",
        "Tax ID (NIF) of entity 1, newly or recently created",
    ): "punctuation (missing de)",
    (
        "en",
        "100",
        "Tax ID (NIF) of entity 2, newly or recently created",
    ): "punctuation (missing de)",
    (
        "en",
        "100",
        "Tax ID number (NIF) of the person with the disability holding the protected estate",
    ): "abbreviation (Numero / No)",
    (
        "en",
        "100",
        "Utilities (electricity, water, gas, telephone and internet)",
    ): "synonym (luz / electricidad)",
    (
        "en",
        "202",
        (
            "Additional information (5) - Amount excluded for capital or equity increases by set-off of"
            " claims not integrated into the tax base (art. 17.2 LIS)"
        ),
    ): "synonym (rewording, same concept)",
    (
        "en",
        "202",
        (
            "Additional information (5) - Amount of exempt income of entities applying the special tax "
            "regime of Chapter XIV of Title VII LIS"
        ),
    ): "punctuation/typo (de/del, Tit./Tit.)",
    (
        "en",
        "202",
        (
            "Additional information (5) - Part integrated into the tax base at liability level for "
            "debt-relief or deferral arrangements (cooperatives only)"
        ),
    ): "abbreviation (op. / operaciones)",
    (
        "en",
        "303",
        "Total accrued VAT amount",
    ): "synonym (short label vs. detailed elaboration of the same total)",
    (
        "hu",
        "100",
        "1. Kataszteri hivatkozás",
    ): "typo (castastral / catastral)",
    (
        "hu",
        "100",
        "1. Új vagy nemrég alapított entitás adóazonosító száma",
    ): "punctuation (missing de)",
    (
        "hu",
        "100",
        "2. Kataszteri hivatkozás",
    ): "typo (castastral / catastral)",
    (
        "hu",
        "100",
        "2. Új vagy nemrég alapított entitás adóazonosító száma",
    ): "punctuation (missing de)",
    (
        "hu",
        "100",
        "3. Kataszteri hivatkozás",
    ): "typo (castastral / catastral)",
    (
        "hu",
        "100",
        "36 év alatti adózók szokásos lakóhelyének bérlése után (a B.9 melléklet [1130] rovatának összege)",
    ): "punctuation (preposition de / en)",
    (
        "hu",
        "100",
        "4. kataszteri hivatkozás",
    ): "typo (castastral / catastral)",
    (
        "hu",
        "100",
        (
            "A 2021. adóévre vonatkozó korábbi önadózásokból vagy közigazgatási adómegállapításokból "
            "származó, befizetendő eredmények"
        ),
    ): "punctuation (added article las)",
    (
        "hu",
        "100",
        (
            "A 2022. adóévre vonatkozó korábbi önadózásokból vagy közigazgatási adómegállapításokból "
            "származó, befizetendő eredmények"
        ),
    ): "punctuation (added article las)",
    (
        "hu",
        "100",
        (
            "A 2023. adóévre vonatkozó korábbi önadózásokból vagy közigazgatási adómegállapításokból "
            "származó, befizetendő eredmények"
        ),
    ): "punctuation (added article las)",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlete miatt (ezt az összeget vigye át a B.6. melléklet [1130] casillájába)",
    ): "synonym (arrendamiento / alquiler, article variant)",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlete miatt (ezt az összeget vigye át a B.8. melléklet [1130] casillájába)",
    ): "synonym (arrendamiento / alquiler, article variant)",
    (
        "hu",
        "100",
        (
            "A szokásos lakóhely bérlete miatt, 36 évesnél fiatalabb adózók számára (ezt az összeget "
            "vigye át a B.6. melléklet [1130] casillájába)"
        ),
    ): "synonym (arrendamiento / alquiler)",
    (
        "hu",
        "100",
        (
            "A szokásos lakóhely bérlete miatt, 36 évesnél fiatalabb adózók számára (ezt az összeget "
            "vigye át a B.8. melléklet [1130] casillájába)"
        ),
    ): "synonym (arrendamiento / alquiler)",
    (
        "hu",
        "100",
        "A szokásos lakóhely bérlése után (ez az összeg a B.9 melléklet [1130] rovatába kerül át)",
    ): "synonym (arrendamiento / alquiler, article variant)",
    (
        "hu",
        "100",
        ("A szokásos lakóingatlan bérbevétele után (ez az összeg átvitelre kerül a B.11 melléklet [1130] rovatába)"),
    ): "synonym (arrendamiento / alquiler, article variant)",
    (
        "hu",
        "100",
        (
            "Az Alternatív Tőzsde terjeszkedő vállalkozási szegmensében jegyzett entitások részvényeibe"
            " történő befektetés után (a B.11 melléklet [1142] rovatának összege)"
        ),
    ): "synonym (Bursatil / Bolsista)",
    (
        "hu",
        "100",
        "Az adóévben alkalmazott összeg",
    ): "synonym (grammar/voice variant, same meaning)",
    (
        "hu",
        "100",
        "Csökkentés kivételes módon szerzett művészi tevékenységekből származó jövedelmek után",
    ): "typo (artisticas / artisticos)",
    (
        "hu",
        "100",
        "Gyermekek nemzetközi örökbefogadása után",
    ): "synonym (rewording, same concept)",
    (
        "hu",
        "100",
        "Járulékfizetési számlakód",
    ): "punctuation (missing de)",
    (
        "hu",
        "100",
        "Napok száma",
    ): "abbreviation (Numero de dias / No de dias)",
    (
        "hu",
        "100",
        "Oktatási kiadások után",
    ): "synonym (gastos educativos / gastos de educacion)",
    (
        "hu",
        "100",
        "Szokásos lakóhely bérlése után (a B.9 melléklet [1130] rovatának összege)",
    ): "synonym (arrendamiento / alquiler)",
    (
        "hu",
        "100",
        "Szokásos lakóingatlan beszerzése vagy felújítása után vidéki övezetekben",
    ): "punctuation (added article la)",
    (
        "hu",
        "100",
        "Szokásos lakóingatlan bérbevétele után (a B.11 melléklet [1130] rovatának összege)",
    ): "synonym (arrendamiento / alquiler)",
    (
        "hu",
        "100",
        "Tankönyvek és iskolai felszerelés beszerzése után",
    ): "punctuation (added article la)",
    (
        "hu",
        "100",
        "Életjáradékokba történő újrabefektetés miatt mentesített nyereségek",
    ): "punctuation (preposition de / en)",
    (
        "hu",
        "100",
        "Ökológiai célú adományok után",
    ): "synonym (donaciones / donativos)",
    (
        "hu",
        "100",
        (
            "Új vagy nemrég alakult jogalanyok részvényeinek vagy üzletrészeinek megszerzésébe történő "
            "befektetés miatt (ezt az összeget vigye át a B.7. melléklet [1136] casillájába)"
        ),
    ): "punctuation/typo (o/y conjunction)",
    (
        "hu",
        "100",
        (
            "Új vagy nemrég alakult jogalanyok részvényeinek vagy üzletrészeinek megszerzésébe történő "
            "befektetés miatt (ezt az összeget vigye át a B.8. melléklet [1136] casillájába)"
        ),
    ): "punctuation/typo (o/y conjunction)",
    (
        "hu",
        "202",
        (
            "Kiegészítő információ (5) - A LIS VII. cím XIV. fejezete szerinti különös adórendszert "
            "alkalmazó szervezetek adómentes jövedelme"
        ),
    ): "punctuation/typo (de/del, Tit./Tit.)",
    (
        "hu",
        "202",
        (
            "Kiegészítő információ (5) - Az adóalapba adóösszeg szintjén beszámított rész "
            "adósságelengedési ügyletek után (csak szövetkezetek)"
        ),
    ): "abbreviation (op. / operaciones)",
    (
        "hu",
        "202",
        (
            "Kiegészítő információ (5) - Követelés-beszámítással történő tőke- vagy sajáttőke-emelés "
            "miatt kizárt, az adóalapba be nem számított összeg (LIS 17.2. cikk)"
        ),
    ): "synonym (rewording, same concept)",
    (
        "hu",
        "303",
        "Összes keletkezett ÁFA összeg",
    ): "synonym (short label vs. detailed elaboration of the same total)",
    (
        "hu",
        "322",
        "IAE besorolás - Egyéb 1.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "IAE besorolás - Egyéb 2.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "IAE besorolás - Egyéb 3.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "IAE besorolás - Egyéb 4.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "IAE besorolás - Egyéb 5.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "Tevékenységi kód - Egyéb 1.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "Tevékenységi kód - Egyéb 2.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "Tevékenységi kód - Egyéb 3.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "Tevékenységi kód - Egyéb 4.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
    (
        "hu",
        "322",
        "Tevékenységi kód - Egyéb 5.",
    ): "punctuation (ordinal ordinal-indicator vs plain a)",
}
#: Lineages whose Spanish wording changed between editions without changing meaning, so one
#: translation correctly renders every edition. Keyed per (locale, modelo, lineage), each with
#: the reviewer's reason; never widened by modelo or prefix.
REVIEWED_EQUIVALENT_SPANISH: Final[dict[tuple[str, str, str], str]] = {
    **{
        (locale, "202", lineage): "The later edition only spells out abbreviations ('op.', 'Tit.') of the same text."
        for locale in ("ca", "en", "hu")
        for lineage in (
            "importe-excluido-aumento-capital-art-17-2-lis",
            "importe-integrado-cuota-quita-espera-cooperativas",
            "renta-exenta-cap-xiv-tit-vii-lis",
        )
    },
    ("en", "100", "irpf-ed-suministros"): "'Electricity' renders both 'luz' and 'electricidad'.",
    ("ca", "100", "irpf-ed-iva-soportado"): "One edition misspells 'por ejemplo' as 'por ejermplo'.",
}


type Coordinate = tuple[int, str, str]
"""``(occurrence index, field, locale)``."""


@dataclass(slots=True)
class CatalogueFindings:
    """Measured state of the casilla surface; every tuple is sorted."""

    orphan_keys: dict[str, tuple[str, ...]] = field(default_factory=dict)
    undeclared_revision_keys: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, keys under a revision id the registry does not declare: a rename to move, never to delete."""
    null_leaves: dict[str, tuple[str, ...]] = field(default_factory=dict)
    redundant_values: dict[str, tuple[str, ...]] = field(default_factory=dict)
    lineage_lifts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, empty lineage keys that could carry text now stored per edition."""
    derived_help: dict[str, tuple[str, ...]] = field(default_factory=dict)
    placeholders: dict[str, tuple[str, ...]] = field(default_factory=dict)
    glossary_artifacts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, translations a word-by-word glossary pass produced."""
    truncated_text: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, values cut short and closed with an ellipsis."""
    irregular_whitespace: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, values with repeated spaces or surrounding whitespace copied from a source."""
    dropped_source_content: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, translations that lost a box reference, amount or comparison the Spanish states."""
    shared_translations: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, one translation rendering more than one Spanish wording of a modelo."""
    segment_drift: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, composed segments whose one Spanish wording is rendered more than one way."""
    shared_segments: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, one rendering standing for more than one Spanish segment."""
    unresolved_spanish: tuple[str, ...] = ()
    untranslated: dict[str, int] = field(default_factory=dict)
    translation_drift: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, lineages whose one Spanish text is translated more than one way."""
    stranded_translations: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, rows rendering Spanish although their lineage translates that text."""
    stale_translations: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, lineages rendering two different Spanish texts with one translation."""

    def counts(self) -> dict[str, object]:
        """Summarise every finding family as counts."""

        def total(family: Mapping[str, tuple[str, ...]]) -> dict[str, int]:
            return {locale: len(keys) for locale, keys in sorted(family.items()) if keys}

        return {
            "orphan_keys": total(self.orphan_keys),
            "undeclared_revision_keys": total(self.undeclared_revision_keys),
            "null_leaves": total(self.null_leaves),
            "redundant_values": total(self.redundant_values),
            "lineage_lifts": total(self.lineage_lifts),
            "derived_help": total(self.derived_help),
            "placeholders": total(self.placeholders),
            "glossary_artifacts": total(self.glossary_artifacts),
            "truncated_text": total(self.truncated_text),
            "irregular_whitespace": total(self.irregular_whitespace),
            "dropped_source_content": total(self.dropped_source_content),
            "shared_translations": total(self.shared_translations),
            "segment_drift": total(self.segment_drift),
            "shared_segments": total(self.shared_segments),
            "unresolved_spanish": len(self.unresolved_spanish),
            "untranslated": dict(sorted(self.untranslated.items())),
            "translation_drift": total(self.translation_drift),
            "stranded_translations": total(self.stranded_translations),
            "stale_translations": total(self.stale_translations),
        }

    @property
    def structurally_pure(self) -> bool:
        """Whether every stored leaf is a canonical, non-derived, readable value."""
        return not any(
            (
                any(self.orphan_keys.values()),
                any(self.undeclared_revision_keys.values()),
                any(self.null_leaves.values()),
                any(self.redundant_values.values()),
                any(self.lineage_lifts.values()),
                any(self.derived_help.values()),
            )
        )

    @property
    def pure(self) -> bool:
        """Whether the surface carries no delete target and no Spanish gap."""
        return not any(
            (
                any(self.orphan_keys.values()),
                any(self.undeclared_revision_keys.values()),
                any(self.null_leaves.values()),
                any(self.redundant_values.values()),
                any(self.lineage_lifts.values()),
                any(self.derived_help.values()),
                any(self.placeholders.values()),
                any(self.glossary_artifacts.values()),
                any(self.truncated_text.values()),
                any(self.irregular_whitespace.values()),
                any(self.dropped_source_content.values()),
                any(self.shared_translations.values()),
                any(self.segment_drift.values()),
                any(self.shared_segments.values()),
                any(self.translation_drift.values()),
                any(self.stranded_translations.values()),
                any(self.stale_translations.values()),
                self.unresolved_spanish,
            )
        )


@dataclass(slots=True)
class CollapsePlan:
    """Catalogue edits that keep every resolved text except the named repairs."""

    removals: dict[str, dict[str, str]] = field(default_factory=lambda: defaultdict(dict))
    """Per locale, each key to delete and why."""
    settings: dict[str, dict[str, tuple[str, str]]] = field(default_factory=lambda: defaultdict(dict))
    """Per locale, each key to write with its value and why."""
    _displaced: dict[str, dict[str, str]] = field(default_factory=lambda: defaultdict(dict))

    @property
    def reasons(self) -> Counter[str]:
        """Count the scheduled edits by kind and reason."""
        counts: Counter[str] = Counter()
        for removals in self.removals.values():
            counts.update(f"remove:{reason}" for reason in removals.values())
        for settings in self.settings.values():
            counts.update(f"set:{reason}" for _value, reason in settings.values())
        return counts

    def remove(self, locale: str, key: str, reason: str) -> None:
        """Schedule deletion of one leaf; dropping a value this plan assigned cancels the assignment."""
        if key in self.settings[locale]:
            del self.settings[locale][key]
            displaced = self._displaced[locale].pop(key, None)
            if displaced is not None:
                self.removals[locale][key] = displaced
            return
        self.removals[locale].setdefault(key, reason)

    def assign(self, locale: str, key: str, value: str, reason: str) -> None:
        """Schedule one leaf value, remembering any removal it replaces."""
        displaced = self.removals[locale].pop(key, None)
        if displaced is not None:
            self._displaced[locale][key] = displaced
        self.settings[locale][key] = (value, reason)


class ModeloCasillaCatalogue:
    """The casilla surface as the runtime resolves it, with delta-keyed edits."""

    def __init__(self, occurrences: tuple[CasillaOccurrence, ...], values: Values) -> None:
        """Index every key by the coordinates whose chains read it."""
        self.occurrences = occurrences
        self.values = values
        self.locales = tuple(sorted(values))
        self.dependents: dict[str, list[tuple[int, str]]] = defaultdict(list)
        self.declared_revisions = frozenset(
            (encode_modelo_locale_segment(occurrence.modelo), encode_modelo_locale_segment(occurrence.revision))
            for occurrence in occurrences
        )
        for index, occurrence in enumerate(occurrences):
            for field_name in _FIELDS:
                for key in occurrence.chain(field_name):
                    self.dependents[key].append((index, field_name))

    @classmethod
    def published(cls, locales_dir: Path = LOCALES_DIR) -> ModeloCasillaCatalogue:
        """Build the view from the published generation and the on-disk catalogue."""
        return cls(casilla_occurrences(), load_casilla_values(locales_dir))

    # -- resolution -------------------------------------------------------

    def lookup_for(self, values: Values) -> Callable[[str, str], str | None]:
        """Return a runtime-shaped lookup over ``values``."""

        def lookup(key: str, locale: str) -> str | None:
            return values.get(locale, {}).get(key)

        return lookup

    def resolve(self, index: int, field_name: str, locale: str, values: Values | None = None) -> str | None:
        """Resolve one coordinate with the runtime selection rule."""
        view = self.values if values is None else values
        chain = self.occurrences[index].chain(field_name)
        source = modelo_localization_source(chain, locale=locale, lookup=self.lookup_for(view))
        return None if source is None else view[source[1]][source[0]]

    def resolution(self, values: Values | None = None) -> dict[Coordinate, str | None]:
        """Resolve every coordinate."""
        return {
            (index, field_name, locale): self.resolve(index, field_name, locale, values)
            for index in range(len(self.occurrences))
            for field_name in _FIELDS
            for locale in self.locales
        }

    # -- findings ---------------------------------------------------------

    def findings(self) -> CatalogueFindings:
        """Measure every delete target and gap on the current catalogue."""
        found = CatalogueFindings()
        plan = self.collapse_plan(include_redundant=True)
        for locale in self.locales:
            leaves = self.values[locale]
            found.orphan_keys[locale] = tuple(
                sorted(key for key in leaves if key not in self.dependents and not self._undeclared_revision(key))
            )
            found.undeclared_revision_keys[locale] = tuple(
                sorted(key for key in leaves if self._undeclared_revision(key))
            )
            found.null_leaves[locale] = tuple(
                sorted(key for key, value in leaves.items() if value is None and key in self.dependents)
            )
            found.derived_help[locale] = tuple(
                sorted(key for key, value in leaves.items() if value is not None and _is_derived_help(key, value))
            )
            found.placeholders[locale] = tuple(
                sorted(
                    key
                    for key, value in leaves.items()
                    if value is not None
                    and (
                        (key.endswith(".label") and _PLACEHOLDER.search(value))
                        or (key.endswith(".title") and _EDITION_TEXT_PLACEHOLDER.search(value))
                    )
                )
            )
            artifact = _GLOSSARY_ARTIFACT.get(locale)
            found.glossary_artifacts[locale] = (
                ()
                if artifact is None
                else tuple(sorted(key for key, value in leaves.items() if value and artifact.search(value)))
            )
            sources = self.served_sources(locale) if locale != SOURCE_LOCALE else {}
            found.truncated_text[locale] = tuple(
                sorted(
                    key
                    for key, value in leaves.items()
                    if value
                    and _TRUNCATED.search(value)
                    and value not in SOURCE_TRUNCATED_SPANISH
                    and not (sources.get(key, frozenset()) & SOURCE_TRUNCATED_SPANISH)
                )
            )
            found.irregular_whitespace[locale] = tuple(
                sorted(key for key, value in leaves.items() if value and _IRREGULAR_WHITESPACE.search(value))
            )
            found.redundant_values[locale] = tuple(
                sorted(key for key, reason in plan.plan.removals.get(locale, {}).items() if reason == "redundant")
            )
            found.lineage_lifts[locale] = tuple(sorted(plan.plan.settings.get(locale, {})))
        found.unresolved_spanish = tuple(
            sorted(
                f"{occurrence.modelo}/{occurrence.revision}/{occurrence.casilla}"
                for index, occurrence in enumerate(self.occurrences)
                if self.resolve(index, "label", SOURCE_LOCALE) is None
            )
        )
        found.untranslated = {
            locale: sum(
                1
                for index in range(len(self.occurrences))
                for field_name in _FIELDS
                if self.resolve(index, field_name, locale) is not None
                and _served_locale(self, index, field_name, locale) != locale
            )
            for locale in self.locales
            if locale != SOURCE_LOCALE
        }
        found.dropped_source_content = {
            locale: tuple(sorted(self.dropped_source_content(locale)))
            for locale in self.locales
            if locale != SOURCE_LOCALE
        }
        found.shared_translations = {
            locale: tuple(sorted(self.shared_translations(locale)))
            for locale in self.locales
            if locale != SOURCE_LOCALE
        }
        found.segment_drift = {
            locale: tuple(sorted(self.segment_drift(locale))) for locale in self.locales if locale != SOURCE_LOCALE
        }
        found.shared_segments = {
            locale: tuple(sorted(self.shared_segments(locale))) for locale in self.locales if locale != SOURCE_LOCALE
        }
        found.translation_drift = self.translation_drift()
        found.stale_translations = {
            locale: self.stale_translations(locale) for locale in self.locales if locale != SOURCE_LOCALE
        }
        found.stranded_translations = {
            locale: self.stranded_translations(locale) for locale in self.locales if locale != SOURCE_LOCALE
        }
        return found

    def dropped_source_content(self, locale: str, values: Values | None = None) -> dict[str, tuple[str, ...]]:
        """Return, per serving key, the source tokens a translation lost.

        A label's or a help text's numbers, box references and comparison symbols are the legal
        content an operator acts on: a cap of 500 euros, the transitional
        provisions a deduction rests on, the box an amount is carried from. A
        translation that renders the prose but drops those states something the
        Spanish does not. Number formatting differs between languages, so
        digits are compared with separators removed.
        """
        lookup = self.lookup_for(self.values if values is None else values)
        dropped: dict[str, tuple[str, ...]] = {}
        for index, occurrence in enumerate(self.occurrences):
            for field_name in _FIELDS:
                spanish = self.resolve(index, field_name, SOURCE_LOCALE, values)
                if spanish is None:
                    continue
                source = _content_tokens(spanish)
                if not source:
                    continue
                served = modelo_localization_source(occurrence.chain(field_name), locale=locale, lookup=lookup)
                if served is None or served[1] != locale:
                    continue
                rendered = _content_tokens(self.resolve(index, field_name, locale, values) or "", spelled=True)
                # A reference repeated in one sentence states the same box once.
                missing = Counter({token: 1 for token in source if token not in rendered})
                if missing:
                    dropped[served[0]] = tuple(sorted(missing.elements()))
        return dropped

    def shared_translations(self, locale: str, values: Values | None = None) -> dict[str, tuple[str, ...]]:
        """Return translations one modelo renders for more than one Spanish wording.

        Two Spanish labels that differ only in case, accents or punctuation say
        one thing, so one translation serves both. A difference in wording may
        still be equivalent, which a reviewer records in
        :data:`REVIEWED_SHARED_TRANSLATIONS`; anything else is two concepts
        wearing one translation, as a reused box number produced in Modelo 200.
        """
        grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
        for index, occurrence in enumerate(self.occurrences):
            spanish = self.resolve(index, "label", SOURCE_LOCALE, values)
            text = self.resolve(index, "label", locale, values)
            if spanish is None or text is None or _served_locale(self, index, "label", locale, values) != locale:
                continue
            grouped[(occurrence.modelo, text)].add(spanish)
        shared: dict[str, tuple[str, ...]] = {}
        for (modelo, text), spanish_texts in grouped.items():
            if len({_plain_wording(spanish) for spanish in spanish_texts}) < 2:
                continue
            if (locale, modelo, text) in REVIEWED_SHARED_TRANSLATIONS:
                continue
            shared[text] = tuple(sorted(spanish_texts))
        return shared

    def segment_drift(self, locale: str, values: Values | None = None) -> dict[str, tuple[str, ...]]:
        """Return the composed segments this locale renders more than one way.

        AEAT composes a long label from segments joined by ``" - "``: a heading,
        a regime, a year, the state of the amount. A segment repeated across
        labels states the same thing each time, so its translation repeats too,
        the way the registry's delta keying stores one text for one meaning.
        Two renderings of one segment are a defect of a kind whole-value drift
        cannot see, since the surrounding labels differ: the meaning may even
        invert, as ``Sin reiteración`` rendered as a repeated donation.
        A reviewer records a segment whose context genuinely forces two
        renderings in :data:`REVIEWED_SEGMENT_RENDERINGS` with its reason.
        """
        view = self.values if values is None else values
        rendered: dict[str, set[str]] = defaultdict(set)
        for key, spanish_texts in self.served_sources(locale).items():
            translation = view.get(locale, {}).get(key)
            if translation is None or len(spanish_texts) != 1:
                continue
            spanish = _segments(next(iter(spanish_texts)))
            parts = _segments(translation)
            if len(spanish) != len(parts) or len(spanish) < 2:
                continue
            for source_part, rendering in zip(spanish, parts, strict=True):
                rendered[source_part.strip()].add(rendering.strip())
        return {
            segment: tuple(sorted(renderings))
            for segment, renderings in rendered.items()
            if len(renderings) > 1 and segment not in REVIEWED_SEGMENT_RENDERINGS.get(locale, {})
        }

    def shared_segments(self, locale: str, values: Values | None = None) -> dict[str, tuple[str, ...]]:
        """Return the renderings this locale gives to more than one Spanish segment.

        The mirror of :meth:`segment_drift`: one rendering standing for two
        segments hides a distinction the Spanish draws, as the Basque
        ``Concierto económico`` and the Navarrese ``Convenio económico`` once
        shared one English rendering. AEAT states one segment several ways
        across editions, abbreviating it or dropping its prepositions, and
        those wordings share one rendering correctly; a reviewer records each
        such pair in :data:`REVIEWED_SHARED_SEGMENTS` with the difference seen.
        """
        view = self.values if values is None else values
        rendered: dict[str, set[str]] = defaultdict(set)
        for key, spanish_texts in self.served_sources(locale).items():
            translation = view.get(locale, {}).get(key)
            if translation is None or len(spanish_texts) != 1:
                continue
            spanish = _segments(next(iter(spanish_texts)))
            parts = _segments(translation)
            if len(spanish) != len(parts) or len(spanish) < 2:
                continue
            for source_part, rendering in zip(spanish, parts, strict=True):
                rendered[rendering.strip()].add(source_part.strip())
        reviewed = REVIEWED_SHARED_SEGMENTS.get(locale, {})
        return {
            rendering: tuple(sorted(sources))
            for rendering, sources in rendered.items()
            if len({_abbreviated_wording(source) for source in sources}) > 1 and rendering not in reviewed
        }

    def translation_drift(self, values: Values | None = None) -> dict[str, tuple[str, ...]]:
        """Return, per locale, the lineages rendering one Spanish text more than one way.

        A lineage is the continuity key when the casilla declares one, else the
        casilla identity within its modelo. Divergent Spanish text is a genuine
        edition difference and is not drift.
        """
        groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
        for index, occurrence in enumerate(self.occurrences):
            lineage = occurrence.continuidad_id or f"casilla:{occurrence.casilla}"
            spanish = self.resolve(index, "label", SOURCE_LOCALE, values)
            if spanish is not None:
                groups[(occurrence.modelo, lineage, spanish)].append(index)
        drift: dict[str, tuple[str, ...]] = {}
        for locale in self.locales:
            if locale == SOURCE_LOCALE:
                continue
            drift[locale] = tuple(
                sorted(
                    f"{modelo}/{lineage}"
                    for (modelo, lineage, _spanish), members in groups.items()
                    if len(
                        {
                            text
                            for index in members
                            if _served_locale(self, index, "label", locale, values) == locale
                            and (text := self.resolve(index, "label", locale, values)) is not None
                        }
                    )
                    > 1
                )
            )
        return drift

    def copied_translations(self, locale: str) -> dict[str, str]:
        """Return the ``locale`` keys that serve a label identical to its resolved Spanish text."""
        copied: dict[str, str] = {}
        lookup = self.lookup_for(self.values)
        for index, occurrence in enumerate(self.occurrences):
            source = modelo_localization_source(occurrence.chain("label"), locale=locale, lookup=lookup)
            if source is None or source[1] != locale:
                continue
            text = self.values[locale][source[0]]
            if text is not None and text == self.resolve(index, "label", SOURCE_LOCALE):
                copied[source[0]] = text
        return copied

    def stale_translations(
        self,
        locale: str,
        excused: Mapping[tuple[str, str, str], str] = REVIEWED_EQUIVALENT_SPANISH,
    ) -> tuple[str, ...]:
        """Return lineages where one translation renders two different Spanish texts.

        The official wording changed and the translation did not follow, so a
        filer reads text that no longer matches the Spanish label.
        """
        lookup = self.lookup_for(self.values)
        spanish_by_translation: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for index, occurrence in enumerate(self.occurrences):
            source = modelo_localization_source(occurrence.chain("label"), locale=locale, lookup=lookup)
            spanish = self.resolve(index, "label", SOURCE_LOCALE)
            if source is None or source[1] != locale or spanish is None:
                continue
            translation = self.values[locale][source[0]]
            if translation is None:
                continue
            lineage = occurrence.continuidad_id or f"casilla:{occurrence.casilla}"
            spanish_by_translation[(occurrence.modelo, lineage, translation)].add(spanish)
        return tuple(
            sorted(
                {
                    f"{modelo}/{lineage}"
                    for (modelo, lineage, _translation), spanish in spanish_by_translation.items()
                    if len({_normalised(text) for text in spanish}) > 1 and (locale, modelo, lineage) not in excused
                }
            )
        )

    def stranded_translations(self, locale: str) -> tuple[str, ...]:
        """Return rows rendering Spanish although their lineage translates that exact Spanish text.

        The translation exists; it is only stored where these rows do not read
        it. Such rows are derivable, never new translation work.
        """
        lookup = self.lookup_for(self.values)
        translated: set[tuple[str, str, str]] = set()
        untranslated: list[tuple[tuple[str, str, str], str]] = []
        for index, occurrence in enumerate(self.occurrences):
            spanish = self.resolve(index, "label", SOURCE_LOCALE)
            if spanish is None:
                continue
            group = (occurrence.modelo, occurrence.continuidad_id or f"casilla:{occurrence.casilla}", spanish)
            source = modelo_localization_source(occurrence.chain("label"), locale=locale, lookup=lookup)
            if source is not None and source[1] == locale:
                translated.add(group)
            else:
                untranslated.append((group, f"{occurrence.modelo}/{occurrence.revision}/{occurrence.casilla}"))
        return tuple(sorted(label for group, label in untranslated if group in translated))

    def served_sources(self, locale: str) -> dict[str, frozenset[str]]:
        """Return, for each ``locale`` key that serves a text, the Spanish texts it renders."""
        lookup = self.lookup_for(self.values)
        sources: dict[str, set[str]] = defaultdict(set)
        for index, occurrence in enumerate(self.occurrences):
            for field_name in _FIELDS:
                source = modelo_localization_source(occurrence.chain(field_name), locale=locale, lookup=lookup)
                spanish = self.resolve(index, field_name, SOURCE_LOCALE)
                if source is not None and source[1] == locale and spanish is not None:
                    sources[source[0]].add(spanish)
        return {key: frozenset(texts) for key, texts in sources.items()}

    # -- collapse ---------------------------------------------------------

    def collapse_plan(self, *, include_redundant: bool = True) -> CollapseResult:
        """Compute removals and lineage lifts that preserve every resolved text.

        Derived help, null leaves and orphan keys are removed first; they are
        delete targets whatever they resolve to. Lineage lifts then place a
        value on a continuity key when every chain reading that key already
        resolves to it in that locale, which changes no resolution. Finally
        every remaining value is tested for redundancy most-specific first: it
        is dropped when removing it changes no coordinate that reads its key.
        """
        working: Values = {locale: dict(leaves) for locale, leaves in self.values.items()}
        plan = CollapsePlan()
        for locale in self.locales:
            for key, value in list(working[locale].items()):
                if self._undeclared_revision(key):
                    continue
                if key not in self.dependents:
                    plan.remove(locale, key, "orphan")
                elif value is None:
                    plan.remove(locale, key, "null")
                elif _is_derived_help(key, value):
                    plan.remove(locale, key, "derived-help")
                else:
                    continue
                del working[locale][key]
        baseline = self.resolution(working)
        # A stale lineage value blocks a lift until the redundancy pass removes
        # it, and a lift makes more occurrence values redundant, so the two
        # passes alternate until neither changes the catalogue.
        lifted_keys: dict[str, set[str]] = defaultdict(set)
        progressing = True
        while progressing:
            lifted = self._lift_to_lineage(working, baseline, plan, lifted_keys)
            removed = self._remove_redundant(working, baseline, plan) if include_redundant else 0
            progressing = bool(lifted or removed)
        return CollapseResult(plan=plan, working=working, baseline=baseline)

    def _remove_redundant(
        self,
        working: Values,
        baseline: Mapping[Coordinate, str | None],
        plan: CollapsePlan,
    ) -> int:
        """Drop every value whose removal changes no resolution; return how many."""
        removed = 0
        # Spanish goes first: removing a Spanish value lowers the Spanish tier,
        # which is what lets a translation move down to the shared key. The
        # pass repeats to a fixed point because each removal can enable another.
        changed = True
        while changed:
            changed = False
            for locale in (SOURCE_LOCALE, *[loc for loc in self.locales if loc != SOURCE_LOCALE]):
                for key in sorted(working[locale], key=_specificity):
                    if self._undeclared_revision(key):
                        continue
                    value = working[locale].pop(key)
                    if self._unchanged(key, locale, working, baseline):
                        plan.remove(locale, key, "redundant")
                        removed += 1
                        changed = True
                    else:
                        working[locale][key] = value
        return removed

    def _undeclared_revision(self, key: str) -> bool:
        """Return whether ``key`` sits under a revision id no occurrence declares."""
        match = _REVISION_SCOPED.match(key)
        return match is not None and (match["modelo"], match["revision"]) not in self.declared_revisions

    def _affected_locales(self, locale: str) -> tuple[str, ...]:
        return self.locales if locale == SOURCE_LOCALE else (locale,)

    def _unchanged(self, key: str, locale: str, working: Values, baseline: Mapping[Coordinate, str | None]) -> bool:
        return all(
            self.resolve(index, field_name, affected, working) == baseline[(index, field_name, affected)]
            for index, field_name in self.dependents.get(key, ())
            for affected in self._affected_locales(locale)
        )

    def _lift_to_lineage(
        self,
        working: Values,
        baseline: Mapping[Coordinate, str | None],
        plan: CollapsePlan,
        lifted_keys: dict[str, set[str]],
    ) -> int:
        """Place agreed text on empty lineage keys where no resolution changes; return how many.

        A key this plan already lifted once is never lifted again: if the
        redundancy pass dropped it, lifting it back would only cycle.
        """
        lifted = 0
        lineage_keys = sorted(key for key in self.dependents if is_lineage_key(key))
        for locale in (SOURCE_LOCALE, *[loc for loc in self.locales if loc != SOURCE_LOCALE]):
            for key in lineage_keys:
                if working[locale].get(key) is not None or key in lifted_keys[locale]:
                    continue
                texts = {baseline[(index, field_name, locale)] for index, field_name in self.dependents[key]}
                if len(texts) != 1:
                    continue
                (text,) = texts
                if text is None:
                    continue
                working[locale][key] = text
                if self._unchanged(key, locale, working, baseline):
                    plan.assign(locale, key, text, "lineage-lift")
                    lifted_keys[locale].add(key)
                    lifted += 1
                else:
                    del working[locale][key]
        return lifted

    # -- application ------------------------------------------------------

    def apply(
        self,
        result: CollapseResult,
        locales_dir: Path = LOCALES_DIR,
        pending_dir: Path = PENDING_CASILLA_INSTALL_DIR,
    ) -> dict[str, int]:
        """Install ``result`` into ``locales_dir`` only after a staged copy proves it.

        The plan is written into a staged copy kept at ``pending_dir``, and that
        copy must resolve every coordinate exactly as ``result.baseline`` does.
        The changed Modelo schema shards are then copied into place, and the
        staged copy is discarded only when every shard is installed. An
        interrupted install leaves ``pending_dir`` behind: planning refuses while
        it exists, because a partly installed catalogue is not a baseline, and
        :func:`resume_install` finishes the verified install instead.

        Raises:
            CollapseVerificationError: An install is already pending, the staged
                catalogue resolves differently, or a shard could not be installed.
        """
        if pending_dir.exists():
            raise CollapseVerificationError(f"an install is pending at {pending_dir}; resume it first")
        staged = pending_dir / "locales"
        shutil.copytree(locales_dir, staged)
        try:
            written = self._write_plan(result.plan, staged)
            proof = ModeloCasillaCatalogue(self.occurrences, load_casilla_values(staged))
            changed = sum(1 for coordinate, text in proof.resolution().items() if result.baseline[coordinate] != text)
        except BaseException:
            _discard(pending_dir)
            raise
        if changed:
            _discard(pending_dir)
            raise CollapseVerificationError(f"the staged catalogue resolves {changed} texts differently")
        resume_install(locales_dir, pending_dir)
        return written

    def author(
        self,
        manifest: Mapping[str, Mapping[str, str | None]],
        locales_dir: Path = LOCALES_DIR,
        pending_dir: Path = PENDING_CASILLA_INSTALL_DIR,
    ) -> dict[str, int]:
        """Install authored casilla values and removals, proving they are the only source of change.

        A ``None`` value removes the key, so an edition falls back to the text a
        less specific key provides; that text's key must be named in the manifest.

        Every coordinate whose resolved text differs afterwards must be served
        by one of the manifest's keys in its own locale, or, for a Spanish
        change, by a manifest key read through the Spanish fallback. Any other
        change means the manifest reached text it did not declare, and the
        install is refused. Returns how many coordinates changed per locale.

        Raises:
            CollapseVerificationError: An install is pending, a key is not a
                casilla key any chain reads, or a change is not attributable.
        """
        unknown = sorted(
            f"{locale}:{key}"
            for locale, values in manifest.items()
            for key in values
            if locale not in self.locales or key not in self.dependents
        )
        if unknown:
            raise CollapseVerificationError(f"manifest names keys no casilla chain reads: {unknown[:5]}")
        if pending_dir.exists():
            raise CollapseVerificationError(f"an install is pending at {pending_dir}; resume it first")
        before = self.resolution()
        staged = pending_dir / "locales"
        shutil.copytree(locales_dir, staged)
        try:
            manager = LocaleManager(src_dir=staged, locales_dir=staged)
            for locale, values in sorted(manifest.items()):
                settings = {key: text for key, text in values.items() if text is not None}
                removals = sorted(key for key, text in values.items() if text is None)
                if settings:
                    manager.set_locale_values(locale, settings)
                if removals:
                    manager.remove_locale_values(locale, removals)
            proof = ModeloCasillaCatalogue(self.occurrences, load_casilla_values(staged))
            after = proof.resolution()
            changed: dict[str, int] = defaultdict(int)
            unattributed: list[Coordinate] = []
            for coordinate, text in after.items():
                if before[coordinate] == text:
                    continue
                index, field_name, locale = coordinate
                source = modelo_localization_source(
                    self.occurrences[index].chain(field_name), locale=locale, lookup=proof.lookup_for(proof.values)
                )
                if source is None or source[0] not in manifest.get(source[1], {}):
                    unattributed.append(coordinate)
                changed[locale] += 1
        except BaseException:
            _discard(pending_dir)
            raise
        if unattributed:
            _discard(pending_dir)
            raise CollapseVerificationError(f"{len(unattributed)} changed texts are not served by the manifest")
        split = self._continuity_splits(before, after)
        if split:
            _discard(pending_dir)
            raise CollapseVerificationError(
                "Spanish text would diverge between editions that render one text today, which the registry "
                f"refuses without a continuity evolution: {split[:5]}"
            )
        resume_install(locales_dir, pending_dir)
        return dict(changed)

    def _continuity_splits(
        self,
        before: Mapping[Coordinate, str | None],
        after: Mapping[Coordinate, str | None],
    ) -> tuple[str, ...]:
        """Return the boxes whose editions agree on Spanish text before and disagree after.

        The registry compares a casilla's label across the editions that declare
        it and refuses an undeclared difference, so an authored edition-specific
        Spanish text must come with a continuity evolution in the registry. Help
        is not one of the fields it compares, so edition-specific help needs no
        evolution and is not judged here.
        """
        editions: dict[tuple[str, str], list[int]] = defaultdict(list)
        for index, occurrence in enumerate(self.occurrences):
            if not occurrence.casilla.startswith("construct:"):
                editions[(occurrence.modelo, occurrence.casilla)].append(index)
        split: list[str] = []
        for (modelo, casilla), members in sorted(editions.items()):
            old = defaultdict(set)
            for index in members:
                old[before.get((index, "label", SOURCE_LOCALE))].add(after.get((index, "label", SOURCE_LOCALE)))
            if any(len(texts) > 1 for texts in old.values()):
                split.append(f"{modelo}/{casilla}")
        return tuple(split)

    def _write_plan(self, plan: CollapsePlan, locales_dir: Path) -> dict[str, int]:
        manager = LocaleManager(src_dir=locales_dir, locales_dir=locales_dir)
        written: dict[str, int] = {}
        for locale in self.locales:
            settings: dict[str, str | None] = {
                key: value for key, (value, _reason) in plan.settings.get(locale, {}).items()
            }
            removals = sorted(set(plan.removals.get(locale, {})) - set(settings))
            if settings:
                manager.set_locale_values(locale, settings)
            if removals:
                manager.remove_locale_values(locale, removals)
            written[locale] = len(settings) + len(removals)
        return written


class CollapseVerificationError(RuntimeError):
    """A collapse could not be proven lossless or installed as proven."""


_INSTALL_ATTEMPTS: Final = 60
_INSTALL_BACKOFF_SECONDS: Final = 0.5


def resume_install(locales_dir: Path = LOCALES_DIR, pending_dir: Path = PENDING_CASILLA_INSTALL_DIR) -> None:
    """Install a verified staged catalogue and discard it once every shard is in place.

    Raises:
        CollapseVerificationError: No install is pending, or a shard could not be written.
    """
    staged = pending_dir / "locales"
    if not staged.is_dir():
        raise CollapseVerificationError(f"no install is pending at {pending_dir}")
    failed = _install_shards(staged, locales_dir)
    if failed:
        raise CollapseVerificationError(f"verified shards could not be installed, resume again: {failed}")
    _discard(pending_dir)


def _discard(pending_dir: Path) -> None:
    """Remove a staged catalogue, tolerating lock sidecars that vanish while it is walked."""

    def ignore_vanished(function: Callable[..., object], path: str, error: BaseException) -> None:
        if not isinstance(error, FileNotFoundError):
            raise error

    shutil.rmtree(pending_dir, onexc=ignore_vanished)


def _install_shards(staged: Path, locales_dir: Path) -> tuple[str, ...]:
    """Copy every changed Modelo schema shard from ``staged``; return the ones that failed."""
    failed: list[str] = []
    for source in sorted(staged.glob("*/modelo/schema/*.yml")):
        relative = source.relative_to(staged)
        target = locales_dir / relative
        payload = source.read_bytes()
        if target.is_file() and target.read_bytes() == payload:
            continue
        for _attempt in range(_INSTALL_ATTEMPTS):
            try:
                atomic_write_text(target, payload.decode("utf-8"))
                break
            except OSError:
                time.sleep(_INSTALL_BACKOFF_SECONDS)
        else:
            failed.append(relative.as_posix())
    return tuple(failed)


@dataclass(slots=True)
class CollapseResult:
    """A collapse plan with the evidence it was computed against."""

    plan: CollapsePlan
    working: Values
    baseline: Mapping[Coordinate, str | None]


def _specificity(key: str) -> tuple[int, str]:
    """Order occurrence keys before lineage keys so the shared value survives."""
    return (1 if is_lineage_key(key) else 0, key)


def _normalised(text: str) -> str:
    """Fold case, accents and punctuation so only a wording change counts."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    letters = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^\w]+", " ", letters).split())


def _content_tokens(text: str, *, spelled: bool = False) -> Counter[str]:
    """Return the numbers, box references and comparison symbols a label states.

    Compared across languages, so a rendering difference is not a difference in
    content: "25 por 100" and "25%" state one rate, a date is reordered, and the
    separators inside a number or between the parts of a citation vary. With
    ``spelled``, a number written as a word counts as that number, which is how
    a translation may render a digit the Spanish wrote; the Spanish side never
    reads words, because its own prose says "un" and "dos" as articles.
    """
    found: Counter[str] = Counter()
    grouped = _PERCENT_WORDS.sub("%", text)
    for ascii_form, symbol in _ASCII_COMPARISON.items():
        grouped = grouped.replace(ascii_form, symbol)
    plain = _THOUSANDS.sub(lambda match: re.sub(r"[^0-9]", "", match.group()), grouped)
    for token in _CONTENT_TOKEN.findall(plain):
        cleaned = re.sub(r"\s+", "", token)
        found[cleaned.lstrip("0") or "0" if cleaned.isdigit() else cleaned] += 1
    if spelled:
        for word in _WORD_TOKEN.findall(text):
            number = _SPELLED_NUMBERS.get(word.casefold())
            if number is not None:
                found[str(number)] += 1
    return found


def _segments(text: str) -> tuple[str, ...]:
    """Split a composed label into its segments, leaving arithmetic whole.

    ``" - "`` both joins the segments of a label and subtracts one box from
    another. A subtraction is written inside its parentheses and its operands
    are box references rather than prose, so a split is read only outside
    brackets and only when every segment states words.
    """
    depth = 0
    parts: list[str] = []
    start = 0
    for match in re.finditer(rf"[()\[\]]|{_SEGMENT.pattern}", text):
        bracket = match.group()
        if bracket in "([":
            depth += 1
        elif bracket in ")]":
            depth = max(0, depth - 1)
        elif depth == 0:
            parts.append(text[start : match.start()])
            start = match.end()
    parts.append(text[start:])
    if len(parts) < 2 or not all(_SEGMENT_PROSE.search(part) for part in parts):
        return (text,)
    return tuple(parts)


def _plain_wording(text: str) -> str:
    """Return text stripped to its letters and digits, so case and punctuation do not distinguish it."""
    unmarked = "".join(ch for ch in unicodedata.normalize("NFD", text) if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", unmarked.casefold())


def _abbreviated_wording(text: str) -> str:
    """Return a wording without the words AEAT drops when it shortens a label.

    An official label is written out in one edition and abbreviated in the
    next, losing its prepositions and articles: ``IVA deducible en
    importaciones de bienes corrientes`` becomes ``IVA deducible importaciones
    bienes corrientes``. The two state one thing, so they may share one
    rendering; a difference in the remaining words may not.
    """
    unmarked = "".join(ch for ch in unicodedata.normalize("NFD", text) if not unicodedata.combining(ch))
    words = (match.group() for match in re.finditer(r"[a-z0-9+]+", unmarked.casefold()))
    return " ".join(word for word in words if word not in _SPANISH_FUNCTION_WORDS)


def _is_derived_help(key: str, value: str) -> bool:
    return key.endswith(".help") and any(pattern.match(value) for pattern in _DERIVED_HELP)


def _served_locale(
    catalogue: ModeloCasillaCatalogue,
    index: int,
    field_name: str,
    locale: str,
    values: Values | None = None,
) -> str | None:
    source = modelo_localization_source(
        catalogue.occurrences[index].chain(field_name),
        locale=locale,
        lookup=catalogue.lookup_for(catalogue.values if values is None else values),
    )
    return None if source is None else source[1]
