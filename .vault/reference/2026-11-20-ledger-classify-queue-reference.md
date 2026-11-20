---
tags:
  - '#reference'
  - '#ledger-classify-queue'
date: '2026-11-20'
modified: '2026-11-20'
body_schema: 'body-v2'
body_hash: 'sha256:0d7b27e73e6aa1f6878588a25e55379138dae61ddc526f53b48b4ef5bcc2843b'
related: []
---

# `ledger-classify-queue` reference: `ledger classification pipeline, consent, cues and long-running operations`

Traced on head `63a0fe06fa` (branch `nevenincs/ledger-iva-edit`) by read-only readers on 2026-11-20, verifying the facts the LEDGER-CLASSIFY brief traced on tui `3f807380db`.

## Summary

### Request path for one classification

- The "Preguntar al modelo" button is `native/desktop/frontend/src/components/ledger/inspector/ModelSuggestion.tsx:264-312`, mounted at `ClassifySection.tsx:378`. It submits `ledger.classify.review` or `ledger.split.review` (`src/cadrumo/application/ledger/llm_review_contracts.py:28-29`) through `shell/ledgerApply.ts:772-780` and `shell/tauriLedger.ts:25-27` to the host command `native/desktop/src-tauri/src/shell/ledger/mod.rs:498`.
- The host holds the profile serial lock (`shell/user_profile.rs:165-167`, taken at `shell/ledger/mod.rs:395`) through `settle::settle` (`settle.rs:571-611`), at most `SETTLE_LIMIT` 90 s (`relay.rs:14`). The follow waits on `OperationChanged` with a 250 ms to 1 s recheck (`relay.rs:365-396`).
- Composition: `operation_composition_ledger.py:487-512`, `ledger_llm_composition.py:126` and `:209-210` (`TextReader(TextLLMClassifier(...))`, no consent token). `llm_review_execution.py:340` acquires on a thread. `TextLLMClassifier.classify` (`adapters/outbound/llm/text_classifier.py:96-110`) wraps `asyncio.run` per call. Provider AGENT, role TEXT_EXTRACTION, `evidence_derived=True` (`text_classifier.py:127-136`).
- `LLMClient.complete` (`adapters/outbound/llm/client.py:325`) does one role lookup (`:708-738`), the consent check (`:341`, `:576-600`), the cache read (`:343-348`) and one agent background run, with at most one JSON re-ask (`providers/agent.py`).
- Runtime relay: `src/cadrumo_runtime/host/profile_connection_model_runs.py:91-125`. Agent service relay pool of 4 threads: `src/cadrumo_agent_service/host/model_run_relay.py:53-130`. Lane resolution and the service-side consent backstop: `providers/application/model_runs.py:180-203`, `:195-196`.
- One movement per request. The output is a JSON object with `classification`, `confidence` and `reason` (`src/cadrumo/domain/transactions/llm.py:650`, `:699`, parsed at `:797`).

### Model selection

- Every role resolves to the one picked `reading` model (`model_runs.py:235-255`, `local_model_list.py:161-169`). There is no per-task setting. `core/model_roles.py:22` claims otherwise and is stale.
- Background runs accept only `temperature`, `context_tokens` and `response_schema` (`providers/domain/catalog.py:388-393`, honoured at `model_runs.py:268-275`, sent at `adapters/agent_background_runs.py:216-236`). Effort exists only on foreground entries (`catalog.py:362-363`).
- cadrumo-agent's OpenAPI pin is `src/cadrumo_agent_service/_data/agent_api/pin.json`, enforced by `dev/packaging/native/agent_api_pin.py`. The source checkout is a folder, not a SHA (`native/cmake/Agent.cmake:4-10`, `native/CONTRACT.md:1136`).

### Consent

- With an off-host lane, `_require_evidence_consent` raises `LLMConsentError` before dispatch (`client.py:576-600`). The error is not a subclass of `LLMConfigError` or `LLMProviderError` (`adapters/outbound/llm/errors.py:31,88,104`), so `run_reader` (`ledger_llm_composition.py:164-178`) does not catch it.
- The desktop shows the generic `desktop.ledger.inspector.model.unavailable` text (`ModelSuggestion.tsx:161-164`, `:315-331`, `inspectorWords.ts:147-158`). The refusal is not silent, but it is misleading: the consent cause is not rendered.
- The existing mint path is invoice evidence extraction (`application/ledger/invoice_evidence_extract_operation.py:63-80`, `:219-235`, person act only at `~:283-286`). It checks `cloud_evidence_read_permitted` (deployment opt-in `core/config.py:657`, capability `core/capabilities.py:53-67`, gestor bar). `EvidenceConsentLedger` (`adapters/persistence/llm/consent_ledger.py:65`, `:94`) appends before dispatch. `agent_consent_binding` (`consent.py:70-94`) binds provider, transport, model and content address.
- `LedgerLlmReviewRequest` has no acknowledgement field (`llm_review_contracts.py:38-61`).

### Batch asking

- "Pedir para cada" is `SelectionInspector.tsx:459-523`. It is a sequential `for` loop over at most `ASK_EACH_MAX = 20` (`:122`) targets. Truncation is silent, and the reviews are held in component state.

### Long-running operations and storage

- The supervisor lease scope is `(definition_id, subject_ref)` (`application/operations/persistence/leases.py:23-32`). There is no concurrency cap and no deadline (`supervisor_execution.py:516-523`). Cooperative cancel needs a `RECORDED_COOPERATIVE_*` capability (`capabilities.py:336`; `supervisor_settlement.py:37-41`, `:75-107`). PARTIAL effects need the partial variant (`capabilities.py:284`).
- The classify review persists its proposal as a digest-bound checkpoint in `operation_secure_references` (`operations/supervisor_context.py:51-67`, `secure_object_namespaces.py:243-256`). It is resumable from the checkpoint (`ledger/llm_review_operation.py:168-181`), but the namespace is process local.
- Secure namespaces are declared in `adapters/persistence/storage/secure_object_namespaces.py` (example `:638-652`) and registered in `namespace_registry.py:94`.
- The AEAT sync run queue is held in host memory (`shell/aeat_sync/mod.rs:96-120`, `run.rs:18-66`, `:183`). It takes the serial lock only around submit (`mod.rs:244-289`), and stop is cooperative (`run.rs:396-405`). It is lost on restart.

### Host-to-window signals

- The window receives Tauri Channels that carry no payload, one per family, through `*_observe` commands (`shell/aeat_sync/mod.rs:777`, `shell/user_profile.rs:1078`, `shell/user_profile/censo.rs:677`, `shell/ledger/mod.rs:604` for drops only). The only revision-gated push is `console-environment-changed` (`src-tauri/src/agent/console_environment.rs:44-52`).
- `PersonEvent` (`src-tauri/src/agent/person.rs:92-99`) carries `RecordsChanged` and `OperationChanged` from the runtime (`agent/person/native.rs:673-710`). It is consumed only in Rust.
- The ledger page subscribes to no cue. It re-reads only after its own apply (`shell/ledgerWindow.ts:398-485`, `components/ledger/editing/useLedgerApply.ts:304-519`). Some views re-read on focus (`calendar.ts:125-126`, `signIn.ts:575-576`).
- Window contract types are generated from Python by `*_contract.py` and `*-contract.mjs` pairs (for example `scripts/ledger_operation_contract.py`) and checked by `npm run check` (`frontend/package.json:10`). `frontend/src/ipc/contract.ts` is hand written.
- There is no global background-task indicator. The nearest patterns are `components/setup/ProvisioningPanel.tsx:118` and `components/aeatSync/AeatSyncProgress.tsx`.
