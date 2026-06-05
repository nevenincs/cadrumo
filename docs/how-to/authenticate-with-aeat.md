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

Current command help exposes providers such as `certificate`, `clave_movil`,
`clave_pin`, `clave_permanente`, and `dnie_pkcs`.

## Configure a provider

Configure the provider you use:

```bash
aeat config auth configure --provider certificate --file ./certificate.p12
```

Use `--file` for providers that need a credential file, such as a certificate
or key file. Keep credential files private and do not commit them to the
repository or attach them to support requests.

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

Use `--reset-lock` only when a previous authentication acquisition left a stale
local lock.

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

## Apoderado support

If you work as an authorized representative, inspect the apoderado surface:

```bash
aeat config auth apoderado --help
```

That command group has status, configure, clear, check, and scope-management
commands. Use command help for the exact options before changing apoderado
configuration.

## Next steps

- [Link Modelo 036 census information](censo-update.md)
- [Set up your taxpayer profile](profile-setup.md)
- [Diagnose and repair your local setup](troubleshooting.md)
