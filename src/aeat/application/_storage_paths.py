"""Shared bucket-scoped storage path helper.

Every application-layer service that persists bucket-scoped files uses the
same shape: a root directory (derived from :class:`~aeat.core.config.Settings`)
is combined with a ``bucket_id`` and a file extension to produce the on-disk
path.  This module centralises that one-liner so callers stay at the
domain level and the filesystem layout is defined in a single place.

Used by:
  * :mod:`aeat.application.aggregation` - ledger record stores
  * :mod:`aeat.application.evidence` - audit evidence bundles

Usage::

    from aeat.application._storage_paths import storage_path

    path = storage_path(settings.aeat_invoices_dir / "payable", bucket_id)
"""

from __future__ import annotations

from pathlib import Path


def storage_path(root: Path, bucket_id: str, *, extension: str = ".jsonl") -> Path:
    """Return the bucket file path under *root*, creating the directory first.

    Args:
        root: The parent directory that groups all buckets for this storage
            domain.  Created (with all parents) if absent.
        bucket_id: The opaque bucket identifier that becomes the file stem.
        extension: File extension including the leading dot.  Defaults to
            ``.jsonl`` — the standard for the remaining append-friendly
            ledger record stores.

    Returns:
        ``root / f"{bucket_id}{extension}"`` — the path is not guaranteed to
        exist; callers must create it on first write.
    """
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{bucket_id}{extension}"
