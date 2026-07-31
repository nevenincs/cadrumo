---
tags:
  - '#audit'
  - '#post-release-distribution'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:96068563d59a6c2751a1f77b14c4aab56e5f8c3c6c353735601888c9129e5ba8'
related: []
---

# `post-release-distribution` audit: `close honesty review`

## Scope

Fresh-context honesty review of the distribution campaign, run against the
closure summary by a reviewer with no prior involvement in it, on the standing
requirement that a campaign is not structurally complete until an inherited
reading has listed what is missing, vague, or assumed-but-unverified.

Reviewed: the topology decision record, the distribution plan, the marketplace
publish module and its tests, the channel descriptor, the publish workflow, and
the documentation-claims gate. Commits examined: `33acaea32a`, `daee60fe7a`,
`157e31ce06`, and `90287d349d` — the last of which landed during this review.

Two claims were supplied as already verified and were not re-verified: the
merged community-package publisher namespace, and the stale pre-rename plugin
name in the public marketplace.

Semantic search was unavailable for this review. The code index reported 1027
sections against roughly 4546 files with its generation still running, and a
partial index answers confidently rather than refusing, so every finding below
rests on direct reading, `rg`, executed scripts, and git history. No finding
here is grounded in a semantic-search result.

Two verification claims were tested by execution rather than by reading, because
both are the shape that passes review while being false. Both survived — the
detail is recorded under the sound-claims findings, since a close review that
reports only failures gives the next reader no way to tell what was checked.

## Findings

### adr-reversed-in-place | critical | The topology ruling reversed its own accepted decision by rewriting the record, deleting the reasoning that had rejected the now-chosen option instead of answering it

The first ruling chose an account-scoped Scoop bucket repository and explicitly
rejected serving the bucket from the product repository's own directory. Commit
`90287d349d` inverts both: the rejected option is now the chosen one
(`.vault/adr/2026-07-25-distribution-repo-topology-adr.md:90`), and the
previously chosen option is now recorded as rejected (`:77`).

What is lost is the reasoning, which was deleted rather than rebutted. The
removed text held two substantive objections: that a bucket living in one
product's repository "is product-scoped by construction and cannot serve a
sibling product, so it solves the count while preserving exactly the
fragmentation under review", and that "no real-world precedent was found for a
product's primary repository serving its own bucket either". Neither survives in
the current record and neither is answered by it. The nearest current text
(`:43-46`) establishes only that Scoop *can* resolve manifests from any
repository's subdirectory — a mechanical point that was never in dispute. The
ownership objection stands untouched: a sibling product served from this
product's repository is precisely the product-scoping the campaign set out to
retire, and the record now asserts "one distribution repository total, and it
does not grow per product" without reconciling that against its own prior
finding.

Compounding this, the reversal was made in place. The filename, the date, and
the `accepted` status are unchanged; only the H1 title differs. A reader
arriving at this record has no signal that the decision it documents is the
opposite of the decision the campaign executed under, and the audit trail exists
only in git history.

Remediation: supersede rather than overwrite. Restore the first ruling as an
`accepted`-then-`superseded` record and issue the reversal as its own dated ADR,
whose Considered options carries the deleted objections explicitly and answers
them — specifically, how a sibling product is served from this product's
repository without reintroducing product scope, and what the precedent search
now concludes.

### completion-claimed-at-27-percent | critical | The campaign was declared complete while its plan stands at 7 of 26 steps and its governing ruling was rewritten after the declaration

`vaultspec-core vault plan status` on
`.vault/plan/2026-07-17-post-release-distribution-plan.md` reports `Completion:
7 of 26 (26.9%)`, with 19 steps open. Every one of the six steps named in the
closure summary remains unchecked. Separately, the governing ADR was materially
rewritten by `90287d349d` after the completion claim was made, which means the
declaration described a topology that the record no longer specifies.

What is lost is the reliability of the completion signal itself. A campaign
reported complete at 27% teaches the next reader that the plan's own counter is
not to be trusted, which is the mechanism by which structural incompleteness
survives a closure pass.

Remediation: retract the completion claim and re-describe the campaign as at a
checkpoint. Enumerate the 19 open steps and, for each, the single action and
actor that would close it. Re-run the honesty review after the ADR reversal has
settled, since the current review necessarily reviewed a moving record.

### unblocked-is-reworded | high | Three steps are annotated as partially unblocked where only a redundant clause was struck, and three re-scoped steps moved their blocker from private to nonexistent

`P03.S20` (`.vault/plan/2026-07-17-post-release-distribution-plan.md:53`) and
`P04.S23` (`:61`) each had a conjoined blocker list from which one clause was
removed. In both cases every remaining clause independently gates the step, so
the distance to executable did not shrink by a single action; `S23` is annotated
partially unblocked while all three of its named dependencies remain blocked.

`P01.S01` (`:24`), `P03.S16` (`:49`), and `P03.S17` (`:50`) moved from "the
repository exists but is private" to "the repository does not exist". Both
states are unusable by any user, and the move is arguably backwards: a private
repository becomes public with one setting change, whereas a nonexistent one
must be created and populated. `S16`'s blocker clause count rose from two to
three.

`P03.S18` (`:51`) states the dangling repository variable "is FIXED". That
variable is a continuous-integration repository variable whose value lives in
the hosting account's settings, not in the tree, and no commit, exec record, or
captured evidence in the tree can establish that the operator changed it. The
step then concedes the acquisition still cannot resolve, pending an operator
deletion of the stale plugin entry — so the blocker moved from "the repository
does not exist" to "the repository exists but serves the wrong plugin name".

What is lost is the ability to read the plan for remaining risk. An annotation
that reports motion where there was none inflates apparent progress precisely on
the steps a reader would otherwise scrutinise.

Remediation: replace each partially-unblocked annotation with the single
remaining gating action and its actor. Withdraw the "is FIXED" claim for any
state the tree cannot evidence, and record it instead as an operator
precondition to be confirmed at publish time. Credit where due: the re-scoped
steps are labelled re-scoped rather than unblocked, and none of the six is
falsely checked.

### plan-names-retired-variables | high | Plan rows name distribution variables the workflow has since renamed or deleted outright

Three plan rows name `CADRUMO_SCOOP_BUCKET_REPO` and `CADRUMO_MARKETPLACE_REPO`.
The workflow now reads `CLAUDE_MARKETPLACE_REPO` and `CLAUDE_MARKETPLACE_TOKEN`
(`.github/workflows/publish-release.yml:507-508`) and `HOMEBREW_TAP_REPO` /
`HOMEBREW_TAP_TOKEN` (`:478-479`), and the Scoop pair no longer exists at all,
with `dev/release/tests/test_publish_release_workflow.py:436` asserting its
absence.

What is lost is that an operator following the plan would set variables nothing
reads, and would not set the ones the publish actually requires — on the exact
path the campaign is holding for operator action.

Remediation: sweep the plan rows onto the current variable names, and delete the
Scoop variable references rather than renaming them, since the in-repository
bucket needs no target and no credential.

### claims-gate-is-inert | high | The documentation-claims gate asserts nothing about its patterns and currently matches nothing at all, so "verified in both directions" is untrue in any test sense

`dev/docs/tests/test_distribution_claims.py` is both the gate and its only test
module; no other file in the tree exercises the patterns. It contains two test
functions, and neither passes any string to any pattern. The row-id guard at
`:236` iterates the pattern table while explicitly discarding the pattern
(`for label, _pattern, row_ids in _CLAIM_PATTERNS`).

The data-driven test is additionally a no-op against the current tree: 59
documentation files are scanned and zero claims are found, so the function
reaches its early return at `:211` and never evaluates evidence rows or its
assertion. The gate is green because it is inert, not because it is satisfied.
The observed run is `2 passed in 8.82s` — a real, non-empty selection, so this
is not a false green from an empty marker selection; the two tests genuinely
pass while covering neither direction.

What is lost is the entire fail-closed guarantee the campaign leans on for
documentation honesty: nothing would notice if a widened pattern stopped
matching a real install command, or started matching prose.

Remediation: add direct per-pattern assertions — for each pattern, one string
that must match and one that must not — so the gate's own behaviour is pinned
independently of whether the current documentation happens to contain a claim.

### brew-pattern-over-broadened | medium | The widened tap pattern is not vacuous but now matches a third-party tap, a line break, and a negated disclaimer

Direct evaluation of the widened pattern
(`dev/docs/tests/test_distribution_claims.py:91`, `brew\s+tap\s+\S+/\S+`)
against the retired one confirms it still rejects the prose line it was written
to reject, at `docs/download.md:110`. The vacuity failure mode is genuinely
absent, and that specific concern should be recorded as cleared.

Three real over-broadenings remain. The pattern no longer anchors on the product,
so an unrelated third-party tap mentioned in documentation matches. The scan
applies `search()` to whole-file text (`:157`) while `\s+` crosses newlines, so a
line ending in "Homebrew tap" followed by a line beginning with a path token
matches. And a negated disclaimer of the form "do not run brew tap … yet"
matches as a positive claim, which directly contradicts the module's own
docstring promise at `:11-15` that disclaimers do not match.

What is lost is precision in the direction that produces false refusals: the gate
would block a release over documentation prose that makes no acquisition claim.

Remediation: anchor the scan per line rather than per file, and re-anchor the
pattern on the product path segment so an unrelated tap does not match. Add the
three strings above to the negative assertions the previous finding requires.

### publish-is-not-atomic | medium | A multi-plugin cohort that refuses partway leaves the marketplace tree mutated and its index unmerged, and no test covers a cohort declaring more than one plugin

`publish_cohort_plugins` validates and mutates in a single loop
(`dev/packaging/marketplace_publish.py:108-117`), so a refusal on the Nth plugin
occurs after plugins 1..N-1 have already been removed and replaced, while the
index merge at `:119-126` never runs. Executed against a cohort declaring two
plugins whose second has no tree, the first plugin's tree was replaced with the
cohort version and the index left unmerged, with the function refusing as
designed — a torn state that is neither the old nor the new.

Every test cohort declares exactly one plugin: the `_cohort` helper at
`dev/packaging/tests/test_marketplace_publish.py:51` hardcodes a single entry
and no test constructs a multi-entry cohort. The scenario is therefore entirely
uncovered.

Severity is medium rather than high because the blast radius is currently
contained: the module runs against an ephemeral clone
(`.github/workflows/publish-release.yml:526`), a non-zero exit fails the step
before the commit and push, and the torn tree is discarded. The defect is real
at the module boundary rather than at the remote today. The module docstring's
claim that "both operations are idempotent" is nonetheless false on the refusal
path.

Remediation: stage into a temporary tree and move into place once every declared
plugin has validated, so a refusal mutates nothing. Add a multi-plugin cohort
test asserting the marketplace is byte-identical after a refusal, and correct the
idempotence claim in the docstring to name the refusal path.

### plugin-name-has-no-owner-check | medium | A cohort silently takes over a sibling product's plugin when the two declare the same plugin name

Ownership is keyed on plugin name alone. `merge_marketplace_index` retains only
published entries whose name the cohort does not declare
(`dev/packaging/marketplace_publish.py:87-89`), and the tree copy removes and
replaces `plugins/<name>` regardless of which product published it (`:113-117`).
A cohort declaring a name a sibling already owns therefore overwrites the
sibling's tree and its index entry with no refusal and no warning — the exact
class of loss the account-scoped narrowing was introduced to prevent, reachable
by a different route.

The single merge test at `:190` asserts same-name replacement as the desired
behaviour, which is correct for one product publishing a new version of its own
plugin, but nothing distinguishes that from a different product claiming the
name.

What is lost is the sibling-safety property the campaign states as the reason
the module exists. It holds for plugins a cohort does not name and fails for
plugins it names by collision.

Remediation: carry the publishing product's identity on the index entry and
refuse when a cohort declares a name an entry attributes to another product,
rather than merging by bare name.

### concurrent-publishes-unhandled | medium | Two products releasing into the shared marketplace can race, and the shared marketplace makes that a designed-in condition rather than a hypothetical

The marketplace step clones, mutates, commits, and pushes
(`.github/workflows/publish-release.yml:525-542`) with no lease, no retry, and
no concurrency group. A sibling product's push landing between this job's clone
and its push makes the push a non-fast-forward, failing the release.

The topology ruling's central premise is that several products publish into one
account-scoped marketplace, so concurrent publication is now an expected
operating condition rather than an edge case. Nothing in the campaign records it
as considered.

What is lost is release reliability at exactly the moment the new topology
starts paying off — the first release where two products are live.

Remediation: add a retry that re-clones and re-applies on a rejected push, or a
repository-level concurrency group serialising marketplace publication across
products. Record whichever is chosen as a constraint on the topology ruling.

### scoop-runner-adr-unreconciled | low | The prior Scoop runner ruling is named only in frontmatter while the new ruling moves where Scoop manifests live

`2026-07-22-scoop-runner-topology-adr` appears in the topology record's
`related:` field and nowhere in its body: the body carries no supersession
statement and no reconciliation. The new ruling relocates Scoop manifests into
this repository's own bucket directory, which bears directly on the evidence lane
the earlier ruling governs.

What is lost is a reader's ability to tell whether the earlier ruling still
stands. Both records are `accepted`, and they are about the same channel.

Remediation: add an explicit prior-decision reconciliation to the topology
record stating which parts of the runner ruling stand, which are amended, and
whether its evidence lane is affected by the manifest relocation.

### sibling-regression-proof-is-sound | low | The anti-regression claim survives execution, though its wording describes something the tree cannot run

The claim that the sibling-survival test fails against the retired wholesale tree
replacement was tested rather than accepted. The retired behaviour was
reconstructed faithfully from `17abf9c021` — the top-level delete preserving only
the git directory, followed by the recursive copy — and the shipped test's
scenario was run against it. All three of the test's survival assertions fail:
the sibling plugin tree is gone, the unrelated top-level file is gone, and the
merged index retains only the publishing product. The regression test is genuine
and is not a false positive.

One wording caveat is worth recording. The retired behaviour was a shell command
inside the publish workflow and the replacement is a Python function, so there is
no seam at which the shipped test can be run against the old behaviour; the
docstring at `dev/packaging/tests/test_marketplace_publish.py:9-12` asserts an
executable counterfactual that requires an out-of-tree reconstruction to check.
The suite itself is real: `8 passed in 4.44s` on a confirmed non-empty selection.

Remediation: soften the docstring to say the property was verified against a
reconstruction of the retired behaviour, so a later reader does not go looking
for a test seam that does not exist.

### homebrew-core-bar-stated-as-terminal | low | The core-submission question is now closed rather than deferred, which resolves a concern this review carried

The current record states the self-submission notability bar is far above the
product's position, quantifies it, and closes the question: "The tap is the
terminal state for that channel, not a waypoint toward core"
(`.vault/adr/2026-07-25-distribution-repo-topology-adr.md:57-60`). This is
recorded as satisfied so the question is not raised again.

One gap remains at the edge of it: the Consequences section enumerates what stays
open and does not mention core submission, so a reader who reaches Consequences
first sees neither an open item nor a closure. Remediation: name it in
Consequences as decided-closed.

### variable-rename-swept-clean | low | The rename off the product prefix is complete outside the vault, which resolves the second concern this review carried

The reversal also overturned the earlier decision not to rename the distribution
variables; the record now states the rename is by operator ruling and concedes
the mechanical gain is nil, keeping the transferability argument
(`.vault/adr/2026-07-25-distribution-repo-topology-adr.md:105-112`). The sweep
itself is clean: no product-prefixed distribution variable survives outside the
vault documents, and the sole remaining occurrence is a negative assertion
proving absence at `dev/release/tests/test_publish_release_workflow.py:436`.

The vault half of the sweep is incomplete and is carried as its own finding
above. Recorded here so the code-side sweep is not re-audited.

## Recommendations

Retract the completion claim before anything else. The plan stands at 7 of 26
and the governing record was rewritten after the declaration, so the campaign is
at a checkpoint; re-running this review after the record settles is the only way
to review a stationary target.

Resolve the reversal through supersession rather than in-place rewriting, and
answer the two deleted objections explicitly. This is the one item that needs a
decision rather than a fix: a follow-on ADR must rule on whether a sibling
product is served from this product's repository, and if so, why that is not the
product-scoping the campaign set out to retire. Until that is answered, the
chosen topology rests on reasoning the record no longer contains.

Make the claims gate assert its own behaviour. Per-pattern positive and negative
assertions are a small change that converts an inert gate into a real one, and
they are the precondition for trusting any future widening.

Harden the publish module on the three uncovered paths — atomicity across a
multi-plugin cohort, plugin-name ownership, and concurrent publication. The first
two are module-local; the third needs a workflow-level decision on serialisation
versus retry.

Sweep the plan: current variable names, and blocked reasons that name the single
remaining action and its actor rather than reporting motion. Every finding above
should become a tracked step rather than remaining prose in this document.

Record for the next reviewer that two supplied claims were taken as given and
that semantic search was unavailable, so both are open surfaces rather than
verified ones.
