"""The working-tree identity canary, and the proofs that it can actually fire.

The gate itself is one assertion: no data payload in this repository carries a
checksum-valid Spanish taxpayer identity. Everything else here exists because
that assertion is worthless on its own -- a scanner that enumerates nothing, or
whose checksum never rejects anything, or whose exclusions have quietly grown to
cover the tree, reports the same clean result as a clean repository.

The positive controls run against a REAL temporary git repository rather than a
patched enumerator, so what they prove is that the real code path finds a real
planted value in a real file. Nothing under ``src/`` or ``dev/`` is mutated to
make them work.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from .._tree_scan import (
    BLOCKING_KINDS,
    EXCLUDED_PATH_FRAGMENTS,
    advisory_findings,
    exclusion_reason,
    matching_fragments,
    scan_tree,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]

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


def _git(*arguments: str, cwd: Path) -> None:
    """Run one git command in ``cwd``, failing loudly."""
    executable = shutil.which("git")
    assert executable is not None, "git is required to build the specimen repository"
    subprocess.run([executable, *arguments], cwd=cwd, check=True, capture_output=True)  # noqa: S603


@pytest.fixture
def specimen_repository(tmp_path: Path) -> Iterator[Path]:
    """A real git repository outside this tree, for planting values into.

    Built rather than patched: the canary enumerates through ``git ls-files``, so
    a specimen that is not a git repository would exercise a different code path
    than the one guarding this project.
    """
    _git("init", "--quiet", cwd=tmp_path)
    yield tmp_path


def test_the_working_tree_carries_no_identity_in_a_data_payload() -> None:
    """The gate. A taxpayer identity in a shipped payload is a leak.

    The failure message lists locations only. It cannot disclose a value, which
    is what makes it safe to print in CI output that anyone can read.
    """
    scan = scan_tree(_REPO_ROOT)

    assert scan.files_scanned > 0, "the canary enumerated no files, so a clean verdict proves nothing"
    assert not scan.findings, (
        f"{len(scan.findings)} checksum-valid taxpayer identities in data payloads (values withheld):\n{scan.render()}"
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


def test_an_untracked_payload_is_scanned_too(specimen_repository: Path) -> None:
    """An untracked file is in scope, because that is how the exposure arrived.

    The leak this canary answers to reached the tree through a file that was
    gitignored and committed anyway. A scanner reading only the index would have
    been blind to it at the moment it mattered.
    """
    payload = specimen_repository / "never-added.csv"
    payload.write_text(f"nif,importe\n{_PLANTED_NIF},100\n", encoding="utf-8")

    scan = scan_tree(specimen_repository)

    assert [finding.path for finding in scan.findings] == ["never-added.csv"]


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
    payload = specimen_repository / "captured.json"
    payload.write_text(f'{{"taxpayer": "{_PLANTED_NIF}"}}', encoding="utf-8")

    scan = scan_tree(specimen_repository)
    assert scan.findings, "the value-free proof needs a real finding to render"

    surfaces = [scan.render(), *(finding.rendered() for finding in scan.findings)]
    surfaces.extend(repr(finding) for finding in scan.findings)
    for surface in surfaces:
        assert _PLANTED_NIF not in surface, "a canary surface disclosed the identity it found"
        assert _PLANTED_NIF[:-1] not in surface, "a canary surface disclosed the identity body"


def test_every_exclusion_still_suppresses_a_live_occurrence() -> None:
    """A stale exclusion is a widening nobody re-reads, so it must fail.

    Measured independently per fragment, not by first match: a fixture directory
    normally sits under a test directory, and crediting only the first-declared
    fragment would make one exclusion look dead purely because another was
    declared above it.
    """
    scan = scan_tree(_REPO_ROOT)

    dead = sorted(fragment for fragment in EXCLUDED_PATH_FRAGMENTS if scan.suppressed_by_fragment.get(fragment, 0) == 0)

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


def test_the_population_the_gate_excludes_stays_observable() -> None:
    """The narrowing is deliberate, and it must not become silent.

    The blocking scope is data payloads only. Source, prose and the excluded
    paths carry occurrences by the thousand, all of them documentation examples
    and synthetic fixtures as far as anyone has declared -- and the absence of a
    declared convention is exactly why they cannot be gated yet. Reporting them
    keeps the size of that gap visible; if this ever observes nothing, the gate
    should widen rather than this test being deleted.
    """
    advisory = advisory_findings(_REPO_ROOT)

    assert advisory, "the excluded population is empty, so the blocking scope should now widen to cover it"
    assert all(finding.kind in BLOCKING_KINDS for finding in advisory)
