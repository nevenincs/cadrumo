---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-19'
body_schema: 'body-v1'
body_hash: 'sha256:ca6f2c799080cdfdca356b6d1c251c5e7bba2269f0f3107f8a26b3f76d343840'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `storage and custody green sweep`

## Scope

A green-sweep of the storage, custody, secure-enrolment and profile-management
surfaces at HEAD after the per-profile password cutover, covering the backend
and the CLI, plus the residue the cutover left behind. Driven by the operator
goal of a verified profile lifecycle rather than by a plan row.

## Findings

### Four defects the cutover left at HEAD, all repaired

A wrong-package import of the snapshot-namespace constant in the profile
repository test module broke COLLECTION of the entire `user_profile` test
package. The constant has never been defined in the domain package it was
imported from; the sibling roundtrip module already imported it from its real
home. A whole package's coverage was silently unrunnable.

The setup-event emission gate still declared the wizard persistence adapter as
the emission site for the profile-values-updated event after the profile-fact
write door was relocated out of the wizard. The emission itself was alive and
correct at the new home, carrying the door payload key. This is a relocation
whose consumer sweep missed a gate, which the atomic-relocation discipline
exists to prevent.

The live IVA wallet test had the retired shared-master-key provider wrapper
mechanically swapped for the EPHEMERAL provider. That provider opens a throwaway
bucket session under a random key, so the block bound every read and write to an
ephemeral bucket while the test asserts against the operator's real active
profile. It also tripped the ephemeral-key storage hygiene gate. The canonical
sibling live test carries no key-provider wrapper at all, which is the
current-model shape. A mechanical rename during a teardown is not a semantic
substitution: the wrapper had to be deleted, not re-pointed.

Two public callables shared the name for exporting a recovery artifact -- the
application door taking an enrolment record, and the substrate narrowing that
door wraps. The package facade mapped the name to the SUBSTRATE one while every
other member of the recovery family mapped to the application module, so the
application door was unreachable through its own facade, and two live consumers
had already diverged on which signature the shared name meant. A duplicate
public name does not announce itself; it splits its consumers first.

### The scripted profile-create verb carried a dead arm

The create verb had two arms and only one worked. The bare form reached the
credential registration door; any invocation carrying profile field flags was
routed back to the setup flow, whose create arm refuses outright before it
validates anything. The flagged form was therefore a dead end -- and the
operator-action catalogue projects exactly that flagged invocation as the
recovery for a clean-root refusal, so the projected recovery could never
succeed. An agent operator following the projected action had nowhere to go.

The routing was justified on the grounds that the flow is where those values are
validated and that handling them at the door would drop them silently. That
concern was real, so the repair kept the validation and dropped the routing: the
flags are projected through the flow's own canonicalisation and handed to the
registration door, which had always accepted initial facts. The projection is
pure and runs before the passphrase is resolved, so a refused flag costs the
operator no prompt and leaves no capsule to undo.

### A guard that looked redundant was carrying the message, not the rule

The explicit foral-regime refusal in that projection appeared to duplicate the
CCAA question's own widget validator, and a first version of the new regression
passed with the guard removed. Removing it does still refuse -- but as a generic
wizard-validation failure instead of the domain refusal naming the Concierto
Economico and the foral tax office the operator actually has to file with.

The lesson generalises past this guard: a check that shares an outcome with a
deeper validator is not thereby redundant, because the OUTCOME is not the only
thing an operator receives. Asserting only that a run refused is what made the
case vacuous; asserting the specific refusal code is what made it bite.

### The tree-wide blocker is not in this domain

Every remaining failure in the profile and storage lanes shares one external
cause: the registry authority refuses to load while six modelo revisions claim
filing authority grade with families still blocked pending evidence. It cascades
into any test that needs a snapshot.

This also re-blocks the deferred carry-forward for the setup-incomplete
anti-tautology confirmation, and that row's blocker has CHANGED IDENTITY: the
missing corpus sidecar it was last attributed to has since been authored, and
what remains is the authority-grade tail. The surface belongs to the registry
temporal-coverage campaign, which is actively landing per-modelo closures, so it
is routed rather than absorbed.

### Recovery enrolment at creation is delivered at the CLI door

The enrolment mint is wired into the create transaction ahead of publication,
with the 24 words delivered through the handover channel BEFORE the capsule is
published, so a channel that cannot deliver aborts creation rather than leaving
an enrolled profile whose only key went nowhere. The CLI door passes a handover
and carries dedicated coverage. The outstanding deferral is narrower than the
row's wording suggests: it is the full-screen creation door only, whose
terminal-direct channel cannot render inside the full-screen display.

### The lifecycle was driven end to end, not inferred from unit results

Every verb was exercised against real encrypted storage rather than argued from
green tests. Create in both arms, list, edit, logout, delete, sealed-archive
export and inspect, and restore all returned success, and a full
create-with-facts, export, logout, delete, restore, login cycle returned the
profile with its facts byte-identical. The sealed archive was a real encrypted
artefact of a few kilobytes whose header inspects without decrypting.

Two refusals met on the way were correct rather than defects, and both name
their remedy: deleting the ACTIVE profile is refused and points at logout, and
a headless restore refuses to take a secret from a terminal that is not there
and points at the bounded stdin channel.

One apparent defect did not survive checking. Restoring under a NEW label is
refused on the ORIGINATING host even after the profile is deleted, which reads
like the archive carrying a label the export documentation says it does not
carry. It does not: on a genuinely fresh storage root the same archive restores
under a new label with its facts intact. What refuses on the original host is
the surviving label-head record, which keeps a UUID's label lineage after the
capsule is gone -- lineage protection working, not a leak. Deletion also
deliberately leaves its journal, receipts and holds behind, which the custody
decision requires: the audit trail must outlive the data it describes.

That fresh-root restore is the accepted decision's central promise -- a profile
password restores a backup on a fresh host without keyring access -- and it was
confirmed on a host that demonstrably has no keyring at all.

### The keychain failures are a property of the host, and provably so

Fourteen session-resume cases fail in the ordinary integration lane because the
Windows credential store refuses every call with "a specified logon session does
not exist", the error a non-interactive logon produces. That was measured
directly against the credential store rather than inferred from the failures.
They are unmarked for the credential-store lane, so they cannot pass on any
headless host including CI. Marking them would move fourteen cases out of the
default lane, which is a coverage decision belonging to the harness campaign
rather than a repair to make in passing.

### A refusal that named the problem and not the remedy

Logging in with no password channel refused with nothing but the fact that a
channel was required. The verb accepts four -- two machine channels, an
interactive terminal and an environment variable -- and custody can name none
of them, because they belong to the entrypoint rather than to the layer that
detects their absence. Each was driven end to end before being advertised.

The repair is worth recording for where it had to go rather than for what it
says. Refusing before the call is wrong: login legitimately proceeds with no
callback at all, since a configured passphrase and a resumed session are both
unlocked inside it, so an early guard refuses operators who had a channel all
along. The instructive refusal only becomes correct once custody has reported a
password failure AND no callback was built AND no passphrase is configured. A
wrong password offered through a real channel must fall through untouched:
telling that operator to supply a channel they already supplied is worse than
saying too little.

Two cases here also still asserted the pre-cutover exit code, from when this
condition surfaced as a generic secret-store failure rather than a typed
refusal. The misdiagnosis they were written to catch -- calling a merely locked
store an unreadable record and prescribing a destructive repair -- is a
diagnosis rather than a number, and is asserted as one now.

### Coverage survived a verb that was never built

Four cases drove a profile-duplicate verb. No such command exists and no
production module mentions one. Three failed against a command the CLI refuses
to parse; the fourth passed vacuously, asserting only a non-zero exit, which a
missing command satisfies exactly as well as a real refusal would. That is the
failure mode to watch for in a retirement: the negative case keeps passing and
reports the retirement as covered.

### Where the lanes finished, and what the residue actually is

The profile, storage and config-CLI integration lane ends at 307 passing and 14
failing, and every one of the fourteen is the session-resume family: the Windows
credential store on this logon answers "a specified logon session does not
exist", measured against the store directly rather than inferred from the
failures. Nothing else in the lane is red. The unit lane ends at 1718 passing
with five failures, all owned elsewhere -- a revision awaiting its review gate,
the wizard's IVA-block question change, and the locale sweep's missing keys.

Getting there turned up one pattern worth naming, because it accounted for most
of the residue and none of it was environmental. A fixture or a case would
assume a side effect of a door that has since been replaced: that creating a
profile leaves a workflow-state row behind, that registering one leaves it
unlocked, that a bucket holds only the row the case seeded. Each assumption was
true before the custody cutover and silently false after it, and each failure
read as a broken subject rather than a stale premise. The repair is always to
state the premise explicitly -- save the row, log the profile in, scope to the
namespace -- never to relax what the case asserts.

Two cases were asserting fields that had been deliberately retired: a rendered
"suggestion" string on the error document, and a pre-cutover exit code. A test
for a retired surface cannot pass without reviving it, so it is not a gap being
tracked, it is a permanent red that teaches readers to skip the module.

### The provider-named substrate is live; the ROTATION subsystem is what is dead

The storage package named for the retired shared-master-key model is not
residue. Its exported provider protocol is consumed by the rotation module, and
the encrypted blob store behind it is instantiated on a live path: the
certificate secret backend reaches it through the route-canonical secret-store
factory. What that factory shows is that the name outlived the model rather than
the code: the store falls through to the ACTIVE BUCKET SESSION's key when no
provider is passed, so "master key" now denotes the current per-profile session
key. The package name is stale; the mechanism under it is current, and the
protective refusal that stops a real profile opening on an unsecured backend is
live safety code rather than a leftover.

What has no production caller is the ROTATION subsystem: the module-level
rotate-master-key and rotate-blob-stores entry points, the default rotation plan
and blob-store roots, and both rotation result models. Every reference outside
the storage facade's own re-exports is a test of that module or the blob store's
same-named method that the module drives. Nothing in application, domain or
entrypoints calls any of it. That is coherent with the accepted custody
decision, which makes DEK rotation unsupported and puts credential rotation on
the profile passphrase instead -- the live verb is the passphrase group, routed
to the profile passphrase rotation service.

So the honest description is dead CAPACITY rather than dead code: a fully
implemented, fully tested rotation path for a key model the cutover retired,
exported from the facade and reachable by nobody. Retiring it is owner-gated,
because deleting a key-schedule path can strand encrypted data, and the check
that has to precede it is that the creation path mints only the current
schedule.

A method note, because it cost time and would cost the next reader the same: an
early sweep concluded the blob store was dead. It was not -- the sweep excluded
the store's own package directory to cut noise, and the one production
instantiation lives inside that directory, in the materialisation factory. A
liveness question cannot be answered by a search that filters out the package
being judged.

### A guard can be built, tested, gated -- and bypassed by the live path

The singleton catalogues share one defect shape: the document is a single
encrypted row, so adding, correcting or removing one entry rewrites all of them,
and two callers touching DIFFERENT entries lose one another's work. No
uniqueness check notices, because the two entries never meet. On a financial
catalogue the lost row is a dropped invoice, which under-declares.

The invoice catalogue had it on all three of its mutators. It sat on the
enveloped persistence, which carried no guarded seam at all while its bare-model
sibling did, so it was the singleton the earlier fix never reached. All three now
run inside the revision-guarded unit of work, through one shared helper, with
their refusals and merges inside it so a retry re-judges them against the
catalogue the write lands on.

The inventory finding is the more instructive one, and it generalises past this
codebase. The repository carries guarded create and record-movement verbs; a
routing gate asserts they stay guarded; concurrency regressions prove the guard
works. All of it passes. And the live path goes around it: the CLI calls the
application service, which does its own load, rebuild and blind save, so the
guarded verbs had no production caller at all. A guard that the operator path
does not reach is indistinguishable, from the test suite's side, from one that
works.

The service's create now delegates to the guarded verb, re-raising the adapter's
storage-level conflict in the layer's own words. Two sites are deliberately NOT
converted yet, because each carries a real design question rather than a
mechanical edit:

* Movement recording runs the domain valuation guard in the application layer,
  before persistence, on a document read outside the guard. Routing the append
  through the repository verb without moving that check would validate against a
  document the write never lands on; moving it into the adapter contradicts the
  stated boundary that the adapter stays calculation-free. The ordering has to be
  decided before the guard is applied.
* Removal has no guarded verb to route to; one has to be authored, mirroring
  create.

Recorded rather than rushed: a wrong move on the first would let an invalid
valuation persist, which is worse than the lost update it would be fixing.

### The audit trail was losing entries, and the calculation catalogue may be next

The bucket event history had the defect on both emit paths. It is the worst
place to have it: events are content-addressed, so every survivor is internally
consistent and a discarded one leaves no gap. The trail reads as COMPLETE while
an operator action has vanished from it, which is less trustworthy than a trail
that refuses, because nothing downstream can tell the difference. Everything
needed was already present and used on exactly one path -- a revision-aware
read, a write that already accepted an expected revision, and a capsule-record
co-commit that passed one. The generic emit functions did not, and now do.

The batch path reads the wrong way round at first glance: batching exists to pay
one round-trip for N events, so its read-to-write window is WIDER than a single
emission's and it can discard more at a time.

The calculation revision catalogue is the next candidate and is NOT converted
here, deliberately. It carries the same load-rebuild-write shape, and its write
is blind. But it writes through a co-commit batch that lands the catalogue and
the participation index in one transaction, and the index is derived inside the
same span from the revision being persisted. A retry therefore cannot simply
re-apply a prepared write set: the extra writes have to be rebuilt against the
catalogue the retry actually read, or the index co-commits against a revision
that lost. Getting that wrong desynchronises an index the deletion guards are
documented NOT to trust for correctness, but which is still persisted as truth.

This is the most safety-critical persistence in the application -- these
revisions carry filing evidence and casilla provenance -- so it wants a
deliberate decision about retry and derived-write rebuilding rather than the
mechanical port that fitted the other singletons.

## Recommendations

Treat the storage substrate package named for the retired shared-master-key
model as the next scoped effort rather than an incidental cleanup. It now houses
the LIVE per-profile session substrate -- bucket sessions, the login throttle,
KDF parameters, idle timeout -- under a package name describing a model the
cutover retired, and it still exports a provider protocol with roughly ten
consumers outside the package plus an unsecured-provider implementation with
about five. Some of that is genuine retired-provider residue; some is protective
code that merely carries a legacy name, such as the refusal that stops a real
profile being opened on an unsecured backend. Classifying those apart is the
work, and a name-driven deletion would remove a safety guard. A rename is a
relocation and must land atomically with every consumer.

Profile rename and profile duplicate are CLOSED as out of scope, not pending.
They exist in neither backend nor CLI, and the operator ruled on them twice, on
the reading that profile names are stable and that treating them as fixed is the
norm in comparable programs. A lifecycle sweep will keep surfacing them as
missing capability, so this is the record that their absence is a decision.

The costing, should the ruling ever be revisited: the label is written only at
capsule creation and a committed capsule has no in-place rewrite path, so rename
needs its own journaled transaction doing a compare-and-swap over the label-head
record rather than a field update. Duplication is the larger of the two, needing
a new identity, a new data-encryption key and a full re-encryption, because the
key is per-profile and its rotation is unsupported -- which puts it outside what
the accepted custody roll-up decided.
