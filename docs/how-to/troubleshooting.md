# Diagnose and repair your local setup

When a command refuses, the active profile won't load, or your stored data or
registry looks wrong, the `aeat config repair` commands diagnose and fix your
local state. Every check here runs locally and never contacts the Agencia
Estatal de Administración Tributaria (AEAT), except the optional connectivity
probe, which only checks reachability and reads nothing. You need `aeat`
installed; if you don't have it yet, see [Get started](../getting-started.md).

## Start with status

Check your current state before you repair anything:

```
aeat app overview status
aeat config profile status
```

`overview status` reports your profile, ledger, and modelo readiness;
`profile status` reports the active profile. Together they tell you whether the
problem is your setup or your data, and point you at the repair below.

## Read the logs

When a command fails, read the log first:

```
aeat config repair logs --lines 50
```

It prints the log file path and the most recent lines. Use `--lines` to control
how many it prints.

## Check stored-data and registry integrity

If a command reports corrupt or unreadable data, check integrity:

```
aeat config repair integrity objects
aeat config repair integrity registry
```

`integrity objects` verifies the AES-256-GCM authentication tags on your
encrypted records; `integrity registry` runs full registry validation. If either
fails, the report names the affected namespace or registry fragment. Take that to
the issue tracker rather than editing stored data by hand.

## Repair the active-profile pointer

If `aeat app` commands refuse with a no-active-profile message but a profile does
exist, repair the pointer:

```
aeat config repair profile
```

It inspects and repairs the active-profile pointer. If the pointer targets
unreadable profile state, clear it with `aeat config repair profile
--clear-active`, then switch to a good profile.

## Reset workflow state as a last resort

If workflow state itself is unreadable and nothing else recovers it, discard the
unreadable wrapper:

```
aeat config repair reset-state --yes
```

This is destructive and requires `--yes`. Use it only when the state is
unreadable and nothing else recovers it.

## Authentication and connectivity

These matter only if you use read-only live data from the AEAT. Live reads
require configured AEAT authentication, such as a registered certificate or
Cl@ve session. Check your AEAT authentication:

```
aeat config auth status
aeat config auth test
```

Probe browser and Sede reachability with a read-only check:

```
aeat config repair connectivity --target browser
```

## Where next

- [Get started](../getting-started.md) - install the tool and run your first
  filing.
- [Set up your taxpayer profile](profile-setup.md) - create and switch profiles.
- [Pipeline explanation](../explanation/index.md) - what the registry, secure
  storage, and workflow state are.
- [CLI reference](../cli/index.rst) - every repair command, flag, and exit code.
