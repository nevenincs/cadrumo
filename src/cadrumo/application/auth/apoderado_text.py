"""Bounded operator commentary on a configured apoderamiento.

The bound sat on the service model that persists the record and again on the
CLI payload that projects it, spelled identically at both. Identical is the
dangerous case rather than the safe one: nothing fails while they agree, so the
day one side is adjusted the other keeps its own answer and the operator is
refused, or not, depending on which surface they reached.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

ApoderadoNotes = Annotated[str, StringConstraints(max_length=500)]
"""Free operator commentary on an apoderamiento. Empty is a legitimate value.

Short by design: this annotates a delegation record, not a filing. Where an
operator needs to explain reasoning at length, that belongs with the work the
delegation authorises rather than with the grant itself.
"""

__all__ = ["ApoderadoNotes"]
