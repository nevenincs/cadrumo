---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1e496acb897104e79a3bf6b69bbe5279028934f5edfb59e5233f74d5e1d1cd45'
step_id: 'S40'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate live-read recovery producers with explicit safety dispositions

## Scope

- `src/cadrumo/application/live`

## Description

- Strip the authored English sentence from every live-owned refusal producer in the package, leaving the registered locale key plus machine facts.
- Migrate both shapes of the defect: the positional argument and the `message=` keyword.
- Key the two refusals that carried English and no key at all.
- Add a live-scoped closed precondition vocabulary and a no-recovery verdict helper, and give the live base error an optional verdict carrier exposed as `terminal_precondition_verdict`.
- Attach an explicit SAFETY no-recovery verdict to the evidence-integrity refusals; bind no recovery action.
- Add 39 refusal keys with real values to all four catalogues.
- Retarget every test that asserted on the deleted prose onto the registered key, and add an absence gate proven to bite on both defect shapes.

## Outcome

- Seventy-two raise sites in this package authored their own operator-facing sentence when the Step opened. Sixty-nine are migrated. The three that remain are `LiveIvaSurfaceTimeoutError`, whose constructor requires a message argument and one of whose three raise sites lives in the CLI entrypoint package, outside this Step's exclusive scope; migrating two of three would leave the row authoring anyway, so it is carried forward whole rather than half-done.
- The substantive finding is that the campaign's named defect was the dominant shape here, not an edge case. Twenty-seven sites across five modules already carried a correct registered key AND an authored English sentence in the positional slot. Resolution prefers the key, so a key-and-context assertion sees a clean refusal; `str(exc)` prefers the positional argument, so tracebacks, structured logs and every direct rendering carried English in all four locales. The keys those sites needed had been pre-staged in the catalogues at some earlier point and had no consumer at all, which is why the defect survived: the catalogues looked migrated while the producers were not.
- A second, quieter shape of the same defect was found that the whole-tree rehoming scan cannot see, because that scan tests only for positional arguments. Ten sites passed the identical English sentence as a `message=` keyword. The effect is the same in every respect, including which of the two `str(exc)` prefers, so a package that reports clean to the ledger can still be shipping English. This is worth generalising to the rest of the campaign: closing the ledger is not the same as closing the defect.
- Two of those keyword sites carried an authored sentence and no key whatsoever, so they had no migration target and are newly keyed rather than merely stripped.
- Six refusals now declare an explicit SAFETY no-recovery outcome, chosen because retrying them is not merely futile but actively harmful: stamping a captured justificante onto a filing whose CSV, axis or record it does not match, overwriting AEAT evidence already held against a filing record, stamping evidence with no resolvable filing tax identity, taking custody of a served document under a certificado it does not belong to, and persisting an AEAT observation AEAT no longer reports as active. No catalogue action is bound to any of them and no action was invented; the closed outcome exists precisely to stop a downstream boundary manufacturing a retry from the observation. Every other refusal in the package stays a plain typed refusal, because supplying a different id is an operator's ordinary correction and not a safety condition.
- The read-only consulta pinning and its fail-closed behaviour on a filing-tool or procedure-launcher landing were not touched, read or weakened. Nothing in this Step adds, enables or approaches a write, submission or notification path, and no live AEAT surface was contacted.
- A discovery worth recording: the snapshot-miss family inherits `KeyError`, whose `__str__` returns `repr(args[0])`. Its rendered form is therefore the quoted key, not the bare key. The absence assertion for that family compares against the quoted form; no locale-specific prose survives either way, but an absence check written naively against the bare key fails for reasons that have nothing to do with the defect.
- The gate is proven to discriminate. The committed modules were copied out of the repository, the authored sentence was reintroduced in both shapes, and the scanner reported exactly one offender each time, returning to zero on restore. The runtime half was proven the same way: the migrated construction renders the key, the defective construction renders the English while still resolving to the key, which is the invisibility the gate exists to remove. Nothing under the source tree was mutated to obtain either proof.
- The gate carries a fixture anchor asserting every class named in its roster still exists in the package, so a rename cannot silently shrink its reach and let it pass vacuously.
- Three hundred and seventy-seven of the package's tests pass and two fail. One failure is the absence gate reporting two peer sites that are uncommitted work in this shared tree, not present in the commit. The other passes in isolation and is an ordering interaction, not a product of this change. Ruff check and format are clean across the package.

## Notes

- The rehoming ledger writer was not run and the ledger file was not touched, as instructed. What this Step changes about its own rows: the two owner-closed findings are resolved on the committed tree, because neither owning qualname authors a message from any committed site any more, which flips the row's open-owner requirement off. The fingerprint multiset finding is NOT resolved and cannot be: the migration rewrote the surrounding expression at most sites, so every recorded fingerprint for the input-error qualname is now stale and the ledger needs regeneration before it can validate. A third qualname's rows also move, since the base live error's six authoring sites were migrated in the same pass.
- Two files in scope carry uncommitted peer work. The package facade carries a peer's notification-row resolver and document-pull verb; the notification-document module carries a peer's custody-conflict detection. Neither was discarded, reverted or overwritten. Both of this Step's edits to those files were rebuilt from the committed bytes and staged as own-only content, so the commit carries this Step's lines and nothing of theirs. The working copies of those two files are consequently stale, which is expected.
- Both peer additions introduce fresh instances of exactly the defect this Step removes: each passes an authored English sentence positionally beside a registered key. They are the sole reason the new absence gate is red in the working tree; it is green on the committed tree. They belong to their author to fix and are reported rather than edited.
- Three further files turned out to be moving under the work. The repository HEAD advanced twice mid-Step, and a first staging attempt would have reverted a peer's committed refactor of the notification-document module and a peer's committed restructuring of its custody test. Both were caught by scanning every staged removal for content this Step did not author, and both were rebuilt against the advanced HEAD before committing. A fourth file briefly carried a peer's staged typing change; by the time the commit was built that change had landed in HEAD on its own, so the final staged content adds none of it.
- The catalogue write path is not safe under this level of concurrency. Setting the keys one at a time performs a whole-file read-modify-write per key; over the roughly fifty minutes that took, peer writers repeatedly won the race and between twenty-six and twenty-nine of the keys were lost per catalogue, while the underlying atomic replace also failed outright with an access-denied error from the backing share. No peer key was lost to this Step in the process, which was verified against the committed bytes: the tool only adds leaves. Re-running the whole set through the batch verb, which performs one guarded read-modify-write per catalogue, landed all of them on the first attempt. The batch verb should be the default for any multi-key change in this tree.
- The catalogue drift check is red, on four keys belonging to a peer's in-flight operator-status work. It reports nothing against this Step's namespace, and all thirty-nine keys are present with real values in all four catalogues with no self-referencing placeholder.
- One in-scope test expectation was absorbed rather than left broken: a storage refusal it asserted on had been migrated to a key by another owner, and the assertion was retargeted.
- The box is deliberately left unchecked, for adjudication.
