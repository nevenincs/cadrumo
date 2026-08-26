"""Gate: no command subject is mounted under a root its own policy contradicts.

The two roots carry one sentence of charter each, and for most of the tree that
is all there is. This module does not try to fix that. It encodes the narrow
case where a subject's own declared `ExecutionPolicySpec` disagrees with where it
is mounted, and refuses only that.

An `app` signal is `filing`, or `registry`, or `calculation` together with a
write route. `calculation` alone is deliberately insufficient: `config profile
status`, `validate` and `preflight` all declare it while computing facts about
the profile, and `config repair integrity registry` declares it while reading
bundled data. All four are read-only, and a criterion that evicted them would be
wrong about the most canonical `config` verbs in the tree.

A `config` signal is a `bootstrap-root` write route, or `profile-custody` without
`encrypted-facts` -- custody state that exists before any profile is unlocked.

**Granularity is the load-bearing choice, and it was found by simulation.** At
top-level-family granularity the rule moves the whole `config google` family to
`app`, because three of its fourteen leaves once carried `app` signals -- which
would have dragged OAuth, folder and credential-source configuration along with
the workbook verbs. At narrowest-subject granularity -- the deepest group that
can move as one -- the same rule produced exactly the two moves this campaign
made and demanded no splits.

**This is a refusal criterion, not a placement criterion, and the distinction is
not pedantic.** Roughly two thirds of subjects carry no signal in either
direction. This module says nothing about where `app live`, `app overview`,
`config auth` or `config provision` belong, and a green run is not evidence they
are correctly placed. Reading it as one would recreate the false confidence the
first draft of the governing decision was rejected for.
"""

from __future__ import annotations

import pytest

from .._command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_APP = "app"
_CONFIG = "config"


def _subjects() -> dict[tuple[str, ...], list]:
    """Group every leaf under its narrowest mountable subject."""
    subjects: dict[tuple[str, ...], list] = {}
    for node in COMMAND_GRAPH.nodes():
        if node.spec.kind != "leaf":
            continue
        subjects.setdefault(node.path[:-1], []).append(node)
    return subjects


def _has_app_signal(policy: object) -> bool:
    capabilities = policy.capabilities
    if "filing" in capabilities or "registry" in capabilities:
        return True
    return "calculation" in capabilities and policy.write_route != "none"


def _has_config_signal(policy: object) -> bool:
    capabilities = policy.capabilities
    if policy.write_route == "bootstrap-root":
        return True
    return "profile-custody" in capabilities and "encrypted-facts" not in capabilities


def test_no_subject_carrying_an_app_signal_is_mounted_under_config() -> None:
    """Tax-application work does not live under the configuration root."""
    offenders = []
    for path, nodes in _subjects().items():
        if path[1] != _CONFIG:
            continue
        carriers = [node.path[-1] for node in nodes if _has_app_signal(node.spec.policy)]
        if carriers:
            offenders.append(f"{' '.join(path)} :: {', '.join(sorted(carriers))}")
    assert not offenders, "subjects carrying an app signal under `config`: " + "; ".join(sorted(offenders))


def test_no_subject_carrying_a_config_signal_is_mounted_under_app() -> None:
    """Custody and bootstrap state does not live under the application root."""
    offenders = []
    for path, nodes in _subjects().items():
        if path[1] != _APP:
            continue
        carriers = [node.path[-1] for node in nodes if _has_config_signal(node.spec.policy)]
        if carriers:
            offenders.append(f"{' '.join(path)} :: {', '.join(sorted(carriers))}")
    assert not offenders, "subjects carrying a config signal under `app`: " + "; ".join(sorted(offenders))


def test_no_subject_carries_both_signals() -> None:
    """A subject pulled both ways is a design defect, not a placement question."""
    conflicted = []
    for path, nodes in _subjects().items():
        app_side = any(_has_app_signal(node.spec.policy) for node in nodes)
        config_side = any(_has_config_signal(node.spec.policy) for node in nodes)
        if app_side and config_side:
            conflicted.append(" ".join(path))
    assert not conflicted, "subjects carrying both signals and needing a split: " + "; ".join(sorted(conflicted))


def test_the_criterion_is_reading_a_populated_graph() -> None:
    """Anti-vacuity: every assertion above greens on an empty or policy-less graph.

    The floors are set far below the live counts so this detects a collapse in
    graph materialisation rather than encoding today's totals.
    """
    subjects = _subjects()
    signal_bearing = sum(
        1
        for nodes in subjects.values()
        if any(_has_app_signal(node.spec.policy) or _has_config_signal(node.spec.policy) for node in nodes)
    )
    assert len(subjects) >= 40, f"mountable subjects collapsed to {len(subjects)}"
    assert signal_bearing >= 10, f"policy signals collapsed to {signal_bearing} subjects"
