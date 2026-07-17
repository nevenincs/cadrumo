---
tags:
  - '#plan'
  - '#cli-authority-quality-backlog'
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

# `cli-authority-quality-backlog` plan

### Phase `P01` - Registry as-of honesty

Make every accepted as_of argument effective or reject it explicitly, so the CLI stops accepting a parameter it silently ignores.

- [ ] `P01.S01` - Make every accepted as_of argument participate in revision validity selection or reject it explicitly instead of silently ignoring it; `src/cadrumo/domain/calculations/registry/_queries.py`.
- [ ] `P01.S02` - Reject an as_of argument on the unscoped registry discovery path with an instructive refusal naming the scoped form that honours it; `src/cadrumo/application/modelo/_registry_discovery.py`.
- [ ] `P01.S03` - Prove historical as-of boundaries are honoured on the scoped path and refused explicitly on the unscoped path rather than silently ignored; `src/cadrumo/domain/calculations/registry/tests/test_queries.py`.

### Phase `P02` - Hashing recurrence gate

Add the AST recurrence gate that prevents new reducible one-shot hash bodies without a mass rewrite of existing callers.

- [ ] `P02.S04` - Add an AST recurrence gate that rejects new reducible production SHA-256 constructor and one-shot hexdigest bodies while allowing streaming, HMAC, HKDF, X509, and digest-byte uses; `src/cadrumo/core/tests/test_hashing_adoption.py`.
- [ ] `P02.S05` - Prove the recurrence gate rejects a new reducible one-shot body and accepts every legitimate cryptographic use it must not block; `src/cadrumo/core/tests/test_hashing_adoption.py`.

### Phase `P03` - Secure-object namespace adoption

Make the namespace registry the sole metadata authority and prove each storage binding consumes a registered definition.

- [ ] `P03.S06` - Correct namespace registry metadata drift and make each namespace definition the sole authority for identifier, schema version, sensitivity, default object key, key grammar, owner, and custody; `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`.
- [ ] `P03.S07` - Remove duplicate namespace, version, sensitivity, catalogue-key, and custody literals from transaction, invoice, modelo participation, and bucket persistence consumers and bind them to registry definitions; `src/cadrumo/domain/transactions/`.
- [ ] `P03.S08` - Remove duplicate namespace metadata from profile, calculation, aggregation, and filed-observation repositories and bind repository construction to registry definitions; `src/cadrumo/application/user_profile/`.
- [ ] `P03.S09` - Remove duplicate namespace and custody declarations from Clave, LLM cache and usage, bundle, attachment, and secure-storage consumers without conflating certificate custody with master-key keyring custody; `src/cadrumo/adapters/outbound/aeat/auth/`.
- [ ] `P03.S10` - Replace literal-membership namespace checks with a non-vacuous production-root adoption gate that recognizes cadrumo-prefixed declarations, detects local metadata declarations, and proves each storage binding consumes the registered definition; `src/cadrumo/application/tests/test_storage_namespace_adoption.py`.

### Phase `P04` - Filed capture finalizer

Give filed observation persistence sole ownership of selection, ordering, and writes behind one typed finalizer.

- [ ] `P04.S11` - Make filed observation persistence the sole owner of latest-record selection, deterministic history ordering, metadata enrollment, and calculation-observation writes and remove the duplicate selector and persistence loop from capture orchestration; `src/cadrumo/application/live/_filed_data_capture.py`.
- [ ] `P04.S12` - Introduce one typed filed-capture finalizer and failure accumulator used by single, bulk, and source capture with explicit fail-fast single and source policy and best-effort bulk policy; `src/cadrumo/application/live/_filed_capture_finalizer.py`.
- [ ] `P04.S13` - Prove identical latest selection and history ordering across all capture routes, their distinct failure policies, and preservation of the separate strict IVA compensation persistence path; `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`.

### Phase `P05` - LLM review workflow typing

Type the language-model review workflow with mandatory invocation origins after ledger evidence atomicity lands.

- [ ] `P05.S14` - Define typed LLM review requests, decisions, results, and mandatory invocation origins without an application-layer default CLI source command; `src/cadrumo/application/ledger/_llm_review_workflow.py`.
- [ ] `P05.S15` - Implement one application review workflow for suggest, saturate, review, apply, reject, evidence no-split, and evidence split while composing existing canonical persistence primitives; `src/cadrumo/application/ledger/_llm_review_workflow.py`.
- [ ] `P05.S16` - Route classify --auto-split and split --llm through the typed review workflow with distinct invocation origins and remove CLI-owned review branching and application source-command defaults; `src/cadrumo/entrypoints/cli/_ledger_llm_cli.py`.
- [ ] `P05.S17` - Prove suggestion, saturation, rejection, no-split, multi-child split, invocation-origin attribution, and CLI-route parity against real persistence and model subprocess boundaries; `src/cadrumo/application/ledger/tests/test_llm_reject.py`.

## Description

Absorb the residue of the CLI authority campaign that is real work but carries neither an operator-safety defect nor a false-green risk. Every phase here is independently closeable and none blocks another plan. This plan is deferrable against spare capacity; it is not a prerequisite for any successor.

Registry as-of honesty ships narrowly. The unscoped registry query accepts an as_of argument and silently ignores it, which is an accepted-parameter lie: the operator asks for a historical view, receives a current one, and gets no signal that the request was discarded. The fix is small and worth shipping on its own: honour the argument in revision validity selection, or refuse it with an instructive message naming the scoped form that does honour it. The decision record keeps scoped and unscoped selection distinct on purpose, so this is a honesty fix, not a merge.

Hashing narrows to the recurrence gate. The eighteen exact one-shot bodies and four reducible file-hash bodies repeat substitutable mechanics, but rewriting them is low-value churn against a canonical service that already exists. Only the AST recurrence gate carries durable value: it prevents new reducible bodies from landing while allowing streaming, keyed, derivation, and certificate uses that are not substitutable and must not be blocked.

Namespace adoption, filed capture, and the language-model review workflow are each genuine single-authority consolidations with no safety urgency. The namespace adoption check currently passes without proving binding, which makes it a weak gate rather than a wrong one. The language-model review phase depends on ledger evidence atomicity landing first, because both touch split persistence.

## Steps

## Parallelization

The registry as-of, hashing recurrence gate, namespace adoption, and filed capture phases are mutually independent and touch disjoint files. Any of them may run alone at any time.

The language-model review workflow phase has one hard dependency: the ledger evidence atomicity plan must land first, because both modify split persistence and the review workflow must compose the atomic writer rather than the generic patch path it replaces. Do not start this phase before that plan closes.

Within the namespace adoption phase, the registry metadata correction must land before the consumer-binding steps, which are otherwise independent of each other and may run in parallel across their disjoint consumer packages.

## Verification

The scoped registry path honours historical as-of boundaries, the unscoped path refuses as_of with an instructive message naming the scoped form, and no path silently ignores the argument. Scoped and unscoped parity holds everywhere as_of is not involved, and the intentional distinction between bindings and casilla detail reports survives.

The hashing recurrence gate rejects a newly introduced reducible one-shot body and accepts every legitimate streaming, keyed-hash, key-derivation, certificate, and digest-byte use it must not block. Existing callers are not rewritten.

The namespace adoption gate is non-vacuous: it proves each production storage binding consumes a registered definition rather than checking literal membership, detects a local metadata redeclaration, and does not conflate certificate custody with master-key keyring custody.

Filed capture proves identical latest selection and history ordering across every capture route, preserves each route's distinct failure policy with single and source fail-fast and bulk best-effort, and preserves the separate strict IVA compensation persistence path.

The language-model review workflow proves suggestion, saturation, rejection, no-split, multi-child split, invocation-origin attribution, and route parity against real persistence and real model subprocess boundaries, with the two CLI intents retaining distinct invocation origins.

Each phase closes independently with its own focused verification and its own fresh-context honesty review.
