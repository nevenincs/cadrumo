---
tags:
  - "#audit"
  - "#kent-cli-roleplay"
date: 2026-04-24
modified: '2026-04-24'
related:
  - "[[2026-04-24-aeat-cli-wireframe-adr]]"
  - "[[2026-04-24-aeat-cli-wireframe-research]]"
  - "[[2026-04-21-auth-cli-adr]]"
  - "[[2026-04-18-unified-review-queue-adr]]"
  - "[[2026-04-18-category-assignment-cli-adr]]"
---

# kent-cli-roleplay-audit

## scope

This audit preserves six completed Kent CLI roleplay scenario findings and the
current wireframe ADR/research trail as one append-only reference for
command-shape decisions. Scope is limited to the scenario outputs already
established in this thread plus the current wireframe pair. No new discovery is
introduced here.

## method

This document is a bounded synthesis, not a fresh research pass. It preserves
three layers only: the user intent Kent actually expresses, the current command
trail Kent must survive today, and the leaner user-facing flow shape that
should survive into wireframing. The audit emphasis is CLI shape, stable units
of work, reconciliation truth, and evidence packaging.

## scenario-index

1. Monday Morning Triage: Kent wakes up, deadlines are approaching, and he
   needs to know what to file and what is missing.
2. I Think I Missed A Form: Kent suspects he forgot a filing and needs to
   reconcile AEAT truth with unfinished local work.
3. Two Years Late Backlog Recovery: Kent is behind across multiple years and
   needs a backlog picture of expected, filed, missing, and noticed
   obligations.
4. Local State Changed, What Differs From AEAT: Kent reclassified local data
   and needs to compare local filing state against AEAT or filed artifacts.
5. AEAT Audit Package Export: Kent is being audited and needs to export every
   calculation, artifact, and reference as evidence.
6. 2,995 Transaction Review Loop: Kent is alternating between manual and
   LLM-backed classification over a very large transaction backlog.

## scenario-1-monday-morning-triage

### user-intent

Kent wants one truthful morning answer: what is due now, what applies to his
business, and what is still missing before he can file.

### current-command-trail

The current path fragments the question across `doctor`, `deadlines`,
`modelos`, `workflow`, and `review`. `deadlines next` depends on profile setup,
so `modelos year-plan` becomes the practical fallback. Kent has to encode
business reality through obligation flags rather than being guided by one
`what applies to me` surface. `workflow next` and `review queue` still do not
answer `what is missing for this filing` cleanly. `filing build --help`
remains developer-shaped and can fail on Windows help rendering.

### better-lean-flow

Preserve one triage surface such as `today`, `status today`, or
`prepare --due`. Preserve one focused filing worklist command per
`(modelo, period)`. Preserve the design rule that deadlines, applicability, and
missing-input detection belong together rather than being split across
unrelated namespaces.

### cli-shape-lesson

Triage fails when the CLI treats due dates, applicability, and preparation gaps
as separate systems. Kent does not want command partitions first; he wants one
filing object with due-state and readiness state attached.

## scenario-2-i-think-i-missed-a-form

### user-intent

Kent wants to ask a simple question in natural operator language: did I miss
something, what is the source of truth, and how do I resume the right filing.

### current-command-trail

The noun Kent expects is `status`, but the real answer is split across `auth`,
`filing import --from-aeat`, `inbox`, `filing list`, `review stale`,
`submission list`, `workflow list`, and finally `run list/show`. `status` is
the natural noun but is not yet a truthful public surface. In practice, `run`
can be more useful for forensic reconstruction than the higher-level workflow
surfaces. Local and AEAT truth are still not reconciled into one object.

### better-lean-flow

Preserve one reconciled `status` family that can answer expected vs AEAT vs
local vs blocked-by-auth. Preserve one `resume this filing` action that opens
the right next step automatically. Preserve inbox and filing history under the
same truth surface instead of scattering them across separate recovery
commands.

### cli-shape-lesson

If Kent says `status` and the product answers with a scavenger hunt, the
operator language is wrong. Reconciliation has to be first-class, and the
recovery path has to branch from that same surface.

## scenario-3-two-years-late-backlog-recovery

### user-intent

Kent wants a backlog view across multiple years that distinguishes what should
exist, what is already filed, what is missing, and what is complicated by
notices or blocked imports.

### current-command-trail

Kent must separately inspect auth state, hidden or gated AEAT history surfaces,
inbox and notices, yearly obligation plans, local submissions, workflows, and
manual declaration imports. The CLI can compute expected obligations by year
and can mark many periods overdue, but it cannot reconcile expected vs
filed-on-AEAT vs known-locally in one place. Manual portal download plus
`filing import --from-declaracion` remains a practical fallback when live AEAT
import is blocked. Multi-period recovery has no first-class backlog model.

### better-lean-flow

Preserve a first-class `backlog` family with canonical period or range syntax.
Preserve states such as `missing`, `filed_on_aeat`, `known_locally`,
`notice_open`, and `ambiguous`. Preserve batch import of already-filed periods
and batch scaffold of genuinely missing periods so Kent can move a whole
backlog instead of one period at a time.

### cli-shape-lesson

Backlog recovery is not a pile of single-period lookups. It needs a durable
multi-period object model and explicit reconciliation states, or Kent is forced
to reconstruct backlog truth manually.

## scenario-4-local-state-changed-what-differs-from-aeat

### user-intent

Kent wants to know what changed after local reclassification and whether local
filing state still matches AEAT-facing truth or the filed artifact baseline.

### current-command-trail

Kent rebuilds local state through `workflow run`, inspects review state,
exports a file, verifies it, imports AEAT or declaration artifacts, and then
diffs files. The real compare unit is fragmented across draft IDs, transaction
IDs, divergence records, PDFs, and BOE files. `submission verify/diff` are
real and useful, but period-level compare is not a first-class command. The
practical fallback is file-vs-file diff once two artifacts exist.

### better-lean-flow

Preserve a first-class `compare` family where the unit is `(modelo, period)`.
Preserve one discrepancy object with drill-down, apply or fix, and rerun
semantics. Preserve a closing `verify` step that rechecks local, export, and
AEAT-facing truth after the correction path.

### cli-shape-lesson

Comparison is currently artifact-first when Kent needs case-first. A coherent
discrepancy object is more important than adding more diff primitives, because
the operator unit has to stay stable through rebuild, inspect, fix, and
reverify.

## scenario-5-aeat-audit-package-export

### user-intent

Kent wants one exportable evidence bundle for an audit case: calculations,
generated artifacts, references, checksums, provenance, and replayability.

### current-command-trail

Strong primitives already exist in `workflow`, `run show`, `run replay`,
`submission preflight/export/verify/diff`, `modelos`, `portals`, and
`normatives`. Kent still has to assemble the evidence package manually through
many unrelated commands and stdout redirections. Audit provenance exists in
parts, but not as one case-level bundle. Manual and reference content are
uneven, so normatives and model metadata matter as supporting evidence.

### better-lean-flow

Preserve a first-class `audit` family that is case-first, not primitive-first.
Preserve immutable case metadata, provenance capture, formula and reference
explanation, round-trip verification, and final packaging. Preserve one output
bundle with manifest, calculations, references, artifacts, checksums, and
replay trace.

### cli-shape-lesson

The problem is not missing primitives; it is missing packaging semantics. Audit
work becomes brittle when evidence, provenance, references, and replay are
spread across unrelated commands rather than attached to a single case object.

## scenario-6-2995-transaction-review-loop

### user-intent

Kent wants throughput on a very large transaction backlog without losing
control over contested rows, reusable rules, or classification quality.

### current-command-trail

Current strong surfaces are `financial txs`, `review`, `categories`, and
`financial profile`. Kent rebuilds the catalogue, sets reusable ratios, runs
`classify-llm` in bulk, then falls back to one-row-at-a-time review and manual
classification. Bulk automation exists, but the human correction loop is still
ID-copying and row-by-row. Review history is useful for contested rows, but
throughput is limited by poor batch review ergonomics.

### better-lean-flow

Preserve a shorter `tx` or equivalent high-throughput namespace. Preserve one
batch auto-run command that can classify, categorize, and infer percentage in a
resumable way. Preserve one review session surface grouped by merchant or
pattern, with accept, edit, exclude, and defer actions. Preserve rule
promotion from repeated human corrections.

### cli-shape-lesson

The bottleneck is not raw model capability; it is operator friction in the
correction loop. When human review remains row-oriented, the system cannot
compound learning fast enough to clear a large backlog.

## cross-scenario-cli-shape-failures

The CLI lacks one truthful reconciliation surface for what Kent owes, what AEAT
has, what exists locally, and what is missing. The current unit of work is
unstable: Kent is forced to think in years, modelos, periods, profiles, draft
IDs, run IDs, files, divergences, and inbox items instead of one coherent
filing object. `status` is the noun Kent expects, but today it is not a
reliable top-level truth surface. `workflow`, `submission`, `review`, `filing`,
and `run` expose real power, but they read like internal system partitions
rather than one operator language. Compare, recovery, and audit flows are
artifact-rich but not case-first. Bulk automation exists in places, but human
review is still too row-oriented and too fragmented. AEAT truth, local truth,
and evidence-package truth remain separate systems in the current UX. The real
redesign pressure is not command renaming; it is choosing stable user-facing
units of work and clustering commands around them.

## emerging-command-families

A stable CLI shape is emerging from the roleplays. `status` should become the
truthful reconciliation surface for expected, local, AEAT, blocked, and
resumable state. `today` or an equivalent due-focused slice should act as the
morning triage view. `backlog` should own range-based recovery and explicit
reconciliation states across periods. `compare` should own `(modelo, period)`
discrepancy analysis and correction loops. `audit` should own case packaging,
provenance capture, replay, and exportable evidence bundles. `tx` or an
equally short high-throughput namespace should own bulk classification and
grouped review sessions. These families matter because they expose durable user
work units rather than internal subsystem boundaries.

## open-naming-tensions-to-carry-into-wireframing

`status` is the strongest natural noun, but it must become truthful before it
becomes prominent. `today` is strong for triage, but may be better as a focused
slice under `status` if the product wants one dominant truth surface. `filing`
is accurate in implementation terms, but may still be too primitive-first if
the visible object is really a case or obligation. `run` is currently useful
for forensics, yet its operator prominence is a symptom of missing higher-level
truth surfaces. `compare` and `audit` are good user verbs only if their units
remain `(modelo, period)` and case, not raw artifact handles. `tx` is
efficient and high-throughput, but the wireframe should test whether Kent reads
it as obvious shorthand or as internal jargon.

## next-scenario-gaps

The next wireframe pass should force decisions on the stable primary object:
filing, obligation, case, or status row. It should also force period and range
syntax, because backlog and compare flows depend on a canonical way to name
work. The wireframe should make blocked-by-auth visible without collapsing
reconciliation truth. It should make evidence packaging visibly case-first, not
a loose collection of exports. It should test whether the review loop can move
from row-based handling to grouped session handling without hiding contested
edge cases. It should also test whether one truthful surface can hold
deadlines, applicability, local progress, AEAT truth, notices, and resume
actions without becoming unreadable.

## reconciliation-wireframe-candidates-status-today-backlog

**Current truth on 2026-04-24.** `status` is publicly advertised but still
empty in help. The real filing-state truth is still split across `deadlines`,
`review`, `submission`, `workflow`, `auth`, and `inbox`. The cleanest
wireframe direction is one shared reconciliation object, with `today` as the
fast triage slice and `backlog` as the range-based recovery surface.

### `status`

Purpose: solve scenario 2, `did I miss something, and what is the real state
for this filing across expected/local/AEAT/blocked?`

Preferred family shape:

- `status show`
- `status resume`
- `status history`
- `status today` as a slice, not a separate model

Wireframe intent:

- top-level reconciliation family for single-target truth
- default view answers: applicable or not, due or not, drafted or not, filed
  or not, AEAT-confirmed or not, blocked or not, next action
- primary unit is one filing obligation, not one subsystem
- `status resume` biases toward `where do I continue?` rather than `show me all
  metadata`
- `status history` exposes prior reconciliation transitions without forcing the
  user into AEAT-only or local-only terminology

Recommended sentence patterns:

- `status show <modelo> --period <period>`
- `status resume <modelo> --period <period>`
- `status history <modelo> --period <period>`

### `today`

Purpose: solve scenario 1, `what needs attention now, this morning, with the
least branching?`

Placement:

- best initial shape is a promoted slice of `status`
- candidate command is `status today`
- a top-level `today` alias can be tested later if discovery shows users reach
  for it before `status`

Wireframe intent:

- fast triage view, not a generic deadline list
- includes review blockers, stale approvals, inbox or notice pressure,
  auth-blocked work, and due-soon obligations
- surfaces urgency, blocker, and next action first
- optimizes for low branching: one screen that tells Kent what to do first,
  second, and ignore for now

Recommended sentence patterns:

- `status today`
- `today show`
- optional horizon control: `--days <n>`

### `backlog`

Purpose: solve scenario 3, `how do I recover multiple missed periods across
years without reconstructing truth one period at a time?`

Placement:

- keep as its own top-level recovery family
- do not collapse into a `status` filter
- frame explicitly as filing or obligation backlog to avoid collision with
  transaction-review backlog language

Preferred family shape:

- `backlog show`
- `backlog import`
- `backlog scaffold`
- `backlog resume`

Wireframe intent:

- range-first recovery surface over many obligations
- shows aggregate counts by reconciliation state before row detail
- supports recovery workflows where local records are incomplete, imported, or
  not yet scaffolded
- `backlog resume` should reopen the highest-value unresolved recovery window,
  not just list rows again

Recommended sentence patterns:

- `backlog show --from <period> --to <period> [--modelo <modelo>]`
- `backlog import --from <period> --to <period> [--modelo <modelo>]`
- `backlog scaffold --from <period> --to <period> [--modelo <modelo>]`
- `backlog resume --from <period> --to <period> [--modelo <modelo>]`

### canonical-object-and-sentence-grammar

Shared base object:

- `ObligationCase`, keyed by `(modelo, period, profile_tax_id)`

Minimum fields carried everywhere:

- deadline/applicability
- local draft state
- local submission state
- AEAT history state
- notice state
- reconciliation state
- next action

Projection rules:

- `status` renders one or more `ObligationCase` rows
- `today` renders `TodayAgendaItem` as a projection of `ObligationCase`, with
  urgency, blocker, and next action surfaced first
- `backlog` renders `BacklogWindow` over many `ObligationCase` rows, plus
  aggregate counts by reconciliation state

Sentence grammar:

- keep grammar as `family + decisive verb + explicit scope`
- single target always uses `--period`
- ranges always use `--from/--to`
- do not fork period grammar by command family

Help-text rules:

- Kent-first, operational, honest
- first sentence answers the user question
- second sentence states the next action
- every view labels whether truth is `local`, `AEAT`, or `blocked by auth`
- keep ASCII-safe
- disclose support limits by `modelo`, `ejercicio`, and stage
- avoid subsystem nouns, issue numbers, and any implication of broader live
  AEAT coverage than actually exists

### collisions-and-naming-risks

- `status` vs `auth status`: keep filing-state and session-state clearly
  separate in naming, help text, and examples
- `today` vs deadline-only view: avoid reducing it to due dates; it must
  include blockers, stale approvals, notice pressure, and auth friction
- `backlog` vs review backlog terminology: label it as filing or obligation
  backlog in help and wireframes
- largest structural risk is divergence: `status`, `today`, and `backlog` must
  remain projections over the same underlying reconciliation object, not three
  separate truth models

### decision-prompts-for-next-wireframe-pass

- Should `status today` ship first, with `today show` held back as an alias
  pending discovery?
- Should `status resume` and `backlog resume` be mandatory first-class verbs in
  the wireframe, or follow after `show` validation?
- Which reconciliation states are required for v1 row labeling so that
  `local`, `AEAT`, and `blocked by auth` remain explicit without becoming
  noisy?
- What exact phrasing best distinguishes filing-state `status` from
  session-state `auth status` at first glance?

## discrepancy-audit-throughput-wireframe-candidates-compare-audit-tx

### compare

**Purpose**

Kent needs one filing-case answer after local changes: what differs now against
AEAT truth or a filed artifact baseline, and what must be fixed or re-verified
next. This should be the case-first surface for discrepancy work, not a raw
artifact diff entrypoint.

**Preferred family shape**

- `compare show`
- `compare explain`
- `compare fix`
- `compare verify`

Keep raw artifact-vs-artifact diff behind an advanced or compatibility leaf.
Current shipped truth remains `aeat submission diff`; `compare` should promote
that primitive into a Kent-facing case workflow.

**Wireframe intent**

`compare show` should open on one filing case, summarize whether local differs
from `AEAT`, `receipt`, or `export`, and immediately separate:

- blocking discrepancies
- non-blocking differences
- next required actions

`compare explain` should answer why a discrepancy exists using existing
`submission diff` and formula discrepancy semantics rather than inventing a
second explanation model.

`compare fix` should stage the shortest safe next action for resolvable local
issues and explicitly say when manual correction or re-verification is
required.

`compare verify` should rerun the smallest useful checks for the case and
report whether the discrepancy state changed.

**Recommended sentence patterns**

- `aeat compare show <modelo> --period <period> --against aeat`
- `aeat compare show <modelo> --period <period> --against receipt`
- `aeat compare explain <modelo> --period <period> --against export`
- `aeat compare fix <modelo> --period <period> --against aeat`
- `aeat compare verify <modelo> --period <period> --against receipt`

Primary grammar should stay case-first:
`compare <verb> <modelo> --period <period> --against <aeat|receipt|export>`.
Reserve explicit `--left/--right` artifact grammar for advanced leaves only.

### audit

**Purpose**

Kent needs one exportable evidence case for a filing, not a scavenger hunt
across workflow state, run traces, submission artifacts, references, and
formula checks. `audit` should answer what evidence bundle exists and whether
it is complete, blocked, or export-ready.

**Preferred family shape**

- `audit show`
- `audit verify`
- `audit export`
- `audit replay`

Optional inspection leaves only if needed:

- `audit manifest`
- `audit references`

Current shipped truth remains `aeat formulas audit`; that surface should be
treated as one audit input, not the audit family itself.

**Wireframe intent**

`audit show` should gather the filing evidence bundle into one case view:
filing identity, latest run state, submitted artifact presence, verify status,
discrepancy status, reference coverage, and checksum/replay availability.

`audit verify` should refresh the evidence bundle and mark which required
inputs are present, stale, missing, or inconsistent.

`audit export` should emit one portable bundle with a stable manifest and
obvious provenance boundaries.

`audit replay` should reopen the evidence path for the same filing case using
stored trace and artifact references, not force the operator to rediscover
entrypoints.

**Recommended sentence patterns**

- `aeat audit show <modelo> --period <period>`
- `aeat audit verify <modelo> --period <period>`
- `aeat audit export <modelo> --period <period>`
- `aeat audit replay <modelo> --period <period>`
- `aeat audit show --case <id>`

First contact should stay filing-addressed:
`audit <verb> <modelo> --period <period>`. `--case <id>` should be secondary
after a case already exists.

### tx

**Purpose**

Kent needs throughput on a large transaction backlog without losing review
control, grouping, resumability, or rule learning. `tx` should be the
transaction-throughput family, not a second cross-domain queue.

**Preferred family shape**

- `tx import` or `tx build`
- `tx auto`
- `tx review`
- `tx resume`
- `tx show`

Keep cross-domain unresolved work under `review`, not under `tx`. Current
shipped truth remains `aeat financial txs`; either `tx` becomes the promoted
Kent-facing tree or it stays a thin alias, but both cannot diverge as separate
public languages.

**Wireframe intent**

`tx import` or `tx build` should prepare the working set and describe what is
now eligible for automation or review.

`tx auto` should run batch classification safely, report confidence and
unresolved residue, and preserve review checkpoints.

`tx review` should optimize grouped decisions by merchant, pattern, or other
learned structure while keeping single-item escape hatches.

`tx resume` should reopen the last useful grouped work state without re-scanning
the whole backlog.

`tx show` should stay narrow: one transaction, one classification history, one
current decision context.

**Recommended sentence patterns**

- `aeat tx auto --all`
- `aeat tx review --group-by merchant`
- `aeat tx review --group-by pattern`
- `aeat tx resume`
- `aeat tx show <transaction_id>`
- `aeat tx import <source>`
- `aeat tx build --period <period>`

Primary grammar should distinguish batch throughput from single-row inspection:
`tx <verb>` for batch work, `tx show <transaction_id>` for one row.

### canonical-object-and-sentence-grammar

**Recommended canonical object model**

- `compare`: `ComparisonCase`
  - key: `(modelo, period, profile_tax_id)`
  - sides: implied current-local plus typed baseline
  - nested: `DiscrepancyItem`
  - note: unify casilla, field, and structural deltas; reuse `submission diff`
    and formula discrepancy semantics rather than creating another raw diff
    shape

- `audit`: `AuditCase`
  - primary key: `case_id`
  - secondary address: `(modelo, period, profile_tax_id)`
  - aggregates: `SubmittedFiling`, `RunTrace`, verify/diff results, formula
    ledgers, references, checksums, replay links

- `tx`: keep storage truth as `Transaction` plus `ClassificationHistoryEntry`
  - project into `TxReviewSession` and `TransactionWorkItem` for throughput
  - reuse `TransactionReviewItem` rather than creating a second review queue
    type

**Recommended sentence grammar**

- `compare`: `compare <verb> <modelo> --period <period> --against <aeat|receipt|export>`
- `audit`: `audit <verb> <modelo> --period <period>`
- `tx`: `tx <verb>` for grouped or bulk work; `tx show <transaction_id>` for
  row inspection

This grammar keeps first contact on the Kent task rather than the storage
artifact, then allows deeper leaves only when the case view is insufficient.

### help-text-rules

- `compare` help should lead with `what changed for this filing`, then
  `what to do next`
- `compare` text should name `local`, `AEAT`, `receipt`, and `export`
  explicitly
- `audit` help should lead with `what evidence bundle exists for this filing`,
  then whether it is complete, blocked, or export-ready
- `audit` should avoid first-contact nouns such as `observability` or
  `normatives`
- `tx` help should lead with `how to clear transactions faster`, then identify
  whether the command is bulk automation, grouped review, or single-record
  inspection
- all three should stay ASCII-safe, terminal-safe, and explicit about support
  gaps
- all three should distinguish current shipped primitives from promoted
  Kent-facing case surfaces where support is partial

### collisions-and-naming-risks

- `compare` vs `submission diff`
  - `compare` should be the case-first UX
  - `submission diff` should remain the low-level primitive

- `audit` vs `formulas audit`
  - formula reverse-evaluation is one audit input, not the whole audit family

- `tx` vs `financial txs`
  - either promote `tx` as the Kent-facing tree or keep it as a thin alias
  - shipping both as separate public languages will fragment help, docs, and
    user memory

- `tx` vs `review`
  - `tx` should own transaction throughput
  - `review` should remain the cross-domain queue

- `compare` vs `audit`
  - `compare` analyzes one discrepancy case
  - `audit` packages evidence around that case

- `tx` naming risk
  - if Kent does not read `tx` naturally, keep `transactions` prominent in
    help, examples, and alias text even if `tx` remains the short command

### decision-prompts-for-next-wireframe-pass

- decide whether `compare` ships as a new public tree immediately or first as a
  Kent alias over `submission diff`
- decide whether `audit` owns evidence export end-to-end or initially wraps
  existing formula and trace surfaces with partial completeness markers
- decide whether `tx import` or `tx build` is the better first verb for backlog
  preparation
- decide whether `tx` becomes the canonical public language or a promoted alias
  for `financial txs`
- decide the minimum viable `ComparisonCase` and `AuditCase` fields required
  for stable case IDs and resumable help text
- decide whether advanced leaves such as `compare --left/--right` and
  `audit manifest` ship in the first pass or stay hidden until the case
  surfaces settle

## paired-gpt-5-5-decision-pass-overlap-boundaries

This pass used paired GPT-5.5 high-reasoning reviews for each overlap boundary.
Each boundary was reviewed twice with the same prompt and then compared for
convergence before the decision was accepted. The three pairs converged
strongly. Differences were lexical, not architectural.

### decision-status-vs-compare

Pair convergence:

- both reviews agreed that `status` owns reconciled filing-state questions
- both reviews agreed that `compare` owns delta and closure questions after a
  baseline exists
- both reviews agreed on the same core object split: `ObligationCase` vs
  `ComparisonCase`

Decision:

- `status` owns `where do I stand?` questions:
  - due
  - applicable
  - missing
  - filed
  - AEAT-confirmed
  - locally known
  - blocked
  - resumable
- `compare` owns `what changed or differs?` questions:
  - local vs AEAT
  - local vs receipt
  - local vs export
  - why it differs
  - what must be fixed
  - what must be re-verified

Canonical objects:

- `status` renders `ObligationCase`, keyed by `(modelo, period, profile_tax_id)`
- `compare` renders `ComparisonCase`, keyed by the same filing address but with
  explicit typed sides and nested `DiscrepancyItem`s

Command ownership:

- `status`:
  - `status show`
  - `status today`
  - `status resume`
  - `status history`
- `compare`:
  - `compare show`
  - `compare explain`
  - `compare fix`
  - `compare verify`

Explicit exclusions:

- `status` must not own diffing, discrepancy explanation, artifact-vs-artifact
  comparison, correction staging, or discrepancy re-verification
- `compare` must not own due-date triage, applicability, missed-form
  detection, backlog recovery, notice pressure, auth/session status, or generic
  resume routing

Append-ready decision:

`Decision: status owns reconciled filing state and next action for an ObligationCase; compare owns discrepancy analysis and closure for a ComparisonCase, and neither family may absorb the other's primary question.`

### decision-audit-vs-export

Pair convergence:

- both reviews agreed that `export` is the normal filing finish line
- both reviews agreed that `audit` is evidence-case packaging around that
  finish line
- both reviews agreed that artifact verification belongs to `export`, while
  bundle completeness, provenance, and replay belong to `audit`

Decision:

- `export` owns AEAT upload artifact questions:
  - can I generate the file
  - can I preflight it
  - can I dry-run it
  - can I verify it
  - can I diff it
  - is this `(modelo, ejercicio)` supported
- `audit` owns evidence-package questions:
  - does a complete case bundle exist
  - is the bundle complete or blocked
  - can I replay the case
  - can I export the evidence bundle
  - are references, checksums, and provenance present

Canonical objects:

- `export`: `ExportArtifact` or `ExportJob`, addressed by
  `(modelo, period, profile_tax_id)`
- `audit`: `AuditCase`, primarily addressed by `case_id`, secondarily by
  `(modelo, period, profile_tax_id)`, producing an `EvidenceBundle`

Command ownership:

- `export`:
  - `export modelo`
  - `export preflight`
  - `export dry-run`
  - `export verify`
  - `export diff`
  - `export schemas`
- `audit`:
  - `audit show`
  - `audit verify`
  - `audit export`
  - `audit replay`
  - optional `audit manifest`
  - optional `audit references`

Explicit exclusions:

- `export` must not own evidence bundles, case manifests, replay traces,
  normative/reference packaging, provenance narratives, or case-level
  completeness
- `audit` must not own first-line BOE artifact generation, schema disclosure,
  dry-run upload semantics, or raw artifact diff as the primary UX

Append-ready decision:

`Decision: export owns AEAT upload artifacts and their trust checks; audit owns case-level evidence bundles that package artifacts, provenance, references, checksums, and replay without becoming the normal filing finish line.`

### decision-tx-vs-review

Pair convergence:

- both reviews agreed that `tx` is the transaction-throughput workspace
- both reviews agreed that `review` is the cross-domain judgment gate
- both reviews agreed that transaction items may appear in `review queue`, but
  transaction execution must route back to `tx`

Decision:

- `tx` owns transaction-throughput questions:
  - import or prep transactions
  - bulk classify and categorize
  - grouped correction
  - resume a transaction work session
  - inspect one transaction
- `review` owns cross-domain judgment questions:
  - what still needs Kent's decision before export
  - what is approved, stale, or unapproved
  - where to drill next across transactions, invoices, findings, divergences,
    notices, and drafts

Canonical objects:

- `tx`: `TxReviewSession`, composed of `TransactionWorkItem`s backed by
  `Transaction` plus `ClassificationHistoryEntry`
- `review`: `ReviewItem`, a discriminated cross-domain queue item with kind,
  severity, summary, source record, and drill command

Command ownership:

- `tx`:
  - `tx import`
  - `tx build`
  - `tx auto`
  - `tx review`
  - `tx resume`
  - `tx show <transaction_id>`
- `review`:
  - `review queue`
  - `review show`
  - `review approve`
  - `review unapprove`
  - `review history`

Explicit exclusions:

- `tx` must not own cross-domain queues, draft approval, stale approval
  renewal, filing findings, notices, divergences, or export-readiness gates
- `review` must not own transaction import, catalogue building, bulk LLM
  classification, merchant/pattern grouping, rule promotion, usage-ratio
  editing, or row-by-row transaction correction workflows

Append-ready decision:

`Decision: tx owns transaction throughput sessions; review owns the cross-domain judgment gate, may list transaction review items, and must route transaction execution back to tx rather than duplicating it.`

## three-alternative-cli-shape-synthesis

This pass tested three root-shape alternatives against the persisted research,
roleplay scenarios, and ADR boundary decisions. Four GPT-5.5 high-reasoning
reviewers were used in two paired prompts: two Kent-persona reviewers and two
domain-boundary reviewers. All four converged on the same base decision.

### ranked-alternatives

1. Alternative 1, explicit Kent roots, is the only viable base. It preserves
   first-class `configure`, `auth`, `status`, `data`, `transactions`,
   `review`, `compare`, `export`, `audit`, `revise`, `records`, and
   `advanced` work domains instead of hiding the pipeline under one overloaded
   root.
2. Alternative 2, compact `filing` workspace, is rejected as the primary
   shape. It is superficially tidy, but `filing` becomes a junk drawer for
   `status`, backlog recovery, comparison, revision, history, build, and
   validation. That buries the commands Kent reaches for under pressure.
3. Alternative 3, action-first roots, is rejected. Global verbs such as
   `import`, `classify`, `categorize`, and `edit` scatter domain ownership
   across the root and replace the stronger obligation-truth noun `status`
   with the weaker verb family `check`.

Reviewer convergence:

- All reviewers selected Alternative 1 as the only acceptable base.
- Three reviewers recommended folding `backlog` under `status` rather than
  exposing it as a competing root.
- Both architecture reviewers flagged `transactions review` as a collision
  with the cross-domain `review` root.
- All reviewers rejected `txs` as canonical public language; the hardened
  shape uses `transactions`.
- All reviewers kept `compare`, `export`, and `audit` first-class because
  they answer different questions: what differs, what upload artifact can be
  trusted, and what evidence bundle proves the case.
- Reviewers split on the draft-construction noun. This synthesis selects
  `draft` for the proposal because it names the local object Kent can inspect
  and avoids the live-filing implication of `file`.

### hardened-root-tree-for-approval

```text
aeat
|-- configure
|   |-- profile set/show/use
|   |-- modelos add/remove/list/calendar
|   |-- defaults set/show
|   `-- import/export
|-- auth
|   |-- login/logout/status/whoami/list-providers
|-- status
|   |-- today
|   |-- show <modelo> --period <period>
|   |-- backlog show/import/scaffold/resume --from <period> --to <period> [--modelo <modelo>]
|   |-- resume <modelo> --period <period>
|   `-- history <modelo> --period <period>
|-- data
|   |-- require <modelo> --period <period>
|   |-- import statement|invoice|receipt <path>
|   |-- link invoice|receipt
|   |-- edit invoice|receipt
|   `-- readiness <modelo> --period <period>
|-- transactions
|   |-- build --period <period>
|   |-- automate --period <period> [--with llm]
|   |-- classify <transaction_id>
|   |-- categorize <transaction_id>
|   |-- edit <transaction_id>
|   |-- inspect --group-by merchant|pattern
|   |-- resume
|   `-- show <transaction_id>
|-- draft
|   |-- create <modelo> --period <period>
|   |-- show <modelo> --period <period>
|   |-- validate <modelo> --period <period>
|   `-- list
|-- review
|   |-- queue
|   |-- show <item_id>
|   |-- approve <item_id>
|   |-- unapprove <item_id>
|   `-- history
|-- compare
|   |-- show <modelo> --period <period> --against aeat|receipt|export
|   |-- explain <modelo> --period <period> --against aeat|receipt|export
|   |-- fix <modelo> --period <period> --against aeat|receipt|export
|   `-- verify <modelo> --period <period> --against aeat|receipt|export
|-- export
|   |-- modelo <modelo> --period <period>
|   |-- preflight <modelo> --period <period>
|   |-- dry-run <modelo> --period <period>
|   |-- verify <path>
|   |-- diff <path> --against aeat|receipt
|   `-- schemas
|-- audit
|   |-- show <modelo> --period <period>
|   |-- verify <modelo> --period <period>
|   |-- export <modelo> --period <period>
|   `-- replay <modelo> --period <period>
|-- revise
|   |-- start <modelo> --period <period>
|   |-- import-baseline <path>
|   |-- status <modelo> --period <period>
|   `-- resume <modelo> --period <period>
|-- records
|   |-- filings
|   |-- receipts
|   |-- notifications
|   `-- aeat fetch/show
`-- advanced
```

### root-ownership-rules

- `configure` owns persistent local identity, taxpayer profile data, tracked
  modelos, and default choices. It does not authenticate live sessions, build
  drafts, compare filings, or export artifacts.
- `auth` owns live AEAT session lifecycle: provider listing, login, logout,
  status, and whoami. It does not store durable filing defaults and it never
  introduces live writes.
- `status` owns reconciled obligation truth: due, applicable, missing, local,
  AEAT, blocked, notice-pressured, and resumable. `status backlog` is a
  range projection over the same obligation truth, not a separate model.
- `data` owns source evidence before transaction throughput or draft
  construction: statements, invoices, receipts, links, and readiness
  checklists. Historical filed declarations belong in `records` or
  `revise import-baseline`, not active `data import`.
- `transactions` owns high-throughput transaction work: build, LLM or rule
  automation, manual classification, AEAT categorization, editing, grouped
  inspection, single-row display, and session resume.
- `review` owns the cross-domain judgment gate: pending decisions, approvals,
  unapprovals, stale decisions, and decision history across transactions,
  invoices, drafts, notices, findings, and divergences.
- `draft` owns local declaration draft creation, display, validation, and
  listing. It does not export upload artifacts and does not imply live filing.
- `compare` owns discrepancy work after a baseline exists: local-vs-AEAT,
  local-vs-receipt, local-vs-export, explanation, fix staging, and
  re-verification.
- `export` owns AEAT upload artifacts and their trust checks: schema support,
  preflight, dry-run, generation, verification, and artifact diff. It is the
  normal export-first finish line and does not live-submit.
- `audit` owns evidence bundles: completeness, provenance, references,
  checksums, manifest, and replay. It packages proof; it is not the normal
  filing finish line.
- `revise` owns correction orchestration only. It starts and resumes a
  correction case and imports a baseline, then delegates discrepancy work to
  `compare`, draft work to `draft`, upload artifacts to `export`, and evidence
  bundles to `audit`.
- `records` owns retrospective records: prior filings, receipts,
  notifications, and read-only AEAT-fetched artifacts. It does not decide what
  is due; `status` owns that reconciliation.
- `advanced` is the quarantine for expert, compatibility, reference, schema,
  provider, workflow, and debug surfaces that should not define Kent's first
  contact tree.

### exclusions-and-collision-rules

- Do not use `txs` as public canonical language. `transactions` is the public
  root; `tx` may be considered only as a compatibility alias after the primary
  language is approved.
- Do not use `check` as a substitute for `status`. The codebase has multiple
  checks: workstation readiness, auth session status, review gates, compare
  verification, export verification, and audit bundle verification.
- Do not expose `transactions review` as a leaf. Transaction execution belongs
  under `transactions`; cross-domain judgment belongs under `review`. Use
  `transactions inspect` for grouped transaction work.
- Do not place `compare` under `draft`, `filing`, or `revise`. The discrepancy
  object must remain stable across local, AEAT, receipt, and export baselines.
- Do not place upload artifact generation under `draft`. Draft construction
  and artifact export are separate user questions.
- Do not let `audit` absorb `export`. `export verify` checks the upload
  artifact; `audit verify` checks case evidence completeness and provenance.
- Do not let `records` become another `status`. Records store what happened;
  status reconciles what Kent owes and what remains blocked.
- Do not use `submit` in the default Kent tree. Live submission remains outside
  the default export-first UX.
- Keep Spanish legal and AEAT-native terms at leaf level, aliases, or
  explanatory help text unless the term is required for legal precision.

### representative-command-sentences

- `aeat configure profile set --nie X1234567L --email kent@example.com`
- `aeat auth login --provider certificate`
- `aeat status today`
- `aeat status backlog show --from 2025Q1 --to 2026Q1`
- `aeat data import statement ./bbva_2026q1.csv`
- `aeat transactions automate --period 2026Q1 --with llm`
- `aeat transactions inspect --group-by merchant`
- `aeat draft create 303 --period 2026Q1`
- `aeat review queue --kind transaction`
- `aeat compare explain 303 --period 2026Q1 --against aeat`
- `aeat export preflight 303 --period 2026Q1`
- `aeat audit export 303 --period 2026Q1`

### approval-points

- Approve or reject `draft` as the draft-construction root. This synthesis
  recommends `draft` over `file` because `file` can imply live filing, and over
  `filing` because `filing` repeatedly collapsed into a junk drawer in review.
- Approve `status backlog` rather than a top-level `backlog` root.
- Approve `transactions` as canonical public language and decide whether `tx`
  remains a hidden or compatibility alias.
- Approve `transactions inspect` as the grouped high-volume correction surface
  instead of `transactions review`.
- Approve `revise` as a coordination root only, with delegated work routed to
  `compare`, `draft`, `export`, and `audit`.
- Approve whether `records` is the retrospective evidence noun, replacing the
  older `history` root proposal for first-contact navigation.
