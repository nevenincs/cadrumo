---
tags:
  - '#plan'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-13'
tier: L3
related:
  - '[[2026-06-13-semantic-dedup-epic-audit]]'
  - '[[2026-06-13-semantic-dedup-epic-adr]]'
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

<!-- RETIRED: W02, P04, S08, S09, S10, S11, S12, S13, S14 -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
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

# `semantic-dedup-epic` plan

## Wave `W01` - Pass 1 — Confirmed Duplication Removal

Remove the three confirmed real-duplication clusters from discovery Pass 1 (F1 tax-id, F2 dormant fichero money stack, F3 bucket-id boilerplate). Each step names a per-file site and its action with a verification gate.

<!-- One-line headline summary plan. -->

### Phase `W01.P01` - F1 — Consolidate Spanish tax-id validation

Collapse the duplicated NIF/NIE/CIF validation and control-letter computation in core/identity/_tax_id.py and core/identity/_documents.py onto one owning core, re-expressing both public surfaces over it.

- [ ] `W01.P01.S01` - Delegate _compute_nif_check_letter to the canonical nif_check_letter single source and remove the duplicate _NIF_LETTERS control-letter table; `src/aeat/core/identity/_documents.py`.
- [ ] `W01.P01.S02` - Consolidate the duplicated _validate_nif/_validate_nie/_validate_cif core into one owning module and re-express the other module's validators over it; `src/aeat/core/identity/_tax_id.py`.
- [ ] `W01.P01.S03` - Migrate the dual-module consumer to a single import site and run the identity validation test suite green; `src/aeat/domain/calculations/registry/_schema_scalars.py`.

### Phase `W01.P02` - F2 — Remove dormant fichero-BOE _formats money stack

Prove the adapters/outbound/aeat/export/_formats currency encode/serialise/deserialise stack has zero production consumers, then delete it or record an explicit retention rationale.

- [x] `W01.P02.S04` - Prove tree-wide that the _formats currency encode/serialise/deserialise path has zero production consumers outside its own package and tests; `src/aeat/adapters/outbound/aeat/export/_formats/_serialise.py`.
- [ ] `W01.P02.S05` - Delete the dormant _formats currency encode/serialise/deserialise path and its tests, or record an explicit retention rationale if a near-term consumer is planned; `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`.

### Phase `W01.P03` - F3 — Extract shared repository bucket-id resolver

Replace the per-domain copy-pasted explicit-or-active-bucket resolver bodies with one shared helper parameterised by error_type.

- [x] `W01.P03.S06` - Add one shared resolve_repository_bucket_id helper parameterised by error_type as the single explicit-or-active-bucket resolver; `src/aeat/core/identity/_bucket.py`.
- [x] `W01.P03.S07` - Redirect every per-domain resolve_*_repository_bucket_id function to the shared helper and remove the copied bodies; `src/aeat/domain/filing/_runtime_repository.py`.

## Wave `W03` - Pass 3 — Structural Sweep Removal

Clean duplications surfaced by the whole-tree structural symbol sweep (production function names defined in 3+ files), confirmed fully substitutable and landed.

### Phase `W03.P05` - F5 — Consolidate storage_validation_error factory

Promote one canonical storage_validation_error to storage/errors.py and remove the seven byte-identical per-module copies and constants.

- [x] `W03.P05.S15` - Promote one canonical storage_validation_error to storage/errors.py and redirect the seven duplicate storage-module copies, removing the duplicate defs and message-key constants; `src/aeat/adapters/persistence/storage/errors.py`.

## Wave `W04` - Pass 4 — Behavior-Preserving Removal Sweep

Land every behavior-preserving consolidation surfaced by the structural sweep and the F4 re-examination, per the corrected directive that only behavior-changing merges are blocked.

### Phase `W04.P06` - F6 — Dedupe live-CLI metric-line and auth-preflight guard

Consolidate the identical _metric_line formatter and auth-preflight registration guard onto shared helpers.

- [x] `W04.P06.S16` - Consolidate the live-CLI _metric_line and auth-preflight guard onto shared helpers in _app_live_auth_preflight and redirect rendering, expedientes, justificante, notifications; `src/aeat/entrypoints/cli/_app_live_auth_preflight.py`.

### Phase `W04.P07` - F7 — Dedupe live-CLI active-bucket guard

Consolidate the four identical _bucket_id guards onto a shared resolve_active_bucket helper.

- [x] `W04.P07.S17` - Consolidate the four identical _bucket_id active-bucket guards onto a shared resolve_active_bucket helper; `src/aeat/entrypoints/cli/_app_live_verify_cli.py`.

### Phase `W04.P08` - F4 — Consolidate European-decimal separator parsing

Promote a canonical normalize_decimal_separators and redirect the eight inline separator sites.

- [x] `W04.P08.S18` - Promote canonical normalize_decimal_separators and redirect the eight inline European-decimal separator sites; `src/aeat/core/decimal/_coerce.py`.

### Phase `W04.P09` - F8 — Dedupe ledger _require_transaction guard

Consolidate the two identical application-ledger _require_transaction guards onto _actions_common.

- [x] `W04.P09.S19` - Consolidate the duplicate _require_transaction guard in _review_projection onto the canonical in _actions_common; `src/aeat/application/ledger/_review_projection.py`.

## Description

<!-- Briefly describe the proposed work. Reference `{adr}`s,
`{research}`, `{reference}`. Supporting documentation must be read prior to
writing the plan document. -->

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

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelized when they share no hard
interdependency. -->

## Verification

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in the plan is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the authorizing
documents linked in the `related:` frontmatter. -->
