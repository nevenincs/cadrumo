"""Bounded operator text carried by an evidence bundle manifest.

One alias, declared here because two layers need it: the manifest model that
persists the value, and the CLI payload that projects it. The bound was written
out at both sites, identically, which is the shape that drifts silently -- the
payload can loosen or tighten without the model noticing, and the operator is
refused (or not) by whichever one they happen to reach first.

Deliberately separate from :obj:`~cadrumo.domain.modelos.filing_text.FilingNotes`,
which is shorter and requires content. A filing note is commentary an operator
attaches to a return; this is commentary attached to an evidence bundle, and the
two have no reason to move together.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

EvidenceBundleNotes = Annotated[str, StringConstraints(max_length=2000)]
"""Free operator commentary on an evidence bundle. Empty is a legitimate value."""

__all__ = ["EvidenceBundleNotes"]
