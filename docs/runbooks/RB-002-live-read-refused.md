# RB-002 A live read from AEAT is refused

A pull from AEAT refuses. Live reads need a registered digital certificate or
Cl@ve PIN and a reachable AEAT site. Check each in turn.

## When to use this

- A `pull` command refuses and points you at your authentication.
- The tool reports `No verified active AEAT session is available. Authenticate ...`.
- A live login fails and you do not know which part broke.

## What you will need

- The profile you want to read for, active.
- Your registered certificate or Cl@ve PIN.
- Your master-key passphrase.

## Fix it

Check your stored credentials. `auth test` is local - it inspects what you have
without contacting AEAT, and it also reports certificate expiry:

```bash
aeat config auth status
aeat config auth test
```

If `auth test` warns that the certificate expired or is expiring, follow
[RB-001 Renew a certificate](RB-001-certificate-expired.md) first.

Check that the tool can reach the AEAT site (Sede Electrónica, the official
online portal):

```bash
aeat config repair connectivity
```

If a live login failed, the tool saved an encrypted diagnostic of the failure.
List them and read the most recent one - sensitive content is redacted:

```bash
aeat config auth diagnostics list
aeat config auth diagnostics show <diagnostic-id>
```

For a Cl@ve failure, record what happened on your phone so the diagnostic is
complete:

```bash
aeat config auth diagnostics report <diagnostic-id> --phone-state app_prompted_not_accepted
```

Accepted phone states are `app_prompted_and_accepted`,
`app_prompted_not_accepted`, `app_did_not_prompt`, and `operator_did_not_check`.

If authentication was never set up, follow [Authenticate with
AEAT](../how-to/authenticate-with-aeat.md).

## Confirm the fix

Re-run the local probe, then retry the read that refused:

```bash
aeat config auth test
```

A clean probe reports valid, non-expiring credentials. The live pull works
again.

## Why this happens

Every live read carries your identity to AEAT. The tool refuses to send a read
when it has no usable identity, when the certificate has expired, or when it
cannot reach the AEAT site - a refusal you can fix locally is safer than a
request AEAT rejects.

## Related

- [Authenticate with AEAT](../how-to/authenticate-with-aeat.md) - set up
  read-only live access.
- [Read live AEAT data](../how-to/read-live-aeat-data.md) - what live reads
  cover and how to run them.
- [RB-001 Renew a certificate](RB-001-certificate-expired.md) - the expiry case.
- [Diagnose and repair your local setup](../how-to/troubleshooting.md) - the
  full symptom index.
