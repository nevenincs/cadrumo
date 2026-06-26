# Testimonial — `docs/how-to/filing-calendar.md`

- **Doc path:** `docs/how-to/filing-calendar.md`
- **Persona:** A first-time user who wants to see what filings are due and plan ahead (agenda / calendar / explain / backlog).
- **Date:** 2026-06-18
- **Environment:** `uv run --no-sync aeat ...`, non-interactive shell, passphrase pre-set by harness, `BASE=/tmp/persona-fc-fg`.

---

## Walkthrough

### 0. Pre-flight: `aeat app overview agenda` with NO profile (naive first run)

- **Command:** `aeat app overview agenda`
- **Expected (page "Before you start"):** Page says I need an active profile and points me to `profile-setup.md`.
- **Actual:**
  ```
  Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.
  ```
- **Verdict:** OK — the refusal is graceful and names the exact next command. (Minor: the page never warns a master-key passphrase is required for a non-interactive shell — see Finding 5.)

### 1. Create a profile (forced by the page's "Before you start")

- **Command:** `aeat config profile create persona1 --tax-id 12345678Z --quiet --accept-defaults`
- **Expected:** Page links to `profile-setup.md`; I create the minimum profile.
- **Actual:** `profile persona1 / estado creado / active_profile persona1 / next aeat app modelo work create`
- **Verdict:** OK (this is off-page setup, not a documented calendar command).

### 2. `aeat app overview agenda` (first documented command)

- **Command:** `aeat app overview agenda`
- **Expected:** "The agenda ranks obligations around a reference date" — due today / next two weeks / overdue.
- **Actual (with a default profile, NO activity declared):**
  ```
  Invalid value: El perfil activo no declara este modelo fiscal; actualiza el perfil o vuelve a ejecutar con la anulación de perfil incompleto.
  ```
- **Verdict:** DOC-ISSUE, MAJOR. The very first documented command fails on a freshly-created profile. The page's "Before you start" tells you to *create* a profile but never says you must also *declare an activity* before agenda/calendar return anything. See Finding 1.

### 2b. `aeat app overview agenda --allow-incomplete` (page documents this flag)

- **Command:** `aeat app overview agenda --allow-incomplete`
- **Expected:** "see partial results before the profile is complete."
- **Actual:**
  ```
  as_of	2026-06-18
  horizon_days	14
  next_due	(none)
  due_today	0
  due_soon	0
  overdue	0
  ```
- **Verdict:** OK (flag behaves), but the result is *empty* — confirming a default profile with no activity has nothing to show. Useful but anticlimactic for a naive user (Finding 1).

### 3. Declare an activity (off-page, required to make the page work)

Following the hint from `explain` (step 5) and `aeat config profile edit --help`:

- **Command:** `aeat config profile edit persona1 --quiet --entity-type natural_person --irpf-income-categories actividad_economica --irpf-estimation-regime directa_simplificada --activity "Servicios de consultoria" --activity-start-date 2024-01-01`
- **Actual:** `profile persona1 / estado actualizado`
- Note: a first attempt without `--quiet` refused with a clear instructive message (`Run 'aeat config profile edit NAME --quiet --<field> VALUE'`) — good. The valid value sets were only discoverable by probing with a bogus value (e.g. `'natural_person', 'legal_entity', 'attribution_entity'`). This whole step is **not on the filing-calendar page** (Finding 1).

### 4. `aeat app overview agenda` (re-run, activity now declared)

- **Command:** `aeat app overview agenda`
- **Expected:** ranked obligations.
- **Actual:**
  ```
  as_of	2026-06-18
  horizon_days	14
  next_due	100	2025 0A	closes=2026-06-30
  due_today	0
  due_soon	1
    100	2025 0A	2026-06-30
  overdue	3
    721	2025 0A	2026-03-31
    130	2026 1T	2026-04-20
    303	2026 1T	2026-04-20
  ```
- **Verdict:** OK — delivers exactly what the page promises (due-today / due-soon / overdue cohorts + a single `next_due`).

### 5. `aeat app overview agenda --date 2026-04-15`

- **Command:** `aeat app overview agenda --date 2026-04-15`
- **Expected:** agenda recomputed around the given reference date.
- **Actual:** `next_due 130 2026 1T closes=2026-04-20`, due_soon=2 (130, 303 1T), overdue=3 (303 4T, 390, 721). 
- **Verdict:** OK — reference-date override works as documented.

### 6. `aeat app overview agenda --date 2026-04-15 --horizon 30`

- **Command:** `aeat app overview agenda --date 2026-04-15 --horizon 30`
- **Expected:** widen the upcoming window from default 14 days.
- **Actual:** `horizon_days 30`, same cohorts surfaced. `--help` confirms `[default: 14]`.
- **Verdict:** OK.

### 7. `aeat app overview explain 130 --year 2026`

- **Command:** `aeat app overview explain 130 --year 2026`
- **Expected:** "whether that modelo applies, the registry reason, and the profile facts used."
- **Actual (after activity declared):**
  ```
  modelo	130
  applicable	true
  verdict	applicable
  rationale	Modelo 130 (pago fraccionado del IRPF): la persona física declara rendimientos de actividades económicas en estimación directa...
  legal_refs	rd-439-2007:art-110, orden-eha-672-2007:art-1, ley-35-2006:art-99
  profile_fact	entity_type	natural_person
  ...
  ```
  Earlier (before the activity), the same command returned `applicable false / verdict incomplete` with a precise rationale: *"el tipo de contribuyente no está declarado. Declare primero el tipo de entidad y, en su caso, las categorías de renta del IRPF con 'aeat config profile edit'."*
- **Verdict:** OK — `explain` is the **best** command on the page. It works even on an incomplete profile and tells you exactly which fact to declare and how. (This is what should have been surfaced from the page's "Before you start".)

### 8. `aeat app live notifications latest`

- **Command:** `aeat app live notifications latest`
- **Expected:** DEHu notification snapshots; page warns capture "requires AEAT authentication."
- **Actual:** `bucket <profile-id> / snapshot_id -` (empty, no auth).
- **Verdict:** OK — graceful empty result, no crash. The page sets the expectation that this needs auth.

### 9. `aeat app overview backlog`

- **Command:** `aeat app overview backlog`
- **Expected:** past-due obligations not locally marked presented; default window = 365 days back to today.
- **Actual:**
  ```
  from	2025-06-18	to	2026-06-18	as_of	2026-06-18	late_count	8
  100	2024 0A	closes=2025-06-30
  303	2025 2T	closes=2025-07-21
  ...
  ```
- **Verdict:** OK — matches the documented default window and purpose.

### 10. `aeat app overview backlog --from 2026-01-01 --to 2026-06-30`

- **Command:** `aeat app overview backlog --from 2026-01-01 --to 2026-06-30`
- **Expected:** narrowed window.
- **Actual:** `late_count 5`, entries within the window only.
- **Verdict:** OK.

### 11. `aeat app overview calendar --from 2026-01-01 --to 2026-12-31`

- **Command:** `aeat app overview calendar --from 2026-01-01 --to 2026-12-31`
- **Expected:** a deadline window with national-holiday / business-day shifts. The page documents this **without any extra flag**.
- **Actual:**
  ```
  Invalid value: El calendario tiene comprobaciones de perfil sin resolver: censo.enrolment_unverified. Ejecuta el comando de correccion del aviso o usa --allow-incomplete para inspeccionar el calendario provisional.
  ```
- **Verdict:** DOC-ISSUE, MAJOR. The exact command printed on the page **fails**, even though `agenda` and `backlog` (same profile, same section) succeed without any flag. The blocker is `censo.enrolment_unverified` — a censo verification gate the page never mentions, and which is NOT a "missing profile fact." See Finding 2.

### 12. `aeat app overview calendar ... --allow-incomplete` (recovery)

- **Command:** `aeat app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete`
- **Actual:** 10 entries printed with `opens/closes/adjusted/shift=business_day`, plus:
  ```
  warning	censo.enrolment_unverified	Censo enrolment unverified	fix=aeat config profile censo pull && aeat config profile censo apply
  computable	5	defaulted	0
  ```
- **Verdict:** OK (app works), DOC-ISSUE for not telling the user to add the flag. The `fix=...` hint here is excellent — but it is only visible *after* you guess to add `--allow-incomplete`, which the calendar section never instructs.

### 13. `aeat app overview calendar ... --all-profiles`

- **Command:** `aeat app overview calendar --from 2026-01-01 --to 2026-12-31 --all-profiles`
- **Actual:** same `censo.enrolment_unverified` refusal as step 11 (needs `--allow-incomplete`).
- **Verdict:** DOC-ISSUE, MAJOR (same root cause as Finding 2).

### 14. `aeat app overview calendar ... --show-suppressed`

- **Command:** `aeat app overview calendar --from 2026-01-01 --to 2026-12-31 --show-suppressed` (then re-run with `--allow-incomplete`)
- **Expected:** suppressed entries each with a reason.
- **Actual (with `--allow-incomplete`):** 10 active entries + suppressed rows such as
  `suppressed 200 2025 0A verdict=not_applicable reason=Modelo 200 no aplica...` and several `verdict=incomplete`.
- **Verdict:** OK — `--show-suppressed` behaves exactly as documented (each entry shows why). Same gating caveat as Finding 2.

### 15. `aeat app modelo list` / `--year 2026`

- **Command:** `aeat app modelo list`, `aeat app modelo list --year 2026`
- **Actual:** full catalogue table (`code / title / cadence / domain / revisions`); `--year` filters to revisions valid that year.
- **Verdict:** OK.

### 16. `aeat app modelo describe 130` / `--period 1T`

- **Command:** `aeat app modelo describe 130`, `aeat app modelo describe 130 --period 1T`
- **Actual:** modelo card (título, nombre oficial, periodicidad, períodos, casillas, vinculaciones, fórmulas).
- **Verdict:** OK.

### 17. Edge checks

- `aeat app overview explain 130` (no `--year`) → defaults to `year 2026`. Page always shows `--year` (NIT, Finding 4).
- `aeat app overview calendar --from 2026-01-01` (missing `--to`) → `Missing option '--to'.` Clean, matches the page's "both dates are required" claim. OK.
- `aeat app overview explain 200 --year 2026` → `verdict not_applicable` with a clear rationale. OK.

---

## Findings

### Finding 1 — "Before you start" understates the setup: a profile alone is not enough; an activity must be declared. `[MAJOR] [DOC]`
The page's "Before you start" only says *create a profile* (linking `profile-setup.md`). But with a freshly created default profile, the **first documented command** `aeat app overview agenda` fails:
```
Invalid value: El perfil activo no declara este modelo fiscal; actualiza el perfil o vuelve a ejecutar con la anulación de perfil incompleto.
```
and `agenda --allow-incomplete` returns all-zeros / `next_due (none)`. To get any obligation to appear I had to declare entity type + IRPF income category + estimation regime (off-page, via `aeat config profile edit persona1 --quiet --entity-type natural_person --irpf-income-categories actividad_economica --irpf-estimation-regime directa_simplificada`). The page lists the relevant facts ("taxpayer type, activity start date, IVA regime…") but never tells the reader *they are mandatory before agenda/calendar will show anything* nor *how* to declare them.
**Repro:** create a default profile → run `aeat app overview agenda` → MAJOR refusal.
**Suggested fix:** In "Before you start," add a concrete step: "Declare at least your taxpayer type and income/activity, e.g. `aeat config profile edit NAME --quiet --entity-type natural_person --irpf-income-categories actividad_economica --irpf-estimation-regime directa_simplificada`. Use `aeat app overview explain <modelo> --year <Y>` to see which facts are still missing." Point this out before the agenda example.

### Finding 2 — Documented `calendar` commands fail on `censo.enrolment_unverified`, which the page never mentions. `[MAJOR] [BOTH]`
The page prints `aeat app overview calendar --from 2026-01-01 --to 2026-12-31` (and the `--all-profiles` / `--show-suppressed` variants) **without** `--allow-incomplete`. On a profile that is complete enough for `agenda` and `backlog` to fully succeed, every `calendar` form refuses:
```
Invalid value: El calendario tiene comprobaciones de perfil sin resolver: censo.enrolment_unverified. Ejecuta el comando de correccion del aviso o usa --allow-incomplete para inspeccionar el calendario provisional.
```
This is inconsistent: `agenda`/`backlog` do not trip this gate, only `calendar` does. The page's only hint ("calendar commands may stop and name the missing facts") frames the blocker as a *missing fact*, but `censo.enrolment_unverified` is a *verification* gate, not a fact you can type in via `profile edit`; the resolution is a censo pull/apply (`aeat config profile censo pull && aeat config profile censo apply`).
**Repro:** complete profile enough for agenda → run the page's exact `calendar` command → MAJOR refusal.
**Suggested fix:** Either (a) show the `calendar` examples with `--allow-incomplete` (matching reality), or (b) add a note in the calendar section: "If `calendar` reports `censo.enrolment_unverified`, either run `aeat config profile censo pull && aeat config profile censo apply` (see Link Modelo 036 census information) or add `--allow-incomplete` to see a provisional calendar." Also reconcile why `calendar` enforces the censo gate while `agenda`/`backlog` do not.

### Finding 3 — The error text refers to "el comando de correccion del aviso" without naming it (in the refusal). `[MINOR] [APP]`
The blocking refusal (step 11) says "Ejecuta el comando de correccion del aviso" but does **not** include the command. The actual command (`aeat config profile censo pull && aeat config profile censo apply`) only appears later in the `--allow-incomplete` warning row's `fix=` field — which the user cannot see because the command was refused. A naive user is told to "run the fix command" without being told what it is.
**Suggested fix:** Put the `fix=` command into the refusal message itself.

### Finding 4 — `explain` examples always pass `--year`, but it is optional (defaults to current year). `[NIT] [DOC]`
`aeat app overview explain 130` (no `--year`) works and defaults to `year 2026`. Harmless, but the page could note `--year` is optional.

### Finding 5 — No mention that a master-key passphrase is required. `[MINOR] [DOC]`
Every command in this guide operates on the encrypted active profile, so a real non-interactive user would be blocked without `AEAT_SECRET_PASSPHRASE` / an interactive passphrase prompt. The page never mentions this. (Per the brief, this absence is itself a finding.) `agenda` on no profile refused cleanly with a profile message, but once a profile exists the passphrase becomes load-bearing.
**Suggested fix:** Add a one-line note (or link to profile-setup.md) that calendar commands read the encrypted profile and require the master-key passphrase.

### Finding 6 — Valid enum values for activity facts are not discoverable from this page (or its links inline). `[NIT] [DOC]`
To declare an activity I had to probe `aeat config profile edit` with bogus values to learn the accepted sets (e.g. `entity-type` ∈ {`natural_person`,`legal_entity`,`attribution_entity`}; `irpf-estimation-regime` ∈ {`directa_normal`,`directa_simplificada`,`objetiva`}). Not strictly this page's job (it links to `profile-setup.md`), but combined with Finding 1 it makes the "make the calendar work" path harder than the page implies.

---

## Testimonial

As a planner who just wanted to see what was due, the page read clearly and the
`explain`, `agenda`, and `backlog` commands genuinely delivered — `explain` in
particular held my hand, telling me exactly which profile fact was missing and how
to set it. But the page tripped me twice on the same theme: it promises that
"create a profile" is enough, yet a default profile shows *nothing* until I declare
an activity (which the page never tells me to do), and the headline `calendar`
command — printed with no flags — refused outright on a `censo.enrolment_unverified`
gate the page doesn't mention, while `agenda` and `backlog` sailed through. Once I
declared an activity and added `--allow-incomplete`, every promise on the page came
true; the app is solid, but the page's "Before you start" undersells the real
prerequisites and the `calendar` examples don't match what actually runs.

---

## Scorecard

- **Doc clarity:** 3 / 5 — well-written and well-linked, but "Before you start" understates setup and the `calendar` examples fail as printed.
- **App capability:** 4.5 / 5 — agenda/explain/backlog/calendar/modelo all deliver; refusals are graceful and (mostly) instructive; only the censo gate inconsistency and the unnamed fix-command knock it down.
- **Findings by severity:** BLOCKER 0 · MAJOR 2 · MINOR 2 · NIT 2 (total 6).
