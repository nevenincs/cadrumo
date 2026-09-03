"""Structural gate for the concurrent packaging-lane campaign driver."""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..campaign import (
    _COHORT_DIR,
    _LANES,
    _PROFILES,
    _TEST_WORKERS_ENV,
    _test_worker_count,
    resolve_form,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_JUSTFILE = REPO_ROOT / "justfile"
_PACKAGING = Path(__file__).resolve().parents[1]

# The executed set, pinned as (module, extra args) per profile in run order.
# This is the guarantee the lane/form migration had to preserve: the hierarchy
# reorganises who OWNS a proof, never which processes run. Pinning the resolved
# invocation rather than the selector names is what keeps that true for the next
# change too — a selector can be renamed freely, but the executed set cannot
# drift without this failing.
_EXPECTED_EXECUTION: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "quick": (("dev.packaging.smoke_core", ()),),
    "portable": (
        ("dev.packaging.smoke_core", ()),
        ("dev.packaging.smoke_pip_core", ()),
        ("dev.packaging.smoke_sdist_core", ()),
        ("dev.packaging.all_extra_smoke", ()),
        ("dev.packaging.smoke_split_install", ()),
        ("dev.packaging.smoke_browser", ()),
        ("dev.packaging.smoke_absent_llm", ()),
    ),
    "ci": (
        ("dev.packaging.smoke_dev", ()),
        ("dev.packaging.smoke_core", ()),
        ("dev.packaging.smoke_pip_core", ()),
        ("dev.packaging.smoke_sdist_core", ()),
        ("dev.packaging.all_extra_smoke", ()),
        ("dev.packaging.smoke_split_install", ()),
        ("dev.packaging.smoke_browser", ("--with-deps",)),
        ("dev.packaging.smoke_absent_llm", ()),
    ),
}


def test_profiles_reference_registered_forms_only() -> None:
    """Every profile entry is a qualified selector resolving to a registered form."""
    assert _PROFILES, "no packaging profiles are declared; every profile trivially references known forms"
    for profile, selectors in _PROFILES.items():
        assert len(selectors) == len(set(selectors)), f"profile {profile} repeats a form"
        for selector in selectors:
            assert "/" in selector, f"profile {profile} entry {selector!r} is not a 'lane/form' selector"
            resolve_form(selector)  # raises KeyError on an unknown lane or form


def test_every_registered_form_is_selected_by_some_profile() -> None:
    """A form no profile runs is dead capacity, which is what the flat registry hid."""
    selected = {selector for selectors in _PROFILES.values() for selector in selectors}
    registered = {f"{lane.name}/{form.name}" for lane in _LANES.values() for form in lane.forms}
    assert registered == selected, f"forms never run: {sorted(registered - selected)}"


def test_profiles_resolve_to_the_pinned_executed_set() -> None:
    """The hierarchy reorganises ownership, never which processes run.

    Each profile's resolved invocations must equal the pinned module/argument
    sequence, in order. This is the migration's load-bearing guarantee, kept as
    a standing pin rather than a one-off check performed at migration time.

    The set equality below is what makes the pin total. Iterating the pinned
    table alone would never VISIT a profile absent from it, so a whole new
    profile — the thing a workflow actually invokes — could land carrying any
    executed set at all and every assertion here would still pass.
    """
    assert set(_EXPECTED_EXECUTION) == set(_PROFILES), (
        f"every profile must be pinned; unpinned: {sorted(set(_PROFILES) - set(_EXPECTED_EXECUTION))}, "
        f"stale pins: {sorted(set(_EXPECTED_EXECUTION) - set(_PROFILES))}"
    )
    for profile, expected in _EXPECTED_EXECUTION.items():
        resolved: list[tuple[str, tuple[str, ...]]] = []
        for selector in _PROFILES[profile]:
            _lane, form = resolve_form(selector)
            resolved.append((form.module, form.extra_args))
        assert tuple(resolved) == expected, f"profile {profile} executed set drifted"


def test_only_the_developer_lane_skips_the_shared_cohort() -> None:
    """Every install-surface form consumes the one built cohort; dev builds its own env."""
    for lane in _LANES.values():
        for form in lane.forms:
            takes_cohort = f"--cohort-dir {_COHORT_DIR}" in " ".join(form.command())
            expected = lane.name != "dev"
            assert takes_cohort is expected, f"{lane.name}/{form.name} cohort wiring is wrong"


def test_quick_profile_is_exactly_the_single_core_probe() -> None:
    """The per-push quick profile proves one install surface and nothing else.

    The quick profile exists to keep the per-push wall inside the ten-minute
    budget; growing it must be a conscious decision against that budget, so
    the set is pinned to exactly one form of the core lane.
    """
    assert _PROFILES["quick"] == ("core/uv-venv",)


def test_portable_profile_matches_the_host_portable_aggregate() -> None:
    """The portable profile carries the host-portable forms, no host-specific ones."""
    assert set(_PROFILES["portable"]) == {
        "core/uv-venv",
        "core/plain-pip",
        "core/sdist",
        "core/extras",
        "core/joined-cohort",
        "browser/host",
        "inference-boundary/wheel",
    }
    assert "browser/host-with-deps" not in _PROFILES["portable"]


def test_ci_profile_is_the_ubuntu_superset() -> None:
    """The ci profile covers every portable proof plus the Linux-only forms."""
    ci = set(_PROFILES["ci"])
    assert {
        "dev/frozen-lock",
        "core/uv-venv",
        "core/plain-pip",
        "core/sdist",
        "core/extras",
        "core/joined-cohort",
        "inference-boundary/wheel",
    } <= ci
    assert "browser/host-with-deps" in ci
    # The portable browser variant is replaced by the --with-deps variant.
    assert "browser/host" not in ci


def test_preflight_test_workers_resolve_flag_then_env_then_local_auto() -> None:
    """CI legs size the preflight pytest per machine share; local keeps -n auto.

    A resolved value becomes an explicit ``-n N`` (the fleet is three runners
    per physical machine, so ``-n auto`` over-subscribes); ``None`` leaves the
    local addopts default untouched.
    """
    assert _test_worker_count(4) == 4
    original = os.environ.get(_TEST_WORKERS_ENV)
    os.environ[_TEST_WORKERS_ENV] = "8"
    try:
        assert _test_worker_count(None) == 8
        assert _test_worker_count(2) == 2  # CLI flag beats env
    finally:
        if original is None:
            del os.environ[_TEST_WORKERS_ENV]
        else:
            os.environ[_TEST_WORKERS_ENV] = original
    if _TEST_WORKERS_ENV not in os.environ:
        assert _test_worker_count(None) is None


def test_aggregates_route_through_the_campaign_driver() -> None:
    """The two workflow aggregates invoke the driver with their profiles."""
    justfile = _JUSTFILE.read_text(encoding="utf-8")
    assert "dev.packaging.campaign --profile portable" in justfile
    assert "dev.packaging.campaign --profile ci" in justfile
    assert "dev.packaging.campaign --profile quick" in justfile


def test_a_lane_with_a_behavioural_proof_names_a_real_reference_form() -> None:
    """The reference form must exist on its own lane, and pair with a proof."""
    for lane in _LANES.values():
        assert (lane.behavioural_proof is None) == (lane.reference_form is None), (
            f"lane {lane.name} pairs a behavioural proof with a reference form, or declares neither"
        )
        if lane.reference_form is not None:
            lane.form(lane.reference_form)  # raises KeyError on an unregistered form


def test_the_behavioural_proof_runs_on_the_reference_form_and_nowhere_else() -> None:
    """The installed oracle is lane-level: exactly one FORM carries it.

    This is the only invariant class that legitimately collapses — it proves a
    property of the PRODUCT, so running it once per form was a real
    triplication (core, split, and the serial oracles pass, against one
    cohort and one target). Install-level invariants are deliberately not
    collapsed this way: the installed virtualenv is what a form produces, so
    asserting those once would leave the other installers unproven.

    "Lane-level" does NOT mean once per run. The oracle still runs twice:
    here at the reference form, and again in the serial installed-oracles pass.
    That is the intended end state — the audit dropped split's copy and kept
    those two — and the serial pass is not a form, so this pin neither covers
    nor should cover it.

    Pinned statically against each form's module source, so a second call site
    fails here rather than after a campaign has paid for it twice.

    Known limitation, recorded where someone would trip on it. This keys on the
    module, so it cannot express a behavioural proof for a lane whose forms
    SHARE a module: ``smoke_browser`` backs both browser host forms, so
    ``calls_oracle`` is necessarily equal across them while ``expected`` would
    differ — unsatisfiable by construction. Every browser-lane form shares its
    all today. Nothing is blocked (``behavioural_proof=None`` is a legitimate
    state the pairing test enforces), but a future "the browser really drives a
    state the pairing test enforces), but a future "the browser really drives a
    page" proof meets this wall. The fix then is to key on the resolved
    ``(module, extra_args)`` invocation, the granularity the executed-set pin
    above already uses.
    """
    oracle = "run_installed_tax_oracle"
    for lane in _LANES.values():
        reference = lane.reference()
        for form in lane.forms:
            module_path = _PACKAGING / f"{form.module.rsplit('.', 1)[-1]}.py"
            calls_oracle = any(
                isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == oracle
                for node in ast.walk(ast.parse(module_path.read_text(encoding="utf-8")))
            )
            expected = reference is not None and form is reference
            assert calls_oracle is expected, (
                f"{lane.name}/{form.name} {'must' if expected else 'must not'} run the "
                f"lane's behavioural proof; it is owned by {lane.reference_form!r}"
            )


def test_lane_names_are_distinct_so_manifest_rows_stay_distinguishable() -> None:
    """Manifest granularity now rides on the lane name, so it must discriminate.

    Claim strings were deliberately genericised: one shared helper performs the
    pip install for the wheel, sdist and extras forms, and an assertion cannot
    honestly name an artifact kind it was never told about. The per-form
    granularity did not vanish — it moved to the manifest's ``lane`` and
    ``artifacts`` fields. That makes lane-name distinctness load-bearing: two
    forms writing the same lane name would collapse separate proofs into
    indistinguishable rows, silently, with every other gate still green.
    """
    names = [lane.name for lane in _LANES.values()]
    assert len(names) == len(set(names)), f"lane names must discriminate manifest rows: {names}"
    assert all(name and name.strip() == name for name in names), f"lane names must be non-empty: {names}"
