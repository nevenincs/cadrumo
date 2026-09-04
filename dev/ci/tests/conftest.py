"""Fixtures the relocated CI tests still need from the package that owns them.

`test_overview_verbs.py` was moved here from `src/cadrumo/entrypoints/cli/tests`
when dev-tooling tests were relocated to their dev family homes. The fixture it
requests through ``usefixtures`` stayed behind in the CLI package's own
`conftest.py`, which pytest cannot reach across that boundary - so seven tests
have been erroring at setup with ``fixture 'overview_cli_backend' not found``
ever since, in a directory no CI lane runs.

The fixture is IMPORTED rather than reimplemented. It composes an isolated
profile storage root, an open profile session and a registered minimal profile,
and a second copy would be four shipped helpers restated in a place that cannot
notice when they change - which is the defect this campaign exists to remove,
not one to introduce while fixing an error.

A second fixture comes with it for the same reason. ``compose_runtime_ports``
is session-scoped and AUTOUSE, and an autouse fixture only reaches tests inside
its own directory tree - so the relocation silently took these tests out of the
composition that binds the real persistence and authentication adapters. Without
it the first fixture gets as far as opening a profile session and then fails on
``profile custody infrastructure has not been composed``, which is a second,
quieter consequence of the same move.

Re-exporting a fixture is what makes it visible to pytest here; the ``noqa``
marks each as used by collection rather than by any statement in this file.
"""

from __future__ import annotations

from cadrumo.conftest import compose_runtime_ports  # noqa: F401
from cadrumo.entrypoints.cli.conftest import overview_cli_backend  # noqa: F401
