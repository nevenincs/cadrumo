---
tags:
  - '#research'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:54c662bb41745ab02471b232cd90ca70ab112452e25acab31963962bd7455464'
related:
  - "[[2026-06-10-ledger-interface-contract-research]]"
  - "[[2026-08-24-tui-architecture-command-enrollment-parity-reference]]"
---

# `clitui-ledger` research: `backend authority and interface parity campaign`

`clitui-ledger` is an authority-recovery and capability-parity campaign, not a TUI feature. The live CLI owns reusable query policy, cross-repository joins, provider workflows, and mutation decisions. Evidence favors hard gates: freeze the census; make every capability a tested frontend-neutral backend use case; reduce CLI to parsing, invocation, and rendering; implement missing backend and CLI capabilities; only then resume Ledger TUI work. The ADR must settle those gates, application contracts, export product boundaries, provenance, and active-plan reconciliation.

## Findings

### Existing architecture already requires backend authority

The CLI contract requires boundary parsing and normalization followed by the same application service used by other entrypoints. Accepted TUI architecture treats TUI, CLI, and MCP as projections over application operations, not imports of one another. This campaign restores an existing boundary. `.codex/rules/aeat-cli-contract.md`; `.vault/adr/2026-08-11-tui-architecture-adr.md:87`; `.vault/adr/2026-08-28-semantic-consolidation-cli-payload-projection-adr.md`.

### The CLI contains business policy, not only presentation

The list engine owns sortable-field projection, missing-last comparison, LLM-rejection state, review-filter mapping, grouping, ordering, paging, and row projection at `src/cadrumo/entrypoints/cli/_ledger_list.py:35`; backend exposes only fixed-order list/review primitives at `src/cadrumo/application/ledger/actions_manual.py:432`. Other confirmed candidates include creation policy at `src/cadrumo/entrypoints/cli/_ledger.py:212`, allocation at `src/cadrumo/entrypoints/cli/_ledger.py:624`, status/history/track joins at `src/cadrumo/entrypoints/cli/_ledger_read_cli.py:382`, ratio workflows at `src/cadrumo/entrypoints/cli/_ledger_ratios_cli.py:34`, Drive evidence ingestion at `src/cadrumo/entrypoints/cli/ledger_lifecycle_cli.py:170`, and prorrata orchestration at `src/cadrumo/entrypoints/cli/_prorrata_register_cli.py:139`.

Direct adapter construction may remain entrypoint composition. Multi-step policy, persistent events, joins, retries, partial-success meaning, provider choice, and result semantics belong in application use cases. Argument grammar, confirmations, localization, safe rendering, redaction, and exit-code mapping remain frontend responsibilities.

### The backend is broad enough to extend rather than rebuild

Application modules already own CRUD, lifecycle, split/merge, per-file import, flat export, classification, LLM primitives, evidence, ratios, preflight, and workspace projections under `src/cadrumo/application/ledger/`. `src/cadrumo/application/ledger/workspace_reader.py` demonstrates the target host-neutral door pattern. Backports should consolidate around these owners.

### Export is three products with different guarantees

The ledger emits deterministic CSV, JSONL, and XLSX through `src/cadrumo/application/ledger/actions_export.py:79` and `src/cadrumo/application/export/tabular.py:37`. These are flat reporting/interchange artifacts, not registry-shaped Modelo review/filing artifacts and not sealed restore archives.

Ledger XLSX is readable, but current round-trip evidence does not prove restoration: `src/cadrumo/entrypoints/cli/tests/test_ledger_workbook_export.py:79` ignores import exit status and accepts refusal/no-op, while `src/cadrumo/entrypoints/cli/tests/test_ledger_corpus_import_export.py:36` establishes that exported CSV and JSONL are not raw-bank inputs. The ADR must distinguish flat export, plaintext review package with optional Google Sheets transport, and encrypted restore archive.

### Missing backend capabilities are substantive

Missing capabilities include canonical export-to-restore, a review-grade workbook/Google transport, complete Ledger archive, evidence-byte download, atomic evidence replacement, append-only notes, exact field change-set provenance, arbitrary typed batch editing, and application-owned scalable sort/page queries. Reuse candidates include `src/cadrumo/application/storage/calc_sheets/workbook_export.py:122`, `src/cadrumo/application/modelo/review_package.py:183`, and the restore analogue at `src/cadrumo/application/user_profile/capsule_archive.py:137`.

### Production parity needs more than a command or screen existing

An earlier audit proves seven Ledger component factories resolve when injected authority exists, but the active plan records missing installed selection/import navigation at `.vault/plan/2026-08-11-tui-architecture-plan.md:627`. Component availability and installed reachability must be separate matrix fields. The ADR must reconcile a Ledger TUI hold with that in-flight plan rather than race it.

### The matrix must be an executable campaign ledger

Each row needs: capability/sub-operation; canonical backend command/result; backend status and real-behavior gate; CLI ownership/delegation and parser gate; TUI component and installed reachability; production composition; artifact validity; registry/Modelo consumer; provenance completeness; blocker and next step. Status must distinguish absent, partial, complete, CLI-owned, delegating, component-only, and installed.

Initial families are create/update/remove/archive/stash/restore/reset; list/filter/sort/group/page/search; review/classification/rules/LLM; batch patch and append-note; attachments and Drive pull; invoice reconciliation; split/merge/allocation/ratios/prorrata; import and FX; flat/review/Google/archive export; history/track/status/preflight; and registry/calculation participation and staleness.

### The ADR must choose the enforcement shape

Evidence favors global gates—backend completeness before CLI completion, CLI completion before TUI work—while allowing atomic slices inside the backend phase. The ADR must decide typed use-case ownership, exact CLI allowance, batch semantics, notes and changed-field provenance, evidence lifecycle, FX source/date visibility, restore versioning, export security, registry/calculation coverage, clean-break behavior, and active-plan reconciliation.

Uninvestigated before closure are the exhaustive command-to-application graph, every direct CLI adapter/repository import, backend-only tests for every command, attachment retention policy, every ledger-fed Modelo/revision/casilla binding, and end-to-end restoration/publication of proposed artifacts. These remain explicit work, not assumed completeness.

## Sources

- `.codex/rules/aeat-cli-contract.md`
- `.vault/adr/2026-06-03-modelo-export-evidence-parity-adr.md`
- `.vault/adr/2026-06-10-ledger-interface-contract-adr.md`
- `.vault/adr/2026-08-11-tui-architecture-adr.md`
- `.vault/adr/2026-08-28-semantic-consolidation-cli-payload-projection-adr.md`
- `.vault/adr/2026-09-02-unreachable-capability-tui-navigation-join-adr.md`
- `.vault/audit/2026-09-03-tui-architecture-w08-p27-s375-final-review-audit.md`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:627`
- `src/cadrumo/application/export/tabular.py:37`
- `src/cadrumo/application/ledger/actions_export.py:79`
- `src/cadrumo/application/ledger/actions_manual.py:432`
- `src/cadrumo/application/ledger/workspace_reader.py`
- `src/cadrumo/application/modelo/review_package.py:183`
- `src/cadrumo/application/storage/calc_sheets/workbook_export.py:122`
- `src/cadrumo/application/user_profile/capsule_archive.py:137`
- `src/cadrumo/entrypoints/cli/_ledger.py:212`
- `src/cadrumo/entrypoints/cli/_ledger.py:624`
- `src/cadrumo/entrypoints/cli/_ledger_list.py:35`
- `src/cadrumo/entrypoints/cli/_ledger_ratios_cli.py:34`
- `src/cadrumo/entrypoints/cli/_ledger_read_cli.py:382`
- `src/cadrumo/entrypoints/cli/_prorrata_register_cli.py:139`
- `src/cadrumo/entrypoints/cli/ledger_lifecycle_cli.py:170`
- `src/cadrumo/entrypoints/cli/tests/test_ledger_corpus_import_export.py:36`
- `src/cadrumo/entrypoints/cli/tests/test_ledger_workbook_export.py:79`
