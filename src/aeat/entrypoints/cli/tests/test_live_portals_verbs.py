"""CLI surface tests for `aeat app live portals {list, show}`."""

from __future__ import annotations

import re

import pytest
from typer.testing import CliRunner

from ....core.errors import resolve_error_message
from ....core.i18n import tr
from ....domain.portals import PORTAL_REGISTRY, UnknownPortalError
from .._app_live import portals_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_portals_list_emits_every_registered_entry(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(portals_app, ["list"])
    assert result.exit_code == 0, result.output
    assert f"count\t{len(PORTAL_REGISTRY)}" in result.output


def test_portals_list_does_not_emit_raw_translation_keys(cli_runner: CliRunner) -> None:
    """Portal labels must be resolved, not dumped as raw i18n key paths.

    `metadata.label` / `metadata.purpose` are Translatable keys
    (`entries.portal_*.label`). A bare `str()` leaked the raw key
    path into the operator-facing list output.
    """

    result = cli_runner.invoke(portals_app, ["list"])
    assert result.exit_code == 0, result.output
    # No `entries.portal_*` translation-key path reaches the operator.
    assert "entries.portal_" not in result.output, result.output


def test_portals_view_does_not_emit_raw_translation_keys(cli_runner: CliRunner) -> None:
    """The single-entry `view` surface must also resolve portal labels."""

    portal = next(iter(PORTAL_REGISTRY.values()))
    result = cli_runner.invoke(portals_app, ["view", portal.portal.value])
    assert result.exit_code == 0, result.output
    assert "entries.portal_" not in result.output, result.output


def test_portals_list_resolves_genuine_labels(cli_runner: CliRunner) -> None:
    """Every portal label must resolve to a real translation, not a raw-key fallback.

    When a label key carries no locale entry, ``tr()`` falls back to a
    humanised key segment such as ``Label 323061``. A genuine catalogue
    name never matches that ``Label <digits>`` shape, so its absence
    proves the locale catalogue actually carries the translations.
    """

    result = cli_runner.invoke(portals_app, ["list"])
    assert result.exit_code == 0, result.output
    assert not re.search(r"\bLabel \d+\b", result.output), result.output


def test_every_portal_label_has_a_translation() -> None:
    """The portal-catalogue label key must resolve to a genuine catalogue value."""

    for metadata in PORTAL_REGISTRY.values():
        key = str(metadata.label)
        rendered = tr(key)
        assert rendered != key, key
        # `_humanise_key` fallbacks surface the final dotted segment, e.g.
        # `Label` — a genuine translation is never the bare word.
        assert rendered.lower() != "label", key


def test_portals_list_refuses_mutually_exclusive_filters(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(portals_app, ["list", "--category", "censal", "--modelo", "303"])
    assert result.exit_code != 0


def test_portals_list_refuses_unknown_category(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(portals_app, ["list", "--category", "not-a-category"])
    assert result.exit_code != 0


def test_portals_show_emits_one_entry(cli_runner: CliRunner) -> None:
    portal = next(iter(PORTAL_REGISTRY.values()))
    result = cli_runner.invoke(portals_app, ["view", portal.portal.value])
    assert result.exit_code == 0, result.output
    assert f"portal\t{portal.portal.value}" in result.output


def test_portals_show_refuses_unknown_portal(cli_runner: CliRunner) -> None:
    portal_id = "NOT_A_PORTAL_ID"
    result = cli_runner.invoke(portals_app, ["view", portal_id])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert resolve_error_message(UnknownPortalError(portal_id)) in result.output
