"""Cross-workflow structural gates for the packaging evidence transport.

Inter-workflow payloads — the sealed release cohort, the per-OS smoke cohorts,
and the per-row ``DistributionEvidence`` records — ride Actions artifacts. They
briefly rode per-run draft releases instead, because artifact storage was
quota-capped while the repository was private on a Free plan; the repository is
public now, that storage is free, and the draft namespace only put machine
scaffolding on the owner's releases page.

These gates pin the invariants that span workflows. The load-bearing one is the
first: no packaging workflow may reach the releases API or hold the permission
that would let it. Exactly one job in the repository creates a release — the
human-armed publication gate — and it creates the one real ``v<version>``.
"""

from __future__ import annotations

from typing import Any, Final

import pytest
import yaml

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_PACKAGING_WORKFLOWS: Final = (
    "packaging-smoke.yml",
    "packaging-scoop.yml",
    "packaging-homebrew.yml",
)
_TRANSPORT_WORKFLOWS: Final = (*_PACKAGING_WORKFLOWS, "publish-release.yml")


def _document(name: str) -> dict[str, Any]:
    return yaml.safe_load((_WORKFLOWS_DIR / name).read_text(encoding="utf-8"))


def _steps(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for job in document["jobs"].values() for step in (job.get("steps") or []) if isinstance(step, dict)]


def _run_surface(document: dict[str, Any]) -> str:
    return "\n".join(str(step.get("run", "")) for step in _steps(document))


def _invocations(surface: str, verb: str) -> list[str]:
    """Command lines only — workflow prose legitimately DESCRIBES a verb."""
    return [line.strip() for line in surface.splitlines() if line.strip().startswith(verb)]


@pytest.mark.parametrize("workflow", _PACKAGING_WORKFLOWS)
def test_no_packaging_workflow_touches_the_releases_api(workflow: str) -> None:
    """No packaging workflow creates, uploads to, or reads a GitHub release.

    This is the invariant the whole conversion exists to hold: CI must not put
    machine scaffolding on the repository's releases page. Asserted on
    invocation lines so a comment may still name the verb it warns against.
    """
    surface = _run_surface(_document(workflow))
    for verb in ("gh release create", "gh release upload", "gh release view", "gh release download"):
        assert _invocations(surface, verb) == [], f"{workflow} still calls {verb!r}"


@pytest.mark.parametrize("workflow", _PACKAGING_WORKFLOWS)
def test_no_packaging_job_can_write_repository_contents(workflow: str) -> None:
    """Least privilege carries the invariant above even if a verb slips back.

    ``contents: write`` is the permission that makes the releases API reachable
    at all, so no packaging job may hold it — at workflow or job level.
    """
    document = _document(workflow)
    assert (document.get("permissions") or {}).get("contents") != "write", workflow
    for job_name, job in document["jobs"].items():
        granted = (job.get("permissions") or {}).get("contents")
        assert granted != "write", f"{workflow}:{job_name} still grants contents:write"


@pytest.mark.parametrize("workflow", _PACKAGING_WORKFLOWS)
def test_packaging_payloads_ride_artifacts(workflow: str) -> None:
    """Every packaging workflow moves its payloads through Actions artifacts."""
    document = _document(workflow)
    uses = [str(step.get("uses", "")) for step in _steps(document)]
    artifact_steps = [entry for entry in uses if "upload-artifact" in entry or "download-artifact" in entry]
    cross_workflow = "gh run download" in _run_surface(document)
    assert artifact_steps or cross_workflow, f"{workflow} moves no payload through artifacts"
    for entry in artifact_steps:
        assert "@" in entry and len(entry.split("@")[1]) == 40, f"{workflow} pins {entry} to a tag, not a SHA"


def test_only_the_publication_gate_creates_a_release() -> None:
    """Exactly one job in the repository creates a release: the armed publish gate."""
    creators: list[tuple[str, str]] = []
    for path in scan_directory(_WORKFLOWS_DIR, pattern="*.yml"):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in (document.get("jobs") or {}).items():
            surface = "\n".join(str(step.get("run", "")) for step in (job.get("steps") or []))
            if _invocations(surface, "gh release create"):
                creators.append((path.name, job_name))
    assert creators == [("publish-release.yml", "publish")], creators
    publish_surface = "\n".join(
        str(step.get("run", "")) for step in (_document("publish-release.yml")["jobs"]["publish"].get("steps") or [])
    )
    assert 'gh release create "v$VERSION"' in publish_surface


def test_no_workflow_creates_a_draft_release() -> None:
    """The reserved evidence-* draft namespace is retired, not merely emptied."""
    for path in scan_directory(_WORKFLOWS_DIR, pattern="*.yml"):
        surface = path.read_text(encoding="utf-8")
        assert "--draft" not in surface, f"{path.name} still creates a draft release"
        assert "evidence-smoke-" not in surface, f"{path.name} still names an evidence draft tag"


def test_debug_diagnostics_never_enter_the_row_aggregation() -> None:
    """debug-* artifacts are diagnostics, never promotable evidence rows.

    A promoted run is green, but a re-run attempt can retain attempt-1 debug
    debris; every row aggregation therefore excludes debug-* by name.
    """
    document = _document("publish-release.yml")
    for job_name in ("validate", "publish"):
        surface = "\n".join(str(step.get("run", "")) for step in (document["jobs"][job_name].get("steps") or []))
        aggregations = surface.count("-name '*.json'")
        debug_excludes = surface.count("! -name 'debug-*'")
        assert aggregations > 0, job_name
        assert debug_excludes == aggregations, (job_name, aggregations, debug_excludes)


def test_gate3_attaches_only_sweep_passed_evidence() -> None:
    """Gate 3 leak-sweeps every evidence asset BEFORE anything can be attached.

    Rows are scrubbed at mint time; the sweep is the fail-closed publication
    tripwire (verify-then-refuse, no rewriting) over the attach directory, and
    the v-release create comes only after it.
    """
    document = _document("publish-release.yml")
    surface = "\n".join(str(step.get("run", "")) for step in (document["jobs"]["publish"].get("steps") or []))
    assert "dev.packaging.evidence_leak_sweep leak-sweep" in surface
    # The sweep covers the UNION of everything Gate 3 attaches: the evidence
    # attach dir AND the cohort files themselves.
    assert '--directory "$EVIDENCE_FINAL_DIR/attach"' in surface
    assert '--directory "$RELEASE_COHORT_DIR"' in surface
    assert surface.index("leak-sweep") < surface.index('gh release create "v$VERSION"')
    # The final release's assets come exclusively from the two swept roots.
    assert '"$RELEASE_COHORT_DIR" "$EVIDENCE_FINAL_DIR/attach" -type f' in surface


def test_promotion_verifies_run_identity_before_downloading_anything() -> None:
    """The run id stays the operator's only handle, and it is checked first.

    An artifact belongs to its producing run by construction, so run identity
    IS the provenance binding — which makes the order load-bearing: every
    ``gh run download`` must sit behind an Actions-API identity assertion that
    pins the workflow path and a successful conclusion.
    """
    document = _document("publish-release.yml")
    for job_name in ("validate", "publish"):
        surface = "\n".join(str(step.get("run", "")) for step in (document["jobs"][job_name].get("steps") or []))
        if "gh run download" not in surface:
            continue
        assert "actions/runs/" in surface, job_name
        # The path may be a literal or a shell parameter of the local verify
        # helper; either way the smoke path and a conclusion check must appear,
        # and the API call must precede the first download.
        assert ".github/workflows/packaging-smoke.yml" in surface, job_name
        assert "conclusion" in surface, job_name
        assert surface.index("actions/runs/") < surface.index("gh run download"), job_name
    # Both jobs need actions:read to reach another run's artifacts, and neither
    # may reach them with a broader grant than that.
    for job_name in ("validate", "publish"):
        assert (document["jobs"][job_name].get("permissions") or {}).get("actions") == "read", job_name


@pytest.mark.parametrize("workflow", _TRANSPORT_WORKFLOWS)
def test_checkouts_never_persist_credentials(workflow: str) -> None:
    """A persisted token would let any later step push commits, tags or releases."""
    document = _document(workflow)
    for job_name, job in document["jobs"].items():
        for step in job.get("steps") or []:
            if str(step.get("uses", "")).startswith("actions/checkout@"):
                with_block = step.get("with") or {}
                assert with_block.get("persist-credentials") is False, (workflow, job_name)


def test_windows_transport_steps_pin_shell_pwsh() -> None:
    """Every Windows transport step declares ``shell: pwsh``, never 5.1.

    The setup actions rewrite PSModulePath for pwsh, which breaks Windows
    PowerShell 5.1 module auto-loading on the self-hosted runner (observed
    live: ``Get-FileHash is not recognized``).
    """
    for workflow in _PACKAGING_WORKFLOWS:
        for step in _steps(_document(workflow)):
            run = str(step.get("run", ""))
            if "gh run download" not in run and "tar -" not in run:
                continue
            shell = step.get("shell")
            assert shell in (None, "pwsh"), (workflow, step.get("name"), shell)


def test_acquisition_lanes_pin_the_linux_python_cohort() -> None:
    """Decision pinned: every acquisition lane consumes the LINUX-built cohort.

    Wheels are py3-none-any, and every lane has always consumed the Linux
    cohort; the artifact spelling keeps that parity.
    """
    for workflow in ("packaging-scoop.yml", "packaging-homebrew.yml"):
        surface = _run_surface(_document(workflow))
        assert "cadrumo-python-cohort-linux" in surface, workflow
        assert "cadrumo-python-cohort-windows" not in surface, workflow
        assert "cadrumo-python-cohort-macos" not in surface, workflow


def test_oracle_emit_row_ids_stay_pairwise_disjoint() -> None:
    """The three oracle legs emit rows whose basenames cannot collide.

    Row files are ``{row_id}-{evidence_id}.json``; the publish gates flatten
    every lane's rows into one directory, so distinct row ids per leg keep
    that aggregation collision-free.
    """
    document = _document("packaging-smoke.yml")
    row_ids = []
    for job_name in ("oracle-emit-linux", "oracle-emit-windows", "oracle-emit-macos"):
        surface = "\n".join(str(step.get("run", "")) for step in document["jobs"][job_name]["steps"])
        row_ids.extend(
            token.split()[1] for token in surface.replace("`", "").splitlines() if token.strip().startswith("--row-id ")
        )
    assert len(row_ids) == 3
    assert len(set(row_ids)) == 3, row_ids


def test_artifact_names_stay_pairwise_disjoint_within_a_workflow() -> None:
    """Two jobs uploading the same artifact name would clobber each other.

    Draft releases forced a single-creator topology to dodge a duplicate-tag
    race; artifacts have no such race, but they DO collide on name, so the
    per-leg suffixes are what keep concurrent matrix legs independent.
    """
    for workflow in _PACKAGING_WORKFLOWS:
        document = _document(workflow)
        names = [
            str((step.get("with") or {}).get("name"))
            for step in _steps(document)
            if "upload-artifact" in str(step.get("uses", ""))
        ]
        assert len(names) == len(set(names)), (workflow, names)
