# RB-005 A modelo does not apply, or a calculation is not ready

A modelo you expected does not appear, appears when you did not expect it, or a
calculation refuses because the profile is incomplete. Check what applies to
your profile and why, then complete the missing facts.

## When to use this

- A modelo you expected to prepare is not listed for you.
- A calculation refuses because the profile is incomplete for that modelo.
- The wrong taxpayer's modelos or numbers appear.

## What you will need

- The profile you are preparing for, active.
- Your master-key passphrase.

## Fix it

First confirm the right profile is active. Each profile keeps its own ledger,
calculations, and filings, so a command run under the wrong one shows someone
else's data:

```bash
aeat config profile status
```

Switch if it is wrong - see [Set up your taxpayer
profile](../how-to/profile-setup.md):

```bash
aeat config switch <profile-name>
```

Ask which modelos apply to you and why, from your saved profile facts:

```bash
aeat app modelo list
aeat app overview explain 303 --year 2026
```

Replace `303` and `2026` with the modelo and year you are checking. `overview
explain` names the profile facts that make a modelo apply or not apply to you.

Check readiness for a specific modelo, year, and period:

```bash
aeat config profile preflight --modelo 303 --filing-year 2026 --period 1T
```

The preflight report names the profile facts that are missing. Supply them by
editing the profile:

```bash
aeat config profile edit <profile-name>
```

If a modelo does not apply to you at all, the facts that would make it apply -
your activities, residency, or registrations - are not in your profile. Correct
them the same way, or leave the modelo out if it genuinely does not apply. See
[Which modelos apply to you](../how-to/choose-modelo.md).

## Confirm the fix

Re-run the readiness check and confirm it names no missing facts, then run the
calculation:

```bash
aeat config profile preflight --modelo 303 --filing-year 2026 --period 1T
aeat app modelo work calculate --modelo 303 --year 2026 --period 1T
```

When preflight reports the modelo is ready and the calculation runs, the profile
is complete for that filing.

## Why this happens

Which modelos apply to a taxpayer is derived from saved profile facts - your
activities, residency, and registrations. A modelo that needs a fact you have
not declared is either absent from your list or refuses to calculate rather than
producing a return on incomplete facts.

## Related

- [Which modelos apply to you](../how-to/choose-modelo.md) - ask what applies
  and why.
- [Set up your taxpayer profile](../how-to/profile-setup.md) - create, switch,
  and edit profiles.
- [Diagnose and repair your local setup](../how-to/troubleshooting.md) - the
  full symptom index.
