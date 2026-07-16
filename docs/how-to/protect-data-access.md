# Protect access to your data

Cadrumo encrypts every profile, transaction, piece of evidence, and filing
under one master key. Your passphrase opens that key. If you lose the
passphrase and have no recovery key, the data cannot be decrypted by anyone,
including you.

Use this guide to set up a recovery key before you need it, change your
passphrase, recover access after a lost passphrase, log out safely, and reset
local state only as a last resort.

## Before you start

You need:

- An active profile - see [set up your taxpayer profile](profile-setup.md). The
  first command below refuses without one (`No se pudo determinar ningún bucket
  activo. Selecciona un perfil y vuelve a intentarlo.`).
- Your current master-key passphrase for recovery-key creation, rotation, and
  passphrase changes.
- Your recovery words for verification or recovery after a lost passphrase.
  Recovery sets a new passphrase without requiring the lost one.

Use `--language en`, `es`, `ca`, or `hu` when you need a specific output
language.

## Create your recovery key first

Do this once, right after setup, while your passphrase still works:

```{cli-sequence} protect-data-access-show-recovery
```

If no recovery key exists yet, the command creates one and prints a
twenty-four-word recovery key. The words are shown exactly once and are never
stored. Only an encrypted wrapper of the master key is written to disk. Write
the words down and keep them offline, separate from your computer.

Run the same command again later to confirm enrollment: once a recovery key
exists, the command reports its status and does not print the words again.

## Check that your recovery key works

Verify the words you wrote down without changing anything:

```{cli-sequence} protect-data-access-verify-recovery
```

The command reports `verified yes` or `verified no` and exits with a failure
code when the words do not open the recovery wrapper. Nothing is modified
either way.

## Replace the recovery key

If the written words may have been seen by someone else, mint a fresh
recovery key:

```{cli-sequence} protect-data-access-rotate-recovery
```

New words are printed exactly once. The previous recovery words stop working
immediately. Store the new words as before.

## Change your passphrase

To change the passphrase while you still know the current one:

```{cli-sequence} protect-data-access-rekey
```

The command asks for the current passphrase if the store is not already
open, then prompts twice (hidden) for the new one. The master key itself
does not change, so all stored data stays readable. Only the passphrase
that opens it is replaced. For non-interactive use, pass `--new-passphrase`
together with `--confirm-new-passphrase`.

## Recover after a forgotten passphrase

If you forgot the passphrase but have your recovery words:

```{cli-sequence} protect-data-access-recover
```

The command prompts twice (hidden) for a new passphrase, unlocks the master
key from the recovery wrapper, and rewraps it under the new passphrase. All
stored data stays intact. Nothing is deleted or re-encrypted. For
non-interactive use, pass `--new-passphrase` together with
`--confirm-new-passphrase` instead of being prompted.

If you have neither the passphrase nor the recovery words, the encrypted
data is permanently unreadable. The only way forward is a reset (below),
which deletes it.

## Run without a passphrase prompt

Automation cannot answer an interactive passphrase prompt. For an agent server,
scheduled job, or script, set `CADRUMO_SECRET_PASSPHRASE` for that process.
Treat the value like the passphrase itself. Never put it in a shared shell
profile, committed script, or log.

Interactive commands prompt when they need the current passphrase. Recovery
commands use the recovery words and ask for a new passphrase instead.

## Log out of the active profile

Use `aeat config profile logout` when you finish working with a profile. Logout
closes the active storage session, discards in-memory key material, disposes the
bucket engines, and clears the active-profile selection:

```{cli-sequence} protect-data-access-logout
:verify: Confirm logout closes the active session without deleting the profile.
```

Nothing in the profile is deleted. Select it again with
`aeat config switch <name>` when you return.

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
- [Diagnose and repair your local setup](troubleshooting.md) - for storage
  or integrity problems that do not need a reset.
- [CLI reference](../cli/index.rst) - full option reference.
