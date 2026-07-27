"""One version-identity authority covering every destination, not just one.

The guard this replaces asked a single question -- does any package index
already own this version -- and that question passed on the day it mattered
most, precisely because the package index was the one destination that did NOT
yet own the version. A published source-forge release did, and the publication
proceeded to an irreversible upload before failing on the release that already
existed. The blind spot was not that the check was wrong; it was that the check
was partial and nothing said so.

So this module asks the question of every destination a release can collide
with, and answers with the destination that owns the version rather than a bare
refusal. Four sources of conflict, each independently sufficient:

*Package indexes.* A version any of the three projects already carries. Uploads
there are irreversible, so this is the collision with no remedy.

*The tag and release namespace.* A version the source forge already carries as
a tag or a release, INCLUDING drafts. Drafts count because a draft holds the
tag: publication would fail on creation after the irreversible upload had
already happened, which is exactly the stranding that prompted this.

*The monotonic floor.* A version at or below the highest the release-please
manifest has recorded. Ordinary backward-bump protection.

*The burned ledger.* A version the world may hold bytes under, whether or not
any destination still shows it. See :mod:`dev.release.burned_versions` for why
the floor cannot express this.

The decision core is pure: it takes the observed state and returns refusals.
That keeps every conflict rule testable against real data with no test double
standing in for a destination, and confines network access to the thin shell
that gathers the state.

See Also:
    :func:`version_conflicts`
        The pure decision core: observed state in, refusals out.
    :func:`assert_version_available`
        The shell that gathers real state and raises on any conflict.
    :mod:`dev.release.burned_versions`
        The append-only record of versions no release may mint again.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from packaging.version import InvalidVersion, Version

from dev.release.burned_versions import burn_reason, is_burned

_UTF_8: Final[str] = "utf-8"

#: The three projects one cohort publishes together. A conflict on any one of
#: them refuses the whole cohort: they ship as a set and a partial set is not a
#: release.
PYPI_PROJECTS: Final[tuple[str, ...]] = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)

#: The release-please manifest, whose recorded version is the monotonic floor.
MANIFEST_PATH: Final[Path] = Path(__file__).resolve().parents[2] / ".release-please-manifest.json"


class VersionIdentityError(RuntimeError):
    """A candidate version collides with a destination that already owns it."""


def manifest_floor(manifest_path: Path | None = None) -> str:
    """Return the version the release-please manifest records for the root.

    The manifest is the floor's home rather than any destination's live state,
    because a destination can be emptied by a deletion while the manifest
    remains the record that the number was once reached.
    """
    path = manifest_path or MANIFEST_PATH
    try:
        payload = json.loads(path.read_text(encoding=_UTF_8))
    except FileNotFoundError as exc:
        raise VersionIdentityError(f"release-please manifest is absent at {path}") from exc
    except json.JSONDecodeError as exc:
        raise VersionIdentityError(f"release-please manifest is not valid JSON: {exc}") from exc
    recorded = payload.get(".") if isinstance(payload, dict) else None
    if not isinstance(recorded, str) or not recorded.strip():
        raise VersionIdentityError(f"release-please manifest records no root version in {path}")
    return recorded


def _parsed(version: str, *, label: str) -> Version:
    try:
        return Version(version)
    except InvalidVersion as exc:
        raise VersionIdentityError(f"{label} {version!r} is not a valid version") from exc


def version_conflicts(
    version: str,
    *,
    owning_projects: Iterable[str] = (),
    existing_tags: Iterable[str] = (),
    existing_releases: Iterable[str] = (),
    floor: str | None = None,
) -> tuple[str, ...]:
    """Return one refusal per destination that already owns ``version``.

    Pure: every input is observed state, so each rule is provable against real
    data. An empty result means no destination owns the version and no rule
    forbids it.

    Every conflict is reported rather than the first, because an operator fixing
    one collision should not have to re-run to discover the next.
    """
    candidate = _parsed(version, label="candidate version")
    refusals: list[str] = []

    for project in sorted(set(owning_projects)):
        refusals.append(
            f"package index already carries {project} {version}; an index upload cannot be undone, "
            "so this version can never be republished",
        )

    tags = sorted(set(existing_tags))
    if tags:
        refusals.append(
            f"the tag namespace already carries {', '.join(tags)}; publication would fail creating "
            "the release after the irreversible index upload had already happened",
        )

    releases = sorted(set(existing_releases))
    if releases:
        refusals.append(
            f"the release namespace already carries {', '.join(releases)} (drafts included, because "
            "a draft holds its tag); publication would fail creating the release",
        )

    if is_burned(version):
        refusals.append(f"version {version} is burned and can never be minted again: {burn_reason(version)}")

    if floor is not None:
        recorded = _parsed(floor, label="manifest floor")
        if candidate <= recorded:
            refusals.append(
                f"version {version} is not above the recorded floor {floor}; the manifest burns a version "
                "even after a destination that held it is deleted",
            )

    return tuple(refusals)


def assert_version_available(
    version: str,
    *,
    owning_projects: Iterable[str] = (),
    existing_tags: Iterable[str] = (),
    existing_releases: Iterable[str] = (),
    manifest_path: Path | None = None,
) -> None:
    """Raise unless no destination owns ``version`` and no rule forbids it.

    The refusal names every owning destination, so the operator learns the whole
    problem from one run rather than one collision at a time.
    """
    refusals = version_conflicts(
        version,
        owning_projects=owning_projects,
        existing_tags=existing_tags,
        existing_releases=existing_releases,
        floor=manifest_floor(manifest_path),
    )
    if refusals:
        joined = "\n  - ".join(refusals)
        raise VersionIdentityError(f"version {version} is not available to publish:\n  - {joined}")
