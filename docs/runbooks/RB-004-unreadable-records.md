# RB-004 Recover unreadable encrypted records

A command reports corrupt or unreadable encrypted data. Check integrity, move
unreadable records aside so other commands work, and recover them if the cause
was a missing key.

## When to use this

- A command reports corrupt, unreadable, or drifted stored data.
- An integrity check names a failing record.
- Unreadable records block commands that should otherwise run.

## What you will need

- The affected profile, active.
- Your master-key passphrase, or your recovery key if the passphrase is lost.

## Fix it

Check the security seals on your encrypted records and the tax-rule definitions:

```bash
aeat config repair integrity objects
aeat config repair integrity registry
```

If either fails, the report names the affected item. Do not edit stored data by
hand.

When unreadable records block other commands, move them aside. Preview first,
then apply - the preview lists how many records would move, per storage area,
without changing anything:

```bash
aeat config repair quarantine --dry-run
aeat config repair quarantine --yes
```

Quarantine deletes nothing. Each unreadable record is moved, still encrypted,
into a quarantine archive inside the same storage; readable records are
untouched. If the cause was a missing key you later recover - for example with
your recovery key - the archived records still exist. See [Protect access to
your data](../how-to/protect-data-access.md) for recovery-key steps.

## Confirm the fix

Re-run the integrity check and confirm it no longer names the record, then retry
the command that failed:

```bash
aeat config repair integrity objects
```

If the check passes and the blocked command now runs, the recovery is complete.

## Why this happens

Every sensitive record is stored encrypted and sealed. A record becomes
unreadable when its key is unavailable or its seal no longer matches - for
example after a passphrase change without the matching key, or storage
corruption. Quarantine isolates the unreadable records so the rest of your data
stays usable while you recover the key.

## Related

- [Protect access to your data](../how-to/protect-data-access.md) - recovery
  keys, passphrase changes, and recovery.
- [Diagnose and repair your local setup](../how-to/troubleshooting.md) - the
  full diagnostic toolbox.
