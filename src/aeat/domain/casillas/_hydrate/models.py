from dataclasses import dataclass
from decimal import Decimal
from typing import cast
from aeat.core.i18n import Translatable
from ..models import (
    CasillaRecord, SelectOption, FormulaReference,
    ValidationRuleReference, CasillaCatalogue
)
from .. import CasillaDataType
from .lemmas import _es_to_ca_via_lemmas, _hu_restore_diacritics

@dataclass(frozen=True)
class _Casilla:
    casilla_id: str
    label_es: str
    label_en: str
    label_hu: str
    help_es: str
    help_en: str
    help_hu: str
    label_ca: str = ""
    help_ca: str = ""
    data_type: CasillaDataType = CasillaDataType.CURRENCY_EUR
    computed: bool = False
    formula_expression: str | None = None
    formula_refs: tuple[str, ...] = ()
    references_rules: tuple[str, ...] = ()
    section: str = ""
    select_options: tuple[SelectOption, ...] | None = None

    def label_for_languages(self, languages: tuple[str, ...]) -> dict[str, str]:
        es = self.label_es
        out: dict[str, str] = {}
        for lang in languages:
            value = getattr(self, f"label_{lang}", "")
            if value:
                out[lang] = _hu_restore_diacritics(value) if lang == "hu" else value
            elif lang == "ca":
                out[lang] = _es_to_ca_via_lemmas(es)
            else:
                out[lang] = es
        return out

    def help_for_languages(self, languages: tuple[str, ...]) -> dict[str, str]:
        es = self.help_es
        out: dict[str, str] = {}
        for lang in languages:
            value = getattr(self, f"help_{lang}", "")
            if value:
                out[lang] = _hu_restore_diacritics(value) if lang == "hu" else value
            elif lang == "ca":
                out[lang] = _es_to_ca_via_lemmas(es)
            else:
                out[lang] = es
        return out
