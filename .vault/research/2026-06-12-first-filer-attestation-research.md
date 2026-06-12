---
tags:
  - '#research'
  - '#first-filer-attestation'
date: '2026-06-12'
related:
  - "[[2026-06-05-cross-period-filing-clean-state-adr]]"
  - "[[2026-06-05-cross-period-calculation-guards-adr]]"
  - "[[2026-06-10-period-revision-resolution-adr]]"
---

# `first-filer-attestation` research: `first-period filer dead end: censo-grounded vs attested no-prior-obligation`

A business that starts economic activity in 2025 4T cannot locally file its first period. It truthfully binds `irpf.previous_year_economic_activity_net_income = 0` and `modelo-130-resultados-negativos-anteriores = 0` (no prior activity existed), yet `work verify` blocks with `cross_period_dependency_unclean`, demanding official AEAT evidence for a Modelo 100 year 2024 filing and a Modelo 130 2025 3T filing that never existed. Because local `file` requires `verified_complete`, the very first period is structurally unfileable.

### Worked failure case: round-5 operator evidence proves the loop is fully closed

Round-5 operator testing exhaustively mapped every exit from the dead end at HEAD and confirmed there is no legitimate offline path out:

- `work verify` blocks on `cross_period_dependency_unclean` (M100 2025 0A) even when the prior-year binding is explicitly supplied as 0 — confirming the gate evaluates filing-record existence, not binding values.
- `export` refuses drafts: `current revision is still draft; verify it before exporting`. Workbook export is therefore unreachable.
- `file` refuses non-verified revisions: `filing requires a verified-complete revision`. A local filing record is therefore unreachable.
- The only gate-satisfying routes are `live filed pull-sources` (live AEAT read), `reconcile file --file` (requires a real justificante PDF), or `filing-record import --evidence-kind aeat_justificante_pdf|aeat_csv_register|aeat_live_capture --evidence-id <id>` — and the import honesty gate correctly refuses any evidence id that is not a persisted real artefact.

All three routes demand official AEAT evidence of a filing that never existed, so a first-time filer can never reach workbook export OR a local filing record by any legitimate offline path. The loop is closed: verify blocks file, file requires verify, and the only key that opens verify is evidence the legal world never minted.

Notably, `filing-record import` accepts exactly the evidence-kind set `_OFFICIAL_SOURCE_KINDS` enumerates (`aeat_justificante_pdf`-class artefacts mapping to `aeat_sede_justificante` / `aeat_csv_register` / `aeat_live_capture`). The gate architecture is *coherent* — every door checks the same official-evidence invariant, and the import honesty gate is right to refuse fabricated ids. The defect is not an inconsistent gate; it is the absence of any vocabulary, anywhere in the architecture, to express that no prior obligation existed.

## Findings

### 1. Current mechanics at HEAD: why a truthful zero still blocks

The clean-state gate lives in `src/aeat/application/calculations/_cross_period_clean_state.py` (HEAD `bb3cfa9c9`, with minor uncommitted peer WIP adding the `_aeat_register_provenance_blockers` ALTA/identity check; read-only confirmed, the WIP does not touch the first-period surface). Its decision pipeline:

- `cross_period_dependency_requirements(snapshot)` derives the requirement graph purely from the registry snapshot, folding `previous_filing_observation_requirements` (direct `previous_filing` bindings) and `relation_source_requirements` (registry relations). Nothing consults the taxpayer history, activity-start date, or whether a prior obligation ever existed; it asks only whether this revision binding selector resolves to a prior period.
- For each derived `CrossPeriodDependencyRequirement`, `_evaluate_requirement` then `_evaluate_filing_history` calls `filing_catalogue.history_for(...)`. For a first-period filer there is no `ModeloRecord` for the prior period, so `current_filings` is empty, `filing is None`, and the function appends `MISSING_CURRENT_FILING_RECORD` (line ~921). That is the first and load-bearing blocker: the verdict is unclean before evidence is even considered.
- Where a stale local-only observation exists, the secondary gate is `_filing_external_evidence_blockers`: if `filing.external_evidence is None` and the observation `source_kind not in _OFFICIAL_SOURCE_KINDS` (`aeat_sede_justificante`, `aeat_sede_live_capture`, `aeat_csv_register`), it adds `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`. The non-official local-filing kind `app_filing` (per `local-filed-observations-are-non-official-evidence`) deliberately never satisfies this gate. That rule is correct and must be preserved; it is not the bug. The bug is upstream: the requirement should never have been raised for a period in which the taxpayer had no filing obligation.

**The precise check a truthful zero fails.** The zero is honest, but the gate does not evaluate the binding value; it evaluates the existence and evidence of an upstream filing record for every registry-resolved anchor. A zero binding still produces an anchor. For M100, `selector = { source_modelo = "100", source_output = "1391", filing_year_delta = -1, period = "0A" }` (`0048-renta-2025-base-liquidable-negativa-anterior.toml`) resolves to a required 100 / 2024 / 0A filing. For M130, `selector = { source_modelo = "130", source_output = "saldo-negativo-fin-periodo", source_period_offset_from_target = -1, max_year_delta = 0 }` (`0001-bindings.toml`) resolves 3T anchor to a required 130 / 2025 / 2T filing. There is no value channel by which "I started activity this period, so the prior anchor is not owed" can be expressed: the requirement is structural.

**Does any existing path express no-prior-obligation?** Partially, at one narrow grammar level. The M130 `required_period_anchors_for_target` / `_PreviousModeloSelector` machinery in `_bindings_previous_filing.py` already implements period-level absent-by-design: with `source_period_offset_from_target = -1` and `max_year_delta = 0`, 1T produces no anchor at all ("1T produces no anchor (absent-by-design) because AEAT rule restricts carry-forward to prior trimestres within the same ejercicio"). So the registry has a vocabulary for "this anchor is legitimately absent", but it is keyed on calendar position within the ejercicio, not on the taxpayer activity-start date. There is no activity-start-scoped absence: a 4T-start filer 3T anchor (M130) and prior-year anchor (M100) are still demanded. No binding flag, registry declaration, or operator input scopes the dependency set by when the obligation began. This is the exact missing concept.

### 2. Legal reality: the alta is the real-world first-period evidence

Spanish tax law does not require a first-period filer to have filed anything for periods before their activity began. The obligation to file Modelo 130 (pago fraccionado IRPF, estimacion directa) arises from carrying on economic activity; RD 439/2007 art. 110 governs the cumulative-from-start-of-activity computation. The registry income binding (`modelo-130-actividad-economica-ingresos-cumulative`) describes casilla 01 as cumulative year-to-date, and the resultados-negativos-anteriores carry is grounded in RD 439/2007 art. 110.5 as a same-ejercicio prior-quarter carry only (max_year_delta = 0; legal refs rd-439-2007:art-110, orden-eha-672-2007:art-1, ley-35-2006:art-99, rd-439-2007:art-95). A quarter before the activity began has no prior saldo to carry: the carry is null, not unevidenced. The M100 prior-year-negative carry cites Ley 35/2006 art. 48 (base imponible general negativa, four-year carry-forward); a first-year filer has no prior ejercicio that could have generated the saldo.

The real-world evidence that activity started in period X is the alta de nueva actividad in the censo (Modelo 036/037 census declaration). AEAT publishes it on the G313 Mis Datos Censales page, and the codebase already captures it. CensoSnapshot.censo_facts (`src/aeat/application/live/_censo.py`) carries the dotted key censo.activity_start_date (line ~78), populated from the live G313 sede read; the schema field activity_start_date exists on SetupAnswers (`src/aeat/core/setup_answers.py:214`) with ISO-8601 validation, and the wizard catalogue binds profile_key = censo.activity_start_date (`application/wizard/_catalogue.py:411`). The censo snapshot is persisted at IDENTITY sensitivity, content-addressed, and lifecycle-managed (ACTIVE / SUPERSEDED / DISCARDED); the docstring states AEAT is the binding legal source of truth for censo data and the local profile is a cache that must be kept honest.

So the codebase already holds a legally-grounded, AEAT-sourced start-of-activity fact. It is captured but never consumed by the cross-period clean-state gate, the calculation actions, or the overview calendar (grep confirms no activity_start reference in `application/calculations/` outside the unrelated iva-wallet module, and none in `application/overview/_calendar.py`). The grounding source exists; it is simply not wired into the dependency-scoping decision.

### 3. Design options

Evaluated against `no-silent-under-declaration`, `aeat-safety-legal-gates`, `local-filed-observations-are-non-official-evidence`, and `carried-observations-stamp-their-revision`.

**Option A: censo-grounded activity-start scoping (recommended).** Teach the requirement derivation that a dependency anchor whose period falls strictly before the taxpayer censo.activity_start_date is absent-by-design, generalising the M130 1T absent-by-design vocabulary from calendar position in ejercicio to activity-start boundary. The date is read from the ACTIVE CensoSnapshot (AEAT-sourced), not the free-text profile field, so the determination is grounded rather than asserted. A suppressed requirement produces no blocker; the binding value resolves to Decimal zero through the existing absent-by-design path with a provenance marker.

- What blocks dishonesty: the fact is sourced from the AEAT G313 censo snapshot, which the operator cannot forge without forging an AEAT-signed read. A real prior filing that post-dates the alta is still in scope and still demands evidence; only periods genuinely before the alta are suppressed, so an operator cannot scope away a real prior obligation that fell after activity start.
- Audit trail: the suppressed requirement carries a typed provenance marker naming the censo snapshot id and the activity-start date that scoped it out; the CrossPeriodDependencyEvidence row records no-obligation pre-activity-period rather than a silent omission, satisfying `no-silent-under-declaration`.
- Blast radius: touches cross_period_dependency_requirements / required_period_anchors_for_target (or a new application-layer filter over the derived requirements), the evaluate_cross_period_clean_state call site (must receive the activity-start date), and relation derivation. It does not weaken the evidence gate for in-scope periods and leaves _OFFICIAL_SOURCE_KINDS / app_filing untouched. Risk: a stale or absent censo snapshot; the gate must fail safe (block, demand a censo pull) not open.

**Option B: explicit operator attestation verb/flag.** A verb such as work attest no-prior-obligation --modelo 130 --year 2025 --period 2T records a typed non-official observation asserting the prior period carried no obligation; the gate treats a present attestation as satisfying the requirement, with a permanent advisory.

- What blocks dishonesty: nothing structural; a bare operator claim. The only brake is the advisory and the non-official source_kind (it must NOT enter _OFFICIAL_SOURCE_KINDS, exactly as app_filing must not). An operator could falsely attest away a real prior filing.
- Audit trail: a typed attestation observation with actor, timestamp, non-blocking advisory; the carry must still stamp the source revision per `carried-observations-stamp-their-revision`.
- Blast radius: new CLI verb, observation kind, advisory code, gate change. Higher dishonesty surface than A; weaker legal grounding because operator-supplied, which `aeat-safety-legal-gates` cautions against (do not treat user preference as authority for regulated calculations).

**Option C: registry-declared first-period semantics.** Extend the selector grammar so a previous_filing selector can declare a first-period sentinel such as first_period_yields_zero = true, so the registry asserts a missing prior anchor is null.

- What blocks dishonesty: the registry is authority, the strongest grounding for the value. But the registry cannot know which period is a given taxpayer first; it declares carry-forward semantics, not the activity-start boundary. C alone cannot distinguish first-period-for-this-taxpayer from an interior period the taxpayer failed to file; it must combine with A to be safe.
- Audit trail: legal refs already cite RD 439/2007 art. 110.5; a first-period facet would be grounded in the same provision.
- Blast radius: selector schema change rippling through the loader, the strict resolvers in `_bindings_previous_filing.py`, and every revision declaring a carry. Broad and registry-wide; per `aeat-registry-authority-flow` it must ride the loader/compiler. Best a complement to A (A scopes which periods are pre-activity; C or the existing absent-by-design path materialises the zero).

### 4. Prior art in-vault

- `2026-06-05-cross-period-filing-clean-state-adr` (accepted): the ADR that introduced the gate, and the most important prior art. It reasons entirely from Modelo 390 aggregates already-filed IVA periods, assumes every cross-period dependency is a real prior obligation (the required modelo/filing-year/period/member exists), and contains no first-period or no-prior-obligation or activity-start carve-out. Its fail-closed-when-upstream-filing-history-is-incomplete consequence is exactly what traps the first-period filer. An amending ADR must scope its requirement graph by activity start.
- `2026-06-05-cross-period-calculation-guards-adr` (accepted): sibling ADR mandating the requirement graph be registry-derived from the selected RegistrySnapshot and that callers cannot pass a smaller ad hoc dependency set. Option A must thread this carefully: activity-start scoping must be a grounded narrowing (driven by the AEAT censo fact), not an ad hoc caller shrink.
- `2026-06-10-period-revision-resolution-adr` (accepted): carried observations stamp and re-confirm their source revision (Ruling 3 / R2), already enforced in _revision_carry_check. A suppressed pre-activity period has no observation to stamp, so the carry resolves to a provenance-marked zero, not an unstamped carry.
- `2026-06-03-m303-cross-period-carry-continuity-adr`: M303 IVA wallet cross-period continuity; a second worked example of the prior-period-assumed-to-exist pattern a first-period filer would trip.
- `2026-06-05-live-censo-calendar-reconciliation` (exec/plan, currently with uncommitted edits in the worktree): the feature that already pulls G313 censo facts and the natural home for consuming censo.activity_start_date into period scoping.

The `local-filed-observations-are-non-official-evidence` and `no-silent-under-declaration` rules are the load-bearing guardrails: the fix must scope which periods are owed without laundering a local chain into official evidence and without silently granting a zero; the suppressed dependency must be explained, not blanked.

## Recommended option and open questions

Recommended: Option A (censo-grounded activity-start scoping), with the existing absent-by-design value path of Option C materialising the zero. Option A is the only sketch whose no-prior-obligation determination is grounded in AEAT-sourced authority (the G313 censo activity_start_date) rather than a forgeable operator claim, so it satisfies `aeat-safety-legal-gates` and resists the dishonesty that sinks Option B; it reuses the registry existing absent-by-design vocabulary; and it preserves `local-filed-observations-are-non-official-evidence` untouched because it never touches the evidence gate for in-scope periods. It removes pre-activity periods from the requirement graph before evidence is demanded, and records the removal as declared, audited provenance rather than a silent blank.

Which refusal points the fix unblocks — and which it deliberately leaves blocking:

- `verify` (UNBLOCKED, the root fix): the pre-activity dependency is removed from the requirement graph with declared provenance, so the clean-state verdict for a genuinely first period comes back clean and verification can proceed to `verified_complete` on the merits of the current-period data alone.
- `export` (unblocked transitively, gate unchanged): export keeps refusing draft revisions; it opens only because verify can now legitimately complete. No export-side change is made or wanted.
- `file` (unblocked transitively, gate unchanged): local `file` keeps requiring a verified-complete revision; it opens for the same transitive reason. The resulting local filing record still persists its observation under the non-official `app_filing` source kind, so a *later* dependent period still demands real AEAT evidence of THIS filing per `local-filed-observations-are-non-official-evidence` — the first-filer fix does not weaken the chain for period two onward.
- `filing-record import`, `reconcile file`, `live filed pull-sources` (DELIBERATELY UNTOUCHED): the official-evidence honesty gates and the `_OFFICIAL_SOURCE_KINDS` set stay exactly as they are. The fix never mints evidence; it removes a demand for evidence of a filing the law never required.

Open questions an ADR must settle:

- Fail-safe on missing/stale censo. When no ACTIVE CensoSnapshot exists, or activity_start_date is blank, must the gate fail closed (block, demand aeat config profile censo pull) rather than fall back to unscoped behaviour? The research position is yes, fail safe; the ADR must rule.
- Snapshot vs. self-declaration. May scoping use the free-text SetupAnswers.activity_start_date as a fallback, or is the AEAT-sourced snapshot the only admissible authority? Per `aeat-safety-legal-gates` a self-declared field is weaker authority.
- Boundary semantics. Is the period containing the alta date in scope (first partial period equals first obligation) and only strictly prior periods suppressed? M130 cumulative-from-start semantics imply the alta-period itself is the first obligation; pin the boundary against `period-filter-single-boundary-authority`.
- Where scoping lives. Application-layer filter over derived requirements (keeps registry pure; treats censo as a grounded input) vs. a selector-grammar facet (Option C; broader blast radius). The research leans application-layer.
- Provenance shape. What typed marker records a suppressed pre-activity requirement so it is auditable and not silent: a new non-blocking enum member, or an explicit no_prior_obligation evidence facet citing the censo snapshot id and activity-start date?
- Relation dependencies. The M100 carry arrives via previous_filing, but registry relations (relation_source_requirements) also feed the graph; confirm the scoping applies uniformly to both origins.
