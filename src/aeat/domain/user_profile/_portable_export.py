"""Portable-export bundle for cross-bucket user-profile transfer.

This module is isolated from :mod:`aeat.domain.user_profile._values` so the
four heavy domain types it composes (:class:`CalculationRevision`,
``WorkUnit``, ``Transaction``, :class:`ModeloRecord`) and their transitive
registry-parse cost do not enter ``sys.modules`` at user-profile package
init. The :class:`UserProfileRecord` is included via the ``profile`` field
of :class:`UserProfilePortableExport`. Callers that need the bundle import
directly from this canonical-site path; the package surface intentionally
does not re-export it.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time import now as utc_now
from ..modelos._calculation_revision import CalculationRevision as _CalculationRevision
from ..modelos._filing_record import ModeloRecord as _ModeloRecord
from ..modelos._work_unit import WorkUnit as _WorkUnit
from ..transactions._models import Transaction as _Transaction
from ._values import UserProfileRecord


class UserProfilePortableExport(BaseModel):
    """User-directed portable profile export payload.

    ``bundle_schema_version`` gates forward-compatible import: callers that read
    an export bundle compare this integer to their supported range before
    attempting to parse ``profile``. Increment it when the serialised shape
    changes in a backward-incompatible way.

    Version 1 is the facts-only bundle (``profile`` only) and remains
    importable. Version 2 is the full bundle — it adds ``work_units``,
    ``ledger_transactions``, ``calculation_revisions``, and
    ``filing_records``, all defaulting to empty tuples so v1 facts-only
    bundles remain importable.

    Encrypted-material blobs are NOT included (ADR D2: strip encrypted
    material; re-encrypt under recipient bucket DEK on import).
    """

    model_config = _STRICT_FROZEN

    bundle_schema_version: int = Field(default=2, ge=1)
    exported_at: datetime = Field(default_factory=utc_now)
    profile: UserProfileRecord

    # --- v2 financial-history fields -----------------------------------------
    # All default to empty tuples so v1 facts-only bundles round-trip
    # cleanly; the import path checks bundle_schema_version before reading.

    work_units: tuple[_WorkUnit, ...] = ()
    ledger_transactions: tuple[_Transaction, ...] = ()
    calculation_revisions: tuple[_CalculationRevision, ...] = ()
    filing_records: tuple[_ModeloRecord, ...] = ()


__all__ = ["UserProfilePortableExport"]
