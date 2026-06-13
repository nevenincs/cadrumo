---
tags:
  - "#plan"
  - "#export-first"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-18-auth-provider-ecosystem-research]]"
---

# export-first-roadmap-plan

Concrete GitHub operations to execute the export-first ADR. Each row is a single atomic operation against the `wgergely/aeat` repository. Execution is gated on explicit user approval for each group.

## group A — label taxonomy additions (7 new labels, no-risk)

Add the missing labels so every subsequent issue can be categorised:

| name | color | description |
|---|---|---|
| `charter` | `b60205` | Policy / charter / direction-setting meta-issue |
| `ux` | `e99695` | User-experience issue affecting non-developer end users |
| `ux:error-messages` | `fbca04` | Error-message quality, remediation hints, actionability |
| `ux:cli-output` | `fbca04` | CLI output formatting, consistency, discoverability |
| `area:submission` | `c2e0c6` | AEAT submission pipeline (preflight, dry-run, export, live-submit) |
| `area:review` | `c2e0c6` | Human-in-the-loop review and approval state |
| `area:export` | `c2e0c6` | AEAT-importable file output (PDF / modelo-specific formats) |

## group B — milestone refactor (3 renames + 3 description rewrites)

Milestones keep their numbers so existing issue references remain valid. Titles and descriptions change.

### B1 — milestone #4 `0.2.0-alpha`

**Old title:** `0.2.0-alpha`
**Old description:** _"Alpha: first end-to-end filing of at least one modelo against AEAT, manual review gate before submission. Multi-modelo schema coverage. Audit trail complete."_

**New title:** `0.2.0-alpha — produce, verify, export`
**New description:**
> Alpha milestone: the user can ingest financial data, classify it, compute at least Modelo 130 via the formula engine, review casilla-by-casilla with full operand traces, explicitly approve the draft, and export an AEAT-importable file. Live AEAT reads (expedientes, justificantes, datos fiscales, inbox) are functional. **Live AEAT submission writes are NOT in scope** — the user self-files via the AEAT portal using the exported file. See ADR `export-first`.

### B2 — milestone #5 `0.3.0-beta`

**Old title:** `0.3.0-beta`
**Old description:** _"Beta: unattended filing for the supported modelo set, divergence alerting, full self-heal allowlist enforcement, hardened security posture, documented runbook."_

**New title:** `0.3.0-beta — export hardening + live-read verification`
**New description:**
> Beta milestone: export surface hardened across all supported modelos (130 + 303 + 390 minimum). Live-read verification loop closes: the tool fetches resulting justificantes after a manual AEAT upload and verifies draft checksums against stored state. Divergence alerting works end-to-end. Security posture documented. **Live AEAT submission writes remain gated off by default.**

### B3 — milestone #6 `1.0.0`

**Old title:** `1.0.0`

**New title:** `1.0.0 — live filing opt-in`
**New description:**
> GA milestone: live AEAT submission writes become opt-in for users who explicitly accept the charter risks (#116, #117). Full unattended-filing path, live-write audit trail, rolling charter compliance audit. Until this milestone closes, the default install of the tool never calls AEAT's submit endpoint.

## group C — new issues to file (~12 issues)

### C1 — CHARTER: Re-anchor product to produce-verify-export; disable live AEAT submission as near-term goal

**Labels:** `charter`, `type:chore`, `blocker`, `domain:aeat-remote`, `area:submission`
**Milestone:** `0.0.2-foundations` (immediate)
**Body (paraphrased):**
> This issue ratifies ADR `export-first`. The project re-anchors to produce-verify-export. Live AEAT submission writes are removed as a default feature; they stay code-complete but are hidden, env-gated, and deferred to milestone 1.0.0. Live AEAT reads remain on the critical path.
>
> **Blocks:** this issue must be closed before the B-group milestone renames land. Links to #116 (safety charter), #117 (env-gated hardening), and the ADR.
>
> **Acceptance:**
> - ADR merged into `.vault/adr/`
> - Milestone renames applied (B-group)
> - `aeat submission submit` is not in `aeat --help` output on the default install
> - README explicitly states "this tool does not submit to AEAT; it produces an importable file you upload yourself"

### C2 — Hide `aeat submission submit` behind env-only opt-in; remove from default `--help`

**Labels:** `type:chore`, `area:submission`, `blocker`
**Milestone:** `0.0.2-foundations`
**Body:**
> Relocate `aeat submission submit` to a dedicated `aeat live-submit` Typer group with `hidden=True` on the group and every subcommand. Activation requires `AEAT_LIVE_SUBMIT_ENABLED=1` (already defined via #117) AND an additional install-time opt-in: `AEAT_ALLOW_LIVE_SUBMIT_OPT_IN=1`. With both unset, `aeat live-submit submit` exits with a non-jargon message: _"Live AEAT submission is disabled by default. Use `aeat submission export` to produce an importable file."_
>
> **Out of scope:** deleting the code. Preflight, dry-run, and submit stay — only the entry point changes.

### C3 — EPIC: `aeat submission export` — produce AEAT-importable files from approved drafts

**Labels:** `epic`, `type:feature`, `area:submission`, `area:export`
**Milestone:** `0.2.0-alpha`
**Body:**
> Top-level EPIC for the export surface that replaces live submission in the default happy path. Children:
>
> - C3a: Research — what file formats does AEAT's portal accept for each modelo? (PDF, OBI XML, proprietary XML, CSV). Document findings as an `.vault/research/` artifact.
> - C3b: Implement `aeat submission export --modelo 130 --period 2025Q1 --format pdf|obi-xml|json --output <path>`
> - C3c: Ensure per-modelo export fidelity: round-trip test (export → parse → compare to draft)
> - C3d: Optional Drive upload destination
> - C3e: Compatibility checklist — manual test of uploading each exported format to the real AEAT portal for each modelo
> - C3f: Document export flow in README and getting-started

### C4 — EPIC: `aeat review` surface — explicit human approval state on drafts

**Labels:** `epic`, `type:feature`, `area:review`, `ux`
**Milestone:** `0.2.0-alpha`
**Body:**
> Top-level EPIC for the human review/approval gate. Children:
>
> - C4a: Extend `FilingDraftStatus` with `APPROVED` state. `EXPORTED` and any future `live-submit` transitions require `APPROVED`.
> - C4b: `aeat review show --modelo 130 --period 2025Q1` — render casilla-by-casilla table with `kind`, `source`, the formula expression, and operand values inline (no separate `aeat formulas compute` needed)
> - C4c: `aeat review approve <draft>` — interactive confirmation prompt; persists `approved_at`, `approved_by`, `review_checksum` to the draft
> - C4d: `aeat review unapprove <draft>` — rescind approval if inputs change
> - C4e: Block `aeat submission export` when draft is not `APPROVED`
> - C4f: Detect stale approval: if underlying catalogue / formulas / inputs change after approval, mark draft `APPROVAL_STALE` and require re-review
> - C4g: `aeat review diff <draft>` — show casilla-level diff between current and last-approved snapshot

### C5 — Regression prevention: no new code path may introduce a default-enabled write to AEAT

**Labels:** `charter`, `type:chore`, `blocker`, `domain:aeat-remote`
**Milestone:** `0.0.2-foundations`
**Body:**
> A static check / pre-commit hook that fails if any new code path (a) calls a POST/PUT against an AEAT endpoint without being inside the `aeat.adapters.outbound.aeat.export.live_submit` module, and (b) is discoverable from the default CLI. Extends the existing #118 static audit.

### C6 — Publish `ROADMAP.md` anchored to Kent-centric milestone questions

**Labels:** `type:chore`, `domain:docs`, `ux`
**Milestone:** `0.0.2-foundations`
**Body:**
> New `ROADMAP.md` in repo root with one section per milestone, each answering: _"What can Kent do at the end of this milestone that he could not do at the start?"_ Cross-links to ADR `export-first` and the Kent journey audit.
>
> - 0.0.2-foundations → Kent can install, configure, and see his situation
> - 0.1.0-pre-alpha → Kent can ingest his financial data and reconcile it with live AEAT reads
> - 0.2.0-alpha → Kent can compute, review, approve, and export a Modelo 130 that AEAT will accept via manual upload
> - 0.3.0-beta → Kent has 303 and 390 coverage, stale-approval detection, and justificante re-sync verification
> - 1.0.0 → Kent can (optionally) enable live AEAT submission behind the charter gate

### C7 — Retitle #112 (was "FIRST LIVE FILING") to "export-readiness gate"

**Operation:** edit issue #112
**New title:** `Rolling pipeline audit: 0.2.0-alpha gate (export-readiness)`
**Body prefix:** add _"Retitled 2026-04-17 per ADR `export-first`. This gate certifies export-readiness, not live filing."_

### C8 — Retitle #123 (was "before first live filing") to "before first export-readiness gate"

**Operation:** edit issue #123
**New title:** `Structural audit: 0.2.0-alpha milestone gate (before export-readiness)`

### C9 — Retitle #113 (was "unattended filing") to "export hardening + live-read verification"

**Operation:** edit issue #113
**New title:** `Rolling pipeline audit: 0.3.0-beta gate (export hardening + live-read verification)`

### C10 — Clarify #70 EPIC scope: READ loop is primary, WRITE loop is deferred

**Operation:** comment on #70
**Comment body:** _"Per ADR `export-first` (2026-04-17): the READ half of this loop remains the critical path. The WRITE half is deferred to milestone 1.0.0 and is gated by #116/#117. Update sub-issues accordingly."_

### C11 — Close #158 as superseded by #C3 (export surface replaces deferred live validation)

**Operation:** comment on #158 and close
**Comment body:** _"Superseded by the `aeat submission export` EPIC C3 — live validation is no longer the blocking concern. Reopen only if the 1.0.0 live-filing opt-in is green-lit."_

### C12 — Acknowledge #150 / #151 stay in force but rescope

**Operation:** comment on #150 and #151
**Comment body:** _"Per ADR `export-first`: the #117 live-submit boundary remains valid but becomes an opt-in-only boundary. Tests should exercise the export path as the primary happy path; live-submit tests move to 1.0.0 scope."_

## group D — Kent journey walls (new issues)

Each issue is a single Kent wall from the audit. All get `ux` label. Walls already tracked get a comment on the existing issue instead.

### D1 — Wall 5: `AEAT_OUTPUT_LANGUAGE` default is `hu`; Spanish users get Hungarian output

**Labels:** `type:bug`, `ux`, `area:config`
**Milestone:** `0.0.2-foundations`
**Body:** one-line fix. `env/.env.example:148` and `src/aeat/config.py` Settings default. Switch default to `es`. Add a comment explaining the three supported languages.

### D2 — Wall 0: Root CLI tagline is DevOps-facing, not tax-user-facing

**Labels:** `type:chore`, `ux`, `ux:cli-output`, `domain:docs`
**Milestone:** `0.0.2-foundations`
**Body:** rewrite the root `help` text and README opening paragraph so that the first sentence a user reads is "file your Spanish tax returns (modelos 130, 303, 390, ...) from the command line." Current wording advertises GCP/Google Workspace, which is infrastructure detail.

### D3 — Wall 1: `just bootstrap` runs steps in the wrong order

**Labels:** `type:bug`, `area:scaffolding`, `ux`
**Milestone:** `0.0.2-foundations`
**Body:** `just bootstrap` calls `gcloud-auth` before the prerequisite `gsuite-oauth-client` has run. Either (a) reorder, or (b) detect the missing `env/oauth-client.json` and auto-run `gsuite-oauth-client` inline with a prompt. The first `just bootstrap` on a clean machine should succeed or offer a one-key continuation, not exit with an unexplained error.

### D4 — Wall 2: GCP-project creation is an undocumented prerequisite

**Labels:** `type:chore`, `domain:docs`, `ux`, `area:auth`
**Milestone:** `0.0.2-foundations`
**Body:** add a README section and a printed onboarding hint explaining that the tool needs a GCP project (free tier) for Drive/Sheets/Docs, why it needs one, and exactly how to create one (link to Cloud Console, screenshots if possible). Runs before any `just` recipe that touches GCP.

### D5 — Wall 3: "scratch" vs "real" Drive resources are confusing

**Labels:** `type:chore`, `domain:docs`, `ux`
**Milestone:** `0.1.0-pre-alpha`
**Body:** `aeat bootstrap` creates scratch Drive/Sheets/Docs. Clarify in the CLI output and docs that these are sandbox resources for the tool's own state — the user's real invoices remain wherever they are, and will be referenced, not replaced.

### D6 — Wall 6: Cert passphrase has no documented home

**Labels:** `type:chore`, `area:auth`, `domain:docs`, `ux`
**Milestone:** `0.0.2-foundations`
**Body:** the setup wizard / README captures the *name* of the env var holding the cert passphrase, but never explains whether the user should export it in the shell, add it to `env/.env`, or use a keyring. Add a section recommending (in order): OS keyring, shell export with a comment about session scope, and `env/.env` only as a last resort. Update the wizard to offer the first two.

### D7 — Wall 9: `aeat status` is a broken facade; every subcommand exits 2 with "#8 not yet landed"

**Labels:** `type:bug`, `ux`, `ux:error-messages`, `domain:aeat-remote`
**Milestone:** `0.0.2-foundations`
**Body:** the group is the most obvious user entry point for "check my situation" but ships as six hidden stubs returning developer-internal error strings. Until #141/#8 land, every subcommand should print a human message pointing to the relevant issue/milestone, NOT exit 2 with internal jargon. After #8/#141 land, the group becomes the primary live-read dashboard.

### D8 — Wall 10: `aeat deadlines list --profile` requires hand-authored tax-law-literate JSON

**Labels:** `type:feature`, `ux`
**Milestone:** `0.0.2-foundations`
**Body:** the setup wizard must generate a valid `AutonomoProfile` JSON by interviewing the user once. Ideally `aeat deadlines list` auto-reads the wizard-generated profile with no `--profile` flag required. Closes the gap left by the #61-merge-without-wizard state.

### D9 — Wall 12: `ObligationStatus.FILED` is never set; OVERDUE is unreconciled

**Labels:** `type:feature`, `domain:mediation`, `ux`
**Milestone:** `0.1.0-pre-alpha`
**Body:** (may be partially tracked by #169). Add the reconciliation layer that joins the deadline engine's expected-obligations against live-read expedientes (once #8 lands) AND the local submission store. Produce a correct "missed filings" report that distinguishes "date passed" from "user is genuinely late."

### D10 — Wall 13: `aeat inbox` is a local ledger, not a sync — stays disabled until live fetch lands

**Operation:** comment on #170
**Comment body:** _"Kent journey wall 13: until live fetch is wired, `aeat inbox fetch` is strictly worse than a manual portal visit because it asks the user to transcribe notifications twice. Propose gating `aeat inbox fetch` behind a `--from-file` flag explicitly so the local-ledger mode is opt-in, and surfacing a clear 'not yet implemented — run X instead' message when the user runs `aeat inbox fetch` with no flags."_

### D11 — Wall 14: `aeat financial ingest` is read-only; no T1→T2 persistence bridge

**Labels:** `type:feature`, `pipeline:T1-ingest`, `pipeline:T2-normalize`, `blocker`, `domain:financial-input`
**Milestone:** `0.1.0-pre-alpha`
**Body:** `aeat financial ingest` parses CSV/XLSX/OFX and prints `RawTransaction` JSON lines to stdout, but never writes the catalogue. Add a `--persist` flag (default ON for interactive mode) that writes parsed records into `transactions.json` using the existing service layer. Without this, T1 feeds nothing into T2, and the entire downstream pipeline is disconnected from real data.

### D12 — Wall 15: No bulk or rule-based categorisation

**Labels:** `type:feature`, `pipeline:T4-classify`, `ux`, `domain:financial-input`
**Milestone:** `0.1.0-pre-alpha`
**Body:** classifying 200+ transactions via one-at-a-time CLI calls is impractical. Add `aeat financial txs classify-batch --rules rules.json` OR LLM-assisted classification via the `aeat llm` surface. Rules format: match-on-counterparty, match-on-amount-range, match-on-description-regex → category + confidence. User reviews low-confidence rows manually.

### D13 — Wall 16: T6 aggregation function is absent — catalogue → casilla numbers

**Labels:** `type:feature`, `pipeline:T6-handoff`, `blocker`, `domain:financial-input`
**Milestone:** `0.1.0-pre-alpha`
**Body:** no code exists that reads the classified `TransactionCatalogue`, applies `CategoryProfile.casilla_mappings`, aggregates by casilla code and period, and produces the `Mapping[str, Decimal]` that `Engine.derive()` requires. Implement the concrete `FilingInputsProviderProtocol.load_inputs` for at least Modelo 130. Expose as `aeat financial aggregate --modelo 130 --period 2025Q1`. Emit a `CasillaAggregation` ledger showing which transactions contributed to each casilla. This is the largest single blocker on the happy path.

### D14 — Wall 17: `aeat filing build --inputs` requires casilla-code JSON; add a wizard

**Labels:** `type:feature`, `ux`
**Milestone:** `0.2.0-alpha`
**Body:** `aeat filing build` currently takes raw `{"01": 12000, ...}`. Add an interactive mode that prompts "how much did you earn this quarter?" and maps to casilla codes using the model catalogue metadata. Alternatively — and preferably — derive the inputs automatically from D13's aggregator so the user rarely runs `build` with explicit inputs.

### D15 — Wall 18: Review table hides formula and operand values

**Labels:** `type:feature`, `ux`, `ux:cli-output`
**Milestone:** `0.2.0-alpha`
**Body:** (subsumed by C4b). `aeat filing show` currently displays `kind` and `source` but not the formula expression or operand values — that information is only available via the separate `aeat formulas compute` command. The review moment is the highest-value place to show the trace. Render inline: `casilla 07 = sub(04, 05) = sub(350.00, 0.00) = 350.00`.

### D16 — Wall 20: Modelo 303 and 390 have no formula engine

**Labels:** `type:feature`, `area:corpus`, `domain:mediation`
**Milestone:** `0.3.0-beta`
**Body:** only Modelo 130 has a typed, cycle-checked `Ruleset`. Port the ruleset pattern to Modelo 303 (IVA quarterly) and Modelo 390 (IVA annual). These are two of the three most important autónomo forms. Scope includes: schema, formula AST, parameter tables, integration tests mirroring the 130 pattern, and corpus integration.

## group E — charter touch-ups (minor)

### E1 — Comment on #116 confirming the ADR extends, not replaces, the charter

**Operation:** comment on #116
**Comment body:** _"ADR `export-first` (2026-04-17) extends this charter by making live-write disabled-by-default at the product level, not merely safety-gated. The six non-negotiable rules remain in force verbatim."_

### E2 — Comment on #117 confirming the env gate stays

**Operation:** comment on #117
**Comment body:** _"Per ADR `export-first` (2026-04-17): the `AEAT_LIVE_SUBMIT_ENABLED` gate stays. A second gate (`AEAT_ALLOW_LIVE_SUBMIT_OPT_IN`) is added at the product level, and the live-submit CLI entry point moves to a hidden group. Both gates must be enabled for live submission to reach the network."_

## execution order

1. **Group A** (labels) — can run immediately, no approval needed beyond this plan.
2. **Group C1** (charter issue) — file first; it becomes the anchor for everything else.
3. **Group B** (milestone renames) — needs C1 as a reference.
4. **Groups C2–C12** (submission hardening + retitles + closures) — batch.
5. **Group D** (Kent walls) — batch. Cross-link to C1.
6. **Group E** (charter comments) — final, purely informational.
7. **Commit ADR + plan documents** to the repo (this conversation's `.vault/adr/` and `.vault/plan/` artifacts).
8. **Publish ROADMAP.md** (C6) last — by then every link it needs exists.

## approval gate

No GitHub operation runs until the user explicitly approves this plan. Preferred form: "ship A", "ship A+B", "ship all", or specific instructions. Destructive operations (issue closures, title edits on issues the user did not raise) are called out in each C-item; none happen without explicit green-light.
