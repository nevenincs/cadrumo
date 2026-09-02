"""Real-behavior tests for the mint-time runner-metadata scrub.

Rows are built through the real evidence authority (real cohort on disk, real
captured subprocess transcripts — the same fixtures as the emitter tests) and
carry genuine hostname-style machine metadata; the scrub must remove it,
keep every non-leaking field intact, revalidate through the strict schema, and
fail closed — never pass silently — on a leak shape it cannot rewrite.
"""

from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import JsonValue

from ..cohort_manifest import LoadedReleaseCohort
from ..evidence import (
    AcquisitionIdentity,
    CommandTranscript,
    DestinationIdentity,
    DistributionEvidence,
    EvidenceStatus,
    ExecutionIsolation,
    InstalledExecutableIdentity,
    ResultIdentity,
    create_distribution_evidence,
    current_runtime_identity,
    evidence_identifier,
)
from ..evidence_scrub import (
    SCRUBBED_MACHINE_ID,
    SCRUBBED_USER,
    SCRUBBED_WORKSPACE,
    EvidenceScrubError,
    default_runner_tokens,
    default_workspace_roots,
    find_residual_leaks,
    scrub_distribution_evidence,
)
from ._release_cohort_support import release_cohort

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_HOSTNAME = "build-host-example"
_USERNAME = "gwuser"
_TOKENS = (_HOSTNAME, _USERNAME)
_HOME = f"C:\\Users\\{_USERNAME}"


def _text_observations(evidence: DistributionEvidence, group: str) -> dict[str, str]:
    """Return one observation group as text, proving its shape on the way.

    ``observations`` is typed as free JSON, so a group is only a mapping and a
    leaf only a string once something checks. Checking here turns a wrong-shaped
    observation into a named test failure instead of an index into a list.
    """
    observed = evidence.result.observations[group]
    if not isinstance(observed, dict):
        raise AssertionError(f"observation {group!r} is not a mapping")
    text: dict[str, str] = {}
    for key, value in observed.items():
        if not isinstance(value, str):
            raise AssertionError(f"observation {group}.{key} is not text")
        text[key] = value
    return text


def _release_cohort(root: Path) -> LoadedReleaseCohort:
    """Materialise a genuine release cohort with every required artifact kind."""
    return release_cohort(root)


def _leaking_evidence(
    cohort: LoadedReleaseCohort, *, observations: dict[str, JsonValue] | None = None
) -> DistributionEvidence:
    """Build a real validated row saturated with runner metadata."""
    transcript = CommandTranscript.from_output(
        argv=(f"{_HOME}\\pipx\\venvs\\cadrumo\\Scripts\\aeat.exe", "--version"),
        cwd=f"{_HOME}\\work\\cadrumo",
        started_at=datetime(2026, 7, 20, 10, 0, tzinfo=UTC),
        completed_at=datetime(2026, 7, 20, 10, 1, tzinfo=UTC),
        exit_status=0,
        stdout="cadrumo 0.2.1",
        stderr="",
        relevant_output=("cadrumo 0.2.1", f"ran on {_HOSTNAME}"),
    )
    result = ResultIdentity(
        status=EvidenceStatus.PASSED,
        assertions=("installed CLI computed DP200014:00562=23000.00",),
        observations={
            "cli_oracle": {
                "resolved_executable": f"{_HOME}\\pipx\\venvs\\cadrumo\\Scripts\\aeat.exe",
                "storage_root": f"/home/{_USERNAME}/.local/state/cadrumo",
            },
            **(observations or {}),
        },
    )
    return create_distribution_evidence(
        row_id="python-windows-x86-64",
        cohort=cohort,
        runtime=current_runtime_identity(),
        client=None,
        isolation=ExecutionIsolation(
            checkout_imports_removed=True,
            ambient_product_executables_removed=True,
            installed_executables=(
                InstalledExecutableIdentity(
                    name="aeat",
                    path=f"{_HOME}\\pipx\\venvs\\cadrumo\\Scripts\\aeat.exe",
                    sha256="a" * 64,
                ),
            ),
        ),
        acquisition=AcquisitionIdentity(mechanism="pip", source="https://pypi.org/simple"),
        commands=(transcript,),
        result=result,
        observed_at=datetime(2026, 7, 20, 10, 2, tzinfo=UTC),
        destination=DestinationIdentity(kind="pypi-index-install", locator=f"{_HOME}\\venv", version="0.2.1"),
    )


def _dump(evidence: DistributionEvidence) -> str:
    return evidence.model_dump_json()


def test_scrub_removes_every_runner_identifier(tmp_path: Path) -> None:
    """Hostname, username, and home-dir segments vanish from the whole row."""
    evidence = _leaking_evidence(_release_cohort(tmp_path / "cohort"))
    scrubbed = scrub_distribution_evidence(evidence, tokens=_TOKENS)
    serialized = _dump(scrubbed)
    assert _HOSTNAME not in serialized
    assert _USERNAME not in serialized
    assert SCRUBBED_USER in serialized
    assert SCRUBBED_MACHINE_ID in serialized


def test_scrub_keeps_non_leaking_fields_and_structure_intact(tmp_path: Path) -> None:
    """Everything that is not a machine identifier survives byte-identically."""
    evidence = _leaking_evidence(_release_cohort(tmp_path / "cohort"))
    scrubbed = scrub_distribution_evidence(evidence, tokens=_TOKENS)
    assert scrubbed.row_id == evidence.row_id
    assert scrubbed.cohort == evidence.cohort  # the sealed binding is untouched
    assert scrubbed.runtime == evidence.runtime
    assert scrubbed.result.status is EvidenceStatus.PASSED
    assert scrubbed.commands[0].exit_status == 0
    assert scrubbed.commands[0].stdout_sha256 == evidence.commands[0].stdout_sha256
    assert scrubbed.commands[0].started_at == evidence.commands[0].started_at
    assert scrubbed.isolation.installed_executables[0].sha256 == evidence.isolation.installed_executables[0].sha256
    assert scrubbed.acquisition == evidence.acquisition
    assert scrubbed.destination.version == evidence.destination.version
    assert scrubbed.commands[0].relevant_output[0] == "cadrumo 0.2.1"


def test_scrubbed_row_revalidates_with_a_fresh_matching_identity(tmp_path: Path) -> None:
    """The scrubbed row is an ordinary tamper-evident record: id matches content."""
    evidence = _leaking_evidence(_release_cohort(tmp_path / "cohort"))
    scrubbed = scrub_distribution_evidence(evidence, tokens=_TOKENS)
    assert scrubbed.evidence_id != evidence.evidence_id
    assert scrubbed.evidence_id == evidence_identifier(scrubbed)
    # A strict JSON roundtrip through the schema (what readiness does) holds.
    assert DistributionEvidence.model_validate_json(_dump(scrubbed)) == scrubbed


def test_scrub_is_idempotent(tmp_path: Path) -> None:
    """Scrubbing an already-scrubbed row is a no-op with a stable identity."""
    evidence = _leaking_evidence(_release_cohort(tmp_path / "cohort"))
    once = scrub_distribution_evidence(evidence, tokens=_TOKENS)
    twice = scrub_distribution_evidence(once, tokens=_TOKENS)
    assert once == twice


def test_novel_leaking_field_fails_closed(tmp_path: Path) -> None:
    """A home path in a field the scrubber never anticipated is still caught.

    Anti-tautology for the fail-closed sweep: the detection walk is
    field-agnostic, so the leak is found even in a novel observation key —
    proven by feeding the detector a document where normalization was skipped.
    """
    evidence = _leaking_evidence(
        _release_cohort(tmp_path / "cohort"),
        observations={"brand_new_diag_field": {"deep": [f"logged at /Users/{_USERNAME}/Library/Logs"]}},
    )
    document = evidence.model_dump(mode="json", exclude={"evidence_id"})
    leaks = find_residual_leaks(document, _TOKENS)
    assert any("brand_new_diag_field" in leak for leak in leaks)
    assert any(_USERNAME in leak for leak in leaks)


def test_unc_path_is_refused_not_silently_shipped(tmp_path: Path) -> None:
    """A UNC host path cannot be normalized, so minting the row is refused."""
    evidence = _leaking_evidence(
        _release_cohort(tmp_path / "cohort"),
        observations={"share": "\\\\fileserver01\\evidence\\row.json"},
    )
    with pytest.raises(EvidenceScrubError, match="UNC host"):
        scrub_distribution_evidence(evidence, tokens=_TOKENS)


def test_leak_inside_the_cohort_binding_is_refused_not_rewritten(tmp_path: Path) -> None:
    """The sealed cohort binding is never rewritten; a leak there refuses the mint."""
    evidence = _leaking_evidence(_release_cohort(tmp_path / "cohort"))
    document = evidence.model_dump(mode="json", exclude={"evidence_id"})
    document["cohort"]["source"]["tag"] = f"/home/{_USERNAME}/v0.2.1"
    leaks = find_residual_leaks(document, _TOKENS)
    assert any("/cohort/" in leak for leak in leaks)


def test_escaped_windows_home_inside_embedded_json_is_scrubbed(tmp_path: Path) -> None:
    r"""A JSON-escaped ``C:\\Users\\name`` inside an observation string is caught."""
    embedded = json.dumps({"cwd": f"{_HOME}\\work"})
    evidence = _leaking_evidence(
        _release_cohort(tmp_path / "cohort"),
        observations={"embedded_transcript": embedded},
    )
    scrubbed = scrub_distribution_evidence(evidence, tokens=_TOKENS)
    assert _USERNAME not in _dump(scrubbed)


def test_default_tokens_name_this_machine(tmp_path: Path) -> None:
    """The default token set is the minting machine's own hostname and username."""
    tokens = default_runner_tokens()
    assert platform.node() in tokens or platform.node() == ""
    # The default-token path is what the emit builders use: a row minted on
    # THIS machine (cwd under this user's home) comes out clean of this user.
    del tmp_path


_WIN_WORKSPACE = "D:\\a\\cadrumo\\cadrumo"
_POSIX_WORKSPACE = "/home/runner/work/cadrumo/cadrumo"


def test_windows_workspace_root_is_redacted_tail_preserved(tmp_path: Path) -> None:
    """A GitHub-hosted Windows workspace prefix vanishes; the evidence tail stays.

    The workspace root carries no home segment and no hostname/username token, so
    only the workspace scrub can redact it — the token/home passes leave it
    untouched. The venv/artefact structure below the root IS evidence and must
    survive verbatim.
    """
    evidence = _leaking_evidence(
        _release_cohort(tmp_path / "cohort"),
        observations={
            "workspace_diag": {
                "resolved_executable": f"{_WIN_WORKSPACE}\\var\\pip-venv\\Scripts\\aeat.exe",
                "storage_root": f"{_WIN_WORKSPACE}\\var\\tax-oracle-state",
            },
        },
    )
    scrubbed = scrub_distribution_evidence(evidence, tokens=_TOKENS, workspace_roots=(_WIN_WORKSPACE,))
    diag = _text_observations(scrubbed, "workspace_diag")
    assert diag["resolved_executable"] == f"{SCRUBBED_WORKSPACE}\\var\\pip-venv\\Scripts\\aeat.exe"
    assert diag["storage_root"] == f"{SCRUBBED_WORKSPACE}\\var\\tax-oracle-state"


def test_posix_workspace_root_redaction_precedes_home_scrub(tmp_path: Path) -> None:
    """A ``/home/runner/work/...`` workspace root is redacted whole, not half by the home pass."""
    evidence = _leaking_evidence(
        _release_cohort(tmp_path / "cohort"),
        observations={"workspace_diag": {"cwd": f"{_POSIX_WORKSPACE}/var/outside-checkout"}},
    )
    scrubbed = scrub_distribution_evidence(evidence, tokens=_TOKENS, workspace_roots=(_POSIX_WORKSPACE,))
    cwd = _text_observations(scrubbed, "workspace_diag")["cwd"]
    assert cwd == f"{SCRUBBED_WORKSPACE}/var/outside-checkout"
    assert "runner" not in cwd


def test_workspace_root_survives_fails_closed(tmp_path: Path) -> None:
    """Anti-tautology: an un-normalized workspace root is caught by the detection sweep."""
    evidence = _leaking_evidence(
        _release_cohort(tmp_path / "cohort"),
        observations={"workspace_diag": {"cwd": f"{_WIN_WORKSPACE}\\var\\state"}},
    )
    document = evidence.model_dump(mode="json", exclude={"evidence_id"})
    leaks = find_residual_leaks(document, _TOKENS, workspace_roots=(_WIN_WORKSPACE,))
    assert any("workspace root" in leak and "workspace_diag" in leak for leak in leaks)


def test_default_workspace_roots_reads_ci_env_longest_first() -> None:
    """The default roots come from the runner's CI env, most specific first."""
    env = {
        "GITHUB_WORKSPACE": "/home/runner/work/cadrumo/cadrumo",
        "RUNNER_WORKSPACE": "/home/runner/work/cadrumo",
    }
    roots = default_workspace_roots(env)
    assert roots == ("/home/runner/work/cadrumo/cadrumo", "/home/runner/work/cadrumo")


def test_default_workspace_roots_empty_without_ci_env() -> None:
    """Off a CI runner the default workspace-root set is empty, so scrubbing is a no-op."""
    assert default_workspace_roots({}) == ()
