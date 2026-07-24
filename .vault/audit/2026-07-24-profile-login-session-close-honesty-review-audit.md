---
tags:
  - '#audit'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
related: []
---

# `profile-login-session` audit: `Fresh-context campaign close honesty review`

## Scope

The mandatory fresh-context close review for this campaign, performed by a
reviewer who was not inside it, as the campaign-close honesty rule requires. The
implementing agent's final report was treated as a set of claims to verify rather
than as given: every sweep, count, and exemption below was re-checked against code
at HEAD `2d5011de5f`, and the gates were re-run here rather than read from a
report.

Two items were referred for explicit adjudication: the deleted corrupt-store
regression test, and the claim that the profile-bound write-policy allowlist
needed no change. Both are adjudicated below with the reasoning that decided them.

A note on method that changed one conclusion. An early sweep found what looked
like a production refusal still naming a deleted verb, and a test pinning it. Both
were already clean when read: peer commits landed between the sweep and the read.
Every sweep result here was therefore re-run and pinned to a single HEAD before
being asserted. In a tree taking roughly twenty commits an hour, a search result is
evidence about a moment, not about the branch.

## Findings

### translated-docs-still-instruct-retired-verbs | high | Three locale catalogues tell readers to run commands the CLI refuses

The documentation step swept the English sources and the sequence contracts, and
those are clean: an exact search across `docs/how-to/` and the top-level
documentation pages finds no occurrence of either retired verb. The translated
catalogues were not swept. The Spanish, Catalan, and Hungarian catalogues under
`docs/locales` carry 12, 11, and 11 occurrences respectively, 34 in total across
nine `LC_MESSAGES` files, spanning the profile-setup, troubleshooting, and
protect-data-access guides.

The occurrences sit in both halves of the catalogue. The English source strings
still name the retired selection and logout verbs, and so do their Spanish,
Catalan, and Hungarian renderings. A reader of the Hungarian protect-data-access
guide is told to finish a session with the retired profile-logout spelling; a
reader of the Catalan troubleshooting guide is told to change profile with the
retired selection verb. The CLI answers both with a usage error and exit 2.

Whether a given reader sees the stale instruction or an untranslated English
fallback depends on whether the changed source string still matches the stored
message id, which varies string by string. Both outcomes are defects: one hands
the reader a dead command, the other silently drops the translation the catalogue
exists to provide.

This belongs to the documentation step, which is correctly still open. The
remediation is the locale half of the same hand-sweep the English pass already
performed, regenerated through the documentation i18n workflow rather than by
editing catalogues by hand.

### environment-blocked-trio-count-and-attribution | medium | Nineteen failures, not eighteen, and only fourteen name the credential store

The three open service steps are reported blocked by this host's broken Windows
credential store, with eighteen failing cases all traced to the same operating
system error. The blocked-by-environment conclusion is correct. The
characterisation is not, in three ways that would mislead the next reader.

The first correction is to the cause, and it is the one that matters most,
because "the machine's credential store is broken" invites someone to try to fix
a machine that is healthy. It is not broken. The agent harness reaches this host
over SSH in Windows session 0, and public-key authentication mints an S4U token
that carries no credentials, so the credential read returns the logon-session
error for the harness and only for the harness. The credential service is
running, its hive is loaded, and an interactive credential listing exits cleanly
with an empty per-logon set. The correct statement is that these cases are
blocked by the harness's logon context, not by the workstation, and that the
application is NOT degraded for a real interactive user. The practical
consequence is that the three steps are verifiable by the operator in a single
interactive run rather than waiting on any repair.

The count is nineteen, not eighteen. A serial run with markers stated explicitly,
across the persisted-session roundtrip suite, the login-session application suite,
the CLI lifecycle suite, and the root-resume suite, reports 19 failed and 32
passed of 51 selected.

More important, only fourteen of the nineteen carry that operating system error
anywhere in their traceback. Five do not: the first-login mint case, both
idempotent-guard cases, and both silent-resume cases. A reader who verifies the
claim by searching the log for the error number finds fourteen and concludes five
failures are unexplained.

They are explained, and they remain environmental, but by a different path. The
keychain failure is caught in production rather than raised:
`src/cadrumo/application/user_profile/_login_session.py:618` logs that the profile
session was not persisted because no usable OS keychain is available, and returns
a flag saying the login is process-scoped. The five tests then fail because they
assert against a persisted session that was deliberately never written. The
credential store is the root cause; the traceback never says so because production
handled it.

The remediation is to the record rather than the code: state nineteen, state the
harness logon context rather than a broken machine, and state that five reach
failure through the graceful-degradation branch rather than a raised error, so a
later reader does not mistake the gap for an unexplained defect. No defect was
found hiding behind the environment attribution, which was the specific risk this
review was asked to probe.

### closure-commit-absorbed-a-peer-change | medium | The campaign's own S11-S14 closure swept an unrelated agent's uncommitted work

The commit that closed this campaign's verb-registration and hard-cut steps also
carried an unrelated agent's uncommitted change to the operator-surface contract
module into its SHA. The content is intact and correct at HEAD; only the
attribution is wrong, and no product defect follows from it.

It is recorded because it is precisely the class of process failure a
fresh-context review exists to surface, and because it is the second such
incident in this session: this reviewer's own audit and execution-record edits
were swept into an unrelated peer commit a few hours earlier. Two independent
occurrences in one evening is a pattern rather than an accident.

The mechanism is the one the explicit-pathspec rule names: in a shared worktree
the index routinely holds several campaigns' staged work, so a commit that does
not name its paths takes whatever is staged. The rule already forbids it. What
this pair of incidents adds is evidence that the failure is recurring under
current practice rather than theoretical, and that its victims only discover it
by accident afterwards, because a swept change looks identical to a correctly
landed one at HEAD.

No remediation is proposed here beyond the existing rule. The finding is the
recurrence.

### plan-row-names-a-path-that-does-not-exist | low | The verb-removal step scopes a curated help surface at the wrong location

The verb-removal step names a curated operator help module beneath
`src/cadrumo/entrypoints/cli/operator_surface/` among its scoped files. That path
does not exist, and no `operator_surface` package exists anywhere under
`src/cadrumo/entrypoints/`. The real surface is
`src/cadrumo/application/operator_surface/_help.py`.

This is a scope-accuracy defect in the step row, not a coverage gap. The real file
was swept: it contains no occurrence of either retired verb and carries the
replacements at `src/cadrumo/application/operator_surface/_help.py:286` and `:290`.
The work was done on the right file; only the row points at the wrong one.

It is recorded because a reader auditing that step against its stated scope would
find a missing file and could reasonably conclude the surface was never swept, or
could sweep a nonexistent path and record a vacuous pass.

### deleted-corrupt-store-regression | accepted | The contract died with its verb and the failure mode kept an owner

The deleted test asserted that a corrupt bucket database reached through the
retired selection verb surfaced via the shared command boundary: exit 6, no
profile-record-unreadable relabelling, no repair-profile suggestion, and a
repair-logs recovery hint instead. The concern put to this review was that
deleting a test whose contract merely moved is coverage loss wearing a good
argument.

The deletion is accepted, on two verified grounds rather than on the argument.

The subject verb is genuinely gone, and the replacement structurally cannot reach
the surface the contract guarded. `_login_session.py` imports only from the
master-key custody package and the storage error module; it contains no reference
to a SQL engine, a secure-object repository, or any database construction. Login
authenticates by master-key unwrap and mints a session record. It never opens the
per-bucket SQL database, so there is no corrupt-database path through it, and
retargeting the assertion at login would have been fitting the test to whichever
verb happened to pass.

The failure mode retains an owner with real coverage. Two tests in
`src/cadrumo/entrypoints/cli/_config/tests/test_config.py`, at `:151` and `:171`,
corrupt the per-bucket SQLite database on disk for real and drive the profile-show
readiness pre-read through it. The first asserts exit 2 and the unreadable-record
payload; the second asserts the boundary error appears in the exception cause
chain. Neither uses a patched attribute swap; both trigger a genuine database
error.

The apparent contradiction between the deleted assertion, which forbade the
unreadable-record label, and the surviving ones, which require it, is not a
contradiction. The retired verb was a selection door, where classifying a corrupt
database as a profile-record repair problem sends the operator to the wrong
remedy. The profile-show pre-read is where that classification is accurate and
instructive, because the operator is in fact trying to read a record that cannot
be read.

A corrupt bucket database still reaches an operator as a typed, instructive
refusal rather than a traceback. No replacement Step is needed.

### write-policy-allowlist-needed-no-change | confirmed | Verified against the short-circuit and against the retired verb's own prior state

This was flagged for independent verification because it is the one surface where
a missed verb fails open on the profile-bound write guard, and a fail-open guard
is exactly what nobody notices.

The claim holds, though the decisive evidence is not the one offered. The offered
reasoning was that both replacements are bootstrap-exempt and the policy query
short-circuits on that before consulting the catalog. That is true:
`src/cadrumo/application/storage_write_policy.py:226` returns an allowing decision
on the bootstrap-exempt input, and the catalog membership test at `:240` is only
reached afterwards, so enrolling either verb in the allowlist would be dead code.
Both replacements are enrolled as exempt at
`src/cadrumo/entrypoints/cli/_bootstrap_exempt.py:63` and `:64`, with a stated
rationale: login is itself the authentication gate, and logout must stay reachable
precisely when the session is absent or expired.

Standing alone that would leave open whether the hard cut widened the unguarded
surface. It did not, and the history settles it: the retired selection verb was
itself bootstrap-exempt, and the migration diff removes it from that same tuple in
the same change that adds the two replacements. The exemption was inherited, not
introduced. The guarded-write catalog never carried the retired verb either, so
nothing was dropped from it.

No fail-open gap was introduced by this campaign.

### confirmed-non-findings | low | Checked and clean, recorded so they are not re-checked blindly

The retired verbs are absent from the product tree. At HEAD `2d5011de5f` an exact
search for either spelling across `src/cadrumo/` returns zero hits in production
code and zero in tests.

The operator harness is clean. An exact search across `src/cadrumo/_data/agent/`
returns no citation of either retired verb, satisfying the harness-conformance
rule's same-commit requirement.

The no-keychain degradation is surfaced to the operator, not silent. The
application returns a persistence flag, the CLI branches on it at
`src/cadrumo/entrypoints/cli/_config/_custody.py:105` and emits a typed Notice, the
envelope carries the flag as a field, and the locale catalogues carry the message.
This was checked specifically because a login reporting success while persisting
nothing would be a silent capability loss.

That flag cannot drift from reality. The lifecycle test asserts at
`src/cadrumo/entrypoints/cli/tests/test_profile_login_session_lifecycle.py:217`
that the envelope's persistence claim equals whether the record exists on disk, so
a login claiming persistence it did not achieve fails the gate.

The lifecycle test is honest on both host types. It branches on the observed
persistence flag rather than assuming a healthy keychain and asserts the
envelope-versus-disk agreement either way. It passed here, on a host whose
credential store is broken, without passing vacuously: it exercised and asserted
the degraded branch.

## Recommendations

Sweep the three translated documentation catalogues for the retired verbs and
regenerate them through the documentation i18n workflow. This is the only item
here that would have shipped unnoticed, it is taxpayer-facing, and it belongs to
the documentation step rather than becoming a new one, because that step is
already open and this is the unfinished half of its own scope.

Correct the environment-blocked record on all three counts: nineteen rather than
eighteen, the harness logon context rather than a broken workstation credential
store, and five of the nineteen reaching failure through the production
graceful-degradation branch rather than a raised operating system error. No code
change. The cause correction is the load-bearing one, because it changes the
remedy from repairing a machine to running the three steps once interactively,
and because the application is not degraded for a real user.

Correct the verb-removal step row to name the operator help surface at its real
location under the application layer. No code change; the sweep was performed
correctly on the real file.

The campaign is not structurally complete, and the gap is not the
environment-blocked trio. Those three steps are honestly blocked and correctly
attributed, subject to the count correction. The documentation step is also
correctly open, and open for a reason its own report did not name. The
implementation itself is sound on both questions that carried real risk: the write
guard did not lose a verb, and the deleted regression test took a contract that
genuinely died with its verb while its failure mode kept a covered owner.
