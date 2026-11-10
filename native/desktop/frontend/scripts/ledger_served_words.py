"""Record the sentences the Ledger operations serve, for the browser fixtures that answer for them.

The prorrata register, capital-goods and inventory operations serve a finished sentence with every
refusal, the evidence review serves one for each reason a read draft cannot be confirmed, and an
off-host evidence read the consent gate refuses settles with the gate's own sentence, and a listed row
whose classification a command wrote serves a word for the command in place of its name. This
words each through the same functions the operations call, for every reason in every language, so
the browser fixtures show what the backend serves and hold no text of their own. A sentence the
operation fills from a refusal's facts is recorded with each fact as a ``{name}`` placeholder, which
the fixture fills from the refusal it builds. Run after changing a served catalogue key or reason:

    uv run --no-sync python native/desktop/frontend/scripts/ledger_served_words.py [--check]
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import cast, get_args

from dev.fixture_projections.location import family_directory
from dev.fixture_projections.producer_output import emit, producer_arguments
from pydantic import TypeAdapter

LANGUAGES = ("en", "es", "ca", "hu")

#: A sentence in each language, by reason, by operation family.
_Words = dict[str, dict[str, dict[str, str]]]
_WORDS = TypeAdapter(_Words)
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _sentinel(name: str) -> str:
    """A fact value the catalogue fills in verbatim and nothing else spells."""
    return f"zq{name}qz"


def _worded(reasons: tuple[str, ...], word: Callable[[str], tuple[str, str]]) -> dict[str, dict[str, str]]:
    """Word each reason as its operation serves it, in every language."""
    from cadrumo.core.config import override_settings

    words: dict[str, dict[str, str]] = {}
    for reason in reasons:
        words[reason] = {}
        for language in LANGUAGES:
            with override_settings(cadrumo_output_language=language):
                sentence, served = word(reason)
            if served != language:
                raise SystemExit(f"{reason} was worded in {served}, not {language}")
            words[reason][language] = sentence
    return words


def _templated(sentence: str, names: tuple[str, ...]) -> str:
    """``sentence`` with each fact's sentinel turned back into its placeholder."""
    for name in names:
        sentence = sentence.replace(_sentinel(name), "{" + name + "}")
    return sentence


def _prorrata() -> dict[str, dict[str, str]]:
    from cadrumo.application.prorrata_register.projection_contracts import ProrrataRefusalReason
    from cadrumo.application.prorrata_register.refusal_words import served_refusal_words

    reasons = cast(tuple[ProrrataRefusalReason, ...], get_args(ProrrataRefusalReason.__value__))

    def word(reason: str) -> tuple[str, str]:
        sentence, served = served_refusal_words(
            cast(ProrrataRefusalReason, reason), error_code="REFUSED_PROFILE_PRORRATA_REGISTER_VALIDATION"
        )
        return sentence, served.value

    return _worded(reasons, word)


def _capital_goods() -> dict[str, dict[str, str]]:
    from cadrumo.application.bienes_inversion.refusal_words import served_refusal_words

    code = "REFUSED_PROFILE_BIENES_INVERSION_VALIDATION"
    cases: Mapping[str, Callable[[], tuple[str, str]]] = {
        "validation": lambda: _served(served_refusal_words("validation", error_code=code)),
        "disposal_incomplete.year": lambda: _served(
            served_refusal_words("disposal_incomplete", error_code=code, missing="year")
        ),
        "disposal_incomplete.regime": lambda: _served(
            served_refusal_words("disposal_incomplete", error_code=code, missing="regime")
        ),
        "duplicate_identifier": lambda: _served(
            served_refusal_words("duplicate_identifier", error_code=code, identifier=_sentinel("identifier")),
            ("identifier",),
        ),
    }
    return _worded(tuple(cases), lambda case: cases[case]())


def _inventory() -> dict[str, dict[str, str]]:
    from cadrumo.application.inventory.refusal_words import served_refusal_words
    from cadrumo.application.inventory.registered_requests import InventoryRefusalReason
    from cadrumo.core.i18n.render import lookup_translation
    from cadrumo.domain.contribuyente.inventory.corrections import inventory_refusal_key

    reasons = tuple(
        reason
        for member in get_args(InventoryRefusalReason)
        for reason in (get_args(member.__value__) if hasattr(member, "__value__") else (member,))
    )

    def word(reason: str) -> tuple[str, str]:
        names = tuple(
            sorted(
                {
                    name
                    for language in LANGUAGES
                    for name in _PLACEHOLDER.findall(
                        lookup_translation(inventory_refusal_key(reason), locale=language) or ""
                    )
                }
            )
        )
        return _served(
            served_refusal_words(
                cast(InventoryRefusalReason, reason),
                error_code="REFUSED_INVENTORY_SERVICE_INPUT",
                facts={name: _sentinel(name) for name in names},
            ),
            names,
        )

    return _worded(reasons, word)


def _confirmation_block() -> dict[str, dict[str, str]]:
    from cadrumo.application.ledger.confirmation_block_words import served_block_reason_words
    from cadrumo.core.confirmation_gate import ConfirmationBlockReason

    def word(reason: str) -> tuple[str, str]:
        return _served(served_block_reason_words(ConfirmationBlockReason(reason)))

    return _worded(tuple(reason.value for reason in ConfirmationBlockReason), word)


def _off_host_consent() -> dict[str, dict[str, str]]:
    """The sentence an off-host read refused by the consent gate settles with, as its error detail words it."""
    from cadrumo.adapters.outbound.llm.consent import mint_evidence_consent_token
    from cadrumo.adapters.outbound.llm.errors import LLMConsentError
    from cadrumo.application.operations.error_detail import operation_refusal_words
    from cadrumo.core.config import load_settings

    def word(reason: str) -> tuple[str, str]:
        if reason != "mint_refused":
            raise SystemExit(f"no off-host consent refusal is named {reason}")
        try:
            mint_evidence_consent_token(
                settings=load_settings().model_copy(update={"cadrumo_evidence_cloud_upload_permitted": False}),
                profile_eligible=False,
                acknowledged=True,
                surface="ledger_served_words",
                evidence_content_address="0" * 64,
            )
        except LLMConsentError as refused:
            worded = operation_refusal_words(refused)
        else:
            raise SystemExit("the consent gate minted with every bar closed")
        if worded is None:
            raise SystemExit("the consent gate's refusal serves no sentence")
        return _served(worded)

    return _worded(("mint_refused",), word)


def _classification_reason() -> dict[str, dict[str, str]]:
    """The word a listed row serves in place of the command that wrote its classification, by source."""
    from cadrumo.application.ledger.transaction_projection import classification_reason_words
    from cadrumo.core.external_constants import OutputLanguage

    return {
        "command": {
            language: classification_reason_words("command", OutputLanguage(language)) for language in LANGUAGES
        }
    }


def _served(worded: tuple[str, object], names: tuple[str, ...] = ()) -> tuple[str, str]:
    """A served sentence and its language's token, its sentinels turned into placeholders."""
    sentence, language = worded
    return _templated(sentence, names), str(getattr(language, "value", language))


def render_fixture() -> str:
    """Word every served Ledger sentence the browser fixtures answer with, in every language."""
    words = {
        "prorrata": _prorrata(),
        "capital_goods": _capital_goods(),
        "inventory": _inventory(),
        "confirmation_block": _confirmation_block(),
        "off_host_consent": _off_host_consent(),
        "classification_reason": _classification_reason(),
    }
    return json.dumps(words, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    """Write, verify or redirect the browser fixture."""
    emit(
        {family_directory("ledger-served-words") / "ledgerServedWords.json": render_fixture()},
        producer_arguments(__doc__),
        remedy="uv run --no-sync python native/desktop/frontend/scripts/ledger_served_words.py",
    )


if __name__ == "__main__":
    main()
