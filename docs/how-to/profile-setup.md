# Set up your taxpayer profile

A profile is your saved taxpayer identity and settings. Every `aeat app` command
runs against the one active profile and refuses to run when no profile is active,
so a profile is the first thing to set up. This guide creates your first profile and shows how
to keep several. You need `aeat` installed; if you don't have it yet, see
[Get started](../getting-started.md).

## Create your first profile

Have ready your NIF or NIE (your tax identity number), your name and surnames or
company name, your postcode, and your taxpayer type. Run the create command with
a name for the profile:

```
aeat config profile create my-profile
```

A short wizard asks for those details, including your taxpayer type - natural
person, legal entity, or attribution entity - and your IRPF (personal income tax)
income category. When
the wizard finishes, the profile is active. Confirm it:

```
aeat config profile status
aeat config profile show
```

## Switch between profiles

List your profiles and see which one is active:

```
aeat config profile list
```

Activate a different one:

```
aeat config profile switch my-other-profile
```

`aeat app` commands always run against the active profile and take no profile
argument, so switch first. Inspect any profile with `aeat config profile show`,
or check the active one with `aeat config profile status`.

## Manage your profiles

Use these when you manage more than one profile:

- Copy a profile under a new id: `aeat config profile duplicate <source> <target>`.
- Rename a profile, moving the active pointer with it:
  `aeat config profile rename <source> <target>`.
- Remove a profile and its local state: `aeat config profile delete <name> --yes`.
- Re-run the wizard over an existing profile: `aeat config profile edit <name>`.

## Your profile and your financial data

Your modelo calculations draw their figures from the classified ledger stored
under the active profile. Setting up that ledger - importing your records, then
classifying them - is the next step. The [tutorial](../tutorials/index.md) walks
through `aeat app ledger import` and `aeat app ledger classify`. For the terms
*ledger* and *classified*, see the [glossary](../glossary.md).

## Where next

- [Quickstart](quickstart.md) - produce a modelo file once a profile and ledger
  are ready.
- [Tutorial](../tutorials/index.md) - the full workflow, including the ledger.
- [Pipeline explanation](../explanation/index.md) - why `aeat` uses a profile,
  and how each figure traces to the law.
- [CLI reference](../cli/index.rst) - every profile command and its flags.
- [Glossary](../glossary.md) - the Spanish tax terms used here.
- Report a problem or ask a question on the
  [issue tracker](https://github.com/wgergely/aeat/issues).
