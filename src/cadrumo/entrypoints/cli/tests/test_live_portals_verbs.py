"""CLI surface tests for `aeat app live portals {list, show}`."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

import pytest
from click.testing import Result

from ....core.i18n import tr
from ....domain.portals import PORTAL_REGISTRY
from ....domain.portals._errors import PortalRegistryInvariant, portal_integrity_error
from ....tests.cli_runner import invoke_cached_cli
from .._app_live_portals_cli import _project_portal_refusal
from .._common import cli_policy_refusal_projection

# INTENTIONAL: integration because it exercises the portals CLI surface over the static
# portal registry without contacting AEAT.
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke_portals(args: Sequence[str]) -> Result:
    return invoke_cached_cli(["app", "live", "portals", *args])


def _assert_exact_terminal_action(
    result: Result,
    *,
    condition_id: str,
    evidence: dict[str, object],
) -> None:
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["command"] in {"app.live.portals.list", "app.live.portals.view"}
    action = payload["error"]["action"]
    assert action == {
        "failed_condition_id": condition_id,
        "evidence": [
            {
                "condition_id": condition_id,
                "evidence_id": f"{condition_id}.observation",
                "provenance": "runtime_observation",
                "values": evidence,
            }
        ],
        "action": None,
        "argument_bindings": [],
        "missing_argument_names": [],
        "conditionality": "not_applicable",
        "no_recovery_outcome": "operator_decision",
    }


def test_portals_list_emits_every_registered_entry() -> None:
    result = _invoke_portals(["list"])
    assert result.exit_code == 0, result.output
    assert f"count\t{len(PORTAL_REGISTRY)}" in result.output


def test_portals_list_does_not_emit_raw_translation_keys() -> None:
    """Portal labels must be resolved, not dumped as raw i18n key paths.

    `metadata.label` / `metadata.purpose` are Translatable keys
    (`entries.portal_*.label`). A bare `str()` leaked the raw key
    path into the operator-facing list output.
    """

    result = _invoke_portals(["list"])
    assert result.exit_code == 0, result.output
    # No `entries.portal_*` translation-key path reaches the operator.
    assert "entries.portal_" not in result.output, result.output


def test_portals_view_does_not_emit_raw_translation_keys() -> None:
    """The single-entry `view` surface must also resolve portal labels."""

    portal = next(iter(PORTAL_REGISTRY.values()))
    result = _invoke_portals(["view", portal.portal.value])
    assert result.exit_code == 0, result.output
    assert "entries.portal_" not in result.output, result.output


def test_portals_list_resolves_genuine_labels() -> None:
    """Every portal label must resolve to a real translation, not a raw-key fallback.

    When a label key carries no locale entry, ``tr()`` falls back to a
    humanised key segment such as ``Label 323061``. A genuine catalogue
    name never matches that ``Label <digits>`` shape, so its absence
    proves the locale catalogue actually carries the translations.
    """

    result = _invoke_portals(["list"])
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


def test_portals_list_refuses_mutually_exclusive_filters() -> None:
    result = _invoke_portals(["list", "--category", "censal", "--modelo", "303"])
    assert result.exit_code != 0


def test_portals_list_refuses_unknown_category() -> None:
    result = _invoke_portals(["list", "--category", "not-a-category"])
    assert result.exit_code != 0


def test_portals_show_emits_one_entry() -> None:
    portal = next(iter(PORTAL_REGISTRY.values()))
    result = _invoke_portals(["view", portal.portal.value])
    assert result.exit_code == 0, result.output
    assert f"portal\t{portal.portal.value}" in result.output


def test_portals_show_refuses_unknown_portal() -> None:
    portal_id = "NOT_A_PORTAL_ID"
    result = invoke_cached_cli(["--format", "json", "app", "live", "portals", "view", portal_id])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    _assert_exact_terminal_action(
        result,
        condition_id="portals.registry.portal.registered",
        evidence={"portal": portal_id, "portal_registered": False},
    )


def test_portals_list_refuses_malformed_modelo_with_a_typed_envelope() -> None:
    modelo = "not-a-modelo"
    result = invoke_cached_cli(["--format", "json", "app", "live", "portals", "list", "--modelo", modelo])

    _assert_exact_terminal_action(
        result,
        condition_id="portals.registry.modelo_code.recognised",
        evidence={"modelo": modelo, "modelo_code_recognised": False},
    )


def test_portal_integrity_refusal_reaches_the_cli_boundary_as_safety() -> None:
    error = portal_integrity_error(
        PortalRegistryInvariant.PORTAL_ENTRY_UNIQUE,
        facts={"portal": "portal_test", "entry_unique": False},
    )

    projection = cli_policy_refusal_projection(_project_portal_refusal(error))

    assert projection is not None
    assert projection.precondition_action.model_dump(mode="json") == {
        "failed_condition_id": "portals.registry.integrity.valid",
        "evidence": [
            {
                "condition_id": "portals.registry.integrity.valid",
                "evidence_id": "portals.registry.integrity.valid.observation",
                "provenance": "application_state",
                "values": {
                    "invariant": "portal_entry_unique",
                    "portal": "portal_test",
                    "entry_unique": False,
                },
            }
        ],
        "action": None,
        "argument_bindings": [],
        "missing_argument_names": [],
        "conditionality": "not_applicable",
        "no_recovery_outcome": "safety",
    }
