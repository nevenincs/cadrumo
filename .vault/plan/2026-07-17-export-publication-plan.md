---
tags:
  - '#plan'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
tier: L1
related:
  - '[[2026-07-15-cli-authority-verb-conformance-adr]]'
  - '[[2026-07-16-cli-authority-verb-conformance-duplication-authority-audit]]'
  - '[[2026-07-17-cli-authority-verb-conformance-audit]]'
  - '[[2026-07-15-cli-authority-verb-conformance-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace export-publication with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorizing documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `export-publication` plan

- [ ] `S01` - Define typed portable-transfer and subject-access export purposes, requests, results, target identity, and categories derived from the actual portable bundle schema and carried registered namespaces while keeping sealed recovery archives separate; `src/cadrumo/application/user_profile/_bundle_export_contracts.py`.
- [ ] `S02` - Persist non-secret profile export operation states atomically outside the target artifact; `src/cadrumo/application/user_profile/_bundle_export_operation.py`.
- [ ] `S03` - Implement one locked target serialization with restrictive temporary files, file fsync, durable PREPARED state, atomic replace, parent-directory fsync, post-publish COMPLETED event, and honest PREPARED recovery; `src/cadrumo/application/user_profile/_bundle_export.py`.
- [ ] `S04` - Re-export the typed profile export service as the sole public export orchestration API; `src/cadrumo/application/user_profile/__init__.py`.
- [ ] `S05` - Prove portable-transfer and subject-access purposes use the same service and bundle schema, derive categories from serialized fields and registry-carried namespaces, and retain distinct purpose metadata; `src/cadrumo/application/user_profile/tests/test_bundle_export.py`.
- [ ] `S06` - Prove restrictive temporary permissions, same-target exclusion, every PREPARED and replace crash window, parent-directory durability, and fresh-process reconciliation without premature completion events; `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`.
- [ ] `S07` - Route both config profile export and subject-access-request through the sole portable-export application service and remove direct serialization, target writes, completion events, and static SAR category ownership from the CLI; `src/cadrumo/entrypoints/cli/_config/_profile_export.py`.
- [ ] `S08` - Migrate the export family help, risk, and cleartext handoff-risk metadata to the accepted grammar with equal classification for both purposes; `src/cadrumo/application/operator_surface/_risk_table.py`.
- [ ] `S09` - Regenerate the operator reference pages for portable export and subject access from the frozen live surface; `docs/reference/import-export-and-evidence.md`.
<!-- One-line headline summary plan. -->

## Description

Collapse two CLI-owned export writers onto one durable publication service. Portable profile export and the subject-access request each independently implement serialization, directory creation, publication, and event sequencing from inside the CLI. That is two parallel writers for the same durable artifact, each with its own crash behaviour, and neither with a recoverable preparation state.

The accepted authority is one export service carrying portable-transfer and subject-access as typed purposes rather than as separate implementations. It owns same-target locking, recoverable preparation, atomic publication, and schema-derived categories. Categories are derived from the actual bundle schema and the registered namespaces the bundle carries, not from a static list hand-maintained in the CLI that silently drifts from what the bundle actually contains.

Publication is the delicate part. The service serializes to a restrictive temporary file, fsyncs it, records a durable prepared state, atomically replaces the target, fsyncs the parent directory, and only then emits the completion event. A crash in any window recovers honestly: a prepared state that never published is reported as prepared, not as complete, and the completion event never fires for an artifact that was not durably published.

The decision record keeps these purposes distinct while sharing machinery. Portable export and subject-access export have different purposes and different legal discoverability, so their purpose metadata stays distinct even though the publication path is shared. The sealed recovery archive has different confidentiality and restoration semantics and stays entirely separate; it is not folded into this service. Both purposes carry equal cleartext handoff-risk classification, because the artifact each produces is equally readable once it leaves the vault.

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorizing documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

The contract, operation-state, and serialization steps carry hard ordering: the typed purposes and requests must exist before the operation state can reference them, and both must exist before the locked serialization can compose them. The public re-export follows the service. The two proof steps run against the finished service. The CLI routing step depends on the service being the sole public orchestration API. The risk metadata and regenerated reference pages run last, from the frozen live surface.

This plan depends on stable profile and storage authorities, which are landed. It shares no files with the reset, evidence, or custody plans and may run in parallel with them.

## Verification

Crash-window suites pass: every prepared and replace crash window recovers honestly in a fresh process, with restrictive temporary permissions, parent-directory durability, same-target exclusion under concurrent export, and no premature completion event for an artifact that was not durably published.

Both purposes provably use the same service and the same bundle schema, and their categories are derived from serialized fields and registry-carried namespaces rather than a static CLI-owned list, while their distinct purpose metadata survives.

The CLI owns no direct serialization, target write, completion event, or static subject-access category list; the export service is the sole public orchestration API.

Both purposes carry equal cleartext handoff-risk classification, and the sealed recovery archive remains separate with its own semantics intact.

A fresh-context honesty review runs against this plan's closure summary before the plan is declared complete.

