---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:8c1d8c50e0a637c1c53846386108408afbf21dcd6d70789472f0f867ff5222e9'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# `cli-action-envelope-hardening` audit: `rehoming ledger owner closed`

## Scope

The recovery-rehoming ledger and its whole-tree gate, audited because the ledger is the real closing condition for every exception-producer migration step in the campaign's producer phase, and the step rows do not say so. The audit was opened while executing one such step, when the step's own scoped test suites were green and the ledger was not.

Audited: the ledger data, its validator, its lexical scanner, the disposition vocabulary, and the join between ledger rows and plan step state. Covered are the 238 ledger rows, the twelve producer steps already closed against them, and the discharge path the ledger actually accepts.

Evidence is the shipped gate run whole, not a reimplementation. An earlier attempt to call the validator directly was discarded as an artefact: it reports failures even against an untouched plan because it skips the reconciliation the gate performs first, so any conclusion drawn from it would have been confidently wrong.

## Findings

### rehoming-gate-red | critical | The producer phase's closing gate is red on committed state

The whole-tree gate fails: 3 failed, 71 passed, 6 minutes 24 seconds. Two error classes, both structural rather than incidental.

The first is 151 occurrences of the closed-owner violation, naming twelve producer steps that are already checked in the plan: S38, S67, S89, S94, S96, S97, S101, S102, S103, S104, S106 and S114. The validator requires a row's owning step to be OPEN for as long as the row's error qualname still yields current source fingerprints. Every one of those steps was closed while its rows still did.

The second is 46 fingerprint-multiset violations, where a row's recorded fingerprint multiset no longer equals the live one. The ledger was last regenerated at 06:07 on the day of this audit; every producer migration landed since has eroded a little more of it, and those migrations run from 16:58 onward.

This is red on committed state, not on a working tree. Anyone reading the phase's plan checkboxes sees twelve closed steps; the gate that was meant to hold them says otherwise.

### migration-invalidates-fingerprints | critical | A correct migration invalidates the ledger without being able to discharge its row

The scanner's recording function observes every constructor and every reference of a target qualname in production modules, unconditionally, and fingerprints each by its normalised syntax. It does not ask whether the site carries a recovery.

A producer migration rewrites a construction's arguments, deleting an authored sentence and adding a registered message key with typed facts, and leaves the construction standing. So it changes the normalised syntax of each site, which invalidates the recorded fingerprints, while leaving the qualname exactly as observable as before, which is what forbids the row from leaving its migration-required state.

The two halves compound. Doing the step correctly guarantees the multiset violation; closing the step afterwards guarantees the closed-owner violation. That is why twelve consecutive steps produced the same result: the failure is a property of the mechanism, not of any executor's care.

### discharge-path-is-disjoint | critical | The only accepted discharge is ceasing to raise the error, which no migration step can do

The falsification test asked whether any row has ever left the migration-required state while its owner step is closed and its qualname is still observable. The answer is none.

Of 238 rows, 226 are migration-required and 12 are retired-or-unreachable. Of the twelve discharged rows, zero carry ownerships and zero have a qualname the scanner still observes. So a discharge path does exist and has been exercised twelve times, but never once for a class that is still produced.

Reading those twelve classes settles what discharge means. All twelve are still DEFINED in the source tree; a search for their construction and reference sites returns only their own class-declaration lines. They discharged because nothing raises them any more, not because they were deleted and not because their messages were migrated.

This is the outcome neither branch of the framing anticipated. The invariant is satisfiable, but only by retiring the error, and a migration step's entire contract is to keep raising it with better structure. The discharge path and the step's contract are disjoint.

### verified-dispositions-unreachable | critical | The three disposition kinds describing a completed migration cannot be stored

The disposition vocabulary is a closed enum of five members. Three of them, verified typed action, verified terminal no recovery, and verified nonproducer reference, name precisely the outcomes a producer migration yields. The producer step rows use the same words, offering typed catalogue verdicts or an explicit terminal or no-recovery disposition. Zero of the 238 rows carry any of the three.

They are not merely unused; they are unreachable. The validator branches once on whether the qualname has current fingerprints, and both arms exclude them. Mutating a live row to each of the three in turn and validating produced the current-migration-required violation for that exact qualname in all three cases. Mutating a discharged row to a verified kind produced the zero-disposition violation. Both arms were exercised against the real ledger, with the mutation applied in memory so no tracked file changed, and each result read as the difference against the unmutated baseline so the pre-existing failures could not be mistaken for the effect.

So the ledger declares a vocabulary for recording that a migration is complete and verified, and then refuses to store it. A step can do the work and has no way to say so.

### attribution-lost-to-a-bare-commit | medium | A tree-wide commit took another agent's uncommitted migration

The migration executed during this audit was swept into four commits authored by concurrent peers running bare commits over the whole index: two corpus-manifest passes, a settings pass, and a formatting pass. The work landed intact, verified before being trusted by confirming the migrated sites and the absence of prose remnants at HEAD, and by finding the executing agent's own comment prose there verbatim.

The loss is attribution, not content, and it cannot be corrected without rewriting history. It is recorded here and in the step record because those are the durable attribution channels. The same hazard is what the worktree discipline warns about: staging with a pathspec does not protect a commit that carries none.

## Recommendations

Do not regenerate the ledger to clear the red. The generator re-attributes every fingerprint to whichever open step covers its path, which would rewrite peer-owned rows wholesale and destroy the evidence that twelve steps closed against an unmaintained ledger. That evidence is the finding.

Do not resolve it by narrowing the scanner, adding an allowlist entry, or hiding the migrated constructions from the matcher. The repository's gates overlap and the tell for a wrong fix is oscillation; a change that satisfies this ledger while reddening another is a signal that a third shape is needed.

Do not treat the twelve closed steps as individually defective. The mechanism guarantees the outcome, so re-opening them one at a time would repeat the same result twelve more times.

A follow-on decision record must rule on what discharges a rehoming row for a step whose contract is to migrate a producer rather than retire it. The evidence here says the disposition rules are the defect and not the data: three verified kinds are declared for exactly this case and are unreachable, and the only accepted discharge requires the error to stop being raised. That decision governs what completion means for the whole producer phase and, retroactively, for twelve already-closed steps, so it belongs to the operator rather than to any executing step.

Whatever that decision is, it must also say how a row's recorded fingerprints are refreshed when a migration legitimately changes them, since that half of the breach recurs on every future producer step independently of the ownership question.
