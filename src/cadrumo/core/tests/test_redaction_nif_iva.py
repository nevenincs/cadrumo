"""The prefixed spelling of a tax identity must not survive the funnel either.

The two shipped tax-identity rules anchor on ``\\b``, and an IVA country prefix is
a word character, so a prefixed identifier presents no boundary before the body
and neither rule fires. Measured before this arm existed: ``B12345674`` redacted
to a digest while ``ESB12345674`` -- the SAME taxpayer, in the spelling this
app's own structured readers recover and its own parsers emit -- passed through
raw, on operator output and log lines alike. It was reaching real envelopes: a
confirming intra-community document emitted its counterparty's identifier
verbatim inside a notice context, exit code 0.

**The gate is the property, not a list of countries.** Enumerating today's
Member States here would pin the vocabulary the way a fixture once pinned a
country and stopped testing anything when the table moved. So the cases below
ask the shipped identity authorities what an IVA number IS and assert that
whatever they recognise does not survive redaction --- the same shape as the
IBAN arm, which admits on the checksum rather than on the look of the string.

**Both directions are asserted, and the negative half is the load-bearing one.**
The scan is deliberately wide (two letters plus an alphanumeric run collides with
hashes, opaque ids and document references), so a rule that simply hashed
everything it matched would pass every positive case here while destroying
ordinary output. Each negative below is a string that must reach the operator
intact.

See Also:
    :attr:`~core.classification.RedactionStrategy.SHA256_PREFIX_IF_NIF_IVA`
        The strategy whose admission rule these cases pin.
"""

from __future__ import annotations

import pytest

from ..identity import NIF_IVA_FORMATS, IdentityError, validate_identity
from ..redaction.rules import redact_for_cli_output, redact_for_log

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REDACTED_MARKER = "sha256:"

# One real number per shipped Member State format, taken from the format spec's
# OWN declared example rather than authored here. A State added to the table
# joins these cases on the day it is declared, and an example that stops
# matching its own pattern is the table's defect rather than this file's.
_SHIPPED_EXAMPLES = tuple(sorted((prefix, spec.example) for prefix, spec in NIF_IVA_FORMATS.items()))

# The Spanish prefixed spelling, which is absent from the IVA format table
# because Spain's own identities belong to the AEAT control-character authority.
# It is the case the whole arm exists for and it must be stated explicitly.
_ES_PREFIXED = "ESB12345674"
_ES_BARE = "B12345674"


def _redacts(value: str) -> bool:
    """Return whether both operator-facing funnels remove *value*.

    Both, because they are separate entry points over the same rule set and a
    leak on either is a leak: the CLI funnel governs what an operator is shown
    and the log funnel governs what lands on disk.
    """
    line = f"counterparty {value} declared"
    cli = redact_for_cli_output(line)
    log = redact_for_log(line)
    assert (value in cli) == (value in log), f"the two funnels disagree about {value!r}"
    return _REDACTED_MARKER in cli and value not in cli


def test_the_shipped_example_corpus_is_populated() -> None:
    """A zero-length corpus would make every case below pass vacuously."""
    assert len(_SHIPPED_EXAMPLES) >= 20, _SHIPPED_EXAMPLES


@pytest.mark.parametrize(("prefix", "example"), _SHIPPED_EXAMPLES)
def test_every_shipped_member_state_number_is_redacted(prefix: str, example: str) -> None:
    """Whatever the IVA format table recognises must not reach an operator."""
    assert _redacts(example), f"{prefix} example {example!r} survived the funnel"


def test_the_spanish_prefixed_spelling_is_redacted_like_its_bare_form() -> None:
    """The case the arm exists for: one taxpayer, two spellings, one treatment.

    Asserted as a PAIR rather than alone. The bare form was already redacted, so
    a case naming only the prefixed one would not show that the funnel had been
    treating two spellings of a single identity differently.
    """
    assert _redacts(_ES_BARE)
    assert _redacts(_ES_PREFIXED)


def test_a_prefixed_spanish_identifier_failing_its_check_character_is_not_an_identity() -> None:
    """The ES arm admits on the AEAT check character, not on the prefix.

    The prefix is a claim. If it were the evidence, every ``ES``-led token in
    ordinary output would be hashed, and the operator would lose readable text
    to protect a value that was never an identity.
    """
    with pytest.raises(IdentityError):
        validate_identity("B99999999")

    assert not _redacts("ESB99999999")


@pytest.mark.parametrize(
    "ordinary",
    [
        "INVOICE2026",
        "XX12345678",
        "Factura",
        "DE00",
        "REF20260311",
        "ES",
        "SHA256ABCDEF12",
    ],
)
def test_ordinary_output_survives_the_wide_scan(ordinary: str) -> None:
    """The negative half: a wide scan admitted by a strict gate, not a hash-all.

    Each of these matches the scanning shape and none is an IVA number. A rule
    that hashed on the shape would pass every positive case above and quietly
    destroy the operator's readable output, which is the failure a positives-only
    suite cannot see.
    """
    assert not _redacts(ordinary), f"{ordinary!r} is not a tax identity and must reach the operator"


def test_a_prefix_naming_no_member_state_admits_nothing() -> None:
    """An unassigned prefix has no structure to match, so it cannot be admitted."""
    assert "XX" not in NIF_IVA_FORMATS
    assert not _redacts("XX123456789")
