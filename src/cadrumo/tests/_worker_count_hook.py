"""Project-branded ``-n auto`` worker-count cap for pytest-xdist.

This module is test-infrastructure, not a production module. It is imported
from the repo-root ``conftest.py`` (mirroring the ``_marker_hook`` delegation
pattern) so every pytest invocation shape — bare ``uv run pytest``,
path-scoped runs, subprocess-spawning gates, and the justfile's
``test-unit`` recipe — resolves ``-n auto`` through the same policy.

pytest-xdist declares ``pytest_xdist_auto_num_workers`` as a
``firstresult=True`` hook: pluggy calls every registered hookimpl in LIFO
registration order and stops at the first non-``None`` return.
Conftest-registered hookimpls are registered after third-party plugins, so
this hook runs BEFORE xdist's own default implementation
(``xdist.plugin.pytest_xdist_auto_num_workers``) and wins by returning an
``int``.

Because this hook now always returns an ``int``, pluggy never reaches xdist's
own implementation on the ``-n auto`` path, so neither
``xdist.plugin.pytest_xdist_auto_num_workers`` nor the native
``PYTEST_XDIST_AUTO_NUM_WORKERS`` variable it honours participates any more.
That is deliberate -- a second, differently-spelled way to set the same number
is what let the width drift unnoticed -- and it is the one behaviour the
earlier fall-through design provided that this one does not.

An explicit ``-n <N>`` on the command line bypasses this hook entirely (xdist
only consults ``pytest_xdist_auto_num_workers`` when ``--numprocesses=auto``
is requested), so this policy governs only the ``-n auto`` default path.

The variable overrides a project DEFAULT rather than enabling an otherwise
absent cap. An opt-in cap was the original design and it did not hold: the
variable has to be remembered on every pytest invocation by every author, so
in practice it was almost never set and ``-n auto`` resolved to the machine's
full physical-core width. On a shared box running many concurrent agents that
width is multiplied by the number of simultaneous invocations, and the
observed consequence was not merely slow tests -- it was git processes killed
mid-write leaving stale zero-byte index locks that blocked commits for
everyone, and xdist workers crashing mid-run, which corrupts a run's own
pass/fail counts.

``DEFAULT_WORKER_CAP`` is therefore a default, never a ceiling: an explicitly
set ``CADRUMO_PYTEST_WORKERS`` still wins in both directions (higher or
lower), and an explicit ``-n <N>`` bypasses this hook entirely, so anyone who
deliberately asks for full width still gets it.
"""

from __future__ import annotations

import os
import warnings

import pytest

_ENV_VAR = "CADRUMO_PYTEST_WORKERS"

#: Worker count ``-n auto`` resolves to when ``CADRUMO_PYTEST_WORKERS`` is
#: absent or unparseable. Half the 12-wide physical-core default measured on
#: the shared development box, chosen to keep per-invocation parallelism
#: meaningful while leaving headroom for concurrent agents -- and for the
#: subprocess CLI invocations integration tests spawn, which are not xdist
#: workers and are governed by nothing.
DEFAULT_WORKER_CAP = 6


def resolve_auto_num_workers(config: pytest.Config) -> int:
    """Return the worker count ``-n auto`` should resolve to.

    Args:
        config: The active :class:`pytest.Config` (required by the
            ``pytest_xdist_auto_num_workers`` hook signature; unused here).

    Returns:
        The parsed integer when ``CADRUMO_PYTEST_WORKERS`` is set to a valid
        integer, otherwise :data:`DEFAULT_WORKER_CAP`. An unparseable value
        warns and falls back to the default rather than raising, so a typo
        degrades to the safe width instead of failing the run -- and instead
        of silently granting the wider machine default, which is what a
        fall-through would do.
    """
    env_var = os.environ.get(_ENV_VAR)
    if not env_var:
        return DEFAULT_WORKER_CAP
    try:
        return int(env_var)
    except ValueError:
        warnings.warn(
            f"{_ENV_VAR} is not a number: {env_var!r}. Using {DEFAULT_WORKER_CAP}.",
            stacklevel=2,
        )
        return DEFAULT_WORKER_CAP
