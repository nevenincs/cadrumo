---
tags:
  - '#audit'
  - '#mcp-parity'
date: '2026-10-11'
modified: '2026-10-11'
body_schema: 'body-v2'
body_hash: 'sha256:e20b1245af06e843feb4f7db6a41f618ad8b1178beae200e5aaa4827710dcd34'
related:
  - "[[2026-10-10-mcp-parity-plan]]"
---

# `mcp-parity` audit: `Phase-close reviews of the MCP parity plan`

## Scope

Rolling log of the formal reviews of `2026-10-10-mcp-parity-plan`. Each review reads committed work against the plan and its governing decisions and traces the affected workflows across their interfaces.

Review 1, 2026-10-11: phase close of `P01` (Steps `S01` to `S11` and `S45`) and `P04` (Steps `S27` to `S29` and `S46`), commits `f72cc2f19e` to `a2aea88f1f`. Verdict: `P04` passes. `P01` required a revision to the packaged agent text of `S10`, applied the same day; it passes once the two medium findings are closed or assigned. Both were closed the same day, with the low findings, as recorded under each.

Checked and found sound in review 1: a definition cannot list MCP against its recorded decision, and each named sensitive act is refused by the real resolver on MCP only; no second route (batch, review response, resume, result read) reaches own-account writes, the Modelo 360 solicitud, the capability opt-ins, the prorrata elections, invoice removal, session reset or the census review; the surface is carried on both logins, inherited by child leases and fixed at first login; fourteen rows of change and network facts agree with their executors; the agent-facing results (evidence query, review summary, both timelines, filing record view, reader readiness) carry no bytes, host path or open payload; every subject declaration is held to its family's check; paged search and the generated command join behave as described; no suppressions, record citations or change-narrating comments in the reviewed commits. Not checked: 28 resolvers that need stored records to probe, the POSIX branch of the path guard, an end-to-end run on a real runtime, translations.

Review 2, 2026-10-11: before handoff, the sign-in door (`458418a63d`, `f45bf1eb42`, `f7decadcc6`), the declaration work (`808e4ccbf7`, `a2aea88f1f`, `0bc6e88234`) and the ledger writes (`6ab3941b45`, `915b264606`), base `fde91b1ebb`. Verdict: revision required, reopening the reader-locality work of `S42` and `S44` and the bulk classification of `S32`; the one-way split of `S35` awaits the owner. No critical finding.

Checked and found sound in review 2: an MCP connection cannot send a password or have a sign-in stored; nothing it does moves either deadline; the lease is re-evaluated at each operation and effect, so sign-out, lock and expiry stop the session; sign-out and locking another session are refused to it; the profile and the surface are fixed by the session. Where the human kind of session gates an act, the MCP frontend is separately refused: session inventory, automation deny, profile resume and recovery, typed secrets (which covers key approval, password rotation and certificate secrets) and workbench generation admit only the command line and the terminal interface; review responses are bound to the submitting session; no definition that requires a person lists MCP. The receipt fix leaves no deletion a caller without the proof can trigger and wipes the unwrapped key. The actor is read from the worker's own binding and fails closed when the session is retired. The calculation variants, observation clear, the signed block, the off-machine read and the reaffirming run are refused whatever the action. Not checked: a running runtime end to end, POSIX, the Windows system proxy, translations.

Review 3, 2026-10-11: re-review of the fixes in `ece30ed551`, base `0cbfe6a994`. Verdict: revision required for `S32`, `S35` and `S42`. The proxy fix holds against hostile addresses and no operation open to MCP writes the endpoint setting; the bulk classification fix holds on its own route; the release of results by admitting frontend holds on every path that returns content; the census is truthful for five of seven entries checked.

## Findings

### agent-text-amend | high | The amend skill told an agent to record a local filing with no approval

`src/cadrumo_harness/_data/agent/skills/cadrumo-rectificar-declaracion/SKILL.md:56` instructed `aeat app modelo work amend` with no approval and described the result as a draft to verify and export. `src/cadrumo/application/operations/mcp_admission.py:411` records the opposite: amending verifies the correction, records it as filed locally and retires the corrected record in one act, behind the person's approval. The skill was edited in `S10` before the re-ruling in `S37` and was not revisited. Resolved 2026-10-11: the skill now puts the person's approval of that exact act in front of the command and describes the act truthfully.

### surface-real-policy | medium | No test holds a read-only-local operation to its real resolver

`src/cadrumo/entrypoints/tests/test_operation_mcp_surfaces.py:339` proves admission with a synthetic policy that has no commit action. A listed read whose resolver holds the commit action is advertised and then refused at submission; `S46` found and fixed exactly this by hand for two Google reads. A probe through the real resolvers found no commit action in 61 of the 89 listed operations; 28 could not be probed without stored records. Resolved 2026-10-11: `src/cadrumo/entrypoints/tests/test_operation_mcp_surface_policies.py` resolves the real policy of every listed operation, from a schema-built request or a seeded profile, and requires that it holds no commit action and is admitted at submission; no operation is left unproven and no defect was found.

### capture-output-root | medium | Six open capture operations keep a caller-chosen host path in request and result with nothing recorded as outstanding

`src/cadrumo/application/live/filed_history_operation.py:114` accepts any absolute root outside the application storage as written and repeats it in the result (for example `src/cadrumo/application/live/filed_single_capture_operation.py:99`). Their rows carry no prerequisite, nor does `modelo.reconcile.import`, whose root confinement the ledger defers to the file-exchange Step. No test fails if that Step forgets either. Resolved 2026-10-11 as a recorded and enforced debt: `MCP_HOST_PATH_FIELDS` in `src/cadrumo/application/operations/mcp_admission.py` names every request and result field of an MCP-open operation that carries a host path, and the catalogue test fails on an unrecorded field and on a stale entry. Reading showed the capture operations only record and echo the root and open or write nothing beneath it. The same pass found host paths released to agents by the reconciliation results and by the local authentication read; an agent now receives the file name only. The request fields remain for the file-exchange Step.

### reader-network-fact | low | The network fact differs for operations that use the same reader

`src/cadrumo/application/operations/mcp_admission.py:241` records the classification and split reviews as local, while line 296 records reader readiness as reaching the network because settings can point the endpoint elsewhere. Not confirmed that the reviews use the same setting. Resolved 2026-10-11: they do. Both rows now record that the operations reach the network, and an agent's review is refused unless the reader's endpoint is on this machine, by the one check the extraction uses.

### agent-text-storage | low | A storage bullet named a command that does not exist and a confirmation flag

`src/cadrumo_harness/_data/agent/rules/cadrumo-operator-orientation-routing.md:124` said to inspect with `show`; the command is `config storage view`. Line 116 spelled `reclaim <category> --yes`, while the safety rule tells an agent that a confirmation flag is not the person's approval. Resolved 2026-10-11: both corrected.

### workflow-run-detail | low | Workflow run reads release undeclared named values

`src/cadrumo/application/workflow/run_projection.py:79` copies every field of a step detail into key and value lists. Today's variants hold identifiers, counts, dates and codes; a later field carrying a path or a message would reach MCP with no contract change and no failing test. Resolved 2026-10-11: the projection releases an allow-listed set of fields per detail variant and a test fails when a variant gains a field. The same change repaired the projection of details that carry an enumeration member, which failed validation.

### harness-raw-subject | low | The harness derives the subject from the unvalidated payload

`src/cadrumo_harness/mcp/admitted_operations.py:163` renders the subject from raw JSON while the families compare against the validated model. A defaulted or non-canonical subject field is refused locally or by the runtime, so it fails closed. Recorded, no action.

### reader-called-local | medium | A reader counts as on this machine by its provider name alone

`src/cadrumo/adapters/outbound/llm/consent.py:60` decides that a read is local from the provider name, while the endpoint the local reader calls is a setting (`src/cadrumo/adapters/outbound/llm/providers/local.py:202`). With the endpoint pointed at another host, extraction and the two model reviews send the person's document and transaction text off the machine without the consent an off-machine read requires. Found 2026-10-11 while admitting extraction. An execution admitted on MCP is now refused unless the endpoint is loopback. The command line and the terminal interface are unchanged, so a person who points the setting elsewhere is still not asked. Open for those two frontends; outside this plan's scope.

### reader-proxy | high | The reader counted as on this machine by its address while its client honoured proxy settings

`src/cadrumo/application/ledger/agent_reader_locality.py:21` passes when the endpoint host is loopback, and `src/cadrumo/adapters/outbound/llm/providers/local.py:198` then posts with a client that reads proxy settings from the environment. With a proxy variable set, requests to `127.0.0.1`, `localhost` and `[::1]` are sent through the proxy, so an agent's extraction or model review sends document text and images off the machine. The adapter also re-reads settings instead of using those the guard checked. Review 2. Resolved 2026-10-11: a request to a loopback endpoint is sent by a client that ignores environment and system proxy configuration and follows no redirect; the guard and the adapter share one definition of a loopback endpoint in `src/cadrumo/core/loopback_endpoint.py`; and the client is chosen from the address the request is about to use. The adapter still resolves its endpoint when it sends, as the product always did, so nothing forces it to match the settings the guard read if they change in between. Not tested against a real Windows system proxy.

### bulk-classify-second-route | high | Bulk classification did on MCP what the same work refuses or holds elsewhere

`src/cadrumo/application/ledger/bulk_classify_operation.py:267` reaches the write of single classification for any active row: it replaces a classification made by hand while its event stores only the new one, stamps the row as manually classified, and lets a row state taxable base, rate and cuota. Single classification is held back for the replay-identity and provenance decisions, and a reaffirming rule run is refused on MCP for the same loss. The entry rules moved into single classification also do not reach it: the real parser accepted an undeclared IRPF category and six-decimal amounts. Review 2. Resolved 2026-10-11: bulk classification no longer lists MCP and waits with single classification on the replay-identity and provenance decisions, and each of its rows now passes through the code single classification uses, on every frontend. An unknown category, a six-decimal amount, a share on a row that is not mixed and a mixed row without a share each fail that row.

### split-one-way | medium | A manual split was admitted as reversible and is not

`src/cadrumo/application/ledger/split_operation.py:132`: the parent keeps classification, evidence and attachments, none pass to the children, restore refuses the parent, and only the approval-bound merge recombines, with the classification entered again. Review 2. Resolved 2026-10-11: an agent's split of a parent that carries a classification made by hand, linked evidence, a linked invoice or attachments is refused before any effect; a parent that carries none of them splits as before. The refusal is in the executor, which holds the row.

### result-sealing-by-executor | medium | Withholding was applied when a result was sealed, not when it was read

`src/cadrumo/entrypoints/runtime/operation_host.py:451` releases a stored result to any live session under the reader's frontend. A result sealed by a person's execution keeps the full draft text, the evidence directory, the reconciliation paths and the certificate path, and an MCP reader that names the operation receives it; the only barrier is that operation identifiers are random and no MCP read was found that lists another session's. Review 2. Resolved 2026-10-11: a reader on the MCP frontend is released a result, a result page, a review projection or error detail only for an operation whose stored admission names the MCP frontend, and is otherwise told the operation is unavailable. A replay from MCP of an operation admitted elsewhere returns its receipt and no content. A person resuming an agent's operation now seals it as the agent's. Left as it is: with its identifier an agent can still observe, cancel, detach or resume a person's operation.

### actor-coverage | low | Fixed labels remained and no census held the rule

`src/cadrumo/application/inventory/registered_executor.py:206` records a fixed label for an agent's inventory create, movement and valuation, and no test fails when an MCP-open request gains an attribution field. A person resuming an agent's interrupted operation records the label the agent typed. Review 2. Resolved 2026-10-11: the three inventory writes record the session label for an agent; a census over the registry fails when an MCP-open request gains an attribution field that no test proves is session-derived; and a resumed operation is attributed by its stored admission.

### refusal-site | low | Three refusals sit in the executor, after the submission is stored

Recording over a pending filing's observation (`src/cadrumo/application/modelo/local_observation_operation.py:157`) and both reader-locality refusals are decided in the executor because they depend on stored state or settings the resolver does not read. Nothing is written before they refuse. Review 2. Recorded, no action.

### certificate-path-text | low | Removing the certificate path from summaries is a literal replacement

`src/cadrumo/application/auth/auth_read_contracts.py:61` replaces two spellings of the full path in the health and probe summaries; a summary that quoted only the directory would pass. Not reproduced. Review 2. Open.

### agent-answers-own-review | medium | An agent can answer the review of an operation it submitted

The model reviews of classification and split are open to MCP and a review response is bound to the submitting session, so on the MCP frontend the agent that asked for the proposal is also the one that applies it. The governing records rule that a model's proposal stays a proposal until accepted and do not say by whom on this frontend. Noted by the orchestrator while reading review 2. Open: a decision for the admission rulings record.

### split-guard-stamp | high | The protection of a hand classification keyed on a last-writer stamp that operations open to MCP rewrite

`src/cadrumo/application/ledger/split_operation.py:306` recognises the person's work by `classified_by` being `manual`, and `src/cadrumo/application/ledger/actions_manual.py:1706` re-stamps every write to a classified row. IVA derivation, open to MCP, replaces a hand-classified row's IVA figures and its stamp, after which the split is admitted. The two model reviews never consult the stamp, and the agent that submits a review also answers it, so applying a proposal replaces a hand classification or splits such a parent. Exclude replaces any active row's classification and only an operation closed to MCP puts it back. Detach empties the attachments the split guard reads. A classification the person accepted from a model or a derivation is not recognised as theirs at all. Review 3. Resolved 2026-10-11: the row records the origin of its classification (the person, an agent, or a rule or the pipeline), changed only by a write that changes the classification or its tax figures, and one predicate in `src/cadrumo/domain/transactions/classification_origin.py` decides whether a classification is the person's. A row stored before the change reads as the person's when it is classified and not stamped by a rule. An execution admitted on MCP is refused, before any effect, IVA derivation, both model reviews (before the model is asked and at the commit), the manual split and exclude on such a row, replacing an existing invoice link, and detaching evidence an agent did not link. Deriving then splitting, and detaching then splitting, both end refused. A proposal the person accepted is protected like one they typed.

### bulk-precision | medium | The two-decimal rule was applied to shares and rates as well as amounts

`src/cadrumo/application/ledger/classify_requests.py:63` limits the business share and the IVA rate to two fraction digits, so a share of 0.333 and rates such as 0.052 and 0.075 are refused where the stored models admit them. Review 3. Resolved 2026-10-11: the limit predated this work on the command line, which capped every decimal at two digits, and the move into the operations had carried it faithfully. A share and a rate are now fractions between 0 and 1 with no scale bound, as the domain and the registry's rates require, on the command line, the terminal interface and in the operations; money keeps two digits. The classification guide states it.

### review-census-proof | medium | Two census proofs did not assert a stored actor

`src/cadrumo/entrypoints/tests/test_operation_mcp_attribution_census.py:117` names a unit test that replaces the commit function and asserts its argument for the two model reviews. Review 3. Resolved 2026-10-11: both entries point at a test that runs a review to its commit through the real supervisor, executor and store and reads the actor from the stored event, with only the proposal function stood in.

### provisioning-clients | low | Runtime probes of the same loopback endpoint still honour proxies

`src/cadrumo/application/provisioning_host.py:178` and the probes in `src/cadrumo/application/provisioning_runtime.py` build clients that read proxy settings. They probe the reader's availability and were not read for whether any request body carries document text. Review 3. Open.

### resumed-label | low | A person resuming an agent's operation is recorded under an agent label that carries the person's client

`src/cadrumo/entrypoints/runtime/operation_authority.py:140`. The operation was admitted for an agent and stays sealed and attributed as an agent's; the label's client part is the resuming session's. Documented in the code. Review 3. Recorded, no action.

## Recommendations

- For `surface-real-policy`: resolve each listed operation's real access policy in the surface test and keep a named, justified set for those that cannot be probed generically, as the admission test does.
- For `capture-output-root`: record, in a form a test enforces, every operation open to MCP whose request still carries a host path, so that a new one fails and the file-exchange Step removes the entries it settles. Whether a capture on the MCP frontend takes an output root at all is a decision for the file-exchange record, which is proposed and not yet accepted.
- For `reader-network-fact`: read which endpoint the two reviews use and record the wider answer if it is the configurable one.
- For `workflow-run-detail`: give the step detail a declared model, or pin its field names in a test so an addition is a visible contract change.
- For `reader-called-local`: decide whether an endpoint that is not on this machine makes a read off-machine for the purposes of consent on every frontend. That is a decision for the record that governs off-machine extraction consent, not for this plan.
- For `bulk-classify-second-route` and `split-one-way`: the admission rulings record should say whether replacing a classification the person made, or a figure the person stated, is sensitive on every route, so that single classification, bulk classification, a reaffirming rule run and a split are ruled alike.
- For `reader-proxy` and `reader-called-local`: one decision, in the record that governs off-machine consent, on what makes a read stay on this machine.
- For `agent-answers-own-review`: the admission rulings record should say which review responses an agent may give on the MCP frontend and which wait for the person.
- For `split-guard-stamp`: the rule now enforced is the conservative reading; the admission rulings record carries it as a row for the owner to confirm or relax, together with two neighbours it does not cover: an agent archiving or stashing the person's row, which restore undoes, and an agent replacing a usage ratio the person set, which the profile does not attribute.
