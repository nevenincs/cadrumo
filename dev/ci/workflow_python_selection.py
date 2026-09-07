"""Resolve the interpreter selection a workflow file settles for a uv step.

The repository pins its toolchain in ``.python-version``, and the CI contract
is that every ``astral-sh/setup-uv`` consumer defers to that pin. A gate can
only read the workflow, so it has to know every channel the workflow has for
overriding the pin -- and ``with: python-version:`` is not the only one.

``UV_PYTHON`` is uv's own selection channel and it outranks the checked-in
``.python-version``. Measured against uv 0.12.8 with two identical projects
pinned to ``3.13``: the baseline built a 3.13 environment, and the same
invocation under ``UV_PYTHON=3.14`` built a 3.14 one. So a workflow that
declares ``env: {UV_PYTHON: "3.12"}`` and a bare ``setup-uv`` step runs on
3.12, while a reader that inspects only ``with:`` sees a step that declares no
override and reports the pin honoured.

Three states are kept apart, because collapsing them is the defect:

* **Overridden.** The file names a selection, through either channel. The
  effective interpreter is that value and the pin is not in play.
* **Pin-deferring.** No selection is named anywhere in scope, so uv resolves
  the ``.python-version`` in the checkout -- provided the checkout already
  happened, which is why step order matters to the caller.
* **Unsettled.** Nothing here can prove the second case holds. ``UV_PYTHON``
  reaches uv from the process environment, and on a self-hosted fleet that
  environment belongs to the machine's operator, not to this repository. A
  workflow that names no selection is deferring to a value the file cannot
  see; that is a weaker claim than "runs on the pin", and callers that need
  the stronger one must say so in the file.

Scope is the declaration only. A ``run:`` line invoking ``uv`` with an explicit
``--python`` is a per-command selection that does not travel, and is left to the
gates that read run text.
"""
from __future__ import annotations
from typing import Any, Final
__all__ = ['UV_PYTHON', 'declared_python_selection', 'uv_python_env']
UV_PYTHON: Final = 'UV_PYTHON'

def _env(container: Any) -> dict[str, Any]:
    """Return ``container``'s ``env:`` mapping, or an empty one."""
    if not isinstance(container, dict):
        return {}
    declared = container.get('env')
    return declared if isinstance(declared, dict) else {}

def uv_python_env(document: dict[str, Any], job_name: str, step_index: int) -> str | None:
    """Return the ``UV_PYTHON`` in scope for one step, innermost declaration first.

    GitHub resolves ``env:`` narrowest-wins -- step over job over workflow --
    so the search runs in that order and stops at the first declaration.

    Args:
        document: The parsed workflow document.
        job_name: The job the step belongs to.
        step_index: The step's position in that job's ``steps:`` list.

    Returns:
        The declared value, or ``None`` when no level declares one.

    Raises:
        KeyError: when ``job_name`` names no job in ``document``.
    """
    jobs = _dp_or('dev/ci/workflow_python_selection.py:74:or', lambda: document.get('jobs'), lambda: {})
    if job_name not in jobs:
        raise KeyError(f'no job named {job_name!r} in this workflow')
    job = _dp_or('dev/ci/workflow_python_selection.py:77:or', lambda: jobs[job_name], lambda: {})
    steps = _dp_or('dev/ci/workflow_python_selection.py:78:or', lambda: job.get('steps'), lambda: [])
    step = steps[step_index] if 0 <= step_index < len(steps) else None
    for scope in (_env(step), _env(job), _env(document)):
        if UV_PYTHON in scope:
            return str(scope[UV_PYTHON])
    return None

def declared_python_selection(document: dict[str, Any], job_name: str, step_index: int) -> str | None:
    """Return the interpreter selection this FILE settles for a ``setup-uv`` step.

    The step's own ``with: python-version:`` when it declares one, otherwise the
    innermost ``UV_PYTHON`` in scope. Both are selections and both outrank the
    checked-in pin, so a caller that treats only the first as an override is
    reading one of two doors.

    Args:
        document: The parsed workflow document.
        job_name: The job the step belongs to.
        step_index: The step's position in that job's ``steps:`` list.

    Returns:
        The declared selection, or ``None`` when the file names none -- the
        unsettled state, not a proof that the pin applies.

    Raises:
        KeyError: when ``job_name`` names no job in ``document``.
    """
    jobs = _dp_or('dev/ci/workflow_python_selection.py:106:or', lambda: document.get('jobs'), lambda: {})
    if job_name not in jobs:
        raise KeyError(f'no job named {job_name!r} in this workflow')
    steps = _dp_or('dev/ci/workflow_python_selection.py:109:or', lambda: (jobs[job_name] or {}).get('steps'), lambda: [])
    step = steps[step_index] if 0 <= step_index < len(steps) else None
    with_block = step.get('with') if isinstance(step, dict) else None
    if isinstance(with_block, dict) and with_block.get('python-version') is not None:
        return str(with_block['python-version'])
    return uv_python_env(document, job_name, step_index)