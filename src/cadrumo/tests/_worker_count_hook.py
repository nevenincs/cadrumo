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
(``xdist.plugin.pytest_xdist_auto_num_workers``) and can win by returning an
``int``; returning ``None`` lets pluggy continue to xdist's own impl, which
itself still honours the native ``PYTEST_XDIST_AUTO_NUM_WORKERS`` env var and
then falls back to ``psutil.cpu_count()``. This composition was proved
empirically before implementation (hook wins when set; falls through
byte-identically to a no-hook control when unset; the native env var still
resolves correctly through the fallthrough; an explicit ``-n <N>`` bypasses
the hook entirely and is never consulted).

An explicit ``-n <N>`` on the command line bypasses this hook entirely (xdist
only consults ``pytest_xdist_auto_num_workers`` when ``--numprocesses=auto``
is requested), so this policy governs only the ``-n auto`` default path.

The variable is opt-in: a shared multi-agent box benefits from capping
concurrent invocations to a small worker count, while CI and a solo run --
where the variable is simply unset -- keep full-width ``auto`` sizing
untouched.
"""

from __future__ import annotations

import os
import warnings

import pytest

_ENV_VAR = "AEAT_PYTEST_WORKERS"


def resolve_auto_num_workers(config: pytest.Config) -> int | None:
    """Return the ``AEAT_PYTEST_WORKERS`` worker cap, or ``None`` to defer to xdist.

    Args:
        config: The active :class:`pytest.Config` (required by the
            ``pytest_xdist_auto_num_workers`` hook signature; unused here).

    Returns:
        The parsed integer cap when ``AEAT_PYTEST_WORKERS`` is set to a valid
        integer; ``None`` when the variable is unset, blank, or not a valid
        integer -- in every ``None`` case, resolution falls through to
        xdist's own hookimpl unchanged.
    """
    env_var = os.environ.get(_ENV_VAR)
    if not env_var:
        return None
    try:
        return int(env_var)
    except ValueError:
        warnings.warn(
            f"{_ENV_VAR} is not a number: {env_var!r}. Ignoring it.",
            stacklevel=2,
        )
        return None
