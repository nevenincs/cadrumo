---
tags:
  - '#plan'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-14'
tier: L2
related:
  - '[[2026-06-14-legal-grounding-centralization-audit]]'
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
     Replace legal-grounding-centralization with a kebab-case feature tag, e.g. #foo-bar.
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

# `legal-grounding-centralization` plan

### Phase `P01` - Safe pure-centralization (value unchanged)

Promote inline-grounded regulatory values to the central authority without changing the value — only its home. Lowest regression risk: each move is value-identical and lands with a grounding/roundtrip assertion. Covers F6 (art.58/59 family thresholds), F5 (DT12 40% + SAL 10%/2x), and F2-interim (prorrata art.103.Dos/art.9.1.c thresholds).


<!-- One-line headline summary plan. -->

- [x] `P01.S01` - F6: promote LIRPF art.58/59 family thresholds (max-age 25, max-age 3, custodia 0.5) to external_constants grounded on the cited articles; `src/aeat/domain/contribuyente/family.py`.
- [ ] `P01.S02` - F5: promote DT12 40% rescate reducción and Ley 44/2015 SAL 10% dotación + 2x cap factor to registry/external_constants with legal_refs->corpus_ref; `src/aeat/domain/modelos/_dt12_reduccion.py`.
- [ ] `P01.S03` - F2-interim: promote prorrata art.103.Dos (1.10) and art.9.1.c (50pp) thresholds to external_constants with legal_refs, value-identical; `src/aeat/domain/iva/_prorrata.py`.

### Phase `P02` - Live calc-path wiring with parity proof

Wire the dormant registry reader into the live calculation dispatch so the registry parameter becomes causal. Higher value, higher risk: the value reaches a real filing amount, so each wiring lands only with a parity proof against the existing oracle tests. Covers F1 (art.23.2 tier reducción).

- [ ] `P02.S04` - F1: wire resolve_reduccion to the dormant _resolve_tier_reduccion_rate registry reader; `constant becomes documented fallback; prove parity against tier oracle tests; `src/aeat/domain/fincas/_tier_resolver.py`.

### Phase `P03` - Dormant/duplicate routing resolution

Resolve dormant or inline casilla-routing per no-legacy-compatibility: bind through the registry OR delete the dormant capacity, never leave live-but-unrouted. Covers F3 (M303/M390 compensación casilla routing), F4 (casilla_59/60 helpers), and the F2 final routing decision for the prorrata subsystem.

- [ ] `P03.S05` - F3: resolve M303/M390 compensación casilla ids through the registry snapshot casilla definitions instead of inline numeric literals; `src/aeat/application/calculations/_iva_compensation_history.py`.
- [ ] `P03.S06` - F4: author the ledger_iva_aggregation base_amount_sum bindings (INTRA_COMMUNITY_SUPPLY->59, EXPORT_THIRD_COUNTRY_ZERO_RATED->60) and delete the dormant casilla_59/60 Python helpers; `src/aeat/application/aggregation/_iva_ledger.py`.
- [ ] `P03.S07` - F2-final: decide prorrata subsystem fate — enroll as registry-declared aggregation source on 303/390 casillas OR delete the dormant subsystem per no-legacy-compatibility; `src/aeat/domain/iva/_prorrata.py`.

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
