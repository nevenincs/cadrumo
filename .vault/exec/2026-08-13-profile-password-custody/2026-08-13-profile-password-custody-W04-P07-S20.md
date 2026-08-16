---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:bb1d43642165f6e5f63fbcfdad23ff560faf712fd68e1c1b964b2b3937cb2e9f'
step_id: 'S20'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh delete retired provider, global recovery, raw-Argon, bootstrap, payload, locale, and legacy test surfaces after the replacement sweep

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/`
- `src/cadrumo/adapters/persistence/storage/{__init__.py`
- `_rotation.py`
- `_kdf_bounds.py`
- `errors.py}`
- `src/cadrumo/application/{bucket_maintenance/`
- `user_profile/}`
- `src/cadrumo/entrypoints/cli/{__init__.py`
- `_bootstrap_exempt.py`
- `_config/`
- `_config_payloads.py`
- `tests/}`
- `src/cadrumo/{core/_storage_taxonomy_locations.py`
- `tests/master_key.py}`

## Description

- Re-measure export reachability across the WHOLE `src/` tree, after finding the earlier scan had covered `src/cadrumo` only and so never saw the sibling harness distribution.
- Reclassify every candidate by transitive reachability from genuinely production-consumed entry points, with docstrings excluded, rather than by whether any module imports the name.
- Delete the shared-master recovery-wrapping family: the wrapping primitives module, the on-disk envelope record module, and their two test modules.
- Remove the six deleted names from the master-key package facade and from the storage package facade, in the same change: eager imports, lazy-export map, and `__all__`.
- Correct the package docstrings that advertised the deleted recovery exports, and the one production docstring naming a deleted primitive as its caller.
- Regenerate the CLI-owned API stubs so the two orphaned stubs are removed rather than left to crash the nitpicky docs build.

## Outcome

Two measurement errors were corrected before anything was deleted, and both changed what the row should do.

The first was a scan blind spot. Reachability had been measured over `src/cadrumo` only, which silently excluded the sibling harness distribution. Widening it to all of `src/` recovered three exports that had been counted as having zero consumers. One of those, the reaper that closes every live key-holding session, is called by the harness stdio server's watchdog, and it is the only mechanism able to zeroise sessions bound on threads the reaping context cannot see. Deleting it would have removed exactly the capability that module exists to provide.

The second was a category error in the metric. Counting IMPORTS of a name answers a different question from whether the symbol is load-bearing. A type that is only ever a return annotation of a live function is never imported by anyone and is entirely alive. Two login-throttle types are exactly that shape: throttling is enforced in production, and those types are what the enforcement functions return. Classifying by transitive reachability from production entry points, with docstring mentions excluded so a name merely discussed in prose does not count as used, is the measurement that answers the real question.

On that basis the candidates split five to twelve. Alive, and not to be deleted: the two throttle types; the secure atomic write that persists the throttle sidecar; the unsecured-provider tax-id refusal, which is NOT an unwired guard, because it is called by the live bucket-level refusal one frame above it; and the unsecured provider class that refusal instantiates. Surplus: the whole shared-master recovery-wrapping family, the two file-backed and keyring provider classes, the passphrase-callback alias, and the three raw Argon2 cost constants, whose only consumer is a convenience derivation wrapper that itself has no caller anywhere, the live derivation caller supplying its own parameters explicitly.

Landed in this pass: the recovery-wrapping family. It is self-contained, has no consumer in any other layer, and needs no edit to the application-layer absence gate. The provider family is left standing and is described below.

## Notes

The row is NOT complete and its plan state was deliberately left unchecked. The provider family, the passphrase-callback alias and the Argon2 cost constants remain. That deletion is a substantially larger landing centred on a twelve-hundred-line module whose live half must survive, it takes roughly seven test modules with it, and it requires an edit to the application-layer hard-cutover absence gate, which belongs to another lane and must land in the same change.

A secrets-in-memory window is recorded here because the intuitive answer to it is wrong. A bucket session closed explicitly has its key buffers zeroised in place. A session DROPPED without close is garbage collected normally, since the live-session registry holds only weak references, but its buffer is never scrubbed: the plaintext data key persists in freed heap until some later allocation overwrites it. Garbage collection frees, it does not zeroise. The trigger is precise and narrow, a caller that opens a session and drops it without closing, and the operator profile-switch path is not one of them, because the login handover closes the outgoing session explicitly. The related limit is that the interpreter-exit hook closes only the session bound in the exiting context and, by context-variable semantics, cannot see one bound on another thread. Neither is a live exposure and neither is reachable through the public surface; both are stated so a later reader does not assume collection implies erasure.

No test doubles, skips or expected-failure markers were used. The deleted modules' own test modules were deleted with them rather than left asserting a removed surface.
