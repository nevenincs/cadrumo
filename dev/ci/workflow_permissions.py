"""Resolve the permissions a workflow job actually runs with.

A ``permissions:`` block is not additive. GitHub Actions lets a workflow
declare one map and each job declare its own, and a job that declares one has
its map REPLACE the workflow-level map wholesale -- it does not merge into it,
and it does not inherit the scopes it leaves out. Only a job that declares no
block at all runs under the workflow-level map.

So the declared text and the effective grant are different facts, and a gate
that reads ``document["permissions"]`` is answering a question about the
document rather than about anything that runs. That divergence is live in this
tree: two packaging workflows declare ``actions: read`` at workflow level while
a watchdog job inside each declares ``actions: write``, and the runtime obeys
the job. A least-privilege gate reading only the workflow map calls those
workflows read-only and is satisfied by any number of write-holding jobs.

Resolution is therefore per job, and this module is the one place that does it.

Absence is kept distinct from denial throughout. ``permissions: {}`` is an
explicit deny-all declaration and still replaces the workflow map; an omitted
block is not a declaration at all. Collapsing the two with ``or {}`` -- the
shape three hand-rolled resolvers in this tree reached for -- makes an
explicitly emptied job silently inherit the very grants it emptied. And where
neither level declares anything, the effective grant comes from repository
settings that no file here can see, so it is reported as unknown rather than
guessed at.
"""

from __future__ import annotations

from typing import Any, Final

__all__ = [
    "LEVELS",
    "effective_job_permissions",
    "granted_level",
    "jobs_granting",
    "jobs_with_unsettled_grant",
]

#: Permission levels in increasing order of capability. ``none`` is a real
#: declared level, distinct from a scope that was never mentioned.
LEVELS: Final = ("none", "read", "write")

#: The scalar shorthands, each standing for one level across every scope.
_SHORTHAND: Final = {"read-all": "read", "write-all": "write", "none": "none"}

_ABSENT: Final = object()


def _declared_jobs(document: dict[str, Any]) -> dict[str, Any]:
    """Return the workflow's ``jobs`` mapping, refusing a document that has none.

    ``jobs`` is mandatory in a workflow, so its absence is a broken or
    misidentified document, never a workflow that runs nothing. Defaulting it
    to an empty map is the same collapse this module refuses for
    ``permissions``, one level up: the enumerating answers below are read as
    confinement -- "no job holds this capability" -- and an empty map produces
    exactly that sentence for a document nobody could read. A renamed or
    restructured key would empty every one of those answers at once and every
    gate over them would stay green.
    """
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        raise KeyError(f"workflow declares no jobs mapping; `jobs` is {type(jobs).__name__}")
    return jobs


def effective_job_permissions(document: dict[str, Any], job_name: str) -> dict[str, str] | str | None:
    """Return the permission declaration the runtime applies to ``job_name``.

    The job's own block when it declares one -- including an empty map, which
    denies everything -- and otherwise the workflow-level block. ``None`` means
    neither level declared anything, so the grant comes from repository
    settings and is not knowable from the workflow file.
    """
    jobs = _declared_jobs(document)
    if job_name not in jobs:
        raise KeyError(f"no job named {job_name!r} in this workflow")
    declared = (jobs[job_name] or {}).get("permissions", _ABSENT)
    if declared is not _ABSENT:
        return declared  # type: ignore[no-any-return]
    return document.get("permissions")


def granted_level(document: dict[str, Any], job_name: str, scope: str) -> str | None:
    """Return the level ``job_name`` effectively holds for ``scope``.

    One of ``none``, ``read`` or ``write`` when the workflow settles it, and
    ``None`` when it does not: either no block was declared at either level, or
    a block was declared that never mentions ``scope``. A declared block that
    omits a scope grants nothing for it, so that case answers ``"none"``; only
    a wholly undeclared permission set is unknown.
    """
    resolved = effective_job_permissions(document, job_name)
    if resolved is None:
        return None
    if isinstance(resolved, str):
        return _SHORTHAND.get(resolved)
    return str(resolved.get(scope, "none"))


def jobs_granting(document: dict[str, Any], scope: str, level: str = "write") -> tuple[str, ...]:
    """Return every job whose effective grant for ``scope`` reaches ``level``.

    The confinement primitive: a caller naming the jobs allowed to hold a
    capability compares against this rather than against the workflow-level
    text, so a job added later that takes the capability is named here.
    """
    if level not in LEVELS:
        raise ValueError(f"unknown permission level {level!r}; expected one of {LEVELS}")
    floor = LEVELS.index(level)
    granted: list[str] = []
    for job_name in _declared_jobs(document):
        held = granted_level(document, job_name, scope)
        if held in LEVELS and LEVELS.index(held) >= floor:
            granted.append(job_name)
    return tuple(granted)


def jobs_with_unsettled_grant(document: dict[str, Any], scope: str) -> tuple[str, ...]:
    """Return every job whose grant for ``scope`` this file does not settle.

    ``jobs_granting`` names the jobs that provably hold a capability, and a job
    declaring no permissions at either level is not among them -- its grant comes
    from repository settings no file here can read. Absence of proof is not proof
    of absence, so a confinement gate asserting ``jobs_granting(...) == ()`` reads
    the same green for a workflow that denies the capability and for one that says
    nothing about it, and the second is only safe if the repository default is.

    This names that second case so a gate can refuse it rather than inherit its
    answer from settings. An explicit ``permissions: {}``, or a declared map that
    omits ``scope``, is settled: both grant nothing, and both are answers.
    """
    return tuple(
        str(job_name) for job_name in _declared_jobs(document) if granted_level(document, job_name, scope) is None
    )
