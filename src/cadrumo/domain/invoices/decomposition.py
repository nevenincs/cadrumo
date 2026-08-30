"""The invoice decomposition contract: usable, or excluded-but-visible.

An invoice record either decomposes into the components a calculation needs,
or it does not. Before this module the second case had no name: a partial
record either travelled onward carrying nulls that downstream code read as
legally-absent components, or it was filtered out at some consumer's discretion
and stopped existing. Both are silent. What an operator needs to see is the
third outcome -- *source data exists which the calculation could not ground* --
and that is the outcome this module makes representable.

The decomposition is therefore a **classifier, never a refusal**. A partial
invoice is a real document the taxpayer holds, so :class:`Invoice` construction
must keep accepting it; refusing at construction would delete the very record
the operator has to be told about. The contract runs afterwards, over an
already-valid record, and its verdict is data.

What "grounded" means is decided by the Axis-A component-expectation table
(:func:`~cadrumo.domain.iva.category_components`), not by inspecting which
fields happen to be populated. That is the whole point: field nullness cannot
distinguish "this component does not exist in law" from "nobody recorded it",
and conflating the two is what let an IVA-exempt professional service and an
untagged bank credit look identical. The declared :class:`IvaCategory` is the
axis that separates them, so a record with no declared category is ungrounded
by construction however complete its amounts look.

The canonical identity the grounded case yields is::

    total (contraprestación) = taxable_base + cuota + recargo + suplido
    cash                     = total - retención

Three optional terms ride this identity and only one of them sits opposite
the other two. Retención is a settlement-side deduction, not a price
component: it reduces what the payer transfers, never what the operation
cost. Recargo de equivalencia and the suplido both join ``total`` instead --
LIVA art. 161 has the supplier repercutir the recargo on the entrega
alongside the cuota, so the comerciante minorista owes it and it belongs to
what the operation cost; a suplido (LIVA art. 78.Tres.3.º) is a sum the
issuer paid in the client's name and on their behalf, excluded from the base
imponible but still something the client owes -- a third position on the
identity, joining neither ``taxable_base`` nor ``cuota``.

See Also:
    :mod:`cadrumo.domain.iva.components`
        Axis A -- which components an operation in each category has.
    :mod:`cadrumo.domain.transactions.retencion_parameters`
        The RIRPF art. 95 rates bounding the row-level retención inference.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Self

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.identity import InvoiceId
from ..iva.components import IvaComponentPresence, IvaKindApplicability, category_bears_taxable_base, category_components
from ..iva.schema import IvaCategory
from .errors import InvoiceValidationError

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .models import Invoice


class InvoiceDecompositionDefect(StrEnum):
    """Why one invoice record could not be decomposed.

    Every member EXCLUDES the record from enrichment and aggregation and is
    surfaced to the operator. None of them is a construction refusal: the
    record stays in the catalogue, keeps its bytes, and remains editable into a
    grounded state.
    """

    IVA_TREATMENT_UNDECLARED = "iva_treatment_undeclared"
    """No usable :class:`~cadrumo.domain.iva.IvaCategory` is declared.

    Either the field is absent, or the declared category is one whose Axis-A
    row states its own components are unknown. Without it an exempt supply and
    an untagged operation are indistinguishable, so every downstream component
    question is unanswerable.
    """

    TAXABLE_BASE_ABSENT = "taxable_base_absent"
    """The category requires a taxable base and the record carries none.

    Cuota-less is not substrate-less: an entrega intracomunitaria exenta and an
    IVA-exempt professional service both require a real base even though
    neither bears a cuota.
    """

    CATEGORY_IMPOSSIBLE_ON_THIS_KIND = "category_impossible_on_this_kind"
    """The declared category is one-directional and this invoice is the other side.

    Kept separate from :attr:`IVA_TREATMENT_UNDECLARED` because the operator
    fix differs. An absent category is a data-entry gap: supply one. A category
    on its impossible side is a CONTRADICTION between two declarations that
    were both made — an entrega intracomunitaria recorded as received, say —
    and the contract cannot tell which of the two is the mistake. Telling that
    operator to "declare the IVA treatment" would send them to fix a field
    they already filled in.
    """

    CUOTA_CONTRADICTS_CATEGORY = "cuota_contradicts_category"
    """The record carries a cuota the declared category makes zero by law.

    One of the two declarations is wrong and the contract cannot tell which, so
    it grounds neither.
    """

    FX_UNRESOLVED = "fx_unresolved"
    """A non-euro invoice carries no resolved conversion rate.

    The euro components are genuinely unknown, and approximating them is
    refused rather than guessed.
    """


INVOICE_DECOMPOSITION_DEFECT_GUIDANCE: Final[Mapping[InvoiceDecompositionDefect, str]] = MappingProxyType(
    {
        InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED: (
            "declare the invoice's IVA treatment (iva_category) so an exempt operation "
            "can be told apart from an untagged one"
        ),
        InvoiceDecompositionDefect.TAXABLE_BASE_ABSENT: (
            "record the base imponible; this category carries a taxable base even when it bears no cuota"
        ),
        InvoiceDecompositionDefect.CATEGORY_IMPOSSIBLE_ON_THIS_KIND: (
            "the declared IVA category cannot occur on an invoice of this kind; correct whichever "
            "is wrong -- the category, or whether the invoice was issued or received"
        ),
        InvoiceDecompositionDefect.CUOTA_CONTRADICTS_CATEGORY: (
            "the recorded cuota and the declared IVA category disagree; correct whichever is wrong"
        ),
        InvoiceDecompositionDefect.FX_UNRESOLVED: (
            "resolve the invoice's conversion rate; a foreign-currency invoice has no euro figure without it"
        ),
    },
)
"""Operator remediation for each defect, one sentence per member.

Lives beside the defect definitions so the surfacing layer renders guidance it
did not have to invent, and so a new defect cannot ship without one.
"""


class InvoiceComponents(BaseModel):
    """The decomposed euro components of one grounded invoice.

    Every field is required and non-optional. That is deliberate: this type
    exists only for a record whose components are all known, so there is no
    null here for a reader to misinterpret. A record with an unknown component
    produces defects instead, never an :class:`InvoiceComponents` with a hole
    in it.

    Attributes:
        taxable_base: The base imponible in euro.
        cuota: The IVA cuota in euro; zero for a category whose cuota is zero
            by law.
        retencion: The declared IRPF retención in euro; zero when none was
            declared.
        recargo: The declared recargo de equivalencia in euro; zero when none
            was declared.
        suplido: The declared suplido (LIVA art. 78.Tres.3.º) in euro; zero
            when none was declared.
        total: The contraprestación -- ``taxable_base + cuota + recargo + suplido``.
        cash: What the payer transfers -- ``total - retencion``.
    """

    model_config = _STRICT_FROZEN

    taxable_base: Decimal
    cuota: Decimal
    retencion: Decimal
    recargo: Decimal
    suplido: Decimal
    total: Decimal
    cash: Decimal

    @model_validator(mode="after")
    def _validate_identity(self) -> Self:
        """Enforce the canonical identity on the decomposed figures themselves.

        Checking it here rather than only at the point of construction means no
        future producer of this type can emit a set of components that does not
        add up, whatever route it took to compute them.
        """
        if self.total != self.taxable_base + self.cuota + self.recargo + self.suplido:
            raise InvoiceValidationError("total must equal taxable_base + cuota + recargo + suplido")
        if self.cash != self.total - self.retencion:
            raise InvoiceValidationError("cash must equal total - retencion")
        if self.retencion < Decimal("0"):
            raise InvoiceValidationError("retencion must be non-negative")
        if self.recargo < Decimal("0"):
            raise InvoiceValidationError("recargo must be non-negative")
        if self.suplido < Decimal("0"):
            raise InvoiceValidationError("suplido must be non-negative")
        return self


class InvoiceDecomposition(BaseModel):
    """The verdict for one invoice: its components, or why it has none.

    ``components`` and ``defects`` are mutually exclusive and jointly
    exhaustive, enforced below. A caller therefore cannot read this record
    ambiguously: populated components mean grounded, a non-empty defect tuple
    means excluded-and-reportable, and neither state can be mistaken for the
    other by looking at a null.

    Attributes:
        invoice_id: The record this verdict is about.
        category: The declared IVA treatment, or ``None`` when undeclared.
        components: The decomposed euro components, present iff grounded.
        defects: Why the record was excluded, non-empty iff ungrounded.
    """

    model_config = _STRICT_FROZEN

    invoice_id: InvoiceId
    category: IvaCategory | None
    components: InvoiceComponents | None
    defects: tuple[InvoiceDecompositionDefect, ...]

    @model_validator(mode="after")
    def _validate_outcome_is_unambiguous(self) -> Self:
        """Refuse a verdict that is neither clearly grounded nor clearly excluded."""
        if (self.components is None) != bool(self.defects):
            raise InvoiceValidationError(
                "an invoice decomposition carries either components or defects, never both and never neither",
            )
        if len(set(self.defects)) != len(self.defects):
            raise InvoiceValidationError("defects must not repeat")
        return self

    @property
    def is_grounded(self) -> bool:
        """Whether the record may feed enrichment and aggregation."""
        return self.components is not None


class InvoiceDecompositionPartition(BaseModel):
    """Both outcome classes for a set of invoices, in one object.

    The two halves travel together on purpose. A consumer that took only a
    filtered list of usable invoices would have no handle on what it dropped,
    which is exactly how an excluded record becomes an invisible one; holding
    both means the excluded set is in the caller's hands whether it looks at it
    or not.

    Attributes:
        grounded: Verdicts whose components may be consumed.
        ungrounded: Verdicts that are excluded and must be surfaced.
    """

    model_config = _STRICT_FROZEN

    grounded: tuple[InvoiceDecomposition, ...]
    ungrounded: tuple[InvoiceDecomposition, ...]


def decompose_invoice(invoice: Invoice) -> InvoiceDecomposition:
    """Return the decomposition verdict for one invoice record.

    Never raises for a partial record: an invoice the contract cannot ground
    comes back carrying defects, which is the outcome the caller surfaces.

    Args:
        invoice: An already-valid invoice record.

    Returns:
        The verdict, carrying either euro components or the defects that
        excluded the record.
    """
    defects = tuple(_defects_for(invoice))
    if defects:
        return InvoiceDecomposition(
            invoice_id=invoice.invoice_id,
            category=invoice.iva_category,
            components=None,
            defects=defects,
        )
    taxable_base = invoice.base_total_eur
    cuota = invoice.iva_total_eur
    # Both are non-None here: FX_UNRESOLVED is a defect, so an unconverted
    # invoice never reaches this branch.
    if taxable_base is None or cuota is None:  # pragma: no cover - guarded by FX_UNRESOLVED
        raise InvoiceValidationError("euro components are unavailable on an invoice that passed the FX check")
    retencion = invoice.retention_amount_eur or Decimal("0")
    recargo = invoice.recargo_amount_eur or Decimal("0")
    suplido = invoice.suplido_amount_eur or Decimal("0")
    total = taxable_base + cuota + recargo + suplido
    return InvoiceDecomposition(
        invoice_id=invoice.invoice_id,
        category=invoice.iva_category,
        components=InvoiceComponents(
            taxable_base=taxable_base,
            cuota=cuota,
            retencion=retencion,
            recargo=recargo,
            suplido=suplido,
            total=total,
            cash=total - retencion,
        ),
        defects=(),
    )


def partition_invoices(invoices: Iterable[Invoice]) -> InvoiceDecompositionPartition:
    """Split invoices into the grounded and the excluded-but-visible.

    Args:
        invoices: Invoice records to classify.

    Returns:
        Both outcome classes, in input order within each half.
    """
    grounded: list[InvoiceDecomposition] = []
    ungrounded: list[InvoiceDecomposition] = []
    for invoice in invoices:
        verdict = decompose_invoice(invoice)
        (grounded if verdict.is_grounded else ungrounded).append(verdict)
    return InvoiceDecompositionPartition(grounded=tuple(grounded), ungrounded=tuple(ungrounded))


def _defects_for(invoice: Invoice) -> Iterable[InvoiceDecompositionDefect]:
    """Yield every decomposition defect the record carries.

    Accumulating rather than short-circuiting: an operator fixing a record
    should see everything wrong with it in one pass, not discover the next
    defect only after correcting the first.
    """
    if invoice.base_total_eur is None:
        yield InvoiceDecompositionDefect.FX_UNRESOLVED
    category = invoice.iva_category
    if category is None:
        yield InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED
        return
    # Keyed on the invoice's own kind: the Axis-A row for a category differs by
    # direction, so reading it without the kind would answer about the wrong
    # side of the operation. The invoice carries its kind, so the caller never
    # has to guess.
    row = category_components(category, invoice.kind)
    if row.applicability is IvaKindApplicability.DOES_NOT_ARISE:
        # The category is one-directional and this invoice claims the other
        # side (an "import" the taxpayer issued, say). Its own defect rather
        # than the undeclared one: the operator DID declare a treatment, so
        # the two failures need different remediation.
        yield InvoiceDecompositionDefect.CATEGORY_IMPOSSIBLE_ON_THIS_KIND
        return
    # The two placeholder categories are not named here. Their Axis-A rows
    # already declare their own components UNKNOWN, so reading that column is
    # both the same test and one that keeps working if the enum grows another
    # placeholder member.
    if row.base is IvaComponentPresence.UNKNOWN or row.cuota is IvaComponentPresence.UNKNOWN:
        yield InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED
        return
    if category_bears_taxable_base(category, invoice.kind) and invoice.base_total == Decimal("0"):
        yield InvoiceDecompositionDefect.TAXABLE_BASE_ABSENT
    if _carries_a_cuota_its_category_forbids(invoice, row.cuota):
        yield InvoiceDecompositionDefect.CUOTA_CONTRADICTS_CATEGORY


def _carries_a_cuota_its_category_forbids(invoice: Invoice, cuota: IvaComponentPresence) -> bool:
    """Whether a recorded cuota contradicts a category that has none by law.

    Only this direction is checked. The mirror -- a category whose cuota is
    ``REQUIRED`` showing zero -- is *not* a defect, because the categories that
    require one are precisely those where somebody other than the issuer
    settles it: the recipient self-assesses under inversión del sujeto pasivo,
    or customs settles it on importación. A zero cuota on the invoice is the
    correct face of those operations, and a zero-rated line legitimately
    produces one on a domestic rated category too.

    An OSS/IOSS-projected invoice is exempted: its cuota is the destination
    member state's, settled through the special regime rather than through the
    Spanish general cuota that the Axis-A row describes.
    """
    if cuota is not IvaComponentPresence.ZERO_BY_LAW:
        return False
    if invoice.oss_ioss_regime is not None:
        return False
    return invoice.iva_total != Decimal("0")


__all__ = [
    "INVOICE_DECOMPOSITION_DEFECT_GUIDANCE",
    "InvoiceComponents",
    "InvoiceDecomposition",
    "InvoiceDecompositionDefect",
    "InvoiceDecompositionPartition",
    "decompose_invoice",
    "partition_invoices",
]
