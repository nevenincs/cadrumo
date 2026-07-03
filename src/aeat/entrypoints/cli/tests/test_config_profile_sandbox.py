"""CLI tests for the ``aeat config profile sandbox`` experiment-workspace lifecycle.

Resolves #422: an operator (or an LLM agent driving the CLI) needs to run
experiments in an isolated bucket without polluting the main profile's
records, then discard the experiment cleanly. These tests drive the real
``aeat config profile sandbox`` verbs against real per-bucket encrypted
storage (no mocks, per the roundtrip-discipline rule) and prove:

- ``create --from-profile`` forks an isolated bucket seeded with the
  source's facts; the source bucket is never mutated.
- writes made while the sandbox is active never appear on the main profile
  after switching back.
- ``discard`` refuses the active bucket (mirroring
  ``BucketMaintenanceService.delete``'s existing contract), refuses without
  ``--yes``, and on success erases the sandbox from the live profile
  surface while leaving every other profile intact.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ._profile_lifecycle_support import create_profile_via_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def test_sandbox_create_forks_isolated_bucket_seeded_from_source() -> None:
    """``sandbox create --from-profile`` copies facts without touching the source.

    The sandbox becomes the active profile and carries the seeded fact
    (``activities.description``); the source profile's own record is
    read through an unrelated bucket session and remains untouched.
    """
    create_profile_via_cli("main")

    created = _invoke(("config", "profile", "sandbox", "create", "bakeoff", "--from-profile", "main"))
    assert created.exit_code == 0, created.output
    assert "label\tsandbox:bakeoff" in created.output
    assert "seeded_from\tmain" in created.output

    # The sandbox is now active and carries the seeded fact.
    shown = _invoke(("config", "profile", "show"))
    assert shown.exit_code == 0, shown.output
    assert "display_name\tsandbox:bakeoff" in shown.output
    assert "activities.description\tdesign" in shown.output

    # The source profile is untouched: switching back shows the original label
    # and the same seeded fact value, never a value written while in the sandbox.
    switched = _invoke(("config", "switch", "main"))
    assert switched.exit_code == 0, switched.output
    main_shown = _invoke(("config", "profile", "show"))
    assert main_shown.exit_code == 0, main_shown.output
    assert "display_name\tmain" in main_shown.output
    assert "activities.description\tdesign" in main_shown.output


def test_sandbox_writes_never_appear_on_main_after_switching_back() -> None:
    """Editing a fact inside the sandbox must not leak into the main profile.

    This is the core isolation proof the issue asks for: an experiment
    (here, a profile-fact edit standing in for "imports, classifications,
    calculations") performed while the sandbox is active must be invisible
    on the main profile once the operator switches back.
    """
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "lab", "--from-profile", "main")).exit_code == 0

    edited = _invoke(
        ("config", "profile", "edit", "sandbox:lab", "--quiet", "--activity", "sandbox-experiment"),
    )
    assert edited.exit_code == 0, edited.output

    sandbox_shown = _invoke(("config", "profile", "show"))
    assert "activities.description\tsandbox-experiment" in sandbox_shown.output

    assert _invoke(("config", "switch", "main")).exit_code == 0
    main_shown = _invoke(("config", "profile", "show"))
    assert main_shown.exit_code == 0, main_shown.output
    # The main profile keeps its original value; the sandbox edit never landed here.
    assert "activities.description\tdesign" in main_shown.output
    assert "activities.description\tsandbox-experiment" not in main_shown.output


def test_sandbox_list_shows_only_sandbox_labelled_buckets() -> None:
    """``sandbox list`` filters to buckets carrying the reserved prefix."""
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "alpha", "--from-profile", "main")).exit_code == 0

    listing = _invoke(("config", "profile", "sandbox", "list"))
    assert listing.exit_code == 0, listing.output
    assert "sandbox:alpha" in listing.output
    assert "\tmain" not in listing.output

    full_listing = _invoke(("config", "profile", "list"))
    assert full_listing.exit_code == 0, full_listing.output
    assert "main" in full_listing.output
    assert "sandbox:alpha" in full_listing.output


def test_sandbox_discard_refuses_without_yes() -> None:
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "temp", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "switch", "main")).exit_code == 0

    refused = _invoke(("config", "profile", "sandbox", "discard", "temp"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_discard_refuses_the_active_bucket() -> None:
    """Discarding the currently-active sandbox is refused; the operator switches first.

    Mirrors ``BucketMaintenanceService.delete``'s existing active-bucket
    refusal, applied through the sandbox composition.
    """
    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "active-one", "--from-profile", "main")).exit_code == 0

    refused = _invoke(("config", "profile", "sandbox", "discard", "active-one", "--yes"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_discard_erases_sandbox_and_leaves_main_intact() -> None:
    """A confirmed discard of a non-active sandbox erases it from the live surface.

    Every other profile — in particular ``main`` — must remain fully
    intact and readable after the discard.
    """
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("main")
    assert _invoke(("config", "profile", "sandbox", "create", "throwaway", "--from-profile", "main")).exit_code == 0
    assert _invoke(("config", "switch", "main")).exit_code == 0

    discarded = _invoke(("config", "profile", "sandbox", "discard", "throwaway", "--yes"))
    assert discarded.exit_code == 0, discarded.output
    assert "previous_label\tsandbox:throwaway" in discarded.output

    # The sandbox is gone from the live surface.
    assert read_profile_bucket("sandbox:throwaway") is None

    # main is unaffected: still resolvable, still active, still carries its facts.
    main_shown = _invoke(("config", "profile", "show"))
    assert main_shown.exit_code == 0, main_shown.output
    assert "display_name\tmain" in main_shown.output
    assert "activities.description\tdesign" in main_shown.output

    listing = _invoke(("config", "profile", "list"))
    assert listing.exit_code == 0, listing.output
    assert "main" in listing.output
    assert "sandbox:throwaway" not in listing.output


def test_sandbox_discard_unknown_name_refuses() -> None:
    create_profile_via_cli("main")

    refused = _invoke(("config", "profile", "sandbox", "discard", "does-not-exist", "--yes"))
    assert refused.exit_code != 0, refused.output


def test_sandbox_create_without_from_profile_refuses_incomplete_schema() -> None:
    """``sandbox create`` with no ``--from-profile`` hits the same schema gate ``profile create`` does.

    A sandbox is a real profile bucket underneath, so an unseeded sandbox
    with zero facts fails the identical required-field validation
    ``config profile create`` enforces — there is no bypass. Operators
    seed a realistic sandbox with ``--from-profile`` (the documented
    success path); this refusal proves the sandbox surface does not
    quietly relax that contract.
    """
    refused = _invoke(("config", "profile", "sandbox", "create", "onboarding-demo"))
    assert refused.exit_code != 0, refused.output
    assert "required_field_missing" in refused.output
