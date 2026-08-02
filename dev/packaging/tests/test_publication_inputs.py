"""Bind the publication dispatch's source demand to the claimed-channel set.

The property under test is a *coupling*, so the negative control matters more
than the positive case: it is easy to write a derivation that happens to agree
with today's descriptor while being insensitive to it. Each tightening test here
therefore mutates a channel's availability and asserts the demand moves with it.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Final

import pytest

from cadrumo.tests.env_scope import scoped_env_var
from dev.docs.download_matrix import Availability, DownloadDescriptor, claimed_channels, load_descriptor
from dev.packaging.publication_inputs import (
    COHORT_INPUT,
    EMIT_REAL_CLIENT_EVIDENCE_COMMAND,
    LANE_WORKFLOW_BY_CHANNEL,
    SOURCE_INPUT_BY_CHANNEL,
    _emit_outputs,
    acquisition_lane_workflows,
    acquisition_lanes,
    demanded_inputs,
    host_extension_precondition_refusal,
    lane_output_name,
    main,
    missing_sources,
    refusals,
    unmapped_acquisition_lanes,
    unmapped_claimed_channels,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_SCOOP: Final[str] = "scoop"
_HOMEBREW: Final[str] = "homebrew"


def _with_availability(
    descriptor: DownloadDescriptor,
    channel_id: str,
    availability: Availability,
) -> DownloadDescriptor:
    """Return ``descriptor`` with one channel's availability replaced."""
    channels = tuple(
        channel.model_copy(update={"availability": availability}) if channel.id == channel_id else channel
        for channel in descriptor.channel
    )
    return descriptor.model_copy(update={"channel": channels})


def test_every_channel_in_the_shipped_descriptor_has_a_known_evidence_source() -> None:
    """No channel can become claimed and find itself unsourced."""
    descriptor = load_descriptor()
    assert descriptor.channel, "the shipped descriptor declares no channels; every channel is trivially sourced"
    unsourced = sorted(c.id for c in descriptor.channel if c.id not in SOURCE_INPUT_BY_CHANNEL)
    assert not unsourced, (
        f"channel(s) {unsourced} have no entry in SOURCE_INPUT_BY_CHANNEL; flipping one to "
        "'available' would refuse the publication instead of demanding its evidence"
    )


def test_todays_descriptor_demands_only_the_cohort_because_only_python_is_claimed() -> None:
    """The registry floor is the whole claim, so it is the whole demand.

    This is the bootstrap case the fixed input list deadlocked on: the Scoop and
    Homebrew acquisition runs cannot succeed before a first publication writes
    the manifest and formula they install.
    """
    descriptor = load_descriptor()
    assert sorted(c.id for c in claimed_channels(descriptor)) == ["python"]
    assert demanded_inputs(descriptor) == (COHORT_INPUT,)
    assert missing_sources(descriptor, {COHORT_INPUT: "30216592706"}) == ()
    assert refusals(descriptor, {COHORT_INPUT: "30216592706"}) == ()


def test_the_cohort_input_is_demanded_even_though_it_is_not_channel_evidence() -> None:
    """It carries the published bytes, so its absence is always a refusal."""
    descriptor = load_descriptor()
    (line,) = refusals(descriptor, {COHORT_INPUT: "   "})
    assert COHORT_INPUT in line
    assert line.startswith("REFUSED:")


@pytest.mark.parametrize(
    ("channel_id", "expected_input"),
    [(_SCOOP, "scoop_run_id"), (_HOMEBREW, "homebrew_run_id")],
)
def test_claiming_a_channel_makes_its_source_mandatory(channel_id: str, expected_input: str) -> None:
    """The negative control: the demand must move when the claim moves.

    A derivation insensitive to availability would pass the assertion above and
    fail here, which is the whole point of asserting both.
    """
    descriptor = load_descriptor()
    assert expected_input not in demanded_inputs(descriptor)

    claimed = _with_availability(descriptor, channel_id, Availability.AVAILABLE)
    assert expected_input in demanded_inputs(claimed)

    # Dispatched without it, the publication now refuses and names the channel.
    (line,) = refusals(claimed, {COHORT_INPUT: "1"})
    assert expected_input in line
    assert channel_id in line


def test_one_source_can_prove_several_claimed_channels_and_is_demanded_once() -> None:
    """The two host-extension channels share one operator evidence release."""
    descriptor = load_descriptor()
    both = _with_availability(
        _with_availability(descriptor, "claude-plugin", Availability.AVAILABLE),
        "mcpb",
        Availability.AVAILABLE,
    )
    demanded = demanded_inputs(both)
    assert demanded.count("claude_evidence_release") == 1
    (line,) = refusals(both, {COHORT_INPUT: "1"})
    assert "claude-plugin" in line
    assert "mcpb" in line


def test_a_claimed_channel_with_no_known_source_refuses_rather_than_passing() -> None:
    """Fail-closed: an unsourced claim is a hole, never an absent requirement."""
    descriptor = load_descriptor()
    orphan = descriptor.channel[0].model_copy(
        update={
            "id": "unknown-channel",
            "availability": Availability.AVAILABLE,
            "artifact_kinds": (),
            "evidence_rows": ("unknown-row",),
        },
    )
    # model_copy bypasses validation by design; the descriptor's own validators
    # would reject the empty kinds tuple, and this test is about the derivation.
    widened = descriptor.model_copy(update={"channel": (*descriptor.channel, orphan)})
    assert unmapped_claimed_channels(widened) == ("unknown-channel",)
    assert any("unknown-channel" in line for line in refusals(widened, {COHORT_INPUT: "1"}))


def test_todays_descriptor_needs_no_acquisition_lane_because_only_python_is_claimed() -> None:
    """The bootstrap case restated for lanes: python's evidence rides the smoke run itself."""
    descriptor = load_descriptor()
    assert acquisition_lanes(descriptor) == ()


@pytest.mark.parametrize("channel_id", [_SCOOP, _HOMEBREW])
def test_claiming_scoop_or_homebrew_arms_its_acquisition_lane(channel_id: str) -> None:
    """The negative control: an unclaimed channel is never a lane, a claimed one always is."""
    descriptor = load_descriptor()
    assert channel_id not in acquisition_lanes(descriptor)

    claimed = _with_availability(descriptor, channel_id, Availability.AVAILABLE)
    assert channel_id in acquisition_lanes(claimed)


def test_claiming_scoop_and_homebrew_together_arms_both_lanes() -> None:
    descriptor = load_descriptor()
    both = _with_availability(
        _with_availability(descriptor, _SCOOP, Availability.AVAILABLE),
        _HOMEBREW,
        Availability.AVAILABLE,
    )
    assert acquisition_lanes(both) == (_HOMEBREW, _SCOOP)


def test_flipping_availability_back_to_public_launch_disarms_the_lane() -> None:
    """No workflow edit either way: the lane set tracks the claim, not a separate switch."""
    descriptor = load_descriptor()
    claimed = _with_availability(descriptor, _SCOOP, Availability.AVAILABLE)
    assert _SCOOP in acquisition_lanes(claimed)
    reverted = _with_availability(claimed, _SCOOP, Availability.PUBLIC_LAUNCH)
    assert _SCOOP not in acquisition_lanes(reverted)


def test_a_claimed_channel_absent_from_the_source_mapping_is_never_silently_a_lane() -> None:
    """Fail-closed composition: an unmapped claim must not pass unproven through this derivation either.

    ``acquisition_lanes`` excludes it (it cannot resolve a lane for a channel
    with no known evidence source at all), and the pre-existing
    ``unmapped_claimed_channels`` / ``refusals`` still catch it at the CLI
    boundary — so nothing about adding this derivation weakens that refusal.
    """
    descriptor = load_descriptor()
    orphan = descriptor.channel[0].model_copy(
        update={
            "id": "unknown-channel",
            "availability": Availability.AVAILABLE,
            "artifact_kinds": (),
            "evidence_rows": ("unknown-row",),
        },
    )
    widened = descriptor.model_copy(update={"channel": (*descriptor.channel, orphan)})
    assert "unknown-channel" not in acquisition_lanes(widened)
    assert unmapped_claimed_channels(widened) == ("unknown-channel",)
    assert any("unknown-channel" in line for line in refusals(widened, {COHORT_INPUT: "1"}))


def test_python_is_never_an_acquisition_lane_even_when_every_channel_is_claimed() -> None:
    """Python's evidence source is the cohort input itself; it must never be mistaken for a lane."""
    descriptor = load_descriptor()
    fully_claimed = descriptor
    for channel in descriptor.channel:
        fully_claimed = _with_availability(fully_claimed, channel.id, Availability.AVAILABLE)
    assert "python" not in acquisition_lanes(fully_claimed)


def test_unclaimed_host_extension_precondition_passes_regardless_of_evidence_release() -> None:
    """No host-extension channel claimed: the precondition holds even with an empty release tag."""
    descriptor = load_descriptor()
    assert host_extension_precondition_refusal(descriptor, claude_evidence_release="") is None
    assert host_extension_precondition_refusal(descriptor, claude_evidence_release="   ") is None


def test_claimed_and_supplied_host_extension_precondition_passes() -> None:
    descriptor = load_descriptor()
    claimed = _with_availability(descriptor, "claude-plugin", Availability.AVAILABLE)
    assert host_extension_precondition_refusal(claimed, claude_evidence_release="evidence-claude-123") is None


def test_claimed_and_absent_host_extension_precondition_refuses_naming_the_capture_command() -> None:
    descriptor = load_descriptor()
    claimed = _with_availability(descriptor, "claude-plugin", Availability.AVAILABLE)

    refusal = host_extension_precondition_refusal(claimed, claude_evidence_release="")

    assert refusal is not None
    assert refusal.startswith("REFUSED:")
    assert EMIT_REAL_CLIENT_EVIDENCE_COMMAND in refusal
    assert "claude-plugin" in refusal
    # Never a step this module performs itself.
    assert "capture them locally" in refusal


def test_host_extension_precondition_treats_whitespace_only_evidence_release_as_absent() -> None:
    """A blank/whitespace tag is not a supplied release; it must not satisfy the precondition."""
    descriptor = load_descriptor()
    claimed = _with_availability(descriptor, "mcpb", Availability.AVAILABLE)
    refusal = host_extension_precondition_refusal(claimed, claude_evidence_release="   ")
    assert refusal is not None
    assert "mcpb" in refusal


def test_host_extension_precondition_names_every_claimed_host_channel() -> None:
    descriptor = load_descriptor()
    both = _with_availability(
        _with_availability(descriptor, "claude-plugin", Availability.AVAILABLE),
        "mcpb",
        Availability.AVAILABLE,
    )
    refusal = host_extension_precondition_refusal(both, claude_evidence_release="")
    assert refusal is not None
    assert "claude-plugin" in refusal
    assert "mcpb" in refusal


def test_host_extension_precondition_never_fires_for_a_non_host_extension_claim() -> None:
    """Claiming scoop/homebrew must not trip the claude-specific precondition."""
    descriptor = load_descriptor()
    claimed = _with_availability(descriptor, "scoop", Availability.AVAILABLE)
    assert host_extension_precondition_refusal(claimed, claude_evidence_release="") is None


def test_every_mapped_lane_channel_resolves_to_an_existing_workflow_path_on_disk() -> None:
    for channel_id, workflow_path in LANE_WORKFLOW_BY_CHANNEL.items():
        resolved = _REPO_ROOT / workflow_path
        assert resolved.is_file(), f"{channel_id!r} maps to {workflow_path!r}, which does not exist on disk"


def test_the_claude_channels_carry_both_a_dispatchable_lane_and_a_human_evidence_precondition() -> None:
    """The two must never collapse into one input: the workflow proves the mechanism, the human proves use."""
    for channel_id in ("claude-plugin", "mcpb"):
        assert channel_id in LANE_WORKFLOW_BY_CHANNEL
        assert LANE_WORKFLOW_BY_CHANNEL[channel_id] == ".github/workflows/packaging-claude.yml"
        assert SOURCE_INPUT_BY_CHANNEL[channel_id] == "claude_evidence_release"


def test_todays_descriptor_needs_no_acquisition_lane_workflow() -> None:
    descriptor = load_descriptor()
    assert acquisition_lane_workflows(descriptor) == ()
    assert unmapped_acquisition_lanes(descriptor) == ()


def test_claiming_scoop_and_homebrew_resolves_to_their_distinct_workflows() -> None:
    descriptor = load_descriptor()
    both = _with_availability(
        _with_availability(descriptor, _SCOOP, Availability.AVAILABLE),
        _HOMEBREW,
        Availability.AVAILABLE,
    )
    assert acquisition_lane_workflows(both) == (
        ".github/workflows/packaging-homebrew.yml",
        ".github/workflows/packaging-scoop.yml",
    )


def test_claiming_both_claude_channels_dedupes_to_one_workflow() -> None:
    """claude-plugin and mcpb are two channels but one acquisition run."""
    descriptor = load_descriptor()
    both = _with_availability(
        _with_availability(descriptor, "claude-plugin", Availability.AVAILABLE),
        "mcpb",
        Availability.AVAILABLE,
    )
    assert acquisition_lane_workflows(both) == (".github/workflows/packaging-claude.yml",)


def test_every_source_mapped_non_cohort_channel_has_a_declared_lane_workflow() -> None:
    """Structural completeness: nothing ``acquisition_lanes()`` could ever return lacks a workflow.

    ``acquisition_lanes()`` can only return a channel id present in
    ``SOURCE_INPUT_BY_CHANNEL`` with a non-cohort source, so this is the exact
    universe ``LANE_WORKFLOW_BY_CHANNEL`` must cover for
    ``unmapped_acquisition_lanes()`` to stay permanently empty. A future channel
    added to ``SOURCE_INPUT_BY_CHANNEL`` without a matching lane workflow fails
    this test immediately, rather than surfacing as a silent orchestration gap.
    """
    potential_lane_channels = {
        channel_id for channel_id, source in SOURCE_INPUT_BY_CHANNEL.items() if source != COHORT_INPUT
    }
    missing = potential_lane_channels - set(LANE_WORKFLOW_BY_CHANNEL)
    assert not missing, f"channel(s) {sorted(missing)} could appear in acquisition_lanes() but have no workflow"


def test_unmapped_acquisition_lanes_stays_empty_even_when_every_channel_is_claimed() -> None:
    """Dynamic confirmation of the structural completeness above, over the real descriptor."""
    descriptor = load_descriptor()
    fully_claimed = descriptor
    for channel in descriptor.channel:
        fully_claimed = _with_availability(fully_claimed, channel.id, Availability.AVAILABLE)
    assert unmapped_acquisition_lanes(fully_claimed) == ()


def test_emitted_outputs_cover_every_known_input_in_both_states(tmp_path: Path) -> None:
    """The workflow guards on these booleans, so every input needs one."""
    output = tmp_path / "github_output"
    output.touch()
    _emit_outputs(load_descriptor(), output)
    emitted = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines() if line)
    assert emitted == {
        "need_packaging_run_id": "true",
        "need_scoop_run_id": "false",
        "need_homebrew_run_id": "false",
        "need_claude_evidence_release": "false",
    }


@contextmanager
def _workflow_inputs(*, absent: Iterable[str], present: dict[str, str] | None = None) -> Iterator[None]:
    """Pin the workflow's GitHub Actions input slots for the with-block.

    ``main`` reads its inputs from ``os.environ`` under the upper-cased input
    names, so a test that asserts a refusal has to prove the slot is genuinely
    ABSENT rather than merely unset in this process's own view — an ambient
    value left by a CI runner would otherwise satisfy the demand and turn the
    refusal case green for the wrong reason.

    Routed through :func:`~cadrumo.tests.env_scope.scoped_env_var`, the
    project's single authoritative os.environ scope, rather than a local
    save/restore or pytest's monkeypatch fixture.
    """
    with ExitStack() as stack:
        for name in sorted(absent):
            stack.enter_context(scoped_env_var(name.upper(), None))
        for name, value in sorted((present or {}).items()):
            stack.enter_context(scoped_env_var(name.upper(), value))
        yield


def test_main_refuses_an_empty_cohort_input_and_emits_nothing(tmp_path: Path) -> None:
    """The CLI the workflow calls must exit non-zero before writing outputs."""
    output = tmp_path / "github_output"
    output.touch()
    with _workflow_inputs(absent={*SOURCE_INPUT_BY_CHANNEL.values(), COHORT_INPUT}):
        assert main(["--github-output", str(output)]) == 1
    assert output.read_text(encoding="utf-8") == ""


def test_main_accepts_a_registry_only_dispatch(tmp_path: Path) -> None:
    """The bootstrap dispatch: cohort only, no acquisition runs to point at."""
    output = tmp_path / "github_output"
    output.touch()
    with _workflow_inputs(
        absent=SOURCE_INPUT_BY_CHANNEL.values(),
        present={COHORT_INPUT: "30216592706"},
    ):
        assert main(["--github-output", str(output)]) == 0
    assert "need_scoop_run_id=false" in output.read_text(encoding="utf-8")


def test_a_claimed_claude_plugin_channel_keeps_its_lane_and_its_evidence_release_separate() -> None:
    """The dispatchable lane and the human capture are two facts, never one.

    A claimed `claude-plugin` channel demands BOTH: `packaging-claude.yml`
    proves the plugin and MCPB install works, and an operator-minted evidence
    release holds the four real-client rows proving a human actually ran it.
    The publication authority consumes the second as a release tag.

    Collapsing them fails the publication at its final leg after a full soak
    and silently replaces operator-minted evidence with a machine-produced
    value.
    """
    claimed = _with_availability(load_descriptor(), "claude-plugin", Availability.AVAILABLE)

    # The lane is dispatched...
    assert ".github/workflows/packaging-claude.yml" in acquisition_lane_workflows(claimed)
    # ...and its run id has its own output name, distinct from the evidence input.
    assert lane_output_name(".github/workflows/packaging-claude.yml") == "claude_plugin_run_id"
    assert lane_output_name(".github/workflows/packaging-claude.yml") != SOURCE_INPUT_BY_CHANNEL["claude-plugin"]

    # ...while the evidence release remains a SEPARATE demanded input, and its
    # absence still refuses the whole chain rather than being satisfied by the
    # lane having run.
    assert SOURCE_INPUT_BY_CHANNEL["claude-plugin"] == "claude_evidence_release"
    refusal = host_extension_precondition_refusal(claimed, claude_evidence_release="")
    assert refusal is not None
    assert "emit_real_client_evidence" in refusal

    # A supplied evidence release satisfies it; a lane run id is not what this
    # input means, and nothing here derives one from the other.
    assert host_extension_precondition_refusal(claimed, claude_evidence_release="claude-evidence-2026-08-02") is None
