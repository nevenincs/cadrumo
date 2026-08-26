"""Enrolment registry for the ledger families' independent-quantity screens.

A family declares which of its facts measure genuinely independent quantities,
and registers that it did so. The enrolment gate outside this package diffs the
registered set against the families it drives end to end, which is what makes
that gate a gate rather than a sample. That reach is why this lives in its own
public defining module: the screen's enrolment is a contract, while the binding
resolution beside it is registry-internal.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal

from .errors import RegistryValidationError

__all__ = [
    "assert_quantity_readers_cover_independent_facts",
    "independent_quantity_facts",
    "screened_quantity_families",
]


def independent_quantity_facts(
    supported_facts: frozenset[str],
    alternative_measure_reasons: Mapping[str, str],
) -> frozenset[str]:
    """Return the facts that are genuinely independent quantities.

    DERIVED as the complement of the family's alternative-measure declarations
    so the two cannot drift apart. A fact added to a family's supported
    vocabulary is screened by default and must be classified deliberately to be
    excluded — the safe direction, since forgetting to classify one surfaces an
    advisory rather than silently dropping a quantity.

    Excluding a fact is a DECLARATION, not a proof. Nothing here can decide
    whether two facts really measure one quantity; that is a reading of the
    form and the statute. What the reason string buys is that the claim is
    written down at the site a reviewer will look, in a form they can disagree
    with — the same posture the fixture-provenance sidecar takes, where the
    declaration is trusted and cross-checked rather than inferred. The
    dangerous direction (classifying a genuinely independent quantity as an
    alternative measure) silently narrows the screen and no check can catch it;
    a required reason converts it from an invisible edit into a written claim.

    Args:
        supported_facts: Every fact the family's selector accepts.
        alternative_measure_reasons: Maps each excluded fact to why it measures
            the SAME quantity as another, so a revision declaring one
            deliberately omits it. Empty for a family whose facts are all
            independent — which is itself a claim, and one the family's tests
            should assert rather than leave as an absence.

    Returns:
        The screened set.

    Raises:
        RegistryValidationError: If a declaration names a fact outside
            ``supported_facts`` (stale, and excludes nothing), or carries a
            blank reason (an exclusion nobody has to justify is the silent
            narrowing this argument exists to prevent).
    """
    unknown = set(alternative_measure_reasons) - supported_facts
    if unknown:
        raise RegistryValidationError(
            f"alternative-measure facts {sorted(unknown)!r} are not in the family's supported fact set "
            f"{sorted(supported_facts)!r}; the classification is stale and excludes nothing",
        )
    unjustified = sorted(fact for fact, reason in alternative_measure_reasons.items() if not reason.strip())
    if unjustified:
        raise RegistryValidationError(
            f"alternative-measure facts {unjustified!r} declare no reason; excluding a fact from the quantity "
            "screen narrows it, so state which quantity the fact re-measures and under which rule",
        )
    return supported_facts - set(alternative_measure_reasons)


#: Families that have declared a quantity screen, recorded as a side effect of
#: :func:`assert_quantity_readers_cover_independent_facts` at import. The
#: enrolment gate diffs this against the families it drives end to end, so a new
#: adapter that declares readers and never runs the screen fails loudly instead
#: of shipping as dead capacity (the shape ``no-dormant-source-resolvers``
#: forbids one level up, for resolvers).
_SCREENED_FAMILIES: set[str] = set()


def screened_quantity_families() -> frozenset[str]:
    """Return every family that declared a quantity screen at import.

    Reading this requires the family adapter modules to have been imported;
    the enrolment gate imports them explicitly rather than relying on load
    order.
    """
    return frozenset(_SCREENED_FAMILIES)


def assert_quantity_readers_cover_independent_facts[ObservationT](
    family: str,
    independent_facts: frozenset[str],
    readers: Mapping[str, Callable[[ObservationT], Decimal]],
) -> None:
    """Assert every screened fact declares a reader, at import time.

    Called at module scope by each family adapter so a partition break — a fact
    classified as an independent quantity with nothing able to read it off an
    observation — fails the registry build rather than waiting for a taxpayer
    whose rows carry that quantity. Registers ``family`` in
    :func:`screened_quantity_families` so the enrolment gate can tell a declared
    screen from a wired one.

    Args:
        family: The family name, for the diagnostic and the enrolment registry.
        independent_facts: The screened set from :func:`independent_quantity_facts`.
        readers: The family's per-fact readers.

    Raises:
        RegistryValidationError: If a screened fact declares no reader, or a
            reader is declared for a fact that is not screened.
    """
    missing = independent_facts - set(readers)
    if missing:
        raise RegistryValidationError(
            f"{family} facts {sorted(missing)!r} are screened as independent quantities but declare no reader; "
            "add a reader or classify them as alternative measures",
        )
    extra = set(readers) - independent_facts
    if extra:
        raise RegistryValidationError(
            f"{family} declares quantity readers for {sorted(extra)!r}, which are not screened as independent "
            "quantities; the reader is dead and its fact's classification is inconsistent",
        )
    _SCREENED_FAMILIES.add(family)
