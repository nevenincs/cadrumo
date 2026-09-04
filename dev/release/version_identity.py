"""One version-identity authority, asking each gate only what that gate can protect.

The guard this replaces asked a single question -- does any package index
already own this version -- and that question passed on the day it mattered
most, precisely because the package index was the one destination that did NOT
yet own the version. A published source-forge release did, and the publication
proceeded to an irreversible upload before failing on the release that already
existed. The blind spot was not that the check was wrong; it was that the check
was partial and nothing said so.

So the rules below cover every destination a release can collide with, and
answer with the destination that owns the version rather than a bare refusal:

*Package indexes.* A version EVERY project in the cohort already carries.
Uploads there are irreversible, so a complete set is the collision with no
remedy: nothing is left to send and the run could only attempt bytes the index
will not take back. A set only SOME of the projects carry is a different state
and is permitted -- six files go up and that upload is not atomic, so a refused
publisher registration or a dropped connection leaves part of the cohort
published. Re-running the same tag is how that converges, and a partial set
read as a collision would refuse the remedy and spend the version for a cause
that was never a version problem. A permitted partial is always stated -- see
:func:`index_convergence_notice`.

*The tag and release namespace.* A version the source forge already carries as
a tag or a release, drafts included where the credential can see them. A draft
counts because it holds its tag; the forge lists drafts only to a caller with
push access, so a run whose credential lacks it says which releases it could
see rather than implying more -- see :func:`forge_push_access`. Both namespaces
exempt the refs belonging to the run being guarded, by commit identity -- see
:func:`refs_owning`.

*The burned ledger.* A version the world may hold bytes under, whether or not
any destination still shows it. See :mod:`dev.release.burned_versions` for why
the floor cannot express this.

*The monotonic floor.* A version strictly below the highest the release-please
manifest has recorded. Ordinary backward-bump protection, asked by the
publication gate alone -- see :func:`manifest_floor` for why the monotonic form
is unsatisfiable and this regression form is what remains.

Which of those bear on a run is not one answer but two, because the two places
this runs are not the same act:

*Sealing* a cohort uploads nothing. The packaging lane builds and proves a
cohort on every push, labelled with the version the commit declares, and
between releases that version legitimately equals the one already shipped
because the bump has not happened yet. Every collision rule states an upload as
its reason, so none of them can bear on a build that performs no upload:
refusing here would refuse the lane's entire working interval. What survives is
the ledger, which is not about a destination at all -- a burned number must
never label a cohort, because the world may already hold different bytes under
it.

*Publishing* is the upload. There the collision rules mean exactly what they
say, and this is the last check before bytes reach an index that cannot take
them back.

The decision core is pure: it takes the observed state and returns refusals.
That keeps every conflict rule testable against real data with no test double
standing in for a destination, and confines network access to the thin shell
that gathers the state.

See Also:
    :func:`version_conflicts`
        The pure decision core: observed state in, refusals out.
    :func:`index_convergence_notice`
        The pure companion that says a permitted partial upload out loud.
    :func:`gate_conflicts`
        The pure gate filter: which of those rules bear on which gate.
    :func:`assert_gate_permits`
        The shell that raises unless a gate permits the version.
    :mod:`dev.release.burned_versions`
        The append-only record of versions no release may mint again.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

from packaging.version import InvalidVersion, Version

from .._paths import REPO_ROOT, UTF_8
from .burned_versions import BurnedVersionLedgerError, burn_reason, is_burned

_UTF_8: Final[str] = UTF_8
_PROBE_TIMEOUT_S: Final[int] = 20

#: Where the per-version index metadata lives. A parameter of the probe rather
#: than a literal inside it, so both directions of "a 404 is the only answer
#: that means free" are provable against a real endpoint instead of against a
#: stand-in for :mod:`urllib`.
_PYPI_JSON_INDEX: Final[str] = "https://pypi.org/pypi"

#: The schemes an index endpoint may use. Anything else would answer from
#: somewhere other than an index, and an answer that is not an index's is
#: not evidence about a version.
_INDEX_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})

#: A Git object name: forty hex digits and nothing else.
_OBJECT_NAME: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{40}")

#: The three projects one cohort publishes together, and so the set the index
#: question is asked about: a version is owned there when every one of them
#: carries it, and part-way is a release still being delivered.
PYPI_PROJECTS: Final[tuple[str, ...]] = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)

#: The release-please manifest, whose recorded version is the monotonic floor.
MANIFEST_PATH: Final[Path] = REPO_ROOT / ".release-please-manifest.json"


class VersionIdentityError(RuntimeError):
    """A candidate version collides with a destination that already owns it."""


@dataclass(frozen=True, slots=True)
class Gate:
    """One place this authority runs, and the destinations it stands in front of.

    A gate asks about a destination only when it is the thing standing between
    the run and a write to that destination. A gate that writes nothing to a
    destination cannot prevent a collision there, so asking would refuse work
    for a reason that does not apply to it.

    The floor is asked as a REGRESSION check rather than a monotonicity one;
    :func:`manifest_floor` records why the monotonic form is unsatisfiable.
    """

    name: str
    checks_index: bool
    checks_forge: bool
    checks_floor: bool

    def summary(self) -> str:
        """Return what this gate checked, for the operator reading a pass."""
        checked: list[str] = []
        if self.checks_index:
            checked.append("the package indexes")
        if self.checks_forge:
            checked.append("the tag and release namespaces")
        if self.checks_floor:
            checked.append("the recorded floor")
        checked.append("the burned ledger")
        return ", ".join(checked)


#: Cohort build. Uploads nothing, so no collision rule bears on it: the version
#: it stamps into an artefact is a label, and labelling a build with a version
#: the world already has is how the lane proves the pipeline on an ordinary
#: commit. Only the ledger survives, because a burned number must never label
#: any bytes again.
SEAL: Final[Gate] = Gate(name="seal", checks_index=False, checks_forge=False, checks_floor=False)

#: The upload itself. Every collision rule means what it says here, and this is
#: the last thing that runs before bytes reach an index that cannot take them
#: back.
PUBLISH: Final[Gate] = Gate(name="publish", checks_index=True, checks_forge=True, checks_floor=True)

#: The gates by name, which is also the CLI's ``--scope`` vocabulary.
GATES: Final[Mapping[str, Gate]] = MappingProxyType({gate.name: gate for gate in (SEAL, PUBLISH)})


def manifest_floor(manifest_path: Path | None = None) -> str:
    """Return the version the release-please manifest records for the root.

    The manifest is the floor's home rather than any destination's live state,
    because a destination can be emptied by a deletion while the manifest
    remains the record that the number was once reached.

    Only the publication gate reads this, and only as a REGRESSION check.
    The reason the MONOTONIC form is enforced nowhere is structural rather
    than a relaxation. Release-please writes this manifest to the released
    version as part of the release change itself, so the recorded floor equals
    the declared version at every commit either gate can observe: on the branch
    between releases, on the release pull request, and at the tagged commit the
    upload runs from. ``candidate > floor`` is therefore unsatisfiable
    everywhere it could be asked, and enforcing it would refuse every build and
    every release. Monotonicity is owned by the tool that writes both numbers
    together.

    The regression form is satisfiable at exactly those commits, because the
    normal state is equality. It catches the one case the tool cannot: a
    declared version edited BELOW what has already shipped. The index rules do
    not cover it, since a number skipped on the way up was never uploaded and so
    collides with nothing, yet publishing it would order the newest bytes behind
    an older release and every resolver would keep serving the stale ones.
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


def _object_name(value: str, *, label: str) -> str:
    """Return ``value`` as a normalised object name, refusing anything else.

    The exemption below compares commits, and only a commit can identify one
    run's own refs. A release cut in the forge's web interface records a BRANCH
    in the same field a release cut from a tag records a commit in, so a bare
    branch name reaching the comparison would exempt every release that targets
    that branch -- an unbounded exemption wearing the shape of an identity
    check. Refusing anything that is not an object name is what keeps the
    exemption bounded to one commit.
    """
    normalised = value.strip().casefold()
    if _OBJECT_NAME.fullmatch(normalised) is None:
        raise VersionIdentityError(
            f"{label} {value!r} is not a 40-character object name; a branch name there would exempt "
            "every ref that targets that branch instead of this run's own",
        )
    return normalised


def version_conflicts(
    version: str,
    *,
    owning_projects: Iterable[str] = (),
    target_projects: Iterable[str] = PYPI_PROJECTS,
    existing_tags: Iterable[str] = (),
    existing_releases: Iterable[str] = (),
    floor: str | None = None,
) -> tuple[str, ...]:
    """Return one refusal per destination that already owns ``version``.

    Pure: every input is observed state, so each rule is provable against real
    data. An empty result means no destination owns the version and no rule
    forbids it. ``target_projects`` is the cohort the index question is asked
    about, passed in rather than decided at the call site, because whether the
    index owns a version is a question about the whole cohort and not about one
    project at a time.

    The index refuses a COMPLETE set only. Every project carrying the version
    leaves nothing to upload, so the run can only be an overwrite attempt. A
    partial set is the state a non-atomic six-file upload leaves behind, and
    re-running the same tag is its remedy, so it is permitted here and reported
    by :func:`index_convergence_notice` instead. A version that belongs to some
    other release is still caught by the tag and release namespaces below.

    Every conflict is reported rather than the first, because an operator fixing
    one collision should not have to re-run to discover the next.
    """
    candidate = _parsed(version, label="candidate version")
    refusals: list[str] = []

    carrying = sorted(set(owning_projects))
    targets = set(target_projects)
    if carrying and targets and targets <= set(carrying):
        refusals.append(
            f"package index already carries {version} for every project in the cohort "
            f"({', '.join(carrying)}); nothing is left to upload and an index upload cannot be undone, "
            "so this version can never be republished: cut a new version",
        )

    tags = sorted(set(existing_tags))
    if tags:
        refusals.append(
            f"the tag namespace already carries {', '.join(tags)}, which this run did not cut; the version "
            "belongs to another release, so cut a new version",
        )

    releases = sorted(set(existing_releases))
    if releases:
        refusals.append(
            f"the release namespace already carries {', '.join(releases)}, which this run was not "
            "dispatched for (drafts included, because a draft holds its tag); cut a new version",
        )

    # The canonical form, because the ledger records one spelling per number
    # while an index treats every spelling of it as the same release: `0.02.1`
    # would otherwise walk past a ledger entry for `0.2.1` and publish under a
    # number the world already holds bytes for.
    canonical = str(candidate)
    if is_burned(canonical):
        refusals.append(f"version {version} is burned and can never be minted again: {burn_reason(canonical)}")

    if floor is not None:
        recorded = _parsed(floor, label="manifest floor")
        if candidate < recorded:
            refusals.append(
                f"version {version} is below the recorded floor {floor}; the release line only moves "
                "forward, and a lower version would be ordered behind one already shipped, so every "
                "resolver would keep serving the older bytes as the newer release: cut a new version",
            )

    return tuple(refusals)


def index_convergence_notice(
    version: str,
    *,
    owning_projects: Iterable[str] = (),
    target_projects: Iterable[str] = PYPI_PROJECTS,
) -> str | None:
    """Return what a permitted partial index state must say, or ``None``.

    Pure, and the other half of the index rule: :func:`version_conflicts`
    permits a partial set, and permitting it silently would tell an operator
    that no index carries the version when some already do. A pass that
    overstates what it found is the defect this module exists to remove, so the
    permit carries its own evidence -- which projects hold the version, which
    are still missing, and that this run completes rather than replaces.

    ``None`` for the two states with nothing to say: no project carries the
    version, or every project does and :func:`version_conflicts` has already
    refused it.
    """
    carrying = sorted(set(owning_projects))
    remaining = sorted(set(target_projects) - set(carrying))
    if not carrying or not remaining:
        return None
    return (
        f"the package index already carries {version} for {', '.join(carrying)} and not yet for "
        f"{', '.join(remaining)}; this run completes that partial upload, and the files already "
        "uploaded are checked against the index rather than replaced"
    )


def gate_conflicts(
    gate: Gate,
    version: str,
    *,
    owning_projects: Iterable[str] = (),
    target_projects: Iterable[str] = PYPI_PROJECTS,
    existing_tags: Iterable[str] = (),
    existing_releases: Iterable[str] = (),
    floor: str | None = None,
) -> tuple[str, ...]:
    """Return the refusals ``gate`` draws from the observed state.

    The single expression of what separates the two gates, and pure, so the
    separation is provable from one set of real observations rather than
    inferred from which network calls a shell happened to make. An observation
    a gate does not stand in front of is dropped here, not argued about at the
    call site.
    """
    return version_conflicts(
        version,
        owning_projects=owning_projects if gate.checks_index else (),
        target_projects=target_projects,
        existing_tags=existing_tags if gate.checks_forge else (),
        existing_releases=existing_releases if gate.checks_forge else (),
        floor=floor if gate.checks_floor else None,
    )


def pypi_projects_owning(
    version: str,
    *,
    projects: Iterable[str] = PYPI_PROJECTS,
    index_url: str = _PYPI_JSON_INDEX,
) -> tuple[str, ...]:
    """Return the projects whose index already carries ``version``.

    A 404 is the only answer that means "free". Any other failure refuses
    rather than being read as absence: an unreachable index cannot prove a
    version is available, and treating a network error as a clean result is how
    a guard silently permits the collision it exists to catch.

    ``index_url`` is where the question is asked. It must address an HTTP
    endpoint: a ``file:`` or custom scheme would answer from the local disk,
    and a local file that opens is exactly the shape of "this version is
    already carried" with nothing having been asked of any index.
    """
    scheme = urllib.parse.urlsplit(index_url).scheme
    if scheme not in _INDEX_SCHEMES:
        raise VersionIdentityError(f"index endpoint {index_url!r} is not an HTTP endpoint")
    owning: list[str] = []
    for project in projects:
        request = urllib.request.Request(  # noqa: S310 - scheme checked above.
            f"{index_url}/{project}/{version}/json",
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


def forge_tags_owning(version: str, *, repository: str, own_source_commit: str | None = None) -> tuple[str, ...]:
    """Return tags matching ``version``, whether or not a release wraps them.

    ``own_source_commit`` exempts the tag this run is publishing, by the same
    identity rule the release namespace uses: the upload is dispatched FOR a
    tag, so that tag necessarily exists by the time the guard runs. A tag
    carrying this version on any other commit is a genuine collision.
    """
    entries = _forge_refs(f"repos/{repository}/tags", '.[] | .name + " " + (.commit.sha // "")')
    return refs_owning(entries, version, own_source_commit=own_source_commit)


def forge_push_access(repository: str) -> bool:
    """Return whether the credential in use has push access to ``repository``.

    The release-namespace answer's reach depends on it. The forge returns DRAFT
    releases only to a caller with push access, so a read-only credential is
    told about published releases and hears nothing about the drafts -- a
    partial answer that looks exactly like a clean one. Asking is what lets a
    run report which it got instead of implying the wider reach.
    """
    return _forge_refs(f"repos/{repository}", ".permissions.push // false") == ("true",)


#: What a run must add to its pass when it could not see draft releases. Stated
#: rather than assumed, because a draft holds its tag and an invisible one is
#: still a collision waiting at the release step after the upload.
DRAFT_BLIND_NOTICE: Final[str] = (
    "the release namespace was read with a credential that does not report push access, and the forge "
    "returns draft releases only to callers that have it; this answer covers published releases only"
)


def forge_releases_owning(version: str, *, repository: str, own_source_commit: str | None = None) -> tuple[str, ...]:
    """Return releases matching ``version``, drafts included where visible.

    Drafts are asked for deliberately: a draft holds its tag, so a later attempt
    to create the release would fail after an irreversible index upload had
    already happened. Whether they come back depends on the credential -- see
    :func:`forge_push_access`, which is how a run says which answer it got.

    ``own_source_commit`` exempts the release this run is publishing, which the
    release that cut the tag already created from this same commit. A release on
    any other commit is a genuine collision and stays refused -- the exemption
    is identity, not a bypass, so it cannot launder a foreign release.
    """
    entries = _forge_refs(f"repos/{repository}/releases", '.[] | .tag_name + " " + (.target_commitish // "")')
    return refs_owning(entries, version, own_source_commit=own_source_commit)


def refs_owning(
    entries: Iterable[str],
    version: str,
    *,
    own_source_commit: str | None = None,
) -> tuple[str, ...]:
    """Return owning ref names from ``"<name> <commit>"`` rows, exempting our own.

    One rule for both forge namespaces, and split from the network shell so it
    is provable against real rows rather than re-implemented by a test. It is
    the rule most worth proving: getting it wrong either blocks the release it
    was dispatched for, by refusing the very tag and release that dispatched it,
    or launders a foreign ref, by exempting one it should have refused.

    The exemption is object-name identity, so ``own_source_commit`` is validated
    as one and both sides are normalised before they are compared -- see
    :func:`_object_name` for the branch name that would otherwise be exempted
    wholesale.
    """
    own = None if own_source_commit is None else _object_name(own_source_commit, label="own source commit")
    owning: list[str] = []
    for entry in entries:
        name, _, target = entry.partition(" ")
        if name not in {version, f"v{version}"}:
            continue
        if own is not None and target.strip().casefold() == own:
            continue
        owning.append(name)
    return tuple(owning)


def assert_gate_permits(
    gate: Gate,
    version: str,
    *,
    owning_projects: Iterable[str] = (),
    target_projects: Iterable[str] = PYPI_PROJECTS,
    existing_tags: Iterable[str] = (),
    existing_releases: Iterable[str] = (),
    floor: str | None = None,
) -> None:
    """Raise unless ``gate`` permits ``version`` against the observed state.

    The refusal names every owning destination, so the operator learns the whole
    problem from one run rather than one collision at a time.
    """
    refusals = gate_conflicts(
        gate,
        version,
        owning_projects=owning_projects,
        target_projects=target_projects,
        existing_tags=existing_tags,
        existing_releases=existing_releases,
        floor=floor,
    )
    if refusals:
        joined = "\n  - ".join(refusals)
        raise VersionIdentityError(f"version {version} is not available to {gate.name}:\n  - {joined}")


def forge_arguments(repository: str | None, own_source_commit: str | None) -> tuple[str, str]:
    """Return the two arguments a forge check needs, refusing an under-specified ask.

    Both are demanded rather than defaulted, and demanded BEFORE any probe runs,
    so an under-specified invocation is an operator error reported in one second
    rather than a network round trip followed by a misleading collision.

    Without the repository there is nothing to ask. Without the commit, the tag
    and release this run was dispatched for look exactly like a stranger's, and
    every release would be refused moments before its upload for colliding with
    itself. The commit is validated as an object name here rather than at the
    comparison, so an argument that could only ever exempt too much is an
    operator error reported before the first probe.
    """
    if not repository:
        raise VersionIdentityError("--repository is required to ask the forge which refs own this version")
    if not own_source_commit:
        raise VersionIdentityError(
            "--own-source-commit is required: the tag and release being published already exist, and "
            "without the commit they sit on they cannot be told apart from a foreign ref",
        )
    return repository, _object_name(own_source_commit, label="--own-source-commit")


def main(argv: list[str] | None = None) -> int:
    """Refuse a candidate version the gate being run cannot let through.

    One authority, two gates. Sealing a cohort writes to no destination, so it
    refuses only a burned version. Publishing is the write, and refuses the
    destinations that own the version outright -- along with anything the pass
    itself has to disclose, which is printed before it.
    """
    parser = argparse.ArgumentParser(description="Refuse a version the named gate cannot let through.")
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--scope",
        required=True,
        choices=tuple(GATES),
        help=(
            "seal: a cohort BUILD, which uploads nothing, so only a burned version is refused. "
            "publish: the irreversible upload, which additionally refuses a version every index "
            "project already carries, a tag or release namespace that owns it, and a version below "
            "the recorded floor."
        ),
    )
    parser.add_argument("--repository", help="owner/name of the forge repository; required by --scope publish")
    parser.add_argument(
        "--own-source-commit",
        help="the commit this run's own tag and release sit on; required by --scope publish",
    )
    args = parser.parse_args(argv)

    gate = GATES[args.scope]
    owning: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    releases: tuple[str, ...] = ()
    # What the pass has to say for itself beyond "available": a state that was
    # permitted rather than absent, and a question whose answer was narrower
    # than the question. Silence about either is how a partial check reads as a
    # clean one.
    notices: list[str] = []
    try:
        # Argument validation precedes every probe: an operator who forgot a
        # flag learns that immediately, not after two network round trips.
        forge = forge_arguments(args.repository, args.own_source_commit) if gate.checks_forge else None
        if gate.checks_index:
            owning = pypi_projects_owning(args.version)
            partial = index_convergence_notice(args.version, owning_projects=owning)
            if partial is not None:
                notices.append(partial)
        if forge is not None:
            repository, own_source_commit = forge
            tags = forge_tags_owning(args.version, repository=repository, own_source_commit=own_source_commit)
            releases = forge_releases_owning(
                args.version,
                repository=repository,
                own_source_commit=own_source_commit,
            )
            if not forge_push_access(repository):
                notices.append(DRAFT_BLIND_NOTICE)

        assert_gate_permits(
            gate,
            args.version,
            owning_projects=owning,
            existing_tags=tags,
            existing_releases=releases,
            floor=manifest_floor() if gate.checks_floor else None,
        )
    except (VersionIdentityError, BurnedVersionLedgerError) as exc:
        # An operator reads this at a refusal, so it must be the message and not
        # a traceback with the message buried at the bottom. The ledger's own
        # error is caught alongside because it is raised on the seal's only
        # remaining rule, where a traceback would be the whole output.
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    for notice in notices:
        print(f"NOTE: {notice}")
    print(f"version {args.version} is available to {gate.name} ({gate.summary()} checked)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
