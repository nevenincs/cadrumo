"""The registry verdict cache must not travel in a distribution.

It is written by a validating load, not by the repository: a green
``validate_registry`` run persists a certification so a later load can skip
re-validating an immutable bundled registry. Capturing it at build time makes
the build depend on whether local tooling has run, and the consequence is not
cosmetic. A tree that has validated yields a distribution two files larger than
a clean checkout does, and its digest then disagrees with the one a release
promoted -- which is precisely what an acquisition proof compares, so the proof
refuses against bytes that are otherwise identical.

The claim is about the built archive, so the archive is what this gate reads.
Asserting that the two paths appear in ``[tool.hatch.build.targets.*.exclude]``
answers a different question: hatchling's ``exclude`` is not the last word on
what ships. A ``force-include`` entry re-admits a path the same target still
excludes, and an ``artifacts`` glob on the shared ``[tool.hatch.build]`` layer
both target tables inherit does it for every target at once -- a layer a
target-scoped ``exclude`` read never looks at. Both were reproduced against the
real backend with every ``exclude`` entry left exactly as it stands, and both
shipped the cache.

Building this repository would not answer the question either: the cache is
untracked and absent from a checkout, so a clean-tree build sheds it whatever
the configuration says. The subject has to be a tree that carries the cache. So
the gate assembles a minimal project around this repository's own
``pyproject.toml``, plants the two files a validating load writes, and runs a
real ``uv build`` over it. The declarations are the repository's, the backend is
the real one, and the measurement is the archive members.

The filenames are read from the modules that write them rather than repeated
here, so a rename cannot leave this gate asserting a path nothing produces.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT, UTF_8
from dev.registry.compiler.identity import REGISTRY_IDENTITY_STAMP_FILENAME
from dev.registry.compiler.verdict_cache import shipped_verdict_location

from ..command_execution import run_command

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.serial]

#: Where the cache is written, relative to the repository root.
_REGISTRY_DATA_ROOT: Final = "src/cadrumo/_data/registry"

#: The shipped verdict is a sibling of the bundled AEAT registry root; derive
#: its archive member from the public registry location helper.
_BUNDLED_VERDICT_MEMBER: Final = shipped_verdict_location(Path(_REGISTRY_DATA_ROOT) / "aeat").as_posix()

#: The registry payload a distribution carries beside the cache: the published
#: authority's descriptor, which the build hook admits. It has to reach both
#: archives: without it, "the cache is absent" would also be true of a build
#: that shipped no registry data at all, or of a subject the backend never
#: populated. The authored registry tree cannot serve, because both targets
#: exclude it whole.
_CONTROL_MEMBER: Final = f"{_REGISTRY_DATA_ROOT}/authority/authority.current.json"

#: The two files a validating load persists, as source-tree relative paths.
_CACHE_MEMBERS: Final = (
    _BUNDLED_VERDICT_MEMBER,
    f"{_REGISTRY_DATA_ROOT}/{REGISTRY_IDENTITY_STAMP_FILENAME}",
)

#: The scaffolding this repository's declarations reference: the readme, the two
#: files ``license-files`` names, and the two packages the wheel target lists.
#: Only their paths matter -- nothing reads their contents.
_SCAFFOLD: Final[dict[str, str]] = {
    "README.md": "# minimal build subject\n",
    "CHANGELOG.md": "# minimal build subject\n",
    "LICENSE": "minimal build subject\n",
    "NOTICE": "minimal build subject\n",
    "THIRD_PARTY_NOTICES.md": "# minimal build subject\n",
    "SECURITY.md": "# minimal build subject\n",
    "PRIVACY.md": "# minimal build subject\n",
    "src/cadrumo/__init__.py": "",
    "src/cadrumo/py.typed": "",
    "src/cadrumo/core/external_constants.toml": "placeholder = 1\n",
    "src/cadrumo_harness/__init__.py": "",
    "src/cadrumo_harness/py.typed": "",
    "src/cadrumo_harness/_data/placeholder.json": "{}\n",
}

#: The build hook both targets declare. The subject carries the repository's own
#: copy, so its build runs the hook a release build runs.
_AUTHORITY_BUILD_HOOK: Final = "packaging/authority/hatch_build.py"

#: A stand-in published authority pair for that hook to admit, outside the
#: subject's ``.authority``: the hook reads a directory named that way as it
#: stands, so the subject needs neither a registry to compile nor a real
#: publication. The pair is content-addressed like a real one.
_PLANTED_AUTHORITY: Final = "planted-authority"
_PLANTED_DATABASE_BYTES: Final = b"stand-in authority database for a packaging subject\n"


def _plant_authority(root: Path) -> None:
    """Plant the build hook and a verifiable stand-in authority pair."""
    hook = root / _AUTHORITY_BUILD_HOOK
    hook.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO_ROOT / _AUTHORITY_BUILD_HOOK, hook)
    authority = root / _PLANTED_AUTHORITY
    authority.mkdir()
    digest = hashlib.sha256(_PLANTED_DATABASE_BYTES).hexdigest()
    database = f"authority-{digest}.sqlite3"
    (authority / database).write_bytes(_PLANTED_DATABASE_BYTES)
    descriptor = {"database": database, "database_sha256": digest, "database_size": len(_PLANTED_DATABASE_BYTES)}
    (authority / "authority.current.json").write_text(json.dumps(descriptor), encoding=UTF_8)


def _wheel_member(source_relative: str) -> str:
    """Project a source-tree path onto its position inside the built wheel."""
    return source_relative.replace("src/cadrumo/", "cadrumo/", 1)


def _plant(root: Path, extra_pyproject: str = "") -> None:
    """Assemble a build subject that carries the cache a release must shed."""
    bodies = dict(_SCAFFOLD)
    for member in _CACHE_MEMBERS:
        bodies[member] = '{"written_by": "a validating load"}\n'
    for relative, body in bodies.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding=UTF_8)
    declarations = (REPO_ROOT / "pyproject.toml").read_text(encoding=UTF_8) + extra_pyproject
    (root / "pyproject.toml").write_text(declarations, encoding=UTF_8)
    _plant_authority(root)
    for member in _CACHE_MEMBERS:
        if not (root / member).is_file():
            raise AssertionError(f"the build subject was assembled without {member}")


def _build(root: Path) -> tuple[frozenset[str], frozenset[str]]:
    """Return the sdist and wheel members of a real build of ``root``."""
    uv = shutil.which("uv")
    if uv is None:
        raise AssertionError("uv binary not found on PATH; the verdict-cache gate cannot build its subject")
    out_dir = root / "dist-out"
    completed = run_command(
        [uv, "build", "--sdist", "--wheel", "--out-dir", str(out_dir)],
        cwd=root,
        environment={**os.environ, "CADRUMO_AUTHORITY_ROOT": str(root / _PLANTED_AUTHORITY)},
    )
    if completed.returncode != 0:
        raise RuntimeError(f"uv build failed: {completed.stderr}")
    sdists = sorted(out_dir.glob("cadrumo-*.tar.gz"))
    wheels = sorted(out_dir.glob("cadrumo-*.whl"))
    if len(sdists) != 1 or len(wheels) != 1:
        raise AssertionError(f"expected one sdist and one wheel in {out_dir}; got {sdists!r} and {wheels!r}")
    with tarfile.open(sdists[0], mode="r:gz") as archive:
        sdist_members = frozenset(
            "/".join(Path(member.name).as_posix().split("/")[1:])
            for member in archive.getmembers()
            if member.isfile() and "/" in Path(member.name).as_posix()
        )
    with zipfile.ZipFile(wheels[0]) as bundle:
        wheel_members = frozenset(bundle.namelist())
    return sdist_members, wheel_members


@pytest.fixture(scope="module")
def built_members(tmp_path_factory: pytest.TempPathFactory) -> tuple[frozenset[str], frozenset[str]]:
    """Build the planted subject once under this repository's declarations."""
    root = tmp_path_factory.mktemp("verdict-cache-subject")
    _plant(root)
    return _build(root)


def test_the_control_declaration_proves_the_archives_were_measured(
    built_members: tuple[frozenset[str], frozenset[str]],
) -> None:
    """The registry payload beside the cache reaches both archives.

    Absence of the cache is evidence only when something adjacent is present.
    An archive carrying no registry data at all would otherwise satisfy the
    exclusion assertions below without the exclusion having done anything.
    """
    sdist_members, wheel_members = built_members
    assert _CONTROL_MEMBER in sdist_members, (
        f"the source distribution carries no {_CONTROL_MEMBER}, so the absence of the verdict cache "
        f"measures nothing; it listed {len(sdist_members)} member(s)"
    )
    assert _wheel_member(_CONTROL_MEMBER) in wheel_members, (
        f"the wheel carries no {_wheel_member(_CONTROL_MEMBER)}, so the absence of the verdict cache "
        f"measures nothing; it listed {len(wheel_members)} member(s)"
    )


@pytest.mark.parametrize("member", _CACHE_MEMBERS)
def test_the_verdict_cache_reaches_no_distribution(
    built_members: tuple[frozenset[str], frozenset[str]],
    member: str,
) -> None:
    """Neither built archive carries the cache, though the tree they built from does.

    The wheel is what an install receives; the sdist is what the wheel is built
    from in this project's release path, so shedding it from only one of them
    leaves the other free to carry the file.
    """
    sdist_members, wheel_members = built_members
    assert member not in sdist_members, (
        f"the source distribution ships {member}. A build run in a tree where registry validation has "
        "happened captures it, and the distribution's digest will no longer match one built from a clean "
        "checkout of the same commit."
    )
    assert _wheel_member(member) not in wheel_members, (
        f"the wheel ships {_wheel_member(member)}. A build run in a tree where registry validation has "
        "happened captures it, and the wheel's digest will no longer match the one a release promoted, "
        "which is exactly what an acquisition proof compares."
    )


def test_a_re_admitting_declaration_is_detected(tmp_path: Path) -> None:
    """The scan is proved against a build that does ship the cache.

    ``force-include`` re-admits a path the target's own ``exclude`` still names,
    so this subject differs from the one above only by a declaration that leaves
    every ``exclude`` entry standing. A gate reading those entries instead of the
    archive would report the same clean result over this build.
    """
    verdict = _BUNDLED_VERDICT_MEMBER
    re_admission = (
        "\n[tool.hatch.build.targets.sdist.force-include]\n"
        f'"{verdict}" = "{verdict}"\n'
        "\n[tool.hatch.build.targets.wheel.force-include]\n"
        f'"{verdict}" = "{_wheel_member(verdict)}"\n'
    )
    root = tmp_path / "re-admitted"
    root.mkdir()
    _plant(root, extra_pyproject=re_admission)
    sdist_members, wheel_members = _build(root)
    assert verdict in sdist_members, "the planted re-admission did not reach the sdist, so the scan proved nothing"
    assert _wheel_member(verdict) in wheel_members, (
        "the planted re-admission did not reach the wheel, so the scan proved nothing"
    )
