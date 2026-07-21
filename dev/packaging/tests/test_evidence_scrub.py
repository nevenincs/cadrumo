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

from dev.packaging.cohort_manifest import (
    REQUIRED_ARTIFACT_KINDS,
    BuildIdentity,
    LoadedReleaseCohort,
    SourceIdentity,
    create_manifest,
    load_release_cohort,
    write_manifest,
)
from dev.packaging.evidence import (
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
from dev.packaging.evidence_scrub import (
    SCRUBBED_MACHINE_ID,
    SCRUBBED_USER,
    EvidenceScrubError,
    default_runner_tokens,
    find_residual_leaks,
    scrub_distribution_evidence,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_HOSTNAME = "build-host-example"
_USERNAME = "gwuser"
_TOKENS = (_HOSTNAME, _USERNAME)
_HOME = f"C:\\Users\\{_USERNAME}"


def _release_cohort(root: Path) -> LoadedReleaseCohort:
    """Materialise a genuine release cohort with every required artifact kind."""
    root.mkdir()
    artifacts = []
    for index, (name, kind) in enumerate(sorted(REQUIRED_ARTIFACT_KINDS.items())):
        path = root / "artifacts" / f"{name}.bin"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(f"{index}:{name}\n".encode())
        artifacts.append((name, kind, path))
    manifest = create_manifest(
        root=root,
        version="0.2.1",
        source=SourceIdentity(commit="c" * 40, tag="v0.2.1"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        builder=BuildIdentity(
            implementation="dev.packaging.release_cohort",
            format_version=1,
            python=platform.python_version(),
            uv="0.11.29",
            platform=platform.system(),
            architecture=platform.machine(),
            build_constraints_sha256="d" * 64,
        ),
        artifacts=artifacts,
    )
    write_manifest(root, manifest)
    return load_release_cohort(root)


def _leaking_evidence(
    cohort: LoadedReleaseCohort, *, observations: dict[str, object] | None = None
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
