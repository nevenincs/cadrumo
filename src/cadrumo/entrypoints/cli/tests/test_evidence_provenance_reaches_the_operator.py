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
from pathlib import Path
from typing import Any

import pytest

from .ledger_ux_support import _invoke, _open_bucket_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]

#: The in-repo corpus, shared with the application-layer tests. Deliberately
#: in-repo: a durable gate must not depend on a tree outside the repository,
#: which would rot into a silent skip.
_EVIDENCE_CORPUS = Path(__file__).parents[3] / "application" / "ledger" / "tests" / "_evidence_corpus"

_STRUCTURED_INVOICE = "facturae_32_series_and_parties_invoice.xml"

#: What the structured reader recovers from the bundled document, so an override
#: below is provably a DISPLACEMENT of a read value rather than a fill of a blank.
_READ_INVOICE_NUMBER = "0031"


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


# ---------------------------------------------------------------------------
# Discrepancies, on the same terms: run the command, read the emitted body
# ---------------------------------------------------------------------------
#
# The provenance cases above prove the how-was-this-obtained record reaches the
# operator. These prove the other half of the envelope does: a document that
# disagrees with itself has to SAY so where the operator is looking, and a
# finding that exists only in the application layer is a finding they never see.
#
# Reachable on this path only since the structured reader began running the
# deterministic checks. Before that a structured document produced no findings at
# all, so a case here would have asserted an emptiness that was a live defect
# rather than a contract.


def _add_edited_structured_evidence(tmp_path: Path, *, old: str, new: str, name: str) -> str:
    """Store a copy of the corpus invoice with one edit, and return its id.

    The corpus tree is never written to: the edit is applied to a copy staged in
    ``tmp_path``. The replacement is asserted to have matched, so a corpus change
    that moves the edited text fails loudly instead of silently storing an
    unedited document and passing whichever assertion happened to be lenient.
    """
    xml = (_EVIDENCE_CORPUS / _STRUCTURED_INVOICE).read_text(encoding="utf-8")
    assert old in xml, f"corpus no longer contains {old!r}; this edit would be a no-op"

    staged = tmp_path / name
    staged.write_text(xml.replace(old, new, 1), encoding="utf-8")

    added = _invoke(["--format", "json", "app", "ledger", "evidence", "add", str(staged)])
    assert added.exit_code == 0, added.output
    return str(json.loads(added.output)["result"]["evidence_id"])


def _extract(evidence_id: str) -> dict[str, Any]:
    """Drive the real extract command and return its emitted result body."""
    extracted = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "extract", "--evidence-id", evidence_id],
    )
    assert extracted.exit_code == 0, extracted.output
    body: dict[str, Any] = json.loads(extracted.output)["result"]
    return body


def test_off_host_extract_preserves_the_consent_precondition_envelope(tmp_path: Path) -> None:
    """A real extract refusal keeps the LLM-owned verdict through the CLI boundary."""
    evidence_id = _add_structured_evidence(tmp_path)

    refused = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "evidence",
            "extract",
            "--evidence-id",
            evidence_id,
            "--off-host-provider",
            "OPENAI",
            "--acknowledge-off-host",
        ],
        env={"CADRUMO_EVIDENCE_CLOUD_UPLOAD_PERMITTED": "false"},
    )

    assert refused.exit_code != 0, refused.output
    document = json.loads(next(line for line in refused.output.splitlines() if line.startswith("{")))
    error = document["error"]
    assert error["code"] != "REFUSED_CLI_BOUNDARY", refused.output
    action = error["action"]
    assert action["failed_condition_id"] == "llm.evidence.off_host_dispatch_permitted"
    assert action["action"] is None
    assert action["conditionality"] == "not_applicable"
    assert action["no_recovery_outcome"] == "operator_decision"
    assert action["evidence"] == [
        {
            "condition_id": "llm.evidence.off_host_dispatch_permitted",
            "evidence_id": "llm.evidence.off_host_dispatch_permitted.observation",
            "provenance": "application_state",
            "values": {
                "acknowledged": True,
                "deployment_permitted": False,
                "gestor_mode": False,
                "profile_eligible": False,
            },
        }
    ]


def test_the_coherent_document_extracts_with_no_discrepancies(tmp_path: Path) -> None:
    """The positive control, and it is what makes the two cases below mean anything.

    Both of those pass equally against a path that flags every document. This one
    also proves the newly-reachable arithmetic identities do not false-fire on
    exactly-read values, which is the risk of running them over a reader that was
    previously exempt.
    """
    body = _extract(_add_structured_evidence(tmp_path))

    assert body["discrepancies"] == []
    # The read genuinely worked: an empty list from a failed read would satisfy
    # the assertion above while proving nothing.
    assert body["grand_total"] is not None


def test_an_arithmetic_disagreement_reaches_the_extract_envelope(tmp_path: Path) -> None:
    """A document whose own figures do not close says so to the operator."""
    evidence_id = _add_edited_structured_evidence(
        tmp_path,
        old="<InvoiceTotal>242.00</InvoiceTotal>",
        new="<InvoiceTotal>999.00</InvoiceTotal>",
        name="broken-total.xml",
    )

    body = _extract(evidence_id)

    kinds = [finding["kind"] for finding in body["discrepancies"]]
    assert "arithmetic_closure" in kinds, f"the emitted envelope carried no closure finding: {body['discrepancies']}"
    # The detail travels too. A kind with no explanation tells an operator that
    # something is wrong and nothing about what, which is the difference between
    # a finding they can act on and one they learn to dismiss.
    closure = next(f for f in body["discrepancies"] if f["kind"] == "arithmetic_closure")
    assert closure["detail"]


def test_a_self_contradicting_document_is_refused_at_confirm(tmp_path: Path) -> None:
    """The chain end to end: read, check, block, and tell the operator why.

    The strongest reachability claim in this module. It needs the reader to
    recover the printed mention, the deterministic checks to run on an exactly
    read document, the finding to enrol as blocking, and the refusal to reach the
    process exit code -- and any one of those failing silently would leave a
    document that contradicts itself minting a record.
    """
    evidence_id = _add_edited_structured_evidence(
        tmp_path,
        old="<Items>",
        new="<LegalLiterals><LegalReference>inversión del sujeto pasivo</LegalReference></LegalLiterals><Items>",
        name="contradicted-regime.xml",
    )

    # Surfaced at review before it is refused at confirm: an operator meets the
    # finding when they look, not only when they are stopped.
    assert "regime_contradicted" in [finding["kind"] for finding in _extract(evidence_id)["discrepancies"]]

    refused = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
        ],
    )  # fmt: skip

    assert refused.exit_code != 0, f"a self-contradicting document confirmed cleanly: {refused.output}"
