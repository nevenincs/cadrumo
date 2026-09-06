"""The published source distribution ships no test tree.

The wheel's test exclusion is asserted post-build elsewhere; the sdist's is not
asserted anywhere. That asymmetry matters more than it looks -- a test tree is a
distribution surface nobody reviews, and this project's fixtures carry document
specimens. The build configuration excludes ``src/cadrumo/**/tests`` from the
sdist target, but an exclude is a declaration that can rot silently: hatchling
matches include and exclude patterns with gitwildmatch semantics, so an
unanchored or mistyped entry changes what ships without changing what the
configuration appears to say.

So this gate reads the members of a real ``uv build --sdist`` archive. It is
floored: an archive that listed nothing, or a build that produced no archive,
raises rather than reading as a clean absence of test members. No mock and no
source-tree proxy -- a proxy would police the repository layout, which is not
what a consumer downloads.
"""

from __future__ import annotations

import shutil
import subprocess
import tarfile
from pathlib import PurePosixPath

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: A real source distribution of this project carries tens of thousands of
#: members. The floor only has to sit far enough above zero that a truncated or
#: empty archive can never be mistaken for one that simply holds no test module.
_MINIMUM_SDIST_MEMBERS = 100


def _test_members(members: frozenset[str]) -> list[str]:
    """Return every member that lives under a ``tests`` package directory."""
    return sorted(name for name in members if "tests" in PurePosixPath(name).parts)


def _assert_populated(members: frozenset[str]) -> None:
    """Refuse a member set too small to have measured anything."""
    if len(members) < _MINIMUM_SDIST_MEMBERS:
        raise AssertionError(
            f"the source distribution listed {len(members)} member(s), below the "
            f"{_MINIMUM_SDIST_MEMBERS} floor; an empty or truncated archive would "
            "otherwise read as carrying no test tree",
        )


@pytest.fixture(scope="module")
def sdist_members(tmp_path_factory: pytest.TempPathFactory) -> frozenset[str]:
    """Build the real source distribution and return its archive-relative members."""
    uv = shutil.which("uv")
    if uv is None:
        raise AssertionError("uv binary not found on PATH; the sdist test-tree gate cannot build its subject")
    out_dir = tmp_path_factory.mktemp("sdist-test-tree")
    subprocess.run(  # noqa: S603 - argv is an explicit internal build command.
        [uv, "build", "--sdist", "--out-dir", str(out_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    archives = sorted(out_dir.glob("cadrumo-*.tar.gz"))
    if len(archives) != 1:
        raise AssertionError(f"expected exactly one cadrumo-*.tar.gz in {out_dir}; got {[p.name for p in archives]!r}")
    with tarfile.open(archives[0], mode="r:gz") as archive:
        return frozenset(
            PurePosixPath(*PurePosixPath(member.name).parts[1:]).as_posix()
            for member in archive.getmembers()
            if member.isfile() and len(PurePosixPath(member.name).parts) > 1
        )


@pytest.mark.timeout(900)
def test_sdist_ships_no_test_member(sdist_members: frozenset[str]) -> None:
    """No file under any ``tests/`` package reaches the source distribution."""
    _assert_populated(sdist_members)
    offenders = _test_members(sdist_members)
    assert not offenders, (
        f"the source distribution ships {len(offenders)} test member(s) the sdist exclude should have shed; "
        f"first ten: {offenders[:10]!r}"
    )


def test_the_detector_reports_a_planted_test_member() -> None:
    """The offender scan is asserted against a deliberately wrong expectation.

    A gate whose scan silently matched nothing would report the same clean
    result over a distribution that did ship a test tree, so the scan is proved
    on a member set that carries one.
    """
    planted = "src/cadrumo/domain/tests/test_specimen_fixture.py"
    members = frozenset({"src/cadrumo/domain/calculations.py", "src/cadrumo/py.typed", planted})
    assert _test_members(members) == [planted]
    assert _test_members(frozenset({"src/cadrumo/domain/calculations.py"})) == []


def test_an_unmeasured_archive_cannot_read_as_clean() -> None:
    """The floor refuses a member set an empty or failed build would produce."""
    with pytest.raises(AssertionError, match="below the"):
        _assert_populated(frozenset())
    with pytest.raises(AssertionError, match="below the"):
        _assert_populated(frozenset({"pyproject.toml"}))
    _assert_populated(frozenset(f"src/cadrumo/module_{index}.py" for index in range(_MINIMUM_SDIST_MEMBERS)))
