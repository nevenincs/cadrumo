---
tags:
  - '#reference'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:46efd2dc0a5e32afc9a9d783eafe1307a2e6b756e6974bcc35d28436dfd1b8c9'
related: []
---

# `mcp-parity` reference: `replay identity`

This record collects the code facts that bear on how a repeated submission is told from a new one. Every locator is relative to the root of this repository, on branch `feature/tui`, read on 2026-10-10 by static analysis with nothing executed; the tree held other sessions' uncommitted work. It states facts only and recommends nothing.

## Summary

- The MCP `execute` tool accepts an idempotency key and nothing requires one. It never generates one (section 1).
- A claim binds definition, subject, key and the exact request. Resolution returns the earlier operation without reading what became of it, and a claim never expires (section 2).
- The journal already holds the lifecycle, terminal condition and effect of every operation, and the runtime already knows at submission whether a request can commit (section 3).
- The command line sets no wire key; `ledger.add` carries its own key in the payload (section 4).

## 1. The MCP tool

- The `execute` tool declares `idempotency_key` as optional (`src/cadrumo_harness/mcp/protocol_contract.py:103-110`).
- `execute` passes the key through unchanged and never generates one (`src/cadrumo_harness/mcp/admitted_operations.py:131-141`).
- A lost or refused submit reply returns `unresolved` with the request id and definition id, and no operation id (`src/cadrumo_harness/mcp/admitted_operations.py:119-124`, `:144-151`).
- The submission receipt carries only the operation id and a secret requirement, so a replay reply looks the same as a fresh admission (`src/cadrumo/application/operations/frontend_requests.py:302-309`; `src/cadrumo_harness/mcp/admitted_operations.py:125`).

## 2. Claims and their resolution

- A claim binds definition id, subject, a digest of the key, the operation id and the request reference; the digest folds definition, subject and key, and neither profile nor session (`src/cadrumo/application/operations/persistence/idempotency.py:13-46`).
- The claim is built whenever the submit carries a key, with no reference to the definition's declared replay policy (`src/cadrumo/application/operations/_supervisor_submission.py:137-146`).
- The request reference is a content address of the payload, and the request is stored before the claim is resolved (`src/cadrumo/application/operations/_supervisor_submission.py:39-41`, `:87-96`; `src/cadrumo/adapters/persistence/operations/secure_references.py:82-94`).
- Resolution scans every journal file under the journal lock and returns the earlier operation id without reading its lifecycle, terminal condition or effect; the claim has no expiry field (`src/cadrumo/adapters/persistence/operations/journal.py:149-153`, `:243-268`, `:282-285`; `src/cadrumo/application/operations/persistence/idempotency.py:18-22`).
- The same key with a different request raises `operation idempotency key is bound to a different request`, which the host reports as `OPERATION_UNAVAILABLE` (`src/cadrumo/adapters/persistence/operations/journal.py:253-264`; `src/cadrumo/entrypoints/runtime/operation_host.py:306-308`).
- A replay does not revive the response capability: it is reserved only when the submitted id equals the proposed id (`src/cadrumo/entrypoints/runtime/operation_host.py:300-305`; `src/cadrumo/application/operations/composition.py:92-97`).
- A second submission of the same definition and subject is refused as busy while the first is unsettled, unless its claim resolves to it; an unstarted holder keeps the subject (`src/cadrumo/application/operations/_supervisor_lease.py:185-230`).
- The operation journal is declared at storage-root scope with an unbounded lifecycle (`src/cadrumo/core/storage_taxonomy_locations.py:44`, `:597-604`; `src/cadrumo/entrypoints/operation_composition.py:2045`, `:2077`).

## 3. What the journal and the runtime already know

- The persisted snapshot records lifecycle, terminal condition and effect beside the claim; effect defaults to `none` (`src/cadrumo/application/operations/persistence/journal.py:83-85`, `:97`; vocabulary at `src/cadrumo/core/operations.py:68-85`).
- Two committing executors record effect `unknown` before their write and `none` after a validation refusal (`src/cadrumo/application/ledger/classify_operation.py:126`, `:140-145`; `src/cadrumo/application/ledger/operator_iva_operation.py:106`, `:122-124`).
- Replay policy has three declared values, and two capability profiles permit an update while declaring `none` (`src/cadrumo/application/operations/capabilities.py:21-26`, `:186-198`, `:277-289`).
- The five ledger write definitions declare idempotent submit and admit only the command line today (`src/cadrumo/application/ledger/add_operation.py:178-179`; `update_operation.py:343-344`; `classify_operation.py:168-169`; `bulk_classify_operation.py:236-237`; `lifecycle_mutation_operation.py:379-380`).
- A test for "this request can commit" already runs at submission: the operation's own access resolution holding the commit action (`src/cadrumo/application/user_profile/operation_access_policy.py:62-79`, `:233-242`).

## 4. The command line, the terminal interface and accepted wording

- The command line's generic submit sets no wire key, and its ledger commands use the profile as subject (`src/cadrumo/entrypoints/cli/runtime_registered_operation.py:134-143`; `runtime_ledger_add.py:176`; `runtime_ledger_lifecycle.py:148`).
- `ledger.add` carries its own key in the payload, and that key names the row (`src/cadrumo/application/ledger/ledger_add_contracts.py:85`; `ledger_add_command.py:106`; `actions_manual.py:1752-1755`). With that payload key, the same content returns the stored row with no event and different content is refused (`src/cadrumo/application/ledger/actions_manual.py:160-184`).
- The terminal interface passes a wire key only when its caller gives one, and a key is refused with typed financial input (`src/cadrumo/entrypoints/tui/operations/runtime_controller.py:244`, `:255-257`, `:267-275`; `src/cadrumo/entrypoints/runtime/profile_connection_operations.py:282-283`).
- The accepted architecture record states "`submit` accepts an idempotency key scoped to the definition and subject; replay returns the existing invocation" (`.vault/adr/2026-08-11-tui-architecture-adr.md:560-561`).

## Not verified

- Whether a profile worker's storage root is bound to one profile at run time. If it is not, claims of two profiles share one journal and are kept apart only by the subject text.
- Whether every committing executor records an effect other than `none` before its first write. Two were read.
- Which terminal condition the supervisor assigns when an executor returns refusal evidence.
- Whether the request id in an `unresolved` reply can find an operation. No lookup by request id was found.
- What `execute` returns for its automatic start after a replayed receipt, and whether a later session can start an operation that was admitted and never started.
- Which commands submit the same definition and subject more than once in one invocation.
