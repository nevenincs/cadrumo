# Diagnose and repair your local setup

When a command refuses, the active profile won't load, or your stored data or
registry looks wrong, the `aeat config repair` commands diagnose and fix your
local state. Every check here runs locally and never contacts the Agencia
Estatal de Administración Tributaria (AEAT), except the optional connectivity
probe, which only checks reachability and reads nothing.

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

`integrity objects` checks the security seals on your encrypted records;
`integrity registry` checks the tax rule definitions. If either fails, the
report names the affected item. Take that report to the issue tracker rather
than editing stored data by hand.

## Repair the active profile setting

If `aeat app` commands refuse with a no-active-profile message but a profile does
exist, repair the active profile configuration setting:

```
aeat config repair profile
```

It inspects and repairs the active profile configuration. If the active profile setting targets
unreadable profile state, clear it with `aeat config repair profile
--clear-active`, then switch to a good profile.

## Reset workflow state as a last resort

If workflow state itself is unreadable and nothing else recovers it, discard the
unreadable wrapper:

```
aeat config repair reset-state --yes
```

This removes the saved progress state for interrupted commands. It is
destructive and requires `--yes`. Use it only when nothing else recovers the
problem.

## Authentication and connectivity

These steps apply only if you use live data reads from the AEAT portal. Live
reads require AEAT authentication — a registered digital certificate or Cl@ve
PIN (the digital identity system Spain uses for citizens to log in to government
services online). Check your authentication:

```
aeat config auth status
aeat config auth test
```

Check that the tool can reach the AEAT website (Sede Electrónica, the official
online portal):

```
aeat config repair connectivity

```

## Where next

- [Quickstart: produce a modelo file](quickstart.md) - follow the first local
  filing path.
- [Set up your taxpayer profile](profile-setup.md) - create and switch profiles.
- [Authenticate with AEAT](authenticate-with-aeat.md) - check read-only live
  access setup.
- [Check AEAT notifications](check-aeat-notifications.md) - inspect saved DEHu
  notification snapshots.
- [Pipeline explanation](../explanation/index.md) - what the registry, secure
  storage, and workflow state are.
- [CLI reference](../cli/index.rst) - every repair command, flag, and exit code.
