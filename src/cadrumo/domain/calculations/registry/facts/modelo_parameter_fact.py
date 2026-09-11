"""Runtime semantic identifiers for modelo-parameter governed facts."""

from __future__ import annotations

from enum import StrEnum


class ModeloParameterFact(StrEnum):
    """Closed fact identifiers shared by runtime consumers and dev projection."""

    M347_COUNTERPARTY_ANNUAL_THRESHOLD = "declarations.m347.counterparty-annual-threshold"
    MATERNITY_MONTHLY_DEDUCTION = "renta.maternity.monthly-deduction"
    MATERNITY_ANNUAL_CAP = "renta.maternity.annual-cap"
    MATERNITY_POST_ENROLLMENT_INCREMENT = "renta.maternity.post-enrollment-increment"
