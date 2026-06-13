---
tags:
  - '#plan'
  - '#llm-evidence-classification'
date: '2026-06-13'
tier: L3
related:
  - '[[2026-06-10-llm-evidence-classification-adr]]'
  - '[[2026-06-13-llm-evidence-classification-audit]]'
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

<!-- RETIRED: W04, W05, W06, W07 -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace llm-evidence-classification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'. The related field
     carries the AUTHORISING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add frontmatter fields
     outside the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artifact: <Step Record>.
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
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `llm-evidence-classification` `Evidence corpus and adversarial hardening` plan

## Wave `W01` - Classify provider-optional UX

Make --llm optional when --read-evidence routes scan/image evidence to the on-host vision model; require a provider only for the text/cloud path.

<!-- One-line headline summary plan. -->

### Phase `W01.P01` - Provider-optional classify/saturate/split

Thread provider Optional with lazy text-classifier resolution; route --read-evidence into the LLM path; instructive refusal when the text path needs a provider.

- [x] `W01.P01.S01` - Thread provider Optional with lazy text-classifier resolution in suggest/saturate/split classification; `src/aeat/application/ledger/_llm_classification.py`.
- [x] `W01.P01.S02` - Route --read-evidence into the LLM path when --llm is absent; `refuse instructively when the text path needs a provider; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W01.P01.S03` - Test image evidence without --llm classifies via the vision model and text/no-evidence without --llm refuses instructively; `src/aeat/application/ledger/tests/test_llm_vision_evidence.py`.

## Wave `W02` - Evidence corpus sourcing

Source licence-clean, PII-free sample invoices (text-layer PDF, scanned/image PDF, image) to fixtures with provenance sidecars, plus generated adversarial variants.

### Phase `W02.P02` - Corpus and provenance

Source real licence-clean invoices to fixtures with provenance sidecars and adversarial variants.

- [x] `W02.P02.S04` - Source licence-clean text-layer PDF, scanned/image PDF, and image invoices into a fixtures corpus; `src/aeat/application/ledger/tests/_evidence_corpus/`.
- [x] `W02.P02.S05` - Write a provenance sidecar per corpus fixture declaring real_corpus or synthetic_generated and its source; `src/aeat/application/ledger/tests/_evidence_corpus/`.
- [x] `W02.P02.S06` - Generate adversarial fixture variants (prompt-injection invoice, malformed/empty PDF, multi-page, foreign-language); `src/aeat/application/ledger/tests/_evidence_corpus/`.

## Wave `W03` - Adversarial testing

Adversarially test evidence parsing (text-layer, rasterise, vision dispatch) and the allow-list parser against the corpus and hostile inputs.

### Phase `W03.P03` - Adversarial parsing tests

Adversarial tests for evidence parsing and the allow-list parser against the corpus and hostile inputs.

- [x] `W03.P03.S07` - Adversarially test evidence parsing (text-layer, in-memory rasterise, vision dispatch) against the corpus; `src/aeat/application/ledger/tests/test_evidence_corpus_parsing.py`.
- [x] `W03.P03.S08` - Adversarially test parse_response: prompt-injection JSON, hostile/oversized output, out-of-allow-list values are rejected; `src/aeat/domain/transactions/tests/test_llm_parse_adversarial.py`.

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

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelised when they share no hard
interdependency. -->

## Verification

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in every Wave is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter. -->
