"""Bounded operator-supplied text carried by modelo filing records.

Three constrained string shapes recur across the modelo record models: the
label naming who acted, the reason an operator gave for discarding or amending
a revision, and the reference identifying an externally-filed return's
evidence. Each is declared here once and imported by every model that carries
it, so a bound cannot drift between the work unit, the calculation revision,
the verification report and the filing record.

This is a defining module, not a facade: nothing here re-exports, and the
models that use these aliases import them from this path.

The neighbouring :class:`FilingEvidenceReference` wrapper carries a SEPARATE
256-character reference and deliberately does not share
:obj:`EvidenceReference`. Its reference is a nominal locator admitted at the
evidence-collection boundary, while :obj:`EvidenceReference` identifies an AEAT
justificante or live capture; the bounds differ because the referents do, and
collapsing them would loosen the AEAT-facing one by 128 characters.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

ModeloActorLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
"""Who performed a modelo lifecycle action -- verified, filed, or discarded by."""

OperatorReason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
"""Why an operator discarded or amended a revision, in their own words."""

FilingNotes = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
"""Free operator commentary attached to a filing record.

Shares its bounds with :obj:`OperatorReason` and is deliberately a separate
name: a reason explains an action the operator took, notes are whatever else
they wanted recorded, and one changing length has no business moving the other.
"""

EvidenceReference = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
"""The AEAT-side identity of an externally-filed return's attested evidence."""

__all__ = ["EvidenceReference", "FilingNotes", "ModeloActorLabel", "OperatorReason"]
