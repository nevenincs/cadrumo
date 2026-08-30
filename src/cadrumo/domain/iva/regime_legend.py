"""The statutory mentions an invoice must print, and what each one declares.

Spanish law does not leave the regime of an operation to be inferred from its
numbers. RD 1619/2012 art. 6.1 obliges the issuer to print a specific *mención*
whenever certain regimes apply, so for those cases the paper states the regime in
words the law itself fixes. That is what makes this axis transcribable at all: a
reading stage can copy a printed phrase, and copying is the only thing it is
allowed to do.

Why this exists as data rather than as prose in two places. The compiled
extraction prompt needs the vocabulary as a recognition aid, and the downstream
deterministic classifier needs the same vocabulary to map a transcribed phrase
onto a category. Two hand-maintained lists that happen to agree today is the
defect this closes -- the same defect the field-form contract closed for the
shape of a value, on the axis of its meaning.

**The phrases are quoted from the bundled consolidated text**, not authored: art.
6.1 puts each one in guillemets, and :data:`REGIME_LEGENDS` carries those exact
strings. Nothing here paraphrases a statute.

**The exempt case is deliberately absent, and that absence is load-bearing.** Art.
6.1.j does not fix a phrase for an exempt operation; it requires a REFERENCE to
the provision that grants the exemption, so an exempt invoice may print "exenta
art. 20 LIVA", "operación exenta según art. 25" or the Directive's article, and no
canonical string exists to match. Inventing one would manufacture a mandated
mention the regulation does not mandate, and matching against it would then look
authoritative while being an author's guess. Exempt operations are therefore not
derivable from a legend and fall to the classifier's absent state.

**A legend is the issuer's declaration, never a licence to compute.** Matching a
printed phrase yields the regime the issuer states; it does not license deriving
an amount, a rate, or a category the phrase does not name.

See Also:
    :class:`IvaCategory`
        The closed catalogue a legend resolves into.
    :data:`NO_PRINTED_TAX_IVA_CATEGORIES`
        The categories whose invoices carry no printed tax line, which is the
        expectation a legend's ``expects_repercutido_line`` states per legend.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from .schema import IvaCategory

__all__ = [
    "REGIME_LEGENDS",
    "RegimeLegend",
    "regime_legend_phrases",
]


class RegimeLegend(BaseModel):
    """One statutory mention, and what printing it declares about the operation.

    Attributes:
        phrase: The mention exactly as RD 1619/2012 art. 6.1 fixes it, quoted
            from the bundled consolidated text. Lower-cased there and here, and
            carrying its accents. A document printing it in capitals, wrapped
            across a line, or with its accents lost by the text layer still
            matches: the match folds case, collapses whitespace runs and folds
            combining accents away, rather than carrying spelling variants as
            extra rows. Nothing beyond those three is normalised, and the whole
            multi-word phrase is what matches -- never a token of it. Two
            mentions that differ only by an accent would become one form under
            that fold, so the vocabulary is refused whole rather than indexed if
            any pair collides.
        provision: The art. 6.1 letter that mandates this mention, so a value
            derived from it can cite the provision that put it on the page.
        declares: The category the mention declares, or ``None`` when the mention
            is real and mandated but says nothing about the IVA category. A
            self-billing mention is the worked case: art. 6.1.l obliges it
            whenever the recipient issues the invoice, which is a fact about WHO
            wrote the document and carries no category at all.
        expects_repercutido_line: Whether an invoice printing this mention should
            also carry a repercutido rate and cuota. ``False`` for the mentions
            whose whole point is that the issuer charges no Spanish IVA, which is
            what lets a contradiction be detected rather than averaged over.
    """

    model_config = STRICT_FROZEN_CONFIG

    phrase: str = Field(min_length=1)
    provision: str = Field(min_length=1)
    declares: IvaCategory | None = None
    expects_repercutido_line: bool = True


REGIME_LEGENDS: Final[tuple[RegimeLegend, ...]] = (
    RegimeLegend(
        phrase="inversión del sujeto pasivo",
        provision="art-6.1.m",
        declares=IvaCategory.DOMESTIC_REVERSE_CHARGE,
        expects_repercutido_line=False,
    ),
    RegimeLegend(
        phrase="facturación por el destinatario",
        provision="art-6.1.l",
        declares=None,
    ),
    RegimeLegend(
        phrase="régimen especial de las agencias de viajes",
        provision="art-6.1.n",
        declares=None,
    ),
    RegimeLegend(
        phrase="régimen especial de los bienes usados",
        provision="art-6.1.o",
        declares=None,
    ),
    RegimeLegend(
        phrase="régimen especial de los objetos de arte",
        provision="art-6.1.o",
        declares=None,
    ),
    RegimeLegend(
        phrase="régimen especial de las antigüedades y objetos de colección",
        provision="art-6.1.o",
        declares=None,
    ),
    RegimeLegend(
        phrase="régimen especial del criterio de caja",
        provision="art-6.1.p",
        declares=None,
    ),
)
"""Every mention RD 1619/2012 art. 6.1 fixes as a literal phrase, in its order.

The mentions under art. 6.1.o are three separate phrases in the regulation rather
than one alternation, and they are carried as three rows for that reason: a
document prints exactly one of them, and collapsing them would either match text
no invoice prints or force a caller to re-split the alternation.

Only one row currently ``declares`` a category. That is the measured state of the
law, not an unfinished table: the remaining mentions are obligations about the
billing arrangement or the special regime's accounting, and none of them fixes
the operation's IVA category on its own. A row is added here when the regulation
mandates a phrase, never when a category would be convenient to derive.
"""


def regime_legend_phrases() -> tuple[str, ...]:
    """Return every mandated phrase, for a caller that needs only the vocabulary.

    Exposed so the compiled prompt renders the phrases from this declaration
    rather than restating them, which is the property the anti-drift gate binds.

    Returns:
        The phrases in declaration order.
    """
    return tuple(legend.phrase for legend in REGIME_LEGENDS)
