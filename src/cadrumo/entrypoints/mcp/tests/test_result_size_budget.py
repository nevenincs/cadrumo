"""Structured tool-result summaries stay within a size budget.

Structured output double-emits (text + structuredContent, ~2x tokens), so a verb
whose structured result is very large inflates every call. This gate bounds the
per-verb output-schema size - the static proxy for the structured content a verb
emits - so a newly-added bulky result shape trips the budget and must move its
bulk arrays to a ``resource_link`` rather than inlining them.

The gate is intentionally static (it reads the registered output schemas, no CLI
run), so it is a cheap always-on lock; the runtime resource-link thinning of a
verb that trips it is the follow-on remediation, verb by verb.
"""

from __future__ import annotations

import json

import pytest

from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# The per-verb output-schema serialized-size ceiling. Set with headroom above the
# current maximum so it locks the posture without churn, yet catches a doubling.
_OUTPUT_SCHEMA_BUDGET_CHARS = 18000


def _schema_size(schema: dict[str, object]) -> int:
    return len(json.dumps(schema, ensure_ascii=False, sort_keys=True))


def test_no_verb_output_schema_exceeds_the_size_budget() -> None:
    over = [
        (descriptor.command_key, _schema_size(descriptor.output_schema))
        for descriptor in build_tool_descriptors()
        if _schema_size(descriptor.output_schema) > _OUTPUT_SCHEMA_BUDGET_CHARS
    ]
    assert over == [], (
        f"output schemas over the {_OUTPUT_SCHEMA_BUDGET_CHARS}-char budget "
        f"(move bulk arrays to a resource_link): {over}"
    )


def test_the_budget_would_flag_a_hypothetically_oversized_schema() -> None:
    # Anti-tautology: a synthetic oversized schema trips the check, proving teeth.
    huge: dict[str, object] = {
        "type": "object",
        "properties": {f"field_{i}": {"type": "string"} for i in range(4000)},
    }
    assert _schema_size(huge) > _OUTPUT_SCHEMA_BUDGET_CHARS
