---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:72dff1d7e2e8b03f4385befb77024baafc5cd7012f4bf608efafb2d7c234cda1'
step_id: 'S36'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate authentication and session recovery predicates and actions

## Scope

- `src/cadrumo/application/auth`

## Description

- Replace the authored English sentence at every registered-error construction in the package with the error's own registered locale key plus typed machine facts.
- Convert the failed-live-assertion diagnostic from a flattened English string into a fact mapping.
- Pin each migrated producer with an assertion that the rendered exception text degrades to the key.
- Repair one in-scope test left matching on prose a sibling migration had already removed.

## Outcome

- Twelve registered-error constructions authored a sentence at the raise site. Every one of them belongs to an error whose registered code already declares a message key, and message resolution prefers that key, so none of the prose was ever shown through the normal operator path. It was not harmless: the exception's own rendered text prefers the positional argument, so the English reached tracebacks, logs and every boundary that renders the exception directly, in every locale, while a key-and-context assertion stayed green. That is the defect this Step existed to remove, and the package now has zero such constructions.
- The confirmed whole-tree finding against the represented-party refusal is cleared. Its owner-closed error named a downstream reference Step, but the cause was the constructor in this package: the ledger validator demands an open owner for every site of a qualname while any site of that qualname still authors a message, so an unmigrated producer here reported as a defect against a closed Step elsewhere. Measured before and after against the same tree, that error is gone.
- Six structural rejections of a persisted diagnostic payload were distinguishable only by their sentences. They now share the one registered key and carry a validation_rule fact naming the check that failed, so the distinction survives as machine data a consumer can route on rather than prose a consumer would have to parse.
- The failed-live-assertion refusal previously built its diagnostic by flattening status, error text, landing host and path, and a cookie presence flag into one English-labelled string. It is now a fact mapping. The landing URL stays decomposed into host and path rather than carried whole, so a redirect query string, which is where AEAT carries session material, cannot enter the refusal; the cookie is still reported only as a presence flag. No credential, token, certificate secret or tax identifier enters any fact added here.
- The represented-party refusal is deliberately the one migrated site with an empty context. The only fact that failure has to report is the rejected tax identifier itself, and that value is identity-sensitive, so reporting nothing is the correct machine-fact set rather than an omission. Its regression asserts both that the rejected value is absent from the rendered text and that the context stays empty.
- Every migrated producer is pinned by asserting the rendered exception text equals the key. That assertion is the point of the Step: the key-and-context assertions beside it cannot fail against a re-introduced sentence, because resolution prefers the key. The proof is direct rather than argued. Re-introducing the pre-migration shape at three producers from outside the repository, passing the sentence positionally alongside the key exactly as the old code did, fails all three tests on the absence assertion and on nothing else, with the recovered sentence printed in the failure. Nothing under the source tree was modified to obtain that proof.
- One test in the package still matched on the word comma to tell one scope refusal from its siblings. That prose was removed by the sibling domain migration, so the test was already failing at HEAD before this Step touched anything, independently of this work. It asserts the typed validation-rule fact and the same absence property now.
- One test fixture built the phone-state error the pre-migration way and then asserted only that the envelope carried some message. It did: the rejected internal token itself. It now builds the error as the production site does and asserts the envelope carries neither the raw token nor the bare key.
- The package suite runs 330 tests, 321 passing. The two files this Step owns run 53 tests, all passing, serially. Lint, format and the type checker are clean across the package.

## Notes

- Nine of the package's tests fail, and none of them are this Step's. Six were reproduced failing against the pre-change bytes of the session module, so they are proven independent of this work; two more share their exact root cause, a missing Cl@ve route in the test environment, at a raise site this Step does not touch; the ninth asserts an active-profile pointer in the certificate-source surface, which this Step does not touch either. The tree also carries unrelated peer breakage outside the package, including a duplicate registry catalogue id that fails registry load.
- The rehoming ledger now reports a fingerprint-multiset mismatch for the three qualnames this Step owns, because migrating a constructor changes the normalized syntax hash the ledger records for it. That is the expected and necessary consequence of the migration, not a defect: the ledger regeneration that reconciles it is being serialized separately and was deliberately not run here, and no ledger entry was edited. Measured against the same tree, the whole-tree error count moves from 123 to 125: one owner-closed finding removed, three multiset findings added, all four in this Step's owned rows.
- No locale key was added or changed. All four keys the migrated producers now render through were already registered in all four catalogues, so the contended catalogue files were never opened. The locale drift gate is red, but on peer work: the four catalogues carry uncommitted edits this Step did not make, and every key the gate names belongs to other surfaces.
- The box is deliberately left unchecked, for the coordinator to adjudicate. Code review has not been run against this change.
- Two builtin-exception guards in the package still carry English text, and were left alone. They are internal programming invariants with no registered code and therefore no message key, so they carry none of the key-hiding defect this Step removes.
- The commit message for the source change says eleven migrated producers. The correct count is twelve, verified against the landed diff. The undercount came from an initial scan that looked only at raise statements and so missed a producer that is constructed and returned rather than raised, in the repository hook that relabels a storage row-identity refusal. That site was found by a second scan over every registered-error construction and is migrated in the same commit; only the message text is wrong, not the change. The message is left as landed rather than rewritten, and the correction is recorded here.
- No carry-forward.
