"""Shared helpers for constructing per-modelo registry entries.

Each entry module in :mod:`aeat.domain.modelos._entries` calls
:func:`build_entry` to turn a compact set of primitive arguments into
a fully validated :class:`aeat.domain.modelos._metadata.ModeloMetadata`.
Keeping this glue private isolates the repetitive construction
boilerplate from the authoritative per-modelo data tables.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from ....core.i18n import Translatable
from ...portals import Portal
from .._applicability import ModeloApplicability
from .._categories import (
    LegalCitationSource,
    ModeloCadence,
    ModeloCategory,
    TaxpayerProfile,
)
from .._citations import LegalCitation
from .._codes import ModeloCode
from .._metadata import ModeloMetadata

RETRIEVAL_DATE: date = date(2026, 4, 13)
"""Retrieval date stamped onto every catalogue-built :class:`LegalCitation`."""


def _all_profiles() -> frozenset[TaxpayerProfile]:
    """Return a :class:`frozenset` of every :class:`TaxpayerProfile` member."""
    return frozenset(TaxpayerProfile)


def make_citation(
    source: LegalCitationSource,
    article: str,
    url: str | None,
    quoted_text_es: str,
) -> LegalCitation:
    """Build a curated :class:`LegalCitation` with catalogue defaults.

    Args:
        source: The :class:`aeat.domain.modelos._categories.LegalCitationSource`
            provenance for the citation.
        article: Article identifier within the source.
        url: Optional BOE / Manual práctico URL pointing at the
            article. ``None`` when no canonical URL is on hand.
        quoted_text_es: Verbatim Spanish summary captured from the
            source corpus.

    Returns:
        A validated :class:`LegalCitation` with ``retrieval_date``
        pinned to :data:`RETRIEVAL_DATE` and ``is_curated_summary``
        set to ``True``.
    """
    return LegalCitation.model_validate(
        {
            "source": source,
            "article": article,
            "url": url,
            "quoted_text_es": quoted_text_es,
            "retrieval_date": RETRIEVAL_DATE,
            "is_curated_summary": True,
        }
    )


def build_applicability(
    mandatory: Sequence[TaxpayerProfile],
    optional: Sequence[TaxpayerProfile],
    trigger_notes_es: str,
) -> ModeloApplicability:
    """Assemble a :class:`ModeloApplicability` with auto-computed exempt bucket.

    Args:
        mandatory: Profiles that must file this modelo.
        optional: Profiles that may file this modelo.
        trigger_notes_es: Spanish prose describing the filing
            triggers.

    Returns:
        A validated
        :class:`aeat.domain.modelos._applicability.ModeloApplicability`
        whose ``exempt_profiles`` bucket is the complement of
        ``mandatory`` and ``optional`` against the full
        :class:`aeat.domain.modelos._categories.TaxpayerProfile` enum.
    """
    mset = frozenset(mandatory)
    oset = frozenset(optional)
    exempt = _all_profiles() - mset - oset
    return ModeloApplicability(
        mandatory_profiles=mset,
        optional_profiles=oset,
        exempt_profiles=exempt,
        trigger_notes_es=trigger_notes_es,
    )


def build_entry(
    *,
    code: ModeloCode,
    official_name_es: str,
    display_label: Translatable,
    category: ModeloCategory,
    cadence: ModeloCadence,
    legal_basis: Sequence[LegalCitation],
    applicability: ModeloApplicability,
    caps_into: ModeloCode | None,
    related_modelos: Sequence[ModeloCode],
    submission_portal: Portal | None,
    known_gotchas: Sequence[str],
) -> ModeloMetadata:
    """Assemble a :class:`ModeloMetadata` entry for a single modelo.

    Args:
        code: Canonical :class:`aeat.domain.modelos._codes.ModeloCode`.
        official_name_es: Official AEAT name of the modelo, in Spanish.
        display_label: Short multilingual label rendered by the CLI
            and UI surfaces.
        category: The
            :class:`aeat.domain.modelos._categories.ModeloCategory`
            classification (IRPF, IVA, censal, ...).
        cadence: The
            :class:`aeat.domain.modelos._categories.ModeloCadence`
            (quarterly, annual, ad hoc, ...).
        legal_basis: Curated tuple of :class:`LegalCitation` rows
            backing the modelo's legal authority.
        applicability: Pre-built
            :class:`aeat.domain.modelos._applicability.ModeloApplicability`
            for the modelo.
        caps_into: Optional :class:`ModeloCode` that this modelo rolls
            up into (e.g. quarterly 111 caps into annual 190).
        related_modelos: Tuple of related :class:`ModeloCode` values
            for cross-navigation.
        submission_portal: Optional :class:`aeat.domain.portals.Portal`
            for the modelo's Sede Electrónica submission flow.
        known_gotchas: Tuple of free-form Spanish gotcha notes the CLI
            surfaces alongside the entry.

    Returns:
        A validated :class:`aeat.domain.modelos._metadata.ModeloMetadata`
        entry with its sequence inputs frozen into tuples.
    """
    return ModeloMetadata(
        code=code,
        official_name_es=official_name_es,
        display_label=display_label,
        category=category,
        cadence=cadence,
        legal_basis=tuple(legal_basis),
        applicability=applicability,
        caps_into=caps_into,
        related_modelos=tuple(related_modelos),
        submission_portal=submission_portal,
        known_gotchas=tuple(known_gotchas),
    )
