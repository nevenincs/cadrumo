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

**The phrases are quoted from the governed consolidated text**, not authored:
art. 6.1 puts each one in guillemets, and :func:`resolve_regime_legends` carries
those exact strings for the caller's selected date. Nothing here paraphrases a
statute.

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

from collections.abc import Mapping
from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ...domain.calculations.registry.schema_base import DateAxis
from .schema import IvaCategory

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation

__all__ = [
    "RegimeLegend",
    "regime_legend_phrases",
    "resolve_regime_legends",
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


def _registry_regime_legend_declarations(
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date,
) -> Mapping[str, str]:
    """Resolve the dated statutory regime-legend catalogue for one operation."""
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-regime-legend-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise ValueError("IVA regime legend catalogue must resolve as a mapping fact")
    return {str(entry.key): str(entry.value) for entry in resolved.payload.entries}


def _required_legend_declaration(declarations: Mapping[str, str], key: str) -> str:
    try:
        return declarations[key]
    except KeyError as exc:
        raise ValueError(f"IVA regime legend declaration is missing: {key}") from exc


def _registry_regime_legends(
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date,
) -> tuple[RegimeLegend, ...]:
    declarations = _registry_regime_legend_declarations(
        operation=operation,
        effective_date=effective_date,
    )
    order = _required_legend_declaration(declarations, "legend_order").split(",")
    legends: list[RegimeLegend] = []
    category_catalogue = resolve_iva_category_catalogue(
        effective_date=effective_date,
        authority=operation,
    )
    for ordinal in order:
        prefix = f"legend.{ordinal}"
        declared_value = _required_legend_declaration(declarations, f"{prefix}.declares")
        try:
            category = None if declared_value == "none" else category_catalogue.require(declared_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"unknown IVA regime legend category: {declared_value}") from exc
        expects_value = _required_legend_declaration(declarations, f"{prefix}.expects_repercutido_line")
        if expects_value not in {"true", "false"}:
            raise ValueError(f"invalid IVA regime legend line expectation: {expects_value}")
        legends.append(
            RegimeLegend(
                phrase=_required_legend_declaration(declarations, f"{prefix}.phrase"),
                provision=_required_legend_declaration(declarations, f"{prefix}.provision"),
                declares=category,
                expects_repercutido_line=expects_value == "true",
            )
        )
    return tuple(legends)


def resolve_regime_legends(
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date,
) -> tuple[RegimeLegend, ...]:
    """Resolve every mandated mention from the selected operation generation.

    The registry fact and its IVA-category dependency are both addressed through
    ``operation`` at the caller's dated filing coordinate.  Importing this module
    performs no authority I/O and creates no process-wide vocabulary.
    """
    return _registry_regime_legends(operation=operation, effective_date=effective_date)


def regime_legend_phrases(legends: tuple[RegimeLegend, ...]) -> tuple[str, ...]:
    """Return every phrase from a caller-selected registry vocabulary.

    Exposed so the compiled prompt renders phrases from the same operation-derived
    declarations the deterministic classifier receives, rather than restating
    them at an adapter boundary.

    Returns:
        legends: The dated declarations already resolved by the caller.

    Returns:
        The phrases in declaration order.
    """
    return tuple(legend.phrase for legend in legends)
