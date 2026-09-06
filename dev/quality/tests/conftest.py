"""Keep this suite's rehearsal and replay roots inside pytest's own temp tree.

The rehearsal and replay code allocate their working copies under
:func:`tempfile.gettempdir` and deliberately RETAIN a root when a run is
refused, so an operator can inspect exactly what the gates saw. That is the
right behaviour for a real run and a leak under test: these suites assert
refusals by the dozen, so every pass left a directory behind in the shared
system temp. They accumulated into the thousands and eventually starved the
machine of the resources needed to launch a gate at all.

Redirecting :data:`tempfile.tempdir` per test puts those roots under the base
directory pytest already garbage-collects, so the retain-on-refusal behaviour
is preserved exactly -- the root still survives the run that created it, and
the operator can still read its path from the failure message -- without the
artefacts outliving the suite.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _isolated_system_temporary_root(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Point temp allocation at a directory beside this test's ``tmp_path``.

    Beside rather than inside: several tests in this suite prove that a failed
    staging attempt leaves NOTHING behind by enumerating ``tmp_path``, and a
    directory of ours within it would be counted as debris and fail them. The
    factory's base is still pytest-owned, so what the code under test retains
    is still collected with the run.
    """
    allocations = tmp_path_factory.mktemp("object-name-system-temp")
    previous = tempfile.tempdir
    tempfile.tempdir = str(allocations)
    try:
        yield
    finally:
        tempfile.tempdir = previous
