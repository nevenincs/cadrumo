---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-20'
body_schema: 'body-v1'
body_hash: 'sha256:e3d68859c68a823b52d5933c262a7a027b805b058db3157d8ac76f3bc69f3664'
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

### Cross-profile isolation is structural, and that is the finding

The multiuser question splits in two, and only one half was a defect. The
lost-update half was real and is fixed across the singleton catalogues. The
ISOLATION half -- can one profile's session reach another profile's rows --
turns out to be enforced by construction, and it is worth recording as a
positive result because a surface reading of the code suggests otherwise.

Fourteen production sites hand a caller-supplied bucket id to the bucket-scoped
repository resolver. That looks like fourteen chances to read the wrong
profile. It is not. Both resolvers funnel through one storage-runtime object
whose repository accessor requires readiness and a current active session
first, and readiness raises a route-mismatch the moment the requested bucket
differs from the session's. A caller cannot obtain a repository for a profile
the active session does not serve, no matter which id it passes, because the
check sits at the single point every path crosses rather than in each caller.

The one carve-out is narrow and safe: a synthetic session id used by test
fixtures skips the mismatch comparison. It is a bare word, not a UUID, and
every real profile id is a UUID, so it cannot collide with a real profile.

The custody half of the same boundary is covered independently -- one profile's
password envelope and one profile's recovery artifact each refuse to open
another's capsule through the real unlock and restore authorities.

What remains is coverage-shaped rather than security-shaped, and should not be
described as a hole. A table of runtime repositories asserts each refuses both
an absent session and a route mismatch, and that table is hand-maintained with
no completeness gate: two profile-scoped stores, the LLM run telemetry and the
LLM consent ledger, do not appear in it. They are protected anyway, because
protection is structural -- they are untested, not unguarded. A completeness
gate deriving the expected set from the resolver's consumers would close the
difference between "we tested the ones we listed" and "we tested every one that
exists".

### Two-catalogue writes: one was precedent, one is ordering, two remain open

The reconciliation writer persisted the invoice and transaction catalogues with
two independent saves. A crash between them rests one-sided -- an invoice citing
a transaction that does not cite it back -- which is exactly what the link
consistency check reports. That needed no new decision: the sibling LINKING
writer already commits both in one batch and its docstring says why in those
words. The path that establishes and removes those links simply had not
followed. Worth separating from the genuinely open questions, because it looked
like the same problem and was not one.

The live evidence-stamp path carries a different shape. It writes the
justificante, then the filing record that cites it, then the audit event, as
three separate writes. The ORDER is load-bearing and was documented nowhere: the
receipt lands before the record cites it, so a failure between them leaves an
orphan receipt, which is harmless and re-runnable. Reversed, it leaves a filing
record carrying live-capture evidence whose justificante does not load -- and
that record CLEARS the cross-period clean-state gate's missing-justificante
blocker on the strength of evidence that is not there. Correct today, silently
fragile to anyone tidying the sequence, so the constraint is now stated at the
write itself. Making the pair one unit of work would retire the dependency
entirely and is the better end state; it restructures three writes across two
early-return branches, so it is named rather than attempted here.

That leaves the co-commit RETRY question genuinely open on four catalogues. It is
not the atomicity question, which the composed write already answers. It is that
a retry cannot re-apply a prepared write set when the sibling writes were derived
inside the same span -- the participation index is derived FROM the revision
being persisted -- so the derived writes must be rebuilt against whatever the
retry actually read, or the index co-commits against a revision that lost.

A note on this tree, since it bit twice in one session: a peer's broad commit
swept an uncommitted working-tree edit of mine into their own commit. The code
and its comment survived; the commit message explaining the hazard did not,
which is why the reasoning is recorded here. In a shared worktree the durable
place for a rationale is the source comment or this document, not the commit.

### The widest lost-update window, and an evidence claim not made

The filed-evidence enrolment read the filing catalogue, parsed every
justificante PDF in the observation, and wrote the catalogue once at the end.
The read-to-write window therefore spanned N PDF parses -- by some distance the
widest singleton write this campaign found -- and anything another caller wrote
to that catalogue inside it was discarded.

Parsing now happens first and the stamping inside one guarded unit of work,
which is possible only because the stamping is a pure function of the parsed
receipt and the catalogue it is handed: a retry re-stamps against the catalogue
the write lands on without re-parsing a PDF. The accumulators clear per attempt
so a retry cannot double-count what it reports. The receipt still lands before
any record cites it, and that ordering is now stated at the write.

The honest limit on the evidence, recorded because the commit message carrying
it was lost. The change is green across its own coverage and both suites sit at
their pre-existing baseline, but NO bespoke concurrency proof is claimed for this
path. Reverting the verb to load-and-save does red existing cases, and the
reaction could not be attributed to the lost-update property specifically. An
unexplained red is not evidence for whatever one happens to be fixing, and
treating it as such is how a suite comes to look like it proves more than it
does. The guard's own behaviour is covered at the seam it shares with the
invoice, inventory and work-unit paths.

### Working in this tree costs rationale, twice over

Two separate peer commits swept uncommitted working-tree edits of mine into
their own, mid-iteration, while verification was still running. Both times the
code and its source comments survived and the commit message did not -- and the
commit message is where the caveats live.

The practical consequence for anyone working here: the verification window
between editing and committing is minutes long, and a broad commit landing
inside it takes the change without its reasoning. Commit narrowly and early, and
put anything that must survive into the source comment or this document rather
than the commit message.

### A legal entity can reach filing with a natural person's surname in its name field

The domain unit lane has exactly one failure left, and it is real. A profile
declaring `entity_type = legal_entity` with `identity.surnames` set and no
`identity.legal_name` passes preflight as READY, and its sibling case with a
short `identity.name` does too.

What that costs downstream is specific. The export producer maps the AEAT
"Apellidos o Razon Social" header to `surnames or legal_name`, and its own
comment states the assumption it rests on: the two are "mutually exclusive by
construction -- a natural person carries surnames and no legal_name, an entity
carries legal_name and no surnames". Nothing enforces that any more, so the
profile above resolves the field to the SURNAME, and a company files under a
natural person's surname. Silently, and in the header AEAT identifies the filer
by.

The enforcement existed and was removed. A preflight method collected the
required HEADER fields from the revision's export layouts and, when any
name-shaped header was required, demanded `identity.legal_name` from a legal
entity and both name parts from a natural person. It went in the typed-producer
integration commit, which left its four module constants behind, defined and
referenced nowhere -- which is how the loss stayed invisible.

The paired tests show why nobody noticed: the ACCEPTING case (entity WITH a
legal_name is ready) passes vacuously once no requirement exists, and only the
REJECTING case detects the loss. A positive test that passes for the wrong
reason is worse than no test, because it reads as coverage of exactly this.

Restoring the old method verbatim will NOT fix it, and this is where the choice
lies. Modelo 202's 2026 revision declares no required headers at all, so the
original early return fires and the check never runs. Three ways out, with
different blast radii:

* Make the legal-entity requirement unconditional in preflight. Defensible on
  its own terms -- an entity without a razon social is an incomplete profile
  whatever it is filing -- but it changes preflight for every modelo.
* Encode the conditionality in the profile schema, which is where a fact like
  "a legal entity needs a razon social" belongs. Today none of `name`,
  `surnames` or `legal_name` is required and none carries a `required_when`, so
  the schema says nothing about entity type at all.
* Treat modelo 202's registry data as the gap and declare the required headers
  its layout should carry, which restores the original conditioning and belongs
  to the registry campaign.

RESOLVED, and none of the three was needed. The premise that this was a design
choice was wrong: the mechanism already existed and already had a branch for
exactly this taxpayer. `conditional_profile_required_paths` in
`application/user_profile/_completeness.py` is the declared home for cross-field
completeness -- its own docstring says static requirements belong to the schema
validator and cross-field ones belong here -- and it already carried a
legal-entity branch requiring `taxpayer_type.legal_entity_form`, with a comment
explaining that the schema's `required` axis is unconditional so the conditional
requirement lives here. The razon social is the same shape of fact about the
same taxpayer, and it was simply absent. Adding `identity.legal_name` to that
branch is a one-line extension of an established pattern, not a new policy.

This also answers the blast-radius worry that made the three options look
expensive. The requirement fires only for `entity_type = legal_entity`, so a
natural person's preflight is untouched -- which is why "changes preflight for
every profile in the product" was the wrong reading of option one. Measured
rather than assumed: the failing gate now passes, and the failure sets of
`application/user_profile`, `domain/user_profile`, `entrypoints/cli/_config`,
`application/overview`, `application/wizard`, `application/flows` and the CLI
work-readiness suite are byte-identical with and without the change. Zero
delta.

Two cautions for whoever reads this next. The requirement closes the missing
half of the exclusivity, not both halves: a legal entity now owes a
`legal_name`, but nothing yet refuses one that ALSO carries `surnames`, and the
producer's `surnames or legal_name` fallback would still prefer the surname in
that state. The forbidden direction is the one a conditional rule usually omits,
and this module already models it elsewhere -- `atribucion_socio_forbidden_country_paths`
exists precisely because a rule that only asks for a value when it is due leaves
the prohibited case to whatever the operator typed. The same treatment is owed
here and is not done. Separately, the measurement above is narrower than it
looks: `application/filing` and `application/modelo` could not contribute a
baseline because both lanes are entirely red at HEAD for an unrelated reason
recorded below.

### The filing runtime demands a filing-grade snapshot from a modelo declared not filing-grade

Found while trying to measure the blast radius of the change above, not looked
for. `application/filing` and `application/modelo` are entirely red at HEAD --
106 and roughly 600 failures respectively -- and neither is a parallel-run
flake: a single test reproduces it sequentially under `-n0`.

One cause. `build_runtime_schema_provider` at
`src/cadrumo/application/filing/runtime.py:517-531` walks EVERY loaded modelo
and asks each for a snapshot; when it is called without a filing year and
period, any modelo whose snapshot refuses aborts the whole provider rather than
being skipped. Modelo 036 now refuses, because
`registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/revision.toml`
declares `authority_grade = "applicability"` and the filing-grade snapshot check
rejects a revision that is not reviewed:

    RegistryValidationError: modelo 036 revision 2025-02-03-y-siguientes is
    'pending_review'; filing-grade snapshot requires a reviewed revision

The demotion itself is right and its own comment says why -- this application
reads the censal declaration through censo synchronisation rather than producing
it, so there is no filing artefact to emit. That is precisely the point: a
provider assembling FILING schemas has no business demanding a filing-grade
snapshot from a modelo that declares it has no filing artefact. The demotion did
not create a bad revision; it exposed a provider that cannot express
"applicability-grade, therefore not mine". The refusal is doing its job.

Left to the registry campaign deliberately, with the locators above so it does
not have to be rediscovered. It is their data and their code, both actively
moving (`ddfa6640af` demoted fifteen revisions, `1a1adc9db8` retracted export
layouts across nineteen modelos), and the choice between skipping non-filing
grades in the provider and re-reviewing the demoted revisions is theirs to make.

Worth stating plainly for anyone reading a green report from this campaign: two
whole application lanes are red at HEAD for this reason, and no storage or
custody work in this audit was measured against them.

A SECOND registry breakage landed during this session, distinct from the one
above and worth separating so neither hides the other. Commit `241ef0acc3`
swept casilla `source_refs` across the modelo tree to drop a stale procedure
reference, and removed evidence that many modelos still require: registry
validation now fails with `modelo 100 revision 2020: filing schedule
modelo-100-2020-anual requires official_source_guidance source evidence` and
the same for its cross-references, application links and deadline windows,
across multiple revisions. Anything that validates the registry reds, which is
why a profile-schema lane measured at 2 failures before that commit measured 28
twenty minutes after it.

The practical consequence for this campaign is a measurement one. Lane counts
taken at different moments are not comparable while another campaign is landing
registry sweeps, so every claim in this audit rests on a failure-set DIFF taken
either side of a single change, never on a total. A green total here would be
the less trustworthy number.

### Concurrent failed logins collapsed the brute-force throttle

FIXED. `record_login_failure` in
`adapters/persistence/storage/master_key/_login_throttle.py` read the sidecar,
added one, and wrote it back with no mutual exclusion. Overlapping attempts all
read `n` and all write `n + 1`, so a burst of `k` wrong passwords advanced the
counter once.

The counter is not incidental to this control, it IS the control: the caller
evaluates `min(2 ** n, 60)` seconds of required wait BEFORE running any
Argon2id derivation, specifically so the KDF cannot be used as a
passphrase-testing oracle. A collapsed counter leaves a burst of eight wrong
passwords facing the two seconds owed to one. Producing the burst needs no
privileged position, because the surface is a local CLI: run the login verb
`k` times at once.

On Windows it was worse than an undercount. The overlapping writes collided in
the atomic rename and the function raised `PermissionError` (WinError 5) out of
the security control. It is called from inside the caller's
authentication-failure handler at `application/user_profile/_login_session.py:1136`,
so that exception REPLACED the wrong-password error the operator needed to see,
and the attempt went unrecorded as well. The operator gets `Access is denied`
about a sidecar they never heard of.

Closed under `core.exclusive_file_lock` rather than a new primitive -- it is
already this codebase's cross-process answer and already carries the operation
lease repository. A write that still cannot be persisted now logs and returns
the on-disk state instead of propagating, which is the policy the sibling
`reset_login_throttle` already documents in its own docstring and which the
increment path simply never adopted.

The sidecar's documented tolerances were deliberately NOT extended. A missing,
unreadable or version-mismatched file still reads as "no active throttle",
because that direction protects a legitimate operator from being stranded by a
local-CLI self-DoS. A lost increment runs the other way -- it only helps
whoever is guessing -- which is why it was never one of the declared
tolerances and should not have been treated as covered by them.

The regression was written and run against unmodified HEAD BEFORE the fix,
where it failed on the WinError 5 collision. That ordering is the point: an
oracle authored after a fix asserts whatever the fix does.

### The master-key provider lead resolves the other way: the residue is a protocol nothing may implement

The standing lead read the `master_key` package as retired-model residue
exporting `MasterKeyProvider` to roughly ten consumers and
`UnsecuredMasterKeyProvider` to five. Enumerated against HEAD, that is not what
is there, and the correction matters more than the original count.

Every `MasterKeyProvider` reference outside the `master_key` package is itself
INSIDE `adapters/persistence/storage` -- blob_store, envelope, secret_store,
_rotation and the package facade -- and nearly all are type annotations on an
optional parameter or Sphinx roles in docstrings. There are ZERO consumers
outside the storage package. The only cross-package references anywhere are to
`EphemeralMasterKeyProvider` in `cadrumo/tests/master_key.py`, which is a
separate harness class that satisfies the protocol structurally rather than an
import of it.

The protective code carrying the legacy name is live and should not be touched.
`refuse_unsecured_bucket_with_real_profile` and `refuse_unsecured_with_real_nif`
are the NIF canary, and they fail CLOSED in every branch that cannot prove the
profile synthetic: an unreadable bucket DB, an undecryptable payload, and an
unparseable profile all raise rather than admitting the published key. The
package also houses the LIVE per-profile session substrate -- bucket sessions,
KDF parameters, idle timeout, the login throttle above. A name-driven deletion
takes all of that with it.

The sharp finding is a different shape than the lead expected, and it is a
contradiction rather than dead code. `_provider_enter` at
`master_key/_master_key.py:248` refuses EVERY provider except one concrete
class:

    if not isinstance(provider, UnsecuredMasterKeyProvider):
        raise MasterKeyMaterialMissingError(...)

So `MasterKeyProvider` is not an extension point. It is a one-member closed set
enforced by an isinstance check at runtime -- while still being exported from
the storage facade's public `__all__`, where it reads as an interface someone
may implement. Anyone who does is refused at session-open time by a check that
names a class rather than a capability. Whether the honest form is a narrowed
export, a documented closed set, or a capability check rather than an identity
check is a design call and is left with the owner; recording it as "provider
residue awaiting deletion" would have been wrong in both directions, since the
protocol is load-bearing internally and the thing that is misleading is its
publicity.

### Multiuser safety: what was checked and what was not

In-process session isolation is sound and deliberately so. The active-session
binding is a `ContextVar`, so each thread and each asyncio task carries its own
session and an encrypt path cannot observe a sibling context's key; child tasks
inherit by PEP 567 copy-on-create, which is the same logical session extending
rather than a leak. `_live_sessions.py` is an in-memory `WeakSet` guarded by a
`threading.Lock`, weak by construction so the registry never extends the
lifetime of key material it exists to destroy, and its docstring is explicit
that it must never be used to FIND a session to work with. It documents its one
blind spot -- a thread cannot see another thread's binding -- and justifies it
against the case it exists for, `os._exit` reaping from a watchdog thread.

Cross-process coordination is where the defect was, and the throttle was the
one found.

CORRECTION to the sentence this entry first carried. It said no concurrent-access
test drives two live processes against one profile. That was wrong about the
bucket lockfile, which is covered thoroughly and cross-process:
`storage/bucket/tests/test_lockfile.py` spawns real holders and asserts busy
detection, eventual acquisition under wait, stale reclaim from a genuinely dead
PID, and a child process failing to inherit its parent's local ownership. The
gap was one layer over, and stating it too broadly would have sent the next
reader to re-verify work already done.

The real gap, now closed, was `profile_custody_root_lock`. It is the mutual
exclusion behind EVERY custody pointer mutation -- the application pointer
transaction and custody compare-and-swap take this exact identity -- and no
test in the tree named it or its `profile_custody_local_lock` leaf. The primitive
guarding the more dangerous mutation had none of the coverage its bucket sibling
has, so its docstring's claim that "sibling processes retain kernel-enforced
exclusion" was prose nothing executed.

Four behaviours were probed empirically before anything was asserted, and all
four held: a second process is refused while the lock is held; the lock is
acquirable again once the holder is KILLED; the owning thread may re-enter; a
sibling thread may not. The second is the one worth stating plainly, because it
is the load-bearing difference from the bucket lockfile. This lock has no
recorded PID, no liveness probe and no lazy takeover, so nothing in this
codebase can reclaim it from a dead holder. Correctness rests entirely on the
kernel dropping the exclusion when the process goes -- and had that ever
regressed, one crashed login would wedge every custody mutation on the machine
permanently while the exclusion test kept passing.

`pid_is_alive` was audited alongside and needs no change. Every ambiguous branch
resolves to "alive": permission denied, a foreign or protected process, a PID
recycled onto something unqueryable. The Windows probe additionally goes through
`OpenProcess` + `GetExitCodeProcess` rather than `os.kill(pid, 0)`, which reports
terminated-but-cached PIDs as alive. The residual over-conservative case -- a
process exiting with code 259, indistinguishable from `STILL_ACTIVE` -- fails
towards never reclaiming, which is the safe direction for a lock.

What remains genuinely unexercised, and should not be read as cleared: no test
drives two live processes through a full concurrent `login` against one profile
at the CLI level. The primitives beneath it are now covered on both sides; the
composition of them is not.

### The secret-store backend setting offered three modes that no longer existed

FIXED. `SecretStoreBackend` advertised `auto`, `keyring`, `file` and
`unsecured`, and `Settings.cadrumo_secret_store_backend` described them to the
operator as real choices:

    auto = OS keychain when available, encrypted file fallback otherwise.
    keyring = OS keychain only (refuses to fall back).
    file = encrypted file only (required for CI / headless).

None of that was true. The keychain-backed and passphrase-derived file-backed
master-key providers were deleted in the per-profile custody cutover -- the
`master_key` module's own docstring records their removal -- and the ONLY
production branch on this setting anywhere in the tree is
`is not SecretStoreBackend.UNSECURED`, in the Google OAuth flow. `KEYRING` had
zero references of any kind. `FILE` appeared only in test fixtures, where it
meant nothing more than "not unsecured". The axis was a boolean wearing the
costume of a four-way choice.

The damage was operator-facing, not merely cosmetic, and the worst line is the
one that reads most helpfully: "file = encrypted file only (required for CI /
headless)". A headless operator follows that, sets
`CADRUMO_SECRET_STORE_BACKEND=file`, and believes they have configured an
encrypted file key store. They have configured nothing. The curated operator
help surface said it too, in the isolation recipe reached from the root landing
-- "set CADRUMO_LOCAL_STORAGE_ROOT, CADRUMO_SECRET_STORE_BACKEND=file,
CADRUMO_SECRET_STORE_DIR and CADRUMO_SECRET_PASSPHRASE" -- so the CLI was
actively handing out an instruction that selected nothing. That surface is one
the CLI-contract rule already names as unscanned by gates and swept by hand,
which is exactly why it kept a retired value alive.

The set is now the two states that exist, `auto` and `unsecured`, with the
description saying which is which and the enum docstring recording why the
other two are gone. Removed rather than tolerated: `=file` and `=keyring` now
fail Settings validation instead of parsing into a value nothing reads, which
is the direction the no-legacy regime requires -- refuse, do not tolerate.
The isolation recipe drops the variable entirely, in the shared translation key
and all four catalogues through `dev.locales`, because `auto` is the default and
needs no setting.

One naming question is deliberately left open rather than decided here. With the
set reduced to two, `auto` no longer describes automatic selection among
anything; it now means "the profile's own password custody". Renaming it would
be the more honest spelling and would also break every operator env file and
`env/.env.example`, so it is a call for the owner rather than a cleanup to
absorb.

Two collateral notes. `docs/reference/environment-overrides.md` is generated
from the settings model and was ALREADY stale at HEAD before this change -- it
still listed `CADRUMO_KEYRING_PROBE_TIMEOUT_S`, deleted earlier in this
campaign, and lacked a peer's newer KDF-calibration setting. Regenerating it
necessarily picks up those rows too; the page is generated output catching up,
not a sweep of peer work, and its drift gate was red before and is green now.
Separately, the first sweep covered `src/cadrumo` only and left one
`SecretStoreBackend.FILE` in `dev/locales/tests/`, found by re-running the
search across both roots -- a reminder that this repo's `dev/` tree consumes
core enums and is outside the habitual search path.

### The confidentiality fence around the published key had no test

COVERED. `UnsecuredMasterKeyProvider` returns a PUBLISHED deterministic key and
provides zero confidentiality by design. The only thing between it and a real
taxpayer's records is the NIF canary: `refuse_unsecured_with_real_nif` and
`refuse_unsecured_bucket_with_real_profile`, resting on the
`looks_like_real_tax_id` predicate.

None of it was tested. `looks_like_real_tax_id` had no coverage of any kind, and
neither refusal function was named by a single test in the tree. The one file
mentioning `UnsecuredModeRefusedError` covers the Google OAuth surface. The
prior entry above judged this fence sound by READING it and said so; that
reading was right, but a read is not a gate, and this is the load-bearing
confidentiality guarantee of the application.

Behaviour was probed before anything was asserted, and two results are worth
recording beyond the obvious ones. A whitespace-padded real NIF still
classifies real, so the canary canonicalises rather than string-matching --
which matters because the value arrives from operator input where padding is
ordinary and a raw comparison would be defeated by one space. And an id whose
digits are a real NIF's but whose check letter is wrong (`12345678A`) is
ADMITTED: it fails to parse, so it is treated as synthetic. That is defensible,
since an id failing its own check digit identifies nobody, but it is a decision
sitting one refactor away from mattering -- loosen tax-id parsing to tolerate a
bad check letter and the fence silently widens onto real people's numbers. It is
now pinned so that change reds here first.

Both failure directions are asserted, and both were proven to bite by patching
the predicate from a pytest plugin outside the repository. Neutralised towards
"nothing is real", the refusal cases red; forced to "everything is real", the
synthetic-admission cases red. The second direction is not padding: a canary
hard-wired to refuse satisfies every refusal assertion while making unsecured
mode unusable, and would read as a working fence. Nothing under `src` was
modified to run either proof.

The sanctioned placeholders are pinned as literals rather than imported from the
private frozenset the code reads. Importing it would make the test agree with
any edit to that set, including one that quietly admitted a real id -- the
property under test is that THESE exact strings are the escape hatch the
refusal message advertises.

### The config-reset resume failures are another campaign's, established rather than assumed

`application/tests/test_config_reset_recovery.py` and `test_state_projection.py`
carry 18 failures at HEAD. The previous iteration attributed them away on the
evidence that they were not caused by the change in flight at the time, which is
weaker than it sounded: "not mine" is not "not storage", and config-reset
recovery is squarely this campaign's surface.

Run down properly. The resume pauses with `TARGET_STATE_CHANGED`, meaning the
deletion fingerprint no longer matches the one journaled -- the guard at
`application/config_reset.py:539` firing because the target's capsule changed
beneath the operation. The specific worry worth chasing was this campaign's own
throttle fix, since `reset_login_throttle` runs on every successful login and
now creates a `.lock` sidecar: if the fingerprint folded the keystore, that
sidecar would change the digest. It does not. The fingerprint folds
`committed_profile_custody_inventory`, which walks one profile's committed
capsule, and the failing module contains no login or throttle reference at all.

Ownership is positive rather than residual: the seeding door the test's own
docstring describes moved in `2c572da77d` under plan steps W05.P08.S188/S205,
and the surrounding fixtures moved again in `ee5eeb889d` under S153/S184/S201.
This is live work with named owners, and the lesson already recorded in this
campaign -- an early attempt at a peer's Google sync module took it from six
failures to eight -- argues against racing it. Left with its owner, with the
mechanism and locator above so they do not have to rediscover it.

### The bucket-level canary admits at activation only, and cannot re-judge a later write

COVERED, with one gap pinned rather than closed. The previous entry covered the
tax-id decision; this covers the branch before it, where
`refuse_unsecured_bucket_with_real_profile` must reach a bucket's stored profile
at all. Five branches, all established empirically before anything was asserted:

| bucket state | outcome |
|---|---|
| named by the literal `unsecured` label | admitted |
| no database file yet | admitted |
| database unreadable | REFUSED |
| profile payload undecryptable | REFUSED |
| real database, no profile rows | admitted |

The two refusals are the fail-closed pair, and the sqlite one carries its own
regression history in a source comment: an earlier revision RETURNED there,
silently downgrading the check and admitting the published key on buckets that
may have held real tax ids. Nothing was asserting that it now raises.

The gap worth recording is in the admitting column. The canary runs at
ACTIVATION only. A bucket with no database is admitted -- correctly, there is
nothing yet to judge -- but a profile written after that point, inside the same
unsecured session, is never re-examined. A real NIF typed into a fresh bucket
therefore lands under the published zero-confidentiality key and is refused only
on the NEXT activation, after the bytes already exist on disk.

It is narrow and it is not being closed here. Reaching it takes the
hostile-named `CADRUMO_ALLOW_UNENCRYPTED=1` together with the unsecured backend,
an opt-in whose whole purpose is to declare the data disposable, and closing it
means re-running the canary on the profile WRITE path -- a design change to that
path rather than a fix to this function. It is pinned in a test docstring so the
next reader meets the ordering as a stated property rather than inferring
protection that is not there.

On proof method, stated plainly rather than overclaimed. The discrimination
evidence is differential: the same function and the same session admitted with
no database and refused once the database was unreadable, so the assertions
track a real state change in production code rather than something ambient. The
stronger mutation -- making the fail-closed branch return instead of raise -- was
NOT run, because it can only be expressed by editing a live security-guard file,
and peers have swept this session's working tree into their own commits four
times. A mutated canary is the worst possible file to have swept, and the
differential already establishes causation.

The corruption cases drive a REAL bucket database from the real runtime fixture
rather than a hand-built table, so a fabricated schema cannot keep agreeing with
itself if production moves.

### The rotation subsystem is the retired model's, and is now uncallable rather than merely uncalled

CLASSIFIED, deletion left with the owner. `adapters/persistence/storage/_rotation.py`
exposes four public functions -- `rotate_master_key`, `default_rotation_plan`,
`rotate_blob_stores`, `default_blob_store_roots` -- across 596 lines, with an
804-line test module behind them. Not one has a production consumer. The only
importers in the tree are the storage facade's own lazy-export map and `__all__`,
which is what makes it read as live public API, and its own tests.

Two facts settle what it is. Its model is the retired one stated outright: walk
every consumer directory in a plan and re-wrap every envelope from an OLD master
key to a NEW one. That is the shared-master-key design the per-profile custody
cutover replaced. And it is now UNCALLABLE in any meaningful sense, not merely
uncalled: `rotate_master_key` takes `old_master_key_provider` and
`new_master_key_provider`, both typed `MasterKeyProvider`, while `_provider_enter`
refuses every implementation of that protocol except `UnsecuredMasterKeyProvider`.
The only call this tree admits rotates the published deterministic key to itself.

The live replacement is per-profile and reachable: `aeat config passphrase change`
to `rotate_profile_passphrase` to `application/user_profile/_passphrase_rotation.py`.
It is a deliberately different operation -- it re-mints the password envelope over
the SAME data-encryption key and preserves the DEK epoch, because re-keying would
re-encrypt every record and silently invalidate any recovery phrase the taxpayer
holds. So the old subsystem is not an unfinished version of the new one; they
answer different questions, and only one of them is still asked.

This is the most deceptive shape dead code takes. An 804-line suite passes green
over it every run, so every health signal reports a working subsystem, and the
facade advertises it as supported API.

DELETED, on the operator's decision, after the classification below was put to
them directly. The removal took `_rotation.py` (596 lines), its three test
modules (`test_rotation.py`, `test_rotation_crash_windows.py`,
`test_rotation_target_containment.py`), the storage facade's six exports of it,
and its API stub. Thirty-eight tests went with it.

What the deletion then surfaced is the part worth recording. Eleven storage
taxonomy members named `_rotation.py` as their `consumer_module`, and the
liveness gate caught every one by name -- "re-point the claim in the same change
that moves or deletes the module" -- which is the gate working exactly as
designed. Those eleven directories are now dormant: nothing writes plaintext
there, the durable records live in the encrypted secure-object store, and the
sweep only ever walked them looking for legacy envelope files. Each now carries
a `dormant_reason` saying so.

Four of the eleven then refused to be declared dormant, and that was also the
gate working. `consumption_evidence` counts a bare settings-field STRING as
evidence, deliberately, because some live consumers resolve fields dynamically
by name -- and `core/config.py` lists those four fields as string constants in a
path-normalising `field_validator`. The gate's sibling skip already discounts
exactly this kind of plumbing, with a docstring saying so ("the declaration and
the machinery that gives it a default"), but it tests for an `AnnAssign` in the
SAME module, and these four are declared by a mixin and normalised by the
facade: two different files.

So the detector was narrowed to treat validator arguments as plumbing, keyed
structurally rather than by an excluded-module list, matching the sibling's
stated preference. This is a gate change made to let this campaign's own change
pass, which deserves naming rather than burying: the guard against it is a
second discrimination test proving a real `settings.<field>` read in the SAME
module is still counted, so the narrowing cannot be read as excusing the
settings facade wholesale. Verified first that nothing outside the declaration,
the validator and the taxonomy reads any of the four fields -- they are dormant
in fact, not merely by declaration.

The prose sweep was larger than the code change. Nine test modules carried
docstrings asserting `_rotation.py` was some category's "sole consumer"; each
now states that the category has no consumer and why. One fixture string in
`test_custody_hard_cutover_absence.py` names `_rotation` and was deliberately
LEFT: that module's own comment records how a previous sweep broke its proof by
rewriting fixture strings, and it is testing path-shape detection, not import
resolution.

The original classification, retained because the reasoning is what justified
the deletion: Key-management removals are owner-gated because
deleting a key-schedule or DEK-derivation branch can strand encrypted data. The
confirmation that gate asks for does hold here -- the creation path
(`register_profile_with_credentials`) mints only the current per-profile
envelope, and this module neither creates nor reads any live schedule, so
removing it cannot render stored bytes unreadable; it removes a re-wrap
capability nothing invokes. That is an argument for the owner to weigh, not a
licence for the agent to act on a key-management surface. It has now been
deferred three times in this campaign, so it is put to the operator directly
rather than recorded a fourth time.

### Four audit-trail emissions bypassed the guard this campaign had already built

FIXED. The lost-update work earlier in this campaign added `append_guarded` to
the bucket-event repository and routed `emit_bucket_event` / `emit_bucket_events`
through it. Four production sites never used that door and wrote the trail
themselves with a bare load-append-save: purchase-invoice evidence attachment
(`application/ledger/_evidence.py`), the profile-activation record written at
login (`application/user_profile/_login_session.py`), live filed-evidence
stamping (`application/live/_filed_observation_persistence.py`), and both
ledger-ratio emissions in `entrypoints/cli/_ledger_ratios_cli.py`.

Each re-derived the id-build-append-save sequence that `emit_bucket_event`'s own
docstring names as the thing every emitting domain must share. The cost was not
duplication for its own sake: the shared primitive appends through the
catalogue's revision guard and a bare rewrite does not, so an emission
concurrent with another process's discards it. Content-addressed events make
that invisible -- every survivor is internally consistent, the missing one
leaves no gap, and the trail still reads complete.

Found by semantic search rather than grep, which is the transferable part. The
question asked was "load the catalogue, modify one entry, save the whole
catalogue back", and the answer set was the already-fixed repositories plus
these. A keyword sweep for `save(append_bucket_event(` then found only two of
the four: the other two span several lines, so the shape was invisible to a
line-oriented pattern. The AST gate written afterwards found them immediately.

The gate is deliberately narrow, and the boundary is the useful record here. It
forbids the bare `save(append_bucket_event(...))` composition, which is never
right -- neither guarded nor atomic with anything. It does NOT forbid composing
an event into a CO-COMMIT via `to_secure_object_write(...)` in another write's
`extra_writes`, because there the event must land in the same transaction as
the record it describes and a self-committing emitter cannot provide that.
Those sites (`_actions_manual.py`, `_actions_common.py`, `_capsule_record.py`,
`workflow/_persistence.py` among them) carry the SAME lost-update exposure and
are not covered by anything: they need a guarded-composition seam, which is the
co-commit retry design already standing open for the owner. The gate carries a
discrimination case proving it leaves that shape alone, so nobody reads its
green as covering them.

No behavioural concurrency regression accompanies the fix, and the reason is
worth recording because it constrains every future test in this area. Worker
threads do not inherit the active-session `ContextVar` -- deliberately, so an
encrypt path cannot observe a sibling context's key -- so a second emitter
cannot be staged in-process at all; the attempt fails with `NO_ACTIVE_SESSION`
before reaching the catalogue. The real concurrency here is cross-PROCESS. And
the bare write is a single expression, so there is no seam to interleave from
outside the way the earlier bucket-event and work-unit regressions did. A
thread-raced test would have passed before the fix as well as after.

### The co-commit class is buildable after all, and the ledger half is closed

The co-commit retry design stood open through this campaign as owner-gated, on
the reading that composing an event into another write's batch could not be made
revision-guarded. That reading was wrong, and the correction matters because it
was blocking the last known instance of the lost-update class.

Every primitive it needs already existed. `load_revisioned()` returns the
catalogue with the exact revision observed, and `to_secure_object_write()`
already accepts `expected_revision_id` -- the same two calls `append_guarded`
composes for the standalone path. The only missing piece was a retry that
re-runs the COMPOSITION rather than a single write, and that is safe here for a
reason worth stating: the domain catalogues the caller closes over are values
computed before the call, not reads that could go stale inside it, so re-running
the batch cannot resurrect a stale record.

`_commit_with_guarded_events` in `application/ledger/_actions_common.py` now
carries the read revision and re-composes on refusal, and when contention
outlasts the attempts it RAISES. That is the deliberate direction: refusing
beats the silent discard it replaces, on a trail whose losses are otherwise
undetectable.

Two things this pass establishes about testing this area, both transferable.
The interleaving CAN be staged deterministically for a guarded composition,
because the retry re-enters the window -- unlike the bare single-expression
writes fixed in the previous entry, which had no seam. And that determinism is
necessary rather than merely neater: worker threads do not inherit the
active-session `ContextVar`, so a second writer cannot be driven in-process at
all, and a thread-raced test here would be measuring nothing.

Scope, stated so the green is not over-read. This closes the ledger's two batch
writers. The remaining sites were listed here as `_capsule_record.py`,
`workflow/_persistence.py`, `_iva_wallet_seed.py` (two sites) and
`_reconcile.py`.

CORRECTION, from checking each rather than applying the seam mechanically. Two
of those five were already correct: `_capsule_record.py` reads with
`load_revisioned()`, compares the observed revision against an expected one and
raises `ProfileRecordConflictError` on divergence, and
`workflow/_persistence.py` composes inside a CAS update with
`expected_revision_id` set. Listing them cost nothing here only because the
next pass looked before editing; a mechanical sweep would have "fixed" two
sites that were already right.

The three real ones are fixed: both IVA wallet emissions were standalone bare
saves and now go through `emit_bucket_event`, and the `_reconcile.py`
co-commit now carries its read revision.

### The canonical co-commit composer was itself unguarded, and the gate that should have said so was matching a shape

The larger find sits under all of it. `bucket_event_history_write` in
`domain/buckets/_event_repository.py` is the shared composer for an audit entry
that must land in the same batch as its record -- its own docstring says it
lives in the domain precisely so no emitter keeps a private copy that drifts --
and it composed from a plain `load()`. All four consumers inherited the
exposure: `sync_runs.py`, `_m036_lifecycle.py`, `_m145_communication_records.py`
and `_revision_persistence.py`. One fix at the composer closes all four.

The gate written a pass earlier did NOT catch any of this, and why is the
transferable part. It matched `save(append_bucket_event(...))` syntactically,
so it passed green over three live defects that bound the appended catalogue to
a variable first -- the argument to `save` was then a Name, not a Call. That is
exactly the failure mode of the line-oriented grep it replaced, repeated one
level up: gating a SHAPE rather than a PROPERTY. It now gates the read (no
append onto an unrevisioned load) and follows what a name was bound from.

Building that detector surfaced two bugs in it, both worth recording because
they are easy to repeat. It double-counted every call inside a function, having
walked scopes from the module down and then again from each function. And its
name-binding scan used `ast.walk` with a `continue` on nested functions, which
does not work: `ast.walk` keeps yielding a skipped node's descendants, so one
function's plain `load()` tainted that name across every sibling function in
the module. That second bug is what falsely reported `_capsule_record.py`, and
believing it would have meant "fixing" correct code. Both are now pinned by
discrimination cases.

One exemption, with its reason: the module DEFINING the composer keeps a
deliberate fallback for the narrow domain port, which promises only
exists/load/save and so may carry no revisioned read. Excluding the definition
rather than the shape keeps a second module adopting it reportable.

Measured rather than asserted: the modelo/buckets selection moves from 147
failed / 313 passed at HEAD to 144 / 316 -- three fixed, none introduced.

### The lost-update class was never only about events: the calculate path could not express a guard

FIXED, and this is the severe end of the class. Every earlier entry on this
subject concerned the bucket event history. The same defect sat on the
CALCULATION-REVISION catalogue, where the cost is different in kind: a lost
audit entry costs a record of what happened, a lost calculation revision costs
a tax computation.

The calculate path in `application/modelo/_revision_persistence.py` composes
that catalogue with the work-unit pointer and the creation event in one unit of
work. It has to -- emitted separately, a failure leaves an advanced pointer
standing over state that never committed -- so it cannot use the
self-committing `mutate()`. It read the catalogue with a plain `load()`, and
the batch then wrote the whole singleton row back, discarding any revision
another calculate run persisted in between. Every surviving revision stays
internally valid and the missing one leaves no hole.

The root is worth separating from the instance. `to_secure_object_write` on the
shared `ProfileEnvelopedModelSecurePersistence` primitive took NO
`expected_revision_id` at all, so no repository composed on that base could
carry a guard even if its author wanted one. The guarded co-commit was not
being skipped; it was unavailable. `modelos_work_units` had grown its own
parameter for exactly this need, which is the tell that the base was the gap
rather than any one caller.

Two limits recorded rather than implied. The work-unit catalogue in the same
batch arrives as a PARAMETER, so that function cannot know its revision and it
stays unguarded -- closing it means threading the revision down from the
caller. And `expected_revision_id` is optional by necessity, since a caller
persisting a catalogue it did not derive from a read has no revision to assert;
that is also precisely the shape a later caller can slip back into without
noticing, so a test pins the looseness as deliberate rather than leaving it to
be rediscovered as a defect.

Measured, not asserted: the calculate-path selection shows 148 failures either
side of the change, 387 passing before and 391 after -- the difference being
these four tests. The guard was proven to bite by removing the parameter at the
base from a plugin outside the repository, where only the discriminating case
reds.

### The lost-update class is now closed by a gate rather than by sweeping

Four further batches carried the defect: the external-import path (composing
BOTH the calculation and filing catalogues), work-unit creation, and the
prorrata settlement write. As with the calculate path, three of the four
repositories could not express the guard -- no `expected_revision_id` on their
composing writes -- so the fix was a capability before it was a call site.

The transferable part is how they were found, and it is the same lesson twice.
A first detector looked only at the ROOT of the written expression and reported
two sites. These paths write `upsert_x(catalogue, entry)` -- a call WRAPPING
the loaded name -- so the root is a Call and the taint sits one level in.
Widening the search to the whole expression surfaced the other two. That is
precisely the failure this campaign already made with a line-oriented grep and
then again with a syntactic gate: matching the shape a defect happened to take
rather than the property it violates. The gate now carries the wrapped case as
its anti-tautology control, because the narrow version of it looked green.

A run-count nearly caused a second error worth recording. The affected
selection reported 201 failures at HEAD and 205 with the change, which reads as
four regressions. Diffing the SORTED failure sets showed them byte-identical at
205 either side: the earlier 201 was run-to-run variance in a lane already red
from the registry breakage documented above. In a tree with hundreds of
unrelated failures, totals are not evidence -- only set differences are. Acting
on the count would have meant hunting four regressions that did not exist.

What the gate does NOT cover is stated in the gate itself rather than left to
be discovered. It follows a catalogue only from a `load()` in the SAME
function. A catalogue arriving as a PARAMETER carries no revision the callee
can assert -- the work-unit catalogue in the calculate path is exactly that --
and those sites remain unguarded and unreported. Closing them means threading
the revision from whoever performed the read, which is a signature change
through several callers rather than a local fix.

### Three false greens from one habit: the detector kept matching shapes, not properties

Work-unit rename and discard both read `catalogue: WorkUnitCatalogue =
repo.load()` and composed it into a batch with their lifecycle event, rewriting
the whole singleton row over any unit another caller had touched. The gate
written the iteration before reported both as CLEAN, because it tracked
`ast.Assign` and an annotated assignment is an `ast.AnnAssign`. The binding form
alone hid two live defects.

That is the third instance of one habit in this campaign, and the pattern is
worth more than any of the three fixes:

* a line-oriented `grep` for `save(append_bucket_event(` found two of four
  sites, missing the two whose call spanned several lines;
* the gate that replaced it matched `save(append_bucket_event(...))`
  syntactically and missed three sites that bound the appended catalogue to a
  variable first;
* the gate that replaced THAT tracked one binding form and missed two sites
  using another.

Every time, the detector encoded the shape the known defects happened to take
rather than the property they violate. Every time it went green and the class
looked closed. The correction is not "write better patterns" but a test
discipline: a detector's discrimination cases must include the shapes it does
NOT yet handle, written from how the code actually reads rather than from the
examples that motivated it. The gate now carries the annotated form as its own
case, naming the two functions it hid, so the next reader sees why it is there.

A related discipline, already recorded once and reinforced here: in a tree with
hundreds of unrelated failures, TOTALS are not evidence. This change's selection
reported 98 failures at HEAD and 62 with the fix, which reads as a large
improvement; the set difference showed zero failures appearing that were not
already present, and nothing was claimed about the other direction. The empty
difference is the property that matters, and it is the only one this lane can
support.

### The fourth false green, and the decision to stop hunting shapes

A fourth blind spot surfaced immediately after the third was fixed:
`_build_participation_writes` reads `index =
participation_index_repository.load(transaction_id)`, derives `updated =
upsert_transaction_participation(index, participation)`, and writes `updated`.
The detector taints names bound DIRECTLY from a load, so taint never reached
the write through the intermediate. Green again.

Four detectors, four live instances passed over:

| detector | missed |
|---|---|
| line-oriented `grep` | calls spanning several lines |
| `save(append_bucket_event(...))` syntactic match | appends bound to a variable first |
| `ast.Assign` tracking | `catalogue: T = repo.load()` |
| direct-binding taint | taint through an intermediate assignment |

Each fix closed the instance in front of it and left the method intact, which
is why the method is the finding. A detector that hunts a SHAPE can only cover
the shapes already imagined, and this class kept producing new ones faster than
the detector could learn them. Continuing would have meant a fifth pass with
the same structure and the same expected outcome.

So the approach changed. `test_every_composing_write_is_declared.py` does not
search for the defect: it ENUMERATES every composing write outside the
repository layer and requires each to pass `expected_revision_id` or be listed.
Eighteen are listed. A nineteenth cannot appear silently regardless of what
binding form it uses, because the thing being matched is now a call to a named
method -- unambiguous -- rather than an inference about where its argument came
from.

The list is an inventory, not a clearance, and the module says so in its own
docstring. It holds three genuinely different situations and only the first is
closed: a document never read has no revision to assert; a document arriving as
a PARAMETER has one that belongs to its caller; a per-record row is not a
singleton and narrows the exposure to two writers touching the same record. Six
entries read "unclassified: not yet traced to a read site". That is deliberate.
Borrowing a plausible neighbouring reason would have made the inventory read as
fully reviewed, and this campaign has already recorded what confident
mis-classification costs.

The residual exposure is therefore now VISIBLE rather than unknown, which is
the honest description of what changed. It is not fixed.

### Tracing the inventory found a wrong declaration, a fifth blind spot, and a break this campaign shipped

The inventory built last pass was explicitly an inventory rather than a
clearance, with six entries reading "unclassified". Tracing them was worth
doing, because one of the entries that was NOT marked unclassified turned out
to be wrong.

Invoice linking and reconciliation were declared as receiving their catalogues
as parameters. The REPOSITORIES are parameters; the catalogues are read
locally, `invoices_repo.load()` passed inline as a call argument with
`result.invoices` derived from it. That is the defect class, not an exemption
from it. The invoice catalogue is a singleton row, so both batches rewrote it
whole over any invoice another caller had added -- a dropped invoice, which
under-declares.

That is a fifth detector blind spot on top of the four already recorded:
derivation reaching the write as an ATTRIBUTE on a result object
(`result.invoices`), which no amount of name-taint tracking would have caught.
It is also the exact failure the inventory was built to make survivable, and it
did: the site was listed, so tracing it was a finite task rather than a search.

The distinction that resolved it is worth keeping. The transaction store beside
these writes is NOT a singleton -- it writes a row per transaction -- so its
side carries no whole-collection risk and needs no revision. Guarding only the
invoice side is the correct scope, and the declarations now say so rather than
the wrong thing they said before.

### A regression this campaign shipped, and the two habits that hid it

`test_register_secure_object_write_keeps_a_conflicted_batch_atomic` has been red
since the prorrata guard landed two iterations ago. That change had
`prorrata_register` pass `expected_revision_id` to
`ProfileBareModelSecurePersistence`, a base that never accepted it -- the
enveloped sibling was extended, this one was not. Confirmed by running the test
against HEAD before fixing it.

Two habits let it through, and both are correctable:

* the regression check ran a keyword-FILTERED selection (`-k "work or revision
  or import or prorrata or calculat"`) which did not collect that test. A
  filtered slice is a convenience, and it silently narrows what "no regression"
  means.
* the required domain lanes for this campaign do not cover
  `adapters/persistence/profile` at all. Every catalogue repository this work
  has been changing lives there, so the standing lanes could never have caught
  it.

The correction applied here: run the FULL packages touched, not a filtered
slice. This pass ran `adapters/persistence`, `application/invoices` and
`domain/buckets` whole -- 1524 passing -- which is what surfaced the break in
the first place.

### The remaining sites were not unguarded by choice: the domain protocols hid the parameter

The inventory's largest category was "the catalogue arrives as a parameter, so
the revision belongs to the caller". That framing was incomplete. Those callers
are typed against the NARROW DOMAIN PROTOCOLS, and three declarations in
`domain/modelos/_protocols.py` (plus one in `domain/prorrata_register`) declared
`to_secure_object_write` and `save_with_secure_object_writes` without
`expected_revision_id`. A caller holding the protocol could not pass a revision
at all, whatever it knew. The guard existed on every concrete repository and was
unreachable through the interface most callers hold.

How it was found is the reusable part, and it came from the previous failure
rather than from fresh insight. The prorrata break repaired last pass had the
same shape one layer lower -- a persistence base that could not express the
guard -- so instead of looking at call sites again, this pass enumerated EVERY
`to_secure_object_write` definition in the tree and classified each as
accepting a revision, forwarding one, or neither. Eighteen definitions, four
without a revision parameter, all four of them protocol declarations. A call-site
search would not have found them, because the defect was in what the callers
were permitted to say.

With the protocols widened, the verification path is threaded end to end: the
caller that performs the read now uses `load_revisioned` and passes the revision
down to the persistence that composes the batch. Its inventory entry was REMOVED
rather than reworded -- the site is guarded now, not differently excused -- and
the staleness half of the gate is what forced that, exactly as intended.

The same threading is now unblocked for the amendment, filed-revision and
calculate paths. They remain listed, and the reason is budget rather than a
missing capability.

### The calculate path is threaded end to end, and a peer sweep briefly split it in half

The work-unit catalogue was the last unguarded document on the calculate
co-commit, and it was the one the earlier passes kept deferring because it
arrives as a parameter. With the protocols widened it became a plain threading
job: `prepare` reads with `load_revisioned`, `PreparedCalculation` carries the
revision as a declared field, and `persist_calculation_revision` asserts it on
the batch write. Single constructor, single caller, verified by search rather
than assumed -- and no test constructs either directly, so the chain is closed.

A worktree hazard is worth recording, because it produced a genuinely broken
HEAD rather than the usual harmless sweep. Peers have absorbed this session's
working tree into their commits repeatedly with no ill effect. This time the
sweep took TWO of the three files -- the preparation and the action, both of
which now PASS the new keyword -- and left the persistence that ACCEPTS it
uncommitted. HEAD therefore had callers handing `persist_calculation_revision`
an argument it did not take, and any calculate run against that commit raises
`TypeError`.

It was found by accident and nearly made worse. Reverting the three files to
HEAD to measure a baseline showed the revision field still present in two of
them, which is what exposed the split; had the baseline measurement not
happened, the local copy would have masked the broken HEAD indefinitely, since
the working tree behaved correctly.

Two practices to carry forward. Revert-and-restore for baselining must be split
into SEPARATE commands, because a timeout inside a single chained command
strands the reverted files -- which happened here on a six-minute package run
and left the persistence file at HEAD until it was noticed. And after any peer
sweep, a partially-absorbed change is worth checking for explicitly: the
signature and its callers can land in different commits, and the local tree
gives no signal because it holds both halves.

### The gate had a cheap-shortcut hole, found by sizing the next job rather than by reviewing it

`persist_filed_revision` was the next threading target: one production caller,
two catalogues still unguarded. Sizing it first turned up 26 TEST call sites,
which changes the economics -- and that is exactly what exposed a hole in the
gate.

The obvious way to thread a revision into a function with that many callers is
an OPTIONAL parameter defaulting to `None`. The gate checked for the
`expected_revision_id` keyword and ignored its value, so that shortcut would
have satisfied it permanently while guarding nothing. The site would have read
as closed in the inventory, in the gate, and to every later reader.

This is the same class of failure as the four detector blind spots already
recorded, arriving from the opposite direction. Those were shapes the detector
could not SEE; this is a shape it saw and misjudged. Both produce a green that
is not earned, and both were found by doing something other than looking harder
at the detector -- here, by pricing the work it was about to bless.

A literal `None` is now rejected, with both directions pinned. What remains
unjudgeable is a NAME that is `None` at runtime, so the rule moves into the
module docstring: a site threading a revision makes its parameter REQUIRED,
because a defaulted one is indistinguishable from a guarded one to any static
check. The gate states that limit rather than implying it does not exist.

The threading itself is deferred, and the entry now says why in terms that
survive: blocked on cost, not capability, with the shortcut that must not be
taken named explicitly. Deferring it is a budget decision. Taking the cheap
route would have been a correctness one, and the inventory would have stopped
showing it.

### Driving the CLI surfaced what reading it had not

The lost-update class had reached the point where every remaining site is
enumerated, gated and budget-bound, so this pass switched to the other half of
the brief -- operability -- and did it by DRIVING the CLI in an isolated
storage root rather than reading the code. Two things came out of that which
reading had not produced in many passes over the same tree.

The smaller one: the JSON flag is `--format json` at the root, not a per-verb
`--json`. Every profile read verb answers "No such option: --json". Not a
defect, but it is the first thing an operator tries.

The finding: a parse-time refusal reported `command: null` even when click had
already resolved the command. The distinction matters and only half of it was
honest. `aeat frobnicate` resolves nothing, and null is the truthful answer;
`aeat config profile preflight --bogus` resolved the command and THEN rejected
an option, with the resolution sitting on the exception's own context. The
spine reported null while the answer was in hand.

The existing resolver's docstring asserted "``None`` before any command
resolves (an argv parse failure), so the spine's ``command`` field is honestly
null there". That statement is true of the general case and was being applied
to a case it does not cover -- which is the same shape as several findings
already in this audit: a correct rule quoted about a situation it was not
written for. The fix reads the exception's context when there is one and leaves
null when there is not, with both directions pinned so that "always name
something" cannot satisfy the gate.

A separate investigation this pass produced NO defect, and that is worth
recording so it is not repeated. Non-interactive profile creation enrols no
recovery phrase, permanently -- and since the CLI contract states this CLI's
operator is an autonomous agent, which never has a terminal, every
agent-created profile is recovery-less by construction. That reads like a
serious gap until the constraint is traced: `enroll_profile_recovery` documents
that a committed capsule has no in-place installation path and that inventing
one would mean a second writer into a published capsule, and the mnemonic is
written only to the controlling terminal because writing it anywhere else would
violate the secure-storage-only rule. The design is correct under this
codebase's own rules, the warning notice reaches the operator in the envelope,
and there is no fix available that does not break one of those rules. Recorded
as a known operability limit rather than a defect.

### The full profile round trip works, and driving it found the refusal that blocked it

The lifecycle was exercised end to end against an isolated storage root rather
than reasoned about: create, validate, archive export, archive inspect, logout,
delete, list-empty, restore, list-restored. It works. That is the goal's
"verified" clause discharged by observation, and it is worth recording as a
positive result -- the sealed-capsule round trip is not merely covered by unit
tests, it survives a real operator sequence.

The defect it exposed was at the restore step. ``--secrets-stdin`` refused a
malformed payload with "not a valid JSON object" and named nothing else. Both
machine channels did, since they share one validator. That is precisely what
the CLI-boundary contract forbids -- a refusal lists the accepted set rather
than only what it rejected -- and the surface makes it worse than a generic
lapse: these are the channels a caller with NO terminal must use, and this
CLI's stated operator is an autonomous agent that cannot be prompted. The one
operator who cannot be asked was told the least.

The accepted set is now read from the strict model's own declared fields, not
restated in prose, so the message cannot drift from what validation accepts.

Three directions are pinned, and the third is the one worth keeping: naming the
accepted KEYS must never drift into echoing the value SENT. On a channel whose
entire purpose is carrying a password, a refusal that quoted the payload back
would put the secret into an error envelope, a log, and whatever the operator
pastes into an issue. The guard against a well-meaning "show them what they
sent" improvement is a test, not a comment.

### Two behaviours observed and deliberately not changed

Recorded so the next pass does not re-derive them as defects.

The redaction funnel replaces EVERY UUID-shaped substring in CLI string output
with ``<profile-id>``, including UUIDs inside filesystem paths that are neither
profile nor bucket identifiers. The archive export's returned ``target`` path
therefore comes back unusable whenever the destination sits under a
UUID-named directory -- a temp dir, a CI workspace, a per-run scratch path.
This is deliberate policy with a documented opt-out
(``CADRUMO_CLI_REVEAL_IDENTIFIERS=1``), and the redactor genuinely cannot tell a
profile UUID from any other. The practical harm is bounded because the operator
supplied the path and therefore already holds it. Left alone; the trade-off was
made knowingly, and the safe direction is the one it chose.

The JSON flag is ``--format json`` at the root, not a per-verb ``--json``.
Every profile read verb answers "No such option: --json" to the first thing an
operator tries. Not a defect, and not worth a second spelling.

### Multi-profile isolation holds at the CLI, and driving it found a retry loop

The multi-profile path was driven rather than reasoned about: create a second
profile while the first is active, read the locked one, delete the non-active
one, then attempt a restore over a live label. The isolation results are
positive and worth recording as such, because the campaign has verified the
primitives repeatedly without ever exercising their composition.

Creating a second profile displaces the session and the new profile becomes
active. Reading the now-locked profile returns `facts: null`,
`setup_state: null` and `profile_record_present: false` while still reporting
`registered_bucket: true` -- the bucket is known to exist, its contents are
not readable without a session, which is exactly the structural isolation the
resolver is supposed to give. Deleting the non-active profile succeeds and
leaves the active one intact; deleting the ACTIVE profile is refused with an
instructive message naming `aeat config logout`. Restoring a capsule over a
live label refuses rather than overwriting, so the data-loss shape that was
worth checking for is not there.

The defect was in HOW that last refusal reported itself: `retryable: true`. It
can never succeed -- the label is bound to a committed capsule and the
identical command fails identically forever -- and on this CLI that field is
not decoration. The stated operator is an autonomous agent, and `retryable` is
the instruction it acts on, so the refusal was inviting a loop with no
terminating condition.

The cause is one error class covering two different conditions in the same
function. "The captured witness no longer matches live state" is a
compare-and-swap conflict that a re-read genuinely fixes and is correctly
published retryable; the label collision inherited that answer. The split is a
SUBCLASS so every existing handler that catches a custody conflict keeps
catching this case, and only the published code and retryability change. The
registry binds by exact qualname and demands an entry per class, which is what
makes the narrower classification reachable without touching a caller.

Both halves are pinned. Marking the whole family not-retryable would have
satisfied the new assertion while stranding the case that only needed another
attempt, so the parent's retryability is asserted too.

### The retryable field had no contract, which is why one refusal got it wrong

The duplicate-label fix raised an obvious follow-on: are there OTHER refusals
misclassified the same way? Enumerating the registry answered a better
question. Of 633 declared codes, 27 are published retryable -- and the field
itself carried NO stated semantics. No docstring, no rule prose, nothing. Each
classification was whatever its author assumed, which is exactly how a
permanent refusal inherited a sibling's `True`.

So the fix this pass is the definition rather than another instance. `retryable`
now means: repeating the IDENTICAL call, with nothing else changed, may
succeed. Time passing, a lock releasing, another party finishing. It was
DERIVED from the 27 already-marked codes -- locks, network, timeouts, rate
limits, compare-and-swap conflicts, login throttles all fit it -- so it
describes the tree rather than redefining it, which is what makes it
documentation of existing intent instead of a new policy.

The consequence worth writing down is the trap: "retryable once the operator
fixes something" is FALSE under this definition. An agent cannot distinguish
that case from a transient one, and telling it to retry is precisely what
produces a non-terminating loop.

Two codes do not fit, and they are NOT mine to reclassify.
`FAIL_GOOGLE_ADC_UNAVAILABLE` and `FAIL_GOOGLE_ADC_STALE` both require the
operator to re-run a gcloud command before any retry can succeed. They are
named in the gate's docstring and left to whoever owns that surface. Applying a
definition I have just written to another area's error contract, on my own
reading of it, would turn documentation into a unilateral policy change --
which is the same overreach this campaign has avoided with rotation deletion
and the profile-verb scope.

The gate is scoped to the storage and custody codes this work is answerable
for. Six of them, each naming what resolves ON ITS OWN, so a seventh cannot
join by inheriting a neighbour's answer unexamined. The duplicate-label code is
asserted ABSENT from the retryable set, so the specific distinction that
motivated all of this cannot quietly collapse back.

### CORRECTED: the risk-assessment gate exists, is wired, and is RED

The entry below is WRONG in its central claim and is kept, corrected here,
because the error is more instructive than the finding was.

I reported that nothing checked whether live commands carry a risk assessment,
and froze the 26 undeclared commands as an accepted debt register. The gate
exists: `src/cadrumo-harness/.../mcp/tests/test_risk_table_parity.py`. It
covers exactly the same surface -- the MCP-exposed and CLI-exposable command
sets are identical, 291 each, verified rather than assumed -- and `testpaths`
in pyproject includes `src/cadrumo-harness`, so a bare pytest run collects it.
It is currently FAILING, on precisely the 26 commands I found.

So the substance was right and the diagnosis was inverted. The 26 are a real
gap, confirmed independently by the repository's own gate. What was wrong is
that nobody had built a check -- somebody had, it has been red, and the
campaign's prescribed lanes simply do not run it.

My register was worse than redundant. It asserted those 26 are acceptable known
debt while the real gate asserts the set must be EMPTY, and mine sat in the
lanes people run while the red one does not. A green weaker claim standing
beside a red stronger one is how the red stops being believed. It has been
reverted.

Two process lessons, both already visible earlier in this campaign and both
missed again:

* The prescribed lanes are not the tree. This is the second time a real red was
  invisible to them -- `adapters/persistence/profile` was the first -- and the
  second time the fix was to run the full surface rather than the given
  selection.
* A dangling-citation sweep is only as wide as its file enumeration. The
  citation in `_risk_table.py` names `test_risk_table_parity.py` correctly; my
  scan reported it absent because the enumeration excluded the harness
  distribution. The technique found a real dangling reference elsewhere and
  manufactured a false one here, which is exactly the failure mode this
  campaign has recorded for every other detector it wrote.

The 26 declarations still belong to the owners of the live, ledger, provision
and config surfaces. That part of the reasoning stands, and is now backed by a
red gate rather than a new one.

### SUPERSEDED, kept for the correction above: a gate the codebase believed it had

The "never file" rule is enforced by a live-write block that fires from the
declared `COMMAND_RISK` table. A command in a mutating family with NO declared
row classifies all-false -- including `live_write=False`. The classification
tests name this exactly: "the default is safe-looking, which is the trap". The
codebase already built the instrument to detect it, `risk_declared`, which
separates an assessed-and-safe command from a never-assessed one.

Nothing used that instrument against the real surface.

The chain of belief is the finding. The contract-drift gate checks one
direction only -- no row outlives its command -- and declines the other with a
sound reason: read-only verbs are legitimately row-less, so an exact mirror
would fail against correct data. Its docstring then says "the classification
tests own the other direction". Those tests prove the distinction works, using
PLANTED verbs (`ledger.unassessed_new_verb`). They never assert that the LIVE
surface is fully assessed. Each artefact is individually correct and each
points at the next; the property none of them holds is the one that matters.

This is the third time in this campaign that a green signal turned out to rest
on a claim about a neighbouring artefact rather than on a check. It is worth
naming as a pattern: a docstring that says another test owns a direction is a
citation, and citations need following.

Measured rather than assumed: 26 of 291 exposable commands carry no risk
assessment. None is a submission verb, so this is a gap rather than a breach --
but nothing prevented the 27th from being one.

The 26 are frozen as a DEBT REGISTER, and the wording matters: being listed
asserts nothing about a command's safety, only that its absence was known
rather than newly introduced. The register must shrink and may never grow, a
cleared entry must leave it, and a bound stops it becoming a blanket -- a
register covering the whole surface would satisfy its own checks while meaning
nothing.

They are deliberately NOT declared here. They span live, ledger, provision and
config surfaces this campaign does not own, and a risk assessment invented to
clear a gate is worse than a recorded gap: it would read as judgement where
none happened.

### Running the distribution the lanes never touch found a regression this campaign shipped

Acting on the previous correction -- that the prescribed lanes are not the tree
-- the harness distribution was run for the first time. It found a break this
campaign caused.

Reducing `SecretStoreBackend` to `{auto, unsecured}` swept `src/cadrumo` and
`dev/` and missed `src/cadrumo-harness`. Two harness tests still set
`CADRUMO_SECRET_STORE_BACKEND="file"`, so every command they drive died in
Settings validation before reaching its subject. Among the casualties was
`test_warm_runtime_holds_no_bucket_session_between_calls` -- a session-isolation
property named directly in this campaign's brief, failing because of this
campaign's own change. Fixed; the harness integration lane goes from 20
failures to 17.

The blind spot is now measured rather than described. The prescribed lanes miss
`adapters/persistence/profile`, they miss `src/cadrumo-harness` entirely, and
the default `addopts` marker selection (`-m 'unit and not external_tool and not
os_keychain'`) excludes every integration test in that distribution on top of
that. A bare `pytest src/cadrumo-harness` collects 51 tests; with `-m
integration` it collects 349. So the red risk-table gate corrected in the entry
above is invisible to BOTH the campaign lanes and a default local run -- which
is how it stayed red without anyone noticing, and how a shared-enum change
broke a sibling distribution unobserved.

Three separate misses now trace to the same cause: a repository-wide change
verified against a subset. The durable correction is not "remember the harness"
but that a change to a shared CORE surface -- an enum, a protocol, an error
code -- is verified against the distributions that import it, enumerated rather
than recalled.

The remaining 17 harness failures are deliberately NOT attributed. They sit in
in-process transport, MCP schema-budget and closed-value-axis gates that this
change does not touch, and there is no cheap baseline establishing when they
started. This campaign has twice had to retract a confident attribution; an
unattributed count is the honest record until someone measures it.

### A red test inside a prescribed lane, unread for the whole campaign

Chasing the harness failures led back into this campaign's OWN lane.
`_complete_setup_payloads.py` was added with the complete-setup verb and never
listed in `RESULT_SCHEMA_MODULES`, so two declare-then-verify gates over that
surface had been failing: one reporting an in-tree schema owner missing from
the declaration, the other that declared modules no longer reconcile with the
registry projection. One line fixes both.

The finding is where it sat. `entrypoints/cli/_config` is one of the three
prescribed lanes, and the CLI package has reported "5 failed" on every run this
campaign made. That number was recorded as an unchanged baseline, iteration
after iteration, and treated as evidence of no regression -- which it was. It
was never treated as five open questions, which it also was. A stable red count
is not a clean signal; it is a signal nobody has read.

That is a different failure from the lane-coverage blind spot recorded above.
There the reds were invisible; here they were printed every time and scrolled
past because the total had not moved.

### A measurement artefact caught before it became a finding

Worth recording as a near-miss. Following the harness envelope-parity failure
produced what looked like a serious defect: `registry.inspect` reported "no
registered output schema", which would mean the MCP transport could not
validate a correct envelope. Checking the population path first, rather than
writing it up, showed the opposite -- with the CLI package imported, all 291
live commands have registered schemas and none is missing. The registry is
populated BY importing the CLI, and the probe script had imported only
`json_contract`.

The probe measured its own import graph, not the tree. This campaign has
already retracted two confident attributions; the cheap habit that avoided a
third was verifying the measurement apparatus before believing an alarming
result from it.

### Reading the standing red counts: 14 confirmed, and an operator-facing English leak fixed

Applying the previous lesson -- that a stable red count is a signal nobody has
read -- to this campaign's own two standing numbers.

The 14 integration failures were carried all campaign on the strength of ONE
sampled test. Checked properly this time: only two cite the keyring in their
assertion (`KEYRING_UNAVAILABLE is ABSENT`, `'keyring_unavailable' == 'absent'`).
The other twelve fail as `assert False is True`, a zero-length material check,
and receipt-dependent retirements -- all of which route through keyring-backed
session acceleration, so a single cause is consistent across all fourteen. The
standing context is confirmed rather than overturned, which is the outcome
worth having recorded either way.

The CLI package's remaining reds were the productive half.
`cli.help.missing_argument`, `missing_option` and `missing_parameter` were cited
by production with English defaults and existed in NO catalogue, so every
"Missing option '--to'" reached the operator in English whatever their output
language. Two shipped gates had been reporting it for as long as this campaign
has been running that package. Fixed, and verified end to end: the same command
now answers "Error: Falta la opción '--to'."

### Nearly "improving" a deliberate design, stopped by its own gate

Worth recording because the instinct was reasonable and wrong.

These keys are invisible to the locale scaffold: they reach `tr()` through a
table of (prefix, key, default) tuples, so the scaffold's literal scan calls
them unused -- and `scaffold` aligns catalogues to keys it can see, which looked
like a live risk of the values being deleted again. The fix seemed obvious:
cite each key directly so both tools agree.

A sibling gate refused it. `test_framework_localisation_cites_keys_the_scaffold_cannot_see`
asserts the indirection MUST remain, because that gate exists to cover exactly
the class of keys the scaffold cannot see and would pass vacuously if every key
became directly cited. The deletion risk was already covered from the other
side: if scaffold removed these keys, the coverage gate fails.

The production change was reverted; only the catalogues gained values. The
lesson is the same one this campaign keeps relearning from the other direction
-- read the neighbouring gate before changing the shape it is built around.
Here the neighbour was right and the instinct was wrong, which is the more
uncomfortable version.

### The CLI package is green, and all five of its standing reds were real

The last of them: a date-binding guidance test asserting the English string
"active profile" while the shipped default output language is Spanish, so it
compared against "en el perfil activo" and failed for the CATALOGUE rather than
for the guidance it was written to check.

Pinned to English for the call rather than weakened to locale-neutral tokens.
That choice is the substance: "points at the active profile" is precisely what
separates correct guidance from guidance that merely mentions something, and no
locale-neutral token available would have told those apart. Weakening it would
have produced a green test that no longer distinguished the two states -- the
outcome this campaign has spent several entries learning to recognise. Proven
still to bite by substituting guidance that suggests `--binding KEY=VALUE` for a
profile-resident value, which is the defect it exists for.

The package now reports 991 passing and none failing. It reported "5 failed" on
every run this campaign made.

What those five turned out to be is the point worth keeping. Two were a
schema-owning module never declared in the canonical surface, so
complete-setup's result schema went unregistered. Two were three framework
localisation keys cited by production and shipped in no catalogue, so every
"Missing option '--to'" reached the operator in English whatever language they
had chosen. One was this test. None was environmental, none was another
campaign's, and none needed more than a few lines. They sat unread for the
entire campaign because the total never moved, and an unchanging red count is
the easiest thing in a test report to stop seeing.

The general form, now demonstrated three ways in this campaign: reds are
invisible when they are outside the lanes you run, when they are inside them
but constant, and when a gate cites a neighbour that nobody follows. All three
produce the same feeling of a clean tree.

### The prescribed-lane packages are clean, and the last standing red rests on a phantom boundary

With the CLI package green, the other two prescribed-lane packages were run
UNFILTERED to see what the marker selection hides. The answer is: almost
nothing, and the exception is precise.

`adapters/persistence/storage` contributes ZERO failures once `os_keychain` is
excluded -- every one of its ten unfiltered failures is a keychain-marked test.
`application/user_profile` hides exactly two extra behind the filter, both
`@pytest.mark.os_keychain` and both failing with WinError 1312. So the storage
domain's own test surface is as clean as this host permits, which is a result
worth recording rather than assuming.

That left one question: the fourteen. They fail for keychain reasons yet carry
NO `os_keychain` marker, which looked like a straightforward marker gap --
until the marker's own declaration was read. It says cases provable WITHOUT
custody stay in the default lanes, and directs the reader to "the boundary the
user_profile tests conftest draws".

There is no such conftest. None under `user_profile`, none anywhere mentioning
`os_keychain`, and no prose drawing that boundary in the tree or the vault. The
rule for deciding which keychain-dependent cases belong in the default lanes
has been uncitable for as long as the citation has stood.

So the fourteen cannot be classified from the tree. They may be intended to
prove something without custody and be failing to, or they may simply be
unmarked. Marking them would make this campaign's lane green immediately, which
is exactly why it would be the wrong move: it is the same shape as inventing a
risk assessment to clear a gate, and it would silently answer a question the
codebase no longer knows the answer to.

The marker description now states the situation instead of pointing at a
phantom, names the four affected modules, and says not to mark or unmark them
on a guess.

This is the fourth dangling citation this campaign has found, after the risk
table, `test_rejects_the_removed_manifest_recovery_mirror`, and the
contract-drift gate handing a direction to tests that did not hold it. The
common shape is worth stating once more: prose that delegates authority to
another artefact ages differently from the artefact, and nothing in the build
notices when the target goes.

### The standing 14 are resolved: custody-dependent, now marked, lane green

The previous entry left this open and said not to answer it on a guess. It has
been answered on evidence instead.

Three independent facts settle it. `resume_profile_session` documents that when
the OS keychain is unavailable the refusal "leaves the login PROCESS-SCOPED" --
cross-process resume IS the keychain, and no acceleration receipt is minted at
all. The `os_keychain` marker's own declared subject is "a later process resumes
the record by unwrapping its DEK under that key", which is precisely what these
ten functions assert. And they fail at their PRECONDITIONS rather than their
subjects: the obstructed-retirement case never reaches its assertion because
there is no receipt to obstruct ("the displaced profile must hold a receipt for
the retirement to reach").

So the boundary the phantom conftest was supposed to draw is now stated in the
marker itself, in a form a maintainer can apply: a case belongs under
`os_keychain` when it cannot reach its subject without a minted receipt.

Marked per FUNCTION, never per module. Those four modules hold 35 tests and only
ten need custody; module-level marking would have removed 30 passing tests from
the default lanes, trading a truthful lane for lost coverage -- the cheap route
that would have looked identical in the summary line.

Verified rather than assumed, because "make the lane green" is exactly the
outcome that invites a shortcut. The `os_keychain` lane now collects 17 where it
collected 2; the four modules still contribute 30 passing tests to the default
lanes; and a marked test still EXECUTES and fails on WinError 1312 when run
under `-m os_keychain`. They are deselected, not disabled, and a real regression
in them still surfaces on any host that can run them.

The integration lane is green: 309 passed, none failed. Both prescribed lanes
and the CLI package are now clean on this host, which means the campaign's own
signal is finally readable -- the condition that, as several entries above
record, is what let real defects hide for so long.

One process note. The commit marking the tests claimed the pyproject note was
updated in the same change; it was not, and the stale note would have warned
against a classification that had just been made on evidence. Corrected in the
next commit rather than left to be discovered.

## Recommendations

Treat the storage substrate package named for the retired shared-master-key
model as the next scoped effort rather than an incidental cleanup. It houses the
LIVE per-profile session substrate -- bucket sessions, the login throttle, KDF
parameters, idle timeout -- under a package name describing a model the cutover
retired. The package NAME is the residue; most of its contents are not, and the
refusal that stops a real profile being opened on an unsecured backend is live
protective code a name-driven deletion would take with it.

An earlier reading of this entry counted "roughly ten consumers" of the provider
protocol outside the package and treated that as evidence it was live. A closer
enumeration disproves it, and the correction is worth more than the original
claim. Nearly every one of those is a TYPE ANNOTATION on an optional parameter
production never passes: the stores and envelope helpers default it to None and
fall through to the active bucket session's key. The only production code that
passes a non-None provider is the rotation module -- which itself has no caller.
So the protocol is not live code with ten consumers. It is an injection seam
exercised by one callerless subsystem, and that optional override IS the
retained provider-fallback the decision says to remove: a second key route
standing beside the per-profile one, reachable by any future caller that passes
an argument.

That turns the removal from a judgement call into a sequence. The rotation
module goes first, being the sole reason the protocol must still exist; its
removal frees the optional override on the stores and the required parameter on
the envelope helpers; the protocol and its single unsecured implementation then
have no referent, along with the provider-session helpers that exist only to
serve them; and the tax-id canary loses a provider parameter whose isinstance
guard is already unreachable, since its one caller constructs the very class it
tests for. The live substrate is renamed out of the package last -- doing that
first would only move residue to a new address -- which is what the
hard-cutover gate's four declared open violations already anticipate.

Counting references is not measuring reach. A parameter nothing passes has
consumers and no callers.

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

### The remote-mirror manifest fixtures never reached their subject

`src/cadrumo/adapters/outbound/storage/tests/test_mirror_manifest.py` built every
manifest from `next(repo.iter_all_records_raw())` — the FIRST raw secure-object
row — on the assumption it was the row the fixture had just saved. It is not: the
runtime profile fixture writes a `cadrumo.application.user_profile.value` row and a
`cadrumo.domain.buckets.event_history` row before it, and
`build_remote_mirror_namespace_manifest` (`_mirror_manifest.py:49`) discards rows
outside the target namespace. Every manifest came out with zero objects.

What makes this worth recording is not the eleven red tests. It is which eleven.
Only the cases that INDEXED an object (`manifest.objects[0]`, `original["objects"][0]`)
failed, with an `IndexError` far from the cause. The cases that compared an
`object_count`, checked ciphertext or metadata drift, or asserted key uniqueness had
nothing to count, drift or repeat — they passed, and had been reporting coverage of
the remote-mirror confidentiality surface while exercising an empty document.

Three further cases were provisioning under a descriptive slug
(`remote-mirror-opaque-<key>`) rather than a canonical identity, refused by
`canonical_profile_bucket_id`, which requires a UUID **version 4** specifically — so a
derived `uuid5` is refused too and the identities have to be fixed literals.

Fixed by selecting the saved row by namespace, giving each parametrised case its own
v4 identity, and asserting in the shared helper that the manifest it hands out is
non-empty. The guard was proven to bite by restoring the positional pick.

**The generalisable tell:** a fixture that selects POSITIONALLY out of a shared store
is only correct while nothing else writes to that store, and a consumer that FILTERS
turns the resulting mis-selection into silence rather than an error. Positional
selection plus downstream filtering is a false-green generator; select by the property
the test means, and make the helper refuse to return an empty subject.

### Classifying the master-key surface: not residue

The campaign brief flagged `adapters/persistence/storage/master_key/` as a package
named for the retired shared-master-key model, still exporting `MasterKeyProvider`
and `UnsecuredMasterKeyProvider`, and asked that genuine residue be separated from
protective code carrying a legacy name before anything was deleted. The answer is
that there is no retired-provider residue in it.

The module defines exactly five things and all five are live. `MasterKeyProvider` is
a `runtime_checkable` **Protocol** — the structural interface every at-rest crypto
consumer accepts — not an abandoned implementation. `UnsecuredMasterKeyProvider` is a
concrete class, so the three `isinstance` guards against it are nominal rather than
structural, which is the correct and fail-closed reading. `_provider_enter` refuses
outright for any provider that is not the unsecured one, and the two
`refuse_unsecured_*` functions are the NIF canary. The name is accurate: "master key"
here is the per-bucket KEK. What was retired is the *shared* master key across
profiles, and none of that survives here.

The `~10` and `~5` external consumers in the brief resolve to production sites all
inside `adapters/persistence/storage` itself, plus that package's own tests.

**What was dead:** two application-layer custody ports —
`profile_bucket_session_open` and `profile_refuse_unsecured_bucket_with_real_profile`
— exported through two facades with no caller in `src`, `dev`, the harness or any
test. Every live hit resolves to the `_resumed` variant. Deleted.

Deleting a *safety* wrapper needs the stronger argument, and it holds: the underlying
guard runs at the one production site that opens an unsecured session, and the
application layer cannot produce one, because `BucketSession.open_resumed` hardcodes
`unsecured_backend=False` — a resumed session comes from per-profile password
custody, which the unsecured backend never participates in.

### A fail-open safety obligation was held by a docstring

`refuse_unsecured_bucket_with_real_profile` does **not** test
`session.unsecured_backend`. It trusts its caller, and its docstring carries the
obligation in prose: every path that opens a session outside `_provider_enter` "must
run exactly this guard rather than re-deriving it."

Prose is the wrong holder for this one. Forgetting the call is silent, and what it
admits is a real taxpayer's records written under a **published deterministic key**.
Today `src/` has exactly one such site and it does call the guard, so this was a
latent obligation rather than a live hole — but nothing stopped the second site.

Now gated: `test_every_unsecured_session_open_runs_the_canary.py` enumerates every
production `BucketSession.open(...)` and requires the enclosing function to run the
canary, carries an anti-vacuity assertion (an empty enumeration would pass every
other assertion in the file), and was proven to bite by removing the real call from
`_provider_enter` and observing it named that exact site.

### Multiuser safety: what is already sound, verified rather than assumed

Three of the four multiuser axes in the campaign brief hold up under inspection, and
recording *why* matters as much as recording gaps — otherwise the next sweep re-derives
them.

**PID liveness is fail-closed in the dangerous direction.** `pid_is_alive`
(`core/_pid_liveness.py`) treats a permission-denied probe as ALIVE on both platforms:
POSIX catches `PermissionError` from `os.kill(pid, 0)`, and Windows classifies only
`ERROR_INVALID_PARAMETER` (87) as dead, every other `OpenProcess` failure as alive.
This is exactly the second-OS-user case — user B cannot query user A's process — and
the wrong polarity would let B reclaim a live holder's bucket lock and produce two
writers.

That branch is **not** covered by a real test, and the module says so honestly. The
claim was checked rather than taken on trust: a scan of all 564 live processes on this
machine found **zero** for which `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` is
denied — the System process (PID 4) grants a handle here. So the docstring's "not
available in this test environment" is accurate, and no behavioural test was
manufactured for it. Left as a stated, verified limitation rather than a fabricated
green.

**The bucket lockfile is the best-covered surface in the domain.** Cross-process busy
detection uses a real live subprocess holder and asserts `BucketBusyError` with the
holder's actual recorded PID — the fail-open direction is genuinely tested. Stale
reclaim re-reads the PID immediately before unlinking and aborts unless the record is
byte-identical, closing the TOCTOU window where a peer reclaims and re-creates. Release
leaves a foreign lockfile alone. Reentrancy, child-process inheritance and
sharing-violation races are all covered.

**Resumed sessions cannot be unsecured.** `BucketSession.open_resumed` hardcodes
`unsecured_backend=False`, and that is sound rather than a papered-over default: a
resumed session comes from per-profile password custody, which the unsecured backend
never participates in.

### The capsule-archive payload was an unenrolled durable format

An exported capsule archive carries two versions — the container's
`ARCHIVE_SCHEMA_VERSION`, long enrolled, and the JSON payload's own — and the second
was accounted for nowhere. The enrolment gate names this exact test: *being inside an
enrolled container does not put a record's own grammar under that container's floor*.
Both conditions hold, so it is enrolled as `profile_capsule_archive_payload`, classed
DURABLE: the payload is what locates the password envelope, sentinel and recovery slot,
so an unreadable one is a backup that no longer restores anything.

Renamed to `CAPSULE_ARCHIVE_PAYLOAD_SCHEMA_VERSION` — the discovery helper keys
constants by bare name with the underscore stripped, so a generic
`PAYLOAD_SCHEMA_VERSION` would have collided with any other module's.

### Six exported contracts that nothing ever constructed

A sweep of the `user_profile` boundary's `__all__` against every identifier LOADED in
production found six pydantic contracts referenced nowhere — not by the CLI, not by
another layer, not by a test, not even by the module declaring them:
`RegisterProfileCommand`, `CompleteSetupCommand`, `EditProfileFieldCommand`,
`EditProfileSectionCommand`, `ProfileLifecycleResult`, `ProfileSnapshotRequest`.

**They did not look dead, and that is the finding.** This project's own records
describe CLI verbs "routed through `EditProfileSectionCommand`" and a
`complete_setup` service arm. Reading the intent alone would have concluded the
wiring was live. It was checked instead: both behaviours DO exist —
`config profile complete-setup` and `capabilities show/set` are live verbs — and
neither goes through these types. The behaviour shipped through repository methods
taking plain arguments, and the command-object layer was left standing.

So a name being load-bearing in the project's *records* is not evidence it is
load-bearing in the *tree*, which is the same lesson the orchestration rule states
about ADR amendments not being self-executing.

Deleted, with a gate that catches the class: each exported name must be LOADED
somewhere. A class statement plus an `__all__` entry is a definition, not a use, and
that asymmetry is the entire detector — a definition-counts-as-use version would
certify exactly the defect it exists to catch, which is asserted directly.

Thirteen further exports are used only *within* their defining module. Those are
over-exported, not dead, and are deliberately NOT failed on: conflating a facade
-narrowing judgement with a dead contract would bury the real finding among harmless
ones.

### Two parallel profile-portability mechanisms, one of them unreachable

Following `register_imported_profile_bundle` — which documents itself as "the
sanctioned entry point for the operator-facing import verb" — turned up something
larger than a stray export.

`aeat config profile` offers `archive` and `restore`, and both resolve to the
**capsule** path (`export_profile_capsule_archive`, `inspect_profile_capsule_archive`,
`read_profile_capsule_archive`). There is **no import verb at all**.

Beneath the unused function sits a second, complete portability subsystem — five
modules (`_bundle.py`, `_bundle_encryption.py`, `_bundle_export.py`,
`_bundle_export_contracts.py`, `_bundle_export_operation.py`) carrying passphrase
encryption, prepared exports, payload validation and import registration. Not one of
its symbols is referenced by any command. Its only entrypoint-layer reference is a
CLI *test* calling `prepare_profile_export` directly — coverage of a subsystem no
operator can reach.

This is the shape `aeat-architecture-boundaries` forbids: two mechanisms for one
concept, with canonicality implicit rather than declared. It was NOT deleted here.
Retiring five modules is a decision rather than a cleanup, and the honest options are
opposite — wire the bundle path to an `import`/`export` verb pair, or retire it and
let the capsule path stand as the single portability mechanism. Recorded for a
ruling; the unused entry point is enumerated in the gate meanwhile so it cannot fade
back into looking ordinary.

### CORRECTED: the bundle subsystem is live; only its IMPORT half is dead

The section above — "Two parallel profile-portability mechanisms, one of them
unreachable" — is **wrong in its central claim** and is corrected here rather than
edited away, because how it went wrong is the more useful record.

The bundle subsystem IS operator-reachable, by two surfaces the search missed:

* the **TUI profile manager's export action** (`_run_export` in
  `entrypoints/cli/_config/_manager_actions.py`) calls `export_profile_bundle`,
  hardcoding encrypted transport; and
* **`aeat app maintenance reconcile`** is a live CLI verb calling
  `reconcile_prepared_exports` to clean up export operations a crash left staged.

The whole export chain is live: `export_profile_bundle` → `prepare_profile_export` +
`publish_prepared_export` → `serialize_profile_bundle` →
`encrypt_profile_bundle_for_passphrase`.

**Why the search said otherwise, twice.** First, reachability was checked by listing
`aeat config profile` verbs and grepping `_config/` — so a TUI action and a verb under
a different command group were both invisible, and "no verb here" was generalised to
"no verb anywhere". Second, when re-measuring per symbol, the encryption entry point
looked dead too: its only live call site is a **function-local deferred import**
inside `_render_export_payload`, and a `grep | head -2` showed that module's own
docstring lines and cut the real call off. A partial measurement was twice read as a
complete one.

**What is genuinely dead is the import half, and it is a sharper finding than the
one it replaces.** `deserialize_profile_bundle`, `register_imported_profile_bundle`,
`decrypt_profile_bundle_with_passphrase` and `validate_bundle_payload` have no caller
on any path. So the product **writes passphrase-encrypted profile bundles that nothing
in it can read back**: the operator is handed an export, the decrypt function exists,
and no surface reaches it. The asymmetry is visible in the symbols themselves —
`encrypt_*` is live, `decrypt_*` is not.

That is a missing import verb, not a subsystem to retire. Deleting the export half
would remove a working operator capability, and deleting the import half would remove
the only code that could ever make those exports restorable.

### Session isolation was the untested half of the multiuser story

The active bucket session holds the bucket's unwrapped DEK, and it is resolved
*implicitly*: the column-level encrypt path cannot be handed a session reference —
SQLAlchemy calls `process_bind_param` with a fixed signature — so it reads one from a
`ContextVar`. If that lookup were process-wide rather than per-context, any thread in
a long-lived host would encrypt or decrypt with whichever profile happened to be bound
last. Both long-lived hosts here run worker threads: the MCP transport and the TUI
screens.

Nothing asserted it. The only threaded session test (`test_live_session_registry.py`)
asserts the **opposite** direction — that the emergency zeroisation sweep deliberately
*reaches* a session bound on another thread — so the substrate's central isolation
guarantee had no coverage at all, and the module's own docstring reasoning about PEP
567 was the only thing standing behind it.

Now covered with real threads and real sessions, and proven to bite by replacing the
`ContextVar` with a process-wide holder from a pytest plugin **outside the repo** — no
tracked file mutated, so a peer's sweep could not commit the mutation.

**The durable lesson is how one of those tests passed while broken.** The
two-threads-hold-different-sessions case originally used a single barrier, so both
threads were bound simultaneously — and it passed against the deliberately-broken
substrate. The faster thread read its value, **left its block**, and
`activate_session`'s restore-on-exit put the previous value back, which was exactly
the value the slower thread then read. Isolation and a lucky unwind produce identical
observations.

A second barrier fixes it: neither block may unwind until both reads have landed, so a
shared holder necessarily returns the last value written to both readers. Generalised:
**when a test asserts that two concurrent actors see different state, the assertion is
only sound if neither actor can finish before both have observed** — otherwise
teardown ordering, not the property under test, decides the result. This is the
concurrency-shaped sibling of the vacuous-fixture finding recorded earlier: in both
cases the test passed while never reaching its subject, and only deliberately breaking
the production code exposed it.

### A live security gate had silently lost its subject

`adapters/inbound/tui/tests/test_no_generated_secret_display.py` forbids any TUI module
from reaching a callable that MINTS recovery words. The reasoning is sound and still
applies: the candidate mnemonic is displayed once on the controlling terminal and
cannot be shown again, and a framework compositor retains, repaints and exports what
it renders — so minting stays CLI-only.

**All four symbols it pinned had been removed from the tree** — not renamed, gone:
`create_recovery_code`, `rotate_recovery_code`, `verify_recovery_code`,
`recover_secret_store`. The prohibition was asserting that no TUI module imports names
that exist nowhere. Structurally green, guarding nothing.

The only reason this was visible at all is that the gate carries an **anchor test**
whose stated purpose is to red when a pinned symbol stops resolving — "a gate that pins
symbol names passes trivially once those symbols are renamed". It did exactly that.
That anchor is the pattern worth copying: any gate keyed on a *name* needs a companion
that fails when the name stops existing, or retiring the subject silently retires the
rule.

The guarded property is unchanged and live. Custody still mints a **24-word BIP-39
mnemonic**, now via `create_profile_recovery_enrollment_material` and
`enroll_profile_recovery` (whose `ProfileRecoveryEnrollment` result carries the secret
in a wipeable container). Both are now pinned.

`generate_recovery_key` is pinned alongside them, and that is a genuine widening rather
than bookkeeping: it is the primitive beneath both AND is exported from the storage
facade in its own right, so a prohibition naming only application-layer callables could
always have been walked around by importing the primitive directly. The list this
replaces did exactly that.

**A second-order finding: the positive control had decoupled from the rule.** It kept
probing the retired names, so it went on proving the AST parser can spot an import —
against names no rule named. It now asserts that the names it exercises are members of
`_MINTING_CALLABLES`, so control and prohibition cannot drift apart again. Generalised:
**a positive control must be derived from, or checked against, the rule it controls**;
one that hardcodes its own example degrades into testing the instrument instead of the
guarantee.

### The same latent gap in a sibling gate, closed

Acting on the lesson rather than only recording it: the domain was swept for other
gates keyed on names. `custody/tests/test_kdf_worker_import_graph.py` forbids the KDF
child process from importing the heavy persistence graph, pinning seven module paths.

All seven still resolve, so it had not lost its subject — but it carried **no anchor**.
A module path that no longer exists is trivially absent from any child's module table,
so a rename would retire the rule silently and green. Its existing bite-proof could not
have caught that either: the proof imports `sqlalchemy`, a third-party name that will
not move, so all five first-party paths could be renamed with the proof still passing.

Anchored, and proven by renaming a target in the tuple. Stated as a general shape for
this tree: **a gate keyed on a name needs two companions, not one** — a bite-proof that
the detector fires, and an anchor that the named subject still exists. The first proves
the instrument works; only the second proves it is still pointed at anything.

### Sweeping the domain for name-keyed gates: two more stale pins

The two-companions shape was applied as a sweep rather than left as advice. Every
module-level constant in the domain's tests holding identifier-shaped strings was
checked against a definition index built from the whole `src/` tree.

Most hits were noise and correctly so — the large sets in
`test_runtime_attached_repositories_part1.py` and `test_active_bucket_consumer_coverage.py`
hold registry namespace **keys**, which are data resolved through
`STORAGE_NAMESPACE_REGISTRY`, not Python symbols. A definition index cannot see them and
should not.

Two genuine stale pins surfaced:

* **`test_ephemeral_key_hygiene.py`** pinned both `FiledDeclaracionObservationStore`
  and an English `FiledDeclarationObservationStore`. Only the Spanish-stem class exists,
  and the English spelling is one `aeat-naming` forbids ever creating — so the entry
  pinned a class that could not appear, in a set whose whole job is naming the
  constructors the hygiene rule covers.
* **`test_namespace_registry.py`** pinned `list_object_keys`, which
  `SecureObjectRepository` does not have.

Neither broke anything today, and that is the point worth recording: **a pin that
matches nothing is silent by construction**. The failure it enables is a future one —
rename a SQL-backed repository or a checked method and it drops out of its rule with
every assertion still green, so the rename looks free precisely because the gate stopped
watching. Both sets now carry anchors, proven by reintroducing each stale pin.

One further stale entry was found and deliberately LEFT: `object_repository` in
`_INJECTION_KEYWORDS`. That set is an **exemption** list — a constructor call carrying
one of those keywords is excused from the hygiene rule — so a name nothing accepts
exempts nothing, and its staleness fails safe rather than open. Anchoring keyword names
would also bind the list to today's parameter spellings, which is a different and weaker
claim than "this class exists". Recorded rather than fixed, so its absence from the
anchors is a decision instead of an oversight.

### The custody commands the MCP console could not classify

`test_risk_table_parity.py` has been red on 26 exposed commands carrying no row in
`COMMAND_RISK`. That table is what the MCP console reads to decide its human-in-the-loop
confirmation tier, so an unclassified command is one an autonomous caller cannot reason
about. Both of the gate's failures share this single cause — including
`test_no_exposed_command_declares_an_aeat_live_write`, which reports the unassessed set
rather than an actual live-write declaration. **No command declares a live write.**

Five of the 26 are custody or storage and are now declared. `config.provision.*` looked
like ours by prefix and is not: it provisions local *inference models*, which is why it
was checked rather than claimed. The remaining 21 belong to the live-AEAT, ledger and
modelo surfaces.

Each row was read from the implementation, because the name is not the evidence:

* **`config.passphrase.change` — destructive.** It re-wraps the existing data key rather
  than re-keying, so no record is re-encrypted and any recovery artifact keeps working.
  Declared destructive anyway: the wrapper the OLD password opened is irreversibly
  overwritten, and a credential rotation is precisely the class of change an autonomous
  caller must not auto-approve.
* **`config.profile.restore` — NOT destructive**, and this is the one that needed
  checking, since "restore a backup over a profile" sounds destructive by default. A
  name already bound to a committed capsule is refused permanently, so the only state it
  can overwrite is a publication interrupted part-way — which is repair, and the reason
  the verb exists. It cannot silently replace a live profile with an older backup.
* `config.profile.archive.export` refuses a destination that already exists;
  `archive.inspect` reads only the plaintext header; `complete_setup` is a lifecycle
  transition.

The gate stays red on the other 21, which is the honest state: those are their owners'
declarations to make, and a risk posture assigned by copying a neighbour is worse than
an absent one.

### The custody lock ORDER was declared in a docstring and enforced nowhere

`profile_custody_transaction_lock` carries the invariant in one line — "acquire root
then profile lock, the only accepted custody lock order" — and nothing checked it.

This is the worst-shaped concurrency defect to leave unguarded. Two processes taking the
same pair in opposite orders deadlock, **neither of them individually doing anything
wrong**, so there is no single bad call site to find in review. It needs two operators,
real contention and unlucky timing, which makes it close to unreproducible once shipped
and structurally invisible to every single-process test. Nothing in the type system
separates the two locks either: the root lock IS a `profile_custody_local_lock`, over
`.profile-custody-root.lock`, so a future caller can take them the other way round with
no signal at all.

**The tree already complies, and that was measured rather than assumed.** The custody
suites were run under a tracker loaded from outside the repo that wrapped the real
primitive and recorded every acquisition: 583 tests, **95 real acquisitions, 17 of them
the root lock, 61 nested — every nesting root-first**. The acquisition COUNT is as
load-bearing as the verdict here: a tracker that observed nothing would have reported
"no inversion" just as cheerfully, which is the vacuous-pass shape this campaign has now
hit four times.

Now enforced by a test, proven by inverting the real acquisition order in
`_custody_repository.py`.

**A methodological finding from writing it.** The first version of the test reported an
inversion that did not exist. It patched the primitive on the `custody` facade, but
`profile_custody_root_lock` reaches the primitive through its **own module global** —
so the root acquisition was never observed and the profile lock looked like the first
one taken. Patching at `_filesystem`, where both resolve, gives the true order.

The lesson generalises past locks: **when instrumenting a function to observe calls,
patch where the callee is RESOLVED, not where the caller is declared.** A facade
attribute and a module global are two different bindings of one function, and an
observer attached to the wrong one produces a confident, precisely-wrong measurement.
That is the same root cause as the earlier bundle-subsystem misreading, where a
function-local deferred import hid the only live call site.

### The slices the prescribed lanes never run

The campaign's two lanes exclude `serial` and `os_keychain`, so those tests had never
been run in this work. Both were checked, because a permanently-unrun slice is where
coverage rots unobserved.

**`serial`: healthy.** 16 tests, all passing.

**`os_keychain`: 26 failures, and every one is the same environmental cause.** The
standing context carried "14", which is now stale — the marked set grew, partly through
this campaign's own correct re-marking. What matters is that the bucket has not become a
hiding place: grouping the failures by their raised error shows 12 `pywintypes.error
(1312, 'CredRead')`, 12 `KeyringUnavailableError` wrapping the same, 12 `OSError
[WinError 1312]`, and the remainder — `assert False is True`, `KEYRING_UNAVAILABLE is
ABSENT` — are downstream consequences of the receipt write failing, not independent
defects. Nothing real is concealed behind the marker. Worth re-checking periodically:
a "known environmental" bucket that is never re-grouped by cause is exactly how a real
failure eventually hides in one.

### The keychain refusal sent the operator to the wrong place

`AUTH_STORAGE_KEYRING_UNAVAILABLE` rendered "The operating-system keychain is
unavailable. Check that a credential store is installed and active."

On a network or service logon — the mode that produces every failure above — the
credential store **is** installed and active. The condition is that the logon session
cannot hold credentials. An operator following that guidance verifies the one thing that
is not the problem, finds it fine, and has nowhere left to go. The text was written for
the headless-Linux case (no backend registered) and silently generalised to a mode it
does not describe.

Fixed in all four catalogues through the locales CLI: the message now names both
conditions and gives the action for each. The `context` channel was considered as an
alternative carrier for the raw OS detail and rejected — it is `Notice`-scoped and its
validators explicitly forbid action-guidance keys, so guidance belongs in the message.

**Two measurement artefacts were caught before acting on them**, both worth noting
because each would have produced a confident wrong fix. Probing `default_suggestion` on
every custody error code returned "all 71 missing" — the field does not exist on
`ErrorCode` at all. And reading the four locales through the terminal showed `hu` blank,
which was the console's cp1252 encoding failing on Hungarian characters, not a missing
key; writing through UTF-8 showed the string present. Neither is a defect in the tree;
both are defects in how it was being looked at.

### A repair verb that deletes was declared as safe as one that archives

`config.repair.reset_progress` deletes the saved workflow-state envelope outright — a
fingerprint survives for audit, the state does not, and there is no re-import path. It
carried a bare `CommandRiskDeclaration()`, contradicting the same table's own recorded
precedent for `app.maintenance.reconcile`: *an unrecoverable local delete is declared
destructive regardless of the recovery intent behind it.*

Its neighbour `config.repair.quarantine` reads alike from the name and is correctly NOT
destructive, which is what makes the pair worth pinning rather than describing:
quarantine **copies** every undecryptable row, ciphertext intact, into a
`secure_objects_quarantine` archive table an operator can restore from. Delete versus
archive is the whole distinction, and nothing held it.

**The `--yes` flag both verbs require is not the same protection.** It gates a human at
a terminal. This table gates whether an *autonomous* caller is asked at all, and a
required flag is something such a caller supplies itself. A command whose only guard is
a flag has no guard against the operator this CLI was built for.

Both halves are now pinned and each was proven to red independently — asserting only the
destructive half would be satisfied by declaring every repair verb destructive, which
buries the real one in noise and trains operators to approve without reading.

Found by sweeping the table for bare rows whose key names a deleting verb. That is a
review heuristic for *finding candidates to judge*, never the rule — leaf-name matching
is precisely the approach this table was built to replace. The other two hits were
checked and are correct: `config.reset.status` is read-only, and `config.reset.start` /
`resume` already carry `destructive=True`.

### Independent corroboration of the bundle-portability gap

Running the operator-surface contract test surfaced the same gap from another direction:
four commands have registered result schemas and **no raw Click surface at all** —
`config.profile.export`, `config.profile.import`, `config.profile.subject_access_request`
and `config.profile.rename`. `_bootstrap_exempt.py` additionally declares a
bootstrap exemption for `config profile export`, a verb that does not exist.

So the profile export/import surface was designed down to its JSON envelopes and
bootstrap policy, and the verbs were never mounted. That is the same finding as the dead
bundle-import half, reached without going near the bundle modules.

**Left untouched deliberately.** The registrations date to the package-root rename, and
the most recent commit on that file is a peer *mounting profile verbs* (archive/restore
landed; these four did not). This is in-flight work by another owner, not residue to
clear, and the honest move is to hand the evidence to the pending ruling rather than
delete a peer's scaffolding or mount verbs nobody asked for.

### The write guard's verb catalogue: a fail-OPEN surface with no anchor

`PROFILE_BOUND_WRITE_VERB_PATHS` is what the storage write guard matches an invocation
against before permitting a bucket-scoped mutation, and it matches by **verb-path
string**. That makes its staleness mode the dangerous one: an unmatched verb is answered
`NON_PROFILE_BOUND_VERB`, so the write proceeds **unguarded**. The guard fails OPEN. A
stale entry here is worse than a stale entry anywhere else this campaign has swept,
where the cost was merely a rule that stopped covering something.

It has already happened once, and the catalogue records it in its own comments: the
payable/collectible invoice verbs collapsed into a single `invoice` family discriminated
by `--kind`, the catalogue kept the pre-collapse spellings, and every invoice mutation
fell out of the guard until someone noticed by hand.

Nothing prevented a repeat. A rename lands in the CLI, the catalogue keeps the old
spelling, every test stays green — because *"this verb was not guarded"* and *"this verb
does not exist"* produce the same observable nothing.

**All 98 entries resolve today**, measured against the live tree before the gate was
written. Now gated: every entry must name a path in the REAL materialised Click tree —
not a schema projection or a manifest, since a projection can agree with the catalogue
while both disagree with what an operator can actually type. Both vacuity directions are
asserted separately, because an empty walk and an emptied catalogue each satisfy the
main assertion perfectly. Proven by re-staging the recorded incident.

This completes the name-keyed sweep's most important case. The earlier passes covered
test-side constants, where staleness costs coverage; this is the production-side
instance, where staleness costs the guard itself.

### Two axes checked and found already sound

Recorded so they are not re-derived. **Batch atomicity** is properly covered:
`test_apply_batch_is_atomic_on_failure` drives a real `SecureObjectRevisionConflictError`
inside the unit of work and asserts all three rollback directions — sibling upsert,
deletion, and the conflicting upsert itself. **Integrity and quarantine** are covered
too: quarantine moves exactly the rows the probes flag, preserves the probed bytes, and
a clean bucket reports clean across every surface.

**The over-export measurement was re-run and the earlier "13" is wrong** — it is 30+
names exported from the `user_profile` facade with no consumer outside the package.
Deliberately NOT swept this iteration: a peer is actively mounting profile CLI verbs in
this exact package, and a 30-name facade change is precisely the broad edit that
collides with in-flight work. It also removes no code — it narrows a surface — so the
cost of deferring is low and the cost of colliding is not.

### The fail-open list was the unguarded one

Two verb-path registries sit in `_bootstrap_exempt.py`, and their guarding is inverted
relative to their risk.

`BOOTSTRAP_EXEMPTIONS` records what is let through without an active profile. When an
entry goes stale it fails **closed** — an exemption naming a verb nobody can type exempts
nothing. It carries eight gates: every entry names a registered verb, still resolves,
cites a test that exists, a prefix exemption carries exactly its declared subtree, a
read-only claim matches the operator-surface contract, plus a positive control.

`LOGIN_GATED_VERB_PATHS` records what must NEVER be readmitted by the mechanical
admission rule. When an entry goes stale it fails **open** — the refusal governs a path
nobody can type while the rule is free to exempt whatever the verb is called now. It had
no resolution check at all.

The module is honest about the gap rather than hiding it: its family anchor stops at
`config profile` by design (a family declares no command inventory), and the docstring
hands the leaf-rename case to "the same hand-sweep discipline every verb rename in this
tree already owes". The residue lands hardest on the strongest entry — `config profile
delete`, whose own recorded reason is that the absence of an exemption IS the protection,
and that a wrongly-granted one costs a taxpayer their encrypted financial history rather
than a redundant copy of it.

**A plain live-resolution rule would have been wrong here**, which is why the design was
read before the gate was written. The registry deliberately admits a path for a verb the
tree does not register yet — "the refusal is what governs the surface when it lands" —
so requiring every entry to resolve would fight a decision, not a defect. Unmounted paths
are therefore exempted BY NAME with a stated reason, because *"does not resolve"* and
*"was renamed"* are indistinguishable unless someone says which; and a staleness check
forces the record out once the verb lands, so the exemption cannot become permanent on
exactly the surface being rebuilt. Today the set holds one entry: `config profile
export`, mid-rebuild by another owner.

Proven both ways — the rename simulated from an out-of-repo pytest plugin so no tracked
file was mutated, and the staleness half by recording a verb that already exists.

**Generalisable:** when two registries express opposite sides of one rule, check which
one fails open, and expect the guarding to have accrued on the other. The safe-when-stale
list is the easier one to write tests for, which is exactly why it ends up with more of
them.

### A barren iteration, recorded as such

Three priority-one probes, no defect. Written down because a negative result nobody
records gets re-derived by the next sweep at full cost.

**Unregistered namespaces fail CLOSED.** Saving to a namespace absent from
`STORAGE_NAMESPACE_REGISTRY` refuses with `StorageValidationError
errors.storage.namespace.unregistered`, so data cannot reach disk without a declared
sensitivity class. Probed against a real runtime profile, not read from the source.

**No fourth redaction consumer is escaping the shared base.** `ALWAYS_REDACT_KEY_TERMS`
exists because `password` once lived in one predicate only, leaving two others treating
it as ordinary — and that "survived because nothing enumerated the third consumer".
`test_redaction_base_composition.py` now enumerates three consumers and asserts each
composes the base, with anti-tautology assertions that each also adds something of its
own. A tree-wide scan found no key-name collection that overlaps the base without being
a superset of it, bar one false positive (`_SEGMENT_ABBREVIATIONS`, an MCP
command-segment map that happens to contain "certificate" and "secret").

**And a gate deliberately NOT built.** The composition gate hand-lists its three
consumers, which is one level up from the failure it records — a fourth predicate would
escape it silently. Two mechanical discovery detectors were tried so the enumeration
could be derived instead of maintained, and BOTH were rejected on measurement:

* word-overlap (a collection sharing two or more base terms) false-positives on ordinary
  vocabulary maps;
* the structural shape `any(term in key for term in SET)` finds only ONE of the three
  known consumers — the other two are written differently.

Shipping either would have replaced a correct hand-list with a detector that misses two
of three real consumers: a false green, which is the exact defect class this campaign has
spent its iterations removing. The hand-enumeration stands, and this note is the reason
not to re-attempt the automation without a sounder signal.

### The bound-repository guard was tested in every direction except the leaking one

`test_runtime.py` proves a repository pinned to one bucket refuses once the active
session moves to another — for a write, a raw-key write, a quarantine, and a diagnostics
pass. **Read was absent from that set**, and read is the only one of the five where a
regression leaks rather than loses.

The two failure shapes are not comparable. A write that escapes the guard puts a row in
the wrong bucket: wrong, loud, and eventually visible as data that does not belong. A
read that escapes hands one profile's decrypted records to an operator who believes they
are in another — into whatever payload, log line or export that operator is composing —
and nothing about the returned value announces which profile produced it.

Measured first: the read **is** refused today, with `SESSION_CHANGED`, because a single
shared method checks the pinned bucket on every operation. That is the argument for
pinning it, not against — the sharing is what makes the protection invisible at the call
site, and reads are the hot path most likely to be "optimised" past a check that reads
as redundant.

Now covered, and proven by clearing the repository's pinned bucket id from an
out-of-repo plugin so no tracked file was mutated: the read then succeeds under the other
bucket's session. Its anti-tautology sibling — the same repository reading its OWN bucket
and asserting the exact payload — keeps passing under that same break, so the refusal is
attributable to the bucket change rather than to a read that had stopped working for any
other reason.

**Generalisable:** when a guard is proven across several operations, list the operations
it was proven on and ask which one fails toward disclosure. A set of sibling tests that
looks exhaustive is not, and the missing member tends to be the read — writes are what
authors think to test, because a bad write is the failure they can picture.

Two fail-closed behaviours were confirmed along the way and are recorded so they are not
re-probed: a singleton namespace refuses any object key but its declared one
(`object_key_grammar_mismatch`), and an unregistered namespace refuses outright.

### Guard coverage measured completely, and one latent ordering dependency

Applying the disclosure-direction heuristic one level deeper than last time: rather than
asking which *test* was missing, asking which repository *operations* actually reach the
session guard at all. That is answerable completely rather than heuristically — the
class's methods are enumerable — so an AST pass walked `SecureObjectRepository`
transitively for `_check_session_freshness`.

**23 of 25 public methods reach it.** The two that do not are `engine` and
`namespace_registry`, which are accessors rather than data operations. So the guard has
no gap among the operations themselves.

The accessors are the more interesting half, because a public `engine` hands out a door
past the guard. Three sites take it: `_all_date_index_rows`, `_date_index_candidate_ids`
and `_sync_date_index` in `adapters/persistence/profile/transactions.py`, each opening a
raw `session_scope(self._objects.engine)`.

**No live exposure — every path reaches a guarded call first.** All three are preceded by
`self._load_index_ids()` or `self.load()`, both of which route through the guarded
`_objects.load`. Recorded because the protection is INCIDENTAL: it lives in call
ordering, not in the raw reads, and nothing states or enforces it. A new entry point that
reaches one of these three first would read after a session seal or idle expiry with
nothing to stop it. Closing it properly needs a public guarded session-scope accessor on
the repository — a cross-package private call is not available and would breach the
facade rule — which is a design change rather than a gate, and not warranted while every
caller is covered.

### Two designs read before being "fixed", both sanctioned

The plaintext date index looked like a `sensitive-financial-data-secure-storage-only`
violation: a plaintext table of transaction ids and dates inside the bucket database,
where `aeat-ledger-contract` names "writing a plaintext index outside the encrypted
repository" as bad. It is not a violation. The ORM class states the decision explicitly —
plaintext by design, `SensitivityClass.CACHE`, only non-sensitive routing keys, and
correctness never depending on it, with a full encrypted scan as the fallback.

Its stated prohibition — *"No amount, counterparty, description, NIF, or other financial
content may ever be added to this table"* — then looked like a prose-held obligation on a
plaintext surface. It is not that either:
`test_date_index_table_carries_only_non_sensitive_routing_columns` reflects the LIVE
table through SQLAlchemy inspection, precisely so a widened schema fails even when the
docstring is not updated, and asserts exact column-set equality.

Both were checked rather than assumed, and both would have produced a confident wrong
"finding" on a first reading. That is the method rule earning its place twice in one
pass: read the design before gating it.

### The ordering dependency, closed structurally

The latent fragility recorded last pass is now fixed rather than described.

`SecureObjectRepository.engine` is the one route into a bucket database that skips
`_check_session_freshness` — the check every operation on that repository otherwise
applies. Three date-index reads in the transaction repository took it, so each served a
sealed session, an idle-expired session, or a session that had moved to another bucket,
with nothing to stop it.

None was exposed, because each is reached only after a guarded `load` and inherited the
check that fired earlier in the call. `guarded_session_scope()` now applies the check at
the read itself, and the three sites use it; the raw accessor stays for callers that
genuinely need an engine.

**The test drives the private method DIRECTLY.** Reaching it through a public entry point
would run a guarded load first and re-establish the exact ordering that used to be the
whole protection — proving the old accident still holds rather than the new guard. Proven
by restoring the raw scope from an out-of-repo plugin: the read then succeeds under a
foreign bucket's session.

What this governs is the **idle lock**, not confidentiality of amounts: the index carries
routing keys only, by design and by a live-schema assertion. An operator who walked away
should not have a profile's transaction ids and filing dates still answering queries.

### Attribution measured, not assumed

Running the wider consumer packages surfaced 541 failures across ledger and modelo,
dominated by `PurchaseInvoiceEvidenceInputError: this profile declares no fiscal-address
postcode`. The one failure whose text mentioned readiness turned out to be a test
matching rendered prose against a translation key, already raising before this change.

Attribution was settled by set difference rather than by reading: the ledger slice was
run with HEAD's copies of both modified files and then with mine — **82 failed / 1286
passed, identical both ways**. None of those failures is attributable to this work; they
belong to whoever landed the postcode requirement. The file-level swap used `git show`
to write the HEAD content and restored from a scratchpad copy, so no git state operation
was performed on a shared worktree.

### The bundle question is answered, and not by us

`2026-08-20-profile-portability-data-subject-access-adr` is **accepted**, and its three
corrections have all landed — verified rather than assumed, since an accepted ruling on
code is not self-executing: the `sar_help` / `sar_catalogue_info` strings are gone from
all four catalogues, the declaration entry now records a missing capability instead of a
legal duty, and the reference documentation states the gap.

It confirms this campaign's finding in its own words — "the profile manager writes
bundles nothing in the product reads back" — and assigns restoring export/import to
`2026-08-13-profile-portability-successor-adr`, not here. The open item this campaign was
carrying is therefore closed: ruled, deferred deliberately, and owned elsewhere.

### The exemption that switches the cross-bucket guard off

Following the raw-engine thread to its neighbours: `secure_object_repository_for_bucket`
attaches a repository to an ARBITRARY bucket id, and the runtime guard that would refuse
a bucket the active session does not serve carries an exemption —

```
if active.bucket_id not in _SYNTHETIC_SESSION_BUCKET_IDS and not session_serves_bucket(...)
```

`_SYNTHETIC_SESSION_BUCKET_IDS` is `frozenset({"ephemeral"})`, used at two sites, and its
only effect is to SKIP the cross-bucket check. So any session whose bucket id is
`"ephemeral"` can attach a repository to **every** bucket.

The only producer of such a session is `EphemeralMasterKeyProvider`, which lives in
`src/cadrumo/tests/` — and that package **ships inside the wheel**. Nothing structural
stopped a production module importing it and acquiring exactly that exemption. A scan
confirmed no production module does, and that nothing prevented it.

Now gated. The gate anchors its own argument against the live set — asserting `"ephemeral"`
is still a member — so it cannot end up defending a hazard that has moved elsewhere.

**A production module WAS reaching test support**, found by the same scan:
`application/calculations/_multi_year.py` imports `isolated_runtime_profile`. It holds a
multi-year observation TEST SCAFFOLD — a `tmp_path` parameter, a throwaway profile, bare
`assert` statements — that came to rest in a production package. Recorded rather than
fixed: the remedy is a relocation into the owning `tests/` directory, which is atomic and
belongs to the calculations campaign. The bare asserts are the quieter half of the same
problem — assertions vanish under `python -O`, so a shipped path relying on one has a
guard in development and none in an optimised wheel.

**The detector was wrong first, and was corrected before landing.** It counted
`conftest.py` files as production modules, which is backwards: importing test support is
conftest's job. Eight false positives, all of them fixtures doing exactly what fixtures
do. The shipped `non_test_package_python_files()` helper yields conftest, which is
reasonable for most gates and wrong for this one — a reminder that a shared discovery
helper encodes someone else's question, not necessarily yours.

### The dev/ tooling lane, and an exemption that had become a pre-authorisation

`testpaths` names exactly one file out of the whole `dev/` tree
(`dev/packaging/tests/test_installed_oracles.py`). Every other dev gate — locales,
identity, registry, docs, audit, sanitizer — runs only under `just test-dev-tooling`,
whose own doc line says it covers "the dev/ tooling gates that no other lane reaches".
So a default run, and both of this campaign's lanes, never collect them. Running that
lane's storage-adjacent subset: **86 failed, 939 passed**, dominated by registry
conformance work belonging to another campaign.

The finding worth keeping is `test_utf8_enrollment_inventory`'s SECOND assertion, and
the gate names the state better than a summary would: five entries in
`_KNOWN_VIOLATING_FILES` exempted nothing — four files had been cleaned since enrolment,
one no longer exists — and it calls them **silent pre-authorisations**.

That is the right reading, and it is the fail-open shape this campaign keeps finding in
new clothes. An exemption that has outlived its violation is not inert: it stands ready
to admit the NEXT bare literal in that file with nothing left to object, and the file
looks enrolled rather than clean to every future reader. A ratchet only ratchets if
entries leave it when their reason does.

Deleted, which locks those five files at zero. Eight bare literals in this domain now
route through `UTF_8_ENCODING` — custody service and login-session pointer writes,
capsule archive and record payloads, the secure-reference digest, the terminal writer,
and the KDF worker.

**The KDF worker was the one that needed checking rather than assuming.** It runs under
an import-graph prohibition — no sqlalchemy, no bs4, no blob_store, envelope, sql,
master_key or capsule machinery in the child — so adding an import could have pulled the
forbidden graph in. The gate was run rather than reasoned about, and stays green.

Six literals remain in `domain/calculations/registry`, left deliberately: they are that
campaign's files, and it has uncommitted work in them right now.

**A method note.** The first attempt inserted each import after "the last import line",
which landed them inside `TYPE_CHECKING` blocks and mid-way through parenthesised
imports — 21 syntax errors across five files. Re-done by parsing each module and
inserting after the last MODULE-LEVEL import node, verified by re-parsing. A textual
heuristic about Python structure is a guess; the AST is the structure.
