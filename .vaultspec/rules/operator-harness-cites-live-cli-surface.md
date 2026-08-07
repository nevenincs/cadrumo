# Operator harness documents cite only the live CLI surface

## Rule

Every operator agent-harness document — each operator rule, persona, and skill
under `src/cadrumo/_data/agent/` — that names a CLI verb (an `aeat ...`
invocation) or a JSON-envelope field MUST cite only verbs that resolve against
the live operator-surface manifest and fields that exist on the live envelope
models, and MUST be co-committed with the CLI surface it couples to. A harness
document and the verb or field it teaches move in the same change.

## Why

The harness is the operating layer an LLM tax advisor loads to drive the
deterministic CLI. A rule, persona, or skill citing a renamed or non-existent
verb hands the agent a dead instruction it cannot recover from — the
operator-side form of the verb drift that `aeat-cli-pull-and-file-standard`
exists to prevent. During the harness build a safety rule cited a verb that does
not exist, and the drift gate caught it before commit.

`src/cadrumo/agent/tests/test_rule_surface_conformance.py` parses every shipped
rule, persona, and skill, extracts each `aeat ...` command path and each named
envelope-spine field, and asserts they resolve against the live manifest and the
real envelope and notice models — so drift is a loud test failure rather than a
silent operator misdirection.

## How

- **Good:** a skill telling the operator to run a verb cites it exactly as the
  CLI exposes it, and ships with any coupled CLI change.
- **Good:** a rule instructing the operator to read the envelope `status` or a
  notice `suggestion` names a field the gate confirms still exists.
- **Bad:** citing a verb that does not exist, or a renamed or removed envelope
  field.
- **Bad:** renaming a CLI verb without sweeping the harness documents that cite
  it.

## Source

ADR `2026-06-30-agent-harness-adr`. Companions:
`aeat-cli-pull-and-file-standard`,
`cli-notices-are-the-only-diagnostic-channel`,
`aeat-architecture-boundaries`.
