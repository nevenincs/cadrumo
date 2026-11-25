"""Shared identifiers and fixture values for the encrypted filing-record round-trip tests."""

from __future__ import annotations

from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

BUCKET_ID = "30330300-0000-4000-8000-000000000700"
# The catalogue is one encrypted object per bucket and the repository refuses
# records from another bucket, so the fixture's records carry the same bucket
# the repository is bound to.
RECORD_BUCKET_ID = BUCKET_ID
FILING_YEAR = filing_year_envelope().horizon
PERIOD_2T = Period.from_year_and_code(FILING_YEAR, "2T")


def hex_blob(seed: str) -> str:
    """Return a stable 64-char hex blob for typed-id fixture values."""

    base = seed * 64
    return base[:64]
