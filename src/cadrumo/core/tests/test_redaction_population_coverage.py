"""The funnel runs over four populations, and a corpus drawn from one proves little.

Every measurement that has cleared a change to this funnel was built from one
population -- the shipped locale catalogues -- and three separate defects have
now shipped past a sound measurement of it. A serialised UTC timestamp is not a
locale string. A decimal-bearing structured payload is not a locale string.
Operator prose describing where on a page a value was printed, carried inside a
structured result payload, is not a locale string either. Each is a population
the funnel genuinely runs over, and each was invisible to the corpus that
cleared the change before it.

The four production entry points, and what reaches each:

* the CLI success envelope, which routes every payload through
  ``redact_structured_for_cli_output`` -- structured result data mixing
  identities, digests and operator prose;
* log lines and error-registry context, through ``redact_for_log`` -- exception
  text with interpolated operator input;
* the observability sink and store, which redact ``model_dump(mode="json")``
  output -- serialised records carrying ISO-8601 instants;
* the LLM cache and usage records, likewise serialised -- decimal-bearing
  payloads.

The last case in this module is the general form of all of them: rather than
enumerating strings that must survive, it recovers every span the funnel hashed
and asks the canonical authorities whether that span really was an identity or
an account. That property does not depend on guessing which population the next
defect will come from.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest

from ..iban import IBAN_SHAPE_RE, iban_mod_97, normalise_iban
from ..classification import RedactionRule, SensitivityClass
from ..hashing import sha256_hex
from ..identity import IdentityError, nif_iva_format_for_country, normalise_nif_iva, validate_identity
from ..redaction import (
    _NIF_PATTERN,
    default_rules_for_class,
    redact_for_cli_output,
    redact_for_log,
    redact_structured,
    redact_structured_for_cli_output,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FUNNELS: list[Callable[[str], str]] = [redact_for_cli_output, redact_for_log]

_DIGEST_RE = re.compile(r"sha256:([0-9a-f]{8})")

#: A real Spanish company identity and its printed spellings, plus a real
#: account. Used across the populations below so one corpus entry cannot drift
#: from another.
_IDENTITY = "ESB12345674"
_SECOND_IDENTITY = "ESX1234567L"
_ACCOUNT = "ES91 2100 0418 4502 0005 1332"

#: An adversarial corpus spanning all four populations. Entries are short so the
#: span-recovery in the soundness case stays cheap; the property it proves does
#: not depend on length.
MIXED_POPULATION_CORPUS = [
    # prose with short neighbours
    "counterparty ESB12345674 is declared",
    "de SE556677889901 y DE811234567",
    "la B.1234567.4 en el registro",
    "es 12345678Z en",
    # printed accounts
    "cuenta ES91 2100 0418 4502 0005 1332 declarada",
    "IBAN ES91-2100-0418-4502-0005-1332 EN FACTURA",
    # serialised instants
    "2026-01-02T09:32:12.345678Z",
    "observed_at=2026-01-02T09:32:12.345678Z status=FILED",
    "2026-01-02 09:32:12+02:00",
    # decimal-bearing payload text
    "base 1234.56 cuota 259.26 total 1493.82",
    "importe -1.234,56 EUR saldo 0.00",
    # operator prose from structured result payloads
    "printed under 'Proveedor'",
    "printed under 'Cliente'",
    "two verified identifiers remained and no role evidence picks exactly one",
    # producer-shaped noise
    "DEudor ESpecial PTolomeo ATencion",
    "BOE-A-2026-12345 y SE-2026-000412",
    "MODELO 303 EJERCICIO 2026 PERIODO 1T",
]


def _diagnostic_rules() -> tuple[RedactionRule, ...]:
    return default_rules_for_class(SensitivityClass.DIAGNOSTIC)


def test_a_serialised_instant_survives_the_structured_funnel() -> None:
    """The population a locale catalogue cannot contain.

    The fractional-second field of an ISO-8601 instant is seven digits with
    separators and a trailing letter, which is a NIF -- and ``12345678Z`` even
    carries a valid check character, so validating the match cannot tell the two
    apart. A rewritten stamp no longer parses, so the record that carries it is
    refused on the way to storage.
    """
    record = {
        "observed_at": "2026-01-02T09:32:12.345678Z",
        "recorded_at": "2026-01-02 09:32:12+02:00",
        "counterparty_tax_id": _IDENTITY,
        "status": "FILED",
    }

    redacted = redact_structured(record, rules=_diagnostic_rules())

    assert isinstance(redacted, dict)
    assert redacted["observed_at"] == "2026-01-02T09:32:12.345678Z"
    assert redacted["recorded_at"] == "2026-01-02 09:32:12+02:00"
    assert redacted["status"] == "FILED"
    assert redacted["counterparty_tax_id"] != _IDENTITY, "the identity beside the stamps was not redacted"


def test_a_decimal_bearing_payload_survives_the_structured_funnel() -> None:
    """Money is not an identity, and a redacted amount is a corrupted record."""
    payload = {
        "base_imponible": "1234.56",
        "cuota": "259.26",
        "total": "1493.82",
        "saldo": "-1.234,56",
        "counterparty_tax_id": _IDENTITY,
    }

    redacted = redact_structured(payload, rules=_diagnostic_rules())

    assert isinstance(redacted, dict)
    for field in ("base_imponible", "cuota", "total", "saldo"):
        assert redacted[field] == payload[field], f"{field} was rewritten to {redacted[field]!r}"
    assert redacted["counterparty_tax_id"] != _IDENTITY


def test_an_ambiguity_candidate_note_survives_while_its_value_is_hashed() -> None:
    """The note is what lets an operator tell two competing readings apart.

    An ambiguity-candidates payload adjudicates between two readings of one
    identity. Both ``value`` and ``anchor`` hash, correctly -- and once they
    have, the note describing WHERE on the page each candidate was printed is
    the only thing distinguishing the rows. A funnel that widened onto the note
    would take adjudication away silently: no error, no refusal, just an
    operator who can no longer choose.

    The note content is chosen for the risk rather than for readability. It
    carries a quoted Spanish word and a capitalised token, which is the shape a
    widening scan reaches for; bland English prose would not exercise it.
    """
    payload = {
        "candidates": [
            {"value": _IDENTITY, "anchor": _IDENTITY, "note": "printed under 'Proveedor'"},
            {"value": _SECOND_IDENTITY, "anchor": _SECOND_IDENTITY, "note": "printed under 'Cliente'"},
        ],
        "note": "two verified identifiers remained and no role evidence picks exactly one",
    }

    redacted = redact_structured_for_cli_output(payload)

    assert isinstance(redacted, dict)
    candidates = redacted["candidates"]
    assert isinstance(candidates, list), f"the candidate rows did not survive as a list: {candidates!r}"
    assert [candidate["note"] for candidate in candidates] == [
        "printed under 'Proveedor'",
        "printed under 'Cliente'",
    ], "the note was rewritten; the operator can no longer tell the candidates apart"
    assert redacted["note"] == payload["note"]

    values = [candidate["value"] for candidate in candidates]
    assert all(value.startswith("sha256:") for value in values), values
    assert values[0] != values[1], "two distinct bearers collapsed onto one digest"


def _recover_hashed_spans(source: str, digest: str) -> set[str]:
    """Return every substring of ``source`` whose digest prefix is ``digest``.

    The funnel hashes the span it replaced, so the span is recoverable from its
    own digest with no ambiguity. That is what makes the soundness case below a
    real property rather than a restatement of the corpus: nothing here consults
    the redaction module's internals or its patterns.
    """
    return {
        source[start:stop]
        for start in range(len(source))
        for stop in range(start + 1, len(source) + 1)
        if sha256_hex(source[start:stop].encode("utf-8"))[:8] == digest
    }


def _admitting_authority(span: str) -> str | None:
    """Name the authority that accepts ``span``, or ``None`` if none does."""
    normalised = normalise_nif_iva(span)
    candidates = [normalised]
    if normalised[:2] == "ES":
        candidates.append(normalised[2:])
    for candidate in candidates:
        try:
            validate_identity(candidate)
        except IdentityError:
            continue
        return "identity"
    spec = nif_iva_format_for_country(normalised[:2])
    if spec is not None and spec.pattern.match(normalised):
        return "nif-iva"
    canonical = normalise_iban(span)
    if IBAN_SHAPE_RE.match(canonical) and iban_mod_97(canonical) == 1:
        return "iban"
    if re.fullmatch(_NIF_PATTERN, span):
        # The personal-identity arm is ungated BY DESIGN: it matches on shape
        # alone and hashes a lookalike rather than risk missing a mistyped
        # identity. A span it accepts is therefore not evidence of over-firing.
        return "shape-arm"
    return None


@pytest.mark.parametrize("source", MIXED_POPULATION_CORPUS)
@pytest.mark.parametrize("funnel", _FUNNELS)
def test_every_hashed_span_is_a_real_identity_or_account(source: str, funnel: Callable[[str], str]) -> None:
    """Soundness: the funnel hashes nothing the authorities do not recognise.

    The gated arms are a wide scan admitted by a strict gate, and a refused span
    is re-read rather than spent, so the gates are consulted on more readings of
    a string than a single greedy match would produce. That widens what is
    ASKED, and the direction it could go wrong is over-firing -- hashing a span
    no authority accepts.

    Enumerating strings that must survive cannot bound that, because it only
    ever covers the population the author thought of. This case bounds it from
    the other side: whatever the funnel hashed, recover it and make the
    authorities themselves rule on it.
    """
    redacted = funnel(source)

    for digest in _DIGEST_RE.findall(redacted):
        spans = _recover_hashed_spans(source, digest)
        assert spans, f"digest {digest} in {redacted!r} matches no substring of {source!r}"
        authorities = {span: _admitting_authority(span) for span in spans}
        assert any(authorities.values()), (
            f"the funnel hashed {sorted(spans)!r} out of {source!r}, and no authority accepts any of them"
        )


def test_the_soundness_corpus_actually_exercises_the_funnel() -> None:
    """A property over spans proves nothing if no span was ever hashed.

    The case above quantifies over the digests in the output. A funnel that
    redacted nothing at all would produce no digests, satisfy every assertion
    vacuously, and read as green.
    """
    hashed = sum(1 for source in MIXED_POPULATION_CORPUS if _DIGEST_RE.search(redact_for_cli_output(source)))

    assert hashed >= 6, f"only {hashed} corpus entries produced a digest; the property is running on nothing"
