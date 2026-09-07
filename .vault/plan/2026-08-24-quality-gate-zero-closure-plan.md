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
modified: '2026-09-07'
body_hash: 'sha256:d8e0d7bdd61b0b08eaca584ab2508b984e5327f790c5d80ff150747282f16e15'
---

<!-- RETIRED: W01, W02, W03, W04, W05, W06, P01, P02, P03, P04, P05, P06, P07, P08, P09, P10, P11, P12, P13, P14, P15, P16, P17, P18, P19, P21, P22, S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S12, S13, S14, S15, S16, S17, S18, S19, S20, S21, S22, S23, S24, S25, S26, S27, S28, S29, S30, S31, S32, S33, S34, S35, S36, S37, S38, S39, S40, S41, S42, S43, S44, S45, S46, S47, S48, S49, S50, S51, S52, S53, S54, S55, S56, S57, S58, S59, S60, S61, S62, S63, S64, S65, S66, S67, S68, S69, S70, S71, S72, S73, S74, S75, S76, S77, S78, S79, S80, S81, S82, S83, S84, S85, S86, S87, S88, S89, S90, S91, S92, S95, S96, S97, S98, S99, S100, S101, S102, S103 -->

# `quality-gate-zero-closure` plan

## Description

This L3 roll-up is repurposed. Its original scope — activating the rolling ratchet controller from 2026-08-24-quality-gate-zero-closure-adr — is superseded: the controller's speculative activation Phases are retired into the record above, and this plan now owns the implementation surface named by 2026-09-07-quality-gate-zero-closure-blind-green-gates-adr. Wave W07 remains as the two closed observation Steps that were actually performed.

The subject is a gate that is green because it cannot fail. Every standing gate decision here governs a gate that can go red; none governs one that stays green through the exact defect it was written to catch. Wave W08 installs the instruments that detect that condition: mutmut first as the prerequisite ground truth, then one structural detector per mechanically decidable class, a locale axis that retires two classes by construction rather than by enumeration, and a recorded disposition of the re-measured candidate population.

Completion is over mechanisms proven to bite, never over an exhausted population; the Verification section states the end signal exactly. No Step permits a baseline, threshold, new exclusion, suppression, skip, xfail, mock, monkeypatch, tautological assertion, or hidden allowlist to make a red signal disappear, and no Step is satisfied by a mutation score. Model routing is stable: Luna max owns audits, type and mechanical work, Terra xhigh owns fixes and refactors, and Sol handles architecture decisions only.

## Steps

## Wave `W07` - activate the rolling ratchet controller

Establish the durable observe, claim, repair, recheck, and evidence loop for the live branch. This Wave activates the operating mechanism only; recurring operation continues as the branch evolves and no codebase-sanity closure is claimed.

### Phase `W07.P20` - observe and claim the live revision

At each observation, capture the current HEAD and gate state, redeclare semantic ownership, and claim only current disjoint work. The live owner queue belongs in execution evidence, never in this plan.

- [x] `W07.P20.S93` - Observe the current branch revision, dirty paths, ownership context, and gate state, recording revision-scoped evidence without treating any result as a baseline (Luna max audit and mechanical); `.vault/exec/`.
- [x] `W07.P20.S94` - Redeclare semantic canonical homes and consumer ownership against the indexed live source, persisting only current RAG evidence (Luna max audit); `.vault/audit/`.

## Wave `W08` - detect blind green

Install the instruments that detect a gate which cannot fail for the reason it was written, per 2026-09-07-quality-gate-zero-closure-blind-green-gates-adr. Each Phase is one domain and is independently completable; a Phase may be added when a new decidable class is measured, or contracted when a class is shown undecidable or empty. Completion is over mechanisms proven to bite, never over an exhausted population.

### Phase `W08.P27` - install mutmut as the prerequisite instrument

Mutation testing is the direct measurement of whether an assertion can fail, so it is installed first and the structural detectors are built against a tree it can already judge. mutmut is the only tool adopted: it is the maintained, reputable option, and a second mutation engine would split the evidence. Scope is bounded per package rather than whole-suite, because this suite carries a recorded history of multi-hour wedged runs. A surviving mutant is a finding, never a metric to optimise.

- [ ] `W08.P27.S104` - Install mutmut as a declared development dependency and pin it, adding no second mutation engine, and record the exact invocation so a run is reproducible outside CI (Terra xhigh fixes and refactors); `pyproject.toml, uv.lock`.
- [ ] `W08.P27.S105` - Run mutmut against one bounded package and record wall clock, mutant count, killed and surviving counts, establishing this suite's real cost per package rather than an assumed one (Luna max audit and mechanical); `.vault/audit/`.
- [ ] `W08.P27.S106` - Triage the surviving mutants into assertions that cannot fail versus mutants that are semantically inert, since an equivalent mutant is not a gate defect and treating it as one would manufacture work (Luna max audit); `.vault/audit/`.
- [ ] `W08.P27.S107` - Declare the standing mutmut scope and cadence from the measured cost, naming which packages are in scope and how a run is triggered, verify-only and outside commit time (Sol architecture); `.vault/adr/`.

### Phase `W08.P23` - correct the recorded boundary

The scanner docstring claims to be the only mechanically catchable member of the gate-integrity family. Measurement refuted that, and the claim is why four decidable classes went unbuilt. Correcting it is the precondition for the rest of the Wave, because the record is what stopped the work.

- [ ] `W08.P23.S108` - Amend the tautological-assertion scanner docstring to retire its claim that it is the only mechanically catchable member of the gate-integrity family, stating which classes are decidable by static analysis, which remain a human question, and the measured evidence for each (Luna max audit and mechanical); `dev/quality/tautological_assertion_scan.py`.

### Phase `W08.P24` - structural detectors for the decidable classes

One AST sweep per class in dev/quality/, each exercised by a gate in dev/tests/ carrying a positive control and an anti-vacuity floor, each registered in a named verify lane. Classes measured so far: subsuming disjunction, self-echoing token, never-emitted literal. Detectors are made precise about legitimate shapes rather than given exemption lists.

- [ ] `W08.P24.S109` - Land the subsuming-disjunction detector: an assertion whose or-operands share one haystack and where one needle contains another is exactly the weaker operand, so the specific claim is never required (Terra xhigh fixes and refactors); `dev/quality/`.
- [ ] `W08.P24.S110` - Land the never-emitted-literal detector: an absence assertion whose literal appears nowhere outside its own module cannot fail for the reason it was written (Terra xhigh fixes and refactors); `dev/quality/`.
- [ ] `W08.P24.S111` - Land the self-echoing-token detector: an assertion keyed on a token the invocation itself supplies, which the refusal quotes back verbatim, cannot separate a retired surface from one that resolved and failed otherwise (Terra xhigh fixes and refactors); `dev/quality/`.
- [ ] `W08.P24.S112` - Give every detector a gate carrying a positive control that fires on a representative defect and an anti-vacuity floor that fails when the swept population collapses, refusing any detector that ships without both, and kill each detector's own gate with mutmut (Luna max audit and mechanical); `dev/tests/`.
- [ ] `W08.P24.S113` - Register the detector gates in a named verify lane that CI invokes, verify-only and outside commit time, and prove the lane runs them rather than only declaring them (Luna max audit and mechanical); `justfile, .github/workflows/`.

### Phase `W08.P25` - the locale axis

A lane that runs tests under a non-ambient locale retires the locale-bound classes by construction rather than by enumeration, which is the only move here that scales better than the defect. The axis must be demonstrated failing against a real locale-dependent assertion before that assertion is repaired, so the axis itself is proven to bite. Detectors in this Phase must recognise all three pinning forms.

- [ ] `W08.P25.S114` - Land the locale-bound assertion detector, joining each asserted literal against all four catalogues and recognising the flag, root-option, and environment pinning forms, so a pinned test is not reported (Terra xhigh fixes and refactors); `dev/quality/`.
- [ ] `W08.P25.S115` - Add the non-ambient-locale test lane and demonstrate it failing against a real locale-dependent assertion BEFORE that assertion is repaired, so the axis is proven to bite rather than assumed to (Luna max audit and mechanical); `justfile, .github/workflows/`.
- [ ] `W08.P25.S116` - Repair the locale-dependent assertions the axis surfaces, replacing each with the stable transport token it stood for or with an explicit locale pin, and reporting a removed redundant branch as a strengthening rather than a defect fixed (Terra xhigh fixes and refactors); `src/cadrumo/`.

### Phase `W08.P26` - dispose the measured absence-assertion population

The void-assertion audit measured 400 absence assertions and deferred disposition to a follow-on plan. This is that plan. Sampling is drawn from the 155 candidates, never extrapolated from the 19 the original sweep happened to surface, and the disposition records its own sampling frame. The count is a floor the instrument cannot itself bound, so no Step here may be satisfied by exhausting a list.

- [ ] `W08.P26.S117` - Re-measure the absence-assertion population at the current revision and record the sampling frame, since the 400/213/13/155 figures describe 2026-08-04 and the tree has moved (Luna max audit); `.vault/audit/`.
- [ ] `W08.P26.S118` - Sample and dispose candidates from the measured frame, recording each as void, safe, or repaired, and stating explicitly what the instrument cannot see so the disposition is not read as an exhausted population (Luna max audit); `.vault/audit/`.

## Parallelization

W08.P27 is a hard prerequisite. mutmut must be installed and measured before the detector Phases, because a detector built with no way to check that it can itself fail is the artefact this plan exists to remove. P23 is a one-Step documentation correction and may run alongside P27.

After P27, P24 and P25 are independent of each other and may run in parallel: they add different modules under dev/quality/ and different gates under dev/tests/. The one shared surface is the verify lane both register into, which is one-writer — whichever Phase lands second re-reads the lane definition and the workflow before editing them. P26 depends only on P27 and may run at any point after it; its measurement is what tells the detector Phases whether a further class is worth a gate at all.

Within P25 the order is strict: the axis must be demonstrated failing against a real locale-dependent assertion before that assertion is repaired, or the axis is never shown to bite. Repairs under P25 touch src/cadrumo/ while other sessions are editing it, so each batch stages only its own files and absorbs no unrelated change. Luna max performs audits, type and mechanical checks, and evidence review; Terra xhigh performs fixes and refactors; Sol is reserved for architecture.

## Verification

This plan is complete when the instruments exist and are proven to bite. It is not complete when the tree is free of blind assertions, and it never claims that. Completion of this plan does not assert permanent codebase sanity or close future work.

All five conditions, each evidenced:

1. mutmut is installed and pinned, one bounded package carries a recorded measurement of wall clock and killed and surviving counts, survivors are triaged into real findings and semantically inert mutants, and the standing scope and cadence are declared from that measured cost.
2. The tautological-assertion scanner's recorded boundary is corrected and names which classes are decidable by static analysis and which remain a human question.
3. Every decidable class named in the governing decision has a detector that sweeps the real tree, carries a passing positive control and an anti-vacuity floor, is registered in a named verify lane that CI invokes, and has had its own gate killed by mutmut.
4. The locale axis exists, is invoked by a named lane, and has been demonstrated failing against at least one real locale-dependent assertion before that assertion was repaired.
5. The re-measured candidate population has a recorded disposition naming its sampling frame. An empty disposition is not a disposition, and a disposition may not claim to have exhausted a population the instrument cannot bound.

Condition 3 is load-bearing: it is satisfied by mechanisms that demonstrably fail on a real defect, not by a count of sites repaired. No condition is satisfied by exhausting a list, by a mutation score, or by a threshold, baseline, exclusion, suppression, skip, xfail, or allowlist. Terra xhigh repairs and refactors with real behavior proof; Luna max runs audits, type and mechanical checks, affected-gate checks, and evidence review; Sol handles architecture only.

A Phase may be added when a new decidable class is measured, or contracted when a class is shown undecidable or empty. Both require evidence and neither reopens the completion condition. Findings produced after this plan closes are routed as ordinary owner work under the rolling ratchet, which is what that controller is for.
