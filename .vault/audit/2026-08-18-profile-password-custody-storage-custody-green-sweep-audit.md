---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:953766a7d33e05e55abe66685181fc425b03d73111fd0866624268419a61e030'
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

### Every exemption list in the domain, and whether it can go stale

The pre-authorisation finding generalises, so it was swept rather than left as a lesson:
**17 exemption-shaped constants** across the domain's test modules (storage, user_profile,
persistence/profile, cli/_config), each checked for whether anything asserts its entries
still apply.

Eleven carry a staleness assertion. The six that do not were read individually, and none
is a defect:

* `_SNAPSHOT_EXCLUDED_FROM_SWEEP` excludes `schema_id` and `created_at` from a
  defaultable-field sweep, and each cites a dedicated case that carries its proof — both
  cited cases were confirmed to still exist, which is the failure mode the encoding gate's
  own history records (a comment justifying itself by citing a test a later sweep deleted).
* `_UNDECLARED_CENSO_PATH` claims `censo.filed_on` is not schema-declared. If it ever
  became declared the refusal would not fire and the assertion would red — the premise is
  self-protecting rather than silently invertible.
* `_UNDECLARED_FACTS` uses an obviously synthetic path nothing would ever declare.
* `_EXPECTED_STORE_CLASSES`, `_LITERAL_EXPECTED_VERSION` and `_DECLARED_CLASS` are pinned
  literals, not exemptions.

The classification-triad module deserves its own note, because it had already reached
this campaign's central insight independently and wrote it down: its expected set is
deliberately NOT derived from the production constant ("this literal is what makes a
widening fail rather than propagate"), and its foreign-class list is named one by one
rather than as a complement, because deriving it "meant admitting a class to the closed
set did not fail the two refusal tests — it deleted their cases, so the assertions
stopped existing rather than stopping passing." That is the vacuous-pass failure exactly,
found and fixed by someone else before this sweep arrived.

Production exemptions were checked too: the storage taxonomy's eleven `dormant_reason`
markers are gated by `test_every_dormant_member_states_a_reason_and_really_is_dormant`,
which refutes a dormancy claim from any module that references the member.

**Conclusion: no defect this pass.** The domain's exemption lists are, with the single
encoding ratchet fixed last pass, uniformly protected against outliving their reasons.
Recorded so the sweep is not repeated — the inventory is the durable artefact here, not
a fix.

### The reader accepted unboundedly more than the writer can emit

`read_sealed_archive` opens the archive `r:gz` and called `read()` on the payload member
with no ceiling. The bytes on disk therefore bound nothing: a member declaring an
enormous size whose compressed form is tiny is handed over in full. The path in is
`config profile restore`, which takes a path — an archive can be corrupted in place, or
handed to an operator by someone other than whoever wrote it — so this was an
operator-supplied memory-exhaustion surface.

**A cap existed and guarded the other direction.** `_MAX_PAYLOAD_BYTES` bounds the WRITE
path that serialises a capsule INTO an archive. Nothing bounded the read. That asymmetry
is what makes the fix free rather than a judgement call: the ceiling is set to the
writer's own cap, so no archive this product produced can exceed it and refusing above it
rejects nothing legitimate. A parity test holds the two equal, because the quieter failure
is a bound drifting BELOW the writer's cap — surfacing much later as an operator unable to
restore a real backup.

**An assertion was written and then removed rather than shipped.** It claimed a forged
`member.size` could smuggle a large payload past a size check. Running it showed the
opposite: `tarfile` limits `extractfile` to the declared size, so a forged SMALL size
truncates and is not a bypass at all. The ceiling's real subject is the opposite shape —
a huge declared size with a tiny compressed form. Shipping the original would have left a
test whose name asserted a threat that does not exist, and a docstring teaching the next
reader something false about the format. The corrected docstring states what the bound is
actually for.

That is the third time in this campaign a plausible threat model survived until it was
executed. The pattern is stable enough to state: **an assertion about a library's
behaviour is a hypothesis until the library runs it.**

### The less-trusted restore door had the weaker read

Following the untrusted-input seam from the sealed archive to the OTHER shape the same
verb accepts. `config profile restore` takes either an archive file or a capsule
DIRECTORY, and the directory is the least trusted input this domain handles: copied out
of a backup, supplied by someone else, or rebuilt by hand after a disk failure.

It was read with `path.is_file()` then `path.read_bytes()`. Meanwhile the PUBLISHED
capsule reader — whose source sits inside this product's own storage root, and is
therefore the *more* trusted of the two — already read the same four members through
custody's anchored, bounded, no-follow primitive with per-record ceilings. **The trust
levels and the read strengths ran in opposite directions.**

Three defects in that pair, each already solved next door:

* `read_bytes` **follows a symlink**, so a member could name a file outside the capsule
  and its contents would be adopted into the restored profile. In a gestor or
  multi-client setting that is an exfiltration route rather than a curiosity: the bytes
  land in a profile the capsule's supplier later receives back.
* it bounds **nothing**, though every member carries a declared ceiling the published
  reader applies — envelope 704 B, sentinel 8 KiB, database 64 MiB.
* `is_file()` then reopen is two operations on a NAME rather than one on a file, which is
  precisely what `read_optional_profile_custody_local_record` documents itself as
  existing to prevent. The anti-pattern was being run against the primitive built to
  replace it.

**Both refusals were asserted from what the code actually said, not from what the test
author expected.** The first draft guessed at wording and failed; the real messages are
"profile capsule record is not a bounded regular file" for the oversized member and
"must not be a reparse point or directory" for the symlink — the no-follow guard naming
itself, which is a stronger and more specific refusal than the one anticipated. Both are
now pinned by their real text.

**Generalisable:** where one concept has two doors, compare their reads and ask which
door is more exposed. Hardening tends to accrue on the path its author was looking at,
which is usually the internal one — the external door is the one that was already
"working".

### A ceiling defined twice, agreeing with itself

Sweeping the domain's remaining bare file reads to see whether the two-doors asymmetry
recurred: it does not. Every one is either bundled package data (the BIP-39 wordlist,
which also checks it holds exactly 2048 words), an operator-TYPED path where following
the name is the operator's own intent (`AttachmentStore.put_file`), or already hardened
in place. `custody/_inventory.py`'s walk is the strongest read in the domain — `lstat`,
explicit link and reparse refusal, regular-file check, size cap, Windows anchor, and a
post-read dev/ino/size identity re-check to catch a swap mid-read.

That read is where the finding was, though not in the read itself.
`PROFILE_CUSTODY_DATA_FILE_MAX_BYTES` and `PROFILE_CUSTODY_DATA_MAX_ENTRIES` were each
defined **twice**, with equal values, in `_filesystem` and `_inventory`. Two halves of
one contract enforced different copies: the capsule data reader used the `_filesystem`
pair, while the inventory that produces a capsule's integrity manifest used its own.

**The equality is what let it survive.** Nothing failed and nothing diverged precisely
because the copies agreed — so the duplication was invisible until someone raised one of
them. At that point a capsule could be inventoried and not readable, or readable and not
inventoriable, and the disagreement would present to an operator as a corrupt-looking
capsule rather than as a constant somebody edited. A ceiling is a decision about what
this format admits, not a value that gets independently rediscovered.

Unified on the owning module, and gated. **The gate counts module-level ASSIGNMENTS
rather than resolved attributes**, which is the load-bearing detail: after an import the
second module's attribute is the same object, so comparing values — or even identity —
would pass over exactly the state being forbidden. Only the definition is evidence of a
second home, and that distinction is asserted directly so a later, weaker reading cannot
satisfy the check.

**Generalisable:** duplicated constants are hardest to see when they agree, and a test
that compares their VALUES will never find them. Look for two definitions, not two
values.

### Seven private copies of three crypto parameters

Sweeping the domain for every constant with more than one defining module — the
enumerable form of last pass's finding. Ten names came back; most are per-module idioms
that SHOULD repeat (`_LOGGER`, the lazy-export maps, a `TypeAdapter`). Three were real,
and they were the crypto parameters:

* `_DEK_BYTES = 32` in `custody/_acceleration_receipt.py`, `custody/_records.py` and
  `master_key/_bucket_session.py`
* `_AEAD_NONCE_BYTES = 12` and `_AEAD_TAG_BYTES = 16` in `custody/_records.py` and
  `custody/_sentinel_contract.py`

`storage.crypto` already exported all three as `KEY_SIZE`, `NONCE_SIZE` and
`GCM_TAG_SIZE` — in the same package tree, each documented with the standard it comes
from. The nonce and tag sizes cite NIST SP 800-38D. A private `= 12` cites nothing, so
the copies were not merely duplicates; they were the values stripped of their reason.

**These are worse than a duplicated file ceiling.** A ceiling that diverges refuses a
file — loud, and the operator sees it. A nonce or tag size that diverges means two
readers of the SAME record disagree about where the tag ends and the ciphertext begins,
and a key length that diverges means two modules disagree about how much key there is.
All seven agreed, which is precisely why nothing had ever surfaced them.

Call sites now use the canonical names rather than a local alias, so there is one NAME as
well as one value — an alias would have left the gate a second assignment to police.

The single-home gate is extended across the whole storage tree, and its anti-vacuity half
was strengthened in the process: the new assertion is an equality against one path, which
would pass vacuously if the walk stopped seeing everything *except* that path. The walk is
now required to find the modules that used to hold the copies.

**Generalisable, and the sharper half of last pass's rule:** when a duplicated constant
also has a canonical home elsewhere, the private copy is not just a second definition —
it is the number without its justification. Look for a value that appears with a citation
in one place and bare in another.

### The same value with no name at all

The residue a name-keyed sweep structurally cannot see. After retiring seven private
copies of the crypto parameters, the same magnitudes were still written inline: two
modules split an AEAD ciphertext with a bare `16` — `ciphertext[:-16]` and
`ciphertext[-16:]` — and four sites checked a DEK against a bare `32`. Those are
`GCM_TAG_SIZE` and `KEY_SIZE`. Inline they are the value with neither its name nor its
reason, which is exactly why they outlived the named copies.

**The rejections are the substance.** The scan surfaced sixteen inline uses of these
magnitudes and most were left alone: a SHA-256 digest is 32 bytes, a salt is 16, a hex
route-marker prefix is 16. Those are different concepts that happen to share a number,
and renaming them to a crypto constant would assert a relationship that does not exist —
a worse defect than the duplication, and one that would read as deliberate. A magnitude
sweep produces candidates; only the surrounding meaning decides.

**Renaming changes no behaviour, so the test does not assert the rename.** There is no
sound gate here either: a tree-wide prohibition on a bare `16` would fire on every salt
and digest above. What is assertable is the property the rename makes checkable — the tag
the production writer splits off is exactly as long as the crypto layer says a tag is,
driven through real encryption rather than compared against a constant. Proven by slicing
at 15 instead.

**Generalisable:** a refactor that changes no behaviour still has a property worth
pinning, and it is usually the one the refactor made expressible. Ask what the change now
lets you say that you could not say before, and assert that — rather than asserting the
edit, or shipping the edit unasserted.

### One name, three guarantees — and a flag that vanishes on Windows

Extending the duplication sweep from constants to FUNCTIONS. `_read_regular_file` was
defined **three times** in the custody package, with three different guarantees. A call
site cannot see that: it reads the name, assumes the anchored no-follow read, and gets
whichever implementation its own module happens to define.

**The sentinel's copy is the finding, and it was measured rather than reasoned about.**
It relied on `os.O_NOFOLLOW`, which does not exist on Windows — `getattr(os,
"O_NOFOLLOW", 0)` quietly becomes `0` — so the protection the code appears to request
silently is not requested at all on this project's primary platform. Driving both
functions against a real symlink: the sentinel reader **followed it and returned the
linked file's contents**; its identically-named sibling refused with "must not be a
reparse point or directory".

A `getattr(os, FLAG, 0)` fallback is worth naming as a pattern: it turns an unsupported
platform into a SILENTLY WEAKER one rather than a loud failure, and the weakening is
invisible at every call site.

Deleted rather than repaired, after classifying which half was superseded:
`read_profile_custody_sentinel` had no caller anywhere, and the live sentinel read goes
through `_capsule_data` using the anchored primitive with the sentinel bound. The WRITE
half is live and stays. That classification is what made deletion safe rather than brave.

The recovery artifact's reader is renamed `_read_external_regular_file` for the
constraint it carries — it anchors a directory OUTSIDE the storage root, which the
in-root primitive cannot do. Genuinely different, not a duplicate to merge, which is the
substitutability filter the audit rules ask for.

**Two notes on the gates, both self-inflicted and both instructive.** The reader check
first reused the constant scan, which reads assignments — asking it about a function
returned nothing, and under any assertion phrased as a maximum that would have read as
compliance. It now uses a function-aware scan, with both behaviours asserted so the two
cannot silently collapse into one helper. Second, the sensitive-write inventory reddened
on the deletion, demanding its stale declaration for the removed function be dropped:
that gate did exactly its job, and it is the same "declaration outliving its subject"
discipline this campaign has been enforcing elsewhere, arriving from the other side.

### The silently-degrading flag, swept to its boundary

Taking the `getattr(os, FLAG, 0)` pattern named last pass and asking how far it reaches.
Twenty-odd sites in the custody package use that idiom; the classification is what
matters:

* `O_BINARY → 0` on POSIX is **correct** — POSIX has no text mode, so the fallback
  requests nothing because nothing is needed.
* `FILE_ATTRIBUTE_REPARSE_POINT → 0` on POSIX is **correct** for the same reason: there
  are no reparse points there, and `O_NOFOLLOW` covers the equivalent case.
* `O_NOFOLLOW → 0` on Windows is the dangerous one, because the guarantee it names is
  still needed on that platform and is simply not requested.

**All ten surviving `O_NOFOLLOW` uses are POSIX-gated** — inside an `os.name` branch,
passing `dir_fd=` (which Windows does not support, so the call cannot succeed there), or
in a helper named for the platform it serves. Windows takes its protection from an
explicit reparse-point refusal instead. So the sentinel reader removed last pass was the
only Windows-reachable instance, and the class is closed rather than merely one instance
of it. That is measured, not assumed.

A gate now holds the boundary, and it is **structural on purpose**. A behavioural check
would need every read path driven with a link in place, and the paths that matter most
are the hardest to drive; what is cheap and complete is the property that made the bug
possible — asking for no-follow where the platform cannot supply it. Its discriminating
case is written against a synthetic function rather than the tree, because a clean tree
is exactly when a detector stops being exercised by its own subject and can rot into
always-passing.

**Generalisable:** a compatibility fallback deserves classifying by whether the thing it
falls back from is still NEEDED on the platform that lacks it. `O_BINARY` and
`O_NOFOLLOW` look identical as code and are opposites as decisions — one degrades to a
no-op because nothing is required, the other degrades to a missing guarantee.

### The detector this campaign built had the defect this campaign hunts

Two sweeps came back clean before the finding arrived, and both are worth recording so
they are not repeated.

**Fallback shapes other than `getattr(os, FLAG, 0)`.** The domain holds exactly two:
the keyring import, which fails CLOSED with a typed `KeyringUnavailableError` and
additionally refuses a null keyring by priority; and a `hasattr` that is class
validation, not a fallback. Neither substitutes a weaker path.

**Handlers that swallow into `pass`/`None`/`continue`.** Thirty-nine of them, and the
classification is the point: `FileNotFoundError → None` means absent, which is a real
answer; `FileExistsError → pass` inside an exclusive-create retry is the retry; and
`os.fstat` raising in `_is_open_file_descriptor` IS the answer that probe asks for.
The acceleration-receipt handlers turn a corrupt receipt or an unavailable keychain into
"no acceleration", which costs a re-authentication and is the safe direction. The one
handler shaped like a fail-open — `_capsule_discovery` skipping a candidate it cannot
anchor, so a retired member there goes undetected — sits in a function with no caller.

**Then the real finding, in this campaign's own instrument.** The unused-export gate
shipped earlier counted every string constant as a use, so a name listed in its OWN
module's `__all__` counted as used. A module declaring what it offers was being read as
somebody taking it — meaning a name was reported as used BECAUSE it was exported, which
is exactly backwards for a gate asking whether exports are used.

Eight names hid behind it, including `decrypt_profile_bundle_with_passphrase` — the read
half of the bundle whose write half ships, which is the concrete symbol behind the
portability gap this campaign recorded weeks of iterations ago. The gate that was
supposed to surface such things was structurally unable to see this one.

Each of the eight is now declared with its own reason rather than a shared one: four
belong to the portability surface another owner is rebuilding;
`bound_profile_record_session` is used by eight TEST modules and no production caller,
which is what a test-support helper looks like rather than a dead symbol; two have no
consumer anywhere and are genuine deletion candidates in other campaigns' surfaces.

**The two halves now pin the detector from both sides.** Loosen it again and the eight
records stop describing anything, so the staleness assertion reds — the declarations
defend the detector's precision, not just the tree's state. Proven by restoring the blind
spot.

**Generalisable:** point the campaign's method at the campaign's own tools. A detector is
production code for the question it answers, and it is subject to every failure mode it
was built to find — including counting a declaration as a use.

### The gate that catalogued four failed detectors was the fifth

Continuing to point the method at this campaign's own tools, now at the highest-stakes
gate: the one guarding lost-update on encrypted singleton records.

Its docstring is a careful record of four previous detectors that each went green over
live instances of the defect — a line-oriented grep, a syntactic match, an `ast.Assign`
tracker, a direct-binding taint check — and concludes that this fifth one "does not hunt.
It ENUMERATES every composing write". Probing it against ordinary refactors showed the
enumeration is itself shape-based, and two spellings walk straight out of it:

```
writer = repository.save_with_secure_object_writes ; writer(...)
getattr(repository, "save_with_secure_object_writes")(...)
```

Neither is exotic — the first is method extraction, the second is what a dispatch loop
reaches for — and both were reported clean.

Both are recognised now, each with a discriminating case, plus an anti-tautology pair
proving a revision passed through the widened spellings still clears the site: widening a
detector until everything is a violation would flag exactly the guarded code the gate
exists to encourage. The tree stayed green through the widening, so no site was hiding
behind the old matcher — this closes an evasion rather than uncovering a defect.

**The docstring was corrected in the same change**, and that is the part worth carrying.
"Does not hunt" was an overstatement about a matcher that hunts three spellings. A gate
whose prose oversells its reach is worse than one that admits a narrow scope, because the
next reader stops checking — and this file's own history is four detectors that were each
believed complete.

**Generalisable:** a detector's claim about itself is a claim to test. Write the evasions
you would use if you wanted the gate to miss something, run them, and either close them or
narrow the claim to what survives.

### The evasion was systemic across this campaign's gates, not one gate's slip

Having found the composing-write detector walkable, the same probe was run against the
remaining shape-matching gates. **Two more were evadable in exactly the same way**, which
makes it a property of how these detectors were written rather than one lapse.

**The unsecured-session canary** matched `BucketSession.open` only as an attribute call.
Three ordinary refactors reported a function as opening no session, so the canary
requirement never applied to it: binding the class to a local, binding the opener, and
`getattr`. Of the three gates this is the worst to have been evadable — a miss here is a
real taxpayer's records written under a published deterministic key.

Its **anti-tautology case earns as much attention as the widening**. `open` is among the
most common method names there is — a file, a connection, a lock — so an unrelated
`.open` and `open_resumed` are both asserted NOT to be flagged. A detector that filled
this gate with functions that never touch a session would convert its requirement into
noise to dismiss, which fails in a quieter way than missing a site.

**The test-support import gate** scanned import STATEMENTS only, so
`importlib.import_module("cadrumo.tests...")` walked past it. That is not an exotic
spelling in this tree: `aeat-architecture-boundaries` explicitly sanctions a dynamic
`import_module` to break a cycle, so a production module has a legitimate reason to
already hold one. Only a tests path is flagged, with a case proving an ordinary dynamic
import is not.

Both trees stayed green through both widenings, so nothing was hiding behind either
matcher — these close evasions rather than uncover defects.

**Generalisable, and stronger than the single-gate version:** when one detector proves
evadable, the evasion is evidence about the AUTHOR'S habit, not about that detector.
Every gate written the same way shares it. The cheap sweep is to take the working evasion
and replay it against every sibling gate before assuming the first was unlucky.

### Mention is not containment

Replaying the evasion probe across the remaining gates found a different hole in the same
family, and a sharper one.

The no-follow gate asked whether a function's SOURCE **contained** gating text. Two
shapes passed it: a function that branches on `os.name` somewhere and requests the flag
OUTSIDE that branch, and one whose only `os.name` sits in a comment. It was checking that
the author had thought about platforms, not that this use was guarded — which is exactly
the sentinel bug it was written to prevent, wearing a decorative branch.

It now walks the AST and requires each flag request to sit INSIDE an `os.name` branch,
keeping the two other admissible gates (a `dir_fd=` argument Windows cannot satisfy, a
`posix`-named helper). **The ten existing sites still pass under the stricter rule**,
which is the useful part: they were genuinely gated rather than merely mentioning a
platform, and the widening closed an evasion instead of exposing a defect.

The ceilings scan was made recursive in the same pass. It used `glob("*.py")`, which
matched `rglob` exactly — because this package has no subpackages. It was complete **by
accident of layout**, and one subpackage would have silently narrowed every check built
on it, with nothing failing to say so.

**Generalisable, and distinct from the alias/getattr family:** a textual check answers
"does this code mention the safeguard", while the property is "is this use covered by
it". The two agree until someone writes the safeguard somewhere else in the same
function — which a refactor does routinely, and which reads as more careful code, not
less. When a gate greps for evidence of thought, it is measuring the author rather than
the code.

A companion note on completeness: a scan that is correct only because of the current
directory layout is not correct, it is lucky. `glob` versus `rglob` is invisible until
the day it matters, and by then the check has been quietly narrower than its name for
some time.

### The lesson applied to gates this campaign did not write

Replaying mention-versus-containment beyond this campaign's own gates found **three**
pre-existing ones with the same hole. Each asserts that a surface routes through a shared
core by testing whether the routine's NAME appears in its source:

* `_validate_envelope(` — `envelope/test_secure_bound_envelope_gates`
* `decode_secure_object_row(` — `sql/test_secure_object_decode_order`
* `probe_row_decryptability(` — `sql/test_secure_object_integrity_agreement`

A surface that stops delegating but keeps a sentence naming the routine passes all three.
Demonstrated rather than argued: substituting a `load()` whose only reference to the gate
is a docstring, the old text check accepted it and the new one names it.

**The negative halves are deliberately left as text checks**, and that asymmetry is the
judgement worth recording. `assert "decrypt_secure_object_payload(" not in source` uses
the presence of a name as evidence of RE-IMPLEMENTATION — so a comment mentioning it
fails safe, refusing something harmless, rather than passing something dangerous.
Tightening those to AST calls would trade a tolerable false positive for a real hole.
The same textual technique is right in one direction and wrong in the other, which is why
"replace text checks with AST checks" would have been the wrong rule to apply
mechanically.

Also closed here: an inconsistency of this campaign's own making. The no-follow gate was
still scanning with `glob("*.py")` after its sibling in the same package was made
recursive one pass earlier — fixing the instance and not the class, which is the failure
these notes keep recording. Both now route through the project's canonical
`scan_directory(recursive=True)` rather than a raw pathlib glob, so they inherit the
convention instead of restating it.

**Generalisable:** a technique is not right or wrong on its own, only in a direction.
Before sweeping a fix across siblings, check which way each instance fails — the ones
that fail safe may be correct exactly as they are.

### Closing the gate-quality seam with a measurement instead of another guess

Five passes of probing detectors produced findings each time, so the question became
whether the seam was exhausted or merely being sampled. It was answered by measuring
rather than by trying one more probe.

The first sweep keyed on variables NAMED like source (`source`, `segment`, `text`) and
returned 23 hits — but most were assertions on rendered error messages and captured log
output, which are exactly right as text checks. Name-based selection was the wrong
instrument. Re-running it by **provenance** — positive membership over a variable
assigned from `inspect.getsource` — returned 20, all genuinely about code.

**Nineteen of those twenty are correct as they stand**, and separating them is the
substance. They assert that an implementation contains its OWN logic: the envelope gate
still raises its two errors, the integrity probe still opens ciphertext, the verifier
still recomputes the row key. Evading one means deleting the code while keeping prose
that describes it, and a stray mention there fails SAFE — it refuses something harmless.
The dangerous direction is delegation, where an ordinary refactor moves a call out of a
function and leaves the sentence behind.

The twentieth was a delegation check: the public scans routing through
`_iter_identified_payloads`. Its own docstring says no input can distinguish "the default
verifies" from "a second unverified scan was reintroduced beside it" — so the text check
was the only thing standing between the tree and that case, and a docstring mention
satisfied it. Fixed and proven by substituting an `iter_records` whose only reference is
prose.

**The seam is closed**, with the boundary recorded rather than left implicit: delegation
checks are AST calls, own-logic checks stay textual, message and log assertions were never
in scope.

**Generalisable, and the reason this pass ran a measurement instead of a probe:** a seam
that keeps yielding is either deep or being sampled badly, and the way to tell is to
enumerate its population once. The first enumeration here selected by NAME and produced
mostly noise; the second selected by PROVENANCE and produced a set small enough to judge
one by one. When a sweep returns mostly false positives, suspect the selector before
concluding the population is dirty.

### Coverage as the selector, after a name-based one produced noise

A fresh axis, opened with the previous pass's lesson applied immediately. The first
attempt enumerated domain modules whose public symbols **no test names** and returned 30
— mostly CLI registration functions and command callbacks, which are driven end-to-end
through the CLI runner without any test mentioning their names. A name-based selector
again, and again mostly noise. Rather than triage 30 candidates, the selector was
replaced: run the lanes under coverage and read what is actually unexecuted.

That produced two items, both real.

**`exit_provider_session` sat at 32% — its body was unexecuted.** The function carries an
explicit safety property in its own docstring: if another boundary already replaced the
active binding, only the CAPTURED session is closed, and a different current session is
never evicted. Nothing checked it.

The property is invisible to ordinary testing because it has **no bad input**. It needs
two bindings and an unwind in between. A provider that reached for
`close_active_bucket_session` unconditionally would seal whatever happened to be bound at
that moment — another context's unlocked bucket, taken away by an unwind it never took
part in — and every single-session test would still pass. Substituting exactly that
teardown reds the discriminating case. Closure is asserted on each session's own sealed
state rather than a call count, because a teardown that "ran" while leaving a session
usable is the failure. 32% → 92%.

**`_rotation_key_fixtures.py` sat at 0%** — a fixture module for the rotation subsystem
this campaign retired many passes ago, with no importer anywhere. Deleting the subsystem
and its tests left its fixtures behind, and nothing noticed because an unimported test
helper is invisible to every gate: it is not production code, so the dead-export sweeps
skip it, and it is not a test, so no failure names it. Deleted.

**Generalisable:** the campaign's sweeps all select by NAME — a symbol, a constant, a
call, an import. That whole family shares a blind spot for code whose usage is
behavioural, and it produces false positives for exactly the same reason. Coverage
selects by EXECUTION, which is the one signal none of the name-based instruments can
fake, and it found both a dead file and an unexecuted safety property that eight passes
of name-based sweeping had walked past.

### The strongest guard in the domain had never judged anything

Following coverage as the selector into `_master_key`, at 62% with the tax-id extraction
and refusal lines among the gaps.

The canary has five existing branch tests, and **every one of them ends earlier in the
function** than the decision: no database, no rows, an unreadable file, an undecryptable
payload, the `unsecured` label bucket. Each is a legitimate early exit, and together they
looked like coverage of the guard. What they never reach is the path where a stored
profile is decrypted and its tax id judged — which is the only path that decides whether
a real taxpayer's records may be opened under a published deterministic key.

So what actually stood behind that guard was a structural gate asserting the CALL exists
(added earlier in this campaign) and unit tests of the predicate in isolation. Both are
useful and neither executes the integration. **A set of branch tests can cover a function
thoroughly while never once reaching its verdict.**

Now driven end to end: the envelope is encrypted through the same `EncryptedBytes` column
the repository binds with — so the bytes on disk are produced the way production produces
them, not by a fixture's own idea of the format — stored as a real row, and read back
under an active unsecured session. The two cases differ in exactly one value. A real NIF
refuses; a synthetic one is admitted, which is not decoration: without it, a canary that
raised on ANY decryptable row would satisfy the refusal while making the unsecured
backend unusable for the throwaway data it exists to serve. Proven by neutering the
recogniser — the real case reds, the synthetic one still passes. 62% → 67%.

`_provider_enter` remains the uncovered region and is recorded as the next candidate on
this axis.

**Generalisable:** when a function is guarded by several tests that all exercise its
EARLY EXITS, the guard is untested. Early exits are easy to construct and the decision is
not, so a test suite drifts toward them naturally — and the resulting coverage reads as
thorough precisely because there are so many cases.

A note on this pass's method: five unit failures appeared after the change and were NOT
attributed until re-running twice, both fully green (1521). The worktree's known
concurrent-I/O flakiness explains them, and the new test writes a real SQLite database,
which is exactly the shape that would deserve suspicion — so it was confirmed rather than
assumed away.

### A test that passed for the wrong reason, caught by breaking the code

The last uncovered region of `_master_key` was `_provider_enter` — the entry path that
CALLS the canary. Covering it completes the guard end to end: previously the link between
"the operator entered the unsecured provider" and "the canary ran" rested on a structural
gate asserting the call exists in the source. 67% → 91% for the module, 86% → 92% for the
package.

**The second assertion was wrong first, and how it was caught is the finding.** It used a
`with` block and asserted the context-var was clear after refusal. It passed — and it
passed with the unwind REMOVED. Rather than accept the green as proof, the break was
investigated: `__enter__` raising means `__exit__` never runs, and the `with` statement
dropped every reference, so CPython finalised the `activate_session` generator and its
`finally` reset the binding. **The test was measuring refcounting, not the guard.**

Rewritten to call `__enter__` directly and hold the provider, asserting what only the
unwind does — the session detached and the bookkeeping cleared. With the unwind removed
the published-key session is left bound, attached and **unsealed**: refused at the door
while the door stands open, so every later column read in that context decrypts under a
key anyone can read. That is now the reported failure.

**Generalisable, and the sharpest version of this campaign's recurring theme:** proving a
gate bites is not a formality to complete, it is a measurement that can come back
NEGATIVE and must then be believed. The break produced a green run; the tempting reading
was "the patch did not take effect", and checking showed the patch was installed and the
property held anyway — for a reason that had nothing to do with the code under test.
Garbage collection is a plausible accomplice for any teardown assertion, and it is
invisible in a passing test.

The corrected docstring records the earlier version and why it was insufficient. A
passing assertion that passes for the wrong reason is harder to notice the second time,
because by then it has a history of being green.

### The accepting paths were tested; the refusals were not

Coverage again, on `_secure_object_schema` at 70%. The unexecuted lines were **the
refusals themselves** — every branch that raises on a shape the format cannot produce.
The accepting paths were exercised, so the module read as tested while the question it
exists to answer, *what happens when the stored bytes are wrong*, had never been asked.

This is the same shape as the canary's early-exit coverage two passes ago, from the other
side: there, many tests reached the function and none reached its verdict; here, the
happy path was covered and none of the refusals were. Both produce a module that looks
well tested. **Coverage of a parser means little until the malformed inputs are among the
cases**, because parsers are mostly refusal by line count and mostly acceptance by test
count.

What these helpers read is whatever the database actually holds — a truncated write, a
hand-edited row, a column written by something that is not this code.
`no-legacy-compatibility` is explicit: refuse, do not tolerate. An ancestry column that
will not parse is corruption now, and returning an empty chain would erase a revision's
lineage rather than report it unreadable.

Each refusal is paired with the acceptance it must not break — bytes, bytearray,
memoryview and str all still coerce; NULL and empty ancestry are still a legitimately
empty chain — because a module where everything raised would satisfy every refusal on its
own. The sharpest case is a well-formed JSON list whose members are not revision ids: the
shape closest to valid, and what a partial write produces. Proven by making the JSON
refusal return `()` instead.

**A flake, now with two data points.** `test_modelo_catalogue_defaults_isolate_bucket_writes`
has failed in two separate lane runs during this campaign and passed on every re-run,
including twice when run directly alongside the new tests. The worktree's known
concurrent-I/O flakiness on its backing share explains it, and the isolation check was
run precisely because these new tests write real SQLite databases and that name would be
the first thing to suspect. Recorded rather than dismissed: one occurrence is noise, two
is a candidate, and the next reader should not have to re-derive that it was checked.

### The redaction exemption list was defined by process-global state

`core/logging.py:56` built the set naming which log-record fields the scrubber skips:

    _STANDARD_LOG_RECORD_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)

`SecretScrubbingFilter` (`core/logging.py:397`) scrubs every field on a record EXCEPT
those in that set, which makes it an exemption list rather than an inventory. And
`logging.makeLogRecord` does not build a plain record — it dispatches through the
**process-global** `_logRecordFactory`. Any field an installed factory adds therefore
enrolled ITSELF as "standard" and was skipped by the scrubber. The exemption was widened
by global state that anything in the process, including a third-party library, can set,
and nothing in the redaction suite could see it: those tests all run in a process where
the factory state happens to be benign.

Fixed by constructing the record directly. With no factory installed the two expressions
yield an identical key set, so the normal case is unchanged — measured, not assumed.

**The same call was also an import cycle.** Line 56 runs at module scope, so it invoked
the factory during the module's own initialisation. Cadrumo's factory reaches the
observability layer, which imports straight back into the half-built module and fails on
`attach_run_sink`. The deferred-import defence inside the factory (`core/logging.py:442`,
with a comment naming this exact hazard) assumes the factory is only ever called AFTER
initialisation — and line 56 was the one call that broke that assumption. A deferred
import defends against a late caller; it cannot defend against its own module calling it
early.

The durable lesson: **a set named for a closed vocabulary, but built through an
extensible hook, is not an inventory of that vocabulary — it is whatever the hook
currently produces.** Where such a set governs what is EXEMPT from a safety pass, the
hook becomes a way to opt out of that pass. Look for the pattern wherever "standard",
"builtin" or "known" fields are derived at runtime rather than declared.

Both halves are gated in `core/tests/test_redaction_exemption_set_is_stdlib_only.py`
through a real subprocess import, because the condition is "a factory was installed
BEFORE this module initialised" and that cannot be staged in a process where it is
already imported. The first attempt at the cycle half was NOT discriminating — its probe
factory added a field but imported nothing, so it passed against the defective code. Only
cadrumo's real factory reaches observability, and the test now installs that one; both
halves were then confirmed to fail against the old expression and pass against the new.

**How it was found:** not by looking for it. A coverage run crashed, and the crash was
investigated instead of worked around. The instrument failing was the finding.

### Open: lock tests fail under fixed ordering, and it pre-dates this work

Running the unit lane with `-p no:randomly` fails deterministically (reproduced twice)
where the random-order lane is green. Without coverage,
`test_custody_transactions.py::test_pointer_cas_and_active_pointer_writer_share_one_root_lock`
fails; with coverage, two different lock tests in `test_substrate_smoke.py` fail instead.
Every failure so far is a LOCK test.

Verified pre-existing: the same failure reproduces with HEAD's `logging.py` restored in
place, so it is not a consequence of the fix above. In `test_file_lock_serializes_writers`
the captured log shows the production lock behaving exactly as designed — acquired, timed
out, released — and the expected `LockAcquisitionError` raised, yet `pytest.raises` did
not suppress it. That signature points at two distinct class objects of the same name
rather than a locking defect, which would make it a module-identity problem in the
harness. Not yet confirmed; recorded with the evidence so the next reader starts from the
measurement rather than the symptom.

### The active-profile pointer read crashed a process starting mid-switch

The previous entry left fixed-order lock failures open with a hypothesis about
duplicate class objects. That hypothesis was WRONG, and reading the actual traceback
rather than trusting it produced the real defect.

`read_pointer` (`core/_bucket_pointer_io.py`) sits on the `Settings()` bootstrap path —
every process resolves the active-profile pointer as it starts. A peer switching profile
rewrites that file through write-then-rename and clears it through `unlink`. Two failures
follow, both measured here rather than reasoned about:

- **A TOCTOU on the absence guard.** The function checked `is_file()` and then opened the
  path. When a concurrent clear lands between the two, it raised `FileNotFoundError` from
  a function whose documented contract answers `None` for an absent pointer.
- **A refused open under contention**, as `PermissionError`. This is the one that crashed
  the test's child process during import.

Measured against the real functions: over ~48,000 reads racing a real restore/clear
cycle, 278 `PermissionError` and 1 `FileNotFoundError`. After the fix, zero.

**The measurement overturned the obvious fix twice.** First, a race harness showed 72,727
concurrent reads of an `os.replace`-d file with ZERO read failures — the reader is fine;
it is the WRITER's replace that Windows refuses. So the read-side failure was not the
replace window, and a fix aimed there would have addressed nothing. Second, the existing
canonical helper for exactly these Windows codes (`core/_lockfile_unlink.py`) discriminates
transient contention from a denying ACL by `winerror` in `{5, 32}` — but the read-side
`PermissionError` arrives with **`winerror` unset**, so that discriminator does not apply
here. Only a bounded wait separates the two cases on this path, which is the same
reasoning that module already ratifies in prose: the retry budget is the discriminator,
not the code.

Two constraints shaped the fix. `_bucket_pointer_io` cannot import `core.logging` — the
module's own comments document that doing so recreates the Settings bootstrap cycle — so
the retry is stdlib-only and cannot reuse `unlink_lockfile`, which does import it. And the
retry is Windows-gated: POSIX has no sharing-violation class, so an `EACCES` there is
genuine and propagates on the first attempt.

Gated by a REAL race against the real IO functions rather than an injected exception,
because the failure is a property of the filesystem under contention and an injected
error would only re-assert the handler. The race carries an anti-vacuity guard — it
asserts the reader observed BOTH a written and a cleared pointer, so a run where the
threads never overlapped fails instead of passing green. A third test pins that tolerating
the race did not become tolerating everything: absence is still `None`, and a malformed
pointer still raises.

**Still open, and now known to be a different bug.** The writer half of the same window is
unfixed: `restore_pointer` and `clear_pointer` lose to a reader's open handle with
`winerror` 32 and 5 (426 and 115 occurrences in the same 8-second race). In production
those run under the custody root lock, but a foreign reader — any process bootstrapping
Settings — does not take that lock and can block them. `unlink_lockfile` already solves
exactly this shape but cannot be imported here, which is the tension to resolve.

**Also still open:** `test_substrate_smoke.py`'s two lock tests fail only under
`-p no:randomly` combined with `--cov`, and are green in isolation, in both shipping
lanes, and under fixed order without coverage. The signature is an expected
`LockAcquisitionError` escaping a `pytest.raises` that names it, which would mean two
distinct class objects of that name; the class has one canonical home behind a lazy
re-export, so that is unexplained. Bisecting a cross-file interaction costs several full
runs and it reproduces only in a diagnostic configuration, so it is recorded rather than
chased. Both shipping lanes stay green.

**Method note:** the pre-existing core failures were confirmed pre-existing by reverting
this change and re-running the same seven gates, not by inspecting whether the offending
lines looked related. They are all `datetime` clock-seam and registry-parity gates owned
by other campaigns.

### The custody root lock serialises pointer writers but not readers

The writer half left open by the previous entry is now closed, and the reason it
existed is worth stating plainly: **the lock covers the wrong population.** Pointer
writes are serialised by the custody root lock, so cooperating writers cannot
interleave. Readers take no lock at all — they cannot, because `read_pointer` runs
during `Settings()` bootstrap, before there is anything to lock with. Every process
reads the pointer as it starts. On Windows a reader's open handle refuses the
writer's replace and unlink outright, so a profile switch or a logout could fail
while correctly holding the lock that was supposed to make it safe.

Measured over an eight-second race against a reader loop: 426 `ERROR_SHARING_VIOLATION`
and 115 `ERROR_ACCESS_DENIED`. After the fix, zero on both sides of the window.

**Checked for the fail-open reading first, and it is not one.** Every caller propagates:
`ActiveProfilePointerTransaction` raises rather than swallowing, and `compare_and_write`
re-reads to confirm publication. Logout is the sharpest caller — it closes the session
artefacts BEFORE clearing the pointer, so a refusal leaves the secrets correctly
zeroised and the pointer still naming the profile. That is fail-closed and the secret
handling stays correct; what the operator gets is a raw `OSError` and a stale selection.
Worth fixing as robustness, not as a confidentiality defect, and the distinction is
recorded so a later reader does not re-escalate it.

**The tension named in the previous entry is resolved rather than worked around.**
`core/_lockfile_unlink.py` already encoded these two codes and the reasoning behind them,
but could not be reused because it imports `core.logging`, which `_bucket_pointer_io`
must not. The codes and their predicate now live in `core/_windows_contention.py`, which
imports nothing at all and is therefore safe from both. Each consumer keeps its own retry
budget, because the right budget depends on what losing the race costs it — a stranded
lockfile wedges a subsystem, a refused pointer write fails one command.

Note the asymmetry between the two halves of this same window, which is why one shared
helper could not serve both: the WRITE refusals carry `winerror` 32 and 5, so contention
is identified by code and bounded by the budget. The READ refusal carries no `winerror`
at all, so only the budget separates it from a denying ACL. Same file, same contention,
two different discriminators available.

Gated by a real race in both directions, each with an anti-vacuity guard asserting the
threads actually overlapped, plus a predicate gate whose sharp test is the FAIL-SAFE
direction: a POSIX `EACCES` must never be classified as contention, because every
consumer waits on a `True` answer and would turn a permanent refusal into a stall. Proven
by making the predicate answer `True` for any `PermissionError` — two tests fail. The
write gate's anti-tautology case puts a directory at the pointer path: unremovable, so a
retry that absorbed the error class outright would report a logout that silently left the
profile selected.

### A concurrent sweep committed production code mid-probe, disabling a live guard

**The incident, recorded because the method caused it.** Proving a gate bites requires
breaking the production code and observing the failure. The standing discipline is to
break it from OUTSIDE the repo — a scratchpad pytest plugin — so no tracked file is ever
mutated. That is not always possible: when the guard under test is an inline conditional
in a module, the only way to weaken it is to edit the file.

While that window was open, roughly three seconds, a peer's sweep committed the working
tree. It captured `_capsule_record.py` carrying `if False:` in place of the assertion
that an initial profile record is exactly revision one without a predecessor. A live
integrity guard shipped disabled on `main`, in a commit whose message announced coverage
for that very authority.

It was caught only because the follow-up `git status` showed the file as modified when it
should have been clean, and the diff was read rather than assumed to be the restore.
Restored in `68e08b020c`; the full file was then re-checked for residue from the other two
probes, both of which had been restored before their own sweeps.

Two durable rules follow:

- **After every break-and-restore, diff the file against HEAD rather than trusting the
  restore.** The restore itself is reliable; what is not reliable is that HEAD still
  matches it afterwards. In this worktree the danger is not a failed restore but a sweep
  landing between the break and the restore.
- **Prefer a weakening that cannot be committed silently.** An outside-the-repo patch is
  first choice. Where the edit is unavoidable, the safest shape is one that BREAKS
  COLLECTION rather than one that quietly passes — a swept syntax error is loud and fixed
  in minutes, whereas `if False:` is valid Python that ships a disabled guard and reds
  nothing until someone writes the test that catches it.

The gate landed in the same sweep, so the tree was self-correcting in principle; but it
was the human check, not the gate, that noticed.

### The session guards that make a profile record un-substitutable were unexercised

Found by ranking modules on how many of their UNCOVERED lines are `raise` statements —
the refinement of the earlier "parser coverage is acceptance-biased" finding, made
possible only because the coverage instrument itself was repaired two entries ago.
`_capsule_record.py` was the purest signal: 26 of 27 uncovered lines were refusals.

The count alone overstated the gap, and the selector was checked before the population
was blamed. A `test_capsule_record.py` already existed and already tested substantial
refusals — tampered provenance, a different envelope, a changed DEK epoch, a mismatched
lineage on restore. What it never reached were the SESSION-level guards:

- `encryption_key` refusing once the session is retired. `close` zeroises the DEK in
  place and leaves the object intact, so a retired authority cannot be told from a live
  one by inspection. Without the refusal the caller does not get an error — it gets
  thirty-two zero bytes and encrypts the profile record with them.
- `assert_initial_record` refusing a mid-chain record as the start of a chain, which
  would let a capsule be created already carrying history it never performed.
- `assert_replacement` refusing a successor that does not descend from the record it
  claims to replace.

The record model already refuses internally impossible shapes, so the tests cover only
what it cannot see: whether a well-formed record belongs to THIS session and THIS chain.
The sharp case is a **fork** — correct revision, a real predecessor digest, a consistent
content digest, valid in isolation and wrong only in context. Accepting it would splice a
foreign branch onto the profile's history and drop the current record silently.

Each guard was weakened separately, and each weakening failed EXACTLY ONE test. Dropping
the predecessor-digest half while keeping the revision check failed only the fork test and
left the skipped-revision test green, which is the proof that the fork test pins the digest
comparison rather than riding on its neighbour.

Remaining on this axis, unactioned: `custody/_filesystem.py` (90 uncovered refusal lines),
`_acceleration_receipt.py` (40) and `_capsule.py` (30). The same caveat applies — the raw
count is a lead, not a verdict, and the existing tests must be read before concluding the
refusals are unreached.

### The swept-probe hazard is now structural rather than a resolution to be careful

The previous entry recorded, as prose, two rules for surviving a sweep that lands
mid-probe. Prose is what the campaign already had; the incident happened anyway. This
entry replaces the second half of it with a gate.

**Measured first, and the measurement decided the design.** Ruff accepts both
`if False:` and `if True:` under this project's own configuration — verified by running
it against a file carrying them, not by reading rules. The weakened module also imports,
type-checks, and passes every test that does not specifically exercise the disabled
branch. That is precisely what makes the shape dangerous: a swept SYNTAX error is loud
and fixed in minutes, while a swept constant condition is valid Python that reds nothing.

An AST scan of the whole package found **zero** `if <constant>:` — production and test
alike — and 34 `while True:` loops, which are the idiomatic infinite loops throughout the
substrate's retry and poll paths. So the gate is hard-cut with **no allowlist**: there is
nothing to exempt, the worklist is recomputed on every run, and `while True:` is
deliberately excluded while a FALSY `while` is refused alongside the `if`.

**The anti-tautology proof needed no edit window, which is the point.** This gate exists
because proving a gate bites can require weakening a tracked file; proving THIS one that
way would have re-opened the exact hazard. Instead the detector is driven over sample
sources carrying the shape, so its emptiness is shown to be the tree's property rather
than the scanner's.

A synthetic probe alone was not accepted as sufficient — a detector can be correct on a
hand-written sample and never meet the shape in the wild. Two further proofs were taken:

- The detector was run over the **actual content of the commit that shipped the disabled
  guard**, recovered from git rather than by re-editing anything, and reported the
  neutered condition at its real line; the restored content reports clean, and the
  incident file is confirmed inside the scanned set. This proof is deliberately NOT
  committed as a test: a commit SHA in source is process history, which the source-hygiene
  rule forbids.
- The committed gate instead asserts that the scan meets real `while True:` loops in this
  package and excludes them, so the green result means the detector looked and decided,
  not that it never encountered the shape.

**Scope, stated honestly.** This catches one shape: a branch a literal already decided. It
does not catch a guard weakened by deleting a clause, inverting a comparison, or returning
early — those are undecidable in general. It is worth having anyway because it is the
shape a probe actually takes, it costs one AST walk, and it converts the recurring
worktree hazard from a discipline every agent must remember into a failure the suite
reports.

### The uncovered-refusal selector double-counts the other platform's branches

The selector introduced two entries ago — rank modules by how many of their UNCOVERED
lines are `raise` statements — put `custody/_filesystem.py` at the top with 90. Acting on
that number directly would have been wrong.

Classifying the same 90 by platform reachability:

- **27 are `_posix_*` / `renameat2` branches**, unreachable on this platform. They are not
  a testing gap at all; they are the other operating system's implementation, and no test
  runnable here can ever execute them.
- 31 are Windows branches, live here.
- 32 are platform-neutral.

So the headline overstated the addressable gap by roughly a third, and would have kept
overstating it for every dual-implementation module in the substrate. **A refusal count
over a cross-platform module measures both platforms and can only ever be executed on
one.** Split by reachability before ranking, or the largest modules will be the ones with
the most unreachable code rather than the most untested code.

This is the third time this campaign that a selector needed checking before its
population was blamed — after the name-keyed sweeps and the raw refusal count on a module
that already had a test file. The pattern is stable enough to state as a rule: **a
selector's output is a hypothesis about where to look, never a measurement of what is
wrong.**

### The local-record contract an interrupted login recovers through

The platform-neutral remainder was worth acting on. The login handover journal is one
bounded local custody record, and `_login_session.py` funnels every failure against it
into a fail-closed refusal — so what these primitives accept and refuse IS the recovery
contract. Three properties were unexercised, and each is one a caller cannot verify for
itself:

- **Write-once refuses a second publisher.** Two processes must not both believe they
  published the witness.
- **A lost compare-and-swap preserves the other party's bytes.** Refusing is not
  sufficient: the record on disk belongs to whoever won the race, and a refusal that had
  already truncated it would leave the winner's witness unrecoverable. The function's
  docstring promises this restoration; nothing asserted it.
- **The idempotent CAS accepts only the current or the exact predecessor.** A crash retry
  must converge — re-submitting the same receipt is a successful no-op, and the exact
  predecessor completes the transition — while any other leaf is refused rather than
  overwritten.

Each was proven load-bearing separately, and the discrimination was precise: removing the
write-once refusal failed only the second-publisher test; making compare-and-replace
ignore its expectation failed only the PRESERVATION test and left the ordinary-advance
test green; degrading the idempotent CAS into a blind write failed only the foreign-leaf
refusal while both convergence tests stayed green, which shows those two do not
over-constrain and the refusal test carries the safety property alone.

Following the rule recorded after the swept-probe incident, each break was restored and
then verified against HEAD rather than trusted, and the working tree was confirmed
identical to the committed file before moving on.

**Observed, not actioned:** `_filesystem.py` carries its own Windows contention retry
(`_LOCAL_RECORD_REPLACE_ATTEMPTS = 8`, 10 ms apart) for the same replace-refused-by-a-reader
problem centralised in `core/_windows_contention.py`. It retries on ANY `PermissionError`
without consulting `winerror`, so it also waits out a genuine ACL denial for eighty
milliseconds before reporting it. That is a mild inefficiency rather than a safety hole,
but it is a third home for one concept and the natural consumer of the shared predicate.
Not changed here because it is a live custody write path and deserves its own iteration.

### The handover-journal write budget was sized by nothing, and it exhausted

Opened as the consolidation item deferred by the previous entry: `_filesystem.py` keeps
its own Windows contention retry, a third home for the concept centralised in
`core/_windows_contention.py`. **That consolidation was measured and then rejected**, and
the measurement is the useful part.

The refusals this retry absorbs all arrive as `winerror 5` — and a genuinely denying ACL
on the same call arrives as `winerror 5` too, confirmed by holding a handle open and by
the module's own prior reasoning. So the shared predicate CANNOT discriminate on this
path: importing it would add a dependency without adding a decision. The codes remain
centralised for the callers that can use them; this caller's discriminator is the budget,
exactly as the shared module's docstring already says. A consolidation that makes two
call sites look alike while one of them cannot use the shared judgement is worse than the
duplication it removes.

Investigating that near-worthless item is what surfaced a real one.

**The budget could not survive the contention it exists for.** It was eight attempts ten
milliseconds apart — eighty milliseconds total, an attempt count with no stated
justification. Measured against concurrent readers of the same record:

| readers | writes ok | exhausted | worst write |
|---|---|---|---|
| 1 | 1056 | 0 | 207 ms |
| 3 | 397 | 0 | 398 ms |
| 8 | 119 | **14** | 852 ms |

Roughly one write in ten failed at eight readers, and none failed at three — which is why
the shortfall was invisible to every test that did not apply real pressure. The
consequence is not a slow login: `_login_session.py` funnels this failure into
`_refuse_handover_journal`, so an exhausted budget REFUSES the login.

Restated as a deadline rather than an attempt count, because what has to be outlasted is
a span of contention, and an attempt count silently shortens the wait whenever the poll
interval is tuned. Sized by what losing costs — the principle already recorded when the
pointer budgets were set, applied here to the consumer whose loss is most expensive and
whose budget was smallest. After: zero exhaustions at eight readers. At sixteen, two
remain; nothing bounded survives unbounded pressure, and that is stated rather than
tuned away.

**The gate is deterministic rather than a stress test.** A test that races N readers and
asserts nothing failed would flake on a loaded machine and prove nothing on a fast one.
Instead a real handle is held for an interval longer than the retired budget and well
inside the current one, then released on a timer: the write succeeds if and only if the
budget outlasts the hold. Both directions are pinned, because a budget fails two ways —
too short refuses a login that only needed to wait, and unbounded hangs forever on a
denial that never clears. The second test holds the handle permanently and requires the
write to give up and report.

Proven by restoring the eighty-millisecond value: the outlast test fails with the exact
production error, while the bounded test stays green because it should refuse under
either budget.

### Budget sweep: four surfaces probed, none defective

The previous entry found a retry budget sized by nothing that exhausted under real
contention, so this iteration asked the obvious follow-up — which OTHER budgets in this
surface are arbitrary — and enumerated them. **The answer is none.** Recorded with the
measurements so the next reader inherits the verdict rather than re-deriving it.

**Login throttle, probed for a fail-open and found sound.** `record_login_failure`
swallows `LockAcquisitionError` and does not count the failure when it cannot take the
lock, which reads as an opening: an attacker generating contention would get uncounted
guesses, and the module's own docstring notes that overlapping attempts collide on
Windows. Measured against the real function rather than argued:

| parallel wrong passwords | counted |
|---|---|
| 2 / 5 / 10 / 20 threads | 2 / 5 / 10 / 20 |
| 4 / 8 spawned processes | 4 / 8 |

Every attempt is counted at both shapes. The swallow is reachable only by holding the
lock long enough to exhaust its timeout, and an attacker holding the lock is an attacker
not attempting logins — while the backoff caps at 60 s regardless. The tolerance is
sound, and so is the deliberate fail-soft on an unreadable sidecar, which is
NIST SP 800-63B §5.2.2 reasoning stated plainly in the module: a local-CLI self-DoS is
worse than throttled retry.

**Its concurrency gate was checked for shape, and the shape is fine.** The existing test
drives threads rather than processes, which would be a real weakness if the file lock had
an in-process shortcut — a thread test would then pass while cross-process counting
broke. `core/locks.py` contains no threading component at all, so threads contend on the
same file lock processes do. A cross-process duplicate was considered and NOT added: it
would gate an already-gated property in a shape that cannot fail independently.

**The non-blocking reconcile lock is deliberate.** `_RECONCILE_LOCK_TIMEOUT_S = 0.0` in
`_bundle_export.py` reads as a missing budget and is the opposite: a lock a live export
already holds means an in-flight publication rather than a crash orphan, so reconcile
skips that target instead of waiting for it. Documented at the constant.

**The custody lock acquisition is the shape the previous fix moved TO.** Both the POSIX
and Windows lock loops are deadline-based with the budget supplied by the caller, gated
on the right error codes (`EACCES`/`EAGAIN`; Windows sharing and lock violation 32/33 —
correctly a different set from the replace-path `{5, 32}`, because it is a different
operation). The bare `0.025` in each is a poll interval, not a budget.

**Why this entry exists.** A campaign this long accumulates surfaces that LOOK defective
on inspection — a swallowed lock error, a zero timeout, a bare sleep literal — and each
costs a full investigation to clear. Three of the four here are deliberate designs whose
reasoning is already written down at the site; the fourth was measured. Recording the
verdicts and the numbers converts that cost into a one-time expense. No change was made
and none was warranted; both lanes are green at HEAD (309 integration, 1552 unit) with
nothing of this iteration's in the tree.

### The substrate-smoke anomaly is a duplicate module execution, and my earlier refutation was wrong

Carried open for several entries: two lock tests fail under `--cov` while green in both
shipping lanes, with an expected `LockAcquisitionError` escaping a `pytest.raises` that
names it. The hypothesis was two class objects of the same name. **This entry both
confirms that hypothesis and corrects an earlier entry that declared it refuted.**

**The refutation was a measurement error, not a wrong hypothesis.** Identity was probed
at `pytest_sessionfinish` and again at the START of the failing test, and both reported
one class (`same=True`) across seven workers. That was recorded as definitive. It was not:
the divergence appears between the test starting and the exception being raised, so both
probes sampled moments where the answer was legitimately "identical" and neither could
see the failure. **A negative result is only as strong as the moment it was taken, and
"measured three ways" means nothing when all three sample the wrong instant.**

Interrogating the ESCAPING exception directly settles it:

    escaped cls_id=1780502285968  __module__=cadrumo.core.locks_errors
    sys.modules["cadrumo.core.locks_errors"].LockAcquisitionError -> 1780496314448
    isinstance(exc, facade_class) -> False

One entry in `sys.modules`, two class objects: the module was **executed twice**. The
test module imports `exclusive_file_lock` at module level and so holds the FIRST
execution's function, whose global raises the first class; the test then resolves
`from .. import LockAcquisitionError` inside the function body, reaching the facade and
the SECOND execution's class. `pytest.raises` compares them, finds no relationship, and
correctly declines to suppress. Every layer behaves exactly as written.

Ruled out along the way, each by measurement rather than argument: the multi-item `with`
idiom (rewriting it as explicit nesting changed nothing), `pytest_playwright`'s
`hard_failure` wrapper (pass-through only), a second `locks_errors` under a different
module name (there is none), and in-process `sys.modules` manipulation by the collected
packages (none exists). The absence of a `pytest.raises` frame in the traceback also
proves nothing and briefly misled the analysis -- an `__exit__` that returns `False` adds
no frame.

**Production is unaffected**, and that is the part worth stating plainly: nothing
re-imports a module at runtime, both lanes are green, and the earlier concern that a
production `except LockAcquisitionError` could miss a real error does not follow from
this mechanism. The hazard is confined to the test harness -- but there it is general
rather than specific to these two tests: ANY test holding a module-level import of a
cadrumo symbol while comparing against a later-resolved one can misfire, and the failure
mode is not always loud. A test whose `except` clause silently fails to match would pass
vacuously rather than fail.

**Open, and now precisely bounded:** what causes the double execution. A circular import
re-entered while a module is still initialising produces exactly this shape -- early
importers keep the first copy while `sys.modules` ends up holding the second -- and this
campaign already fixed one such cycle in `core/logging.py`, where the trigger was likewise
only visible under a particular import order. `--cov` changes import timing, which is
consistent with a latent cycle surfacing only there. The next step is narrowing WHEN the
re-execution happens by sampling the class id at `pytest_configure` and again at test
time; that was not run here.

**Flake, third data point.** `test_modelo_catalogue_defaults_isolate_bucket_writes` failed
once more in a unit lane and passed on the immediate re-run (1552 passed), alongside a
one-off `test_preflight_accepts_legal_entity_legal_name_for_export_headers` that also
cleared. Both consistent with the worktree's known concurrent-I/O flakiness on its backing
share.

### Retraction: the "four executions per worker" figure was my instrument, not the tree

The previous entry closed by naming the next step — find WHEN the duplicate class is
created. That step was taken, produced a confident-looking answer, and the answer was
wrong. Recording it because the failure mode is more useful than the result.

**What was measured.** A `sys.meta_path` finder wrapping the target module's loader
reported that `cadrumo.core.locks_errors` and `cadrumo.core.locks` each executed FOUR
times per pytest worker, every execution completing without raising. That neatly
explained duplicate classes and even suggested a mechanism.

**Why it was wrong.** Logging `sys.modules` state at each execution showed
`target_in_sysmodules=True` on every one, with 86+ cadrumo modules already loaded. The
module was already imported each time the wrapped loader ran it again. The finder calls
`importlib.util.find_spec()` to obtain the real spec, and that call imports the parent
package and lets the target complete an ordinary import; the wrapped loader then executes
it a second time and overwrites it. **The probe manufactured the duplication it
reported.**

**The lesson, and it is the second measurement error in two entries.** The previous one
sampled identity at moments where the answer was legitimately "identical". This one used
an instrument that MUTATES the system it measures: a `meta_path` finder is not an
observer, it is a participant in the mechanism under investigation. The campaign already
carries the rule "confirm the instrument observed something"; the missing half is
**confirm the instrument did not CAUSE what it observed** — and the check that caught it
was cheap, one line of state logged beside the event.

**What survives, and why it is trustworthy.** The duplicate class itself is real and was
established with pure-observation plugins that install no import hooks and only inspect
objects already present: interrogating the escaping exception gives `isinstance=False`
against the facade's class, two distinct ids, and exactly one `locks_errors` entry in
`sys.modules`. Those measurements are independent of the retracted one.

**What is now unknown again:** the cause of that duplication. The failed-import theory was
disproved (no execution raised, though that evidence came from the contaminated probe and
should not be leaned on), and the four-execution theory is withdrawn. A future attempt
should prefer an observer that cannot participate — for example sampling
`id(sys.modules["cadrumo.core.locks_errors"].LockAcquisitionError)` at many hook points
and looking for the value to CHANGE, which requires no import machinery at all.

**Unchanged and worth repeating:** production is not affected. A plain interpreter import
of the storage facade produces one execution and one class, both shipping lanes are green
(309 integration, 1552 unit), and the anomaly is confined to `--cov` runs spanning both
packages. Two iterations have now been spent on it; it is a test-harness curiosity with no
operator-visible consequence, and it should not be picked up again ahead of work that
changes what the product does.

### The guard that decides which directory a profile deletion may destroy

Reached by the coverage-refusal selector, with both reachability caveats applied before
acting — and a THIRD one discovered in the process.

**`_acceleration_receipt.py` was dropped, not deferred.** It ranked second with 40
platform-neutral uncovered refusals, but reading the functions shows the cluster
(`_keyring`, `_store_acceleration_secret`, `_delete_acceleration_secret`) is entirely
OS-keychain-dependent, and this environment's credential store fails with error 1312 by
standing context. Those refusals are unreachable here for the same reason POSIX branches
are: not untested, untestable. So the selector needs a third axis beside platform —
**environment-gated by an excluded marker** (`os_keychain`). Both inflate a raw refusal
count, and both are invisible until the functions are read.

**`_capsule.py`'s deletion protocol was the real gap.** Five functions implement it —
mark, rename to tombstone, verify tombstone, verify marker, remove tombstone — all live,
all consumed by `_custody_service.py`'s delete flow, and **three of the five had no test
naming them anywhere in the tree**. Checked before concluding: `test_capsule.py` is
substantial but covers publication, discovery and retirement, never deletion.

The consequence is unusually direct. `verify_profile_custody_deletion_tombstone` returns
"the exact transaction-owned tombstone proven safe to remove", and its caller removes what
it returns. Its refusals are the only thing between a profile deletion and destroying
something it does not own: a live capsule, another transaction's tombstone, or data that
arrived after the operator consented. Most guards in this campaign protect a value; this
one authorises an `rm -rf` of a directory.

Covered: the transaction binding (a foreign transaction owns no tombstone and must not be
handed this one), the post-preflight inventory change (new data must not be destroyed by
an old approval), an absent tombstone treated as ambiguous rather than as an idempotent
success, and the marker's exclusivity (two transactions must not each believe they own the
same capsule's destruction). Paired with the acceptance each must not break, because a
verifier that refused everything would satisfy every refusal while stranding every real
deletion.

Proven by removing the inventory comparison and the marker-exclusivity check separately;
each failed exactly one test. Restored and verified byte-identical to HEAD afterwards, per
the rule from the swept-probe incident.

**A note on the remaining lead.** The refusal counts for `_acceleration_receipt.py` should
now be read as environment-blocked rather than open work. What is left on this axis after
this entry is thin, and the campaign is close to the point where the coverage-refusal
selector stops paying.

### The deletion protocol is now covered end to end, and the linked tombstone is defended twice

Completes the previous entry, which covered two of the protocol's five functions. The
remaining three — the pre-rename marker checkpoint, the tombstone removal, and the
tombstone path derivation — are now exercised.

**A test that passed for the wrong reason, caught by probing it.** The linked-tombstone
test was written and documented as pinning the directory anchor's reparse-point refusal.
Removing that refusal left all twelve tests GREEN. The test was real, but its stated
mechanism was wrong, and had the probe not been run the docstring would have taught the
next reader something false about which guard protects that path.

What actually happens is better than what was claimed: the removal is defended **twice
over**. With the anchor's check removed, a second independent refusal fires from the
staging snapshot ("unpublished profile capsule staging contains a reparse point"), and the
link target survives either way. The test now asserts the OUTCOME — refusal plus target
survival — and says explicitly that it does not pin either mechanism, because naming one
would restate the error just corrected.

The general form is worth keeping: **a passing test proves the outcome, never the reason
for it.** The docstring is a claim about mechanism, and only a probe against that specific
mechanism substantiates it. This campaign has now produced two variants of the same
mistake — a measurement taken at the wrong moment, and an instrument that caused what it
measured — and this is the third: an explanation attached to a result that does not
depend on it.

**What the protocol now guarantees, each proven load-bearing where a single guard owns
it:** the marker binds one deletion exclusively and to one transaction; a capsule or
tombstone that changed after preflight is refused rather than swept into the deletion; an
absent tombstone is ambiguous at verification but idempotent at removal, which is the
correct asymmetry for a rollback that may run twice; and a tombstone that is not a real
directory never has its tree walked.

### Dead export, recorded rather than removed

`default_policy_table` is defined in `core/classification`, re-exported through the
storage facade, and called by nothing anywhere in `src/` or `dev/` — its only occurrences
are the three facade plumbing lines. Left in place: the definition belongs to another
package, and removing one name from a facade is not worth an isolated change while the
standing directive excludes facade narrowing as a mechanical edit. Recorded so it can ride
along with whoever next touches that surface.

Measured alongside it, and NOT actioned for the same reason: 51 of custody's 145 exports
and 53 of storage's 261 have no consumer outside their own package. That is over-exposure
rather than dead code — the implementations are all used internally — and it is the same
shape as the deferred `user_profile` over-export item.

### The deletion guards were unwired-proof, but the wiring itself had nothing watching it

The previous entry covered the deletion protocol's five adapter functions. That work
proves what each guard does WHEN CALLED. It says nothing about whether the live path calls
them, and the distinction turned out to be the whole remaining risk.

`_remove_delete_capsule` in `_custody_service.py` calls
`verify_profile_custody_deletion_tombstone` immediately before
`remove_profile_custody_deletion_tombstone`. The verification is unconditional and
adjacent — the wiring is correct today. What was missing is anything that keeps it that
way.

**Measured, not assumed:** removing that single verify call from the live delete step
leaves ALL TWELVE adapter tests green. They exercise the verifier and the remover in
isolation, so nothing in them can observe that the product stopped calling one before the
other. A refactor dropping that line would ship a tree deletion nobody checked, against a
fully green suite.

The invariant is lexical — the verification appears earlier in the same function body — so
it is asserted against the source rather than by observing a run, which would have to
reach the destructive step before it could report anything.

**Both halves of the proof were taken, because the campaign has already been burned by
each.** The detector was driven over synthetic source carrying the shape (it flags an
unguarded removal and accepts a verified one), AND the gate was run against the real
service with the verify call actually deleted, where it fails naming
`_custody_service.py:780`. The synthetic half alone proves only that the detector works;
the earlier lesson was that a detector correct on a sample can still never reach the real
site. The gate also asserts that the call site it found is in `_custody_service.py`, so an
empty scan cannot pass as a clean one.

**Scope, stated deliberately.** This pins one pairing rather than a general "every
destructive call needs a matching verification" rule. The general form needs its own
inventory of what counts as destructive and what counts as verifying it, and a rule that
cannot enumerate its own subjects is the kind that passes vacuously. One protocol, one
ordering, one gate.

### Destructive-ordering sweep: one gap found last entry, none remaining

Extending the verify-before-remove finding, the domain's destructive operations were
hand-enumerated rather than discovered by heuristic, and the risk class was narrowed
first: **a guard INSIDE the destructive function cannot be unwired.** Only a guard in a
separate call, ordered by the caller, can be dropped silently. That reduces the inventory
sharply.

Checked, and each is sound:

- **Tombstone removal** — separate verification, gated by the previous entry.
- **Pointer compare-and-swap clear** — the comparison sits in the same function as the
  clear, under the root lock, and an existing test asserts a stale expectation raises AND
  leaves the pointer untouched. Watched.
- **Live DEK revocation** — the identity check is inside the function and re-checked after
  zeroisation, so caller ordering cannot lose it.
- **The unguarded `clear_profile_custody_local_record` call sites** — internal staging and
  backup paths where the caller owns the file, plus the pointer CAS above. The
  compare-and-clear variant is used where a witness belongs to another party.
- **Output-language hint clear** — a non-authoritative sidecar, fail-soft by design.

### Concurrent registration cannot duplicate a label, and the test says only what it proved

A profile label is what an operator types to select a profile, so two capsules answering
to one name makes every later selection ambiguous. Every existing duplicate-label test
registers profiles one after another; the concurrent case the refusal exists for was
unasserted.

**Two hypotheses were formed and both were wrong, which is the useful part.**

First: the duplicate scan is named `_refuse_duplicate_label_under_root_lock` but takes no
lock itself, and the service only ever calls `profile_custody_transaction_lock(root,
profile_id)` — a per-profile lock by signature, which would not serialise two DIFFERENT
profiles claiming one label. Reading the implementation refuted it: that helper acquires
the custody ROOT lock first and holds it across the whole transaction. The name is
accurate; the signature was misleading.

Second, and caught before the test was committed: the test was written and documented as
pinning that root lock. **Removing the root lock from the transaction lock does not make
it fail** — three runs, all still one winner. The losing process is refused a layer higher,
by the registration path reporting `profile_already_exists`. So the docstring was
corrected to claim only what the test holds: the operator-visible outcome, one capsule per
label, however the second attempt is turned away.

This is the second consecutive entry where a mechanism claim in a docstring did not
survive being probed. The habit that catches it is cheap and now routine: after a
concurrency or ordering test goes green, break the mechanism it names and confirm the test
notices. If it does not, the docstring is the thing to fix, not the test.

Stability was measured before committing rather than assumed: six consecutive races each
produced exactly one registration, so a failure here indicates a genuine duplicate rather
than a timing artefact.

### A lost custody race was reported to the operator as a name already taken

The previous entry ended with a correction that was itself wrong, and chasing that is
what found a real defect.

**Correcting the correction.** That entry recorded, from the concurrent-registration race,
that the losing process was "turned away one layer higher, by the registration path
reporting `profile_already_exists`". Only the top-level exception type had been captured.
Reading the `__cause__` chain shows
`ProfileRegistrationError <- ProfileCustodyDuplicateLabelError`: the refusal originates in
the custody duplicate-label scan exactly as first supposed, and the registration boundary
merely translates it. **A top-level exception type is not the refusal; it is the last
wrapper around it.** The prior test's docstring has been corrected in the same change.

**The defect that translation hides.** `ProfileCustodyDuplicateLabelError` is a SUBCLASS of
`ProfileCustodyTransactionConflictError` — a deliberate earlier decision so existing
handlers keep catching both. Their answers are opposites:

| error | code | retryable |
|---|---|---|
| `ProfileCustodyTransactionConflictError` (stale witness) | `..._TRANSACTION_CONFLICT` | **true** |
| `ProfileCustodyDuplicateLabelError` (label taken) | `..._DUPLICATE_LABEL` | false |
| what registration published for BOTH | `REFUSED_PROFILE_REGISTRATION` | **false** |

The registration boundary caught only the parent, so a transient conflict — one the
identical call can win once the witness is re-read — reached the operator as a permanent
"profile already exists". This CLI's stated operator is an autonomous agent: told the name
it just chose is taken, it does not retry, and instead picks a different name for a profile
that does not exist.

This is the mirror image of the defect this campaign already fixed one layer down, where a
permanent refusal had inherited a retryable answer from a sibling. The same rule applies in
both directions, and the same remedy fits: a SUBCLASS, so every existing
`except ProfileRegistrationError` handler — including the TUI front end, which catches it
by name — keeps working, while only the published code and its retryability differ. No new
locale key was needed; the existing custody-conflict message key was reused.

**Proven in both directions, and the swap is the sharper half.** Ordering the parent ahead
of its subclass fails the ordering test AND, end to end, makes a genuinely taken label
report as `ProfileRegistrationConflictError` — retryable — which would loop an agent forever
on a name it can never have. Reverting to the single broad catch leaves a real duplicate
refusing identically, which is the anti-regression check that the permanent path was not
disturbed.

**An earlier gate did its job unprompted.** Registering the new retryable code immediately
reddened `test_custody_retryable_codes_are_declared`, which refuses any owned retryable code
that does not state what resolves on its own. The declaration was written rather than the
gate widened.

### The flattened-retryability defect is one site, now gated; the rest is another surface's

The previous entry fixed a boundary that applied one `retryable` answer to two opposite
situations. That is an enumerable shape, so it was swept rather than left as an anecdote.

**The sweep pairs the live registry with the source.** Every registered error class is
resolved, real subclass relationships are computed, and a pair is divergent when parent and
child publish opposite `retryable` answers. **28 such pairs exist across the tree** — the
shape is common and mostly deliberate, since the subclassing is what keeps established
handlers working. Handlers are then read from the AST, and one is reported when it catches
a divergent parent and re-raises a DIFFERENT type without routing the subclass first.

**In scope, the answer is one site — the one already fixed.** The sweep initially reported
a second, `_custody_repository.save_journal`, and it is a FALSE POSITIVE: that handler
re-raises the SAME type it caught, narrowing a message rather than changing an answer, and
its `try` body is a bounded file read that cannot raise the subclass at all. Requiring a
genuine translation — a raised type other than the caught one — removes it by construction,
so the gate ships with **no allowlist** rather than with an exemption and a reason. That is
the better outcome: an allowlist is where judgement drifts, and here none is needed.

**Out of scope, and deliberately left there.** Roughly thirty sites under
`entrypoints/cli/_config` flatten `GoogleAuthError` over five retryable ADC subclasses, and
`OutboundStorageError` over two. Whether those codes should be retryable AT ALL is an open
question for whoever owns that surface — `test_custody_retryable_codes_are_declared` drew
the same boundary when it scoped itself. Gating them here would be this campaign answering
a question it does not own, so the inventory is recorded and handed over rather than acted
on. The precise sites are reproducible by running the gate with
`_SCOPED_PACKAGES` widened to include `entrypoints/cli`.

**Proven against the real site, not only a sample.** The detector was driven over synthetic
source in both directions, AND the fix was temporarily reverted in `_registration.py`,
where the gate fails naming line 309. The synthetic half alone would prove only that the
detector works — the campaign's earlier lesson is that a detector correct on a sample can
still never reach the real code. Two anti-vacuity assertions guard the rest: the divergent
map must be non-empty and must contain the known custody pair, and the module scan must
reach more than fifty files, because an empty map or an empty file list clears every
handler for free.

### A gate outside the domain lanes caught a defect this campaign introduced

Found by following a stale path, which is the useful part: the always-on architecture rule
states the import boundary is "Enforced by `dev/import_hygiene_scan.py` and
`src/cadrumo/tests/test_import_hygiene_gate.py`". **Neither path exists.** The scanner is
at `dev/quality/import_hygiene_scan.py` and the gate at `dev/tests/test_import_hygiene_gate.py`.
An agent checking whether the boundary is enforced finds nothing at the cited locations and
can reasonably conclude it is not — which is nearly what happened here. Corrected on the
rule source and propagated with `vaultspec-core sync`, with the note that the gate sits
outside the `src/` lanes and must be run explicitly.

**Running it found a reach this campaign added.**
`test_capsule_record_lineage_authority.py` imported `ProfileSetupState` from
`domain.user_profile._values` — a cross-package PRIVATE module, which the architecture rule
forbids outright. The symbol is already on the package facade, so the reach bought nothing;
it was copied from a neighbouring test that carries the same debt, and it was never
declared in `import_hygiene_test_debt.json`, so it was undeclared debt rather than accepted
debt. Repointed to the facade.

**The lesson is about lane coverage, not about that import.** Every iteration of this
campaign has run two domain lanes over `src/`, and those lanes cannot see a gate that lives
in `dev/tests/`. A defect introduced in `src/` and enforced from `dev/` is invisible to the
loop that produced it. **A green lane is evidence about the lane's scope, not about the
tree**, and the gates that matter most — the tree-wide architectural ones — are exactly the
ones most likely to sit outside a domain-scoped lane. Worth running `dev/tests/` after any
iteration that adds files under `src/`.

**State of that gate, recorded honestly:** it is currently RED at 6 failed / 37 passed, and
the remaining failures name the TUI boundary census, family2 delegate shims, and test-debt
entries for other packages. None name this campaign's files after the fix above, and none
were introduced by it; they belong to whoever owns those surfaces.

### Dead cross-package bridges in the storage facade, measured and handed over

Of the 25 names the storage facade re-exports from OTHER packages, **14 have no consumer
reaching them through storage** — every reference lives in the owning package: the corpus
manifest family, three classification types, `default_rules_for`, `DEFAULT_LOCK_TIMEOUT`
and `default_policy_table`. They are a second, unused import path for symbols storage does
not own.

Not acted on, deliberately. Removing fourteen facade entries is facade narrowing, which the
standing directive excludes as a mechanical edit, and it is the same shape as the deferred
`user_profile` over-export item. Checked and NOT a rule violation on a second axis: the
lazy-map targets name public subpackages (`core.classification`, `core.corpus_manifest`)
whose `__init__` defines those symbols, so they are the owning facade, not private modules.
Recorded with the measurement so whoever narrows facades can act without re-deriving it.

Also verified covered this iteration and needing nothing: the six-phase login handover
machine (every phase appears in tests) and the crash-recovery paths around it.

### Running the tree-wide gates found a second self-inflicted reach, and bounded the rest

Acting on the previous entry's lesson — a green domain lane is evidence about the lane's
scope, not the tree — the whole `src/cadrumo/tests/` gate suite was run for the first time
this campaign: **61 failed, 734 passed.**

**One failure was this campaign's, and it is fixed.**
`test_no_absolute_self_imports_in_cadrumo_package` reported four offenders, two of them the
concurrent-registration test's spawned-child target, which imported `cadrumo.*` absolutely
inside the worker function. The absolute form was reflexive rather than reasoned: spawn
re-imports the module normally, so the relative form resolves in the child, and the test
still passes as a real two-process race. That is now two out-of-lane violations this
campaign introduced and did not see — the first an undeclared private import, this one an
absolute self-import. Both were invisible for the same reason, and both were found only by
running gates the loop never ran.

**The rest is other work's, and the attribution was measured rather than assumed.** Every
remaining failure was checked against this campaign's files by name; none match. The
largest cluster deserves recording because it looks like domain debt and is not:

`test_any_param_rationale_inventory` reports 30 parameter-level `Any` sites without a
rationale, **12 of them in storage or custody**. The first hypothesis was that this
campaign caused it — editing `_filesystem.py` for the budget fix added roughly twenty lines
and a line-keyed exemption list would have gone stale, which is exactly the anti-pattern
this project's own quality rule names. **That hypothesis was wrong and checking it mattered:**
the ratchet is EMPTY. It was deliberately emptied and its matcher WIDENED in
`4cbe88be7f`, and the widening is what surfaced sites that already existed. The gate is red
tree-wide as a consequence of that change, and closing it belongs to whoever made it.

**Not half-fixed, deliberately.** The twelve in-domain sites are not one kind of problem.
`kernel32: Any` in the Windows job wrapper is a genuine third-party ctypes boundary that
the architecture rule says to DOCUMENT inline. `adapters: Any | None` on
`ProfileCustodyService` is a design escape that wants a Protocol over roughly thirty adapter
attributes — real design work with live blast radius. Adding a rationale marker to the
second kind would be using the marker as a mute button on exactly the judgement the gate
exists to force, so nothing was marked. The classification is recorded here so the work can
start from it.

**Standing recommendation, now with two data points behind it:** run
`src/cadrumo/tests/` and `dev/tests/` after any iteration that adds or moves files under
`src/`. The domain lanes cannot see either, and both have now caught something this
campaign introduced.

### Two candidates examined, both declined on their merits; no defect this iteration

**The `adapters: Any` seam: a Protocol is feasible and still the wrong trade here.** Last
entry classified it as a design escape wanting a Protocol rather than a rationale marker.
Feasibility was checked first — `ty` does accept a module where a Protocol is expected, so
the obvious blocker is not one — and the Protocol was then generated from
`inspect.signature` rather than transcribed: sixteen methods referencing twelve domain
types, roughly sixty lines.

Declined, for reasons that only surfaced by generating it:

- The class is `_ProfileCustodyTransactionCapability`, PRIVATE and internal, whose
  docstring states no application caller may use it directly. It is not a public boundary.
- The failure it would catch — an adapter renamed out from under an unchecked attribute
  access — is already caught: the integration lane drives the whole delete path through
  this service.
- The generated Protocol necessarily includes `_trace`, a private observability parameter,
  so the type contract would cement a seam that exists for one security proof.
- Eighteen of the thirty unrationalised sites are outside this domain, so fixing one does
  not change the gate's colour; it belongs with whoever widened the matcher.

Recorded rather than done, and deliberately NOT papered over with a rationale marker
either, which remains the wrong answer for a design escape. The generated signatures are
reproducible in one command if the work is picked up.

**The `_trace` parameter is live, and the investigation of it is worth recording for the
mistake it nearly caused.** It is the only underscore-prefixed parameter on any public
production function in the domain — exactly the shape of a test hook left in a shipped
signature. A first pass concluded nothing supplies it.

That conclusion was wrong, and the reason is instructive: the search printed an
unconditional "(none above = never supplied)" line immediately after a `grep | head`, and
the grep's first two lines WERE the call sites. **A summary line asserted by the harness
rather than derived from the result will happily contradict the output directly above it.**
Reading the actual lines showed `_capsule.py:950` supplies it inside
`load_committed_profile_password_material`, which builds the `access_trace` a test asserts
on to prove the password path never opens the recovery envelope. A live, load-bearing
observability seam for a real security property — not dead surface.

**Prior out-of-lane fixes re-verified.** Both violations this campaign introduced and
corrected in the two preceding entries stay corrected: no campaign file appears in
`test_relative_imports_only` or in the import-hygiene gate. The residual failures in both
name other packages. Domain lanes green at 311 integration and 1573 unit, with nothing of
this iteration's in the tree, because nothing needed changing.

### The legal retention floor: a known-cost duplication, now a detected divergence

Reached by finally looking at the domain as an OPERATOR meets it rather than through its
libraries. `aeat config profile delete` turns out to be well shaped for this CLI's stated
operator: it never prompts. Without `--yes` it runs the full preflight and emits the
envelope with nothing destroyed, so a destructive verb is dry-run by default and an agent
that cannot answer a prompt is never blocked by one.

Two guards run before destruction, and the second carries a candid admission worth acting
on. `_refuse_erase_inside_the_retention_floor` enforces a LEGAL floor -- the
Administration's four-year review window (Ley 58/2003 LGT art. 66/67) and the matching
conservation duty (art. 70.2). Its docstring states the risk and then accepts it:

> A third condition added to the retention contract would reach one site and not the
> other. ... until that happens the duplication is a known cost, not an invariant.

**Measured, and the duplication is wider than the docstring's "one site and the other".**
The erase decision is expressed at five production sites in four shapes: three in
`config_reset.py`, one in `_config_reset_repository.py` (written inverted), and the delete
verb. Four admit `override_approved`; the verb deliberately does not, because it offers no
override to record.

The shapes differing is fine and the gate does not fight it. What it pins is the shared
VOCABULARY: every attribute read while deciding an erase must be a declared term. A new
term at any single site fails and lists every site, so whoever adds one has to decide, per
site, whether it belongs. That converts the docstring's known cost into a detected
divergence without forcing a consolidation this campaign does not own -- the real remedy
is still the shared function the docstring proposes, and it belongs with the config-reset
surface.

**The detector needed narrowing twice, and both narrowings are real distinctions rather
than convenience.** It first flagged constructor calls passing `blocks_erase=` as a
keyword, which name the floor and decide nothing; requiring a boolean operator excludes
them, because a keyword never sits inside one. It then flagged the assessment model's own
validator comparing `self.blocks_erase` against `self.retained_record_count` -- the floor
checking itself for internal consistency, not a surface deciding an erase. Every real
decision reads the floor from an assessment handed to it, so a marker read off `self` is
excluded. Neither exclusion was declared as an exemption; both are properties of what a
decision IS.

Proven against the real verb, not only a sample: adding a third condition to the delete
verb alone fails the gate, and the synthetic probes cover both directions. Two
anti-vacuity assertions guard the population -- at least four sites must be found, and the
delete verb must be among them -- because a renamed marker would empty the scan and clear
the tree for free.

**Applied this campaign's own standing recommendation for once, unprompted:** the new file
was checked against the out-of-lane gates before committing, not after being caught by
them.

### The recovery door's advisory: absence was proven, presence was not

Continuing the operator-facing review, `config profile restore` is well built for an
unpromptable caller: `--file` follows the CLI naming contract, `--secrets-stdin` and
`--secrets-fd` carry machine secrets, and the capsule is parsed BEFORE any secret is
requested, so a bad source never costs the operator a retyped passphrase.

Its recovery-artifact path emits a warning that the records came back and the credential
did not. That advisory is the difference between an operator who knows to rotate and one
who finds out at the next login prompt -- and nothing held it in place. The existing test
asserts the advisory is ABSENT on the password door, which passes identically whether the
advisory is correct or has been deleted outright. **Absence was proven; presence was not.**

**The gap was declared, and the declared reason was true.** The module docstring stated the
recovery door was not covered here because minting an artifact needed a replayed recovery
key with no sanctioned test-support door, and faking one from another package's private
helpers would be worse than the honest gap. That was verified rather than assumed, and the
first attempt to close it failed exactly as the docstring predicted.

**What made it closable was a detail about the secret's lifetime.** The recovery key lives
in a wipeable buffer that the creation flow zeroises once the handover callback returns:
an enrollment captured and read afterwards yields NUL bytes -- correct behaviour for a
secret, and the reason storing the object is not enough. Copying the phrase INSIDE the
handover, while the key is still live, mints the artifact through the operator's own public
door with no replay helper. The application-layer test needed its private helper only
because it keeps the phrase and rebuilds a key; capturing at the live moment sidesteps that
entirely.

Proven by diverting the advisory in the live verb while leaving the file valid: ONLY the
new test fails, and the password-door control stays green, which is the correct
discrimination. An earlier probe that deleted the block outright left an empty `else:` and
failed both tests for the wrong reason -- recorded because a probe that breaks the file
proves nothing about the assertion under test, and the difference is easy to accept when
red is the expected outcome.

The module docstring was rewritten in the same change. Leaving prose that declares a door
uncovered after covering it is the same stale-citation defect this campaign corrected in an
always-on rule two entries ago.

### A healthy storage report that never examined permissions, and a red test the lanes could not see

Swept the previous entry's shape — an operator notice whose ABSENCE is asserted and whose
presence is not — across the domain's notice codes. Of the seven custody and storage
advisories checked, **six had no test reference at all**. The sharpest is
`storage_root_mode_unenforced`.

**What it guards.** `config storage check` computes `healthy` from its issue list. On a host
that cannot enforce the storage root's mode, that list is empty because the permission axis
was never EXAMINED — the emitting comment says so exactly: "a different claim from
examined-and-clean". Run here, the envelope reads `healthy: true`, `issues: []`,
`root_mode_enforced: false`. The advisory is the only thing standing between "permissions
are fine" and "permissions were not looked at", for the root that holds this application's
financial data at rest. Nothing asserted it fired.

Gated as a biconditional against the flag rather than as a platform assertion, so the test
stays honest on a POSIX host where the axis IS enforced and the notice must stay silent.
Proven by diverting the advisory while leaving the file valid: both new tests fail, and
they pass again on restore.

**A red storage test the domain lanes structurally cannot reach.** Adding the tests
surfaced two pre-existing failures in the same file — `storage reclaim`'s durable-area
refusal — which were confirmed pre-existing by running the file at HEAD. The file lives in
`entrypoints/cli/tests`, and the lanes cover `entrypoints/cli/_config`, so this is the
out-of-lane pattern for a third time.

The cause is worth stating because the test was not wrong about the product: it asserts the
raw enum token (`state`, `exports`) appears in the refusal prose, and area names are now
TRANSLATED, so the operator sees "estado" and "exportaciones". The refusal was naming the
area correctly all along, in the operator's language. The substantive assertions — that the
reclaim refuses and the durable content survives — passed throughout; only the prose read
failed. Fixed by pinning `--output-language en` for that assertion, which is the convention
the file's own sibling text assertions already use. **A test that reads a value out of
localised prose is asserting against a translation, and must pin the language or read the
payload instead.**

Absorbed rather than deferred: it is a storage-surface test, red, in this campaign's
domain. It is not a "locale failure belonging to another campaign" — the locale work is
correct and the assertion was language-dependent.

### Sweeping the out-of-lane CLI tests: four reds, none of them defects

Having hit the out-of-lane pattern three times one failure at a time, the storage and
profile tests under `entrypoints/cli/tests` — which the domain lanes do not cover — were
swept as a population. Six custody-core modules produced **four failures**, and the
triage matters more than the fixes.

**Three were mis-CLASSIFIED, not broken.** Their subject is cross-process session
resumption, and the `os_keychain` marker's own description states the rule exactly: a case
belongs under it "when it cannot reach its subject without a minted acceleration receipt,
because `resume_profile_session` leaves the login PROCESS-SCOPED when the keychain is
unavailable and mints no receipt at all". The observed envelope said precisely that —
`registered_bucket: true`, `profile_record_present: false`, `profile_source: "none"`. One
module's docstring even records that it was authored only once the credential store had
been cleared, so its dependence was known and simply never expressed as a marker.

They carried no marker, so on any host whose store refuses they fail indistinguishably
from real defects — and cost a full re-triage every time, as they did here. Marked per
function, never per module, because that is what the marker's description requires and
those modules hold cases that do NOT need custody. Verified as classification rather than
suppression: `-m os_keychain` still selects all three, and the default lane now runs the
same files green.

**The fourth was an over-broad assertion against a contract this campaign helped pin.**
`test_cold_start_refusal_is_consistent_across_surfaces` demanded byte-identical output from
`modelo work list` and `ledger list`. The two differed in exactly one line — `command:` —
which the envelope spine REQUIRES each surface to fill with its own command. The refusal,
its failed condition, its evidence and its recovery action were identical throughout, so
the contract the test names was never violated; the comparison simply included a field that
differs by design. Narrowed to the surface-independent lines.

**The triage nearly went wrong twice, both times from an unverified instrument.** An awk
extraction meant to count keychain mentions per failure block matched nothing — pytest's
header format differs — and reported a confident "0 mentions" for all four, which would
have argued they were NOT keychain-related. Checking that the extraction captured any lines
at all showed it had captured none. The direct search then found zero occurrences of
"1312" anywhere in the log, which is true but also not evidence of absence of the class:
the marker's subject is a missing receipt, and a host that mints none produces no error
code at all. **A grep for the symptom is not a test for the cause.**

Net effect: the six-module subset now runs green at 34 passed, and the three genuinely
environment-bound cases are enrolled where `just test-os-keychain` can reach them on a
desktop session.

### Second out-of-lane batch: two reds, two different wrong assumptions, no defects

Five more storage and profile modules under `entrypoints/cli/tests`. Four failures across
two causes, and again the diagnosis was the work.

**A CLI test asserting through a door its fixture never opened.**
`test_two_profiles_keep_independent_ledgers_across_unlocks` seeds with
`register_minimal_profile` and then invokes `aeat config login`. That helper's own
docstring rules it out in as many words: the sibling `register_cli_profile` exists because
"the custody envelope has to open under the passphrase the isolated CLI backend
configures... Seeding a record writes no such envelope, which is why the two doors are not
interchangeable". The login refused for a PASSWORD, not a missing receipt, so it was never
the keychain class.

The isolation assertions -- the module's actual subject -- passed throughout. The module
docstring also states that re-entering the session span drives the same primitive
`config login` does, so the login call added no coverage and required a door the seeding
never opened. Removed, with the reason recorded at the site. **Verified this did not soften
the claim**: pointing both profiles at one bucket still fails the test.

**A control assertion in the wrong language, for the second time.**
`test_the_verb_refuses_because_the_profile_fact_is_unanswered` asserts `"Refused."` appears
in the output; the refusal renders as "Rechazado.". Its own siblings in the same module do
NOT have this problem, because they resolve their expected label through the same locale
the CLI renders in -- the control was the only assertion holding a hardcoded English token.

Moved to the envelope's `error.category == "REFUSED"`, which is what "this is a refusal"
means independently of rendering. That is a better answer than pinning a language here:
the sibling assertions read localised text on purpose, so forcing English for the module
would have fought them.

**The pattern is now three-for-three and worth stating as a rule.** Every red found in
these out-of-lane sweeps has been a test asserting something its own fixture, marker, or
locale could not deliver -- never a product defect. `entrypoints/cli/tests` holds the
domain's end-to-end surface and no lane runs it, so nothing forces these assumptions to
stay true. **A test asserting operator-visible TEXT is asserting against a translation, and
a test invoking a verb is asserting against whatever door its fixture opened.** Both are
easy to write correctly once and then have quietly invalidated by work elsewhere.

Eleven of roughly fifty domain-relevant modules in that directory have now been swept.

### Third out-of-lane batch: fixtures that cannot produce the state they assert

Five more modules; nine failures; the same class as the previous two batches, now with a
sharper root cause worth naming once.

**`register_cli_profile` completes every profile it registers.** It merges a
`_REQUIRED_PLACEHOLDERS` map before registering and fills conditional requirements too, so
a profile seeded through it carries sixteen facts including
`activities.description = "economic activity"`. Four preflight cases assert the OPPOSITE —
that readiness is blocked on a missing baseline, that `activity_present` is `False`, that
the profile is not `configured`. Their fixtures could not produce any of those states, and
the product was answering correctly throughout.

Measured rather than inferred: registering through that door and reading the record back
shows the fact present with that exact value; passing it as an empty string yields fifteen
facts with the field absent.

**The affordance already existed and had not been used.** The door drops falsy facts before
registering, so `"activities.description": ""` is how a caller declines one of its fills,
and `complete=False` is how a test whose subject is an unconfigured profile says so — the
helper's own docstring offers the second and the first falls out of its implementation. No
helper change was needed; the fixtures simply never expressed their subject. One persona
additionally asserted two income categories (`capital_inmobiliario,pension`) that its
fixture only half supplied.

Five of the six cases in that module now pass.

**The sixth is another campaign's, and is handed back rather than quietly rewritten.**
`test_profile_preflight_names_profile_only_scope_for_m100` asserts a
`full_modelo_readiness_command` line. That string exists NOWHERE in production — it was
removed by `d6ae28688d` and replaced with the structured components the output now carries
(`modelo`, `revision_id`, `filing_year`, `period`), which the test's own failure output
shows are all correct. Whether composed next-step guidance should return, or the test
should assert the components, is a decision for whoever made that change. Deleting the
assertion here would erase the only remaining record that the guidance ever existed.

**Three batches, one conclusion.** Every red in `entrypoints/cli/tests` has been a test
whose fixture, marker, or locale no longer delivers what its assertions name — never a
product defect. Sixteen of roughly fifty domain modules are now swept. The recurring cause
is that this directory holds the end-to-end operator surface and no lane runs it, so
assumptions inside it are never re-validated by the work that invalidates them.

### Correction: the package lanes DO cover that directory — and the real gap is reachability

Three consecutive entries here concluded that `entrypoints/cli/tests` is red because "no
lane runs it". **That was wrong, and it should be corrected rather than left standing.**

`just test-unit` and `just test-integration` name NO paths. They run the whole tree and
select by marker, so that directory is covered by the project's own lanes and every red
found in those sweeps was visible to anyone running them. What is narrow is the
three-path lane this campaign re-runs each iteration — a property of the working loop, not
of the project. The sweeps were still worth doing, but the reason recorded for them was
not the true one.

**Checking that correction surfaced the real structural gap.** Because the lanes select by
marker and name no path, a module carrying only architectural markers (`hex_application`
and friends) is selected by nothing. It is not skipped and not reported; it simply never
runs, and a suite that never runs it stays green forever. That is the failure mode that
would let a whole module rot exactly the way individual assertions did in the last three
entries.

Measured: of 2,926 test modules under the package, **17 carry neither `unit` nor
`integration`** — and all 17 carry `aeat_live`, which `just test-live` enrols. So the tree
is currently reachable end to end, with zero orphans. Nothing proved it, and nothing kept
it so.

`dev/` already had this gate — `dev/tests/test_lane_reachability.py`, which the Justfile
calls the sole declaration site for `dev/` lanes. The same argument applies to `src/`, and
the check is simpler there because no lane names a path, so only marker selection can
fail. The gate is hard-cut at zero orphans and lists the execution markers explicitly
rather than deriving them: the Justfile's expressions are prose to a test, so if a lane's
marker changes, this list is where the change is noticed.

The `aeat_live` population is pinned in its own assertion, so removing that marker from the
set fails loudly instead of silently narrowing what counts as reachable — the same
anti-vacuity concern as an empty scan, applied to the gate's own vocabulary. Proven on a
real module rather than only a sample: stripping `unit` from a live test file fails the
gate naming it.

### Replacing a prose assertion needs a MEASURED discriminator, not a plausible one

Fourth out-of-lane batch: four modules, one failure — the localised-prose class for the
third time. `test_calendar_refusal_reads_as_a_refusal_not_as_invalid_input` asserts
`"Refused."` and `"Invalid value" not in`, both English tokens against Spanish output.

The class was measured before being treated as systemic: only five sites in the tree assert
the English refusal word, and just this one fails. Too small for a gate, so it was fixed in
place rather than turned into machinery.

**The fix took three attempts, and the two failures are the finding.** The test's subject
is the CHANNEL — workflow state versus a bad command line — so the replacement had to
separate those two. Each candidate was checked against the live CLI:

1. `error.category == "REFUSED"` — **does not discriminate.** A Click parameter error on
   the same verb is published as `REFUSED` too. This one was written, run green, and
   would have been committed on the strength of passing.
2. `error.code != "REFUSED_CLI_BOUNDARY"` — **does not discriminate.** Both channels carry
   that identical code, which the failing assertion revealed by printing the workflow
   refusal's own envelope.
3. `action.failed_condition_id == "cli.overview.profile.complete"` — **discriminates.**
   Workflow state names the condition it could not satisfy; a parameter error carries
   `None`, confirmed by invoking one.

**The lesson generalises past this test.** Moving an assertion off prose and onto a
structured field feels like a strict improvement, and it is not automatically one: the new
field has to be shown to differ between the two situations the test distinguishes.
A structured assertion that passes proves the field's value, never that the field can tell
the cases apart. Both wrong candidates passed the test they were written for -- the first
would have shipped a test that could no longer fail for its stated reason, which is exactly
the defect this campaign has been finding in other people's work.

Nothing here was a product defect. The gate landed two entries ago was checked before
committing, along with the import gate; the two absolute-import offenders it reports are
another campaign's registry tests, unchanged.

### Applying the previous entry's lesson to this campaign's own work

The previous entry concluded that a structured assertion which passes proves the field's
VALUE, never that the field can tell two situations apart. That conclusion was then turned
on the change this campaign had made two entries earlier, and it did not survive.

`test_the_verb_refuses_because_the_profile_fact_is_unanswered` was moved off localised
prose onto `error.category == "REFUSED"` here. Its docstring states its one job: it is the
positive control for the label assertions beside it, and it exists so that "a refusal
caused by something else entirely" cannot let those siblings pass for the wrong reason.
`category == "REFUSED"` cannot establish that — **a Click parameter error on these same
verbs is published as REFUSED too.** The control was rewritten into precisely the defect it
was written to prevent, and it passed, which is why nothing noticed.

Measured against the live CLI for both affected verbs rather than argued from the sibling
module:

| | `category` | `failed_condition_id` |
|---|---|---|
| parameter error (`--bogus-flag`) | `REFUSED` | `None` |
| the profile-completeness refusal | `REFUSED` | `cli.overview.profile.complete` |

So the old assertion PASSES on a parameter error and the new one FAILS on it. The control
now asserts the failed condition, which workflow state names and a bad command line never
does.

**Two things worth keeping from this.** The first is that the lesson had to be applied
backwards, not only forwards: the entry that identified the trap was written while an
instance of it sat committed three entries earlier in this same campaign's work. A rule
discovered is worth a sweep of the work that preceded it, because the reason it was worth
writing down is that it is easy to do.

The second is that both the weakness and the fix were demonstrated on the verbs actually
under test. The sibling module's measurement would have been a fair analogy and not a
proof, and this campaign has now twice found analogies that did not hold when checked
directly.

### Completing the backward sweep: every gate this campaign added is now proven to bite

The previous entry applied the discriminator lesson to one earlier change. This entry
finishes the job by auditing the whole set, because a rule applied to a single instance is
an anecdote.

Sixteen gates and test additions were reviewed against one question: has a change been
observed that makes this fail? Fifteen had a recorded real-site probe — a reverted
expression, a removed retry, a swapped handler pair, a stripped marker, a diverted
advisory. **One did not.**

`test_concurrent_registration_cannot_duplicate_a_label` was committed after its only probe
— removing the custody root lock — left it GREEN across nine races. That result was
recorded honestly at the time, but it meant the test shipped with nothing demonstrated
that could fail it. By this repo's own standard, quoted in a module docstring elsewhere in
the tree, "a test which can never be watched to fail asserts only that its author believed
the fix correct".

Probed properly: disabling the single label comparison in the custody scan makes BOTH
processes register, and both assertions fail naming the two winning UUIDs. So the test does
discriminate, and what it pins is the duplicate-label REFUSAL. What it does not pin is the
root lock. Both halves are now in its docstring, because a reader meeting a test named for
concurrency would otherwise reasonably assume it covers the serialisation, and it does not:
the losing process still meets the winner's committed capsule when it scans, which is why
the lock can be removed without the test noticing.

**The residual gap is recorded rather than closed.** Nothing asserts that the root lock
serialises two registrations under a tighter race than spawn timing produces. Closing it
needs a race that reliably interleaves the scan and the publication, which the current
barrier does not achieve — the processes are released together but diverge across seconds
of Argon2id work. That is a real limit of the harness, not a missing assertion someone
forgot, and inventing a test that cannot be watched to fail would repeat exactly the defect
this entry exists to correct.

### A lock-exclusion assertion that measured process startup, not the lock

The previous entry recorded a residual gap: nothing asserts the custody root lock
serialises two DIFFERENT profiles. Checking that claim before building anything found it
overstated — two tests in `test_custody_transactions` already address it — and checking
THOSE found something worse than the gap.

**`test_create_root_lock_serializes_duplicate_labels_across_real_processes`** races two
spawned creates for different profile ids under one label. Removing the root lock makes it
fail **1 run in 3**: a genuine detector, but probabilistic, so a single CI run catches the
regression about a third of the time.

**`test_transaction_lock_serializes_siblings_and_releases_after_process_death`** looked
deterministic and was not. With the root lock removed entirely it passed **3 out of 3**.
The reason is in its timing:

    second.start()
    with pytest.raises(Empty):
        result_queue.get(timeout=0.25)

The window opens at `start()` and closes 250 ms later, while a spawned interpreter needs
SECONDS to import cadrumo before it can attempt a lock at all. The sibling could never have
reported inside that window whatever the lock did, so "the second process must not acquire"
was satisfied by startup latency. Half the test was real — it does prove the lock releases
after the holder is terminated, which is the stale-lock property — and half asserted
nothing.

Fixed by having the sibling publish `ready` once its interpreter is up and the lock call is
all that remains. The window now opens after that report, so it measures contention rather
than spawn cost. With the root lock removed the test fails **3 out of 3**; restored, it
passes.

**The general shape is worth carrying.** A timing window is only an assertion about the
subject if the subject is the slowest thing inside it. Anything expensive that happens
before the measurement starts — a process spawn, an import, a fixture — will satisfy a
short window on its own, and the test then passes for a reason unrelated to its name. The
tell is that the window is shorter than the setup it races.

Three consecutive entries have now found that a claim about coverage did not survive being
probed: a gap that was already covered, a control that no longer discriminated, and an
exclusion window that measured the wrong thing. In each case the probe cost minutes and the
belief would have persisted indefinitely.

### The spawn-race window was a pattern, not an incident

The previous entry fixed one exclusion window that measured process startup instead of the
lock. Sweeping the domain for the shape — a negative timing assertion opened immediately
after a spawn — found exactly one more, and it was the same defect.

`test_pointer_cas_and_active_pointer_writer_share_one_root_lock` asserts that a sibling
cannot write the active pointer while the custody transaction lock is held. Its window
opened at `writer.start()` and closed 250 ms later. With the root lock removed from the
transaction lock entirely, it passed **3 out of 3**. Repaired the same way — the writer
publishes `ready` once its interpreter is up and the pointer transaction is all that
remains — it now fails **3 out of 3** with the lock removed and passes with it restored.

Both tests kept assertions that were always real and are untouched: the first proves the
lock is released after its holder is terminated, and the second proves a stale-witness
compare-and-swap is refused with the pointer unchanged. In each case the vacuous assertion
sat between load-bearing ones, which is part of why it survived — the test as a whole was
demonstrably doing something.

**The sweep also bounded the pattern.** Only two negative timing windows exist in the
domain's tests. Two other short timeouts (`exclusive_file_lock(timeout=0.0)` and
`timeout=0.1`) are a different shape and correct: they bound the CALL UNDER TEST, asserting
a non-blocking acquire refuses promptly, rather than racing a window against setup the test
performed itself. The distinction is whether the timeout constrains the subject or merely
outlasts the scaffolding.

**Lane note.** One integration failure appeared in a file this change does not touch,
`test_status_notices_wiring`. It passed in isolation and on an immediate re-run of the full
lane, and the file's last commit is a peer's; recorded as transient rather than triaged as
a regression, consistent with this worktree's known concurrent-I/O flakiness.

### Custody transactions are globally serialised, and the per-profile lock is not what does it

With the root lock now pinned by three tests, the obvious next question was whether its
partner earns its place. `profile_custody_transaction_lock` takes the ROOT lock, then a
lock named for the profile, and holds both for the span.

**Measured by removing it:** dropping the per-profile acquisition while keeping the root
lock fails exactly two tests -- both in `test_custody_lock_order`, which assert the pair's
order and its naming -- while **321 others pass**. Nothing observes any exclusion it
provides, because it is only ever acquired inside that one function with the root lock
already held, so it can never contend.

The architectural consequence is the part worth having, and it was not written down
anywhere: **there is no per-profile concurrency in custody.** Two transactions for
DIFFERENT profiles exclude each other exactly as two for the same profile do, and a long
transaction on one profile blocks every other. Several concurrency tests in this domain
read as though per-profile isolation were being exercised; what they actually exercise is
a global serialisation point.

Recorded at the site rather than only here, because a function that names a per-profile
lock reads as a promise of per-profile concurrency that the root lock does not deliver, and
the next reader meets the code before the audit.

**Not removed.** The order is the deadlock-safety rule -- a future path taking both must
take them this way round -- and the order gate is live, which the probe confirmed by being
the only thing that failed. Redundant-for-exclusion is not the same as unnecessary, and
deleting a lock to simplify a protocol whose whole purpose is ordering would trade a
documented invariant for nothing.

Also verified in passing: `profile_custody_local_lock` is the general file-lock PRIMITIVE,
not "the per-profile lock" -- the root lock itself is built on it, as are the journal,
receipt, evidence and session locks. Only one call site uses it for the per-profile path.

### Correction: no test claims per-profile concurrency, and the weak race is now stronger

**Correcting the previous entry.** It asserted that "several concurrency tests in this
domain read as though per-profile isolation were being exercised". That claim was made
without enumerating them, and enumerating them shows it is wrong.

Every use of "independent" in the domain's concurrency tests refers to independent
PROCESSES -- "an independent interpreter", "two independent interpreters", "two
independently scheduled creates" -- which is accurate. `test_custody_isolation_matrix`
concerns CRYPTOGRAPHIC isolation, that profile A's envelope cannot open profile B's
capsule, and says so. `test_two_profiles_keep_independent_ledgers_across_unlocks` asserts
disjoint ledger DATA, which is genuinely per-profile and is exactly what it checks. None
promises per-profile concurrency. The conflation of "independent interpreters" with
"independent profiles" was the reader's, not the tests'.

What survives from that entry is the design fact — custody transactions serialise globally
— and it is recorded at the site, which remains worth having because it was written down
nowhere.

**The weak detector recorded there is now measurably stronger.**
`test_create_root_lock_serializes_duplicate_labels_across_real_processes` caught the root
lock's removal in **1 run of 3**: each sibling reached the create whenever its own KDF
setup happened to finish, so which one collided was scheduling luck rather than the lock.
Releasing both from a barrier placed after the envelope material exists and before the
transaction raises detection to **4 runs of 5**, measured the same way.

It is deliberately left probabilistic. Its role is the REAL race — proving that two
genuinely scheduled creates yield one winner — and forcing determinism would require
holding the lock, which converts it into the exclusion test its two siblings already
provide deterministically. A suite wants both shapes: one that proves the invariant under
a held lock, and one that proves it under actual scheduling.

### The serial slice, and a hole in this campaign's own reachability gate

**The serial slice was verified rather than assumed.** Every iteration of this campaign
excludes `serial` from both lanes, and the standing note that the slice is healthy predates
weeks of peer commits. Run for the domain: **16 tests, all passing.** The note still holds.

**Running it exposed a weakness in the gate added a few entries ago.** That gate asserts
each module carries an execution marker. The lanes, however, also EXCLUDE markers, and a
combination excluded by every one of them is run by nothing while still looking marked:
`integration and serial and perf` is dropped by the parallel lane for being serial and by
the serial lane for being perf. The `dev/` reachability gate evaluates its lane
EXPRESSIONS precisely for this reason, and the `src/` one only checked presence — a
weaker check than the sibling it was modelled on.

The hole is currently empty, measured rather than assumed: no module carries
`serial and perf`, and `external_tool`, `perf` and `resident_service` are not used anywhere
under `src/` at all — those exclusions are defensive against markers that live in other
trees. The 16 `serial` tests are the only occupants of any exclusion.

The gate now evaluates the five declared lane expressions instead. Proven on a real module
by marking it `integration+serial+perf`: the new check fails, and **the presence check
stays green** — which is the whole point, since the old assertion could not see the case.

**One instrument correction worth recording.** The first marker census reported 29,704
tests for `-m serial`, the size of the entire suite. The number was real and the reading
was wrong: pytest prints `16/29704 tests collected`, and the pattern matched the total
rather than the selection. Every "no tests collected" in the same census was accurate,
which is what made the one wrong figure easy to accept — a census is only as good as its
least-checked line.

### The registration screen showed an operator a message key

Found by following this campaign's own retryability split through to the HUMAN surface.
The split gave an agent operator the right answer; the question was whether the screen
inherited it. It had a worse problem, and one that predates the split.

`attempt_registration` is the seam between the application layer, which classifies a
refusal, and the screen, which displays it. **Its docstring says translating between the
two is this seam's job.** It returned `str(refusal)`. On a translated error `str()` yields
the message KEY -- the constructor passes `translated_message` to `Exception.__init__` as a
fallback, which the base class documents as "readable text" and which a dotted key is not.

Measured by driving the real path twice with one label:

    OPERATOR SEES: 'application.user_profile.errors.profile_already_exists'

The rendered message existed in all four catalogues the whole time, and it is markedly
better than the key: it names the profile AND tells the operator to run `aeat config login`
or `config profile delete`. Nothing asked for it. Fixed by rendering
`tr(translated_message, **context)`, the pattern already used elsewhere in the entrypoints
layer.

**Nothing could have caught this.** The screen deliberately treats the refusal as opaque
text -- "a refusal arrives as text the screen displays, not as an exception it has to
recognise" -- and every existing screen test asserts a refusal is SHOWN, never what it says.
A key satisfied them exactly as prose would. The new gate asserts the content: the refusal
must not match a message-key shape and must carry its context by naming the profile.

**Attribution was measured, not inferred.** The TUI package reports 92 failures, and six of
them name registration or refusal, which is uncomfortably close to a change in the
registration refusal path. Running those modules with the change reverted and again with it
restored gives **29 failures either way** -- identical, so none is this change's. The
dominant signatures are 53 "requires the target's active bucket session" and 33 "profile
facts require an authenticated session", which is the credential-store class the standing
context already excludes, plus a handful of theme colour assertions.

The lesson is the one this campaign keeps meeting from a new direction: a fallback that
makes a value *printable* is not the same as making it *readable*, and a test that asserts
something was displayed says nothing about whether it could be understood.

### The renderer that seam needed already existed

Following the previous finding one step further asked the obvious question: where *else*
does this domain hand `str(error)` to an operator? The sweep found the answer to a
different question. Of the twelve `str(exc)` sites in scope, eleven wrap a pydantic or OS
exception into a domain error's message, where `str()` genuinely *is* the prose. The
twelfth was the sibling login seam at `_login_frontend.py:186` -- and it was already
correct, calling `resolve_error_message(refusal)`.

So a canonical renderer existed the whole time, and the fix authored one iteration earlier
had reinvented a weaker copy of it. `core/errors/_registry.py:492` does three things the
hand-rolled `_refusal_text` did not:

- it reduces the context through `_coerce_interpolation_kwargs`, dropping non-identifier
  keys so a free-form context entry cannot break the `tr(...)` interpolation contract --
  the hand-rolled version splatted the raw mapping and would have raised `TypeError`;
- it falls back to `args[0]` when there is no key;
- it falls back to `tr(code.message_key)` off the **registered** error code, so a refusal
  carrying no `translated_message` at all still reaches the screen as words.

Neither gap is reachable today: all five refusals that can arrive at this boundary were
enumerated from their raise sites, and each carries a `translated_message` with
identifier-shaped context keys. Both renderers were then driven over all five and produced
byte-identical output, so the swap is behaviour-preserving now and strictly stronger for
whatever is raised next. `_refusal_text` was deleted rather than kept beside its twin.

**The general shape, worth carrying:** a duplicate is most dangerous when it is *correct*.
Nothing failed, no lane moved, and the copy would have sat there being right until the
first refusal without a key -- at which point the two seams would have disagreed about what
an operator sees, and only one of them would have been wrong. Checking for an existing
authority is cheaper before writing the second one than after.

**Provenance note, not a defect.** Both files were swept into `d86551026e`
(*"src(registry): record-design type-code rendering coverage with the IS catalogue"*) by a
peer's broad commit while the domain lanes were running, so the `git commit` that followed
found a clean tree. The content on `main` is complete and unmangled -- verified by reading
both files back out of `HEAD` -- but it is filed under an unrelated subject, and no
pathspec discipline on this side could have prevented it. This is the third time the shared
worktree has absorbed in-flight work; the durable lesson is that verifying the change
landed has to be done by reading `HEAD`, never by trusting the commit to be one's own.

### An iteration that found nothing, and the four axes it closes

Recorded so none of these is re-derived. Nothing was changed in the tree.

**The `str(error)` sweep is complete in both spellings.** The earlier explicit sweep matched
only `str(...)` calls, which cannot see an f-string interpolating an exception -- `f"{exc}"`
calls `str()` implicitly. Re-run for that shape, the domain yields twenty-odd sites and all
but one interpolate a THIRD-PARTY exception (keyring, tarfile, cryptography, pydantic) into
a diagnostic, where `str()` genuinely is the prose. The exception,
`_manager_actions.py:246`, splices a variable named `refusal` straight after a translated
string, which looks exactly like the defect fixed two iterations ago -- but `_clave_refusal`
is annotated `-> str | None` and returns the refusal text already. Not a bug. The name
matched the pattern; the type did not.

**The sealed-archive pair is LIVE, and the claim that it was not was a tooling error.**
Searching for `read_sealed_archive` / `write_sealed_archive` outside their own modules
appeared to show only tests -- but the search was piped through `head -6`, and the test
module's many matches filled all six lines, hiding the production consumer below the cut.
`application/user_profile/_capsule_archive.py` calls `write_sealed_archive` at line 161 and
`read_sealed_archive` at 177 and 206; it is the `config profile archive` / `restore`
surface, documented in `docs/how-to/protect-data-access.md`. The pair is not dead code and
must not be treated as such. **The method lesson is one this campaign has now paid for
twice: never truncate the output of a completeness search.** `head` is for reading, not for
deciding, and a bounded window over an unsorted result set is indistinguishable from a
complete one.

**The archive's label-disclosure guard has its read sibling.** The surface carries a real
disclosure risk, stated in its own words: a published capsule keeps the operator's chosen
label in plaintext beside the ciphertext, so an archive built by packing the directory
verbatim would leak it to anyone holding the file. The obvious hole would be a guard that
proves only what `inspect` PRINTS -- and one assertion is exactly that. But it is not the
only one: `test_profile_archive_roundtrip.py:186` opens the tar, pins the member set to
`{header.json, payload.envelope}`, and asserts the label, the NIF, and the name and surname
tokens are absent from the joined member payloads. The bytes-level sibling is present, so
the axis that usually fails toward disclosure does not fail here.

**Conclusion.** No item in the selection order produced actionable work this iteration. The
directive's own instruction applies -- say so rather than manufacture a gate -- and it is
worth stating why the well is running dry rather than treating it as a temporary result:
the domain's remaining named items are not defects but DECISIONS (the profile-bundle import
half, the over-exported `user_profile` names), and a decision cannot be closed by testing
harder at it.

### Auditing the previous iteration's own completeness claims

The truncated-search error recorded above has an implication worth acting on rather than
noting: every earlier sweep in this campaign was read through `head`, so the CONCLUSIONS
rest on windows, not on result sets. Re-run without a cut:

- The explicit `str(exc)` sweep yields **11 matches in 9 files**. The window was 14 lines
  and showed all 11. That claim was sound.
- The f-string sweep yields **27 matches**. The window showed 20. **Seven were hidden, in
  two files never seen at all** -- `storage/master_key/_master_key_derivation.py` and
  `storage/sql/repository.py`. Read in full, all seven interpolate a third-party exception
  (keyring, argon2, SQLAlchemy's `exc.orig`), so the conclusion "no Cadrumo error is
  rendered by implicit `str()`" survives. But it survived by luck of the sort order: either
  unseen file could have carried the defect, and nothing about the truncated read would
  have looked different.

The distinction worth keeping is between a claim that is TRUE and a claim that is
JUSTIFIED. Last iteration's was true. It was not justified, and it was published in the
same entry that warned against exactly this.

**One observation from the newly-visible lines, recorded rather than acted on.**
`sql/repository.py:47` wraps an `IntegrityError` as
`RepositoryError(f"... {exc.orig}")`. Using `.orig` rather than `exc` is load-bearing:
SQLAlchemy's `StatementError.__str__` appends `[SQL: ...] [parameters: ...]`, embedding row
values into the text, while the DBAPI original does not. The choice is undocumented, so
nothing tells a future editor that widening it to `exc` would push row values into an
operator-facing message. It is not a live defect -- the redaction funnel scrubs the record,
and the sibling `_log.warning(..., exc_info=True)` is covered because the filter formats and
scrubs the traceback into `exc_text` (`core/logging.py:396`), which `logging.Formatter`
prefers over re-formatting; the tree contains exactly one `Formatter`, so no sink bypasses
it. Redaction base composition is already verified sound and is not re-probed here. The
residue is a silent invariant, not an open hole.

**No production change this iteration.** The lanes were not re-run, because nothing ran.

### A dot segment is a separator the separator check cannot see

`bucket_paths(root, bucket_id)` at `adapters/persistence/storage/bucket/_layout.py:66` is
the one place the on-disk layout `<root>/buckets/<bucket-id>/` is composed. It refused an
empty id and an id carrying `/` or `\`. It accepted `".."`.

Measured rather than reasoned about, against a real call:

    '..'    -> C:\storage-root            (ABOVE buckets/, at the storage root)
    '.'     -> C:\storage-root\buckets    (the buckets directory itself)
    '../..' -> REFUSED, path separator
    'ok-id' -> C:\storage-root\buckets\ok-id

The shape is worth naming because the guard looks complete: `".."` IS a traversal, but it
is spelled without the character the traversal check looks for, so it passes on a
technicality. `"../.."` was refused, which makes the surface look guarded from the outside
-- and it was refused incidentally, for carrying a separator, not for traversing.

**No live exploit path, and the reason is the interesting part.** The one place an
untrusted `bucket_id` could enter is a restored archive header, and an archive is an
attacker-supplyable file. That path is contained: `_capsule_archive.py:252,258` requires the
header's `bucket_id` to equal the custody envelope's `profile_id`, which is a UUID, so
`".."` cannot survive the cross-check. The system-scoped ids in the tree are `system`,
`unsecured` and `diagnostic-probe`. So the containment is real -- but it lives upstream, in
an identity check written to prove the archive's members agree with each other, not to
prove a path stays inside its directory. `BucketId` itself is
`StringConstraints(min_length=1, max_length=128)` and admits `".."` happily.

The fix puts the refusal at the boundary that owns the join, so the guarantee no longer
depends on every future caller happening to have a UUID. The refusal is `set(id) == {"."}`,
which covers `"."`, `".."` and `"..."` without touching an id that merely CONTAINS a dot --
`a.b` and `..alpha` are still valid ids, and a test pins that direction, because a guard
that widened onto legitimate ids would break `system` and `unsecured` while passing every
assertion about `".."`.

**The general lesson:** when a validator enumerates the dangerous CHARACTERS, ask which
dangerous VALUES contain none of them. Path traversal is the classic case because the
dangerous value is spelled entirely in a character every path legitimately contains.

Gate: `bucket/tests/test_layout.py`, beside the empty-id and separator siblings it belongs
with. Proven to bite by restoring the permissive join from a scratchpad plugin: DID NOT
RAISE. Lanes 314 integration / 1576 unit (+3).

### The same lens, applied to the sibling validators: two more escapes

The dot-segment finding generalises to a question worth asking of any path
validator: **which dangerous values contain none of the dangerous characters it
enumerates?** Asked of the storage domain's other path-composing functions, it found
`custody/_capsule_data.py:validated_data_path` -- the designated guard for the names in a
capsule's data inventory, whose refusal text is literally "escapes its staging root".

It is a good validator. It refuses absolute paths, refuses `""`, `"."` and `".."`
components, refuses backslashes, and parses as `PurePosixPath` because that is the
capsule's on-wire spelling. Two values still get through.

**A drive qualifier reads as relative on POSIX and absolute on Windows.** Measured against
a real join with staging root `D:/staging/root`:

    'C:/foo' -> 'C:foo'                 (staging root discarded entirely)
    'C:foo'  -> 'C:foo'                 (drive-relative: resolves against the CWD on C:)
    'a/b'    -> 'D:/staging/root/a/b'   (correct)

`PurePosixPath("C:/foo")` is an ordinary two-component RELATIVE path -- not absolute, no
dot component -- so it cleared every check. The UNC form `//server/share/x` and the
backslash form were both already refused, and that is what made the gap hard to see: three
of the four ways to escape were covered, so the guard looked complete from the outside.
The platform this application runs on is the one where the fourth bites.

**The `"."` clause could never fire.** `PurePosixPath` normalises a lone dot away, so `"."`
and `"./"` parse to NO components at all and the `{"", ".", ".."}` membership test never
runs against the value it explicitly names. A validator listing a value it cannot reach is
worse than one that omits it, because the listing is what stops anyone looking again.
Contained rather than dangerous -- it resolves to the staging root, a directory, so a write
fails there -- but the stated rule was not true.

**A wrong test expectation is what surfaced the normalisation.** The first draft asserted
`"a/./b"` was refused; it is not, because pathlib collapses it to `a/b` before any check
runs, and accepting it is correct. The failing test was right to fail, and chasing it is
what exposed the dead `"."` clause. That direction is now pinned in its own test so the
next reader does not repeat the assumption.

**Neither is live.** The inventory's keys are the constant `profile-label.v1.json` and
callers passing `{}`; no untrusted name reaches the validator today. Both are fixed at the
validator because containment is the function's stated contract, not an accident of who
happens to call it -- the same reasoning as the `bucket_paths` dot segment, and the second
time in two iterations that a guard's real guarantee lived somewhere other than where it
was written.

Gate: `custody/tests/test_capsule_data_path_validation.py`, seven tests. Proven to bite by
restoring the POSIX-only validator from a scratchpad plugin: both new checks fail
independently. Lanes 314 integration / 1583 unit (+7).

### The fix that did not travel, and a failure that is not a traversal

Hardening `bucket_paths` against a dot-segment id was correct and incomplete. Its twin
`keystore_path` carried the SAME two checks -- empty and separator -- and therefore the same
omission, so `".."` still resolved to the storage root; the escape had simply moved to the
tree holding key material. `keystore_sidecar_path` was weaker again: it validated
`bucket_id` through the separation contract and joined `filename` without examining it at
all, and its own docstring names it the canonical join point for the persisted session
record, the wrapped bucket DEK and the login-throttle cache. Measured against real joins
with root `C:/storage-root`:

    keystore_path('..')                    -> C:/storage-root
    sidecar(filename='../../secrets.json') -> C:/storage-root/secrets.json
    sidecar(filename='C:/evil.json')       -> C:/evil.json

**The fourth failure is not a traversal, and it is the one worth carrying.** `"D:x"`
resolves onto another drive. `"C:x"`, against a root already on `C:`, stays inside the tree
and silently becomes the component `"x"` -- pathlib drops the same-drive qualifier. The
directory name then no longer equals the identifier that named it, so two distinct ids land
on one directory. Every containment check in the world calls that safe, because it IS
contained; what it violates is identity, not containment. A gate written as "does the join
stay under the root" would pass it, which is why the anti-vacuity test pins the renaming
directly rather than the escape.

**Three copies of one rule had drifted into three different answers.** That is the actual
defect: not any single missing check, but a rule with no home, so hardening one join left
the others as they were. The rule now lives in `validate_path_component` and the three joins
consult it -- empty, separator, dot segment, drive-qualified. The tests pin the JOINS rather
than the helper, so a caller that stops consulting it fails rather than quietly reverting.

**Still latent, and the reasoning is the same each time.** Every caller passes a constant --
`PROFILE_SESSION_FILENAME`, `LOGIN_THROTTLE_FILENAME`, a UUID or a system-scoped id -- and
`keystore_path` has no external callers at all, though it is a facade export. The check
belongs at the join so containment stays a property of the join rather than of whoever
happens to call it. This is the third consecutive iteration where a guard's real guarantee
lived somewhere other than where it was written, and the pattern is now explicit enough to
state as a heuristic: **when hardening a validator, find its twins before closing the item
-- a rule enforced in more than one place is a rule that has already drifted.**

Gate: `bucket/tests/test_keystore_path_components.py`, five tests. Proven to bite by
restoring the pre-fix joins from a scratchpad plugin: both refusals fail independently.
Lanes 314 integration / 1588 unit (+5). Swept into peer commit `4d08cf20c4`, verified
complete by reading all three files back out of HEAD.

### A second layer left standing after its only consumer was deleted

Following the twins heuristic to the storage domain's other path validators found
`_path_safety.safe_repository_id`, which is stricter than the join validator hardened last
iteration -- it refuses any dot-PREFIXED token, not just a bare dot segment. It is sound.
What was not sound was the contract its docstring described.

It called itself "the early-rejection half of the substrate's two-layer path contract" and
named the second half: `safe_subpath`, re-resolving a token against the real filesystem,
"the only layer that can catch a symlinked store directory". Both halves were said to be
necessary -- "neither layer subsumes the other".

`safe_subpath` had no production caller. Searched across the whole repository without
truncation, it appeared in exactly four places: its own definition, its own `__all__`, three
export entries in the storage facade, and tests. The field the docstring named as needing
it -- a rotation entry's `target_filename` -- is nowhere in the tree.

The history explains it exactly: `6bee98b0be` *"storage: delete the dead rotation surface
and its tests"* removed the module that owned `target_filename`, and left the second layer
behind. A stale `_rotation.cpython-313.pyc` was what first pointed at it.

**The prose was the live part of the defect.** Dead code is inert; a docstring asserting
that real-filename cases are covered by another layer is not. Someone adding a token that
becomes a filename would have read that sentence and believed the guarantee existed
somewhere. It exists nowhere. `safe_repository_id` now states that shape rejection is the
whole contract, and that containment must be added back AT THE JOIN if a token ever becomes
a filename -- the same conclusion the last three iterations reached from three other
directions.

No capability was lost: `core.paths.resolve_relative_subpath` is untouched and still has a
live consumer in `domain/manuals`. Two tests used `safe_subpath` only as a convenient way to
raise a `PathContainmentError`; they now raise through `safe_repository_id` and keep what
they actually assert -- the registered code, the localized operator message, and
`ValueError` inheritance.

**One measured non-finding, recorded so it is not re-attributed.** `dev/tests/test_import_
hygiene_gate.py` is red with 6 failures: the test-only cross-package private-import count
regressed from a documented 69 to 108, across the TUI, invoices, modelo, filing, live and
aggregation packages. Every listed site was checked against the four files changed here and
none of them is one; the single storage entry names
`bucket/tests/test_sealed_archive_member_bound.py`, untouched by this work. It is tree-wide
debt accumulated by other campaigns, and closing it is the broad mechanical sweep this
campaign's directive excludes.

Lanes 314 integration / 1586 unit -- down exactly two, the deleted `TestSafeSubpath` cases.

### The storage facade has no more orphans, and its best candidate is protective

`safe_subpath` was orphaned when the rotation surface was deleted, which raises the obvious
question: what else did a deletion leave behind? Answered by measurement rather than
suspicion -- all 260 names in the storage facade's `__all__`, each checked for a production
consumer outside its defining module.

**Twenty-five names have no such consumer, and none of them is dead.** The distinction that
matters is the one the safe_subpath case established: a name used only inside its own
package is OVER-EXPORTED, which is a different finding from a name used nowhere at all.
Facade narrowing was already declined for this campaign as broad mechanical work, and
nothing here changes that judgement.

**The strongest candidate is protective, and deleting it would have removed a proof.**
`BUCKET_MANIFEST_FILENAME` has no production consumer and a retired module behind it --
`3fa483d89b` retired the bucket manifest -- so it reads exactly like the `safe_subpath`
residue. It is the opposite. `test_namespace_registry.py:560` uses it to assert the
retirement: `path_by_key("bucket_manifest")` must raise, and the filename must not appear as
any registry segment. Its own docstring says why -- *"A member that simply stops being
declared is indistinguishable from one nobody got around to declaring -- which is the
confusion that let this manifest sit half-retired, its reader deleted while the hierarchy
still declared it as a live format."* The constant carries a comment saying it is kept to
recognise the retired format on a pre-cutover bucket.

This is precisely the classification the standing lead asks for before any deletion, and it
generalises: **a legacy NAME with no production consumer is evidence of nothing.** The
`safe_subpath` case and this one are indistinguishable by consumer count, by naming, and by
having a deleted module behind them. What separates them is that one was cited by a live
assertion and the other by a docstring describing a contract it no longer had. Only reading
the references tells them apart.

**The vacuity question was asked and answered.** A negative assertion can pass for free, so
the anchor was checked rather than assumed: no `StorageCategory` has an empty subpath (all
64 measured), and `BUCKET_MANIFEST` resolves to `'manifest.toml'`, so the retirement test
asserts something real today. The sibling taxonomy test binds each constant to its
declaration, which catches a future hand-copied literal.

**No production change this iteration**, so the lanes were not re-run. The remaining named
items are unchanged: the profile-bundle import half needs an operator ruling, and the
over-export inventory is deferred by scope, not by ignorance of it.

### A gate two docstrings cite, that nobody had written back

The `safe_subpath` defect was prose describing a contract the code no longer had, which
makes "prose naming an artefact that does not resolve" a searchable class -- the discipline
the firmware-parity rule already applies to shipped rules. Swept over the domain's Sphinx
roles, after filtering builtins, stdlib, third-party roots and package directories, eleven
references did not resolve. Three are bare external class names (`TypeDecorator`,
`ContextVar`, `sessionmaker`), one is a deliberate past-tense note about a consolidated
method, and two named artefacts that genuinely do not exist.

The important one is cited TWICE, in both directions.
`application/user_profile/__init__.py:55` says the boundary's laziness is enforced by "the
:mod:`entrypoints.cli.tests.test_lazy_command_tree` gate and the producer-side probe in
:mod:`application.user_profile.tests.test_lazy_boundary`". The producer probe says the same
in reverse: "The CLI-side gate ... enforces that the state-free CLI surfaces do not
transitively load the registry. This module pins the same contract at the *producer*
boundary." **Only the producer half existed.** The mutual citation is what made the absence
invisible: each document points at the other as corroboration, and two documents agreeing
reads as two gates.

**The property was measured before anything was written, and it holds** -- building the
command tree and rendering `--help` and `--version` loads ZERO registry modules. So this is
a missing gate over correct behaviour, not a live regression, and saying so matters:
restoring a gate that would have been red is a different act from restoring one that is
green.

**The halves are not redundant, which is why the survivor did not cover the gap.** The
producer probe imports `cadrumo.application.user_profile` alone. The CLI reaches that
boundary through Typer registration, group callbacks and Click's help rendering, so an eager
import added in a command module, a callback default or an import-time help string is
invisible to the producer probe. Demonstrated rather than argued: injecting an eager
registry import into the CLI startup path surfaces 162 registry modules here while the
producer probe stays green.

The gate is restored under the name both docstrings cite, so the references resolve rather
than being edited away -- and the second citation is corrected, since it omitted the
`.tests` segment and named a module path that could never have existed.

**Two method notes.** The anti-vacuity risk was specific: a probe whose CLI invocation
crashed would import nothing and pass. Both invocations therefore assert exit code and
non-empty output before the scan, and the probe prints a completion sentinel the test
requires. Separately, the detector that found this had 67 hits of which most were builtins
and stdlib; the filtered rerun cut it to 11. A sweep whose false-positive rate is unknown
cannot support a "nothing else is wrong" claim, which is why the filter was tightened before
any conclusion was drawn from it.

Lanes 314 integration / 1586 unit, both unchanged -- the new gate lives in
`entrypoints/cli/tests`, outside the domain lane paths, and is reachable through the `unit`
marker that `just test-unit` selects.

### Closing the prose class, and what a better instrument found

Three iterations were each misled by a docstring, so the class was closed rather than the
cases. The instrument matters more than the findings here.

**The first detector was wrong in both directions.** Matching a reference's leaf name
against every symbol defined anywhere in the tree produced 67 hits, mostly builtins and
stdlib -- and, far worse, it produced false NEGATIVES. Resolving instead by IMPORT --
walking back from the longest importable dotted prefix, then `getattr` for the remainder --
found three dangling references in the same packages that the name-matching scan had
cleared, because each one's leaf name existed somewhere else entirely. Import resolution is
also the only method that respects this tree's PEP 562 facades: a name reached through
`__getattr__` is absent from the module's source and present on the module object.

**Four references were wrong, and one implied a missing export.**

- `_section_rows` named `ProfileCapsuleLifecycle.edit_fields` as the write door that
  "judges a whole fact batch at once". There is no such method, and that class owns no
  field-editing method at all -- only create, restore, select and the delete trio. The
  property is real and lives in `reject_invalid_profile_facts`, reached through
  `apply_profile_fact_changes`, which states it in nearly the same words: "The whole
  resulting fact sequence is judged rather than the incoming change alone, so a patch is
  never left half-applied by a later field's refusal." Right about behaviour, wrong about
  the artifact -- the most durable kind of wrong, because the behaviour checks out when a
  reader tests the claim and only the name fails.
- A test cited `SubmissionRepository` in the DOMAIN layer; it is an adapter class, and the
  domain holds only the port protocol.
- Another cited `BucketSession` on the storage facade; `master_key` exports it.
- The trash-removal test cited a converged implementation in a module deleted since.

`CommittedProfileView` was PROMOTED rather than re-pointed. It is the return type of three
public `ProfileCapsuleLifecycle` methods and was absent from its package facade, while
`ProfileRestoreAuthority` -- defined in the same module, in the same `__all__` -- is
exported in all three facade places. The citation was assuming an export that had simply
been missed, and pointing it at the private module instead would have written the
architecture violation into the prose.

**The gate's own false-positive risk was the thing to get right.** A pydantic v2 field is
not a class attribute; `getattr(Invoice, "operation_date")` is nothing. A resolver without
that knowledge calls every correct `:attr:` reference in the tree stale, and the honest
response to a gate that cries wolf is to narrow its scope until it means nothing. Fields
and annotations are therefore counted as present, with both directions pinned. Scope is
fully-qualified `cadrumo.*` targets only: a bare anchor is ambiguous by design and the docs
build's resolver owns that question.

**An in-scope regression absorbed on the way past.** `test_wheel_content_boundary` was red,
asserting the wheel was missing `storage/master_key/_bip39_wordlist.txt`. The file was not
missing: `3452ca29b6` promoted the mnemonic codec out of `master_key` into `storage` and
moved the wordlist with it, without sweeping the gate's required-members list. Relocations
are meant to land every referencing surface in one commit; this surface was missed, and the
gate had been failing since. Fixed to the real path.

**Attribution for the rest, measured not assumed.** `src/cadrumo/tests` reports 59 failures;
the wheel one was mine to fix, leaving 58. They group across IVA-stem conformance, taxonomy
literals, type-ignore rationales, acceptance-wall collection and the self-import gate. The
two that could plausibly have been caused by this work were checked directly: the
self-import gate names two registry test files, and the wheel gate named the wordlist. The
remainder was grouped by module rather than opened one by one, and is reported as
unattributed rather than as cleared.

Lanes 314 integration / 1586 unit, both unchanged -- the new gate lives in
`src/cadrumo/tests`, outside the domain lane paths.

### The per-push stub gate was watching a tree it had just written itself

The wheel-gate fix raised the obvious follow-up: that relocation missed one referencing
surface, so which others did it miss? Chasing the docs surface found something better than
another stale path.

**First, a self-inflicted one.** `python -m dev.docs.apidocs scaffold --check` reported
drift: `cadrumo.core._windows_contention` had no stub. That module was added EARLIER IN
THIS CAMPAIGN -- the Windows contention predicate -- and `scaffold` was never run, so it
was silently absent from the published documentation. The docs rule states both autodoc
failure modes and names this as the quieter one: an orphan stub crashes the next nitpicky
build loudly, while a missing stub produces no error anywhere.

**Then the reason nothing caught it.** `test-dev-ci` -- the lane `ci.yml` runs per push --
already named `dev/docs/apidocs/tests`, enrolled with a long and careful argument: a module
add, rename or delete is the only thing that drifts the stubs, `docs-check` is path-scoped
to `docs/` so no `src/**` push fires it, and therefore no per-push lane produced a verdict.
Every step of that reasoning is right. **The directory it names cannot answer the
question.** `dev/docs/apidocs/tests` scaffolds the real module tree into a `tmp_path` and
checks THAT for drift, so it proves the manager's round-trip and is clean by construction;
it never looks at the committed `docs/api/` tree. The gate whose subject is the committed
tree is `dev/docs/tests/test_api_stubs.py`, which ran only in `test-dev-tooling` (ci-full)
and the path-scoped `docs-check`.

Measured rather than argued, with one stub removed from the committed tree:

    dev/docs/apidocs/tests                            -> 10 passed   (blind)
    ... plus dev/docs/tests/test_api_stubs.py         ->  1 failed

So the fix is one path on one recipe line, and the marker was checked rather than assumed --
`unit`, `hex_core`, `docs` -- exactly as the neighbouring comment insists, since a
`docs`-only marker would be deselected by that lane's expression and still exit zero.

**The shape is worth naming, because it is the most expensive kind of gap.** This was not
an unguarded surface anyone had overlooked; someone identified the exact risk, wrote out the
failure modes, chose the lane deliberately, and documented why. The enrollment then pointed
at a test directory whose name matches the subject while its SUBJECT does not -- tmp_path
round-trip versus committed tree. Everything downstream reads as covered, and the more
carefully the reasoning is written, the less likely anyone re-derives it. **A gate is only
as good as the thing it looks at, and a directory name is not evidence of what its tests
assert.** My own missing stub sat on main through several pushes as the live proof.

Lanes 314 integration / 1586 unit, both unchanged. `scaffold --check` now clean, and the
nitpicky docs build passes with the new stub (17 tests).

### The same shape again, and this time the fix is not mine to make

The stub-gate finding was that a per-push lane ran a test directory whose SUBJECT was a
`tmp_path` round-trip rather than the committed tree. That instance was safe to fix because
the real gate was green. Asking whether the shape repeats found that it is systemic.

**Measured, not inferred:**

- `pyproject.toml` sets `testpaths = ["src/cadrumo", "src/cadrumo-harness",
  "dev/packaging/tests/test_installed_oracles.py"]`, so `just test-unit` -- which names no
  paths -- never collects `dev/`. Confirmed empirically: a default `--collect-only` run
  matches `test_import_hygiene_gate` **zero** times.
- The lanes `ci.yml` runs per push are `test-dev-ci`, `test-per-push-integration-gates`,
  `test-unit` and `test-harness`. `dev/tests` appears in none of them; it is named by
  `test-dev-tooling` and `test-ratchets`, and by `test-per-push-integration-gates` for
  exactly ONE module (`test_suggestion_command_conformance.py`).
- `ci-full.yml`, which runs `test-dev-tooling`, is `workflow_dispatch:` **only** -- no push,
  no pull request, no schedule.
- **28 modules under `dev/tests` scan the real `src/cadrumo` tree.** One of them is
  per-push. The rest produce a verdict only when a human manually dispatches a workflow.

**The shape is identical to the stub case, one layer along.** `dev/quality/tests` IS
per-push -- and its tests drive the scanners over `tmp_path` and synthetic path strings
like `"src/cadrumo/provider.py"`. So the per-push lane proves the TOOL works; the gate that
asks whether the TREE is clean is the one nobody runs. Twice now the enrolled thing has
been the tool's own unit tests, which are green by construction, sitting where a tree
verdict was assumed to be.

**This predicted a symptom already recorded here.** Two iterations ago the import-hygiene
gate was found red, with the test-only cross-package private-import count regressed from a
documented 69 to 108 -- 39 undocumented sites across the TUI, invoices, modelo, filing, live
and aggregation packages. That is not a lapse by 39 authors; it is what a ratchet does when
nothing pulls it on a push. The debt is the visible consequence of the blindness measured
above.

**Why this one is left open rather than fixed.** The remedy is one path on one recipe line,
identical to the stub fix. But that gate is currently RED, so enrolling it per-push would
fail every peer's next push until 39 sites in six packages this campaign does not own are
either fixed or documented. That is an outward-facing change with a blast radius across
other people's work, and the sequencing -- fix or document the debt first, enrol second --
is a call for whoever owns those packages, not something to impose from here. Documenting
the 39 entries to make the gate green would be worse: it would rubber-stamp the violations
the ratchet exists to prevent.

Recorded with the evidence so the decision can be made on measurement rather than
re-derived. **No production change this iteration**, and the lanes were not re-run because
nothing ran.

### Three custody cases nothing could run, found by a gate nothing runs

The previous entry measured that `dev/tests` produces a verdict only on a manual
`workflow_dispatch`. Running it deliberately is therefore the cheap move, and it returned
71 failures over 610 passes -- a directory that has not been read in some time.

**First, attribution.** `test_lane_reachability.py` was among the failures, and a lane was
edited here last iteration, so the failure was read before anything else. Its unreachable
list named `dev/packaging` serial cases and `os_keychain` cases; the addition made here was
a single file appended to a PARALLEL lane line, which cannot remove coverage from either.
Not this campaign's breakage, and confirmed by reading the list rather than by reasoning
about the edit.

**Then the finding, which is squarely in this domain.** Three `os_keychain` cases were
selected by no lane at all:

    entrypoints/cli/tests/test_config_custody_profile_lifecycle.py
        test_registered_profile_custody_survives_logout_and_reopens_on_login
    entrypoints/cli/tests/test_named_profile_resolution_cross_process.py
        test_a_named_profile_resolves_in_a_process_that_did_not_write_it
        test_the_named_and_active_paths_agree_about_the_same_record

`test-os-keychain` is the only lane that can select them, and it named ONE module from that
directory -- `test_profile_session_root_resume.py` -- while these live in two siblings. So
the cross-process resumption contract the lane exists for was, in two of its three files,
never selectable. The gate's own words for this are exact: *a test nobody runs reads as
coverage and is not.*

The fix names the DIRECTORY instead of a third and fourth file, because `-m os_keychain` is
what scopes it: a future custody case added beside them is selected when it lands rather
than joining the same silence. Measured both directions -- the lane selected 39 and now
selects 42, and the unreachable list drops from 8 to 5.

**A qualification that matters.** These cases still cannot PASS on this host: the OS
credential store refuses a network logon with error 1312, which the standing context already
records and which the lane's own comment calls a true report of the host rather than a
defect. Making them SELECTABLE is the whole of the fix. It would have been easy to overstate
this as restored coverage; what is restored is the ability of an interactive desktop session
to exercise them at all.

**The remaining five are left deliberately.** They are `dev/packaging` integration+serial
cases that `test-dev-ci`'s serial line does not name. Enrolling never-run heavy install
tests into a per-push lane has the same blast-radius problem as the import-hygiene gate --
a different surface, other owners, and a decision that should be made by them.

**The compounding shape, now three deep.** A stale stub survived because the per-push lane
watched a `tmp_path` round-trip; the hygiene ratchet drifted because its gate runs only on
manual dispatch; and these three custody cases were unreachable because the gate that says
so ALSO runs only on manual dispatch. Each layer of the safety net is itself watched by a
layer nobody looks at. The generalisation worth carrying: **when a gate reports a gap, ask
what runs the gate -- an unread verdict and an absent one are the same thing.**

Lanes 314 integration / 1586 unit, both unchanged.

### The no-shim mandate turned on this campaign's own tests

Scope was widened by operator direction: the ban on stubs, shims, re-export bridges and
duplicate APIs binds `src/`, `src/**/tests/` and `dev/` equally, and test and dev modules
are first-class subjects rather than support scaffolding. Applied here first.

**The bridge shape is essentially absent, measured not assumed.** A forward-only detector
(top-level imports, no definitions beyond `__all__`) over 3,284 package test modules and 697
dev modules found FOUR, all `conftest.py` — which is how pytest shares fixtures, not a
bridge. Nothing to do there.

**The substitution shape was present, and both offenders were this campaign's own.**
`dev/tests/test_monkeypatch_inventory.py` names exactly two files tree-wide, and `git log`
attributes both to commits from this work. The ratchet is absolute — no allowlist, because
the resolution is meant to be removal — and it lives in `dev/tests`, the per-push blind spot
recorded two entries above. So the violations were introduced and never reported, which is
the blindness and the mandate meeting in one place.

**Lock order: a delegating observer is still a patch.** The old module wrapped
`profile_custody_local_lock` to record each path, and its docstring defended this at length
— the wrapper delegated to the real implementation, acquired real file locks, faked nothing.
That defence is true and beside the point: the rule forbids the machinery, not just the
faking, and accepting "it only observes" is how the exception widens.

Real contention answers the same question without touching the code under test. A sibling
PROCESS holds the ROOT lock; a thread here enters the transaction and must block; this
process then acquires the PROFILE lock itself. **That acquisition succeeding is the proof**
— had the transaction taken the profile lock first, it would already be held. The probe is a
real acquisition of the real leaf, and on Windows the primitive opens with no sharing, so a
second acquire refuses even in-process. That property is what makes the probe discriminating
rather than decorative, so it is pinned by its own anti-tautology test instead of assumed.
One real detail had to be handled: the transaction creates the capsules directory only AFTER
taking the root lock, so while blocked the probe had no parent to anchor against and failed
for the wrong reason.

**Secrets channel: enter one call lower rather than substitute the stream.**
`read_secrets_stdin` reaches `sys.stdin.buffer` directly, so it can only be driven by
replacing that stream. It delegates to `_validate_secrets_payload`, which takes raw BYTES
and decides every refusal the module asserts — malformed JSON, wrong shape, and the value
that must never be echoed. The stdin reader's own contribution is the size bound, which no
test here exercises, and the refusal keys passed are the stdin channel's, so the messages
under test are unchanged. Rejected alternatives: a manual `sys.stdin` save/restore is the
same practice with the detector's matcher evaded, which this project explicitly forbids; and
adding a stream parameter would be production surface existing only for a test.

Both proven to bite from outside the repo: inverting the production lock order leaves the
probe unable to acquire, and stripping the accepted-key context fails two of the three
secrets tests. The ratchet is now green — zero monkeypatch machinery in deterministic
production tests.

Lanes 314 integration / 1587 unit (+1, the probe's anti-tautology case).

### A facade gate that could not read half the facades it judged

`dev/tests/test_facade_export_gate.py` was red with nineteen breaks under a serious
headline: *"facade(s) name a symbol that does not exist at HEAD -- a clean checkout will
fail to import these packages even though every working tree resolves them."* That claim, if
true, is a shipping defect. It is false.

**Established before touching anything**, because the gate deliberately compares HEAD
against the working tree and this is a shared worktree full of peers' uncommitted files:
the symbols ARE defined at HEAD (`git grep` against the rev), the facades and their target
modules are unmodified (so working tree == HEAD for them), and a real interpreter resolves
all nineteen. The gate was wrong, not the tree.

**The cause is one the scanner's own docstring anticipated and half-solved.** A lazy facade
resolves inside `__getattr__`, so nothing binds statically and the scanner must model the
dispatch. It modelled the inline form -- `name == "X"` -- by harvesting string constants
from the function body. The tree ships a second shape:

    _REGISTRY_CONTRACT_EXPORTS = frozenset({"UserProfileSelectorIndex", ...})
    def __getattr__(name):
        if name in _REGISTRY_CONTRACT_EXPORTS: ...

The names live at module level; the body holds none. So the scanner read those facades as
resolving NOTHING and reported every export they serve. The tell was visible in the output
and easy to miss: `cadrumo.domain.user_profile` reported six symbols but NOT
`UserProfilePortableExport`, which sits in the same `__getattr__` under an inline
comparison. One facade, two shapes, one of them invisible.

**Why this was worth an iteration rather than a note.** A gate's value is that red means
something. Nineteen standing false positives are how a gate stops being read -- and while it
is red it also buries the next REAL break in its own output, which is the failure mode it
exists to prevent.

**The fix is narrowed deliberately, and that narrowing is the anti-tautology test.** Only
containers `__getattr__` actually references are harvested. Trusting every module-level
string set would let an unrelated constant list vouch for names the dispatch never serves --
turning a repaired gate into a blind one, which is strictly worse than the false positives
it replaced. Both directions are pinned in `dev/quality/tests/`, placed there rather than
beside the gate so the private helper is an intra-package import rather than a new
cross-package private reach; that directory is also in the per-push lane. The gate's own
anti-tautology pass against the pinned broken revision still detects all five known breaks,
so the scan is repaired rather than silenced.

**Two dev/quality failures measured and attributed, not inherited silently.**
`test_doc_privacy` reports operator-identifying tokens in vault documents from other
campaigns (dated 2026-08-01 to 08-15) plus a legal-catalogue TOML whose `reviewed_by` the
grounding rule positively requires -- which is what the gate's allowlist is for, and not
this campaign's call. This campaign's audit file was checked directly and is clean and
unreported. `test_fixture_census` refuses a dynamically-named fixture; the changed files
here define no fixtures at all, and a line-87 scan of both trees finds no match, so it
originates in the census's own manifest set.

Lanes 314 integration / 1587 unit, unchanged.

### A refusal that would not say where

The fixture census refuses any fixture whose effective name it cannot state statically --
correctly, because inventing one would make the ownership manifest a guess. It reported
that refusal as `fixture name at line 87 is dynamic`, with no file.

**How much that costs was measured rather than asserted: six probes, and still no answer.**
A text scan of line 87 across every root the census scans found nothing, because the census
reports the FUNCTION's line while the decorator sits one line above it. A subtree bisect
reported nothing at all -- and that one is the instructive failure. The census refuses a
root carrying no `conftest.py`, so nearly every subtree raised THAT error instead, and the
probe's `if "is dynamic" in str(exc)` filter swallowed each one. **A clean sweep and an
instrument that never ran produced identical output**, which is the exact discipline this
campaign keeps writing down and, here, failed to apply to its own probe.

With the module named, the same run answers in one line:

    src/cadrumo/tests/seeded_isolated_backend_fixture.py:87: fixture name is dynamic

**The refusal turns out to be right, which is worth stating.** That factory derives its
fixture name from its own parameter -- `origin_name = f"{name}_origin"` -- so the effective
value genuinely is a call-site fact. The census DEFERS a bare parameter name and refuses
this, deliberately: its own docstring warns that "treating any non-literal as deferred would
hide genuinely unmeasurable expressions, so only a bare parameter name qualifies." Whether a
name DERIVED from a parameter deserves the same deferral is a real question about the
census's model -- the value is equally not-yet-known -- but widening the carve-out is how a
narrow rule becomes a broad one, so it is left open here rather than decided in passing.

The gate is still red, for the reason it was already red. What changed is that its verdict
can now be acted on, and the deferral carve-out is pinned by its own test so that locating a
refusal cannot quietly become refusing everything.

**Placement follows the same rule as the previous entry**: the tests live in
`dev/quality/tests/`, beside the module they exercise, so reaching its private helpers is an
intra-package import rather than a new cross-package private reach — and that directory is
in the per-push lane, unlike `dev/tests`.

Lanes 314 integration / 1587 unit, unchanged. The two standing `dev/quality` failures are
the ones attributed in the previous entry and are unchanged by this work.

### Deciding a deferral question rather than widening to make a gate green

The located refusal from the previous entry named
`src/cadrumo/tests/seeded_isolated_backend_fixture.py:87`: a factory deriving its second
pytest fixture name from its first, `origin_name = f"{name}_origin"`. The census defers a
BARE parameter -- the call site supplies that -- and refuses a derived expression. The open
question was whether a derived-from-parameter name is equally "not-yet-known" and should
defer too.

**It should not, and the reason is specific rather than conservative.** No caller passes
`name`, so the effective value comes from a parameter DEFAULT composed into an f-string.
Deferring would record the template's own function name while pytest actually registers
`_isolated_backend_origin` — an ownership manifest naming a fixture that does not exist,
which is precisely the guess the census refuses to make. Deferral is only honest when the
binding site can state the value, and here it cannot without the census learning to
evaluate defaults through string composition. Widening the carve-out to turn the gate green
is also how a narrow rule stops being narrow.

**Measured before deciding.** Every consumer was enumerated by symbol: three test modules,
all binding `live_fx_seeded_backend(seed=...)` and none overriding `name`. So the derivation
served a generality nothing uses, and stating both names as parameters with literal defaults
is byte-identical for every caller — confirmed by running all three consumer modules, 26
passed. It uses the census's EXISTING deferral rather than a new rule, and it moves the real
hazard into the signature: a module using this factory twice must now give both names
distinct values, where before the derivation implied that protection without stating it.

**One blocker was hiding another.** With the census clean, the gate advanced to a second
refusal it had never reached: `active_profile_isolated_backend_fixture.py:28` bound at
`application/auth/tests/test_certificate_source_tax_id.py:50`, "cannot uniquely resolve the
nested fixture closure". Different factory, different failure mode, and present all along
behind the first. The substitutable-duplicate check the manifest exists for has therefore
still never run — which is the thing worth knowing: this gate has been reporting a blocked
scan, not a clean population, and the previous entry's locating fix is what makes each
successive blocker addressable instead of anonymous.

Lanes 314 integration / 1587 unit, unchanged.

### The second blocker is a model mismatch, not a bug, and is left for a ruling

The census's next refusal, now reachable, is
`active_profile_isolated_backend_fixture` bound at
`application/auth/tests/test_certificate_source_tax_id.py:50`. The cause is exact:
`_closure_record_for_candidate` requires EXACTLY ONE nested `@pytest.fixture` per factory,
and this factory branches on `scope` and returns a module-scoped closure or a
function-scoped one.

**Refusing is correct, not lazy.** `_factory_binding_record` reads scope and autouse off the
closure, so picking either arbitrarily would record a lifecycle the binding does not have --
the same "do not invent a value" principle behind the dynamic-name refusal.

**Both real fixes are structural, and neither was taken here.** Teaching the resolver to
evaluate the return branch means simulating control flow against argument defaults, which is
a new capability rather than a repair. Splitting the factory so each has one closure touches
a fixture 31 modules bind, and the one module-scope consumer reaches it through a wrapper
that exists specifically so the shared arguments cannot drift -- so the branch would move
rather than disappear. Choosing between those is a design decision about the census's model,
not a defect to fix in passing, and the directive's own rule applies: do not widen a
narrow carve-out to turn a gate green.

**What was done instead is the previous entry's lesson applied again.** The refusal named the
factory and the binding but not what it FOUND. It now lists the candidate closures with
their scopes and lines and states why the shape is unresolvable, so the next person meets a
decision rather than a puzzle.

**No test pins that message, deliberately.** It is a diagnostic on an error path that exists
only while this factory is unresolved; a test asserting its content would have to be deleted
alongside the condition it describes. A test that expires on the fix is worse than none. The
behaviour is unchanged -- it still refuses -- and the message was verified against the live
gate.

**Two process notes.** A grep for the swept change reported absent because the pattern did
not allow for the f-string braces between the tokens; reading the actual line showed HEAD was
correct. And the added detail was 132 characters -- over the limit -- and reached main
through a peer sweep before ruff ran on it here. That lint error was live and is fixed; it is
the second time this session that a sweep has published work before its own verification
finished, which is an argument for running the linter BEFORE the lanes, not after.

Lanes 314 integration / 1587 unit, unchanged.

### Two private reaches promoted, and a bigger shim question surfaced rather than answered

The import-hygiene ratchet is red across six peer packages, which is an operator matter --
but the sites inside THIS domain are not. Filtered to storage, user_profile and cli/_config,
exactly two undocumented test-only private cross-package imports exist, and both are now
fixed by promotion, which the mandate names as the fix.

**One bought nothing.** `test_bundle_encryption_kdf_window` reached into
`domain.user_profile._values` for `UserProfileFact` and `UserProfileRecord`. Both were
ALREADY in that package's `__all__` -- measured before touching it -- so the private path
was pure habit. One import line.

**The other is a real cross-layer contract that lacked a public name.**
`test_sealed_archive_member_bound` compares the storage reader's member ceiling against the
application writer's payload cap. The two constants are deliberately separate: the reader is
an ADAPTER, and importing the application layer would invert the hexagonal dependency, so
the adapter keeps its own value and a test holds them equal. That design is right, and it
means the coupling test needs a public name to compare against. Promoted to
`PROFILE_CAPSULE_ARCHIVE_MAX_PAYLOAD_BYTES`, documented at its canonical home as the
cross-layer contract it is -- including why the adapter must NOT import it -- and the
reader's comment now cites the public name.

**The bigger find is deliberately not acted on.** The same run surfaced
`test_family2_delegate_wrapper_shims`, red on roughly thirty-four callables in
`application/user_profile/_custody_ports.py`. The gate's message is this campaign's mandate
almost word for word: "a public callable whose whole body re-calls another package's symbol
with its own arguments unchanged, so it owns no decision and only adds a second import path
to a symbol that already has a canonical home."

That module's own docstring answers back: it exists so "the custody surface has exactly one
application-owned door", binding narrowed ports to the persistence facade so consumers do
not reach into adapters themselves. **Both statements are defensible, and they contradict.**
A shipped gate says delete the indirection; a deliberate hexagonal ports boundary says the
indirection IS the design. Thirty-four callables with many consumers is not a question to
settle in passing, and the resolution is not obvious: documenting them as reasoned
exemptions is as plausible as deleting them. Recorded for a ruling rather than decided.

**Process note, applied not just recorded.** Ruff ran BEFORE the lanes this iteration and
caught two errors: an `__all__` left unsorted by a naive alphabetical insertion, and an
import block reordered by the shortened path. Last iteration an over-long line reached main
because a peer sweep published the work before the linter ran here; running it first is the
cheap fix and it paid immediately.

Lanes 314 integration / 1587 unit, unchanged.

### Measuring the custody-ports contradiction instead of arguing it

The previous entry left thirty-four flagged forwarding wrappers as a standoff: a shipped
gate says delete them, the module's docstring says the indirection IS the design. That was
stated from the two claims without reading the wrappers. Reading them splits the population
and dissolves most of the standoff.

**Twelve are methods implementing declared Protocols.** For those the gate's own remedy --
"point the consumers at the owning package's facade and delete the wrapper" -- cannot be
followed: a method that satisfies an interface is the binding, and deleting it removes the
implementation rather than an alias. That is a distinct class the flag does not distinguish,
and it is the strongest part of the module's defence.

**The module is mixed, which the flag correctly reflects.** `profile_zeroise` is a pure
forward to `custody.zeroise` whose only addition is a prefix. `profile_is_authentication_
failure` -- a TypeGuard that recognises adapter refusals "without leaking adapter types" --
is NOT flagged. So the gate discriminates between aliasing and deciding, and the module
genuinely holds both.

**Twenty-two are module-level functions, and exactly one has no consumers.** Counted per
symbol across the tree: the rest carry 2 to 57 callers, so deleting them is the contested
design question and stays open. `profile_custody_read_member` had ONE reference in the whole
repository -- its own definition -- and no facade export.

**Its docstring made a security claim, which was checked before deleting rather than after.**
It said the anchored, bounded, no-follow read "matters MORE for the source an operator hands
to `config profile restore`, which is the less trusted of the two". If nothing called it, the
question is whether restore reads members some weaker way. It does not: restore uses the
OPTIONAL sibling, equally anchored and bounded, whose call site explicitly rejects the
"``is_file()`` then ``read_bytes()``, which follows a symlink" shape. The property holds; the
wrapper was residue whose prose described what its sibling does.

The sibling documented the TOCTOU reasoning but not the untrusted-source one, so that
paragraph moved there. **Deleting code should not delete the reason it existed** -- the
rationale outlives the residue, and this is the second time this campaign has found a
security argument living only in prose attached to something removable.

Flagged wrappers 34 -> 33. The remaining question is unchanged and still needs a ruling; what
changed is that it is now a question about 21 consumed functions rather than 34 mixed items,
with the 12 Protocol methods excluded on evidence.

Lanes 314 integration / 1587 unit, unchanged. Ruff ran before the lanes again: clean.

### Using a gate's own escape hatch, and refusing to use it for the real question

The previous entry split the 34 flagged wrappers into 12 Protocol methods and 22 module-level
functions. This entry acts on the half that is decidable and refuses to act on the half that
is not.

**The 12 are documented as exemptions, through the mechanism built for exactly this.** The
family's stated harm is "a second import path to a symbol that already has a canonical home".
For an instance method on a port adapter that harm cannot arise: the consumer holds the PORT
object and calls through the interface, so there is no import site to move -- and the family's
own remedy, "point the consumers at the owning facade and delete the wrapper", would delete
the Protocol implementation rather than an alias. Both classes were verified to be live port
providers, instantiated and returned as the default, and both are documented as adapting the
persistence facade to an application-owned Protocol. Pure delegation is what such an adapter
looks like when the facade already matches the port.

The mechanism is well designed and was used as designed: each exemption carries a required
reason, a sibling test refuses a blank one -- *"an exemption without a stated reason is a mute
button, not a judgement"* -- and the check is EQUALITY, so an entry that stops being a wrapper
fails too and a dead slot can never hide a live one. The reason guard was proven to bite by
blanking one reason from outside the repo.

**The 21 module-level forwards are deliberately left undocumented.** They are the actual
design question -- whether that port layer should exist -- and answering it by writing
exemptions would be precisely the mute button the reason test exists to prevent. An escape
hatch used on the case it was built for is judgement; the same hatch used to silence an open
question is evasion, and the difference is not visible in the diff.

The gate stays red, which is correct, and now names 21 actionable items instead of 33 mixed
ones. That is the same shape as the census work two entries ago: the value delivered is not a
green gate but a verdict someone can act on.

Lanes 314 integration / 1587 unit, unchanged.

### Removing the forwarding port layer: slices 1-4, and three mistakes worth keeping

Operator ruling: the codebase carries no shims or re-exports, so the twenty-one module-level
forwarding wrappers in `_custody_ports.py` go. Sixteen are now gone across four slices;
five remain, all in the heavy tail. The twelve Protocol-adapter METHODS stay, exempted on
evidence in an earlier entry.

**Two of the first three had no callers at all** -- forwards registered in the package
facade's TYPE_CHECKING block AND its lazy map, absent from `__all__`, called by nothing.
Dead weight in three places at once, which is what a forwarding layer decays into once its
consumers move on.

**A wrapper's prose is not automatically worth preserving.** `profile_custody_read_optional_
member` carried a security rationale that an earlier entry had deliberately moved INTO it.
Checking the call site before deleting showed `_require_member` already stated it better --
the restore source is the less trusted capsule kind and previously took a weaker
`is_file()`-then-`read_bytes()` read. So that move had been redundant when it was made.
Check the destination before relocating prose to save it.

**Three mistakes, each caught by something other than my own reading:**

- *Text-span deletion is unsafe in a file mixing functions and classes.* Taking each
  function as "start of `def` to the next `def`" swallowed three adapter CLASSES that
  followed one of them, leaving their factories referencing undefined names. Ruff caught it
  in seconds. The redo uses exact AST line spans and asserts the classes survive.
- *A wrapper can have an INTERNAL caller.* `load_profile_custody_password_material` was
  called by another function in its own module. The post-edit assertion that the name was
  fully gone fired BEFORE the file was written, so nothing was left half-edited -- the value
  of asserting the end state rather than trusting the edit.
- *Format the files you changed, not the directories they live in.* `ruff format` over whole
  packages reformatted fifteen files nobody had asked me to touch, several belonging to
  peers. All fifteen were restored so the tree stays as its owners left it.

**Attribution, three times, none of it assumed.** A `bucket_maintenance` retention failure
traced to a peer's UNCOMMITTED `config_reset` rework re-deriving retention against the live
assessment. Sixteen failures across `application/tests`, `workflow/tests` and `custody/tests`
were read rather than counted: pydantic constraint tightenings on
`LedgerPreflightIssue.transaction_id` and `ProjectionActiveProfile.profile_id` whose fixtures
now violate them. None mentions a session or custody symbol, and all sit outside the domain
lanes. The one attribution attempt that FAILED is worth recording too: reverting a single
file to compare against HEAD left the change set half-applied and the module unimportable,
so the comparison proved nothing.

**Precedent found mid-work:** peer commit `3f1a947674` already dissolved an entire
`application/profile_custody` package -- 1,176 lines -- into user_profile. This is a
continuation of an established pattern here, not a new direction.

The two `parse_*` forwards are held for their own slice: their names are IDENTICAL to the
adapter functions they call, so a name-based rewrite risks silently altering the adapter's
own internal uses.

Flagged forwarding wrappers 21 -> 5. Lanes 314 integration / 1589 unit.

### The forwarding port layer is gone: task complete

All twenty-one module-level forwarding wrappers in `_custody_ports.py` are removed across
six slices. `test_family2_delegate_wrapper_shims` now names NOTHING from that module. The
twelve Protocol-adapter methods remain, exempted on evidence rather than convenience. Lanes
held at 314 integration / 1589 unit throughout.

**The last slice was the hardest, and every problem in it was caught by a machine rather
than by reading.** Three shapes defeated pattern-based rewriting:

- A function-LOCAL import, indented inside a function body, invisible to a column-anchored
  pattern.
- A single-line multi-name import (`from .. import A, B`), which a name-level substitution
  corrupted into `from .. import master_key.current_active_bucket_session`. `ast.parse`
  refused it before a single byte was written.
- `profile_close_bucket_session` passed as a VALUE to `ExitStack.callback` rather than
  called, so a rewrite keyed on `name(` left it standing.

The fix was to stop pattern-matching imports and rewrite the statements by AST line span,
which handles all three. **The general lesson: a name has more shapes than a call.** Import
membership, indented local import, bare reference, and same-name aliasing each need a
different treatment, and only the parser knows which one it is looking at.

**Identical names turned the biggest item into the cheapest.** `profile_session_path` had 57
call sites -- and forwarded to an adapter function of exactly the same name, so changing the
import SOURCE left every call site untouched. Measuring the shape before estimating the work
inverted the order entirely: the 57-site symbol took one line, while a 24-site one needed
every reference rewritten.

**Evidence the layer was not doing its job.** Three user_profile TEST modules already
imported these names straight from the adapter facade, and two wrappers had no callers at
all while still being registered in the package facade in two places. The "one
application-owned door" the module's docstring described was not the door the package
itself used.

**Attribution stayed disciplined to the end.** Sixteen failures in `application/tests` and
`workflow/tests` were grouped before AND after the final slice -- same modules, same counts
-- so the slice added none. They remain the peer constraint-tightening on
`LedgerPreflightIssue.transaction_id` / `ProjectionActiveProfile.profile_id` plus the
uncommitted `config_reset` retention rework.

**Running formatters and fixers over DIRECTORIES was the recurring self-inflicted cost.**
Twice it modified files belonging to peers -- fifteen by `ruff format`, seven by
`ruff check --fix` -- and both sets were restored. Both tools are now run on the explicit
list of files a slice changed.

**What the gate says next, and it is a different scope:** twelve forwarding wrappers survive
elsewhere -- `adapters/persistence/profile/_filing_runtime`, `_modelo_runtime`,
`application/evidence`, `flows`, `modelo`, `domain/iva`, `domain/transactions` and one more
in `user_profile/_custody_transactions`. They belong to other surfaces and are not part of
this bounded task.

### The last forward in this domain, and where the boundary now sits

`_custody_transactions.validate_sha256_digest` forwarded to
`core.hashing.validate_prefixed_digest`, relabelling one keyword on the way -- `subject=`
passed as `field_name=`. The family-2 contract anticipates exactly that and rules on it:
"A keyword may be RELABELLED and the call is still a forward: relabelling an argument is not
translating it." Three call sites, two of them inside the owning module. The value reaching
the validator is unchanged, so the refusal message is unchanged.

**`application/user_profile` and `adapters/persistence/storage` now contain no forwarding
wrappers at all.** That is the whole of this campaign's surface.

**The twelve the gate still reports belong to other owners** -- `persistence/profile`'s
filing and modelo runtimes, `application/evidence`, `flows`, `modelo`, `domain/iva`,
`domain/transactions`. Each is the same shape and each will want the same treatment, but
none is storage or custody, and taking them would repeat the drift this campaign was
explicitly bounded to stop.

**What the six-slice removal is worth as a general result.** Twenty-two wrappers, roughly
264 call sites, zero behaviour changes, lanes flat at 314 / 1589 from first slice to last.
Two of the wrappers had no callers whatsoever while still being registered in the package
facade in two places each; three test modules inside the owning package were already
bypassing the port they were supposed to use. A forwarding layer does not fail loudly -- it
decays into a second name that some callers use and others do not, and the only signal is a
gate counting them.

### The same rule written as assignments

Removing the forwarding FUNCTIONS did not finish the job, because the module carried the
identical shape as module-level bindings: four capsule ceilings and one warning type bound
as `PROFILE_CAPSULE_* = custody.PROFILE_CUSTODY_*`. One decision, two names, and a
vocabulary split between CAPSULE and CUSTODY for the same value.

**This is the milder shape and worth distinguishing from the one already gated.** An alias
cannot diverge in VALUE the way the duplicated ceiling definitions in
`test_custody_ceilings_have_one_home` did -- that gate's whole finding was two independent
definitions agreeing until someone raised one. A reference binding cannot drift like that.
What it costs is a second import path and two names for one contract, which is what the
no-re-export rule forbids on its own terms rather than because of a divergence risk.

**One of the five was public vocabulary nobody asked for.**
`ProfileRecoveryArtifactWarning` was exported from the `user_profile` package facade in two
places, and no consumer outside that package used it. The package was publishing a renamed
adapter type into its own public surface for its own internal use.

**A scan of the whole domain found only these five.** The other eleven module-level
`NAME = other.ATTR` bindings are a different shape entirely -- destructuring fields off a
namespace record (`...STORAGE_NAMESPACE.schema_version`), a sentinel bound to `date.min`, and
SQLAlchemy's `metadata = Base.metadata`. Reading each rather than counting the pattern is
what separated them; a rule applied to the AST shape alone would have "fixed" eleven things
that were not aliases.

`application/user_profile` and `adapters/persistence/storage` now carry neither a forwarding
wrapper nor a re-export alias. Lanes 314 integration / 1589 unit.

### Two remaining no-shim axes, both measured clean

With the forwarding wrappers and re-export aliases gone, two shapes from the mandate were
still unswept in this domain. Both were checked and neither is present.

**Duplicated fixture facades.** Four profile/storage fixture factories exist, and three of
them call themselves "Canonical", which reads like three canonical homes for one concern.
They are not. They wrap three genuinely different primitives, and each primitive's docstring
states its own boundary against the others: `isolated_sessionless_storage_root` starts NO
session and exists for cold-start and no-session assertions;
`isolated_profile_storage_root` provisions no bucket, so the creation path itself is the
system under test; `isolated_runtime_profile` provisions the full bucket, manifest, wrapped
DEK, active route and session. The fourth factory is a seed-once-per-module variant for
suites whose setup is expensive. Three points on a spectrum of how much world exists, plus
one lifecycle variant -- the opposite of duplication, and documented as such before anyone
asked.

**Dev tooling re-implementing a src primitive.** Several `dev/` modules call
`hashlib.sha256(...).hexdigest()` directly while `core.hashing.sha256_hex` exists. That is
stdlib usage, not a re-implementation of project logic -- `sha256_hex` is itself a thin
wrapper over the same call. Flagging it would be the cry-wolf failure this campaign has
repeatedly guarded against, and the modules are corpus and docs tooling outside this domain.
The shape worth finding here would be dev re-deriving project LOGIC, such as its own
registry loader or path-containment rule; none was found.

**Position.** `application/user_profile`, `adapters/persistence/storage` and
`entrypoints/cli/_config` carry no forwarding wrappers, no re-export aliases, no forward-only
bridge modules and no duplicated fixture facades. The remaining named items are decisions
rather than defects: the profile-bundle import half, the import-hygiene ratchet at 108 vs 69
across six peer packages, the five unreachable `dev/packaging` cases, and the twelve
forwarding wrappers in other owners' surfaces.

### A JSON-contract field that is null 634 times out of 634

Probing the "easy to operate from the CLI" half of the goal led to `ErrorCode.runbook_id`,
the field that would point an operator at guidance for a refusal. Measured across the live
registry rather than grepped:

- **634 registered error codes project-wide. Zero carry a `runbook_id`.**
- 636 source sites pass `runbook_id=None` explicitly -- every registration, without exception.
- It is declared TWICE, on `ErrorCode` and on `ErrorEnvelope`, and copied between them at
  `_registry.py:369`, so it is rendered into the machine-readable error document of every
  command that refuses.
- Nothing reads it. There is no populate path and no consumer.

The domain measurement that started this is a subset with no separate meaning: all 88
storage, custody and config-CLI codes lack it because ALL codes do. Reporting it as a
domain gap would have been wrong, which is why the project-wide count was taken before
saying anything.

**By the project's own rule this is a design-only shell** -- "ship working behavior,
executable validation and tests together", not a declared surface awaiting an
implementation. An operator, or the autonomous agent this CLI is written for, reads
`runbook_id: null` on every refusal it will ever see.

**Not acted on, deliberately.** The two honest resolutions are to populate it or to remove
it, and both are wide: removal is a change to the error-document JSON contract that every
command shares, plus 636 edits across an error registry the whole project writes into;
population is a documentation programme, not a refactor. Either is a decision about the
shared error contract rather than a defect inside this domain's boundary, and this campaign
has already been bounded once for drifting into work like that.

Recorded with the counts so the decision can be made on measurement. **No production change
this iteration.**

### Driving the CLI instead of reading it

Several iterations of reading code had found nothing, so the instrument changed: run the
real command tree against an isolated storage root and see what an operator sees. That
found something reading had not.

**`config profile archive export` took `--to` for its destination.** The other two export
verbs in this CLI -- `ledger export` and the modelo export -- both take `--output`. One
concept, two operator-facing names, and this verb was the odd one of three.

**`--to` is worse than inconsistent here.** This CLI already uses `--to` as the END of a date
range, paired with `--from`, in the overview verbs. The same flag meant a date bound in one
place and a file path in another. The rename removes an overload, not just a variance.

**The input side was checked and deliberately left alone.** `--file` is the mandated name for
the one local file a verb READS, so `archive inspect --file` is correct and stays. `--output`
is where a verb WRITES. An early reading of this as a contract violation was wrong, and
measuring the rule's actual wording -- it governs INPUT options -- is what corrected it
before anything was changed. The locale key was already
`cli.config.profile.archive.export_out_help`, so the help text needed no edit at all; the
option had been conceptually "out" since it was written.

**The conformance gate earned its place.** It caught a documented sequence contract still
carrying `--to`, which is exactly the surface the CLI-contract rule warns a rename must sweep
by hand. Here the gate swept it instead.

**Two measurement notes.** A filtered listing of the command tree omitted `config profile
edit` and briefly looked like a dangling doc reference -- the verb exists; the filter did not
include the word. And `docs/cli/config/profile.rst` appeared stale mid-iteration and then was
not: it is generated, and a peer's commit regenerated it WHILE this rename sat uncommitted in
the shared tree, so it picked the new name up. Regenerating rather than hand-editing was
still the right move; the page simply needed no write by the time it was checked.

Lanes 314 integration / 1589 unit.

### The agent-facing refusal contract, verified by driving it

This CLI's operator is an autonomous agent, so the JSON error envelope is the real
operability surface. Driven against a cold storage root rather than read:

- The envelope carries the full spine on every refusal: `schema_version`, `command`,
  `status`, `notices`, `error`, `active_profile`.
- Refusals carry a registered `code` and a `retryable` answer.
- Where a REMEDY exists, the error carries a structured action: `censo pull` without a
  profile returns `action_id: operator.profile.create` with its `cli_path`, so an agent
  learns the exact command to run without parsing prose.
- Where no remedy exists, the refusal does not merely omit the action -- it declares WHY,
  through `no_recovery_outcome`, alongside `conditionality` and a `failed_condition_id`.

**Two readings were tested and both dissolved**, which is the result worth recording.
`delete <unknown>` returns `action: null` while its TEXT names a next command, which looked
like a human-gets-guidance / machine-gets-nothing asymmetry. It is not: the same guidance is
in the JSON `message`, and the structured channel correctly reports no RECOVERY action
because listing profiles does not make that call succeed. Then `no_recovery_outcome:
operator_decision` looked like a silent default -- it IS a default parameter value in several
precondition helpers -- but the distribution refutes the concern: TERMINAL 16, SAFETY 9,
OPERATOR_DECISION 18 across the tree, with per-domain defaults (`SAFETY` in calculations and
live). The vocabulary is genuinely exercised, unlike `runbook_id`, which is null 634 times
out of 634.

**One judgement left to its owner.** `delete <unknown>` is classified `operator_decision`
because that is the default in `cli_exception_preconditions`, not because someone chose it
for this refusal. TERMINAL is arguable -- nothing makes that exact call succeed. It is
defensible either way and belongs to whoever owns the CLI refusal vocabulary.

No defect found. Recorded so this axis is not re-probed: the domain's refusals are
well-formed, discriminable, and actionable for the operator they were written for.

### The non-interactive creation path, and a third suspicion that dissolved

Driving the flow end to end, `config profile create --secrets-stdin` refuses with "unknown
option". Against the secrets-channel contract -- "`--secrets-stdin` and `--secrets-fd` are
the channels a caller with NO terminal must use, and for this CLI that caller is the ORDINARY
one" -- that reads like an agent being unable to perform the very first operation. It is not.

`create` is a lazy WIZARD leaf serving two audiences through one verb, and the scripted arm
is explicit about it: a script or agent passing field flags or `--quiet`/`--accept-defaults`
gets "a JSON envelope with no screen", routed to
`register_profile_from_scripted_invocation`. That path resolves the credential from
`CADRUMO_SECRET_PASSPHRASE`, described in its own module as the sanctioned secrets
environment surface "so creation and login read one" -- confirmed: `_login_session` and
`preflight` read the same setting. And the module states the security reason `--secrets-*`
is absent here: **"The passphrase is never accepted as an argv value, on this verb or any."**
An argv secret is visible in a process listing.

`restore` carrying `--secrets-stdin` while `create` does not is therefore a distinction, not
a drift: the ambient environment passphrase is the LOCAL profile's, while restore needs the
ARCHIVE's, which may differ -- an export can be sealed under `--recovery-wrap-passphrase`.
Two secrets, two channels.

**Three suspicions across two iterations, all dissolved on measurement**: the text/JSON
guidance asymmetry, the `operator_decision` default, and now the missing secrets channel.
Each looked like a defect from one angle and was answered by a design decision written down
at the site. Set against the one real find in the same sweep -- `--to` versus `--output` --
the ratio is worth stating plainly: driving the CLI is a productive instrument, and most of
what it surfaces in this domain turns out to be deliberate.

The custody CLI surface is recorded as verified across refusals, scripted creation and
secrets channels. No defect found.

### Closing position

The last unprobed marker slice is empty: `perf` is excluded from every per-push lane and runs
only in the dispatch-only full lane, which made it a candidate for hidden failures -- but this
domain declares NO perf-marked tests at all (1,950 collected, 0 selected). Nothing was hiding
there. With the serial slice already recorded healthy, the marker axes are exhausted.

**What this campaign leaves behind.** `application/user_profile`,
`adapters/persistence/storage` and `entrypoints/cli/_config` carry no forwarding wrappers, no
re-export aliases, no forward-only bridge modules, no duplicated fixture facades and no
monkeypatch machinery. Twenty-two forwarding wrappers and five re-export aliases were removed
across seven slices, roughly 264 call sites repointed, with the domain lanes flat at
314 integration / 1,589 unit from the first slice to the last. Real defects fixed earlier in
the sweep include a fail-open redaction exemption, two pointer-contention races, a
retryability flattening that told an agent to rename a profile that did not exist, a
dot-segment path traversal, a drive-qualified capsule path, a keystore join that accepted an
unchecked filename, and an operator-facing refusal that printed a message key.

**Where the remaining value is, and it is not here.** Four items are named, measured and
waiting on a decision rather than on effort: the profile-bundle IMPORT half (the product
writes passphrase-encrypted bundles nothing can read back -- the one genuine product-level
defect still open); the import-hygiene ratchet at 108 sites against 69 documented across six
peer packages; five `dev/packaging` cases reachable by no lane; and `runbook_id`, null 634
times out of 634 in the shared error contract. Each was left alone deliberately: acting would
mean either overriding an owner's judgement or making a broad mechanical change to a surface
this campaign does not own.

**The honest read on continuing.** The last four iterations produced one real defect
(`--to` versus `--output`) against three suspicions that dissolved on measurement. That is a
sound instrument meeting a sound surface, not a stalled search -- but it is a poor use of
further iterations. The campaign is complete on its stated goal.

### The bundle export told the operator it had a backup

The profile-bundle import half has been carried as "needs an operator ruling" for many
iterations. Re-examining it corrected that framing and found a real defect next to it.

**The keep-or-delete decision was already made, in the tree.** `test_no_exported_contract_is_
never_used` carries a reasoned entry for `register_imported_profile_bundle`: *"the product
writes passphrase-encrypted bundles and nothing in it reads them back, which the symbols show
plainly (encrypt_* is live, decrypt_* is not). Kept because deleting it would remove the only
code that could make those exports restorable."* That is the same finding this campaign kept
reporting, reached independently and settled. What remains open is only whether to BUILD the
import verb, which is roadmap rather than a defect.

**The defect is what the export says while that half is missing.** The TUI profile manager's
export is live -- `_manager_actions.py:518`, reached through a function-local import, which is
why an earlier symbol sweep here missed it -- and `aeat app maintenance reconcile` cleans up
its crash orphans. It collects a destination and a passphrase, writes a `PORTABLE_TRANSFER`
bundle, and reported: **"Encrypted copy written to <path>."** Nothing more.

An operator reads "encrypted copy" as a backup. It is not one. The product has TWO export
paths and only one is restorable: `config profile archive export` produces a sealed archive
that `config profile restore` reads back, while this bundle has no reader at all. Nothing
distinguished them at the moment of use, and the failure mode is silent and delayed -- it
surfaces when someone tries to restore.

The message now states the limitation and names the path that does work, in all four
catalogues through the locale CLI. **This needed no ruling**: it neither builds nor deletes
the import half, it stops the product claiming something it cannot do.

**Method note.** A check of whether the strings had landed reported zero for all four locales
and was wrong: the catalogue wraps long values, so the searched phrase spanned a line break.
Reading the committed value directly showed all four present. Same lesson as the truncated
searches earlier in this campaign -- a pattern that cannot match is indistinguishable from an
absent value.

Lanes 314 integration / 1592 unit; locale parity and translation-honesty gates green.

### The recovery instruction points at a file nothing can write

Reading the rest of the unused-export register -- the same source that settled the bundle
question last iteration -- surfaced the MIRROR of that defect, on a safety-critical path.

`config profile restore --artifact <file>` documents itself to the operator as:
*"Archivo de artefacto de recuperación; úselo cuando se haya perdido la contraseña del
perfil."* -- use this when the profile password has been lost. That is the last-resort route
for a locked-out operator.

**Nothing in the product writes that file.** Traced end to end rather than assumed:

- `application.user_profile.export_profile_recovery_artifact` -- three test modules, no
  shipped caller.
- The adapter it delegates to, `custody.export_profile_custody_recovery_artifact` -- one test
  module plus facade re-exports, no production caller.
- The READER is live: `prove_profile_recovery_artifact` sits on the restore path, and the
  register states the format is sound -- *"a missing export door, not a dead format."*

So this is the exact inverse of the bundle gap fixed last iteration. There, the product WRITES
a file it cannot read, and an operator believes they have a backup. Here it READS a file it
cannot write, and an operator following the CLI's own recovery instruction has nowhere to
obtain one. The 24-word phrase shown at enrolment does not close it: the help says the phrase
is used WITH `--artifact`, so the words alone are not a route.

**Deliberately not fixed here.** The obvious move -- make the `--artifact` help honest about
the missing door -- would edit operator-facing text on a surface the register says "another
owner is rebuilding", and the two restore entry points are recorded as part of that same
rebuild. Correcting help that an in-flight rebuild is about to change would collide with
their work, and unlike the bundle warning there IS active work here to collide with.

**What the rebuild owner needs to know**, and may not: `restore --artifact` currently
advertises a recovery route with no producer, on the path an operator reaches only after
losing their password. If the rebuild lands the export door, the gap closes on its own. If it
does not, the help is a promise the product cannot keep.

No production change this iteration.

### Settling an "unclassified" register entry, narrowly

The unused-export register carried `bound_profile_record_session` as explicitly undecided:
*"used by eight TEST modules as their binding fixture and by no production caller. That shape
-- heavily used by tests, unused by the tree -- is what a test-support helper looks like, and
its home is likely the tests package rather than the boundary; unclassified pending that
judgement."*

**The measurement narrows the question rather than confirming the guess.** All eight test
consumers import it through the PRIVATE module path, `.._profile_record_repository`, which is
an intra-package import the architecture rules explicitly allow. So the tests are not reaching
across a boundary at all, and the function's LOCATION is not the problem. What has no
justification is the public contract wrapped around it: three facade registrations --
TYPE_CHECKING import, lazy map, `__all__` -- for a name no production code loads, inside the
package or out.

So the fix is de-export, not relocation. That removes exactly the unearned part, leaves the
helper where a future production caller would find it, and is reversible if one appears.
Moving it into the tests package would decide something stronger -- that it may never have a
production caller -- on evidence that only shows it has none today.

**The gate made the second half of the change mandatory, which is good design.**
`test_no_record_outlives_the_name_it_describes` fails on a record naming a name the facade no
longer exports, so the register entry had to go in the same commit. Proven by re-adding the
entry from outside the repo: the guard fires. An allowlist that cannot go stale is worth more
than one that merely holds reasons.

Lanes 314 integration / 1592 unit.

### Four unearned re-exports, chosen by the strictest bar

The de-export in the previous entry set a usable test, so it was applied to the storage
facade: which exports have NO consumer anywhere -- production or test -- outside the module
that defines them? Four of 255.

All four turned out to be `core` symbols the storage facade re-exported: `CorpusManifestDiff`
(`core.corpus_manifest`), `DEFAULT_LOCK_TIMEOUT` (`core.locks`), `RetentionPolicy` and
`default_policy_table` (`core.classification`). Each gave a name with a canonical home a
second import path, and not one consumer across `src/` or `dev/` used it. Removed, and
verified after: none resolves from the storage facade, `RetentionPolicy` still resolves from
`core.classification`, and the facade imports cleanly at 251 exports.

**This is deliberately not the facade narrowing this campaign declined.** That work was
sweeping over-exported names with real internal consumers -- a broad mechanical change over
dozens of symbols. This is four names with zero consumers by measurement, the same bar that
settled `bound_profile_record_session`. The distinction is the evidence available per symbol,
not the size of the diff.

**One measurement caution worth recording.** A display grep for `RetentionPolicy` matched
`RetentionPolicyError` and briefly suggested the symbol lived in storage's `errors.py`. The
detector itself was correct -- it used a word boundary -- but the confirming grep did not,
and the two disagreed. The exact search found it in `core.classification`. A confirming
command that is looser than the detector it is confirming will invent disagreements.

**A test-isolation defect found on the way, not caused by this change.**
`test_execution_policy` fails order-dependently: different tests fail on different runs, all
pass in isolation, and it reproduces under `-n0`, so the `serial` marker would not help --
the dependence is on ordering WITHIN one process, not on xdist workers. The module reads the
process-global Typer command tree, so something earlier in a run leaves that tree modified.
It appeared in failures before this change as well. Recorded rather than chased: finding the
polluting test is a bisect, and the execution-policy surface is not this campaign's.

Lanes 314 integration / 1612 unit sequential.

### Correcting the previous entry: the execution-policy failure was not order dependence

The previous entry recorded `test_execution_policy` as carrying an order-dependent defect,
reasoning that it reads the process-global Typer command tree and that something earlier in a
run leaves that tree modified. **That mechanism was inferred from a single non-reproducing
failure, and measurement refutes it.**

Bisected properly this time, all sequential (`-n0`), all with the lane's own marker
expression:

- storage package, then the failing module: **1,196 passed**
- user_profile package, then the failing module: **330 passed**
- the `_config` package alone: **95 passed**
- the FULL three-package lane, the exact command that failed: **1,613 passed**

`pytest-randomly` is not installed, so collection order is deterministic and the original run
should have reproduced. It did not. The remaining explanations are environmental: this
worktree's backing share is documented as unreliable under concurrent I/O, and peers commit
into this tree continuously, so a file can change underneath a running session -- which for a
test asserting on rendered CLI help is enough to flip a result.

**Two things to carry.** First, the campaign's own rule -- re-run before blaming the code --
was applied to the individual test but not to the CLAIM: the isolation pass proved the test
was innocent, and I then published a mechanism for a failure I had not shown was
reproducible. Diagnosing why something failed is a separate act from establishing that it
fails at all, and the second has to come first.

Second, the correction is worth more than the original note: the domain lane is a RELIABLE
instrument. Every "lanes green" statement in this campaign rests on it, and a genuine
order-dependence would have undermined all of them. It does not exist.

Also corrected: the previous entry called the execution-policy surface "not this campaign's".
`entrypoints/cli/_config` is one of the three domain lane paths. It is this campaign's, which
is precisely why the claim was worth re-testing rather than leaving recorded.

No production change this iteration.

### The blocked closure resolver is rotting a committed artefact

The fixture-ownership manifest is generated, and its `[manifest]` header states three totals
about the records beneath it. Measured against the file:

    header:  fixture_count = 540   retained_current_owner = 257   retained_divergent = 283
    actual:  536 records            255                            281

Every number is exactly four high -- the signature of a write that did not finish, not of a
single miscount.

**Nothing catches it, and the reason is a defect already recorded here.** The manifest's
verifier rebuilds the census and compares it to these records, but it refuses first, at
`active_profile_isolated_backend_fixture` -- the factory returning a different nested closure
per `scope` argument. Every downstream check that gate performs is unreachable behind that
refusal, so the drift is invisible.

**The regeneration path is blocked by the same refusal.** `python -m dev.quality.
fixture_ownership --write` fails identically. So the artefact cannot be brought back into
agreement with itself until the closure question is answered, and it will keep drifting as
fixtures are added and removed.

That materially changes what the closure question is worth. It was recorded twice as a design
choice someone should make -- teach the resolver which argument selects the closure, or give
the factory one closure. It is now a blocker actively preventing a committed artefact from
being regenerated, with no gate able to report the resulting rot.

**A backstop was written and then deliberately NOT committed.** A check reading only the
committed TOML -- no census, no source walk, no closure resolution -- detects the drift
immediately and would keep working while the deeper gate is blocked. It is correct and it is
red, and `dev/quality/tests` is in the per-push lane, so committing it would fail every
peer's next push over a defect they did not introduce and cannot fix without answering the
design question first. Enrolling a red gate in a per-push lane is the one thing this campaign
has consistently refused to do, and being the author of the gate is not an exemption. It can
land the moment the manifest is regenerable.

No production change this iteration.

### Unblocking the census: the factory now has one closure

The closure refusal was deferred twice as "a design decision someone should make". The
previous entry changed what it was worth by showing it also blocked manifest REGENERATION,
so the artefact was rotting behind it. That justified doing the work.

**The split.** `active_profile_isolated_backend_fixture` selected between two nested fixtures
on its `scope` argument, so the decorator a binding inherits was chosen at the call site --
unresolvable for a static census, and correctly refused. It is now two factories with one
nested fixture each, and the seeding body is hoisted to a shared module-level helper so the
two scopes cannot diverge. Sharing that body was the point: splitting without it would have
duplicated the world setup, which is exactly what the single factory was protecting.

**The wrapper had to go with it, and its stated purpose survived.** `_live_fx_backend` existed
so the bucket id and settings could not drift between the two scopes -- but those were already
module CONSTANTS. What the wrapper added was a function returning a different fixture per
call: the same unresolvable shape, one level up. The shared arguments are now one named
mapping and each binding calls its own factory, so the anti-drift guarantee is kept and the
shape is gone.

**Measured result.** `fixture_ownership --write` no longer refuses at the closure. It now
reaches the check it exists for and reports two genuine substitutable duplicates --
`bundled_root_pointing_at`, in two `domain/calculations/registry/tests` modules. That belongs
to the registry campaign to adjudicate, and the manifest stays unregenerable until it is. But
the blocker has moved from "this shape cannot be analysed" to "the tool found something",
which is the difference between a broken instrument and a working one with a finding.

**A process note, third occurrence.** The module using the module-scoped variant reported 13
errors under xdist and passed sequentially; re-run unchanged, it then passed under xdist too.
That is the documented share flakiness, and the rule -- re-run before blaming the code -- has
now paid three times in this campaign. The first of those runs also included a fixtures module
in the pytest arguments, which is not a test module and should not have been there; that was
my error, not the tree's.

Lanes 340 integration / 1637 unit.

### The per-push dev lane is red, and mostly not from here

Unblocking the census moved `test_fixture_census` from two failures to one, and the remaining
message changed from the closure refusal to *"ownership manifest does not exactly match stable
generation"* -- the drift itself, now visible to the gate that owns it. That thread is now
blocked on the registry campaign: `--write` refuses while two substitutable duplicates
(`bundled_root_pointing_at`) stand in `domain/calculations/registry/tests`.

Since `dev/quality/tests` sits in the per-push lane, the obvious next question was whether
peers' pushes are currently failing. Run exactly as `test-dev-ci` runs it: **18 failed, 7
errors** across 25 items.

    dev/ci/tests/test_overview_verbs.py                   7
    dev/packaging/tests/ (eight modules)                  11
    dev/quality/tests/test_fixture_census.py               1
    dev/quality/tests/test_doc_privacy.py                  1
    dev/docs/tests/test_api_stubs.py                       1

**One of those is this campaign's enrollment, and it is the gate working.** `test_api_stubs`
was enrolled here deliberately, because it is the only check whose subject is the COMMITTED
stub tree and no per-push lane ran it. It now reports three modules with no stub --
`application/operator_surface/_calculation_workflows`,
`application/registry/_source_connectivity_authority`, `core.source_connectivity` -- plus two
orphan stubs. Those modules are silently absent from the published documentation right now,
which is precisely the quiet failure the enrollment was for. The remedy is one command,
`python -m dev.docs.apidocs scaffold`, run by whoever owns them: the docs rule is explicit
that a scaffold run also emits stubs for peers' modules and that only one's OWN modules may
be staged.

**The other 24 predate and surround it.** Packaging and CI-verb failures are in packages this
campaign has never touched, so the lane was red before the enrollment and would be red without
it. Worth stating plainly rather than leaving the enrollment looking like the cause: adding a
gate to a lane that is already failing does not break it, and this one is reporting a real
absence.

No production change this iteration. The finding is that a lane the whole team pushes through
is failing on 25 items with at least four owners, which nobody is likely to see while it stays
red for reasons each of them treats as somebody else's.

### This campaign's own documents leaked the operator's OS username

The doc-privacy gate is one of the 25 red items above, and its offender list was previously
dismissed here as "other campaigns' vault docs plus a legal TOML". Re-reading it against the
feature tags disproves that: two of the offenders carry `#profile-password-custody` and are
this campaign's own work -- the bucket-key-schedule ADR and the capabilities-removed audit,
both of which pasted the operator's Windows account name into committed prose as a bucket
label. A finding filed under someone else's name does not get fixed, and this one had been
sitting in the "needs an operator ruling" bucket while two thirds of it needed no ruling at
all. Read an offender list by OWNER before deciding it is not yours.

The label carried one piece of evidence -- two of the four pre-capsule buckets share an owner,
distinct from the `sync-test` and `operator` buckets -- and a placeholder carries it intact.
The substitution is `<operator-username>` rather than `<operator>` deliberately: the same
table lists a bucket genuinely labelled `operator`, and the shorter placeholder would have
silently merged two distinct labels into one and corrupted the inventory the table exists to
record.

Scrubbing prose invalidates the `body_hash` the `modified:` stamp attests, which is the
mechanism working: the reconciliation check named both edited documents and nothing else.
Running it `--feature profile-password-custody` scopes the re-attestation to this campaign, so
a shared worktree's peer documents are not restamped in passing. Two peer registry audits did
show modified afterwards, and their mtimes (22:02:22, against 22:06:50 for the fix) place them
minutes BEFORE the run -- a peer's own edit, not the filter leaking. In a tree where several
agents commit continuously, "my command touched it" and "it was already dirty" look identical
in `git status` and are separated by the clock.

The gate stays red: seven offenders remain across four other campaigns plus the legal TOML
whose `reviewed_by` the grounding rule positively requires. That last one is a genuine
standing conflict between two rules and still needs the operator's ruling. What changed is
that this campaign is no longer part of the problem it was reporting.

### A peer's write-policy consolidation silently stranded three tests behind the guard

The integration lane, green all campaign, came back with three failures minutes after
`980605f15a` routed the storage write policy through one authority and retired the duplicate
verb gate. Two distinct symptoms, one cause: `config profile censo file` returned
`REFUSED_CLI_BOUNDARY` where the case asserted `FAIL_CERTIFICADO_CENSAL_PARSE`, and the
secret-taking verb returned "No active profile" where the case asserted the `--secrets-stdin`
hint. Both refusals carry `failed_condition_id: profile.active` with evidence
`route_kind: root_fallback_database`.

The verbs declare `write_route = "profile-bound"`, and that declaration PREDATES the commit --
what changed is that it now bites. So the consolidated authority is doing its job; three cases
were passing only because the old duplicate gate let them through to a stage the guard should
always have stopped them reaching without a profile. Sequential re-run confirmed it is
deterministic and not this share's parallel-I/O race, and eleven commits landed on top without
anyone noticing, which is what a red lane nobody owns looks like.

**The fix is NOT to re-baseline the expectation to `REFUSED_CLI_BOUNDARY`.** That code is
already covered by the sibling `test_missing_artefact_is_refused_at_the_cli_boundary`, so
adopting it would have retired the parser contract while leaving two green tests that look
like they still cover it -- the "encode the current defect as the contract" failure. The cases
assert a PARSER refusal that lives downstream of the guard, so the honest repair is to give
them the active profile the verb is bound to. That is also the truthful scenario: a cotejo
compares a certificate against the active profile's censo facts and has nothing to compare
against without one.

The censo module had no storage isolation at all, having never needed any -- it was refused
before the artefact was opened. Registering a profile without adding isolation first would
have written into the operator's real store, so the fixture requests `_isolated_cli_backend`
explicitly rather than leaning on autouse ordering. `register_cli_profile` already defaults to
the canonical minimal fact set, so nothing duplicates the twenty-line dict the sibling module
carries.

Proven from outside the repo: a scratchpad plugin replaced
`adapters.inbound.censo.parse_certificado_censal_bytes` with a raiser. The traceback shows the
substitute REACHED, called from the verb, and both cases reddened -- which is precisely what
the boundary refusal previously prevented. Nothing tracked was mutated to run the proof. Lanes
back to 361 integration and 1644 unit.

Durable lesson: when a guard is correctly tightened, the tests it strands do not all deserve
the same treatment. Ask for each whether it was asserting something DOWNSTREAM of the new
refusal. If it was, the assertion is still the contract and the setup is what is stale;
adopting the new refusal as the expectation quietly deletes coverage while turning the lane
green.

### The full CLI integration tree is red, and mostly not for the reason it looks like

The previous entry ended with a pointer: the tightened profile-active guard might have
stranded cases outside the two domain lanes. Measured, that pointer is largely WRONG and is
retracted here. The full CLI integration tree reports 431 failed and 42 errors, but counting
signatures across the log gives `KDF_SUPERVISION_UNAVAILABLE` 111 hits against
`REFUSED_CLI_BOUNDARY` 8. The dominant failure has nothing to do with the write policy, and a
report written from the hypothesis rather than the counts would have filed a hundred phantom
findings against a peer's correct commit.

The KDF signature does not survive its own check either. `test_config.py` carries seven real
registrations, each spawning a supervised Argon2id worker, and at eight xdist workers in
isolation it passes 13/13 with zero KDF hits -- the same eight-worker parallelism the full run
uses. So the mechanism is not "the supervisor cannot take eight workers". What differs in the
full run is machine-wide load: this is a shared box with other agents running their own
suites, and the supervisor spawns a subprocess per call and fails CLOSED with a clear code
when it cannot. Failing closed on genuine resource exhaustion is correct behaviour, not a
defect. The honest conclusion is that the full CLI integration suite is not a trustworthy
instrument on this machine under concurrent load, and a red result from it needs its
signatures counted before any of it is believed.

Note also that this tree is in NO per-push lane -- the per-push integration gate names four
specific files, and the broad suite runs only in the dispatch-only full workflow. That is how
a tree this red stays invisible.

### A repair can import a cost the case never had

Fixing the three stranded cases in the previous entry, the censo module was given an active
profile through `register_cli_profile`, the CLI registration door. That door derives custody
material through the supervised KDF worker. Four cases that had previously touched no storage
at all -- they were refused before the artefact was opened -- now each spawned a subprocess,
and under the full tree all four ERRORED on `KDF_SUPERVISION_UNAVAILABLE`. The repair was
correct in substance and wrong in weight: those cases assert a PARSER contract and have no
interest in key derivation, so paying for a real Argon2id run made them fail for reasons
unrelated to their subject.

Replaced with `isolated_cli_runtime_profile`, which provisions the bucket directly: same
active-profile guarantee, no subprocess, and the module runs in 4.2 s against 18.8 s. The
external-break proof was re-run against the new fixture and still bites -- the substituted
parser is reached and both cases red. The sibling `test_config.py` change stands as written,
because that module already registers through the same door at seven call sites and one more
is consistent with it.

Durable lesson: when a guard strands a test, the cheapest setup that satisfies the guard is
not automatically the right one. Ask what the case is ABOUT, and pay only for that. A fixture
that drags in a heavyweight real subsystem the assertions never mention will eventually fail
for a reason the test name cannot explain.

### The KDF refusals' `retryable` value is genuinely ambiguous, and was NOT changed

Built and then reverted. Recording it because the next reader will find the same apparent bug
and should not have to re-derive the reason it is not one.

`ProfileCustodyRefusedError` carries four refusals under one registry entry with
`retryable=False`: `LEGACY_CUSTODY_DETECTED`, `DEK_ROTATION_UNSUPPORTED`,
`KDF_RESOURCE_LIMIT` and `KDF_SUPERVISION_UNAVAILABLE`. Measured, not inferred -- all four
emit `REFUSED_STORAGE_PROFILE_CUSTODY` with `retryable=False`. The first two are permanent
until re-enrolment. The other two looked misclassified: `profile_kdf_resources` refuses when
AVAILABLE MEMORY is insufficient, and the supervision refusal fires when the worker could not
be spawned or answered -- both of which clear on their own. The field's own docstring defines
`True` as "time alone, or another party finishing, can make the same request work", and a
sibling custody refusal is deliberately `True` on exactly that reasoning (something else holds
the receipt open and will release it).

A subclass carrying `retryable=True` was implemented for the supervision refusal alone, on the
theory that it was the unambiguous half. It is not. The shipped message in all four catalogues
reads "Key-derivation supervision is unavailable on this HOST" -- the permanent reading, that
this machine cannot supervise a KDF worker at all. And the raise sites support both: a host
that cannot spawn subprocesses fails here permanently, while a host merely out of memory this
second fails here transiently. The same mixture disqualified `KDF_RESOURCE_LIMIT`, whose
refusal also covers a missing `cpu_count` and a broken `sysconf` -- neither transient.

What decides it is the ASYMMETRY, which the field's docstring already states: the operator is
an autonomous agent, and "telling it to retry is what produces the loop". `False` on a
transient failure costs one abandoned operation the operator can repeat by hand. `True` on a
permanent one costs an unbounded retry loop against a host that will never succeed. With
causes genuinely mixed under one refusal, the conservative value is the defensible one, and
the existing `False` is most likely deliberate rather than an oversight.

Correcting this properly is not a `retryable` edit. It requires SPLITTING each refusal by
cause at the raise site -- "this host cannot supervise" separated from "this host is
momentarily out of room" -- across roughly forty raise sites, each classified by hand, plus
new codes and catalogue entries. That is a taxonomy decision with an owner, and it is
recorded here rather than taken alone.

Durable lesson: a refusal that bundles a permanent and a transient cause cannot carry an
honest `retryable`, whichever value it picks. The tell is a message that asserts one reading
("on this host") while the raise sites support both. Check the shipped MESSAGE against the
raise sites before concluding a classification is wrong -- the message is where the original
author recorded which cause they meant.

### The standing multiuser-safety lead is closed on evidence, not impression

Both halves of the lead carried in the campaign directive are now answered against the tree.

*Concurrent access, locking, session isolation.* Real separate-process coverage already exists
across the domain: `bucket/tests/test_lockfile.py`,
`user_profile/tests/test_concurrent_registration_cannot_duplicate_a_label.py`,
`test_custody_transactions.py`, `test_login_handover.py`,
`test_registration_retires_displaced_profile.py`, `test_capsule_lifecycle.py`, plus the lock
ORDER proof this campaign added. Session isolation is covered in its own right --
`test_active_session_thread_isolation.py`, `test_adverse_sessions.py`,
`test_live_session_registry.py`, `test_custody_isolation_matrix.py`,
`test_every_unsecured_session_open_runs_the_canary.py`. This is not a thin surface.

*The canary named in the lead.* `refuse_unsecured_bucket_with_real_profile` is protective code
and is properly gated in BOTH directions. The permissive branch ("is admitted") is
assertion-free by design -- admission means no refusal -- but the refusing branch is real:
`test_the_unsecured_provider_refuses_a_real_tax_id` raises `UnsecuredModeRefusedError`, the
classifier is asserted directly in both directions, and a whitespace-smuggling case proves a
padded real tax id cannot slip past. A deletion of the canary would red that half immediately.

### A vacuity scan over the domain, and the scan's own blind spot

Selection-order item 5 asks for cases that never reach their subject. Scanned all 1,675 test
functions in the three domain paths for any function with no `assert`, no `pytest.raises` and
no assertion call: 15 flagged, and every one inspected is legitimate -- "does not raise" cases
(idempotent clears, admitted canary branches, clean refusals) where absence of an exception IS
the assertion.

One flag was my instrument's fault and is worth recording. `test_archive_bundle_round_trips_
three_rows` looked assertion-free and would have been a serious finding, since the quality
rule requires strict equality at every persistence boundary. It asserts through
`_assert_raw_bundle_is_ciphertext` and `_assert_rows_load_back_through_natural_keys`; the scan
matched call names starting with `assert` and those start with an underscore. A detector whose
misses look exactly like clean results is the failure mode this campaign has hit repeatedly --
here it produced a false POSITIVE, which is the survivable direction, but the same blind spot
run as an exclusion filter would have hidden real vacuity.

### The domain lanes are currently unreadable, and HEAD is not the reason

Two consecutive iterations could not obtain a clean lane reading. The lanes collapsed from
361 collected to 166 with collection errors, and every error traces to one class:
`SyntaxError: keyword argument repeated`, from another campaign's in-flight multi-file sweep
adding `binding_source=` and then `source_provenance=` keyword arguments. Four files were
observed broken across the two iterations; one broke, self-healed, and a sibling broke the
same way minutes later.

The diagnostic that separates this from a real regression, and which is worth reusing:
`git show HEAD:<path>` parses clean while the working tree does not, and the file's mtime is
minutes old. Committed state is sound; the working tree is mid-edit. No fix belongs to this
campaign, and none was attempted -- editing a peer's file during a sweep that is repairing
itself would collide with an author who is actively in it. The last trustworthy reading for
this domain remains 361 integration and 1,644 unit.
