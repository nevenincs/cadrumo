---
tags:
  - '#plan'
  - '#iva-workflow'
date: '2026-09-23'
tier: L1
related:
  - '[[2026-09-21-iva-workflow-m303-filing-evidence-authoring-adr]]'
modified: '2026-09-23'
body_schema: body-v2
body_hash: 'sha256:a2d7aa11b5c32512dabb10ebdc6c721acb64d850c7031778e0d98488ade88666'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries governing ADRs, if any.
       Steps inherit their evidence transitively. Direct supporting
       evidence links are optional; per-row footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace iva-workflow with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries governing ADRs; Steps inherit their evidence transitively.
     Direct supporting evidence links are optional. A decision-free plan
     records its coverage assessment in the Description.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution artifact: the plan's ledger.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 until `vaultspec-core vault check all --fix` adds it).
     The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Select the smallest hierarchy that clarifies coordination:
       L1 = a flat sequence of cohesive revisions, including broad changes.
       L2 = Phases clarify groups of Steps.
       L3 = Waves clarify dependencies between groups of Phases.
       L4 = an Epic coordinates a program with external tracking.
     Duration, file count, package count, or short parallel work alone
     never requires a higher tier.
     Between two tiers take the smaller and promote later.
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

<!-- COHESIVE GRANULARITY:
     One Step is one cohesive, verifiable commit. Coordinated repeated edits
     may share a row when scope and verification are explicit. Separate
     unrelated outcomes. Name the bounded files or area, expected creations,
     and intended result; avoid unspecified catch-all work. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change; the `plan_edit` and `plan_progress`
     MCP tools reach the Step verbs only, and the above-Step verbs run
     through the CLI. Hand edits are forbidden and
     flagged by `vaultspec-core vault plan check`; canonical-identifier
     preservation is guaranteed only when a verb performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `iva-workflow` plan

Ordinary Modelo 303 evidence follows the record design's period rules, and monthly settlement periods are admitted.

## Description

Approved 2026-09-23. Basis: the operator's standing pre-approval of IVA implementation work in this session, and the coordinator's direction to amend the M303 filing-evidence decision before changing the persisted schema, then plan and implement monthly Modelo 303.

The governing decision is `2026-09-21-iva-workflow-m303-filing-evidence-authoring-adr`, Amendment 3, which carries the grounding (DP30301 fields 14, 23 and 24, Notas 3, 4 and 5, in every bundled design from 2022 through `2026-y-siguientes`; Orden EHA/3786/2008 art. 7). All Steps implement that amendment; no further costly decision is expected. The wrong annual-volume output the same reading exposed is already corrected outside this plan.

Scope: persisted evidence shape (S01), coordinate and authoring (S02), the calculate operation request (S03), CLI (S04), TUI (S05), documentation sequences (S07), and installed proof (S06). Out of scope: the exempt-from-390 branch, typed per-field period applicability in the registry, and monthly-settlement eligibility, which S02 only identifies an owner for.

## Steps

- [x] `S01` - make the persisted ordinary Modelo 303 evidence period-scoped: optional annual-volume answer, Modelo 390 evidence required only in the last period, stored revisions still valid; `src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py, application/filing/producer_snapshot.py, application/filing/export_producer.py, application/modelo/m303_filing_evidence.py`.
- [ ] `S02` - admit monthly coordinates and author period-scoped evidence; refuse a 390 attestation outside the last period; record which owner refuses monthly work for a non-monthly filer; `src/cadrumo/application/modelo/m303_ordinary_evidence_coordinate.py, m303_ordinary_filing_evidence_authoring.py, m303_exonerado_390_applicability_attestation.py`.
- [ ] `S03` - version the calculate request: nested ordinary request without the annual-volume answer and with an optional attestation pair, schema version 3, previous pending invocations refused; `src/cadrumo/application/modelo/operation_definitions.py and its conformance tests`.
- [ ] `S04` - align the CLI and quickfile flags with the period rule and regenerate the CLI reference and locale keys; `src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py, _app_quickfile.py, command specs, locales`.
- [ ] `S05` - align the TUI evidence form: no annual-volume question, attestation only in the last period; `src/cadrumo/entrypoints/tui/modelo/m303_evidence.py, view/overview.py, lifecycle.py, locales`.
- [ ] `S07` - update the Modelo 303 and 390 docs sequence contracts to the period rule and regenerate their goldens through the sequence runner; `docs/_sequences/contracts/how-to/modelo-303, modelo-390 and the other contracts that calculate Modelo 303`.
- [ ] `S06` - prove the attestation contract at 4T and a monthly coordinate on an installed wheel built from a committed source; `dev/acceptance/iva/installed_m303_evidence_journey.py`.

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- Progress is recorded through the plan verbs (`plan_progress`,
     `vaultspec-core vault plan step check`), one Step at a time. -->

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

Sequential. S01 fixes the persisted shape every later Step consumes; S02 and S03 build on it in order; S04 and S05 both consume the S03 request and may run in parallel only with disjoint files; S07 needs S04; S06 needs every earlier Step committed so the wheel is built from a committed source.

## Verification

- Persisted revisions written under the previous rules load and export unchanged in meaning; a last-period revision without Modelo 390 evidence is refused; a non-final revision without it is valid.
- A monthly coordinate (for example 2026/01) authors evidence and calculates; a quarterly non-final period calculates without any attestation; 4T and 12 require the attestation; an attestation supplied outside the last period refuses with a typed REFUSED code.
- A pending invocation recorded under the previous request schema is refused, never replayed.
- Focused unit and integration tests pass with `-n0` and explicit markers; ruff, format, ty, basedpyright and pyrefly are clean on every changed file; locale audit shows no new missing or extra key; the generated CLI reference and docs goldens are regenerated through their owners and their checks are clean.
- The installed journey on a wheel built from a committed source proves the 4T attestation contract and a monthly calculation, with receipts carrying commit, wheel digest, authority generation and installed module hash.
