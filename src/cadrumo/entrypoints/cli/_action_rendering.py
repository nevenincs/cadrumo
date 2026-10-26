"""Canonical CLI text projection for resolved precondition-action DTOs.

The CLI presents recovery data only as the typed
``ResolvedPreconditionAction`` returned by the application verdict projection.
This helper serializes that exact DTO for tabular text output; it neither
derives a command nor authors recovery prose.
"""

from __future__ import annotations

import json

from ...core.json_contract import ResolvedPreconditionAction


def resolved_precondition_action_json_cell(action: ResolvedPreconditionAction | None) -> str:
    """Render a resolved action DTO as one deterministic text-table cell."""
    value = None if action is None else action.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
