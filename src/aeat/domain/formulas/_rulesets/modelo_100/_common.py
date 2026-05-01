"""Shared helpers for Modelo 100 per-anexo per-año modules.

Centralises the trilingual label helper and the BOE URL constants the
M100 sub-package's anexos cite. Cuts boilerplate in each anexo file.
"""

from __future__ import annotations

from datetime import date

from .....core.i18n import Translatable
from ....modelos import LegalCitation, LegalCitationSource
from .._common import make_citation as _shared_make_citation

# BOE consolidated-text URLs — pinned with consult-date suffix so the
# citation traces to the exact text version used at authoring time.
LIRPF_BASE_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764"
LIS_BASE_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328"
RIRPF_BASE_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820"

LIRPF_CONSULT_2026_02_28_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764&p=20260228&tn=1"
LIS_CONSULT_2026_02_28_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328&p=20260228&tn=1"
RIRPF_CONSULT_2026_02_28_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820&p=20260228&tn=1"

# Modifying-law BOE ids referenced from anexo citations.
RD_LEY_4_2024_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2024-13066"
LEY_7_2024_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2024-26694"
LEY_12_2023_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2023-12203"
ORDEN_HAC_242_2025_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2025-5049"
ORDEN_HAC_277_2026_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2026-7041"

# Default retrieval date — every M100 sub-package citation defaults to
# 2026-04-27 unless explicitly overridden. The 2026-02-28 consult-date
# pin in the URL is independent (it identifies the BOE consolidated-text
# version), retrieval_date identifies when the human/agent consulted it.
M100_RETRIEVAL_DATE = date(2026, 4, 27)


def label(es: str, en: str, hu: str) -> Translatable:
    """Build a trilingual `Translatable` label for a casilla.

    Spanish is authoritative (matches the AEAT form text verbatim);
    English is a concise functional description; Hungarian is encoded
    per project trilingual mandate.
    """
    return {"es": es, "en": en, "hu": hu}


def cite_lirpf(article: str, quoted_text_es: str) -> LegalCitation:
    """Build a LIRPF (Ley 35/2006) citation pinned to 2026-02-28 consult."""
    return _shared_make_citation(
        LegalCitationSource.LEY,
        article,
        quoted_text_es,
        url=LIRPF_CONSULT_2026_02_28_URL,
        retrieval_date=M100_RETRIEVAL_DATE,
    )


def cite_lis(article: str, quoted_text_es: str) -> LegalCitation:
    """Build a LIS (Ley 27/2014) citation pinned to 2026-02-28 consult."""
    return _shared_make_citation(
        LegalCitationSource.LEY,
        article,
        quoted_text_es,
        url=LIS_CONSULT_2026_02_28_URL,
        retrieval_date=M100_RETRIEVAL_DATE,
    )


def cite_rirpf(article: str, quoted_text_es: str) -> LegalCitation:
    """Build a RIRPF (RD 439/2007) citation pinned to 2026-02-28 consult."""
    return _shared_make_citation(
        LegalCitationSource.REGLAMENTO,
        article,
        quoted_text_es,
        url=RIRPF_CONSULT_2026_02_28_URL,
        retrieval_date=M100_RETRIEVAL_DATE,
    )


__all__ = [
    "LEY_7_2024_URL",
    "LEY_12_2023_URL",
    "LIRPF_BASE_URL",
    "LIRPF_CONSULT_2026_02_28_URL",
    "LIS_BASE_URL",
    "LIS_CONSULT_2026_02_28_URL",
    "M100_RETRIEVAL_DATE",
    "ORDEN_HAC_242_2025_URL",
    "ORDEN_HAC_277_2026_URL",
    "RD_LEY_4_2024_URL",
    "RIRPF_BASE_URL",
    "RIRPF_CONSULT_2026_02_28_URL",
    "cite_lirpf",
    "cite_lis",
    "cite_rirpf",
    "label",
]
