"""Project the hardware profile and contention verdict onto ``config check`` rows.

Both render into the EXISTING
:class:`~entrypoints.cli._config._check_payloads.CheckDependencyPayload` shape,
so the doctor gains two rows and no payload change. Semantics stay in
:mod:`~application.provisioning`; what lives here is the mapping onto the row
contract plus one decision the row shape forces, described below.

The decision: ``available`` on the contention row distinguishes a MEASURED
shortfall from an UNMEASURABLE machine, and the two are not the same claim.

* A measured shortfall -- the runtime's own residents, or a peer process,
  accounting for the gap -- is a real state with a real remediation, so the row
  reports ``available`` false and carries that remediation. That is the shape
  the doctor already uses for "not provisioned, here is the fix".
* An unreadable figure keeps ``available`` **true** and says so in the detail.
  Reporting fails open where acting fails closed: a diagnostic must not
  manufacture a shortfall on a platform it merely cannot measure, and
  :func:`~application.provisioning.probe_local_inference_hardware` already sets
  that direction for the profile row.

The classification is not re-derived here. It is read from
:class:`~core.ContentionCause` on the snapshot the application layer produced,
because attributing a shortfall is exactly the judgement that module owns --
telling an operator to unload a model when the pressure is another
application's would be a false instruction.

Neither row changes the command's exit contract. Like the preflight rows, they
are reported for visibility; the capability/dependency pairing owns the verdict.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core import ContentionCause

if TYPE_CHECKING:
    from ....application.provisioning import ContentionSnapshot, DependencyStatus

__all__ = ["CONTENTION_ROW_ID", "contention_row"]

CONTENTION_ROW_ID = "local-inference-contention"
"""Stable row id, alongside ``local-inference-hardware`` from the profile probe."""


def contention_row(snapshot: ContentionSnapshot | None) -> DependencyStatus:
    """Return the ``config check`` row for a model-load contention verdict.

    Args:
        snapshot: The measured verdict, or ``None`` when no model could be
            selected for the role and there is therefore nothing to assess.

    Returns:
        A :class:`~application.provisioning.DependencyStatus` on the
        :data:`CONTENTION_ROW_ID` row.
    """
    from ....application.provisioning import DependencyStatus

    if snapshot is None:
        return DependencyStatus(
            service=CONTENTION_ROW_ID,
            available=True,
            detail="no model is selected for local inference, so there is no load to assess",
        )

    if snapshot.admitted:
        return DependencyStatus(
            service=CONTENTION_ROW_ID,
            available=True,
            detail=snapshot.detail,
        )

    # Unmeasurable, and ONLY unmeasurable: the acting path refuses this, the
    # report does not. A machine carrying a measured shortfall as well is
    # reported on the shortfall, which is the more actionable of the two.
    if tuple(snapshot.causes) == (ContentionCause.UNREADABLE,):
        return DependencyStatus(
            service=CONTENTION_ROW_ID,
            available=True,
            detail=f"unverified: {snapshot.detail}",
            remediation=snapshot.remediation,
        )

    return DependencyStatus(
        service=CONTENTION_ROW_ID,
        available=False,
        detail=snapshot.detail,
        remediation=snapshot.remediation,
    )
