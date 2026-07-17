---
tags:
  - '#plan'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-15-cli-authority-verb-conformance-adr]]'
  - '[[2026-07-15-cli-authority-verb-conformance-research]]'
  - '[[2026-07-15-cli-authority-verb-conformance-reference]]'
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

# `ledger-evidence-atomicity` plan

### Phase `P01` - Evidence write authority

Make attach the sole evidence mutation authority and expose one atomic invoice-only linkage writer.

- [x] `P01.S01` - Make generic manual-field updates refuse all evidence fields, reserve evidence catalogue and provenance mutation for attach, and expose a single atomic invoice-only linkage writer; `src/cadrumo/application/ledger/_actions_manual.py`.
- [x] `P01.S02` - Prove direct evidence patches fail, invoice linkage cannot mutate evidence, and failed attach or link leaves transaction, evidence catalogue, provenance, and event history unchanged; `src/cadrumo/application/ledger/tests/test_actions_update_evidence.py`.
- [x] `P01.S03` - Prove create-time and attach-time evidence validation enforce the same missing and cross-bucket policy; `src/cadrumo/application/ledger/tests/test_actions_create_evidence_validation.py`.

### Phase `P02` - Atomic split persistence

Make evidence-driven splitting persist parent, children, evidence links, provenance, classifications, and events in one transaction.

- [x] `P02.S04` - Make evidence-driven LLM splitting persist the parent transition, every child, inherited validated evidence links, provenance, classifications, and events in one atomic application transaction without generic field patching; `src/cadrumo/application/ledger/_actions_split_manual.py`.
- [x] `P02.S05` - Prove every LLM split child inherits the parent evidence and provenance consistently and any child validation or persistence failure leaves the parent, children, catalogue, and event history unchanged; `src/cadrumo/application/ledger/tests/test_llm_evidence_split_apply.py`.

### Phase `P03` - Evidence and replay CLI door

Restrict ledger link to invoice-only linkage and remove the duplicate backend replay route entirely.

- [x] `P03.S06` - Remove EvidenceBundleService replay, its public export, and backend tests while preserving evidence check and unrelated observability replay facilities; `src/cadrumo/application/evidence/_service.py`.
- [ ] `P03.S07` - Restrict ledger link to invoice-only linkage, route it through the atomic application writer, and remove evidence-id and evidence-update result paths; `src/cadrumo/entrypoints/cli/_ledger.py`.
- [x] `P03.S08` - Remove modelo audit replay and every call to the backend replay method while retaining only genuine evidence audit check; `src/cadrumo/entrypoints/cli/_modelo_audit_cli.py`.
- [ ] `P03.S09` - Prove attach remains the sole evidence mutation, invoice link is atomic and invoice-only, and link rejects every removed evidence grammar; `src/cadrumo/entrypoints/cli/tests/test_ledger_link_check_verbs.py`.
- [x] `P03.S10` - Prove modelo audit exposes check without replay, backend replay calls, replay result schemas, or synthetic replay events; `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`.

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
