"""The duplicate-document refusal must reach the operator through the real CLI.

The application-level gate proves the guard's logic against a real encrypted
bucket. It cannot prove the guard is REACHED: a refusal built, gated and never
wired is a shape this codebase has shipped before, and a guard nobody's command
runs is indistinguishable from no guard at all.

So these drive the real Typer tree end to end -- ``evidence add`` then
``evidence confirm`` twice -- and read the operator-facing JSON envelope.

The document is a Facturae 3.2.2 XML rather than the text-bearing PDF the sibling
confirm suite uses. That is deliberate and load-bearing: the XML lane is the
deterministic parser, so these cases need no on-host reading model and exercise
the confirm path on any machine. The PDF lane's cases cannot run without a
provisioned reader, which is exactly how a CLI-surface regression goes unnoticed.

See Also:
    :func:`~application.ledger.invoice_confirmation.confirm_invoice_draft_from_evidence`
        The application service whose document-identity guard is reached here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._ledger_ux_support import _invoke, _open_bucket_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]

# The bundled structured fixture the application-level confirm suites read.
_FACTURAE_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "application"
    / "ledger"
    / "tests"
    / "_evidence_corpus"
    / "facturae_32_recargo_invoice.xml"
)


def _add_the_document(tmp_path: Path, *, filename: str = "factura.xml") -> str:
    source = tmp_path / filename
    source.write_bytes(_FACTURAE_FIXTURE.read_bytes())
    added = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "add", str(source), "--supplier", "Mayorista SL"],
    )
    assert added.exit_code == 0, added.output
    payload = json.loads(added.output)
    assert isinstance(payload, dict), added.output
    body = payload.get("result")
    assert isinstance(body, dict), added.output
    evidence_id = body.get("evidence_id")
    assert isinstance(evidence_id, str), added.output
    return evidence_id


def _confirm(evidence_id: str, *extra: str):
    return _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            *extra,
        ],
    )  # fmt: skip


def _catalogue_count() -> int:
    listed = _invoke(["--format", "json", "app", "ledger", "invoice", "list"])
    assert listed.exit_code == 0, listed.output
    return int(json.loads(listed.output)["result"]["count"])


def test_an_identical_reconfirm_is_a_no_op_through_the_cli(tmp_path: Path) -> None:
    """The retry an autonomous operator actually makes still succeeds.

    Asserted first, because a guard that only ever refused would be safe and
    useless. The second call must exit clean, report ``created: false``, and
    leave one row behind.
    """
    evidence_id = _add_the_document(tmp_path)

    first = _confirm(evidence_id)
    assert first.exit_code == 0, first.output
    assert json.loads(first.output)["result"]["created"] is True

    second = _confirm(evidence_id)
    assert second.exit_code == 0, second.output
    assert json.loads(second.output)["result"]["created"] is False
    assert _catalogue_count() == 1


def test_a_reconfirm_restating_the_number_refuses_through_the_cli(tmp_path: Path) -> None:
    """The refusal reaches the operator's envelope, and no second row is written.

    The invoice number is one of the six fields the invoice id folds, so this
    call hashes to a fresh id. Before the document-identity guard it exited
    zero, reported ``created: true`` and left the catalogue holding two records
    made from one piece of paper -- both feeding Modelo 303, 347 and 390.
    """
    evidence_id = _add_the_document(tmp_path)
    assert _confirm(evidence_id).exit_code == 0

    second = _confirm(evidence_id, "--invoice-number", "RESTATED-0001")

    assert second.exit_code != 0, second.output
    assert "invoice_number" in second.output
    assert _catalogue_count() == 1


def test_the_same_bytes_added_twice_are_still_one_document_through_the_cli(tmp_path: Path) -> None:
    """A re-run of the ingest does not launder the document into a new identity.

    Two ``evidence add`` calls over the same file mint two evidence records. The
    attachment store is content-addressed, so both resolve to one address --
    which is why the guard is keyed there. An evidence-id-keyed guard would let
    this straight through, and re-running an ingest is the single most likely
    way an operator arrives here.
    """
    first_evidence = _add_the_document(tmp_path, filename="scan-monday.xml")
    second_evidence = _add_the_document(tmp_path, filename="scan-tuesday.xml")
    assert second_evidence != first_evidence

    assert _confirm(first_evidence).exit_code == 0
    refused = _confirm(second_evidence, "--invoice-number", "RESTATED-0001")

    assert refused.exit_code != 0, refused.output
    assert _catalogue_count() == 1
