"""A word standing beside a tax identity must not carry it through the funnel.

Every shipped case in the sibling suites wraps its value as
``counterparty <value> declared`` or passes it as a lone token. Both neighbours
are long words there, and a lone token has no neighbour at all, so **no case in
the suite could reach the defect this module measures** -- the harness was not
weak, it was shaped so the failure was unreachable. Ordinary Spanish operator
prose puts short words beside identifiers constantly (``es``, ``de``, ``en``,
``y``, ``la``, ``el``), and that is the shape a producer emits.

Two mechanisms are covered, and both are SCAN-time rather than gate-time, which
is why four review passes over the gates found neither.

**The neighbour swallow.** The prefixed arm admits a space as an internal
separator, so the greedy scan joins the adjacent word to the number:
``ESB12345674 is`` in one direction and ``de SE556677889901`` in the other. The
joined span normalises to nothing any authority recognises, so the gate refuses
it *correctly* -- and the identity, already inside a consumed span, is never
asked about again. Both constraints the module cites for admitting the space
(the letters must name a Member State; the per-State table must accept the
number) are gate-time and cannot prevent this.

**The dotted bare form.** The CIF scan admits a dot between body characters
while ``validate_identity`` strips only spaces and hyphens, so ``B.1234567.4``
matched the scan and was refused by the gate. The codebase already had the
answer: ``same_tax_identifier`` compares on ``normalise_nif_iva`` and reports
the dotted and the compact spelling as one bearer. The canonical same-bearer
predicate said yes while the confidentiality funnel said no.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ..identity import normalise_nif_iva, same_tax_identifier
from ..redaction.rules import redact_for_cli_output, redact_for_log

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FUNNELS: list[Callable[[str], str]] = [redact_for_cli_output, redact_for_log]

#: ``(sentence, identity, surviving fragments)``. Each sentence is prose a
#: producer emits, with the identity pressed against short words on one or both
#: sides. The surviving fragments are the load-bearing half: an over-wide fix
#: that ate the neighbour would satisfy "the identity is gone" and still corrupt
#: the operator's sentence.
IDENTITY_BESIDE_A_SHORT_WORD = [
    ("counterparty ESB12345674 is declared", "ESB12345674", ["counterparty ", " is declared"]),
    ("NIF ESB12345674 en factura", "ESB12345674", ["NIF ", " en factura"]),
    ("el ESB12345674 y la factura", "ESB12345674", ["el ", " y la factura"]),
    ("es ESB12345674 la contraparte", "ESB12345674", ["es ", " la contraparte"]),
    ("de SE556677889901 y otros", "SE556677889901", ["de ", " y otros"]),
    ("en DE811234567 es", "DE811234567", ["en ", " es"]),
    ("la B.1234567.4 en el registro", "B.1234567.4", ["la ", " en el registro"]),
    ("de B-1234567-4 y", "B-1234567-4", ["de ", " y"]),
    ("es 12345678Z en", "12345678Z", ["es ", " en"]),
]

#: Two identities in one line, each with short neighbours. A fix that recovers
#: only the first reading of a refused span passes every single-identity case.
TWO_IDENTITIES_IN_ONE_LINE = "de SE556677889901 y DE811234567 en la factura"

#: Printed spellings of ONE bearer that the funnel must treat alike. The dotted
#: entries are the leak: ``same_tax_identifier`` folds them onto the compact
#: form, and the funnel did not.
SAME_BEARER_SPELLINGS = [
    ("B12345674", "B.1234567.4"),
    ("B12345674", "B-1234567-4"),
    ("ESB12345674", "ESB.1234567.4"),
    ("12345678Z", "12.345.678.Z"),
]

#: Operator text that must reach the operator intact. The first block is the
#: shape the neighbour-swallow fix is most likely to break: ordinary words that
#: BEGIN with a Member State prefix, which the prefixed scan reads as a country
#: code, plus short function words in the positions the corpus above exercises.
ORDINARY_OPERATOR_PROSE = [
    "DEudor principal",
    "ESpecial de la factura",
    "PTolomeo y asociados",
    "ATencion al contribuyente",
    "ITinerario de la solicitud",
    "es de la factura y en el registro",
    "la factura es de 2026 y no de 2025",
    "SE-2026-000412 es la serie",
    "de F-2026-0142 y de INV-001",
    "el modelo 303 es de 2026",
    "A 2020-2024",
    "meghaladja a 6 000 000-t",
    "casilla-303 en el modelo",
    "aeat app ledger evidence extract",
    "no-such-thing es la respuesta",
    "Total factura 1.234,56 EUR en el registro",
    "BOE-A-2026-12345 es la referencia",
]


@pytest.mark.parametrize(("sentence", "identity", "survivors"), IDENTITY_BESIDE_A_SHORT_WORD)
@pytest.mark.parametrize("funnel", _FUNNELS)
def test_a_short_neighbouring_word_does_not_carry_an_identity_through(
    sentence: str,
    identity: str,
    survivors: list[str],
    funnel: Callable[[str], str],
) -> None:
    """The leak, on both funnels, in both directions."""
    redacted = funnel(sentence)

    assert identity not in redacted, f"{identity!r} reached the operator inside {redacted!r}"
    assert "sha256:" in redacted, "nothing was hashed; the identity was removed some other way"
    for fragment in survivors:
        assert fragment in redacted, f"the fix ate operator text: {fragment!r} is missing from {redacted!r}"


@pytest.mark.parametrize("funnel", _FUNNELS)
def test_every_identity_on_a_line_is_recovered_not_just_the_first(funnel: Callable[[str], str]) -> None:
    """A refused span may hide more than one reading, and both must be reached."""
    redacted = funnel(TWO_IDENTITIES_IN_ONE_LINE)

    assert "SE556677889901" not in redacted
    assert "DE811234567" not in redacted
    assert redacted.count("sha256:") == 2, redacted
    assert redacted.startswith("de "), redacted
    assert redacted.endswith(" en la factura"), redacted


@pytest.mark.parametrize(("compact", "printed"), SAME_BEARER_SPELLINGS)
def test_the_funnel_agrees_with_the_canonical_same_bearer_predicate(compact: str, printed: str) -> None:
    """The codebase already answered this; the funnel must not contradict it.

    ``same_tax_identifier`` is the one "is this the same identifier" predicate
    in this tree and it compares on ``normalise_nif_iva``. Asking it here rather
    than asserting a hand-picked pair is what keeps this case honest: if the
    predicate ever stops folding the two spellings together, the premise is gone
    and this case must fail rather than quietly assert a coincidence.
    """
    assert printed != compact, "the pair must actually differ in its printed form"
    assert same_tax_identifier(compact, printed), (
        f"{printed!r} and {compact!r} are not the same bearer; this pair proves nothing"
    )
    assert redact_for_cli_output(compact) != compact, "the compact spelling must already redact"
    assert redact_for_cli_output(printed) != printed, (
        f"the funnel emitted {printed!r} raw while same_tax_identifier calls it the same bearer as {compact!r}"
    )


@pytest.mark.parametrize("text", ORDINARY_OPERATOR_PROSE)
@pytest.mark.parametrize("funnel", _FUNNELS)
def test_ordinary_operator_prose_survives_untouched(text: str, funnel: Callable[[str], str]) -> None:
    """The bound. Re-reading a refused span widens what the gates are ASKED.

    The gates still decide, but they are now consulted on sub-spans a greedy
    scan previously hid, so the over-redaction direction has to be measured
    rather than assumed. Words beginning with a Member State prefix are the
    sharp cases: the scan reads ``DEudor`` as a country code and a body.
    """
    assert funnel(text) == text, f"{text!r} was rewritten to {funnel(text)!r}"


def test_the_negative_corpus_is_not_vacuous() -> None:
    """Every case above asserts an ABSENCE, so the funnel must be proven live.

    Disabling redaction wholesale would red the positive cases but leave the
    whole negative half passing in silence, which reads as green.
    """
    removed = sum(1 for _, identity, _ in IDENTITY_BESIDE_A_SHORT_WORD if redact_for_cli_output(identity) != identity)

    assert removed == len(IDENTITY_BESIDE_A_SHORT_WORD), (
        "the funnel redacted nothing in isolation; the negative half is measuring nothing"
    )


def test_a_refused_span_stays_refused_when_it_hides_no_identity() -> None:
    """Re-reading a refused span must not become "keep trying until something sticks".

    A string whose every sub-reading the gates reject has to come through
    verbatim. This is what separates the mechanism shipped here from simply
    widening the scan.
    """
    lookalike = "de B.1234567.9 y ESB99999999 en"

    assert normalise_nif_iva("B.1234567.9") == "B12345679"
    assert redact_for_cli_output(lookalike) == lookalike
    assert redact_for_log(lookalike) == lookalike
