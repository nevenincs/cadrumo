"""The working-tree identity canary, and the proofs that it can actually fire.

The gate itself is one assertion: no TRACKED data payload in this repository
carries a checksum-valid Spanish taxpayer identity. Everything else here exists
because that assertion is worthless on its own -- a scanner that enumerates
nothing, or whose checksum never rejects anything, or whose exclusions have
quietly grown to cover the tree, reports the same clean result as a clean
repository.

Untracked and ignored content is swept just as hard and reported in a separate
non-blocking tier, because a credential file is expected to hold the operator's
own identity. The tier is keyed on tracking state and never on a path, and the
proof that matters plants one value in a tracked file and an ignored file at
once: the tracked copy must red while the ignored copy only reports. A tier that
could be reached by naming a directory would be an escape route, and a path
exclusion for the environment file is the blindness this module was rebuilt to
remove.

The positive controls run against a REAL temporary git repository rather than a
patched enumerator, so what they prove is that the real code path finds a real
planted value in a real file. Nothing under ``src/`` or ``dev/`` is mutated to
make them work.

A specimen repository carries a real ``.gitignore`` wherever the ignore path is
the thing under test, and a separate proof confirms git really does ignore the
planted file. Specimens without one exercise the untracked path, which is a
different path: a control that plants an unignored file while citing the ignore
scenario proves the scenario it names was never run.

The whole-tree sweeps are computed once per module. Each costs tens of thousands
of file operations, this lane runs pytest in parallel, and the working copy is
network-backed, so repeating a sweep per assertion buys nothing but I/O.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ...sanitizer import ResidualKind
from .._tree_scan import (
    BLOCKING_KINDS,
    BLOCKING_TRACKING,
    DATA_SUFFIXES,
    EXCLUDED_PATH_FRAGMENTS,
    SCANNED_SUFFIXES,
    UNENUMERATED_PATH_FRAGMENTS,
    UNENUMERATED_ROOT_PREFIXES,
    UNENUMERATED_ROOT_SUFFIXES,
    CandidateFile,
    FileTracking,
    TreeFinding,
    TreeScan,
    advisory_findings,
    exclusion_reason,
    matching_fragments,
    repository_files,
    scan_tree,
    unenumerated_reason,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT

#: This module's own path, as the scan reports it.
#:
#: The advisory census counts every ``.py`` file in the tree, this one included,
#: so the planted constants below are themselves part of the population the
#: observability tripwire measures. Left in, the tripwire could never fire: the
#: bucket for this package was exactly one occurrence, and that occurrence was
#: the specimen written to prove the scanner works.
_CANARY_TEST_MODULE = Path(__file__).resolve().relative_to(_REPO_ROOT).as_posix()

#: A checksum-valid identity PLANTED into temporary specimens to prove the scan
#: fires. The body is all zeros and ``T`` is its AEAT control letter, so it cannot
#: resemble a real document; it is the same all-zero specimen the sanitiser's
#: residual-identity gate plants, deliberately, so this project keeps ONE
#: recognisable planted value rather than minting a new one per gate.
#:
#: It is a positive control, not a test double: no collaborator is substituted,
#: and the real scanner really reads it off a real disk.
_PLANTED_NIF = "00000000T"

#: The same shape with the wrong control letter. The pattern matches it and the
#: checksum must reject it -- which is the only thing standing between this canary
#: and a gate that fires on every eight-digit run in the repository.
_PLANTED_SHAPE_ONLY = "00000000X"

#: The legal-entity and ES-prefixed spellings of the same all-zero convention.
#:
#: A gate carrying only the personal shape reports a payload naming a company by
#: its tax identity as clean, and the prefixed spelling hides every shape behind
#: two alphanumeric characters. Both are as unmistakably synthetic as the
#: personal specimen above.
_PLANTED_CIF = "B00000000"
_PLANTED_NIF_IVA = "ES00000000T"


def _git(*arguments: str, cwd: Path) -> None:
    """Run one git command in ``cwd``, failing loudly."""
    executable = shutil.which("git")
    assert executable is not None, "git is required to build the specimen repository"
    subprocess.run([executable, *arguments], cwd=cwd, check=True, capture_output=True)  # noqa: S603


def _git_output(*arguments: str, cwd: Path) -> list[str]:
    """One git command's stdout in ``cwd``, as lines."""
    executable = shutil.which("git")
    assert executable is not None, "git is required to build the specimen repository"
    completed = subprocess.run(  # noqa: S603
        [executable, *arguments], cwd=cwd, check=True, capture_output=True, text=True
    )
    return [line for line in completed.stdout.splitlines() if line]


@pytest.fixture
def specimen_repository(tmp_path: Path) -> Iterator[Path]:
    """A real git repository outside this tree, for planting values into.

    Built rather than patched: the canary enumerates through ``git ls-files``, so
    a specimen that is not a git repository would exercise a different code path
    than the one guarding this project.
    """
    _git("init", "--quiet", cwd=tmp_path)
    yield tmp_path


@pytest.fixture(scope="module")
def repository_files_once() -> list[CandidateFile]:
    """One enumeration of this working tree, shared by every whole-tree assertion.

    Enumerating and reading the tree costs tens of thousands of file operations,
    and this lane runs pytest in parallel over a network-backed working copy that
    fails under concurrent I/O. Three independent sweeps in one module was three
    times that cost for one answer.
    """
    return repository_files(_REPO_ROOT, suffixes=SCANNED_SUFFIXES)


@pytest.fixture(scope="module")
def repository_scan(repository_files_once: list[CandidateFile]) -> TreeScan:
    """The blocking-scope sweep of this working tree, computed once."""
    return scan_tree(_REPO_ROOT, files=repository_files_once)


@pytest.fixture(scope="module")
def repository_advisory(repository_files_once: list[CandidateFile]) -> tuple[TreeFinding, ...]:
    """The advisory census of this working tree, computed once."""
    return advisory_findings(_REPO_ROOT, files=repository_files_once)


def test_the_working_tree_carries_no_identity_in_a_tracked_data_payload(repository_scan: TreeScan) -> None:
    """The gate. A taxpayer identity in a TRACKED payload is a leak.

    Tracked content ships, reaches every clone and cannot be taken back out of
    history, which is what makes an identity there different in kind from one in
    an ignored credential file. The failure message lists locations only. It
    cannot disclose a value, which is what makes it safe to print in CI output
    that anyone can read.
    """
    assert repository_scan.files_scanned > 0, "the canary enumerated no files, so a clean verdict proves nothing"
    assert not repository_scan.findings, (
        f"{len(repository_scan.findings)} checksum-valid taxpayer identities in tracked data payloads "
        f"(values withheld):\n{repository_scan.render()}"
    )


def test_every_blocking_finding_would_come_from_tracked_content(repository_scan: TreeScan) -> None:
    """The tier must not be a route by which anything escapes the blocking set.

    A tier keyed on tracking state is only honest while the two sides stay
    disjoint and exhaustive: every blocking finding tracked, every operator
    finding not. A classification bug that quietly moved a tracked file into the
    operator tier would leave the gate green over the exact case it exists for,
    and nothing else here would notice.
    """
    assert all(finding.tracking in BLOCKING_TRACKING for finding in repository_scan.findings)
    assert not any(finding.tracking in BLOCKING_TRACKING for finding in repository_scan.operator_findings), (
        "tracked content reached the non-blocking tier, so the tier is an escape route:\n"
        + repository_scan.render_operator()
    )


def test_no_enumerated_file_was_silently_skipped(repository_scan: TreeScan) -> None:
    """A file the sweep could not open must be named, not absorbed.

    An unopenable file contributes no findings, so a scanner that swallowed the
    error would report the same clean verdict whether it read the file or not --
    and would still have counted it towards the number that is supposed to
    evidence the sweep. In a security scanner a silent skip is the defect.
    """
    assert repository_scan.unreadable == (), (
        "the sweep enumerated files it could not open, so its clean verdict does not cover them:\n"
        + "\n".join(f"  {relative}" for relative in repository_scan.unreadable)
    )


def test_a_planted_identity_in_a_data_payload_is_found(specimen_repository: Path) -> None:
    """The gate bites: plant a checksum-valid identity in a payload, get a finding."""
    payload = specimen_repository / "captured.json"
    payload.write_text(f'{{"taxpayer": "{_PLANTED_NIF}"}}', encoding="utf-8")
    _git("add", "captured.json", cwd=specimen_repository)

    scan = scan_tree(specimen_repository)

    assert [finding.path for finding in scan.findings] == ["captured.json"]
    assert scan.findings[0].line == 1
    assert scan.findings[0].kind in BLOCKING_KINDS


def test_an_untracked_payload_is_scanned_into_the_operator_tier(specimen_repository: Path) -> None:
    """A file that was never added to the index is scanned, and does not block.

    This covers the untracked case only. The specimen carries no ``.gitignore``,
    so nothing here exercises the ignore path; that is the separate proof below,
    and conflating the two is how a scanner came to be believed to cover ignored
    files while omitting them.
    """
    payload = specimen_repository / "never-added.csv"
    payload.write_text(f"nif,importe\n{_PLANTED_NIF},100\n", encoding="utf-8")

    scan = scan_tree(specimen_repository)

    assert scan.findings == ()
    assert [finding.path for finding in scan.operator_findings] == ["never-added.csv"]
    assert scan.operator_findings[0].tracking is FileTracking.UNTRACKED


def test_a_planted_identity_in_a_gitignored_environment_file_is_reported(specimen_repository: Path) -> None:
    """The ignore path, on a specimen shaped like the exposure that motivated this.

    Everything here is load bearing and none of it was exercised before: a REAL
    ``.gitignore``, a directory ignored wholesale by it, and a checksum-valid
    value inside an environment file in that directory. ``git ls-files
    --exclude-standard`` omits every one of those files, so a canary enumerating
    only that way sees nothing at all here. The file is also a bare dotfile,
    which has no suffix at all, so a suffix-keyed scope misses it a second time
    for a second reason.

    It is reported and does NOT block. A Cl@ve Movil credential file must carry
    the operator's own identity to authenticate, and gitignoring it is the
    correct handling; what the report is for is the next proof, which needs this
    sweep to exist in order to say the same identity is absent from tracked
    content.
    """
    (specimen_repository / ".gitignore").write_text("env/*\n", encoding="utf-8")
    ignored_directory = specimen_repository / "env"
    ignored_directory.mkdir()
    (ignored_directory / ".env").write_text(f"CADRUMO_CLAVE_MOVIL_DNI_NIE={_PLANTED_NIF}\n", encoding="utf-8")

    scan = scan_tree(specimen_repository)

    assert scan.findings == (), "an ignored credential file must not fail a build"
    assert [finding.path for finding in scan.operator_findings] == ["env/.env"], (
        "a checksum-valid identity in a gitignored environment file must be reported; "
        f"got {[finding.rendered() for finding in scan.operator_findings]}"
    )
    assert scan.operator_findings[0].kind is ResidualKind.NIF_NIE
    assert scan.operator_findings[0].tracking is FileTracking.IGNORED


def test_the_same_identity_blocks_when_tracked_and_only_reports_when_ignored(
    specimen_repository: Path,
) -> None:
    """The tier boundary, proven in both directions at once, on one value.

    One identity, two files, one sweep. If the tier were keyed on anything but
    tracking state -- a path, a filename, a directory -- these two occurrences
    would be classified alike, and the tier would either block a credential file
    or, far worse, let a tracked leak through beside it. This is also the
    cross-check the ignored sweep exists to make possible: the operator's own
    identity is visible in the credential file AND visibly absent from tracked
    content, and neither half of that sentence can be said without the other.
    """
    (specimen_repository / ".gitignore").write_text("env/*\n", encoding="utf-8")
    ignored_directory = specimen_repository / "env"
    ignored_directory.mkdir()
    (ignored_directory / ".env").write_text(f"CADRUMO_CLAVE_MOVIL_DNI_NIE={_PLANTED_NIF}\n", encoding="utf-8")
    (specimen_repository / "captured.json").write_text(f'{{"taxpayer": "{_PLANTED_NIF}"}}', encoding="utf-8")
    _git("add", "captured.json", cwd=specimen_repository)

    scan = scan_tree(specimen_repository)

    assert [finding.path for finding in scan.findings] == ["captured.json"], (
        f"the tracked copy of the identity must fail the gate; got {[finding.rendered() for finding in scan.findings]}"
    )
    assert [finding.path for finding in scan.operator_findings] == ["env/.env"]
    assert scan.render() != scan.render_operator()


def test_the_specimen_confirms_git_really_ignores_the_planted_directory(specimen_repository: Path) -> None:
    """The proof above means nothing unless the file really was ignored.

    A specimen whose ``.gitignore`` did not actually cover the payload would pass
    the ignore proof through the untracked path instead, which is the shape of
    the coverage this canary was faulted for: a docstring citing the ignore
    scenario over a specimen that never exercised it.
    """
    (specimen_repository / ".gitignore").write_text("env/*\n", encoding="utf-8")
    ignored_directory = specimen_repository / "env"
    ignored_directory.mkdir()
    (ignored_directory / ".env").write_text(f"CADRUMO_CLAVE_MOVIL_DNI_NIE={_PLANTED_NIF}\n", encoding="utf-8")

    listed = _git_output("ls-files", "--cached", "--others", "--exclude-standard", cwd=specimen_repository)
    ignored = _git_output("ls-files", "--others", "--ignored", "--exclude-standard", cwd=specimen_repository)

    assert "env/.env" not in listed, "the specimen's payload is not actually ignored, so it proves the wrong path"
    assert "env/.env" in ignored


@pytest.mark.parametrize(
    ("planted", "kind"),
    [
        (_PLANTED_NIF, ResidualKind.NIF_NIE),
        (_PLANTED_CIF, ResidualKind.CIF),
        (_PLANTED_NIF_IVA, ResidualKind.NIF_IVA),
    ],
)
def test_every_blocking_class_is_found_in_a_data_payload(
    specimen_repository: Path,
    planted: str,
    kind: ResidualKind,
) -> None:
    """Each gated class must fire on a payload, not merely be declared.

    A legal entity's tax identity is letter-led and an intra-community number
    carries a country prefix, so neither is expressible by the natural-person
    shape. A gate that lists a class it cannot match is a capability claim
    nothing checks.
    """
    payload = specimen_repository / "captured.json"
    payload.write_text(f'{{"identificador": "{planted}"}}', encoding="utf-8")
    _git("add", "captured.json", cwd=specimen_repository)

    scan = scan_tree(specimen_repository)

    assert [finding.kind for finding in scan.findings] == [kind], (
        f"a payload carrying a {kind.value} identity produced {[finding.rendered() for finding in scan.findings]}"
    )
    assert kind in BLOCKING_KINDS


def test_a_shape_valid_identity_with_a_wrong_control_letter_is_not_reported(
    specimen_repository: Path,
) -> None:
    """The checksum, not the pattern, is what makes this gate usable.

    Without it every eight-digit run followed by a letter would be a finding, and
    a gate that fires on ordinary data is a gate that gets switched off.
    """
    payload = specimen_repository / "reference.json"
    payload.write_text(f'{{"code": "{_PLANTED_SHAPE_ONLY}"}}', encoding="utf-8")

    scan = scan_tree(specimen_repository)

    assert scan.findings == ()
    assert scan.operator_findings == (), "the checksum must reject the shape in both tiers, not only the gated one"
    assert scan.files_scanned == 1, "the specimen file must have been read for the absence to mean anything"


def test_a_planted_identity_in_an_excluded_path_is_suppressed_and_counted(
    specimen_repository: Path,
) -> None:
    """An exclusion removes a finding from the gate WITHOUT removing it from view.

    Suppression that is invisible is indistinguishable from a scanner that never
    looked, so the scan reports what each exclusion took out.
    """
    fixture_directory = specimen_repository / "tests" / "fixtures"
    fixture_directory.mkdir(parents=True)
    (fixture_directory / "specimen.json").write_text(f'{{"nif": "{_PLANTED_NIF}"}}', encoding="utf-8")

    scan = scan_tree(specimen_repository)

    assert scan.findings == ()
    assert scan.suppressed_by_fragment["/tests/"] == 1
    assert scan.suppressed_by_fragment["/fixtures/"] == 1, (
        "an occurrence covered by two exclusions must be credited to both, or declaration order "
        "decides which exclusion looks like it is doing work"
    )


def test_no_finding_and_no_failure_message_carries_the_matched_value(
    specimen_repository: Path,
) -> None:
    """The handling rule, proven rather than asserted in a docstring.

    Everything a reader of this gate can see is built here -- the finding, its
    rendering, the whole-scan rendering -- and none of it may contain the value.
    """
    planted = (_PLANTED_NIF, _PLANTED_CIF, _PLANTED_NIF_IVA)
    body = json.dumps({"taxpayer": _PLANTED_NIF, "empresa": _PLANTED_CIF, "intracomunitario": _PLANTED_NIF_IVA})
    (specimen_repository / "captured.json").write_text(body, encoding="utf-8")
    _git("add", "captured.json", cwd=specimen_repository)
    (specimen_repository / "local.json").write_text(body, encoding="utf-8")

    scan = scan_tree(specimen_repository)
    assert len(scan.findings) == len(planted), "the value-free proof needs one finding per class to render"
    assert len(scan.operator_findings) == len(planted), "the operator tier must be rendered under the same rule"

    every_finding = (*scan.findings, *scan.operator_findings)
    surfaces = [scan.render(), scan.render_operator(), *(finding.rendered() for finding in every_finding)]
    surfaces.extend(repr(finding) for finding in every_finding)
    for surface in surfaces:
        for value in planted:
            assert value not in surface, "a canary surface disclosed the identity it found"
            assert value[:-1] not in surface, "a canary surface disclosed the identity body"


def test_every_exclusion_still_suppresses_a_live_occurrence(repository_scan: TreeScan) -> None:
    """A stale exclusion is a widening nobody re-reads, so it must fail.

    Measured independently per fragment, not by first match: a fixture directory
    normally sits under a test directory, and crediting only the first-declared
    fragment would make one exclusion look dead purely because another was
    declared above it.
    """
    dead = sorted(
        fragment for fragment in EXCLUDED_PATH_FRAGMENTS if repository_scan.suppressed_by_fragment.get(fragment, 0) == 0
    )

    assert not dead, (
        f"these path exclusions no longer suppress anything and must be deleted rather than left standing: {dead}"
    )


def test_every_exclusion_states_a_reason() -> None:
    """An exclusion without a stated reason is where the judgement disappears."""
    for fragment, reason in EXCLUDED_PATH_FRAGMENTS.items():
        assert reason.strip(), f"{fragment} is excluded with no stated reason"
        assert len(reason.split()) >= 5, f"{fragment} has a reason too terse to be auditable"
        assert exclusion_reason(f"some{fragment}file.json") == reason
        assert matching_fragments(f"some{fragment}file.json")[0] == fragment


def test_the_population_the_gate_excludes_stays_observable(repository_advisory: tuple[TreeFinding, ...]) -> None:
    """The narrowing is deliberate, and it must not become silent.

    The blocking scope is data payloads only. Source, prose and the excluded
    paths carry occurrences by the thousand, all of them documentation examples
    and synthetic fixtures as far as anyone has declared -- and the absence of a
    declared convention is exactly why they cannot be gated yet. Reporting them
    keeps the size of that gap visible; if this ever observes nothing, the gate
    should widen rather than this test being deleted.

    This module's own specimens are subtracted first. They are ``.py`` constants
    in the advisory population, so counting them let the tripwire measure the
    proof rather than the tree: the whole bucket for this package was one
    occurrence, and that occurrence was written here to make the scanner fire. A
    tripwire that can only ever observe its own bait cannot trip.
    """
    observed = [finding for finding in repository_advisory if finding.path != _CANARY_TEST_MODULE]

    assert observed, "the excluded population is empty, so the blocking scope should now widen to cover it"
    assert len({finding.path for finding in observed}) > 1, (
        "the excluded population has collapsed to a single file, which is not a population; "
        "the blocking scope should widen rather than this observation being deleted"
    )
    assert all(finding.kind in BLOCKING_KINDS for finding in observed)


def test_the_observability_tripwire_is_not_measuring_its_own_specimens(
    repository_advisory: tuple[TreeFinding, ...],
) -> None:
    """The subtraction above must actually remove something.

    If this module ever stopped contributing to the advisory population, the
    subtraction would be a no-op and the next reader would delete it as dead
    code -- taking the correction with it. It contributes because the planted
    specimens are checksum-valid by design and this file is scanned like any
    other source file.
    """
    own = [finding for finding in repository_advisory if finding.path == _CANARY_TEST_MODULE]

    assert own, (
        "this module no longer contributes to the advisory census, so subtracting it is a no-op "
        "and the tripwire is no longer protected from measuring its own specimens"
    )


def test_a_file_that_vanishes_between_enumeration_and_read_is_named_not_absorbed(
    specimen_repository: Path,
) -> None:
    """The unreadable counter, proven on the race it exists for.

    A working tree is live: a file enumerated a moment ago can be gone, locked or
    permission-denied by the time it is opened. Swallowing that returns the same
    clean verdict as reading it, while still crediting it to the count that is
    supposed to evidence the sweep. The file is deleted here after enumeration
    and before the scan, which is the real sequence rather than a simulated one.
    """
    payload = specimen_repository / "captured.json"
    payload.write_text(f'{{"taxpayer": "{_PLANTED_NIF}"}}', encoding="utf-8")
    enumerated = repository_files(specimen_repository, suffixes=DATA_SUFFIXES)
    assert [candidate.relative for candidate in enumerated] == ["captured.json"]
    payload.unlink()

    scan = scan_tree(specimen_repository, files=enumerated)

    assert scan.unreadable == ("captured.json",)
    assert scan.files_scanned == 0, "a file that could not be opened must not be counted as scanned"
    assert scan.findings == ()
    assert scan.operator_findings == ()


def test_an_ignored_machine_written_tree_is_never_opened(specimen_repository: Path) -> None:
    """The ignored sweep skips trees this repository does not author.

    Reading them means several hundred thousand files whose contents differ per
    machine and per hour, so the verdict would differ per developer. The cost is
    that a value inside one is invisible, which is why each skipped tree has to
    name what it is.
    """
    (specimen_repository / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    installed = specimen_repository / ".venv" / "Lib"
    installed.mkdir(parents=True)
    (installed / "package.json").write_text(f'{{"nif": "{_PLANTED_NIF}"}}', encoding="utf-8")

    scan = scan_tree(specimen_repository)

    assert scan.findings == ()
    assert scan.operator_findings == ()
    assert scan.files_scanned == 0
    assert unenumerated_reason(".venv/Lib/package.json") is not None


def test_a_tracked_file_is_scanned_even_under_an_unenumerated_name(specimen_repository: Path) -> None:
    """The enumeration skip applies to the ignored sweep alone.

    A directory name that marks scratch when git ignores it marks nothing when a
    file inside it is tracked: somebody committed that file deliberately. If the
    skip reached the tracked sweep it would narrow coverage that existed before
    the ignored sweep did, which is a regression wearing the shape of an
    optimisation.
    """
    scratch_like = specimen_repository / "var"
    scratch_like.mkdir()
    (scratch_like / "config.json").write_text(f'{{"nif": "{_PLANTED_NIF}"}}', encoding="utf-8")
    _git("add", "var/config.json", cwd=specimen_repository)

    scan = scan_tree(specimen_repository)

    assert [finding.path for finding in scan.findings] == ["var/config.json"], (
        "a tracked file was dropped by an exclusion that only governs the ignored sweep"
    )


def test_every_unenumerated_tree_states_what_it_is() -> None:
    """A tree that is never opened must say why, in words a reviewer can weigh.

    This is the widest judgement in the module -- a file here is not read,
    counted or reported -- so an unreasoned entry is where the narrowing would
    disappear entirely.
    """
    declared = {
        **UNENUMERATED_PATH_FRAGMENTS,
        **UNENUMERATED_ROOT_PREFIXES,
        **UNENUMERATED_ROOT_SUFFIXES,
    }
    assert len(declared) == (
        len(UNENUMERATED_PATH_FRAGMENTS) + len(UNENUMERATED_ROOT_PREFIXES) + len(UNENUMERATED_ROOT_SUFFIXES)
    ), "two enumeration exclusions share a key, so one of their reasons is unreachable"
    for entry, reason in declared.items():
        assert reason.strip(), f"{entry} is skipped with no stated reason"
        assert len(reason.split()) >= 5, f"{entry} has a reason too terse to be auditable"


def test_an_exclusion_reason_does_not_claim_a_class_the_detector_cannot_see(
    repository_advisory: tuple[TreeFinding, ...],
) -> None:
    """A stated reason is a claim about the tree, and it has to hold.

    The locale exclusion says the operator help strings illustrate the NIF, NIE
    and CIF formats. While the detector carried no legal-entity class that
    sentence asserted an awareness nothing behind it possessed, and a reason
    nobody can check is a reason nobody re-reads. The suppressed population is
    read back here and must really contain both a natural-person and a
    legal-entity occurrence.
    """
    locale_kinds = {finding.kind for finding in repository_advisory if finding.path.startswith("src/cadrumo/locales/")}

    assert {ResidualKind.NIF_NIE, ResidualKind.CIF} <= locale_kinds, (
        "the locale exclusion's stated reason names the NIF, NIE and CIF formats, but the "
        f"suppressed population carries only {sorted(kind.value for kind in locale_kinds)}"
    )


def test_an_authored_ignored_file_is_still_enumerated() -> None:
    """The enumeration skips must not have swallowed the ignored sweep whole.

    The proofs above show the skips work; this shows they left something behind.
    An exclusion set that grew until it covered every ignored file would pass
    every other assertion here while restoring exactly the blindness the ignored
    sweep was added to remove.
    """
    ignored = _git_output("ls-files", "--others", "--ignored", "--exclude-standard", cwd=_REPO_ROOT)
    enumerated = {path for path in ignored if unenumerated_reason(path) is None}

    assert enumerated, (
        "every ignored file in this tree is now skipped before it is opened, so the ignored sweep covers nothing at all"
    )
