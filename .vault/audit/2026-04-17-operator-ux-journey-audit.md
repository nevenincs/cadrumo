---
tags:
  - "#audit"
  - "#kent-ux-journey"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-12-gsuite-bootstrap-audit]]"
  - "[[2026-04-13-modelo-inventory-audit]]"
  - "[[2026-04-16-submission-safety-sweep-code-review-audit]]"
  - "[[2026-04-17-modelo-inventory-remediation-audit]]"
---

# kent-ux-journey-audit

## who is kent

Kent is a British autónomo based in Málaga, self-employed six years, works remotely for UK and EU clients. He holds an FNMT digital certificate (collected last year at a Hacienda office). His income lands in BBVA (EUR) and Wise (EUR + GBP). Invoices live in Google Docs; receipts are scattered across Drive folders, Gmail attachments, and his local `~/Documents/facturas/` folder. He is comfortable at a terminal but is not a developer — he can read `README.md`, run `npm`-style commands, and edit a config file, but he will not read Python source to understand a tool. His Spanish is functional; he prefers to operate in English. It is **2026-04-17**, three days before Modelo 130 Q1 closes on 2026-04-20. A friend recommended this tool yesterday.

This audit walks Kent's actual journey as the tool exists on `main` today, marks the walls he hits, and cross-references each wall against the open issue set.

## kent's journey, stage by stage

### stage 0 — discovery

Kent reads `README.md`. The tagline he sees first is: _"AEAT automation CLI: Google Workspace + GCP helpers and health checks."_ This is the actual root-command description in `src/aeat/entrypoints/cli/__init__.py:50`. Kent does not know what GCP is and does not see the word _taxes_ or _modelo_ anywhere in the opening. He almost closes the tab. He keeps going only because his friend swore.

★ **Wall 0 — the product is introduced as a DevOps utility, not a tax tool.** A Spanish autónomo should see in the first line: "help a self-employed person file their AEAT returns." The current tagline optimises for contributors, not users.

### stage 1 — install and bootstrap

`git clone && uv sync` works. Kent has `uv` because his friend told him to install it. (A non-developer autónomo would not — this is a filter the project implicitly applies.) He runs `just bootstrap` per README.

`just bootstrap` calls `just gsuite-bootstrap` → `just gcloud-install` → `just gcloud-auth`. `gcloud-auth` exits: _"env/oauth-client.json not found — run \`just gsuite-oauth-client\` first."_

★ **Wall 1 — the bootstrap recipe runs its steps in the wrong order.** The message is accurate, but `just bootstrap` should have run `gsuite-oauth-client` *before* `gcloud-auth`. Kent has to decipher the dependency graph himself on his first ever command.

Kent runs `just gsuite-oauth-client` → `aeat oauth-client init`. It prints _"Go to Cloud Console, create a project, create an OAuth Desktop app, download the JSON."_

★ **Wall 2 — creating a GCP project is an undocumented prerequisite.** The tool needs Google Workspace access to store Kent's reviewed outputs, but nothing explains *why* a tax tool requires a GCP billing-enabled project. Kent spends twenty minutes in Cloud Console. He also has to agree to GCP billing even for the free tier. This is the point where most non-developers stop.

He downloads the JSON, runs `aeat oauth-client init --json`, then must manually edit `env/.env` to set `GOOGLE_CLOUD_PROJECT`. The `.env.example` comment on that line is actually helpful — points him to the Cloud Console URL — so he finds the value.

`just gcloud-auth` opens three browser tabs for three scope grants. `just gsuite-enable-apis` enables five APIs. `aeat bootstrap` creates scratch Drive/Sheets/Docs.

★ **Wall 3 — the "scratch" resources are a sandbox, not Kent's real data surface.** Kent's invoices and receipts live in *his* Drive. The tool has created parallel empty folders. It is not obvious when/if his real Drive will be used.

### stage 2 — `aeat setup`

README step 2 says `aeat setup`. Kent runs it. `Error: No such command 'setup'`. README footnote says _"merging in #61."_

★ **Wall 4 — the primary onboarding wizard does not exist on `main`.** Issue #61 is closed but the command is not there. `src/aeat/entrypoints/cli/setup.py` exists but Kent cannot find it via `aeat setup`. He falls back to hand-editing `env/.env` — ~200 lines, many AEAT-specific keys, no ordering by importance.

He guesses values for `AEAT_CERTIFICATE_PATH`, `AEAT_CERTIFICATE_PASSWORD_SECRET` (name of an env var — but where does the actual passphrase go?), `AEAT_DEFAULT_PROFILE_NAME` (no comment in `.env.example`), `AEAT_OUTPUT_LANGUAGE` (he spots the default is `hu` — Hungarian — and has to change it to `es`).

★ **Wall 5 — the default output language is Hungarian.** This is `env/.env.example:148` verbatim. A Spanish autónomo who copies the file without auditing will get Hungarian output on every command. This is almost certainly unintentional but is shipping today.

★ **Wall 6 — the cert passphrase has no documented home.** `AEAT_CERTIFICATE_PASSWORD_SECRET` is the *name* of the env var that should hold the passphrase — but nothing tells Kent whether to export it in his shell, put it in `env/.env`, or use a keyring. He guesses `.env`.

### stage 3 — `aeat doctor`

`aeat doctor` runs. Rich table. Green across Google Workspace rows. Certificate row: `SKIP`. Kent doesn't know whether that means "pass" or "not checked." ADC-scopes row shows a `WARN` but doctor exits 0, so Kent moves on.

★ **Wall 7 — `doctor` does not actually verify AEAT connectivity.** It never attempts a live handshake against Sede Electrónica. The function `verify_handshake()` exists in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` but is wired only in tests. Kent will not discover his cert is misconfigured until a real workflow fails.

★ **Wall 8 — `doctor` does not check Playwright, LLM keys, or inbox readiness.** Three critical realms for Kent's journey are invisible to the one health command Kent will trust.

### stage 4 — "what do i owe this month?"

Kent's instinct is `aeat status`. He runs it. The group shows six subcommands. He tries `aeat status expedientes` → `exit 2: cert-auth backend #8 not yet landed`. He tries `aeat status calendario` → same. All six fail identically.

★ **Wall 9 — `aeat status` is a broken facade.** The group is the most obvious entry point for "check my situation" and it ships as six hidden stubs that return developer-internal error strings. `src/aeat/entrypoints/cli/status/__init__.py`. Kent has no way to know this group will be useful "later." It looks broken.

He pivots to `aeat deadlines list --year 2026`. It needs `--profile profile.json`. He has no such file. There is no wizard, no template. He reads `src/aeat/domain/deadlines/_helpers.py` to understand the schema, then writes one by hand.

★ **Wall 10 — `--profile` requires hand-authored JSON.** `AutonomoProfile` has nine boolean/enum fields with Spanish tax-law semantics (IVA regime, IRPF estimation method, IAE heading, intracomunitario flag, ...). Kent cannot author this correctly without reading tax law and the Pydantic model. A wizard that interviews him once and writes this file is exactly what `aeat setup` was supposed to be. It is missing.

Eventually he has a schedule. Modelo 130 Q1 due 2026-04-20. Modelo 303 Q1 due 2026-04-20. He can finally see his obligations.

### stage 5 — "what did i file last quarter?"

Kent wants to copy last quarter's Modelo 130 as a starting point. `aeat status expedientes` → exit 2. `aeat submission list` → empty, because he's never submitted through this tool before. He has no path to pull his existing AEAT history.

★ **Wall 11 — there is no live filing-history retrieval on `main`.** The `StatusReader.fetch_expedientes()` function is implemented, but the CLI entry point is hidden pending #8. This is the single most-asked user question, and the tool cannot answer it today.

He does discover `aeat justificante parse` — takes a PDF he saves from the AEAT portal, parses it into structured form. Useful, but it requires him to have manually downloaded the PDF first. And there is no `aeat justificante list` — his parsed receipts land in `var/justificantes/` with no index command.

### stage 6 — "am i behind?"

Kent worries he missed an informativa last autumn. `aeat deadlines list` shows an `OVERDUE` column for some rows.

★ **Wall 12 — `OVERDUE` is computed from the calendar, not reconciled against filings.** `ObligationStatus.FILED` exists in the enum but is never set anywhere. An `OVERDUE` row means "the date has passed," not "Kent is late." A user cannot tell the difference without cross-referencing AEAT expedientes — which the tool cannot fetch (Wall 11).

### stage 7 — "does aeat have messages for me?"

`aeat inbox list` → empty. `aeat inbox fetch` → needs `source.json`. Kent reads the docstring: he must manually log in to the AEAT portal, read his notifications, and retype them into a JSON file.

★ **Wall 13 — the "inbox" is a local ledger, not an AEAT sync.** Until the live fetcher lands with #43, `aeat inbox` is strictly worse than just visiting the portal — it asks Kent to do the reading work *twice* (once to transcribe, once to file). `aeat inbox next-deadline` is a well-designed alerting primitive with no real data to alert on. And there is no background sync, no cron hook, no MOTD, no `doctor` integration. A requerimiento with a 10-day response window can expire silently.

### stage 8 — "here are my bank statements"

Kent has `bbva_q1_2026.csv`, `wise_q1_2026_eur.csv`, `wise_q1_2026_gbp.csv`, and ~40 PDF invoices in a folder.

`aeat financial ingest bbva_q1_2026.csv` → parses, prints `RawTransaction` JSON lines to stdout. Nothing persists.

★ **Wall 14 — `aeat financial ingest` is read-only.** There is no `--persist` flag, no command that writes parsed records into `transactions.json`. The bridge from T1 (parse) to T2 (catalogue) is not wired. Kent cannot get his bank data into the system without writing Python. This is the largest single failure in the pipeline.

Assume he clears that wall (hand-written script; an hour of work). He has 247 transactions, most `UNCLASSIFIED`.

`aeat financial txs classify <id> --as BUSINESS` — one transaction at a time.

★ **Wall 15 — there is no bulk or rule-based categorisation.** `aeat categories` shows the taxonomy but cannot apply it. There is no `aeat financial txs classify-batch --rules rules.json`, no LLM-assisted classification command. 247 transactions at ~15 seconds each is an hour of pure CLI toil. A real autónomo would abandon and switch to a spreadsheet.

Assume he clears that too (another hour). The catalogue is classified. He now wants casilla-level numbers for Modelo 130.

★ **Wall 16 — T6 (catalogue → casilla aggregation) does not exist.** No code walks the classified catalogue, applies `CategoryProfile.casilla_mappings`, aggregates by casilla code and period, and produces the `Mapping[str, Decimal]` that `Engine.derive()` requires. The middle of the pipeline is a void. Kent has to open a spreadsheet and compute casilla values manually from his catalogue. Everything he did in T1–T5 was reconnaissance, not automation.

### stage 9 — build the filing draft

`aeat filing build --modelo 130 --period 2025Q1 --inputs inputs.json`.

★ **Wall 17 — `--inputs` is a raw JSON file keyed by casilla codes.** `{"01": 12000.00, "02": 4000.00, ...}`. Kent does not know which casilla is "gross professional income" vs "deductible Seguridad Social." He cross-references an AEAT manual PDF. A wizard that asks "how much did you earn this quarter?" and maps that to casilla 01 is what `aeat filing build` should be; it is instead a developer pass-through.

He eventually builds a draft. `aeat filing show draft.json` prints a Rich table with `kind` (literal/computed) and `source` columns. The computed rows carry `formula_trace` — a tuple of contributing casilla IDs.

★ **Wall 18 — the review table does not show the formula or operand values.** `formula_trace` is IDs only. To see "casilla 07 = 04 − 05 = 350.00 − 0.00 = 350.00" Kent must run the separate `aeat formulas compute` and parse its JSON output. The review step is where computation transparency matters most, and the most useful provenance is hidden in a different command.

★ **Wall 19 — there is no explicit "I approve this" state.** The draft status advances `DRAFT → VALIDATED → READY_TO_SUBMIT` purely via validation rules. There is no "Kent reviewed this at 15:47 on 2026-04-17" record anywhere in the draft, the workflow result, or a dedicated approval log. The submission confirmation phrase gates URL + checksum, not casilla values. A cautious Kent has no artifact that proves to himself — or to an auditor — that he reviewed his own filing before signing.

### stage 10 — submission

`aeat submission preflight` → passes. `aeat submission dry-run` → walks the portal, stops short. `aeat submission submit draft.json --i-understand-this-is-real` → Kent types the phrase, the live submission runs, a justificante PDF is produced.

This stage is genuinely good. The `--i-understand-this-is-real` phrase gate (`src/aeat/adapters/outbound/aeat/export/`), the append-only `LiveSubmitAuditRecord`, the dry-run parity — this is the strongest UX artifact in the project. If Kent got here, he gets out cleanly.

### stage 11 — after submit

`aeat status expedientes` → exit 2. Kent cannot confirm AEAT acknowledged his submission from within the tool. He checks the portal in a browser manually.

Modelo 303 Q1 is also due today. Kent tries `aeat formulas compute --modelo MODELO_303 --period 2025Q1`. No ruleset.

★ **Wall 20 — only Modelo 130 has a formula engine.** Modelos 303 (IVA quarterly) and 390 (IVA annual) — two of the three most important autónomo forms — have no formula rulesets. Their filing builders exist and can emit drafts, but casilla derivation is either manual or buried in ad-hoc builder code. Kent files 303 by hand in a spreadsheet.

## the walls, synthesised

Kent hits **twenty walls** between `git clone` and a successfully submitted Modelo 130. Of these:

- **Five walls block him at onboarding** (0, 1, 2, 4, 5, 6) — he cannot even configure the tool without decoding an inverted bootstrap graph, creating a GCP project, and hand-editing 200 lines of env. Walls 5 (HU default) and 6 (password home) are trivially fixable and should be fixed this week.
- **Four walls block him at reconnaissance** (9, 10, 11, 12) — the "check my situation" surface (`aeat status`) looks broken, the deadline command requires a hand-written profile, history retrieval is hidden pending #8, and overdue detection is unreconciled against filings.
- **Three walls gut the financial pipeline** (14, 15, 16) — ingest is read-only, classification is one-by-one, and the catalogue→casilla aggregation step is not implemented. T1–T5 build a well-designed local cache that nothing can read.
- **Three walls weaken the review/approval moment** (17, 18, 19) — casilla inputs are raw JSON, the trace is a separate command, and there is no approval state.
- **Two walls leave Kent unprotected after submission** (11 repeated, 13) — no live confirmation that AEAT accepted, no inbox sync, no alerting.
- **One wall leaves him stranded for two of his three main forms** (20) — 303 and 390 have no formula engine.

## what the tool does well (worth preserving)

- The **submission safety gate** (`--i-understand-this-is-real`, dry-run parity, audit JSONL) is exemplary. Do not water it down.
- The **deadline engine** produces a correct forward-looking schedule for 11 autónomo modelos across 2024–2027 once a profile JSON exists.
- The **Modelo 130 formula engine** is typed, cycle-checked, period-aware, and produces a real `ComputationLedger` with operand traces.
- The **model registry** enforces coverage at import time — all 21 registered modelos have trilingual labels, legal basis, and applicability metadata.
- The **setup verifier** (`src/aeat/application/setup/_verifier.py`) is the only surface in the codebase that produces trilingual findings with remediation hints — it is the template the rest of the error surface should follow.
- `aeat doctor` output is clear and exits non-zero correctly for the realms it does check.
- `aeat bootstrap` gives exceptionally clear remediation text on Drive-quota failures (consumer-Gmail path). This is the gold-standard error message in the codebase; copy it elsewhere.

## wall-to-issue cross-reference

Mapping Kent's walls to the open-issue inventory:

| # | Wall | Tracked? | Issue(s) / note |
|---|---|---|---|
| 0 | Product tagline is DevOps-y | **No** | No `ux` label, no copy issue |
| 1 | `just bootstrap` step order inverted | **No** | Not tracked |
| 2 | GCP-project prereq undocumented | **No** | Docs gap; not tracked |
| 3 | Scratch vs real Drive confusion | **No** | Not tracked |
| 4 | `aeat setup` missing on main | **Partial** | #61 closed but command absent; no follow-up issue |
| 5 | `AEAT_OUTPUT_LANGUAGE=hu` default | **No** | Not tracked — trivial fix, ship this week |
| 6 | Cert passphrase has no home | **No** | Not tracked |
| 7 | `doctor` skips AEAT handshake | **No** | Not tracked; `verify_handshake()` exists unwired |
| 8 | `doctor` ignores Playwright/LLM/inbox | **Partial** | #102 scope is narrower |
| 9 | `aeat status` is a broken facade | **Partial** | Blocked by #141/#8; no issue for the facade-UX problem itself |
| 10 | `--profile` requires hand-authored JSON | **No** | Not tracked |
| 11 | No live filing history | **Yes** | #166 EPIC + #168 — good coverage on fetch; display surface untracked |
| 12 | `OVERDUE` unreconciled | **Yes** | #169 |
| 13 | Inbox is a local ledger | **Partial** | #170 (new API integration); no alerting/notification issue |
| 14 | `ingest` doesn't persist (T1→T2) | **No** | Not explicitly tracked — should be a leaf of the TDP EPIC #104 |
| 15 | No bulk/rule categorisation | **No** | Not tracked |
| 16 | T6 aggregation absent | **Partial** | #81 tracks derivation at a high level; no concrete leaf issue for the aggregator function |
| 17 | `--inputs` is raw casilla JSON | **No** | Not tracked |
| 18 | Review table hides formula/operands | **No** | Partially addressed by #175 EPIC; no concrete CLI issue |
| 19 | No explicit approval state | **Yes** | #175 EPIC + #177 |
| 20 | Modelos 303/390 lack formula engines | **Partial** | #183–#189 waves address formula codification; scope unclear |

**Summary:** Of Kent's 20 walls, **6 are tracked in a way that would actually close them**, **7 are partially tracked** (the EPIC exists but the leaf issues are missing or ambiguous), and **7 are untracked**. Four of the untracked walls (0, 1, 5, 6) are trivial fixes that would measurably improve first-run experience for <1 day of work each.

## roadmap review

The project's milestone ladder is `0.0.1-scaffolding → 0.0.2-foundations → 0.1.0-pre-alpha → 0.2.0-alpha → 0.3.0-beta → 1.0.0`. None of the six milestones has a due date. There is no `ROADMAP.md`. The six-milestone spine encodes a reasonable technical progression, but it does not encode which of Kent's walls it intends to close and when.

A roadmap that spoke to Kent would look like:

- **0.0.2 Foundations — "Kent can install":** close walls 0, 1, 2, 4, 5, 6 (tagline, bootstrap ordering, GCP prereq docs, `aeat setup` wizard on `main`, HU default, password home).
- **0.1.0 Pre-alpha — "Kent can see his situation":** close walls 9, 10, 11, 12, 13 (fix the `status` facade, wizard-author profile, live history via #8, overdue reconciliation #169, live inbox fetch via #43/#46).
- **0.2.0 Alpha — "Kent can compute his own filing":** close walls 14, 15, 16, 17 (ingest→catalogue bridge, bulk categorisation, T6 aggregator, wizard-driven filing build). This is the first milestone at which Kent can produce a valid Modelo 130 without writing Python.
- **0.3.0 Beta — "Kent can trust his filing":** close walls 7, 8, 18, 19 (doctor handshake + broader coverage, in-CLI formula trace in review, explicit `aeat review approve` state that persists).
- **1.0.0 GA — "Kent handles all three main forms":** close wall 20 (303 + 390 formula engines).

This mapping would let the project answer a single question at every release boundary: _"What can Kent do at the end of this milestone that he could not do at the start?"_

## prioritised remediation — first 14 days

Ranked by ratio of UX impact to implementation effort:

1. **Switch `AEAT_OUTPUT_LANGUAGE` default from `hu` to `es`** (wall 5). One-line change in `env/.env.example` and `src/aeat/config.py`. Ship today.
2. **Rewrite the root CLI tagline** (wall 0). `src/aeat/entrypoints/cli/__init__.py:50` — change to something like "File your Spanish tax returns (modelos 130, 303, 390, ...) from the command line." Ship today.
3. **Fix `just bootstrap` step order** (wall 1). Either reorder or detect the `oauth-client.json` precondition and run `gsuite-oauth-client` inline with a prompt. One-hour fix.
4. **Document the cert passphrase home** (wall 6). `env/.env.example` comment + README section + `aeat setup`-generated instructions. Half-day.
5. **Detect unconfigured state at root and print "Run `aeat setup` to get started"** (wall 4 partial). If `env/.env` is missing or empty, the root command should print a greeting instead of dumping 25 commands. One-day fix, even before the full `aeat setup` wizard lands.
6. **Stop leaking internal issue numbers in `aeat workflow next` errors** (wall 9 adjacent, `src/aeat/entrypoints/cli/workflow/_helpers.py:73`). Replace `"requires sibling-branch adapters for #43/#46/#8"` with `"This command needs additional configuration. Run \`aeat setup --check\` to see what is missing."` One-hour fix.
7. **Un-hide `aeat status` but make every subcommand return a human "coming in v0.1.0" line** (wall 9). Returning `exit 2` with developer jargon is strictly worse than an honest "not yet" message that points to the issue tracker. One-day fix.
8. **Add `aeat financial ingest --persist`** (wall 14). The single highest-impact change in the financial pipeline. This is a leaf issue that should exist under EPIC #104 and does not.
9. **File the missing issues.** Walls 0, 1, 2, 5, 6, 10, 13, 14, 15, 17 need GitHub issues before they can be scheduled. Add a `ux` label at the same time.
10. **Publish a `ROADMAP.md`** that anchors each milestone to a Kent-centric question (see previous section). Half-day. This also gives external collaborators and user-experience contributors something to push back on.

## verdict

Kent cannot use this tool today to file his Q1 returns end-to-end without writing Python at least twice (to bridge T1→T2 and to run a T6 aggregator he has to author himself). The submission pipeline and its safety gates are exemplary; the deadline engine and model registry are quietly excellent; but the user never reaches either because the first 60 minutes of his journey are consumed by onboarding walls, and the middle of the financial pipeline is missing. The project is perhaps 70% of the way to Kent's minimum-viable end state, and the remaining 30% is concentrated in a small handful of very concrete functions and CLI entry points that can be identified and tracked individually. The two biggest risks to UX are (a) continuing to ship without a user-centric roadmap while continuing to close engineering-scoped issues, and (b) treating the absence of UX-labelled issues as evidence that UX is not a problem. Both are fixable in one afternoon: label the taxonomy, anchor the milestones to Kent's questions, and file the ten missing leaf issues identified above.
