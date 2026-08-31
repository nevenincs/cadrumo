"""Real-CLI proof that an uncatalogued country code advises and does not refuse.

The deliverable of moving the two country-vocabulary conditions off the blocking
channel. Both halves have to be measured against the real Typer tree, because
either alone is escapable: an advisory nothing surfaces is a value nobody reads,
and a "non-blocking" claim asserted where no gate runs measures nothing.

So this drives the real command against a real encrypted bucket and asserts, on
one draft carrying both kinds at once, that the notices arrive under two distinct
codes AND that the draft raises no blocker. The bundled vocabulary carries a
bounded subset of the world's jurisdictions, so a code outside it is an ordinary
event for a real foreign counterparty; refusing there would make those documents
unfileable until the registry caught up.

The refusal that carries the safety is elsewhere and untouched: an unresolved
country yields no residency, the classification criteria do not assemble, and
the zero-rated export category stays unreachable. That is proven at the
application layer beside the advisory itself.

The two codes are seeded on the STATED country fields, which are the ones a
reading path populates: the resolved siblings are contracted alpha-2 and stay
empty for precisely these tokens, so seeding them would describe a draft no
document produces.

Assertions are on CODES and STRUCTURE -- the notice codes, the context keys and
the stated codes they carry -- never on prose, which is localised.

See Also:
    :func:`~application.ledger.country_vocabulary_advisory`
        The domain advisory the notices project.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from ....application.ledger.deterministic_findings import deterministic_findings
from ....application.ledger.extraction_draft_store import write_extraction_draft
from ....application.ledger.invoice_draft_records import InvoiceDraft
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.config import load_settings
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....tests.country_vocabulary_specimens import an_uncatalogued_alpha2
from ._ledger_ux_support import _invoke, _open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REFERENCE: Final = "ev-country-vocabulary-001"
_UNASSIGNED_CODE: Final = "ledger.evidence.review.country_code_unassigned"
_UNCATALOGUED_CODE: Final = "ledger.evidence.review.country_code_uncatalogued"


@pytest.fixture
def seeded_draft(tmp_path: Path) -> Iterator[None]:
    """A pending draft whose two parties state one code of each kind.

    Both on one document deliberately. Two separate fixtures would each pass a
    test that had collapsed the kinds into a single notice, because neither would
    ever see the other's.
    """
    read = InvoiceDraft(
        supplier_tax_id="B12345674",
        supplier_stated_country_code=an_uncatalogued_alpha2(),
        customer_stated_country_code="XX",
        taxable_base=Decimal("100.00"),
    )
    # Stamped through the real check list, exactly as a reading path hands a
    # draft on. Seeding an empty ``discrepancies`` tuple instead would make the
    # no-blocker assertion below true of the fixture rather than of the product:
    # the gate reads what the reader stored, so a fixture that stores nothing
    # cannot raise a blocker whatever the check list does.
    stored = read.model_copy(update={"discrepancies": deterministic_findings(read)})
    with _open_ledger_ux_session(tmp_path):
        bucket_id = resolve_active_bucket_id()
        assert bucket_id is not None
        write_extraction_draft(
            bucket_id=bucket_id,
            evidence_reference=_REFERENCE,
            draft=stored,
            extractor="text_layer",
            settings=load_settings(),
        )
        yield


def _envelope() -> dict[str, object]:
    result = _invoke(["--format", "json", "app", "ledger", "evidence", "review", "view", _REFERENCE])
    assert result.exit_code == 0, result.output
    return STR_KEYED_MAPPING_ADAPTER.validate_json(result.output)


def _notice(envelope: dict[str, object], code: str) -> dict[str, object]:
    notices = envelope.get("notices")
    assert isinstance(notices, list)
    matching = [notice for notice in notices if isinstance(notice, dict) and notice.get("code") == code]
    assert len(matching) == 1, notices
    return STR_KEYED_MAPPING_ADAPTER.validate_python(matching[0])


@pytest.mark.usefixtures("seeded_draft")
def test_an_uncatalogued_country_code_does_not_block_the_draft() -> None:
    """The deliverable: advised, listed, and still confirmable.

    ``blockers`` is the gate's own answer, read off the shipped payload rather
    than recomputed, so this cannot pass against a surface that stopped asking.
    """
    envelope = _envelope()

    body = envelope["result"]
    assert isinstance(body, dict)
    assert body["blockers"] == []
    assert body["discrepancies"] == []


@pytest.mark.usefixtures("seeded_draft")
def test_the_two_kinds_arrive_under_distinct_notice_codes() -> None:
    """A typo the operator fixes and a gap we fix must not wear one sentence."""
    envelope = _envelope()

    unassigned = _notice(envelope, _UNASSIGNED_CODE)
    uncatalogued = _notice(envelope, _UNCATALOGUED_CODE)

    assert unassigned["severity"] == "warning"
    assert uncatalogued["severity"] == "warning"
    assert envelope["status"] == "warning"
    assert unassigned["message"] != uncatalogued["message"]


@pytest.mark.usefixtures("seeded_draft")
def test_each_notice_names_the_code_the_document_stated_and_the_party() -> None:
    """An advisory that does not quote the string is one the operator cannot act on."""
    envelope = _envelope()

    unassigned = _notice(envelope, _UNASSIGNED_CODE)["context"]
    uncatalogued = _notice(envelope, _UNCATALOGUED_CODE)["context"]

    assert isinstance(unassigned, dict)
    assert isinstance(uncatalogued, dict)
    assert unassigned["billed_country_code"] == "XX"
    assert unassigned["fields"] == "customer_stated_country_code"
    assert uncatalogued["issuing_country_code"] == an_uncatalogued_alpha2()
    assert uncatalogued["fields"] == "supplier_stated_country_code"


@pytest.mark.usefixtures("seeded_draft")
def test_the_text_surface_carries_the_same_advisories_as_the_json_one() -> None:
    """A terminal operator is told what a JSON consumer is told."""
    result = _invoke(["app", "ledger", "evidence", "review", "view", _REFERENCE])

    assert result.exit_code == 0, result.output
    assert _UNASSIGNED_CODE in result.output
    assert _UNCATALOGUED_CODE in result.output
    assert "country_code_unresolved\tbilled\tXX" in result.output
    assert f"country_code_unresolved\tissuing\t{an_uncatalogued_alpha2()}" in result.output


@pytest.mark.usefixtures("seeded_draft")
def test_no_bespoke_advisory_field_appears_on_the_result_payload() -> None:
    """The notice channel is the only diagnostic channel, and stayed the only one.

    A regression here is the easy one to land: attaching the advisory to the
    review payload reads as more discoverable and quietly forks the contract.
    """
    body = _envelope()["result"]

    assert isinstance(body, dict)
    assert not [key for key in body if "advisory" in key or key in {"next", "suggestion"}]
