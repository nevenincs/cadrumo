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

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from packaging.version import InvalidVersion, Version

from .._paths import REPO_ROOT, UTF_8
from .burned_versions import burn_reason, is_burned

_UTF_8: Final[str] = UTF_8
_PROBE_TIMEOUT_S: Final[int] = 20

#: The three projects one cohort publishes together. A conflict on any one of
#: them refuses the whole cohort: they ship as a set and a partial set is not a
#: release.
PYPI_PROJECTS: Final[tuple[str, ...]] = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)

#: The release-please manifest, whose recorded version is the monotonic floor.
MANIFEST_PATH: Final[Path] = REPO_ROOT / ".release-please-manifest.json"


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


def pypi_projects_owning(version: str, *, projects: Iterable[str] = PYPI_PROJECTS) -> tuple[str, ...]:
    """Return the projects whose index already carries ``version``.

    A 404 is the only answer that means "free". Any other failure refuses
    rather than being read as absence: an unreachable index cannot prove a
    version is available, and treating a network error as a clean result is how
    a guard silently permits the collision it exists to catch.
    """
    owning: list[str] = []
    for project in projects:
        request = urllib.request.Request(  # fixed HTTPS index endpoint.
            f"https://pypi.org/pypi/{project}/{version}/json",
            headers={"Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=_PROBE_TIMEOUT_S) as response:  # noqa: S310
                response.read(1)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise VersionIdentityError(f"index check failed for {project}: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise VersionIdentityError(f"index check failed for {project}: {exc.reason}") from exc
        owning.append(project)
    return tuple(owning)


def _forge_refs(endpoint: str, jq: str) -> tuple[str, ...]:
    """Return forge ref names, refusing rather than defaulting to empty."""
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell.
            ["gh", "api", endpoint, "--paginate", "--jq", jq],  # noqa: S607 - resolved from PATH like every dev gate.
            capture_output=True,
            text=True,
            check=True,
            timeout=_PROBE_TIMEOUT_S * 3,
        )
    except FileNotFoundError as exc:
        raise VersionIdentityError("forge check needs the gh CLI on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise VersionIdentityError(f"forge check timed out for {endpoint}") from exc
    except subprocess.CalledProcessError as exc:
        raise VersionIdentityError(f"forge check failed for {endpoint}: {exc.stderr.strip()}") from exc
    return tuple(line.strip() for line in completed.stdout.splitlines() if line.strip())


def forge_tags_owning(version: str, *, repository: str) -> tuple[str, ...]:
    """Return tags matching ``version``, whether or not a release wraps them."""
    tags = _forge_refs(f"repos/{repository}/tags", ".[].name")
    return tuple(tag for tag in tags if tag in {version, f"v{version}"})


def forge_releases_owning(version: str, *, repository: str, own_source_commit: str | None = None) -> tuple[str, ...]:
    """Return releases matching ``version``, drafts included.

    Drafts are included deliberately: a draft holds its tag, so creation would
    fail after the irreversible index upload had already happened.

    ``own_source_commit`` exempts this cohort's OWN prior attempt. A re-dispatch
    after a later step failed must converge rather than refuse, and the release
    it finds is the one it created, from this same commit. A release on any
    other commit is a genuine collision and stays refused -- the exemption is
    identity, not a bypass, so it cannot launder a foreign release.
    """
    entries = _forge_refs(f"repos/{repository}/releases", '.[] | .tag_name + " " + (.target_commitish // "")')
    return releases_owning(entries, version, own_source_commit=own_source_commit)


def releases_owning(
    entries: Iterable[str],
    version: str,
    *,
    own_source_commit: str | None = None,
) -> tuple[str, ...]:
    """Return owning tags from ``"<tag> <commit>"`` rows, exempting our own.

    Split from the network shell so the exemption rule is provable against real
    rows rather than re-implemented by a test. It is the rule most worth
    proving: getting it wrong either makes recovery impossible, by refusing a
    re-dispatch its own prior attempt, or launders a foreign release, by
    exempting one it should have refused.
    """
    owning: list[str] = []
    for entry in entries:
        tag, _, target = entry.partition(" ")
        if tag not in {version, f"v{version}"}:
            continue
        if own_source_commit is not None and target.strip() == own_source_commit:
            continue
        owning.append(tag)
    return tuple(owning)


def assert_version_available(
    version: str,
    *,
    owning_projects: Iterable[str] = (),
    existing_tags: Iterable[str] = (),
    existing_releases: Iterable[str] = (),
    manifest_path: Path | None = None,
    enforce_floor: bool = True,
) -> None:
    """Raise unless no destination owns ``version`` and no rule forbids it.

    The refusal names every owning destination, so the operator learns the whole
    problem from one run rather than one collision at a time.

    ``enforce_floor`` distinguishes the two call sites, and the distinction is
    load-bearing rather than a convenience. Sealing a cohort is not publishing
    one: the packaging lane builds and proves a cohort on every push, and
    between releases the declared version legitimately EQUALS the manifest floor
    because the bump has not happened yet. Requiring a candidate above the floor
    before a cohort may be BUILT therefore refuses every build in the interval
    where the lane does its work, which is the state the lane exists to prevent.

    Everything that makes a collision impossible survives at both sites: a
    version an index, tag, or release namespace already owns is refused when
    sealing, and so is a burned one. Only "you have not bumped yet" is deferred
    to publication, where it means what it says.
    """
    refusals = version_conflicts(
        version,
        owning_projects=owning_projects,
        existing_tags=existing_tags,
        existing_releases=existing_releases,
        floor=manifest_floor(manifest_path) if enforce_floor else None,
    )
    if refusals:
        joined = "\n  - ".join(refusals)
        raise VersionIdentityError(f"version {version} is not available to publish:\n  - {joined}")


def main(argv: list[str] | None = None) -> int:
    """Refuse a candidate version that any destination already owns.

    One authority invoked from two places: cohort seal time, where refusing
    costs nothing but a re-run, and publication Gate 2, where it is the last
    check before an irreversible upload.
    """
    parser = argparse.ArgumentParser(description="Refuse a version any destination already owns.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--repository", required=True, help="owner/name of the forge repository")
    parser.add_argument(
        "--own-source-commit",
        help="exempt a release already created by THIS cohort, so a re-dispatch converges",
    )
    parser.add_argument(
        "--scope",
        choices=("seal", "publish"),
        default="publish",
        help=(
            "seal: refuse only a version some destination already owns or that is burned, "
            "which is what a cohort BUILD must satisfy. publish: additionally require the "
            "version to exceed the manifest floor, which is what shipping must satisfy."
        ),
    )
    parser.add_argument(
        "--skip-network",
        action="store_true",
        help="check only the manifest floor and the burned ledger (offline pre-flight)",
    )
    args = parser.parse_args(argv)

    owning: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    releases: tuple[str, ...] = ()
    try:
        if not args.skip_network:
            owning = pypi_projects_owning(args.version)
            tags = forge_tags_owning(args.version, repository=args.repository)
            releases = forge_releases_owning(
                args.version,
                repository=args.repository,
                own_source_commit=args.own_source_commit,
            )

        assert_version_available(
            args.version,
            owning_projects=owning,
            existing_tags=tags,
            existing_releases=releases,
            enforce_floor=args.scope == "publish",
        )
    except VersionIdentityError as exc:
        # An operator reads this at a refusal, so it must be the message and not
        # a traceback with the message buried at the bottom.
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    reach = "floor and ledger only" if args.skip_network else "every destination"
    verb = "seal" if args.scope == "seal" else "publish"
    print(f"version {args.version} is available to {verb} ({reach} checked)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
