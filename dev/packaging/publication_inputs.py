"""Derive which acquisition-evidence sources a publication dispatch must carry.

The publication authority promotes a sealed cohort to every *claimed* channel,
and the readiness gate already derives its blocking evidence set from exactly
those claims (:func:`dev.docs.download_matrix.required_evidence_rows`). The
dispatch inputs that name where each channel's evidence comes from must follow
the same derivation, or the two disagree.

They did disagree, and the disagreement was a bootstrap deadlock. The workflow
hard-required a Scoop acquisition run id and a Homebrew acquisition run id on
every dispatch. Those acquisition runs install the published manifest and
formula out of the shared repository — so they cannot succeed until a first
publication has written that manifest and formula, and the first publication
could not be dispatched without them. A channel that no release claims was
being demanded as a precondition for releasing the channels it does claim.

This module makes the demand derived instead of fixed. An input is required
precisely when some claimed channel sources its evidence from it; a channel the
descriptor does not claim demands nothing. The guarantee is therefore strictly
stronger than the fixed list it replaces: it cannot drift out of step with the
readiness gate, and the moment a channel's ``availability`` flips to
``available`` its source becomes mandatory with no workflow edit at all.

Fail-closed in both directions. A claimed channel whose evidence has no known
source refuses rather than passing unproven, so adding a channel without
teaching this module where its evidence comes from cannot silently publish an
unevidenced channel.

See Also:
    :data:`SOURCE_INPUT_BY_CHANNEL`
        Where each channel's acquisition evidence comes from.
    :func:`missing_sources`
        The refusal this module exists to raise.
    :func:`dev.docs.download_matrix.claimed_channels`
        The single authority for what a release claims.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from .._paths import UTF_8
from ..docs.download_matrix import DownloadDescriptor, claimed_channels, load_descriptor

_UTF_8: Final[str] = UTF_8

#: Channel id -> the ``publish-release.yml`` dispatch input naming the run or
#: release that carries that channel's acquisition evidence. A claimed channel
#: absent from this mapping is a refusal,
#: never a pass — see :func:`unmapped_claimed_channels`.
SOURCE_INPUT_BY_CHANNEL: Final[Mapping[str, str]] = {
    "python": "packaging_run_id",
    "scoop": "scoop_run_id",
    "homebrew": "homebrew_run_id",
}

#: The input that carries the sealed cohort itself. It is unconditional: it is
#: the source of the published bytes for every channel, not evidence for one.
COHORT_INPUT: Final[str] = "packaging_run_id"

#: Claimed channel id -> the acquisition workflow the orchestrator dispatches
#: to prove that channel. Kept SEPARATE from :data:`SOURCE_INPUT_BY_CHANNEL`:
#: ``python`` carries no entry — its evidence rides the packaging-smoke run
#: itself, so it is never in :func:`acquisition_lanes`.
LANE_WORKFLOW_BY_CHANNEL: Final[Mapping[str, str]] = {
    "scoop": ".github/workflows/packaging-scoop.yml",
    "homebrew": ".github/workflows/packaging-homebrew.yml",
}


def acquisition_lanes(descriptor: DownloadDescriptor) -> tuple[str, ...]:
    """Return claimed channel ids requiring a separate acquisition-workflow dispatch, sorted.

    Derived from the SAME claimed-channel authority :data:`SOURCE_INPUT_BY_CHANNEL`
    already declares — no second mapping is introduced. A channel whose evidence
    source IS the cohort input itself (today, only ``python``: its evidence rides
    the packaging-smoke run that produced the cohort) needs no acquisition
    dispatch. Every other claimed channel's evidence comes from a dedicated
    acquisition workflow run, so it is a lane. A claimed channel absent from
    :data:`SOURCE_INPUT_BY_CHANNEL` entirely is never silently treated as
    lane-free here — it is simply excluded from this result, and the existing
    fail-closed :func:`unmapped_claimed_channels` / :func:`refusals` catch it
    at the CLI boundary instead of letting it pass unproven.

    Flipping a channel's availability to ``available`` therefore arms its lane
    with no workflow edit: the set changes because the claim changed, not
    because this function was taught a new channel.
    """
    return tuple(
        sorted(
            channel.id
            for channel in claimed_channels(descriptor)
            if SOURCE_INPUT_BY_CHANNEL.get(channel.id) not in (None, COHORT_INPUT)
        ),
    )


def unmapped_acquisition_lanes(descriptor: DownloadDescriptor) -> tuple[str, ...]:
    """Return lane channel ids from :func:`acquisition_lanes` with no declared workflow, sorted.

    Fail-closed companion to :data:`LANE_WORKFLOW_BY_CHANNEL`: every channel
    :func:`acquisition_lanes` names as needing a dispatch must resolve to a
    workflow here, or the orchestrator would have nothing to dispatch for a
    claim it is supposed to prove. A non-empty result is a hole in the
    mapping, not a reason to proceed silently.
    """
    return tuple(
        sorted(channel_id for channel_id in acquisition_lanes(descriptor) if channel_id not in LANE_WORKFLOW_BY_CHANNEL)
    )


def acquisition_lane_workflows(descriptor: DownloadDescriptor) -> tuple[str, ...]:
    """Return the distinct acquisition workflow paths the claimed lanes require, sorted.

    Built from :func:`acquisition_lanes`: every claimed channel needing a
    separate acquisition dispatch is resolved to its workflow path here,
    deduplicated. A lane channel absent from :data:`LANE_WORKFLOW_BY_CHANNEL` is
    silently excluded here rather than raised; callers that need the fail-closed
    behaviour check :func:`unmapped_acquisition_lanes` first.
    """
    return tuple(
        sorted(
            {
                LANE_WORKFLOW_BY_CHANNEL[channel_id]
                for channel_id in acquisition_lanes(descriptor)
                if channel_id in LANE_WORKFLOW_BY_CHANNEL
            },
        ),
    )


def lane_output_name(workflow_path: str) -> str:
    """Return the workflow-output name one acquisition lane's run id is carried under.

    Derived from the same mapping that chose the lane, so a lane can never be
    dispatched without somewhere to put its run id. A lane whose id is dropped
    reaches the publication without its acquisition proof, and does so silently
    because the descriptor claiming that channel is what arms the path.
    """
    for channel_id, path in LANE_WORKFLOW_BY_CHANNEL.items():
        if path == workflow_path:
            return f"{channel_id.replace('-', '_')}_run_id"
    raise ValueError(f"acquisition lane {workflow_path!r} has no declared output name")


def unmapped_claimed_channels(descriptor: DownloadDescriptor) -> tuple[str, ...]:
    """Return claimed channel ids this module cannot source evidence for.

    A non-empty result is a hole in the derivation, not a reason to proceed.
    """
    return tuple(
        sorted(channel.id for channel in claimed_channels(descriptor) if channel.id not in SOURCE_INPUT_BY_CHANNEL),
    )


def demanded_inputs(descriptor: DownloadDescriptor) -> tuple[str, ...]:
    """Return the dispatch inputs the claimed channels require, sorted.

    Always includes :data:`COHORT_INPUT`, which carries the published bytes.
    """
    demanded = {COHORT_INPUT}
    for channel in claimed_channels(descriptor):
        if source := SOURCE_INPUT_BY_CHANNEL.get(channel.id):
            demanded.add(source)
    return tuple(sorted(demanded))


def missing_sources(
    descriptor: DownloadDescriptor,
    provided: Mapping[str, str],
) -> tuple[str, ...]:
    """Return demanded inputs absent or blank in ``provided``, sorted."""
    return tuple(
        sorted(name for name in demanded_inputs(descriptor) if not provided.get(name, "").strip()),
    )


def refusals(descriptor: DownloadDescriptor, provided: Mapping[str, str]) -> tuple[str, ...]:
    """Return every instructive refusal line, empty when the dispatch is sound."""
    lines: list[str] = []
    if unmapped := unmapped_claimed_channels(descriptor):
        lines.append(
            f"REFUSED: claimed channel(s) {list(unmapped)} have no acquisition-evidence source. "
            "Add them to SOURCE_INPUT_BY_CHANNEL in dev/packaging/publication_inputs.py and give "
            "publish-release.yml an input to carry them; a claimed channel is never published unproven.",
        )
    for name in missing_sources(descriptor, provided):
        if name == COHORT_INPUT:
            lines.append(
                f"REFUSED: input {COHORT_INPUT!r} is empty. It names the packaging-smoke run whose "
                "sealed cohort IS the published bytes, so no publication of any shape can proceed "
                "without it. Dispatch again with a successful Cadrumo Packaging Smoke run id.",
            )
            continue
        owners = sorted(
            channel.id for channel in claimed_channels(descriptor) if SOURCE_INPUT_BY_CHANNEL.get(channel.id) == name
        )
        lines.append(
            f"REFUSED: input {name!r} is required because this release claims channel(s) {owners}, "
            "and it was dispatched empty. Run that channel's acquisition workflow against the sealed "
            "cohort and dispatch again with its run id, or stop claiming the channel in "
            "docs/_data/download_channels.toml.",
        )
    return tuple(lines)


def _emit_outputs(descriptor: DownloadDescriptor, output_path: Path) -> None:
    """Append one ``need_<input>`` boolean per known input to ``GITHUB_OUTPUT``."""
    demanded = set(demanded_inputs(descriptor))
    lines = "".join(
        f"need_{name}={'true' if name in demanded else 'false'}\n"
        for name in sorted(set(SOURCE_INPUT_BY_CHANNEL.values()) | {COHORT_INPUT})
    )
    with output_path.open("a", encoding=_UTF_8, newline="\n") as handle:
        handle.write(lines)


def main(argv: list[str] | None = None) -> int:
    """Refuse an under-sourced dispatch, else emit the per-input demand."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-output", type=Path, default=None)
    # Orchestrator-facing modes. Both READ the same claimed-channel derivation
    # the publication gate reads, so the lanes a release dispatches and the
    # evidence it later demands can never disagree.
    parser.add_argument(
        "--emit-lane-workflows",
        action="store_true",
        help="Print the acquisition workflow paths the claimed channels require, one per line.",
    )
    args = parser.parse_args(argv)

    descriptor = load_descriptor()

    if args.emit_lane_workflows:
        # Each line is `<workflow path>	<output name>`. The output name rides
        # along so the orchestrator needs no lane names of its own: a lane whose
        # id had nowhere to go was silently dropped, and re-deriving the mapping
        # in shell would fork this module's authority over the lane set.
        for workflow_path in acquisition_lane_workflows(descriptor):
            print(f"{workflow_path}	{lane_output_name(workflow_path)}")
        return 0

    provided = {name: os.environ.get(name.upper(), "") for name in SOURCE_INPUT_BY_CHANNEL.values()}
    provided[COHORT_INPUT] = os.environ.get(COHORT_INPUT.upper(), "")

    if lines := refusals(descriptor, provided):
        for line in lines:
            print(line, file=sys.stderr)
        return 1

    demanded = demanded_inputs(descriptor)
    print(f"required by the claimed channels: {list(demanded)}")
    if args.github_output is not None:
        _emit_outputs(descriptor, args.github_output)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
