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

    It remains an inference and is recorded as one, so a later reader asking
    which records rest on it can enumerate them.
    """

    DECLARED = "declared"
    """The document's own code established it and the rule table could not.

    The reverse-charge, exempt and zero-rated population. Those treatments turn
    on facts a printed page does not carry, so the table refuses; the code is
    the issuing system's own record-level declaration and is the only evidence
    that separates them from an ordinary zero-cuota supply.
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
