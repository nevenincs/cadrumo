"""Project the hardware profile and contention verdict onto ``config check`` rows.

Both render into the existing
:class:`~entrypoints.cli.config._check_payloads.CheckDependencyPayload` shape.
Semantics stay in :mod:`~application.provisioning`; this module only projects
the typed outcome onto the row contract.

The decision: ``available`` on the contention row distinguishes a MEASURED
shortfall from an UNMEASURABLE machine, and the two are not the same claim.

* A measured shortfall reports ``available`` false with the application-owned
  facts and failed-condition verdict.
* An unreadable figure keeps ``available`` **true**. Reporting fails open where
  acting fails closed: a diagnostic must not manufacture a shortfall on a
  platform it merely cannot measure.

The classification is not re-derived here. It is read from
:class:`~core.ContentionCause` on the snapshot the application layer produced,
because the attribution is application-owned evidence.

Neither row changes the command's exit contract. Like the preflight rows, they
are reported for visibility; the capability/dependency pairing owns the verdict.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.hardware import ContentionCause

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
            facts={"model_selected": False},
        )

    if snapshot.admitted:
        return DependencyStatus(
            service=CONTENTION_ROW_ID,
            available=True,
            facts=snapshot.facts,
        )

    # Unmeasurable, and ONLY unmeasurable: the acting path refuses this, the
    # report does not. A machine carrying a measured shortfall as well is
    # reported on the shortfall, which is the more actionable of the two.
    if tuple(snapshot.causes) == (ContentionCause.UNREADABLE,):
        return DependencyStatus(
            service=CONTENTION_ROW_ID,
            available=True,
            facts=snapshot.facts,
        )

    return DependencyStatus(
        service=CONTENTION_ROW_ID,
        available=False,
        facts=snapshot.facts,
        precondition_verdict=snapshot.precondition_verdict,
    )
