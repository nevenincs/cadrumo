---
tags:
  - '#plan'
  - '#quality-gate-zero-closure'
date: '2026-08-24'
tier: L3
related:
  - '[[2026-08-24-quality-gate-zero-closure-adr]]'
  - '[[2026-08-24-quality-gate-zero-closure-static-gate-matrix-research]]'
  - '[[2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference]]'
  - '[[2026-07-14-honest-all-green-adr]]'
  - '[[2026-06-09-quality-hardening-campaign-adr]]'
  - '[[2026-06-04-repo-health-triage-adr]]'
  - '[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]'
  - '[[2026-09-07-quality-gate-zero-closure-blind-green-measurement-research]]'
  - '[[2026-09-07-quality-gate-zero-closure-gate-consumer-parser-blindness-audit]]'
modified: '2026-09-07'
body_hash: 'sha256:7b7bcd869ff8925865e8a6ab981084be9d4280ec03c10ef91b8b0e0da0392f6c'
---

<!-- RETIRED: W01, W02, W03, W04, W05, W06, P01, P02, P03, P04, P05, P06, P07, P08, P09, P10, P11, P12, P13, P14, P15, P16, P17, P18, P19, P21, P22, S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S12, S13, S14, S15, S16, S17, S18, S19, S20, S21, S22, S23, S24, S25, S26, S27, S28, S29, S30, S31, S32, S33, S34, S35, S36, S37, S38, S39, S40, S41, S42, S43, S44, S45, S46, S47, S48, S49, S50, S51, S52, S53, S54, S55, S56, S57, S58, S59, S60, S61, S62, S63, S64, S65, S66, S67, S68, S69, S70, S71, S72, S73, S74, S75, S76, S77, S78, S79, S80, S81, S82, S83, S84, S85, S86, S87, S88, S89, S90, S91, S92, S95, S96, S97, S98, S99, S100, S101, S102, S103 -->

# `quality-gate-zero-closure` plan

## Description

This L3 roll-up is repurposed. Its original scope - activating the rolling ratchet controller from 2026-08-24-quality-gate-zero-closure-adr - is superseded: the controller's speculative activation Phases are retired into the record above, and this plan now owns the implementation surface named by 2026-09-07-quality-gate-zero-closure-blind-green-gates-adr. Wave W07 remains as the two closed observation Steps that were actually performed.

The subject is a gate that is green because it cannot fail. Every standing gate decision here governs a gate that can go red; none governs one that stays green through the exact defect it was written to catch. Wave W08 installs the instruments that detect that condition: mutmut first as the prerequisite ground truth, then one structural detector per mechanically decidable class, a both-locales condition over the locale detector's hit set, and a conformance gate that closes the absence-assertion class by requiring the canonical accessor or a site-naming declaration. No Phase creates a CI lane; the detector gates land where the per-push lane already looks.

Completion is over mechanisms proven to bite, never over an exhausted population; the Verification section states the end signal exactly. No Step permits a baseline, threshold, new exclusion, suppression, skip, xfail, mock, monkeypatch, tautological assertion, or hidden allowlist to make a red signal disappear, and no Step is satisfied by a mutation score. Model routing is stable: Luna max owns audits, type and mechanical work, Terra xhigh owns fixes and refactors, and Sol handles architecture decisions only.

## Steps

## Wave `W07` - observation performed before the repurpose

Historical. This Wave was the rolling ratchet controller's activation, and its repair, recheck and checkpoint Phases are retired into the record above. Only the two observation Steps below were performed. The controller described by 2026-08-24-quality-gate-zero-closure-adr is accepted and now has no installation plan; a successor plan must be opened to install it, and that loss is recorded in the amendment to that ADR rather than absorbed here.

### Phase `W07.P20` - observe and claim the live revision

At each observation, capture the current HEAD and gate state, redeclare semantic ownership, and claim only current disjoint work. The live owner queue belongs in execution evidence, never in this plan.

- [x] `W07.P20.S93` - Observe the current branch revision, dirty paths, ownership context, and gate state, recording revision-scoped evidence without treating any result as a baseline (Luna max audit and mechanical); `.vault/exec/`.
- [x] `W07.P20.S94` - Redeclare semantic canonical homes and consumer ownership against the indexed live source, persisting only current RAG evidence (Luna max audit); `.vault/audit/`.

## Wave `W08` - detect blind green

Install the instruments that detect a gate which cannot fail for the reason it was written, per 2026-09-07-quality-gate-zero-closure-blind-green-gates-adr. Each Phase is one domain and is independently completable; a Phase may be added when a new decidable class is measured, or contracted when a class is shown undecidable or empty. Completion is over mechanisms proven to bite, never over an exhausted population.

### Phase `W08.P27` - install mutmut as the prerequisite instrument

Mutation testing is the direct measurement of whether an assertion can fail, so it is installed first and the structural detectors are built against a tree it can already judge. mutmut is the only tool adopted: it is the maintained, reputable option, and a second mutation engine would split the evidence. Scope is bounded per package rather than whole-suite, because this suite carries a recorded history of multi-hour wedged runs. A surviving mutant is a finding, never a metric to optimise.

- [x] `W08.P27.S104` - Install mutmut as a declared development dependency and pin it, adding no second mutation engine, and record the exact invocation so a run is reproducible outside CI (Terra xhigh fixes and refactors); `pyproject.toml, uv.lock`.
- [x] `W08.P27.S105` - Run mutmut against one bounded package and record wall clock, mutant count, killed and surviving counts, establishing this suite's real cost per package rather than an assumed one (Luna max audit and mechanical); `.vault/audit/`.
- [x] `W08.P27.S106` - Triage the surviving mutants into assertions that cannot fail versus mutants that are semantically inert, since an equivalent mutant is not a gate defect and treating it as one would manufacture work (Luna max audit); `.vault/audit/`.
- [x] `W08.P27.S107` - Declare the standing mutmut scope and cadence from the measured cost, naming which packages are in scope and how a run is triggered, verify-only and outside commit time (Sol architecture); `.vault/adr/`.

### Phase `W08.P23` - correct the recorded boundary

The scanner docstring claims to be the only mechanically catchable member of the gate-integrity family. Measurement refuted that, and the claim is why four decidable classes went unbuilt. Correcting it is the precondition for the rest of the Wave, because the record is what stopped the work.

- [x] `W08.P23.S108` - Correct the refuted boundary claim in all three places it lives: rewrite the scanner docstring to state which classes are decidable and which are not, and cross-link the audit finding and the closed tui-interface Step row to this decision rather than rewriting them, so the correction travels with the surfaces a future reader treats as durable (Luna max audit and mechanical); `dev/quality/tautological_assertion_scan.py, .vault/`.

### Phase `W08.P24` - structural detectors for the decidable classes

One AST sweep per decidable class in dev/quality/, each exercised by a gate under dev/quality/tests/ carrying a positive control and an anti-vacuity floor, and each killed by mutmut so the instruments meet the standard they enforce. That directory is already in the per-push test-dev-ci path set, so no lane is created and no workflow file is touched. The measured decidable classes are subsuming disjunction and self-echoing token; the never-emitted-literal proposal is contracted by S110 after the stricter live join proves that legitimate runtime-produced guards have the same AST and corpus facts. Detectors are made precise about legitimate shapes; where precision cannot separate a legitimate site from a defect, the class is contracted rather than hidden behind an exemption or declaration.

- [x] `W08.P24.S109` - Land the subsuming-disjunction detector: an assertion whose or-operands share one haystack and where one needle contains another is exactly the weaker operand, so the specific claim is never required (Terra xhigh fixes and refactors); `dev/quality/`.
- [x] `W08.P24.S110` - Contract the proposed never-emitted-literal detector after the stricter real-tree corpus join demonstrates that source absence cannot distinguish blind assertions from valid runtime-produced guards, retaining the result as measurement evidence rather than shipping an exclusion-backed gate (Terra xhigh fixes and refactors); `.vault/audit/, dev/quality/`.
- [x] `W08.P24.S111` - Land the self-echoing-token detector: an assertion keyed on a token the invocation itself supplies, which the refusal quotes back verbatim, cannot separate a retired surface from one that resolved and failed otherwise (Terra xhigh fixes and refactors); `dev/quality/`.
- [x] `W08.P24.S112` - Give every detector a gate carrying a positive control that fires on a representative defect and an anti-vacuity floor that fails when the swept population collapses, refusing any detector that ships without both, and kill each detector's own gate with mutmut (Luna max audit and mechanical); `dev/quality/tests/`.
- [x] `W08.P24.S113` - Land the detector gates under dev/quality/tests/, which the per-push test-dev-ci path set already invokes, adding no lane and touching no workflow file so ci-lane-deconflation keeps sole ownership of that surface, and prove the existing lane runs them (Luna max audit and mechanical); `dev/quality/tests/`.

### Phase `W08.P25` - the both-locales condition

Flipping the ambient locale does not retire the locale-bound classes: it mirrors them, and it cannot reach a test that pins its own locale at the call site, which is one of the two sanctioned repairs. The condition is that every assertion in the locale detector's hit set passes under the ambient locale and under a second one, delivered as a parameterised re-run of the affected assertions rather than a CI lane, so no workflow surface is touched. The mechanism must be demonstrated failing before any repair it surfaces; a seeded instance removed once recorded is accepted, because the classes here were found by repairing them and a real unrepaired instance may not exist.

- [x] `W08.P25.S114` - Land the locale-bound assertion detector, joining each asserted literal against all four catalogues and enumerating the pinning forms from their declaration site rather than from observed usage -- _LANGUAGE_FLAGS, _LANGUAGE_FLAG_PREFIXES and the environment variable in language_argv.py, which together cover --lang and the spliced --flag=LANG spellings no test currently uses (Terra xhigh fixes and refactors); `dev/quality/`.
- [x] `W08.P25.S115` - Deliver the both-locales condition over the locale detector's hit set as a parameterised re-run rather than a CI lane, since flipping the ambient locale only mirrors the vacuity and cannot reach a test that pins its own locale, and demonstrate it failing first -- preferring the live residual instance, else seeding synthetic in-memory source or an isolated fixture, never the shipped tree (Terra xhigh fixes and refactors); `dev/quality/, dev/quality/tests/`.
- [ ] `W08.P25.S116` - Repair the locale-dependent assertions the axis surfaces, replacing each with the stable transport token it stood for or with an explicit locale pin, and reporting a removed redundant branch as a strengthening rather than a defect fixed (Terra xhigh fixes and refactors); `src/cadrumo/`.

### Phase `W08.P26` - close the absence-assertion class by mechanism

The void-assertion audit measured a population and also wrote the rule that closes it: an absence assertion in a module mentioning a taxonomy token either routes through the canonical accessor or carries a declaration naming its own site. Importing the population without the rule is what would leave this open forever, because the count is a floor the instrument cannot bound and the audit demonstrated its own blind spot by missing one of its sites. The population is re-measured only to scope the work; the conformance gate is what closes the class.

- [x] `W08.P26.S117` - Re-measure the absence-assertion population at the current revision to scope the work, recording the sampling frame and treating the figure as context rather than as a pass condition, since the 2026-08-04 numbers describe a tree that has moved (Luna max audit); `.vault/audit/`.
- [ ] `W08.P26.S118` - Close the class with the mechanism the source audit proposed: an absence assertion in a module mentioning a taxonomy token either routes through the canonical accessor or carries a site-naming declaration, enforced by a conformance gate that fails on both a stale declaration and an undeclared site (Terra xhigh fixes and refactors); `dev/quality/, dev/quality/tests/`.

### Phase `W08.P28` - verdict-layer blind green

Extend the family from assertions to verdicts. A gate's reporting layer converts output into a pass/fail claim, and `dev/audit/report.py` did so with a containment test that could not represent nine of twelve real contract verdicts -- green, accurately named, and blind for months. Close that decidable class, and bring the second hand-maintained census to the sanctioned declaration pattern rather than tidying its rows.

- [x] `W08.P28.S119` - Repair the import-linter verdict parser in dev/audit/report.py so a contract verdict is read as the last word before its optional parenthetical rather than by suffix containment, since `KEPT (3 ignored imports)` is the form nine of twelve contracts emit and the layer that exists to detect an aborted run could not see any of them (Terra xhigh fixes and refactors); `dev/audit/report.py`.
- [ ] `W08.P28.S120` - Land the verdict-grammar detector: a containment, prefix or suffix test applied to a gate output token whose real grammar admits a trailing parenthetical is fixed on the weaker reading and cannot fail for the reason it was written, decidable from the AST joined against the gate's declared output shape (Terra xhigh fixes and refactors); `dev/quality/`.
- [ ] `W08.P28.S121` - Give the verdict-grammar detector a gate carrying a positive control that fires on the repaired report.py shape and an anti-vacuity floor that fails when the swept verdict-consumer population collapses, and kill that gate with mutmut under the standing scope (Luna max audit and mechanical); `dev/quality/tests/`.
- [ ] `W08.P28.S122` - Reconcile the live two-drift-direction deferred-edge declaration: remove the 26 stale rows, classify the 8 undeclared live edges with checked site-specific rationale, and retire the generic _DECLARED aggregate in favour of PINNED_DEFERRED_CROSS_LAYER_IMPORTS, since the existing undeclared and stale tests correctly failed in both directions (Terra xhigh fixes and refactors); `src/cadrumo/tests/`.
- [ ] `W08.P28.S123` - Replace the banned unittest.mock spy in dev/registry/newmodelo/tests/test_manager.py with observation of the real cache through the public loader's object identity, so the assertion fails when the production reset call is removed rather than merely recording that a call occurred (Terra xhigh fixes and refactors); `dev/registry/newmodelo/tests/`.

## Parallelization

W08.P27 is a hard prerequisite. mutmut must be installed and measured before the detector Phases, because a detector built with no way to check that it can itself fail is the artefact this plan exists to remove. P23 is a one-Step documentation correction and may run alongside P27.

After P27, P24 and P25 are independent of each other and may run in parallel: they add different modules under dev/quality/ and different gates under dev/quality/tests/, which the per-push test-dev-ci path set already invokes. No Phase edits the justfile or a workflow file, so there is no shared lane surface to contend over and ci-lane-deconflation keeps sole ownership of it. What each Phase must still prove is that the existing lane actually runs its gate: residence in that directory is necessary but not sufficient, because the lane's marker expression deselects an unmarked test. P26 depends only on P27 and may run at any point after it; its measurement is what tells the detector Phases whether a further class is worth a gate at all.

Within P25 the order is strict: the axis must be demonstrated failing against a real locale-dependent assertion before that assertion is repaired, or the axis is never shown to bite. Repairs under P25 touch src/cadrumo/ while other sessions are editing it, so each batch stages only its own files and absorbs no unrelated change. Luna max performs audits, type and mechanical checks, and evidence review; Terra xhigh performs fixes and refactors; Sol is reserved for architecture.

## Verification

This plan is complete when the instruments exist and are proven to bite. It is not complete when the tree is free of blind assertions, and it never claims that. Completion of this plan does not assert permanent codebase sanity or close future work.

All five conditions, each evidenced:

1. mutmut is installed and pinned, one bounded package carries a recorded measurement of wall clock and killed and surviving counts, survivors are triaged into real findings and semantically inert mutants, and the standing scope and cadence are declared from that measured cost.
2. The tautological-assertion scanner's recorded boundary is corrected and names which classes are decidable by static analysis and which remain a human question.
3. Every decidable class named in the governing decision has a detector that sweeps the real tree, carries a passing positive control and an anti-vacuity floor, lives under `dev/quality/tests/` so the existing per-push lane invokes it, and has had its own gate killed by mutmut.
4. The both-locales condition holds over the locale detector's hit set and has been demonstrated failing against a locale-dependent assertion before any repair it surfaces - real, or seeded for the demonstration and removed once recorded.
5. An absence assertion in a module that mentions a taxonomy token either routes through the canonical accessor or carries a declaration naming its own site, enforced by a conformance gate that fails on both a stale declaration and an undeclared site. The re-measured population is context for scoping, never the pass condition.

Condition 3 is load-bearing: it is satisfied by mechanisms that demonstrably fail on a real defect, not by a count of sites repaired. Condition 5 is deliberately a mechanism rather than a disposition of a measured population, because that count is a floor the instrument cannot bound. No condition is satisfied by exhausting a list, by a mutation score, or by a threshold, baseline, exclusion, suppression, skip, xfail, or unchecked allowlist. No Step creates a CI lane or edits a workflow file; `ci-lane-deconflation` keeps that surface. Terra xhigh repairs and refactors with real behavior proof; Luna max runs audits, type and mechanical checks, affected-gate checks, and evidence review; Sol handles architecture only.

A Phase may be added when a new decidable class is measured, or contracted when a class is shown undecidable or empty. Both require evidence and neither reopens the completion condition. Findings produced after this plan closes are routed as ordinary owner work under the rolling ratchet, which is what that controller is for.
