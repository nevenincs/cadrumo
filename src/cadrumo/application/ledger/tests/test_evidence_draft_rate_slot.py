"""A percentage outside the closed IVA taxonomy refuses; it never rounds.

Structured-document ingestion reads the rate off the document itself rather
than taking it from an operator, which is what makes this reachable: the
taxpayer does not choose the percentage on a supplier's invoice, so any
percentage that has ever existed can arrive at the confirm boundary.

Eight percent is the specific case, and it is real rather than hypothetical:
Spain's reducido was 8% from July 2010 until September 2012, when it became the
present 10%. A 2011 invoice therefore prints a percentage that is perfectly
valid history and that :class:`~domain.invoices.IvaRate` does not carry.

The rate this module names has already had to change once, which is the better
argument for the gate than any wording could be. It was originally the transient
5% electricity rate; a slot for that was added while this test was being
written, and the module's own non-vacuity assertion caught it and said so
directly rather than letting the refusal test quietly become a test of nothing.
The taxonomy is expected to keep growing as older filing years come into scope,
so the assertion below is what keeps this module honest across that growth.

**Refusing is the correct outcome and rounding is the dangerous one.** Silently
resolving eight percent down to the four percent slot understates the cuota;
resolving it up to ten percent overstates it. Both produce a structurally valid invoice
record carrying a figure that appears on no document, and neither leaves a
signal -- which is precisely the silent-misfiling class the confirm boundary
exists to prevent. The nearest slot is never the right answer for a rate the
taxonomy does not know.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.invoices import InvoiceValidationError, IvaRate, numeric_iva_rate_slots
from ....domain.iva import InvoiceKind
from ....tests.pdf_fixtures import text_pdf_bytes
from .._evidence_draft import confirm_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects
from ._loopback_reader import serving_a_loopback_reader

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

_SUPPLIER_CIF = "B12345674"

# A 2011 invoice at the then-current 8% reducido: base 100,00, cuota 8,00.
# Every figure is internally coherent -- the document is not malformed, it is
# simply expressed in a rate slot this taxonomy does not carry.
_UNREPRESENTABLE_RATE = Decimal("8")
_UNREPRESENTABLE_RATE_INVOICE_LINES = (
    "Factura de Energia Peninsular SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2011-0451",
    "Fecha: 14/06/2011",
    "Base imponible: 100,00",
    "IVA 8%",
    "Cuota IVA: 8,00",
    "Total factura: 108,00",
)

# The same document at a slot the taxonomy DOES carry. This is the positive
# control: it differs from the fixture above only in the percentage, so a
# refusal above that is really caused by a broken fixture would show up here
# as well.
_KNOWN_RATE_INVOICE_LINES = (
    "Factura de Energia Peninsular SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2024-0452",
    "Fecha: 14/06/2024",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

# A real loopback reader. The two documents differ ONLY in the percentage, which
# is what makes the positive control work, so the replies must differ only there
# too -- a shared payload would make the control vacuous.

_UNREPRESENTABLE_RATE_FIELDS = {
    "supplier_tax_id": _SUPPLIER_CIF,
    "supplier_tax_id_anchor": _SUPPLIER_CIF,
    "invoice_number": "2011-0451",
    "invoice_number_anchor": "2011-0451",
    "invoice_date": "2011-06-14",
    "invoice_date_anchor": "14/06/2011",
    "taxable_base": "100,00",
    "taxable_base_anchor": "100,00",
    "iva_rate": "8",
    "iva_rate_anchor": "8%",
    "iva_amount": "8,00",
    "iva_amount_anchor": "8,00",
    "grand_total": "108,00",
    "grand_total_anchor": "108,00",
}

_KNOWN_RATE_FIELDS = {
    **_UNREPRESENTABLE_RATE_FIELDS,
    "invoice_number": "2024-0452",
    "invoice_number_anchor": "2024-0452",
    "invoice_date": "2024-06-14",
    "invoice_date_anchor": "14/06/2024",
    "iva_rate": "21",
    "iva_rate_anchor": "21%",
    "iva_amount": "21,00",
    "iva_amount_anchor": "21,00",
    "grand_total": "121,00",
    "grand_total_anchor": "121,00",
}


@pytest.fixture(autouse=True)
def _loopback_reader() -> Iterator[None]:
    """Serve a real reading endpoint keyed on each document's own figures."""
    with serving_a_loopback_reader(
        (("2024-0452", _KNOWN_RATE_FIELDS), ("2011-0451", _UNREPRESENTABLE_RATE_FIELDS)),
    ):
        yield


def _confirm(
    lines: tuple[str, ...],
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    filename: str,
):
    pdf_path = tmp_path / filename
    pdf_path.write_bytes(text_pdf_bytes(lines))
    svc = _make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
    return confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        evidence_id=record.evidence_id,
        counterparty_name="Energia Peninsular SL",
        settings=isolated_settings,
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
    )


def test_the_chosen_rate_is_genuinely_outside_the_taxonomy() -> None:
    """Non-vacuity: the refusal below only means something while this rate is unknown.

    This assertion has already earned its place. The module first used the
    transient 5% rate; a ``RATE_5`` slot was added while it was being written,
    and this check failed immediately and named the cause, instead of letting
    the refusal test below silently become a test that nothing refuses.

    The taxonomy is expected to keep growing as older filing years come into
    scope, so this will fire again. When it does the fix is HERE -- pick a
    percentage the taxonomy still does not carry -- and never in the resolver,
    which is behaving correctly by representing a rate it now has a slot for.
    """
    slots = numeric_iva_rate_slots()

    assert _UNREPRESENTABLE_RATE not in slots, (
        f"a slot for {_UNREPRESENTABLE_RATE}% now exists, so such a document is representable and "
        "must no longer refuse. Choose a percentage still outside the taxonomy and update the "
        "fixture in this module; do not change the resolver"
    )
    # Neighbours on both sides, so "did not round" is a claim with somewhere to
    # have rounded TO. Derived from the taxonomy rather than listed, so this
    # keeps holding as slots are added.
    assert any(rate < _UNREPRESENTABLE_RATE for rate in slots), "no lower slot for the rate to round down into"
    assert any(rate > _UNREPRESENTABLE_RATE for rate in slots), "no higher slot for the rate to round up into"


def test_an_unrepresentable_rate_refuses_and_names_the_accepted_rates(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The confirm boundary refuses, and the refusal is actionable.

    A bare "value invalid" would leave the operator with a document they can
    read and no idea why the application will not take it, so the rejected rate
    and the accepted set both travel on the error's context where the localised
    message renders them.

    Asserted on the context rather than on ``str(exc)`` deliberately: the
    operator-facing wording lives in the locale catalogues, and pinning English
    prose here would both duplicate that authority and break on translation.
    """
    with pytest.raises(InvoiceValidationError) as excinfo:
        _confirm(
            _UNREPRESENTABLE_RATE_INVOICE_LINES,
            isolated_settings=isolated_settings,
            secure_objects=secure_objects,
            tmp_path=tmp_path,
            filename="factura_luz_2011.pdf",
        )

    error = excinfo.value
    assert error.translated_message == "application.invoices.creation.errors.unsupported_iva_rate"
    # A refusal that names neither the rejected rate nor the accepted set is the
    # bare "value invalid" the CLI boundary rule forbids, so its absence is a
    # failure of this test's subject rather than a typing detail.
    assert error.context is not None, "the refusal must carry the context naming the rate and the accepted slots"
    assert error.context["iva_rate"] == format(_UNREPRESENTABLE_RATE, "f"), (
        f"the refusal must name the rate rejected: {error.context}"
    )
    # The context is a str-keyed mapping of arbitrary values; the accepted set is
    # published as a comma-joined string, so assert that shape before splitting
    # it rather than discovering a changed encoding as an AttributeError.
    accepted_raw = error.context["accepted"]
    assert isinstance(accepted_raw, str), f"the accepted set must be published as a string, got {type(accepted_raw)}"
    accepted = {slot.strip() for slot in accepted_raw.split(",")}
    assert accepted == {format(rate, "f") for rate in numeric_iva_rate_slots()}, (
        f"the refusal must advertise exactly the taxonomy's slots, got {accepted}"
    )
    assert format(_UNREPRESENTABLE_RATE, "f") not in accepted, (
        "the rejected rate must not appear in the set the refusal advertises as accepted"
    )


def test_the_refusal_is_the_same_one_whether_or_not_a_cuota_was_printed(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """One unrepresentable rate, one refusal -- on both confirm branches.

    The confirm path forks on whether the document printed a cuota: a printed
    figure is evidence and builds an explicit invoice line, an absent one lets
    the writer derive it. Both forks resolve the same percentage, and they once
    resolved it through two different functions raising two different error
    types -- so the operator's experience of the identical mistake depended on
    a property of their document that has nothing to do with the rate.
    """
    printed_cuota = _UNREPRESENTABLE_RATE_INVOICE_LINES
    no_printed_cuota = tuple(line for line in _UNREPRESENTABLE_RATE_INVOICE_LINES if not line.startswith("Cuota IVA"))
    assert len(no_printed_cuota) == len(printed_cuota) - 1, "the second fixture must differ by the cuota line alone"

    raised = []
    for index, lines in enumerate((printed_cuota, no_printed_cuota)):
        with pytest.raises(InvoiceValidationError) as excinfo:
            _confirm(
                lines,
                isolated_settings=isolated_settings,
                secure_objects=secure_objects,
                tmp_path=tmp_path,
                filename=f"factura_luz_fork_{index}.pdf",
            )
        raised.append(excinfo.value)

    assert raised[0].translated_message == raised[1].translated_message
    # Both refusals must carry their context: the point of this test is that the
    # two paths advertise the SAME accepted set, which a missing context would
    # vacuously satisfy by having nothing to compare.
    assert raised[0].context is not None
    assert raised[1].context is not None
    assert raised[0].context["accepted"] == raised[1].context["accepted"]


def test_the_same_document_at_a_known_rate_confirms(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Positive control: the fixture shape itself is confirmable.

    Without this, the refusal above is equally consistent with a fixture the
    reader cannot parse at all -- a test that passes because nothing works is
    indistinguishable from one that passes because the guard fired.
    """
    result = _confirm(
        _KNOWN_RATE_INVOICE_LINES,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        filename="factura_luz_21.pdf",
    )

    assert [line.iva_rate for line in result.invoice.lines] == [IvaRate.RATE_21]
    assert result.invoice.grand_total == Decimal("121.00")
