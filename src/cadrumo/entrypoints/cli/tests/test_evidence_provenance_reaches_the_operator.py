"""Provenance REACHES the operator: the real command, the real emitted envelope.

The schema-level gate proves the evidence payloads *can* carry provenance. It
cannot prove either command *populates* it, because it validates a payload the
test itself assembles -- so a projection that silently stopped stamping
envelopes leaves that gate green. Reachability is a different claim from
capability, and only a run of the real command can make it.

Every case here drives the real Typer tree against a real encrypted bucket and
the bundled structured document, and reads the envelopes out of the emitted
JSON. **Nothing in this module builds a payload.** A hand-assembled payload
would reproduce exactly the gate this one exists to complement.

The document is deliberately the STRUCTURED e-invoice: that reader is
deterministic and needs no model and no network, so this gate cannot rot into
an environment-dependent failure the way a reading-model path does.

**Why the extract surface is not asserted here, deliberately.** At the time of
writing the structured reader stamps no envelopes, so ``extract`` emits an empty
``provenance`` list on this path -- measured through the real command, not
inferred. Asserting that emptiness would encode a live gap as the contract
behind a name that reads like grounding coverage, which is worse than leaving it
uncovered; and the reading-model path that does populate it cannot run
model-free. So the extract surface stays uncovered ON PURPOSE and is named here
rather than silently omitted. When the structured reader stamps
``EXACT_STRUCTURED`` envelopes, the extract case belongs in this module.

What IS reachable end to end today is the confirm surface's
``confirmed_provenance``: an operator's override at confirm produces an envelope
whatever the reading path recorded, so this module gates that, which is the half
of the claim the tree can currently honour.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ._ledger_ux_support import _invoke, _open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The in-repo corpus, shared with the application-layer tests. Deliberately
#: in-repo: a durable gate must not depend on a tree outside the repository,
#: which would rot into a silent skip.
_EVIDENCE_CORPUS = Path(__file__).parents[3] / "application" / "ledger" / "tests" / "_evidence_corpus"

_STRUCTURED_INVOICE = "facturae_32_series_and_parties_invoice.xml"

#: What the structured reader recovers from the bundled document, so an override
#: below is provably a DISPLACEMENT of a read value rather than a fill of a blank.
_READ_INVOICE_NUMBER = "0031"


@pytest.fixture(autouse=True)
def _open_bucket_session(tmp_path: Path) -> Iterator[None]:
    with _open_ledger_ux_session(tmp_path):
        yield


def _add_structured_evidence(tmp_path: Path) -> str:
    staged = tmp_path / _STRUCTURED_INVOICE
    staged.write_bytes((_EVIDENCE_CORPUS / _STRUCTURED_INVOICE).read_bytes())

    added = _invoke(["--format", "json", "app", "ledger", "evidence", "add", str(staged)])
    assert added.exit_code == 0, added.output
    return str(json.loads(added.output)["result"]["evidence_id"])


def _confirm(evidence_id: str, *overrides: str) -> dict[str, Any]:
    """Drive the real confirm command and return its emitted result body."""
    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            *overrides,
        ],
    )  # fmt: skip
    assert confirmed.exit_code == 0, confirmed.output
    body: dict[str, Any] = json.loads(confirmed.output)["result"]
    return body


def test_an_operator_override_reaches_the_confirm_envelope_as_provenance(tmp_path: Path) -> None:
    """The whole claim: a correction is visible to the operator as an assertion.

    Asserts the envelope's CONTENT, not merely that a list is non-empty. A
    ``confirmed_provenance`` carrying field names with the origin and grounding
    stripped would satisfy a shallower check while losing exactly what makes an
    operator's figure distinguishable from a value read off the document.
    """
    evidence_id = _add_structured_evidence(tmp_path)

    result = _confirm(evidence_id, "--invoice-number", "OVERRIDDEN-0031")

    assert result["invoice_number"] == "OVERRIDDEN-0031"
    envelopes = {envelope["field"]: envelope for envelope in result["confirmed_provenance"]}
    assert "invoice_number" in envelopes, f"the override left no provenance: {result['confirmed_provenance']}"

    stamped = envelopes["invoice_number"]
    assert stamped["origin"] == "operator"
    # Never ANCHORED: an operator's value is not a reading of the document, so
    # there is no verbatim occurrence to anchor it to. Stamping one would
    # launder an assertion into a corroborated reading, which is the single
    # most consequential thing this envelope prevents.
    assert stamped["grounding"] == "unanchored"
    assert stamped["anchor"] is None
    assert stamped["anchor_self_reported"] is False
    # The displaced reading survives in the note, so the operator can see WHAT
    # their correction replaced rather than only that they corrected something.
    assert _READ_INVOICE_NUMBER in stamped["note"]


def test_a_field_the_operator_left_alone_is_not_stamped_as_asserted(tmp_path: Path) -> None:
    """The discriminating half: stamping must track the override, not the call.

    Without this, a confirm path that stamped every field ``OPERATOR`` on every
    call would pass the case above while telling every downstream consumer the
    operator had personally asserted values they never saw.
    """
    evidence_id = _add_structured_evidence(tmp_path)

    result = _confirm(evidence_id, "--invoice-number", "OVERRIDDEN-0031")

    stamped_fields = {envelope["field"] for envelope in result["confirmed_provenance"]}
    assert "invoice_number" in stamped_fields
    assert "taxable_base" not in stamped_fields, f"an untouched field was stamped as asserted: {stamped_fields}"
    assert "grand_total" not in stamped_fields, f"an untouched field was stamped as asserted: {stamped_fields}"


def test_a_confirm_with_no_override_asserts_nothing(tmp_path: Path) -> None:
    """No correction, no assertion: the channel stays empty rather than inventing one.

    The other direction of the same property. An empty
    ``confirmed_provenance`` here is not a gap -- it is the honest report that
    the operator asserted nothing on this call.
    """
    evidence_id = _add_structured_evidence(tmp_path)

    result = _confirm(evidence_id)

    operator_stamped = [e for e in result["confirmed_provenance"] if e["origin"] == "operator"]
    assert not operator_stamped, f"a confirm with no override manufactured assertions: {operator_stamped}"


def test_every_confirm_carries_a_confirmation_id(tmp_path: Path) -> None:
    """The envelope is addressable: provenance without an id cannot be cited later."""
    evidence_id = _add_structured_evidence(tmp_path)

    result = _confirm(evidence_id, "--invoice-number", "OVERRIDDEN-0031")

    assert result["confirmation_id"]
    assert len(result["confirmation_id"]) == 16
