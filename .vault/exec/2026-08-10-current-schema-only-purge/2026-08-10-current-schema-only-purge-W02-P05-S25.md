---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:933e5015da2d8811b5ce1fdf8b1b61eab736d41cbf3e9f08f66fc4b3589f9a6c'
step_id: 'S25'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Gate the encrypted-bundle kdf_version marker against the current Argon2 version

## Scope

- `src/cadrumo/application/user_profile/_bundle_encryption.py`
- `src/cadrumo/adapters/persistence/storage/__init__.py`

## Description

- Promote the Argon2 version constant onto its owning package's public facade.
- Gate the transport envelope's declared KDF version against that constant with
  exact equality.
- Record in the code why the neighbouring constant is the wrong authority.
- Extend the strip-marker and non-current refusals to this fourth marker, and
  assert the stamped value on the positive round trip.

## Outcome

Landed in `f85256509f`.

The marker was stamped onto every exported bundle and never checked, so a bundle
claiming a key-derivation version this build does not implement decrypted under
parameters it had never agreed to. Its three sibling markers on the same record
were already required and gated; this one was required and ungated.

The promotion was a precondition rather than a follow-up: the constant is
declared in a private module of the storage package and was exported by no
facade, with no importers anywhere. It went onto the STORAGE facade, which owns
the module, rather than the master-key facade the consumer already imports two
other symbols from -- re-exporting one package's symbol through a sibling would
be a bridge.

## Notes

The first attempt at this row was briefed against the WRONG authority and was
refused before any edit. The lead named the constant whose name matched the
concept -- the on-disk KDF parameter record shape, value 2 -- while the writer
stamps the Argon2 ALGORITHM version, value 19. Gating as briefed would have
compared 19 against 2 and refused every bundle this build writes, including the
row's own positive round trip.

What caught it was a disconfirming instruction written into the brief: confirm
what stamps the value, and if it differs from the named constant, report rather
than proceed. That clause existed because the same lead had already been wrong
about a canonical version number earlier in the campaign. A brief that names only
the intended change cannot catch its own mistakes; one that names the observation
that would falsify it can.

The chosen constant is a sound target rather than merely the correct one: its
module declares the number once as a literal type and reads the constant back out
of that annotation, so the value compared against and the type the parameter
record validates under cannot drift apart. The positive round trip now asserts
the stamped value equals that constant, which is the assertion that reds if the
wrong constant is ever substituted again.
