---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:4275eb0d7814e8661175ff52530c0fdc9c8b35a80e41203f4c2e37b3b38246e6'
step_id: 'S97'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh remove the private duplicate of the canonical bucket-identity primitive that the authority package carries beside the one being relocated into custody, since two implementations of one identity rule can disagree about which strings name the same bucket, and fold its consumers onto the surviving canonical home

## Scope

- `src/cadrumo/application/auth/_apoderado.py`

## Description

- Read `_apoderado.py` whole and located the private duplicate: `_canonical_bucket_id`, wrapping `TypeAdapter(BucketId)`.
- Searched by name and by meaning for the primitive it duplicates; found exactly one dedicated bucket-identity canonicalisation function outside the auth package, in the storage layer's master-key submodule.
- Read the storage function's own facade chain (`master_key/__init__.py`, `storage/__init__.py`) to confirm export status, and cross-checked a same-day sibling execution record that had already measured its consumer count tree-wide.
- Compared the two implementations' constraint shape and probed both on identical inputs (blank, whitespace-wrapped, over-length, boundary-length, mixed-case) from an out-of-repo script to check for disagreement.
- Concluded the fold as specified cannot be landed today and reported instead of forcing it.

## Outcome

**The row's premise does not hold at HEAD, and the correction is the deliverable — no code changed.**

The private duplicate is real: `_apoderado.py:93` defines `_canonical_bucket_id`, a thin wrapper around `TypeAdapter(BucketId)`. But the row's "surviving canonical home ... being relocated into custody" does not exist as a stable, resolvable target. The only dedicated bucket-identity canonicalisation function anywhere outside the auth package is `canonical_bucket_id` in the storage layer's `adapters/persistence/storage/master_key/_bucket_identity.py`. Its own docstring frames it as the master-key cryptographic boundary's authority, and it plainly reads as what "the one being relocated into custody" refers to — its module lives beside the package a same-day sibling record (`W04.P07.S164`) investigated for collapse into the storage layer's `custody/` package, a collapse that record found is deliberately NOT happening yet (blocked behind still-open rows `W05.P08.S24`/`S25`).

Three independent problems block folding onto it today, not one:

1. **It is dead code, not a survivor.** A same-day sibling record (`W04.P07.S109`) built an orphan detector spanning the shipped package, the harness distribution and the dev tree, counting static imports, `importlib` targets and string-constant references, and named this exact file — `adapters/persistence/storage/master_key/_bucket_identity.py` — as one of only two modules in the entire tree with zero references of any kind, reported "for routing" and left unresolved. Re-confirmed independently here: grepping the whole `storage` package for `canonical_bucket_id` and for `_bucket_identity import` returns only the defining module's own `def` and `__all__` lines. Nothing imports it, inside or outside its own package.
2. **It is not exported.** `canonical_bucket_id` is absent from `master_key/__init__.py`'s `__all__` and therefore from `storage/__init__.py`'s facade. Per the architecture rule, a cross-package import must resolve to the owning package's public `__all__`; importing the private `master_key._bucket_identity` submodule directly from `application/auth` would itself be a boundary violation, and promoting it is not mine to do — `adapters/persistence/storage/**` is another lane's ownership, held explicitly read-only for this row.
3. **Promoting it now would be premature, not a fix.** The orphan is flagged "for routing" precisely because its disposition (delete vs. promote-and-consolidate) is an open decision for the storage lane. At least three OTHER packages outside my ownership carry the identical private-duplicate pattern (`application/modelo/_review_package_signing.py`, `application/modelo/_review_package_recipient_encryption.py`, `domain/usage_ratios/_service.py`), all independently wrapping `TypeAdapter(BucketId)` the same way `_apoderado.py` does. Folding only the auth copy onto a still-undecided, still-orphaned target attaches one new consumer to code another lane may delete, and leaves the wider duplication (four-plus sites) unconsolidated — creating work rather than removing it, which is exactly the trap this row's dispatch message warned against.

**Substitutability, checked anyway.** Both implementations wrap the identical `TypeAdapter(BucketId)` — `BucketId` (`core/identity/_bucket.py`) is the one constraint authority (`strip_whitespace=True, min_length=1, max_length=128`) both already defer to, so their constraint shapes are not merely a superset relationship but byte-identical. Probed both functions, out-of-repo, on: a plain id, a whitespace-wrapped id, a mixed-case id, an empty string, a whitespace-only string, a 128-char string (boundary, valid), a 129- and 200-char string (over boundary, invalid), and a whitespace-wrapped 127-char string (valid after stripping). **No disagreement on any input**: every accepted value normalises identically and every rejected value is rejected identically. The sole difference is exception TYPE on rejection — `_apoderado.py`'s helper lets `pydantic.ValidationError` propagate, while the storage helper deliberately catches it and re-raises the plain builtin `ValueError` (its own docstring states this is intentional, so each caller can translate into its own typed error) — not a difference in which strings name the same bucket. So the row's stated risk ("two implementations . . . can disagree about which strings name the same bucket") does not materialise between these two specific implementations today; the risk is theoretical parity, not an observed identity-confusion defect.

**Conclusion.** `_apoderado.py`'s `_canonical_bucket_id` is left in place, unchanged. It already derives its behaviour from the sole constraint authority (`core.identity.BucketId`), so it is not diverging from anything live; it is one of several independent, behaviourally-identical wrappers around that authority, none of which currently has a promoted, exported, cross-package home to consolidate onto. Consolidation is a `core.identity`-level or storage-lane decision (add a shared canonicalisation function to `core.identity`'s facade, or resolve and then promote the orphaned storage one) that neither belongs to nor is reachable from `application/auth/**` ownership, and forcing it prematurely inside this row would either violate the private-submodule-import rule or attach a live consumer to code flagged the same day as awaiting a delete-or-promote ruling.

## Notes

- No files under `application/auth/**` or elsewhere were modified. No promotion was requested of the storage lane, because the orphan's disposition (delete vs. promote) is undecided and premature promotion for a single consumer would pre-empt that lane's own ruling while leaving the other three duplicate sites (`_review_package_signing.py`, `_review_package_recipient_encryption.py`, `usage_ratios/_service.py`) unaddressed.
- Recommend to the team lead: route the `master_key/_bucket_identity.py` orphan disposition to whoever next works `adapters/persistence/storage/**` (already logged for "routing" by `W04.P07.S109`); once that lane either promotes a consolidated `canonical_bucket_id` to a public facade or lands it in `core.identity`, re-open a row to fold `_apoderado.py` (and the other three duplicate sites) onto it in one atomic sweep.
- No test run was needed since no production code changed; the substitutability probe was exploratory verification only, run via `uv run --no-sync python -c "..."` against the live installed package, not persisted as a test.
- Plan row left unchecked per instruction; this record documents why it cannot be closed as specified without either an ownership or a legacy-adjacent violation, and names the concrete unblocking condition.
