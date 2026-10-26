---
tags:
  - '#research'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:cd4e2218a71acecb4a7511486e62c5f12a923bb31f8e001fa06cb1d1db171f12'
related:
  - "[[2026-08-22-profile-registration-password-policy-tui-custody-validation-mismatch-reference]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `profile-registration-password-policy` research: `holistic credential capability`

Profile creation exposed a fork between the application-visible password capability
and the encrypted-custody format contract. The same fork reaches password rotation,
while raw adapter diagnostics also cross login, restore, and recovery-authorization
surfaces. Evidence favors one capability-specific profile-password contract in core,
typed application mappings for establish/change versus authenticate operations, and a
separate recovery-secret codec. A global error-resolver reorder is too broad, and the
accepted recovery-reset mismatch requires a separately bounded decision rather than an
incidental patch.

## Findings

### Accepted custody intent already defines the authoritative password shape

The accepted custody ADR requires 15 through 256 Unicode scalar values, at most
1,024 strict UTF-8 bytes, no normalization or rewriting, and full preservation by
every transport. The persistence validator implements those limits  and
the former source file. The new failure
trace records how the upstream capability diverged.

NIST SP 800-63B-4 requires at least 15 characters for a single-factor password,
permits eight only when the password participates in multi-factor authentication,
counts Unicode code points, recommends accepting at least 64 characters, forbids
composition rules, and requires a prospective-password blocklist. It recommends NFC
normalization, whereas the accepted product ADR deliberately preserves the exact
sequence. The normalization difference and blocklist requirement are decision inputs;
they must not be smuggled into a crash repair.

### The application contract is stale, incomplete, and misnamed as generic NIST policy

the former source file declares a generic eight-character minimum.
Registration re-exports it as its capability contract and defines acceptability only
as not below that floor
and the former source file. It neither models the
256-scalar ceiling, 1,024-byte ceiling, nor invalid scalar/transport cases. Registration
then reaches custody material creation , after the incomplete gate.

Password rotation imports and repeats the same incomplete assessment  and
the former source file, then uses the same
custody mint .
The defect is therefore an establish/change capability defect, not a TUI-only defect.

### Establishing a secret and authenticating an existing secret require different mappings

Registration and rotation choose a prospective password. They need actionable typed
reasons before KDF, staging, locking, or transaction work. Login, password restore, and
recovery-artifact authorization verify an already-enrolled exact sequence; applying
prospective-password quality guidance there would create an authentication oracle.
Those surfaces should collapse malformed and incorrect submissions into one localized
authentication-refusal family. The current broad predicate  classifies every custody
password error as authentication failure, so structurally invalid input also consumes
login throttle .

### Structured custody-password errors solve localization without destabilizing the registry

`resolve_error_message` prioritizes a typed translation key, then a raw positional
message, then the registered code message .
Every `ProfileCustodyPasswordError` constructor supplies raw English, while its localized
registry row exists at `src/cadrumo/core/errors/registry/_adapters_part2.py:651`.
Registration catches only `ProfileRegistrationError` , so the TUI worker reaches
the unexpected-error renderer at

Reordering the resolver globally would replace precise raw diagnostics across hundreds
of integrity and refusal construction sites with broad registry prose. The narrower
alternative is a typed password-validation reason plus safe numeric context, mapped to
localized application errors for prospective operations and non-oracular authentication
errors for proof operations. This keeps diagnostics out of operator output without
changing unrelated resolver semantics.

### Recovery secrets are incorrectly coupled to profile-password validation

Recovery uses a generated 24-word BIP-39 mnemonic, an independent credential domain,
but the KDF supervision path passes generic recovery `secret` values through
`validate_profile_password` and its byte decoder  and
`src/cadrumo/adapters/persistence/storage/custody/_kdf_worker.py:130`. Today's mnemonic
happens to fit the password limits. A separate exact recovery-secret codec prevents a
future encoding change from being constrained accidentally by profile-password policy.

### Recovery restore contains a separate accepted-intent mismatch

The accepted rollup describes recovery-based password reset, but the current recovery
restore republishes the existing password envelope and explicitly leaves lost-password
access lost . This is
a capability gap, but repairing it changes archive publication and password-envelope
lineage. It should receive its own decision and execution boundary; the current repair
may add a protective characterization or follow-up but must not redesign restore
incidentally.

### One core contract is stronger than importing custody upward or copying constants

Option A places a capability-specific profile-password contract in core: typed bounds,
pure exact validation, and reason-bearing assessment. Application and custody both
consume the core facade; application maps reasons to operation errors, while custody
retains defense-in-depth validation. This matches the permitted dependency direction.

Option B makes application the sole owner and exposes custody through a port. It leaves
the persistence adapter unable to enforce its own format without duplication or an
upward dependency. Option C makes custody the sole owner and imports it from application,
which reverses the architectural boundary. Option D changes eight to fifteen locally;
it leaves the upper/byte/scalar rules, localization, recovery coupling, and future drift
unresolved.

### Verification must prove cross-surface parity and unchanged storage

The decision needs tests at 14, 15, 256, and 257 scalars; at 1,024 and 1,025 UTF-8
bytes independently of scalar count; for surrogate refusal in direct Python input; and
for composed/decomposed exact preservation. Registration and rotation refusals must
perform no publication or mutation. TUI and scripted CLI must render localized typed
refusals without INTERNAL guidance or secret echo. Login and restore must remain
non-oracular. Recovery-mnemonic roundtrips must use the distinct codec.

### Investigation boundary

This research inspected current profile credential code, error registration, locale
behavior, accepted custody intent, and NIST SP 800-63B-4. It did not select a blocklist
source or update mechanism, reconsider exact-sequence normalization, redesign recovery
restore, run live AEAT operations, or alter production code.

## Sources

- `.vault/adr/2026-08-13-profile-password-custody-rollup-adr.md`
- `.vault/reference/2026-08-22-profile-registration-password-policy-tui-custody-validation-mismatch-reference.md`
- https://pages.nist.gov/800-63-4/sp800-63b/authenticators/

- `src/cadrumo/core/errors/registry/_adapters_part2.py:651`

- `src/cadrumo/adapters/persistence/storage/custody/_kdf_worker.py:130`
