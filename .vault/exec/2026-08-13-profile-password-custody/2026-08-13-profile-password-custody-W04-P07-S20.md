---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:580aa924916a34142b0cfccc7cd0d59ddbf713fc3640d4b697531049d247cfb0'
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

The provider family followed in a second pass. The two shared-master providers,
the backend resolver and its activation wrapper, the budgeted keychain reader,
two provider error helpers and nine provider constants were removed; the
passphrase-callback alias and its resolver went with them, as did the three raw
Argon2 cost constants and the no-parameter derivation wrapper whose only
consumer they were. The module carrying them fell from twelve hundred and
forty-seven lines to four hundred and fifty-six.

Reading the code corrected the plan twice before it did damage. The provider
entry helper and the provider-session teardown are NOT deletable: both serve
the one implementation that survives, the published-key unsecured provider,
which itself stays exported because the live tax-id refusal instantiates it.
The teardown helper is therefore defined-and-unexported deliberately rather
than by accident, which is the sanctioned shape for a helper used only inside
its own package.

Coverage was salvaged rather than swept. Six test modules whose entire subject
was a deleted provider went with it. A seventh was kept: only one of its five
cases exercised a provider, so that case was removed and four session cases
retained. The terminal registration test was converted rather than deleted,
because its intent -- the password typed at the screen is the one that opens
the profile -- outlived the mechanism it used to assert with; it now proves the
same property against the committed capsule through the custody unlock.

The consumer sweep was completed across every lane. In the packages this record
owns, no reference to a deleted provider remains. Three classes of surviving
mention were each confirmed legitimate rather than missed: prose in docstrings,
the retired-name list and synthetic detector sources of the layering gate, and
assertion DATA in a gate that asserts production files do not contain those
tokens -- an assertion now strictly stronger than before, because the names no
longer exist anywhere to be found.

## Notes

The landing was sequenced wrongly and the tree suffered for it. The canonical
removals were made before the consumer sweep was complete, and the measurement
that authorised them counted PRODUCTION consumers only. Tests are consumers: an
atomic deletion is atomic across every consumer, not every production consumer.
The consequence was real breakage in two packages this record does not own, and
one earlier instance that blocked collection for a whole layer because a shared
test-support module imported a removed name at module scope.

Two properties of the failure are worth carrying forward, because both are
counter-intuitive.

The first is that a clean collection proves very little here. Almost every
remaining consumer imported the removed names INSIDE a test body rather than at
module scope, so those modules collected without error and failed only when the
test ran. A collection-only gate reported a healthy tree while several modules
were broken. The gate that would have caught it is a real run of the affected
modules, and the gate that would have PREVENTED it is a name sweep across every
lane before the first deletion.

A corollary caught only during the conversion itself: a consumer sweep must
classify the SHAPE of each reach, not just its location. Three shapes appeared,
and they do not take the same repair. A context-manager wrapper around a test
body is removed by deleting its line and dedenting what it wrapped. A bare call
is rewritten. But an entry composed into an exit-stack argument list has to be
DELETED outright, because dedenting it leaves a stack member that no longer
exists -- and a sweep that had catalogued only the first two shapes would have
converted the third wrongly while reporting the file done.

A third shape of survivor is the most dangerous, because it looks like the
second and is not. An error class with no raise site anywhere may still have a
live RECOGNISER: an isinstance arm that classifies it when it arrives. Deleting
the class collapses the recognition arm with it, and if any raiser still
existed the failure would be silent and fail OPEN -- a real authentication
failure would simply stop being recognised as one, with no error and no
refusal. Presence in a recognition tuple is therefore not evidence a class is
live, and absence of a raiser is not by itself licence to delete: only checking
the RAISE sites separates a genuinely dead class from a live recogniser's
subject. That check was run for all four classes retired here, in production
and in tests alike, and returned nothing in both.

The second is that a name still present after a deletion is not automatically an
oversight. Three legitimate reasons for one were found: prose; a tracked fixture
that exists only to be read by a scope proof, whose whole job is to carry a
retired name where it cannot execute, and converting which would make the proof
pass vacuously; and assertion data in a gate asserting the token's ABSENCE. Each
must be classified rather than swept, and the sweep is not finished when the
count reaches zero -- it is finished when every survivor is explained.

Residual scope this row names but has NOT delivered, found while verifying the
above and deliberately not started, because it repeats the same cross-lane shape
that caused the failure. Four storage-taxonomy members addressing the deleted
key store, and the location entries beside them, now have no consumer at all.
Four error classes exported and registered against the error catalogue have no
production raise site left. Retiring either group reaches a forwarding port in
the application layer, so neither is lane-contained and neither may be landed
without its owner in the same change.

No test doubles, skips or expected-failure markers were used at any point.
