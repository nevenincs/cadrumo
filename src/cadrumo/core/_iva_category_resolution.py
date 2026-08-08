"""The closed outcome axis for resolving one document's IVA category.

One enum. It names how the category on a confirmed record was established --
or why it was not -- so a later reader can tell a rule-table verdict from the
issuer's own written declaration from a document that contradicts itself.

The distinction is not bookkeeping. Those three states carry different
evidentiary weight and different remedies: a verdict is reproducible from the
operation's facts, a declaration rests on a code only the issuing system wrote,
and a contradiction is a question for the person holding the paper.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["IvaCategoryOutcome"]


class IvaCategoryOutcome(StrEnum):
    """How one document's IVA category was established, or why it was not.

    Deliberately without a "probable" or "best guess" member, matching the
    legend axis it sits beside: either something established the category or
    nothing did, and a threshold between those two would be an invention.
    """

    CORROBORATED = "corroborated"
    """The rule table and the document's own declared code agree.

    The strongest state available: the operation's facts reach a category
    independently, and the issuing system wrote the same one into the record.
    """

    CLASSIFIED = "classified"
    """The rule table placed the operation and the document declared no code.

    The ordinary path for a domestic invoice. A standard-rated supply carries
    no special category code by design -- the rate is the meaning -- so there is
    nothing to corroborate against and nothing missing.
    """

    RATE_INFERRED = "rate_inferred"
    """The rule table could not place the operation and the tier charged settled it.

    **The weakest state that still yields a category, and it is named so it can
    be told apart from the others rather than blending in.** The table refuses
    whenever a party's IVA territory is unestablished, and an ordinary domestic
    Spanish invoice frequently prints no country at all -- so that refusal falls
    on the commonest document there is. Leaving those records with no declared
    treatment is not neutral: the invoice decomposition contract refuses an
    undeclared record, and the renta income path then contributes the row's bank
    cash instead of its ingresos íntegros, dropping the base, the cuota and the
    retención from the figure that reaches the declaration.

    What carries the inference is the charged tax itself, not a default: Spanish
    repercutido IVA at a registered Spanish tier is charged on operations inside
    the Spanish IVA territory, and Canarias and Ceuta y Melilla levy IGIC and
    IPSI rather than IVA. A document that charged a registered Spanish rate has
    therefore said something about itself that a blank country field did not
    retract.

    It remains an inference and this member is what names it as one.

    **Naming it is not yet showing it, and the gap is stated rather than
    implied.** Nothing persists this outcome and no operator surface reads it:
    the confirmed record carries the resolved category and not the rung it came
    from, so a record resting on the inference is presently indistinguishable
    from one the rule table placed outright. Enumerating them requires re-running
    the resolution, not querying a store. Until a surface carries it, treat this
    member as an internal distinction and not as a disclosure to the taxpayer.
    """

    DECLARED = "declared"
    """The document's own code established it and the rule table could not.

    The reverse-charge, exempt and zero-rated population. Those treatments turn
    on facts a printed page does not carry, so the table refuses; the code is
    the issuing system's own record-level declaration and is the only evidence
    that separates them from an ordinary zero-cuota supply.
    """

    UNSUPPORTED_RELIEF = "unsupported_relief"
    """The document claimed a relief resting on an establishment nothing established.

    Two declared treatments relieve a supply of Spanish output IVA purely on
    where the counterparty is -- an entrega intracomunitaria under LIVA art. 25
    and an export under art. 21. When the rule table cannot place the operation,
    the document's own code would otherwise be taken at face value, and the
    rate-tier corroboration is silent on every non-domestic category by
    construction. So an unplaceable counterparty reached a relieved category
    with nothing disagreeing anywhere.

    **Distinct from** :attr:`CONTRADICTED` **because nothing disagrees.** A
    contradiction says the document is wrong somewhere; this says the document
    may be perfectly right and the evidence does not reach the claim. The two
    take different remedies -- one asks which half to believe, the other asks
    for the establishment -- so collapsing them would send an operator to
    re-read a page that was never the problem.

    Carries no category, on the same terms as its siblings: a relieved category
    honoured on absent evidence is a zero-rated supply nobody could place, and
    that is under-declaration produced by treating silence as proof.
    """

    CONTRADICTED = "contradicted"
    """The declared code and the operation's other evidence cannot both be true.

    Carries NO category, on the same terms the legend axis withholds one: the
    document disagrees with itself, which half is wrong is not decidable from
    the page, and a caller holding a value would use it while ignoring the
    conflict. A wrong category is worse than an absent one -- an absent category
    asks the operator and a wrong one does not.
    """

    UNRESOLVED = "unresolved"
    """Nothing established a category.

    The rule table refused for want of an input and the document declared no
    code. An honest blank rather than a default: a category invented here would
    be indistinguishable, downstream, from one the evidence supported.
    """
