# Protect access to your data

Cadrumo encrypts every profile, transaction, piece of evidence, and filing
under one master key. Your passphrase opens that key. If you lose the
passphrase and have no recovery key, the data cannot be decrypted by anyone,
including you.

Use this guide to set up a recovery key before you need it, change your
passphrase, recover access after a lost passphrase, lock the session, and, as a
last resort, wipe local state and start over.

## Before you start

You need:

- An active profile - see [set up your taxpayer profile](profile-setup.md). The
  first command below refuses without one (`No se pudo determinar ningún bucket
  activo. Selecciona un perfil y vuelve a intentarlo.`).
- Your master-key passphrase. These commands open the encrypted store, so
  they prompt for the passphrase. The recovery and rekey commands below
  replace which passphrase opens the key.

The runtime emits help, prompts, and messages in Spanish.

## Create your recovery key first

Do this once, right after setup, while your passphrase still works:

```{cli-sequence} protect-data-access-show-recovery
@step Create or confirm the recovery key.
@static aeat config show-recovery
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
@step Verify the recovery words without changing anything.
@static aeat config verify-recovery --recovery-key "word1 word2 word3 ..."
```

The command reports `verified yes` or `verified no` and exits with a failure
code when the words do not open the recovery wrapper. Nothing is modified
either way.

## Replace the recovery key

If the written words may have been seen by someone else, mint a fresh
recovery key:

```{cli-sequence} protect-data-access-rotate-recovery
@step Mint a fresh recovery key and retire the previous words.
@static aeat config show-recovery --rotate
```

New words are printed exactly once. The previous recovery words stop working
immediately. Store the new words as before.

## Change your passphrase

To change the passphrase while you still know the current one:

```{cli-sequence} protect-data-access-rekey
@step Change the passphrase that opens the master key.
@static aeat config rekey
```

The command asks for the current passphrase if the store is not already
open, then prompts twice (hidden) for the new one. The master key itself
does not change, so all stored data stays readable. Only the passphrase
that opens it is replaced. For non-interactive use, pass `--new-passphrase`
together with `--confirm-new-passphrase`.

## Recover after a forgotten passphrase

If you forgot the passphrase but have your recovery words:

```{cli-sequence} protect-data-access-recover
@step Unlock the master key from the recovery words and set a new passphrase.
@static aeat config recover --recovery-key "word1 word2 word3 ..."
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

Automation cannot answer a prompt - an agent server, a scheduled job, a
script. For those runs, set the `CADRUMO_SECRET_PASSPHRASE` environment
variable to your passphrase before the command starts. Treat that value
like the passphrase itself: set it only in the environment of the process
that needs it, and never write it into a shared shell profile, a script
you commit, or a log.

Interactive use never needs this - every command prompts.

## Lock the session

Clear the active-profile selection with `aeat config lock` so commands stop
operating on your data until a profile is selected again. The card confirms a
profile is active, locks the session, then shows that the active selection is
cleared:

```{cli-sequence} protect-data-access-lock
:verify: Confirm locking clears the active-profile selection without deleting anything.
@step Confirm a profile is currently active.
aeat config profile status
@step Clear the active-profile selection.
aeat config lock
@result aeat config profile status
@expect exit_code == 0
```

Nothing is deleted. Locking only clears the active-profile pointer. Select
a profile again with `aeat config switch <name>` when you return.

## Reset local state (last resort)

Reset deletes operator-local state. It is not recoverable. The command
refuses to run without `--yes`:

```{cli-sequence} protect-data-access-reset
@step Delete operator-local state for the chosen scope.
@static aeat config reset --scope profile --yes
```

Pick the scope deliberately:

- `--scope profile` - deletes every profile and its stored data, including
  archived profiles.
- `--scope auth` - clears the saved AEAT session and provider settings.
  Stored profiles and records are untouched.
- `--scope data` - quarantines unreadable encrypted rows only. Readable
  records are not deleted.
- `--scope all` - all three of the above: a full wipe. There is no default
  scope; the command refuses to run without an explicit `--scope`.

Before any reset, export profiles you want to keep with
`aeat config profile export`. See
[Set up your taxpayer profile](profile-setup.md).

## Next steps

- [Set up your taxpayer profile](profile-setup.md) - create, export, and
  import profiles.
- [Diagnose and repair your local setup](troubleshooting.md) - for storage
  or integrity problems that do not need a reset.
- [CLI reference](../cli/index.rst) - full option reference.
