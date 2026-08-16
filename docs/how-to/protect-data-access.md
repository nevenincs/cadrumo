# Protect access to your data

Cadrumo encrypts every profile, transaction, piece of evidence, and filing
under one master key. Your passphrase opens that key. Lose it with no recovery
phrase and the data cannot be decrypted by anyone, including you.

Use this guide to store the passphrase and recovery phrase safely, change the
passphrase, run commands without an interactive prompt, log out safely, and
reset local state only as a last resort.

## Before you start

You need:

- An active profile - see [set up your taxpayer profile](profile-setup.md).
- Your current master-key passphrase.

Use `--language en`, `es`, `ca`, or `hu` when you need a specific output
language.

## Store your passphrase safely

Your passphrase opens the key to your encrypted data. Treat it accordingly:

- Write the passphrase down and keep it offline, separate from your computer.
- Keep a second copy somewhere you can still reach after a disk failure.
- Never store it in a shared shell profile, a committed script, or a log.

If you lose the passphrase and hold no recovery phrase, the encrypted data is
permanently unreadable. The only way forward is a reset, which deletes it.

Do not reset when only *some* records fail to open. Quarantine them first.
Quarantine moves each unreadable record, still encrypted, into an archive
inside the same storage and leaves every readable record untouched, so it
deletes nothing and can be previewed before it runs. See
[diagnose and repair your local setup](troubleshooting.md).

## Store your recovery phrase safely

Cadrumo shows a 24-word recovery phrase once, at the moment it creates a
profile, on your terminal only. It is never written to a file, an export, or a
log, and Cadrumo keeps no copy. Nobody can show it to you again.

Write it down when it appears. Store it apart from your passphrase and apart
from the computer holding the data - anyone who has the phrase can open the
profile without the passphrase.

You hold a recovery phrase only if you created the profile at a terminal. A
profile created by a script or a scheduled job has no terminal to display the
phrase on, so Cadrumo creates none and says so in that run's output. Recovery
is installed only while the profile is being created, so a profile created
without it cannot be given one later.

Keep the phrase even though you cannot yet use it on your own. The command that
opens a profile from a recovery phrase is not available in this release. Until
it ships, your passphrase is the working key and the phrase is what preserves
your ability to recover once it does.

## Change your passphrase

Change the passphrase whenever you suspect it has been seen, or on whatever
schedule your own policy sets:

```
aeat config passphrase change
```

Enter the current passphrase, then the new one twice. Nothing is echoed.

The change re-wraps the existing key rather than replacing it, so:

- No record is re-encrypted, and every existing record stays readable.
- A recovery phrase you wrote down earlier stays correct.

The command reports both facts back to you. If the current passphrase is wrong,
the new one is too short, or the two copies do not match, it refuses and leaves
the existing passphrase working.

To change the passphrase without an interactive prompt, pass the three values as
one JSON object on standard input:

```
aeat config passphrase change --secrets-stdin
```

Send `{"current_passphrase": "...", "new_passphrase": "...",
"new_passphrase_confirmation": "..."}`. Never pass a passphrase as a
command-line argument: arguments are visible in the process list and in shell
history.

(run-without-a-passphrase-prompt)=
## Run without a passphrase prompt

Automation cannot answer an interactive passphrase prompt. For an agent server,
scheduled job, or script, set `CADRUMO_SECRET_PASSPHRASE` for that process.
Treat the value like the passphrase itself. Never put it in a shared shell
profile, committed script, or log.

Interactive commands prompt when they need the passphrase.

## Log out of the active profile

Run `aeat config logout` when you finish working with a profile. Logout
closes the active storage session, discards in-memory key material, disposes the
bucket engines, and clears the active-profile selection:

```{cli-sequence} protect-data-access-logout
:verify: Confirm logout closes the active session without deleting the profile.
```

Nothing in the profile is deleted. Log in again with
`aeat config login <name>` when you return.

## Reset local state (last resort)

Export every profile you want to keep before continuing. Reset permanently deletes
every profile stored locally, related local authentication state, and the active
profile selection. It doesn't delete exports stored elsewhere. You can't undo
the reset.

```{cli-sequence} protect-data-access-reset
```

1. Use `start` only when you intend to remove all local profiles. Confirm the
   reset explicitly. It checks retention requirements before deleting anything
   and refuses to start while another reset is incomplete.
2. Use the read-only `status` command to inspect the latest operation without
   changing local data. Provide an operation ID to inspect an exact operation.
   Status reports an incomplete, paused, or complete operation. Its output
   includes the operation ID and any pause reason.
3. Use `resume` after an interruption or pause. Confirm the reset again. It
   continues the same incomplete operation instead of creating another. Provide
   an operation ID to resume an exact operation. After deletion starts, resuming
   the reset doesn't restore deleted data.

If legal retention requirements pause the reset, stop if you must keep the
affected records. Override the pause only after reviewing and accepting the
legal retention consequence, and always provide a non-empty reason. If you
provide a reason without the override, the command refuses to continue.

See [Set up your taxpayer profile](profile-setup.md) for profile export
instructions.

## Next steps

- [Import, export, and evidence](../reference/import-export-and-evidence.md) -
  see where encrypted custody ends and deliberate plaintext handoffs begin.
- [Set up your taxpayer profile](profile-setup.md) - create, export, and
  import profiles.
- [Diagnose and repair your local setup](troubleshooting.md) - quarantine
  unreadable records and fix storage or integrity problems without a reset.
- [CLI reference](../cli/index.rst) - full option reference.
