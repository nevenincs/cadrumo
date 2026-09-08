"""A job's guard decides its reach; the workflow's ``on:`` block only starts the run.

The gate these tests protect is the one a trigger model gets wrong by default:
attributing a workflow's events to every job inside it. The defect is proved
directly rather than asserted about the live tree alone -- a synthetic workflow
shaped exactly like ``runner-fleet-health.yml`` must report its dispatch-gated
job as unreached by push, and the fork guard beside it must keep every event it
has.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ..lane_reachability import ci_invoked_recipe_opt_in, ci_invoked_recipe_triggers
from ..workflow_job_gates import (
    JobGate,
    dispatch_input_defaults,
    job_gate,
    narrowed_events,
    opt_in_conjuncts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FORK_GUARD = (
    "github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository"
)
_DEV_IMAGE_GUARD = "${{ github.event_name == 'workflow_dispatch' && inputs.include_dev_image }}"


def _workflow() -> dict[str, Any]:
    """A workflow shaped like the live fleet-health lane: push plus an opt-in job."""
    return {
        # YAML 1.1 parses `on:` as the boolean True, which is how a safe-loaded
        # workflow really arrives. Building the fixture the naive way would test
        # a document this code never sees.
        True: {
            "push": {"branches": ["main"]},
            "workflow_dispatch": {"inputs": {"include_dev_image": {"type": "boolean", "default": False}}},
        },
        "jobs": {
            "runner-image": {"steps": [{"run": "just test-runner-image"}]},
            "dev-image": {"if": _DEV_IMAGE_GUARD, "steps": [{"run": "just test-devcontainer"}]},
            "guarded": {"if": _FORK_GUARD, "steps": [{"run": "just test-unit"}]},
        },
    }


def test_a_dispatch_gated_job_does_not_inherit_the_workflow_push() -> None:
    """The defect itself: the run starts on push and this job is not in it."""
    document = _workflow()
    events = ("push", "workflow_dispatch")
    assert job_gate(document, "runner-image", events) == JobGate(events=("push", "workflow_dispatch"))
    assert job_gate(document, "dev-image", events).events == ("workflow_dispatch",)


def test_a_falsy_input_default_is_reported_as_a_second_weakening() -> None:
    """Manual and opt-in are distinct: the button exists and pressing it is not enough."""
    document = _workflow()
    gate = job_gate(document, "dev-image", ("push", "workflow_dispatch"))
    assert gate.is_opt_in
    assert gate.opt_in == ("include_dev_image",)
    # Flipping only the default removes the second weakening and leaves the first.
    document[True]["workflow_dispatch"]["inputs"]["include_dev_image"]["default"] = True
    relaxed = job_gate(document, "dev-image", ("push", "workflow_dispatch"))
    assert relaxed.events == ("workflow_dispatch",)
    assert not relaxed.is_opt_in


def test_the_fork_guard_narrows_nothing_because_it_cannot_be_proved_to() -> None:
    """A disjunct this module does not model could re-admit any event, so it narrows none.

    This is the case that decides whether the model is usable: ten per-push jobs
    in this repository carry exactly this guard, and a model that narrowed it
    would report them all unreachable on push and bury the one true finding.
    """
    events = ("pull_request", "push", "workflow_dispatch")
    assert narrowed_events(_FORK_GUARD, events) == events
    assert opt_in_conjuncts(_FORK_GUARD) == ()


def test_an_inequality_subtracts_and_an_equality_intersects() -> None:
    """Both comparison directions are modelled, and only inside a pure conjunction."""
    events = ("pull_request", "push", "workflow_dispatch")
    assert narrowed_events("github.event_name != 'pull_request'", events) == ("push", "workflow_dispatch")
    assert narrowed_events("github.event_name == 'push'", events) == ("push",)
    assert narrowed_events("github.event_name == 'push' && inputs.deep", events) == ("push",)


def test_an_input_compared_against_a_value_is_not_claimed_to_be_opt_in() -> None:
    """Its default may well satisfy it, so calling it opt-in would claim an unproved weakening."""
    assert opt_in_conjuncts("inputs.mode == 'full'") == ()
    assert opt_in_conjuncts("github.event_name == 'workflow_dispatch' && inputs.mode") == ("mode",)


def test_an_undeclared_input_reference_is_falsy_rather_than_unknown() -> None:
    """GitHub evaluates an absent input as empty, so the gated job never runs at all."""
    document = _workflow()
    document["jobs"]["dev-image"]["if"] = "github.event_name == 'workflow_dispatch' && inputs.never_declared"
    assert job_gate(document, "dev-image", ("push", "workflow_dispatch")).is_opt_in


def test_the_trigger_block_is_read_from_the_yaml_boolean_key() -> None:
    """`document["on"]` is empty for every workflow here; an empty default map is the silent failure."""
    assert dispatch_input_defaults(_workflow()) == {"include_dev_image": False}
    assert dispatch_input_defaults({"on": {"workflow_dispatch": {"inputs": {"deep": {}}}}}) == {"deep": None}
    assert dispatch_input_defaults({"jobs": {}}) == {}


def test_a_job_the_document_does_not_declare_reaches_nothing() -> None:
    """Absence is not silently the workflow's own event set."""
    assert job_gate(_workflow(), "absent", ("push",)) == JobGate(events=())


def test_the_live_devcontainer_lane_is_manual_only_and_opt_in() -> None:
    """The finding this module was written for, asserted against the real tree.

    ``just test-devcontainer`` is the only thing that builds and probes the
    contributor image, it is invoked exactly once, and both weakenings on that
    one route are individually documented in the workflow. Their product is that
    no automatic event and no ordinary dispatch runs it.
    """
    root = Path(__file__).resolve().parents[3]
    triggers = ci_invoked_recipe_triggers(root)
    assert triggers["devcontainer-test"] == ("workflow_dispatch",)
    assert "devcontainer-test" in ci_invoked_recipe_opt_in(root)
    # The sibling job in the same workflow is gated by nothing and keeps its push.
    assert "push" in triggers["runner-image-test"]
