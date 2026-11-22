"""The Modelo 349 clave de operación must not contradict the invoice's IVA category.

One invoice carries two independent fields that both decide how a single
operation is declared. :attr:`~cadrumo.domain.invoices.Invoice.iva_category` is
the IVA treatment, and it selects the Modelo 303 bindings. ``operation_type`` is
the Modelo 349 clave de operación, and
:func:`cadrumo.application.invoices.source_observations.intracommunity_clave`
returns it verbatim when it is set, checking only that the letter is reachable
from the invoice's DIRECTION. Nothing checked that the letter agrees with the
category.

The diseño de registro (``instr_mod_349.txt``, position 133, "CLAVE DE
OPERACIÓN") defines each letter as a named operation, and each named operation
is exactly one IVA treatment:

- ``E`` "Entregas intracomunitarias exentas" -- LIVA art. 25;
- ``A`` "Adquisiciones intracomunitarias sujetas";
- ``T`` the triangular onward entrega -- LIVA art. 26.3, RIVA art. 79.cinco;
- ``S`` "Prestaciones intracomunitarias de servicios realizadas por el
  declarante" -- LIVA art. 69.Uno.1º;
- ``I`` "Adquisiciones intracomunitarias de servicios localizadas en el TAI"
  whose "destinatario es el declarante" -- LIVA art. 84.Uno.2º.

So clave ``S`` on a ``domestic_general`` invoice is not a tolerable looseness
between two free axes. It declares one operation twice and incompatibly: Modelo
303 settles it as a domestic supply with cuota repercutida, while Modelo 349
reports the same base to VIES as a prestación intracomunitaria de servicios the
declarant made. RIVA art. 79 obliges the declaración recapitulativa for the
intra-community operations and no others, so one of the two filings is false
whichever way the operator meant it.

The rule reaches exactly the claves fact 0084 declares a category for, which is
these five. Two groups fall outside it, for different reasons.

``R``, ``D`` and ``C`` are outside it permanently. They report movements under
acuerdos de ventas de bienes en consigna -- a transferencia, a devolución and a
sustitución del destinatario. LIVA art. 9 bis.Dos places the entrega, and its
exemption, at the later moment the acquirer takes the power of disposal, so the
movement these three report is not an entrega and has no IVA treatment to agree
with. The registry declares no category for them, and this module asserts that
absence rather than inventing one.

``M`` and ``H`` are outside it only because fact 0084 declares no category for
them either, which leaves a real hole this module pins rather than closes: see
``test_claves_m_and_h_are_outside_this_rules_reach_and_that_is_recorded``.

The refusal is scoped to write admission, which covers the creation and the
edit path, because the two fields were independent before this rule and a
contradicting pair may already be stored.
:class:`~cadrumo.domain.invoices.catalogue.StoredInvoiceCatalogue` validates
each record as it is READ, so refusing on hydration would strand exactly the
records needing correction. Such a record therefore still hydrates, and
``intracommunity_clave`` refuses to DECLARE it -- the incoherent filing is
never produced, and the record stays reachable. That is the same split the
pagos anticipados rule already makes.

The reverse direction is already correct and is covered here as a control: an
intra-community category carrying NO clave is not silently dropped from Modelo
349, because ``intracommunity_clave`` derives the letter from the category
through the same registry fact.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.application.invoices.source_observations import intracommunity_clave
from cadrumo.core.aggregation import IntracomOperationType

from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...iva.schema import InvoiceKind, IvaCategory
from ..enums import IvaRate, PaymentStatus, resolve_iva_rate_slot
from ..errors import InvoiceValidationError
from ..models import INVOICE_WRITE_ADMISSION, Invoice, InvoiceLine, derive_invoice_id
from ..rule_findings import InvoiceRuleFindingCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = filing_year_envelope().horizon
_ISSUED_AT = date(_YEAR, 3, 10)
_BASE = Decimal("1000.00")
_REFUSAL = "clave de operación"


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Validate invoices under the generation-pinned authority production uses."""
    with bundled_indexed_authority().operation():
        yield


def _payload(
    *,
    kind: InvoiceKind,
    iva_category: IvaCategory | None,
    operation_type: IntracomOperationType | None,
    exempt: bool = True,
) -> dict[str, object]:
    """Build one synthetic invoice payload differing only in the two axes under test."""
    rate = IvaRate.from_registry("EXEMPT") if exempt else resolve_iva_rate_slot(Decimal("21"), _ISSUED_AT)
    iva_total = Decimal("0") if exempt else Decimal("210.00")
    return {
        "invoice_id": derive_invoice_id(
            kind=kind,
            invoice_number="F-349-001",
            issued_at=_ISSUED_AT,
            counterparty_tax_id="DE123456789",
            currency="EUR",
            grand_total=_BASE + iva_total,
        ),
        "kind": kind,
        "invoice_number": "F-349-001",
        "issued_at": _ISSUED_AT,
        "counterparty_name": "EU Counterparty GmbH",
        "counterparty_tax_id": "DE123456789",
        "counterparty_country": "DE",
        "base_total": _BASE,
        "iva_total": iva_total,
        "grand_total": _BASE + iva_total,
        "currency": "EUR",
        "lines": (
            InvoiceLine(
                description="Operación intracomunitaria",
                quantity=Decimal("1"),
                unit_price=_BASE,
                subtotal=_BASE,
                iva_rate=rate,
                iva_amount=iva_total,
            ),
        ),
        "payment_status": PaymentStatus.PENDING,
        "iva_category": iva_category,
        "operation_type": operation_type,
    }


def _written(
    *,
    kind: InvoiceKind,
    iva_category: IvaCategory | None,
    operation_type: IntracomOperationType | None,
    exempt: bool = True,
) -> Invoice:
    """Validate the payload the way the creation and edit paths do."""
    return Invoice.model_validate(
        _payload(kind=kind, iva_category=iva_category, operation_type=operation_type, exempt=exempt),
        context=INVOICE_WRITE_ADMISSION,
    )


def _stored(
    *,
    kind: InvoiceKind,
    iva_category: IvaCategory | None,
    operation_type: IntracomOperationType | None,
    exempt: bool = True,
) -> Invoice:
    """Validate the payload the way a hydrating read does, with no write admission."""
    return Invoice.model_validate(
        _payload(kind=kind, iva_category=iva_category, operation_type=operation_type, exempt=exempt),
    )


def test_clave_s_on_an_intracommunity_service_supply_is_accepted_and_reaches_m349() -> None:
    """Positive control: the coherent pair must stay recordable and declarable.

    Without this, a refusal that rejected every clave would look like a pass.
    """
    invoice = _written(
        kind=InvoiceKind.ISSUED,
        iva_category=IvaCategory("intra_community_service_supply"),
        operation_type=IntracomOperationType.S,
    )
    assert intracommunity_clave(invoice) == "S"


def test_clave_s_on_a_domestic_general_invoice_is_refused() -> None:
    """The defect: one operation declared domestic in M303 and intracom in M349.

    ``domestic_general`` settles cuota repercutida in Modelo 303, while clave
    ``S`` reports the same base to VIES as a prestación intracomunitaria de
    servicios. RIVA art. 79 admits only the intra-community operations to the
    recapitulativa, so the pair cannot both be true.

    The refusal must also be usable by an operator surface, so the stable code
    and BOTH field names are asserted rather than only the prose: a message
    naming one field leaves the other looking correct.
    """
    with pytest.raises(ValidationError) as refusal:
        _written(
            kind=InvoiceKind.ISSUED,
            iva_category=IvaCategory("domestic_general"),
            operation_type=IntracomOperationType.S,
            exempt=False,
        )
    # ``pydantic_validation_boundary`` re-raises the registered refusal as the
    # ``ValueError`` pydantic's protocol requires, keeping the original as its
    # ``__cause__``, so the typed finding is recovered from the chain.
    findings = [
        raised.__cause__
        for error in refusal.value.errors()
        if isinstance(ctx := error.get("ctx"), Mapping) and isinstance(raised := ctx.get("error"), BaseException)
        if isinstance(raised.__cause__, InvoiceValidationError)
    ]
    assert findings, f"the refusal carried no registered invoice rule failure: {refusal.value}"
    context = findings[0].context
    assert context["rule_finding_code"] == InvoiceRuleFindingCode.M349_CLAVE_CATEGORY_MISMATCH.value
    assert set(context["fields"]) == {"operation_type", "iva_category"}


def test_clave_e_on_an_export_invoice_is_refused() -> None:
    """Clave ``E`` is the art. 25 entrega intracomunitaria, not an art. 21 export.

    An export to a third country is declared in Modelo 303 box 60 and belongs in
    no declaración recapitulativa at all; ``E`` would file it to VIES against a
    Member State operator.
    """
    with pytest.raises(Exception, match=_REFUSAL):
        _written(
            kind=InvoiceKind.ISSUED,
            iva_category=IvaCategory("export_third_country_zero_rated"),
            operation_type=IntracomOperationType.E,
        )


def test_clave_s_on_a_goods_supply_is_refused_because_the_claves_separate_the_legs() -> None:
    """The goods/services split is the whole point of ``E``/``S`` and ``A``/``I``.

    Modelo 303 titles boxes 10/11 "adquisiciones intracomunitarias de bienes y
    servicios" and so cannot catch this, which is exactly why the check belongs
    on the record.
    """
    with pytest.raises(Exception, match=_REFUSAL):
        _written(
            kind=InvoiceKind.ISSUED,
            iva_category=IvaCategory("intra_community_supply"),
            operation_type=IntracomOperationType.S,
        )


def test_clave_m_keeps_the_intra_community_supply_category_of_an_ordinary_entrega() -> None:
    """``M`` is an entrega intracomunitaria whose distinguishing fact is a prior import.

    The diseño defines ``M`` as "Entregas intracomunitarias de bienes
    posteriores a una importación exenta" (LIVA art. 27.12º) and ``H`` as the
    same thing "efectuadas por el representante fiscal" (art. 86.Tres). Both
    are entregas intracomunitarias de bienes, so the coherent pair must stay
    recordable and declarable.
    """
    for letter in (IntracomOperationType.M, IntracomOperationType.H):
        invoice = _written(
            kind=InvoiceKind.ISSUED,
            iva_category=IvaCategory("intra_community_supply"),
            operation_type=letter,
        )
        assert intracommunity_clave(invoice) == letter.value


def test_claves_m_and_h_are_outside_this_rules_reach_and_that_is_recorded() -> None:
    """The scope boundary, asserted so it is visible rather than assumed.

    This rule refuses only a clave the registry declares a category for, and
    fact 0084 declares none for ``M`` or ``H``. So clave ``M`` on a
    ``domestic_general`` invoice is still accepted today, even though the diseño
    defines ``M`` as an entrega intracomunitaria de bienes and the pair is
    therefore the same contradiction clave ``E`` is refused for.

    Closing it means declaring a category for ``M``/``H`` in fact 0084, which
    reverses the stated reasoning of
    ``test_a_clave_carrying_no_inferable_category_yields_none`` and changes the
    treatment that bulk import, the intake wizard and the CLI derive for a
    clave-only row. That is a registry decision, not an implementation detail,
    so it is left to one and pinned here instead of being made silently.
    """
    catalogue = resolve_iva_category_catalogue(effective_date=_ISSUED_AT)
    assert catalogue.category_for_operation_type(IntracomOperationType.M.value) is None
    assert catalogue.category_for_operation_type(IntracomOperationType.H.value) is None
    accepted = _written(
        kind=InvoiceKind.ISSUED,
        iva_category=IvaCategory("domestic_general"),
        operation_type=IntracomOperationType.M,
        exempt=False,
    )
    assert accepted.operation_type is IntracomOperationType.M


def test_an_intracommunity_category_without_a_clave_is_not_dropped_from_m349() -> None:
    """Control for the reverse direction, which the registry already derives.

    ``operation_type`` is optional on every creation path, so the common case
    is a category alone. It must reach Modelo 349 with the clave the registry
    fact maps it to, not vanish.
    """
    goods = _written(
        kind=InvoiceKind.ISSUED,
        iva_category=IvaCategory("intra_community_supply"),
        operation_type=None,
    )
    services = _written(
        kind=InvoiceKind.RECEIVED,
        iva_category=IvaCategory("intra_community_service_acquisition_reverse_charge"),
        operation_type=None,
    )
    assert intracommunity_clave(goods) == "E"
    assert intracommunity_clave(services) == "I"


def test_the_call_off_stock_claves_declare_no_iva_category_to_agree_with() -> None:
    """``R``, ``D`` and ``C`` report movements, not entregas, so they are unconstrained.

    Asserting the registry's silence from the test side keeps a later addition
    of a category for one of these letters from quietly changing the coherence
    rule's reach without a decision.
    """
    catalogue = resolve_iva_category_catalogue(effective_date=_ISSUED_AT)
    for letter in (IntracomOperationType.R, IntracomOperationType.D, IntracomOperationType.C):
        assert catalogue.category_for_operation_type(letter.value) is None


def test_a_record_stored_before_this_rule_hydrates_but_is_refused_at_declaration() -> None:
    """The reason the refusal is scoped to write admission, asserted both ways.

    A contradicting pair could already be persisted, and the stored catalogue
    validates each record as it is read. The record must therefore still
    hydrate -- otherwise the operator cannot open it to correct the
    contradiction -- while never reaching Modelo 349 as a declared row.
    """
    stored = _stored(
        kind=InvoiceKind.ISSUED,
        iva_category=IvaCategory("domestic_general"),
        operation_type=IntracomOperationType.S,
        exempt=False,
    )
    assert stored.operation_type is IntracomOperationType.S
    assert stored.iva_category == IvaCategory("domestic_general")
    with pytest.raises(RegistryValidationError, match="must be corrected on the record"):
        intracommunity_clave(stored)
