"""A bank account in the form it is PRINTED must not reach operator output.

The IBAN arm exists by operator decision, deliberately reaching past this
module's stated tax-identity must-handle list, because a bank account number is
sensitive financial data. It matched only the uppercase, separator-free
spelling -- and that is the spelling that does not arrive. An IBAN is
essentially always printed in groups of four: that is how it appears on a bank
statement, in an invoice footer and on a refund-account form, which are exactly
the surfaces this app reads one from. The covered rendering was the one no
producer emits.

The corpus below is therefore built from what a producer prints, not from the
canonical form the app stores. The negative half is built the same way: an
uppercase invoice or statement line is where a widened scan does its damage,
because the arm's body class is uppercase alphanumeric and ordinary uppercase
prose looks exactly like a BBAN.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ..iban import IBAN_SHAPE_RE, iban_mod_97, normalise_iban
from ..redaction import redact_for_cli_output, redact_for_log

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FUNNELS: list[Callable[[str], str]] = [redact_for_cli_output, redact_for_log]

#: Real, checksum-valid accounts in the groupings a producer prints. Every entry
#: is proven to be a genuine IBAN below, against the same primitives the arm's
#: gate uses, so this corpus cannot decay into arbitrary strings.
PRINTED_ACCOUNTS = [
    "ES91 2100 0418 4502 0005 1332",
    "ES91-2100-0418-4502-0005-1332",
    "ES9121000418450200051332",
    "DE89 3704 0044 0532 0130 00",
    "GB29 NWBK 6016 1331 9268 19",
    "FR14 2004 1010 0505 0001 3M02 606",
]

#: The printed account inside the sentence a surface actually emits.
ACCOUNTS_IN_PROSE = [
    ("cuenta ES91 2100 0418 4502 0005 1332 declarada", ["cuenta ", " declarada"]),
    ("es ES91 2100 0418 4502 0005 1332 y nada mas", ["es ", " y nada mas"]),
    ("IBAN ES91 2100 0418 4502 0005 1332 EN FACTURA", ["IBAN ", " EN FACTURA"]),
    ("de DE89 3704 0044 0532 0130 00 en", ["de ", " en"]),
]

#: Uppercase producer output that must reach the operator intact. The first
#: entries are the sharp ones: an uppercase statement or invoice line is
#: indistinguishable from a spaced BBAN by shape alone, so only the checksum
#: keeps them apart.
PRODUCER_TEXT_THAT_MUST_SURVIVE = [
    "MODELO 303 EJERCICIO 2026 PERIODO 1T",
    "FACTURA SERIE A NUM 0001 FECHA 2026 01 15",
    "BASE IMPONIBLE 1000 00 CUOTA 210 00 TOTAL 1210 00",
    "ASIENTO CONTABLE 4700 0001 0002 0003 0004 0005",
    "BOE-A-2026-12345",
    "ES-2026-000412 es la serie",
    "ES91 2100 0418 4502 0005 1333",
    "DE89 3704 0044 0532 0130 01",
    "Total factura 1.234,56 EUR",
    "aeat app ledger evidence extract",
]


@pytest.mark.parametrize("printed", PRINTED_ACCOUNTS)
def test_the_corpus_entries_are_genuine_accounts(printed: str) -> None:
    """Anti-tautology: the positive corpus must be real IBANs.

    Without this the case below passes against a scan that hashes anything
    grouped, and the suite would be measuring over-firing rather than
    protection. The authority asked is the pair of primitives the arm's own
    gate consults.
    """
    canonical = normalise_iban(printed)

    assert IBAN_SHAPE_RE.match(canonical), f"{printed!r} is not shaped like an IBAN"
    assert iban_mod_97(canonical) == 1, f"{printed!r} fails the mod-97 check and proves nothing"


@pytest.mark.parametrize("printed", PRINTED_ACCOUNTS)
@pytest.mark.parametrize("funnel", _FUNNELS)
def test_a_printed_account_does_not_survive_the_funnel(printed: str, funnel: Callable[[str], str]) -> None:
    """The leak this closes, on both funnels."""
    redacted = funnel(printed)

    assert redacted != printed
    assert redacted.startswith("sha256:"), redacted


@pytest.mark.parametrize(("sentence", "survivors"), ACCOUNTS_IN_PROSE)
@pytest.mark.parametrize("funnel", _FUNNELS)
def test_a_printed_account_inside_prose_is_removed_without_eating_the_sentence(
    sentence: str,
    survivors: list[str],
    funnel: Callable[[str], str],
) -> None:
    """Admitting a space is what lets a scan swallow the neighbouring word.

    The account must go and the operator's sentence must stay; an over-wide
    match that carried ``EN FACTURA`` into the span would fail the checksum and
    put the whole account back on screen.
    """
    redacted = funnel(sentence)

    assert "0005 1332" not in redacted
    assert "0130 00" not in redacted
    assert "sha256:" in redacted, redacted
    for fragment in survivors:
        assert fragment in redacted, f"the fix ate operator text: {fragment!r} is missing from {redacted!r}"


@pytest.mark.parametrize("text", PRODUCER_TEXT_THAT_MUST_SURVIVE)
@pytest.mark.parametrize("funnel", _FUNNELS)
def test_producer_text_that_is_not_an_account_survives(text: str, funnel: Callable[[str], str]) -> None:
    """The bound. The checksum, not the shape, is what admits a match here.

    A BOE citation is the module's standing negative control: an arm that
    starts eating one is too wide. The two near-miss accounts differ from a
    real one only in their final check character, so nothing but the mod-97
    residue separates them from the positive corpus.
    """
    assert funnel(text) == text, f"{text!r} was rewritten to {funnel(text)!r}"


def test_a_grouped_account_and_its_compact_form_are_one_account() -> None:
    """The two spellings the funnel must not disagree about.

    They hash differently, as every separator-bearing spelling in this module
    does -- the span is hashed as printed. What must not differ is whether they
    are redacted at all.
    """
    grouped = "ES91 2100 0418 4502 0005 1332"
    compact = "ES9121000418450200051332"

    assert normalise_iban(grouped) == compact

    assert redact_for_cli_output(grouped) != grouped
    assert redact_for_cli_output(compact) != compact


def test_the_negative_corpus_is_not_vacuous() -> None:
    """Every negative case asserts an ABSENCE, so the arm must be proven live.

    If the IBAN arm were dropped from the policy entirely the positive cases
    would red, but the whole negative half would pass in silence and read as
    green.
    """
    removed = sum(1 for printed in PRINTED_ACCOUNTS if redact_for_cli_output(printed) != printed)

    assert removed == len(PRINTED_ACCOUNTS), "the funnel removed nothing; the negative half is measuring nothing"
