"""Real clean-root refusal, profile recovery, and guarded-command retry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from ....adapters.persistence.storage.master_key import close_active_bucket_session
from ....application.operator_actions import OPERATOR_ACTION_CATALOGUE
from ....application.workflow.profile_bucket_scan import read_profile_bucket
from ....core.bucket_pointer import read_pointer
from ....core.errors.error_codes import ErrorCategory, get_error_exit_code
from ....tests.cli_runner import invoke_cached_cli, semantic_cli_output
from ....tests.secure_sql import isolated_profile_storage_root
from .._verb_input_schema import build_verb_input_schemas, cli_argv_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ORIGINAL_ARGUMENTS = (
    "app",
    "ledger",
    "ratios",
    "set",
    "vehiculo_combustible",
    "0.5",
)
_ORIGINAL_LEAF_KEY = "ledger.ratios.set"
_FAILED_CONDITION_ID = "profile.active"
_RECOVERY_ACTION_ID = "operator.profile.create"


def _json_object(raw: str) -> dict[str, object]:
    document = json.loads(raw)
    assert isinstance(document, dict)
    return cast(dict[str, object], document)


def test_clean_root_refusal_executes_projected_profile_recovery_then_retries(
    tmp_path: Path,
) -> None:
    """A real guarded mutation recovers through its live-schema action and persists."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        text_refusal = invoke_cached_cli(
            _ORIGINAL_ARGUMENTS,
            catch_exceptions=False,
        )

        assert text_refusal.exit_code == get_error_exit_code(ErrorCategory.REFUSED), text_refusal.output
        text = semantic_cli_output(text_refusal)
        assert f"  command: {_ORIGINAL_LEAF_KEY}" in text
        assert f'  action.failed_condition_id: "{_FAILED_CONDITION_ID}"' in text
        assert '"evidence_id":"profile.active.storage_route"' in text
        assert (
            '  action.action: {"action_id":"operator.profile.create",'
            '"cli_path":["config","profile","create"],'
            '"target_command_key":"config.profile.create"}'
        ) in text
        assert '"argument_name":"profile_name"' in text
        assert '  action.missing_argument_names: ["profile_name"]' in text
        assert '  action.conditionality: "requires_arguments"' in text
        assert "  action.no_recovery_outcome: null" in text
        assert "suggestion:" not in text

        json_refusal = invoke_cached_cli(
            ("--format", "json", *_ORIGINAL_ARGUMENTS),
            catch_exceptions=False,
        )

        assert json_refusal.exit_code == get_error_exit_code(ErrorCategory.REFUSED), json_refusal.output
        assert json_refusal.stdout == ""
        refusal_document = _json_object(json_refusal.stderr)
        assert refusal_document["command"] == _ORIGINAL_LEAF_KEY
        error = cast(dict[str, object], refusal_document["error"])
        assert "suggestion" not in error
        projected = cast(dict[str, object], error["action"])
        assert projected == {
            "failed_condition_id": _FAILED_CONDITION_ID,
            "evidence": [
                {
                    "condition_id": _FAILED_CONDITION_ID,
                    "evidence_id": "profile.active.storage_route",
                    "provenance": "runtime_observation",
                    "values": {
                        "active_bucket_attached": False,
                        "active_profile_present": False,
                        "route_kind": "root_fallback_database",
                    },
                }
            ],
            "action": {
                "action_id": _RECOVERY_ACTION_ID,
                "cli_path": ["config", "profile", "create"],
                "target_command_key": "config.profile.create",
            },
            "argument_bindings": [
                {
                    "argument_name": "profile_name",
                    "status": "missing",
                    "value": None,
                    "source": None,
                    "source_key": None,
                    "source_evidence_id": None,
                }
            ],
            "missing_argument_names": ["profile_name"],
            "conditionality": "requires_arguments",
            "no_recovery_outcome": None,
        }

        projected_action = cast(dict[str, object], projected["action"])
        action_id = cast(str, projected_action["action_id"])
        target_command_key = cast(str, projected_action["target_command_key"])
        catalogue_entry = OPERATOR_ACTION_CATALOGUE.lookup(action_id)
        assert action_id == _RECOVERY_ACTION_ID
        assert target_command_key == catalogue_entry.target_command_key

        live_schema = build_verb_input_schemas((target_command_key,))[target_command_key]
        missing_argument_names = cast(list[str], projected["missing_argument_names"])
        live_parameter_names = {parameter.name for parameter in live_schema.parameters}
        assert set(missing_argument_names) <= live_parameter_names

        recovery_input: dict[str, object] = {
            "profile_name": "recovered",
            "quiet": True,
            "entity_type": "natural_person",
            "tax_id": "12345678Z",
            "name": "Recovered",
            "surnames": "Operator",
            "activity": "design",
            "iva_regime": "GENERAL",
        }
        assert set(missing_argument_names) <= recovery_input.keys()
        recovery_argv = cli_argv_for(live_schema, recovery_input)

        recovery = invoke_cached_cli(recovery_argv, catch_exceptions=False)

        assert recovery.exit_code == 0, recovery.output
        recovery_document = _json_object(recovery.stdout)
        assert recovery_document["command"] == target_command_key
        assert recovery_document["active_profile"] == "recovered"
        assert recovery_document["result"] == {
            "profile_name": "recovered",
            "status": "created",
            "active_profile": "recovered",
        }
        active_pointer = read_pointer(storage_root)
        registered_profile = read_profile_bucket("recovered")
        assert active_pointer.bucket_id is not None
        assert registered_profile is not None
        assert registered_profile.bucket_id == active_pointer.bucket_id

        close_active_bucket_session()
        assert read_pointer(storage_root) == active_pointer

        retry = invoke_cached_cli(
            ("--format", "json", *_ORIGINAL_ARGUMENTS),
            catch_exceptions=False,
        )

        assert retry.exit_code == 0, retry.output
        retry_document = _json_object(retry.stdout)
        assert retry_document["command"] == _ORIGINAL_LEAF_KEY
        assert retry_document["active_profile"] == "recovered"
        assert retry_document["status"] == "success"
        assert retry_document["result"] == {
            "bucket_id": "<bucket-id>",
            "category": "vehiculo_combustible",
            "ratio": "0.5",
        }

        close_active_bucket_session()
        persisted = invoke_cached_cli(
            ("--format", "json", "app", "ledger", "ratios", "list"),
            catch_exceptions=False,
        )

        assert persisted.exit_code == 0, persisted.output
        persisted_document = _json_object(persisted.stdout)
        assert persisted_document["command"] == "ledger.ratios.list"
        assert persisted_document["active_profile"] == "recovered"
        assert persisted_document["result"] == {
            "bucket_id": "<bucket-id>",
            "rows": [{"category": "vehiculo_combustible", "ratio": "0.5"}],
            "count": 1,
            "censo_mismatch": None,
        }
