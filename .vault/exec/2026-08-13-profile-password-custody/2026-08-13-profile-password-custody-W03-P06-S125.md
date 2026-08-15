---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:a0b494d6cbfe892a2b9e865bc9a61140c7aa3f9e7ecb61410681a6da2b0313ad'
step_id: 'S125'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule whether the retired-member refusal should stay whole-store, since one leftover plaintext manifest in any bucket directory makes the profile listing verb exit two with destructive-reset guidance and an operator cannot then enumerate their profiles to find the offending file, which may be intended under the no-legacy regime but currently leaves no path from the refusal to its cause

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/_capsule_discovery.py`

## Description

- Rule the refusal's radius, on the regime rather than on the scan's shape.
- Observe what the operator actually sees today, by running the listing verb against a
  planted retired store.
- Pair each detected retired member with the root it was found under, from existence
  facts alone, so the refusal names its cause as well as its remedy.
- Audit the refusal for states that do not warrant it.

## Outcome

**The ruling: the refusal stays whole-store.**

Four reasons, in ascending order of how hard they are to work around.

First, the remedy is the store. Under the no-legacy regime there is no code that may
read, adopt, or migrate a retired custody member, so there is no bucket-scoped repair to
offer. A narrower refusal would name a smaller blast radius without making any smaller
action available, which is worse than the current message rather than better: it would
imply a targeted fix that does not exist.

Second, narrowing requires an identity claim the boundary refuses to make. "The affected
bucket" means asserting that a particular directory IS a retired profile — an identity
inferred from the presence of retired custody. Discovery itself declines that inference:
a directory name is only a candidate there until the current commit marker opens and
binds it. Refusing the inference on the read path while making it on the refusal path
would be the same rule spelled two ways.

Third, half the detector has no bucket to narrow to. The retired shared-master key
material sits under the keystore root, which is a sibling of the buckets root, not
anything nested inside a bucket. A per-bucket radius is not merely undesirable there, it
is undefined — so a narrowing would silently fall back to whole-store on that arm and
the one refusal would carry two different radii depending on which arm fired. That
inconsistency is a worse operator surface than a uniform radius.

Fourth, and this is the claim that a narrowing would have to defeat: a store carrying the
retired plaintext manifest is a store in which at least one profile's authority is the
retired one, and the system cannot say which without reading the thing it is forbidden to
read. Enumerating the remaining capsules would answer "these are your profiles" from a
store that is provably not wholly current-format, with no way to qualify the answer. That
is a stronger claim than "one bucket is stale", and nothing available at this boundary
supports it.

So the radius stands, and it stands for the regime rather than for how the scan happens
to walk. What does not stand is leaving the operator with no route from the refusal to
its cause.

**What the operator actually saw, before this row.**

Established by running the listing verb against a planted retired store rather than by
reading the code: the verb exits two and prints the refusal token, both scanned roots,
the recovery-guidance pair, and a flat list of detected member names.

An earlier row in this campaign had already added the roots, and that closed the worst of
it — the refusal no longer prescribes destroying a store whose location it withholds. Two
gaps survived it.

The first is that the member list is a flat union across both roots. With one member
detected the pairing is recoverable by luck; with two it is lost outright, and the
operator is given two names and two directories with nothing connecting them. The reverse
case is sharper: a store carrying only retired key material still reports the buckets
root, and the buckets root has nothing wrong with it. That is the same failure an earlier
row warned about — sending an operator to clear a directory whose removal leaves the
refusal standing — reached from the other direction.

The second is that the detected member's depth was never stated. The scan looks at
exactly one depth, one level below a scanned root, and the operator had no way to know
that.

**How the dead end closes, on existence facts only.**

Each firing arm now contributes its own key: the members found below the capsules root
under one key, the members found below the keystore root under another, and an arm that
did not fire contributes nothing. The two roots are still both named, unchanged, because
both are the prescribed remedy — that earlier ruling is preserved deliberately, and the
new keys sit beside it rather than replacing it. The refusal now separates the two
questions it was conflating: which directories the reset covers, and where the cause was
seen.

Each member is reported as a root-relative search pattern with the candidate directory
left as a wildcard. The wildcard is doing real work in three ways. It encodes the depth
the scan looked at, which is a property of the scan and not of the store. It is directly
usable — the operator pastes it against the named root and lands on the file. And it
withholds exactly the one thing the detector refuses to infer, the candidate's identity.

There is also a mechanical reason a literal candidate name would have been useless even
if the design permitted it, and it was observed rather than assumed: a candidate name is
a UUID, and the operator envelope's redaction funnel rewrites a bare UUID to its
profile-id placeholder. A refusal naming the directory literally would have reached the
operator with the useful part replaced. The wildcard survives the funnel intact.

Nothing here opens, reads, parses, or digests a retired member. Which name matched, below
which root, at one depth, is what the existing anchored no-open scan already observed;
this row stopped discarding it.

**Audit of states that do not warrant the refusal.**

The fire condition is the existence of an exactly-named member one level below a scanned
root. Both inventories are closed and both members' production writers are gone, so no
current-format code path can create either — the presence of one is unambiguous evidence
of a retired store, which is what makes the destructive guidance proportionate. The
residual false-fire is an operator hand-placing a file with one of those two exact names,
and fail-closed is the right answer there.

The scan's use of a link-tolerant existence check is deliberate and left alone: a
dangling link or a directory bearing a retired member's name still fires. Narrowing to
regular files would trade a fail-closed posture for a marginal reduction in a false-fire
class that has no known instance.

The guidance itself was checked for being more destructive than the situation requires
and was left unchanged, because under the ruling above the store is the unit. What was
wrong was not the severity of the instruction but the absence of a route to its cause,
and that is what this row addressed.

**What is still missing, and is not mine to land.**

The refusal's operator-facing message is the raw token, with no prose. The context is
readable but the message line explains nothing, and the recovery guidance renders as two
more raw tokens. Closing that needs an error-registry or locale change outside this
package's ownership; it is reported to the campaign lead with concrete values rather than
landed here, because a message key without its four catalogue entries reds a shipped
gate.

**Verification.**

The custody package suite plus the three consumer modules that exercise this refusal pass
sequentially in full: 186 passed, 0 failed. The two existing refusal-context assertions
were updated to the enriched context, and three cases were added: a store retired in both
roots asserting the full pairing, a keystore-only store asserting the buckets root
contributes no match, and a proof that the candidate directory's identity appears nowhere
in the refusal.

The operator surface was re-observed after the change against both a both-arms store and
a keystore-only store, and renders as intended.

The wider storage, user-profile and workflow suites report failures that are not
attributable here; the attribution is recorded in the sibling record for the other row
executed in this session, measured by re-running the same set against a runtime reversal.

Linter, formatter and both type checkers are clean on every module changed here.

## Notes

The instinct on reading this row is to soften the refusal, and that would have been the
wrong deliverable. Two earlier rows had already established the radius as deliberate on
grounds that survive re-examination, and the row's own question — whether whole-store is
correct — has an affirmative answer that is stronger than it looks from the operator's
side. The work was in separating the remedy from the cause, which were sharing one set of
fields and therefore answering neither question well.

The keystore-only case is the one that convinced me the flat union was a real defect
rather than a cosmetic one. A store whose buckets tree is entirely current would report
the buckets root as though it were implicated, and an operator acting on that clears the
wrong tree and sees the same refusal again.

The detector's buckets arm still names its retired member with a local literal while the
storage taxonomy declares the same name and marks it retired. That duplication predates
this row and was left alone, as an earlier row in this campaign also chose to; unifying
both against the taxonomy remains a reasonable follow-up.

Nothing was committed from here.
