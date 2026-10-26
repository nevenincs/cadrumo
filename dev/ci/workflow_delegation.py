"""Recognise a workflow job that delegates to a reusable workflow of this repository.

This module used to resolve a job's ``runs-on`` to concrete runner targets --
label sets, hosted images, matrix indirection through a producer script -- so a
gate could check which machines the fleet scheduled work onto. That question is
no longer this repository's to ask: the hardware a project happens to execute
on is not part of the project, so every screen whose subject was the self-hosted
fleet has been removed, and the resolver that served them with it.

What remains is the one reading that was never about runners. A job calling a
reusable workflow stored in this repository declares no ``runs-on`` and no
``timeout-minutes`` of its own, because GitHub refuses both on a calling job. A
shape check walking the workflow directory has to recognise such a job so it
does not report those absences as defects -- a fact about delegation, not about
machines.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

#: The prefix a job's ``uses:`` carries when it calls a workflow of this repository.
_LOCAL_WORKFLOW_PREFIX: Final = "./.github/workflows/"


def calls_local_workflow(job: Mapping[str, Any]) -> bool:
    """Return whether ``job`` calls a reusable workflow stored in this repository.

    Such a job declares no ``runs-on`` and no ``timeout-minutes`` of its own:
    GitHub refuses both on a calling job, and its jobs run where the called
    workflow places them. The called file sits in the same workflow directory,
    so every census that walks that directory gates those jobs there. A call
    to a workflow outside this repository is not covered that way and is not
    matched here.
    """
    uses = job.get("uses")
    return isinstance(uses, str) and uses.startswith(_LOCAL_WORKFLOW_PREFIX) and "@" not in uses
