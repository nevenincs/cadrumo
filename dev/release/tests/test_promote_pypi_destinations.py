"""The pre-upload PyPI destination guard, against the live index.

Split out of ``test_promote_python_cohort`` so each module carries one execution
lane. Every other gate there builds artifacts on disk and validates a cohort
offline; this one makes real HTTP requests to pypi.org, so it is ``integration``.

The refusal path -- the version already being published -- cannot be exercised
without network mocking, which this project forbids, so only the absent case is
asserted here and the refusal stays uncovered rather than faked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...packaging.python_cohort import PythonCohort
from ..promote_python_cohort import assert_pypi_destinations_absent

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_SAMPLE_COMMIT = "a" * 40


def test_pypi_destinations_absent_passes_for_dev_version(tmp_path: Path) -> None:
    """The pre-upload guard passes when no PyPI destination owns the dev version.

    This exercises ``assert_pypi_destinations_absent`` with its real HTTP logic
    against a ``PythonCohort`` constructed directly from the public dataclass.
    The version ``0.99.0.dev1`` is a dev build that will never be published to
    PyPI, so the check is expected to find no existing distribution and return
    without raising.

    Marked ``integration`` because the function makes live HTTP requests to
    ``pypi.org``.  The refusal path (version already published) requires the
    version to be present on the live index and cannot be tested in unit scope
    without network mocking (which is forbidden).
    """
    cohort = PythonCohort(
        directory=tmp_path,
        manifest=tmp_path / "python-cohort.json",
        source_commit=_SAMPLE_COMMIT,
        version="0.99.0.dev1",
        root_wheel=tmp_path / "cadrumo.whl",
        root_sdist=tmp_path / "cadrumo.tar.gz",
        source_archive=tmp_path / "cadrumo-source.zip",
        manuals_wheel=tmp_path / "manuals.whl",
        manuals_sdist=tmp_path / "manuals.tar.gz",
        official_wheel=tmp_path / "official.whl",
        official_sdist=tmp_path / "official.tar.gz",
        sha256={},
    )

    # Must not raise: pypi.org should return 404 for this dev version.
    result = assert_pypi_destinations_absent(cohort)
    assert result is None
