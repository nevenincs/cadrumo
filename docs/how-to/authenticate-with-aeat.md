# Authenticate with AEAT

Use this guide before a command needs read-only live access to AEAT, such as
pulling Modelo 036 census information.

Authentication is local setup for read access. It does not let `aeat` submit
filings, register Modelo 036 changes, or modify AEAT records.

## See supported providers

List providers:

```bash
aeat config auth providers
```

Available providers include:

- `certificate` — your digital certificate file (certificado digital)
- `clave_pin` — Cl@ve PIN (a one-time code system from AEAT)
- `clave_permanente` — Cl@ve Permanente (a username and password for
  government services)
- `clave_movil` — mobile-based Cl@ve
- `dnie_pkcs` — the national ID card (DNI electrónico)

## Configure a provider

Configure the provider you use:

```bash
aeat config auth configure --provider certificate --file ./certificate.p12
```

Use `--file` for providers that need a file, such as your digital certificate.
Keep credential files private and do not share them.

## Check local readiness

Check what is configured:

```bash
aeat config auth status
aeat config auth test
```

Use `--provider` with either command when you want to inspect a specific
provider.

## Acquire or verify a live session

When you are ready to use a live-read command:

```bash
aeat config auth login
```

Force a fresh authentication when needed:

```bash
aeat config auth login --fresh
```

Use `--reset-lock` only when a previous login was interrupted and left the
authentication step stuck. Run it if `login` reports that another login is
already in progress when it is not.

## Clear local auth metadata

Clear one provider:

```bash
aeat config auth clear --provider certificate
```

Clear sessions or locks:

```bash
aeat config auth clear --sessions
aeat config auth clear --locks
```

Clear all configured providers only when you intend to reset authentication
setup:

```bash
aeat config auth clear --all
```

## Act for someone else (apoderado)

If you act as an authorized tax representative for another taxpayer (a
gestor, asesor, or authorized agent), record locally who you represent and
under which AEAT apoderamiento scopes.

The apoderamiento itself is granted at AEAT: the represented party authorizes
you through AEAT's own apoderamiento procedures. The commands below only
record that grant in your local profile so live-read commands know whose data
they read. They never register, extend, revoke, or renounce an apoderamiento
at AEAT — there is no command that writes representation state to AEAT.

### See the accepted scopes

List the scope codes the tool accepts:

```bash
aeat config auth apoderado scopes list
```

Each scope is an AEAT apoderamiento area, and some bind specific modelos —
for example `RENT` (modelos 100, 714), `IVA` (303, 390), `PAGOSF` (130, 131),
`RETEN` (withholding modelos), plus `GENERALNT`, `CENSO`, `INFORM`,
`NOTIFIC`, and `EXPED`.

### Record who you represent

Set the represented party's tax identifier (NIF, CIF, DNI, NIE, or NII) and
the scopes that match the grant at AEAT:

```bash
aeat config auth apoderado configure --represented-nif <nif> --scope IVA --scope PAGOSF
```

Repeat `--scope` for each code — a comma-separated list is rejected. Scope
codes are uppercase. Use `--scope ALL` to record every catalogue scope at
once. Unknown codes are refused with the accepted set named.

The active profile holds at most one apoderado configuration; configuring
again replaces it. The represented identifier is stored encrypted.

### Review or retire the configuration

Show what is recorded for the active profile:

```bash
aeat config auth apoderado status
```

`aeat config auth apoderado check` re-reads the same stored configuration; it
does not contact AEAT.

Remove the configuration when the representation ends:

```bash
aeat config auth apoderado clear
```

Clearing removes only the local record. The apoderamiento at AEAT is
unaffected — revoke it through AEAT's own procedures.

## Next steps

- [Link Modelo 036 census information](censo-update.md)
- [Set up your taxpayer profile](profile-setup.md)
- [Diagnose and repair your local setup](troubleshooting.md)
