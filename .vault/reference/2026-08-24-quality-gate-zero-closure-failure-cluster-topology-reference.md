---
tags:
  - '#reference'
  - '#quality-gate-zero-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:6086d256dab08d4b0c57a94260c78c7bee03a977dd86872b739c61ba1e9513e7'
related:
  - "[[2026-08-24-quality-gate-zero-closure-static-gate-matrix-research]]"
  - "[[2026-06-04-repo-health-triage-reference]]"
  - "[[2026-08-16-test-harness-sanity-suite-performance-baseline-reference]]"
---
# `quality-gate-zero-closure` reference: `Quality gate zero closure failure cluster topology`

## Summary

This reference turns the 2026-08-24 dirty-tree inventory into an executable
closure map. It names the existing gate authorities, the observed failure
clusters, the active plan that owns each overlapping surface, and the proof
sequence that preserves gate meaning. The counts are measurement notes only:
re-run every command after an owner batch and record the commit and dirty-path
set beside the result.

## Gate authority map

| Surface | Canonical command or authority | Scope and acceptance |
| --- | --- | --- |
| Ruff style | `justfile:225-228` and `uv run --no-sync ruff check .` | Repository Python tree; exit 0, with no exclusion added for active work. |
| Ruff format | `justfile:230-233` and `uv run --no-sync ruff format --check .` | Repository Python tree; exit 0, with formatter output reviewed for peer-owned paths. |
| Types | `justfile:237-240`, `dev/quality/types.py:29-31,109-183,235-280` | ty over `src`; pyrefly and BasedPyright over configured strict domain/application surfaces; zero diagnostics and no unresolved-import allowance. |
| Architecture imports | `justfile:242-245`, `dev/quality/suite.py:37-44` | Import-linter contracts remain kept; no new carve-out or pin without the owning architecture decision. |
| Relative imports | `justfile:247-248`, `src/cadrumo/tests/test_relative_imports_only.py:82-91` | No absolute intra-`cadrumo` imports in the scanned test/source surface. |
| Dependencies | `justfile:250-253` | `src/cadrumo` and `dev/registry`, with test trees excluded by the recipe; deptry emits no findings. |
| Ratchets | `justfile:462-464` | Inventory, marker, shortcut, double, monkeypatch, broad-raise, bare-except, tautology, and related policies all pass. |
| Vault | `uv run --no-sync vaultspec-core vault check all --json` | Hard-error count is zero. Warnings are a separately reported inventory, not silently converted to success. |

`dev/quality/suite.py:37-44,94` confirms that the static dashboard executes
each static gate and aggregates failures instead of stopping after the first
red. `.github/workflows/ci.yml:153-163` is the per-push static route; the local
recipe and CI route should remain byte-equivalent in scope.

## Failure cluster map

The 2026-08-24 snapshot observed 5,182 type diagnostics (1,949 ty, 1,206
pyrefly, 2,027 BasedPyright), 86 Ruff findings, 310 format files, nine
recipe-scoped deptry findings, 23 failed and 143 passing ratchet tests, and 18
Vault hard errors. These numbers drift in a concurrent worktree and must not be
used as a baseline.

- **Type root causes.** The largest pyrefly cluster is
  `src/cadrumo/application/calculations/_row_set_assembly.py`; ty is dominated
  by `call-non-callable` and `unresolved-attribute`; BasedPyright is dominated
  by unknown-member and unknown-argument families. Begin with the shared
  type-producing boundary or protocol that fans into the cluster, then rerun
  all three checkers. Do not add a diagnostic baseline, blanket cast, or
  unresolved-import allowance; the empty allowance at
  `pyproject.toml:860-868` is part of the contract.
- **Ruff and format.** The largest line-length cluster is
  `src/cadrumo/application/filing/_export_producer.py:589-832`; import-order
  findings are distributed across profile, application, CLI, and test modules.
  Four syntax records were present in
  `src/cadrumo/entrypoints/cli/tests/test_action_reconciliation_invocation_scope.py:52-75`.
  Repair syntax first, then run owner-scoped formatter/import sorting; verify
  behavior tests for any file whose imports are reorganized.
- **Dependencies.** The recipe-scoped nine include local `dev` imports, plus
  direct `grimp` and `tomlkit` imports that are not present in the dev group
  beginning at `pyproject.toml:340-355`. Validate the first-party map before
  treating local `dev` as a missing package; declare genuinely direct tooling
  dependencies rather than adding per-rule ignores.
- **Inventory and topology ratchets.** Relocation assertions remain in
  `dev/tests/test_test_inventory.py:929-959,1511-1547,1644-1653`, while
  `dev/tests/_project_inventory.py:18-53` defines `dev` and `docs` as project
  test roots. Marker, absolute-import, skip/xfail, mock/double, broad-raise,
  and monkeypatch failures are separate policy families. Repair the owner
  policy or its test topology; do not make the inventory pass through a path
  allowlist.
- **Vault hard errors.** The current hard-error set is twelve frontmatter
  violations in three hand-authored records:
  `.vault/audit/2026-08-23-issue-113-operator-gate-audit.md`,
  `.vault/reference/2026-08-23-registry-unblock-loop-reference.md`, and
  `.vault/reference/2026-08-24-registry-unblock-loop-reference.md`; and six
  schema violations in older ADR/plan records lacking grounding. Repairs must
  be made through the owning Vault CLI, with the missing references and
  provenance reviewed by the owning feature. Do not run a global fix in a
  shared dirty tree without a path ledger.

## Ownership routing

The active plans overlap the failure surface and must retain path authority:

- `test-harness-sanity` owns marker/live-import enforcement, monkeypatch
  removal, central-harness topology, and the reopened W09 census
  (`.vault/plan/2026-08-14-test-harness-sanity-plan.md:115-153,185-225`).
- `import-centralization` owns the private/import-boundary sweep, including
  relative-import consumers; do not repoint those consumers in an unrelated
  type or style batch.
- `secure-storage-performance-hardening` explicitly owns repository-wide
  lint, architecture, full-test, and Vault convergence in `W05.P11.S43`, with
  independent closure in `W05.P12`
  (`.vault/plan/2026-08-22-secure-storage-performance-hardening-plan.md:146-160`).
- `source-casilla-integration` owns connected-proof and row-observation
  surfaces (`.vault/plan/2026-08-22-source-casilla-integration-plan.md:122-126,293-400`).
- `registry-completeness-closure` owns live proof wiring and registry
  conformance closure (`.vault/plan/2026-08-24-registry-completeness-closure-plan.md:48-79`).
- TUI, profile-password-custody, CI-lane-deconflation, and documentation plans
  own their corresponding adapter, profile, workflow, and docs paths. Confirm
  the current status ledger before touching a path not listed above.

The safe handoff record for every batch is: path set, owning plan/Step, starting
HEAD, dirty-path overlap result, command transcript, focused behavior proof,
and post-batch full-gate result. If the owner cannot accept the batch, record a
new unowned finding for ADR/plan adjudication instead of silently editing it.

## Sequencing protocol

1. Capture `git rev-parse HEAD`, `git status --short`, the active-plan status,
   and all gate outputs. Store counts as a dated snapshot with no baseline
   semantics.
2. Clear syntax blockers and path-local Ruff/format defects only where the
   owner has accepted the path. Re-run the affected focused tests, then the
   full style and format checks.
3. Resolve deptry's first-party classification and direct-dependency findings.
   Run the packaging dependency preflight after changing `pyproject.toml`.
4. Reduce type diagnostics by root-cause families. For each family, record the
   dominant rule/file before and after, run relevant tests, then run all three
   type checkers. A count reduction is not sufficient if behavior or another
   checker regresses.
5. Route ratchet failures to the active test-harness/import/profile/registry
   owner. Preserve real behavior and mutation-biting controls; never add
   skip/xfail, mock/monkeypatch exemptions, or stale topology allowlists.
6. Repair Vault hard errors with `vaultspec-core vault edit` or the owning
   lifecycle verb. Rebuild affected feature indexes only when their owner
   accepts the change. Run targeted checks, then global `vault check all`.
7. Re-read HEAD and the status ledger. Repeat the full matrix from a clean
   verification snapshot; separate hard errors from warnings and separately
   record external/credential-gated lanes.

## Verification contract

A closure report should include, for each command:

- exact command and environment;
- start/end HEAD and whether the worktree was clean;
- exit status and full failure count;
- top rules/files only as diagnostics, never as a pass threshold;
- focused tests proving the changed behavior;
- active-plan owner and path scope;
- any warning or environment gate left outside the hard predicate.

The final static predicate is exact zero for style, format, types, imports,
relative imports, dependencies, and ratchets. The final Vault predicate is
zero hard errors; warnings remain visible until their own owner resolves them.
CI's integration lane has an explicit `continue-on-error` enrolment
(`.github/workflows/ci.yml:219-242`), so a closure report must state whether
that lane was actually green or only enrolled.

## Safety constraints

The quality policy requires real behavior and forbids mocks, fakes, stubs,
monkeypatches, skip/xfail shortcuts, tautological assertions, and hidden
allowlists (`.codex/rules/aeat-quality-gates.md:10-11,56-60,78-85`). Vault
frontmatter, filenames, related links, body hashes, and modified stamps are
owned by `vaultspec-core`; only scaffolded body prose may be edited manually
(`.codex/rules/vaultspec-cli.builtin.md:13-19,67-70`,
`.codex/rules/vaultspec.builtin.md:193-201`). These constraints are part of
the closure proof, not optional cleanup after the gates turn green.
