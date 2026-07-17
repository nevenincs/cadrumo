---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---

# Enumerate the actual inline revision set at HEAD by grep for inline binding and formula tables in revision.toml, confirming it against the ADR list before migrating

## Scope

- `src/aeat/_data/registry/aeat/modelos`

## Description

- Grep every `revision.toml` under the modelos tree for inline array-table headers, handling BOTH quoted (`[revisions."id"]`) and unquoted (`[revisions.id]`) revision keys.
- Cross-check the discovered set against the ADR's enumerated list.

## Outcome

The authoritative inline set at HEAD is FOURTEEN revisions across eleven modelos: 117, 126, 128, 187, 188, 194, 231, 296, 361 (each 2019/2021/2024/2010 revision), 303 (both `2009-y-siguientes` AND `2023-y-siguientes`), and 369 (all THREE schemas: `esquema-exterior`, `esquema-importacion`, `esquema-union`).

Three discrepancies from the ADR's list were found and resolved in favour of the grep (the ADR wrote "at least ten" and the plan mandated re-enumeration at HEAD): modelo 296 is inline but was omitted from the ADR; 303 `2023-y-siguientes` is inline but the ADR named only `2009`; and 369 has three schemas, not "both" (two). The definition-of-done is zero inline, so all fourteen are in scope.

An initial grep pattern missed 303 entirely because 303 authors its revision keys UNQUOTED; the corrected pattern accepts both key styles.

## Notes

At enumeration time, eight of the fourteen revisions carry live peer WIP in their `revision.toml` (a peer campaign is adding workflow `application_links` inline to 117/126/128/187/188/194/296, and 303/2023 has uncommitted edits). Those are deferred per the shared-worktree WIP discipline; only the six clean revisions (231, 361, 369×3, 303/2009) are migrated in this campaign pass.
