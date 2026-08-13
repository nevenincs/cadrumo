---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:e395fbf01a7c0f22dd32160e4e52a6b36ba8628819fce1368a9c5c857cd0aa30'
step_id: 'S100'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate core corpus, access-gate, and active-profile exception producers to typed catalogue/live-input verdicts or explicit terminal/no-recovery dispositions

## Scope

- `src/cadrumo/core/corpus_manifest/__init__.py`
- `src/cadrumo/core/access_gate/__init__.py`
- `src/cadrumo/core/config.py`
- `src/cadrumo/core/corpus_manifest/_errors.py`

## Description

- Audit the four declared core modules for exception producers carrying operator-facing prose, a flattened cause, or an authored recovery.
- Migrate the six remaining corpus-manifest and corpus-bundle refusals to the message key already registered against each error class.
- Migrate the seven remaining settings refusals the same way, and replace the one bare `ValueError` producer with its registry-bound typed class.
- Carry the offending path, digest field, drift triple, timeout pair, placeholder and env var as machine facts in place of the deleted sentences.
- Rewrite the seven assertions that matched on removed prose so they read the typed facts instead.
- Second pass: pin every migrated producer with an absence assertion, so a re-introduced sentence fails a gate rather than passing one.

## Outcome

- The declared scope carries no operator-facing prose refusal. The access-gate module needed no change: both its producers were already key-rendered with facts, and the errors module holds only class declarations.
- Every migration reused a key already registered against its error class, so no new locale leaf was required in any of the four catalogues.
- One producer flattened its cause with a bare stringification of the raised validation error; the cause now survives as a registered error type alongside the field that failed.
- The drift and bundle-verification refusals had interpolated their file lists into a sentence. Those lists are now the typed added, removed, mismatched and missing tuples, which the context stringifier already renders as flat collections.
- One bare `ValueError` in a settings model validator became the registry-bound core validation error, so a producer that was previously outside the taxonomy entirely now binds to it.
- A live probe run from outside the repository confirms the migration is real and not cosmetic: the drift refusal's text no longer contains the diverged filename, so the assertion that matched on it would now fail, while the operator's rendered envelope carries the localised sentence plus the filename as a fact in both the text and JSON channels.
- Verification: the corpus-manifest suite passes 30 tests, and the scoped core suites pass 59, both run sequentially. The changed files are format, lint and type clean.

## Second pass: absence assertions

- The first pass migrated the producers but pinned nothing. That gap is the whole exposure this campaign is built around, because the two assertion shapes are not interchangeable: a key-and-context assertion stays green when an authored sentence is passed alongside a registered key, since message resolution prefers the key, while `str(exc)` prefers the positional argument and carries English into tracebacks, logs and every boundary that renders the exception directly, in every locale. Three new test modules assert the absence instead. The pinned form is `assert str(error) == error.translated_message, f"the raise site carries an authored sentence: {str(error)!r}"`, followed by an assertion against the key literal.
- Coverage is every producer in the declared scope that can be reached with real inputs: all four corpus path-traversal branches, the naive-timestamp refusal, the malformed, over-version and tampered manifest loads, the corpus drift refusal, all five bundle-structure refusals, the bundle-verification refusal, the live-read gate, the IVA timeout hierarchy, both URL-template placeholders, both DNI-date branches, and both storage-tree branches. Thirteen tests, all passing, no new locale key required because every key was already registered and already present in Catalan, English, Spanish and Hungarian.
- A refusal raised inside a pydantic validator is recoverable rather than lost: pydantic preserves the original typed exception under the violation context, and it embeds `str(exc)` in its own rendered text, so an authored sentence would leak through the wrapper as well. The validator-backed producers are therefore asserted on the refusal object itself rather than on pydantic's rendering of it.
- The gates are proven to discriminate. A plugin held outside the repository re-installs the defect at two representative producers, raising the same registered error with the same key and the same machine facts plus an authored positional sentence. Both gates red, and they red precisely on the absence assertion while the preceding key assertion passes, which is the discriminating evidence that a key-and-context assertion could not have caught it. Nothing under the source tree was mutated to obtain that proof.
- The absence gate immediately found a live defect the first pass had recorded as clean, and it is a worse shape than a positional sentence at a raise site. The permanent live-write refusal defaults an authored English sentence into its class's first positional parameter, so the in-scope producer, and every other call site in the tree, looks argument-free while the prose still reaches the exception's arguments. No raise-site scan can see it, and its error code is not a rehoming-ledger row, so the ledger never flagged it either.

## Notes

- Scope was read as the declared file list rather than only the three families the step title names, matching how the sibling migration steps in this phase were executed. The settings module was therefore audited whole, which is why the Cl@ve identity and URL-template validators were migrated alongside the active-profile chain.
- A refusal raised inside a pydantic validator is re-wrapped, and the wrapper carries neither the typed context nor the message. This is not a regression introduced here: the CLI boundary already withholds any message a domain validator authored, precisely because such messages commonly interpolate the offending value, so the prose deleted here never reached an operator. What changes is that the facts now exist on the raised exception, which pydantic preserves under the violation context, where previously there was nothing to project. The timeout-hierarchy assertion was rewritten to read them through exactly that channel.
- Carry-forward, unchanged and still open: the active-profile pointer error authors its operator sentence twice, once as prose and once as a key, and only the catalogue half is ever rendered. The duplicated sentence lives on the class in the core errors module, which is outside this step's declared scope and already owned by an earlier step in this phase. Two assertions in the core storage-route classification suite still match on that prose and will need rewriting when it goes. The second pass confirmed the leak is live rather than theoretical.
- Carry-forward, new: the permanent live-write refusal's class-default sentence, described above. The prose lives in the access-gate private errors module, which no step in the plan names, so it is unowned rather than contested. Both keys involved already resolve in all four catalogues, so neither fix needs locale work. Neither file was touched, because both sit outside the declared scope and the dispatch forbade widening it; both were escalated instead.
- The live-write test therefore asserts the terminal disposition and the argument-free raise site only, and its docstring states plainly that the absence assertion is deliberately withheld and why. Asserting the present behaviour would have pinned the defect as the contract, and deleting the test would have hidden a real finding; neither was acceptable.
- Triaged as peer churn or pre-existing, not owner surface, each confirmed against HEAD: a storage-taxonomy test expecting an audit directory the taxonomy no longer materialises, which fails on the happy path where no refusal branch is reached and whose file and taxonomy are both clean at HEAD; a settings override test seeing a passphrase leak from the environment; and four whole-tree scanners naming only peer files and documentation fixtures. The second pass re-ran the three owning packages and confirmed no failure names any of the new modules.
- The step's real closing gate is the recovery-rehoming ledger, not a test suite, and it is RED across the whole producer phase. The ledger stamps fingerprint ownerships with an owning step, requires the owning step to be OPEN while its error qualname still has current source fingerprints, and requires each row's recorded fingerprint multiset to equal the live one. A message migration changes a construction's normalised syntax without removing the construction, so it invalidates the recorded fingerprints while leaving the row unable to leave its migration-required state. Nothing in the phase has been regenerating the ledger, so it has silently rotted.
- The second pass measured the ledger rather than repeating the earlier estimate. Whole-tree validation reports 114 findings: 64 fingerprint-multiset and 50 closed-owner. This step owns two of the multiset rows, the corpus manifest error and the corpus drift error. For both, the live scan reports no authored message at any construction, so the rows are migrated by evidence and the residue is purely stale bookkeeping: eight recorded fingerprints in the two rows carry pre-migration hashes. The ledger writer was not run and the ledger file was not edited, as the dispatch reserved that regeneration.
- The row is left UNCHECKED, deliberately. Checking it is the act that would add this step to the closed-owner list, and every earlier producer step in the phase was closed exactly that way. Regenerating the ledger was rejected as the fix here: the generator re-attributes every fingerprint to whichever open step covers its path, which would rewrite peer-owned rows wholesale and erase the evidence that twelve steps closed against an unmaintained ledger. That is a phase-level decision, not one this step may take on its own.
