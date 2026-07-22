---
tags:
  - '#audit'
  - '#cli-authority-quality-backlog'
date: '2026-07-22'
modified: '2026-07-22'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
  - "[[2026-07-17-cli-authority-quality-backlog-adr]]"
  - "[[2026-07-17-cli-authority-verb-conformance-audit]]"
---

# `cli-authority-quality-backlog` audit: `Close honesty review`

## Scope

Fresh-context honesty review of the CLI authority quality backlog plan, which reported twenty-seven of twenty-seven steps complete across eleven phases with no close audit. The campaign close honesty review discipline requires this gate before structural completeness may be declared; it never ran, and the plan sat at full completion for three days without it. This record is that gate.

The originating rescope record describes this plan as the one absorbing the residue of the split epic, which is the shape most likely to hide declarative-but-unexecuted steps. Every step and every execution record was verified against the tree at review time. Gates were run rather than read: two hundred thirty-one tests were executed across all eleven phases, plus one executed syntax-tree probe against the storage-namespace detector.

The campaign is substantively real. Twenty-four of twenty-seven steps carry verifiable, non-tautological artefacts confirmed at review time, and the execution records are unusually self-honest. Three steps closed weaker than their action text claims.

## Findings

### mcp-request-parity-is-tautological | high | The request half of the surface-parity gate asserts an identity and cannot fail

The step claims a per-verb parity diff proving every operator verb exposes the same request and response schema across the command-line and machine-context surfaces. Production builds the verb input schemas once and assigns the result verbatim to the tool descriptor. The test re-calls that same builder over the same keys and diffs the result against the descriptor it produced, so the mismatch list is structurally always empty. The failure modes the step describes, a parameter added to one surface but missing from the other, or an overridden input schema, are unreachable: any change flows into both sides identically, and no override occurs after assignment. The execution record half-discloses the shared builder and then claims a residual drift-catching value the test does not have.

The other two thirds of the same gate are sound. The response-side expectation is independently rebuilt from the schema registry rather than by calling the surface builder, and the verb-set comparison is a real cross-surface set difference. Only the request third is false-green.

### namespace-gate-blind-to-indirection | high | The storage-namespace adoption gate cannot detect the regression shape its sibling step fixed

The gate's predicates recognise only a direct sensitivity-class attribute access and a bare integer constant. A module-level constant bound to a raw literal and then referenced at the binding site appears as a name node and escapes both predicates. The reviewer executed the gate's own extracted detector against a probe using precisely the idiom the sibling step had fixed, and the detector returned no findings at all.

This is not hypothetical. The sede observation store uses exactly this module-constant shape today across six constants, correctly registry-sourced by the sibling step. Reverting any one of them to a raw literal passes the gate silently. The companion binding test does not close the gap either, because it compares values and a same-value re-hardcode is byte-identical.

Two narrower escapes sit in the same detector: a raw namespace string passed at a write site is never checked despite the module docstring claiming the definition is the single authority for that string, and the write-call inspection requires a keyword argument, so a positional call escapes. The gate's positive and negative controls are real and it is non-vacuous for the shapes it models; it is the coverage boundary that is misrepresented.

### triage-step-closed-as-vault-prose | medium | A disposition verdict was recorded only in removable scaffolding

The step claims a recorded disposition classifying a duplication cluster as intentionally distinct so that no duplicated policy, state ownership, or persistence behaviour survives unclassified. Its closing commit touched vault documents only and no code files. The dispositions file's last modification belongs to a different campaign's commit, and the rows the step cites pre-existed it. For the synchronous-wrapper category the dispositions file contains no entry at all; the execution record states in prose that it extends the intentional-distinctness verdict to that category.

Because the vault is removable development scaffolding by mandate, a verdict living only there has no home in the codebase, and the next duplication scan re-surfaces the wrapper category unclassified. The triage reasoning itself is sound: the divergent-coroutine and divergent-payload constraint-shape argument was confirmed, and the substitutability pre-filter was applied correctly. Only the persistence of the verdict is missing.

### publish-guardrail-lost-its-non-vacuity-proof | medium | A retired artefact took its discrimination proof and its publish half with it

The guardrail module authored by the eleventh phase no longer exists. It was deleted alongside the workflow stub it guarded, which is a legitimate retirement, and the same commit extended the successor guardrail. The successor is nonetheless weaker on two axes the step explicitly claimed. Its pattern set carries only the build half; the publish half the step authored, together with the action-marker scan for publishing actions, is absent. The step also shipped a companion non-vacuity test covering thirteen forbidden variants and five benign shapes, and no equivalent exists for the successor's pattern set, leaving an unproven detector that returns empty. Publish confinement remains covered behaviourally by three other tests in the successor module.

### custody-clause-closed-as-bookkeeping | medium | A step closed by verifying other steps' work without demonstrating its own clause

The execution record states plainly that the closure is bookkeeping only, documenting verification against the tree rather than new implementation, and that no production change was needed. That is honest and the cited verification is real. The gap is the second half of the action text, which required showing that certificate custody is not conflated with master-key custody. The record enumerates namespace, sensitivity, and schema version only; custody is never mentioned, and the sibling step's notes explicitly scope custody out as this step's separate concern, so neither step covers it.

Independent verification found the underlying conclusion holds: no production readers of the custody fields exist outside the registry module, and no custody literals exist under the authentication adapter tree. The facts are sound; the evidence for them does not exist in the campaign, and no gate would catch a future custody redeclaration.

### missing-close-audit | medium | The mandated close honesty review never ran

No close audit existed for this plan while it stood at full completion. This record is that gate, and the two high findings above are what it exists to surface.

### size-budget-red-at-head | low | Budget failures at review time belong to peer campaigns

The size-budget suite reports two failures covering three offenders across a ledger action module, a live command module, and a ledger command function. Commit history traces all of them to peer campaigns rather than this one. This campaign's own surface is clean and well inside budget, so the line-budget claim made by its own commit holds.

### registry-floor-assertions-are-lower-bounds | low | Deletions above the floor are invisible

Two of the adoption gate's assertions are lower bounds rather than exact counts, so a deletion that leaves the population above the floor is not detected. Defensible against a growing tree.

### declarative-verb-audit | low | Four of five declarative steps nonetheless produced durable gates

Five steps use declarative verbs in their action text. Four produced real artefacts: a drift correction landed a grammar gate, an adjudication landed a relocation plus a write-path binding proof, a caller audit landed a syntax-tree gate with a pinned sanctioned-site set and a discrimination proof sharing the production gate's own extraction helpers, and a contract decision was deliberately paired with a following step carrying the enforcing assertion. Only the triage step closed as prose. The caller-audit step and the triage step form a controlled experiment: the same declarative verb with opposite outcomes.

### exec-record-coverage-complete | low | Every step carries a record and the records correct their own plan

All twenty-seven execution records are present, one per step, correctly named. None is narrative-only except the two named above. The records are notably self-honest: one admits its plan text was architecturally impossible as literally stated and records the layering-correct realisation instead, one discloses its own deferral and an audit-label change, one corrects the plan's framing of a duplication as composition rather than runtime nesting, and one reproduces a flake before fixing it. Several record owner-external red gates rather than claiming full green.

### relocation-atomicity-confirmed | low | The diagnostics-namespace relocation landed atomically and clean

One commit carries the canonical move, both re-export removals, the consumer repoint, the raw-literal replacement, a dormant-path deletion, both test consumers, the registry parity count, and a new binding proof in a single index. No leftover core symbol and no re-export shim remain. The consumer imports through the storage package facade rather than a private submodule, and the binding test asserts the absence of the old attribute as a positive proof of deletion rather than relying on search. The commit subject carries the relocation tag the boundary discipline requires.

### review-workflow-parity-sound-with-scope-caveat | low | Real persistence, real classifier, one mis-named test

The persistence proofs use isolated profiles and a real subprocess classifier with no mocks, and origin attribution asserts against the recorded source command rather than a hardcoded copy. One caveat is worth naming: the route-parity test hands the direct path its source command explicitly, so it proves plumbing parity rather than label parity, and it invokes the application layer rather than the command-line surface despite its name. The step disclosed the related label change openly, so nothing is hidden. The step's stated deferral has since become stale in the campaign's favour, because the defaults it left intact were subsequently removed and the source command is now a required parameter at every construction site.

## Recommendations

Delete the request-schema parity assertion as false-green, or make it independent by deriving the expected request schema from the live command parameter objects directly, mirroring what the response side already does, and add a discrimination proof that injects a property into one descriptor and fails.

Extend the storage-namespace detector to resolve module-level constant bindings: when a sensitivity, schema-version, or classification value is a name node, look up its module-level assignment and apply the raw-literal predicates to that. Add the indirection shape to the injected-redeclaration fixture so the discrimination proof covers it. Also flag a raw string passed as a namespace argument and match positional write calls.

Write the synchronous-wrapper disposition into the dispositions file with a classification and concrete locations so the verdict survives removal of the vault, and re-confirm the command-registry rows still describe current line ranges.

Restore the publish-half denylist and a non-vacuity proof for the successor guardrail's pattern set, scoping the release-creation pattern to non-publish jobs.

Add a custody-binding assertion to the adoption gate, or record explicitly that custody has no consumers and therefore no duplication surface.

Where a future plan writes a declarative verb such as triage, assess, or review, require the step row to name the durable artefact that is its completion condition, whether a gate or a row in a tracked dispositions file. The caller-audit and triage steps in this plan are the controlled experiment justifying the requirement.

The plan should not stand at twenty-seven of twenty-seven complete until the two false-green gates are addressed.
