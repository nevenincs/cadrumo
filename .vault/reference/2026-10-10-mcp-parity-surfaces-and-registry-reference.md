---
tags:
  - '#reference'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:e11c1bcc0b83209b1e25bf5055e7b0aebb06b4ffef9f9a1dcfacec5952033709'
related: []
---
# `mcp-parity` reference: `surfaces and registry`

This record describes how the three operator surfaces of Cadrumo reach its work and how the operation registry decides what each surface may use. Every locator is relative to the root of this repository, on branch `feature/tui` at commit `85f84a2680`, read on 2026-10-10 by static analysis with nothing executed; the tree had uncommitted changes by another session. It records how the code works and decides nothing. The per-operation list of closed operations is in `2026-10-10-mcp-parity-closed-operations-reference`, and sign-in and session mechanics are in `2026-10-10-mcp-parity-sign-in-doors-reference`.

## Summary

- The command line, the terminal interface and the MCP server all reach the work through one operation registry. The MCP server names no tax operation: it has 16 fixed tools, and nine of them are a generic envelope over whichever registered operations list the MCP frontend and the caller's grant names.
- The registry is the capability catalogue. Each of 266 definitions states its permitted frontends explicitly. 123 list MCP, 116 of those are reachable, and 143 are closed to MCP.
- The command line has one generic function that submits any registered operation but no command that addresses an operation by id. The MCP envelope can observe, resume and cancel an operation after submission; the command line cannot after its command exits.
- Changing a definition's frontend set changes its contract digest, and a stored invocation pinned to the old digest is refused for observation, result, review and refresh.

## 1. The three surfaces

### 1.1 Command line

- Two roots exist, `config` and `app` (`src/cadrumo/application/operator_surface/models.py:54-58`). The executable is `aeat` (`src/cadrumo/entrypoints/cli/_root_command_specs.py:44-46`).
- The tree has 398 nodes: one root, 70 groups and 327 leaf commands, of which 224 are under `app` and 103 under `config`; four groups are also executable commands. These counts come from static extraction of every spec declaration; the graph was not loaded.
- The tree is declared as data. `CommandSpec` is a frozen dataclass with key, parent key, token, kind, invocation, parameters, execution policy, a lazily bound handler and a result schema (`src/cadrumo/entrypoints/cli/command_spec.py:115-138`). The graph mounts 15 spec families (`src/cadrumo/entrypoints/cli/command_specs.py:14-33`).
- One generic function submits a registered operation: `run_registered_operation` (`src/cadrumo/entrypoints/cli/runtime_registered_operation.py:80-95`). It has 144 call sites in non-test CLI code, plus 17 through `submit_profile_operation`. Each call site hard-wires its own request model, definition id and result type. No `*command_specs.py` file contains `definition_id`, so no command addresses an operation by id.
- There is no CLI verb to list, describe, observe, resume or cancel an operation. Non-test CLI code contains no `operation_resume` message and no cancellation request. Observe, result, review, response and detach run inside the one command invocation. A command waits at most 3600 s for settlement (`src/cadrumo/entrypoints/cli/registered_operation_deadlines.py:13`), and on timeout reports the operation as still running with its identity and unknown effect (`src/cadrumo/entrypoints/cli/runtime_registered_operation.py:96-104`).
- 272 command keys (269 leaves and 3 executable groups) open a runtime profile client at dispatch (`src/cadrumo/entrypoints/cli/_profile_authentication_gate.py:45-320`, used at `:647`). By the audit's import-graph heuristic, 250 leaves reach a registered operation through the generic function, 33 use the runtime outside the registry and 44 run in process or locally.
- A machine-readable command-surface manifest exists: `aeat --cadrumo-command-surface` is handled before any other work (`src/cadrumo/entrypoints/cli/main.py:147-149`) and emits commands with input schemas, result schemas and execution policy (`:310-332`). Its docstring says the retained harness invokes the installed `aeat` executable and consumes it (`:311-317`). Nothing under `src/cadrumo_harness` references `command_surface`, `cli_argv_for` or `verb_input_schema`. A command is listed as exposable when its parent is not the root, a handler is bound and it is a leaf or invokes without a command (`src/cadrumo/entrypoints/cli/verb_input_schema.py:45-54`).
- Every runtime client the command line opens declares the CLI frontend: `src/cadrumo/entrypoints/cli/runtime_profile_admission.py:172,205,233`, `src/cadrumo/entrypoints/cli/config/custody.py:195,309,352`, `src/cadrumo/entrypoints/cli/config/passphrase.py:77`, `src/cadrumo/entrypoints/cli/config/runtime_automation_request.py:125,201`. The bound client is refused unless its frontend is the CLI (`src/cadrumo/entrypoints/cli/runtime_profile_binding.py:109-112,137-144`). Non-test CLI code names neither the TUI nor the MCP frontend.

### 1.2 Terminal interface

- It pins the TUI frontend: it opens clients with `OperationFrontendProjection.TUI` (`src/cadrumo/entrypoints/tui/installed_session.py:98,109,156`), and its workbench root refuses any other (`src/cadrumo/entrypoints/tui/runtime_workbench.py:197-198`).
- It submits the same registered operations. The generic controller fetches the contract first and refuses a definition that requires an ephemeral secret (`src/cadrumo/entrypoints/tui/operations/runtime_controller.py:170-189`). Secrets travel only through bespoke doors that call `submit_secret`, which accepts only the CLI and TUI frontends (`src/cadrumo/adapters/local_runtime/frontend_client.py:310-316`).
- It observes by polling. The operation modal loops on `observe` at a 200 ms interval (`src/cadrumo/entrypoints/tui/operations/modal.py:63,188-194`). Non-test TUI code contains no `operation_resume` message.
- Its screens read from one registered read, `workbench.generation` (`src/cadrumo/application/workbench_generation_operation.py:42`), captured by the workbench root (`src/cadrumo/entrypoints/tui/runtime_workbench.py:216-235`).
- Screens unwired in production:
  - The ledger screen factory accepts classification, link and exclusion submitters, record doors and a refresh door (`src/cadrumo/entrypoints/tui/ledger/routes.py:145-162`), and production passes none of them (`src/cadrumo/entrypoints/tui/runtime_workbench.py:280-291`).
  - Invoice-book import is refused; only bank statements are accepted (`src/cadrumo/entrypoints/tui/runtime_ledger_import.py:142-145`).
  - The `workbench.withholding` destination is hard-coded unavailable (`src/cadrumo/entrypoints/tui/runtime_workbench.py:246-250`).
  - The AEAT synchronization screen factory has a notification-document handoff parameter (`src/cadrumo/entrypoints/tui/aeat_sync/routes.py:84-91`) that production does not pass (`src/cadrumo/entrypoints/tui/runtime_workbench.py:315-320`).
  - `TuiActionCandidateV1` is defined (`src/cadrumo/entrypoints/tui/navigation.py:189`) and non-test code never constructs it, so Home next-action rows and palette action entries cannot navigate.

### 1.3 MCP server

- The transport is stdio only (`src/cadrumo_harness/mcp/server.py:49,59`), and the server registers only a tool-list handler and a tool-call handler (`:43`). It advertises tools only.
- The catalogue is static: 16 tools hand-written in `src/cadrumo_harness/mcp/protocol_contract.py:52-128`. The list handler returns it unconditionally, with no admission check (`src/cadrumo_harness/mcp/server.py:27-33`). Each tool advertises only a name, description and input schema (`:30`); a result is JSON text plus the same dict as structured content, with the error flag set by `has_refusal` (`:35-41`).
- Five tools are the connection and authorization journey: `status`, `authorization_prepare`, `authorization_request`, `authorization_poll`, `authenticate` (`src/cadrumo_harness/mcp/protocol_contract.py:53-65`). Their mechanics are in `2026-10-10-mcp-parity-sign-in-doors-reference`.
- Two tools are public reference reads, dispatched before any admission check (`src/cadrumo_harness/mcp/runtime_adapter.py:202-205`) and needing no grant and no runtime:
  - `authority` takes one of seven queries (`modelos`, `support`, `describe`, `casillas`, `casilla`, `formulas`, `bindings`) with a fixed set of allowed and required coordinates (`src/cadrumo_harness/mcp/authority_query.py:21-41`), under one pinned publication of the bundled authority (`:98-106`).
  - `corpus_search` takes a query and a limit of 1 to 50, default 8 (`src/cadrumo_harness/mcp/protocol_contract.py:79-84`, `src/cadrumo_harness/mcp/corpus_query.py:13,24`), over bundled normative text and approved terminology (`src/cadrumo_harness/mcp/corpus_query.py:16-35`). On first use it builds a lexical index file in the application cache under an exclusive file lock (`src/cadrumo/application/corpus_search/runtime.py:79-103`).
- Nine tools are a generic envelope. All of them need an admitted client (`src/cadrumo_harness/mcp/runtime_adapter.py:182-185`) and run under one deadline of 30 s computed once per call (`src/cadrumo_harness/mcp/admitted_operations.py:43,64`). All calls on a connection are serialized by one lock (`src/cadrumo_harness/mcp/runtime_adapter.py:191`).

| tool | what it sends to the runtime | locator |
|---|---|---|
| `search` | one contract request per definition id in the session's granted scope, skipping ids refused as `frontend_denied` or `operation_denied`, ranked lexically; takes only an optional query, no paging | `src/cadrumo_harness/mcp/admitted_operations.py:83-95` |
| `describe` | one contract request; the reply is the public contract plus the request JSON Schema, the only place an input schema is available | `src/cadrumo_harness/mcp/admitted_operations.py:98-102` |
| `execute` | a contract request first, then one submit message with definition id, subject reference, payload JSON and optional caller-supplied idempotency key, then an `operation_start` control unless `start` is false or the receipt carries a secret requirement | `src/cadrumo_harness/mcp/admitted_operations.py:105-135` |
| `observe` | an observe message carrying an observation request | `src/cadrumo_harness/mcp/admitted_operations.py:168-179` |
| `result` | result-page requests until the whole settled document is collected | `src/cadrumo_harness/mcp/admitted_operations.py:182-184` |
| `result_page` | one result-page request | `src/cadrumo_harness/mcp/admitted_operations.py:187-193` |
| `review` | a review-projection request | `src/cadrumo_harness/mcp/admitted_operations.py:196-207` |
| `respond` | a manage message holding an inspect, apply or reject request; the server sets the actor to `session:<session id>` | `src/cadrumo_harness/mcp/admitted_operations.py:210-245` |
| `control` | start or resume as a control message; cancel or detach as a manage message that requires `expected_revision` (start and resume forbid it) | `src/cadrumo_harness/mcp/admitted_operations.py:248-290` |

- `execute` outcomes are `submitted`, `unresolved` (the submit round trip died, so the effect is uncertain) or `refused` (`src/cadrumo_harness/mcp/admitted_operations.py:109-122,138-145`). A lost start reply keeps the durable receipt (`:163-165`).
- The adapter builds only the inline submit message (`src/cadrumo_harness/mcp/admitted_operations.py:125-135`). The transport streams a submit message in 16 KiB chunks when its frame exceeds the frame limit (`src/cadrumo/adapters/local_runtime/runtime_operation_transport.py:58-64,84-122`; chunk size `src/cadrumo/application/runtime/submission_payload.py:14`), so large payloads reach the runtime without a tool for it. The financial-operand message and the workspace-refresh request have no MCP tool: the adapter imports neither (`src/cadrumo_harness/mcp/admitted_operations.py:13-34`).
- Secret submission is refused unless the frontend is the CLI or TUI, on the client (`src/cadrumo/adapters/local_runtime/frontend_client.py:315-316`) and again in the runtime (`src/cadrumo/entrypoints/runtime/profile_connection_operations.py:89-90`). MCP has no secret tool.

## 2. The operation registry as the capability catalogue

### 2.1 What a definition carries

- `OperationDefinition` is a frozen model with definition id, request and result types, executor factory, phase codes, interaction kinds, capabilities, reconciliation policy, permitted frontends, optional action reference, optional ephemeral secret, optional transient financial operand, refusal detail codes and an opt-in public error detail flag (`src/cadrumo/application/operations/operation_definition.py:56-78`).
- `OperationCapabilities` carries durability, cancellation, deadline, replay, baseline, request storage, sensitive input, conflict scope, owned resources, permitted effects and close policy (`src/cadrumo/application/operations/capabilities.py:65-80`). Mutability is therefore not one field: it is the permitted effects plus whether the access resolver adds the commit action (`src/cadrumo/application/operations/access_resolution.py:102`).
- The public contract copies these fields and adds the schema identities and the contract digest (`src/cadrumo/application/operations/registry.py:80-110`). A registration binds live schemas and may carry an access resolver, which defaults to none (`:378`). The registry holds sorted unique ids and, when it has registrations, requires them to cover the definitions exactly (`:513-546`).
- REVIEW is declared by `export.google-review` (`src/cadrumo/application/export/google_review_operation.py:160`), `config.google.login` when consent applies (`src/cadrumo/application/user_profile/google_configuration_operation.py:126`), `ledger.classify.review` and `ledger.split.review` (`src/cadrumo/application/ledger/llm_review_operation.py:151`) and `user-profile.censo-review` (`src/cadrumo/application/user_profile/censal_operation.py:753`). INPUT is declared only by `modelo.edit.apply` (`src/cadrumo/application/modelo/operation_definitions.py:1713`). A search for `OperationInteractionKind.CHOICE` in `src/cadrumo/application` found no declaration.

### 2.2 Permitted frontends

- The set is required and non-empty on every definition (`src/cadrumo/application/operations/operation_definition.py:69`). The one-phase builder takes it as a required keyword with no default (`:173-208`).
- There are three frontends, `CLI`, `MCP` and `TUI` (`src/cadrumo/application/operations/registry.py:189-194`). `ALL_OPERATION_FRONTENDS` names all three explicitly, so a new frontend is never granted silently (`:197-201`).
- The set is an allow-list per definition. It is copied into the public contract (`src/cadrumo/application/operations/_registry_contracts.py:366`) and is part of the digest material (`:313`).

The frontend list is enforced in these places:

| place | what it does | locator |
|---|---|---|
| runtime describe | checks the session's granted operations (`operation_denied`), then the frontend (`frontend_denied`) | `src/cadrumo/entrypoints/runtime/profile_connection_operations.py:237-242` |
| runtime payload upload | repeats the frontend check | `src/cadrumo/entrypoints/runtime/profile_connection_operations.py:262-264` |
| access evaluation | after the human gate, refuses a request whose frontend is not in the contract | `src/cadrumo/application/user_profile/operation_access_policy.py:159-179` |
| resolver helper | refuses a frontend, then an action, the operation does not declare | `src/cadrumo/application/operations/access_resolution.py:160-170` |
| definition-specific resolvers | for example the MCP-only definitions refuse any other frontend | `src/cadrumo/application/modelo/mcp_query_operation.py:225-227` |
| MCP client | rejects a contract that does not list MCP | `src/cadrumo/adapters/local_runtime/frontend_operation_client.py:121` |
| CLI admission | requires the CLI frontend in the contract | `src/cadrumo/entrypoints/cli/registered_operation_admission.py:36-43` |
| TUI filters | keep only contracts listing the TUI | `src/cadrumo/application/aeat_sync/workspace_reader.py:280`, `src/cadrumo/application/aeat_sync/_workspace_projection.py:308`, `src/cadrumo/entrypoints/tui/aeat_sync/runtime_handoff.py:85`, `src/cadrumo/entrypoints/tui/aeat_sync/controller.py:82`, `src/cadrumo/entrypoints/tui/secret/automation_requester_setup.py:42,55` |
| secret door | accepts only the CLI and TUI frontends | `src/cadrumo/adapters/local_runtime/frontend_client.py:315-316`, `src/cadrumo/entrypoints/runtime/profile_connection_operations.py:89-90` |

### 2.3 Access resolver and human gate

- A resolver turns a request into an access request and an access policy (`src/cadrumo/application/operations/access_port.py:14-22`). `resolve_operation_access` looks up the definition and registration and calls the resolver (`src/cadrumo/application/operations/access_resolution.py:512-520`). A definition registered without a resolver, or with a request or contract that does not match, is refused as `operation_unavailable` (`:484-491`).
- The policy carries allowed actions, disclosures, periods and `requires_human` (`src/cadrumo/application/user_profile/access_contracts.py:374-394`). Actions are submit, start, resume, observe, result, review, respond, cancel, detach and commit; a scope is explicit allow sets with no operation wildcard (`:45-57,78-93`).
- The human gate refuses a policy with `requires_human` for any session whose kind is not human, with `human_authority_required` (`src/cadrumo/application/user_profile/operation_access_policy.py:175-176`). Session kinds are human, attended and api key (`src/cadrumo/application/user_profile/access_contracts.py:152-157`). MCP admission requires a live automation grant (`src/cadrumo_harness/mcp/runtime_admission.py:49-52`).

### 2.4 Contract digest and stored invocations

- The digest is derived over the identity, schema and policy values, and the policy values include the permitted frontends (`src/cadrumo/application/operations/_registry_contracts.py:248-260,297-319`). The contract validates that its digest reproduces (`src/cadrumo/application/operations/registry.py:112-122`).
- A stored invocation records the digest it was submitted under. When the current contract's digest differs:
  - observation refuses with a definition-contract mismatch (`src/cadrumo/application/operations/observation.py:166-172`);
  - a result request is refused with `DEFINITION_CONTRACT_MISMATCH` (`src/cadrumo/application/operations/_projection_read.py:467-475`);
  - a workspace refresh target is refused the same way (`:324-332`);
  - a review fails its currency check unless both the stored and the requested digest equal the current one (`:153-161`).
- The accepted tui-architecture decision (status `accepted`) says a breaking definition cutover must first prove zero affected nonterminal invocations, may not rewrite only a stored digest, and that a current-shape invocation whose digest no longer matches refuses acquisition and enters normal reconciliation (`.vault/adr/2026-08-11-tui-architecture-adr.md:568-576`).
- A review reference and a result request both carry the digest (`src/cadrumo/application/operations/frontend_projection.py:67-77`, `src/cadrumo/application/operations/frontend_requests.py:418-433`), so a client holding either must refetch the contract after a change.

## 3. The numbers and their derivation

- There is one production composition function, `build_production_operation_registry` (`src/cadrumo/entrypoints/operation_composition.py:996`). It builds the definitions tuple (`:1550-1750`), sorts it by definition id (`:1748`), builds and sorts the registrations (`:1751-1984`) and constructs the registry (`:1985`). Outside tests, `OperationRegistry(` is called only there.
- The definitions tuple holds 194 entries on 194 lines (`:1553-1746`): 174 single definitions and 20 splat groups. The 20 groups and their sizes, as the audit read them from their builders, are `resolved_auth_definitions` 5, `review_read_definitions` 2, `evidence_followup_definitions` 5, `evidence_ingestion_definitions` 1, `google_configuration_definitions` 6, `certificate_secret_definitions` 2, `prorrata_mutation_definitions` 7, `apoderado_definitions` 4, `borrador_100_definitions` 3, `m036_definitions` 3, `modelo_audit_definitions` 3, `modelo_spreadsheet_definitions` 1, `review_package_exchange_definitions` 6, `profile_archive_definitions` 3, `profile_definitions` 10, `automation_definitions` 7, `m145_communication_definitions` 5, `modelo_definitions` 8, `overview_definitions` 6, `workbench_definitions` 5. They total 92, and 174 plus 92 is 266.
- An earlier count of 264 missed two ids of the Modelo 145 family, which has five (`src/cadrumo/application/modelo/m145_communication_contracts.py:35-39`).

| frontends declared | meaning | definitions |
|---|---|---|
| CTM | CLI, TUI and MCP | 119 |
| CT | CLI and TUI | 72 |
| C | CLI only | 71 |
| CM | CLI and MCP | 1 (`modelo.audit.query`, `src/cadrumo/application/modelo/audit_operation.py:76,549`) |
| M | MCP only | 3 (`modelo.bindings.resolve.typed`, `modelo.readiness.summary` at `src/cadrumo/application/modelo/mcp_query_operation.py:205,218`; `modelo.history.timeline` at `src/cadrumo/application/modelo/history_timeline_operation.py:147`) |

- 123 definitions list MCP (119 + 1 + 3). 143 do not: 72 closed to MCP that the command line and terminal interface share, and 71 command line only.
- 116 of the 123 are reachable, because seven cannot run:
  - Four automation proposal definitions (`user-profile.automation-request`, `-rotate`, `-renew`, `-scope`) list all three frontends but register no resolver. Only inventory, approve and decline are human definitions, and only those get one (`src/cadrumo/application/user_profile/automation_operations.py:77-83,413-417,450`).
  - `export.google-sheets` lists all frontends (`src/cadrumo/application/export/google_operation.py:556`) and is registered without a resolver (`:574-591`).
  - `local-reader.provision` lists all frontends (`src/cadrumo/application/local_reader_operation.py:111`) and is registered without a resolver (`:116-132`).
  - `user-profile.bundle-export` has a resolver but declares an ephemeral secret (`src/cadrumo/application/user_profile/operations.py:149,226`), and an MCP client cannot submit a secret.

## 4. Gap classes used by the audit

The audit classified each of the 266 operations; one operation can carry more than one class, so the tallies do not sum to 266.

| class | meaning | operations |
|---|---|---|
| G0 | reachable through MCP today: lists MCP, has an access resolver, needs no secret, financial operand or human session | 116 |
| G1 | closed only by the frontend list, with no reason stated in code and nothing enforced outside the operation | 65 |
| G2 | as G1, but a confirmation or gate lives in the CLI handler or TUI screen rather than in the operation | 23 |
| G3 | takes or writes a host file path, or needs document bytes | 34 (25 closed, 9 already open to MCP) |
| G4 | closed to automation by stated design (a human requirement, a human-only statement in code, a secret only the CLI or TUI may send, anything that grants or widens access) | 48 |
| G5 | the runtime supports it and the MCP adapter has no tool or wiring | 2 (`modelo.edit.apply`, `modelo.edit.preflight`, which need the financial-operand message) |
| G6 | a CLI or TUI capability implemented in process with no registered operation | about 42 capability rows, not reducible to one figure because the matrices overlap |
| G7 | local machine, installation or terminal administration | 3 |
| G8 | declared but not usable | 7 (the six without a resolver and `user-profile.bundle-export`) |

- The audit's definition of G5 also names chunked payload upload; the MCP adapter does use it implicitly (section 1.3), so no operation is counted under G5 for it.
- Tallies were reconciled by id across three merged matrices (ledger 92 rows, modelo and filing 120, profile and platform 79; union 266 after removing overlaps).

## 5. Agent-facing sibling definitions

Next to a human definition the registry carries a separate, narrower definition for agents. These are the established examples; each sibling is a read.

| human definition (frontends) | agent sibling (frontends) | what the sibling withholds or narrows |
|---|---|---|
| `modelo.readiness` (CT) | `modelo.readiness.summary` (M) | publishes only closed result fields whose disclosure was authorized for the MCP destination; the human prose stays in worker memory (`src/cadrumo/application/modelo/mcp_query_operation.py:1-6,52-59`) |
| `modelo.bindings.resolve` (CT) | `modelo.bindings.resolve.typed` (M) | validates caller values against the same pinned declaration (`src/cadrumo/application/modelo/mcp_query_operation.py:3-6`); which result fields differ is not established |
| `modelo.history` (CT) | `modelo.history.timeline` (M) | events carry only id, kind and instant, with actor and details kept in custody, and the disclosure category is forced to operation metadata (`src/cadrumo/application/modelo/history_timeline_operation.py:46-70,170-187`) |
| `modelo.audit.read` (C) | `modelo.audit.query` (CM) | frontend sets at `src/cadrumo/application/modelo/audit_operation.py:75-76,493,548-549`; the withheld fields are not established |
| `modelo.036.read` (CT) | `modelo.036.query` (CTM) | frontend sets at `src/cadrumo/application/modelo/m036_operation.py:425,476-477`; the withheld fields are not established |
| `live.borrador.100.read` (CT) | `live.borrador.100.query` (CTM) | frontend sets at `src/cadrumo/application/live/borrador_100_operation.py:419-424`; the withheld fields are not established |

- The two MCP-only readiness and binding siblings refuse any other frontend in their resolver (`src/cadrumo/application/modelo/mcp_query_operation.py:225-227`).
- No existing sibling narrows a mutating lifecycle operation.

## 6. Shapes any client must handle

| shape | limit or rule | locator |
|---|---|---|
| per-call deadline on the MCP envelope | 30 s shared by every round trip of one call; `result` has its own 60 s default and the smaller applies | `src/cadrumo_harness/mcp/admitted_operations.py:43,64`, `src/cadrumo/adapters/local_runtime/frontend_operation_client.py:169-181` |
| submit payload | JSON text of 2 to 16,777,216 characters; idempotency key 1 to 256 characters, never generated by the MCP server | `src/cadrumo/application/runtime/operation_access.py:61-68`, `src/cadrumo/application/runtime/submission_payload.py:15`, `src/cadrumo_harness/mcp/admitted_operations.py:134` |
| observation request | `after_cursor` at least 0 and `page_limit` 1 to 1000 | `src/cadrumo/application/operations/frontend_requests.py:173-181`, `src/cadrumo/application/operations/event_replay.py:7`, `src/cadrumo/application/operations/persistence/replay.py:16` |
| observation reply | a public projection with revision, lifecycle, terminal condition, definition contract, pending interaction and result references, plus an event page | `src/cadrumo/application/operations/frontend_projection.py:138-171`, `src/cadrumo/application/operations/frontend_requests.py:650-658` |
| settled-result request | four coordinates: `operation_id`, `terminal_revision`, `definition_contract_digest` and the result schema identity; the caller never supplies the private result reference | `src/cadrumo/application/operations/frontend_requests.py:418-433` |
| result paging | pages of 32,768 raw bytes, document ceiling 16,777,216 bytes (at most 512 pages); an offset above 0 requires the document digest | `src/cadrumo/application/runtime/projection_pages.py:19-20,23-34` |
| result collection | `result` re-checks consent on every page, verifies length, digest and canonical JSON, and discards a partial document on any refusal or change; `result_page` returns one page | `src/cadrumo/adapters/local_runtime/frontend_operation_client.py:130-219` |
| review request | a reference taken from a `review_available` pending interaction: operation, interaction, revision, review schema, contract digest and expiry; it excludes every response credential | `src/cadrumo/application/operations/frontend_projection.py:67-114`, `src/cadrumo/application/operations/frontend_requests.py:184-189` |
| unsupported interactions | INPUT and CHOICE interactions appear as an unsupported marker | `src/cadrumo/application/operations/frontend_projection.py:117-135` |
| response | apply and reject carry operation, interaction, revision, actor and time, plus a reason code for reject, and no response body | `src/cadrumo_harness/mcp/admitted_operations.py:228-245` |
| cancel and detach | `expected_revision` is mandatory; start and resume refuse it | `src/cadrumo_harness/mcp/admitted_operations.py:258-290` |

- A review response is bound to the submitting session. The runtime refuses a response control unless the actor is `session:<session id>`, a stored submission exists for the same session and the original in-memory response capability is held (`src/cadrumo/entrypoints/runtime/operation_host.py:526-532`). Its comment says a new session, an idempotent receipt or a reattached operation cannot obtain the capability (`:540-541`).
- The MCP `respond` tool builds the actor from the admitted client's session id (`src/cadrumo_harness/mcp/admitted_operations.py:233`).
- There is no blocking wait, progress notification or push in the MCP envelope: a client submits, then polls `observe`, then reads `result`.

## 7. Capabilities with no registered operation

- 58 command-line leaves bind no runtime client at dispatch: the 327 leaves less the 269 in the runtime key set, with `app modelo work report-verify` and `config profile censo import` conditional on flags (`src/cadrumo/entrypoints/cli/_profile_authentication_gate.py:641-647`). By family:
  - `config provision` 11, `config storage` 5, `config reset` 3, `config repair` leaves 6;
  - `config passphrase change` and `reset`, `config login`, `config logout`, `config sign-in-status`;
  - `config profile` create, delete, list, resume, archive import, archive inspect, recovery enable, recovery disable and automation create;
  - `config auth providers` and `config auth apoderado scopes list`;
  - six `app modelo` bundled-registry reads (`list`, `describe`, `casilla`, `casillas`, `formulas`, `support-matrix`);
  - three `app modelo review-package` verify verbs, `app modelo m360 declare`, `list` and `remove`, `app ledger categories`, `app live portals list` and `view`, and `app tui`.
- The bootstrap-exemption registry records why some are profile-free: bundled catalogues (`src/cadrumo/entrypoints/cli/_bootstrap_exempt.py:255-262`) and operator-supplied artefacts, which includes the review-package verifiers meant for third-party reviewers (`:315-337`). Eight of the 58 open their own runtime client or run a bootstrap flow; the rest are in process or local, by the audit's heuristic.
- Six command-line reference reads overlap the MCP `authority` tool, and the overlap is partial:

| CLI command | `authority` query | coverage | difference |
|---|---|---|---|
| `modelo list` | `modelos` | partial | the CLI takes a domain filter (`src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py:180-182`); `authority` accepts only `filing_year` (`src/cadrumo_harness/mcp/authority_query.py:22`) |
| `modelo describe` | `describe` | partial | the CLI accepts year and period omitted and refuses ceded autonomic modelos 600, 620, 650 and 660 (`src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py:106-122,203-220`); `authority` requires year and period and always uses the scoped form (`src/cadrumo_harness/mcp/authority_query.py:25,69-74`) |
| `modelo casillas` | `casillas` | partial | the CLI filters by input kind, required, form number and casilla number (`src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py:282-305`); `authority` passes none (`src/cadrumo_harness/mcp/authority_query.py:75-78`) |
| `modelo casilla` | `casilla` | full when year and period are given | the CLI allows the unscoped form (`src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py:324-349`) |
| `modelo formulas` | `formulas` | full when year and period are given | the CLI allows the unscoped form (`src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py:613-633`) |
| `modelo support-matrix` | `support` | full | both call the same registry function (`src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py:661-662`, `src/cadrumo_harness/mcp/authority_query.py:60-61`) |

- `authority` also has a `bindings` query with no command-line reference counterpart; the profile-bound `modelo.bindings.list` operation is the nearest. The portal registry commands read a separate bundled registry and have no `authority` counterpart (`src/cadrumo/entrypoints/cli/_app_live_portals_cli.py:88-89,125-126`). `corpus_search` has no counterpart among the command rows the audit examined.

## Boundary facts

- `AeatAccessGate.require_live_write` always raises (`src/cadrumo/core/access_gate/gate.py:96-107`). Its only production call site is command-line dispatch (`src/cadrumo/entrypoints/cli/_command_runtime.py:331-346`), which applies it to a command whose policy declares a live write; no command in `src/cadrumo/entrypoints/cli` sets `live_write=True`.
- A tool call does not pass through that gate. On the tool path the boundary holds because no registered operation submits anything. Read-only captures from AEAT (`live.*` operations) are a different thing, and `modelo.work.file` writes a local record and submits nothing.

## Not verified

- The leaf, group and node counts of the command tree (327, 70, 398), the 250, 33 and 44 route split, and the family breakdown of the 58 unbound leaves come from the audit's static extraction and import-graph heuristics. I re-confirmed only the 272-key runtime set, the 144 call sites and the absence of `definition_id` in the spec files.
- The sizes of the 20 composition groups are the audit's reading of their builders. I confirmed the 194 entries, the 174 and 20 split and the five Modelo 145 ids, not each group size.
- The frontend tallies CTM 119, CT 72 and C 71 were not recomputed; I confirmed the CM and M members and that the tallies sum to 266.
- That none of the 123 MCP-listing definitions sets `requires_human` is the audit's reading and was not re-checked here.
- Shared capability profiles on definitions named list or status may permit updates, so declared effects do not prove a definition is read-only; this is the audit's reading and was not traced to executors.
- Subject references have per-definition forms (a profile-prefixed id for most, a work-unit id, a run id, and a bare profile id for `user-profile.censo-review`); this comes from the audit and was not confirmed here.
- That no command-line command submits an agent sibling, that all six siblings are reads, and the fields the audit, 036 and borrador siblings withhold, were not established.
- TUI revision and filing-history row open being unwired, and the TUI's push channel being limited to session retirement and lifecycle notices, are the audit's reading.
- Whether a grant can be proposed for a definition that does not list MCP is not covered.
