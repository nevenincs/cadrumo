"""Overlap rule of the substantive-law window check.

A provision stays grounded on every edition whose covered period it overlaps,
and leaves at the first edition whose period starts after its ``effective_to``.
A provision that only starts after the edition's period has closed never
governed it. The timeline is anchored on the support floor so the relations
hold wherever the floor sits.
"""

from __future__ import annotations

from datetime import date

import pytest

from ..schema import ModeloRevision
from ..schema_references import LegalReference, PeriodSelector
from ..snapshot import legal_window_covers_devengo
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_YEAR = filing_year_envelope().floor + 1


def _revision() -> ModeloRevision:
    """A closed edition covering the first half of one year."""
    return ModeloRevision(
        id=f"{_YEAR}-fixture",
        localization_key="fixture",
        valid_from=date(_YEAR, 1, 1),
        valid_to=date(_YEAR, 8, 31),
        period_selector=PeriodSelector(year_from=_YEAR, year_to=_YEAR, periods=("1T",)),
        legal_refs=("ley-37-1992:art-103-fixture",),
        source_refs=("aeat-fixture-procedure",),
    )


def _reference(effective_from: date, effective_to: date | None) -> LegalReference:
    return LegalReference.model_validate(
        {
            "id": "ley-37-1992:art-fixture-overlap",
            "evidence_tier": "legal_authority",
            "authority": "boe",
            "kind": "ley",
            "corpus_ref": "corpus/normatives/html/ley-37-1992.html#a103",
            "document_id": "BOE-A-1992-28740",
            "article": "103",
            "permalink": "https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a103",
            "published_at": date(_YEAR - 3, 12, 29),
            "required_text": ("regla de prorrata",),
            "effective_from": effective_from,
            "effective_to": effective_to,
            "review_status": "agent_reviewed",
            "reviewed_at": date(1980, 9, 4),
            "reviewed_by": "fixture for the overlap rule; not authored into the tree",
        },
    )


def test_a_provision_expiring_inside_the_edition_is_still_grounded() -> None:
    """Overlap: the edition is still partly inside the provision's window."""
    assert legal_window_covers_devengo(_revision(), _reference(date(_YEAR - 2, 1, 1), date(_YEAR, 6, 30)))


def test_a_provision_that_expired_before_the_edition_is_refused() -> None:
    """Fully before: the edition's period starts after the provision's last day."""
    assert not legal_window_covers_devengo(_revision(), _reference(date(_YEAR - 2, 1, 1), date(_YEAR - 1, 12, 31)))


def test_a_provision_that_starts_after_the_edition_is_refused() -> None:
    """Fully after: the provision enters force once the period has closed."""
    assert not legal_window_covers_devengo(_revision(), _reference(date(_YEAR, 9, 1), None))
