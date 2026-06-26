# Testimonial — docs/how-to/modelo-390.md

- **Doc path:** `docs/how-to/modelo-390.md`
- **Persona:** A first-time user preparing the annual IVA summary (Modelo 390), worried about whether the page tells me how to establish the quarterly Modelo 303 filings it depends on.
- **Date:** 2026-06-18
- **Environment:** non-interactive shell, `AEAT_SECRET_PASSPHRASE` pre-set, `BASE=/tmp/persona-390-fg`, CLI via `uv run --no-sync aeat`.

## Walkthrough

### 0. Profile prerequisite (not on the page as a command)
- **Command:** `aeat config profile status`
- **Expected:** page assumes an active profile already exists ("Use the same active profile for every command").
- **Actual:** `Sin perfil configurado. Ejecuta `aeat config profile create NAME` para empezar.` I had to create one myself: `aeat config profile create persona390 --tax-id 12345678Z --activity "Comercio"` first **refused** (`El asistente guiado necesita una terminal interactiva`), then succeeded only with `--quiet`. The page never mentions `--quiet`, the passphrase requirement, or that a profile must exist.
- **Verdict:** DOC-ISSUE, MINOR (profile setup is offloaded to a linked page, but the page does not warn that the create wizard blocks non-interactively).

### 1. `aeat config profile status` (documented)
- **Expected:** show the active profile.
- **Actual:** OK — `profile persona390`, `iva.regime GENERAL`, etc.
- **Verdict:** OK.

### 2. `aeat app modelo work status --modelo 303 --year 2025 --period {1T,2T,3T,4T}`
- **Expected:** "Inspect the four 303 filing targets before you work on the annual target."
- **Actual:** all four error: `Invalid value: Ninguna unidad de trabajo activa coincide con este modelo, ano y periodo. Ejecute primero aeat app modelo work create.`
- **Verdict:** DOC-ISSUE, MAJOR — the page presents these as the first inspection step but never tells me to *create* the 303 work units, and there is no in-page command to do so; it only links out to `modelo-303.md`. A naive user runs four commands and gets four errors with no instruction on the page to recover.

### 3. `aeat app modelo work list`
- **Expected:** see the broader filing surface.
- **Actual:** OK — `work_unit_count 0` (empty, as expected).
- **Verdict:** OK.

### 4. `aeat app modelo work revisions/revision --modelo 303 ... --select filed`
- **Expected:** "list revisions and inspect the selected revision."
- **Actual:** both error with the same `Ninguna unidad de trabajo activa...` message — there is no 303 work unit.
- **Verdict:** DOC-ISSUE, MAJOR — same root cause as #2; the entire "Review the 303 values" section is unreachable until 303 work exists, which the page never establishes.

### 5. `aeat app live filed pull-sources --modelo 390 --year 2025 --period 0A`
- **Expected:** read-only capture of filed evidence.
- **Actual:** dumps a long `auth_*` diagnostic block, then `Refused. La identidad de Cl@ve Móvil no coincide con la identidad fiscal del perfil activo; cambia al perfil que coincida... -> Run `aeat config switch NAME``.
- **Verdict:** APP graceful refusal, but DOC-ISSUE MINOR — the page does not warn this needs live AEAT auth/identity match; the refusal is verbose (15+ lines of `auth_*`) before the actual message.

### 6. `aeat app modelo reconcile file --modelo 303 ... --file ./303-2025-1T-justificante.pdf`
- **Expected:** reconcile against a local justificante.
- **Actual:** `Invalid value: Ninguna unidad de trabajo activa coincide... Ejecute primero aeat app modelo work create.` (errors on the missing 303 work unit before even checking the file).
- **Verdict:** DOC-ISSUE, MINOR (chained from #2).

### 7. IVA wallet commands
- `aeat app modelo iva-wallet balance --as-of-year 2025` → OK (`total_balance 0`).
- `aeat app modelo iva-wallet seed --filing-year 2024 --period 4T --amount 0 --confirm` → OK (`status seeded`).
- `aeat app modelo iva-wallet correct --filing-year 2024 --period 4T --amount 1200.50 --reason "..." --confirm` → OK (`status seeded`, previous 0 → 1200.50).
- `aeat app live iva-wallet history` → OK (shows the seeded lot).
- `aeat app live iva-wallet pull-history` → **ERROR:** `Missing option '--from-year'.`
- **Verdict:** the documented `aeat app live iva-wallet pull-history` (with no flags) **fails** — it requires `--from-year`, which the page omits. DOC-ISSUE, MAJOR.

### 8. `aeat app modelo work create --modelo 390 --year 2025 --period 0A`
- **Expected:** create/reuse annual work unit.
- **Actual:** OK — `status created`, `revision_id 2010-y-siguientes`, `state borrador`.
- **Verdict:** OK.

### 9. `work status / history / bindings list / bindings list --missing / casillas / formulas`
- **Expected:** binding list shows "ledger IVA aggregation bindings and `previous_filing` bindings from Modelo 303."
- **Actual:** all OK. `bindings list` shows 10 bindings, but the five 303 ones (`modelo-390-prev-303-*`) have `source = relation_prefill`, **not** `previous_filing`. The page repeatedly calls them "`previous_filing` bindings" and has a whole "Current policy limits" section about "previous-filing resolution" — but the implementation routes them as `relation_prefill`. `casillas` and `formulas --explain` render cleanly with legal_refs.
- **Verdict:** DOC-ISSUE, MAJOR — the page's central vocabulary ("previous-filing bindings from Modelo 303", "previous-filing resolution is keyed by modelo, filing year, and period") does not match the actual `relation_prefill` source kind the CLI reports. A user inspecting the binding list to "treat the previous-filing rows as values that must be reviewed" will not find any row labelled previous-filing.

### 10. `aeat app ledger preflight / status --year 2025 --period 0A`
- **Expected:** check the annual ledger window.
- **Actual:** OK — `ready true`, 0 rows.
- **Verdict:** OK.

### 11. `aeat app modelo work calculate --modelo 390 --year 2025 --period 0A`
- **Expected:** "calculation uses the annual ledger window... If those binding values are not already available... inspect the missing binding list."
- **Actual:** OK — produced a revision, all casillas `0.00`. It did **not** fail despite zero 303 history (matching the page's "Do not assume calculation always fails early" note). Output also includes `days_overdue 139`, `recargo_band within_6_months`, `recargo_pct 6.00` — a surcharge warning the page never mentions.
- **Verdict:** OK (calculate works); NIT that the recargo output is undocumented.

### 12. Calculate with documented `--binding` overrides
- **Command:** the full 5-line `--binding modelo-390-prev-303-...=...` example from the page (with real numbers).
- **Expected:** reviewed 303 values flow into the annual reconciliation casillas.
- **Actual:** OK — `iva.anual.reconciliacion.devengada-303 = 1000.00`, `deducible-303 = 400.00`, `resultado-303 = 600.00`. The documented binding IDs are all accepted.
- **Verdict:** OK — strongest part of the page; the binding example is accurate and works.

### 13. `work revisions / revision --modelo 390 --year 2025 --period 0A`
- **Actual:** OK — lists both revisions; revision detail renders.
- **Verdict:** OK.

### 14. `aeat app modelo work verify --modelo 390 --year 2025 --period 0A`
- **Expected:** "Verification promotes a complete draft to `verificado_completo`."
- **Actual:** `completeness_status blocked`, `granted_verificado_completo false`, `finding_count 17`. Every finding is `cross_period_dependency_unclean` for 303 1T–4T (`blockers=missing_observation, missing_current_filing_record`) tied to the `modelo-390-rel-303-*` relations. Each finding gives a concrete remediation command.
- **Verdict:** OK (app) — this is exactly the 303-prerequisite enforcement the persona cares about, and the findings are instructive. But it **contradicts** the page's "Current policy limits" claim that "the resolver does not apply a verified/filed/reconciled lifecycle-state filter" and "Do not assume calculation always fails early" — verify (not calculate) hard-blocks on missing 303 observations/filing records. The page should state plainly: *390 cannot be verified until each 303 quarter has a stored observation or filing record.*

### 15. `aeat app modelo export --modelo 390 ... --output ...`
- **Expected:** "Export the verified or locally filed revision."
- **Actual:** `Invalid value: current revision is still draft; verify it before exporting or select a verified revision explicitly.`
- **Verdict:** OK — graceful, correct refusal (downstream of the blocked verify).

### 16. `aeat app modelo work file --modelo 390 ... `
- **Actual:** `Invalid value: current revision '...' is in state 'borrador'; filing requires a verified-complete revision.`
- **Verdict:** OK — graceful refusal.

### 17. `filing-record list`, `verification-report list --calculation-revision-id <id>`
- **Actual:** OK — `record_count 0`; verification-report list shows the one blocked report.
- **Verdict:** OK (note: `verification-report list` requires `--calculation-revision-id`, which the page shows as `<...>` placeholder — fine).

### 18. `aeat config google sync calc export --modelo 390 ...`
- **Expected:** spreadsheet review surface.
- **Actual:** `Refused. La autenticación con Google falló: No hay ningun cliente OAuth de Google registrado... Ejecuta `aeat config google register --client-json <path>` primero.`
- **Verdict:** OK — graceful refusal; page does not warn Google must be registered first (MINOR).

## Findings

1. **[MAJOR][DOC]** The page tells you to inspect/review four Modelo 303 targets (work status, revisions, revision, reconcile) but never gives an in-page command to *create* them, so a naive user hits `Ninguna unidad de trabajo activa... Ejecute primero aeat app modelo work create` four-plus times. *Repro:* §2, §4, §6. *Fix:* add an explicit `aeat app modelo work create --modelo 303 --year 2025 --period 1T` (×4) step, or state up front that you must complete `modelo-303.md` end-to-end first and that all 303 inspection commands here will error otherwise.

2. **[MAJOR][DOC]** Documented `aeat app live iva-wallet pull-history` (no args) fails: `Missing option '--from-year'.` *Repro:* §7. *Fix:* document the required `--from-year` (and any companion flags), e.g. `aeat app live iva-wallet pull-history --from-year 2024`.

3. **[MAJOR][BOTH]** Vocabulary mismatch: the page calls the 303-derived bindings "`previous_filing` bindings from Modelo 303" and devotes a "Current policy limits" section to "previous-filing resolution," but `bindings list` reports their `source` as `relation_prefill`, and the verify findings reference them as `registry_relation` / `modelo-390-rel-303-*`. *Repro:* §9, §14. *Fix:* align the page with the actual source kind (`relation_prefill` / registry relation), or note that the operator-facing label differs from the implementation term.

4. **[MAJOR][DOC]** The "Current policy limits" section understates enforcement. It says the resolver "does not apply a verified/filed/reconciled lifecycle-state filter" and "Do not assume calculation always fails early," which reads as "390 is lenient about 303 evidence." In reality `work verify` hard-**blocks** with 17 `cross_period_dependency_unclean` findings (`missing_observation, missing_current_filing_record`) until each 303 quarter has stored evidence. *Repro:* §14. *Fix:* state plainly that verification cannot grant `verificado_completo` until every 303 quarter has a stored observation or filing record, and that `--binding` overrides alone do not satisfy this gate.

5. **[MINOR][DOC]** No passphrase / master-key warning, and the profile-create wizard blocks non-interactively. The page assumes an active profile but never warns that creating one needs `--quiet` in a non-interactive shell (`El asistente guiado necesita una terminal interactiva`) or that a master-key passphrase is required. *Repro:* §0. *Fix:* one line cross-linking profile setup and noting the `--quiet`/passphrase requirements for scripted use.

6. **[MINOR][DOC]** Several documented commands need live AEAT auth (`live filed pull-sources` → Cl@ve identity mismatch) or Google OAuth (`google sync calc export` → no OAuth client). Refusals are graceful but the page does not set the expectation. *Repro:* §5, §18. *Fix:* add a short "these steps need live AEAT login / a registered Google client" note.

7. **[NIT][DOC]** `work calculate` emits recargo fields (`days_overdue 139`, `recargo_band within_6_months`, `recargo_pct 6.00`) that the page never explains; a user filing 2025 in mid-2026 may be alarmed. *Repro:* §11. *Fix:* a one-line note that overdue periods surface a recargo estimate.

## Testimonial

As someone whose whole task is the annual 390-from-303 dependency, the page got the *concept* right — it told me to do the four 303 quarters first and warned the 303-derived values must be reviewed — but it left me stranded on execution: every 303 inspection command errored because nothing on the page actually creates the 303 work units, and the one place it does enforce the dependency (`work verify`, 17 blocking findings) is described in the "policy limits" section as if it were *not* enforced. The genuinely good part was the `--binding` calculate example, which worked exactly as printed and pushed my reviewed 303 totals into the reconciliation casillas. I also tripped on `iva-wallet pull-history` (missing `--from-year`) and on the "previous_filing" vs `relation_prefill` naming, which made the binding list look like it was missing the very rows the page told me to review. The app itself behaved robustly and refused gracefully everywhere; the gaps are almost all in the docs.

## Scorecard

- **Doc clarity:** 2.5 / 5
- **App capability:** 4 / 5
- **Findings by severity:** BLOCKER 0 · MAJOR 4 · MINOR 2 · NIT 1
