---
tags:
  - '#audit'
  - '#wrong-surface-gates'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:7f28aea5bcca0e36c866b9b1c963cdffd53cb6311b68b0da6c2f3f41e6d277c3'
related:
  - "[[2026-07-25-test-harness-honesty-adr]]"
  - "[[2026-07-25-test-harness-honesty-false-green-gates-audit]]"
---

# `wrong-surface-gates` audit: `gates that read the wrong surface: the class, and two refusals to automate it`

## Scope

One day's sweep for a defect class, its two attempted automations, and what landed. Prompted by five defects found in a single day (2026-08-01) that shared one shape and were each found by accident, none by a gate.

**The class.** An instrument whose observed surface was not the surface the defect passes through. The assertion can fail. The corpus is non-empty. The instrument discriminates. It is simply pointed somewhere else.

**Method, and its measured limit.** Semantic search cannot find this class, and the reason is structural rather than a tooling gap: shape-phrased queries ("test asserts an env value rather than produced output") scored 0.006-0.06 against 0.6+ for domain-phrased queries. The index embeds what code is *about*; this class is a property of the RELATION between an assertion and a defect that is not in the file. A gate asserting the wrong surface reads identically to one asserting the right surface. The working method is therefore: semantic search to locate load-bearing gates BY DOMAIN, then read them and judge the surface by hand; `rg` only for the narrow syntactically visible sub-shapes.

**Coverage, stated so it is not overread.** The publish/deploy preflight band (`dev/deploy`, `dev/release`, `dev/packaging`, production only) holds ~45 validation functions. Ten were read closely. The remaining ~35 did not surface under these queries with this method, which is NOT a claim that they are sound. The vacuity-screen measurement covers all 526 emptiness-asserting test functions under `src/cadrumo/tests` and `dev`.

**Not in scope, deliberately.** Rule promotion: codification is retired by operator directive, so this audit record is the home for these lessons.

## Findings

### c1-narrow-screen-cannot-separate-the-defect-from-its-remedy | refusal | built, measured, ABANDONED — do not rebuild

The most re-inventable idea in this record, so it is first. The proposal was a screen for the one sub-shape that looked both mechanically visible and load-bearing: **a non-emptiness assertion as the SOLE check on a filesystem-derived artefact**, scoped to publish-path production code. It was built and measured. It fails the one test a screen must pass.

| case | base rule | refined rule | wanted |
| --- | --- | --- | --- |
| the real defect (pre-fix `_validate_language_roots`) | flags | MISSES | flag |
| the remedy (post-fix `_require_search_index`) | FLAGS | clears | clear |
| legitimate sibling (sitemap, content-checked) | clears | clears | clear |

Base rule: a collection built by a filesystem walk whose bound name is used only in an `if not X: raise` guard. It catches the original defect and correctly clears the legitimate sitemap check living in the *same function* — then also flags the corrected code. The obvious refinement (the non-emptiness guard is the only `raise` in the function) clears the fix and the sibling, but misses the original, because that function already had a second `raise` for the missing index page. **Exactly complementary in the wrong direction.**

On the live tree, across all three publish-path trees: **1 hit, and it was the false positive on the just-corrected code.** A screen whose only live output is a false positive on the remedy teaches its reader to ignore it on first contact.

**Why it fails, which is the part that generalises.** In the fixed code the content check reaches the artefact through a DIFFERENT variable (`present`, returned from a function call). So "is this artefact content-checked?" is not a property of the guard or of the variable; answering it requires knowing which values derive from the artefact, across a call boundary. That is the same knowledge-of-what-ships the general detector needed. **The narrow sub-shape was never actually narrower** — it only looked narrower because the original defect happened to keep the guard and the artefact in one variable. Under any correct refactoring the property goes non-local and the rule collapses into the general detector, which was separately declined because no rule separates a bad proxy assertion from a legitimate signature-conformance test.

If you have just had this idea again: it is a good idea that does not work, and the table above is why.

### c2-a-demonstrated-subclaim-carried-a-false-conclusion | retraction | the claim was wrong; the mechanism is the lesson

**Retracted claim:** that `dev/audit/vacuity_screen.py`'s `proves_it_scanned()` returning `True` for a bare `assert index_chunks` meant the screen read the non-emptiness defect shape as EVIDENCE OF RIGOUR, and could credit it module-wide to exempt sibling scans. This was reported, believed, authorised for repair in strong terms, and is false.

Two independent reasons, either fatal:

1. **Domain.** The screen walks `test_*.py` under `src/cadrumo/tests` and `dev` only. The defect it was accused of mishandling lived in `dev/deploy/docs_static_site.py` — production code the screen never scans. No predicate could have flagged it.
2. **Inside a test, that credit is CORRECT.** A bare `assert <corpus>` fails when the walk returns nothing, which is precisely the property the screen exists to require.

The candidate discriminator dissolved on measurement too. Of 526 emptiness-asserting functions: 174 cleared by module-proof, 106 flagged, 106 by a real lower bound, 73 by a truthy assert whose names are DISJOINT from the emptiness assert, 47 shared-name, 20 literal-control. The 73 "disjoint" cases were the proposed hole — but corpus and result are *necessarily different variables*, so disjointness identifies the LEGITIMATE shape. Spot-checks confirmed it: `dev/docs/tests/test_api_stubs.py` and `dev/docs/tests/test_cli_reference_conformance.py` both carry author comments written expressly to satisfy that screen, and the auditor's own new test landed in the same bucket with an entirely valid proof-of-scan.

**The generalisable error:** a predicate's output was observed IN ISOLATION and described as a property of the INSTRUMENT, without checking the instrument's domain. Transplanting a production-code shape into a test-only screen's predicate yields a true observation about the predicate and a false claim about the screen.

**How it survived review, which matters more than the error.** It persuaded BECAUSE it arrived demonstrated. A real predicate table was produced, it was correct, and it was reproducible — and it lent its credibility to the inference built on top of it, which is where the error was. Both parties failed the same way: the coordinator authorised the repair calling it "a live weakening, worse than the absence of a screen" without asking whether that screen ever reads production deploy code — the exact question that had just been written down as the one to always ask. **Treat "this was demonstrated" as a reason to check the SCOPE of the conclusion more carefully, not less.**

No change was made. `vacuity_screen.py` is untouched and its worklist stands at 106.

### the-class-three-instruments-on-three-axes-none-of-them-the-surface-axis | analysis | why nothing caught any of the six

Running the real predicates from both existing screens against the six defect shapes: `test_no_tautology.py` classifies **zero of six**. The three instruments the project already has occupy three different axes, and none is the surface axis:

- `src/cadrumo/tests/test_no_tautology.py` — assertions that CANNOT FAIL (syntactic).
- `dev/audit/vacuity_screen.py` — assertions over a possibly-EMPTY corpus. Axis: *did you measure anything*.
- ADR `2026-07-25-test-harness-honesty` — instruments that cannot DISCRIMINATE. Remedy: positive controls.

All three ask **"is the instrument working?"** Every one of these defects had a perfectly working instrument. Nothing asks **"is it pointed at the shipped surface?"** The harness-honesty ADR states its own axis in a line that reads as the exact complement: *"Neither could be caught by reading the assertion, because the assertion was correct in both cases. What was missing was any evidence that the instrument still worked."* Here the assertion was correct, the instrument demonstrably worked, and what was missing was evidence that the surface it read was the surface that ships.

The six shapes: (1) a deploy gate asserting an ENV VALUE while the shipped index carried none of the decided records; (2) a gate asserting an injector was SELECTED rather than that its output reached the artefact; (3) a "real artefact" gate that built a FIXTURE site and never the localized root where the defect lived; (4) a validation asserting index chunks were NON-EMPTY, which pure prose satisfies; (5) a completeness gate measuring a catalogue AGAINST ITSELF rather than current source; (6) the fixture shape below.

### the-sixth-shape-a-fixture-built-from-the-checks-own-predicate | new | invisible to all three screens, and it recurred inside this work

A test fixture wrote a non-empty index chunk and called the result "a minimal valid localized site root" — valid *by the old check's own definition*. So the acceptance test asserted "a complete matrix is accepted" using a fixture that was record-free. It could never have caught the defect, because **the fixture was constructed to satisfy the property the check measured**.

The assertion can fail. The corpus is non-empty. The instrument discriminates. All three screens pass it. The wrong-surface axis is expressed in the FIXTURE rather than in the assertion, so reading the assertion alone can never reveal it.

**It then recurred inside the work that discovered it.** `_complete_build` in the landing-page suite wrote the placeholder `"x"` into every artifact, so its `index.html` referenced no bundles and the new reference check had nothing to compare — a "complete build" fixture complete only by the weaker definition. That the shape reappeared in the very campaign that named it is the strongest available evidence it is a real pattern rather than one author's habit.

The transferable question: **was this fixture built from the check's own predicate?**

### stronger-and-weaker-checks-coexist-in-one-file-by-artefact-kind | recurrence | predicts where to look

Observed in three separate files, each containing one check that binds provenance or reads content beside a neighbour that does not:

- `dev/deploy/docs_static_site.py` — the sitemap validated by CONTENT (canonical root present, no non-canonical URL) ten lines above an index validated by SIZE.
- `dev/release/readiness.py` — `check_latest_packaging_smoke_evidence` takes the newest manifest by mtime and reads `ok` without binding it to a commit, beside `check_distribution_evidence_set`, which binds cohort commit to checked-out commit and tag to version. (Advisory, never blocking: recorded, not fixed.)
- `dev/deploy/frontend_static_site.py` — a required-artifact check naming specific files beside an assets check asserting only that *some* `.js` and *some* `.css` exist.

The useful form is predictive rather than moralising: **authors demonstrably know how to write the stronger check and write the weaker one when the subject is a different KIND of artefact** — a file versus a directory, a status versus a body, a count versus a manifest. That tells you where to look next.

### post-publish-verification-could-only-confirm-that-something-answered | fixed | the layer that should have caught the live defect

Both publishers verified delivery with HTTP status codes alone. A status cannot distinguish a working root from a broken one: a docs root serving a record-free search index answers 200 on every checked URL, and a landing page whose bundles are missing answers 200 while rendering blank. This is the layer meant to confirm that what LANDED is correct, and it is the layer that would have caught the original defect live and could not.

Closed by comparing served against built: each published root's `pagefind-entry.json` must match the built entry's per-language counts. The strength is inherited — the preflight has already refused a record-free build — so no record total is hardcoded and nothing rots on the next corpus change. Every root is read, not only the default: a localized root serving a record-free index was the second defect in this family.

### an-instrument-can-be-measuring-your-own-decoder | incident | the theme in miniature, on the last commit of the sweep

While preparing a formatting-only commit, a token-equivalence probe reported the streams DIFFERED — which would have contradicted the "no behavioural change" claim about to be written. The difference was an em-dash rendered as a replacement character, and the cause was the probe: `subprocess.run(text=True)` decodes with the platform locale rather than UTF-8, so the two sides were compared under different codecs. Re-run on bytes: 537 tokens both sides, identical, zero differing.

A claim about the artefact was nearly published on an instrument measuring the auditor's own decoder. **The check disagreeing with its author is what caught it** — which is the whole argument for running the check rather than reasoning about whether it could fail.

## Recommendations

### The one instrument that generalises

> **Name the artefact that ships. Does this assertion read it?**

All six shapes fail it instantly. One sentence per gate. Deliberately ONE question rather than a checklist, because five-item checklists get skimmed.

**Where to spend it:** gates guarding PUBLISH-time or DEPLOY-time behaviour. That is where the observed surface and the shipped surface diverge, and where all six shapes lived. Ordinary unit tests over in-process values have no such gap, so the whole calculation-test surface is not implicated.

**The companion question, for acceptance tests:** was this fixture built from the check's own predicate?

### Do not build

- **A general AST detector for "asserts a proxy".** No rule separates a bad proxy assertion from a legitimate signature-conformance test, of which this codebase has many, correctly. A screen flagging every signature assertion is ignored within a week.
- **The narrow non-emptiness screen.** Built, measured, abandoned; see the C1 finding. It cannot distinguish the defect from its own remedy, and the refinement that fixes that also blinds it to the defect.

The precedent for both: `vacuity_screen.py` reports a 106-item worklist across 248 modules that nobody reads. A screen nobody reads and a gate that passes wrongly fail identically from outside.

### What landed, for anyone tracing the fixes

Publish preflight reads the index rather than its size, at both the default and every localized root (`dev/deploy/docs_static_site.py`). Post-publish verification compares served against built in both publishers. `assert_supersession_complete` distinguishes VERIFIED from NOTHING_RETIRED and NOTHING_PUBLISHED, and refuses a missing marketplace directory as UNVERIFIED rather than reporting it clean. Landing-page validation requires the bundles `index.html` actually names. The search index is written once rather than twice — the second, unpathed write was depositing a ~10,000-file tree in the process working directory on every build, and is the mechanism behind the incident that motivated the committed-index rule. The campaign-metadata gate's roots now include `packaging/`, which was invisible to it.

Every fix carries a mutation proof against real artefacts, and each pairs the refusal with the assertion that the OLD predicate still holds on the same artefact — so the record shows the previous check passing on what the new one rejects, rather than claiming that in prose.

### Open, not closed

- ~35 of the ~45 preflight-band validation functions were not read. Not a claim they are sound.
- How `--marketplace` is populated in the real release flow was not traced, so the reachability of the wrong-path case is unknown. The fix does not depend on the answer.
- `test_source_test_comments_and_docstrings_do_not_reference_campaign_metadata` remains red on two pre-existing violations at HEAD in a file owned by another campaign.
