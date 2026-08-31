"""The exactly-read path is checked too, and that is proven by running it.

Reachability, not capability. Every deterministic check in this package had
passing tests before this module existed, and none of them proved the check runs
on a document a real invocation can hand it: they built a draft and called the
producer. The structured e-invoice reader returns straight from its own function,
so it reached the findings assembly not at all -- arithmetic closure, rate
consistency, breakdown sums and the regime contradiction were all structurally
unreachable for a Facturae, CII or UBL document.

So a structured invoice whose base plus cuota did not equal its total confirmed
clean, and so did one printing a reverse-charge mention beside a charged cuota.
The most machine-readable documents in the corpus were getting the least
scrutiny, because the property that makes them safe from prompt injection was
silently read as making them safe from being wrong.

Every case here drives the REAL path: bytes are written through the real
encrypted-bucket evidence service and read back through
:func:`~application.ledger.evidence_draft.extract_invoice_draft_from_evidence`, which is the
function the CLI calls. No draft is constructed and no producer is called
directly -- doing either would reproduce exactly the gates that were already
green while this path ran nothing.

The documents are copies of the in-repo corpus invoice, edited in ``tmp_path``.
The corpus tree itself is never written to.

See Also:
    :func:`~application.ledger.deterministic_findings`
        The shared list both readers now run.
    :func:`~application.ledger.evidence_draft.extract_invoice_draft_from_evidence`
        The real entry point these cases drive.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.draft_discrepancy import DraftDiscrepancyKind
from ....core.config import Settings
from ..evidence_draft import extract_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects"]

_CORPUS = Path(__file__).parent / "_evidence_corpus"
_STRUCTURED_INVOICE = "facturae_32_series_and_parties_invoice.xml"

# The document states 200.00 + 42.00 = 242.00, and the reader DERIVES
# grand_total from TotalGrossAmountBeforeTaxes + TotalTaxOutputs (the printed
# InvoiceTotal element is display-only and never read, because it is stated
# net of retencion and would understate a withheld invoice -- see
# adapters.inbound.einvoice._parsers). Breaking TotalTaxOutputs alone moves the
# DERIVED total away from the header TaxesOutputs/Tax/TaxAmount the closure
# check's iva_amount comes from, leaving an exactly-read document whose own
# arithmetic does not close -- which is the case the structured path could not
# previously notice.
_COHERENT_TOTAL = "<TotalTaxOutputs>42.00</TotalTaxOutputs>"
_BROKEN_TOTAL = "<TotalTaxOutputs>999.00</TotalTaxOutputs>"

# Facturae carries the statutory mention in LegalLiterals, and the parser reads
# it into the draft, so a reverse-charge declaration beside the document's real
# 42.00 cuota is a genuine self-contradiction rather than a manufactured one.
_LEGAL_LITERALS = "<LegalLiterals><LegalReference>inversión del sujeto pasivo</LegalReference></LegalLiterals>"


def _stored(
    xml: str,
    *,
    settings: Settings,
    objects: SecureObjectRepository,
    tmp_path: Path,
    name: str,
) -> str:
    staged = tmp_path / name
    staged.write_text(xml, encoding="utf-8")
    return _make_svc(settings, objects).add(bucket_id=_BUCKET_ID, source_path=staged).record.evidence_id


def _corpus_xml() -> str:
    return (_CORPUS / _STRUCTURED_INVOICE).read_text(encoding="utf-8")


def _draft(evidence_id: str, settings: Settings):
    return extract_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        evidence_id=evidence_id,
        settings=settings,
    )


def test_the_coherent_structured_document_raises_nothing(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The positive control, and it is load-bearing.

    Every case below passes equally against a path that flags everything, so the
    unmodified corpus document has to come back clean. It also proves the checks
    do not false-fire on the exactly-read values, which is the risk of running
    arithmetic identities over a reader that was previously exempt from them.
    """
    evidence_id = _stored(
        _corpus_xml(),
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="coherent.xml",
    )

    draft = _draft(evidence_id, isolated_settings)

    assert draft.discrepancies == ()
    # The read itself still worked: an empty finding set from a failed read would
    # pass this assertion while proving nothing.
    assert draft.grand_total is not None


def test_a_structured_document_whose_arithmetic_does_not_close_is_caught(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The defect, stated as the case that used to confirm clean."""
    xml = _corpus_xml()
    assert _COHERENT_TOTAL in xml, "corpus total moved; the edit below would be a no-op"

    evidence_id = _stored(
        xml.replace(_COHERENT_TOTAL, _BROKEN_TOTAL),
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="broken-total.xml",
    )

    draft = _draft(evidence_id, isolated_settings)

    assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE in {finding.kind for finding in draft.discrepancies}


def test_a_structured_document_contradicting_its_own_regime_is_caught(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The regime check reaches the exact reader too.

    This one is why the fix is not merely tidiness: the contradiction blocker
    was landed, gated and enrolled as blocking, and it had never once run on a
    structured document. A reverse-charge declaration beside a charged cuota is
    the shape it exists for, and this path could not see it.
    """
    xml = _corpus_xml()
    assert "<LegalLiterals>" not in xml, "corpus already declares a legend; this edit would be ambiguous"

    evidence_id = _stored(
        xml.replace("<Items>", f"{_LEGAL_LITERALS}<Items>", 1),
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="contradicted-regime.xml",
    )

    draft = _draft(evidence_id, isolated_settings)

    assert draft.regime_legend is not None, "the parser did not read the mention; the case proves nothing"
    assert DraftDiscrepancyKind.REGIME_CONTRADICTED in {finding.kind for finding in draft.discrepancies}
