---
tags:
  - '#audit'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:708c02aa8a6e1140639e316ba612861a5a46cbda6ca8ddf1e4606949e70d3afd'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-adr]]"
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# `cli-machine-secret-channel-unification` audit: `S13 subprocess success matrix review`

## Scope

Independent SOL review of the S13 fresh-process success matrix against the
accepted machine-secret ADR, both research records, the implementation plan,
the S07/S12/S19-S22 execution and review trail, and the live canonical readers,
root gate, Windows bootstrap, and subprocess test. The review covered real
process and encrypted-storage boundaries, all five leaf payloads and both
restore doors, POSIX descriptor inheritance and closure, fd 0, root
authentication reads and writes, valid cross-scope certificate combinations,
prompt and leak oracles, the non-persistence Notice, and honest Windows HANDLE
semantics without numeric CRT-fd parity claims.

## Findings

### windows-leaf-descriptor-route | high | The Windows bootstrap cannot carry any leaf machine-secret descriptor

`test_machine_secret_channels_subprocess.py:104` skips every case that supplies
an inherited leaf payload on Windows, and `:334` skips all three valid
certificate dual-source combinations. The two Windows replacements exercise
only a root profile HANDLE: `_windows_profile_secret_bootstrap.py:33` always
converts the one HANDLE into `--profile-secrets-fd`, while the certificate write
still supplies its leaf secret through stdin. Consequently the reported nine
passes plus eight skips prove neither `--secrets-fd` on login, create,
passphrase change, either restore door, or certificate secret set, nor a Windows
profile-stdin plus leaf-HANDLE combination. This is not an honest absence of
POSIX numeric-fd parity; it is the absence of the ADR's supported Windows
HANDLE-to-descriptor route for the entire five-leaf contract. A Windows caller
must currently invent an unshipped shim to call `msvcrt.open_osfhandle` before
it can use any advertised leaf descriptor option.

#### Closure

Closed. The bootstrap now hard-cuts its old single `--handle` grammar to
optional `--profile-handle` and `--secrets-handle` inputs, maps either or both
allowlisted HANDLEs to separate CRT descriptors, injects the matching canonical
root and leaf options, closes the first conversion if the second conversion
fails, and finally closes any descriptor left unread by parse or dispatch
failure. The common subprocess matrix no longer skips inherited payloads on
Windows: it routes every leaf-fd case and all three certificate combinations
through a `STARTUPINFOEX` HANDLE allowlist and the production conversion
function. The focused Windows run reports 17 passed with no skips, including
leaf-only, mixed stdin/HANDLE, and dual-HANDLE success. No numeric CRT-fd
inheritance parity is claimed.

### incomplete-descriptor-closure-proof | medium | Certificate, root, fd 0, and Windows closure claims have no process oracle

The child-side `os.fstat` closure oracle is enabled for the POSIX login,
creation, rotation, and restore descriptor cases, but the certificate matrix at
`test_machine_secret_channels_subprocess.py:363` calls `_run` without any
`assert_closed_index`. Its two-descriptor case could not check both sources with
the current single-index harness in any event. The fd-0 case at `:310` checks
success but never verifies that stdin was closed, and neither Windows HANDLE
case observes that the child-owned CRT descriptor/HANDLE was closed after the
canonical read. The shared reader makes closure plausible, but the S13
execution record's blanket one-shot-closure claim is broader than this runtime
evidence.

#### Closure

Closed. The POSIX harness now accepts every descriptor index selected by an
invocation, the certificate matrix checks one or two inherited descriptors as
applicable, and fd 0 has its own post-dispatch closure assertion. The Windows
production-bootstrap harness discovers every mapped root and leaf CRT
descriptor from the generated argv and applies the same child-side `os.fstat`
oracle; every success requires one closure marker per mapped descriptor. The
bootstrap itself also finally-closes a mapped descriptor if normal canonical
consumption did not reach it.

### recovery-secret-leak-oracle | medium | The recovery-door secret is absent from the leak census

`_ALL_SECRETS` contains the planted profile, replacement, and certificate
passphrases only. The recovery-door parameter constructs a fresh mnemonic at
`test_machine_secret_channels_subprocess.py:298`, passes it as
`recovery_secret`, and then delegates to `_assert_success`, which cannot detect
that mnemonic in stdout, stderr, or the diagnostic log. A regression that
emits or logs the recovery authority would therefore leave the recovery stdin
and descriptor success cases green despite violating the ADR's no-secret-output
constraint.

#### Closure

Closed. `_assert_success` now accepts invocation-specific secret values, and
both restore doors pass the generated recovery mnemonic into that census. The
mnemonic is therefore checked alongside the planted profile, replacement, and
certificate passphrases in stdout, stderr, and diagnostic logs for stdin and
descriptor cases.

### prompt-absence-oracle | medium | The asserted prompt text is not any live localized passphrase prompt

`_assert_success` looks only for the literal phrase `enter passphrase`, while
the live English prompts are `Profile passphrase:`, `Current profile
passphrase:`, `New profile passphrase:`, confirmation text, and `PKCS#12
passphrase (input hidden):`. Thus the matrix can print a real prompt and still
satisfy its explicit prompt-absence assertion. Captured non-terminal success is
useful indirect evidence, but it does not justify the execution record's direct
claim that prompt text was checked.

#### Closure

Closed. The matrix now carries the exact live English prompt texts for login,
current/new/confirmation passphrases, certificate protection, and recovery,
normalizes captured output, and refuses any match. Successful captured
non-terminal operation is now paired with a direct oracle over the prompts the
five leaves can actually emit.

### write-notice-proof | medium | Non-persistence is asserted only for the stdin read path

The root-history stdin test requires exactly one
`config.login.session_not_persisted` Notice, but the POSIX certificate writes
and both Windows HANDLE success paths use only `_assert_success`, which accepts
an empty or duplicated Notice list. The S13 outcome therefore overstates the
proof that successful keychain-free root authentication carries the Notice on
representative writes and through the Windows bootstrap.

#### Closure

Closed. Every valid certificate root/leaf source combination now requires
exactly one `config.login.session_not_persisted` Notice, and both direct Windows
HANDLE read/write cases assert the same exact singleton list. Together with the
existing stdin history assertion, the matrix now proves the Notice across the
representative root read and write paths and both platform transports. No
critical, high, or medium finding remains open.

## Recommendations

- Generalize the supported Windows bootstrap to map an allowlisted leaf HANDLE
  as well as a root HANDLE, and two independently allowlisted HANDLEs for the
  certificate dual-fd case. Inject the selected root/leaf options only after
  conversion, retain the existing parsed cross-scope preflight, and add real
  Windows leaf and mixed-scope subprocess successes. Do not infer or advertise
  direct numeric CRT-fd inheritance.
- Extend the closure harness to accept every selected descriptor, including fd
  0 and both certificate descriptors, and add a child-side Windows ownership
  oracle that distinguishes canonical close from mere process teardown.
- Pass invocation-specific secret values into the leak assertion so the
  generated recovery mnemonic is checked alongside the static planted values;
  apply the same oracle to setup subprocesses whose root authentication is part
  of the claimed sequence.
- Assert the actual localized prompt catalogue values are absent, or instrument
  the hardened prompt seam in the child without replacing the real command
  boundary.
- Require exactly one non-persistence Notice on every root-authenticated read
  and write success, including both Windows HANDLE cases.
