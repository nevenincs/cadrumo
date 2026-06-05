# Set up your taxpayer profile

Use this guide to create the local taxpayer profile that `aeat app` commands
use. The active profile is the one `aeat` reads and updates when you import
ledger records, calculate a modelo, or export a local file. A modelo is a
Spanish tax form.

Profiles are local. Creating or editing a profile does not contact the Agencia
Estatal de Administración Tributaria (AEAT).

## Before you start

You need `aeat` installed. If it is not installed, start with
[Get started with aeat](../getting-started.md).

Have these facts ready:

- Your Spanish identity or tax identifier:
  - Spanish citizens usually use Documento Nacional de Identidad (DNI).
  - Foreign individuals usually use Número de Identidad de Extranjero (NIE).
  - Companies and other legal entities use Número de Identificación Fiscal
    (NIF). If your records say Código de Identificación Fiscal (CIF), enter
    that identifier as requested by the command.
- Name and surnames, or company name
- Tax address postcode
- Taxpayer type, such as natural person or legal entity
- Business activity, as plain text or an Impuesto sobre Actividades Económicas
  (IAE) heading if you know it
- Impuesto sobre la Renta de las Personas Físicas (IRPF) income category, the
  personal income tax category for the income you report
- Impuesto sobre el Valor Añadido (IVA) regime, the value-added tax regime for
  the activity
- Output language for command responses

## Create the profile with the wizard

Run `create` with a profile name you recognize, such as `my-profile`:

```
aeat config profile create my-profile
```

Answer the prompts. The wizard asks only the questions that apply to the choices
you make. When it finishes, the new profile becomes active.

## Confirm the active profile

Check which profile is active:

```
aeat config profile status
```

Inspect the saved facts:

```
aeat config profile show
```

Fix any wrong facts before you import ledger records or calculate a modelo.

## Create a profile without prompts

Use non-interactive creation only when the wizard cannot ask questions, such as
inside a script. Pass `--quiet`, and add `--accept-defaults` when you want `aeat`
to fill any omitted facts from its defaults.

This example creates a natural-person profile for an economic activity. First
create the profile with the facts required for profile status checks:

```
aeat config profile create my-profile --quiet --accept-defaults --tax-id 12345678Z --activity "graphic design"
```

Then add the name and filing facts:

```
aeat config profile edit my-profile --quiet --name "Ana" --surnames "Garcia Lopez"
aeat config profile edit my-profile --quiet --address-postcode 28013 --entity-type natural_person
aeat config profile edit my-profile --quiet --irpf-income-categories actividad_economica --iva-regime GENERAL --output-language en
```

Use the [CLI reference](../cli/index.rst) for the full flag list and accepted
values.

## Update profile facts

Use `edit` to change an existing profile:

```
aeat config profile edit my-profile
```

For a single scripted change, pass `--quiet` and the field you want to change:

```
aeat config profile edit my-profile --quiet --address-postcode 28014
```

Run `status` or `show` again after editing.

## Switch between profiles

List your profiles:

```
aeat config profile list
```

Switch before you work on another taxpayer:

```
aeat config profile switch my-other-profile
```

Run `aeat config profile status` after switching if you are not sure which
profile is active.

## Check the profile

Validate the active profile against the profile schema:

```
aeat config profile validate
```

To validate another profile without switching:

```
aeat config profile validate my-other-profile
```

Modelo-specific checks need a modelo, registry revision, filing year, and
period. For those checks, see
`aeat config profile preflight --modelo ... --revision-id ... --filing-year ... --period ...`
in the [CLI reference](../cli/index.rst).

## Manage profile records

Copy a profile when you need a second profile that starts from the same facts:

```
aeat config profile duplicate my-profile my-copy
```

Rename a profile:

```
aeat config profile rename my-profile new-profile-name
```

Delete a profile only when you mean to remove it from normal use:

```
aeat config profile delete old-profile --yes
```

`--yes` is required. Deletion is a local operation, but it is destructive.
The profile stops being available for ordinary `list`, `switch`, and `app`
workflows. If it was active, `aeat` clears the active-profile pointer.

## If a command stops with an error

If a command reports that no profile is active, a field value is invalid, or you
are working under the wrong profile, use
[Diagnose and repair your local setup](troubleshooting.md).

## Next steps

- [Import and classify a bank statement](import-bank-statements.md)
- [Plan your filing calendar](filing-calendar.md)
- [CLI reference](../cli/index.rst)
