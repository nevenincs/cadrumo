---
tags:
  - '#research'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-10'
body_schema: 'body-v2'
body_hash: 'sha256:f86e3983d712d760ac33d454a33e87d4a8c76013fef41ba3bf244152697f9289'
related: []
---
# `mcp-parity` research: `parity mechanism options`

The question is by what mechanism Cadrumo's MCP server should become a full interface for the tax operations that its command line (`aeat`) and terminal interface already implement. Four mechanisms were weighed: one native MCP tool per operation, a generic "run a command" tool over the command line's manifest, targeted command-line calls for specific capabilities, and the operation registry behind the existing generic tools. Every locator below is relative to the root of this repository, on branch `feature/tui` at commit `85f84a2680`, read on 2026-10-10 by static analysis with nothing executed; the tree had uncommitted changes by another session. A locator starting with `.vault/adr/` is a Cadrumo decision record and is quoted with its status token.

Records named `2026-10-10-cadrumo-integration-...` belong to the vault of the cadrumo-agent repository, a separate project that drives this application through its MCP server; they are cited by name and are not in this vault.

The evidence favours the registry behind the existing generic tools, and two independent reviews could not break that choice. What they broke was the authority model that had been attached to it: writes on a grant alone, a replay key derived from the payload, "parity by default", a launch-time "read-only" profile, and lease refresh treated as a detail. The owner has since ruled that the MCP server resumes the shared sign-in, which changes the session the work runs as and so the premises of several arguments. Four code-mechanics Reference records carry the detail this record does not repeat: `2026-10-10-mcp-parity-surfaces-and-registry-reference`, `2026-10-10-mcp-parity-sign-in-doors-reference`, `2026-10-10-mcp-parity-admitted-surface-defects-reference` and `2026-10-10-mcp-parity-closed-operations-reference`. The numbers used throughout come from them: 266 registered operations, 123 listing the MCP frontend, 116 reachable through it, 143 closed to it (72 command line plus terminal interface, 71 command line only).

## Findings

### The four options, compared at one level

Five facts in the code decide the verdicts.

- The command line has a built, tested manifest nobody consumes. `aeat --cadrumo-command-surface` is handled before anything else (`src/cadrumo/entrypoints/cli/main.py:147-149`), and its emitter names the retained harness as the intended reader (`src/cadrumo/entrypoints/cli/main.py:310-318`). The manifest is built from `is_exposable_command_spec` (`src/cadrumo/entrypoints/cli/verb_input_schema.py:37-54`) and `build_verb_input_schemas` (`src/cadrumo/entrypoints/cli/verb_input_schema.py:83`), with an argv encoder `cli_argv_for` (`src/cadrumo/application/operator_surface/command_ports.py:366-376`). A search of `src/cadrumo_harness` for the flag, the encoder and the schema type returns no match. The only reader is a test (`src/cadrumo/entrypoints/cli/tests/test_command_surface_beside_retired_state.py:72`). A static count of the declarations gives 330 exposable commands (326 leaves and 4 executable groups); no run was needed.
- The command line has one generic submit function and no generic command. `run_registered_operation` (`src/cadrumo/entrypoints/cli/runtime_registered_operation.py:80-104`) is called from 144 hand-written sites in 115 non-test modules, plus 17 calls through `submit_profile_operation`; each site hard-wires its own request model, definition id and result type. No command-spec file under `src/cadrumo/entrypoints/cli` mentions a `definition_id`, so no command addresses an operation by id and no table maps a command to the operations it submits.
- A command-line call presents as the command-line frontend. The client is opened with `frontend=OperationFrontendProjection.CLI` (`src/cadrumo/entrypoints/cli/runtime_profile_admission.py:229-236`). Each operation lists the frontends it admits, explicitly and with no default (`src/cadrumo/application/operations/registry.py:189-201`), and the access check refuses a non-listed frontend (`src/cadrumo/application/user_profile/operation_access_policy.py:175-178`).
- The MCP tool list is a static tuple of 16 names with no admission check: `status`, the four authorization tools, `authority`, `corpus_search`, and nine generic tools `search`, `describe`, `execute`, `observe`, `result`, `result_page`, `review`, `respond`, `control` (`src/cadrumo_harness/mcp/protocol_contract.py:52-128`, served at `src/cadrumo_harness/mcp/server.py:27-33`). `execute` takes `definition_id`, `subject_ref`, `payload` and an optional `idempotency_key` (`src/cadrumo_harness/mcp/protocol_contract.py:92-97`).
- An earlier MCP package that drove the command line existed on `main` (commit `813a607ed5`, with files such as `src/cadrumo_harness/mcp/_cli_executable.py` and `_elicitation.py`). This branch deletes it: 104 files changed, 4315 insertions and 17686 deletions under `src/cadrumo_harness/mcp` against `main`.

Option A, one native tool per operation. It would be built on the registry's contracts, generating a tool and its input schema for each admitted definition. Its strongest case is that the model sees each schema in `tools/list` without a `search` then `describe` round trip, and that tools can carry read-only and destructive annotations, which is the hook a consuming agent's permission gate keys on. Accepted records leave it open: the refoundation record chose "domain-grouped toolsets with a meta-tool fallback" and rejected "meta-tools only" as the sole architecture because it "weakens annotation-driven client confirmation for the common path" (`.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:125-127`, status `accepted`), the progressive-discovery record rejected a meta-tools-only default for the same reason (`.vault/adr/2026-07-08-mcp-progressive-discovery-adr.md:79-91`, status `accepted`), and the purpose record allows "optional domain-tool projections" that "enforce the same registered contracts" (`.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:157`, status `accepted`). The costs are that the list would change with every operation (116 reachable today, more after parity), that a list answerable before any session would advertise tools the caller's grant does not permit, that the lifecycle still needs `observe` and `result` so only one `describe` is saved, and that it rebuilds the second catalogue this branch deleted.

Option B, a generic command tool over the manifest. It would be built on the manifest, the argv encoder, the `--format json` envelope and the per-command execution policy. Its strongest case is breadth at the lowest cost: every command is already typed, the packaged skills name `aeat` verbs and no operation ids (section 4), and it reaches what the registry route cannot without new work, namely in-process commands, safeguards that live in command handlers, and multi-submit orchestration. The blocks are these.
- Authority: every call presents as the command-line frontend (`src/cadrumo/entrypoints/cli/runtime_profile_admission.py:229-236`), so the per-operation frontend list stops meaning anything for that call.
- Records: the purpose record lists "Independent privileged CLI subprocess wrappers" as rejected (`.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:39`) and orders the displaced "CLI-wrapper execution path" deleted (`:163`); it also says "MCP never reconstructs application verdicts from localized CLI text" (`:159`). Choosing B reverses a rejected option, so it would need a superseding record, not an amendment.
- Lifecycle: the command waits for settlement up to a ceiling (`src/cadrumo/entrypoints/cli/registered_operation_deadlines.py:13`, 3600 s); when the wait ends first it reports the operation still running with its identity (`src/cadrumo/entrypoints/cli/runtime_registered_operation.py:80-104`), and otherwise there is no verb to list, observe, resume or cancel an operation by id. A review that arises is raised as an error unless the call site passed a handler (`src/cadrumo/entrypoints/cli/registered_operation_reviews.py:75-80`), so the consuming agent never sees it.
- Secrets and terminal: secrets travel on stdin or a descriptor and the profile and leaf channels may not share one (`src/cadrumo/entrypoints/cli/_profile_authentication_gate.py:382-391`). Resuming a stored sign-in and every no-echo prompt require a real console (`src/cadrumo/entrypoints/cli/runtime_profile_admission.py:125-146`, `src/cadrumo/entrypoints/cli/config/secure_input.py:443-458`), which a process spawned with piped streams does not have.
- Output: JSON success output passes identity redaction before serialisation (`src/cadrumo/core/json_contract.py:546-554`), so identifiers the agent needs may come back masked.
- Cost: one interpreter start, one authority admission and one login per call; and it shares the human's ambient active-profile pointer.
The audit did not count how many command-line call sites pass an idempotency key, so "most pass none" is not established.

Option C, targeted command-line calls. It would be built on the same manifest for a short list of capabilities. Its strongest case is a few in-process, read-only, file-local commands (review-package verification, document-only report verification, the workstation check) where a fixed command is cheaper than registering an operation. A proposed record uses that shape for the desktop shell: "a closed list of view commands ... There is no command that takes a command" (`.vault/adr/2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr.md:42`, status `proposed`). The costs are the same deletion clause, the same terminal limits as B, and one fact on the other side: for public reference data the MCP process can call the application function directly, which is how `authority` and `corpus_search` already work, so no subprocess is needed. For anything that changes state the architecture record says "TUI, CLI, and MCP dispatch registered operations through the supervisor ... none may invoke an executor, outbound adapter, or mutating business callback directly" (`.vault/adr/2026-08-11-tui-architecture-adr.md:646-648`, status `accepted`). The audit went through the in-process command lists for a capability where C wins and found none; that search was a reading of lists, not a proof.

Option D, the registry behind the existing generic tools. It is built on what exists: the nine generic tools, the registry's per-operation frontend lists, and enforcement in the runtime rather than in the adapter. Its strongest case is that it keeps the tool list constant, is the mechanism the purpose record names as the primary surface, and is already more general than the command line for lifecycle work. The costs, stated plainly:
- Admission is not free. A result projection written for a human may carry prose not meant for an agent host, and each admission needs a disclosure check.
- Widening a frontend list changes the contract digest (`src/cadrumo/application/operations/_registry_contracts.py:313`), and the purpose record requires "zero affected nonterminal operations before breaking operation-contract cutover" (`.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:131`).
- Safeguards that live in command handlers and terminal-interface screens must be rebuilt inside the operations before the operation is opened. The closed-operations Reference lists them.
- Discovery has defects today: `search` costs one runtime round trip per permitted operation (`src/cadrumo_harness/mcp/admitted_operations.py:83-95`); the admitted-surface-defects Reference lists the rest.
- Capabilities that are not registered operations are out of reach until registered or added as sub-queries of `authority`.
- On the second review's reading, the existing census test cannot guard the MCP side, because the MCP package names no operation and takes ids as data; a drift check for MCP admission would be new machinery.

The design opinion's comparison table, corrected where the reviews and the owner's ruling changed it:

| concern | A native tool per operation | B generic command tool | C targeted command calls | D registry behind generic tools |
|---|---|---|---|---|
| principal and frontend | MCP-frontend session | command-line-frontend session | same as B | MCP-frontend session |
| scope that applies | grant, frontend list, human-only flag; under a resumed sign-in the grant drops out (section 5) | grant only; frontend list bypassed | same as B | same as A |
| secrets | refused to the MCP frontend (`src/cadrumo/adapters/local_runtime/frontend_client.py:315-316`) | stdin or descriptor; needs a console to prompt | same as B | same as A |
| file transfer | host path in the payload, unconfined today | host path in argv | same as B | same as A |
| replay | durable claim on definition, subject and key (`src/cadrumo/application/operations/persistence/idempotency.py:13-46`) | per call site, not counted | same as B | same as A |
| reviews | `review` and `respond`, answerable only by the submitting session (`src/cadrumo/entrypoints/runtime/operation_host.py:525-532`) | answered inside the command, invisible to the agent | same as B | same as A |
| long-running work | operation id, `observe`, `result`, `control` | synchronous wait, identity only on timeout | same as B | same as A |
| constant tool list | changes with each operation | one more tool, once | one per capability | unchanged |
| read or write by tool name | possible | impossible | per capability | impossible; separation must come from the runtime's scope, not the name |
| capabilities outside the registry | not reached | reached | reached for the listed few | not reached until registered |
| accepted records | allowed as an optional projection | reverses a rejected option | needs an amendment per use | aligned |
| maintenance | second catalogue | command text and exit codes become the API | small, permanent exceptions | one registry, one new drift check |

The row "read or write by tool name" differs from the design opinion, which gave D a launch-time profile that makes the same tools "read-only in fact"; section 3 records why that was withdrawn.

### What Cadrumo's accepted decision records already settle

The purpose-authentication record (status `accepted`, `.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:23`) settles the mechanism most directly.
- Discovery and execute: "Use a small stable orientation/status and authorization-request surface, published-authority queries, and operation discovery/execute over the existing catalogues. Optional domain-tool projections may improve discovery but enforce the same registered contracts." (`:157`)
- Command-line wrappers: "Independent privileged CLI subprocess wrappers: rejected as the target because profile/session admission and revocation lack one local owner." (`:39`) and "Delete the displaced identity-flag admission, password-file bootstrap, retained-password forwarding, CLI-wrapper execution path and unsafe timeout/process assumptions" (`:163`).
- What no tool may expose: "No MCP tool exposes arbitrary shell execution, SQL, raw secure references, DEKs or unregistered executor calls." (`:85`) and "Source evidence bytes, passwords, keys and raw secure payloads do not enter MCP." (`:161`).
- Its limits: "There is no claim of process isolation from arbitrary hostile code under that same OS account." (`:101`), and it says the older multi-decision records are not superseded wholesale (`:58`).

The agent-harness refoundation record (status `accepted`, `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:19`) held the earlier command-line design: the command line was a "black box" universe and the console executed "every operation by shelling `aeat --format json`" (`:48`). Its 2026-09-26 amendment replaces "the CLI-subprocess-only parts of R1, Q1, the CLI-as-contract consideration and their dependent implementation prose" (`:252`) and says that "human approval where required and the applicable never-live-submit/data-disclosure rules survive" (`:254`). It also says "Client confirmation hints and an LLM's claimed approval never replace application authorization" (`:256`), which a review read as a limit on hints, not a withdrawal of the human decision. The surviving commitments that bear on writes are: manifest mutability drives client confirmation while the command line's guards remain the backstop (Q3, `:76-78`); faithfulness is a hard block at export or record-marker handoff (Q4, `:79-80`); "the verifier owns export and the record marker so the preparer cannot self-certify the irreversible handoff" (D3, `:96-97`); "Separate invocation is structural enforcement; self-report is explicitly degraded trust" (D7, `:107-108`); and the confirmation tier enforced by elicitation, with "per-verb deny rules for the handoff boundary" (R6, `:172`). Two earlier records on the same subject, `.vault/adr/2026-06-30-agent-harness-adr.md` and `.vault/adr/2026-07-01-agent-harness-adr.md`, carry status `superseded` by the refoundation record; the first had planned a server that "wraps CLI leaves as typed tools" (`.vault/adr/2026-06-30-agent-harness-adr.md:233-235`).

What displaced what. The purpose record displaced the command-line-subprocess execution path of the refoundation record, and the refoundation record's R2 delivery posture was already amended by the progressive-discovery record (status `accepted`), which rejected both a flat listing and a meta-tools-only default and chose an orientation core with the rest discovered (`.vault/adr/2026-07-08-mcp-progressive-discovery-adr.md:79-91`). Neither the progressive-discovery record nor the purpose record says whether that record's `core`/`full` surface toggle survives. What survives from the refoundation record is its safety posture: the confirmation tier, the handoff boundary, the verifier's ownership of export and the record marker, and the permanent rule that no tool submits to the tax agency.

The terminal-interface architecture record (status `accepted`, `.vault/adr/2026-08-11-tui-architecture-adr.md:29`) states the rule the registry mechanism rests on: "TUI, CLI, and MCP dispatch registered operations through the supervisor." (`:646`). It also says approval "binds the exact request, baseline, reviewed proposal, proposed effect digest, actor, and time" (`:481-482`). The profile-access record (status `accepted`, `.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md:20`) lists "Attended agent access" as explicit delegation tied to a human authorization, and "Unattended agent" as an enrolled key (`:72-73`); its "parity" heading means command line and terminal interface parity for profile authentication, grants, sessions and work, not parity of MCP with the command line (`:171-173`, `:197`).

### What the two independent reviews found

Both reviews, one on authority and conformance and one on evidence and feasibility, returned "sound with required changes". The findings below are findings, not decisions.

What held:
- The mechanism. Neither reviewer found a capability for which a command-line call beats the registry, nor any way to break the rejection of per-operation tools. The reviewer on authority tried and could not break these claims: a human-only operation is refused to every non-human session (`src/cadrumo/application/user_profile/operation_access_policy.py:175-176`); a secret never reaches an operation from MCP (`src/cadrumo/entrypoints/runtime/operation_host.py:386-392`); a review is answerable only by the submitting session and a replayed submit does not revive the response capability (`src/cadrumo/entrypoints/runtime/operation_host.py:303`, `:525-532`); and in the executors sampled every state change sits inside the commit section. That last claim is a sample, not a census.

What did not hold:
- Writes on a grant alone. The design had an agent prepare, verify and export a declaration on its grant. That contradicts accepted records the design did not name: D3, Q3, Q4, D7 and R6 above, and the packaged rule "Obtain explicit human confirmation for destructive actions; a grant alone does not express that intent" (`src/cadrumo_harness/_data/agent/rules/cadrumo-operator-operating-rules.md:54-58`). Verify stamps `verified_by` from a caller-supplied actor (`src/cadrumo/application/modelo/verification_actions.py:503-508`), so one principal could produce the whole chain. The consuming side is a single agent with no roles, so "separate invocation" cannot be supplied there.
- A replay key derived from the payload. The design proposed a default key from grant, definition, subject and payload digest. The accepted idempotency record weighed that shape for `ledger add` and rejected content-derived identity because it "cannot distinguish a retry from a genuine second identical same-day movement" and would "convert a genuine second cash payment into a silent overwrite" (`.vault/adr/2026-06-30-ledger-add-idempotency-adr.md:71-88`, status `accepted`); it chose a caller-supplied key and keeps the keyless path as an append (`:143-147`). In code a claim resolves to the first operation whatever its outcome (`src/cadrumo/application/operations/_supervisor_submission.py:137-146`; the scan is at `src/cadrumo/adapters/persistence/operations/journal.py:243-252`), so a first attempt that failed transiently would be returned for every identical retry, and archive, restore, archive would swallow the third call. The default was withdrawn.
- "Parity by default". The design admitted every operation unless a recorded exclusion applied. The registry's rule is the opposite and says why: "Membership is explicit so a new frontend is never granted to existing operations silently" (`src/cadrumo/application/operations/registry.py:197-198`). Admission stays opt-in, with a recorded decision in both directions.
- The argument from an agent with a shell. The design said the frontend list is no boundary against an agent that can run `aeat`, so widening gives it nothing new. True in code: an API-key login takes its client id from the grant "from protected state, not proof" (`src/cadrumo/entrypoints/runtime/profile_connection_sessions.py:144-147`), the command line opens such a session as the CLI frontend (`src/cadrumo/entrypoints/cli/runtime_profile_admission.py:229-236`), and the sign-in record concedes "Any same-user process can allocate a pseudo-terminal or declare a frontend, and the runtime cannot verify either" (`.vault/adr/2026-10-04-application-sign-in-adr.md:93`, status `accepted`) and "Same-user native code can still present a live proof" (`:257`). But it proves too much: by the same reasoning grant scope and the human-only flag are no boundary either, and nobody concludes human-only operations should open. Absence of a stated reason for an exclusion is silence, not intent. For `ledger.add`, the CLI-only list was written inside the MCP integration commit of 2026-09-30 (`3bb3b64787`, `src/cadrumo/application/ledger/add_operation.py:179`), while sibling ledger definitions were given all three frontends; history gives no reason either way.
- The launch-time read-only profile. The design narrowed the lease at launch so the same 16 tools were "read-only in fact". It is not read-only: the commit section is entered only when an executor chooses to open it (`src/cadrumo/application/operations/_execution_context.py:82-92`) and recording an effect checks the definition's declared effects, not that a guard is held (`:233-245`); refusal therefore comes at commit, not at submit. Before it, a provider browser may be launched (`src/cadrumo/application/live/live_operation_execution.py:60-70`), and every submit writes a journal record and takes a subject lease. The flag is set by the client. The review's name for the real property is "no local domain commit".
- Lease refresh as a detail. Nothing in production code calls the client's `refresh_api_key` (`src/cadrumo/adapters/local_runtime/frontend_client.py:385-387` defines it); the lease is capped at five minutes. Every held authorization section lasts the lesser of the lease and 30 seconds (`src/cadrumo/application/runtime/worker_authorization.py:33`, `src/cadrumo/adapters/local_runtime/worker_authorization.py:311-316`), and a held section that does not release cleanly makes the runtime contain the worker (`src/cadrumo/adapters/local_runtime/worker_authorization.py:154-172`); a profile host has one immutable worker (`src/cadrumo/entrypoints/runtime/profile_host.py:183-184`), so the human's operations on that profile would stop with it. The accepted rule bounds refresh: "every executing stage needs newly admitted authority; waiting releases access and keys" (`.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md:144`), so refreshing for the whole life of an adapter conflicts with it. What happens after containment was not traced.
- Indifference to the kind of session. The design said its plan was the same for an enrolled key or a session delegated from the human sign-in. Refresh is refused for any session that is not a root key session (`src/cadrumo/application/user_profile/session_authority_admission.py:453-454`, `src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py:102-103`), narrowing at login exists only on the key path, and delegation has no caller. The sign-in record says the idle deadline is extended only by a submission from a human session on an interactive operation, never by observe or result traffic (`.vault/adr/2026-10-04-application-sign-in-adr.md:97-98`).

Smaller findings that changed the plan: ledger operations resolve with whole-profile scope (`src/cadrumo/application/ledger/add_operation.py:188-191`, `src/cadrumo/application/ledger/read_access.py:51-54`), so a grant limited to two exercises would refuse them (`src/cadrumo/application/user_profile/operation_access_policy.py:62-72`); the export request carries refund, payment and direct-debit elections and the bank account (`src/cadrumo/application/modelo/operation_definitions.py:1309-1320`); and the evidence-extraction request carries an off-host acknowledgement as a boolean the caller sets (`src/cadrumo/application/ledger/invoice_evidence_extract_operation.py:69-81`).

A cited safeguard sat on the wrong path. The design cited the live-write gate as the enforcement of the owner's absolute boundary. The facts: `AeatAccessGate.require_live_write` always raises (`src/cadrumo/core/access_gate/gate.py:96-107`); its only production call site is command-line dispatch (`src/cadrumo/entrypoints/cli/_command_runtime.py:346`), and no command declares a live write; a tool call does not pass through that gate, and on that path the boundary holds because no registered operation submits anything. `modelo.work.file` writes a local record and submits nothing (`src/cadrumo/application/modelo/operation_definitions.py:976-981`). Read-only captures from the tax agency (`live.*`) are a different thing and are not part of this boundary.

### The demand side: what the skills and the consuming agent need

Packaged skills, rules and personas (34 skills, 7 rules, 7 personas, all under `src/cadrumo_harness/_data/agent/`) expect command-line verbs. The workspace names 58 distinct leaf commands, recounted against the command tree, plus 5 `app runtime` commands in its README that the command tree does not declare. No skill mentions MCP, and no operation-id-shaped token occurs anywhere in the packaged tree. The only MCP guidance is in the README and the rules: use `search` then `describe` and read the contract before `execute` (`src/cadrumo_harness/_data/agent/rules/cadrumo-operator-orientation-routing.md:123-132`, `src/cadrumo_harness/_data/agent/README.md:23-26`); "CLI availability does not imply that an operation is exposed or granted to MCP" (`src/cadrumo_harness/_data/agent/rules/cadrumo-operator-orientation-routing.md:6`); and "Never construct a tool name or operation payload from a CLI command's spelling" (`src/cadrumo_harness/_data/agent/rules/cadrumo-operator-operating-rules.md:37-42`). So a skill's verb has no path to its operation id today, and six personas name a "capability manifest" (for example `src/cadrumo_harness/_data/agent/personas/cadrumo-classifier.md:10`) that the tree does not contain.

The hand-off sentences the skills carry must survive any remapping: "Your job ends at produce → verify → export; the taxpayer uploads the generated file in the AEAT portal themselves" (`src/cadrumo_harness/_data/agent/rules/cadrumo-operator-safety-handoff.md:8-12`) and the same wording in the export steps (for example `src/cadrumo_harness/_data/agent/skills/cadrumo-exportar-declaracion/SKILL.md:25-30`). Two places have the agent record the local filed marker: that skill step and the verifier persona (`src/cadrumo_harness/_data/agent/personas/cadrumo-verifier.md:34-36`). The ledger persona tells the agent to pass a stable idempotency key on every add and to omit it only for a genuinely identical second movement (`src/cadrumo_harness/_data/agent/personas/cadrumo-ledger-groomer.md:18-22`). The harness rules are "prompt material rather than enforcement" (`.vaultspec/rules/02-runtime-tui-and-agent-harness.md:7`).

What the consuming agent requires of the tool surface, as the integration research records state it:
- A constant tool list, answerable before any session. Its probe is cached per worker process, so the list "must be a constant of the Cadrumo package version" and "may not vary with profile, lock state or grant scope" (`2026-10-10-cadrumo-integration-opinion-agent-relay-fit-research` line 78). The list is already static and served without admission (`src/cadrumo_harness/mcp/server.py:27-33`); whether the server answers `initialize` before admission is recorded as an open conflict.
- Few, generic names, so the toolset can change on Cadrumo's side without an agent change (`2026-10-10-cadrumo-integration-requirements-reconciliation-research` line 608; the trilemma at line 487: an undecided toolset, a frozen agent and a write gate keyed on tool names "cannot all be had").
- No way to tell reads from writes by tool name: "`execute` is one tool for reads and writes, so the agent's allowlist cannot tell them apart" (`2026-10-10-cadrumo-integration-opinion-cadrumo-managed-mcp-research` line 174), and "Generic tool names defeat gating by tool name. That stops mattering once Cadrumo is the only gate" (`2026-10-10-cadrumo-integration-opinion-agent-relay-fit-research` line 187).

Which of these is a decision. The kickoff record's constraints are labelled as fixed by the owner but are the kickoff session's own summary, not a transcript; among them "The toolset is not decided" (`2026-10-10-cadrumo-integration-kickoff-research` line 46). Everything else above is an opinion: the frozen, versioned surface passed as a literal argument, the exact-surface matching, and the claim that a Cadrumo-owned gate makes name-based gating moot. The packaged skills and rules describe current behaviour and are not decisions.

### The owner's rulings that bear on the mechanism

First-hand in the MCP-PARITY session on 2026-10-10 (typing lightly corrected there):
- On the governing rule: "How is CLI and TUI checking the login state? There should be no divergence from their implementation - or the implementation should be evolved in tandem. None should be able to operate unless runtime is running, available and authed, and valid user session logged in and authed. The only exception is long-lived API key we can issue against a profile that allows accessing and authenticating directly without the runtime and status."
- Confirmation: "I confirm MCP should resume the shared sign-in like CLI and TUI."
- On the login prompt: "Completely fine to have a state based login. no need to change architecture." On a time-out: "timeout like sign-out is correct. backend should return no conversations when there's no signed in active user."
- "Storage administration should not be an MCP responsibility". On which exclusions were intended the owner had "no good answer" and asked that the other sessions and "the rules that drive the app" be consulted and a judgement made.
- On Python and the terminal: that opening a profile with Python "isn't a security concern", and "I FEEL QUITE STRONGLY THAT THE AGENT SHOULD BE ABLE TO WRITE PYTHON SCRIPTS AND EXECUTE THEM TO BATCH AND CREATE AD HOC SCRIPTS AS WELL AS ACCESS THE CLI, PYTHON INTERNALS AND MCP"; whether a general terminal that installs tools is allowed, "I don't know".
- The boundary on writing to the tax agency is fixed and is not a design subject.

Relayed second-hand, through the record `2026-10-10-cadrumo-integration-owner-rulings-research`, whose own last section records answers given in another session: "Terminal access is ciritcal - the cli and python code lives there.the agent must abolsutly must jhave acess to the pyhton and console cadrumo bundles to produce and write, operate the cli" (lines 61-65); the answer "Command line plus Cadrumo's Python" to what the terminal may run (lines 158-164); "Assistant, after asking each time" for destructive or irreversible commands (lines 165-169); and the record's own statement that "A script the assistant writes can call Cadrumo's internals directly and is not held by that approval or by any of Cadrumo's checks" (lines 214-218).

Consequences for this question, without deciding it.
- The rulings change the premises. Today the runtime refuses the password and receipt methods from any frontend other than the command line and the terminal interface (`src/cadrumo/entrypoints/runtime/profile_connection_admission.py:136-140`) and the MCP adapter requires an automation grant (`src/cadrumo_harness/mcp/runtime_admission.py:49-51`), so MCP can use only the key. The ruling to resume the shared sign-in means a human-kind session with no grant narrowing. The human-only check refuses only non-human sessions (`src/cadrumo/application/user_profile/operation_access_policy.py:175-176`), so for such a session the frontend list is what remains between an agent and an operation, with Cadrumo's write confirmation; the enrolled key survives sign-out by design (`src/cadrumo/application/user_profile/session_authority_lifecycle.py:35-52`). That is the audit's reading plus a derived point about the human-only check. The audit's view is that it needs an amendment to the profile-access record, which says agents use enrolled keys or attended delegation.
- An agent's own use of the command line is a different thing from the MCP server calling it. In the first the agent chooses and runs a command; the command opens its own command-line-frontend session on the same sign-in, with that command's own guards and exit codes, and no operation id, observation or typed review reaches the agent. In the second, Cadrumo's server runs the command on the agent's behalf. The owner's terminal rulings give the agent reach to the command line and to Python whatever MCP admits.
- That changes what MCP admission is for. With a terminal, MCP admission is not about reach, since reach exists; it is about a typed, observable, reviewable access path: operation ids, contracts, idempotency, a journal and a review the host can show. A decision record has to say whether admission still has to be conservative to protect reach, or may be judged on those properties.
- The refoundation amendment says "The agent still sees a confined deterministic tool universe, with no arbitrary code, SQL or shell capability" (`.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:254`). The purpose record's ban is on MCP tools (`.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:85`), but the amendment speaks of the agent's tool universe, and the owner has asked for a terminal. A decision record has to say which governs the agent's terminal.

### What a decision record must settle

Each item is a choice, with the evidence on each side.

1. Which exclusions were intended, and must every operation carry a recorded MCP decision. For admitting: 65 of the 143 closed operations are closed only by the frontend list with no reason in code (closed-operations Reference), and history gives none. Against: silence is not intent; the 2026-09-30 commit for `ledger.add` was written inside the MCP integration; D3 and the 2026-06-30 idempotency record are recorded reasons for parts of the same set. Reviewer's recommendation, not a ruling: opt-in admission with a recorded decision both ways.
2. How an agent's write is authorised, and who holds the hand-off (export, the local filed record). For a human decision: D3, Q3, R6 and the packaged rule above; the consuming agent cannot separate preparer from verifier. For confirmation in Cadrumo beside a present human: the owner's resumed sign-in places a person at the keyboard, a Cadrumo host can show a review and send the response after a click (`2026-10-10-cadrumo-integration-opinion-cadrumo-managed-mcp-research` line 188), and the preview-digest alternative is a drift guard, not consent. Open: whether the confirmation tier still binds a single-agent consumer; what replaces elicitation.
3. What tells a replay from a repeat. For a caller-supplied key from the host that owns the turn: the accepted idempotency record and the consuming side's requirement that no key be chosen by the model (`2026-10-10-cadrumo-integration-requirements-reconciliation-research` line 600). Against content-derived keys: section 3. Open: refuse an effectful call without a key, and never return a settled-without-effect operation as the answer to a replay.
4. Documents and plaintext. Which documents an agent may originate, where plaintext may live and for how long. Evidence-grade imports raise evidentiary weight; exports for a non-human session create plaintext copies; and admitted operations take host paths with no containment check. The owner has said the agent's folder sits beside encrypted storage and that attached documents may go to the hosted provider under one standing consent (`2026-10-10-cadrumo-integration-owner-rulings-research` lines 57-68), which bears on the rule that evidence bytes do not enter MCP (`.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:161`) and has to be reconciled with it.
5. Amounts a model read. Whether model-read amounts may enter the ledger as fact, and under what provenance. Against: the regulated figure is registry-derived, and `ledger.add` accepts base, rate and amount from the caller (`src/cadrumo/application/ledger/ledger_add_contracts.py:67-69`). For: the agent's own model replaces Cadrumo's local model for classification (`2026-10-10-cadrumo-integration-owner-rulings-research` lines 42-45).
6. Export elections and accounts. Whether an agent may choose refund, payment and direct-debit elections and the bank account in an export (`src/cadrumo/application/modelo/operation_definitions.py:1336-1338` describes the elections as deciding the file's declaration type), or create and change own accounts. These are the taxpayer's decisions with money attached; `actor` is caller-supplied on verify, file and export.
7. What a read-only surface contains. Only operations with no local commit and no network reach, enforced at submit, would need a per-operation egress class that does not exist. Live captures read from the tax agency and store local snapshots, so they fall outside "no local commit". Separation by grant scope, enforced by the runtime, is the alternative the reviews preferred.
8. Session lifetime under the resumed sign-in. The owner closed the principal (resumed sign-in; the key is the single exception) and treats a time-out like a sign-out. Still open: whether an executing operation outlives the human idle window (agent activity does not extend it), how long keys may stay unlocked while an operation executes, and a floor of remaining lease below which no commit section opens.

### The option the evidence favours

Label: this is what the evidence favours, not a decision. It favours option D, the registry behind the existing generic tools, as the mechanism, with no command-line path inside the MCP server. The agent's own use of a terminal is a separate matter the owner has raised. Option D is the one the purpose record names as the primary surface and needs no superseding record, it keeps the 16-name list constant for the consumer, it carries operation ids, observation and review that a command-line call does not, and it survived two attempts to break it. Option A remains a possible later refinement if a live evaluation shows models fail to find operations through `search`. The evidence does not settle the authority model for writes, the replay identity, or which exclusions were intended; those are the items above, and they belong to the decision record.

### Not verified

- Nothing was run; every runtime statement is a static reading of a tree another session was changing.
- Whether the four extra tools named in the earlier MCP package were advertised by default. A recount on 2026-10-10 settled two counts first listed here: that package built its tool list at run time from the command line's command-surface output, so it has no static tool count (the same rule gives 313 exposable commands on `main`, and 273 is a figure from a comment in that package); and no call site of the generic submit function passes an idempotency key as an argument.
- Whether Cadrumo's classifier is invoked before any commit section in `ledger.classify.review`, whether any live read writes provider session state outside a commit section, what the supervisor records when a worker is contained, and whether the worker enforces the terminal interface's export gates were not traced.
- The reviews' reading that the existing census test does not guard the MCP side was not re-traced beyond the MCP package naming no operation.
- Whether the MCP server answers `initialize` before admission, and the place of the `core`/`full` surface toggle after the purpose record, are unresolved in the records.

## Sources

Decision records of this repository:
- `.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:23` (status `accepted`)
- `.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:39`
- `.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:58`
- `.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:85`
- `.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:101`
- `.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:131`
- `.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:157`
- `.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:159`
- `.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:161`
- `.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md:163`
- `.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md:20` (status `accepted`)
- `.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md:72-73`
- `.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md:144`
- `.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md:171-173`
- `.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md:197`
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:19` (status `accepted`)
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:48`
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:76-78`
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:79-80`
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:96-97`
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:107-108`
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:125-127`
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:172`
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:252`
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:254`
- `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:256`
- `.vault/adr/2026-06-30-agent-harness-adr.md:233-235` (status `superseded`)
- `.vault/adr/2026-07-01-agent-harness-adr.md` (status `superseded`)
- `.vault/adr/2026-07-08-mcp-progressive-discovery-adr.md:79-91` (status `accepted`)
- `.vault/adr/2026-08-11-tui-architecture-adr.md:29` (status `accepted`)
- `.vault/adr/2026-08-11-tui-architecture-adr.md:481-482`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:646-648`
- `.vault/adr/2026-06-30-ledger-add-idempotency-adr.md:71-88` (status `accepted`)
- `.vault/adr/2026-06-30-ledger-add-idempotency-adr.md:143-147`
- `.vault/adr/2026-10-04-application-sign-in-adr.md:93` (status `accepted`)
- `.vault/adr/2026-10-04-application-sign-in-adr.md:97-98`
- `.vault/adr/2026-10-04-application-sign-in-adr.md:257`
- `.vault/adr/2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr.md:42` (status `proposed`)
- `.vaultspec/rules/02-runtime-tui-and-agent-harness.md:7`

Cadrumo command line and manifest:
- `src/cadrumo/entrypoints/cli/main.py:147-149`
- `src/cadrumo/entrypoints/cli/main.py:310-318`
- `src/cadrumo/entrypoints/cli/verb_input_schema.py:37-54`
- `src/cadrumo/entrypoints/cli/verb_input_schema.py:83`
- `src/cadrumo/application/operator_surface/command_ports.py:366-376`
- `src/cadrumo/entrypoints/cli/tests/test_command_surface_beside_retired_state.py:72`
- `src/cadrumo/entrypoints/cli/runtime_registered_operation.py:80-104`
- `src/cadrumo/entrypoints/cli/registered_operation_deadlines.py:13`
- `src/cadrumo/entrypoints/cli/registered_operation_reviews.py:75-80`
- `src/cadrumo/entrypoints/cli/runtime_profile_admission.py:125-146`
- `src/cadrumo/entrypoints/cli/runtime_profile_admission.py:229-236`
- `src/cadrumo/entrypoints/cli/_profile_authentication_gate.py:382-391`
- `src/cadrumo/entrypoints/cli/config/secure_input.py:443-458`
- `src/cadrumo/entrypoints/cli/_command_runtime.py:346`
- `src/cadrumo/core/json_contract.py:546-554`
- `src/cadrumo/core/access_gate/gate.py:96-107`

Cadrumo registry, runtime and operations:
- `src/cadrumo/application/operations/registry.py:189-201`
- `src/cadrumo/application/operations/registry.py:197-198`
- `src/cadrumo/application/operations/_registry_contracts.py:313`
- `src/cadrumo/application/operations/_execution_context.py:82-92`
- `src/cadrumo/application/operations/_execution_context.py:233-245`
- `src/cadrumo/application/operations/_supervisor_submission.py:137-146`
- `src/cadrumo/application/operations/persistence/idempotency.py:13-46`
- `src/cadrumo/adapters/persistence/operations/journal.py:243-252`
- `src/cadrumo/application/user_profile/operation_access_policy.py:62-72`
- `src/cadrumo/application/user_profile/operation_access_policy.py:175-176`
- `src/cadrumo/application/user_profile/operation_access_policy.py:175-178`
- `src/cadrumo/application/user_profile/session_authority_admission.py:453-454`
- `src/cadrumo/application/user_profile/session_authority_lifecycle.py:35-52`
- `src/cadrumo/adapters/persistence/storage/master_key/profile_worker_custody.py:102-103`
- `src/cadrumo/application/runtime/worker_authorization.py:33`
- `src/cadrumo/adapters/local_runtime/worker_authorization.py:154-172`
- `src/cadrumo/adapters/local_runtime/worker_authorization.py:311-316`
- `src/cadrumo/adapters/local_runtime/frontend_client.py:315-316`
- `src/cadrumo/adapters/local_runtime/frontend_client.py:385-387`
- `src/cadrumo/entrypoints/runtime/operation_host.py:303`
- `src/cadrumo/entrypoints/runtime/operation_host.py:386-392`
- `src/cadrumo/entrypoints/runtime/operation_host.py:525-532`
- `src/cadrumo/entrypoints/runtime/profile_connection_admission.py:136-140`
- `src/cadrumo/entrypoints/runtime/profile_connection_sessions.py:144-147`
- `src/cadrumo/application/live/live_operation_execution.py:60-70`
- `src/cadrumo/application/ledger/add_operation.py:179`
- `src/cadrumo/application/ledger/add_operation.py:188-191`
- `src/cadrumo/application/ledger/read_access.py:51-54`
- `src/cadrumo/application/ledger/ledger_add_contracts.py:67-69`
- `src/cadrumo/entrypoints/runtime/profile_host.py:183-184`
- `src/cadrumo/application/ledger/invoice_evidence_extract_operation.py:69-81`
- `src/cadrumo/application/modelo/operation_definitions.py:976-981`
- `src/cadrumo/application/modelo/operation_definitions.py:1309-1320`
- `src/cadrumo/application/modelo/operation_definitions.py:1336-1338`
- `src/cadrumo/application/modelo/verification_actions.py:503-508`

Cadrumo MCP harness and packaged agent material:
- `src/cadrumo_harness/mcp/protocol_contract.py:52-128`
- `src/cadrumo_harness/mcp/protocol_contract.py:92-97`
- `src/cadrumo_harness/mcp/server.py:27-33`
- `src/cadrumo_harness/mcp/admitted_operations.py:83-95`
- `src/cadrumo_harness/mcp/runtime_admission.py:49-51`
- `src/cadrumo_harness/_data/agent/README.md:23-26`
- `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-orientation-routing.md:6`
- `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-orientation-routing.md:123-132`
- `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-operating-rules.md:37-42`
- `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-operating-rules.md:54-58`
- `src/cadrumo_harness/_data/agent/rules/cadrumo-operator-safety-handoff.md:8-12`
- `src/cadrumo_harness/_data/agent/personas/cadrumo-verifier.md:34-36`
- `src/cadrumo_harness/_data/agent/personas/cadrumo-ledger-groomer.md:18-22`
- `src/cadrumo_harness/_data/agent/personas/cadrumo-classifier.md:10`
- `src/cadrumo_harness/_data/agent/skills/cadrumo-exportar-declaracion/SKILL.md:25-30`

Cadrumo git, read-only: `main` at `813a607ed5` against `feature/tui` for `src/cadrumo_harness/mcp` (`git diff --shortstat main HEAD`, 104 files, 4315 insertions, 17686 deletions); commit `3bb3b64787` (2026-09-30) via `git blame` on `src/cadrumo/application/ledger/add_operation.py:179`.

Vault records in this vault, cited by stem:
- `2026-10-10-mcp-parity-surfaces-and-registry-reference`
- `2026-10-10-mcp-parity-sign-in-doors-reference`
- `2026-10-10-mcp-parity-admitted-surface-defects-reference`
- `2026-10-10-mcp-parity-closed-operations-reference`
- `2026-10-10-cadrumo-integration-owner-rulings-research`
- `2026-10-10-cadrumo-integration-opinion-agent-relay-fit-research`
- `2026-10-10-cadrumo-integration-opinion-cadrumo-managed-mcp-research`
- `2026-10-10-cadrumo-integration-requirements-reconciliation-research`
- `2026-10-10-cadrumo-integration-kickoff-research`
