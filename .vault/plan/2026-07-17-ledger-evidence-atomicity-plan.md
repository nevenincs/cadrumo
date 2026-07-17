---
tags:
  - '#plan'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
tier: L2
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
     Replace ledger-evidence-atomicity with a kebab-case feature tag, e.g. #foo-bar.
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

# `ledger-evidence-atomicity` plan

### Phase `P01` - Evidence write authority

Make attach the sole evidence mutation authority and expose one atomic invoice-only linkage writer.


<!-- One-line headline summary plan. -->

- [ ] `P01.S01` - Make generic manual-field updates refuse all evidence fields, reserve evidence catalogue and provenance mutation for attach, and expose a single atomic invoice-only linkage writer; `src/cadrumo/application/ledger/_actions_manual.py`.
- [ ] `P01.S02` - Prove direct evidence patches fail, invoice linkage cannot mutate evidence, and failed attach or link leaves transaction, evidence catalogue, provenance, and event history unchanged; `src/cadrumo/application/ledger/tests/test_actions_update_evidence.py`.
- [ ] `P01.S03` - Prove create-time and attach-time evidence validation enforce the same missing and cross-bucket policy; `src/cadrumo/application/ledger/tests/test_actions_create_evidence_validation.py`.

### Phase `P02` - Atomic split persistence

Make evidence-driven splitting persist parent, children, evidence links, provenance, classifications, and events in one transaction.

- [ ] `P02.S04` - Make evidence-driven LLM splitting persist the parent transition, every child, inherited validated evidence links, provenance, classifications, and events in one atomic application transaction without generic field patching; `src/cadrumo/application/ledger/_actions_split_manual.py`.
- [ ] `P02.S05` - Prove every LLM split child inherits the parent evidence and provenance consistently and any child validation or persistence failure leaves the parent, children, catalogue, and event history unchanged; `src/cadrumo/application/ledger/tests/test_llm_evidence_split_apply.py`.

### Phase `P03` - Evidence and replay CLI door

Restrict ledger link to invoice-only linkage and remove the duplicate backend replay route entirely.

- [ ] `P03.S06` - Remove EvidenceBundleService replay, its public export, and backend tests while preserving evidence check and unrelated observability replay facilities; `src/cadrumo/application/evidence/_service.py`.
- [ ] `P03.S07` - Restrict ledger link to invoice-only linkage, route it through the atomic application writer, and remove evidence-id and evidence-update result paths; `src/cadrumo/entrypoints/cli/_ledger.py`.
- [ ] `P03.S08` - Remove modelo audit replay and every call to the backend replay method while retaining only genuine evidence audit check; `src/cadrumo/entrypoints/cli/_modelo_audit_cli.py`.
- [ ] `P03.S09` - Prove attach remains the sole evidence mutation, invoice link is atomic and invoice-only, and link rejects every removed evidence grammar; `src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py`.
- [ ] `P03.S10` - Prove modelo audit exposes check without replay, backend replay calls, replay result schemas, or synthetic replay events; `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`.

### Phase `P04` - Contract migration for the evidence family

Move the evidence and replay payload schemas, locales, help and risk metadata, and generated documentation.

- [ ] `P04.S11` - Remove replay-specific fields from every payload and schema projection; `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`.
- [ ] `P04.S12` - Migrate the ledger evidence and audit family help and risk metadata to the accepted grammar; `src/cadrumo/application/operator_surface/_help.py`.
- [ ] `P04.S13` - Migrate the four locale catalogues for the ledger evidence and audit families through the locales CLI; `src/cadrumo/locales/en.yml`.
- [ ] `P04.S14` - Regenerate the operator how-to and reference pages for ledger evidence from the frozen live surface; `docs/how-to/ledger-evidence.md`.
- [ ] `P04.S15` - Prove the removed replay and evidence-patch spellings are absent from every source and generated surface; `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`.

## Description

Make evidence attachment the sole evidence write authority, make invoice linking atomic and invoice-only, and retire the duplicate evidence replay path. Two defects motivate this plan. Generic manual-field patching can reach evidence fields, so a caller can mutate the evidence catalogue and its provenance outside the attach authority's validation, replacement, and custody policy. Combined invoice and evidence linking can partially commit, leaving a transaction whose evidence links, provenance, and event history disagree with each other.

The accepted authority is narrow: evidence attachment owns validation, replacement, custody, catalogue mutation, and events, and invoice linking establishes an atomic invoice-only relationship and nothing else. The decision record preserves the neighbouring distinctions deliberately. Evidence document linking acquires and stores bytes before delegating to canonical attach; it is composition, not a second evidence writer, and stays. Evidence export invokes evidence check as a precondition before publishing; check remains the verifier. Listing is read-only discovery; review applies a decision workflow.

Evidence replay is different: it duplicates integrity checking without reproducing stored-input outcomes, so it is a second, weaker path claiming the same contract. It is removed rather than consolidated, along with its CLI route, result schema, event and token, tests, documentation, and generated projections. Genuine evidence check and the unrelated observability replay facility both remain.

Language-model split persistence is in scope here because it shares the split persistence files: an evidence-driven split must persist the parent transition, every child, inherited validated evidence links, provenance, classifications, and events in one atomic transaction rather than splitting and then patching. Splitting before this lands would re-enter evidence through the generic patch door this plan closes. The remaining language-model review workflow typing is out of scope and lives in the quality backlog.

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

The evidence write authority phase must land before the atomic split persistence phase: the split path must have an atomic writer to persist through, and it must no longer have a generic patch door to reach evidence with. This is the ordering the campaign identified as ledger evidence preceding language-model split persistence, and it is a hard dependency because both modify split persistence files.

The replay removal in the CLI door phase is independent of the evidence write authority and may run in parallel with it; it touches the evidence service and the audit CLI, not the ledger manual actions.

The contract migration runs last. The config payload modules and the four locale catalogues are shared with peer campaigns and must be serialized rather than co-edited; route all locale work through the locales CLI.

## Verification

Bypass-impossible proofs pass: a direct evidence patch fails rather than succeeding quietly, invoice linkage cannot mutate evidence, and create-time and attach-time evidence validation enforce the same missing and cross-bucket policy, so there is no weaker door into the same state.

Atomicity proofs pass: a failed attach or link leaves the transaction, evidence catalogue, provenance, and event history unchanged, and any child validation or persistence failure during a split leaves the parent, children, catalogue, and event history unchanged. Every split child inherits the parent evidence and provenance consistently.

Replay is absent everywhere: the backend replay method, its public export, the CLI route, the result schema, the event and token, the backend tests, the documentation, and the generated projections are all gone, while evidence check and the unrelated observability replay facility still work. Exact absence checks cover every source and generated surface.

The standing root grammar, documented-command, JSON schema, and locale parity gates run green after each vertical lands.

A fresh-context honesty review runs against this plan's closure summary before the plan is declared complete.

