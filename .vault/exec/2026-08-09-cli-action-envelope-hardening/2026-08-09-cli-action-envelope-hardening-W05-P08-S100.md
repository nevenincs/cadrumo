---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:99fe17ef1b2d360e2a8e0b95256c00563a4a97e570987f73d9e153dac068fd23'
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

## Outcome

- The declared scope carries no operator-facing prose refusal. The access-gate module needed no change: both its producers were already key-rendered with facts, and the errors module holds only class declarations.
- Every migration reused a key already registered against its error class, so no new locale leaf was required in any of the four catalogues.
- One producer flattened its cause with a bare stringification of the raised validation error; the cause now survives as a registered error type alongside the field that failed.
- The drift and bundle-verification refusals had interpolated their file lists into a sentence. Those lists are now the typed added, removed, mismatched and missing tuples, which the context stringifier already renders as flat collections.
- One bare `ValueError` in a settings model validator became the registry-bound core validation error, so a producer that was previously outside the taxonomy entirely now binds to it.
- A live probe run from outside the repository confirms the migration is real and not cosmetic: the drift refusal's text no longer contains the diverged filename, so the assertion that matched on it would now fail, while the operator's rendered envelope carries the localised sentence plus the filename as a fact in both the text and JSON channels.
- Verification: the corpus-manifest suite passes 30 tests, and the scoped core suites pass 59, both run sequentially. The changed files are format, lint and type clean.

## Notes

- Scope was read as the declared file list rather than only the three families the step title names, matching how the sibling migration steps in this phase were executed. The settings module was therefore audited whole, which is why the Cl@ve identity and URL-template validators were migrated alongside the active-profile chain.
- A refusal raised inside a pydantic validator is re-wrapped, and the wrapper carries neither the typed context nor the message. This is not a regression introduced here: the CLI boundary already withholds any message a domain validator authored, precisely because such messages commonly interpolate the offending value, so the prose deleted here never reached an operator. What changes is that the facts now exist on the raised exception, which pydantic preserves under the violation context, where previously there was nothing to project. The timeout-hierarchy assertion was rewritten to read them through exactly that channel.
- Carry-forward: the active-profile pointer error authors its operator sentence twice, once as prose and once as a key, and only the catalogue half is ever rendered. The duplicated sentence lives on the class in the core errors module, which is outside this step's declared scope and already owned by an earlier step in this phase. Two assertions in the core storage-route classification suite still match on that prose and will need rewriting when it goes.
- Triaged as peer churn, not owner surface, each confirmed by inspection against HEAD: a storage-taxonomy test expecting an audit directory the taxonomy no longer materialises, which fails on the happy path where no refusal branch is reached; an exception-base hygiene gate naming a registry fixed-width codec class a peer added; a settings override test seeing a passphrase leak from the environment; and a route-literal gate naming hardcoded AEAT URLs in a peer's live IVA test.
- The step's real closing gate is the recovery-rehoming ledger, not a test suite, and it is RED across the whole producer phase. The ledger stamps fingerprint ownerships with an owning step, requires the owning step to be OPEN while its error qualname still has current source fingerprints, and requires each row's recorded fingerprint multiset to equal the live one. A message migration changes a construction's normalised syntax without removing the construction, so it invalidates the recorded fingerprints while leaving the row unable to leave its migration-required state. Nothing in the phase has been regenerating the ledger, so it has silently rotted: the gate reports 151 closed-owner violations naming twelve already-closed producer steps, and 46 fingerprint-multiset violations. The ledger was last regenerated at 06:07 on the day of this step, and every producer migration landed since has invalidated a little more of it. Of the two corpus entries, the drift error is this step's own; the manifest error was already violating from an earlier partial pass over the same module at 16:58 and this step compounded it.
- The row is therefore left UNCHECKED, deliberately. Checking it is the act that would add this step to the closed-owner list, and every earlier producer step in the phase was closed exactly that way. Regenerating the ledger was rejected as the fix here: the generator re-attributes every fingerprint to whichever open step covers its path, which would rewrite peer-owned rows wholesale and erase the evidence that twelve steps closed against an unmaintained ledger. That is a phase-level decision, not one this step may take on its own.
