---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:bffe964b2b68d776c4f429d024e5d0ad3be3417ae91ff7f6ff82c95033f69af5'
step_id: 'S152'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh repair the profile edit path that crashes with an internal error because two production sites stamp an event-type string the bucket event enum does not contain, noting that a contract test already documents the divergence as a missing catalogued emitter while nobody recorded that the string is rejected at validation, so its own suggested remedy assumes a validity the string does not have

## Scope

- `src/cadrumo/application/wizard/_persistence.py and src/cadrumo/application/wizard/_commands.py`

## Description

- Reproduce the crash end to end against a real encrypted profile capsule before touching anything.
- Add a closed `WizardFactWriteDoor` surface taxonomy to the wizard persistence module and export it from the package facade.
- Repoint every wizard fact-write door at `BucketEventType.PROFILE_VALUES_UPDATED`, carrying the surface in a `door` payload key.
- Promote the closed emission gap into the pinned required-emission set and strengthen its needle.
- Prove the gate bites on a reverted stamp without editing any tracked file.

## Outcome

**The crash is real, was reproduced, and is repaired.** Driving a real capsule — real custody envelope, real DEK, real encrypted secure-object store — the write refuses with `ProfileRecordIntegrityError: profile record command event is not a current bucket event`, raised from a `ValueError: 'profile.wizard.answers.applied' is not a valid BucketEventType`. Nothing is recorded: the record replacement and its event are one batch, so the whole command is lost, not merely its event.

**True state of enum versus stamped strings.** `BucketEventType` carries 115 members. The coercion point is a single line in the capsule writer that funnels the command's free-`str` event type through the closed enum; the intervening model types the field as a bare length-bounded `str`, which is why nothing refuses earlier and the failure surfaces deep in the writer as an integrity error rather than at the boundary as a validation error. Measured against the enum, **12 call sites stamp 9 distinct non-member strings**. Six are wizard doors (answers, patch, checkpoint, descendants — the last two never named in the row) and six are CLI config doors. Only `profile.censo.applied` and `profile.setup.completed` were ever valid.

**The row's warning was correct, and sharper than the contract test's own text.** The test's prose called the strings "un-catalogued", which reads as a benign taxonomy gap — a string that works but is not enrolled. It does not work. The enum is closed and the writer coerces through it, so the string is REJECTED and the operator edit path is not degraded but dead. Cataloguing those strings — the remedy that framing implies — would have been wrong twice over: it would enshrine a surface verb in the one slot that holds a single event per record revision and binds the row's lineage witness, and it would leave `PROFILE_VALUES_UPDATED` still emitterless, so the dead-capacity defect would survive its own fix.

**Repair chosen: repoint the doors at the existing correct member, and move the surface identity into the payload.** All four wizard doors now emit `PROFILE_VALUES_UPDATED` through the one shared writer, each passing a typed `WizardFactWriteDoor` member that lands as a `door` payload key beside the existing changed-fact count.

**Why the alternatives were rejected.** *Adding new taxonomy members* would multiply the closed enum by door — nine members for nine strings, each naming an operator verb rather than a data change, in a slot that admits exactly one event per revision; it is also the remedy the contract test's framing implied, and it leaves the declared member dead. *Not emitting at all* is not an available state: the record row REQUIRES a `source_event_id` witness and the read path refuses a row without one, so some event must be written, and the write is by definition a profile-values change. The ruling behind this choice is recorded under `S48`.

**Bite proof.** Reverting the production stamp to the surface string it used to carry, in a temporary copy fed to the real gate function from a scratchpad script, now reds the gate with the exact missing token named; no tracked file was modified, and the source was byte-compared before and after to confirm it. **The first attempt did NOT bite**, and that is the more useful finding: the gate matches file TEXT, and the bare-symbol needle was satisfied by the new prose cross-reference in the emitting module's own docstring, so a fully reverted stamp left the gate green. The needle now pins the emission expression rather than the symbol. The three pre-existing entries carry the same latent weakness but are sound today — each matches exactly one occurrence, which is its real emission.

**Verification.** The emission contract gate passes (3 passed) and was observed failing beforehand with the exact promotion instruction, so the closure was detected rather than assumed. All four doors were driven end to end and persist, with the bucket history showing four `profile.values.updated` rows carrying distinct door values and the record revision advancing 1 to 5. Lint and format are clean on every changed file; both type checkers report no errors on the wizard package.

The wizard, buckets and user-profile packages run 568 passed, 22 failed, 4 errors. **None of the failures is attributable to this change** — no failure mentions the new symbols, the writer, or the event taxonomy. They are peer breakage and pre-existing debt: registry validation errors, a `register_minimal_profile` signature mismatch from a half-landed relocation, login-session pointer handover refusals, locale drift, and a deliberate registration refusal. The import-hygiene and docstring-link gates run 11 failed, and the wizard package is named in none of them.

## Notes

- **Scope correction.** The row names two files; the defect spans four wizard modules and, beyond this agent's ownership, six CLI config call sites. All six wizard sites were fixed because leaving siblings crashing while repairing their neighbours would be incoherent. The CLI sites were NOT touched and remain broken: two in the manager frontend stamping `profile.manager.field.applied`, one in manager actions stamping `profile.auth.facts.applied`, one stamping `profile.manager.row.added`, one in the capabilities surface stamping `profile.capability.changed`, and one in the descendiente surface stamping `profile.wizard.descendants.changed`. Each needs the same one-line change; the door taxonomy was promoted to the wizard package's public facade specifically so their fix is a facade import rather than a private reach. Whether the door taxonomy should then move to a shared home is a judgement for whoever takes them.
- **The shared-writer parameter was renamed** from `event_type` to a typed `door`. This is a deliberate hard break for those six CLI callers: they were already 100 percent broken, and keeping a parameter named `event_type` that no longer selects the event type would have silently absorbed their invalid strings into a payload, converting a loud crash into a quiet wrong record. A signature break is greppable and type-checkable; the previous behaviour was neither.
- **A contract test outside the named scope was edited**, and this was unavoidable rather than opportunistic: the gate asserts that the member has NO production emitter, so the repair reds it by construction. The test's own failure message instructs exactly the promotion that was performed. Leaving it red would have been knowingly shipping a red gate.
- **Peer interference, reported not remedied.** Mid-task, a peer commit folded the setup package into user profile — relocating the contract test — and in the same commit captured this agent's uncommitted wizard edits. The repair is therefore already in history under someone else's commit message rather than sitting in the working tree. Nothing was reset, stashed or rewritten to undo it.
- **Not done:** no locale key was added or needed. No new event-taxonomy member was added. No surface events were introduced for these verbs. The latent bare-symbol weakness in the three pre-existing gate entries was left alone, since each is currently sound and they belong to other contracts.
