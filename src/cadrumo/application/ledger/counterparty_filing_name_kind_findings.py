"""Surface a declared counterparty kind that contradicts the form of its Spanish identifier."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.identity.documents import IdentityDocument, IdentityError, validate_identity
from ...core.identity.tax_id import validate_spanish_tax_id
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ...domain.filing.declared_party_name import DeclaredPartyKind
from ...domain.iva.establishment import SPAIN_COUNTRY_CODE
from ..operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH, served_words_language

FILING_NAME_KIND_CONTRADICTS_FORM_FINDING = "counterparty_filing_name_kind_contradicts_identifier_form"
"""Stable code of the finding raised when a declared kind and a Spanish NIF's form disagree."""


_FINDING_LOCALE_KEY = "application.ledger.counterparty.findings.kind_contradicts_identifier_form"
_PARTY_KIND_LOCALE_KEYS: dict[str, str] = {
    DeclaredPartyKind.NATURAL_PERSON.value: "application.ledger.counterparty.party_kinds.natural_person",
    DeclaredPartyKind.ENTITY.value: "application.ledger.counterparty.party_kinds.entity",
}


class CounterpartyFilingNameFinding(BaseModel):
    """A disagreement between the declared kind and the form of the identifier.

    It carries the two kinds and the sentence a frontend shows for them, in the
    language it is in, and nothing else: never the identifier or the name, so it
    may travel through any channel the result does.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    code: Literal["counterparty_filing_name_kind_contradicts_identifier_form"]
    declared_kind: Literal["natural_person", "entity"]
    observed_form: Literal["natural_person", "entity"]
    words: str | None = Field(default=None, min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)
    words_language: OutputLanguage | None = None

    @model_validator(mode="after")
    def _words_name_their_language(self) -> CounterpartyFilingNameFinding:
        if (self.words is None) != (self.words_language is None):
            raise ValueError("served words name the language they are in")
        return self


def served_kind_finding_words(*, declared_kind: str, observed_form: str) -> tuple[str, OutputLanguage]:
    """The finished sentence for a kind that contradicts the identifier's form, and the worker's language."""
    language = served_words_language()
    return (
        tr(
            _FINDING_LOCALE_KEY,
            locale=language.value,
            declared=tr(_PARTY_KIND_LOCALE_KEYS[declared_kind], locale=language.value),
            observed=tr(_PARTY_KIND_LOCALE_KEYS[observed_form], locale=language.value),
        ),
        language,
    )


def _identifier_form(
    tax_identifier: str, *, country_code: str | None, operation: PinnedAuthorityOperation
) -> DeclaredPartyKind | None:
    """Classify a Spanish identifier's form with the canonical NIF kernel, or ``None``.

    The kernel partitions the nine-character identifier by its leading
    character: digits (NIF), K, L, M and X, Y, Z (NIE) name natural persons, and
    the organisation letters name entities (Orden EHA/451/2008, arts. 2 to 4,
    as declared in the pinned identifier-format fact). A non-Spanish identifier,
    or one the kernel does not accept, has no form to classify.
    """
    if country_code is not None and country_code != SPAIN_COUNTRY_CODE:
        return None
    tax_id_format = runtime_tax_id_format(authority=operation)
    try:
        document = validate_identity(validate_spanish_tax_id(tax_identifier, tax_id_format), tax_id_format)
    except IdentityError:
        return None
    return DeclaredPartyKind.ENTITY if document is IdentityDocument.CIF else DeclaredPartyKind.NATURAL_PERSON


def filing_name_kind_findings(
    *,
    tax_identifier: str,
    country_code: str | None,
    declared_kind: str,
    operation: PinnedAuthorityOperation,
) -> tuple[CounterpartyFilingNameFinding, ...]:
    """Surface a declared kind that contradicts the identifier's form; never resolve it."""
    observed = _identifier_form(tax_identifier, country_code=country_code, operation=operation)
    if observed is None or observed.value == declared_kind:
        return ()
    declared = DeclaredPartyKind(declared_kind).value
    words, language = served_kind_finding_words(declared_kind=declared, observed_form=observed.value)
    return (
        CounterpartyFilingNameFinding(
            code=FILING_NAME_KIND_CONTRADICTS_FORM_FINDING,
            declared_kind=declared,
            observed_form=observed.value,
            words=words,
            words_language=language,
        ),
    )


__all__ = [
    "FILING_NAME_KIND_CONTRADICTS_FORM_FINDING",
    "CounterpartyFilingNameFinding",
    "filing_name_kind_findings",
    "served_kind_finding_words",
]
