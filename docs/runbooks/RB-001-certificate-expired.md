# RB-001 Renew a certificate before it blocks live reads

Your digital certificate expired or is close to expiring, so live reads from
AEAT are blocked or about to be. Renew the certificate and register the new one.

## When to use this

- `auth test` warns `The certificate expires in N days`.
- `auth test` reports `The certificate expired N days ago. Renew it before ...`.
- A live pull refuses and points you at your authentication.

## What you will need

- The profile whose certificate is expiring, active.
- A renewed certificate file from your certificate authority.
- Your master-key passphrase (the tool prompts for it, or set
  `CADRUMO_SECRET_PASSPHRASE` first).

## Fix it

Check the current certificate and its expiry. `auth test` is a local probe - it
reads your stored credentials without contacting AEAT:

```bash
aeat config auth status
aeat config auth test
```

If the report warns about expiry or says the certificate already expired, renew
it. Follow [Renew your certificate before it
expires](../how-to/authenticate-with-aeat.md#renew-your-certificate-before-it-expires),
which walks through obtaining the new certificate file and registering it in
place of the old one.

## Confirm the fix

Run the local probe again and read the expiry line:

```bash
aeat config auth test
```

A renewed certificate reports a future expiry date and no warning. Live reads
work again.

## Why this happens

AEAT accepts a digital certificate or Cl@ve PIN as your identity for live reads.
A certificate is issued with a fixed validity window. Once it passes 60 days to
expiry the tool warns you; once it expires the tool refuses live reads rather
than sending an identity AEAT will reject.

## Related

- [Authenticate with AEAT](../how-to/authenticate-with-aeat.md) - set up and
  renew live-read authentication.
- [RB-002 A live read from AEAT is refused](RB-002-live-read-refused.md) - when
  the certificate is valid but the read still refuses.
- [Diagnose and repair your local setup](../how-to/troubleshooting.md) - the
  full symptom index.
