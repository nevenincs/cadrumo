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

When available to your identity, the command-line interface (CLI) can read filed declarations, expedientes, notifications, and AEAT receipts. To pull your census address into your profile, use the [census facts guide](censo-update.md).

## Before you start

You need:

- an [active profile](profile-setup.md#what-the-active-profile-means). `aeat
  config auth configure` refuses with `No active profile.` until you
  create one. Start the interactive wizard (it asks for your NIF or NIE; for
  a Spanish citizen, the NIF is the DNI number plus letter). It prompts for
  the profile passphrase and offers an optional recovery code once the
  profile exists:

  ```{cli-sequence} authenticate-profile
  :verify: Review interactive profile creation and confirm a profile is active.
  ```

- the passphrase that protects your local store; the tool prompts for it.
- the `browser` extra, because `aeat config auth login` and every live read
  drive a browser. Install it with `pip install "cadrumo[browser]"`, or follow
  [Install Cadrumo](../workstation-setup.md).

The examples in this documentation are recorded in English. `aeat` prints its
messages in Spanish unless you [choose another
language](profile-setup.md#choose-the-output-language).

## See supported providers

List providers:

```{cli-sequence} authenticate-providers
:verify: Confirm the tool lists the supported authentication providers.
```

Cadrumo supports three providers:

- `certificate`: your digital certificate file (certificado digital).
- `clave_movil`: mobile-based Cl@ve, confirmed on your phone.
- `clave_permanente`: Cl@ve Permanente, a DNI/NIE and password login.

Pass the identifier to `--provider`. Cl@ve PIN and the electronic national ID
card (DNI electrónico) are not supported.

## Configure a provider

Configure the provider you use:

```{cli-sequence} authenticate-configure
```

Use `--file` for providers that need a file, such as your digital certificate.
Keep credential files private and do not share them.

The command stores the provider choice and the certificate path, never a
secret. Supply the secrets separately:

- `certificate`: bind the passphrase to a registered certificate source with
  `aeat config auth certificate secret set`, or set the
  `CADRUMO_CERTIFICATE_PASSWORD_SECRET` environment variable.
- `clave_permanente`: set `CADRUMO_CLAVE_PERMANENTE_DNI_NIE` and
  `CADRUMO_CLAVE_PERMANENTE_PASSWORD`.
- `clave_movil`: set `CADRUMO_CLAVE_MOVIL_DNI_NIE`.

The [environment overrides reference](../reference/environment-overrides.md)
describes these variables.

## Check local readiness

Check what is configured:

```{cli-sequence} authenticate-readiness
:verify: Confirm the tool reports what is configured and probes it locally.
```

If you want to inspect a specific provider, use `--provider` with either
command.

(renew-your-certificate-before-it-expires)=
## Renew your certificate before it expires

A digital certificate has an expiry date. The tool reads that date from the
certificate file and warns you as it approaches. This helps you avoid a failed
live read caused by an expired certificate.

Check the remaining validity:

```{cli-sequence} authenticate-check-validity
:verify: Confirm the local probe reports the certificate's remaining validity.
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
```

If the renewed file uses a new password, register it as a
[named certificate source](#manage-several-certificates) if it is not one yet,
then rotate the stored passphrase for that source. `secret set` refuses a name
that is not registered. It prompts without
echo, or reads `{"certificate_passphrase": "..."}` from `--secrets-stdin` or
`--secrets-fd`:

```{cli-sequence} authenticate-secret-set
```

Confirm the new expiry:

```{cli-sequence} authenticate-confirm-expiry
:verify: Confirm the local probe reports the renewed certificate's later expiry.
```

The report now shows the renewed certificate's later expiry date.

## Manage several certificates

If you act for several entities, register one certificate per entity. Do not
reconfigure `aeat config auth configure --file` every time you switch.

Register each certificate under a name:

```{cli-sequence} authenticate-certificate-register
```

List every registered certificate:

```{cli-sequence} authenticate-certificate-list
:verify: Confirm the tool lists the registered certificates.
```

Select the one you want active:

```{cli-sequence} authenticate-certificate-select
```

Remove a registered certificate you no longer need:

```{cli-sequence} authenticate-certificate-remove
:verify: Confirm the tool removes a registered certificate by name.
```

### Check every registered certificate's expiry

Each registered certificate has its own expiry date. Check all registered
certificates in one pass, not only the active one:

```{cli-sequence} authenticate-certificate-check
:verify: Confirm the tool checks every registered certificate's expiry in one pass.
```

The report lists each registered certificate with its status:

- `ok`: valid, with the days remaining.
- `expiring`: within the renewal window (60 days or fewer by default, or 14
  days or fewer for the critical window). A warning names the certificate.
- `expired`: already expired. A warning names the certificate.
- `file_missing`, `unreadable`, or `corrupt`: Cadrumo cannot read the file, or
  cannot open it with the stored passphrase.

Renew an expiring or expired certificate with the body that issued it, then
re-register it under its existing name:

```{cli-sequence} authenticate-certificate-reregister
```

Re-run `aeat config auth certificate check` to confirm the new expiry date.

(acquire-or-verify-a-live-session)=
## Start or check a live session

When you are ready to use a live-read command:

```{cli-sequence} authenticate-login
```

If you need to intentionally reauthenticate, force a fresh authentication:

```{cli-sequence} authenticate-login-fresh
```

If a previous login was interrupted and left the authentication step stuck, use
`--reset-lock`. Run it when `login` reports another login is in progress but it
is not.

## End sessions or reset authentication

To end the local certificate-provider session without removing its
configuration:

```{cli-sequence} authenticate-logout-provider
:verify: Confirm logout ends the local session while preserving the provider configuration.
```

To remove one provider's local configuration, sessions, sign-in lock, registered
certificates, and stored certificate secrets:

```{cli-sequence} authenticate-reset-provider
:verify: Confirm reset removes the selected provider's local authentication state.
```

To remove local authentication state for every configured provider:

```{cli-sequence} authenticate-reset-all
:verify: Confirm reset removes local authentication state for all configured providers.
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
```

Each scope is an AEAT apoderamiento area. Examples include:

- `RENT` for Modelos 100 and 714.
- `IVA` for Modelos 303 and 390.
- `PAGOSF` for Modelos 130 and 131.
- `RETEN` for withholding modelos.
- `GENERALNT`, `CENSO`, `INFORM`, `NOTIFIC`, and `EXPED` for their respective
  authority areas.

### Record who you represent

Set the represented party's tax identifier (a NIF or NIE) and the scopes that
match the grant at AEAT:

```{cli-sequence} authenticate-apoderado-configure
:verify: Confirm the tool records the represented party and scopes locally.
```

Repeat `--scope` for each code. The CLI rejects a comma-separated list. Scope
codes are uppercase. Use `--scope ALL` to record every catalogue scope at
once. The CLI rejects unknown codes. Without any `--scope`, it refuses with a
message that lists the accepted codes.

The active profile holds at most one apoderado configuration; configuring
again replaces it. The represented identifier is stored encrypted.

### Review or retire the configuration

Show what is recorded for the active profile:

```{cli-sequence} authenticate-apoderado-status
:verify: Confirm the tool shows the apoderado configuration recorded locally.
```

`aeat config auth apoderado check` is the command for the live check, but the live check is not available. It refuses with `The live check of representatives is unavailable, or contact with the AEAT failed.` Use `aeat config auth apoderado status` for the offline configuration read.

Remove the configuration when the representation ends:

```{cli-sequence} authenticate-apoderado-clear
:verify: Confirm the tool removes the local apoderado record.
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
