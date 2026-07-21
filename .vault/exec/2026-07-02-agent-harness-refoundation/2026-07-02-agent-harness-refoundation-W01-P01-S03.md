---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S03'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add a domain-toolset grouping derived from the operator-surface manifest for renta, iva, ledger, censo, and modelo-lifecycle

## Scope

- `src/aeat/entrypoints/mcp/_toolsets.py`

## Description

- Add `_toolsets.py` declaring the closed `Toolset` StrEnum (renta, iva, ledger, censo, modelo-lifecycle) and a typed `ToolsetGroup` record.
- Derive `ledger` and `modelo-lifecycle` membership from the live operator-surface manifest domains; derive the three tax-concept toolsets from the command tree's own stable segment tokens (m036 and profile censo, the iva-wallet surface, the borrador draft).
- Compute membership against the live command keys so a verb added to any grouped surface joins its toolset automatically, and classify long-tail verbs as belonging to no curated toolset.
- Add real-behavior tests asserting per-toolset membership and derivation completeness against the live surface.

## Outcome

`build_toolsets` emits one group per toolset in declaration order: renta (3 borrador-draft keys), iva (8 wallet keys across live and modelo), ledger (58 keys, the whole LEDGER domain), censo (9 keys spanning modelo 036 and the profile census sync), and modelo-lifecycle (44 remaining modelo keys, the tax-concept carve-outs excluded). Long-tail verbs such as `overview.status` belong to no curated toolset and fall to the meta-tool fallback. Ruff check/format clean; the mcp suite is green at 55 passed.

## Notes

The five toolset names are finer than the family-granular manifest can express (renta, iva, and censo are tax concepts, not manifest domains), so those three key on the command tree's own segment tokens rather than a manifest domain. Membership is still computed over the live key set, not a hand-listed verb frozenset, so the console cannot drift from the CLI. The only pyright diagnostic on the module is the pre-existing dynamic-re-export typing of `command_schema_refs`, identical to the one already present on `_tools.py` at HEAD.
