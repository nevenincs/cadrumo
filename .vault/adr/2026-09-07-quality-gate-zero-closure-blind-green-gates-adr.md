---
tags:
  - '#adr'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:6740343d7265bed8ba9aad804e61cbc71c850a9ec507b6d6c557054d947c2f89'
related:
  - "[[2026-08-24-quality-gate-zero-closure-adr]]"
  - "[[2026-07-25-test-harness-honesty-adr]]"
  - "[[2026-07-14-honest-all-green-adr]]"
  - "[[2026-08-04-canonical-storage-management-void-assertion-class-audit]]"
  - "[[2026-08-30-repo-gate-integrity-wrong-subject-gates-audit]]"
  - "[[2026-09-02-gate-integrity-adjudication-commit-time-mechanical-gates-adr]]"
  - '[[2026-09-07-quality-gate-zero-closure-blind-green-measurement-research]]'
  - '[[2026-09-07-quality-gate-zero-closure-never-emitted-decidability-measurement-audit]]'
  - '[[2026-09-07-quality-gate-zero-closure-gate-consumer-parser-blindness-audit]]'
---

# `quality-gate-zero-closure` adr: `Blind green is a gate failure, and most of it is mechanically detectable` | (**status:** `accepted`)

## Problem Statement

Every accepted gate decision in this repository governs a gate that can go red. `2026-08-24-quality-gate-zero-closure-adr` makes exact zero the checkpoint predicate. `2026-07-14-honest-all-green-adr` mandates whole-tree honesty. `2026-07-25-test-harness-honesty-adr` requires a scanning gate to prove it discriminates. None of them governs a gate that is green because it *cannot* fail.

A blind gate is invisible to all three. It is green, it is fast, it has a name that describes a real property, and it stays green through the exact defect it was written to catch. Under every existing predicate it is indistinguishable from a healthy gate.

At decision time, the repository already carried both the instrument and the boundary claim that stopped it. `dev/quality/tautological_assertion_scan.py` named the property well — an assertion is tautological when its truth value is fixed before any operand is understood — and `dev/tests/test_tautological_assertion_gate.py`, its only consumer, sweeps `src/cadrumo` and `dev` with a per-root anti-vacuity floor. A second, independent inline detector in `dev/tests/test_no_tautology.py` sweeps the test-control modules; it does not use the scanner. Neither reaches per-push CI: `just test-ratchets` occurs once in the `justfile` and in no workflow, and `dev/tests` is outside the path set of the per-push `test-dev-ci` lane, reaching CI only through the `workflow_dispatch`-only full run. The scanner's docstring then draws the line:

> WHAT THIS SCAN CANNOT DO, which matters more than what it can. This is the only member of the gate-integrity family a linter can catch. Every other instance in that family needed a person to ask what the assertion was ABOUT: a gate whose assertion is perfectly well-formed and simply irrelevant to its subject is indistinguishable, to any scan, from one that is on point.

Measurement in September 2026 refuted that boundary. Four further classes were found and repaired, each located by static analysis alone, none of them trivially true, none requiring a person to judge what the assertion was about:

- **Subsuming disjunction.** `assert A in X or B in X` where `B` is a substring of `A`. The verdict equals the weaker operand; the specific claim is never required. Eight found, seven repaired; the residual at `test_profile_session_root_resume.py:175` could not be observed because the test skips where the OS credential store refuses a probe write. It is the only live instance, and therefore the best available real control for the demonstration criterion 4 requires.
- **Self-echoing token.** An assertion keyed on the token the operator typed, which the error message quotes back verbatim, so it cannot separate "the surface is retired" from "it resolved and failed for another reason". Three found.
- **Locale-bound absence.** `assert X not in output` where `X` is our own English rendering and the ambient test locale is Spanish. Satisfied by every run. The instance in `test_modelo_source_mesh_calculate.py` asserted `"ADVISORY:"` absent while the Spanish catalogue renders the same notice `"AVISO:"` — an under-declaration gate that could not fail if an advisory were surfaced.
- **Never-emitted literal candidate.** An absence assertion whose literal appears nowhere else in the tree. The stricter follow-up measurement recorded below later showed that this corpus fact does not decide whether the assertion is blind, so the proposed gate was contracted rather than shipped.

Every count above is recorded with its probe design, its false positives, and its two false starts in `2026-09-07-quality-gate-zero-closure-blind-green-measurement-research`. Each is a floor taken at a moving revision while other sessions committed, not a stable population.

Separately, `2026-08-04-canonical-storage-management-void-assertion-class-audit` measured the absence-assertion population at 400, resolving to 213 provably excluded, 13 already safe, and **155 candidates needing examination**. It explicitly deferred disposition: "Do not remediate any site from this audit yet; disposition is a scoping decision for a follow-on plan" and "A follow-on ADR should decide". That deferral has stood unowned since 2026-08-04.

Four decisions are needed: whether blind green is a gate failure with a predicate of its own; how much of it is mechanically detectable; whether mutation testing is adopted and with which tool; and which plan owns the work.

## Considerations

- The refuted boundary is the load-bearing fact. The scanner's claim was not careless — it was true of the classes it enumerated. It generalised from a list of forms to a claim about the family, which is the same error the scanner's own docstring warns against when it says naming the property beats listing the instances.
- Detectability is per-class, not global. Subsumption is decidable from the AST alone. Locale-binding is decidable by joining the asserted literal against the four catalogues and the test's locale pinning. The later bounded measurement in `2026-09-07-quality-gate-zero-closure-never-emitted-decidability-measurement-audit` refuted the proposed never-emitted-literal detector: runtime renderers, dependencies, interpreters, operating systems, user-controlled values, and composed helpers can all produce meaningful forbidden text absent from the source corpus, so corpus absence cannot distinguish a blind assertion from a valid guard. "Well-formed but irrelevant to its subject" and corpus-only producer absence remain genuinely undecidable by static analysis and stay human questions — but they are exactly the questions a surviving mutant answers empirically.
- Locale pinning takes four forms in this tree. `language_argv.py:26` declares `("--language", "--lang", "--output-language")`, and a test may also pin through `env={"CADRUMO_OUTPUT_LANGUAGE": ...}`. A detector that recognises fewer reports false positives; the first probe recognised two of the four and misreported 8 of 17 hits. `--lang` is currently unused by any test, which is exactly why a detector written from observed usage rather than from the declaration would miss it.
- Not every disjunction is a defect. Locale-alternative tuples are the sanctioned shape, real boundaries exist, and Click's own messages are untranslated and stable, so asserting them is a real claim. A detector that cannot tell these apart will be silenced rather than fixed.
- The absence-assertion sweep cannot see literals composed inside helper functions, and demonstrated this against its own corpus by missing `_hash_bucket_tree`. Its count is "a floor, not a population, in a direction the instrument cannot itself measure". Any static detector in this family inherits that property; mutation testing does not, because it perturbs behaviour rather than reading source shape.
- No mutation tool is present in `pyproject.toml` or `uv.lock` — not merely unconfigured, not installed. `2026-07-12-mutation-harness-extension-audit` is not evidence against adoption: it concerns a retired ruleset-AST mutation suite for an architecture that no longer exists, not mutation testing of the test suite.
- Cost is the live constraint on mutation testing, not principle. The unit lane already carries a per-test wall ceiling and a documented history of multi-hour wedged runs; a naive whole-suite mutation run multiplies that by the mutant count. Bounded per-package scope is what makes adoption tractable.
- A surviving mutant and a gate defect are not the same thing. An equivalent mutant changes no observable behaviour, so no assertion could have caught it; counting it as a finding manufactures work and would push the repository toward a mutation score, which is a metric, not a gate.
- `2026-09-02-gate-integrity-adjudication-commit-time-mechanical-gates-adr` is accepted and binding: mechanical gates stay verify-only and out of commit time, because a pre-commit stash destroyed uncommitted work in this repository.
- `dev/quality/tests/test_taxonomy_absence_conformance.py` is the live in-repo declaration gate: hand-edited `PINNED_TAXONOMY_LITERALS` claims are checked against AST-discovered absence sites, where nobody can keep the gate green without also changing what the test asserts. It supersedes and removes the former off-lane `src/cadrumo/tests/test_pinned_taxonomy_literal_conformance.py` implementation and its exception/debt tables.
- `2026-08-24-quality-gate-zero-closure-adr` reserves implementation authority to owning feature plans and forbids the ratchet controller from taking over an owned surface. Its plan has been stranded at two closed steps since 2026-08-24, and the blind-green evidence has had no owner at all.

## Considered options

- **O1 — Leave the family to human review, as the scanner's docstring concluded.** Rejected: refuted by measurement. Four classes were located mechanically, and the largest of them sat inside an under-declaration gate that no reviewer had questioned.
- **O2 — Adopt mutation testing as the sole instrument and build no structural detectors.** Rejected: a surviving mutant proves an assertion is weak but does not name which class it belongs to, so it cannot be turned into a standing gate that refuses the defect at authoring time. Mutation testing measures; detectors prevent. The repository needs both.
- **O3 — Build structural detectors first and defer mutation testing behind a cost measurement.** Rejected: it inverts the dependency. A detector built with no means of checking that it can itself fail is precisely the artefact under adjudication here, and the repository has already shipped one whose confident boundary claim went unchallenged from the day it was written until it was measured.
- **O4 — Install mutmut first as the prerequisite instrument, then build per-class structural detectors and a locale axis against a tree it can already judge.** Chosen: mutation testing supplies the ground truth for "can this assertion fail", and every detector built afterwards is held to it, including each detector's own gate.
- **O5 — Route the work through the ratchet controller as owner-attributed batches with no owning plan.** Rejected: that is what has happened since 2026-08-04 and it produced a measured population with no disposition. The ratchet routes to owners; the defect is that no owner exists.

## Constraints

- Blind green is a gate failure. A gate that cannot fail for the reason it was written is red for the purposes of this decision, whatever its exit status.
- mutmut is the only mutation engine adopted. A second engine is not added: mutant models differ between tools, so survival counts are not comparable and a disagreement between them would have no adjudicating authority.
- Mutation runs are bounded per package with a recorded, reproducible invocation. Whole-suite runs are not authorised by this record.
- A mutation score is never a pass condition, a target, or a reported metric. A surviving mutant is a finding to triage; an equivalent mutant is closed as inert with its reason recorded.
- Every detector added under this decision sweeps the real tree, ships a positive control proving it fires on a representative defect, and ships an anti-vacuity floor proving it examined a non-trivial population. A detector without all three is not accepted. This is `2026-07-25-test-harness-honesty-adr` applied to the detectors themselves.
- A detector's finding count is a diagnostic floor. It never becomes a pass condition, an exhaustive worklist, or a debt allowance, and no detector may be satisfied by exhausting a list.
- This decision authorises no baseline, threshold, exclusion, suppression, skip, xfail, or allowlist. Where a legitimate shape would trip a detector, the detector is made precise about the shape; it is not given an exemption list.
- A **declaration** is not an allowlist, and this record sanctions exactly one declaration pattern: a hand-authored, site-specific claim whose docstring states why this particular site is correct, checked by a conformance gate against AST-discovered reality, in both drift directions — a stale declaration and an undeclared site both fail. The sanctioned thing is the symbol and its two drift tests — `PINNED_TAXONOMY_LITERALS`, checked that every declared literal still has a source site and that every taxonomy-bound absence site is accessor-routed or declared — not any particular module that houses it. The live gate is `dev/quality/tests/test_taxonomy_absence_conformance.py`; the superseded off-lane module and its `PENDING_UNDECLARED`, homonym, and embedded-literal tables are removed. The distinguishing property is that nobody can keep the gate green without also changing what the test asserts, which is precisely what an exemption list permits. An exemption list that carries no per-site reason, or that no gate checks back against the tree, remains forbidden.
- No new CI lane is created by this decision. Detector gates land under `dev/quality/tests/`, which the per-push `test-dev-ci` path set already invokes, so `2026-08-05-ci-lane-deconflation-plan` keeps sole ownership of `justfile` and `.github/workflows/` and no tier under `2026-07-21-ci-discipline-adr` is claimed. If a mechanism here ever genuinely requires a new lane, it is handed off to that plan rather than added here.
- Detectors and mutation runs are verify-only and run outside commit time, under `2026-09-02-gate-integrity-adjudication-commit-time-mechanical-gates-adr`. No hook is installed.
- Repairs replace a weakened assertion with the stronger claim it stood for. Removing a redundant branch is a strengthening and must be reported as such, never as a defect fixed, unless the assertion can be shown to pass while the behaviour is broken.
- The `quality-gate-zero-closure` plan is repurposed as the owning implementation plan for this decision. To the extent that `2026-08-24-quality-gate-zero-closure-adr` reserves implementation authority away from that plan, this record amends it for this surface only: the rolling-ratchet controller's delegation rule is unchanged for every other surface, and the controller's speculative activation steps are superseded rather than deleted from the record.
- No new feature tag is created. This decision and its plan carry `#quality-gate-zero-closure`.

## Implementation

The work divides into domains that are independently completable and independently expandable, each landing as its own Phase. A domain may grow or shrink as measurement changes; the plan's completion condition is stated over mechanisms, never over populations. The mutation instrument is a prerequisite and lands first.

**Install mutmut as the prerequisite instrument.** mutmut is pinned as a development dependency with a recorded, reproducible invocation. Scope is bounded per package: this suite carries a documented history of multi-hour wedged runs, and an unbounded first run would establish nothing except that mutation testing is expensive. One bounded package is measured for wall clock, mutant count, and killed and surviving counts. Survivors are triaged into assertions that cannot fail and semantically inert mutants. The standing scope and cadence are then declared from the measured cost.

**Standing mutation scope and cadence.** The initial standing scope is one
detector module per run: `dev/quality/tautological_assertion_scan.py`, judged by
`dev/quality/tests/test_tautological_assertion_gate.py`. The generated tree copies the
two roots that gate actually sweeps, `src/cadrumo` and `dev`; they are test
subjects, while mutation generation remains bounded to the selected detector.
An additional detector enters this scope only after its own bounded run has
been measured and its non-killed mutants individually disposed.

The manual trigger snapshots the current tree into WSL `/tmp`, so mutmut's generated
`mutants/` tree never becomes repository-root scratch:

```sh
scratch="$(mktemp -d /tmp/cadrumo-mutmut.XXXXXX)"
cp -a src dev pyproject.toml uv.lock "$scratch/"
cd "$scratch"
/tmp/cadrumo-mutmut-venv/bin/mutmut run "dev.quality.tautological_assertion_scan*"
```

Run the selected detector after changing its implementation, its gate, or the
mutation selection/copy configuration, and before closing the corresponding
implementation Step. A shared mutation-configuration change triggers one
bounded run for each affected detector, separately; unchanged detectors carry
no calendar re-run. The minute-scale cost measured in
`2026-09-07-quality-gate-zero-closure-bounded-mutmut-measurement-audit` makes
this change-triggered cadence practical without moving mutation testing into
commit time or CI. A future `just` wrapper or manually dispatched GitHub job
belongs to the owner of those surfaces and is not authorised here. Whole-suite
mutation remains forbidden, every survivor remains an individual finding, and
no aggregate score is calculated or reported.

**Correct the recorded boundary, in all three places it lives.** The claim that the tautology scan is the only mechanically catchable member of the family is recorded in `dev/quality/tautological_assertion_scan.py`, in the standalone finding `the-tautology-scan-is-the-only-mechanisable-member-of-this-family` in `2026-08-30-repo-gate-integrity-wrong-subject-gates-audit`, and in the closed Step row `W01.P01.S106` of `2026-08-11-tui-interface-plan`. Correcting only the docstring would leave the refuted claim standing in an accepted audit finding and a closed plan row — the two surfaces a future reader is most likely to treat as durable, since the audit finding exists precisely because that row's warning "needed a durable home". The docstring is rewritten to state which classes are decidable and which are not; the audit and plan records are historical evidence and are not rewritten, but each is cross-linked to this decision so the correction travels with them.

The claim is recent — the scanner was written on 2026-09-01, the audit finding on 2026-08-30, the plan row completed 2026-08-31 — so the cost so far is small and the correction is cheap. Left standing, it is a documented reason for the next author not to try.

**Structural detectors, one per decidable class.** Subsumption; self-echoing token; locale-bound absence assertions. Each is an AST sweep in `dev/quality/`, exercised by a gate under `dev/quality/tests/` carrying its positive control and anti-vacuity floor. That directory is already in the per-push `test-dev-ci` path set, so the gates reach CI without a new lane and without touching a workflow file. Each detector's own gate is then killed with mutmut, so the instruments are held to the standard they enforce. The locale detectors join against all four catalogues and recognise all four pinning forms, including the `--lang` alias no test currently uses. A subsumption hit is a diagnostic candidate, not a defect: it is promoted only on the demonstration that the assertion passes while the behaviour is broken, and absent that it is reported as a redundant branch removed. The never-emitted-literal step is contracted rather than replaced by a weaker heuristic: its stricter follow-up sweep still reported 22 mechanically indistinguishable valid guards, and making those pass would require a forbidden baseline, exclusion, or unchecked intent declaration.

**The locale axis, as a both-locales condition.** Flipping the ambient locale does not retire the class — it mirrors it, making English-literal assertions bite and Spanish-literal ones vacuous. And a test that pins its own locale at the call site, which is one of the two sanctioned repairs, is unreachable by any ambient change. The condition is therefore that every assertion in the locale detector's hit set passes under the ambient locale **and** under a second one, delivered as a parameterised re-run of that hit set rather than as a new CI lane, so no workflow surface is touched and the cost is bounded to the assertions selected by the detector. The mechanism must be demonstrated failing before any repair it surfaces; a seeded instance, removed once the demonstration is recorded, is an accepted demonstration.

**Close the absence-assertion class with the mechanism the source audit proposed.** That audit measured a population and then wrote the closing rule for it: an absence assertion in a module mentioning a taxonomy token either routes through the canonical accessor or carries a declaration naming its own site. Importing the population without the rule is what would leave this open forever, because the count is a floor the instrument cannot bound — the audit demonstrated its own blind spot by missing `_hash_bucket_tree`. The population is re-measured at the current revision to scope the work, since the 2026-08-04 figures describe a tree that has moved, but the conformance gate is what closes the class.

## Rationale

O4 is chosen because the two instruments answer different questions and the order between them is not arbitrary. Mutation testing answers "can this assertion fail" directly, for any assertion, without anyone having named its failure mode in advance. A structural detector answers "does this assertion belong to a class we have already learned to recognise", which is what makes it enforceable at authoring time and cheap enough to run on every change. Detectors are the standing gates; mutation is the ground truth that tells us a detector is worth writing and that the detector itself is not blind.

Putting mutmut first inverts the order this record first proposed, and the subject matter is the reason. A detector built before any means of checking that it can fail is the exact artefact under adjudication, and one such detector already shipped here and went unchallenged until it was measured. Building the remaining detectors against a tree mutmut can already judge is the only sequence in which the instruments are held to their own standard.

mutmut alone, rather than a survey, because a second mutation engine splits the evidence: mutant models differ, so survival counts from two tools are not comparable and a disagreement between them would have no adjudicating authority.

Repurposing the stranded plan, rather than opening a new one, follows the reason the ratchet ADR itself gives: the ratchet routes findings to owners, and the failure since 2026-08-04 was the absence of an owner. Creating a fourth overlapping feature would reproduce that. The amendment is narrow and names the surface it applies to, so the controller's delegation rule survives everywhere else.

## Consequences

A new class of gate failure becomes reportable, and the first effect is that the repository will look worse before it looks better: assertions that have been green for months will be named as blind. That is the decision working, not a regression, and no Step may reduce the count by weakening a detector.

The `quality-gate-zero-closure` plan stops being the rolling-ratchet installation plan. The controller described by `2026-08-24-quality-gate-zero-closure-adr` therefore has no installation plan until one is opened, and this record does not open one. That is a deliberate cost of repurposing a stranded plan rather than a side effect: the controller has had no owner since 2026-08-24, and pretending otherwise is what stranded it.

mutmut becomes a declared development dependency, so the toolchain grows and its runtime cost lands on whichever lane invokes it. Bounded per-package scope keeps that cost visible and refusable; a future decision to widen it must state the new cost.

Detectors added here will produce false positives on shapes nobody has enumerated yet. Each is paid for either by making the detector more precise or by a checked declaration at the site, which is slower than an exemption list and is the point: an unchecked list would reintroduce the blind spot under a different name. The declaration route carries its own ongoing cost — every declared site is a docstring somebody must keep true, and the conformance gate is what stops that decaying.

No CI lane is added and no workflow file is touched, so `ci-lane-deconflation` keeps its surface and no tier budget is consumed. The costs that do land are real and bounded: mutmut's runtime on whichever packages enter its declared scope, and a second evaluation of the assertions that are locale-sensitive. Neither is a full-suite re-run, and both are stated so a future widening has to restate them.

The never-emitted-literal class cannot be closed by corpus absence alone. A literal appearing nowhere else is either a dead assertion or a sentinel for a string the product must never emit — a leaked English fallback, an unfilled placeholder, a secret in a serialized payload — and the corpus cannot distinguish them. Sites of the second kind are resolved by declaration, not by repair, which is why the declaration pattern is sanctioned above rather than treated as debt.

Repairs under this decision touch test files across the tree while other sessions edit them concurrently. Every repair is therefore scoped to its own files, and a removed redundant branch is reported as a strengthening rather than as a defect fixed, so the record does not overstate what was broken.

## End signal

This plan completes when the instruments exist and are proven to bite. It does not complete when the tree is free of blind assertions, and it never claims that.

Completion requires all five, each evidenced:

1. mutmut is installed and pinned, one bounded package has a recorded measurement, survivors are triaged into real findings and inert mutants, and the standing scope and cadence are declared from that measured cost.
2. The recorded boundary in `tautological_assertion_scan` is corrected and states the decidable and undecidable classes.
3. Every decidable class named in this record has a detector that sweeps the real tree, carries a passing positive control and an anti-vacuity floor, and has had its own gate killed by mutmut. The gate lives under `dev/quality/tests/` and is *demonstrated* to run in the existing per-push lane — residence is necessary but not sufficient, because that lane's marker expression deselects an unmarked test, and a gate CI never runs is the blind gate this record exists to prevent.
4. The both-locales condition holds for every assertion the locale detector reports, and has been demonstrated failing against a locale-dependent assertion. The population is the detector's hit set, not a judgement about which assertions are "locale-sensitive" — binding the condition to the detector is what stops it being argued in either direction. The demonstration prefers the live residual instance; where none exists, a seeded one is accepted, but it is seeded into synthetic in-memory source or an isolated fixture and never into the shipped tree, which is concurrently edited. `dev/quality/tests/test_taxonomy_absence_conformance.py` is the live pattern here too: it fires on both seeded drift directions using an isolated non-collected source fixture, with no mutation of the shipped tree.
5. An absence assertion in a module that mentions a taxonomy token either routes through the canonical accessor or carries a declaration whose docstring names its own site, and a conformance gate enforces that in both drift directions. The re-measured population is reported as context for scoping, never as the pass condition.

Criterion 3 is the load-bearing one: it is satisfied by mechanisms that demonstrably fail on a real defect, not by a count of sites repaired. Criterion 5 is deliberately a mechanism rather than a disposition of the measured population: a count is a floor the instrument cannot bound, so closing on it would be closing on a number that was never a population. No criterion is satisfied by exhausting a list, and none may be satisfied by a threshold, baseline, exclusion, suppression, skip, xfail, or unchecked allowlist.

A Phase may be added when a new decidable class is measured, or contracted when a class is shown undecidable or empty; both require evidence and neither reopens the completion condition. Findings produced after completion are routed as ordinary owner work under the rolling ratchet, which is what that controller is for.
## 2026-09-07 verdict-layer extension

The measured family extends from assertion expressions to verdict consumers: code that converts a gate output into a pass/fail claim is subject to the same blind-green rule. The triggering instance was `dev/audit/report.py`, whose suffix predicate could not represent import-linter's optional parenthetical and therefore missed nine of twelve valid contract verdicts. The measurement and repair evidence live in `2026-09-07-quality-gate-zero-closure-gate-consumer-parser-blindness-audit`.

This adds one decidable class: direct containment, prefix, or suffix predicates against a declared gate-output token when that producer grammar admits surrounding structured text. Its detector must join the AST predicate to the declared producer grammar, sweep the real tree, carry a positive control and anti-vacuity floor under `dev/quality/tests/`, run in the existing per-push lane, and have its own gate killed by mutmut. Criterion 3 applies to this class exactly as it applies to the assertion classes. The extension adds no CI lane, threshold, baseline, suppression, or unchecked declaration, and does not turn the mutation run into a pass score.

The same measurement also found a second hand-maintained declaration census and a mock that asserted a reset call rather than its cache effect. Those are repaired under the checked two-drift-direction declaration mechanism and effect observation respectively; they do not define additional structural detector classes.
