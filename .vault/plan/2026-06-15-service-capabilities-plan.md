---
tags:
  - '#plan'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
tier: L3
related:
  - '[[2026-06-15-service-capabilities-adr]]'
  - '[[2026-06-15-dependency-provisioning-adr]]'
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
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
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

# `service-capabilities` plan

## Wave `W01` - Capability backend

Core ServiceCapability enum, the profile capabilities schema section, the resolution layer, and gate rewiring.

<!-- One-line headline summary plan. -->

### Phase `W01.P01` - Core enum + schema section

Add ServiceCapability StrEnum in core and the capabilities section in the profile schema TOML.

- [ ] `W01.P01.S01` - Add ServiceCapability StrEnum (cloud_evidence_upload, llm_vision, google_export) in core with per-member docstrings; `src/aeat/core`.
- [ ] `W01.P01.S02` - Add a capabilities [[sections]] with boolean fields to the user_profile schema TOML; `add a roundtrip test; `src/aeat/_data/registry/aeat/user_profile/schema.toml`.

### Phase `W01.P02` - Resolution layer + gates

Add resolve_capability and rewire cloud-evidence/vision/google gates through it.

- [ ] `W01.P02.S03` - Add resolve_capability + CapabilityDecision overlaying profile facts onto the global Settings default (gestor-mode absolute bar first); `src/aeat/application/user_profile`.
- [ ] `W01.P02.S04` - Rewire cloud_evidence_read_permitted, the vision path, and google export through resolve_capability with typed refusals; `src/aeat/application/ledger/_evidence_input.py`.

### Phase `W01.P03` - CLI + wizard

config profile capabilities show/set and a wizard capabilities section.

- [ ] `W01.P03.S05` - Add config profile capabilities show/set verbs routed through EditProfileSectionCommand; `add a wizard capabilities section; `src/aeat/entrypoints/cli/_config`.

## Wave `W02` - Dependency probes + graceful degradation

Typed dependency probes, close the Ollama headline gap, Playwright remediation, CLI error containment.

### Phase `W02.P04` - Dependency probes

Typed DependencyStatus + per-service probes (ollama/model, playwright, google, provider CLIs).

- [ ] `W02.P04.S06` - Add DependencyStatus + per-service probes (ollama reachability/model, playwright, google creds, provider CLIs) that never raise on absence; `src/aeat/application`.

### Phase `W02.P05` - Close ungraceful paths

Ollama probe-before-inference refusal, CLI catches LLMProviderError/connection errors, providers vision row, Playwright hint.

- [ ] `W02.P05.S07` - Probe Ollama before vision inference + refuse instructively; `widen classify CLI to catch LLMProviderError/connection errors; add ollama providers row; Playwright hint; `src/aeat/application/ledger, src/aeat/entrypoints/cli`.

## Wave `W03` - Doctor + provisioning

aeat config doctor, pyproject extras + torch relocation, just doctor and provisioning recipes.

### Phase `W03.P06` - config doctor

aeat config doctor reporting availability + capability posture + remediation per service.

- [ ] `W03.P06.S08` - Add aeat config doctor: per-service availability + active-profile capability posture + remediation; `typed envelope + non-zero exit on opted-in-but-missing; `src/aeat/entrypoints/cli/_config`.

### Phase `W03.P07` - pyproject + justfile

Capability extras, torch relocation, just doctor/provision recipes, fix env-playwright, README reconcile.

- [ ] `W03.P07.S09` - Capability extras + relocate torch; `just doctor/provision recipes; fix env-playwright; reconcile README/justfile; `pyproject.toml, justfile, README.md`.
- [ ] `W03.P07.S10` - Tests + locales + how-to onboarding doc across capabilities, probes, doctor, provisioning; `src/aeat tests, src/aeat/locales, docs/how-to`.

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
