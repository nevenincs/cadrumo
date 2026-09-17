"""Known-bad citation guardrails for registry validation."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Literal, NamedTuple, Protocol, cast, runtime_checkable

from ....core.i18n.translatable import Translatable as tr
from ....core.text_fold import fold_diacritics
from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .schema_references import TemporalSupportEnvelope


@runtime_checkable
class _FilingYearFloorSource(Protocol):
    """A :class:`GovernedFactSource` that also publishes its filing-year floor.

    The protocol is not part of ``GovernedFactSource`` itself: minimal fact
    sources such as ``PublishedGovernedFactSource`` resolve governed facts
    without exposing a support envelope. Narrowing to this local protocol
    keeps that distinction typed instead of assuming every authority carries
    the method.
    """

    def supported_filing_years(self) -> TemporalSupportEnvelope:
        """Return the generation's single filing-year support envelope."""
        ...


CitationSource = Literal[
    "ley",
    "real_decreto",
    "real_decreto_legislativo",
    "orden",
    "reglamento",
    "manual",
    "instruction",
]
"""Closed parser token set for the registry citation ``source`` field.

The tokens identify the syntax category accepted by the validation boundary;
the cited declarations and their governing text remain registry data.
"""


def _fold_diacritics(text: str) -> str:
    return fold_diacritics(text).casefold()


class KnownBadCitation(NamedTuple):
    """A guardrail entry recording one mis-cited Spanish-tax legal reference.

    Attributes:
        source: The ``CitationSource`` category of the misfiring citation
            (e.g. ``"ley"``, ``"reglamento"``).
        article: The article number string as it appears in registry TOML
            (e.g. ``"103"``, ``"100.3.a"``).
        role_substring: A translatable substring that the casilla's
            ``role`` field must contain to trigger this guard. Matching is
            done after Unicode diacritic folding and case folding.
        reason: Human-readable explanation of why the citation is wrong and
            which article should be used instead. Used in validation
            error messages surfaced to the registry author.
    """

    source: CitationSource
    article: str
    role_substring: tr
    reason: str


_CITATION_FACT_ID = "registry-known-bad-citation-catalogue"
_CITATION_SOURCE_VALUES: frozenset[str] = frozenset(
    {
        "ley",
        "real_decreto",
        "real_decreto_legislativo",
        "orden",
        "reglamento",
        "manual",
        "instruction",
    },
)


def _known_bad_citations(
    *,
    authority: GovernedFactSource,
    effective_date: date,
) -> tuple[KnownBadCitation, ...]:
    """Resolve and type the dated known-bad citation catalogue.

    The mapping payload is intentionally narrowed here, at the validation
    boundary. Missing or malformed declarations raise instead of returning an
    empty tuple, so a missing authority cannot silently permit a bad citation.
    """
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_CITATION_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("known-bad citation catalogue must resolve as a mapping fact")
    declarations = {str(entry.key): str(entry.value) for entry in resolved.payload.entries}
    raw_ids = declarations.get("catalogue.ids", "")
    identifiers = tuple(identifier.strip() for identifier in raw_ids.split(",") if identifier.strip())
    if not identifiers:
        raise RegistryValidationError("known-bad citation catalogue is empty")
    if len(set(identifiers)) != len(identifiers):
        raise RegistryValidationError("known-bad citation catalogue contains duplicate identifiers")

    citations: list[KnownBadCitation] = []
    for identifier in identifiers:
        prefix = f"citation.{identifier}"
        try:
            source = declarations[f"{prefix}.source"]
            article = declarations[f"{prefix}.article"]
            role_substring = declarations[f"{prefix}.role_substring"]
            reason = declarations[f"{prefix}.reason"]
        except KeyError as exc:
            raise RegistryValidationError(
                f"known-bad citation catalogue is missing declaration {exc.args[0]!r}",
            ) from exc
        if source not in _CITATION_SOURCE_VALUES:
            raise RegistryValidationError(f"known-bad citation catalogue has unknown source {source!r}")
        if not article or not role_substring or not reason:
            raise RegistryValidationError(f"known-bad citation catalogue has an empty field for {identifier!r}")
        citations.append(
            KnownBadCitation(
                cast(CitationSource, source),
                article,
                tr(role_substring),
                reason,
            ),
        )
    return tuple(citations)


def find_known_bad(
    source: str,
    article: str,
    role_text: str,
    *,
    effective_date: date,
    effective_to: date | None = None,
    authority: GovernedFactSource | None = None,
) -> KnownBadCitation | None:
    """Return the first blocklist entry that matches the supplied citation, or ``None``.

    Matching is performed after diacritic folding: ``role_text`` and every
    ``KnownBadCitation.role_substring`` are lowercased and stripped of combining
    diacritics before the substring test runs, so ``"cuota íntegra"`` and
    ``"cuota integra"`` compare as equal.

    Args:
        source: The ``CitationSource`` category of the citation being validated.
        article: The article number string as written in registry TOML.
        role_text: The free-text ``role`` field of the casilla being validated.
        effective_date: The legal reference's effective date, used on the
            catalogue's filing-period date axis. A date before the registry's
            supported filing-year floor is evaluated at the floor instead: the
            catalogue cannot open a window earlier than the floor, and a norm
            already in force before the floor is still checked at the earliest
            coordinate the registry can represent.
        effective_to: The legal reference's own expiry, when known. A
            reference whose entire validity ends before the floor is skipped
            rather than clamped: the registry has no representable coordinate
            at which that citation could ever be checked.
        authority: Optional validated authority; omitted callers use the
            bundled published authority.

    Returns:
        The matching :class:`KnownBadCitation` entry, or ``None`` if the citation
        is not on the blocklist.
    """
    authority = authority or governed_facts_in_scope()
    if authority is None:
        raise RegistryValidationError("known-bad citation lookup requires an explicit authority operation or scope")
    if source not in _CITATION_SOURCE_VALUES:
        raise RegistryValidationError(f"known-bad citation lookup has unknown source {source!r}")
    if not isinstance(authority, _FilingYearFloorSource):
        raise RegistryValidationError(
            "known-bad citation lookup requires an authority that publishes its supported filing years"
        )
    floor = authority.supported_filing_years().date_envelope().floor
    if effective_to is not None and effective_to < floor:
        return None
    evaluation_date = max(effective_date, floor)
    folded = _fold_diacritics(role_text)
    for entry in _known_bad_citations(authority=authority, effective_date=evaluation_date):
        if entry.source == source and entry.article == article and _fold_diacritics(entry.role_substring) in folded:
            return entry
    return None


__all__ = ["CitationSource", "KnownBadCitation", "find_known_bad"]
