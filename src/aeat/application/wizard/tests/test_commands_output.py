"""Output-boundary tests for wizard command helpers."""

from __future__ import annotations

import json
from collections.abc import Iterator

import click
import pytest

from ....core.redaction import CLI_PROFILE_ID_PLACEHOLDER
from .._commands import _emit_wizard_success
from .._persistence import WizardPersistMode

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def _json_context() -> Iterator[None]:
    """Activate a Click context that requests ``--format json`` output.

    ``_emit_wizard_success`` chooses its transport via
    :func:`json_output_requested`, which walks the active Click context
    chain. Pushing an upstream :class:`click.Context` whose ``obj``
    carries the JSON flag drives the real JSON branch without a full
    CliRunner round-trip — the same probe the production root callback
    populates.
    """
    command = click.Command("probe")
    with click.Context(command, obj={"json": True}):
        yield


def test_wizard_success_text_uses_central_output_redaction(capsys: pytest.CaptureFixture[str]) -> None:
    profile_id_like_label = "123e4567-e89b-12d3-a456-426614174000"

    _emit_wizard_success("create", profile_id_like_label)

    output = capsys.readouterr().out
    assert profile_id_like_label not in output
    assert CLI_PROFILE_ID_PLACEHOLDER in output
    assert "next\taeat app modelo work create" in output


@pytest.mark.parametrize(
    ("mode", "command_path"),
    [
        pytest.param("create", "config.profile.create", id="create"),
        pytest.param("edit", "config.profile.edit", id="edit"),
    ],
)
def test_wizard_success_json_emits_shared_spine_and_next_step_notice(
    mode: WizardPersistMode,
    command_path: str,
    capsys: pytest.CaptureFixture[str],
    _json_context: None,
) -> None:
    """JSON mode emits the shared envelope spine with the next-step as a Notice.

    Locks the ``cli-notices-are-the-only-diagnostic-channel`` contract for
    the wizard verbs: the JSON emit carries the shared spine
    (``schema_version`` / ``command`` / ``status`` / ``result`` /
    ``notices``), and the post-create / post-edit hint rides on the
    ``notices`` channel as an ``info``-severity :class:`Notice` whose
    ``suggestion`` is the follow-on command — never as a bespoke ``next``
    field smuggled into ``result``. (The registered-``OutputSchema``
    coverage of these command paths is owned by the entrypoints conformance
    gate; this application-layer test asserts the runtime emit contract
    without reaching up into the entrypoints registry.)
    """
    _emit_wizard_success(mode, "probe-profile")

    document = json.loads(capsys.readouterr().out)

    assert set(document) == {"schema_version", "command", "status", "result", "notices"}
    assert document["command"] == command_path
    assert document["status"] == "success"

    result = document["result"]
    assert "next" not in result
    assert "suggestion" not in result

    notices = document["notices"]
    assert len(notices) == 1
    notice = notices[0]
    assert notice["severity"] == "info"
    assert notice["code"] == f"{command_path}.next_step"
    assert notice["suggestion"] == "aeat app modelo work create"
