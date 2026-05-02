"""Application-layer surface for filing attachment orchestration.

Re-exports the attachment service from
:mod:`aeat.domain.attachments._service` so callers in the application
and entrypoints layers depend on a stable boundary rather than reaching
into the domain module directly.
"""

from __future__ import annotations

from ...domain.attachments._service import add_attachment, list_attachments, load_attachment

__all__ = ["add_attachment", "list_attachments", "load_attachment"]
