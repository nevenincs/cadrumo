"""Typed ``--json`` payload schemas for ``aeat config profile archive reconcile``.

Every declared payload is an :class:`OutputSchema` subclass referenced by
production-authored CommandSpec as deferred public schema targets and carried by :class:`SchemaEnvelope` through
:func:`emit_envelope`. These schemas project
:class:`~application.user_profile.ProfileBundleExportReconciliation` -- the
outcome of one crash-recovery sweep over the portable profile-bundle export
journals -- into the CLI JSON contract.

The two halves are deliberately distinct. A reconciled row is an export whose
crash-interrupted publication was resolved: its journal is gone and any leftover
cleartext staged temporary file with it. A failed row is one the sweep isolated
and left journalled for a later attempt, which matters to an operator precisely
because a journal left behind may still describe cleartext bundle bytes on disk.

See Also:
    :mod:`~entrypoints.cli._config._archive_reconcile`
        CLI transport that populates these payloads.
    :mod:`~application.user_profile`
        Application facade owning the reconciliation this module projects.
"""

from __future__ import annotations

from pydantic import Field

from cadrumo.application.user_profile.bundle_export_contracts import ProfileBundleExportPurpose

from ....core import Hex64Str
from ....core.json_contract import OutputSchema


class ReconciledProfileExportPayload(OutputSchema):
    """One crash-interrupted export the sweep resolved and cleared."""

    operation_id: Hex64Str
    destination: str = Field(min_length=1)
    purpose: ProfileBundleExportPurpose


class UnreconciledProfileExportPayload(OutputSchema):
    """One export journal the sweep isolated instead of finalising.

    ``destination`` is ``null`` when the journal itself could not be read, so
    nothing is known about it beyond its identifier. ``reason`` is the refusing
    error's class name: stable and machine-readable, and carrying no journal
    contents onto an operator-facing surface.
    """

    journal_id: str = Field(min_length=1)
    destination: str | None = None
    reason: str = Field(min_length=1)


class ProfileBundleReconcileResult(OutputSchema):
    """Outcome of one portable profile-bundle export reconciliation sweep."""

    reconciled_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    reconciled: list[ReconciledProfileExportPayload]
    failed: list[UnreconciledProfileExportPayload]


__all__ = [
    "ProfileBundleReconcileResult",
    "ReconciledProfileExportPayload",
    "UnreconciledProfileExportPayload",
]
