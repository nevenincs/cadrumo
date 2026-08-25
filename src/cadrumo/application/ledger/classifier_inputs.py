"""The facts an IVA classification is derived from, each with where it came from.

An IVA category decides whether tax is charged, self-assessed, or not due at
all. When a later audit asks why a document was classified the way it was, the
answer has to be a record of the inputs rather than a re-run of the code — the
code will have moved on, and a re-run cannot show what the profile said at the
time.

So every input arrives here as a typed row carrying its own source, and the two
sources are not interchangeable:

**Document evidence is anchorable.** It was printed, so an operator can be
pointed at the printed form and shown what was read.

**A profile fact is authoritative and unanchorable.** The taxpayer's censo
regime is true of the filer whichever document is being classified; there is no
phrase on the page to highlight, and pretending otherwise would have the
envelope claim the document said something it never said.

What this module deliberately does NOT do is decide the classification, or map
its inputs into the substrate classifier's own criteria record. It collects
facts and states their provenance. The mapping needs one authority this
pipeline does not consult (see
:class:`~core.CounterpartyTaxablePersonStatus`), and inventing it here would
put a legal conclusion behind an unverified reading.

See Also:
    :class:`~domain.iva.IvaInvoiceClassificationCriteria`
        The substrate classifier's input record these facts eventually feed.
    :class:`~application.ledger.evidence_draft.InvoiceDraft`
        The read document these evidence-sourced facts are derived from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG, ClassifierInputSource, CounterpartyTaxablePersonStatus

# Runtime imports: both are pydantic field types on the models below, so a
# TYPE_CHECKING-only import leaves the models un-buildable at construction.
from ...domain.deadlines import IVARegime

if TYPE_CHECKING:
    from typing import Self

    from ...domain.deadlines import TaxpayerProfile
    from .evidence_draft import InvoiceDraft

__all__ = [
    "ClassifierInputFact",
    "ClassifierInputs",
    "collect_classifier_inputs",
]


class ClassifierInputFact(BaseModel):
    """One fact a classification stood on, and where it came from.

    Attributes:
        name: Which input this is.
        value: The fact, as its closed-enum token.
        source: Whether the document established it or the profile did.
        anchor: The verbatim printed form it was read from, when the document
            established it. ``None`` for a profile fact, which has no printed
            form on this document to point at.
        authority: What vouches for a profile fact. ``None`` for document
            evidence, which is vouched for by its own anchor.
    """

    model_config = STRICT_FROZEN_CONFIG

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source: ClassifierInputSource
    anchor: str | None = None
    authority: str | None = None

    @model_validator(mode="after")
    def _each_source_carries_only_its_own_backing(self) -> Self:
        """Refuse a fact backed the wrong way for its source.

        An anchor on a profile fact would claim the document printed something
        it did not, and is the exact laundering the source split exists to
        prevent. An authority on document evidence hides that a printed value
        was read rather than vouched for. Every direction is refused, because
        any one of them makes the envelope lie about what an auditor should go
        and look at.

        Exhaustive over the source set rather than an if/else pair. An operator
        assertion reaching a two-branch check would fall to the document arm and
        be allowed to carry an anchor -- which would state that the page printed
        the very fact the operator had to supply BECAUSE the page did not.
        """
        if self.source is ClassifierInputSource.PROFILE_AUTHORITY:
            if self.anchor is not None:
                raise ValueError(f"profile fact {self.name!r} must not carry a document anchor")
            if not self.authority:
                raise ValueError(f"profile fact {self.name!r} must name the authority that vouches for it")
        elif self.source is ClassifierInputSource.OPERATOR_ASSERTION:
            if self.anchor is not None:
                raise ValueError(
                    f"operator assertion {self.name!r} must not carry a document anchor: "
                    "it was asserted because the document did not state it",
                )
            if self.authority is not None:
                raise ValueError(
                    f"operator assertion {self.name!r} is vouched for by the operator, not a profile authority",
                )
        elif self.authority is not None:
            raise ValueError(f"document evidence {self.name!r} is vouched for by its anchor, not an authority")
        return self


class ClassifierInputs(BaseModel):
    """Every fact collected for one document's IVA classification.

    Attributes:
        counterparty_taxable_person: What the document established about the
            counterparty. ``UNKNOWN`` when nothing was established.
        filer_iva_regime: The taxpayer's own censo-registered IVA regime, or
            ``None`` when no profile was resolvable.
        facts: One row per input, each stating its own source.
    """

    model_config = STRICT_FROZEN_CONFIG

    counterparty_taxable_person: CounterpartyTaxablePersonStatus = CounterpartyTaxablePersonStatus.UNKNOWN
    filer_iva_regime: IVARegime | None = None
    facts: tuple[ClassifierInputFact, ...] = ()


def _printed_counterparty_identifier(draft: InvoiceDraft) -> str | None:
    """Return the counterparty tax identifier the document printed, if any.

    Reads the customer identifier first and the supplier's second, because the
    draft is deliberately pre-direction data: which party is the counterparty is
    settled by the operator at confirm, not here. Either printed identifier is
    equally evidence that a tax identifier was printed for a party to this
    document, which is the only claim being made.
    """
    return draft.customer_tax_id or draft.supplier_tax_id


def collect_classifier_inputs(
    draft: InvoiceDraft,
    *,
    profile: TaxpayerProfile | None = None,
) -> ClassifierInputs:
    """Collect the classification facts from a read document and the filer's profile.

    **Absence resolves to UNKNOWN and can never resolve to consumer.** The
    function has no branch that produces a consumer verdict, which is stronger
    than a default that happens to be safe: a factura simplificada legitimately
    prints no recipient at all, so treating absence as evidence about the
    recipient would silently reclassify that whole legitimate population.

    Args:
        draft: The read document. Only its printed identifiers are consulted.
        profile: The filer's own :class:`TaxpayerProfile`, when one is
            resolvable. ``None`` records no regime fact rather than assuming a
            regime — guessing the filer's regime would change the tax on every
            document they file.

    Returns:
        :class:`ClassifierInputs`: The facts, each with its source.
    """
    facts: list[ClassifierInputFact] = []

    identifier = _printed_counterparty_identifier(draft)
    counterparty = (
        CounterpartyTaxablePersonStatus.TAXABLE_PERSON if identifier else CounterpartyTaxablePersonStatus.UNKNOWN
    )
    facts.append(
        ClassifierInputFact(
            name="counterparty_taxable_person",
            value=counterparty.value,
            source=ClassifierInputSource.DOCUMENT_EVIDENCE,
            # The identifier IS the anchor: it is the printed form the reading
            # was taken from. UNKNOWN carries none, because nothing was read.
            anchor=identifier or None,
        ),
    )

    regime = profile.iva_regime if profile is not None else None
    if regime is not None:
        facts.append(
            ClassifierInputFact(
                name="filer_iva_regime",
                value=regime.value,
                source=ClassifierInputSource.PROFILE_AUTHORITY,
                authority="taxpayer profile (censo-registered)",
            ),
        )

    return ClassifierInputs(
        counterparty_taxable_person=counterparty,
        filer_iva_regime=regime,
        facts=tuple(facts),
    )
