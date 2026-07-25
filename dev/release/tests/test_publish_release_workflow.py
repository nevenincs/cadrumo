"""Structural proof that the real publication authority stays fail-closed.

``publish-release.yml`` is the sole upload authority (the former validate-only
``publish.yml`` diagnostic stub was retired; its ``dry_run`` mode now lives on
this authority). These tests pin its safety contract: it is inert until the
operator opts in, it never builds or regenerates an artifact, OIDC minting is
confined to the environment-protected publish job, and every external channel
push refuses instructively when its credential is absent.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "publish-release.yml"

# A build/regenerate invocation is forbidden in EVERY job: publication promotes
# stored bytes and must never rebuild. Publishing/upload verbs are deliberately
# excluded here because the environment-protected publish job legitimately runs
# them; their confinement is asserted separately.
_BUILD_RUN_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\buv\s+build\b", re.IGNORECASE),
    re.compile(r"\bpython[0-9.]*\s+-m\s+build\b", re.IGNORECASE),
    re.compile(r"\bpip[0-9.]*\s+wheel\b", re.IGNORECASE),
    re.compile(r"\b(?:poetry|flit|hatch|pdm)\s+build\b", re.IGNORECASE),
    re.compile(r"\bsetup\.py\b[^\n]*\b(?:sdist|bdist_wheel|bdist|build)\b", re.IGNORECASE),
    re.compile(r"\bpackaging/\S*generate\.py\b", re.IGNORECASE),
    re.compile(r"\brelease_cohort\b", re.IGNORECASE),
)

# Jobs permitted to invoke a publish/upload verb. Publication is confined to the
# single environment-protected job; every other job is read-only.
_PUBLISHING_JOBS: Final[frozenset[str]] = frozenset({"publish"})

# A publish verb is legitimate inside `_PUBLISHING_JOBS` and forbidden outside it,
# so unlike the build set this one is scanned per job rather than workflow-wide.
#
# These patterns are anchored to a shell COMMAND POSITION -- line start, or after
# `;`, `&`, `|`, or `$(` -- because the operator-preflight refusal text quotes
# `gh release create` as prose inside an echoed instruction. An unanchored scan
# flags that documentation and reds the gate on a false positive. A backtick is
# deliberately NOT treated as a command position for the same reason: the only
# three backticks in the workflow are documentation prose, and it uses `$( )`
# rather than legacy backtick substitution for real command expansion.
#
# SCOPE BOUNDARY, for anyone widening this scan beyond `publish-release.yml`:
# the four packaging workflows (smoke, scoop, homebrew, claude) each call
# `gh release create` once, and every one of those is machine EVIDENCE TRANSPORT,
# not publication -- it mints a per-run draft carrying rows, cohorts, and sealed
# manifests, and never a release. They are benign and must be pinned as such
# rather than silencing the pattern, which would re-open the hole this gate
# closes. The discriminators are `--draft` together with an `evidence-*` tag
# prefix and an "EVIDENCE (non-release)" title; a real publication carries a
# `v$VERSION` tag and no `--draft`. Widen by exempting on that evidence shape,
# never by loosening the verb patterns below.
_COMMAND_POSITION: Final[str] = r"(?:^|[;&|]|\$\()[ \t]*"

_PUBLISH_RUN_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(rf"{_COMMAND_POSITION}uv\s+publish\b", re.IGNORECASE | re.MULTILINE),
    re.compile(
        rf"{_COMMAND_POSITION}(?:python[0-9.]*\s+-m\s+)?twine\s+upload\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        rf"{_COMMAND_POSITION}(?:poetry|flit|hatch|pdm)\s+publish\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(rf"{_COMMAND_POSITION}npm\s+publish\b", re.IGNORECASE | re.MULTILINE),
    re.compile(
        rf"{_COMMAND_POSITION}gh\s+release\s+(?:create|upload|edit|delete)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    # The Scoop bucket, Homebrew tap, and marketplace channels publish by pushing
    # a cloned working copy, so a push from any non-publish job is an egress too.
    re.compile(rf"{_COMMAND_POSITION}git\b[^\n]*?\bpush\b", re.IGNORECASE | re.MULTILINE),
)


def _command_lines(surface: str) -> str:
    """Drop whole-line shell comments so a commented verb is not read as an invocation.

    Only lines whose first non-whitespace character is ``#`` are dropped. A
    trailing comment is deliberately left in place: stripping from the first ``#``
    anywhere would also cut ``${var#prefix}`` parameter expansion and could hide a
    real invocation behind a quoted ``#``, which is the false-green shape these
    gates exist to prevent.
    """
    return "\n".join(line for line in surface.splitlines() if not line.lstrip().startswith("#"))


def _pattern_hits(surface: str, patterns: tuple[re.Pattern[str], ...]) -> list[str]:
    """Return every denylisted invocation in ``surface``, whitespace-normalised."""
    cleaned = _command_lines(surface)
    return [" ".join(match.group(0).split()) for pattern in patterns for match in pattern.finditer(cleaned)]


def _document() -> Any:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _run_surface(job: Mapping[str, object]) -> str:
    steps = job["steps"]
    assert isinstance(steps, list)
    return "\n".join(str(step.get("run", "")) for step in steps if isinstance(step, Mapping) and "run" in step)


def test_workflow_shape_and_least_privilege_top_level() -> None:
    """One run-bound input, least-privilege top-level perms, the three staged jobs."""
    document = _document()
    dispatch = document[True]["workflow_dispatch"]
    assert set(dispatch["inputs"]) == {
        "packaging_run_id",
        "scoop_run_id",
        "homebrew_run_id",
        "claude_evidence_release",
        "dry_run",
    }
    assert document["permissions"] == {"contents": "read"}
    assert set(document["jobs"]) == {"operator-preflight", "validate", "publish"}


def test_dry_run_validates_everything_and_skips_publish() -> None:
    """A dry_run dispatch runs Gate 1+2 fully but gates the publish job off."""
    document = _document()
    dry_run = document[True]["workflow_dispatch"]["inputs"]["dry_run"]
    assert dry_run["type"] == "boolean"
    assert dry_run["default"] is False
    assert dry_run["required"] is False
    # Only the publish job is conditioned on dry_run; operator-preflight and
    # validate always run so the validate-everything-publish-nothing mode is real.
    publish = document["jobs"]["publish"]
    assert publish["if"] == "${{ inputs.dry_run != true }}"
    assert "if" not in document["jobs"]["operator-preflight"]
    assert "if" not in document["jobs"]["validate"]


def test_inert_until_operator_opt_in() -> None:
    """The first gate refuses unless the operator sets CADRUMO_PUBLISH_ENABLED=true."""
    preflight = _document()["jobs"]["operator-preflight"]
    surface = _run_surface(preflight)
    assert "vars.CADRUMO_PUBLISH_ENABLED" in _WORKFLOW.read_text(encoding="utf-8")
    assert 'PUBLISH_ENABLED}" != "true"' in surface
    assert "REFUSED: Cadrumo publication is not enabled" in surface


def test_oidc_and_write_are_confined_to_the_protected_publish_job() -> None:
    """id-token/contents:write live only on the environment-protected publish job."""
    document = _document()
    publish = document["jobs"]["publish"]
    assert publish["environment"] == "release"
    assert publish["permissions"] == {"id-token": "write", "contents": "write"}
    assert publish["needs"] == "validate"

    for name in ("operator-preflight", "validate"):
        perms = document["jobs"][name].get("permissions", {})
        assert perms.get("id-token") != "write", f"{name} must not mint an OIDC token"


def test_validate_promotes_without_rebuild() -> None:
    """The validate gate re-verifies retained bytes; it never builds or publishes."""
    validate = _document()["jobs"]["validate"]
    surface = _run_surface(validate)
    assert "dev.release.promote_python_cohort" in surface
    assert "dev.release.readiness" in surface
    assert "cadrumo-release-cohort" in surface
    # The per-OS smoke build artifact never enters the publication chain; the
    # promotion guard is re-pointed at the sealed cohort's python bytes, and the
    # sealed cohort's installed behaviour is proven by the DistributionEvidence
    # rows the readiness gate reads.
    assert "--name cadrumo-python-cohort" not in surface
    assert "--check-pypi-only" in surface
    # Every channel's rows arrive hash-verified from its evidence draft.
    assert "dev.packaging.evidence_release verify" in surface
    # No publish verb in the read-only validate gate.
    assert "uv publish" not in surface
    assert "gh release create" not in surface


def test_validate_aggregates_all_eleven_rows_from_authoritative_sources() -> None:
    """Gate 2 pulls every channel's rows from its own run and re-checks 11/11, no weakening.

    Eleven is the true bound set: ``REQUIRED_DISTRIBUTION_ROWS`` carries exactly
    3 python + 1 scoop + 3 homebrew + 4 claude-* rows, and Gate 2 aggregates the
    same partition (packaging smoke draft, scoop, homebrew, and the operator's
    claude evidence release).
    """
    validate = _document()["jobs"]["validate"]
    surface = _run_surface(validate)

    # Each channel's rows come verified from its authoritative run's evidence
    # draft; the tags are DERIVED from the run-id inputs (no free-form evidence
    # tag input except the operator's claude release, which has no backing run).
    assert 'verify "evidence-smoke-$PACKAGING_RUN_ID"    "$PACKAGING_RUN_ID"' in surface
    assert 'verify "evidence-scoop-$SCOOP_RUN_ID"        "$SCOOP_RUN_ID"' in surface
    assert 'verify "evidence-homebrew-$HOMEBREW_RUN_ID"  "$HOMEBREW_RUN_ID"' in surface
    assert 'gh release download "$CLAUDE_EVIDENCE_RELEASE"' in surface

    # Trusted-source predicate on the smoke run (ci-speed redesign): a
    # dispatch-event campaign run is accepted only when its commit is verified
    # on main history via the compare API; push stays accepted for historical
    # campaign runs.
    assert '"$event" = "workflow_dispatch"' in surface
    assert "/compare/main..." in surface
    assert 'test "$ancestry" = "identical" -o "$ancestry" = "behind"' in surface

    # Per-source identity checks on the acquisition runs (parity with the smoke gate).
    assert ".github/workflows/packaging-scoop.yml" in surface
    assert ".github/workflows/packaging-homebrew.yml" in surface
    assert 'event <<<"$run_json")" = "workflow_dispatch"' in surface
    assert 'head_repository.full_name <<<"$run_json")" = "$GITHUB_REPOSITORY"' in surface

    # The readiness gate still enforces the complete bound row set (no weakening).
    assert "dev.release.readiness" in surface
    assert "--evidence-dir" in surface


def test_workflow_row_count_prose_matches_the_required_distribution_set() -> None:
    """Both Gate-2/Gate-3 row-count comments name the true REQUIRED_DISTRIBUTION_ROWS size."""
    from dev.release.readiness import REQUIRED_DISTRIBUTION_ROWS

    assert len(REQUIRED_DISTRIBUTION_ROWS) == 11
    text = _WORKFLOW.read_text(encoding="utf-8")
    # The stale "twelve" drift is reconciled to the one true count everywhere.
    assert "twelve" not in text
    assert "Aggregate all eleven rows" in text
    assert "eleven verified rows" in text


def test_validate_runs_the_open_blocker_check_over_the_network() -> None:
    """Gate 2 drops --skip-network so the readiness gate's open-P0-blocker check runs here."""
    validate = _document()["jobs"]["validate"]
    # issues:read is granted so the gh-backed blocker query can succeed here.
    # Authority against a failed/blind query comes from the readiness gate's
    # strict mode on the cohort-dir path (cannot-determine -> blocking), verified
    # in test_readiness; a granted scope alone does not make a fail-open advisory
    # authoritative.
    assert validate["permissions"].get("issues") == "read"

    steps = validate["steps"]
    assert isinstance(steps, list)
    readiness_step = next(
        step for step in steps if isinstance(step, Mapping) and "dev.release.readiness" in str(step.get("run", ""))
    )
    # Inspect the executable lines only; a comment may still explain the change.
    command = "\n".join(line for line in str(readiness_step["run"]).splitlines() if not line.lstrip().startswith("#"))
    assert "--skip-network" not in command, "Gate 2 must run the networked open-blocker check"
    assert "dev.release.readiness" in command
    # The blocker query needs a token; the step provides the workflow token.
    env = readiness_step.get("env", {})
    assert isinstance(env, Mapping)
    assert env.get("GH_TOKEN") == "${{ github.token }}"


def test_pypi_ships_the_sealed_cohort_not_the_per_os_smoke_build() -> None:
    """Every PyPI upload path resolves under the sealed release cohort's python dir."""
    publish = _document()["jobs"]["publish"]
    surface = _run_surface(publish)
    # The per-OS smoke build (cadrumo-python-cohort) is out of the publish chain.
    assert "--name cadrumo-python-cohort" not in surface
    # Each of the six wheels/sdists is uploaded from RELEASE_COHORT_DIR/python.
    for artifact in (
        'cadrumo-"$VERSION"-py3-none-any.whl',
        'cadrumo-"$VERSION".tar.gz',
        'cadrumo_data_manuals-"$VERSION"-py3-none-any.whl',
        'cadrumo_data_manuals-"$VERSION".tar.gz',
        'cadrumo_data_official-"$VERSION"-py3-none-any.whl',
        'cadrumo_data_official-"$VERSION".tar.gz',
    ):
        assert f'"$RELEASE_COHORT_DIR"/python/{artifact}' in surface


def test_no_job_ever_builds_or_regenerates_an_artifact() -> None:
    """Promotion moves stored bytes; a build/regenerate invocation is forbidden anywhere."""
    document = _document()
    offenders: dict[str, list[str]] = {}
    for job_name, job in document["jobs"].items():
        hits = _pattern_hits(_run_surface(job), _BUILD_RUN_PATTERNS)
        if hits:
            offenders[job_name] = hits
    assert offenders == {}, f"publication must never build/regenerate: {offenders}"


def test_no_non_publish_job_invokes_a_publish_verb() -> None:
    """Publish/upload verbs are confined to the environment-protected publish job.

    The sibling assertions pin this with exact-substring ``not in`` guards for the
    two spellings the workflow happens to use today, so a differently-spelled
    egress in the read-only validate gate -- ``twine upload``, ``poetry publish``,
    a ``gh release upload``, or a tap ``git push`` -- would slip past both those
    guards and the parsed-YAML presence checks. This is the structural half.
    """
    document = _document()
    offenders: dict[str, list[str]] = {}
    for job_name, job in document["jobs"].items():
        if job_name in _PUBLISHING_JOBS:
            continue
        hits = _pattern_hits(_run_surface(job), _PUBLISH_RUN_PATTERNS)
        if hits:
            offenders[job_name] = hits
    assert offenders == {}, f"only {sorted(_PUBLISHING_JOBS)} may publish; found egress in: {offenders}"


def test_the_publish_job_is_the_one_that_actually_publishes() -> None:
    """Anti-vacuity for the confinement scan: the exempted job really does publish.

    Without this, deleting every publish verb from the workflow -- or renaming the
    publish job -- would leave the confinement test passing over an empty set.
    """
    hits = _pattern_hits(_run_surface(_document()["jobs"]["publish"]), _PUBLISH_RUN_PATTERNS)
    assert len(hits) >= 4, f"expected the real publish surface to carry its egress verbs, saw {hits}"


@pytest.mark.parametrize(
    "forbidden",
    [
        "uv build",
        "python -m build",
        "python3.12 -m build",
        "pip wheel .",
        "poetry build",
        "hatch build",
        "pdm build",
        "flit build",
        "python setup.py sdist",
        "python setup.py bdist_wheel",
        "uv run packaging/cohort/generate.py",
        "python -m dev.release.release_cohort",
    ],
)
def test_build_detector_flags_every_forbidden_build_spelling(forbidden: str) -> None:
    """Non-vacuity: each build spelling the denylist claims to bar is really flagged."""
    assert _pattern_hits(forbidden, _BUILD_RUN_PATTERNS), f"build denylist missed {forbidden!r}"


@pytest.mark.parametrize(
    "forbidden",
    [
        "uv publish --trusted-publishing always",
        "twine upload dist/*",
        "python -m twine upload dist/*",
        "poetry publish",
        "flit publish",
        "hatch publish",
        "pdm publish",
        "npm publish",
        'gh release create "v$VERSION"',
        'gh release upload "v$VERSION" file.json',
        'gh release delete "v$VERSION"',
        'git -C "$work" -c http.extraheader="$auth" push',
        "cd tap && git push origin main",
    ],
)
def test_publish_detector_flags_every_forbidden_publish_spelling(forbidden: str) -> None:
    """Non-vacuity: each egress spelling the denylist claims to bar is really flagged."""
    assert _pattern_hits(forbidden, _PUBLISH_RUN_PATTERNS), f"publish denylist missed {forbidden!r}"


@pytest.mark.parametrize(
    "benign",
    [
        # The workflow's own real promotion verbs must never read as a BUILD.
        "uv publish --trusted-publishing always",
        'gh release create "v$VERSION" "${assets[@]}"',
        'gh release upload "v$VERSION" "$DIR/download-latest.json"',
        'git -C "$work" -c http.extraheader="$auth" push',
        'git -c http.extraheader="$auth" clone "https://github.com/${TAP_REPO}.git"',
        # Ordinary read-only validate-gate work.
        "uv sync --frozen",
        "uv run python -m dev.release.readiness",
        "python -m dev.packaging.evidence_release verify",
    ],
)
def test_build_detector_leaves_publish_and_read_only_verbs_alone(benign: str) -> None:
    """Negative control: the build denylist must not creep into the promotion verbs.

    Tightening the build patterns until they also match a publish or a checkout
    would red the workflow's own legitimate promotion steps, so each real egress
    invocation is pinned here as benign *for the build detector*.
    """
    assert _pattern_hits(benign, _BUILD_RUN_PATTERNS) == [], f"build denylist over-matched {benign!r}"


@pytest.mark.parametrize(
    "benign",
    [
        # Documentation prose in the preflight refusal text, not an invocation.
        "them to a release (`gh release create <tag> --draft <row json...>`);",
        "(`python -m dev.packaging.emit_real_client_evidence ...`) and upload",
        # A whole-line comment naming a verb is not an invocation.
        "# gh release create flattens every asset to its basename",
        # Read-only channel reads and git operations that publish nothing.
        'gh release view "v$VERSION"',
        'gh release download "v$VERSION"',
        'git -c http.extraheader="$auth" clone "https://github.com/${TAP_REPO}.git" "$work"',
        'git -C "$work" add -- bucket/cadrumo.json',
        'git -C "$work" diff --cached --quiet',
        'echo "marketplace already at cadrumo $VERSION; nothing to push"',
        "uv sync --frozen",
    ],
)
def test_publish_detector_leaves_prose_comments_and_read_only_verbs_alone(benign: str) -> None:
    """Negative control: quoted prose, comments, and read-only verbs are not egress.

    The command-position anchor and the whole-line comment filter exist for these
    exact shapes; without them the gate reds on the preflight instruction text.
    """
    assert _pattern_hits(benign, _PUBLISH_RUN_PATTERNS) == [], f"publish denylist over-matched {benign!r}"


def test_external_channel_pushes_refuse_instructively_when_unconfigured() -> None:
    """The externally-hosted channels fail closed with instructions when credentials are absent.

    Scoop is deliberately absent from this set: the bucket is this repository's
    own ``bucket/`` directory, so that push takes no repo variable and no PAT and
    consequently has nothing to refuse. Only the two genuinely external channels
    -- the Homebrew tap and the Claude marketplace -- can be unconfigured.
    """
    surface = _run_surface(_document()["jobs"]["publish"])
    assert "REFUSED: Homebrew tap not configured" in surface
    assert "REFUSED: Claude marketplace not configured" in surface
    assert "HOMEBREW_TAP_TOKEN" in surface
    assert "CLAUDE_MARKETPLACE_TOKEN" in surface
    # The channel credential names stay product-neutral so a sibling product
    # reuses the identical configuration.
    assert "CADRUMO_HOMEBREW_TAP_TOKEN" not in surface
    assert "CADRUMO_MARKETPLACE_TOKEN" not in surface
    assert "CADRUMO_SCOOP_BUCKET_REPO" not in surface


def _step_run(name_fragment: str) -> str:
    """Return the run body of the single publish step whose name contains the fragment."""
    steps = _document()["jobs"]["publish"]["steps"]
    matches = [
        str(step["run"])
        for step in steps
        if isinstance(step, Mapping) and "run" in step and name_fragment.lower() in str(step.get("name", "")).lower()
    ]
    assert len(matches) == 1, f"expected exactly one publish step matching {name_fragment!r}, got {len(matches)}"
    return matches[0]


def test_a_second_product_drops_into_each_shared_channel_as_one_more_file() -> None:
    """The acceptance test for the shared-channel design.

    The bucket and the tap are shared across every product published under the
    account, so a release of one product must stage only that product's own file.
    Each push is asserted to name its single product-scoped path and to carry
    none of the sweeping forms -- ``git add -A``, ``git add .``, or a wholesale
    delete of the checkout -- that would take a sibling product's file with it.
    A second product therefore lands as one more manifest and one more formula,
    with no restructuring of either channel.
    """
    bucket = _command_lines(_step_run("Scoop bucket manifest"))
    tap = _command_lines(_step_run("Homebrew formula"))

    assert "git -C \"$work\" add -- bucket/cadrumo.json" in bucket
    assert "git -C \"$work\" add -- Formula/cadrumo.rb" in tap

    for label, surface in (("bucket", bucket), ("tap", tap)):
        assert "add -A" not in surface, f"{label} push stages the whole tree; a sibling product's file would ride along"
        assert re.search(r"\bgit\b[^\n]*\badd\s+\.(?:\s|$)", surface) is None, f"{label} push stages the whole tree"
        # The wholesale-replace shape that the marketplace push used to carry.
        assert "-maxdepth 1" not in surface, f"{label} push deletes the checkout wholesale"


def test_the_marketplace_push_merges_rather_than_replacing_the_tree() -> None:
    """The shared marketplace is updated through the merge module, never a tree wipe.

    A wholesale replacement is correct only while exactly one product is served;
    against the account-scoped marketplace it deletes every sibling product's
    plugin. The push therefore delegates to the module that replaces only the
    cohort's own plugin subtrees and merges the index by plugin name.
    """
    marketplace = _command_lines(_step_run("marketplace"))
    assert "dev.packaging.marketplace_publish" in marketplace
    assert "-maxdepth 1" not in marketplace, "marketplace push still wipes the tracked tree wholesale"


def test_the_marketplace_push_retries_a_lost_race_and_fails_closed() -> None:
    """Concurrent publication into the shared marketplace is a designed-in condition.

    Several products releasing into one account marketplace can interleave clone
    and push, making the later push a non-fast-forward. GitHub concurrency
    groups are per-repository and cannot serialise across product repos, so the
    push re-clones and re-applies. Exhausting the retries must fail the release
    rather than report success on an unpublished marketplace.
    """
    marketplace = _command_lines(_step_run("marketplace"))
    assert "for attempt in" in marketplace, "the marketplace push does not retry a lost race"
    # The retry must re-clone inside the loop; re-pushing a stale checkout would
    # simply be rejected again.
    loop_body = marketplace.split("for attempt in", 1)[1]
    assert "clone" in loop_body, "the retry does not re-clone, so it would re-push the same stale tree"
    assert "REFUSED" in marketplace, "an exhausted retry must refuse rather than pass silently"


def test_the_scoop_bucket_is_this_repository_and_needs_no_channel_credentials() -> None:
    """Scoop reads a ``bucket/`` subdirectory, so no separate bucket repo is configured.

    This is what removes a repository per product rather than merely renaming one:
    the push targets ``github.repository`` with the job's own token, so a sibling
    product's workflow serves its own bucket with zero configuration.
    """
    bucket = _command_lines(_step_run("Scoop bucket manifest"))
    assert "${GITHUB_REPOSITORY}" in bucket
    assert "vars." not in bucket, "the Scoop push must not depend on a configured bucket repo variable"
    assert "SCOOP_BUCKET_REPO" not in bucket
    assert "SCOOP_BUCKET_TOKEN" not in bucket


def test_external_pushes_keep_the_token_out_of_the_persisted_remote() -> None:
    """Scoop/Homebrew/marketplace push via an -c http.extraheader, never a token-in-URL clone."""
    surface = _run_surface(_document()["jobs"]["publish"])
    # No clone embeds the token in the URL (it would persist in .git/config).
    assert "x-access-token:${GH_TOKEN}@" not in surface
    assert "x-access-token:${TAP_TOKEN}@" not in surface
    assert "x-access-token:${MARKETPLACE_TOKEN}@" not in surface
    # Each channel authenticates via a per-command HTTP header and scrubs its temp
    # dir right after the push.
    assert surface.count('http.extraheader="$auth"') >= 6  # clone + push per channel
    assert surface.count("printf 'x-access-token:%s'") == 3
    assert 'rm -rf "$work"' in surface
    # The refuse-when-empty guards survive for the two externally-hosted channels.
    assert "REFUSED: Homebrew tap not configured" in surface
    assert "REFUSED: Claude marketplace not configured" in surface


def test_leak_sweep_passes_a_non_empty_runner_token_set() -> None:
    """The publication leak-sweep feeds this runner's identity tokens, not an empty set."""
    surface = _run_surface(_document()["jobs"]["publish"])
    assert "evidence_release leak-sweep" in surface
    # Real identity tokens are collected and passed; an empty token would match
    # every byte, so only non-empty ones are forwarded.
    assert "$RUNNER_NAME" in surface
    assert "sweep_tokens+=(--token" in surface
    assert '"${sweep_tokens[@]}"' in surface
    # Both attach roots are still swept.
    assert '"$EVIDENCE_FINAL_DIR/attach"' in surface
    assert '"$RELEASE_COHORT_DIR"' in surface


def test_publish_uploads_the_stored_cohort_via_trusted_publishing() -> None:
    """The publish job promotes stored wheels via OIDC Trusted Publishing and a GH release."""
    surface = _run_surface(_document()["jobs"]["publish"])
    assert "uv publish --trusted-publishing always" in surface
    assert "gh release create" in surface
    # It re-downloads and re-verifies the stored cohort rather than rebuilding.
    assert "dev.packaging.evidence_release verify" in surface
    assert '--pattern "cadrumo-release-cohort.tar.gz"' in surface
    # D8: the published release also carries the verified rows and the three
    # per-lane manifests, so draft GC can never orphan a shipped audit trail.
    assert "evidence-manifest-$4.json" in surface
    assert '"$EVIDENCE_FINAL_DIR/attach"' in surface


def test_download_latest_payload_is_emitted_swept_and_attached() -> None:
    """The docs download-latest.json is a projection of the sealed cohort, swept then attached.

    It must (a) be projected from the SEALED cohort manifest (not rebuilt), (b)
    pass the same fail-closed leak-sweep every attached asset passes, and (c) be
    uploaded to the just-created release — after ``gh release create``, so the
    versioned asset URLs it carries are valid.
    """
    surface = _run_surface(_document()["jobs"]["publish"])
    assert "dev.docs.download_matrix emit-latest" in surface
    # Projected from the sealed cohort manifest, not a rebuild.
    assert '--cohort-manifest "$RELEASE_COHORT_DIR/release-cohort.json"' in surface
    # The payload is leak-swept before it is attached.
    assert surface.count("evidence_release leak-sweep") >= 2
    assert '--directory "$DOWNLOAD_LATEST_DIR"' in surface
    # Attached to the release that already exists (emit runs after the create).
    assert 'gh release upload "v$VERSION" "$DOWNLOAD_LATEST_DIR/download-latest.json"' in surface
    assert surface.index('gh release create "v$VERSION"') < surface.index("dev.docs.download_matrix emit-latest")


def test_github_release_refuses_colliding_asset_basenames() -> None:
    """Gh flattens assets to basename, so a collision guard runs before the release create."""
    surface = _run_surface(_document()["jobs"]["publish"])
    assert "uniq -d" in surface
    assert "colliding asset basenames" in surface
    # The hard guard precedes the actual release invocation, so a clobbered asset
    # cannot ship. Anchor on the versioned invocation, not the explanatory comment.
    assert surface.index("colliding asset basenames") < surface.index('gh release create "v$VERSION"')


def test_no_workflow_consumes_per_os_cohort_for_publication() -> None:
    """The retired stub is gone and the sole publication authority never pulls a per-OS cohort."""
    workflows = _REPO_ROOT / ".github" / "workflows"
    # publish.yml (the validate-only stub that downloaded the per-OS cohort and
    # carried that publication defect class) is retired outright.
    assert not (workflows / "publish.yml").exists()

    # The sole publication authority downloads ONLY the sealed cohort: no step in
    # any job names a per-OS smoke cohort artifact, via gh run download or the
    # download-artifact action.
    document = _document()
    for job_name, job in document["jobs"].items():
        steps = job["steps"] if isinstance(job.get("steps"), list) else []
        for step in steps:
            if not isinstance(step, Mapping):
                continue
            run = str(step.get("run", ""))
            assert "--name cadrumo-python-cohort" not in run, job_name
            uses = str(step.get("uses", ""))
            with_block = step.get("with", {})
            if "download-artifact" in uses and isinstance(with_block, Mapping):
                name = str(with_block.get("name", ""))
                assert not name.startswith("cadrumo-python-cohort"), job_name
