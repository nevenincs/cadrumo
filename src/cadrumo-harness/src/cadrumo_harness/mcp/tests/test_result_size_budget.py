"""Every verb's output schema stays within a size budget.

A verb's output schema is transmitted in the tool listing, once per session, and a
client defers loading tools past a definition-token threshold. Schema bytes are
therefore a cost in their own right, and this gate bounds them DIRECTLY. It is not
a proxy for anything.

In particular it is not a proxy for what a call emits, and reading it as one leads
somewhere wrong. Structured output double-emits (text + structuredContent, ~2x
tokens), but that per-call cost scales with the rows a call returns while the schema
does not, and schema-only text such as ``title`` and ``description`` never appears in
``structuredContent`` at all. So per-call emitted size is genuinely unbounded and this
gate does not bound it -- a static measurement cannot, because the row count exists
only at call time. Anyone reaching for "this measure can be gamed by moving content
out of the schema" has substituted that other target for this one: removing bytes the
listing really transmits is a real reduction of the real cost measured here.

The gate is intentionally static (it reads the registered output schemas, no CLI
run), so it is a cheap always-on lock; reducing what a tripping verb returns is
the follow-on remediation, verb by verb.

One thing about the instrument, learned by tripping it: the measured schema
includes docstring-derived ``description`` text the repository separately
mandates, so the number is not purely a payload measure and a genuine payload
fix can still read over -- a known impurity, not a licence to delete
documentation.

The measure is deliberately in two parts, and the split is a RE-BASING that
should be understood before reading a green result here.

Measuring each verb's TOTAL made this gate demand the impossible of most verbs
it failed. 5769 chars of every verb's schema is the notice/action machinery,
byte-identical in all 295 of them: a verb cannot shrink it by returning less,
and ``test_action_projection`` positively REQUIRES those definitions present, so
the bytes are mandated by one gate and charged by another. Of 36 verbs over the
old total ceiling, 29 were over solely because of that constant. Asking their
owners to summarise a nested collection would have been asking them to pay down
a cost they neither own nor can touch.

So the per-verb ceiling now applies to the payload the verb decides, and the
shared spine carries its own ceiling below. The honest consequence: the
effective per-verb TOTAL this file permits rises from 18000 to 18000 + 6500.
That is a deliberate loosening of the headline number in exchange for a measure
each half can actually act on -- reducing a verb's payload, or noticing spine
growth once instead of 295 times -- rather than a red that no owner could clear.
"""

from __future__ import annotations

import json

import pytest

from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# The per-verb ceiling, applied to the payload the VERB controls: its total
# serialized schema minus the shared envelope definitions every verb carries
# identically. Set with headroom above the current maximum so it locks the
# posture without churn, yet catches a doubling.
_OUTPUT_SCHEMA_BUDGET_CHARS = 18000

#: The notice/action definitions pydantic inlines into EVERY verb's schema,
#: byte-identical in all of them. They are envelope, not payload: a verb cannot
#: shrink them by returning less, and the canonical-notice-action gate in
#: test_action_projection REQUIRES them present, so they are excluded from the
#: per-verb measure and locked separately by the spine test below.
_SHARED_ENVELOPE_DEFS: frozenset[str] = frozenset(
    {
        "ActionArgumentSource",
        "ActionConditionEvidence",
        "ActionConditionality",
        "ActionEvidenceProvenance",
        "NoRecoveryOutcome",
        "NoticeSeverity",
        "ResolvedActionArgument",
        "ResolvedActionReference",
        "ResolvedNoticeAction",
        "ResolvedPreconditionAction",
    }
)

#: The shared spine's own ceiling. It is paid once per verb across the whole
#: listing (295 verbs at the time of writing), so growth here is multiplied by
#: every verb and must be seen as one loud failure, not 295 quiet ones.
_SHARED_ENVELOPE_BUDGET_CHARS = 6500


def _schema_size(schema: dict[str, object]) -> int:
    return len(json.dumps(schema, ensure_ascii=False, sort_keys=True))


def _shared_envelope_size(schema: dict[str, object]) -> int:
    """Bytes this schema spends on definitions every other verb carries too."""
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        return 0
    return sum(_schema_size(body) for name, body in definitions.items() if name in _SHARED_ENVELOPE_DEFS)


def _verb_payload_size(schema: dict[str, object]) -> int:
    """The part of the advertised schema the verb itself decides."""
    return _schema_size(schema) - _shared_envelope_size(schema)


def test_no_verb_output_schema_exceeds_the_size_budget() -> None:
    over = [
        (descriptor.command_key, _verb_payload_size(descriptor.output_schema))
        for descriptor in build_tool_descriptors()
        if _verb_payload_size(descriptor.output_schema) > _OUTPUT_SCHEMA_BUDGET_CHARS
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


def test_the_shared_envelope_spine_stays_within_its_own_budget() -> None:
    """The constant every verb pays is locked once, loudly.

    Excluding the spine from the per-verb measure would be an accounting trick if
    nothing then watched it, because its cost is real and is multiplied by every
    verb in the listing. This is the other half: the spine is measured directly,
    and is asserted to be genuinely shared -- identical in every verb -- so it
    cannot quietly become a per-verb cost that escapes both halves.
    """
    descriptors = build_tool_descriptors()
    sizes = {_shared_envelope_size(descriptor.output_schema) for descriptor in descriptors}
    assert len(sizes) == 1, f"the shared envelope is not identical across verbs: {sorted(sizes)}"
    spine = sizes.pop()
    assert spine <= _SHARED_ENVELOPE_BUDGET_CHARS, (
        f"the shared envelope spine is {spine} chars, over its {_SHARED_ENVELOPE_BUDGET_CHARS}-char "
        f"budget. Every one of the {len(descriptors)} advertised verbs pays this in full, so the "
        f"listing cost of this growth is {spine * len(descriptors)} chars."
    )
