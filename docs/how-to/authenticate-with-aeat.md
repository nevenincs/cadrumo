# Authenticate Cadrumo with AEAT

Authenticate Cadrumo with Spain's Tax Agency, the Agencia Estatal de
Administración Tributaria (AEAT), to let Cadrumo's `aeat` command read information
your AEAT identity authorizes. Authentication provides read-only access only.
It never files a declaration, makes a payment, acknowledges a notification, or
performs representative-write actions.

Run `aeat --help` before continuing. If it fails, stop before configuring
authentication and follow the [CLI troubleshooting guide](troubleshooting.md).
If that does not restore the command, report the failure with the Cadrumo
version and redacted output.

When available to your identity, the command-line interface (CLI) can read
filed declarations, expedientes, notifications, and filed justificantes. For
Modelo 036/Censo profile facts, use the [profile/Censo facts guide](censo-update.md).
Cadrumo no longer retrieves these facts live.

## Before you start

You need:

- an [active profile](profile-setup.md#what-the-active-profile-means). `aeat
  config auth configure` refuses with `No hay un perfil activo` until you
  create one. Create one non-interactively (a NIF, CIF, DNI, or NIE is a
  Spanish tax identifier):

  ```{cli-sequence} authenticate-profile
  :verify: Confirm a taxpayer profile can be created non-interactively.
  @step Create a taxpayer profile non-interactively (use your own NIF, CIF, DNI, or NIE).
  @result aeat config profile create me --quiet --entity-type natural_person --tax-id 87654321X --name "Ana" --surnames "Garcia Lopez"
  @expect exit_code == 0
  ```

- the master-key passphrase that protects your local store; the tool
  prompts for it.

## See supported providers

List providers:

```{cli-sequence} authenticate-providers
:verify: Confirm the tool lists the supported authentication providers.
@step List the supported authentication providers and their availability.
@result aeat config auth providers
@expect exit_code == 0
```

The list marks each provider as `disponible` (available now) or `reservado (no
disponible aún)` (reserved, not available yet). Three are available:

- `certificate`: your digital certificate file (certificado digital).
- `clave_movil`: mobile-based Cl@ve, confirmed on your phone.
- `clave_permanente`: Cl@ve Permanente, a DNI/NIE and password login.

Two more are listed but reserved, so you cannot configure them yet:

- `clave_pin`: Cl@ve PIN, a one-time code system from AEAT. Reserved.
- `dnie_pkcs`: the national ID card (DNI electrónico). Reserved.

Configure one of the available providers.

## Configure a provider

Configure the provider you use:

```{cli-sequence} authenticate-configure
@step Configure a provider that needs a file, such as your digital certificate.
@static aeat config auth configure --provider certificate --file ./certificate.p12
```

Use `--file` for providers that need a file, such as your digital certificate.
Keep credential files private and do not share them.

## Check local readiness

Check what is configured:

```{cli-sequence} authenticate-readiness
:verify: Confirm the tool reports what is configured and probes it locally.
@step Show what authentication is configured.
aeat config auth status
@step Probe the stored credentials locally, without contacting AEAT.
@result aeat config auth test
@expect exit_code == 0
```

If you want to inspect a specific provider, use `--provider` with either
command.

## Renew your certificate before it expires

A digital certificate has an expiry date. The tool reads that date from the
certificate file and warns you as it approaches. This helps you avoid a failed
live read caused by an expired certificate.

Check the remaining validity:

```{cli-sequence} authenticate-check-validity
:verify: Confirm the local probe reports the certificate's remaining validity.
@step Read the certificate's remaining validity from the local probe.
@result aeat config auth test
@expect exit_code == 0
```

The report tells you how the certificate stands:

- More than 60 days left: the certificate is valid and reports the days
  remaining.
- 60 days or fewer left: a warning appears: `The certificate expires in N
  days. Plan the renewal.` Start the renewal now.
- 14 days or fewer left: the warning is critical. Renew before your next live
  read.
- Already expired: `The certificate expired N days ago. Renew it before
  authenticating.` A live read is refused until you replace it.

Renew the certificate with the body that issued it, such as the Fábrica
Nacional de Moneda y Timbre (FNMT) or AEAT. This happens outside the tool.
Download the renewed certificate file (`.p12` or `.pfx`) to your machine.

Point the tool at the renewed file:

```{cli-sequence} authenticate-configure-renewed
@step Point the tool at the renewed certificate file.
@static aeat config auth configure --provider certificate --file ./renewed-certificate.p12
```

If the renewed certificate uses a new password, rotate the stored
passphrase for its source:

```{cli-sequence} authenticate-secret-set
@step Rotate the stored passphrase for the certificate source.
@static aeat config auth certificate secret set --name personal
```

Confirm the new expiry:

```{cli-sequence} authenticate-confirm-expiry
:verify: Confirm the local probe reports the renewed certificate's later expiry.
@step Read the renewed certificate's expiry from the local probe.
@result aeat config auth test
@expect exit_code == 0
```

The report now shows the renewed certificate's later expiry date.

## Manage several certificates

If you act for several entities, register one certificate per entity. Do not
reconfigure `aeat config auth configure --file` every time you switch.

Register each certificate under a name:

```{cli-sequence} authenticate-certificate-register
@step Register a certificate under a name.
@static aeat config auth certificate register --name personal --file ./personal.p12
@step Register another certificate with a friendly name.
@static aeat config auth certificate register --name apoderado-acme --file ./acme.p12 --friendly-name "ACME SL"
```

List every registered certificate:

```{cli-sequence} authenticate-certificate-list
:verify: Confirm the tool lists the registered certificates.
@step List every registered certificate.
@result aeat config auth certificate list
@expect exit_code == 0
```

Select the one you want active:

```{cli-sequence} authenticate-certificate-select
@step Select the registered certificate you want active.
@static aeat config auth certificate select --name apoderado-acme
```

Remove a registered certificate you no longer need:

```{cli-sequence} authenticate-certificate-remove
:verify: Confirm the tool removes a registered certificate by name.
@step Remove a registered certificate you no longer need.
@result aeat config auth certificate remove --name personal
@expect exit_code == 0
```

### Check every registered certificate's expiry

Each registered certificate has its own expiry date. Check all registered
certificates in one pass, not only the active one:

```{cli-sequence} authenticate-certificate-check
:verify: Confirm the tool checks every registered certificate's expiry in one pass.
@step Check every registered certificate's expiry.
@result aeat config auth certificate check
@expect exit_code == 0
```

The report lists each registered certificate with its status:

- `ok`: valid, with the days remaining.
- `expiring`: within the renewal window (60 days or fewer by default, or 14
  days or fewer for the critical window). A warning names the certificate.
- `expired`: already expired. A warning names the certificate.

Renew an expiring or expired certificate with the body that issued it, then
re-register it under its existing name:

```{cli-sequence} authenticate-certificate-reregister
@step Re-register a renewed certificate under its existing name.
@static aeat config auth certificate register --name apoderado-acme --file ./renewed-acme.p12
```

Re-run `aeat config auth certificate check` to confirm the new expiry date.

## Acquire or verify a live session

When you are ready to use a live-read command:

```{cli-sequence} authenticate-login
@step Acquire or verify a live AEAT session.
@static aeat config auth login
```

If you need to intentionally reauthenticate, force a fresh authentication:

```{cli-sequence} authenticate-login-fresh
@step Force a fresh authentication.
@static aeat config auth login --fresh
```

If a previous login was interrupted and left the authentication step stuck, use
`--reset-lock`. Run it when `login` reports another login is in progress but it
is not.

## Clear saved authentication

Clear one provider:

```{cli-sequence} authenticate-clear-provider
:verify: Confirm the tool clears the saved authentication for one provider.
@step Clear the saved authentication for one provider.
@result aeat config auth clear --provider certificate
@expect exit_code == 0
```

Clear sessions or locks:

```{cli-sequence} authenticate-clear-sessions
@step Clear saved sessions.
@static aeat config auth clear --sessions
@step Clear saved locks.
@static aeat config auth clear --locks
```

If you intend to reset authentication setup, clear all configured providers:

```{cli-sequence} authenticate-clear-all
@step Clear all configured providers.
@static aeat config auth clear --all
```

## Act for someone else (apoderado)

If you act as an authorized tax representative for another taxpayer, record
locally who you represent and the relevant AEAT apoderamiento scopes. An
apoderado is an authorized representative, such as a gestor or asesor.

The apoderamiento itself is granted at AEAT. The represented party authorizes
you through AEAT's own apoderamiento procedures. The commands in this section
record that grant in your local profile so read commands know whose data they
read. They never register, extend, revoke, or renounce an apoderamiento at
AEAT. No command writes representation state to AEAT.

### See the accepted scopes

List the scope codes the tool accepts:

```{cli-sequence} authenticate-apoderado-scopes
:verify: Confirm the tool lists the accepted apoderamiento scope codes.
@step List the scope codes the tool accepts.
@result aeat config auth apoderado scopes list
@expect exit_code == 0
```

Each scope is an AEAT apoderamiento area. Examples include:

- `RENT` for modelos 100 and 714.
- `IVA` for modelos 303 and 390.
- `PAGOSF` for modelos 130 and 131.
- `RETEN` for withholding modelos.
- `GENERALNT`, `CENSO`, `INFORM`, `NOTIFIC`, and `EXPED` for their respective
  authority areas.

### Record who you represent

Set the represented party's tax identifier (NIF, CIF, DNI, NIE, or NII) and
the scopes that match the grant at AEAT:

```{cli-sequence} authenticate-apoderado-configure
:verify: Confirm the tool records the represented party and scopes locally.
@step Record who you represent and the scopes that match the grant at AEAT.
@result aeat config auth apoderado configure --represented-nif 11111111H --scope IVA --scope PAGOSF
@expect exit_code == 0
```

Repeat `--scope` for each code. The CLI rejects a comma-separated list. Scope
codes are uppercase. Use `--scope ALL` to record every catalogue scope at
once. The CLI rejects unknown codes and lists the accepted codes.

The active profile holds at most one apoderado configuration; configuring
again replaces it. The represented identifier is stored encrypted.

### Review or retire the configuration

Show what is recorded for the active profile:

```{cli-sequence} authenticate-apoderado-status
:verify: Confirm the tool shows the apoderado configuration recorded locally.
@step Show the apoderado configuration recorded for the active profile.
@result aeat config auth apoderado status
@expect exit_code == 0
```

`aeat config auth apoderado check` is the live-verification verb, but the
live AEAT read path is sealed. It refuses with a "live verification unavailable"
message and points you back to `status`. Use `aeat config auth apoderado status`
for the offline configuration read.

Remove the configuration when the representation ends:

```{cli-sequence} authenticate-apoderado-clear
:verify: Confirm the tool removes the local apoderado record.
@step Remove the local apoderado record when the representation ends.
@result aeat config auth apoderado clear
@expect exit_code == 0
```

Clearing removes only the local record. The apoderamiento at AEAT is
unaffected. Revoke it through AEAT's own procedures.

## Next steps

- [Maintain Modelo 036 census facts in your profile](censo-update.md)
- [Set up your taxpayer profile](profile-setup.md)
- [Diagnose and repair your local setup](troubleshooting.md)

Run `aeat config auth test` before each live-read task. Follow [Renew your
certificate before it expires](#renew-your-certificate-before-it-expires) when
the command reports an expiry warning.
