"""The managed channels install what the index serves, not release assets.

Homebrew and Scoop are downstream of PyPI: the accepted distribution decision
puts the index first and makes those two channels install what it serves. Both
generators previously addressed `releases/download/v<version>/...` instead, and
no workflow attaches an asset to a release — a standing gate forbids the
packaging workflows from reaching the releases API at all. So every install
through either channel addressed a file that was never going to exist, and the
failure would have surfaced to a user rather than to CI.

Asserted against the generator sources rather than a rendered artifact, because
rendering needs a built cohort and this must fail in seconds when someone
reintroduces a release URL.
"""

from __future__ import annotations

import re
from typing import Final

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_GENERATORS: Final = (
    "packaging/homebrew/generate.py",
    "packaging/scoop/generate.py",
)

#: A release asset lives under this path on the forge. Matched as a URL
#: fragment so a formatted string assembling one is caught as readily as a
#: literal.
_RELEASE_ASSET: Final = re.compile(r"releases/download")

#: The index's stable per-project source path — the only address a generator
#: can emit before an upload, because the hashed location a file finally lives
#: at is not predictable.
_INDEX_SOURCE_ROOT: Final = "https://files.pythonhosted.org/packages/source"


def _source(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("relative", _GENERATORS)
def test_no_channel_generator_addresses_a_release_asset(relative: str) -> None:
    """The failure this prevents reaches a user, not a build."""
    offenders = [
        f"{relative}:{number}: {line.strip()}"
        for number, line in enumerate(_source(relative).splitlines(), start=1)
        if _RELEASE_ASSET.search(line) and not line.lstrip().startswith("#")
    ]

    assert offenders == [], "these lines address a release asset, and no workflow attaches one:\n  " + "\n  ".join(
        offenders
    )


def test_the_formula_addresses_the_index_for_every_cadrumo_distribution() -> None:
    """Removing the release URL is only half of it; something must replace it.

    A generator that addressed nothing would pass the check above while
    producing a formula that installs nothing, so the positive half is asserted
    too.
    """
    source = _source("packaging/homebrew/generate.py")

    assert _INDEX_SOURCE_ROOT in source, "the formula no longer addresses the index for its own distributions"


def test_the_scoop_manifest_installs_by_name_from_the_index() -> None:
    """Scoop cannot use the stable source path: it serves only sdists.

    So the manifest installs by name and exact version instead, and must carry
    no download block — an `architecture` entry exists only to fetch files, and
    a stale one would send Scoop to a URL again.
    """
    source = _source("packaging/scoop/generate.py")

    assert '"architecture"' not in source, "the manifest still declares a download block"
    assert "cadrumo=={version}" in source, "the manifest does not install by exact version from the index"
