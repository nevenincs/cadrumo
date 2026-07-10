---
tags:
  - '#adr'
  - '#obligation-coverage-completeness'
date: '2026-06-30'
modified: '2026-07-08'
related:
  - "[[2026-06-30-obligation-coverage-completeness-research]]"
  - "[[2026-04-12-deadline-engine-adr]]"
  - "[[2026-05-26-cross-domain-continuity-audit]]"
---

# `obligation-coverage-completeness` adr: `reconcile obligation coverage: surface or advise, never silently drop a filing obligation` | (**status:** `accepted`)

## Update: external-universe gate (AEAT-wide enrollment)

Extended beyond the registry subset toward AEAT-wide enrollment. The coverage
invariant now binds to the **AEAT obligation universe** — `registry_modelo_codes()`
∪ `UNMODELED_OBLIGATIONS` (a central declaration of recognized AEAT obligations the
registry does not yet model) — rather than to the registry alone. Architecture: an
unmodeled obligation is a `Modelo` enum member carried in `NON_REGISTRY_MODELOS`
(no registry TOML, so the enum parity gate stays green) and listed in
`UNMODELED_OBLIGATIONS` with a description; the reconciliation advises it with a new
`REGISTRY_UNMODELED` reason, so an obligation AEAT expects but the app never modeled
surfaces as advised rather than being invisible. Grounded against AEAT's published
catalogue of declaraciones informativas and retención forms, the recognized
obligation universe has ratcheted to **68** (30 registry + 27 advised-unmodeled + 11
out-of-scope non-registry) from the original 30. `UNMODELED_OBLIGATIONS` (advised)
carries the autónomo/PYME/entity-relevant retenciones and informativas
(117/126/128/136/165/179/181/182/187/188/189/194/198/216/222/231/233/234/238/270/280/289/296/345/361/368/379);
recognized forms a general taxpayer never files (financial-institution / registrar /
regional-special: 159/170/171/172/173/192/196/290/291/294/295) are declared
out-of-scope with recorded reasons rather than advised, so they are accounted for
without becoming investigate-noise. The reconciliation universe and the completeness
invariant now bind to registry ∪ unmodeled ∪ out-of-scope. (Registry-dependent gates
for this ratchet batch are transiently blocked by an unrelated peer's in-flight
`registry/_schema.py` import breakage; the core parity arithmetic — `enum −
NON_REGISTRY == 30` — is verified standalone.) The out-of-scope escape hatch is now guarded by a gate asserting
it cannot silence any modelo the applicability table can positively decide. **All six
`overview` surfaces are now wired**: single-profile calendar / agenda / backlog,
`--all-profiles` (per-profile advisories), `overview status` (reconciles the active
profile's coverage over the current year), the undeclared-profile path (shows the whole
universe as advised, never "nothing to file"), and `overview explain` (a
recognized-unmodeled modelo returns an informative "recognized AEAT obligation, not
modeled yet — investigate" answer, distinct from an unknown-typo rejection). The
localized advisory is complete across all four catalogues (en / es / ca / hu). Remaining
toward full AEAT-wide enrollment (inherently multi-session, grounding-gated): continue
ratcheting `UNMODELED_OBLIGATIONS` toward AEAT's full ~200-form set, and promote each
unmodeled entry to a full registry definition (deadline windows + applicability rule)
with each window and rate grounded in its publishing Orden/RD verified against the
bundled corpus — the point at which "investigate" resolves into a confident
applies/doesn't-apply.

## Implementation status

The structural closure (Decision 1 and Decision 5) is **implemented**: a total
obligation-coverage reconciliation partitions every registry modelo into
surfaced / confidently-excluded / advised / out-of-scope, attached to the
`overview` calendar / agenda / backlog read models and projected into a
default-visible typed `Notice` (warning when a known-applicable obligation has no
window — the Modelo-190 shape; info otherwise). The central out-of-scope
declaration (`OUT_OF_SCOPE_OBLIGATIONS` in `core`) and the completeness invariant
test (asserting the partition is total, `advised` catches M190, and buckets are
disjoint) are landed. This makes silent under-scoping structurally impossible:
every obligation not surfaced is either confidently answered, advised for
investigation, or explicitly out of scope with a recorded reason.

**Deferred to follow-up (each upgrades an advised item to surfaced, and the
advisory already prevents silent under-filing in the interim):** authoring the
M190 deadline window and any class-C seed rules (Decisions 2 and 3), which
require the legal-grounding + bundled-corpus verification the plan owns; and
scaffolding the `cli.overview.coverage.investigate` locale key across the four
catalogues — currently blocked by an unrelated peer's duplicate
`file_idempotent_noop` key in `en.yml`, so the advisory renders from its English
`tr(..., default=...)` fallback until that clears.

## Problem Statement

The `aeat app overview` surface is where the target operator — an autonomous LLM
tax-advisor — scopes "what must this taxpayer file?". The research
(`2026-06-30-obligation-coverage-completeness-research`) proves that this answer
is the **silent intersection of two divergent coverage tables**, and that every
mismatch is dropped without a default-visible trace, so an agent (or a human)
trusting `overview` would under-file. Under-filing is the worst regulated
outcome. This is the `no-silent-under-declaration` discipline applied one layer
up — at obligation *determination*, not calculation.

Concretely, an obligation reaches a default-visible row only if it passes both
gates of the single producer `compute_obligation_schedule`
(`src/aeat/domain/deadlines/_engine.py:443`): Gate 1 requires a registered
deadline window (or the engine never emits it); Gate 2 requires the seed
applicability verdict to be `APPLICABLE` (`_calendar.py:1349-1360`), else the row
is dropped and captured only when the default-off `--show-suppressed` flag is
set. `agenda` and `backlog` compose the calendar and read only `entries`, so the
silent drop propagates to every default surface. Crossing the two tables over the
30 registry modelos leaves four classes: **A** surfaced (15), **B** seed-ruled
but window-less (Modelo 190 — silently absent though positively known to apply),
**C** windowed but rule-less (123 232 322 353 360 369 — dropped `INCOMPLETE`,
hidden unless `--show-suppressed`), **D** neither (036 151 193 210 308 309 714 840
— fully invisible). The `2026-05-26-cross-domain-continuity-audit` (Cluster C)
diagnosed this at a coarser grain and left remediation item (d) — a calendar-side
diagnostic for the silent drop — open.

## Considerations

- **The invariant is coverage, not calculation.** Correctness here is not "is the
  number right" but "did the operator learn every obligation it must investigate".
  A confident negative (`NOT_APPLICABLE`, `ATTRIBUTION_PASS_THROUGH`) is an
  *answer*; an `INCOMPLETE` verdict, a missing window, or a not-yet-scoped modelo
  is an *unanswered question* that must be surfaced, not hidden.
- **Two independent drop points.** Fixing the window gate does not close the
  applicability gate. Class B/D fail Gate 1 (no window); class C and a subset of
  class A (the payer-fact-gated 111/115/180/190 when the fact is undeclared) fail
  Gate 2 (`INCOMPLETE`). The reconciliation must cover both, driven from the full
  `registry_modelo_codes()` set — not a hand-maintained gating dict.
- **"Declared but empty" is a silent-drop shape.** Modelos 308/309 carry an empty
  `deadline_windows = []`; presence of the key is not coverage. The completeness
  gate must assert *resolved* windows, not key presence.
- **Diagnostic-channel rule.** `cli-notices-are-the-only-diagnostic-channel`
  requires the advisory be a typed `Notice` on the envelope spine, not a bespoke
  `result` field. The overview commands already emit through `_emit_envelope(...,
  notices=...)`.
- **Central-authority rule.** New windows live in the registry authoring tree
  (`aeat-registry-authority-flow`); the "explicitly out-of-scope" declaration is
  central typed data (`aeat-schema-central-config`), never inlined in feature
  code. `revision-resolution-is-law-determined` is preserved — the fix adds
  windows and advisories, it never changes how existing windows resolve.
- **Legal grounding.** Every new deadline window must cite the publishing
  Orden/RD/ley article, defined in the legal catalogue with a `corpus_ref`
  resolving to the bundled authoritative text, with the date verified against that
  text (`registry-calculation-legal-grounding`,
  `legal-grounding-verifies-bundled-authoritative-corpus`).

## Considered options

- **O1 — default-on coverage reconciliation + typed `Notice` advisory (chosen).**
  Compute a coverage reconciliation over the full registry modelo set on every
  calendar build; attach a typed, always-populated `ObligationCoverageReport` to
  `OverviewCalendar`; project it into a default-on `Notice` carrying a count plus
  the undetermined / window-missing modelo list. `--show-suppressed` degrades to
  "show per-entry detail". Closes both gates from one authority; agenda/backlog
  inherit it. Chosen.
- **O2 — flip `show_suppressed` default to True.** Cheapest; but dumps every
  confident-negative row as noise, gives no count/advisory framing, and still says
  nothing about class B/D (which never enter the schedule). Rejected — trains
  operators to ignore the surface and misses the window-less classes entirely.
- **O3 — backfill only the missing windows (the Cluster-C data-backfill reading).**
  Authors M190 and other windows but leaves the structural silent-drop for class
  C/D and the class-A `INCOMPLETE` subset, and adds no invariant test. Rejected as
  incomplete — it fixes today's known gaps without preventing the next one.
- **O4 — a new `OUT_OF_SCOPE` applicability verdict instead of a central
  declaration.** Folds product-scope into the taxpayer-model verdict enum. Rejected
  — "the product does not yet support this modelo" is a product-scope fact, not a
  taxpayer-model derivation; conflating them pollutes the applicability semantics.
  Out-of-scope becomes a central typed declaration analogous to
  `NON_REGISTRY_MODELOS`.

## Decisions

1. **The coverage invariant (Decision 1).** Every modelo in
   `registry_modelo_codes()` MUST resolve, at obligation determination, to exactly
   one of: **surfaceable** (has a resolved window AND a seed rule), **advised** (an
   `INCOMPLETE` / window-missing state that raises a default-visible advisory), or
   **explicitly out-of-scope** (a central declaration with a recorded reason). No
   fourth "silently absent" state is permitted. The default surfacing changes: the
   calendar always computes an `ObligationCoverageReport`, and the CLI emits a
   default-on advisory `Notice` counting and naming the advised set. Confident
   negatives stay suppressed without an advisory (they are answered);
   `--show-suppressed` reveals per-entry detail, it is no longer the only signal
   that anything was dropped.

2. **Window-less-but-applicable (Decision 2).** Author the missing deadline
   window(s), legally grounded and corpus-verified. Modelo 190 is the sole class-B
   modelo: a 1–31 January annual resumen window shaped like Modelo 180/390,
   grounded in RD 439/2007 art. 108 and the approving Orden.

3. **Window-but-no-seed (Decision 3, class C: 123 232 322 353 360 369).** Per
   modelo, either author a seed applicability rule so it surfaces when applicable,
   or classify it as "applicability-undetermined → investigate" (advised) — never
   default-invisible. Ratified dispositions: 123 → payer-fact seed rule (like
   111/115); 322/353 → enrolment-gated (grupo de entidades IVA); 369 →
   enrolment-gated (OSS); 232 and 360 → advised-only initially. Exact legal
   grounding is deferred to the plan.

4. **Neither-table (Decision 4, class D: 036 151 193 210 308 309 714 840).** Per
   modelo, either promote to window+rule or declare **explicitly out-of-scope with
   a recorded reason** in the central declaration; fix the empty
   `deadline_windows = []` in 308/309. Initial dispositions to ratify in the plan:
   036 (censo) and 840/714 (patrimonio) likely out-of-scope for the autónomo/PYME
   core; 193/210 candidates for window+rule. Every class-D modelo ends the campaign
   either surfaceable or explicitly out-of-scope.

5. **The completeness invariant test.** A test iterates the full
   `registry_modelo_codes()` set and asserts each modelo lands in exactly one
   disposition (surfaceable / advised / out-of-scope), asserting *resolved*
   windows rather than key presence so an empty `deadline_windows = []` cannot pass
   as coverage. This is the anti-silent-drop gate; it is what would have caught
   M190.

## Constraints

- **Parent-feature stability.** The deadline engine (`2026-04-12-deadline-engine-
  adr`), the seed applicability table, and the registry authority are mature and
  in production; this ADR reconciles their coverage rather than reshaping them. No
  frontier risk.
- **Concurrent-agent worktree.** The registry/deadlines tree carries live peer WIP
  (currently `verification_predicates.toml` files under a separate feature). The
  plan must `git diff` each file before edit and abort on non-authored WIP; the new
  windows and the central out-of-scope declaration are additive and touch files the
  verify-nonzero feature does not.
- **Legal grounding is blocking per window.** No new deadline window ships without
  its publishing-instrument citation resolved against the bundled corpus. This
  gates Decision 2 and any window authored under Decisions 3–4.
- **DTO shapes are sound and frozen.** The calendar DTOs are not to be reshaped
  beyond adding the `ObligationCoverageReport`; `revision-resolution-is-law-
  determined` for surfaced modelos is preserved.

## Implementation

A single coverage-reconciliation function, owned by the overview application
layer, walks `registry_modelo_codes()` for a given profile and range and returns
a typed `ObligationCoverageReport`: the surfaced set (already in `entries`), the
confident-negative set (answered, no advisory), the advised set (`INCOMPLETE` /
window-missing, with per-modelo reason), and the explicitly-out-of-scope set
(read from the central declaration). `build_overview_calendar` always attaches
the report to `OverviewCalendar`; `agenda`/`backlog` inherit it through
composition. The CLI projects the advised set into a default-on `Notice` (count +
modelo list + the `overview explain <modelo>` follow-up), leaving `--show-
suppressed` to control per-entry detail only.

New deadline windows (M190 first, then the Decision-3/4 promotions) land in the
registry authoring tree in the established inline-or-fragmented shape, each with
`legal_refs` resolving to a legal-catalogue entry whose `corpus_ref` points at the
bundled authoritative text. The central out-of-scope declaration is a typed frozen
mapping in `core` (modelo → recorded reason), analogous to `NON_REGISTRY_MODELOS`,
consumed by both the reconciliation and the completeness test. Seed rules added
under Decision 3 follow the existing `ModeloApplicabilityRule` shape (payer-fact
or enrolment-fact gated, legally grounded). The completeness invariant test is the
enforcement surface. Empty `deadline_windows = []` declarations (308/309) are
resolved as part of their class-D disposition.

## Rationale

O1 is the only option that closes both silent-drop points from one authority and
prevents the next gap rather than only patching today's (research F6, F9). Routing
the advisory through the typed `Notice` channel honours
`cli-notices-are-the-only-diagnostic-channel` and keeps JSON and text in
lock-step; keeping out-of-scope as central data rather than an applicability
verdict (rejecting O4) keeps the taxpayer-model semantics clean (research F8). The
completeness test driven from `registry_modelo_codes()` is what structurally
distinguishes this from the Cluster-C data-backfill (O3): it asserts *resolved*
coverage over the full set, so a future windowless-but-applicable modelo fails CI
the moment it is added, exactly as M190 would have (research F5, F9).

## Consequences

- **Gains.** The overview surface becomes honest by construction: an operator can
  trust that absence-of-advisory means "positively answered", and any obligation
  the system cannot confidently scope is counted and named by default. The
  completeness test freezes the invariant so coverage can only ratchet up.
- **Costs.** Every registry modelo now needs an explicit disposition; the class-C
  seed rules and class-D out-of-scope reasons are real per-modelo work requiring
  legal grounding, and the M190 window (and any Decision-3/4 windows) must be
  corpus-verified before shipping. The default advisory adds a `Notice` to
  previously-clean output; it must be scoped tightly to `INCOMPLETE` /
  window-missing so it does not become ignorable noise (the confident-negative
  exclusion is load-bearing).
- **Pathways.** The central out-of-scope declaration and the completeness test give
  a durable home for future modelo onboarding: adding a modelo forces a
  disposition, and the advisory framework is reused for any later coverage class.
- **Pitfalls.** If the advisory is not tightly scoped it re-creates the alert
  fatigue this ADR exists to prevent; if a new window is authored without corpus
  verification it violates the grounding rules; if the out-of-scope declaration is
  used to silence a genuinely-applicable modelo it re-opens the very gap being
  closed — the recorded-reason requirement and code review are the guardrails.
