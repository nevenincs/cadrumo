---
tags:
  - '#audit'
  - '#codebase-health'
date: '2026-05-21'
modified: '2026-05-21'
related: []
---



# `codebase-health` audit: ty type-debt inventory

## Scope

`uv run --no-sync ty check src/aeat/` run on 2026-05-21, branch `chore/eliminate-shims`.
Read-only inventory pass; no production code modified.
Cross-referenced against `git diff --name-only HEAD` to classify each diagnostic as
**CLEAN** (safely fixable now) or **CONTENDED** (file carries uncommitted foreign-campaign WIP;
must wait for that campaign to land before touching).

---

## Diagnostic inventory

### By error code

| Code | Count | Trivial / Substantive | Notes |
|---|---|---|---|
| `invalid-argument-type` | 177 | Substantive | Largest cluster; two distinct sub-patterns — type-narrowing gaps (Literal vs str, tuple union narrowing) and Mapping/dict covariance mismatches |
| `unresolved-attribute` | 138 | Substantive | Driven overwhelmingly by `object`-typed variables (type erasure); 123 of 138 touch `object`-typed expressions |
| `not-subscriptable` | 19 | Substantive | Cascade from `object` / `int | float` union — same erasure root as `unresolved-attribute` |
| `unsupported-operator` | 15 | Substantive | `in` / comparison on `str | None` where return type is too wide |
| `invalid-context-manager` | 12 | Trivial | All 12 are `MasterKeyProvider` used as context manager; `__enter__`/`__exit__` missing from the class |
| `invalid-return-type` | 8 | Substantive | Mix of `Mapping` vs `dict` covariance, missing generator `yield` annotation, `SiteHealthStatusLike` not narrowed to `SiteHealthStatus` |
| `invalid-type-form` | 8 | Trivial | 7× `type(None)` in generic parameter (must be `None`); 1× `self.payload_type` in runtime subscript |
| `invalid-assignment` | 6 | Substantive (5) / Trivial (1) | `str | None` mismatch (1 trivial), Literal vs str in assignments (5 substantive) |
| `invalid-method-override` | 3 | Substantive | All three are `invalid-method-override` on `_observations_repository.py` (dirty file) |
| `call-non-callable` | 2 | Substantive | `object`-typed callables in Playwright test helper (erasure cascade) |
| `missing-argument` | 2 | Trivial | Constructor calls missing a required parameter |
| `not-iterable` | 2 | Substantive | `object`-typed iterables in CLI |
| `unresolved-reference` | 1 | Trivial | Single missing name |
| **TOTAL** | **393** | **23 trivial / 370 substantive** | |

### By subpackage

| Subpackage | Clean | Contended | Total |
|---|---|---|---|
| `application` | 123 | 26 | 149 |
| `domain` | 74 | 29 | 103 |
| `adapters` | 43 | 23 | 66 |
| `entrypoints` | 41 | 7 | 48 |
| `core` | 20 | 0 | 20 |
| `locales` | 6 | 0 | 6 |
| `diagnostics` | 1 | 0 | 1 |
| **TOTAL** | **308** | **85** | **393** |

### Trivial vs Substantive

| Category | Count | Clean | Contended |
|---|---|---|---|
| Trivial | 23 | 21 | 2 |
| Substantive | 370 | 287 | 83 |
| **TOTAL** | **393** | **308** | **85** |

Trivial codes: `invalid-context-manager` (12), `invalid-type-form` (8), `missing-argument` (2), `unresolved-reference` (1).
All other codes are Substantive.

### Clean vs Contended (top error files)

**Clean files — highest diagnostic count (safely fixable now)**

| File | Count | Dominant codes |
|---|---|---|
| `application/ledger/test_actions.py` | 37 | `unresolved-attribute:37` |
| `domain/calculations/registry/test_cross_boundary_roundtrip.py` | 34 | `invalid-argument-type:34` |
| `application/modelo/test_amend_flow.py` | 21 | `unresolved-attribute:21` |
| `application/live/test_census_snapshot.py` | 17 | `invalid-argument-type:16, unresolved-attribute:1` |
| `domain/calculations/registry/test_constraints_text_shape.py` | 14 | `invalid-argument-type:7, unsupported-operator:7` |
| `application/modelo/test_import_flow.py` | 13 | `unresolved-attribute:13` |
| `entrypoints/cli/test_registry_cli.py` | 13 | `not-subscriptable:5, unsupported-operator:4, invalid-argument-type:2` |
| `adapters/outbound/aeat/sede/test_renta_web_open_explore_dom.py` | 12 | `unresolved-attribute:10, call-non-callable:2` |
| `application/overview/test_backlog.py` | 8 | `invalid-argument-type:8` |
| `entrypoints/cli/_modelo.py` | 8 | `unresolved-attribute:8` |
| `adapters/persistence/storage/master_key/_master_key.py` | 7 | `unresolved-attribute:7` |
| `core/resources/_repos/manuals.py` | 6 | `invalid-argument-type:5, missing-argument:1` |
| `entrypoints/cli/test_profile_output_language.py` | 6 | `invalid-context-manager:6` |
| `locales/_ast_scanner.py` | 6 | `invalid-argument-type:6` |
| `entrypoints/cli/test_fast_path_no_state.py` | 5 | `unresolved-attribute:5` |
| `adapters/inbound/sanitizer/_streams.py` | 4 | `invalid-argument-type:2, not-subscriptable:2` |
| `application/filing/test_history_repository_roundtrip.py` | 4 | `invalid-argument-type:4` |
| `adapters/outbound/aeat/auth/test_session_store_roundtrip.py` | 3 | `not-subscriptable:3` |
| `adapters/outbound/aeat/browser/session.py` | 3 | `invalid-argument-type:3` |
| `adapters/persistence/storage/envelope/test_secure_bound_repository.py` | 3 | `unresolved-attribute:3` |

**Contended files (must wait — carry foreign-campaign WIP)**

| File | Count | Dominant codes |
|---|---|---|
| `domain/calculations/registry/_loader.py` | 23 | `invalid-argument-type:19, invalid-assignment:4` |
| `adapters/outbound/aeat/auth/test_clave_movil.py` | 11 | `invalid-argument-type:11` |
| `adapters/outbound/aeat/sede/_iva_compensation_wallet.py` | 7 | `unresolved-attribute:6, invalid-argument-type:1` |
| `application/auth/_diagnostics.py` | 7 | `invalid-argument-type:7` |
| `application/modelo/_actions.py` | 5 | `unresolved-attribute:5` |
| `entrypoints/cli/test_apex_workflow_verification.py` | 5 | `not-subscriptable:4, invalid-argument-type:1` |
| `domain/calculations/registry/_validate.py` | 4 | `invalid-argument-type:4` |
| `adapters/outbound/aeat/auth/_clave_movil.py` | 3 | `invalid-argument-type:3` |
| `application/calculations/_observations_repository.py` | 3 | `invalid-method-override:3` |
| `application/diagnostics.py` | 3 | `unresolved-attribute:2, invalid-return-type:1` |

---

## Root cause analysis

Three structural root causes account for the majority of diagnostics.

**Root cause 1 — Type erasure via `object`-typed variables (≈ 137 diagnostics)**

`unresolved-attribute` (123 of 138) and cascade `not-subscriptable` / `call-non-callable`
are caused by variables inferred as `object` at call sites. This happens in two distinct
contexts:

- *Application action outcomes*: `application/ledger/test_actions.py` (37),
  `application/modelo/test_amend_flow.py` (21), `application/modelo/test_import_flow.py`
  (13), `entrypoints/cli/test_fast_path_no_state.py` (5) — all test files accessing
  `.result`, `.persisted`, `.ref`, `.payload`, etc. on outcome dataclasses whose fields
  are typed `object` or whose return types are not narrowed in the action layer.
- *Playwright / browser session*: `adapters/outbound/aeat/sede/test_renta_web_open_explore_dom.py`
  (12), `entrypoints/cli/_modelo.py` (8), `adapters/persistence/storage/master_key/_master_key.py`
  (7) — browser `page` and `locator` objects held as `object` instead of typed
  `playwright.async_api.Page` / `Locator`.

**Root cause 2 — Literal / union narrowing gaps in registry types (≈ 95 diagnostics)**

`invalid-argument-type` in `domain/calculations/registry/test_cross_boundary_roundtrip.py` (34),
`application/live/test_census_snapshot.py` (16), `domain/calculations/registry/test_constraints_text_shape.py`
(7 `invalid-argument-type` + 7 `unsupported-operator`), `application/overview/test_backlog.py` (8)
all share the same pattern: a function parameter demands a specific `Literal[...]` union
or a typed ID alias, but the caller passes a plain `str` or a wider union including
`tuple[()] | datetime`. The registry TOML loader (`_loader.py`, contended, 23 diagnostics)
has the same pattern internally — `str` where typed casilla/casilla-type literals are expected.

**Root cause 3 — `MasterKeyProvider` missing context manager protocol (12 diagnostics)**

Every `invalid-context-manager` diagnostic is the same: `get_master_key_provider()` returns
`MasterKeyProvider`, which is used in `with` blocks across six test and application files.
`MasterKeyProvider` lacks `__enter__` / `__exit__`. Adding the protocol (or wrapping it in
a `contextlib.contextmanager` helper) clears all 12 at once. All 10 clean-file occurrences
are fixable in a single targeted change to `MasterKeyProvider`.

**Root cause 4 — `type(None)` in generic parameter (7 diagnostics)**

Seven `core/resources/_repos/*.py` classes inherit from
`ResourceCacheRepository[object, type(None)]`. `ty` rejects `type(None)` as a type
expression; the fix is `ResourceCacheRepository[object, None]` in each of the six
repository files. This is purely mechanical.

**Root cause 5 — `Mapping` vs `dict` covariance (≈ 9 diagnostics)**

`_clave_movil.py` (contended, 3), `_auth_state.py` (clean), and related call sites pass
`Mapping[str, object]` where `dict[str, object]` is declared. Fix is either to widen the
parameter signature to `Mapping` or to narrow the stored value to `dict` at the persistence
boundary.

---

## Remediation plan

Waves are ordered by: trivial-first, then by diagnostic count per-wave, then clean-only.
Each wave is bounded to clean files; contended files are deferred to Wave 5.

### Wave 1 — Trivial mechanical fixes (21 diagnostics, 5 files, CLEAN)

Target codes: `invalid-type-form` (8), `invalid-context-manager` (10 in clean files),
`missing-argument` (2), `unresolved-reference` (1).

Actions:
- `core/resources/_repos/*.py` (6 files): replace `type(None)` with `None` in generic base.
- `MasterKeyProvider` class: add `__enter__` / `__exit__` (or `contextmanager` wrapper);
  clears all 10 clean-file `invalid-context-manager` occurrences.
- `core/resources/_repos/manuals.py`: supply the missing constructor argument.
- Single `unresolved-reference` (clean file): import the missing name.

Estimated diagnostics cleared: **21**.

### Wave 2 — `Mapping` vs `dict` covariance (clean files only, ≈ 4 diagnostics)

Target: `adapters/outbound/aeat/sede/_auth_state.py` (`invalid-return-type`),
`adapters/outbound/aeat/browser/session.py` (3 `invalid-argument-type`).

Actions: widen parameter / return-type signatures from `dict[str, object]` to
`Mapping[str, object]` at the boundary, or cast at the single coercion point.

Estimated diagnostics cleared: **~4**.

### Wave 3 — Registry Literal / union narrowing in clean test files (≈ 70 diagnostics)

Files: `domain/calculations/registry/test_cross_boundary_roundtrip.py` (34),
`application/live/test_census_snapshot.py` (16),
`domain/calculations/registry/test_constraints_text_shape.py` (14),
`application/overview/test_backlog.py` (8).

Root cause: tests pass raw `str` literals where typed ID aliases or `Literal[...]`
unions are expected, or `violates_text()` returns `str | None` where the test assumes
a container it can use `in` on.

Actions:
- Widen function signatures to accept `str` where the Literal constraint is overly strict
  (or cast test call sites with typed IDs).
- Change `violates_text()` return type from `str | None` to `frozenset[str] | None` or
  similar collection so `in` is valid.
- Fix `tuple[()] | datetime` union narrowing in roundtrip test fixture builders.

Estimated diagnostics cleared: **~70**.

### Wave 4 — Type erasure: action outcome dataclasses + browser objects (≈ 90 diagnostics)

Files: `application/ledger/test_actions.py` (37),
`application/modelo/test_amend_flow.py` (21),
`application/modelo/test_import_flow.py` (13),
`entrypoints/cli/_modelo.py` (8),
`adapters/persistence/storage/master_key/_master_key.py` (7),
`entrypoints/cli/test_fast_path_no_state.py` (5),
`adapters/persistence/storage/envelope/test_secure_bound_repository.py` (3),
and others carrying `unresolved-attribute` on `object`.

Root cause A (action outcomes): action layer returns or stores fields as `object`;
test files access typed attributes that are invisible to `ty`. Fix is to annotate
result dataclass fields with their concrete types rather than `object`.

Root cause B (browser/Playwright): `page` / `locator` variables typed as `object`;
fix is to import and annotate with `playwright.async_api.Page` / `Locator`.

Root cause C (`adapters/persistence/storage/sql/secure_objects.py`): SQLAlchemy
`Result[Any]` lacks `.rowcount`; requires a `CursorResult` cast or `isinstance` guard.

This wave is the highest-effort; treat it as two sub-waves (B is independent of A).

Estimated diagnostics cleared: **~90**.

### Wave 5 — Contended files (deferred, 85 diagnostics)

All 85 diagnostics in the dirty/contended file set. Do not touch until the owning campaigns
(`live-iva-compensation-wallet`, `auth` refactor, `registry/_loader` hardening,
`calculations/_observations_repository`) land and their files become clean.

Primary files awaiting clearance:
`domain/calculations/registry/_loader.py` (23), `adapters/outbound/aeat/auth/test_clave_movil.py` (11),
`application/auth/_diagnostics.py` (7), `adapters/outbound/aeat/sede/_iva_compensation_wallet.py` (7),
`application/modelo/_actions.py` (5), `application/calculations/_observations_repository.py` (3),
`domain/calculations/registry/_validate.py` (4).

Estimated diagnostics cleared once unblocked: **85**.

### Wave summary

| Wave | Scope | Diagnostics | Status |
|---|---|---|---|
| 1 | Trivial: `type(None)`, `MasterKeyProvider` CM, missing args | ~21 | Ready |
| 2 | `Mapping`/`dict` covariance, auth-state return type | ~4 | Ready |
| 3 | Registry Literal narrowing in clean test files | ~70 | Ready |
| 4 | Type erasure: action outcome fields + browser objects | ~90 | Ready (two sub-waves) |
| 5 | All contended files | ~85 | Blocked on foreign campaigns |
| **Total** | | **~270 clear now / 85 deferred** | |

Note: Wave 3 + 4 involve substantive type design decisions (return type widening vs.
narrowing at production boundaries); they should be reviewed against the architecture
boundary rules before merging.

---

## Recommendations

- **Start with Wave 1** immediately. All 21 diagnostics are mechanical, touch only
  clean files, and cluster into ≤ 3 distinct fixes (`type(None)` replacement,
  `MasterKeyProvider` protocol, one missing argument). Single small commit.

- **Wave 2** is a two-file fix (`_auth_state.py`, `browser/session.py`). Combine with Wave 1
  if the reviewer bandwidth allows.

- **Wave 3** requires agreeing on whether `violates_text()` should return a collection
  (preferred — enables `in` membership test semantics) or whether tests should assert
  differently. Resolve this design question before writing code.

- **Wave 4** (type erasure) is the highest-value substantive wave. Prioritise fixing
  production source annotations (action result dataclasses) first; the test files will
  automatically clear once the production types propagate.

- **Wave 5** is blocked; the only action item now is to note the 85 deferred diagnostics
  in the handoff for each owning campaign, so they clear their own files before merging.

- The `MasterKeyProvider` context-manager fix (Wave 1) is also required to unblock the
  2 contended-file occurrences in `test_iva_compensation_wallet_live.py` — clean that
  class first, then the contended test automatically inherits the fix.

- Do not introduce `type: ignore` suppressions as a shortcut. The mandate is to tackle
  the root cause; the wave structure above makes every diagnostic bounded and tractable.
