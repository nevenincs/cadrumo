"""Structural proof for the single operator-facing surface of a release.

This workflow is the one place a human still makes a release decision, so its
SHAPE carries the safety properties the removed approval click used to imply.
Two absences are asserted as hard as any presence: no input may re-add human
ceremony, and no job may reach the publication authority directly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT: Final[Path] = REPO_ROOT
_WORKFLOW: Final[Path] = _REPO_ROOT / ".github" / "workflows" / "release-orchestrator.yml"


def _document() -> Any:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _run_surface(document: Any, *job_names: str) -> str:
    jobs = document["jobs"]
    selected = [jobs[name] for name in job_names] if job_names else list(jobs.values())
    return "\n".join(str(step.get("run", "")) for job in selected for step in job.get("steps", []) if "run" in step)


def _invocation_surface(document: Any, *job_names: str) -> str:
    """Return the run surface with whole-line shell comments dropped.

    The property these gates assert is what the workflow INVOKES, not what its
    prose mentions. This workflow's comments deliberately name
    `publish-release.yml` to explain that it must never dispatch it, and a
    naive substring scan reads that explanation as the violation - forcing the
    prose to go quiet about exactly the constraint it exists to record. The
    sibling publication gate strips comments for the same reason.

    Only whole-line comments are dropped; a trailing `#` is left in place so a
    real invocation cannot hide behind one.
    """
    return "\n".join(
        line for line in _run_surface(document, *job_names).splitlines() if not line.lstrip().startswith("#")
    )


def test_the_dispatch_takes_exactly_two_inputs() -> None:
    """One rehearsal flag and one resume handle. Nothing else.

    The input set is pinned as an exact equality rather than a subset, because
    every additional input is a decision moved out of the code and onto a form
    where it is neither validated nor recorded.
    """
    triggers = _document()[True]

    assert set(triggers) == {"workflow_dispatch"}, "the orchestrator is dispatched, never triggered by a push"
    assert set(triggers["workflow_dispatch"]["inputs"]) == {"dry_run", "resume_packaging_run_id"}


def test_no_input_reintroduces_a_human_confirmation() -> None:
    """The dispatch IS the intent act; a phrase to type would be ceremony.

    Matched by pattern over input names rather than an allowlist, so a future
    `confirm_publish` or `type_yes_to_continue` reds without anyone remembering
    to extend a list.
    """
    inputs = _document()[True]["workflow_dispatch"]["inputs"]

    ceremony = re.compile(r"confirm|acknowledg|i_understand|type_|yes|approve|proceed", re.IGNORECASE)
    offenders = [name for name in inputs if ceremony.search(name)]
    assert not offenders, f"inputs re-adding the removed human ceremony: {offenders}"


def test_dry_run_defaults_to_the_safe_value() -> None:
    """A dispatch that accepts every default must rehearse, never release.

    The costly direction is asymmetric: defaulting to a real release makes an
    accidental Run-button press irreversible, while defaulting to a rehearsal
    costs one extra dispatch.
    """
    dry_run = _document()[True]["workflow_dispatch"]["inputs"]["dry_run"]

    assert dry_run["type"] == "boolean"
    assert dry_run["default"] is True


def test_two_dispatches_cannot_interleave_two_versions() -> None:
    """Serialised and never cancelled.

    Interleaving races two versions through one manifest: the second bump
    would compute its version from a tree the first had already advanced.
    """
    concurrency = _document()["concurrency"]

    assert concurrency["cancel-in-progress"] is False
    assert "cadrumo" in concurrency["group"], "the group must be product-scoped on a shared account"


def test_every_job_runs_on_the_self_hosted_fleet() -> None:
    """No hosted runner, ever - the standing operator mandate on cost."""
    for name, job in _document()["jobs"].items():
        runner = job["runs-on"]
        assert isinstance(runner, list) and runner[0] == "self-hosted", f"{name} escapes the self-hosted fleet"


def test_the_orchestrator_seals_then_dispatches_publication_directly() -> None:
    """The soak wait is retired by operator ruling.

    The orchestrator itself
    seals the candidate record (the evidence trail) then immediately dispatches
    publish-release.yml with the same run ids, rather than waiting for a
    scheduled promoter to notice an elapsed deadline. The orchestrator itself
    still never calls a publication verb directly - it only ever presses the
    button on the publication authority, which carries its own Gate 2/Gate 3
    checks (including the dry_run propagation asserted elsewhere in this file).
    """
    document = _document()
    surface = _invocation_surface(document)

    assert "publish-release.yml" in surface, "the orchestrator must dispatch the publication authority itself"
    for verb in ("uv publish", "twine upload", "gh release create"):
        assert verb not in surface, f"the orchestrator must not {verb} directly - only publish-release.yml may"
    for name, job in document["jobs"].items():
        assert job.get("permissions", {}).get("id-token") != "write", f"{name} must not mint an OIDC token"
        assert "environment" not in job, f"{name} must not enter a deployment environment"


def test_the_bump_stage_runs_the_tested_bump_executor() -> None:
    """The bump is a module invocation, never shell re-implementing seven surfaces.

    Seven declaration surfaces, a lock, and a changelog block were previously
    transcribed by hand from a printed checklist. Re-expressing that in YAML
    would recreate the same error class one layer down, untested.
    """
    surface = _run_surface(_document(), "bump")

    assert "dev.release.version_bump" in surface
    # The version must never be supplied by hand: it is computed from
    # conventional-commit history inside the module.
    assert "--version" not in surface, "a hand-supplied version is the error class this stage removes"


def test_the_bump_publishes_the_version_and_commit_the_chain_keys_on() -> None:
    """Downstream stages READ the bump's outputs rather than re-deriving them.

    Re-deriving is how a campaign ends up building a different commit than the
    one the bump landed - the two would differ only when something else raced,
    which is exactly when it matters.
    """
    bump = _document()["jobs"]["bump"]

    assert set(bump["outputs"]) == {"version", "commit"}
    assert "steps.bump.outputs.version" in str(bump["outputs"]["version"])


def test_write_authority_is_confined_to_the_two_stages_that_need_it() -> None:
    """Exactly two jobs may write, each for a stated and different reason.

    `bump` lands a commit and a tag. `seal` creates the candidate's own DRAFT
    release, which is not a publication: it lives in a reserved tag namespace
    the evidence GC cannot reach, and only the promoter ever reads it.

    Pinned as an exact set rather than a per-job exemption, so a third job
    acquiring write reds here instead of passing unnoticed.
    """
    jobs = _document()["jobs"]
    writers = {name for name, job in jobs.items() if job.get("permissions", {}).get("contents") == "write"}

    assert writers == {"bump", "seal"}


def test_the_campaign_resolves_its_own_run_rather_than_the_newest() -> None:
    """Identity, not recency - the hazard the whole resolver exists for.

    packaging-smoke QUEUES rather than cancels on a newer dispatch, so the
    newest run of that workflow can belong to a neighbouring campaign.
    Promoting it would seal a cohort this release never built, and every
    downstream hash check would still pass because the cohort is internally
    consistent - just not ours.
    """
    surface = _run_surface(_document(), "campaign")

    assert "dev.release.run_resolution" in surface
    assert ".github/workflows/packaging-smoke.yml" in surface
    # The stage must key on a head commit, which is what makes the resolution
    # an identity question rather than an ordering one.
    assert "--head-sha" in surface

    # A bare newest-run query is exactly the shortcut this must never take.
    for shortcut in ("--limit 1", "runs?per_page=1", "| head -1", "[0].id", "--jq '.workflow_runs[0]"):
        assert shortcut not in surface, f"campaign stage takes the recency shortcut: {shortcut}"


def test_the_campaign_builds_the_commit_the_bump_landed() -> None:
    """The campaign keys on the bump's output commit, never a re-derived one.

    A re-derived commit differs from the bump's only when something else raced
    - which is precisely the moment the difference matters.
    """
    campaign = _document()["jobs"]["campaign"]

    assert "bump" in campaign["needs"]
    assert "needs.bump.outputs.commit" in str(campaign)


def test_campaign_dispatch_cannot_override_resolution_with_a_mutable_ref() -> None:
    """The resolver owns one SHA for both dispatch and run identity matching."""
    surface = _run_surface(_document(), "campaign")

    assert '--head-sha "${head_sha}"' in surface
    assert "--ref" not in surface


def test_the_acquisition_lane_set_is_derived_not_hardcoded() -> None:
    """Lanes come from the claimed-channel authority the publication gate reads.

    Hardcoding them would let the two disagree: a channel flipped to
    `available` would demand evidence at the publication gate that no lane in
    this workflow ever produced, and the release would refuse at the very end
    of the chain instead of dispatching one more run at the start.
    """
    surface = _run_surface(_document(), "acquire")

    assert "dev.packaging.publication_inputs --emit-lane-workflows" in surface
    # No lane workflow may be named literally here - naming one IS the
    # hardcoding this test forbids.
    for lane in ("packaging-scoop.yml", "packaging-homebrew.yml"):
        assert lane not in surface, f"{lane} is hardcoded; the lane set must be derived"


def test_each_dispatched_lane_carries_this_release_s_cohort_and_commit() -> None:
    """Every lane is pinned to the campaign's own run and commit.

    A lane dispatched without them would install whatever the shared
    repository last published, proving a previous release rather than this one.
    """
    surface = _run_surface(_document(), "acquire")

    assert "source_run_id=" in surface
    assert "source_commit=" in surface
    assert "needs.campaign.outputs.packaging_run_id" in str(_document()["jobs"]["acquire"])


def test_todays_python_only_descriptor_dispatches_no_acquisition_lane() -> None:
    """Bound to the real descriptor: the loop is legitimately empty right now.

    Asserted against the shipped channel descriptor rather than a fixture,
    because the property that matters is that THIS repository's current claims
    produce no lane - which is what makes the empty loop correct rather than
    broken.
    """
    from ...docs.download_matrix import load_descriptor
    from ...packaging.publication_inputs import acquisition_lane_workflows

    assert acquisition_lane_workflows(load_descriptor()) == ()


def test_the_seal_job_is_terminal() -> None:
    """Nothing depends on the seal, because the run ends there.

    The soak runs 48-72 hours. No run spans it, and a job that waited would
    hold one of four shared self-hosted runners for days - so the chain records
    its state durably and stops. A job downstream of the seal would either be
    waiting or publishing, and both are wrong here.
    """
    jobs = _document()["jobs"]

    assert "seal" in jobs
    dependents = [name for name, job in jobs.items() if "seal" in (job.get("needs") or [])]

    # The failure-only alert job is not a chain STAGE: it runs solely under
    # `failure()`, produces nothing, and cannot extend the release past the
    # seal. Excluding it keeps this assertion about the property that matters -
    # that no stage waits on or continues after the seal - rather than about
    # the shape of the needs graph.
    stages = [name for name in dependents if "failure()" not in str(jobs[name].get("if", ""))]
    assert stages == [], f"release stages depending on the terminal seal: {stages}"


def test_no_job_waits_out_the_soak_inside_the_run() -> None:
    """A held runner is the failure mode this whole design avoids.

    Asserted over the entire workflow rather than the seal alone, because the
    tempting shortcut is a sleep or poll added anywhere in the chain.
    """
    surface = _invocation_surface(_document())

    for held in ("sleep ", "soak_promoter", "select_promotable"):
        assert held not in surface, f"the orchestrator must not wait out the soak ({held})"


def test_the_seal_records_state_through_the_tested_candidate_module() -> None:
    """The candidate is minted by the module whose roundtrip and window are tested."""
    surface = _run_surface(_document(), "seal")

    assert "dev.release.seal_candidate" in surface
    assert "--packaging-run-id" in surface


def test_the_seal_module_exists_and_is_runnable() -> None:
    """The workflow and the module cannot drift apart silently.

    A workflow naming a module path that does not exist fails only when
    someone dispatches a release, which is the worst possible moment to
    discover it.
    """
    module = _REPO_ROOT / "dev" / "release" / "seal_candidate.py"

    assert module.is_file()
    assert "def main(" in module.read_text(encoding="utf-8")


def test_dry_run_reaches_every_stage_of_the_chain() -> None:
    """The rehearsal proves bump, campaign, acquisition, and seal.

    A rehearsal that skipped any of the four newly-automated stages would
    leave it exercised only by a real release. It stops at the seal rather
    than reaching publish-release.yml's own gates -- Gate 2 there pins the
    exact packaging-smoke.yml source, which a rehearsal's lightweight
    campaign lane structurally cannot produce (see the campaign/seal tests
    below), so re-proving Gate 1/2 needs a real dispatch regardless.
    """
    document = _document()
    jobs = document["jobs"]

    # preflight resolves it once; every later stage reads that resolution
    # rather than re-reading the raw input, so they cannot disagree.
    assert "dry_run" in jobs["preflight"]["outputs"]
    for stage in ("bump", "campaign", "seal"):
        assert "needs.preflight.outputs.dry_run" in str(jobs[stage]), f"{stage} does not read the resolved dry_run"


def test_a_rehearsal_uses_the_quick_campaign_not_the_full_smoke() -> None:
    """A rehearsal proves the chain wires together, not that the campaign is green.

    That's what the campaign's own CI already checks. The
    full packaging-smoke.yml campaign has historically taken 1-6 hours; a
    dispatch whose dry_run defaults to true must not pay that cost just to
    exercise bump/campaign/acquire/seal wiring, or every rehearsal becomes
    the fleet's single longest-running job.
    """
    surface = _run_surface(_document(), "campaign")

    assert "packaging-quick.yml" in surface, "the campaign stage never mentions the lightweight lane"
    assert 'DRY_RUN}" == "true"' in surface, "the workflow choice must branch on the resolved dry_run"


def test_a_rehearsal_never_dispatches_the_publication_authority() -> None:
    """The seal step must not fire publish-release.yml for a dry_run candidate.

    Gate 2 there pins the packaging-smoke.yml path; a rehearsal's candidate
    points at packaging-quick.yml and would refuse every single time -- a
    permanent, expected-looking failure with no diagnostic value, on a
    separate workflow run the orchestrator's own alerting can't see.
    """
    surface = _run_surface(_document(), "seal")

    assert 'DRY_RUN}" == "true"' in surface, "the publish-dispatch step must branch on the resolved dry_run"
    assert "not dispatching publish-release.yml" in surface, "the skip must be visible in the run log, not silent"


def test_a_real_release_waits_for_its_own_publication_before_consuming_the_candidate() -> None:
    """Only a conclusively green publication may retire the selectable draft.

    A bare ``gh workflow run`` proves only that GitHub accepted the dispatch;
    it says nothing about Gate 2/Gate 3 or publication. The tested resolver
    identifies this dispatch by immutable commit, waits for its conclusion,
    and exits non-zero on failure. Shell fail-fast ordering then guarantees the
    consumption primitive is unreachable after a rejected or failed publish.
    """
    surface = _invocation_surface(_document(), "seal")

    dispatch = surface.index("dev.release.run_resolution")
    consume = surface.index("mark_candidate_consumed")
    assert dispatch < consume, "the candidate must remain selectable until publication succeeds"
    assert '.github/workflows/publish-release.yml' in surface
    assert '--head-sha "${HEAD_SHA}"' in surface
    assert "--conclude-seconds 7200" in surface, "the publication conclusion must be awaited"
    assert "dev.release.release_candidate import candidate_tag, mark_candidate_consumed" in surface
    assert "gh workflow run publish-release.yml" not in surface, "fire-and-forget cannot prove publication success"


def test_candidate_consumption_uses_the_packaging_run_identity() -> None:
    """The retired draft must be the candidate sealed by this exact campaign."""
    seal = _document()["jobs"]["seal"]
    surface = _run_surface(_document(), "seal")

    assert "needs.campaign.outputs.head_sha" in str(seal)
    assert 'candidate_tag(os.environ["PACKAGING_RUN_ID"])' in surface


def test_a_rehearsal_does_not_consume_its_candidate() -> None:
    """The existing dry-run exit remains ahead of both publication and retirement."""
    surface = _invocation_surface(_document(), "seal")

    rehearsal_exit = surface.index('DRY_RUN}" == "true"')
    consume = surface.index("mark_candidate_consumed")
    assert rehearsal_exit < consume


_BUMP_BRANCH = re.compile(
    r'if\s*\[\[\s*"\$\{DRY_RUN\}"\s*==\s*"true"\s*\]\]\s*;\s*then\s+'
    r"bump_mode=\((?P<rehearsal>[^)]*)\)\s+"
    r"else\s+"
    r"bump_mode=\((?P<real>[^)]*)\)",
)


def bump_polarity(body: str) -> tuple[str, str]:
    """Return (rehearsal-branch flag, real-branch flag) from the bump stage.

    Extracts the branch->flag MAPPING rather than checking that both flags
    appear somewhere. Presence checks cannot tell `--dry-run` on the rehearsal
    branch from `--dry-run` on the real one, which is the entire property.
    """
    match = _BUMP_BRANCH.search(body)
    if match is None:
        raise AssertionError("the bump stage no longer carries a parseable rehearsal/real branch")
    return match.group("rehearsal").strip(), match.group("real").strip()


def assert_bump_polarity(body: str) -> None:
    """Raise unless the rehearsal branch rehearses and the real branch pushes."""
    rehearsal, real = bump_polarity(body)
    assert rehearsal == "--dry-run", f"the rehearsal branch emits {rehearsal!r}, not --dry-run"
    assert real == "--push", f"the real branch emits {real!r}, not --push"


def test_the_bump_branch_polarity_is_pinned_as_a_mapping() -> None:
    """Which branch emits which flag, not merely that both flags exist.

    The previous form asserted three independent substring presences, so
    swapping the two flags left the whole suite green. Inverted, `dry_run`
    defaults to true, so a rehearsal would push a real version bump and tag -
    the one irreversible act this design exists to gate - while a real dispatch
    would never land its version.
    """
    assert_bump_polarity(_run_surface(_document(), "bump"))


def test_inverting_the_bump_branch_reds_this_gate() -> None:
    """Mutation control: apply the exact inversion and prove the gate catches it.

    This is the assertion the old test lacked. Without it, a polarity check that
    had quietly stopped checking polarity is indistinguishable from a correct
    one, which is how the original vocabulary check survived review.
    """
    body = _run_surface(_document(), "bump")
    inverted = body.replace("bump_mode=(--dry-run)", "bump_mode=(@TMP@)")
    inverted = inverted.replace("bump_mode=(--push)", "bump_mode=(--dry-run)")
    inverted = inverted.replace("bump_mode=(@TMP@)", "bump_mode=(--push)")
    assert inverted != body, "the inversion did not apply; this control is not exercising anything"

    with pytest.raises(AssertionError, match="rehearsal branch emits"):
        assert_bump_polarity(inverted)


def test_a_rehearsal_bump_pushes_no_ref() -> None:
    """The one irreversible thing the bump does is gated on the rehearsal flag."""
    surface = _invocation_surface(_document(), "bump")

    assert "--dry-run" in surface
    assert "--push" in surface


def test_a_resume_skips_the_bump_so_no_second_version_is_burned() -> None:
    """Recovering from a late failure must not cost another version.

    A chain that failed after a successful campaign has already landed a
    version. Re-bumping to retry would burn a second one permanently via the
    identity ledger, to recover from a failure that had nothing to do with the
    first.
    """
    bump = _document()["jobs"]["bump"]

    assert bump["if"] == "${{ needs.preflight.outputs.resume == '' }}"


def test_a_resumed_run_is_verified_on_gate_twos_terms() -> None:
    """The one place an operator still types a run id is the one place to check it.

    Unverified, a resume could carry a foreign, failed, or never-landed
    campaign's cohort straight to a sealed candidate - and every later hash
    check would pass, because that cohort is internally consistent.
    """
    surface = _invocation_surface(_document(), "campaign")

    assert ".conclusion" in surface and "success" in surface
    assert ".github/workflows/packaging-smoke.yml" in surface
    assert "head_repository.full_name" in surface
    # main-ancestry, matching Gate 2's own dispatch-event rule.
    assert "compare/main..." in surface
    assert 'ancestry" = "identical"' in surface


def test_the_campaign_is_skipped_on_resume_without_skipping_the_chain() -> None:
    """The resume path reuses the campaign job rather than bypassing it.

    Bypassing would mean the seal reads its run id from a different place on
    the resume path than on the normal path - two sources for one fact, which
    is how they drift.
    """
    campaign = _document()["jobs"]["campaign"]

    assert "always()" in campaign["if"], "a skipped bump must not skip the campaign job on the resume path"
    assert "needs.bump.result != 'failure'" in campaign["if"], "a genuinely failed bump must still stop the chain"


def test_every_acquisition_run_id_reaches_the_seal_stage() -> None:
    """The ids were computed and then dropped at the job boundary.

    `seal_candidate` reads two acquisition environment variables; the stage
    declared no outputs and the seal step set none, so a sealed candidate
    recorded empty acquisition sources and the promoter would dispatch the
    publication without its acquisition proofs. Vacuous only while the
    descriptor claims python alone - it arms the moment a channel is claimed,
    which is exactly when nobody is looking for it.
    """
    jobs = _document()["jobs"]
    acquire_outputs = set(jobs["acquire"].get("outputs") or {})

    assert acquire_outputs == {"scoop_run_id", "homebrew_run_id"}

    seal_env = str(jobs["seal"]["steps"][-1].get("env", {}))
    # Both acquisition run ids are fed from the acquisition stage.
    for variable, output in (
        ("SCOOP_RUN_ID", "scoop_run_id"),
        ("HOMEBREW_RUN_ID", "homebrew_run_id"),
    ):
        assert variable in seal_env, f"the seal step does not set {variable}"
        assert f"needs.acquire.outputs.{output}" in seal_env, f"{variable} is not fed from the acquire stage"


def test_the_seal_reads_exactly_the_variables_the_module_consumes() -> None:
    """Bind the workflow's env names to the module's own reads.

    The original defect was a silent mismatch between two files that never
    reference each other, so this asserts against the module source rather
    than restating the names a second time.
    """
    module = (_REPO_ROOT / "dev" / "release" / "seal_candidate.py").read_text(encoding="utf-8")
    seal_env = str(_document()["jobs"]["seal"]["steps"][-1].get("env", {}))

    for variable in ("SCOOP_RUN_ID", "HOMEBREW_RUN_ID"):
        assert f'"{variable}"' in module, f"{variable} is no longer read by the seal module"
        assert variable in seal_env, f"{variable} is read by the module but never set by the workflow"


def test_an_unmapped_acquisition_lane_refuses_rather_than_dropping_its_run_id() -> None:
    """A future lane with no output name must fail loudly, not silently vanish.

    This is the same defect class one step later: adding a lane without
    plumbing its id would otherwise reproduce exactly the drop this guard
    fixes.
    """
    surface = _invocation_surface(_document(), "acquire")

    assert "carries no output name" in surface
    assert "--output-name" in surface


_RESUME_CHECK = re.compile(
    r'test\s+"\$\(jq -r \.(?P<field>[\w.]+) <<<"\$run_json"\)"\s*(?P<op>!?=)\s*"(?P<value>[^"]*)"'
)


def resume_identity_checks(body: str) -> dict[str, tuple[str, str]]:
    """Return each verified field mapped to its (operator, expected value).

    Captures the OPERATOR as well as the value. A scan that only confirmed the
    field names and expected literals appear would pass just as happily on
    `!=`, which inverts every check into accepting exactly what it was written
    to refuse.
    """
    return {m.group("field"): (m.group("op"), m.group("value")) for m in _RESUME_CHECK.finditer(body)}


def assert_resume_identity_polarity(body: str) -> None:
    """Raise unless every resume identity check ACCEPTS its expected value."""
    checks = resume_identity_checks(body)
    for field, expected in (
        ("conclusion", "success"),
        ("path", ".github/workflows/packaging-smoke.yml"),
        ("head_repository.full_name", "${GITHUB_REPOSITORY}"),
    ):
        assert field in checks, f"the resume path no longer verifies {field}"
        operator, value = checks[field]
        assert operator == "=", f"{field} is compared with {operator!r}, which accepts what it should refuse"
        assert value == expected, f"{field} is compared against {value!r}, expected {expected!r}"


def test_the_resume_identity_checks_are_pinned_by_polarity_not_vocabulary() -> None:
    """Same class as the bump ternary, one severity lower.

    A resume is the only place an operator still types a run id, so these are
    the checks standing between a typo and a sealed candidate built from a
    foreign, failed, or never-landed campaign.
    """
    assert_resume_identity_polarity(_run_surface(_document(), "campaign"))

    # The ancestry check is a two-branch acceptance rather than a single
    # equality, so it is asserted separately and on both accepted values.
    surface = _run_surface(_document(), "campaign")
    assert 'ancestry" = "identical"' in surface
    assert 'ancestry" = "behind"' in surface


def test_inverting_a_resume_identity_check_reds_this_gate() -> None:
    """Mutation control: flip one comparison to `!=` and prove the gate catches it."""
    body = _run_surface(_document(), "campaign")
    inverted = body.replace(
        'test "$(jq -r .conclusion <<<"$run_json")" = "success"',
        'test "$(jq -r .conclusion <<<"$run_json")" != "success"',
    )
    assert inverted != body, "the inversion did not apply; this control is not exercising anything"

    with pytest.raises(AssertionError, match="accepts what it should refuse"):
        assert_resume_identity_polarity(inverted)
