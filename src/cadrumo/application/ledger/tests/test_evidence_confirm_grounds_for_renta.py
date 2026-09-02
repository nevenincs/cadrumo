"""An invoice confirmed from a structured document is legally interpretable.

The renta sales-evidence path refuses a linked invoice whose own figures cannot
be interpreted, and it asks exactly one question to decide: whether
``decompose_invoice`` grounds the record. An invoice read from a structured
document carries everything that contract needs -- its base resolves in euro and
its IVA treatment is stated by the document rather than guessed -- so it must
ground, and the sales-evidence path must contribute its figures instead of
reporting an ungrounded-decomposition verdict.

Asserted end to end from the document bytes rather than on a hand-built
``Invoice``, because the failure this guards against lives in the confirm
boundary: the parser reads a category the persisted record then drops, and a
constructed fixture would carry the category the constructor was handed and
prove nothing about that hop.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.invoices.decomposition import InvoiceDecompositionDefect, decompose_invoice
from ....domain.iva.classification import InvoiceKind
from ..invoice_confirmation import confirm_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

# Single-rate on purpose. A multi-rate document has no single domestic category
# to declare, so it grounds for a different and legitimate reason -- using one
# here would have tested the multi-rate carve-out rather than the confirm hop.
_SINGLE_RATE_FIXTURE = Path(__file__).parent / "_evidence_corpus" / "facturae_32_series_and_parties_invoice.xml"


def _confirm_as_issued(
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
):
    """Confirm the structured document as an ISSUED invoice, with no overrides.

    The absence of an ``iva_category`` argument is the point: whatever grounds
    the record has to come from the document, which is the claim under test.
    """
    source = tmp_path / "facturae_32_series_and_parties_invoice.xml"
    source.write_bytes(_SINGLE_RATE_FIXTURE.read_bytes())
    svc = _make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=_BUCKET_ID, source_path=source).record
    return confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        # Supplied because this document states no name. The claim under test is
        # grounding, and an operator-supplied name is the ordinary confirm path,
        # so withholding it would fail on an unrelated precondition.
        counterparty_name="Cliente SL",
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        evidence_id=record.evidence_id,
        settings=isolated_settings,
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
    )


def test_a_structured_confirm_grounds_through_the_decomposition_contract(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The step's red condition: the renta path must not refuse this as ungrounded.

    ``sales_invoice_evidence_payload`` returns
    ``SalesInvoiceEvidenceRefusal.UNGROUNDED_DECOMPOSITION`` when and only when
    ``decompose_invoice(invoice).is_grounded`` is false, so grounding the
    decomposition IS the absence of that verdict. Asserting the contract
    directly keeps the proof on the fact that decides the outcome rather than on
    a linkage fixture that could pass for unrelated reasons.
    """
    result = _confirm_as_issued(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    decomposition = decompose_invoice(result.invoice)

    assert decomposition.is_grounded, (
        "an invoice read from a structured document must be legally interpretable; "
        f"the renta sales-evidence path refuses it as ungrounded. Defects: {decomposition.defects}"
    )


def test_the_grounding_rests_on_a_declared_treatment_not_a_defaulted_one(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Name the defect that would otherwise fire, so the proof cannot pass hollowly.

    ``IVA_TREATMENT_UNDECLARED`` is the defect a structured confirm trips when
    the category is read from the document and then lost at the persistence
    boundary. Asserting its absence by name means a future change that grounds
    the record some other way -- by defaulting a category, say -- does not
    silently satisfy the test above while reintroducing exactly the guess the
    structured reader exists to remove.
    """
    result = _confirm_as_issued(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    defects = set(decompose_invoice(result.invoice).defects)

    assert InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED not in defects
    assert InvoiceDecompositionDefect.FX_UNRESOLVED not in defects
    # The invoice carries real figures, so a grounding that rode on empty totals
    # would be a different thing passing under the same assertion.
    assert result.invoice.base_total > Decimal("0")


def test_an_unreadable_document_is_not_grounded_by_this_path(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The discriminator: grounding must come from the document, not from confirming.

    Without this, a confirm boundary that stamped every record grounded would
    satisfy both assertions above. An invoice whose treatment nothing declares
    must still carry the undeclared defect, so the tests are reading the
    document's contribution rather than the act of persisting it.
    """
    invoice = _confirm_as_issued(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    ).invoice

    stripped = invoice.model_copy(update={"iva_category": None})

    assert InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED in set(decompose_invoice(stripped).defects), (
        "removing the declared treatment must reintroduce the defect; if it does not, the "
        "grounding assertions above are not reading the category at all"
    )
