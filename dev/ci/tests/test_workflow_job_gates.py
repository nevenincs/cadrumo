"""A job's guard decides its reach; the workflow's ``on:`` block only starts the run.

The gate these tests protect is the one a trigger model gets wrong by default:
attributing a workflow's events to every job inside it. The defect is proved
directly rather than asserted about the live tree alone -- a synthetic workflow
with a push trigger and an opt-in dispatch-only job must report its dispatch-gated
job as unreached by push, and the fork guard beside it must keep every event it
has.
"""

from __future__ import annotations

from typing import Any

import pytest

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
_OPT_IN_GUARD = "${{ github.event_name == 'workflow_dispatch' && inputs.include_opt_in_lane }}"


def _workflow() -> dict[str | bool, Any]:
    """A workflow with a push trigger plus an opt-in, dispatch-only job."""
    return {
        # YAML 1.1 parses `on:` as the boolean True, which is how a safe-loaded
        # workflow really arrives. Building the fixture the naive way would test
        # a document this code never sees.
        True: {
            "push": {"branches": ["main"]},
            "workflow_dispatch": {"inputs": {"include_opt_in_lane": {"type": "boolean", "default": False}}},
        },
        "jobs": {
            "ungated": {"steps": [{"run": "just test-unit"}]},
            "opt-in": {"if": _OPT_IN_GUARD, "steps": [{"run": "just test-tooling"}]},
            "guarded": {"if": _FORK_GUARD, "steps": [{"run": "just test-unit"}]},
        },
    }


def test_a_dispatch_gated_job_does_not_inherit_the_workflow_push() -> None:
    """The defect itself: the run starts on push and this job is not in it."""
    document = _workflow()
    events = ("push", "workflow_dispatch")
    assert job_gate(document, "ungated", events) == JobGate(events=("push", "workflow_dispatch"))
    assert job_gate(document, "opt-in", events).events == ("workflow_dispatch",)


def test_a_falsy_input_default_is_reported_as_a_second_weakening() -> None:
    """Manual and opt-in are distinct: the button exists and pressing it is not enough."""
    document = _workflow()
    gate = job_gate(document, "opt-in", ("push", "workflow_dispatch"))
    assert gate.is_opt_in
    assert gate.opt_in == ("include_opt_in_lane",)
    # Flipping only the default removes the second weakening and leaves the first.
    dispatch = next(value for key, value in document.items() if key is True)
    dispatch["workflow_dispatch"]["inputs"]["include_opt_in_lane"]["default"] = True
    relaxed = job_gate(document, "opt-in", ("push", "workflow_dispatch"))
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
    document["jobs"]["opt-in"]["if"] = "github.event_name == 'workflow_dispatch' && inputs.never_declared"
    assert job_gate(document, "opt-in", ("push", "workflow_dispatch")).is_opt_in


def test_the_trigger_block_is_read_from_the_yaml_boolean_key() -> None:
    """`document["on"]` is empty for every workflow here; an empty default map is the silent failure."""
    assert dispatch_input_defaults(_workflow()) == {"include_opt_in_lane": False}
    assert dispatch_input_defaults({"on": {"workflow_dispatch": {"inputs": {"deep": {}}}}}) == {"deep": None}
    assert dispatch_input_defaults({"jobs": {}}) == {}


def test_a_job_the_document_does_not_declare_reaches_nothing() -> None:
    """Absence is not silently the workflow's own event set."""
    assert job_gate(_workflow(), "absent", ("push",)) == JobGate(events=())
