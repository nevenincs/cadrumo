"""Application services for modelo work-unit lifecycle.

The modelo work-unit verbs (``create``, ``list``, ``status``,
``rename``) call into this package. The CLI layer at
``aeat.entrypoints.cli._modelo`` is a thin Typer transport over
the services exposed here.

Bucket scoping is honoured at the API boundary: every action
accepts an explicit ``bucket_id`` rather than implicitly reading
the active profile. The CLI layer derives ``bucket_id`` from the
active profile when the caller did not pass one explicitly; this
keeps the application service unit-testable without a workflow-
state fixture.
"""

from __future__ import annotations

from ._actions import (
    WorkUnitNotFoundError,
    create_work_unit,
    get_work_unit,
    list_work_units,
    rename_work_unit,
)


__all__ = [
    "WorkUnitNotFoundError",
    "create_work_unit",
    "get_work_unit",
    "list_work_units",
    "rename_work_unit",
]
