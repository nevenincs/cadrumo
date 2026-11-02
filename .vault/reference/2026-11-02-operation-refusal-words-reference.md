---
tags:
  - '#reference'
  - '#operation-refusal-words'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:126c5ee959b5c0307edeabe19cec032e88e1b121fa00090d5e655784a1302011'
related: []
---

# `operation-refusal-words` reference: `Refusal detail path from worker to window`

How a registered operation's refusal travels from the Python worker to the desktop window, read in the current source of this checkout.

## Summary

- The catalogue owns the localized refusal sentence: `src/cadrumo/core/errors/error_codes.py:541` (`resolve_error_message`) renders it for the CLI. Public context is scrubbed by `src/cadrumo/core/errors/error_codes.py:354` (`public_error_context`).
- The worker records a stopped executor's error as `OperationErrorDetailV1`, built at `src/cadrumo/application/operations/error_detail.py:292`. It is stored only for definitions with `public_error_detail=True`.
- The served sentence fields sit at `src/cadrumo/application/operations/error_detail.py:161`. They are worded by `_worded` at `src/cadrumo/application/operations/error_detail.py:248`, and record validation faults by `_record_fault_words` at `src/cadrumo/application/operations/error_detail.py:378`. Typed refusal details reuse `operation_refusal_words` at `src/cadrumo/application/operations/error_detail.py:340`.
- The language comes from `output_language()` at `src/cadrumo/core/i18n/render.py:181` when the detail is built. The runtime result read carries no language.
- The runtime relay releases a terminal refusal's error detail under its own schema when the definition declares no typed refusal detail: `src/cadrumo_runtime/host/session_hold_operations.py:320`.
- The desktop host reads the detail for refused and failed stops: `native/desktop/src-tauri/src/shell/settle.rs:419`.
- The window reads the served sentence through one helper, `native/desktop/frontend/src/shell/ledger.ts:287` (`servedRefusalWords`), and otherwise falls back to its generic notice keys.
- The window may hold no code-to-text map: `dev/quality/tests/test_window_holds_no_tax_data.py`.
