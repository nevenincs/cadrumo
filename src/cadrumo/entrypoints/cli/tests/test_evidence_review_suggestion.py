"""The extract review hint must be executable as printed, not merely correct.

A Notice `suggestion` is an instruction the operator is expected to run, and
it is also a string emitted into a JSON envelope that may be pasted into an
issue or a log. Both are true at once, so the suggestion travels through the
same redaction funnel as the rest of the envelope -- and a tax identity stays
redacted there even under `reveal_identifiers`, which is the operator opt-out
for opaque profile ids and deliberately does not extend to tax identities.

The hint used to embed the extracted supplier NIF. For a natural-person
supplier -- an autónomo, which is most freelance invoices -- the operator was
handed `--counterparty-nif sha256:1c9f9632` to paste. It failed exactly where
it was most needed and kept working for companies, so the common path was
broken and the uncommon one hid it.

`test_suggestion_command_conformance` already proves a cited command EXISTS.
Nothing proved a cited command SURVIVES the funnel, which is the half these
cases add: a verb that resolves is not usable if its arguments come out
hashed.
"""

from __future__ import annotations

import pytest

from ....core.hashing import content_hash_hex
from ....core.redaction import redact_for_cli_output
from .._ledger_evidence_cli import extract_review_suggestion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REFERENCE = content_hash_hex({"evidence": "sample"})[:16]
#: A real natural-person NIF shape. The checksum letter is not what matters
#: here -- the redaction funnel keys on the shape, and this is the shape an
#: autónomo supplier's tax id has.
_NATURAL_PERSON_NIF = "12345678Z"


@pytest.mark.parametrize("evidence_id", [_REFERENCE, None])
def test_the_hint_is_executable_as_printed(evidence_id: str | None) -> None:
    """The emitted suggestion must survive redaction unchanged.

    Both reference branches are covered because the extract command accepts
    either an evidence id or an attachment id, and a suggestion that is
    pasteable for one and not the other is broken for half its callers.
    """
    suggestion = extract_review_suggestion(evidence_id=evidence_id, reference=_REFERENCE)

    assert redact_for_cli_output(suggestion) == suggestion


def test_the_hint_carries_the_reference_the_operator_needs() -> None:
    """Naming the stored draft is what replaces the embedded values.

    Without the reference surviving, the suggestion would be pasteable and
    useless -- which is the failure this fix could have traded for.
    """
    suggestion = extract_review_suggestion(evidence_id=_REFERENCE, reference=_REFERENCE)

    assert _REFERENCE in redact_for_cli_output(suggestion)
    assert "evidence confirm" in suggestion


def test_the_hint_embeds_no_extracted_identifier() -> None:
    """The property that keeps it pasteable, asserted as an absence.

    Stated separately from the redaction check because the two can drift: a
    future edit could add an identifier the funnel does not yet redact, which
    would pass the stability check today and break the moment that shape is
    enrolled -- the IBAN work is exactly such an enrolment in flight.
    """
    suggestion = extract_review_suggestion(evidence_id=_REFERENCE, reference=_REFERENCE)

    assert "--counterparty-nif" not in suggestion


def test_the_funnel_really_would_break_an_embedded_nif() -> None:
    """Anti-tautology: prove the assertion above can fail.

    Without this, `redact(suggestion) == suggestion` passes for any string
    the funnel happens not to touch, and would keep passing if the funnel
    itself were disabled. This reconstructs the shape the hint used to emit
    and shows the redaction it produced, so the guard is measured against a
    real failing input rather than assumed.
    """
    old_shape = f"aeat app ledger invoice add --kind received --counterparty-nif {_NATURAL_PERSON_NIF}"

    redacted = redact_for_cli_output(old_shape)

    assert redacted != old_shape
    assert _NATURAL_PERSON_NIF not in redacted


def test_revealing_identifiers_would_not_have_fixed_it() -> None:
    """The obvious fix does not work, and that is worth pinning.

    `reveal_identifiers=True` is the operator opt-out for opaque profile and
    bucket ids; tax identities stay redacted regardless. A future reader
    reaching for that flag to re-embed the NIF should meet this case rather
    than discover it in production.
    """
    old_shape = f"--counterparty-nif {_NATURAL_PERSON_NIF}"

    assert redact_for_cli_output(old_shape, reveal_identifiers=True) != old_shape
