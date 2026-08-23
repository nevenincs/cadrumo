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
from typing import Any, Final

import pytest
import yaml

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = REPO_ROOT
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
# `;`, `&`, `|`, or `$(` -- because workflow prose quotes publish verbs such as
# `gh release create` inside comments and echoed instructions. An unanchored scan
# flags that documentation and reds the gate on a false positive. (The original
# instance was the retired operator-preflight refusal heredoc; the anchoring
# outlives it, because the hazard is prose quoting a verb, not that one job.)
# A backtick is
# deliberately NOT treated as a command position for the same reason: the only
# three backticks in the workflow are documentation prose, and it uses `$( )`
# rather than legacy backtick substitution for real command expansion.
#
# SCOPE BOUNDARY, for anyone widening this scan beyond `publish-release.yml`:
# the three packaging workflows (smoke, scoop, homebrew) each call
# `gh release create` once, and every one of those is machine EVIDENCE TRANSPORT,
# not publication -- it mints a per-run draft carrying rows, cohorts, and sealed
# manifests, and never a release. They are benign and must be pinned as such
# rather than silencing the pattern, which would re-open the hole this gate
# closes. The discriminators are `--draft` together with an `evidence-*` tag
# prefix and an "EVIDENCE (non-release)" title; a real publication carries a
# `v$VERSION` tag and no `--draft`. Widen by exempting on that evidence shape,
# never by loosening the verb patterns below.
# A shell keyword introduces a command position too: `if git ... push; then` runs
# git exactly as surely as a bare `git ... push` does. Without the keyword prefix
# below, wrapping an egress in `if`/`else`/`do` would hide it from this scan --
# a real hole, since the retry loops that make a SHARED distribution repository
# safe put every channel push behind exactly that `if`.
_COMMAND_POSITION: Final[str] = r"(?:^|[;&|]|\$\()[ \t]*(?:(?:if|then|elif|else|do|while|until|!)[ \t]+)*"

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
    # The Scoop bucket and Homebrew tap publish by pushing
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


def _collapse_spaces(text: str) -> str:
    """Collapse runs of spaces/tabs so assertions bind substance, not alignment."""
    return re.sub(r"[ \t]+", " ", text)


def _run_surface(job: Mapping[str, object]) -> str:
    steps = job["steps"]
    assert isinstance(steps, list)
    return "\n".join(str(step.get("run", "")) for step in steps if isinstance(step, Mapping) and "run" in step)


# A job "reads a protection rule" when it queries the environments API for the
# rule set. Anchored on the API path together with the rule vocabulary so that
# an unrelated environments read (there is none today, but a variables read
# would use the same prefix) is not mistaken for a re-introduced approval gate.
_PROTECTION_RULE_READ: Final[re.Pattern[str]] = re.compile(
    r"environments/[^\s\"']+.*?(?:protection_rules|required_reviewers)|(?:protection_rules|required_reviewers).*?environments/",
    re.IGNORECASE | re.DOTALL,
)

# A job "conditions on a protection rule" when its `if:` expression consults
# reviewer/approval state. This is the second half of the same property: a job
# could consume a protection-rule fact another job emitted as an output.
_PROTECTION_RULE_CONDITION: Final[re.Pattern[str]] = re.compile(
    r"required_reviewers|protection_rules|approval",
    re.IGNORECASE,
)


def _protection_rule_readers(document: Any) -> set[str]:
    """Return every job whose run surface reads an environment protection rule."""
    jobs = document.get("jobs", {})
    return {
        name
        for name, job in jobs.items()
        if isinstance(job, Mapping) and _PROTECTION_RULE_READ.search(_command_lines(_run_surface(job)))
    }


# Vocabulary that names a human approval gate, and the negation vocabulary that
# turns a mention of it into a statement of its ABSENCE. The pairing is the
# whole point: this header must be free to say "there is no approval click".
_HUMAN_GATE_TOKENS: Final[tuple[str, ...]] = (
    "approval click",
    "approval gate",
    "required-reviewers",
    "required_reviewers",
    "opts in",
    "opt-in",
    "human release gate",
)
_NEGATION_TOKENS: Final[tuple[str, ...]] = ("no ", "not ", "never", "removed", "without", "absence", "nobody")


def _workflow_header() -> str:
    """Return the workflow's leading comment block, lowercased."""
    lines: list[str] = []
    for line in _WORKFLOW.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        lines.append(line.lstrip("# ").strip())
    return "\n".join(lines).lower()


def _sentences_affirming_a_human_gate(text: str) -> list[str]:
    """Return each sentence naming a human gate WITHOUT negating it.

    Scoping to the sentence is what lets the header state the truthful
    negation. A bare substring ban cannot tell "the approval click is the gate"
    from "there is no approval click", and banning the vocabulary outright
    would push the header into silence about the change it exists to explain.
    """
    sentences = re.split(r"(?<=[.;:])\s+|\n", text.lower())
    return [
        sentence.strip()
        for sentence in sentences
        if any(token in sentence for token in _HUMAN_GATE_TOKENS)
        and not any(negation in sentence for negation in _NEGATION_TOKENS)
    ]


def _protection_rule_conditioned_jobs(document: Any) -> set[str]:
    """Return every job whose `if:` expression consults human-approval state."""
    jobs = document.get("jobs", {})
    return {
        name
        for name, job in jobs.items()
        if isinstance(job, Mapping) and _PROTECTION_RULE_CONDITION.search(str(job.get("if", "")))
    }


def test_workflow_shape_and_least_privilege_top_level() -> None:
    """One run-bound input, least-privilege top-level perms, the three staged jobs."""
    document = _document()
    dispatch = document[True]["workflow_dispatch"]
    assert set(dispatch["inputs"]) == {
        "packaging_run_id",
        "scoop_run_id",
        "homebrew_run_id",
        "dry_run",
    }
    assert document["permissions"] == {"contents": "read"}
    # Two staged jobs since the approval gate's removal (the retired
    # `operator-preflight` job existed only to enforce it), plus the
    # failure-only alert job that pays for that removal by guaranteeing
    # somebody is told when a publication fails.
    assert set(document["jobs"]) == {"validate", "publish", "alert"}


def test_publication_declares_no_tag_trigger_the_dispatch_path_would_mask() -> None:
    """Publication is dispatched explicitly; a declared tag trigger would be dead weight.

    A tag created by a workflow's own token does NOT fire tag-triggered workflows,
    so a release-please style tag push could never start this publication. A
    declared ``push.tags`` filter would therefore be inert while reading, to any
    maintainer, as a second and automatic way to publish — the most dangerous
    kind of dead configuration on the one workflow that uploads to public
    channels.

    Cadrumo has never carried such a trigger; this gate is what keeps it that
    way, and it is the property the sibling products' migration instructions ask
    them to reach.
    """
    document = _document()
    on = document[True]
    assert set(on) == {"workflow_dispatch"}, f"publication must be dispatch-only, found triggers: {sorted(on)}"
    assert "tags" not in str(on), "a tag filter on the publication authority is inert and misleading"


def test_dry_run_validates_everything_and_skips_publish() -> None:
    """A dry_run dispatch runs Gate 1+2 fully but gates the publish job off."""
    document = _document()
    dry_run = document[True]["workflow_dispatch"]["inputs"]["dry_run"]
    assert dry_run["type"] == "boolean"
    assert dry_run["default"] is False
    assert dry_run["required"] is False
    # Only the publish job is conditioned on dry_run; validate always runs so
    # the validate-everything-publish-nothing mode is real.
    publish = document["jobs"]["publish"]
    assert publish["if"] == "${{ inputs.dry_run != true }}"
    assert "if" not in document["jobs"]["validate"]


def test_oidc_and_write_are_confined_to_the_protected_publish_job() -> None:
    """id-token/contents:write live only on the environment-protected publish job.

    Asserted as EQUALITY rather than membership, because the property is a
    ceiling: a job holding OIDC and contents-write must hold nothing else that
    was not argued for. ``actions: read`` is in the expected set deliberately —
    the artifact-return transport pulls the producing runs' artifacts with
    ``gh run download``, which the releases-API transport it replaced did not
    need, so the scope grew by one read permission as a consequence of that
    accepted decision rather than by drift.
    """
    document = _document()
    publish = document["jobs"]["publish"]
    assert publish["environment"] == "release"
    assert publish["permissions"] == {"id-token": "write", "contents": "write", "actions": "read"}
    assert publish["needs"] == "validate"

    for name in ("validate",):
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
    assert "--emit-version-only" in surface
    # The partial guard is gone, not merely bypassed: asking a narrower version
    # of the same question in a second place is how the tag and release
    # namespaces went unchecked while the index check passed.
    assert "--check-pypi-only" not in surface
    # And the authority that asks EVERY destination runs before any write.
    assert "dev.release.version_identity" in surface
    assert surface.index("dev.release.version_identity") > surface.index("--emit-version-only")
    # Every channel's rows arrive from a run whose identity was pinned first.
    # This replaced the sealed-manifest verify verb rather than dropping the
    # check: an artifact cannot be attached to a run that did not produce it,
    # so asserting the run's workflow path and conclusion against the Actions
    # API IS the binding the manifest used to reconstruct.
    assert r'"\(.path)|\(.conclusion)"' in surface
    assert 'if [ "$identity" != "$2|success" ]; then' in surface
    # No publish verb in the read-only validate gate.
    assert "uv publish" not in surface
    assert "gh release create" not in surface


def test_validate_aggregates_base_channel_rows_from_authoritative_sources() -> None:
    """Gate 2 pulls every channel's rows from its own run, no weakening.

    Gate 2 aggregates the packaging smoke, Scoop, and Homebrew partitions.
    How many rows BLOCK is derived from the
    claimed channels by the readiness gate, which this job still runs.

    Matching is whitespace-normalised: the property is that each tag is derived
    from its own run-id input, not the column the continuation happens to sit in.
    """
    validate = _document()["jobs"]["validate"]
    surface = _collapse_spaces(_run_surface(validate))

    # Each channel's rows come from its OWN run, and the run id is PAIRED at
    # the call site with the workflow path that run is required to have. The
    # pairing is the property: both tokens appearing somewhere in the surface
    # would also hold if the ids were crossed, which is the failure this
    # aggregation exists to prevent.
    for run_id, workflow in (
        ("$PACKAGING_RUN_ID", ".github/workflows/packaging-smoke.yml"),
        ("$SCOOP_RUN_ID", ".github/workflows/packaging-scoop.yml"),
        ("$HOMEBREW_RUN_ID", ".github/workflows/packaging-homebrew.yml"),
    ):
        paired = re.compile(rf'verify "{re.escape(run_id)}"\s*\\?\s*"{re.escape(workflow)}"')
        assert paired.search(surface), f"{run_id} must be verified against {workflow} at the same call site"
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


def test_no_job_gates_the_publication_on_a_human_protection_rule() -> None:
    """The human approval gate is ABSENT, and its absence is the asserted property.

    This gate is the inverse of the one it replaces. Three accepted 2026-07-27
    records and this test previously asserted that the publication refused
    unless the `release` environment carried a `required_reviewers` rule. That
    choice was reversed: the pipeline is fully automated, the mechanical guard
    set is the whole safety net, and the operator removed the protection rule
    from the forge.

    A removal that is merely performed reads, to the next honesty pass, as
    something that went missing -- so it is pinned here. Without this test an
    agent reading those three records would "restore" the gate and silently
    re-block every release.

    What is NOT asserted: that no human ever approves anything. `environment:
    release` stays on the publish job and is checked below, because it is the
    Trusted Publishing trust anchor and the shared-runner product boundary, not
    merely the click's former host. Deleting the environment breaks OIDC
    publication outright.
    """
    document = _document()

    offenders = _protection_rule_readers(document)
    assert not offenders, (
        f"jobs reading an environment protection rule: {sorted(offenders)}. "
        "The human approval gate was deliberately removed; a job that reads "
        "protection rules is re-introducing it."
    )

    conditioned = _protection_rule_conditioned_jobs(document)
    assert not conditioned, (
        f"jobs conditioned on a human protection rule: {sorted(conditioned)}. "
        "Publication proceeds on the mechanical guard set alone."
    )

    # The retired job is gone in full, not neutralised into a warning: a live
    # job asserting a gate that no longer exists is the documented-but-
    # unenforced shape the original job was built to close.
    assert "operator-preflight" not in document["jobs"]

    # The environment survives, and with it the OIDC trust anchor.
    assert document["jobs"]["publish"]["environment"] == "release"


def test_the_header_describes_the_gate_that_actually_runs() -> None:
    """The workflow's own prose may not promise a gate the workflow does not run.

    This is the drift class the retired job was itself built to close, one layer
    up. Before the automation change the header claimed the run was "inert until
    the operator opts in" via a `CADRUMO_PUBLISH_ENABLED` variable that had
    already been deleted from the entire tree, and described an approval click
    as the gate. Prose that describes a safety property the code does not have
    is worse than no prose: it is what stops the next reader from checking.
    """
    header = _workflow_header()

    # The variable is gone from the entire tree, so any mention is stale by
    # construction and needs no sentence analysis.
    assert "cadrumo_publish_enabled" not in header

    # Every other check is sentence-scoped rather than a vocabulary ban,
    # because the CLEAREST statement this header can make is the negation
    # ("there is no approval click"), and a substring ban would forbid exactly
    # the sentence the reader most needs while permitting a paraphrase that
    # affirms the gate. The property is not "these words are absent"; it is
    # "this header does not CLAIM a human gates the run".
    affirming = _sentences_affirming_a_human_gate(header)
    assert not affirming, f"header sentences claiming a human gate: {affirming}"

    # It must describe what DOES gate the run, so the reader is left with the
    # real answer rather than merely the absence of a wrong one.
    for guard in ("version-identity", "sha256", "leak sweep", "evidence"):
        assert guard in header, f"the header does not name the {guard} guard that actually gates the run"

    # And it must say why the environment is still here, since that is the one
    # piece a naive "remove the gate" sweep would delete and break publication.
    assert "trusted publishing" in header


def test_the_header_pin_reds_on_a_restored_gate_claim() -> None:
    """Positive control for the sentence-scoped matcher.

    Without this, a matcher that never fires and a header that never lies are
    indistinguishable - and the negation-awareness that makes the matcher
    usable is also what could make it silently permissive.
    """
    restored = "it is inert until the operator opts in, and the approval click is the gate."
    assert _sentences_affirming_a_human_gate(restored)

    # The honest negation must NOT trip it, or the gate would force the header
    # to go quiet about the very change it is documenting.
    honest = "there is no approval click and no opt-in variable; both were removed."
    assert not _sentences_affirming_a_human_gate(honest)

    # A sentence that merely explains why the environment survives is not a
    # gate claim either.
    survives = "environment: release remains for its trusted publishing anchor, not for an approval rule."
    assert not _sentences_affirming_a_human_gate(survives)


def test_the_protection_rule_pin_reds_on_a_planted_reader() -> None:
    """Positive control: the absence pin above is not vacuous.

    An assertion that nothing matches passes just as happily when the matcher
    is broken as when the tree is clean, so the pin is worthless until a
    planted violation is shown to trip it. Both halves are planted, because
    both halves are load-bearing and either could rot independently.
    """
    reading = {
        "jobs": {
            "sneaky": {
                "steps": [
                    {"run": 'gh api "repos/${GITHUB_REPOSITORY}/environments/release" --jq .protection_rules'},
                ],
            },
        },
    }
    assert _protection_rule_readers(reading) == {"sneaky"}

    conditioned = {"jobs": {"sneaky": {"if": "${{ needs.check.outputs.required_reviewers == 'true' }}", "steps": []}}}
    assert _protection_rule_conditioned_jobs(conditioned) == {"sneaky"}

    # And the clean shape trips neither, so the matchers are not simply
    # returning every job they are handed.
    clean = {"jobs": {"publish": {"if": "${{ inputs.dry_run != true }}", "steps": [{"run": "uv publish"}]}}}
    assert _protection_rule_readers(clean) == set()
    assert _protection_rule_conditioned_jobs(clean) == set()


def test_acquisition_inputs_are_optional_at_the_form_and_derived_at_the_gate() -> None:
    """The bootstrap deadlock stays closed without loosening a single guarantee.

    A Scoop or Homebrew acquisition run installs the manifest or formula out of
    the shared repository, so it cannot succeed before a first publication writes
    that pointer -- and the first publication could not be dispatched without it.
    The inputs are therefore optional AT THE FORM; whether each is actually
    required is derived at Gate 2 from the channels the release claims, the same
    authority the readiness gate derives its blocking rows from.

    The paired assertions are the control: optional-at-the-form is only safe
    BECAUSE the derivation step runs, so this test fails if either half is
    dropped.
    """
    document = _document()
    inputs = document[True]["workflow_dispatch"]["inputs"]
    for name in ("scoop_run_id", "homebrew_run_id"):
        assert inputs[name]["required"] is False, f"{name} must not deadlock the first publication"
        assert inputs[name]["default"] == "", f"{name} must default empty, not to a fabricated id"
    # The cohort itself is never optional: it carries the published bytes.
    assert inputs["packaging_run_id"]["required"] is True

    surface = _run_surface(document["jobs"]["validate"])
    assert "dev.packaging.publication_inputs" in surface, (
        "optional inputs are only safe because Gate 2 derives which are mandatory; "
        "without this step a claimed channel could be published unproven"
    )
    # The derivation must run BEFORE the aggregation it authorises. Anchored on
    # the identity-pinning helper the aggregation is built around, which is what
    # the retired sealed-manifest verify verb was replaced by.
    assert surface.index("dev.packaging.publication_inputs") < surface.index("verify() {")
    # And the readiness gate still runs, so the row set is enforced regardless.
    assert "dev.release.readiness" in surface


#: The dispatch inputs Gate 2 demands only when a channel claims them.
_DERIVED_INPUTS: Final[tuple[str, ...]] = ("scoop_run_id", "homebrew_run_id")

#: Words that make a mention of a derived input conditional rather than flat.
_CONDITIONAL_MARKERS: Final[tuple[str, ...]] = ("claim", "only", "empty", "deriv")


def _unconditional_input_mentions(prose: str) -> list[str]:
    """Return refusal lines that name a derived input with no conditional marker.

    The operator never sees the derivation run; they see this refusal. So an
    instruction naming one of these inputs flatly -- "re-dispatch with
    scoop_run_id" -- walks the operator straight back into the bootstrap
    deadlock the derivation exists to break, however correct the gate is.
    """
    flagged: list[str] = []
    in_fence = False
    for line in prose.splitlines():
        if line.lstrip().startswith("```"):
            # A fenced block is a syntax example, not an instruction. The full
            # four-input dispatch has to be SHOWN somewhere, and every one of its
            # `-f` lines names a derived input by construction; flagging those
            # would make the runbook unable to document its own command. The
            # conditional belongs in the prose that introduces the block, which
            # is still scanned, and the explicit "deriv" assertion below stops
            # this exemption from being satisfied by an empty explanation.
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if any(name in line.lower() for name in _DERIVED_INPUTS) and not any(
            marker in line.lower() for marker in _CONDITIONAL_MARKERS
        ):
            flagged.append(line.strip())
    return flagged


def test_operator_instructions_never_present_a_derived_input_as_unconditional() -> None:
    """The prose the operator reads must agree with the gate that refuses them.

    This used to read the workflow's opt-in refusal. That refusal is gone with
    the opt-in variable, so the runbook is now the only place an operator learns
    which inputs a dispatch needs, and it is what this checks.
    """
    prose = (_REPO_ROOT / "RELEASING.md").read_text(encoding="utf-8")

    assert not _unconditional_input_mentions(prose), (
        "the runbook instructs the operator to supply an input that Gate 2 "
        "demands only for a claimed channel; that is the bootstrap deadlock as prose"
    )
    # Vacuously satisfiable by deleting the explanation, so require it explicitly.
    assert re.search(r"deriv", prose, re.IGNORECASE), (
        "the refusal must tell the operator that the acquisition inputs are derived "
        "from the claimed channels, or the empty-input dispatch looks like an omission"
    )


@pytest.mark.parametrize(
    "offending",
    [
        pytest.param(
            "re-dispatch with the packaging_run_id, scoop_run_id, and homebrew_run_id inputs.",
            id="the-deadlocked-instruction-this-gate-retired",
        ),
        pytest.param("5. Note the scoop_run_id and homebrew_run_id.", id="flat-numbered-prerequisite"),
    ],
)
def test_the_instruction_predicate_flags_every_unconditional_shape(offending: str) -> None:
    """Negative control: the property is not vacuous on today's prose."""
    assert _unconditional_input_mentions(offending)


@pytest.mark.parametrize(
    "benign",
    [
        pytest.param("scoop_run_id is required once the scoop channel is claimed.", id="claim-scoped"),
        pytest.param("Leave homebrew_run_id empty on a bootstrap dispatch.", id="empty-scoped"),
        pytest.param("Gate 2 derives whether scoop_run_id is needed.", id="derivation-scoped"),
    ],
)
def test_the_instruction_predicate_leaves_conditional_prose_alone(benign: str) -> None:
    """It must not force the prose to stop naming the inputs at all."""
    assert not _unconditional_input_mentions(benign)


def test_absent_optional_sources_are_skipped_not_fabricated() -> None:
    """Both jobs guard each optional aggregation on a non-empty id.

    An unguarded ``verify "evidence-scoop-"`` would resolve to a nonexistent tag
    and fail the publication for a channel the release does not even claim.
    """
    document = _document()
    for job_name in ("validate", "publish"):
        surface = _collapse_spaces(_run_surface(document["jobs"][job_name]))
        for variable in ("SCOOP_RUN_ID", "HOMEBREW_RUN_ID"):
            assert f'if [ -n "${variable}" ]; then' in surface, (
                f"{job_name} consumes ${variable} without a presence guard"
            )


def test_workflow_row_prose_names_only_base_channels() -> None:
    """Both Gate-2/Gate-3 comments describe the base-channel evidence set.

    The workflow AGGREGATES every row the channels can produce -- that count is
    the full set, not the claimed subset -- and the readiness gate then requires
    the rows the claimed channels own. Anchoring this prose on the required set
    would make it drift every time a channel flips to available.
    """
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "claude" not in text.lower()
    assert "marketplace" not in text.lower()


def test_required_rows_derive_from_claimed_channels_and_never_collapse_to_nothing() -> None:
    """Evidence is proportional to claims, and the registry floor keeps it non-vacuous.

    The required set is a subset of the full set (an unclaimed channel does not
    block a claimed one) and always contains the language-native registry rows
    (the floor of the account standard). Without the floor a descriptor with no
    channel marked available would require nothing, and the readiness gate would
    pass while measuring nothing at all.
    """
    from ...docs.download_matrix import ChannelTier, load_descriptor
    from ..readiness import ALL_DISTRIBUTION_ROWS, REQUIRED_DISTRIBUTION_ROWS

    assert frozenset(REQUIRED_DISTRIBUTION_ROWS) <= frozenset(ALL_DISTRIBUTION_ROWS)
    registry_rows = frozenset(
        row
        for channel in load_descriptor().channel
        if channel.tier is ChannelTier.REGISTRY
        for row in channel.evidence_rows
    )
    assert registry_rows
    assert registry_rows <= frozenset(REQUIRED_DISTRIBUTION_ROWS), (
        "the language-native registry is the floor of the account standard and must always be required"
    )


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
    # Every wheel/sdist is uploaded from RELEASE_COHORT_DIR/python.
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
        # An egress wrapped in a shell keyword still runs. The retry loops that
        # make the shared distribution repository safe use exactly these shapes,
        # so the scan must see through them.
        'if git -C "$work" -c http.extraheader="$auth" push; then',
        "else\n  git push origin main",
        "while ! git push; do :; done",
        "if uv publish --trusted-publishing always; then",
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
        # Documentation prose, not an invocation.
        "the lane uploads rows to a release (`gh release create <tag> --draft`);",
        # A whole-line comment naming a verb is not an invocation.
        "# gh release create flattens every asset to its basename",
        # Read-only channel reads and git operations that publish nothing.
        'gh release view "v$VERSION"',
        'gh release download "v$VERSION"',
        'git -c http.extraheader="$auth" clone "https://github.com/${TAP_REPO}.git" "$work"',
        'git -C "$work" add -- bucket/cadrumo.json',
        'git -C "$work" diff --cached --quiet',
        'echo "channel already at cadrumo $VERSION; nothing to push"',
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
    """Every externally-hosted channel fails closed with instructions when unconfigured.

    Both channels are externally hosted: the Scoop bucket and the
    Homebrew formula land in the shared account distribution repository. Neither can fall back
    to the workflow's own repository, so each must refuse instructively rather
    than publish somewhere unintended.
    """
    surface = _run_surface(_document()["jobs"]["publish"])
    assert "REFUSED: shared distribution repository not configured" in surface
    assert "REFUSED: Homebrew tap not configured" in surface
    assert "HOMEBREW_TAP_TOKEN" in surface
    # The channel credential names stay product-neutral so a sibling product
    # reuses the identical configuration.
    assert "CADRUMO_HOMEBREW_TAP_TOKEN" not in surface
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


def shared_repository_push_violations(surface: str, *, product_path: str) -> list[str]:
    """Return every reason ``surface`` would be unsafe against a SHARED repository.

    This is the acceptance predicate for the one-repository design, factored out
    of the tests so a negative control can drive the same code against a known-bad
    push. A push into a repository that also holds sibling products' files is safe
    only when it stages exactly its own product-scoped path and carries none of
    the sweeping forms that would take a sibling's file with it.
    """
    violations: list[str] = []
    if f"add -- {product_path}" not in surface:
        violations.append(f"does not stage its own product-scoped path {product_path!r}")
    if re.search(r"\bgit\b[^\n]*\badd\b[^\n]*(?:\s-A\b|\s--all\b)", surface):
        violations.append("stages the whole tree with `git add -A`; a sibling product's file would ride along")
    if re.search(r"\bgit\b[^\n]*\badd\s+\.(?:\s|$)", surface, re.MULTILINE):
        violations.append("stages the whole tree with `git add .`")
    if "-maxdepth 1" in surface:
        violations.append("deletes the checkout wholesale before writing")
    if re.search(r"\bgit\b[^\n]*\brm\b[^\n]*\s-r\b", surface):
        violations.append("removes tracked paths recursively; a sibling product's file would be deleted")
    # A push aimed at the product's own repository is not a shared-repository
    # push at all: it re-creates a per-product distribution surface, which is the
    # topology the account standard replaces.
    if "${GITHUB_REPOSITORY}" in surface:
        violations.append("targets the product's own repository instead of the shared account repository")
    return violations


def test_a_second_product_drops_into_each_shared_channel_as_one_more_file() -> None:
    """The acceptance test for the one-repository design.

    ONE shared account repository carries ``Formula/`` for Homebrew and
    ``bucket/`` for Scoop, so both pushes land in a repository that also holds
    every sibling product's files. A release of one product must therefore stage
    only that product's own file. A second product then drops in as one more
    formula file and one more manifest file, with ZERO restructuring -- which is
    the property the whole standard is chosen for.

    The negative control for this assertion lives in
    ``test_the_conformance_predicate_rejects_every_unsafe_push_shape``: without
    it, this test would pass just as happily against a workflow with no pushes at
    all.
    """
    for label, step, product_path in (
        ("bucket", "Scoop manifest", "bucket/cadrumo.json"),
        ("tap", "Homebrew formula", "Formula/cadrumo.rb"),
    ):
        surface = _command_lines(_step_run(step))
        violations = shared_repository_push_violations(surface, product_path=product_path)
        assert violations == [], f"the {label} push is unsafe in a shared repository: {violations}"


@pytest.mark.parametrize(
    ("label", "unsafe_surface"),
    [
        # The PRE-CHANGE Scoop push: it targeted the product's own repository,
        # which held the repository count down only by giving every product its
        # own bucket. This is the exact shape the shared-repository push was
        # redesigned to replace, and the predicate must reject it.
        (
            "pre-change in-repository bucket push",
            'git -c http.extraheader="$auth" clone --depth 1 "https://github.com/${GITHUB_REPOSITORY}.git" "$work"\n'
            'git -C "$work" add -- bucket/cadrumo.json',
        ),
        ("stages the whole tree with -A", 'git -C "$work" add -A'),
        ("stages the whole tree with --all", 'git -C "$work" add --all'),
        ("stages the whole tree with a dot", 'git -C "$work" add .'),
        (
            "wipes the checkout before writing",
            'find "$work" -maxdepth 1 ! -name .git -exec rm -rf {} +\ngit -C "$work" add -- bucket/cadrumo.json',
        ),
        (
            "removes tracked paths recursively",
            'git -C "$work" rm -r --cached bucket\ngit -C "$work" add -- bucket/cadrumo.json',
        ),
        ("stages nothing at all", 'git -C "$work" commit -m "cadrumo $VERSION"'),
    ],
)
def test_the_conformance_predicate_rejects_every_unsafe_push_shape(label: str, unsafe_surface: str) -> None:
    """Non-vacuity: the acceptance predicate really rejects each shape it claims to bar.

    A conformance test that passes vacuously proves nothing. Each case here is a
    push that would damage a sibling product's file in the shared repository --
    including the literal pre-change shape the redesign replaced -- and the
    predicate must return at least one violation for every one of them.
    """
    violations = shared_repository_push_violations(unsafe_surface, product_path="bucket/cadrumo.json")
    assert violations, f"the conformance predicate accepted an unsafe push: {label}"


def test_the_conformance_predicate_accepts_the_safe_shape() -> None:
    """Negative control the other way: the predicate is not simply always-failing.

    Paired with the rejection cases above, this pins the predicate as
    discriminating rather than vacuously strict -- a predicate that returned a
    violation for every input would satisfy the rejection tests alone.
    """
    safe = (
        'git -c http.extraheader="$auth" clone "https://github.com/${TAP_REPO}.git" "$work"\n'
        'cp "$RELEASE_COHORT_DIR/scoop/cadrumo.json" "$work/bucket/cadrumo.json"\n'
        'git -C "$work" add -- bucket/cadrumo.json\n'
        'git -C "$work" -c http.extraheader="$auth" push'
    )
    assert shared_repository_push_violations(safe, product_path="bucket/cadrumo.json") == []


def test_both_ecosystems_are_served_from_the_one_shared_repository() -> None:
    """Homebrew and Scoop resolve from the SAME account repository.

    This is what holds the account's distribution repository count at one. The
    ``homebrew-`` name prefix is mandatory for the one-argument tap form, so that
    repository must exist regardless; Scoop imposes no name constraint and scopes
    discovery to ``bucket/`` when present, so it rides along for free. Both
    pushes therefore read the same repository variable and the same token.
    """
    bucket = _command_lines(_step_run("Scoop manifest"))
    tap = _command_lines(_step_run("Homebrew formula"))
    for label, surface in (("bucket", bucket), ("tap", tap)):
        assert "${TAP_REPO}" in surface, f"the {label} push does not target the shared repository"
        assert "vars.HOMEBREW_TAP_REPO" in _WORKFLOW.read_text(encoding="utf-8")
        assert "SCOOP_BUCKET_REPO" not in surface, f"the {label} push reintroduces a per-product bucket repo variable"


def test_each_shared_repository_push_guards_against_a_backward_bump() -> None:
    """A committed release pointer may never move backward.

    Both files are release POINTERS a user's package manager resolves, so an
    ordinary merge that resurrects an older one silently un-publishes the current
    version with no workflow failing. The guard runs against the CLONED
    repository state, before the new pointer is copied over it -- checking after
    the copy would compare the file with itself.
    """
    for label, step, pointer, fmt in (
        ("bucket", "Scoop manifest", "bucket/cadrumo.json", "scoop"),
        ("tap", "Homebrew formula", "Formula/cadrumo.rb", "homebrew"),
    ):
        surface = _command_lines(_step_run(step))
        assert "dev.packaging.release_pointer_guard" in surface, f"the {label} push has no backward-bump guard"
        assert f"--format {fmt}" in surface
        assert f'--existing "$work/{pointer}"' in surface
        # The guard must read the CLONE, not the freshly-copied cohort file.
        guard_at = surface.index("release_pointer_guard")
        copy_at = surface.index('cp "$RELEASE_COHORT_DIR')
        assert guard_at < copy_at, f"the {label} guard runs after the copy, so it compares the file with itself"


def test_each_shared_repository_push_retries_a_lost_race_and_fails_closed() -> None:
    """Concurrent publication into the one shared repository is a designed-in condition.

    Several products releasing into one account repository can interleave clone
    and push, making the later push a non-fast-forward. GitHub concurrency groups
    are per-repository and cannot serialise across product repos, so each push
    re-clones and re-applies. Exhausting the retries must fail the release rather
    than report success on an unpublished channel.
    """
    for label, step in (("bucket", "Scoop manifest"), ("tap", "Homebrew formula")):
        surface = _command_lines(_step_run(step))
        assert "for attempt in" in surface, f"the {label} push does not retry a lost race"
        loop_body = surface.split("for attempt in", 1)[1]
        assert "clone" in loop_body, f"the {label} retry does not re-clone, so it would re-push a stale tree"
        assert "REFUSED" in surface, f"an exhausted {label} retry must refuse rather than pass silently"


def test_no_channel_push_writes_to_a_product_repository_default_branch() -> None:
    """No publication writes to any product repository's own default branch.

    The superseded in-repository-bucket topology served Scoop from the product's
    own repository, which held the repository count down only by giving every
    product its own bucket AND by committing to a public product repository's
    default branch at release time. Both costs are gone: every channel push now
    targets an account-scoped shared repository.
    """
    for step in ("Scoop manifest", "Homebrew formula"):
        surface = _command_lines(_step_run(step))
        assert "${GITHUB_REPOSITORY}" not in surface, (
            f"the {step!r} push writes to the product repository; channel pushes are account-scoped"
        )


def test_external_pushes_keep_the_token_out_of_the_persisted_remote() -> None:
    """Scoop/Homebrew push via an -c http.extraheader, never a token-in-URL clone."""
    surface = _run_surface(_document()["jobs"]["publish"])
    # No clone embeds the token in the URL (it would persist in .git/config).
    assert "x-access-token:${GH_TOKEN}@" not in surface
    assert "x-access-token:${TAP_TOKEN}@" not in surface
    # Each channel authenticates via a per-command HTTP header and scrubs its temp
    # dir right after the push.
    assert surface.count('http.extraheader="$auth"') >= 4  # clone + push per channel
    assert surface.count("printf 'x-access-token:%s'") == 2
    assert 'rm -rf "$work"' in surface
    # The refuse-when-empty guards survive for the two externally-hosted channels.
    assert "REFUSED: Homebrew tap not configured" in surface


def test_leak_sweep_passes_a_non_empty_runner_token_set() -> None:
    """The publication leak-sweep feeds this runner's identity tokens, not an empty set."""
    surface = _run_surface(_document()["jobs"]["publish"])
    assert "evidence_leak_sweep leak-sweep" in surface
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
    # The re-verification is the run-identity assertion, pinned here to the
    # smoke workflow literally rather than through a parameter, because the
    # cohort has exactly one producing lane.
    assert '!= ".github/workflows/packaging-smoke.yml|success" ]; then' in surface
    assert 'gh run download "$PACKAGING_RUN_ID" --name cadrumo-release-cohort' in surface
    # D8: the published release is self-evidencing — it carries the verified
    # rows themselves, so a shipped version's audit trail outlives the
    # producing runs' artifact retention. The per-lane manifest filenames that
    # used to be asserted here belonged to the sealed-draft transport and no
    # step emits them now; the surviving property is that the attach root is
    # filled from the identity-verified runs.
    assert '"$EVIDENCE_FINAL_DIR/attach"' in surface
    assert "verify_rows() {" in surface


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
    assert surface.count("evidence_leak_sweep leak-sweep") >= 2, (
        "the download-latest payload must pass the same fail-closed sweep the attach roots do"
    )
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


def test_the_irreversible_upload_runs_after_every_reversible_write() -> None:
    """Ordering is the invariant, and it is the one that was wrong.

    Every destination above the index upload is reversible: a release and its
    assets can be deleted, a tag removed, and the channel pushes are ordinary
    git commits that can be reverted. An index upload is permanent and burns the
    version the moment it lands.

    Running it first meant a failure in any later step stranded the index
    holding bytes that matched no release, with no way back -- which is exactly
    what a version collision produced. Ordered last, a failure before it unwinds
    completely, and a failure at it leaves every channel serving release assets,
    none of which depend on the index.
    """
    steps = _document()["jobs"]["publish"]["steps"]
    names = [str(step.get("name", "")) for step in steps]
    upload = next(index for index, name in enumerate(names) if "PyPI" in name)

    reversible = (
        "Create the GitHub release",
        "download-latest.json",
        "Scoop manifest",
        "Homebrew formula",
    )
    for fragment in reversible:
        position = next(index for index, name in enumerate(names) if fragment in name)
        assert position < upload, f"{fragment!r} is reversible and must run before the irreversible upload"
    assert upload == len(names) - 1, "the irreversible upload must be the final step, with nothing after it to fail"
