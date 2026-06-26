# Testimonial — `docs/how-to/verification-reports.md`

- **Doc:** `docs/how-to/verification-reports.md`
- **Persona:** a user about to file who wants to verify a 303 draft is complete and understand the verification report.
- **Date:** 2026-06-18
- **Isolation base:** `BASE=/tmp/persona-verification` (test scaffolding, not part of the documented workflow)

---

## Walkthrough

### Prereq A — cold verify with no profile (to test the "Before you start" gate)
- **Command:** `aeat app modelo work verify --modelo 303 --year 2026 --period 1T`
- **Expected:** the page assumes an active profile and a calculated draft already exist; it does not show what happens without them.
- **Actual:** `Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.`
- **Verdict:** OK (refusal is graceful and instructive) — but Spanish refusal under an English page. NIT/DOC.

### Prereq B — establish profile + draft (per "Before you start" links)
- **Commands:** `aeat config profile create my-profile --quiet --tax-id 12345678Z`; `aeat app modelo work create --modelo 303 --year 2026 --period 1T`; `aeat app modelo work calculate --modelo 303 --year 2026 --period 1T`
- **Expected:** a calculated draft I can then verify.
- **Actual:** profile `creado`; work unit created (`AVISO: plazo voluntario vencido`); calculate saved a draft revision `1f2e71...`. All fine. The page itself gives none of these commands — it points to `profile-setup.md` / `quickstart.md`.
- **Verdict:** OK.

### 1. Run verification (documented)
- **Command:** `aeat app modelo work verify --modelo 303 --year 2026 --period 1T`
- **Expected (per page):** either `granted_verificado_completo true` + `completeness_status complete`, OR a `false`/`incomplete|blocked` result; report saved either way.
- **Actual:** `completeness_status blocked`, `granted_verificado_completo false`, `finding_count 3`, all three `cross_period_dependency_unclean` blocking (prior 303 2025 4T evidence missing / no activity-start date). Report id `d36f8e...` saved.
- **Verdict:** OK (report saved, matches the "blocked" branch) — but see Finding 1: the documented *pass* outcome is unreachable from this page's example.

### 2. List reports (documented)
- **Command:** `aeat app modelo verification-report list` and `... --calculation-revision-id 1f2e71...`
- **Expected:** every run leaves a listable report; filter narrows to one calculation.
- **Actual:** `report_count 1`, columns `verification_report_id / calculation_revision_id / completeness_status / granted / run_at / verified_by`. Filter works.
- **Verdict:** OK.

### 3. View a report (documented)
- **Command:** `aeat app modelo verification-report view d36f8e...`
- **Expected (per page bullet list):** status, granted flag, when/who, resolved-casilla count, **which required casillas are still missing**, the findings; and each finding carrying severity, casilla, message, suggested action, **and the legal references behind the rule**.
- **Actual:** shows `completeness_status`, `granted_verificado_completo`, `run_at`, `verified_by`, `resolved_casilla_count 0`, `missing_required_casilla_count 0`, and 3 findings with type/severity/(empty casilla)/message/suggested-action. **No legal references appear anywhere**; missing casillas appear only as a count (`0`), not a list.
- **Verdict:** DOC+APP / MAJOR (legal refs promised, never rendered — Finding 2).

### 4. Export refuses (documented "Export refuses…" section)
- **Commands:** `aeat app modelo work status --modelo 303 --year 2026 --period 1T`; `aeat app modelo export --modelo 303 --year 2026 --period 1T --output ./modelo-303.boe`
- **Expected:** export refuses a plain draft with the quoted message.
- **Actual:** export error: `Invalid value: current revision is still draft; verify it before exporting or select a verified revision explicitly` — matches the page's quoted text closely.
- **Verdict:** OK (excellent — page quote matches reality).

### 5. "More than one filing matches" (documented)
- **Commands:** `aeat app modelo work list`; `aeat app modelo work history --modelo 303 --year 2026 --period 1T`
- **Expected:** list shows work-unit IDs to disambiguate; status/history confirm which filing a command touched.
- **Actual:** `work list` shows `short_work_unit_id 3b0d88c3ea22` + full id, modelo/year/period/state. `work history` shows 3 events incl. `modelo.verification.refused`. Both work.
- **Verdict:** OK. (Could not trigger the actual multi-match refusal with one work unit; the disambiguation commands themselves function.)

### 6. After-any-fix re-run (documented)
- **Command:** `aeat app modelo work verify --modelo 303 --year 2026 --period 1T` (again) + `--by tester` + `--select latest-draft`
- **Expected:** re-run produces a fresh report; `--by` records who ran it; `--select latest-draft` targets a draft.
- **Actual:** fresh report id, still `blocked`/3 findings (nothing fixed, as expected); `--by tester` → `verified_by tester`; `--select latest-draft` runs cleanly. `verify --help` shows `--select [current|latest-draft|explicit]` as a proper Choice.
- **Verdict:** OK.

### 7. "The report says incomplete" fix path (documented `--casilla`)
- **Command:** `aeat app modelo work calculate --modelo 303 --year 2026 --period 1T --casilla iva.repercutido.general=1000`
- **Expected (per page):** "Enter a value for each missing casilla and recalculate."
- **Actual:** `Error. Caller casilla inputs cannot override bucket-derived source-bound casillas: ['iva.repercutido.general']`.
- **Verdict:** DOC / MINOR — the documented `--casilla <ID>=<VALUE>` does not apply to source-bound casillas, and the page never says which casillas accept manual input (Finding 5).

---

## Findings

### 1. [MAJOR][DOC] The page's primary worked example never reaches the documented "passes" state
The page prominently describes success — `granted_verificado_completo true`, `completeness_status complete`, "ready to export" — yet the exact documented example (`--modelo 303 --year 2026 --period 1T`) is **always `blocked`** in a fresh setup because 303 1T has a cross-period dependency on a prior 303 (2025 4T). A naive reader following the page top-to-bottom never sees the pass they were told to expect, and the page's resolution for it lives only in the "blocked" symptom section.
**Repro:** create profile → create+calculate 303/2026/1T → verify → `blocked`, 3 findings.
**Fix:** either use an example modelo/period with no cross-period dependency for the happy-path, or add a one-line note up front: "A first-period 303 will report `blocked` until you record the prior filing or an activity-start date — see *The report says blocked*."

### 2. [MAJOR][BOTH] Promised "legal references behind the rule" are not shown by `view`
The page states each finding carries "The legal references behind the rule," but `verification-report view` renders no legal-refs field/column, and there is no `--json` or other flag to surface them (`--json` is rejected: `No such option: --json`; `view --help` lists only `--help`).
**Repro:** `aeat app modelo verification-report view <id>` — inspect output; no legal refs present.
**Fix:** either add legal refs to the `view` output (and/or a `--json` machine view), or drop that bullet from the page until it's rendered.

### 3. [MAJOR][DOC] "Blocked" remediation can't be executed from this page
The blocked findings' suggested actions point at `aeat config profile edit` (to record an activity-start date) and `aeat app live filed pull-sources` (needs live AEAT). The page's "blocked → A prior-period record is missing" describes this conceptually but gives no runnable command. A naive user is told to "record or confirm that earlier filing first" with no on-page command, and `profile edit` is interactive with no documented flag to set the activity-start date.
**Fix:** give a concrete command (or cross-link) for recording the activity-start date and for the prior-filing record/reconcile path.

### 4. [MAJOR][DOC] No mention that a master-key passphrase is required
Per the test brief: the page never warns that a master-key passphrase is needed. Verification only ran here because the harness pre-set `AEAT_SECRET_PASSPHRASE`. A naive user in a non-interactive shell (or scripting) would be blocked with no warning from this page.
**Fix:** add a one-line prerequisite note (or cross-link) that the active profile's master-key passphrase is required and is prompted for.

### 5. [MINOR][DOC] `--casilla <ID>=<VALUE>` silently doesn't apply to source-bound casillas
The "incomplete" fix tells users to enter a value for a missing casilla via `--casilla`, but source/ledger-bound casillas refuse the override (`cannot override bucket-derived source-bound casillas`). The page doesn't distinguish hand-entered vs source-bound casillas.
**Fix:** note that `--casilla` is for casillas you enter by hand; values derived from ledger/sources are corrected upstream (link to *Review your calculation values*).

### 6. [NIT][DOC] English page, Spanish runtime output
Every result label, `AVISO`, and `Refused`/`Error` message renders in Spanish (`borrador`, `Guardado como revisión…`, `No hay un perfil activo`) under an English page. The structured field names the page cites (`granted_verificado_completo`, `completeness_status`) do match the real output keys — good — but prose messages do not.
**Fix:** acknowledge the bilingual surface, or gloss the key Spanish terms once.

### 7. [NIT][DOC] "Which required casillas are still missing" shows only a count
`view` exposes `missing_required_casilla_count` (a number), not the labelled "missing required casillas" list the page references. I could not reach an `incomplete` state to confirm a list ever renders.
**Fix:** confirm the list field exists in the `incomplete` case, or soften the wording to "a count of missing required casillas."

---

## Testimonial

Following the page felt orderly — calculate, verify, view, export-refusal, re-run all did exactly what the prose said, and the export refusal even matched the quoted message word-for-word, which built trust. But I never reached the "passes / ready to export" finish the page kept promising: the page's own 303/2026/1T example lands on `blocked` every time, and the way out (record a prior filing or an activity-start date, or pull live AEAT evidence) isn't a command I could run from this page. I also went looking for the "legal references behind the rule" the page told me each finding carries, and they simply aren't in the report output. So the report machinery is solid and the symptom map is genuinely helpful, but a first-time filer is left at a blocking wall the page describes without quite letting them climb it.

## Scorecard
- **Doc clarity:** 3 / 5
- **App capability:** 4 / 5
- **Findings:** BLOCKER 0 · MAJOR 4 · MINOR 1 · NIT 2
