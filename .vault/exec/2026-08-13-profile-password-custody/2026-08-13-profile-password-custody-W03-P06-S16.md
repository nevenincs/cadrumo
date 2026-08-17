---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:1e175040e65ce9c8d93ce25e2b16bc338b29300dd59c3435f4fcce63a3874b7b'
step_id: 'S16'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh expose canonical profile restore, restore-recover, and delete verbs through action envelopes and one-shot secrets-fd

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Description

- Read the closed rulings that bind this row before touching code: the
  per-family capability verdicts, the bundle-transfer ruling, the scripted
  creation refusal, the verb-existence authority ruling, and the
  bootstrap-exemption clearance.
- Established by inspection, not assumption, which of the three named verbs
  had an application layer to wire and which did not.
- Built the one-shot descriptor secret channel and gave it a real consumer on
  the session login verb rather than shipping it with none.
- Built the single-target deletion verb on the sessionless assessment
  authority and the journalled custody primitives, with its own safety
  argument rather than an inherited one.
- Removed the deletion verb's declared-unimplemented entry in the same change
  that registered it, per that entry's own stated exit condition.
- Swept the surfaces the gates do not scan: the curated operator help, the
  risk table, and the login-gated verb list.
- Proved the descriptor channel from a script outside the repository, found a
  defect in this row's own design, and corrected it.

## Outcome

**One of the three named verbs is delivered. Two are not, and the reason is
structural rather than a shortfall of effort.**

### Delete — delivered, with its own safety argument

`aeat config profile delete NAME [--yes]` is registered and its
declared-unimplemented entry is gone. The subject is a positional argument.
The default posture is a preflight that destroys nothing and reports the
label, the observed content fingerprint and the legal retention position; a
caller diffs that envelope field for field against the confirmed run, because
both postures share one schema discriminated by a `deleted` flag.

The safety argument is stated at the module head rather than inherited from
the all-profile reset, because the two have different blast radii and
different confirmation machinery. Four elements carry it: the subject must be
named, so a bare invocation cannot destroy whatever happened to be selected;
the default destroys nothing; the ACTIVE profile is refused outright rather
than reaching a path that would leave the pointer and session material aimed
at a capsule that no longer exists; and the legal retention floor is enforced
at the point bytes are destroyed, from the same assessment the all-profile
flow uses, so the two cannot state different law about the same records.

Two deliberate omissions, each a decision rather than an oversight. There is
NO single-target retention override: the all-profile flow can offer one only
because it records the operator's stated reason on a durable journal, nothing
in this verb's path records such a reason, and an override that leaves no
account of itself is worse than none — so an operator inside the window is
told the retained count and the clearing date and is deliberately NOT routed
to the all-profile reset, which would destroy every other profile to reach
this one. And there is NO bootstrap exemption: the verb stays login-gated, and
the absence is recorded as a login-gated entry with its reason, because the
prior clearance of dead exemptions warned specifically that this verb is the
one where a silently-inherited exemption costs a taxpayer their financial
history. That entry states its reason is DIFFERENT from its two siblings': the
output-leaves-the-store reasoning that gates them does not reach a verb whose
output is nothing at all.

**The verb is correct and its destruction path is blocked by a defect below
it.** Confirmed by running it: a confirmed delete refuses with `canonical
legal hold owner facts are absent`. The custody hold authority joins two
independently-owned evidence projections; the filing arm has two producers,
and the legal arm has NONE — its snapshot recorder has zero callers outside
its own module and tests, so the join always fails and the deletion primitive
refuses for EVERY profile regardless of session state. That is broader than
the standing framing of this defect, which describes it as affecting a
logged-in profile. By construction it also disables the all-profile reset,
which calls the same three primitives; that half is an inference from the
shared call site rather than an observation, and is marked as such.

### Restore and restore-recover — not delivered, and the gap is precise

The application layer landed mid-session from the row that owns it:
`restore_profile_with_password` and `restore_profile_from_recovery_artifact`
are live on the profile package facade. Both take `password_envelope`,
`sentinel` and `database_bytes` as parameters. Nothing in the tree maps a
transport artefact to that triple: the sealed-archive reader returns a header
and an opaque payload envelope, and no component turns those into the three
arguments the restore functions require. So a CLI verb has no way to obtain
the arguments it would pass, and building that mapping is the transport half
of the restore work, not CLI exposure. Restoring is therefore blocked on a
named, verifiable missing piece rather than on judgement.

Reported rather than absorbed, and no design-only shell was landed in the
meantime — a registered verb that cannot construct its own arguments is worse
than an absent one, because it advertises a capability the tree cannot honour.

### The one-shot descriptor channel

`--secrets-fd` reads one bounded strict-JSON secrets object from an inherited
descriptor and closes it, on the success path and on every refusal path. It
shares the bound, the duplicate-key refusal and the strict-model contract with
the stdin channel through one validator, so the two cannot drift; only the
refusal keys differ, because a message naming the wrong flag sends the
operator to a channel they did not use. Naming both machine channels at once
refuses rather than picking one, because whichever lost would be a secret the
caller staged and this process never drained.

It is wired into `config login` immediately rather than shipped as capacity: a
secret channel with no caller is the dead capacity this campaign exists to
remove. The routing predicate that decides whether the full-screen login page
opens now reads one condition, "has the factor been supplied", instead of
naming a single pipe, so the descriptor and the stdin object cannot diverge in
how they suppress the page.

Its portability cost is stated in the module rather than papered over:
arbitrary descriptors are not inherited by subprocess on Windows, so a caller
there must map an inherited handle before naming the number, and the stdin
object remains the portable machine channel.

## Notes

**The probe found a defect in this row's own design, and it was a real one.**
The first implementation kept a process-local register of consumed descriptor
numbers, on the reasoning that a closed number can be reopened and a second
read must refuse loudly. Running the probe showed the opposite: the operating
system reissues a freed number immediately, so the number a caller stages a
SECOND, genuinely different secret behind is very often the one the first read
just released — and the register refused that legitimate channel while blaming
the caller for a collision the platform created. A verb collecting two secrets,
which is exactly what a restore verb would be, would have hit it on its first
run. The register was deleted. The case it was meant to catch is covered more
precisely without it: reading a closed descriptor fails at the operating
system and surfaces as unreadable, never as an empty payload. The corrected
reasoning is recorded in the function rather than merely fixed, because the
wrong version looked like the safer one.

**Two surfaces this row was told to sweep do not exist.** There is no
`entrypoints/tui/` package and no `_data/agent/` harness directory anywhere in
the tree, so the agent-harness citation sweep the CLI contract mandates had no
target. The full-screen surfaces the row means live inside the CLI package.

**Fourteen locale keys are owed and are reported rather than added**, since the
catalogues belong to another owner. Until they land, the new flag and verb
render humanised key fallbacks in help and the new refusals render fallback
text. The coverage list in the secure-input locale gate is hand-maintained and
does not include the new keys, so it will not catch their absence — reported
with the exact keys to add rather than edited, since that module is another
owner's.

**One consumer update crossed an ownership line and is reported.** Renaming the
login routing predicate's parameter to say what it now means required updating
its only test module, which sits in the excluded tests directory. Leaving a
peer's test red on a rename this row made would have been worse than the
crossing, and the atomic-relocation discipline requires the consumer update to
land with the rename.

**Two of the five new deletion tests are red on the legal-hold defect above.**
They are correct coverage of a path production cannot currently execute. They
were not made green by seeding the missing snapshot from a fixture: that would
prove the chain works in a configuration no operator can reach, which is the
shape the quality rules name specifically. Held for the campaign lead to
attribute or reassign.

**Two failures in adjacent gates were checked before being attributed
elsewhere, not assumed to be someone else's.** The live operator-surface
reconciliation reds over declared-unimplemented profile keys — this row
REDUCED that list from five to four by restoring one of them. The verb
input-schema metadata test reds on an optional argument it asserts is
required; that module is unmodified against committed state and names no
surface this row touched.

No commit was made and no plan checkbox was set. Every capture lives under the
session scratchpad directory, not the repository.

## Continuation, 2026-08-16: the named blocker was removed and restore is delivered

**The gap this record named precisely is closed, by the piece it said was
missing rather than by working around it.** The blocker was recorded as
"nothing in the tree maps a transport artefact to that triple". The
capsule-restore row has since landed `read_profile_capsule_source`, which
reads an unpublished capsule DIRECTORY and returns exactly the password
envelope, sentinel and database bytes the two restore functions require, plus
the recovery wrapper. That is the mapping whose absence blocked this row.

`aeat config profile restore LABEL --file CAPSULE_DIR [--artifact PATH]` is
registered and green.

**One verb, two credentials, argued rather than assumed.** The row names
"restore" and "restore-recover" as two verbs. They are delivered as one verb
selected by `--artifact`, because they are two ways of PROVING one key rather
than two restore paths: both converge on the single application restore
authority, and splitting them would have produced two argument surfaces over
one operation that could then drift. Recorded here as a deliberate narrowing
of the row's literal wording, not a silent one. What the standing goal still
gets: both credentials reach restore from the command line, which is what the
row exists to deliver.

**The recovery door's limit is surfaced, not hidden.** That door republishes
the capsule under its EXISTING password envelope, so it recovers the records
and not the credential. The verb emits a warning `Notice` saying so and
carries a `password_unchanged` field so a machine caller can branch on it. A
plain success envelope here would have been a half-truth at exactly the moment
an operator is deciding whether they are recovered. Rotation-through-recovery
— which would close that gap properly — is sequenced onto the custody lane
with the constraint that it reuse the ONE rotation authority the passphrase
verb already calls, not a recovery-specific fork.

**Bootstrap-exempt, with the reason recorded as data.** Registered as a
`TORN_STATE_RECOVERY` exemption. The profile an active-session gate would
demand is the one being restored, so gating it is a deadlock in the literal
sense; and it grants nothing, because the caller must already hold both the
capsule bytes and a credential that opens them. This is the deliberate
counterpart to the delete verb's recorded REFUSAL of an exemption above —
same registry, opposite ruling, each with its own stated ground.

**Coverage, including what is NOT covered.** Two real end-to-end CLI tests: a
capsule directory registered under one storage root restores into a second
root that has never seen it, with identity asserted ON DISK (the payload
redacts the profile id by contract, so the restored capsule directory being
named for the SOURCE profile UUID is the real claim — a restore that minted a
new id would have cloned the records, not recovered them); and a non-capsule
directory refuses without a traceback. The recovery-artifact door is NOT
covered at CLI level and the module says so in its docstring: minting an
artifact needs a replayed recovery key with no sanctioned test-support door,
and reaching into another package's private test helpers to fake one would be
worse than the honest gap. The artifact door is covered at application level.
The consequence is stated rather than left to be inferred — the CLI assertion
that a password restore carries no advisory would pass identically if the
advisory never fired at all, so it is written as a control on the password
door, not as evidence about the recovery door.

**Two boundary preconditions were landed rather than deferred.**
`ProfileRestoreAuthority` was promoted to the profile package's `__all__`
before the payload consumed it, so the closed authority set is one canonical
Literal rather than a duplicate declared at the CLI boundary. And the notice
code constant was RENAMED rather than suppressed when the linter flagged it as
a possible hardcoded password — the rule was right to be suspicious of a
constant named that way.

**The fourteen owed locale keys this record reported have since landed**, and
six further keys for this verb were added through the locale CLI in all four
catalogues with real values, not placeholders.

**The pre-existing red this record documented is confirmed still pre-existing.**
`test_every_cli_leaf_has_a_registered_schema` reds over four
declared-unimplemented profile keys — export, import, rename and
subject_access_request. This record states it reduced that list from five to
four; it is still four, and today's work neither added to it nor cleared it.
Attributing it here so it is not re-discovered a third time as if new.

## Continuation, 2026-08-16: the sealed-archive backup surface and acceptance 276

**A catalogued operator capability was unimplemented at two layers and its
acceptance test had been failing for an unrelated reason, which is why nobody
had noticed.** `acceptance_wall_catalogue.py` binds issue **276** — *"the
operator backs up their local catalogue to an archive and restores it on a
fresh machine without data loss"* — to
`test_profile_archive_roundtrip.py`. That module drove
`config profile archive export | import | inspect`, none of which existed; the
application service had been removed with, in `bucket_maintenance`'s own words,
"no successor primitive at all". The module never reached those verbs because
it died earlier on `r_create.exit_code`, the registration door having changed
to return a profile id. A test failing at the wrong line concealed a missing
capability for as long as nobody read past the first exception.

**Delivered: `archive export` and `archive inspect`. Deliberately NOT
delivered: `archive import`.**

An archive and a capsule directory differ only in how their material is READ —
both produce a `ProfileCapsuleSource`, and from there both reach one shared
publication authority. So `config profile restore` now takes EITHER shape and
tells them apart by asking the filesystem, and there is no import verb. A
second import verb would have been a second door onto one authority, and would
have left an operator guessing which of two commands restores a backup. This
is the same single-authority argument that made restore one verb with two
credentials rather than two sibling verbs.

**Two properties were verified rather than accepted on assertion.** The
recovery slot is constant-WIDTH, not merely fixed-marker — the distinction
matters, because any differently-sized marker still signals absence by length,
so enrolment would have stayed inferable from a copy of the file. And a
byte-scan over the archive members proves no tax id, name, surname or LABEL
appears outside the encrypted member. The label is the one an obvious
implementation leaks: it lives in plaintext beside the ciphertext inside a
published capsule, so packing the directory verbatim would publish the
operator's chosen name. Packing from `ProfileCapsuleSource` excludes it
structurally, because that type never reads it.

**The acceptance module was rewritten, not repaired, and its anchor renamed.**
Three of its assumptions no longer hold: an `import` verb, a `size_bytes`
inspect field, and an automatic active-profile switch on restore. The last is a
deliberate behaviour change — republishing a profile is not a claim that the
operator wants to work in it. The capability the wall names is unchanged and is
proved end to end, including a seeded ledger row so that restoring an empty but
structurally valid profile cannot pass. The wall entry now names
`test_archive_export_restore_roundtrip`. Six tests, all green.

**A gate defect was fixed rather than worked around.**
`test_every_cli_leaf_has_a_registered_schema` reds on registry keys with no CLI
leaf, and had no knowledge of `DECLARED_UNIMPLEMENTED_SURFACES` — the mapping
whose entire purpose is to declare exactly that state, and which
`assert_schema_coverage` has always honoured. Two gates therefore disagreed
about the same four keys, so one was red for a state the other called legal.
A red that cannot be cleared teaches everyone to ignore the gate. The exclusion
is now honoured here too, and the teeth are kept by a NEW companion assertion:
a declared entry whose verb has since landed is itself a failure, because every
entry's own stated exit condition is that restoring the verb removes it.
Nothing enforced that before, so a landed verb could have left its
"knowingly absent" declaration standing indefinitely — the same
prose-nobody-re-derives class this campaign keeps meeting.

**Locale debt was cleared in both directions:** five keys describing the absent
import verb and a non-existent `--recovery-wrap-passphrase` flag were removed,
and three were rewritten to describe the live surface, all four catalogues.

**Attribution for the reds NOT addressed here.** 25 failures in
`entrypoints/cli/_config/tests` (status frontend and status notices) and the
bulk of the wider CLI suite resolve a live modelo-303 snapshot. The registry
campaign has M303 mid-authoring and refusing — missing export layouts, and a
revision whose id claims an open-ended window its own `year_to = 2022` closes —
and registry validation is whole-tree, so a single refusal takes every snapshot
resolution with it. Not custody, not this row, and not fixable from this lane.
