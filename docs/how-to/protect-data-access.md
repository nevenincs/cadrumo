# Protect access to your data

Everything aeat stores — profiles, transactions, evidence, filings — is
encrypted under one master key. Your passphrase opens that key. If you lose
the passphrase and have no recovery key, the data cannot be decrypted by
anyone, including you.

Use this guide to set up a recovery key before you need it, change your
passphrase, recover access after a lost passphrase, lock the session, and —
as a last resort — wipe local state and start over.

## Create your recovery key first

Do this once, right after setup, while your passphrase still works:

```bash
aeat config show-recovery
```

If no recovery key exists yet, the command creates one and prints a list of
recovery words. The words are shown exactly once and are never stored — only
an encrypted wrapper of the master key is written to disk. Write the words
down and keep them offline, separate from your computer.

Run the same command again later to confirm enrollment: once a recovery key
exists, the command reports its status and does not print the words again.

## Check that your recovery key works

Verify the words you wrote down without changing anything:

```bash
aeat config verify-recovery --recovery-key "word1 word2 word3 ..."
```

The command reports `verified yes` or `verified no` and exits with a failure
code when the words do not open the recovery wrapper. Nothing is modified
either way.

## Replace the recovery key

If the written words may have been seen by someone else, mint a fresh
recovery key:

```bash
aeat config show-recovery --rotate
```

New words are printed exactly once. The previous recovery words stop working
immediately. Store the new words as before.

## Change your passphrase

To change the passphrase while you still know the current one:

```bash
aeat config rekey
```

The command asks for the current passphrase if the store is not already
open, then prompts twice (hidden) for the new one. The master key itself
does not change, so all stored data stays readable — only the passphrase
that opens it is replaced. For non-interactive use, pass `--new-passphrase`
together with `--confirm-new-passphrase`.

## Recover after a forgotten passphrase

If you forgot the passphrase but have your recovery words:

```bash
aeat config recover --recovery-key "word1 word2 word3 ..."
```

The command prompts twice (hidden) for a new passphrase, unlocks the master
key from the recovery wrapper, and rewraps it under the new passphrase. All
stored data stays intact — nothing is deleted or re-encrypted.

If you have neither the passphrase nor the recovery words, the encrypted
data is permanently unreadable. The only way forward is a reset (below),
which deletes it.

## Lock the session

Clear the active-profile selection so commands stop operating on your data
until a profile is selected again:

```bash
aeat config lock
```

Nothing is deleted — locking only clears the active-profile pointer. Select
a profile again with `aeat config switch <name>` when you return.

## Reset local state — last resort

Reset deletes operator-local state. It is not recoverable. The command
refuses to run without `--yes`:

```bash
aeat config reset --scope profile --yes
```

Pick the scope deliberately:

- `--scope profile` — deletes every profile and its stored data, including
  archived profiles.
- `--scope auth` — clears the saved AEAT session and provider settings.
  Stored profiles and records are untouched.
- `--scope data` — quarantines unreadable encrypted rows only. Readable
  records are not deleted.
- `--scope all` — all three of the above: a full wipe. There is no default
  scope; the command refuses to run without an explicit `--scope`.

Before any reset, export profiles you want to keep with
`aeat config profile export` — see
[Set up your taxpayer profile](profile-setup.md).

## Next steps

- [Set up your taxpayer profile](profile-setup.md) — create, export, and
  import profiles.
- [Diagnose and repair your local setup](troubleshooting.md) — for storage
  or integrity problems that do not need a reset.
- [CLI reference](../cli/index.rst) — full option reference.
