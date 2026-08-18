---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:f9d9baec6d2d290f5341c957af84a73c1a26bf377fb02026b745a49cb8e839c3'
step_id: 'S18'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium review CLI and TUI secret handling, typed outcomes, bootstrap exemptions, and local-only operator guarantees

## Scope

- `src/cadrumo/entrypoints/cli/`

## Description

- Reviewed the two sibling rows' delivered surfaces against the secret-handling,
  typed-outcome, exemption and local-only mandates, treating them as an
  inherited stranger's work rather than as this session's own.
- Ran the descriptor channel's behaviour probe from outside the repository and
  read its disagreements as findings rather than as probe defects.
- Corrected two findings in place where the fix was a truthfulness repair to
  the sibling rows' own prose; recorded the rest.

## Outcome

**Seven findings against the sibling rows' own work. Two were corrected in
place, one was corrected during construction, and four stand as recorded
costs. A review of three rows of new surface that found nothing would not be
credible, and this one did not have to strain.**

### Corrected during construction — the descriptor one-shot guard was wrong

The first implementation of the one-shot descriptor channel kept a
process-local register of consumed descriptor numbers. The probe refused a
legitimate second descriptor, and the reason is structural: the operating
system reissues a freed descriptor number immediately, so the number behind
which a caller stages a SECOND, genuinely different secret is very often the
one the first read just released. The guard would have fired on the first run
of any verb collecting two secrets. It was deleted; the close is the
enforcement, and a second read of a closed number surfaces as unreadable
rather than as an empty payload. Recorded here as well as in the sibling
record because it is the strongest available evidence that the probe was doing
real work: the design that failed was the one that LOOKED safer.

### Corrected in place — the retention refusal overclaimed

The deletion verb's guard docstring said this refusal and the all-profile one
"cannot drift into stating different law about the same records". That is true
of the NUMBERS, which both read from one assessment, and false of the
DECISION, which is written twice: the all-profile flow tests the blocking flag
together with a recorded override, and the single-target verb tests the flag
alone. A third condition added to the retention contract would reach one site
and not the other. The claim is now scoped to what it can support and the
duplication is named as a known cost with its owner. An overclaiming comment
is worse than none — this campaign has already found four false stated reasons
in production prose, and this would have been the fifth.

### Corrected in place — the login-gated list's block comment became false

The single-target deletion verb was added to the login-gated verb list, whose
block comment declares its entries to be the paths the operator-surface
contract declares for the profile restore, export and import surface. The new
entry is not part of that surface and rests on a different ground entirely:
nothing leaves the store, the capsule is destroyed in place, and what gates it
is irreversibility plus the fact that the custody primitives destroy a capsule
WITHOUT opening it — so the mechanical target-scoped reasoning that frees the
other two frees this one most easily of the three. The comment now says the
list is not limited to one surface and that each entry stands on its own
ground, because a single shared justification silently extends to verbs it
does not fit.

### Standing finding — the curated help now advertises a path that refuses

Restoring the deletion verb added a curated help entry for it. The preflight
posture works; the confirmed posture refuses inside the custody layer for a
defect neither sibling row owns. So an operator who follows the help through
to confirmation meets an opaque custody refusal about legal-hold owner facts,
which tells them nothing they can act on. This is the same class of defect a
closed row fixed in the opposite direction — help advertising an unregistered
verb — and it was introduced here knowingly rather than by oversight, because
the alternative was to withhold the help entry and leave a live verb
undiscoverable. It should be revisited the moment the custody defect is
closed, and if that closure is delayed the honest move is to withdraw the help
entry rather than leave the misroute standing.

### Standing finding — the machine secret is never wiped

Both machine channels read plaintext secret bytes and hand them to a
`SecretStr`. Neither the raw bytes, the decoded string, nor the extracted
secret value is zeroed; they remain resident until garbage collection. The
custody layer maintains a zeroisation primitive, so the capability exists in
the tree and is simply not reached from here. This is NOT a regression — the
stdin channel behaved identically before — but the descriptor channel's
documentation emphasises one-shot hygiene, and a reader could reasonably infer
a stronger memory guarantee than is delivered. Recorded rather than fixed,
because wiping a Python string is not achievable without changing the type
carried across the whole channel, which is a design change and not a review
correction.

### Standing finding — a time-of-check gap on the active-profile refusal

The deletion verb refuses the ACTIVE profile by comparing the resolved active
bucket to the target before it does anything else. The target lock is acquired
later, inside the destruction step. Between the two, another process could
select the target and the destruction would proceed against a profile that had
become active. The window is narrow and the tool is a single-operator local
CLI, so this is a real gap of low reachability rather than a live hazard.
Closing it means resolving the pointer under the same lock, which the locking
primitive supports; it was not done because the check must run BEFORE the
preflight for the refusal to be cheap and instructive, and moving it inside
the lock would make the preflight acquire a destruction lock it does not need.

### Standing finding — the secure-input locale gate cannot see the new keys

The gate asserting that custody secure-input refusal keys resolve to real
operator copy iterates a hand-authored tuple of four key names. Six new
refusal keys were added by the sibling row and are not in it, so the gate will
stay green while those keys render fallback text at the exact moment an
operator is locked out. This is the hardcoded-inventory shape the quality
rules name: the denominator encodes a moment instead of a property. The
correct fix is to derive the key set from the module's own refusals rather
than to append six names. That module belongs to another owner and was not
edited; the six keys are reported with the fix direction.

### Reviewed and found sound

The secret never reaches `argv`: the descriptor NUMBER is the only thing on
the command line, and the probe confirms the value does not render in a repr.
Refusals are typed and localised through the registered boundary error, not
bare strings. The deletion verb's diagnostics ride the typed notice channel
rather than a bespoke next-step or advisory field on the result payload, and
the notice text embeds no executable invocation. The result schema was
rewritten to describe what the verb actually returns rather than the retired
tombstone semantics it inherited, and it deliberately drops a field no
production path can populate. Nothing in either row writes a secret, a
decrypted byte or a profile record outside the encrypted store — the deletion
verb reads a sessionless assessment and destroys in place, and no temporary
file, scratch directory or log receives anything. Every test drives a
temporary storage root; no destructive action touched a default store.

2026-08-18 fresh-context re-review (HEAD c382f9f171): all five axes PASS, no revision required — the row closes clean. Secret handling: `--secrets-fd` bounded to 8192 bytes, closed on every refusal path, duplicate-key rejection at any depth, strict SecretStr models, zero `--passphrase` argv anywhere, channel precedence prefers the staged callback over the env channel, interactive prompts refuse on echo-indeterminacy. Typed outcomes: every reviewed verb's OutputSchema is a typed model with enum IDs and nested fingerprints — no dict bags, no key material in payloads. Bootstrap exemptions: closed enum with per-entry criterion and checkable citations; export/import/SAR not exempt; the S113 recency principle is data (`LOGIN_GATED_VERB_PATHS`) and both gates green (68 passed). Local-only: login/logout/rotate/restore/delete are all custody/pointer/file operations with no remote-write reach. TUI login: masked input asserted by test, zero env reads, typed secret zeroised in a finally. Two LOW notes stand: the login closure holds a plain str for the call duration, and `Input.value` itself cannot be unmade — both process-lifetime bounded and documented in-code.

## Notes

Reviewing one's own work has a known failure mode: the reviewer re-derives the
author's reasoning and agrees with it. Two things limited that here. The probe
disagreed with the design on its own terms, which is not something the author
can talk it out of. And the three surviving prose findings are all cases where
the sibling rows' own STATED reason was stronger than what the code delivers —
which is the class this campaign has repeatedly found, so it was the class
looked for first rather than a class stumbled into.

The finding this review would most want a second reader on is the curated help
entry, because it is the one where the reviewer and the author have the same
incentive: withdrawing it makes the delivered work look smaller.

No commit was made and no plan checkbox was set. Every capture lives under the
session scratchpad directory, not the repository.
