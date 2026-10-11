---
tags:
  - '#audit'
  - '#mcp-parity'
date: '2026-10-11'
modified: '2026-10-11'
body_schema: 'body-v2'
body_hash: 'sha256:b75e79c94db2ce43e24053804e18296f8b8bfda6bb5404933cf1e8e5c57e482c'
related:
  - "[[2026-10-10-mcp-parity-plan]]"
---

# `mcp-parity` audit: `Phase-close reviews of the MCP parity plan`

## Scope

Rolling log of the formal reviews of `2026-10-10-mcp-parity-plan`. Each review reads committed work against the plan and its governing decisions and traces the affected workflows across their interfaces.

Review 1, 2026-10-11: phase close of `P01` (Steps `S01` to `S11` and `S45`) and `P04` (Steps `S27` to `S29` and `S46`), commits `f72cc2f19e` to `a2aea88f1f`. Verdict: `P04` passes. `P01` required a revision to the packaged agent text of `S10`, applied the same day; it passes once the two medium findings are closed or assigned. Both were closed the same day, with the low findings, as recorded under each.

Checked and found sound in review 1: a definition cannot list MCP against its recorded decision, and each named sensitive act is refused by the real resolver on MCP only; no second route (batch, review response, resume, result read) reaches own-account writes, the Modelo 360 solicitud, the capability opt-ins, the prorrata elections, invoice removal, session reset or the census review; the surface is carried on both logins, inherited by child leases and fixed at first login; fourteen rows of change and network facts agree with their executors; the agent-facing results (evidence query, review summary, both timelines, filing record view, reader readiness) carry no bytes, host path or open payload; every subject declaration is held to its family's check; paged search and the generated command join behave as described; no suppressions, record citations or change-narrating comments in the reviewed commits. Not checked: 28 resolvers that need stored records to probe, the POSIX branch of the path guard, an end-to-end run on a real runtime, translations.

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

## Recommendations

- For `surface-real-policy`: resolve each listed operation's real access policy in the surface test and keep a named, justified set for those that cannot be probed generically, as the admission test does.
- For `capture-output-root`: record, in a form a test enforces, every operation open to MCP whose request still carries a host path, so that a new one fails and the file-exchange Step removes the entries it settles. Whether a capture on the MCP frontend takes an output root at all is a decision for the file-exchange record, which is proposed and not yet accepted.
- For `reader-network-fact`: read which endpoint the two reviews use and record the wider answer if it is the configurable one.
- For `workflow-run-detail`: give the step detail a declared model, or pin its field names in a test so an addition is a visible contract change.
- For `reader-called-local`: decide whether an endpoint that is not on this machine makes a read off-machine for the purposes of consent on every frontend. That is a decision for the record that governs off-machine extraction consent, not for this plan.
