---
tags:
  - '#audit'
  - '#aeat-verify'
date: '2026-04-24'
modified: '2026-04-24'
related:
  - "[[2026-04-24-aeat-verify-plan]]"
  - "[[2026-04-24-aeat-verify-adr]]"
---



# aeat-verify code review audit

Full code-review audit of the `#239` aeat-verify feature branch covering
the two new subpackages (`aeat.remote` and `aeat.application.filing.reconciliation`),
the `aeat filing reconcile` CLI surface, and the `aeat sync run`
auto-reconcile integration. Verdict line below.

## Verdict

`APPROVED-WITH-NITS` — the two remaining nits (Medium-severity M1 and
M2) are resolved in the same commit that persists this audit, so the
branch is effectively `APPROVED` at the point the code-review
artefact is written to disk.

## Scope

The six feature-branch commits plus the merge commit with `origin/main`
that preceded this audit:

- `66e832b` `feat(remote): aeat.remote domain foundation (#239, phase 1)`
- `f6ecbb2` `feat(remote): modelo 130/303/390 read-only fetchers + navigation catalogue (#239, phase 2)`
- `60aa470` `feat(filing): reconciliation comparator for FilingDraft vs RemoteFiling (#239, phase 3)`
- `63f15a9` `feat(cli): aeat filing reconcile subcommand (#239, phase 4)`
- `eeeb2bc` `feat(sync): auto-reconcile APPROVED drafts in aeat sync run (#239, phase 5)`
- `d509d8e` `chore(deps): pin tree-sitter-language-pack below 1.6.3 for cp313`
- `5bce67c` `Merge remote-tracking branch 'origin/main' into feature/239-aeat-verify`

Scope includes every file under `src/aeat/remote/`,
`src/aeat/application/filing/reconciliation/`, the CLI surface at
`src/aeat/application/filing/_cli.py`, the sync-run surface at
`src/aeat/application/sync/_run.py`, and their colocated test suites. Out of scope:
modules untouched on this branch.

## Non-negotiable constraints audit

- **Zero writes on the wire**: verified. No module under `aeat.remote`
  or `aeat.application.filing.reconciliation` contains a mutating Playwright
  primitive, a mutating HTTP verb, or an English/Spanish write-verb
  prefix on the public API. The Layer 3 structural grep guard at
  `src/aeat/remote/test_no_write_surface.py` and
  `src/aeat/application/filing/reconciliation/test_no_write_surface.py`
  enforces this at CI time, and both walk their respective subtrees
  exhaustively.
- **Clave never mocked**: verified. The live-read integration test at
  `src/aeat/remote/test_fetch_live.py` is gated behind
  `AEAT_LIVE_TESTS_ENABLED` and exercises the real authenticated
  Playwright session; no Clave shim, double, or stub exists in the
  tree.
- **Strict pydantic v2**: verified. Every `BaseModel` under the two
  new subpackages carries
  `ConfigDict(strict=True, frozen=True, extra="forbid")`. The Layer 1
  write-guard marker `mode: Literal["read"] = "read"` was already
  present on every `aeat.remote` record; it is now present on every
  `aeat.application.filing.reconciliation` record too (M1 fix in this commit).
- **No edits to forbidden modules**: verified. The closed
  `aeat.application.sync._divergence.DivergencePayload` discriminated union is
  not widened. The persistence adapter emits a parallel wrapping
  record (`FilingReconciliationDivergenceRecord`) per the ADR's
  fork-rationale paragraph.
- **Public API discipline**: verified. Every `__init__.py` under the
  two new subpackages exports a sealed, sorted `__all__` tuple, and
  every leading-underscore module is private by construction.

## Findings

### Critical

None.

### High

None.

### Medium

- **M1 — `mode: Literal["read"] = "read"` missing on reconciliation
  records**. `src/aeat/application/filing/reconciliation/_schema.py` and
  `src/aeat/application/filing/reconciliation/_persist.py` did not carry the
  Layer 1 write-guard marker on `CasillaDelta`, `FilingDraftRef`,
  `ReconciliationReport`, the six payload variants, or
  `FilingReconciliationDivergenceRecord`. The adjacent
  `aeat.remote._schema` already complied; the reconciliation
  subpackage inherited the same boundary-crossing contract and
  therefore owes the same marker. **Status: FIXED IN THIS COMMIT.**
  Field added to every record, module docstring updated to mention
  the marker, runtime test
  `test_every_boundary_record_reports_read_mode` added to
  `src/aeat/application/filing/reconciliation/test_no_write_surface.py`.
- **M2 — Dead `elif delta == 0` branch in `_classify_pair`**.
  `src/aeat/application/filing/reconciliation/_reconcile.py:145-147` carried an
  unreachable branch that re-classified a zero delta as
  `ROUNDING_ONLY`. The caller in the same module at lines 351-352
  already short-circuits with `continue` whenever
  `local_decimal == remote_decimal`, so the branch can never be
  entered. **Status: FIXED IN THIS COMMIT.** Branch removed; full
  test suite re-runs green (76 reconciliation tests, 3364 total
  after the new Layer-1 runtime test lands — +1 over the
  pre-fix baseline of 3363).

### Low

- **L1 — Narrative builder duplicates mirror pattern**. The
  trilingual narrative builder at
  `src/aeat/application/filing/reconciliation/_narrative.py` intentionally
  mirrors `aeat.application.verification._verify._compose_narrative` by value,
  as the ADR requires. A future refactor could lift the shared
  vocabulary into `aeat.core.i18n` to eliminate the by-value duplication,
  but the ADR explicitly accepts the duplication so Kent sees one
  definition of "rounding" today. **Status: accepted per ADR.**
- **L2 — `_FILING_SCOPE_SENTINEL` is a 1-char placeholder**. The
  `"*"` sentinel used for filing-scoped (non-casilla) divergences
  in `_reconcile.py` works, and the field's `max_length=16`
  accommodates longer sentinels. If a future contributor surfaces a
  second filing-scope divergence kind, a two-sentinel taxonomy may
  collide. **Status: noted; no action required while the taxonomy
  has a single filing-scope kind.**
- **L3 — Payload variant ordering is alphabetical, not ADR-ordered**.
  `FilingReconciliationPayload` in `_persist.py` orders its variants
  by declaration order in the union expression. A contributor
  adding a new variant should append to the end; the
  discriminator-keyed union does not rely on order. **Status:
  cosmetic.**
- **L4 — `reconciliation_records` returns an empty tuple for MATCH**.
  This is correct behaviour — `MATCH` reports have nothing to
  surface on the Kent-facing divergence queue — but the return type
  is `tuple[..., ...]` without an `Empty` marker class, so callers
  rely on `len(records) == 0` to detect the branch. The CLI surface
  handles this correctly today. **Status: acceptable.**
- **L5 — `_record_id` uses SHA-256 truncated to 32 hex chars**. The
  32-char prefix gives ~128 bits of collision resistance; the record
  id is stable per `(draft_id, casilla_id, kind)` so a collision
  would require two distinct `(draft, casilla, kind)` triples
  hashing to the same prefix. **Status: acceptable given the
  content-addressed scope.**

### Coverage gaps

- **C1 — No probe script for the live-read fetcher**. The Phase 2
  live-read path is covered by
  `src/aeat/remote/test_fetch_live.py`, which is a pytest item
  gated behind `AEAT_LIVE_TESTS_ENABLED`. A standalone
  `scripts/probe_remote_fetch.py` would let Kent verify the fetcher
  against his real AEAT session without running the full pytest
  invocation. **Status: deferred; the pytest item is the system of
  record today.**
- **C2 — `aeat sync run` auto-reconcile integration relies on a
  real `RemoteFilingFetcher` Protocol-conforming class in tests**.
  The Phase 5 sync-run integration test at
  `src/aeat/application/sync/test_run_reconcile.py` builds a real pydantic
  `RemoteFiling` inline and threads it through via a
  Protocol-conforming class (no mocks). One edge case not covered:
  `RemoteFilingStatus.UNKNOWN` on a submitted draft. The current
  coverage matrix touches `EN_TRAMITACION`, `RECHAZADA`, and
  `ANULADA`; `UNKNOWN` goes through the same divergence path but is
  not explicitly exercised. **Status: low-priority gap, matrix
  extension recommended but not blocking.**
- **C3 — CLI surface does not have a negative test for malformed
  `--draft-id`**. `aeat filing reconcile --draft-id` is typed by
  Click / the project's CLI framework, and the pydantic record it
  loads is strict. A directly-invoked unit test for the error path
  when `--draft-id` does not resolve to a persisted draft would
  firm up the operator-facing error. **Status: low-priority gap.**

## Commendations

- **The fork-rationale for `DivergencePayload` is the right call**:
  widening the closed discriminated union would silently widen
  `aeat.application.sync`'s auto-heal-safety contract, which is load-bearing for
  the existing Kent-facing divergence queue. The parallel wrapping
  record is the minimum structural change that preserves both
  contracts.
- **The Layer 3 grep guard is self-covering**: the fixture lives as
  a plain-text sidecar so no forbidden token has to appear in any
  importable Python source, including the guard's own test. This
  composes well with the new Layer 1 runtime test.
- **The trilingual narrative builder mirrors the existing
  verification pattern by value**: Kent sees one definition of
  "rounding" and one definition of "divergence" across the project.
  The by-value duplication is explicit in the ADR, not accidental.
- **The pure async-free comparator keeps `reconcile` easy to test
  exhaustively**: 44 reconciliation tests walk the full decision
  table (terminal triad crossed with six divergence kinds plus the
  rounding edge cases) without any I/O seam.
- **The `aeat filing reconcile` CLI surface carries a clear
  exit-code contract**: `0` for MATCH, `1` for DIVERGENT, `2` for
  NOT_YET_FOUND. Kent's automation can branch on the exit code
  directly.

## Final test gate

After M1 and M2 are applied in the same commit as this audit, the
standard gate command chain reports:

- `just lint` — ruff check + relative-imports guard both pass.
- `just typecheck` — `ty check src tests` passes.
- `just test` — 3364 passed, 5 skipped, 29 deselected (the +1 over
  the pre-fix 3363 count is the new
  `test_every_boundary_record_reports_read_mode` Layer-1 runtime
  test landing in `src/aeat/application/filing/reconciliation/test_no_write_surface.py`).
- `just hooks` — every `prek` hook (whitespace, EOF, YAML, TOML,
  large-file, merge-conflict, private-key, ruff check, ruff format,
  `ty`, relative-imports guard) passes.
