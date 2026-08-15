# Protect access to your data

Cadrumo encrypts every profile, transaction, piece of evidence, and filing
under one master key. Your passphrase opens that key. Lose the passphrase and
the data cannot be decrypted by anyone, including you.

Use this guide to store the passphrase safely, run commands without an
interactive prompt, log out safely, and reset local state only as a last
resort.

## Before you start

You need:

- An active profile - see [set up your taxpayer profile](profile-setup.md).
- Your current master-key passphrase.

Use `--language en`, `es`, `ca`, or `hu` when you need a specific output
language.

## Store your passphrase safely

The passphrase is the only key to your encrypted data. Cadrumo ships no
command to change it and no command to recover access without it. Treat it
accordingly:

- Write the passphrase down and keep it offline, separate from your computer.
- Keep a second copy somewhere you can still reach after a disk failure.
- Never store it in a shared shell profile, a committed script, or a log.

If you lose the passphrase, the encrypted data is permanently unreadable. The
only way forward is a reset, which deletes it.

Do not reset when only *some* records fail to open. Quarantine them first.
Quarantine moves each unreadable record, still encrypted, into an archive
inside the same storage and leaves every readable record untouched, so it
deletes nothing and can be previewed before it runs. See
[diagnose and repair your local setup](troubleshooting.md).

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
