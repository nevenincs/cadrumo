---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:df6ee1bc4890c25c281a198010b3c5061e8ec109036f1648c38c923ee1633849'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S06 phantom source-kind removal`

## Scope

Formal read-only review of the current unstaged `W01.P02.S06` deletion across `_required_binding_gate.py`, `state_projection.py`, `_modelo_discovery_cli.py`, the related binding-readiness, data-inventory and wizard documentation, and the taxonomy and CLI regressions. The review was grounded through `vaultspec-rag`, the full `casilla-schema` plan and research, the canonical `BindingSourceKind` authority, registry-authority and quality rules, the no-legacy rule, and the shared-worktree boundary. Unrelated action-envelope, terminology, transport, LLM, period, storage-taxonomy, external-grounding, and other peer WIP was excluded.

The production change deletes all four phantom assumptions identified by research: the M202 required-binding exemption, the state-readiness exemption, the CLI readiness-label entry, and the `bindings list --missing` row exemption. Supporting prose no longer claims a literal-value source exists. The wizard's promptable source set remains exactly `manual_input` and `profile`; deletion of the phantom explanation does not widen operator entry to ledger, prior-filing, relation, or pre-mesh sources.

The real authority is consistent. `BindingSourceKind` contains 27 canonical members and no `constant_value`; the loaded registry declares 23 source kinds and no `constant_value`. A production-tree search finds zero exact token references. The new negative enum regression proves the retired token refuses typed validation; no alias, fallback, tolerance branch, compatibility shim, or replacement pseudo-source was added.

The `--missing` implementation still applies both live conditions: it removes binding ids resolved by the active profile and retains only rows whose registry query projection says `operator_input_required`. The latter remains derived from the real revision and period, including Modelo 202 relation-prefill default semantics. The weak former surface test that only asserted the echoed `missing_filter` flag has been deleted. The retained strict-subset integration test persists a real profile in real isolated storage, invokes the real CLI twice, and proves that `--missing` removes exactly the profile-resolved bindings. The no-profile and M200/M202 relation-guidance tests exercise the conservative and period-scoped branches. No fake, mock, stub, patch, monkeypatch, skip, xfail, or mirrored filtering implementation was introduced.

## Findings

No actionable findings.

The three failures observed in a broader unrestricted selector run are outside S06 behavior: each stops in the unchanged `_create_profile` fixture because quiet profile creation now requires `--tax-residence-jurisdiction-scope`, before the binding listing or readiness path runs. The broader CLI BasedPyright lane likewise remains red with 139 existing private-import, unknown-type, missing-annotation, and Typer registration diagnostics spread through the two large CLI modules; the S06 edits delete string comparisons and comments and introduce none of those diagnostics. These boundaries are recorded rather than hidden or repaired through peer-owned fixtures.

## Recommendations

No S06 changes requested. Keep `BindingSourceKind` and the loaded registry as the sole source-kind authorities, keep the retired-token refusal regression, and do not reintroduce a literal-value alias or special-case exclusion. Repair the independent CLI profile fixtures and legacy typing debt under their existing owners rather than absorbing them into this atomic deletion.

## Verification

- Production exact-token search: zero `constant_value` references outside tests.
- Authority probe: 27 enum members and 23 loaded registry source kinds; neither contains `constant_value`.
- Focused default unit lane: 9 passed; 8 integration selectors were explicitly deselected by configured markers and were not claimed as executed.
- Focused unrestricted selector run: 14 passed and 3 failed. All three failures are the known missing `--tax-residence-jurisdiction-scope` fixture precondition and occur before S06 code executes.
- The executed green integration paths include the real strict-subset profile filter, the no-active-profile conservative listing, and the M200/M202 relation-guidance cases.
- Real `aeat app registry verify`: verified true with 73 modelos, 94 revisions, 799 legal references, 316 source references, and 16,800 casillas.
- Scoped Ruff across all S06 files: exit 0, all checks passed.
- Scoped BasedPyright across the application/state/taxonomy subset: exit 0, zero errors, warnings, and notes.
- Broader CLI BasedPyright boundary: 139 existing diagnostics, none introduced by the removed-token lines; not treated as green.
- Scoped `git diff --check`: exit 0; only existing CRLF normalization warnings were emitted for two touched CLI paths.
- Prohibited-test-construct scan: no executable fake, stub, mock, patch, monkeypatch, skip, or xfail construct in the S06 tests.

Verdict: **PASS.** `W01.P02.S06` removes the phantom source kind completely from production behavior and prose, preserves the real profile-resolution plus `operator_input_required` missing-filter contract, adds a typed refusal for the retired token, deletes the tautological echo-only test, and introduces no compatibility surface or unrelated shared-worktree repair. The observed broader reds are independently attributable and do not execute S06 behavior.
