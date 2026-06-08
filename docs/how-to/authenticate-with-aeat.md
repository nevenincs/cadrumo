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

## Authorized representative (apoderado)

If you act as an authorized tax representative for someone else (a gestor,
asesor, or authorized agent), inspect the representative access commands:

```bash
aeat config auth apoderado --help
```

Those commands let you set up, check, and clear representative access scopes.
Run the help command first to see the available options before changing
anything.

## Next steps

- [Link Modelo 036 census information](censo-update.md)
- [Set up your taxpayer profile](profile-setup.md)
- [Diagnose and repair your local setup](troubleshooting.md)
