---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-19'
body_schema: 'body-v1'
body_hash: 'sha256:ce3b03c3b6599da5816099b9d48c697bee3d730dc6cd5e771e967ccf5b50241a'
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
