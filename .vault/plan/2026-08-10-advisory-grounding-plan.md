---
tags:
  - '#plan'
  - '#advisory-grounding'
date: '2026-08-10'
modified: '2026-08-10'
body_hash: 'sha256:456b04ec26683acbeb853be02d0aba1db4347aa7cc54ce7fab905d5c6382c8d1'
tier: L2
related:
  - '[[2026-08-10-advisory-grounding-adr]]'
  - '[[2026-08-10-advisory-grounding-reference]]'
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
     Replace advisory-grounding with a kebab-case feature tag, e.g. #foo-bar.
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

# `advisory-grounding` plan

<!-- One-line headline summary plan. -->

## Description

<!-- Briefly describe the proposed work. Reference `{adr}`s,
`{research}`, `{reference}`. Supporting documentation must be read prior to
writing the plan document. A plan may execute one ADR or a cluster; when
several feed it, state here which Wave or Phase each ADR governs. -->

## Steps

### Phase `P01` - Mechanism and build-time validation

Give an advisory a typed place to declare the provisions it asserts, and make registry build refuse a declared id that does not resolve.

- [ ] `P01.S01` - Give CalculationSourceDiagnostic a typed place for an advisory to declare the provisions it asserts itself, distinguished on the diagnostic from the casilla-derived path that the one existing correct instance uses. The two are not alternatives and neither replaces the other. Record the subject distinction on the type so a future author copying the casilla-derived instance onto an eligibility-rule advisory is stopped by the type rather than by convention; `src/cadrumo/application/, src/cadrumo/core/`.
- [ ] `P01.S02` - Refuse at registry build any declared provision id that does not resolve to a legal-catalogue entry. This is the check the prose form could never carry. State a control proving the legitimate population still passes and do not close on the refusal firing. The disconfirming observation: if the control shows a legitimate advisory declaring an id that does not resolve, the catalogue is incomplete for that provision and this row must stop and report rather than relax the refusal; `src/cadrumo/domain/calculations/registry/, src/cadrumo/tests/`.

### Phase `P02` - Per-site adjudication

Decide, per site, which catalogue entry the message actually asserts. This is a tax review per site rather than a sweep, and the art-81 sites are gated.

- [ ] `P02.S03` - HARD GATE, read before any conversion. Do not convert the art-81 advisory sites until the ley-35-2006 art-81 catalogue entry is repointed off the two-vintage excerpt, or exclude them explicitly from every conversion row. Casilla 0613 carries exactly one ref and its corpus target lacks the 81.2 turning-three extension, the 81.3 complemento-de-ayuda-para-la-infancia exclusion and the 150-euro increment, which are the clauses those advisories assert. Converting first makes them look grounded while citing a document that does not contain the rule, which is strictly worse than the prose because the prose claims no corroboration. Record in this row which of the two dispositions was taken; `src/cadrumo/_data/registry/aeat/legal/irpf.toml, src/cadrumo/application/modelo/`.
- [ ] `P02.S04` - Adjudicate per site which catalogue entry each advisory message actually asserts, and declare it. This is a tax review against the provision the message states, never a lookup, and it does not parallelise into a sweep. Where the casilla already carries the exact provision the derivation is correct and should be used. Where the catalogue carries a finer entry the casilla does not reference, declare the finer one and record why the casilla's coarser ref was not used. Do NOT append the finer entry to the casilla legal_refs to make a derivation work, because a casilla's refs describe what establishes that box and an eligibility rule governing one of its inputs is a different subject; `src/cadrumo/application/modelo/, src/cadrumo/application/aggregation/`.

### Phase `P03` - Population C threading

Thread a registry object into the five modules that hold none, as its own change with its own blast radius.

- [ ] `P03.S05` - Thread a registry object into the five modules that hold none, as its own change rather than inside a citation change. The invoice-devengo advisory, the retencion-rate advisory, the invoice source resolver and the prior-payment advisory hold no revision, snapshot or casilla definition anywhere. Every provision they cite has a catalogue entry, so this is threading rather than grounding. The disconfirming observation: if threading a revision into any of these modules would invert a dependency direction the architecture forbids, stop and report rather than route around it, because that would mean the advisory belongs at a different layer; `src/cadrumo/application/aggregation/, src/cadrumo/application/invoices/`.
- [ ] `P03.S06` - Read the twelve modules that assert no provision in either form and record, per module, whether that silence is proper. Nothing measured so far says they are proper and nothing contradicts it, so this row exists to convert an untested assumption into a stated finding. A diagnostic about wiring rather than law correctly carries no provision. The disconfirming observation: any module found asserting a regulatory claim through a channel the earlier regex could not see, such as a formatted or multi-line message, belongs in the P02 population and this row must say so rather than close on the count; `src/cadrumo/application/`.


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
