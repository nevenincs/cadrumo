---
tags:
  - '#plan'
  - '#reachability-burndown'
date: '2026-09-04'
tier: L3
related:
  - '[[2026-09-04-reachability-burndown-adr]]'
  - '[[2026-09-04-reachability-burndown-reference]]'
modified: '2026-09-04'
body_schema: body-v2
body_hash: 'sha256:b4ef53f2954861f7a1b6da75517d46bd0ec6d48e89bdc845871ab7d39168d972'
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
     Replace reachability-burndown with a kebab-case feature tag, e.g. #foo-bar.
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

# `reachability-burndown` plan

<!-- One-line headline summary plan. -->

## Description

Close the false green in entrypoint reachability. The audit reports 43 modules and 1408 symbols that no declared console script reaches, plus 21 orphaned test modules, while the standing ratchet exits 0 because it adjudicates modules only and defers a frozen prefix. W01 turns one undifferentiated population into evidenced classes, because the remedies differ completely and the wrong remedy either deletes capability or wires code to nothing. W02 relocates code whose callers prove it belongs elsewhere, smallest blast radius first. W03 clears the symbol backlog by owning package. W04 extends the gate to symbols and orphaned tests and proves the joined state.

## Steps

## Wave `W01` - classify the population

Turn one undifferentiated audit population into evidenced classes. Every later wave depends on knowing which remedy a finding needs, and applying the wrong remedy deletes capability or wires code to nothing.

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

### Phase `W01.P01` - survey and classify

Produce an evidenced classification for every module and orphaned-test finding, and for the symbol population by owning package.

- [ ] `W01.P01.S01` - Classify every unreachable and module-exec-only module by outside-use label and semantic uniqueness probe, recording the evidence behind each supersession or staging claim; `dev/audit`.
- [ ] `W01.P01.S02` - Classify the 21 orphaned test modules against whether their shipped subjects are themselves findings; `src/cadrumo`.
- [ ] `W01.P01.S03` - Partition the exact-confidence symbol population by owning package and record the dominant kinds per area; `dev/audit`.

## Wave `W02` - resolve by owning home

Relocate code whose only callers prove it belongs elsewhere, smallest blast radius first. Dev-only harness code precedes test-only support because it leaves the shipped wheel without touching the product surface.

### Phase `W02.P02` - relocate dev-only harness code

Move modules whose only callers are dev/ beside the consumer that drives them.

- [ ] `W02.P02.S04` - Relocate dev-only harness modules beside their dev consumers and shrink the ratchet by the entries resolved; `dev`.

### Phase `W02.P03` - relocate test-only support

Move shared test support into the wheel-excluded test tree and verify the distributed artifact.

- [ ] `W02.P03.S05` - Relocate test-only support into the wheel-excluded test tree and prove the distributed artifact no longer carries it; `src/cadrumo/tests`.

### Phase `W02.P04` - adjudicate owner-decision modules

Resolve modules requiring a delete-or-wire decision, each with its authorising record.

- [ ] `W02.P04.S06` - Resolve the operator_surface CRUD catalogue cluster against its conformance-test consumer; `src/cadrumo/application/operator_surface`.
- [ ] `W02.P04.S07` - Adjudicate the staged-capability modules against their authorising decisions and classify or wire each; `src/cadrumo/application`.

## Wave `W03` - burn down the symbol backlog

Resolve the 1408 unused symbols by owning package, largest concentration first. Symbols are ungated today, so this wave carries the bulk of the false green.

### Phase `W03.P05` - resolve domain and registry symbols

Clear the largest exact-confidence concentration at its owning boundary.

- [ ] `W03.P05.S08` - Resolve the domain/calculations exact-confidence symbol concentration at its owning boundary; `src/cadrumo/domain/calculations`.

### Phase `W03.P06` - resolve CLI and application symbols

Clear the entrypoints and application concentrations without disturbing command contracts.

- [ ] `W03.P06.S09` - Resolve the entrypoints/cli symbol concentration without altering command contracts; `src/cadrumo/entrypoints/cli`.
- [ ] `W03.P06.S10` - Resolve the application/modelo and adapters/persistence symbol concentrations; `src/cadrumo/application`.

## Wave `W04` - extend the gate and close

Extend the ratchet to symbols and orphaned test modules once their populations carry classifications, then prove the joined state. Extension is shrink-only from the day it lands.

### Phase `W04.P07` - extend the ratchet

Bring symbols and orphaned test modules under the gate, shrink-only.

- [ ] `W04.P07.S11` - Extend the ratchet to unused symbols and orphaned test modules with detector-teeth proof; `dev/quality`.

### Phase `W04.P08` - prove the joined state

Re-measure every signal from one stable revision and prove no false green remains.

- [ ] `W04.P08.S12` - Re-measure every signal from one stable revision and prove no false green remains; `dev/audit`.

## Parallelization

Waves are ordered: no resolution proceeds before its finding is classified, and the gate extends only after the populations it will cover carry classifications. Within W02 the three phases are independent by ownership and may run in parallel, though P02 precedes P03 in practice because dev-only relocation leaves the shipped wheel untouched. Within W03 the two phases own disjoint packages. The `cadrumo.entrypoints.tui` prefix stays deferred throughout while its owning campaign is in flight, so 26 of the module findings are out of scope here. Executors check the shared worktree before every step and must not modify peer-owned dirty files.

## Verification

- Every module, orphaned-test, and exact-confidence symbol finding carries exactly one class from the ADR's closed taxonomy, and every supersession or staging claim names the evidence that established it.
- Semantic uniqueness claims are grounded by a recorded `vaultspec-rag` query over production code, not by name similarity; class-level supersession additionally names the live type that discharges the responsibility.
- Each relocation is proven by the distributed artifact no longer carrying the module, and by the owning tests passing from their new home.
- Each deletion of shipped capability cites the record authorising it; no capability is removed on the audit's say-so alone.
- The ratchet's `allowed` list only ever shrinks, and the extended gate demonstrates a representative defect is detected for both symbols and orphaned test modules.
- No threshold, exclusion, baseline, skip, or allowlist widening appears in any step's diff.
- Closure requires the audit and the extended ratchet to agree from one stable revision, with the remaining count explained entirely by classified, recorded dispositions.
