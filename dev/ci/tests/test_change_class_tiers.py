"""Structural gates for the change-class tier topology.

The push and pull-request discipline is tiered by change class — T0 vault/docs churn runs
nothing, T1 code changes run the quick profile, T2 release-artifact-shaping
changes auto-dispatch the full campaign, T3 releases bind to the
publish-release gate topology. Classification is structural (path filters and
workflow topology), so these gates pin the boundaries: the T0 carve-out set,
the T2 detector's paths, the fork pull-request guard on every fleet-facing job, the
repo-wide zero-Actions-artifact posture, and the workflow naming convention.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from cadrumo.core import scan_directory

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_TRIGGER: Final = _WORKFLOWS_DIR / "packaging-campaign-trigger.yml"
_CI: Final = _WORKFLOWS_DIR / "ci.yml"
_QUICK: Final = _WORKFLOWS_DIR / "packaging-quick.yml"
_FULL: Final = _WORKFLOWS_DIR / "ci-full.yml"
_DOCS: Final = _WORKFLOWS_DIR / "docs.yml"

# The carve-out on the PYTHON code lanes: everything that never reaches the
# Python code or artifact surface those lanes gate. Shared verbatim by every
# per-push T1 Python workflow so a path cannot be carved out for one lane and
# not the other.
#
# `docs/**` joined the set when it gained its own lane. It is not a "runs
# nothing" path — that is the point. Before the split the carve-out was keyed on
# file SUFFIX rather than on role, so `**.md` held `docs/index.md` out while
# `docs/**.rst` (1384 files) started the full Python unit suite and still
# produced no documentation verdict. A path belongs here when the PYTHON lanes
# cannot observe its regressions, and a path that belongs here needs a lane of
# its own — which is what docs.yml is, and what
# `test_every_code_lane_carve_out_path_has_a_lane_of_its_own` enforces so the
# set cannot become a silent dumping ground.
_CODE_LANE_CARVE_OUT: Final = frozenset(
    {
        ".vault/**",
        ".vaultspec/**",
        ".claude/**",
        ".codex/**",
        ".gemini/**",
        ".agents/**",
        "docs/**",
        "**.md",
    }
)

# The T2 boundary: the files that define the shipped artifact set. A push
# touching any of these auto-dispatches the full campaign.
_T2_RELEASE_ARTIFACT_SURFACE: Final = frozenset(
    {
        "pyproject.toml",
        "uv.lock",
        "packaging/**",
        "dev/packaging/**",
        ".github/workflows/packaging-smoke.yml",
    }
)

_SAME_REPO_GUARD: Final = (
    "github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository"
)


def _document(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(document: dict[str, Any]) -> Any:
    return document[True] if True in document else document["on"]


def test_t2_trigger_paths_pin_the_release_artifact_surface() -> None:
    """The campaign auto-dispatch fires exactly on the release-artifact paths."""
    document = _document(_TRIGGER)
    triggers = _triggers(document)
    assert set(triggers) == {"push"}
    push = triggers["push"]
    assert push["branches"] == ["main"]
    assert set(push["paths"]) == set(_T2_RELEASE_ARTIFACT_SURFACE)


def test_t2_trigger_dispatches_the_full_campaign_and_nothing_else() -> None:
    """One tiny job that presses the packaging-smoke dispatch button on main."""
    document = _document(_TRIGGER)
    assert "Cadrumo" in document["name"]
    assert document["permissions"] == {"actions": "write", "contents": "read"}
    assert set(document["jobs"]) == {"dispatch-full-campaign"}
    job = document["jobs"]["dispatch-full-campaign"]
    assert job["timeout-minutes"] <= 10
    commands = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "gh workflow run packaging-smoke.yml" in commands
    assert "--ref main" in commands
    # The trigger never runs the campaign inline or mints evidence itself.
    for forbidden in ("just packaging", "campaign.py", "evidence", "gh release"):
        assert forbidden not in commands, forbidden


def test_code_lane_carve_out_is_identical_across_every_python_lane_and_trigger() -> None:
    """The Python lanes agree EXACTLY on what never reaches the code surface.

    Equality, not superset. The previous form asserted ``>= _T0_CARVE_OUT`` per
    lane independently, which is satisfiable by two lanes that disagree: it can
    only catch a lane dropping a shared path, never one lane carving out
    something the other does not. That is not a hypothetical — it is how the
    tree actually drifted. `packaging-quick.yml` carved out `docs/**` and
    `ci.yml` did not, for long enough that the whole documentation tree was
    carved out for one Python lane and not the other, while the governing
    decision described the carve-out as shared and this gate reported green.

    Both triggers, not just push. The old form read only ``push``, so the
    pull-request carve-out could diverge from the push one with nothing
    watching — the same class of hole one level down.
    """
    for path in (_CI, _QUICK):
        triggers = _triggers(_document(path))
        for event in ("push", "pull_request"):
            assert event in triggers, f"{path.name} lost its {event} trigger"
            carve_out = set(triggers[event]["paths-ignore"])
            assert carve_out == set(_CODE_LANE_CARVE_OUT), f"{path.name}:{event}"


def test_every_code_lane_carve_out_path_has_a_lane_of_its_own() -> None:
    """A path carved out of the Python lanes is verified elsewhere or is inert.

    The carve-out set is where verification goes to die if nobody watches it:
    adding a path is a one-line way to make a lane green. So every carved-out
    path must be either genuinely inert (agent config, vault records, loose
    markdown — development scaffolding that ships nothing) or covered by a lane
    that names it. `docs/**` is a product surface, so it is held to the second
    standard.
    """
    inert = {".vault/**", ".vaultspec/**", ".claude/**", ".codex/**", ".gemini/**", ".agents/**", "**.md"}
    owned = {"docs/**": _DOCS}
    assert inert | set(owned) == set(_CODE_LANE_CARVE_OUT), "a carve-out path is neither inert nor lane-owned"

    for carved, workflow in owned.items():
        assert workflow.exists(), f"{carved} is carved out of the Python lanes with no lane of its own"
        triggers = _triggers(_document(workflow))
        for event in ("push", "pull_request"):
            assert carved in set(triggers[event]["paths"]), f"{workflow.name}:{event} does not claim {carved}"


def test_the_docs_lane_claims_every_input_its_build_reads() -> None:
    """The docs lane triggers on the docs tree, its generators, and its corpus.

    A docs lane keyed only on `docs/**` would miss the two surfaces that
    GENERATE the docs tree: the builders and gates under `dev/docs`, and the
    terminology corpus the glossary and shipped search are produced from. A
    change to either can break the build without touching `docs/` at all.
    """
    triggers = _triggers(_document(_DOCS))
    for event in ("push", "pull_request"):
        paths = set(triggers[event]["paths"])
        assert {"docs/**", "dev/docs/**", "src/cadrumo/_data/terminology/**"} <= paths, event

    commands = "\n".join(str(step.get("run", "")) for step in _document(_DOCS)["jobs"]["cadrumo-docs"]["steps"])
    assert "just docs-check" in commands, "the docs lane runs no docs check"


def test_the_docs_verification_lane_never_publishes() -> None:
    """Verification and delivery stay separate lanes with separate triggers.

    docs.yml proves the build on the push that changed it; docs-publish.yml
    ships the site on `release: published`. Conflating them is how a docs
    defect strands a half-published release, and how a routine docs push
    acquires deploy credentials it has no use for.
    """
    document = _document(_DOCS)
    assert set(_triggers(document)) == {"workflow_dispatch", "push", "pull_request"}
    assert document["permissions"] == {"contents": "read"}

    job = document["jobs"]["cadrumo-docs"]
    assert "environment" not in job, "the verification lane must not enter the deploy environment"
    assert "id-token" not in (job.get("permissions") or {}), "the verification lane needs no OIDC federation"
    commands = "\n".join(str(step.get("run", "")) for step in job["steps"])
    for forbidden in ("docs_static_site", "publish", "--confirm"):
        assert forbidden not in commands, forbidden

    # And the delivery lane stays free of push and pull-request triggers, so no
    # ordinary commit can reach it.
    delivery = _triggers(_document(_WORKFLOWS_DIR / "docs-publish.yml"))
    assert set(delivery) == {"release", "workflow_dispatch"}


def test_no_lane_verifies_a_website_this_repository_does_not_contain() -> None:
    """Refuse external-site source or CI ownership in the product repository."""
    # Check the tracked source marker rather than ignored build residue.
    assert not (REPO_ROOT / "frontend" / "package.json").exists(), (
        "external-site source does not belong in the product repository"
    )
    assert not (_WORKFLOWS_DIR / "frontend.yml").exists(), "an external-site lane entered the product repository"


def test_no_workflow_installs_python_dependencies_unfrozen() -> None:
    """Every lane installs from the committed lock, never a live resolve.

    A bare `uv sync` re-resolves the whole dependency graph against the index on
    every job. That costs real time on the lanes that run most often (measured
    on run 30977318339: 2m03s of a 2m25s static job, 1m56s of the unit job, paid
    independently by the two jobs on one machine against one warm cache), and it
    costs attributability: an unfrozen resolve can pick up an index change
    nobody pushed, so a red is not necessarily a property of the commit under
    test.

    Eleven sites across the packaging, release, and delivery lanes were already
    frozen. The only two that were not were ci.yml and ci-full.yml — the
    per-push lane and the full lane, i.e. exactly the ones where both costs
    land hardest.
    """
    offending: list[str] = []
    for path in sorted(
        {*scan_directory(_WORKFLOWS_DIR, pattern="*.yml"), *scan_directory(_WORKFLOWS_DIR, pattern="*.yaml")}
    ):
        document = _document(path)
        for job_name, job in (document.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                for line in str(step.get("run", "")).splitlines():
                    stripped = line.strip()
                    if stripped.startswith("uv sync") and "--frozen" not in stripped:
                        offending.append(f"{path.name}:{job_name}: {stripped}")
    assert offending == [], offending


def test_every_pull_request_workflow_guards_every_job_against_fork_heads() -> None:
    """Every pull_request workflow carries the same-repo guard on every job.

    Fork pull-request head code must never execute on the self-hosted fleet.
    """
    for path in sorted(
        {*scan_directory(_WORKFLOWS_DIR, pattern="*.yml"), *scan_directory(_WORKFLOWS_DIR, pattern="*.yaml")}
    ):
        document = _document(path)
        if "pull_request" not in set(_triggers(document)):
            continue
        for job_name, job in document["jobs"].items():
            assert job.get("if") == _SAME_REPO_GUARD, f"{path.name}:{job_name} lacks the fork guard"


def test_no_workflow_anywhere_uses_actions_artifact_storage() -> None:
    """Zero-Actions-artifact posture, promoted from per-family to repo-wide.

    Evidence rides draft releases; diagnostics live in job logs.
    """
    offending: list[str] = []
    for path in sorted(
        {*scan_directory(_WORKFLOWS_DIR, pattern="*.yml"), *scan_directory(_WORKFLOWS_DIR, pattern="*.yaml")}
    ):
        document = _document(path)
        for job_name, job in (document.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                uses = str(step.get("uses", ""))
                if "upload-artifact" in uses or "download-artifact" in uses:
                    offending.append(f"{path.name}:{job_name}")
    assert offending == [], offending


def test_no_workflow_carries_a_schedule_trigger() -> None:
    """Operator ruling 2026-07-21: manual cadence, no standing compute.

    The project is not developed continuously, so every lane is dispatch-,
    push-, or pull-request-triggered; a schedule trigger anywhere is creeping standing
    compute this gate refuses.
    """
    for path in sorted(
        {*scan_directory(_WORKFLOWS_DIR, pattern="*.yml"), *scan_directory(_WORKFLOWS_DIR, pattern="*.yaml")}
    ):
        assert "schedule" not in set(_triggers(_document(path))), path.name


def test_every_workflow_name_carries_the_product_identity() -> None:
    """Naming convention: kebab-case filenames, `name:` contains "Cadrumo"."""
    for path in sorted(
        {*scan_directory(_WORKFLOWS_DIR, pattern="*.yml"), *scan_directory(_WORKFLOWS_DIR, pattern="*.yaml")}
    ):
        document = _document(path)
        assert "Cadrumo" in document["name"], path.name
        assert path.stem == path.stem.lower(), path.name


def test_durable_maintenance_gates_moved_into_the_full_lane() -> None:
    """The retired weekly workflow's two gates live on in ci-full.yml.

    The vault structural-drift audit and the ledger + storage roundtrip suite
    (aeat-quality-gates: never removed without a replacement).
    """
    assert not (_WORKFLOWS_DIR / "durable-maintenance-gates.yml").exists()
    commands = "\n".join(
        str(step.get("run", "")) for step in _document(_FULL)["jobs"]["cadrumo-full-conformance"]["steps"]
    )
    assert "vaultspec-core vault check all" in commands
    assert "dev/tests/test_roundtrip_coverage.py" in commands
    assert "src/cadrumo/application/ledger/tests" in commands
    assert "src/cadrumo/adapters/persistence/storage" in commands
    assert "src/cadrumo/adapters/persistence/profile" in commands
    assert "-k roundtrip" in commands


def test_drift_detector_targets_exist_on_disk() -> None:
    """Every drift-detector pytest target must exist on disk.

    The l1-anchor-drift failure class: a scheduled workflow whose pytest
    targets moved leaves a red cron nobody attributes.
    """
    repo_root = _WORKFLOWS_DIR.parents[1]
    document = _document(_WORKFLOWS_DIR / "aeat-drift-detector.yml")
    commands = "\n".join(str(step.get("run", "")) for job in document["jobs"].values() for step in job["steps"])
    targets = [token for token in commands.replace("\\", " ").split() if token.startswith("src/")]
    assert targets, "drift detector runs no src-tree pytest targets"
    for target in targets:
        assert (repo_root / target).exists(), f"drift-detector target moved or deleted: {target}"
