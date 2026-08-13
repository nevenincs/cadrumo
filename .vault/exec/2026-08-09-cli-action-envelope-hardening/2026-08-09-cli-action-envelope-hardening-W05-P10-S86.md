---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:9c19acb3b69131c0451fd69eb915bc8812b1cb87f7f0fa03dfeda25169e4b1fe'
step_id: 'S86'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate transaction-domain recovery producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/domain/transactions`

## Description

- Audit the declared package for the three shapes an authored sentence survives a migrated producer: positional beside a key, `message=` keyword, and constructor default or constructor-built prose.
- Migrate the three adjudicated key-derivation refusals to the class's own registered locale key plus locale-neutral machine facts.
- Retire the literal constructor default that displaced a subclass's own registered key.
- Pin every migrated site with an absence assertion and a structural sweep, and prove both bite by mutating production behaviour from outside the repository.
- Classify every remaining refusal in the package that was not migrated, and name the two that need an owner.

## Outcome

- Three constructor sites in the transaction-catalogue port now carry the registered key and no sentence. Each states the key through one module constant read from the error class's own bound error code rather than restated as a literal, so the raise sites and the error registry cannot drift apart. The facts are the repository, the operation, and the field that was blank.
- The blank field survives as a machine fact rather than as an English noun inside a sentence, so the two previously distinct refusals stay distinguishable to a caller while rendering identically to an operator in every locale. A test asserts exactly that: same rendered text, different blank-field fact.
- The constructor default was the third shape and it was live. The base ledger-storage error defaulted its translated message to its own key spelled as a literal, and the no-active-bucket subclass inherited that literal verbatim, so a bare construction of the subclass rendered the parent's `FAIL_FINANCIAL_LEDGER_STORAGE` key instead of its own registered `REFUSED_FINANCIAL_LEDGER_NO_ACTIVE_BUCKET` key. No raise-site scan could have seen it, because every call site looked clean. The default now resolves through the error registry per constructed class. The one live raise site supplies its own explicit key and is unaffected; a test pins that the explicit key still wins.
- No locale key was added and no catalogue was touched. Both keys are already registered against their classes and already present in all four catalogues, so nothing untranslated entered the tree and the contended catalogue files were never opened.
- The absence assertion is the discriminating one, and that was proven directly rather than assumed. Constructing the migrated error with the sentence restored positionally alongside the key leaves a key-and-context assertion green while the rendered text is the English sentence; only the absence form is false for that construction.
- Sixteen assertions cover the surface: three runtime absence assertions, one machine-fact discrimination test, three constructor-default tests, two registered-key identity tests, four structural sweep assertions, one detector self-proof, and two amount-contract assertions.
- The structural sweep refuses message text supplied positionally or through the `message=` keyword, and it walks constructions rather than only raise statements, so a refusal that is built and returned would be caught alongside one that is raised. It is anchored to the set of enclosing functions expected to construct a refusal, so a rename cannot make it pass vacuously, and it gates no count.
- Five mutations were applied from an out-of-repository pytest plugin that reads the real module source, mutates it in memory, and rebinds the resulting objects in the test module. Nothing under the source tree was written. A restored positional sentence, a `message=` keyword, command prose in the facts, and an unregistered key each reddened exactly the discriminating assertion and left the others green. The fifth mutation reverted the constructor default to the literal and reddened the per-class default assertion.
- The non-negative amount refusal still bites and was not weakened. The raw-transaction boundary validator is untouched; a negative amount is refused on the amount field and zero and positive magnitudes are accepted. That refusal's own message is deliberately not migrated and deliberately not pinned by text, because pinning its English here would only entrench it.

## Notes

- What was found, counted by defect shape. Positional beside a key: three sites, all migrated. The `message=` keyword shape: zero sites in this package, confirmed by an abstract-syntax pass over every production module. Constructor default or constructor-built prose: one site, migrated. Constructed and returned rather than raised: zero, confirmed by comparing every error construction against the set of constructions that are the operand of a raise. All ninety-one production error constructions in the package are raised.
- Deliberately not migrated, and this is a classification rather than a proof. Eighty-eight production sites author English prose with no locale key at all. That is a different and larger defect class than the one this Step was dispatched against: not a sentence hiding behind a key, but a refusal that never acquired a key. Sixty-two are transaction-validation invariants raised from pydantic field and model validators, where the text is consumed by pydantic's own error rendering; the rest are model-tier profile resolution, catalogue service guards, a classification-rule regex guard, and the language-model output parsers. None carries a rehoming ledger row and none contributes an action census candidate, so the campaign's adjudication never enrolled them. If the standing goal is that every reachable failed precondition emits a stable condition identity, these eighty-eight remain outstanding and no row currently covers them.
- Needs an owner, and it is a confidentiality concern rather than a messaging one. Four language-model parse refusals embed raw model output verbatim into the exception message: up to four hundred characters of the model's response, and up to one hundred characters of a candidate payload. That output is the model's reply about one specific transaction, so it can carry the counterparty, the narrative, and the amount, and it reaches tracebacks and structured logs from there. Sensitive financial data is supposed to live only in encrypted secure storage and never in logs. Migrating those messages to a key would incidentally remove the leak, but the correct fix is a deliberate decision about what diagnostic remains, not a side effect of a message sweep, so it is reported rather than half-done inside this Step.
- Needs an owner, second item. The base ledger-storage error still accepts a positional message argument at all. Removing it would make the positional shape structurally impossible for this class rather than merely policed, but ten of its construction sites live in the persistence adapter and belong to another Step, and every one of them passes a positional sentence today. Retiring the parameter is therefore a cross-package change, not a domain one, and was not attempted.
- What this changes about the owned rehoming rows, for the serialized ledger regeneration. This Step owns four rows on the ledger-storage error code. The three constructor rows keep their path, role, and lexical owner, and change their normalised syntax hash and their line span, because the argument list changed. The one reference row is the subclass declaration; its hash is location-independent and unchanged, but its line moved from seventy-three to eighty-three because the base constructor's docstring grew. One new reference fingerprint appears at module scope in the port module, where the message-key constant reads the class's bound error code. The ledger writer was deliberately not run and no disposition was edited.
- Gate results, with peer failures separated from the owner surface. The new module runs sixteen passed. The package suite plus the three direct consumer suites run two hundred forty-eight passed and three failed; all three fail identically with the head bytes of both modified modules restored in place, so none is owner surface. Two are a split-lineage expectation overtaken by a peer's constrained retype of the split group identifier, which now refuses before the sibling check the test asserts on, and one is an IVA category hint expectation against catalogue files carrying uncommitted peer edits. Lint and format are clean across the package. The static type checkers report no diagnostic in any modified file; the three diagnostics the package does carry are in a peer test module for withholding parameters.
- The recovery rehoming gate runs seventy-one passed and four failed. The ledger-storage error code appears among the fingerprint multiset findings, which is the expected consequence of changing three constructor sites before the ledger is regenerated. That finding is not introduced here: the same code's ledger rows already diverged from live source on the persistence adapter side, where two of the twelve recorded hashes have no live match at head. This Step adds three changed constructor hashes and one new module-scope reference to a divergence that was already open.
- The plan checkbox is deliberately left unchecked, pending adjudication.
