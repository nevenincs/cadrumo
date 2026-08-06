# Testimonial — docs/how-to/filing-readiness.md

- **Doc path:** `docs/how-to/filing-readiness.md`
- **Persona:** A user checking whether their ledger/profile is ready to calculate a given modelo/period.
- **Date:** 2026-06-18

---

## Walkthrough

### 1. `aeat app modelo describe 303 --year 2026 --period 1T`
- **Command:** `uv run --no-sync aeat app modelo describe 303 --year 2026 --period 1T`
- **Expected:** A listing that includes the revision id, so I can plug it into the readiness command.
- **Actual:** Worked with no profile. Output included `Ids de revisión 2009-y-siguientes, 2023-y-siguientes`. Headers in Spanish (`Revisión`, `Casillas`).
- **Verdict:** OK (NIT: Spanish headers vs English doc — minor friction reading `Ids de revisión`).

### 2. `aeat app modelo readiness ... --revision-id <revision-id>` (no profile yet)
- **Command:** `uv run --no-sync aeat app modelo readiness --modelo 303 --year 2026 --period 1T --revision-id 2023-y-siguientes`
- **Expected:** A readiness report (profile + ledger). The page gives zero indication a profile must exist first.
- **Actual:** `Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.`
- **Verdict:** DOC-ISSUE (MAJOR) — page never states a profile is a precondition. The refusal itself is graceful and instructive.

### 3. Create profile (forced by step 2; NOT on the page)
- **Command (a):** `uv run --no-sync aeat config profile create persona --tax-id 12345678Z` → refused: `El asistente guiado necesita una terminal interactiva...` then offered the `--quiet` one-shot form.
- **Command (b):** `uv run --no-sync aeat config profile create persona --quiet --tax-id 12345678Z` → `estado creado`, `active_profile persona`.
- **Verdict:** OK (refusal is graceful and self-documenting; passphrase env was pre-set by the harness — see Finding 2).

### 4. `aeat app modelo readiness ... --revision-id 2023-y-siguientes` (with profile)
- **Command:** `uv run --no-sync aeat app modelo readiness --modelo 303 --year 2026 --period 1T --revision-id 2023-y-siguientes`
- **Expected:** Profile readiness + ledger readiness sections.
- **Actual:** `ready True`, `profile_ready True`, `missing 0`, `ledger_preflight_required True`, `ledger_ready True`, `ledger_checked 0`, plus a `finish_line` hint. A freshly-created profile reported fully ready.
- **Verdict:** OK (MINOR: page promises "every profile fact the modelo requires" listed by section/field; with a near-empty profile it reported `missing 0` and listed nothing, so I couldn't observe the documented "missing fact" surface).

### 5. Readiness without `--revision-id`
- **Command:** `uv run --no-sync aeat app modelo readiness --modelo 303 --year 2026 --period 1T`
- **Expected:** Page renders `--revision-id <revision-id>` as if mandatory.
- **Actual:** `Error: Missing option '--revision-id'.` Confirmed required.
- **Verdict:** OK (the two-step "find the revision id first" instruction is correct and necessary).

### 6. `aeat app modelo work dependencies --year 2026`
- **Command:** `uv run --no-sync aeat app modelo work dependencies --year 2026`
- **Expected:** Registry-declared dependencies for the filing year.
- **Actual:** `target_count 43`, a full table (target modelo/year/period/revision/dependency_count/source_modelos).
- **Verdict:** OK.

### 7. Narrowed dependencies + `--period requires --modelo`
- **`--modelo 390`:** one row, `390 2026 0A ... 16 source 303`. OK.
- **`--modelo 390 --period 0A`:** additionally printed a `clean_state` block with `clean False`, `blockers missing_observation, missing_current_filing_record` — exactly the "current blockers for that exact filing" the page promises. OK.
- **`--period 0A` without `--modelo`:** `Error: Invalid value: --period requires --modelo`. Matches the page. OK.
- **Verdict:** OK (this section of the page is accurate and the app delivers).

### 8. `aeat app modelo history --modelo 303 --year 2026`
- **Command:** `uv run --no-sync aeat app modelo history --modelo 303 --year 2026`
- **Expected:** Stream of lifecycle events.
- **Actual:** `modelo 303`, `count 0` (no events yet — expected for a fresh profile).
- **Verdict:** OK.

### 9. `aeat app modelo compare --modelo 100 --year 2024 --year 2025`
- **Command:** `uv run --no-sync aeat app modelo compare --modelo 100 --year 2024 --year 2025`
- **Expected:** Box-by-box comparison.
- **Actual:** `Error: Invalid value: No se encontraron unidades de trabajo del Modelo 100 para el ejercicio 2024. Crea y calcula una unidad de trabajo primero.`
- **Verdict:** OK (clear, instructive refusal; cannot exercise the comparison output without prior data, which the page implies is needed but does not state as a precondition — NIT).

### 10. `aeat app modelo project --year 2026 --ccaa cataluna`
- **Command:** `uv run --no-sync aeat app modelo project --year 2026 --ccaa cataluna`
- **Expected:** Accumulated M130 figures + projected M100 result.
- **Actual:** `Error: Invalid value: No hay unidades de trabajo M130 para el ejercicio indicado. Crea y calcula unidades M130 primero con 'aeat app modelo work create --modelo 130 --year 2026 --period 1T'.`
- **Verdict:** OK (refusal names the exact remediation command; the documented output is unobservable without M130 data).

### 11. `aeat app modelo project ... --casilla 0513=1150 --binding KEY=VALUE`
- **Command:** `uv run --no-sync aeat app modelo project --year 2026 --ccaa cataluna --casilla 0513=1150 --binding KEY=VALUE`
- **Expected:** Page prints `--binding KEY=VALUE` literally as a runnable refinement example.
- **Actual:** `Error: Invalid value: La clave --binding no es un BindingId válido (alfanumérico en minúsculas más separadores . _ : -, máx. 128 caracteres)`. The literal `KEY` is rejected before any M130 check.
- **Verdict:** DOC-ISSUE (MINOR) + APP-ISSUE (NIT) — the doc's literal `KEY=VALUE` is not copy-runnable; `KEY` must be a real lowercase BindingId. The CLI's own help repeats the same misleading `KEY=VALUE` placeholder.

### 12. `aeat app modelo formulas 303 --period 1T --explain`
- **Command:** `uv run --no-sync aeat app modelo formulas 303 --period 1T --explain`
- **Expected:** Each computed box's formula with legal + source references.
- **Actual:** Full table of `formula_id / target / inputs / legal_refs / source_refs` (e.g. `ley-37-1992:art-88`, `aeat-dr-303-2025`). Grounding present as promised.
- **Verdict:** OK.

### 13. `aeat app review queue --explain`
- **Command:** `uv run --no-sync aeat app review queue --explain`
- **Expected:** Pending findings with legal references.
- **Actual:** Header row with `Referencias legales` column, then `No hay elementos pendientes de revisión.` (empty, expected).
- **Verdict:** OK.

### Link check
All eight internal links resolve: `verification-reports.md`, `review-calculation-values.md`, `review-queue.md`, `filing-spine.md`, `filing-periods.md`, `../explanation/building-on-earlier-filings.md`, `../cli/index.rst`.

---

## Findings

### 1. [MAJOR] [DOC] Page never states an active profile is a prerequisite
Every command except `describe` requires an active profile. `readiness` refused with `No hay un perfil activo` on a clean install. The page opens straight into `aeat app modelo readiness` with no "first, create a profile" sentence and no link to profile setup.
- **Repro:** Fresh state → run the first documented readiness command → refused.
- **Fix:** Add a one-line precondition at the top ("You need an active profile — see [Set up a taxpayer profile]") linking the profile-creation guide.

### 2. [MAJOR] [DOC] No mention of the master-key passphrase requirement
Per the brief, a page that never warns a master-key passphrase is required is a finding: a naive user in a non-interactive shell would be blocked. None of these commands tripped a passphrase prompt in my run (the harness pre-set `AEAT_SECRET_PASSPHRASE`), but the page gives no warning that profile-scoped state needs an unlocked master key. Profile creation also requires either an interactive terminal or `--quiet` + flags — also undocumented here.
- **Fix:** Note that profile-scoped commands require an unlocked master key (passphrase), and cross-link the setup/onboarding page where the passphrase is established.

### 3. [MINOR] [BOTH] Documented `--binding KEY=VALUE` example is not copy-runnable
The refinement example `--binding KEY=VALUE` fails validation: `KEY` is not a valid BindingId (must be lowercase alnum plus `. _ : -`). The CLI help shows the same `KEY=VALUE` placeholder, so the doc inherited a misleading literal.
- **Repro:** `aeat app modelo project --year 2026 --ccaa cataluna --binding KEY=VALUE` → `no es un BindingId válido`.
- **Fix:** Use a real example binding id (e.g. `--binding iva.something=1234`) or mark `KEY` explicitly as "a lowercase binding id, not the literal word KEY". Same for the CLI help string.

### 4. [MINOR] [DOC] `compare` and `project` need prior calculated work units, unstated as preconditions
Both refused cleanly because no M100/M130 work units exist. The page presents these as things a readiness-checker can just run; it does not say "you must have created and calculated the relevant work units first." The refusals are excellent (they name the exact next command), so this is doc-only.
- **Fix:** One clause per section: "requires calculated work units for the year(s)/quarters in question."

### 5. [NIT] [DOC] Readiness "missing fact" surface unobservable on a minimal profile
The page promises each missing profile fact listed by section/field key, but a freshly created profile reported `missing 0`. Not wrong, but a reader expecting to see the missing-fact format gets nothing to compare against. Consider a short example of the missing-fact output.

### 6. [NIT] [DOC] Spanish CLI output vs English docs
Output headers render in Spanish (`Ids de revisión`, `Refused.`, `Referencias legales`). An English-only reader following the English page must map terms. The page does not flag this. (Expected per brief; recording the friction.)

---

## Testimonial

Following this page felt smooth *once I had a profile* — the dependency, history, formula, and review-trace commands all did exactly what the page said, and the clean-state blocker output in `work dependencies --period` was genuinely impressive. But as a true first-timer I hit a wall on the very first command: `readiness` refused because I had no profile, and the page never warned me. Every refusal afterward was graceful and told me the next command to run, which kept me moving, but the page assumes a fully set-up taxpayer with calculated work units — context it never establishes. The one outright broken example was `--binding KEY=VALUE`, which the doc (and the CLI help) print as if runnable but the app rejects. The app delivered what the page promised wherever data existed; the gaps were all in unstated preconditions, not in capability.

---

## Scorecard

- **Doc clarity:** 3 / 5 (accurate command syntax and great cross-links, but unstated profile/passphrase/work-unit preconditions and one non-runnable example)
- **App capability:** 5 / 5 (every command worked or refused gracefully with an instructive, exact next step)
- **Findings by severity:** BLOCKER 0 · MAJOR 2 · MINOR 2 · NIT 2
