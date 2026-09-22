# Shared session policy

Revision: 1.8. Owner: user-driven preflight coordinator. Applies to INCOME-01, IVA-01, RETENCIONES-01, ASSETS-01, LIVE-WALLET-01, CALENDAR-01, PROFILE-01, and LEDGER-01, including already-running implementation sessions. Revision 1.8 adds ledger lifecycle ownership and shared input-evidence coordination; mandatory discovery and execution cadence is unchanged.

## Identity and scope

Every session records a name, concrete goal, provider, lead model, cc number, UUID, worktree, brief revision, owned files, acceptance IDs, and dependencies. Unknown identifiers stay pending; never invent them. The coordinator supplies a provider-specific launch prompt when the provider is assigned. These briefs are provider-neutral.

User choices and authorized scope govern the work. An acceptance brief is not proof of implementation or permission to submit real filings. This preflight does not use the Vaultspec planning workflow. Preserve other sessions' work and use one writer per file or coupled surface.

## Agent levels

| Level | Codex | Claude | Responsibility |
| --- | --- | --- | --- |
| Lead | recorded per session | recorded per session | Own goal, bounded delegation, integration, context, and reporting |
| Adviser | Sol High | Fable 5.1 Medium | One named adviser per session; bounded architecture/optimization consultations only, no coding; idle otherwise |
| Principal | Terra High | Opus Medium | Complex implementation and analysis of already defined work; never define new architecture |
| Execution | Terra Max | Sonnet High | Bounded code manipulation, tool calls, process monitoring, log/data sanitization, and reporting |
| Discovery and factual audit | Luna Max | Consume Luna Max reports through the coordinated Codex discovery lane | Mandatory bounded codebase discovery, call/data-path tracing, existing-test mapping, and evidence-backed audit reports throughout the session |

Verify exact launcher model aliases before starting a roster; do not silently substitute unavailable models. Every delegated task has a name, directive, goal, allowed files/actions, dependencies, end condition, and report format. Execution and summarization workers spawn no children. Principal delegation is only to explicitly named bounded workers within the lead's concurrency budget. Advisers do not start independent work or delegate.

Escalate undefined invariants, conflicting authority, new architecture, or scope expansion with a compact evidence packet. Principal agents may analyze the conflict but may not choose new architecture. The adviser receives the narrowed question and returns idle after responding; the coordinator retains user-driven scope decisions.

## Context and implementation

Send each worker only this policy, its bounded assignment, relevant source-map excerpt, and necessary existing contracts. Avoid full transcript forks and repeated inventories. Read current files before editing; stale handoffs do not override the live tree.

### Mandatory discovery cadence

Codebase discovery and factual audit collection are delegated to named Luna Max agents. This applies during implementation and debugging as well as preflight. A lead must not repeatedly search the tree, read whole subsystems, or load many full files to build its own inventory. A higher-tier principal receives the relevant report and uses targeted source reads for its actual implementation/complex analysis; delegation must not merely move the same unrestricted context accumulation one level down.

1. Check the existing source map, last handoff, and previous discovery reports. Reuse evidence whose relevant source state has not changed.
2. Assign one concrete question and bounded surface to a Luna Max agent: for example, trace invoice retention into its period observation, or enumerate the installed TUI writers for those fields. State name, goal, files/entry boundary, exclusions, stopping condition, and report format. Reuse an existing agent for a related follow-up; no full transcript fork, recursive delegation, edits, test execution, or architecture decisions.
3. Parallelize only independent bounded questions within the session's resource budget. The lead can continue already-grounded work while reports are produced. Stop discovery when the question is answered; missing evidence is a reported gap, not a reason to traverse the whole repository.
4. Luna returns a short report, normally 300-600 words maximum, containing: question answered; inspected scope and source-state identity; facts with exact path:line references; traced callers/contracts; gaps/conflicts and confidence limits; proposed narrow checks marked NOT RUN; next necessary source reads. No full files, raw logs, long search output, or unrelated inventories. Smaller questions should return smaller reports.
5. The lead integrates the report and assigns a bounded implementation/audit decision task. Direct source reading is limited to the relevant function/contract, the code the reader will edit, an ambiguous cited claim, or final integrated verification. Verify consequential delegated findings against current code; do not repeat the entire exploration to verify the summary.
6. Ask the same discovery agent for a delta report when inputs change or one question remains. Do not restart a subsystem inventory. Architectural correctness and new architecture decisions remain with the principal/adviser roles; Luna collects evidence and identifies factual inconsistencies, not design authority.

For Claude sessions without a Luna invocation mechanism, route discovery to the coordinator's Codex/Luna discovery lane and consume its report. Record the concrete route/session identity. Do not silently replace Luna with the lead or a different model. If that route is not available, report the specific capability gap and continue work supported by existing evidence; do not disguise broad lead-driven exploration as conformance.

### Context checkpoints and report retention

Persist the compact report or its durable pointer in a session-owned handoff under .agents/session-briefs/handoffs/ (or the already assigned session handoff location). Leads need only the relevant report excerpt, not every report from every lane. Large detailed findings stay in an owned artifact; the returned message contains the bounded summary and pointer.

At phase transitions, before expecting large tool output, and whenever context pressure appears, update the session checkpoint: current goal/acceptance IDs; consumed brief/policy/pattern revisions; named agents and bounded tasks; relevant report pointers/source state; decisions and unresolved questions; owned files; running process handles and verification reservations; actual results; next bounded actions. Never retain secrets or raw financial payloads there.

After compaction or restart, resume from that checkpoint and inspect only the necessary deltas. Do not rediscover the codebase or rerun an owned process merely because its earlier output is absent from conversation context. Avoid unbounded searches and full-file concatenation; narrow the question in the discovery agent first when output would exceed its report budget.

### Adoption by active sessions

Before further broad discovery, an active lead reads this revision, records its adoption in the next checkpoint/status, names its Luna discovery agent or coordinated route, and states the next bounded discovery question. Inventory raw-context work already performed once; preserve useful findings in the checkpoint and resume from them. This is a cadence correction, not a request to restart implementation or repeat completed tests. Reading this instruction file or other instructions that the lead must personally read is not delegated codebase discovery.

Keep CLI and TUI independent; neither imports the other. Shared runtime behavior uses existing common contracts/composition. src/ never imports dev/. Use the existing secure persistence boundary for financial data and secrets. Automated fixtures use synthetic inputs. Explicitly user-authorized live read-only acquisition follows ACCEPTANCE-01's live exception; it does not authorize private data in fixtures or transcripts. Redact before reporting. Do not log secrets or pass them as command-line arguments.

Pin shared behavioral and fixture contracts before dependent frontend implementation. Record integration order. Changes to shared code, fixtures, configuration, dependencies, or generated authority invalidate affected evidence. No session independently repairs another session's owned shared files.

PROFILE-01 coordinates shared taxpayer facts, selection and profile persistence with the existing tax/calendar owners. A profile change does not authorize recalculation or rewriting of persisted filing history, nor a remote census modification. Record the selected entity and effective/evaluation context in dependent scenarios; do not silently replace missing facts with scenario-specific defaults. Reuse profile setup and unaffected verification across lanes while their relevant contracts remain unchanged.

LEDGER-01 coordinates shared invoice/transaction lifecycle, import replay, correction and evidence-link contracts. Existing tax/frontend ownership takes precedence until an explicit handoff; it does not acquire every file named in its map. Tax sessions retain liability and modelo-export semantics. Assign one owner for each cross-store write/reconciliation change and reuse shared lifecycle checks rather than rerunning each full tax lane. Preserve the difference between a local record correction, a rectifying invoice and an amended tax return.

## Verification coordination

Every acceptance driver follows [ACCEPTANCE-01](acceptance-pattern.md), the central pattern for dev/acceptance/ code, temporary settings, isolated run roots, frontend execution, credentials, cleanup, and receipts. Read it before creating a family-specific runner; do not fork the pattern or treat the current income implementation as automatically conformant.

The coordinator maintains one reservation list across all briefs, not one list per tax family. Reserve exact checks before execution. Use node IDs/paths and explicit markers; -n0 for small checks unless assigned a different worker budget. Pytest's default -n auto and excluded capability markers must not silently determine the scope or resource budget.

One named owner runs each applicable aggregate gate after integrated changes. Full lane checks are never duplicated concurrently, and completed evidence is reused while its relevant inputs remain unchanged. Brief-local ownership cannot override a reservation made for another brief. Do not launch broad test collection simply to choose a small test.

Existing pytest logs and dev.test_runs.command provide execution records, not cross-session scheduling. Record source/dependency state, exact command, selection/exclusions, exit status, counts, and sanitized artifact pointers. Retain a compact durable summary because logs are temporary. A started, timed-out wait, interrupted, or still-running process is not a passing result; monitor the existing owned process rather than relaunching it.

Reservations record owner, process/tool handle, status, and last observation. Confirm process state before reassigning interrupted work; expiry alone does not permit duplicate execution. Give shared resources such as OS keychain, databases, render output, ports, or generated files explicit exclusive ownership when needed.

Live acquisition additionally reserves the taxpayer's authentication session and browser context. One owner starts one authentication request; other sessions reuse safe evidence instead of generating competing mobile prompts. User approval, cancellation and expiry are explicit checkpoints. Never turn an auth retry into an unbounded polling/login loop. A successful authentication is not proof of a successful protected-service extraction.

Protected notification metadata, content access, acknowledgement and response are separate capabilities. Opening content can have legal effects even when implemented as a read request. A calendar/reconciliation brief or wallet-read authorization does not authorize that access; obtain explicit action-specific direction before a legally consequential operation. Existing live-testing blockers remain in force until separately resolved.

## Report format

Status: complete | partial | blocked.
Outcome by acceptance ID.
Changed files.
Verification: exact command/selection, exit status/counts, relevant source state, artifact pointer.
Uncovered cases and remaining risks.
Decision packet if needed: conflicting contract, evidence, bounded options, impact.
Next bounded action.

Report at meaningful milestones, blockers, and handoff. Do not send raw logs or repeated unchanged inventories to leads. Completion claims distinguish proven, failed, blocked, and not exercised.
