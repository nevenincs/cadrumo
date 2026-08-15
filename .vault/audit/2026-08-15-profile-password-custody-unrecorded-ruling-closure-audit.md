---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:0b846e793a6ff138afae81a47e7b00088f4aee8b6eb21807580c84367f49e382'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `unrecorded ruling closure`

## Scope

Every closed (`[x]`) "Have Sol Medium/Terra XHigh rule / decide / triage / confirm
or refute / reconcile" row in the plan, cross-checked against its execution
record in the feature's exec folder and against the rest of `.vault/` for any
earlier, untraced ruling episode on the same question. Twenty rows matched that
pattern: `S32`, `S40`, `S44`, `S51`, `S54`, `S59`, `S62`, `S70`, `S73`, `S77`,
`S91`, `S107`, `S115`, `S121`, `S126`, `S133`, `S134`, `S156`, `S158`, `S159`.
Every one of the eighty-five closed steps in the plan was also cross-checked
mechanically against the exec folder's filenames for the narrower question of
whether a matching record exists at all.

## Findings

### unrecorded ruling closure | high | one confirmed instance, self-reported and self-repaired inside `S59`, no other document names it

`S59`'s own execution record states plainly that the row "cost roughly twice
what it should have, because the ruling it assumed existed had been delivered
as a report and never persisted," and that establishing its absence took "a
full search of the execution folder, every audit of the week, and the corpus
by both keyword and meaning." I re-ran that search independently — `rg` across
`.vault/` for the phrase and for "seventeen operator command subtrees" turns up
only the plan row and `S59`'s own record. No exec record, no audit, no earlier
draft of this row exists anywhere in the corpus that carries the missing
ruling. It is not mis-filed or under-titled; it does not exist as a document.
The only trace of it left in the entire vault is `S59`'s own account of having
had to reconstruct the tree's true state from scratch because the prior
verdict was gone. This is the literal case the row was dispatched to close:
a decision made and reported, with nothing durable behind the report.

### unrecorded ruling closure | none-found | zero further instances among the twenty ruling rows read in full

Every one of the other nineteen rows was read end to end, not sampled by
heading. Every one states its verdict as prose a reader can act on without
re-deriving it: `S44` names which callers raise and why; `S62` states which
layer owns the manifest and which facts fall to which authority, including a
correction where the dispatcher's own relayed severity claim was withdrawn
inside the same record rather than left standing; `S91` counts the population
before renaming and states which twenty-three hundred occurrences were
deliberately left alone and why; `S107` states the ownership test that
separates a wipeable-buffer ruling from an immutable one and records it as an
enforced invariant, not prose; `S115` and `S126` and `S133` each argue a
durability class from what is lost on unreadability rather than from
neighbouring entries, and `S133` explicitly walks its own earlier exclusions
backward when a later argument falsified them; `S121` records a first ruling
that was wrong, states why, and lands the corrected one in the same document;
`S134` and `S156` each divide a question that looked singular into the
populations that actually govern it and state which one is answered today and
which is not; `S158` and `S159` each resolve a layering question by reading
what the code does rather than by principle, and record that the same
principle was tested and answered oppositely in the sibling row. None of these
twenty records is a stub, a pointer to a chat transcript, or a restatement of
the row's own question. **This campaign's ruling rows are, at the point of
closure, uniformly better-recorded than the failure mode `S105` was dispatched
to find** — with the one exception above.

### unrecorded ruling closure | informational | mechanical completeness (closed step has a matching exec file) holds at 85/85

A script cross-referencing every `[x]` step id in the plan against the exec
folder's filenames found zero closed steps without a matching record. Three
still-open steps (`S127`, `S142`, `S148`) already carry a scaffolded record —
one of them (`S148`) is scaffolded with an empty Outcome, which is the correct
shape for a record created ahead of dispatch and is not a finding.

### unrecorded ruling closure | medium | the direction nobody watches produced no confirmed instance in this pass, and that absence is not a structural guarantee

I looked specifically for a ruling that WAS persisted but that states something
narrower than the row asked it to decide — the case where the checkbox and the
document both exist but quietly answer less than the question. I did not find
one among the twenty rows read. Every observed narrowing was itself named in
the record as a deliberate scope limit, not left implicit: `S91` declined a
roughly twenty-four-hundred-occurrence sweep and said so; `S133` classified
two of "roughly a dozen" formats and left the rest in an explicit
awaiting-classification state, raising that count rather than hiding it;
`S126` excluded the capsule's directory categories from enrolment and stated
the reason. None of these read as a narrower answer disguised as a full one.
That is a genuinely clean result for this pass, not a standing property of the
system — nothing mechanical checks it, so the absence of a finding here means
"not found by one reader on one day," and the next reader inherits no
detector, only this note.

## Recommendations

**Close this row on the evidence above; do not treat the clean sweep of
nineteen rows as grounds to skip auditing future closed ruling rows.** The one
confirmed defect (`S59`'s predecessor) is already fully repaired by `S59`
itself; there is nothing further to remediate in that instance.

**A mechanical closure condition exists today only for exec-record existence,
and only in one direction.** `vaultspec-core vault check exec-mapping` verifies
that every execution record maps to a live Step in its plan (record → step);
it does not verify the reverse (a closed step → a matching record). This
campaign's 85/85 result was produced by author discipline, not by a gate — the
CLI currently cannot fail a commit that checks a Step with no record behind
it. Extending `exec-mapping` (or a sibling `structure` check) to walk plan
Steps marked `[x]` and require a matching exec filename would make that half
of the orchestration clause — "no plan step marked complete without a matching
exec record" — gate-enforced rather than honor-system. That is a CLI change,
out of this row's ownership (`.vault/audit/` only), and is recorded here as
the concrete shape the next implementer needs rather than executed.

**What no mechanical check can ever cover is content fidelity: whether the
Outcome section states an actual verdict, and whether that verdict answers the
full question the row posed.** `S59`'s predecessor ruling and the
narrower-than-decided direction both live entirely in this second, unwatchable
half — a document can pass every structural check (exists, non-empty,
correctly linked) while still stating nothing, or stating less than it
decided. The only defence found in this campaign's own practice is the one
`S121`, `S133`, `S62` and `S91` demonstrate: a later reader re-deriving the
answer instead of trusting the prior record, and writing the correction into
the same document rather than a silent second pass. That is a discipline, not
a gate, and the campaign-close fresh-context honesty review this row's own
governing rule already prescribes is the existing mechanism for it — nothing
new is needed there.

**Governing-rule fit.** The closest existing clause is in
`aeat-agent-orchestration`: "No plan step marked complete without a matching
exec record ... or a close audit recording the deferred carry-forward." That
clause is intact and was followed here — the gap this row found sits outside
its scope rather than inside a violation of it. The clause presumes a ruling
is always dispatched against a plan Step; `S59`'s predecessor ruling was
apparently produced and reported before it had one, so no Step-completion
check could ever have caught it — there was no checkbox to leave unmatched.
If a sentence is ever added to that clause, the shape that would have caught
this specific failure is: a verdict relayed only through team messaging is not
a ruling until it is written to `.vault/` — the same "reference direction is
one-way" discipline the corpus already applies to code-versus-vault, applied
here to chat-versus-vault. That sentence is not added by this row, per the
retirement of rule authorship; it is named here for whoever next edits that
rule.
