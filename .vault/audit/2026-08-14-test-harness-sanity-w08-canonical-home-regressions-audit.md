---
tags:
  - '#audit'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:3665d8a36e87d8e2fa47f46ed985ce2d9923ab6693a65b24dd0ae9eff29501b5'
related: []
---

# `test-harness-sanity` audit: W08 close review, canonical-home regressions

## Scope

Close-phase review of the two-lane harness campaign, covering the nine findings of the originating audit against current code, plus the regressions introduced by the close phase itself. Verification of the fixture lane is bounded by live peer ownership and is reported as such rather than asserted.

## Findings

### originating-audit | resolved | Every one of the nine original findings is closed against current code

Re-checked at close rather than trusted from the execution records. The duplicated encrypted-storage fixture now has one definition consumed through two pytest discovery boundaries, which is required topology and not duplication. The four forbidden mutation sites carry none. The retired naked-test rationale is replaced by the real distributed-subtree requirement. The banned-import policy and the marker contract are both applied once from the repository root, and the child collection hook that duplicated the marker walk no longer exists, which closes the double-walk finding with it. The owner-specific modules left the central harness for their domain owners, guarded by a property-based ownership gate rather than a file list. The worker-count reversal is no longer unrecorded: the superseding decision is accepted, the superseded one carries the back-reference, and the implementation matches the new decision. Both expensive proofs are out of the routine unit lane.

### lane-topology | high | Moving the proofs out of unit left them fully reachable from the parallel integration lane

The two proofs carry an integration marker and no serial marker, so the parallel integration lane and its standalone variant collected all five of their cases into an xdist pool. Measured before the fix: that marker expression collected five tests. The cost is multiplicative rather than additive, because each proof spawns its own child pytest, so an outer pool of width N yields N inner pools. The dispatch-only full lane reaches that recipe on the shared runners, so this was live in CI and not only locally.

### census-instrument | high | The full-corpus proof was measuring a scratch copy of the repository

The corpus boundary was a hand-written set of excluded directory NAMES. A concurrent campaign had copied the entire repository into a gitignored scratch directory, which was not on that name list, so the proof walked the copy and reported 2097 uncollectable modules. The true first-party figure is 21. The same defect runs the other way: the plausibility floor that exists to catch an empty corpus could have been satisfied by the scratch copy alone. The module's own docstring had warned against a hardcoded list of INCLUDED roots while carrying a hardcoded list of EXCLUDED ones.

### close-phase-regression | high | The close phase introduced the duplication the campaign exists to remove

Holding the proofs out of the parallel lanes was first attempted with a new capability marker, which the governing decision explicitly forbids: the harness lane is to be selected by explicit owned paths, never by a runtime-cost marker competing with the execution and hexagonal taxonomies. The correction to path-based exclusion then restated the member list at four lanes beside the recipe that declares it, which is five copies of one list. Both attempts were made while implementing a campaign whose subject is canonical homes.

### close-phase-regression | high | Collapsing the member list to one declaration silently widened a lane's modelled scope

Declaring the members once as justfile variables and deriving both the runner and the exclusions is the correct shape, and it stands. But the repository's lane authority parses the justfile as text and does not resolve templates, and an unresolved token is not recognised as a path, so the lane falls back to the configured testpaths. Measured: the dedicated harness recipe's three lanes moved from naming their two modules to claiming the whole source tree. Any integration-marked test under that tree with no lane to run it now reads as reachable. The unchanged count of already-unreachable tests is not evidence of harmlessness, because those are excluded by the marker half of the check rather than the path half.

### fragmentation | high | The lane question is answered by an authority and by two independent re-implementations

A module already owns lane enumeration, recipe attribution, path scope, marker-expression evaluation and CI-invocation closure, and it has exactly one consumer. Two CI gate modules nonetheless carry their own justfile recipe parsers, marker regular expressions and template substitution, and one of them keeps a third hand-written copy of the harness member list. Separately, the executable that renders the justfile is resolved independently at four sites, each with its own missing-tool handling. One of those gates reads the recipe through a rendering mode that does not resolve templates, so it compares source text while describing it as the rendered recipe.

### lane-authority | high | The lane authority models no exclusion, so an excluded file still reports as covered

The lane record carries source, paths, marker expression and recipe, and nothing else; both exclusion spellings are discarded during parsing. Measured: a lane that explicitly excludes a module reports that it covers it. Before the exclusions were added this was accidentally correct, so the defect was latent until the campaign started excluding files.

### verification-boundary | open | The fixture census cannot reach a verdict on this tree

The census is fail-closed against source mutation during generation, and this worktree is shared with several concurrently editing campaigns. Successive runs refused first because two source files changed mid-generation and then because a manifest record no longer resolves to a fixture body in a file a peer holds open. The refusals are the instrument behaving correctly, not census defects, but they mean no clean verdict is obtainable here. The plan already anticipated this coupling for that file.

### peer-state | open | The harness verdict is red for causes outside this campaign

With the corpus boundary corrected, 21 first-party modules genuinely fail collection. The sampled cause is a registry authority-grade transition in another campaign that leaves a modelo revision pending review, which refuses at snapshot build. Separately, eight tests carrying the credential-store capability marker are selected by no declared lane, because the enrolling recipe names three paths and those tests live outside them. Neither is this campaign's to repair, and neither was repaired here.

### verification-outcome | blocked | The no-monkeypatch criterion is red again, from outside this campaign

This campaign's own four reported mutation sites are clean, verified directly: none of the modules named in the originating audit carries monkeypatch machinery. The gate is nonetheless red, on a fifth site in another campaign's file, introduced by a commit that landed after the restoration. The mutation there is deliberate and documented in place: it redirects the bundled registry root because the default-root branch carrying the defect cannot otherwise be reached without editing the shipped tree.

That makes it a genuine policy violation with a considered rationale, and resolving it needs a production seam in a domain this campaign does not own, not a local edit. It is therefore reported rather than absorbed, and the campaign's stated criterion that the no-monkeypatch inventory passes with no allowlist or suppression is NOT met on this tree. What the standing goal still asks for, and this exclusion does not deliver, is a green gate rather than a green subset: a restored gate that a later commit re-reds has been restored only for the sites someone happened to look at.

### verification-outcome | blocked | Three further ratchets are red on other campaigns' code

The marker-integrity module fails six ways, on hexagonal marker placement, statement ordering, credential-store membership pinning, live-test token usage, and two campaign-metadata prohibitions. The tautology ratchet names one comparison of two distinct literal error codes in an invoices test. The test-double ratchet names definitions elsewhere. None of these modules is this campaign's, and none of the failures was introduced by it; the same six marker failures were measured at session start, before any change here.

They are recorded because the campaign's verification asks for these gates to pass, and they do not. Reporting them as another campaign's debt is accurate but does not make the criterion met.

### verification-outcome | met | Vault provenance is complete and clean for this feature

Every closed Step has exactly one execution record and there are no unlinked records, verified through the plan trace rather than by counting files. The feature-scoped vault checks pass with zero errors and zero warnings across all nineteen checks after an index rebuild. The repository-wide check reports zero errors and roughly thirteen hundred advisory warnings, almost all of them plans in other campaigns lacking research references; these are reported here and deliberately not rewritten, because editing other campaigns' documents to clear a count would manufacture a green rather than earn one.

### verification-outcome | partial | The fixture census cannot return a verdict on this worktree

Every attempt to validate the live ownership manifest refuses, each time naming a different set of files that changed between the before and after source snapshots: registry modules, a custody test, an applicability module. The refusal is the fail-closed guard behaving exactly as designed on a tree with several campaigns writing concurrently, and it is not a census defect. But the consequence stands: no clean verdict on fixture completeness or substitutable duplicates is obtainable here, and none is claimed. A verdict needs either a quiet tree or a clean checkout.

### fixture-disposition | reviewed | Every landed disposition preserves lifecycle, and the measure behind them was corrected twice

The encrypted-storage cluster has one definition consumed through two package-configuration boundaries; two boundaries are pytest's requirement for exposing one fixture to two subtrees and are not duplication. The modelo repositories, committed registry snapshot families and remaining source, development and packaging clusters were reviewed against their current consumers with no lifecycle change found.

Of the four dispositions landed during this close phase, none is a flat merge, and that is the substantive result. Each cluster's bodies were byte-identical while closing over a module-level constant whose value differed per file, so a flat merge would have pointed several modules' own later assertions at another module's record with every test still passing. Two now take the value through a dependency the consuming module overrides, with the shared default raising; one takes it as a required positional on a factory with no default anywhere; one moved its rendezvous object together with the fixture that closes over it. A candidate was excluded on genuine body divergence rather than merged for tidiness.

No shared definition was placed in a package configuration file. An autouse fixture defined in a module is autouse for that module alone, and the same fixture in a package conftest reaches every test beside it, which is a lifecycle widening that presents as consolidation. Autouse reach was measured before and after each move and preserved exactly.

### fixture-disposition | corrected | The redundancy figure was wrong twice, in opposite directions

Grouping first on whole-name identity understated the population: a name with twenty-six definitions of which eleven are identical is real duplication a whole-group reading does not surface. Regrouping per cluster raised it to roughly fifty redundant definitions. That measure still compared only the executable body while ignoring the owner globals the census already models for this exact purpose. Including them, the count of genuinely substitutable clusters is zero.

The consequence is that most of the remediation this phase set out to do should not be done. The large remaining same-name groups were never dispatched, because under the corrected measure they are not duplicates. Both corrections came from running the instrument rather than reasoning about its output, and the decisive one came from an implementer who read the constants rather than the bodies.

### instrument | open | The census cannot classify what it can now see

A fixture produced by a factory and bound at module level carries no decorator, so the walk that fills the fixture population omits it, and the ownership manifest is built from that population alone. Such a fixture therefore received no row, no group and no disposition. Roughly ten exist in the tree today, created by this phase's own remediation.

The census now reports them, and a separate soundness defect was closed alongside: the import matcher compared bare function names with no scope check, so two identically named fixtures in one file both received an external import's consumers, which had already produced one false clean reading.

But visible is not classified. These bindings still take no manifest row, so the substitutable-duplicate rule cannot see them, and the campaign's requirement that the census contain no unclassified record is not satisfied for them. This is recorded as an open item rather than a closed one, because the alternative is to let a narrowed claim stand as if it were the original.

## Recommendations

- Keep the single justfile declaration and teach the lane authority to resolve templates through the rendering mode that actually substitutes them, failing closed when the tool is absent rather than falling back to unresolved text.
- Add an exclusion field to the lane record, parse both spellings, and subtract exclusions in the coverage predicate. Land it with its one consumer, since the predicate's verdict moves.
- Migrate both CI gate modules onto the lane authority and delete their private parsers, and derive the harness member list from the justfile declaration rather than restating it in Python.
- Collapse the four independent resolutions of the justfile executable, and the two independent answers to what counts as first-party corpus, onto one owner each.
- Re-run the fixture census verdict on a quiet tree, or on a clean checkout, before treating the fixture lane as verified. Record the peer-owned collection failures and the unenrolled credential-store tests as carry-forward against their own campaigns rather than absorbing them here.

## Notes

The close-phase regressions were found by measurement, not by review of intent. Each was confirmed against the live tree before being written down, and the widening finding is recorded with its before and after rather than as a judgement. The instrument defect is the load-bearing lesson: a proof whose reach is wrong reports a number about the wrong population, and 2097 against a true 21 is an error large enough to have been read as a catastrophe or ignored as noise, neither of which is the finding.
