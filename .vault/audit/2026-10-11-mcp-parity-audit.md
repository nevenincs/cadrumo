---
tags:
  - '#audit'
  - '#mcp-parity'
date: '2026-10-11'
modified: '2026-10-12'
body_schema: 'body-v2'
body_hash: 'sha256:92886fb728f3d95392e42b305132a527f6f85863b91d0aef28c7ee64bdff9806'
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

Review 4, 2026-10-11: re-review of `3e8f9e3725` and `7e6226e084`, base `ece30ed551`. Verdict: revision required for `S35`. The agent side of the classification-origin rule holds: every classifying write goes through one stamper, each executor refuses before any effect, and deriving, detaching, linking or archiving and restoring before a split all end refused; stored rows load safely and the filing snapshot fingerprint is unchanged. The decimal fix holds and the census proofs for the reviews now read a stored actor.

Review 5, 2026-10-11: re-review of `d4c6b485a5`, base `3e8f9e3725`. Verdict: revision required for `S35`. Ownership by confirmation holds in every direction probed, archive, stash and restore hold, and the review commit holds. The exemption that lets a confirmation through the finalised-revision guard does not.

Review 6, 2026-10-11: confirmation review of `d632ec6246`, base `d4c6b485a5`. Verdict: pass. Fifty single confirmations on sealed rows, with share, prorrata and locally-filed cases, left the stored row identical apart from its record fields, with identifier, fingerprint and staleness unmoved; every real change was refused with nothing stored; bulk agrees with single row by row; an agent's purchase evidence on the person's row is refused through the real runtime and no attach, detach or relink sequence flips a person's row.

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

### origin-not-taken | high | A person who confirms or completes a classification did not become its owner

`src/cadrumo/application/ledger/actions_manual.py:1146` returns without a write when the person classifies a row with the value an agent gave it, so the origin stays the agent's and an agent can still replace or exclude it; on a row stamped by a rule or a model the same act is refused as changing nothing. `src/cadrumo/domain/transactions/classification_origin.py:23` omits five fields the classification patch sets, so a person setting only the counterparty country leaves the origin unchanged, and `src/cadrumo/application/ledger/agent_row_guard.py:103` compares only the same fields. Review 4. Resolved 2026-10-11: a person's write that names any field of one declared set takes the row whether or not a value changes, and is recorded as a classification; a test holds the set equal to what the classification, update and bulk patches can set; the second guard compares the same set. A write that moves no value leaves the row's fingerprint unchanged.

### archive-stash-open | medium | An agent could archive or stash a row carrying the person's classification

`src/cadrumo/application/ledger/lifecycle_mutation_operation.py:237` guards exclude only. An archived or stashed row leaves every calculation until someone restores it, and calculation is open to MCP. Review 4. Resolved 2026-10-11: an execution admitted on MCP is refused archiving or stashing a row whose classification is the person's, and restoring a row whose archived or stashed state the person set, read from the row's lifecycle record; a row without that record reads as the person's.

### review-commit-baseline | low | The review's commit-time check read the captured baseline, not the current row

`src/cadrumo/application/ledger/llm_review_execution.py:413`. The writers still protect the current row, but in plain classification mode that refusal comes after the effect is declared unknown. Review 4. Resolved 2026-10-11: the commit reads the stored row before any effect.

### decimals-range-placement | low | The entry request models enforce range and canonical text in different places

Classification refuses a rate above 1 at the request; update accepts it there and relies on the domain's refusal (`src/cadrumo/application/ledger/update_contracts.py:116`); add accepts a trailing zero that classification refuses (`src/cadrumo/application/ledger/ledger_add_contracts.py:110`). None is new and nothing wrong is stored. Review 4. Open.

### review-in-flight-upgrade | low | A model review captured before the origin field existed is refused as a conflict

`src/cadrumo/application/ledger/llm_review_operand.py:128` re-serialises the baseline row, which now carries the origin. Only test profiles hold data. Review 4. Recorded, no action.

### confirm-moves-sealed-fingerprint | high | A same-value confirmation of a row cited by a finalised revision was written in another decimal representation and turned the revision stale

`src/cadrumo/application/ledger/actions_manual.py:935` exempts a write from the finalised-revision guard when its values compare equal (`src/cadrumo/application/ledger/actions_common.py:407`), while the row fingerprint hashes the decimal text (`src/cadrumo/application/aggregation/ledger_filing_snapshot.py:158`). The request models admit only stripped decimals and stored rows carry trailing zeros, so a confirmation of `500.00` stored `500` and a verified revision became stale. Before `d4c6b485a5` the guard refused the write. Review 5. Resolved 2026-10-11: when every value compares equal and only the origin changes, the stored row is written back with its origin, stamp, reason, lineage and modification time replaced and every other member untouched, and the exemption admits the write only when the built replacement keeps the transaction identifier and the row fingerprint. A write that changes a value on a sealed row is still refused.

### evidence-id-declared-no-tax | medium | Purchase evidence was declared as bearing on no tax although it changes how a row is calculated

`src/cadrumo/application/ledger/tests/test_classification_decision_fields_are_complete.py:51` excludes `purchase_invoice_evidence_id` from the fields that make a classification, while `src/cadrumo/application/ledger/actions_common.py:395` and `src/cadrumo/application/aggregation/renta_ledger.py:929` say purchase evidence turns an incoming row into a refund and lets the invoice's figures override the row's own. An agent's attach of purchase evidence to a row the person classified was stored. The route predates the commit. Review 5. Resolved 2026-10-11: the purchase-evidence link is in the set of fields that make a classification, and an execution admitted on MCP is refused linking purchase evidence to a row the person classified, before any effect and again at the writer; supplementary attachments stay open.

### bulk-single-disagree-on-sealed | low | Bulk confirmation of a sealed row was refused where single confirmation was admitted

`src/cadrumo/application/ledger/actions_classification.py:268`. Review 5. Resolved 2026-10-11: bulk classification passes its blockers to the same builder as single classification.

### confirmation-resets-model-rejection | low | A confirmation counts as the latest model decision

`src/cadrumo/application/ledger/list_query.py:47` and `view_operation.py:93` read the last classified-or-rejected event, so after a confirmation an earlier rejection stops showing. Any classification made by hand already did the same. Review 5. Recorded, no action.

### restated-amount-takes-row | low | Naming an unchanged amount beside a description takes the row

The amount is in the declared set, so a person's update or bulk table that restates it takes every restated row and closes it to agents. Review 5. Recorded for the owner with the rule itself.

### verify-counts | low | Recorded verification counts did not name every failing test

Ledger rows give counts such as 7054 of 7058 without naming the tests outside the count. They are the known failures in other work, listed in the ledger note of `S45` and in later notes: four form-layout tests, four reporting no usable authority, one Modelo 184 context key, one Modelo 100 export version, one bulk-classify save count, and one command-line test expecting an English message; two cases that timed out under load were re-run alone and pass. Review 5. Resolved by this entry.

### evidence-only-compares-stamp | medium | Evidence could not be attached to a sealed row that a rule stamped

`src/cadrumo/application/ledger/actions_common.py:401` compares the classification stamp when deciding that a write only adds evidence, and an attach always re-stamps the row, so a person linking evidence to a sealed row stamped by a rule is refused with the finalised-revision message, which defeats the documented remedy for an export evidence refusal on such rows. Predates the reviewed commit. Review 6. Resolved 2026-10-11: the decision that a write only adds evidence no longer compares the stamp, which the fingerprint does not cover; a person attaches a supplementary document or purchase evidence to a sealed row a rule stamped, and a supplementary attach leaves the row's origin as it was.

### purchase-link-outside-fingerprint | medium | The purchase-evidence link bears on tax but the filing fingerprint does not cover it

`src/cadrumo/domain/transactions/classification_origin.py:48` declares the link a field that decides a classification, while `src/cadrumo/application/aggregation/ledger_filing_snapshot.py:121` leaves it out of the fingerprint, so a person's link to a sealed row is admitted, reports the cited revision once, and the staleness evaluation stays false afterwards. Review 6. Open: covering the link needs a new version of the fingerprint's field set, which is a decision for the record that governs filing snapshots.

### blank-purchase-id-takes-row | low | A whitespace-only purchase evidence identifier linked nothing yet took the row

`src/cadrumo/application/ledger/actions_manual.py:261`. Review 6. Resolved 2026-10-11: a blank identifier is read as absent in the request model and at the writer, and a link set to nothing is not a decision.

### sealed-confirmation-with-reason | low | A confirmation carrying a new reason is refused on a sealed row without naming the field

`src/cadrumo/application/ledger/actions_manual.py:1024`. The reason is stored as a note, which is a change to the row. Review 6. Resolved 2026-10-11: the refusal stays and its context names the fields that differ, by name only.

### test-hygiene | low | One assertion on the test's own data and helpers imported by private name

`src/cadrumo/application/ledger/tests/test_classification_decision_fields_are_complete.py:94` and `src/cadrumo/adapters/persistence/profile/tests/test_confirmation_keeps_a_sealed_row_at_the_ledger_writers.py:58`. Review 6. Resolved 2026-10-11: the assertion checks production code and the shared helpers live in a support module under public names.

### refusals-withdrawn | high | Findings resolved by refusing an agent what the command line can do no longer apply

The owner ruled on 2026-10-11 that MCP never refuses anything the command line can do and that the three frontends are at parity; `2026-10-11-mcp-parity-full-parity-adr` records it and supersedes the admission rulings. Six reviews recorded here had been read as asking for the opposite, and several resolutions above added a refusal, a withheld part of a result or a held-back variant on the MCP frontend. Those resolutions are reversed in the tree: an operation carries no list of frontends, and no resolver, executor, guard or runtime check decides by frontend. Closed as not applicable, in the part that depended on the frontend: `bulk-classify-second-route`, `split-one-way`, `split-guard-stamp`, `archive-stash-open`, `agent-answers-own-review`, `result-sealing-by-executor`, `refusal-site`, `reader-called-local`, the refusal half of `reader-proxy`, and `capture-output-root`, whose recommendation named a file-exchange record that is rejected. What stands on every frontend alike: the loopback client that ignores proxy settings, the decimal rule, the recorded origin of a classification as a fact that refuses nothing, a confirmation that writes a sealed row back as stored, the session-derived actor, and the typed subject reference. A reviewer's observation that an agent has a second route to an act is a description of parity, not a defect.

### reset-and-storage-acts-root | high | The reset and storage acts took their tree from ambient settings while the fence came from the served root

`src/cadrumo/entrypoints/runtime/installation_reset.py:44` fenced the profiles of the root the runtime serves and then reset the tree `load_settings()` named; `installation_storage.py:47` had the same shape. Review 7, of phases `P08` and `P09`, reopening `S55`. Resolved 2026-10-12: every act runs inside one served-root scope on the exchange, shown with a runtime over one root while ambient settings name another. In an installed runtime the two could not differ, because the manager clears the child's environment and pins the root.

### reset-fallback-on-unavailable | medium | The command line reset in process on any unavailable answer, which three paths give while a runtime is alive

`src/cadrumo/entrypoints/cli/runtime_installation.py:97` and `src/cadrumo/entrypoints/cli/config/reset_cli.py:116`. A busy pipe, missing package metadata and a failed endpoint release all read as no runtime. Review 7. Resolved 2026-10-12: the endpoint reports absent, held or indeterminate, and the command works in process only on absence. Not run on macOS, where a socket left by a crashed runtime reads as indeterminate.

### tui-operations-idempotency-key | medium | The terminal interface's Operations form could not carry the replay key the command line and MCP carry

`src/cadrumo/entrypoints/tui/operations/run_screen.py:410`. Review 7. Resolved 2026-10-12: an optional field, offered for the operations that can take a key.

### plan-prose-contradicts-the-rule | medium | The plan's Verification and Parallelization sections still stated the rejected rules as requirements

Review 7. Resolved 2026-10-12: both sections state the parity criteria.

### decision-coverage | medium | The plan did not link the protocol record this work changed, and four new mechanisms had no record

Review 7. Resolved 2026-10-12 in part: the plan links `2026-07-08-mcp-protocol-hardening-adr` and `2026-07-31-mcp-sdk-major-carry-adr`, and the full-parity record lists the mechanisms in its Implementation section as implementation, not commitments. Open: whether the sessionless installation door, the worker's server-start instruction, the held-secret records and the shipped contract document become commitments of a record of their own.

### once-secret-consumed-early | low | A one-use held secret was deleted before the call naming it was validated or sent, and without a lock

`src/cadrumo_harness/mcp/held_secrets.py:213`. Review 7. Resolved 2026-10-12: taken last, immediately before the send, under the store's cross-process lock.

### door-refusal-read-as-no-effect | low | An error inside an act's handler after its change began was answered as a refusal

`src/cadrumo/entrypoints/runtime/installation_door.py:378`. Review 7. Resolved 2026-10-12: a changing handler marks where its change begins, a later error settles as failed with effect unknown, and a changing act that completes without the mark fails.

### request-fault-message-heuristic | low | The value-free promise of a request fault rested on matching the message against the value

`src/cadrumo/core/request_faults.py:94`. Review 7. Resolved 2026-10-12: a registry-wide test fails on a validator message that interpolates anything but a field name or a constant; eleven offenders were fixed.

### declaration-proof-selection | low | The proof named the actor as the one difference and dropped a second recorded one

`src/cadrumo/entrypoints/tests/test_declaration_through_mcp_equals_command_line.py:92`. Review 7. Resolved 2026-10-12: the origin of a classification is asserted as the second intended difference, and event payloads and notices are compared.

### gate-limits | low | The counterpart gate classified by the first way that applied and checked existence only

`src/cadrumo/entrypoints/cli/tests/command_frontend_counterparts.py:254`. Review 7. Resolved 2026-10-12 in part: each in-process pair names its proving test and the gate fails when it is missing; a reached operation with no resolver fails the gate. Open: the pairs declared unproven, which are the bare command and the session-door commands, and the censo import, proven for refusal only because the shipped parser refuses every document.

### spreadsheet-push-unavailable | medium | The spreadsheet push command names an operation no frontend can submit

`src/cadrumo/entrypoints/cli/command_operation_table.py:231` records that `app modelo spreadsheet push` reaches `export.google-sheets`, which is composed with no access resolver (`src/cadrumo/entrypoints/tests/test_google_review_enrollment.py:17`), so every frontend is answered that the operation is unavailable. Found while resolving `gate-limits`, read from the code and not run. Equal on all three frontends, so not a parity gap. Open: whether the command should submit the reviewed publication instead is a question for the record that governs the Google export.

### input-interaction-wording | low | Two Steps said every interaction kind can be answered; input and choice cannot, on any frontend

`src/cadrumo/application/operations/observation.py:319`. Review 7. Resolved 2026-10-12: the plan's Verification section says so.

### admission-wait-spin | low | The admission wait re-read the profile binding from disk under the connection-wide guard every ten milliseconds

`src/cadrumo/entrypoints/runtime/profile_connection_admission.py:119`. Review 7. Resolved 2026-10-12: it retries only the retirement, backs off, and holds the guard only to notice a removed host.

### placement-and-private-reach | low | A generator of shipped data lived in a tests package, and the installation client drove private members of the connection

Review 7. Resolved 2026-10-12: the writers are under `dev/harness_data`, and the transport has a public held exchange.

### wide-pass-gates | medium | A wide test pass showed four gates failing because of code this work added

Five exception classes rooted only at a builtin base; a test naming a storage location with a path literal; the terminal interface composing the operation registry outside the installed session; a test pinning a refusal's members without the request faults. Found 2026-10-12 after the phase closed. Resolved the same day.

## Recommendations

- The recommendations below that ask the admission rulings record, the file-exchange record or the approval record for a decision are withdrawn with `refusals-withdrawn`: the first is superseded and the others are rejected, and the owner's ruling leaves no such decision open. `reader-network-fact`, `workflow-run-detail`, `surface-real-policy` and `purchase-link-outside-fingerprint` are unaffected.

- For `surface-real-policy`: resolve each listed operation's real access policy in the surface test and keep a named, justified set for those that cannot be probed generically, as the admission test does.
- For `capture-output-root`: record, in a form a test enforces, every operation open to MCP whose request still carries a host path, so that a new one fails and the file-exchange Step removes the entries it settles. Whether a capture on the MCP frontend takes an output root at all is a decision for the file-exchange record, which is proposed and not yet accepted.
- For `reader-network-fact`: read which endpoint the two reviews use and record the wider answer if it is the configurable one.
- For `workflow-run-detail`: give the step detail a declared model, or pin its field names in a test so an addition is a visible contract change.
- For `reader-called-local`: decide whether an endpoint that is not on this machine makes a read off-machine for the purposes of consent on every frontend. That is a decision for the record that governs off-machine extraction consent, not for this plan.
- For `bulk-classify-second-route` and `split-one-way`: the admission rulings record should say whether replacing a classification the person made, or a figure the person stated, is sensitive on every route, so that single classification, bulk classification, a reaffirming rule run and a split are ruled alike.
- For `reader-proxy` and `reader-called-local`: one decision, in the record that governs off-machine consent, on what makes a read stay on this machine.
- For `agent-answers-own-review`: the admission rulings record should say which review responses an agent may give on the MCP frontend and which wait for the person.
- For `split-guard-stamp`: the rule now enforced is the conservative reading; the admission rulings record carries it as a row for the owner to confirm or relax, together with two neighbours it does not cover: an agent archiving or stashing the person's row, which restore undoes, and an agent replacing a usage ratio the person set, which the profile does not attribute.
- For `purchase-link-outside-fingerprint`: decide, in the record that governs filing snapshots, whether the fingerprint's field set gains the purchase-evidence link in a new version, so that linking evidence to a sealed row keeps the revision reported as stale.
- For `decision-coverage`: decide whether the four mechanisms are recorded as commitments, in an amendment to the full-parity record or in records of their own, before another product builds on any of them.
- For `spreadsheet-push-unavailable`: verify by running the command, and decide in the record that governs the Google export which operation it submits.
- For `gate-limits`: give the session-door commands a test that holds each command's output to the session tool's reply, so the pairs can leave the unproven list.
