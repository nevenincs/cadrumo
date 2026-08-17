---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:d094d2d710447858f247b4fbcbee5d837d9a20898e67bd12dd98c1ccb2e4fdf7'
related: []
---

# `profile-password-custody` audit: `retired custody absence`

## Scope

The negative half of the custody cutover: proving that the retired shared-master
surface is not merely unused but unreachable, and that what remains of it is an
existence-only detector rather than a reader.

Audited across the whole source tree, by measurement rather than by reading:
whether the retired-path detector opens or parses any retired content; whether
any production path can still resolve a key from the deleted file store; whether
the application layer can reach a retired custody name; whether any path can
still WRITE a retired artefact; and what declarations of the retired surface
survive in the storage taxonomy, the error catalogue and the record models.

A negative claim is only as good as its instrument, so each check below states
how it was made. Two are mechanical AST scans, four are exhaustive name sweeps
across `src/`, and one is an existing gate re-run. Prose mentions were counted
separately from executable references throughout, because a deletion sweep that
cannot tell them apart either misses live code or chases docstrings.

## Findings

### retired-path-detector | low | The detector is existence-only, and this was verified mechanically rather than by reading.

An AST scan of the discovery module for every reading or parsing call --
`open`, `read`, `read_text`, `read_bytes`, `model_validate_json`, `loads`,
`parse`, `readlink` -- returns none. The single metadata call is an
`os.stat(..., follow_symlinks=False)` used only to decide whether a candidate is
a directory, which is existence and kind rather than content, and is explicitly
no-follow. The detector reports exact member NAMES below a named root and infers
no identity, so a caller can act only on the refusal and its reset guidance. The
claim the row asks to be proven holds, and holds for the reason the code says it
does.

### legacy-key-route | low | No production path resolves a key from the deleted file store.

Every surviving mention of `master.key`, `master.kdf` and `master.recovery.key`
across the tree is prose in a docstring or comment. There is no executable
reference: no reader, no writer, no path constant joined onto a store directory.
The active key is the unlocked bucket's own data key, resolved from the live
bucket session, and the secret store falls back to exactly that.

### application-layer-reach | low | The layering gate proves no retired custody name is reachable from the application layer.

The hard-cutover absence gate passes in full. It scans the application layer for
IMPORTS of retired names rather than asserting the names do not exist, which is
why entries for now-deleted classes correctly remain: they are reintroduction
guards, and its anchor case is deliberately silent once a name is gone
entirely.

### retired-artefact-write-path | low | Nothing can create a retired artefact.

The two retired member names are declared in one closed tuple each and appear
nowhere else as an executable reference. No path composes them for writing.

### dead-record-models | medium | Two models of the deleted on-disk KDF record survive with no consumer.

The master-key records module still defines the parameter model and the
version-gate model for the deleted `master.kdf` artefact. Both have zero
references anywhere outside their own module. Their siblings in the same module
are live and must stay: the envelope document is read by the unsecured-provider
tax-id refusal, and its fact model is that document's own field type. So the
module is live and two of its members are not, which is the case a
module-granular sweep cannot see.

### retired-artefact-still-an-expected-member | medium | One component refuses a store containing the retired manifest while another counts its bytes as an expected member.

The retired plaintext bucket manifest is declared as a current storage-taxonomy
member with no dormancy reason, and the bucket disk-usage verb enumerates it as
an extra file to measure beside the database directory, tolerating its absence.
Meanwhile the discovery refusal treats the presence of that same file anywhere
under the buckets root as grounds to refuse the whole store and demand a
destructive reset. The two behaviours are mutually exclusive: a store the
disk-usage verb could ever count it in is a store the detector would already
have refused. Nothing writes the file, but the declaration still presents a
retired artefact as an ordinary member of a current bucket.

Corrected on review, and the correction matters more than the original finding.
This was written as a binary -- either the member is retired and the taxonomy
should say so, or it is current and the refusal is wrong -- and the true state
fits neither. The NAME is live, the FILE is retired, and only the accounting
branch is wrong. The taxonomy member's consumer claim was therefore never
false: the detector really does read that name, for a real purpose, which means
giving the member a dormancy reason would have traded one contradiction for
another (the declaration model refuses a member claiming both a consumer and a
dormancy reason). A binary framing of a three-state situation produced a
proposed repair that would have broken the thing it was meant to fix.

The reachability claim above was also too generous to the code. Tracing rather
than assuming: `disk_usage` does not pass through the refusal at all. The
refusal has one caller in the tree, the capsule inventory; `disk_usage` reaches
its paths through pure path arithmetic that opens and checks nothing. So a
pre-cutover store can be measured while every other custody path refuses it,
and it is measured *including the very file that makes it refusable*. The
branch is reachable in principle and unreached in practice -- `disk_usage` has
no production caller anywhere, only its own test module -- which is the worst
combination for a latent defect, because nothing exercises the contradiction
and nothing would notice it appearing.

Resolved: the accounting branch is removed, the constant and the consumer claim
stay, and the claim now points at the detector -- the load-bearing reader that
needs the name -- rather than at the layout module that merely re-exports it.

### retired-filename-declared-twice | low | The retired manifest filename is declared independently in two places with no link between them.

It is a storage-taxonomy member with a subpath, and separately a literal inside
the detector's closed tuple. Neither reads the other. A rename or correction to
one would silently leave the other stating the old value, and the detector is
the half whose correctness is load-bearing.

Resolved by making the detector read the taxonomy member rather than re-type
it. The direction was chosen deliberately: the load-bearing half must not be
the copy that can drift, and if the member is ever deleted outright the
detector now fails loudly at module load instead of quietly recognising
nothing. Loud is the correct failure mode for a refusal path.

### stale-prose-describing-the-deleted-store | low | Two modules describe the deleted on-disk record as a current mechanism.

The KDF parameter module and the records module carry docstring prose
describing the on-disk `master.kdf` record and its version gate as present.
The code they document is gone. Scoped to two rather than three on re-check:
the master-key module's own header was already rewritten in the past tense
when the providers were deleted, and counting it here was this audit
overreaching by pattern-matching a filename rather than reading the sentence
around it -- the same conflation of prose with executable reference that the
scope section warns about.
This is the false-stated-reason class the campaign has corrected repeatedly:
prose that was true when written, that nothing re-checks, and that a later
reader inherits rather than re-derives.

## Recommendations

Delete the two dead record models with the artefact they describe. They are
in-lane, have no consumer, and are the last executable residue of the deleted
on-disk format.

Keep the retired manifest's name and drop only its accounting. The decision
this recommendation originally asked for was posed as a choice between two
options, and the answer was a third: remove the disk-usage enumeration, keep
the filename constant, keep the consumer claim but point it at the detector,
and state in the declaration that the member names a retired artefact kept for
recognition so the next reader does not repeat the inference that a declared
member is a current one.

Bind the retired filename to a single declaration so the detector and the
taxonomy cannot disagree. Done, with the taxonomy as the declaration and the
detector as its reader.

Correct the two stale docstrings to describe the deleted store in the past
tense, naming per-profile capsule custody as what replaced it, so a reader
meeting them does not conclude the file store is still a live route.

Every check above is repeatable and each states its instrument, so a later
reader can re-derive the negative claims rather than inherit them -- which is
the property this audit exists to leave behind, more than any single finding.

## Lessons

A gate that cannot see a failure class reports the same green as a gate that
checked for it and found nothing. This campaign produced the lesson three
separate ways: a suite run selected on one marker reported a lane green while
an integration-marked module in it had never executed; a dead-export scan
rooted at one source tree reported a symbol unconsumed while a sibling tree
consumed it; and a retired-artefact declaration passed every liveness check
because its consumer claim was true, while the branch that actually
contradicted it sat in a different package the check does not reach. In all
three the output was indistinguishable from a real pass. The defence is not a
better gate but a stated instrument: an assertion of absence has to name what
it looked at, so a reader can see the shape of what it could not have seen.

Its companion, learned the same way: measuring the wrong thing and reporting
the measurement honestly is still a wrong finding, and the correction is worth
more visible than tidied away. Three findings in this audit were revised on
re-check -- a module count, a reachability claim, and the framing of the
manifest contradiction itself. Each revision is recorded beside the original
rather than replacing it, because a finding that was wrong once tells a later
reader where the reasoning is slippery, and a silently corrected number tells
them nothing.

A binary framing is itself a finding worth checking. The manifest
contradiction was posed as two mutually exclusive options and the true state
was a third; worse, one of the two proposed repairs would have violated a
model invariant. When a situation resists both branches of a clean either/or,
the framing is the thing to re-examine before the code.
