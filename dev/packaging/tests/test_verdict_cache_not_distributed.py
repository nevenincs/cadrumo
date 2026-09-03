"""The registry verdict cache must not travel in a distribution.

It is written by a validating load, not by the repository: a green
``validate_registry`` run persists a certification so a later load can skip
re-validating an immutable bundled registry. Capturing it at build time makes
the build depend on whether local tooling has run, and the consequence is not
cosmetic. A tree that has validated yields a distribution two files larger than
a clean checkout does, and its digest then disagrees with the one a release
promoted -- which is precisely what an acquisition proof compares, so the proof
refuses against bytes that are otherwise identical.

The filenames are read from the modules that write them rather than repeated
here, so a rename cannot leave this gate asserting a path nothing produces.
"""

from __future__ import annotations

import tomllib
from typing import Final

import pytest

from cadrumo.domain.calculations.registry._verdict_cache import _BUNDLED_VERDICT_FILENAME
from cadrumo.domain.calculations.registry.identity import REGISTRY_IDENTITY_STAMP_FILENAME

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Where the cache is written, relative to the repository root.
_REGISTRY_DATA_ROOT: Final = "src/cadrumo/_data/registry"


def _excluded_paths(target: str) -> set[str]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    return set(pyproject["tool"]["hatch"]["build"]["targets"][target].get("exclude", []))


@pytest.mark.parametrize("target", ["wheel", "sdist"])
@pytest.mark.parametrize("filename", [_BUNDLED_VERDICT_FILENAME, REGISTRY_IDENTITY_STAMP_FILENAME])
def test_the_verdict_cache_is_excluded_from_every_distribution(target: str, filename: str) -> None:
    """Both build targets refuse the cache, and both matter.

    The wheel is what an install receives; the sdist is what the wheel is built
    from in this project's release path, so an exclusion on only one of them
    leaves the other free to carry the file.
    """
    expected = f"{_REGISTRY_DATA_ROOT}/{filename}"

    assert expected in _excluded_paths(target), (
        f"the {target} build does not exclude {expected}. A build run in a tree where registry "
        "validation has happened will capture it, and the distribution's digest will no longer "
        "match one built from a clean checkout of the same commit."
    )
