"""Real-CLI regression for the human review gate over pending extraction drafts.

Drives the real Typer tree against a real encrypted bucket session. The pending
draft is seeded through the sanctioned store rather than by running an
extraction, deliberately: the review surface is what is under test, and routing
through a reader would make every assertion here depend on a model being
reachable.

Every assertion is on CODES and STRUCTURE -- envelope command, blocker reason
tokens, field names, exit codes -- never on prose, which is localised.

See Also:
    :func:`~entrypoints.cli._ledger_evidence_review_cli.register_evidence_review_commands`
        The registration under test.
    :func:`~application.ledger.confirmation_blockers`
        The gate the surface projects.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.ledger import (
    DraftDiscrepancyFinding,
    FieldAmbiguityCandidate,
    FieldProvenance,
    InvoiceDraft,
    write_extraction_draft,
)
from ....core import DraftDiscrepancyKind, FieldGroundingOutcome, FieldOrigin, resolve_active_bucket_id
from ....core.config import load_settings
from ._ledger_ux_support import _invoke, _open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLEAN_REFERENCE = "ev-clean-001"
_BLOCKED_REFERENCE = "ev-blocked-001"


def _clean_draft() -> InvoiceDraft:
    return InvoiceDraft(
        supplier_tax_id="ESB12345674",
        supplier_name="Acme Suministros SL",
        invoice_number="2026-0142",
        invoice_date="2026-03-10",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        currency="EUR",
        provenance=(
            FieldProvenance(
                field="taxable_base",
                origin=FieldOrigin.EXACT_STRUCTURED,
                grounding=FieldGroundingOutcome.ANCHORED,
                anchor="100,00",
            ),
        ),
    )


def _blocked_draft() -> InvoiceDraft:
    return _clean_draft().model_copy(
        update={
            "discrepancies": (
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.ROLE_UNRESOLVED,
                    detail="nothing on the page distinguishes issuer from recipient",
                ),
            ),
            "provenance": (
                FieldProvenance(
                    field="supplier_tax_id",
                    origin=FieldOrigin.TEXT_LAYER,
                    grounding=FieldGroundingOutcome.AMBIGUOUS,
                    candidates=(
                        FieldAmbiguityCandidate(value="ESB12345674", note="header block"),
                        FieldAmbiguityCandidate(value="ESX1234567L", note="footer block"),
                    ),
                ),
            ),
        },
    )


@pytest.fixture
def seeded_queue(tmp_path: Path) -> Iterator[None]:
    """A live bucket session carrying one clean and one blocked pending draft."""
    with _open_ledger_ux_session(tmp_path):
        bucket_id = resolve_active_bucket_id()
        assert bucket_id is not None
        settings = load_settings()
        write_extraction_draft(
            bucket_id=bucket_id,
            evidence_reference=_CLEAN_REFERENCE,
            draft=_clean_draft(),
            extractor="exact_structured",
            settings=settings,
        )
        write_extraction_draft(
            bucket_id=bucket_id,
            evidence_reference=_BLOCKED_REFERENCE,
            draft=_blocked_draft(),
            extractor="text_layer",
            settings=settings,
        )
        yield


def _json_result(args: list[str]) -> dict[str, object]:
    result = _invoke(["--format", "json", *args])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    body = payload.get("result", payload)
    assert isinstance(body, dict)
    return body


def test_review_list_reports_both_pending_drafts_with_their_blocking_reasons(seeded_queue: None) -> None:
    """The queue names what is pending and, per row, why it cannot be confirmed."""
    body = _json_result(["app", "ledger", "evidence", "review", "list"])

    rows = {row["evidence_reference"]: row for row in body["rows"]}
    assert set(rows) == {_CLEAN_REFERENCE, _BLOCKED_REFERENCE}
    assert rows[_CLEAN_REFERENCE]["blocking_count"] == 0
    assert rows[_CLEAN_REFERENCE]["reasons"] == []
    assert set(rows[_BLOCKED_REFERENCE]["reasons"]) == {"unresolved_direction", "ambiguous_identity"}


def test_review_list_filters_narrow_the_queue(seeded_queue: None) -> None:
    """Each filter narrows to the intended row, and the clean row is the control.

    Without the clean row present, a filter that returned everything would look
    identical to one that filtered correctly.
    """
    blocking = _json_result(["app", "ledger", "evidence", "review", "list", "--blocking"])
    assert [row["evidence_reference"] for row in blocking["rows"]] == [_BLOCKED_REFERENCE]

    by_reason = _json_result(
        ["app", "ledger", "evidence", "review", "list", "--reason", "ambiguous_identity"],
    )
    assert [row["evidence_reference"] for row in by_reason["rows"]] == [_BLOCKED_REFERENCE]

    by_finding = _json_result(
        ["app", "ledger", "evidence", "review", "list", "--finding", "role_unresolved"],
    )
    assert [row["evidence_reference"] for row in by_finding["rows"]] == [_BLOCKED_REFERENCE]

    unmatched = _json_result(
        ["app", "ledger", "evidence", "review", "list", "--finding", "arithmetic_closure"],
    )
    assert unmatched["rows"] == []


def test_review_show_carries_value_origin_anchor_grounding_and_candidates(seeded_queue: None) -> None:
    """Every axis the review gate requires reaches the operator, per field.

    A surface showing only values would make an exactly-parsed structured figure
    and an ambiguous text-layer reading look identical at exactly the moment a
    person decides whether to accept them.
    """
    body = _json_result(["app", "ledger", "evidence", "review", "show", _BLOCKED_REFERENCE])

    fields = {row["field"]: row for row in body["fields"]}
    identity = fields["supplier_tax_id"]
    assert identity["origin"] == "text_layer"
    assert identity["grounding"] == "ambiguous"
    assert [candidate["value"] for candidate in identity["candidates"]] == ["ESB12345674", "ESX1234567L"]
    # A field with no envelope is still surfaced, with its axes null rather than
    # dropped: an absent reading is the field an operator most needs to see.
    assert "grand_total" in fields
    assert fields["grand_total"]["origin"] is None

    assert [finding["kind"] for finding in body["discrepancies"]] == ["role_unresolved"]
    reasons = {blocker["reason"] for blocker in body["blockers"]}
    assert reasons == {"unresolved_direction", "ambiguous_identity"}
    assert all(len(blocker["blocker_id"]) == 16 for blocker in body["blockers"])


def test_review_show_of_a_clean_draft_reports_no_blockers(seeded_queue: None) -> None:
    """Positive control: the surface does not manufacture a blocker for every draft."""
    body = _json_result(["app", "ledger", "evidence", "review", "show", _CLEAN_REFERENCE])

    assert body["blockers"] == []
    assert body["discrepancies"] == []


def test_review_show_of_an_unknown_reference_refuses(seeded_queue: None) -> None:
    """A reference with no pending draft refuses rather than showing an empty document."""
    result = _invoke(["app", "ledger", "evidence", "review", "show", "ev-does-not-exist"])

    assert result.exit_code != 0, result.output


def test_the_confirm_verb_offers_no_bulk_resolution_flag() -> None:
    """No ``--confirm-all``, ``--force`` or ``--accept-all`` on the confirm surface.

    Asserted against the rendered option set rather than against module source
    text: the operator's escape hatch would be a CLI OPTION, and a source scan
    would also match a comment or a docstring that merely mentions one.
    """
    result = _invoke(["app", "ledger", "evidence", "confirm", "--help"])

    assert result.exit_code == 0, result.output
    rendered = result.output.replace("\n", " ")
    for forbidden in ("--confirm-all", "--force", "--accept-all", "--resolve-all", "--yes"):
        assert forbidden not in rendered, f"{forbidden} re-creates the rubber stamp the gate removes"
    assert "--resolve" in rendered
