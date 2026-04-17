"""Shared helpers for constructing per-modelo registry entries.

Each entry module in :mod:`aeat.models._entries` calls
:func:`build_entry` to turn a compact dict of primitive values into a
fully validated :class:`ModeloMetadata`. Keeping this glue private
isolates the repetitive construction boilerplate from the authoritative
per-modelo data tables.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from aeat.i18n import Translatable
from aeat.models._applicability import ModeloApplicability
from aeat.models._categories import (
    LegalCitationSource,
    ModeloCadence,
    ModeloCategory,
    TaxpayerProfile,
)
from aeat.models._citations import LegalCitation
from aeat.models._codes import ModeloCode
from aeat.models._metadata import ModeloMetadata
from aeat.portals._codes import Portal

RETRIEVAL_DATE: date = date(2026, 4, 13)


def _all_profiles() -> frozenset[TaxpayerProfile]:
    return frozenset(TaxpayerProfile)


def make_citation(
    source: LegalCitationSource,
    article: str,
    url: str | None,
    quoted_text_es: str,
) -> LegalCitation:
    """Build a curated :class:`LegalCitation` with the v1 defaults.

    Args:
        source: The :class:`LegalCitationSource` provenance.
        article: Article identifier within the source.
        url: Optional BOE / Manual práctico URL.
        quoted_text_es: Verbatim Spanish summary from the research doc.

    Returns:
        A validated :class:`LegalCitation` with
        ``retrieval_date=2026-04-13`` and
        ``is_curated_summary=True``.
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
    """Assemble a :class:`ModeloApplicability` with an auto-computed exempt bucket.

    Args:
        mandatory: Profiles that must file this modelo.
        optional: Profiles that may file this modelo.
        trigger_notes_es: Spanish prose describing the triggers.

    Returns:
        A validated :class:`ModeloApplicability`. The ``exempt``
        bucket is ``set(TaxpayerProfile) - mandatory - optional``.
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
    """Assemble a :class:`ModeloMetadata` entry for a single modelo."""
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
