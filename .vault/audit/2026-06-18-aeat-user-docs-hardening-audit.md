---
tags:
  - '#audit'
  - '#aeat-user-docs-hardening'
date: '2026-06-18'
modified: '2026-06-18'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace aeat-user-docs-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `aeat-user-docs-hardening` audit: `Naive-user persona documentation and functionality review`

## Scope

Continuously-evolving audit for an open-ended, persona-driven documentation +
functionality review campaign. One naive-user persona is dispatched per
user-facing documentation page under `docs/` (how-to, quickstart, tutorials,
explanation). Each persona reads only its assigned page, executes the documented
commands literally through the real CLI, and reports where the documentation and
the application diverge. The coordinator confirms every reported finding against
HEAD before recording it here, and independently verifies backend calculation /
factual correctness. Two objectives: (1) stress the docs (clarity, completeness,
correctness, links); (2) verify the app delivers what each page promises.

Persona testimonials persist under `.agents/testimonials/<doc>.md`. Each persona
runs in an isolated state root (per-persona `AEAT_LOCAL_STORAGE_ROOT` plus the
sibling `var/*` dirs via `.agents/persona_env.sh`) so parallel runs never collide
on the active profile, master key, ledger, or drafts. This audit is the durable,
crash-safe index of confirmed findings.

## Executive summary

Full user-facing documentation surface (33 pages) exercised by naive-user personas
against the live CLI, every finding coordinator-confirmed at HEAD. Headline:

- **The engine and safety posture are trustworthy.** Calculations are coherent and
  legally grounded; the verify gate, cross-period clean-state guards, encryption /
  recovery, and the never-submit boundary all hold and are source-verified. The
  conceptual/explanation surface is accurate (mostly 5/5).
- **One genuine calculation-correctness bug (B2):** Modelo 303's final result casilla
  71 silently reads 0.00 on a real liability because the state-attribution ratio
  (casilla 65) defaults to 0 instead of 100 — a silent under-declaration of the
  headline figure. Highest-priority fix (needs legal grounding).
- **Four more BLOCKER-class defects (B1, B3, B4, B5):** a documented `profile history`
  filter crashes (tz bug); two documented commands are un-runnable as written
  (`portals list`, `ledger participation rebuild`); and the only tutorial's export
  payoff is unreachable with its shipped data.
- **Seven systemic documentation/UX patterns (S-*)** account for most MAJOR/MINOR
  findings — fix once at the source rather than page-by-page: undocumented passphrase
  (S-PASS), English-doc/Spanish-runtime (S-LANG), unstated profile/draft prerequisites
  (S-PREREQ), reversed/failing headline examples (S-ORDER), the `--quiet`-less
  profile-create hint (S-QUIET), the "Cl@ve identity mismatch" mis-framing when auth is
  unconfigured (S-AUTH), and doc-cites-nonexistent-command/flag drift (S-DRIFT).
- **Recurring app-ergonomics class:** several commands emit raw tracebacks / pydantic
  dumps / unrendered `%{detail}` placeholders / literal `<profile-id>` on bad input,
  and refusal exit codes + language are inconsistent.

`modelo-036` and the explanation pages are the cleanest surfaces; `quickstart`,
`tutorials/index`, `modelo-303`, and `review-calculation-values` the weakest.

## Method note

The crucial isolation detail: `aeat_secret_store_dir` (master key) and the other
`var/*` paths default under `PROJECT_ROOT` and are NOT re-rooted by
`AEAT_LOCAL_STORAGE_ROOT` alone, so true per-persona isolation requires setting
every `AEAT_*_DIR` env var. A master-key passphrase (`AEAT_SECRET_PASSPHRASE`) is
also required for any non-interactive run — undocumented in the user docs.

## Coverage status

Done (testimonial + coordinator confirmation): `quickstart` (coord),
`import-bank-statements` (coord), `profile-setup`, `review-calculation-values`,
`verification-reports`, `classify-transactions`, `choose-modelo`, `filing-periods`
(coord), `filing-readiness`, `filing-spine`, `filing-calendar`,
`correct-ledger-entries`, `modelo-036`, `reconcile`, `setup-llm-classification`,
`classify-with-llm`, `classify-with-llm-evidence`, `protect-data-access`,
`review-with-google-sheets`, `authenticate-with-aeat`, `read-live-aeat-data`,
`check-aeat-notifications`, `censo-update`, `justificante-receipts`,
`troubleshooting`, `workstation-setup`, and explanation pages
`from-records-to-figures`, `editing-and-verifying`, `reviewing-and-exporting`,
`building-on-earlier-filings`, `recording-a-filing-and-the-boundary`,
`tutorials/index`, `explanation/index`. **(33 — full user-facing surface covered.)**

Dispatch note: BACKGROUND persona dispatch is non-functional in this dev
environment (0–4 of 6 take hold per wave; most fail to start or hang on stdin).
FOREGROUND agent dispatch works reliably and is now the chosen mechanism, run in
small concurrent batches; the coordinator also drives some pages directly with
backend verification.

Remaining (queued): `correct-ledger-entries`, `filing-spine`, `filing-periods`,
`filing-calendar`, `filing-readiness`, modelo-036/303/390, `ledger-evidence`,
`review-queue`, the LLM guides, `protect-data-access`, `review-with-google-sheets`,
`file-at-aeat`, the live AEAT guides, `censo-update`, `justificante-receipts`,
`reconcile`, `workstation-setup`, tutorials index, `troubleshooting`, and the
explanation set.

## Findings

### Systemic cross-cutting patterns (recur across most pages)

These four are the highest-leverage fixes — each appears in 4+ pages independently
and should be addressed once at the source rather than page-by-page.

- **S-PASS [DOC] master-key passphrase is undocumented everywhere.** Confirmed in
  `quickstart`, `profile-setup`, `classify-transactions`, `review-calculation-values`,
  `verification-reports`, `choose-modelo`. Every profile-scoped command needs the
  passphrase (interactive prompt, or `AEAT_SECRET_PASSPHRASE`); no page warns of it,
  so any scripted/non-interactive first run hard-blocks. Fix once: a shared
  prerequisite note (e.g. in workstation-setup + quickstart, cross-linked).
- **S-LANG [DOC] English docs vs Spanish runtime.** CLI help, refusal/error text,
  result labels, and verdict rationales render in Spanish while docs are English and
  sometimes quote English message text in ```` ```text ```` blocks. Confirmed in
  `profile-setup`, `classify-transactions`, `verification-reports`, `choose-modelo`.
  An English-only reader cannot match documented messages, and `choose-modelo` sells
  the verdict rationale as "plain-language" yet it is Spanish-only.
- **S-PREREQ [DOC] pages assume an active profile and/or an existing work
  unit/draft, with no on-ramp.** Confirmed in `review-calculation-values`,
  `verification-reports`, `classify-transactions`, `choose-modelo`, `quickstart`.
  First command bounces with `No hay un perfil activo` or `Ejecute primero aeat app
  modelo work create`. Fix: a standard "Before you start" prerequisite block linking
  profile-setup + work-create.
- **S-QUIET [APP] the profile-create remediation hint omits `--quiet`.** Many
  refusals print `Ejecuta 'aeat config profile create NAME --tax-id <...>'`, but that
  exact command (no `--quiet`) enters the interactive wizard and hangs/refuses in a
  non-interactive shell — so a user following the tool's own suggested fix hits a
  SECOND wall. Confirmed in justificante-receipts, check-aeat-notifications,
  review-calculation-values, and others. Fix once: the suggested command should
  include `--quiet` (or the wizard should degrade gracefully headless).
- **S-AUTH [APP] live AEAT verbs blame a "Cl@ve identity mismatch" when auth is
  simply unconfigured.** With `auth_configured=False`, `reconcile pull`,
  `live ... pull`, `censo pull`, and `justificante pull` all refuse with a Cl@ve-Móvil
  identity-mismatch message and a `config switch` hint, rather than "no AEAT session /
  run auth configure". Confirmed in reconcile, read-live-aeat-data, censo-update,
  justificante-receipts. Misleads a first-time user about the real blocker.
- **S-DRIFT [BOTH] docs cite commands/flags/args that do not exist or are wrong.**
  Confirmed: `config check --format json` (no such option — the documented
  machine-readable form), `config profile use` (real verb is `config switch`),
  `portals list --category sede_modelo` (invalid), `live filed pull` / `justificante
  pull` (missing required `--year` / `--modelo/--year/--period`), the troubleshooting
  `ledger preflight` "needs a year" friendly message (command emits generic `Missing
  option`), `ollama pull qwen2.5vl:7b` (default model is `qwen2.5vl:3b`). A CLI-to-doc
  conformance sweep is warranted — these passed no command-existence gate.
- **S-ORDER [DOC] headline examples that fail on their own / reversed ordering.**
  `quickstart` step 6 and `review-calculation-values` `--casilla 02=` example fail
  until a binding is supplied; `review-calculation-values` documents "review a saved
  calculation" before the calculate step that produces one; `verification-reports`
  uses a 303/2026/1T example that is always `blocked` so the documented "passes"
  state is unreachable. Fix: order examples so a top-to-bottom reader never hits a
  wall, and pick happy-path examples with no cross-period dependency.

### BLOCKER

- **B2 [APP] CALCULATION CORRECTNESS: Modelo 303 final result casilla 71 silently
  reads 0.00 — FIXED (2026-06-19), regression-clean.** With sale base 1000 / IVA 210 and
  purchase base 500 / IVA 105: casilla 64 (suma de resultados) = 105.00 (correct,
  210−105), but casilla 65 ("% atribuible a la Administración del Estado") resolves
  to **0**, so casilla 66 = [64]×[65]/100 = 0 and the headline casilla 71 (Resultado
  final) = 0.00. The binding `modelo-303-profile-state-attribution-ratio` (source:
  profile fact) defaults to 0 rather than 100 for an ordinary (non-foral, común
  territory) taxpayer, and nothing blocks — the final box silently contradicts the
  visible régimen-general result of 105. A filer trusting casilla 71 would under-
  declare. Coordinator-reproduced. Directly violates `no-silent-under-declaration`.
  Fix needs grounding (default the ratio to 100 for común-territory profiles, or make
  it a required input that blocks rather than silently zeroing) — treat as a graver
  sibling of the M200 base-determination case. Source: modelo-303 persona.
  ROOT CAUSE (coordinator, two layers, NOT yet fixed):
  (1) `tax_residence.jurisdiction_scope` is documented to "default to common_regime"
  but nothing in production profile creation sets it (only `application/user_profile/
  _testing.py` does), and `_profile_fact_index` does not apply schema defaults — so
  `_inject_derived_state_attribution_facts` never hits its `common_regime → 100`
  branch. (2) Even when the synthetic ratio fact is injected, the profile-binding
  resolver `resolve_profile_sourced_bindings` only resolves bindings whose id appears
  in a FORMULA expression's binding refs (`_profile_binding.py:397-402`); casilla 65's
  binding feeds an INPUT casilla and casilla 66's formula references casilla 65 (not
  the binding id), so the binding is excluded and casilla 65 falls back to 0. A
  speculative one-line default-to-100 in the injector was tried and REVERTED because
  it does not surface (layer 2 blocks it). GROUNDING IS SETTLED: the `CCAA` enum is
  común-only by construction and foral regimes are refused at profile creation
  (`ForalRegimeError`), so 100% State attribution (Concierto Económico, Ley 12/2002
  art. 29) is correct for every supported profile. PROPER FIX (engine work, own
  change): ensure input-casilla profile bindings are resolved even when their id is
  not a formula binding-ref, AND derive the ratio for común profiles (or block when
  truly indeterminate) — with a non-tautological 303 calc test asserting casilla 71
  equals the real liability.
  FIX LANDED (2026-06-19): both layers fixed in `_profile_binding.py` — (1)
  `resolve_profile_sourced_bindings` now also resolves profile bindings that feed a
  `bound` NUMERIC casilla (data_type in {decimal,money,integer,ratio}; identity/text
  bindings still excluded so they don't hit the Decimal channel), and (2)
  `_inject_derived_state_attribution_facts` defaults común/absent scope to 100 (foral
  → 0), grounded in the común-only `CCAA` enum + foral refusal at creation (Concierto
  art. 29). Live CLI now yields casilla 65=100, 66=105, 71=105.00 on a 210/105 IVA
  case. Regression test `application/modelo/tests/test_state_attribution_ratio.py`
  (5 tests, incl. a real-snapshot resolver assertion); full modelo + registry-binding
  sweep green (exit 0, 0 failures); the 23 existing profile-binding tests pass.

- **B5 [DOC] `tutorials/index` payoff is unreachable with its shipped sample data.**
  The page is actually a single tutorial (mislabelled "index"); its central promise
  (export a fichero-BOE at the end) cannot be reached: Step 5 calculate errors on the
  literal documented command, and after recovery Step 6 verify returns `incomplete`
  with 3 blocking findings so export/file refuse. Also stale expected outputs
  (English vs Spanish headers; `-49.99` vs absolute `49.99`); the BUSINESS-classified
  expense is dropped and the income falls outside the cumulative window → 0
  rendimiento. Source: tutorials-index. (Same unreachable-happy-path family as quickstart.)

- **B4 [APP] `ledger participation rebuild` is uninvokable.** The subcommand's
  optional `TRANSACTION_ID` positional swallows the literal `rebuild`, so the command
  the troubleshooting page calls "safe to regenerate at any time" fails with a hex
  -validation error instead of dispatching. Source: troubleshooting. ROOT CAUSE
  (coordinator): in `src/aeat/entrypoints/cli/_participation_cli.py` the `participation`
  group is built with `invoke_without_command=True` AND its callback declares an
  optional positional `transaction_id` Argument; Click parses the positional greedily,
  so `rebuild` binds to `transaction_id` and the `rebuild` subcommand never dispatches.
  FIX OPTIONS (needs a UX decision): (a) keep `participation <id>` and special-case the
  reserved `rebuild` token in the callback to defer to the subcommand; (b) move the
  lookup to an explicit `participation lookup <id>` verb and drop the group-level
  positional (cleaner, but changes the documented `participation <id>` form). Pair the
  fix with a documented-command-conformance test that invokes `participation rebuild`.

- **B3 [BOTH] `check-aeat-notifications` Section 5 `portals list` command is
  un-runnable.** The documented `portals list --category sede_modelo --modelo 303`
  fails two ways: `sede_modelo` is not a valid category AND `--category`/`--modelo`
  are mutually exclusive. Source: check-aeat-notifications.

- **B1 [APP] `config profile history --since/--until` crashes. — FIXED (2026-06-18).**
  Was `TypeError: can't compare offset-naive and offset-aware datetimes` at
  `_bucket_history.py` (`event.occurred_at < since_dt`): a bare `--since 2026-01-01`
  parsed naive while events stamp `occurred_at` as aware UTC. Fix: `_parse_bucket_history_instant`
  now normalises a naive operator instant to UTC. Regression tests added in
  `_config/tests/test_bucket_history_parsing.py` (real content-addressed events through
  the matcher, no mocks); live CLI re-verified (returns events, no traceback). Source:
  profile-setup persona.

### MAJOR

- **M1 [APP] calculate's missing-binding remediation misleads.** The calculate
  error tells the user to pass `--binding KEY=VALUE` for every missing binding, but
  ledger-aggregation bindings reject it (`Los bindings de agregación derivados del
  bucket entran en conflicto...`). Only `previous_filing` bindings accept
  `--binding`; ledger-sourced values require real ledger rows. The message should
  distinguish the two source kinds. Coordinator-reproduced. Source: quickstart.
- **M2 [BOTH] profiles are addressed by display-name, not the positional token.**
  After `profile duplicate X Y --display-name "Ana copy"`, the doc's own next
  command `profile delete ana-copy --yes` fails with `Unknown profile: ana-copy`;
  only `delete "Ana copy"` works. Source: profile-setup.
- **M3 [DOC] quickstart's linear path breaks for a real first-timer.** Step 2 import
  has no sample CSV/format; step 4 `overview agenda` errors on the minimal step-1
  profile (`el perfil activo no declara este modelo`); step 6 calculate needs ledger
  income + prior-filing bindings; steps 7-9 hit blocking
  `cross_period_dependency_unclean` (requires activity-start date or evidence).
  Coordinator-reproduced. Source: quickstart.
- **M4 [DOC] no sample `statement.csv` / CSV format** on quickstart or import pages.
  `--provider auto` does work with a realistic bank CSV
  (`Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda`, semicolon, comma
  decimals). Coordinator-reproduced. Source: quickstart + import.
- **M5 [DOC] English docs vs Spanish runtime.** (See S-LANG.) Refusal text is shown
  in English ```` ```text ```` blocks but the app emits Spanish. Source: profile-setup.
- **M6 [BOTH] mixed-use classification is unresolvable from the documented verb.**
  `classify-transactions` presents `--business-pct`, `--usage-ratio-id`, and
  `--prorrata-reference` under a `classify` example, but `ledger classify` accepts
  only `--business-pct` (`No such option: --usage-ratio-id`), and a MIXED row with
  `--business-pct` alone fails preflight (`missing_proportionality_reference`). The
  fix (`ledger allocate --business-pct N --usage-ratio-id <category-id>`, where the
  ratio id is a spending-category id) is undocumented and discoverable only from an
  error string. Coordinator-reproduced. Source: classify-transactions.
- **M7 [BOTH] `overview explain` and `profile preflight` give opposite readiness for
  the same profile+modelo.** `explain 303` → `applicable false / verdict incomplete`
  ("el tipo de contribuyente no está declarado"); `profile preflight --modelo 303` →
  `readiness ready missing=0`. They measure different things (applicability facts vs
  filing-context facts) but read as a contradiction. Coordinator-reproduced.
  Source: choose-modelo. Fix: reconcile the surfaces or explain the distinction on-page.
- **M8 [BOTH] `verification-report view` does not render the legal references the
  page promises.** The page states each finding carries "the legal references behind
  the rule," but `verification-report view` shows no legal-refs field and offers no
  `--json` (`No such option: --json`). (The inline `work verify` output *does* carry
  legal_refs — so the data exists but the report view drops it.) Source: verification-reports.
- **M9 [DOC] `review-calculation-values` ordering inversion + headline example
  fails.** Documents `work revision`/`work verify` before the calculate step (both
  refuse `no selectable current_calculation_revision_id` on a fresh unit), and its
  first `--casilla 02=4000.00` example fails until a binding is supplied. (See S-ORDER.)
  Source: review-calculation-values.
- **M10 [DOC] `verification-reports` happy-path is unreachable.** Its 303/2026/1T
  example is always `blocked` (cross-period dependency on the prior 303), and the
  remediation (record activity-start date; `live filed pull-sources`) has no runnable
  on-page command. Source: verification-reports.
- **M11 [APP] `ledger split` → `merge` is broken at the seam.** `split` never prints
  the child transaction IDs, but `merge --child-id` requires them (and refuses a
  partial cohort), so the documented undo path cannot be completed from CLI output
  alone; additionally the `correct-ledger-entries` "find stashed rows" recipe uses a
  classification filter that does not actually isolate stashed rows. Source:
  correct-ledger-entries. (split/update/archive/dry-run refusals otherwise behaved.)
- **M12 [BOTH] `overview calendar` refuses on an undocumented `censo.enrolment_unverified`
  gate** while `agenda`/`backlog`/`explain` succeed; `filing-calendar` "Before you
  start" also undersells setup (a fresh profile shows nothing until an activity is
  declared off-page, and `--allow-incomplete` is needed). Source: filing-calendar.
- **M13 [DOC] filing-spine opening 4-command block does not run end-to-end** — `work
  create` refuses (no profile, unstated), then `verify` blocks on a 2025 cross-period
  dependency so `export` fails, with no on-page recovery. Source: filing-spine.
  (Concepts, idempotent reuse, by-ID forms all delivered.)
- **M14 [APP] 303 reverify degrades to opaque `DRAFT_HAS_ERRORS`.** After applying
  verify's own suggested remedy (recording an activity-start date), reverify returns
  `Refused ... abort_code: DRAFT_HAS_ERRORS` with NO findings list — inconsistent with
  the detailed-findings verify path and the page's promise that verify exposes
  findings with legal refs. Source: modelo-303.
- **M15 [BOTH] 303→390 dependency has no on-page on-ramp + framing is wrong.** Every
  documented 303 inspection step for 390 errors `Ejecute primero work create`; `390`
  `work verify` hard-blocks with 17 `cross_period_dependency_unclean` findings until
  each 303 quarter has stored evidence, contradicting the page's "does not apply a
  lifecycle-state filter" framing. Also the 303 bindings are called `previous_filing`
  on the page but the CLI reports `source = relation_prefill` /
  `registry_relation`. Source: modelo-390.
- **M16 [APP] documented `live iva-wallet pull-history` fails as written** — the
  documented no-arg form errors `Missing option '--from-year'`. Source: modelo-390.
- **M17 [APP] `ledger invoice add` → `link --invoice-id <id>` is broken** — `link
  --invoice-id` rejects ids produced by `invoice add` (`no se puede vincular aquí`),
  so the page's end-to-end invoice example fails; also the page tells users to attach
  via `--attachment-id <file-id>` but never documents how to obtain a file-id. Source:
  ledger-evidence. (evidence add/attach/list/view/update/remove + doclink refusal all OK.)
- **M18 [BOTH] `review queue`/`view` promise JSON with legal_refs but offer none.**
  The page says "the JSON output always carries legal_refs" (twice), but `--json`,
  `--format json`, `--output json` are all rejected (`No such option`); and an unknown
  `--kind` gives a bare "value invalid" without naming the accepted set — the latter
  violates the CLI-instructive-gate mandate in `aeat-architecture-boundaries`. Source:
  review-queue. (Also: queue table shows 8 columns vs 6 documented, with a `Bucket`
  cell printing the literal `<profile-id>` placeholder.)
- **M19 [APP] `config google login` hangs silently in a non-interactive shell** — no
  URL, no prompt, no timeout, even with stdin closed. Other Google verbs refuse
  gracefully and name the fix, but the page never warns login is an interactive
  browser gate, and mis-frames `verify` / `push --dry-run` as offline/local when both
  need a live Google session. (Likely the cause of an earlier stuck background agent.)
  Source: review-with-google-sheets.
- **M20 [DOC] cloud-evidence consent gate does not fire on a no-evidence transaction.**
  `classify-with-llm-evidence` says the cloud text-layer command "refuses and explains"
  without `--evidence-acknowledged`, but the consent gate fires ONLY when real
  text-layer evidence is attached; on a no-evidence transaction the command goes
  straight to the provider with no consent refusal. (Source review confirms the
  security posture is otherwise correct: gestor-bar-first, capability default-off, ack
  non-sticky, decrypted bytes in-memory only.) Page should state the precondition.
  Source: classify-with-llm-evidence.
- **M21 [BOTH] `read-live-aeat-data` documented `pull` commands miss required args.**
  `aeat app live filed pull` (needs `--year`) and `aeat app live justificante pull`
  (needs `--modelo/--year/--period`) are printed verbatim but error on copy. Refusals
  otherwise fast/graceful. Source: read-live-aeat-data.
- **M22 [DOC] `authenticate-with-aeat` over-states provider support** — presents all 5
  auth providers as usable while 3 are `reservado (no disponible aún)`; also assumes a
  profile for `configure` and omits the passphrase prereq. Apoderado section accurate.
  Source: authenticate-with-aeat.
- **M23 [DOC] `check-aeat-notifications` mislabels `filed list`** as non-downloading
  while it does a live AEAT read; local views (`list`/`latest`/`view`/`history`) work
  offline only after a profile exists. Source: check-aeat-notifications.
- **M24 [BOTH] `workstation-setup` cites a non-existent flag and command** —
  `config check --format json` (no such option) and a capability-set refusal pointing
  at `config profile use` (real verb `config switch`); also `ollama pull qwen2.5vl:7b`
  vs the real default `qwen2.5vl:3b`. `just doctor` + `capabilities show` work and
  match the page. Source: workstation-setup. (See S-DRIFT.)
- **M25 [APP] troubleshooting bucket-session inconsistency + wrong quoted message** —
  `ledger participation`/`reset-progress` refuse "no active bucket session" while
  `ledger status`/`quarantine`/`integrity` open the same bucket fine; and the page
  quotes a friendly `ledger preflight` "needs a year" message the command never emits
  (it gives generic `Missing option '--year'`). Source: troubleshooting.
- **M27 [DOC] `recording-a-filing-and-the-boundary` overstates reconcile** — says the
  comparison confirms "the totals the receipt prints," but `_reconcile.py` compares
  only four header fields (modelo, filing year, period, tax id), NOT box/casilla
  totals. On an honesty-focused page this misleads; name the filing year instead of
  "totals." Source: exp-recording-a-filing-and-the-boundary.
- **M26 [DOC] `editing-and-verifying` under-scopes verify** — says the check reads
  "the agency's published rules for that modelo and year" and frames Blocked as an
  in-draft issue, but the real verify gate also blocks on cross-period clean-state,
  IVA-wallet reconciliation, and provenance; a reader hitting Blocked hunts in the
  wrong place. All other claims verified clean against source. Source: exp-editing-and-verifying.

### MINOR

- **m1 [APP] `ledger import <missing-file>` dumps a traceback** (`FileNotFoundError`
  + a spurious `pdf_n26_provider: failed to parse PDF` ERROR log) before the
  friendly `auto-detection failed`. Coordinator-reproduced. Source: quickstart + import.
- **m2 [DOC] master-key passphrase never documented.** No page warns a passphrase is
  required; scripted users are hard-blocked (`AEAT_SECRET_PASSPHRASE is not set`).
  Source: quickstart + profile-setup.
- **m3 [DOC] `duplicate`/`import` silently switch the active profile** — unstated.
  Source: profile-setup.
- **m4 [BOTH] `profile history` needs an active bucket session** even with an
  explicit name; the doc orders `logout` before `history`, so a literal reader hits
  `No hay una sesión de bucket activa`. Source: profile-setup.
- **m5 [BOTH] `bindings list --missing` does not filter and `readiness` is a source
  restatement.** `--missing` returns all rows; the `readiness` column prints "prior
  filed revision"/"ledger source" (a restatement of `source`), not the resolved/
  unresolved status the page describes. Source: review-calculation-values.
- **m6 [APP] `ledger list` prints no column headers** — tab-separated rows with no
  header line, so a reader cannot tell the short-id column from the full-id column
  (`view`/`categories`/`export` all label columns). Source: classify-transactions.
- **m7 [DOC] `--casilla ID=VALUE` silently rejects source-bound casillas** (`cannot
  override bucket-derived source-bound casillas`); pages do not distinguish
  hand-entered from source-bound casillas. Source: verification-reports.
- **m8 [DOC] `choose-modelo` domain list and `modelo describe` fields are
  incomplete/undocumented** — the page's domain enumeration omits `cross_tax`,
  `irnr`, `patrimonio`, `iae`; `modelo describe` prints undocumented Casillas/
  Vinculaciones/Fórmulas counts. Source: choose-modelo.
- **m9 [BOTH] `filing-readiness` `--binding KEY=VALUE` example is non-runnable** —
  the literal placeholder is rejected as an invalid `BindingId`; `compare`/`project`
  examples also need prior calculated work units the page leaves unstated. Source:
  filing-readiness. App side otherwise clean (every command worked or refused with an
  exact next-step command).
- **m10 [BOTH] `overview calendar` errors on a minimal profile** (`el perfil activo
  no declara este modelo fiscal`), same root as quickstart step 4; and `filing-periods`
  lists `0A` as a common token while a 303-scoped rejection lists only `1T–4T`/`01–12`
  (valid tokens are modelo-specific). Source: filing-periods. App validation otherwise
  precise and instructive (token/filter rejections all behaved as documented).
- **m11 [BOTH] `reconcile` documents `evidence_invalid` as a friendly third verdict**
  ("check this is the right document") but a wrong/malformed PDF produces a bare hard
  refusal (exit 2, `parse failed`, Spanish) with none of that guidance; and the
  `mismatches` verdict shows SHA-256 hashes, not the legible local-vs-PDF values the
  page promises. `reconcile pull` refuses gracefully (Cl@ve identity), as the page
  warns. Source: reconcile. (history + link integrity clean.)
- **m12 [DOC] `correct-ledger-entries` lifecycle verbs give no confirmation** —
  `stash`/`archive` print no lifecycle status in output. Source: correct-ledger-entries.
- **m13 [APP] `ledger add` IVA ergonomics** — `--amount` must be the GROSS (base+IVA),
  enforced as `taxable_base + iva must equal gross to the cent`; a violation dumps a
  ~30-line raw pydantic `RawTransaction(...)` repr instead of a one-line message. No
  page shows a ledger-add IVA example. Source: modelo-303.
- **m14 [APP] `%{detail}` locale placeholder leaks + malformed inline command** — the
  calculate "preflight blocks" error prints unrendered `%{detail}` and a malformed
  `aeat app ledger preflight --period 2026 1T` (year inside `--period`) next to the
  correct structured `-> Run` line. Source: modelo-303.
- **m15 [DOC] expense rows need an undocumented `--category-id`** — the 303/import
  pages say rows need "enough IVA detail" but never that deductible-expense rows
  require `--category-id` (discoverable only via the unmentioned `ledger categories`).
  Source: modelo-303 (also classify).
- **m16 [APP] invalid-PDF refusals leak parser internals** — `reconcile`/`file-at-aeat`
  surface `pdfplumber/PdfminerException` / `parse failed` tracebacks on a bad PDF
  instead of a clean typed refusal. Source: reconcile + file-at-aeat. (Same class as m1.)
- **m17 [APP] `<profile-id>` placeholder literal leaks into output** — recurs in
  `review queue` (Bucket cell) and `config lock`. Source: review-queue + protect-data-access.
- **m18 [APP] LLM classify `--nif` is silently ignored** (real flag is `--tax-id`); a
  logged-out provider fails with a cryptic `Invalid value` (exit 2) instead of pointing
  to the setup page; error-class inconsistency (exit 1 `Error.` vs exit 2 `Invalid
  value`). Source: classify-with-llm.
- **m19 [BOTH] documented LLM preview fields not surfaced** — `classify-with-llm`
  promises preview provenance / whether-persisted and applied confidence/reason, but
  the CLI does not render them. Source: classify-with-llm.
- **m20 [DOC] `protect-data-access`/`classify-with-llm` prerequisite gaps** —
  `protect-data-access` first command refuses without an active profile + passphrase
  (S-PREREQ/S-PASS); `recover` omits its `--new-passphrase`/`--confirm-new-passphrase`
  flags in the doc. Source: protect-data-access.

### NIT

- **n1 [DOC] `ledger add`** (the manual single-row path) is absent from the curated
  top-level help overview though present in `ledger --help`. Source: quickstart.
- **n2 [APP] refusal localisation inconsistent** — `switch` unknown-profile is
  Spanish, `delete` unknown-profile is English. Source: profile-setup.

## Backend capability — positive confirmations

- Modelo 130 1T calculates correctly from real ledger income: casilla 07 = 2000.00
  (20% of the 10 000 rendimiento), box 13 minoración 100.00, casilla 19 = 1900.00.
- The verify gate is robust and well-grounded: carries `legal_refs` / `source_refs`,
  blocks unevidenced cross-period dependencies and a missing activity-start date,
  and gives concrete remediation.
- `export` / `work file` correctly refuse a draft (non-verified) revision.
- The full ledger surface works end-to-end with a realistic bank CSV: import
  auto-detect, add, list, view, classify, update, history, export, rule add/apply,
  preflight (preflight names each missing tax fact precisely).
- profile create/show/validate/edit/rename/duplicate/export/import/logout all
  function; the foral-CCAA refusal is legally grounded; the unencrypted-export
  warning is appropriately blunt.
- **`modelo-036` is clean** (Doc 4/5, App 5/5, 0 major): alta/modificación/baja,
  list, view by id+prefix, no-match refusal, idempotency, `--note-only` all delivered
  exactly as documented; refusals graceful and instructive.
- `reconcile file` happy path works (real fixture → true `mismatches` verdict naming
  `tax_id`); `reconcile pull` and `history` behave as documented; all page links resolve.
- Period/filter validation is precise and instructive: `2026Q1`, `period=2026-1T`, and
  `period=1T` without `year=` are all rejected with helpful, accepted-value errors.
- modelo work concepts (work unit / revision / filed record), idempotent reuse, and
  by-ID addressing forms all deliver as documented across filing-spine and reconcile.
- Modelo 303 IVA mechanics are coherent up to the attribution step: devengada 210,
  deducible 105, resultado-régimen-general 105 (210−105), casilla 64 = 105 — only the
  state-attribution step (casilla 65→66→71, finding B2) breaks. preflight correctly
  blocks a deductible-expense row missing its category.
- `file-at-aeat` SAFETY is solid: the tool never claims or attempts to submit to AEAT
  (`Local; nunca contacta con AEAT`; `reconcile pull` = "solo lectura"); all cited
  in-tool commands (export, work file --notes/--by, reconcile file/pull) exist, take
  the documented flags, and refuse cleanly for unverified drafts / missing markers.
- `ledger-evidence` core flow holds (evidence add/attach/list/view/update/remove; Drive
  doclink refuses gracefully and instructively; export carries
  `purchase_invoice_evidence_id`).
- LLM classification machinery is solid where a provider is present (claude/codex CLIs
  were on PATH here): real suggestions, self-derive/reject/apply/CSV-batch all work,
  `--apply` leaves the ledger unchanged on failure, saturate math exact (base 200 + IVA
  42 = 242), and guardrails fire. The on-host/cloud evidence security posture is
  source-verified correct (gestor-bar, default-off capability, non-sticky ack,
  in-memory-only decrypted bytes).
- `protect-data-access` delivered fully end-to-end: show-recovery, verify-recovery,
  passphrase `--rotate`, rekey-without-re-encrypt, `recover`, lock, reset guards — data
  stayed readable through a passphrase change and a full recovery; both reset guards fire.
- **The explanation/conceptual surface is accurate and strong.**
  `from-records-to-figures` and `reviewing-and-exporting` both scored Doc 5/5 · App 5/5
  with every load-bearing claim verified against the live CLI/source (formulas compute
  boxes from boxes with legal_refs/source_refs; export refuses unverified drafts;
  fichero-BOE offline never-submits; SHA-256 + byte size; Google export auth-gated).
  `editing-and-verifying` was clean except verify-scope (M26). Doc/CLI drift is
  concentrated in the command how-tos, not the explanations. `building-on-earlier-
  filings` and `explanation/index` also scored 5/5 (the carry-forward guards are even
  stronger than documented — also blocks `REGISTRY_REVISION_DIVERGENCE`).
- **SAFETY BOUNDARY CONFIRMED IN SOURCE: the app never submits to AEAT.** Verified by
  the `recording-a-filing-and-the-boundary` reader: an intentionally-empty
  `_submitters` package ("submission permanently forbidden"), `mode: Literal["read"]`
  on every sede boundary record, CI grep write-guards, a runtime click/navigation/
  dialog denylist, `work file` records locally only ("NO envía a la AEAT"), and
  local-filed observations carry the non-official `app_filing` source_kind. This
  upholds `aeat-safety-legal-gates`.

## End-to-end from-nothing → BOE (cross-period goal)

Goal: every persona, starting from nothing, must reach a complete cross-period
calculation and a `.boe` export, all-green.

- **Modelo 130 — PROVEN working end to end (2026-06-19).** From an empty store, the
  full chain produces a valid 946-byte fichero-BOE: `config profile create p
  --quiet --tax-id … --name … --surnames … --activity … --activity-start-date 2026-01-01`
  → `ledger add` income → `modelo work create 130` → `modelo work calculate 130
  --casilla 02=0 --binding modelo-130-resultados-negativos-anteriores=0 --binding
  modelo-130-pagos-fraccionados-anteriores=0 --binding
  irpf.previous_year_economic_activity_net_income=0` → `work verify`
  (`completeness complete / granted true`) → `modelo export` (`.boe`, SHA-256, valid
  `<T130020261T…>` header). The activity-start-date correctly scopes the prior-period
  dependency to a non-blocking advisory; the verify workflow gate passes.
- **The 130 "blockers" are required INPUTS the docs never surface, not engine bugs:**
  (a) the profile must carry `identity.name` + `identity.surnames` or export refuses
  (`requires the operator name`); (b) `casilla 02` (gastos) is a required manual input
  that must be supplied even as `0`; (c) the prior-filing bindings must be supplied
  (`=0` for a first period); (d) an `--activity-start-date` is needed to scope out the
  cross-period dependency. None of the how-to/quickstart pages give this complete
  chain — this is the highest-leverage documentation fix for the goal.
- **Modelo 303 — NOW PROVEN end-to-end (2026-06-19, after the build_draft fix).** From
  nothing, the same chain as 130 yields a valid 7994-byte fichero-BOE: verify
  `completeness complete / granted true`, export `.boe` (SHA-256). The blocker below was
  fixed by the briefed-out fix-agent.
- **Modelo 303 — original blocker (FIXED).** With B2 fixed and an
  activity-start-date, 303 verify reaches `granted` but the verify **workflow gate**
  aborts `DRAFT_HAS_ERRORS` (M14): `_run_revision_workflow_gate` builds a `ModeloDraft`
  via `build_draft` (`_workflow_gate.py:_RevisionDraftBuilder.build`) and only promotes
  when the draft reaches `ModeloDraftStatus.LISTO_PARA_PRESENTAR`; for 303 it stays
  `BORRADOR`, so `_engine.py`'s ready-status check aborts. 130's `build_draft` DOES
  reach `LISTO_PARA_PRESENTAR` (gate passes), so this is 303-specific — `build_draft`
  for a complete 303 is producing a non-filing-ready draft (likely a draft-builder
  validation warning/missing field distinct from the verify completeness check). Next
  step: trace `build_draft` for 303 against the passing `test_verificado_completo_*` /
  `test_file_flow_verify` oracles to find the residual field/warning, fix it, and add a
  303 from-nothing→boe e2e test mirroring the proven 130 chain.
- **Cross-period proper** (e.g. 130 1T filed → 2T cumulative fold-in, or 130 quarters →
  100 annual): the application-level oracle `test_e2e_ledger_m130_quarters_to_m100_annual`
  exists and passes; the CLI-level from-nothing cross-period chain still needs an
  explicit all-green run per modelo once 303's `build_draft` is fixed.

## Briefed-out fix-agent results (2026-06-19)

Issues are being briefed out to per-issue fix-agents (each: confirm at HEAD, minimal fix,
real regression test, lint + scoped tests, no commit). Batch 1 landed:

- **303 build_draft (e2e blocker) — FIXED.** Root cause: `build_draft` set a computed
  casilla's `formula_trace` from short-circuit runtime operands, but the validator checks
  set-equality against the declared `formula_inputs`; the conditional
  `iva.prorrata-porcentaje` (`if_then_else`) evaluated only the predicate operand → spurious
  `formula-divergence` → draft stuck `BORRADOR` → verify gate abort. Fix in
  `application/filing/__init__.py`: computed-casilla trace now comes from declared
  `formula_inputs` (branch-independent). New test
  `application/filing/tests/test_build_draft_conditional_formula_trace.py`; 222 filing +
  20 domain/filing tests green. **303 now exports a valid .boe from nothing.**
- **B4 `ledger participation rebuild` — FIXED.** Callback now detects reserved subcommand
  tokens and dispatches them instead of binding to the optional positional id; both
  `participation <id>` and `participation rebuild` work. New test
  `entrypoints/cli/tests/test_participation_cli_surface.py` (9 green).
- **M8 verification-report legal_refs / `--json` — RE-ASSESSED + test added.** The data
  path was already wired at HEAD; the JSON view is the GLOBAL `aeat --format json <cmd>`
  flag, not a per-command `--json` (the doc/audit assumed the wrong spelling). The 303
  `cross_period_dependency_unclean` findings legitimately carry empty legal_refs; findings
  that have refs render them in text + JSON. Regression test added locking the
  view→legal_refs contract. → reduces to a DOC fix (show `--format json`).
- **M18 review-queue JSON / `--kind` / `<profile-id>` — FIXED.** `--json` is likewise the
  global `--format json` (doc updated). `--kind` now lists the accepted set on a bad value
  (was a bare refusal — closed-set instructive-gate). The `<profile-id>` Bucket cell was
  intentional paste-safety redaction; the redundant column was dropped. Tests + locale gates green.

Batch 2 landed (all disjoint files, lint + scoped tests + conformance/locale gates green,
uncommitted):

- **m13 `ledger add` raw pydantic dump — FIXED** (`_ledger.py`): gross-invariant
  `ValidationError` now a clean one-line refusal, no `RawTransaction(...)` repr.
- **M6 mixed-use unreachable — FIXED (doc)** (`classify-transactions.md`): rewrote the
  mixed-use section to the real working flow (`ratios eligible` → `ratios set` → `allocate
  --business-pct N --usage-ratio-id <category-id>`); dropped the false "most users need only
  `--business-pct`" claim. The preflight proportionality requirement is intentional design.
- **M11 `ledger split` child ids — FIXED** (`_ledger_lifecycle_cli.py` + payload): split now
  emits child transaction ids (text + typed payload) that `merge --child-id` accepts.
- **m1 import missing-file traceback — FIXED** (`application/ledger/_actions_import.py` +
  `_pdf_n26.py`/`_ofx.py`): missing file is a clean typed refusal up front; auto-probe parse
  failures downgraded from ERROR+traceback to debug.
- **M1 calculate missing-binding error — FIXED** (`_modelo.py`): routes by binding source —
  ledger-sourced → "add/classify ledger rows + run preflight"; previous_filing → "supply
  `--binding`". (Also backfilled 2 pre-existing missing locale parity keys.)
- **m18 LLM `--nif` — re-diagnosed (no code change needed):** `--nif` is already rejected by
  Typer; the "silent ignore" was a no-active-profile artifact (the write-guard refuses
  first). Regression test added. Residual: the no-profile generic "No such option" doesn't
  suggest `--tax-id` — a CLI-global concern in `entrypoints/cli/__init__.py` (briefed next).

Batch 3 landed (disjoint files, gates green, uncommitted):

- **M19 google login hang — FIXED** (`adapters/outbound/google/_oauth_flow.py` + typed error
  + locale): non-interactive stdin now refuses fast with an instructive typed message; the
  blocking local-server wait is bounded (300s). Subprocess test with a hard timeout so a
  regression to hanging fails loudly.
- **M2 profile display-name addressing — DOC FIX** (`profile-setup.md`): the single-label
  model is intentional (`duplicate X Y` makes `Y` the address); the doc's divergent
  `--display-name "Ana copy"` then `delete ana-copy` was the bug. Dropped it; token-equals-
  label tests added.
- **M20 cloud-evidence consent gate — CORRECT, DOC FIX** (`classify-with-llm-evidence.md`):
  traced — a no-evidence transaction uploads nothing extra, so the gate correctly fires only
  when evidence text is present. Doc clarified; test confirms no evidence leaks the cloud
  boundary without the ack. No security weakening.
- **m16 PDF-parse leak — FIXED** (`application/modelo/_reconcile.py` + locale): malformed
  justificante PDF now a clean typed `evidence_invalid` refusal with "check this is the right
  document" guidance, no pdfminer/path leak. (Deferred: `evidence_invalid` as a verify-style
  verdict row vs a hard refusal is an ADR-level report-contract change.)

**Meta-finding (S-DRIFT refinement):** several "missing `--json`/`--format json`" findings
(M8, M18, workstation-setup `config check --format json`) are the GLOBAL flag placed BEFORE
the subcommand: `aeat --format json <cmd>` works; `aeat <cmd> --format json` does not. The
docs put the flag in the wrong position — a documentation fix, not an app gap.

## Documentation batch landed (2026-06-19, all gates green, uncommitted)

Each page re-verified end-to-end against the live CLI; `test_documented_command_conformance`
+ `test_educational_docs_conformance` green (126 passed) per agent.

- **quickstart.md** — rewritten to a working from-nothing→`.boe` 130 chain (profile with
  name/surnames/activity-start-date; `ledger add` GROSS amounts + expense category; first-
  period prior bindings =0; verify granted; export 946-byte .boe). Passphrase + Spanish-
  runtime notes added; failing `overview agenda`/`calendar` steps fixed/moved.
- **tutorials/index.md** — fixed the unreachable payoff: dates inside the 1T window, real
  Spanish outputs, prior bindings =0; export is the verified finish; `work file` shown with
  its honest `DEADLINE_PASSED` refusal.
- **modelo-303.md / modelo-390.md** — full from-nothing 303→.boe chain (casilla-65 auto-100
  note); 390 honestly documents the filed-303-evidence requirement + establishment paths;
  `relation_prefill` naming fixed; `iva-wallet pull-history` `--from-year/--to-year` fixed.
- **verification-reports.md / review-calculation-values.md / workstation-setup.md** — JSON is
  the global `aeat --format json <cmd>` (legal_refs present); reachable happy-path setup;
  `--casilla` only on manual boxes (130 box 02 is bound → example uses box 06); ordering
  inversion fixed; `config check` JSON flag position fixed; `qwen2.5vl:3b` default corrected.
- **check-aeat-notifications.md / read-live-aeat-data.md / authenticate-with-aeat.md** —
  runnable `portals list` (real category enum, mutual-exclusion noted); `filed list` is a
  live read; `pull` verbs show required args; only `certificate`+`clave_movil` marked
  available; profile + passphrase prereqs added.

Key real-world refinement: with a ledger EXPENSE row present, 130 casilla 02 is bucket-derived
and `--casilla 02=0` is REFUSED — only supply it when there is no expense row.

## Goal acceptance — from-nothing → BOE validation personas (2026-06-19)

Naive personas, each starting from an EMPTY store, following ONLY the now-fixed doc:

- **quickstart (Modelo 130) → PASS.** 946-byte `.boe`, `verify granted`, following only the page.
- **modelo-303 → PASS.** 7994-byte `.boe`, `verify granted`, casilla 71 = 105.00 (real
  liability, B2 confirmed end-user-visibly). All 7 documented commands ran literally.
- **tutorials/index → PASS.** 946-byte `.boe`, byte-identical to the documented sha256; every
  documented field/value matched real output.

**Cross-period boundary (probe):** a FIRST period from nothing reaches `.boe` and DOES exercise
the cross-period machinery (the prior-period dependency is computed and scoped out via the
activity-start date). A DEPENDENT period (e.g. 130 2T folding in 1T) is GATED BY DESIGN: the
cross-period clean-state guard requires OFFICIAL AEAT prior-period evidence
(`cross_period_dependency_unclean` / `missing_observation` + `missing_current_filing_record`),
and `work file` for a past-deadline 1T refuses `DEADLINE_PASSED`. So a from-nothing
dependent-period `.boe` is correctly IMPOSSIBLE without importing the prior justificante — this
is the `aeat-safety-legal-gates` / `local-filed-observations-are-non-official-evidence` rule
holding, not a defect. The achievable from-nothing→BOE scope (first-period filings) is
all-green across the end-to-end filing docs.

## Recommendations

- Fix B1 (timezone-normalise `since_dt`/`until_dt` or `event.occurred_at` before
  comparison) — a documented command emitting a raw traceback is the highest-value
  fix found so far.
- Reframe the calculate missing-binding error (M1) to separate ledger-sourced from
  previous_filing bindings.
- Add a sample CSV + column format to the import and quickstart pages (M4); make
  missing-file import a clean refusal (m1).
- Rework the quickstart so its linear narrative matches the app's (correct) gates:
  sequence import → classify → calculate, cover the activity-start date for
  first-period filers, and note the passphrase prerequisite (M3, m2).
- Reconcile documented English refusal text with the Spanish the app emits (M5).

### Prioritised remediation order

1. **B2 — 303 casilla-65 state-attribution default** (calculation correctness; needs
   legal grounding per `registry-calculation-legal-grounding` + `no-silent-under-
   declaration`). Default to 100 for común-territory profiles, or make it a blocking
   required input. Most important; not a trivial patch.
2. **B1, B4 — crashing/un-runnable CLI commands** (`profile history --since` tz bug at
   `_bucket_history.py:178`; `ledger participation rebuild` positional swallow). Small,
   localized code fixes with regression tests.
3. **B3, B5, S-DRIFT — doc-cites-nonexistent/under-specified commands.** Add a
   doc↔CLI command-existence conformance gate; fix the cited commands/flags
   (`config check --format json`, `config profile use`→`switch`, `portals list`, the
   live `pull` required args, the tutorial's data/expected outputs).
4. **App-ergonomics class** — replace raw tracebacks / pydantic dumps / `%{detail}` /
   `<profile-id>` leaks with typed refusals; normalise refusal exit codes + language
   (the `cli-errors-never-raw-traceback` codification candidate).
5. **S-PASS / S-PREREQ / S-QUIET / S-AUTH** — one shared "Before you start"
   prerequisite block (active profile + passphrase + the `--quiet` create form), and
   fix the auth-unconfigured refusal wording. Largely documentation work via the
   `vaultspec-documentation` workflow, plus the S-QUIET/S-AUTH message fixes in code.
6. **S-LANG** — decide the bilingual policy (translate operator-facing rationale/labels
   for the `en` locale via the `aeat.locales` CLI, or document that runtime is Spanish);
   touches many pages.

## Codification candidates

Pending campaign completion. One recurring pattern is already visible and may
qualify once it holds across more pages:

- **Source:** B1 + m1 (documented commands — `profile history --since`, `ledger
  import <missing-file>` — emit raw Python tracebacks instead of typed CLI
  refusals). **Candidate rule slug:** `cli-errors-never-raw-traceback`. **Rule:**
  every operator-reachable CLI command must surface failure as a typed refusal /
  notice on the envelope spine, never an unhandled exception traceback, even for
  bad input (missing file, malformed filter). Do not promote yet — confirm the
  pattern recurs across further pages first.
