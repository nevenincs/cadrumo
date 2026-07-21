---
name: operator-harness-cites-live-cli-surface
---

# Operator harness documents cite only the live CLI surface

## Rule

Every operator agent-harness document — each operator rule, persona, and skill
under `src/cadrumo/_data/agent/` — that names a CLI verb (an `aeat ...` invocation)
or a JSON-envelope field MUST cite only verbs that resolve against the live
operator-surface manifest and fields that exist on the live envelope models, and
MUST be co-committed with the CLI surface it couples to. A harness document and
the verb or field it teaches move in the same change, or the document orphans the
operator.

## Why

The harness is the operating layer an LLM tax-advisor loads to drive the
deterministic CLI; a rule, persona, or skill that cites a renamed or non-existent
verb hands the agent a dead instruction it cannot recover from — the operator-side
form of the verb-drift failure the `aeat-cli-pull-and-file-standard` rule exists
to prevent. During the agent-harness build a safety rule cited `aeat app modelo
work export`, which does not exist (the real verb is `aeat app modelo export`); the
drift gate caught it before commit. The gate
(`src/cadrumo/agent/tests/test_rule_surface_conformance.py`) parses every shipped
rule, persona, and skill, extracts each `aeat ...` command path and each named
envelope-spine field, and asserts they all resolve against the live manifest and
the real `SchemaEnvelope`/`Notice` models, so a drift is a loud test failure rather
than a silent operator misdirection.

## How

- **Good:** a skill that tells the operator to run `aeat app modelo work calculate`
  cites the verb exactly as the CLI exposes it; the drift gate confirms it resolves
  and the change ships with any coupled CLI surface.
- **Good:** a rule that instructs the operator to read the envelope `status` or a
  notice `suggestion` names a field the gate confirms still exists on the live
  model.
- **Bad:** authoring `aeat app modelo work export` (a verb that does not exist) or
  citing a renamed/removed envelope field — the gate fails until the citation
  matches the live surface.
- **Bad:** renaming a CLI verb without sweeping the harness documents that cite it,
  leaving the operator a dead instruction.

## Source

Authored during the agent-harness framework build (ADR
`2026-06-30-agent-harness-adr`, plan step W05.P13.S54), codifying the discipline
the rule-surface drift gate enforces. Companion to `aeat-cli-pull-and-file-standard`
(CLI verb naming), `cli-notices-are-the-only-diagnostic-channel` (the envelope
fields the rules cite), and `aeat-architecture-boundaries` (the two-root surface).
