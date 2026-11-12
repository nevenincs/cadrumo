"""The literal operator action a corrupt active-profile pointer must produce."""

from __future__ import annotations

from pathlib import Path

from .served_action_expectation import served_action_words


def corrupt_pointer_action(pointer_file: Path, language: str) -> dict[str, object]:
    """Return the serialized action the error boundary projects for a corrupt pointer at ``pointer_file``.

    ``language`` is the language the projection served its action words in; the
    repair command submits no registered operation, so no target operation is named.
    """
    return {
        **served_action_words("operator.profile.repair_active_pointer", language),
        "failed_condition_id": "profile.active.pointer.valid",
        "evidence": [
            {
                "condition_id": "profile.active.pointer.valid",
                "evidence_id": "profile.active.pointer.corruption",
                "provenance": "runtime_observation",
                "values": {
                    "path": str(pointer_file),
                    "pointer_corrupt": True,
                    "root_fallback_refused": True,
                },
            },
        ],
        "action": {
            "action_id": "operator.profile.repair_active_pointer",
            "target_command_key": "config.repair.profile",
            "cli_path": ["aeat", "config", "repair", "profile"],
        },
        "argument_bindings": [
            {
                "argument_name": "clear_active",
                "status": "resolved",
                "value": True,
                "source": "operator_action.verdict_context",
                "source_key": "clear_active",
                "source_evidence_id": None,
            },
            {
                "argument_name": "yes",
                "status": "missing",
                "value": None,
                "source": None,
                "source_key": None,
                "source_evidence_id": None,
            },
        ],
        "missing_argument_names": ["yes"],
        "conditionality": "requires_arguments",
        "no_recovery_outcome": None,
    }
