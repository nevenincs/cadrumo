"""Shared helpers for Modelo 100 per-anexo per-año modules.

Centralises the multilingual label helper :func:`label` and the BOE URL
constants the M100 sub-package's anexos cite via :func:`cite_lirpf`,
:func:`cite_lis` and :func:`cite_rirpf`. Cuts boilerplate in each anexo
file.
"""

from __future__ import annotations

from datetime import date

from .....core.i18n import Translatable
from ....modelos import LegalCitation, LegalCitationSource
from .._common import make_citation as _shared_make_citation

# BOE consolidated-text URLs — pinned with consult-date suffix so the
# citation traces to the exact text version used at authoring time.

LIRPF_CONSULT_2026_02_28_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764&p=20260228&tn=1"
LIS_CONSULT_2026_02_28_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328&p=20260228&tn=1"
RIRPF_CONSULT_2026_02_28_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820&p=20260228&tn=1"

# Modifying-law BOE ids referenced from anexo citations.

# Default retrieval date — every M100 sub-package citation defaults to
# 2026-04-27 unless explicitly overridden. The 2026-02-28 consult-date
# pin in the URL is independent (it identifies the BOE consolidated-text
# version), retrieval_date identifies when the human/agent consulted it.
M100_RETRIEVAL_DATE = date(2026, 4, 27)


def label(es: str, en: str, hu: str) -> Translatable:
    """Build a multilingual :class:`~aeat.core.i18n.Translatable` label for a casilla.

    Spanish is authoritative — it matches the AEAT form text verbatim;
    English is a concise functional description; Hungarian is encoded
    per the project multilingual mandate.

    Args:
        es: Spanish (authoritative) label text.
        en: English label text.
        hu: Hungarian label text.

    Returns:
        Mapping of the three locale codes to their respective texts.
    """
    return {"es": es, "en": en, "hu": hu}


def cite_lirpf(article: str, quoted_text_es: str) -> LegalCitation:
    """Build a LIRPF (Ley 35/2006) citation pinned to the 2026-02-28 consult.

    Args:
        article: LIRPF article reference (for example ``"20"`` or ``"23.2"``).
        quoted_text_es: Authoritative Spanish quotation from the BOE
            consolidated text.

    Returns:
        A :class:`~aeat.domain.modelos.LegalCitation` anchored to the
        LIRPF consolidated text URL.
    """
    return _shared_make_citation(
        LegalCitationSource.LEY,
        article,
        quoted_text_es,
        url=LIRPF_CONSULT_2026_02_28_URL,
        retrieval_date=M100_RETRIEVAL_DATE,
    )


def cite_lis(article: str, quoted_text_es: str) -> LegalCitation:
    """Build a LIS (Ley 27/2014) citation pinned to the 2026-02-28 consult.

    Args:
        article: LIS article reference (for example ``"12.1.a"``).
        quoted_text_es: Authoritative Spanish quotation from the BOE
            consolidated text.

    Returns:
        A :class:`~aeat.domain.modelos.LegalCitation` anchored to the
        LIS consolidated text URL.
    """
    return _shared_make_citation(
        LegalCitationSource.LEY,
        article,
        quoted_text_es,
        url=LIS_CONSULT_2026_02_28_URL,
        retrieval_date=M100_RETRIEVAL_DATE,
    )


def cite_rirpf(article: str, quoted_text_es: str) -> LegalCitation:
    """Build a RIRPF (RD 439/2007) citation pinned to the 2026-02-28 consult.

    Args:
        article: RIRPF article reference (for example ``"30"`` or ``"90"``).
        quoted_text_es: Authoritative Spanish quotation from the BOE
            consolidated text.

    Returns:
        A :class:`~aeat.domain.modelos.LegalCitation` anchored to the
        RIRPF consolidated text URL.
    """
    return _shared_make_citation(
        LegalCitationSource.REGLAMENTO,
        article,
        quoted_text_es,
        url=RIRPF_CONSULT_2026_02_28_URL,
        retrieval_date=M100_RETRIEVAL_DATE,
    )


__all__ = [
    "LIRPF_CONSULT_2026_02_28_URL",
    "M100_RETRIEVAL_DATE",
    "cite_lirpf",
    "cite_lis",
    "cite_rirpf",
    "label",
]
