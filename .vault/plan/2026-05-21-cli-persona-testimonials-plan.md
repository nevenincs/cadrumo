---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/plan/ location)
# Feature tag (replace cli-persona-testimonials with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#plan'
  - '#cli-persona-testimonials'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-21'
# Complexity tier (mandatory for new plans).
# Allowed: L1 (Steps only), L2 (Phases above Steps),
# L3 (Waves above Phases above Steps), L4 (Epic above Waves
# above Phases above Steps; PM association required).
# Pre-existing plans without this field default to L2.
tier: L2
# Related documents as quoted wiki-links.
# Carries the AUTHORISING documents (ADR, research, reference,
# prior plan) for every Step in this plan; Steps inherit this
# chain; per-row reference footers do not exist.
related:
  - "[[2026-05-20-cli-persona-testimonials-audit]]"
  - "[[2026-05-20-cli-persona-testimonials-research]]"
  - "[[2026-05-20-test-fidelity-sweep-audit]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - The related: field carries the AUTHORISING documents (ADR, research,
       reference, prior plan) for every Step in this plan. Steps inherit this
       chain; per-row reference footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artefact: <Step Record>.
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
     in plan body. Authorising documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULT PLAN CLI:
     The `vault plan` CLI (vaultspec-core) is the canonical surface
     for structural manipulation of this plan document. Writers and
     executors MUST use `vault plan step add/insert/move/remove/
     check/uncheck/toggle/edit`, `vault plan phase add/move/remove/
     edit`, `vault plan wave add/move/remove/edit`, `vault plan epic
     intent`, and `vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `cli-persona-testimonials` `cli-persona-testimonial-remediation-plan` plan

Brief description of the proposed feature, change, or refactor.

## Proposed Changes

Describe what work needs to be done at a high level. Reference `{adr}`s,
`{research}`, `{reference}`, and other plan or reference files where
appropriate so implementation remains grounded in architectural decisions.

## Steps

The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks.

Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates.

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
     Wave depends on it, and which authorising documents back it.

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

State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelised when they share no hard
interdependency.

## Verification

State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in every Wave is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter.


## Context

## Intent

Remediation campaign driven by the operator-persona testimonial swarm
and the test-fidelity sweep. Each phase is a remediation wave; granular
execution state is maintained in the coordinator task list (task ids
cross-referenced per step). Complexity tier: L2 (Phases > Steps).

Source artefacts: `[[2026-05-20-cli-persona-testimonials-audit]]`,
`[[2026-05-20-cli-persona-testimonials-research]]`,
`[[2026-05-20-test-fidelity-sweep-audit]]`.

## P01 — i18n naked-string remediation — COMPLETE

Wave delivered: 8 commits, ~55 operator-facing naked strings eliminated,
~45 locale keys translated es/en/ca/hu via the `aeat.locales` CLI.

- [x] S01 Cluster C — ledger import (9ec797b5f) — task #519
- [x] S02 Cluster D — CLI boundary errors + locale-scanner extension (46889d841)
- [x] S03 Cluster E — censo sync (6903944a9)
- [x] S04 Cluster A — IdentityError NIF/NIE/CIF (5e30ffd18)
- [x] S05 Cluster F — app-live verify/portals/borrador (7502b3ec1)
- [x] S06 Cluster B — modelo-work BadParameter (70715be3a)
- [x] S07 singletons — startup / bucket-history / auth-diagnostic (7afd19aed)

## P02 — bucket isolation & workflow correctness

- [x] S01 modelo work create binds to active profile bucket (d870a936c) — task #513
- [x] S02 work verify NO_PENDING_OBLIGATION raw-repr leak — task #516 — DELEGATED to `cli-workflow-redesign`; RESOLVED by their commit 0775cfb63 (bug-inventory B2).

## P03 — profile-lifecycle & session

- [x] S01 delete/logout active profile → switch lockout — task #515 — DELEGATED to `cli-workflow-redesign`; RESOLVED by their commit 623795a8d (BLOCKER B1, cluster A).

## P04 — calculation-engine binding gaps

- [x] S01 engine populates decl.ejercicio/decl.periodo from work-unit metadata — task #517
- [x] S02 profile-sourced bindings auto-resolve; estimacion-directa enum/Decimal — task #521

## P05 — CLI UX & display

- [x] S01 profile display name instead of UUID across surfaces — task #518 — DELEGATED to `cli-workflow-redesign` (profile-uuid-identity ADR, plan Wave W01). Tracking only.
- [x] S02 CLI UX polish cluster (revision discoverability, classify echo, etc.) — task #520 (cross-check against `cli-workflow-redesign` bug-inventory clusters D/E before executing)

## P06 — tooling & follow-ups

- [x] S01 aeat.locales ErrorCode message_key scope decision — task #522 — investigated; decision persisted in [[2026-05-21-cli-persona-testimonials-audit]]. Remediation split to S05.
- [x] S02 i18n aeat config google error wrappers — task #523 (6491aeceb + 8e0f15b7b) — _google_refusal helper + 14 cli.config.google.errors.* keys × 4 locales.
- [x] S03 audit help-text vocabulary drift (aede996da) — task #524
- [x] S04 registry drift: modelo-200 casilla 00592 — task #514 (concurrent #476 campaign)
- [x] S05 errors.* registry-fallback translation wave (+ scanner extension) — task #525 — RESOLVED: scanner generalisation landed in _ast_scanner.py; ~375 errors.* + wizard.setup.verifier.* keys translated across all 4 locales by a concurrent campaign; parity + locale-honesty gates green.

## Maintenance

This plan is the durable wave tracker; the coordinator task list is the
live granular tracker. Update both as steps complete: check the step
here, mark the task completed, and record the commit SHA.
