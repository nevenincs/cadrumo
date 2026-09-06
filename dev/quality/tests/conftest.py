"""Keep this suite's rehearsal and replay roots inside pytest's own temp tree.

The rehearsal and replay code allocate their working copies under
:func:`tempfile.gettempdir` and deliberately RETAIN a root when a run is
refused, so an operator can inspect exactly what the gates saw. That is the
right behaviour for a real run and a leak under test: these suites assert
refusals by the dozen, so every pass left a directory behind in the shared
system temp. They accumulated into the thousands and eventually starved the
machine of the resources needed to launch a gate at all.

Redirecting :data:`tempfile.tempdir` per test puts those roots under the
``tmp_path`` pytest already garbage-collects, so the retain-on-refusal
behaviour is preserved exactly -- the root still survives the run that
created it, and the operator can still read it from the failure message --
without the artefacts outliving the suite.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_system_temporary_root(tmp_path: Path) -> Iterator[None]:
    """Point temp allocation at this test's own ``tmp_path`` for its duration.

    A directory rather than ``tmp_path`` itself, because the code under test
    refuses a system temporary root that is not a directory it can allocate
    inside, and because keeping the allocations in one child makes what the
    run created obvious when a test does fail.
    """
    allocations = tmp_path / "system-temp"
    allocations.mkdir()
    previous = tempfile.tempdir
    tempfile.tempdir = str(allocations)
    try:
        yield
    finally:
        tempfile.tempdir = previous
