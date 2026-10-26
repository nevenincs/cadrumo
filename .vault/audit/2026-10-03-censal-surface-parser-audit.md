---
tags:
  - '#audit'
  - '#censal-surface-parser'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:96fd247f83b82f3e2fcbc32cf3b3a46c2a7699c87772fa7bea0033ea7e582b06'
related:
  - "[[2026-10-03-censal-surface-parser-plan]]"
---

# `censal-surface-parser` audit: live census driver and canonical observation review

## Scope

S01, reviewed on 2026-10-03. Includes the driver and additive observation changes captured by concurrent shared-worktree snapshot f4729489f9, plus the subsequent working-tree corrections and synthetic tests. Governing decision: 2026-10-03-censal-surface-parser-adr. Review traced fetch_censal_datos through the existing application/live/censo acquisition door, reviewed operand, encrypted reference repository and shared TUI/CLI profile-adoption authority. No alternate sync route or profile model was introduced.

Verification: 105 passing tests in the combined driver/guard/parser/operand/preview/CLI/sync run, followed by the three corrected sync tests passing. Logs: test-runs/2026-10-03/20261003T134508.329405Z-pytest-49320-09e3c02c/run.log and 20261003T134853.219668Z-pytest-53332-868083d9/run.log under the Windows temporary .logs directory. Scoped Ruff lint/format and ty checks pass. Refreshed generated import inventory with its owning command; import_load_probe loaded all 4332 configured non-test modules with zero failures.

Real Cl@ve Movil own-name authentication and a final production-driver pull succeeded. Captured identity/addresses, one activity, three premises with activity association, 77 tax-status rows and three obligations. Every rendered tax fieldset text was accounted for; complete observation equality survived the canonical encrypted-reference round trip. Private values were not copied to fixtures or vault records. Browser/provider/profile scopes were closed after verification.

Verdict: PENDING only for repository-wide type/import-boundary verification. No unresolved in-scope functional defect was found. Implementation and live capture are verified; the Step remains open rather than claiming that required global gates passed.

### S02: persistent frontend readback

Reviewed 2026-10-03 against uncommitted S02 changes. The full observation stays in the existing encrypted preview result; reviewed captures resolve through their existing result and reviewed operand. One application reader supplies the existing preparation operation and workbench generation. CLI `config profile censo show` and the TUI restore this evidence. No separate census store or AEAT write path was introduced.

The combined focused run passed 132 tests and exposed two reviewed-readback failures; their corrected rerun passed both. A further 48 workbench/CLI tests passed, including concurrent-capture refusal. Logs under `var/storage/development/.logs/test-runs/2026-10-03`: `20261003T145650.216168Z-pytest-68900-59750ed8/run.log`, `20261003T145911.719604Z-pytest-89208-64f177b0/run.log`, and `20261003T150056.164139Z-pytest-51316-6d7e7209/run.log`. Fresh journal and encrypted-reference instances recover complete synthetic observations after preview, accepted adoption, and declined adoption, selecting the later capture. Actual Textual screens pass reopen, unknown-column, serialization and full-value keyboard-selection checks at widths 80 and 120. Scoped Ruff and ty checks pass.

S02 verdict: PENDING. Installed live frontend round trips have not passed. The native runtime rejects this agent's Windows Session 0 at `windows_desktop_logon.py:_native_token_fields_are_supported`, before password admission or AEAT access. Both CLI and TUI reach this same refusal. No guard was weakened. `.tmp/censal-ui-verify.py` prepares the real desktop-run CLI pull/read, TUI read/pull, fresh CLI read and reopened TUI read sequence, using Clave Movil and in-memory comparisons. Prior S01 live-driver evidence does not establish installed frontend readback.

## Findings

### historical-review-digest | medium | Additive defaults changed historical digest preimages; corrected

The observation's empty consultations default must be excluded when reproducing older reviewed operands. The canonical digest producer now preserves that historical preimage while including all nonempty consultation evidence. Old-record restoration, tamper rejection and encrypted custody tests pass.

### obsolete-test-result-decoder | low | Existing sync helper bypassed typed result custody; removed

Three integration tests reached successful terminal operations but tried to decode an obsolete censo-review string. The helper now resolves the canonical typed result through the existing public result service. Apply, reject, provenance and single-review checks pass without changing the production settlement path.

### global-verification | medium | Shared workspace prevents a clean repository-wide verdict

The configured type harness reported 132 diagnostics across platform checks in unrelated shared-worktree code; focused census module and helper type checks pass. The import gate reported a harness test dependency through cadrumo.conftest to entrypoint composition, existing private/reexport findings, stale generated targets and changes during its run. Generated targets were refreshed and the separate loadability phase now passes all 4332 modules. The full boundary gate has not been represented as passing. Owner: repository integration workstream; next action: rerun configured type/import gates after the concurrent worktree changes settle and address their findings.

### supported-shape-boundary | low | Unsupported redesign and incomplete pagination refuse explicitly

Parsers retain unknown columns, original labels, casilla identifiers and unresolved rendered cells. Empty-result markers are distinguished from missing/loading tables. Required tax sections and unparsed text are checked. Missing semantic structure or a partial paginated result refuses the pull. Multi-page acquisition and arbitrary redesign are not claimed supported. The observed live account's complete single-page consultations passed.

### preview-evidence-readback | medium | Complete preview evidence was not retained; corrected

Preview results previously retained only reconciliation facts; reopened workspaces always described census as never captured. The existing encrypted preview result now carries the canonical observation. Preparation and workbench generation share one journal-backed reader. Legacy previews without evidence remain uncaptured; missing historical facts do not become confirmed blanks.

### census-journal-subjects | medium | Preview and review use distinct existing subject contracts; corrected

The first reader incorrectly applied the preview's hashed subject to both operation families. Real-supervisor tests exposed missing reviewed captures. Selection now follows each operation's existing subject contract and validates the decrypted profile identity. Accept and decline tests pass, including subsequent newer captures, without migrating historical records.

### desktop-live-roundtrip | medium | Installed acceptance requires an interactive Windows desktop

Native transport connects, but profile login rejects Session 0 before provider access. CLI and TUI both show this refusal. Owner: this feature. Next action: run the prepared `.tmp/censal-ui-verify.py` from the operator's normal Windows terminal with phone approval and address downstream failures. The verifier never uploads to AEAT. Keep S02 open until actual installed round-trip evidence passes.

## Recommendations

Keep the Step open for the global-verification finding; retain existing passing focused and live evidence while the relevant code stays unchanged. Use the shared adoption authority for future grounded regime mappings. Do not infer tax eligibility from retained rows or add another profile synchronization path.
