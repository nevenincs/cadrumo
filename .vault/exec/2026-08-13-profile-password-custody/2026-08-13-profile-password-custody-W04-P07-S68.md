---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:01d114a4f576bc381b750bd8413405e6dafa884d87c316d7731f9843db633eef'
step_id: 'S68'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh widen the substrate signatures that force ten delegate sites to narrow a handle and then hand the same object back to a substrate demanding its concrete type, one of which returns a type guard, since the interim fail-closed identity check correctly refuses a structurally conforming stand-in the substrate never minted but is a guard standing in for a boundary that should not need one

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/ and src/cadrumo/adapters/persistence/storage/custody/ and src/cadrumo/adapters/persistence/storage/bucket/ and src/cadrumo/application/profile_custody/`

## Description

- Enumerate the fourteen delegate sites that re-widen a narrowed handle through `_substrate_handle` in `src/cadrumo/application/profile_custody/__init__.py`, and group them by target type: bucket paths, password envelope, DEK sentinel, recovery envelope, bucket session, persisted session receipt, secure-object repository.
- Decide each group by comparing, per substrate function, the fields that function actually consumes against the fields the application port actually exposes.
- Add `BucketLockTarget`, a runtime-checkable protocol declaring the two fields the bucket lock reads: `bucket_dir`, the directory the lock sidecar is placed in, and `bucket_id`, which every lock refusal names.
- Widen `lock_path`, `_ensure_bucket_dir_lockable`, `acquire_lock`, `release_lock` and the three internal lock helpers onto that protocol in `src/cadrumo/adapters/persistence/storage/bucket/_lockfile.py`.
- Export `BucketLockTarget` from the bucket package facade so a consumer can satisfy the contract without importing a private module.
- Cover the widening with a test that drives the real lock through a stand-in proven not to be a `BucketPaths`, and an anti-vacuity test proving a view omitting `bucket_id` is refused by the protocol.
- Type-check the existing bucket-lock consumers in the auth and bucket-maintenance packages to confirm the concrete record still satisfies the widened signature unchanged.

## Outcome

The row's premise holds for two of the fourteen sites. The other twelve are not ceremony, and the per-function comparison is what separates them.

Widened and landed: the two bucket-lock sites. The lock reads `bucket_dir` to place its sidecar and `bucket_id` to name its refusals, and nothing else. A protocol stating exactly those is the truthful contract, the concrete paths record satisfies it structurally, and the runtime identity check those two call sites needed disappears once the signature says what the function means.

Not widenable, first kind, nine sites: the custody record ports are deliberately opaque. The sentinel port exposes only `profile_id`; the envelope port exposes four identity fields. Their own contract states the reason, that the KDF parameters, the wrapped key and the AAD descriptor stay opaque because the application has no business reading key material. The substrate needs precisely that hidden material to wrap, unwrap and verify. Widening those signatures onto the ports would require publishing key material on an application-facing contract, which is the exact exposure the ports exist to prevent and which the sensitive-financial-data rule forbids outright. The asymmetry is the design working, not a defect to remove.

Not widenable, second kind, three sites: the bucket-session port is narrower than the active-session slot requires. It declares no keyed-subkey derivation, no engine acquisition, no routed-settings derivation and no engine disposal, yet an object bound as the active session is later asked for all four by the column-encryption path, the runtime repository factory and the close path. Widening the binding function would convert a composition error caught at the boundary into a failure at a distance, on a field the port never promised.

The type guard the row singles out is load-bearing rather than an oddity. The identity predicate reads only `bucket_id`, so its parameter could widen in isolation; but it returns a type guard narrowing to the concrete session, and widening the parameter while keeping that return would let a port-shaped object be narrowed to the concrete session and then bound as active, reintroducing the failure the second kind above describes. The boolean-returning wrapper that port-shaped callers need already exists in the application package, so the arrangement is already correct and was left untouched.

Remaining work is one line in the application layer, and it belongs to the lane that owns those ports: declare `bucket_id` on the bucket-storage-paths port. That port exposes the bucket directory, the database directory, the blobs directory and the database file, but not the identity, so it does not yet satisfy the new protocol. Once declared, the two bucket-paths re-widening calls delete outright.

## Notes

The row as written implies ten removals. Eleven of the remaining twelve sites must NOT be removed, and this correction is recorded here rather than left in conversation so a later reader does not sweep them as ceremony. Removing the nine opaque-record narrowings would mean widening cryptographic signatures onto ports that deliberately hide key material; removing the three session narrowings would mean binding an object into the process-wide active-key slot without the capabilities that slot later exercises. Each of those eleven would be a weakening presented as a cleanup. The twelfth, the identity predicate's type guard, is safe only in company with the boolean wrapper that already exists.

The interim runtime identity check the row describes as standing in for a boundary that should not need one is therefore accurate for two sites and inaccurate for the rest. Where the application port is genuinely narrower than the substrate requires, a boundary is exactly what is needed, and the check is the thing converting a silent composition error into a refusal.

No test doubles, skips or expected-failure markers were used. The widening is proven by driving the real lock with a non-conforming concrete type and by an anti-vacuity case; the protocol admits the narrowed shape and refuses one missing the identity field.

Scope was held to the three storage packages. The application package was not edited, and the single change it needs is named above for its owning lane.
