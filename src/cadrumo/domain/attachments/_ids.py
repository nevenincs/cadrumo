"""Typed id alias for :class:`Attachment` records.

:data:`AttachmentId` pins the hex-64 sha-256 shape persisted by the
:class:`AttachmentCatalogue`. The alias lives in the attachment domain
package because the attachment domain owns both the catalogue-key shape
and the persisted-record contract; consumers in :mod:`application.evidence`
and :mod:`application.ledger` import the alias under its public name.
"""

from __future__ import annotations

from ...core import Hex64Str

AttachmentId = Hex64Str
"""Hex-64 content-addressed attachment identity."""

__all__ = ("AttachmentId",)
