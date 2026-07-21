---
tags:
  - '#research'
  - '#obligation-coverage-completeness'
date: '2026-06-30'
modified: '2026-07-17'
related:
  - "[[2026-04-12-deadline-engine-adr]]"
  - "[[2026-05-26-cross-domain-continuity-audit]]"
---

# `obligation-coverage-completeness` research: `obligation coverage completeness: no silent under-scoping of filing obligations`

The `aeat` CLI's target operator is an autonomous LLM tax-advisor that scopes
its filing work from `aeat app overview` (`calendar` / `agenda` / `backlog` /
`explain`). This research establishes exactly how the overview surface decides
"what must this taxpayer file?", proves that the decision is the silent
intersection of two divergent coverage tables, enumerates every modelo that
falls through the gaps, and frames the decisions an ADR must resolve so that no
supported filing obligation is ever silently dropped. Under-filing is the worst
regulated outcome; this is the `no-silent-under-declaration` discipline applied
one layer up — at obligation *determination*, not calculation.

The scope is deliberately narrow: the two coverage tables, their reconciliation,
the default surfacing behaviour, and a completeness invariant test. The
calculation engines, the per-modelo verify nonzero guards (separate feature
`#modelo-verify-nonzero-guards`), the calendar DTO shapes (already sound), and
live data pulls are out of scope.

## Findings

### F1 — There is one canonical obligation producer, gated twice

The single producer of the pending-obligation datum is
`compute_obligation_schedule` (`src/aeat/domain/deadlines/_engine.py:443`), which
delegates to `DeadlineEngine.compute`. Both the operator state read-projection
(`pending_obligations`) and the workflow `NO_PENDING_OBLIGATION` gate route
through it, so the two cannot draw a divergent obligation set. An obligation
reaches a *default-visible* calendar row only if it passes **both** of two
independent gates, and a modelo that fails either is dropped without a
default-visible trace.

**Gate 1 — deadline window (engine).** `DeadlineEngine.compute` iterates only the
`(modelo, revision, window)` tuples returned by
`self._registry.deadline_windows(year)` (`_engine.py:177`). A modelo with **no
registered deadline window for that year never enters the schedule at all** — the
engine cannot emit a row it has no window to place. `build_overview_calendar`
catches the benign `NoDeadlineWindowsError` per covered year and continues
(`src/aeat/application/overview/_calendar.py:1311`), so a windowless modelo
contributes zero entries and zero diagnostics.

**Gate 2 — seed applicability rule (calendar).** For every obligation the engine
*does* emit, `build_overview_calendar` calls
`derive_modelo_applicability(profile, obligation.modelo)` and keeps the row only
when `verdict is ApplicabilityVerdict.APPLICABLE`
(`_calendar.py:1349-1360`). Any other verdict is dropped. The dropped row is
captured into a **separate** `suppressed_entries` list **only when
`show_suppressed=True`** — a CLI flag that defaults to `False`
(`_calendar.py:1235`, `src/aeat/entrypoints/cli/_overview.py:509`). The seed rule
table `_MODELO_APPLICABILITY_RULES`
(`src/aeat/domain/calculations/registry/_applicability.py:571`) is explicitly
narrow; a modelo absent from it resolves to `INCOMPLETE` via
`_incomplete_applicability(..., unruled=True)` (`_applicability.py:1227-1229`),
carrying the `_SEED_COVERAGE_NOTICE` "deferred expansion" rationale.

**Surfaced = the intersection of {has a window} and {seed verdict APPLICABLE}.**
Everything else is silent by default.

### F2 — The silent drop propagates to every default surface

`agenda` and `backlog` are not independent surfaces. Both compose
`build_overview_calendar` and iterate **only** `calendar.entries`
(`src/aeat/application/overview/_agenda.py:134-147`,
`src/aeat/application/overview/_backlog.py:124-133`). Neither reads
`suppressed_entries`. So the intersection gate governs `calendar`, `agenda`, and
`backlog` alike; the suppressed/incomplete remainder is invisible on every
default surface. `explain` is the only surface that answers per-modelo on demand,
and only if the operator already knows to ask about that modelo — which is
exactly what an under-scoped agent does not know.

### F3 — Complete coverage matrix (all 30 registry modelos)

The registry defines 30 modelo directories: 036, 100, 111, 115, 123, 130, 131,
151, 180, 184, 190, 193, 200, 202, 210, 232, 303, 308, 309, 322, 347, 349, 353,
360, 369, 390, 714, 720, 721, 840. (`Modelo.M037` exists in the core enum but is
listed in `NON_REGISTRY_MODELOS`, so it is not part of `registry_modelo_codes()`
and has no directory.)

Windowed set (21, confirmed by grepping both inline `[[…deadline_windows]]`
tables and fragmented `deadline_windows/*.toml` files): 100 111 115 123 130 131
180 184 200 202 232 303 322 347 349 353 360 369 390 720 721.

Seed-ruled set (16): 100 111 115 130 131 180 184 190 200 202 303 347 349 390 720
721.

Crossing the two tables classifies every registry modelo into exactly one of four
coverage classes:

| Class | Definition | Default behaviour | Modelos |
|-------|-----------|-------------------|---------|
| **A — surfaced** | has window ∧ seed rule | a calendar/agenda/backlog row when the seed verdict is `APPLICABLE` for the profile | 100 111 115 130 131 180 184 200 202 303 347 349 390 720 721 (15) |
| **B — seed but no window** | seed rule exists ∧ no window | engine never emits it → **silently absent** even though the system positively knows it applies | **190** (1) |
| **C — window but no seed** | window exists ∧ no seed rule | emitted then dropped `INCOMPLETE`; visible only under `--show-suppressed` | 123 232 322 353 360 369 (6) |
| **D — neither** | no window ∧ no seed rule | **fully invisible** on every surface | 036 151 193 210 308 309 714 840 (8) |

15 + 1 + 6 + 8 = 30; every registry modelo is accounted for.

### F4 — M190 is the strongest gap and is a pure data omission

`Modelo.M190` (resumen anual de retenciones e ingresos a cuenta del IRPF) **has a
seed rule** (`_applicability.py:758-779`) keyed on the same
`PayerFact.PAYS_WITHHELD_INCOME` as its quarterly companion Modelo 111, i.e. the
system *positively knows when it applies*. But it has **no deadline window of any
form** — grep for `deadline_windows` under `modelos/190` returns nothing, and its
sole revision `2024-y-siguientes` carries no filing-deadline data at all. The
mandatory January annual companion to the quarterly 111/115 filings is therefore
silently absent from every calendar. This is a pure un-authored-window omission,
not an intentional exclusion: the applicability half already treats M190 as a
first-class obligation. The presentation window is 1–31 January of the year
following the retenciones (the same annual-resumen shape as Modelo 180/390), to
be grounded in the approving Orden and RD 439/2007 art. 108 against the bundled
corpus during implementation.

### F5 — "Declared but empty" is a third silent-drop shape (correction to the brief)

The framing brief placed modelos 308 and 309 in the windowed set (class C). The
registry disagrees: both carry only an **empty** `deadline_windows = []` in their
constructs file (`308/…/constructs/0001-constructs.toml:30`,
`309/…/constructs/0001-constructs.toml:46`) and no actual window table anywhere.
An empty-list declaration resolves to zero windows exactly like an absent one, so
308 and 309 are class **D (neither)**, not class C. This matters twice: it
corrects the class-C membership to 123/232/322/353/360/369 (6, not 8) and the
class-D membership to 036/151/193/210/308/309/714/840 (8, not 6); and it shows
that "looks declared, resolves to nothing" is its own silent-drop shape a
completeness gate must catch — presence of a `deadline_windows` key is not
evidence of coverage.

### F6 — The two silent-drop points are distinct and both must be closed

Gate 1 (window) and Gate 2 (applicability) fail independently, and the fix for
one does not close the other:

- **Gate 1 drops:** class B (190) and class D (the invisibles) — no window, so the
  engine emits nothing regardless of applicability.
- **Gate 2 drops:** class C (always `INCOMPLETE` — no seed rule) **and a subset of
  class A**. Class A includes payer-fact-gated modelos (111/115/180/190) whose
  seed rule returns `INCOMPLETE` when the payer fact is undeclared
  (`_applicability.py`, `required_payer_fact`). So even a "surfaced" modelo is
  silently dropped by default for a taxpayer who *does* pay withheld income but
  has not set the fact — an under-scoping the `_GATING_FIELDS` warning channel
  only partially covers (see F7).

A complete fix reconciles both gates against the full registry modelo set, not
just one.

### F7 — This gap was already diagnosed once, at a coarser grain

The `2026-05-26-cross-domain-continuity-audit` (Cluster C) already recorded the
dual-mechanism problem: "Two parallel mechanisms decide 'does Modelo X apply'…
Neither mechanism references the other," and named remediation item (d): "Add a
calendar-side diagnostic when an `APPLICABLE` modelo has no deadline window for
the requested year — silent drop is the failure mode." That audit framed it as
missing 2025/corporate windows (a data backfill). This research generalises it to
the structural invariant: the diagnostic must cover **every** class of silent
drop (B, C, D, and the class-A `INCOMPLETE` subset), driven from the full
registry modelo set, not a hand-maintained gating dict.

### F8 — The diagnostic channel and central-authority constraints

Two project rules bind the fix's shape:

- `cli-notices-are-the-only-diagnostic-channel`: the "coverage incomplete /
  investigate" surface must be a typed `Notice` on the shared CLI envelope spine,
  not a bespoke `result` field. The overview commands already emit through
  `_emit_envelope(...)` which accepts `notices=` (`_overview.py:463-468` shows the
  status command already passing `overview_next_step_notices(...)`). Today the
  calendar carries an in-result `CalendarWarning` tuple
  (`_calendar_models.py:327`) for under-specified-profile warnings; the ADR must
  decide whether the coverage advisory extends that existing typed channel or
  routes through the envelope `Notice` spine (the rule points at `Notice`).
- `aeat-registry-authority-flow` + `aeat-schema-central-config`: any new deadline
  windows live in the registry authoring tree; any "explicitly out-of-scope"
  declaration is central authority data (a typed declaration analogous to
  `NON_REGISTRY_MODELOS`), never inlined in feature code. `revision-resolution-is-
  law-determined` must be preserved for the surfaced modelos — the fix adds
  windows and advisories, it does not change how existing windows resolve.

### F9 — There is no completeness invariant test today

`test_calendar_applicability_consistency.py` asserts that `calendar` and
`explain` agree on the verdict for **every modelo the deadline engine produces an
obligation for** (it uses `show_suppressed=True` to capture both applicable and
suppressed rows). But it iterates only the engine's *emitted* set — the windowed
modelos — so it structurally cannot catch class B (190) or class D: those never
enter the schedule, so there is nothing for the test to compare. No test iterates
the full `registry_modelo_codes()` set and asserts each modelo is either
surfaceable, advised, or explicitly out-of-scope. That missing invariant is the
gate that would have caught M190.

## Options for the ADR

### Decision 1 — the coverage invariant and default surfacing

Every supported filing obligation must **either** surface as an obligation row
**or** be surfaced by default as an explicit "coverage-incomplete /
must-investigate" advisory — never silently dropped.

- **Option 1a (recommended): default-on coverage reconciliation + typed advisory.**
  Compute a coverage reconciliation over the full `registry_modelo_codes()` set on
  every calendar build, attach a typed `ObligationCoverageReport` to
  `OverviewCalendar` (always populated), and project it into a default-on `Notice`
  advisory carrying a count plus the list of undetermined / window-missing
  modelos. `--show-suppressed` degrades from "reveal that anything was dropped" to
  "show the full per-entry detail". Agenda/backlog inherit the advisory because
  they compose the calendar. Confident negatives (`NOT_APPLICABLE`,
  `ATTRIBUTION_PASS_THROUGH`) are answered, so they stay suppressed without an
  advisory; only `INCOMPLETE` / window-missing / not-yet-scoped raise it.
- **Option 1b: flip the `show_suppressed` default to True.** Cheapest, but dumps
  every confident-negative row into the default output as noise and still gives no
  count/advisory framing; rejected as it trains operators to ignore the surface.

### Decision 2 — M190 and any known-applicable-but-windowless obligation

Author the missing deadline window(s), grounded in the approving Orden/RD and
verified against the bundled corpus. M190 is the only class-B modelo, so this is
scoped and concrete: a 1–31 January annual window shaped like Modelo 180/390.

### Decision 3 — the window-but-no-seed set (class C: 123 232 322 353 360 369)

Per modelo, either author a seed applicability rule (so it surfaces when
applicable) or classify it as "applicability-undetermined → investigate" advisory
— never leave it default-invisible. Preliminary dispositions to be ratified in
the ADR: 123 (retenciones capital mobiliario) is a payer-fact rule like 111/115;
322/353 (grupo de entidades IVA) and 369 (OSS/ventanilla única) gate on an
enrolment fact; 232 (operaciones vinculadas) and 360 (devolución IVA no
establecidos) are niche and may start as advisory-only. Exact legal grounding is
deferred to the implementation plan.

### Decision 4 — the neither-table set (class D: 036 151 193 210 308 309 714 840)

Per modelo, either promote it to window+rule or **explicitly declare it
out-of-scope with a recorded reason** in a central typed declaration, so
"invisible" becomes "explicitly scoped". Includes fixing the empty
`deadline_windows = []` in 308/309 (F5). The completeness invariant test (F9)
then asserts every registry modelo is surfaceable, advised, or explicitly
out-of-scope — no fourth "silently absent" state is permitted.

## Open questions for the ADR

- Does the coverage advisory extend the existing `CalendarWarning` channel or
  route through the envelope `Notice` spine? (`cli-notices` points at `Notice`.)
- Where does the "explicitly out-of-scope" declaration live — a new central
  `core` constant (like `NON_REGISTRY_MODELOS`) with per-modelo reasons, or a new
  applicability verdict? Central constant is the closer precedent.
- Is the coverage reconciliation profile-dependent (undetermined depends on which
  payer facts are undeclared) or profile-independent (structural window/rule
  presence)? The recommendation is both layers: a structural completeness test
  (profile-independent) plus a per-profile advisory (profile-dependent).
