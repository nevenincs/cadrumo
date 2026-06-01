"""Canonical period code enumeration for filing periods.

Period codes represent the filing frequency and scheme for tax returns:
- Quarterly: 1T, 2T, 3T, 4T (standard filing periods)
- Instalment: 1P, 2P, 3P, 4P (corporate-tax/IS instalment periods)
- Annual: 0A
- Monthly: 01-12 (calendar months)
- OSS/IOSS: EXT-1T, EXT-2T, EXT-3T, EXT-4T (extra-Union scheme)
- Ad-hoc/Event: AD-HOC, EVENT-N (event-driven filings)

StandardPeriodCode is the canonical StrEnum for the basic period codes
(1T-4T, 1P-4P, 0A, 01-12). Extended forms (EXT-*, AD-HOC, EVENT-*) are
validated via separate regex patterns for modeller flexibility.
"""

from __future__ import annotations

from enum import StrEnum


class StandardPeriodCode(StrEnum):
    """Canonical enumeration of standard filing-period codes."""

    Q1 = "1T"
    Q2 = "2T"
    Q3 = "3T"
    Q4 = "4T"

    P1 = "1P"
    P2 = "2P"
    P3 = "3P"
    P4 = "4P"

    ANNUAL = "0A"

    JAN = "01"
    FEB = "02"
    MAR = "03"
    APR = "04"
    MAY = "05"
    JUN = "06"
    JUL = "07"
    AUG = "08"
    SEP = "09"
    OCT = "10"
    NOV = "11"
    DEC = "12"


__all__ = ["StandardPeriodCode"]
