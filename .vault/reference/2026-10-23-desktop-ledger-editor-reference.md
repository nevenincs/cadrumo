---
tags:
  - '#reference'
  - '#desktop-ledger-editor'
date: '2026-10-23'
modified: '2026-10-23'
body_schema: 'body-v2'
body_hash: 'sha256:f2b176ba58f728e33a04672d381b28ffc3603bff13f7c5edc4e60aa99c62d091'
related: []
---

# `desktop-ledger-editor` reference: `Ledger surfaces and the desktop relay: what a desktop ledger editor builds on`

Read-only discovery on 2026-10-23 across the desktop frontend and host, the person relay, the CLI ledger family, the TUI ledger workspace, and the ledger, invoice and import/export application code. Line numbers are those observed on that date and can drift. The symbols named are the stable locators.

## Summary

### Desktop host and relay

- Every webview command is a closed Tauri command, registered through the `commands!` macro and gated by the per-launch token in `dispatch` (`native/desktop/src-tauri/src/app.rs:23-115`). The composed module list is at `app.rs:140-160`.
- Profile data reaches the window through the held person's child, `cadrumo-runtime session hold` (`native/desktop/src-tauri/src/agent/person.rs`, `Person::hold`). The wire is one JSON request per line, capped at 16,383 bytes, correlated by `request_id` and checked for the runtime boot and connection ids.
- The Python relay accepts `operation_submit {definition_id, subject_ref, payload}`, `operation_observe`, `operation_result`, `operation_review`, `operation_respond {review_digest}` and `operation_cancel` for any definition (`src/cadrumo_runtime/host/session_hold_operations.py`, `RELAY_ACTION_KEYS`, `OperationRelay`). The runtime then decodes the payload against the registered contract (`src/cadrumo_runtime/host/operation_host.py`, `submit_payload`) and applies the access policy (`src/cadrumo/application/user_profile/operation_access_policy.py`). The frontends that count as persons are CLI, TUI and DESKTOP (`src/cadrumo/application/operations/person_acts.py`, `PERSONS_FRONTENDS`).
- The settle pattern is `ProfileHost::run`: submit, observe until `operation_changed` reports settlement, read the result, with a 90 s bound (`native/desktop/src-tauri/src/shell/user_profile.rs:116-188`). An unknown outcome of a mutation is reported as unknown, and a committed write whose readback fails is reported as `saved_unread`.
- Digest-bound answers already exist in two flows. Censo answers with `review_digest` through `operation_respond` (`native/desktop/src-tauri/src/shell/user_profile/censo.rs:308-365`). Setup answers with `planDigest` and refuses a changed plan with `plan_changed` (`native/desktop/frontend/src/ipc/contract.ts`).
- The only native file picker today feeds agent storage (`native/desktop/src-tauri/src/agent/mod.rs`, `agent_attach`, `tauri_plugin_dialog`). No product code wires drag and drop. `DropOverlay` is mounted only in stories.

### Desktop frontend

- Pages are `Layout["page"]` values (`native/desktop/frontend/src/shell/layout.ts:46`: docs, calendar, profile), wired in `App.tsx` through visibility flags, the first pane, the focus helpers, actions and the rail. Host capabilities are optional ports on `Host` (`src/shell/host.ts:114-205`), implemented in `src/shell/tauriHost.ts` and answered by the scenario host in `src/dev/scenarioHost.ts`.
- No grid, table or virtualisation primitive exists. `RecordList` hand-rolls block windowing (`src/components/RecordList.tsx`, `WINDOW`, `BLOCK`) with `role="log"`. The staged-edit and compare-and-swap pattern is `ProfileEditor` and `useUserProfile` (`src/components/profile/ProfileEditor.tsx`, `src/shell/userProfile.ts`).
- Design-system enforcement is the `design-system/token-styles` and `design-system/component-names` ESLint rules plus the layer import restrictions (`dev/eslint/design-system.mjs`, `eslint.config.js`). Colour roles are defined in `src/styles/theme.css` and lengths in `src/styles/tokens.css`. Strings are `desktop.*` keys declared in `dev/locales/desktop_chrome.py` (en, es, ca, hu).

### CLI and TUI ledger surface

- `aeat app ledger` has 88 leaves (`src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`). Command paths map to operations in `src/cadrumo/entrypoints/cli/command_operation_table.py`, and contracts are in `src/cadrumo/_data/operations/contract_manifest.json`. Only `ledger.classify.review` and `ledger.split.review` declare a review interaction.
- The TUI workspace has seven areas (`src/cadrumo/application/ledger/workspace.py:55-64`, `LedgerWorkspaceArea`) and 27 tools (`src/cadrumo_runtime/host/frontend/tui/runtime_ledger_tools.py`). Its doors submit about eighty `ledger.*` definitions through the runtime profile session (`src/cadrumo_runtime/host/frontend/tui/runtime_ledger_*.py`).

### Contract facts a grid must respect

- Listing: `LedgerTransactionListQuery` orders filter, group selection, sort, group partition, then paging (`src/cadrumo/application/ledger/list_query.py:53-408`). It has nine sort axes (`src/cadrumo/core/ledger_sort.py:29`) and filter keys status, period with year, issue, import, classification, text, direction and account (`src/cadrumo/application/review/filter.py:137`).
- The only multi-row write for row facts is `ledger.classify.bulk`. It takes CSV with `classification` required on every row, loads once, saves once, is revision-guarded and collects per-row failures (`src/cadrumo/application/ledger/bulk_classify_operation.py`, `src/cadrumo/application/ledger/actions_classification.py:301-362`). `ledger.update` edits 14 fields of one row (`src/cadrumo/application/ledger/update_contracts.py:27-62`).
- Editing amount, description, effective date or own account re-keys `transaction_id` (`src/cadrumo/domain/transactions/models.py:92-130`). Rows cited by sealed revisions refuse writes (`src/cadrumo/application/ledger/actions_manual.py:1252-1275`).
- The invoice catalogue has no draft state, its lines are write-once, and `ledger.invoice.list` filters only by kind (`src/cadrumo/domain/invoices/models.py:313-448`, `src/cadrumo/application/invoices/`).
- Bank import binds apply to previewed SHA-256 digests through `expected_source_sha256` (`src/cadrumo/application/ledger/import_operation.py:104-141`). Invoice-book import has no dry run (`src/cadrumo/application/invoices/catalogue_intake_contracts.py:25-45`). `ledger.export` overwrites its target (`src/cadrumo/application/ledger/actions_export.py:113`).
