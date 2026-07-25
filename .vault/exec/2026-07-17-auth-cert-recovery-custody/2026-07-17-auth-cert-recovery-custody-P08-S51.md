---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S51'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Thread an explicit no-echo secure-input callback into the recovery create and rotate enrollment path so it stops prompting through bare getpass, closing the P04 door safety review HIGH finding that a console-less host blocks past 45 seconds in the very hang the real-console precondition exists to prevent and that a rebound stdin enters the echoing fallback with GetPassWarning swallowed, gated on a regression that drives the verb itself and fails on timeout rather than exercising the helper in isolation

## Scope

- `src/cadrumo/application/user_profile/_custody.py`

## Description

Thread an explicit passphrase callback through the enrollment chain. The
private `_enroll_recovery_code` seam now takes the callback as a required
keyword with no default, and both `create_recovery_code` and
`rotate_recovery_code` accept and forward it.

Bind the hardened no-echo prompt at the CLI. `_run_recovery_enrollment` passes
a new `_prompt_secret_store_passphrase`, which routes the store passphrase
through `prompt_secret_no_echo` on the existing current-passphrase locale key,
so no new catalogue entry was needed.

Make the omitted-callback case fail closed. A settings-bound
`_configured_passphrase_callback` reads the configured passphrase and refuses
with a typed storage error when none is set; it can never prompt, so a
programmatic driver cannot silently acquire an interactive read.

Bind the same non-interactive resolver on the two paths that resolve a provider
only to narrow or inspect it, `verify_recovery_code` and the passphrase-change
`_require_file_custody` probe, so a later change that starts asking those
providers for the master key cannot inherit the unguarded read.

Add a console-less regression that drives the verb. A detached, console-less
child runs `config recovery create` under a subprocess budget and must exit
non-zero through the CLI error boundary having minted no key material and
installed no envelope.

Add two application-layer gates: an omitted callback with no configured
passphrase refuses before the candidate is minted or displayed, and an explicit
callback supersedes a differently-valued configured passphrase, proven by
provisioning the store under the callback value and reading back which value
opens it.

Amend the two module docstrings for the decisions this campaign settled: the
custody door's secret-channel scope, and the deliberate absence of a
failed-attempt throttle on the custody verbs.

## Outcome

`config recovery create` and `rotate` no longer reach the storage substrate's
bare terminal read. Verified by reproduction rather than inspection: a detached
console-less probe of the pre-change chain was still alive past 45 seconds
having written its marker immediately before the passphrase read, so the block
was at the read and not at import; the same shape against the changed verb
refuses in about 14 seconds.

The regression is the load-bearing part and it fails on timeout, so a
reintroduced hang cannot pass by hanging. It asserts structure only, an exit
through the error boundary, a non-zero code, no escaped exception type, and the
absence of both `master.key` and the recovery envelope, and it records the
preconditions that make the run attributable, that no passphrase was configured
and that the channel reports a TTY while being no real console.

Verification: the two new modules plus the existing echo-suppression gate, nine
tests passed. The custody-adjacent suites, recovery lifecycle, custody audit
trail, recovery-flag reconciliation, echo guard and TTY error locale, 34 tests
passed. Formatter and linter clean on all four files, project type check
reports zero diagnostics for them, import-boundary and relative-import gates
clean, generated API stub tree conformant, core-struct docstring gate three
tests passed, and full-tree collection clean at 14012 tests with no collection
errors.

Investigated whether recovery verify reaches passphrase resolution, because it
also resolved a provider without a callback. It does not: the facade narrows
the provider to the file backend by type, then reads the envelope and unwraps
it with the mnemonic alone, never calling `get_master_key`. So there is no live
second instance of this finding. The provider there was bound to the
non-interactive resolver anyway, as defence in depth rather than a fix.

## Notes

The callback is required on the private enrollment seam but remains optional on
the two public application entry points. Making it required there would break
one call site in a CLI recovery-lifecycle test owned by a peer agent, which
this Step was instructed not to edit; landing a required parameter without that
one-line update would have left a red test at HEAD. The fail-closed default is
what removes the risk in the meantime: an omitted callback selects a resolver
that cannot prompt, so the fail-open shape this finding is about is gone from
every caller rather than only from the CLI. Promoting the parameter to required
on the public entry points is a small follow-up once that test is free.

The gate has teeth on Windows only. There a console-less stdin reports a TTY,
so the verb's cheap interactive pre-check admits the channel and the refusal has
to come from the real-console precondition deeper in. On other platforms the
same spawn yields a non-tty stdin that the pre-check refuses on its own, and the
substrate's own resolver also refuses on a non-interactive stdin, so no
equivalent blocking read exists to regress. The test asserts the preconditions
so which case ran is auditable rather than assumed, and the module docstring
states the limitation plainly.

The subprocess budget is 300 seconds. A genuine block is unbounded, so any
finite budget detects the regression and the size only trades against a false
failure under load; the child must import the whole CLI tree before it can
refuse, which the P04 door review measured at over a minute on a box running
parallel lanes, so the budget sits well clear of that rather than close to it.
The observed run is about 14 seconds.

Committing was blocked for roughly six minutes by a peer index lock. It was
live contention, not residue, confirmed by a commit landing minutes earlier and
the lock clearing on its own; no lock file was removed and no destructive Git
command was used. The commit named its four files explicitly, because the
shared index already carried nine unrelated staged files from a peer campaign.

The keyring custody path was not exercised, as agent sessions run over an SSH
network logon where Windows keychain calls fail with an environment error
rather than a defect. This change does not touch that path, which refuses
before any passphrase is resolved.
