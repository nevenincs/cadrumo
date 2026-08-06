"""Structured tool-result summaries stay within a size budget.

Structured output double-emits (text + structuredContent, ~2x tokens), so a verb
whose structured result is very large inflates every call. This gate bounds the
per-verb output-schema size - the static proxy for the structured content a verb
emits - so a newly-added bulky result shape trips the budget and must move its
bulk arrays to a ``resource_link`` rather than inlining them.

The gate is intentionally static (it reads the registered output schemas, no CLI
run), so it is a cheap always-on lock; reducing what a tripping verb returns is
the follow-on remediation, verb by verb.

Two things about the instrument, learned by tripping it. The measured schema
includes docstring-derived ``description`` text the repository separately
mandates, so the number is not purely a payload measure and a genuine payload
fix can still read over -- a known impurity, not a licence to delete
documentation. And roughly 4700 chars of every verb's total is the shared
envelope spine, which no payload change can touch, so the verb-specific
allowance is materially smaller than the headline budget.
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
        f"output schemas over the {_OUTPUT_SCHEMA_BUDGET_CHARS}-char budget: {over}. "
        "Reduce what the verb RETURNS -- summarise a nested collection and let the "
        "caller fetch detail per item. Moving bulk rows to a resource_link works only "
        "where those rows are PERSISTED and a read verb can resolve them again; a verb "
        "computed from a clock has nothing to resolve against. Note also that roughly "
        "4700 chars are envelope spine no payload change can touch, so the verb-specific "
        "allowance is well under the headline budget."
    )


def test_the_budget_would_flag_a_hypothetically_oversized_schema() -> None:
    # Anti-tautology: a synthetic oversized schema trips the check, proving teeth.
    huge: dict[str, object] = {
        "type": "object",
        "properties": {f"field_{i}": {"type": "string"} for i in range(4000)},
    }
    assert _schema_size(huge) > _OUTPUT_SCHEMA_BUDGET_CHARS
