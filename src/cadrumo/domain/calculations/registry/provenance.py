"""Signed provenance classifications exposed by published authority evidence."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["NormativeCorpusProvenance"]


class NormativeCorpusProvenance(StrEnum):
    """The strongest provenance conclusion captured at publication time."""

    BOE_ATTESTED = "boe_attested"
    BOE_PRESUMPTIVE = "boe_presumptive"
    AUTHORED = "authored"
    OUT_OF_SCOPE = "out_of_scope"
