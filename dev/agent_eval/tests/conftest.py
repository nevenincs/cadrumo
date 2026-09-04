"""The runtime composition these relocated tests lost by moving out of the package.

``compose_runtime_ports`` is declared in `src/cadrumo/conftest.py` as
session-scoped and AUTOUSE, which means it reaches every test inside that
directory tree and no test outside it. These evaluation tests open isolated CLI
runtime profiles through the shipped `cadrumo.tests.secure_sql` helpers, and
those helpers need the real persistence and authentication adapters bound - so
outside the tree they fail at setup with ``profile custody infrastructure has
not been composed``, before a single assertion runs.

Thirteen tests here were in that state. The same absence had already been found
and fixed in `dev/ci/tests`, where it accounted for twelve setup errors across
two files, one of which turned out to be guarding a performance budget that had
been over for as long as it could not start.

Imported rather than reimplemented: the composition binds more than a dozen
adapters, and a second copy would restate shipped wiring in a place with no way
to notice when it changes.
"""

from __future__ import annotations

from cadrumo.conftest import compose_runtime_ports  # noqa: F401
