---
tags:
  - '#adr'
  - '#aeat-cli-wireframe'
date: '2026-04-24'
modified: '2026-04-24'
related:
  - "[[2026-04-24-aeat-cli-wireframe-research]]"
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
  - "[[2026-04-21-auth-cli-adr]]"
  - "[[2026-04-18-unified-review-queue-adr]]"
---



# `aeat-cli-wireframe` adr: `kent-first cli language system and root wireframe` | (**status:** `proposed (hardening iteration 1 applied 2026-04-24)`)

## CLI Backend Boundary

The CLI layer MUST remain a thin entrypoint boundary. It MUST NOT implement business logic, schema conversion logic, validation policy, orchestration rules, persistence behavior, provider behavior, or compatibility/deprecation shims. CLI commands MUST delegate to existing implemented centralized standardized tested Pydantic backend, application, and domain services.

CLI logging and error handling MUST use the central facilities: `aeat.core.logging.get_logger(__name__)`, `aeat.core.logging.SecretScrubbingFilter`, `aeat.core.errors.AeatError`, `ERROR_REGISTRY`, `ErrorCode`, `ErrorCategory`, `ErrorEnvelope`, `build_error_envelope`, `render_error_text`, `render_error_json`, `get_error_exit_code`, and `get_registered_error_code`. CLI command execution MUST pass through `aeat.entrypoints.cli._errors.command_error_boundary` and app decoration through `decorate_typer_app`, using `CliValidationBoundaryError`, `CliUnexpectedBoundaryError`, `CliRefusedBoundaryError`, and `write_stderr` only as boundary adapters.

CLI output MUST use the established emitters, including `aeat.entrypoints.cli._common._emit`, `aeat.entrypoints.cli._schemas.emit_json_success`, and `aeat.entrypoints.cli._schemas.emit_json_document`. New CLI behavior MUST be expressed by wiring existing backend/application/domain services and centralized error/output drivers, not by adding parallel CLI-local implementations.

> Note on document shape: sections above "## Hardening pass iteration 1" preserve
> the earlier draft wireframe as a decision trail. Where the earlier draft
> conflicts with the hardening pass, the hardening pass wins. The superseding
> root tree, the hardened Kent boundaries, the evidence-bundle manifest
> contract, the advanced quarantine allocation, the vocabulary retirement
> table, and the pre-approval blockers all live in the hardening pass section
> near the end of this document. Read that section first if you only have time
> for one pass.

## Problem Statement

The current CLI root is too wide and too mixed to serve as Kent's primary
navigation surface. It exposes Kent-facing work beside provider utilities,
reference corpora, admin helpers, debugging tools, and partially shipped
surfaces. The result is a technically rich root that does not read like one
coherent operator language.

The first draft of this ADR had the same failure mode in document form. It
explained naming policy better than it showed an actual CLI construction
contract. That is not sufficient for the workflow this document must support.

This ADR therefore does three jobs at once:

- define the Kent-first root language
- define the parent, child, and grandchild tree boundaries
- define the command-sentence grammar that later `--help` wireframes must obey

It is still not implementation code, and it is still not the final approved
tree. It is the architecture contract for how the future CLI should speak,
cluster work, disclose availability, and separate current truth from planned
capability.

## Considerations

- The product direction is still `produce -> verify -> export`, with live
  submission deferred from the default CLI before `1.0.0`.
- The root must separate three different status questions that are easy to
  blur:
  - what Kent owes next
  - what still needs Kent's decision now
  - what already happened
- `submission` is a real shipped public namespace today. It is not merely a
  compatibility alias, and parts of it are browser-backed and live-adjacent.
- `workflow` is also a real shipped public namespace today, but its public
  presence does not mean it should remain the canonical Kent-facing taxonomy.
- `status` is a public promise with hidden-only child commands. That is an
  architectural failure even if backend code exists.
- `inbox` is already a visible live-read surface, while other live-read status
  surfaces are still hidden or partially implemented. A future history tree
  cannot pretend that all live-read surfaces have the same maturity.
- Draft, export, and verify support are not equivalent across modelos. `130`
  and `303` have shipped export and verify support for `2024` and `2025`.
  `390` remains draft-capable but export-pending.
- `filing import` and `filing complementaria` already prove that Kent's
  correction journey exists and needs a home in the wireframe, even if the
  final noun is not approved yet.
- Help copy must stay ASCII-safe and terminal-safe. The architecture cannot
  depend on Unicode symbols or typographic flair for meaning.

## Constraints

- This ADR must stay Kent-first. Root nodes answer Kent questions before they
  expose subsystem inventory.
- This ADR must preserve the export-first and no-default-live-submit mandates.
- This ADR must not advertise empty, hidden-only, dependency-blocked, or
  developer-shaped surfaces as if they are Kent-complete.
- This ADR must show representative command sentences. It is not enough to name
  roots without showing how Kent would traverse them.
- Each public root node must state:
  - why Kent uses it
  - why it deserves its own tree
  - why it is not nested under another root
- The wireframe must distinguish local evidence and live AEAT reads.
- The wireframe must reserve a truthful home for revise and amend flows.
- Advanced and admin tooling must remain reachable without dominating the root.
- Shared language must stay stable across roadmap milestones even as leaf
  commands evolve.
- This ADR must leave explicit approval points where user sign-off is still
  required before implementation hardens the tree.

## Implementation

### Root-language contract

The root is a decision menu, not an inventory dump. A root node is allowed only
if it satisfies all of these rules:

- It answers a distinct Kent question.
- It owns a recurring operator task family.
- It can be explained in plain language without repo structure.
- It can remain truthful about current availability.
- It does not duplicate another root node's primary job.

The new rule is more precise than the first draft:

- Root nodes are stable operator domains, not raw subsystems.
- A root may be a domain noun or a human-readable action family if the meaning
  is stable and the subtree is semantically coherent.
- Leaf commands carry the imperatives.
- The command sentence should read like prose. Two shapes are allowed:
  - `aeat <root> <verb> <object>`
  - `aeat <root> <resource> <verb>`
- Each root must pick one primary ordering and stay internally consistent.

Representative sentence shapes:

- `aeat configure profile set --name ... --nie ...`
- `aeat auth login --provider certificate`
- `aeat data import statement C:/path/to.pdf`
- `aeat data classify transactions --period 2025Q1`
- `aeat file build 303 --period 2025Q1`
- `aeat export modelo 303 2025Q1`
- `aeat review approve draft 303/2025Q1`
- `aeat revise start 303 2025Q1`

### Kent path boundaries

The wireframe must preserve this operator path boundary contract:

| Step | Kent question | Entry condition | Exit artifact |
| --- | --- | --- | --- |
| `configure` | Who am I and what defaults does this workspace use | None | Active local taxpayer/profile defaults |
| `auth` | Can I authenticate to AEAT right now | Local config exists | Live session or explicit auth failure |
| `obligations` | What do I owe next | Identity and tax profile are known | Target modelos and periods |
| `data` | Do I have usable financial evidence for this period | Target period is known | Prepared transactions, invoices, receipts, local edits, and either filing-ready inputs or an explicit not-ready boundary |
| `file` | Can I build a filing draft for this modelo and period | Filing-ready inputs or imported local draft inputs exist | Draft filing state |
| `review` | What still needs my judgment before export | Drafts or data findings exist | Explicit approvals or unresolved queue |
| `export` | Can I generate and verify the upload artifact | Approved draft exists for a supported modelo and year | Exported artifact plus verification result |
| `history` | What already happened | Local records exist, and live reads may or may not be available | Filing/evidence history view |
| `revise` | How do I correct an already filed period | Prior filing or imported declaration exists | Amendment or correction draft |

Stop conditions are explicit:

- `configure` stops if Kent identity is incomplete.
- `auth` stops if live access is unavailable or intentionally not required.
- `data` stops if evidence is insufficient.
- `file` stops if draft support is missing for the target modelo or year.
- `review` stops if unresolved findings remain.
- `export` stops if schema support is missing or verification fails.
- `history` stops at the truthful boundary between local evidence and live AEAT
  reads.
- `revise` stops if the product cannot yet support the required correction path.

### Proposed root tree

The working root tree is:

```text
aeat
|-- configure    [public target]
|-- auth         [public target]
|-- obligations  [public target]
|-- data         [public target]
|-- file         [public target]
|-- review       [public target]
|-- export       [public target]
|-- history      [conditional target]
|-- revise       [reserved target]
`-- advanced     [public target]
```

This is a working wireframe, not final approval. The semantics below are the
important part.

| Root node | Kent POV | Why it needs its own tree | Why it is not nested elsewhere | Representative command sentences | Availability rule |
| --- | --- | --- | --- | --- | --- |
| `configure` | Kent uses this to declare who he is locally: taxpayer identity, contact details, residence, tracked modelos, and local defaults. | These settings are reused by every later phase and persist beyond one session. | It is not part of `auth` because login/logout are recurring live operations, not persistent workspace definition. It is not part of `data` or `file` because it exists before either. | `aeat configure profile set --name Kent --nie X123...`; `aeat configure modelos add 303`; `aeat configure auth set --default certificate` | Public when the CLI can truthfully manage local identity and defaults, even if later phases remain partial |
| `auth` | Kent uses this to start, inspect, or end a live AEAT session. | Live session lifecycle is a recurring operational concern with its own failure modes and help language. | It is not nested under `configure` because `login`, `logout`, `status`, and `whoami` are not one-time setup actions. | `aeat auth login`; `aeat auth status`; `aeat auth whoami` | Public now |
| `obligations` | Kent uses this to answer what he owes, when he owes it, and which modelos apply. | Forward-looking filing awareness is its own mental model. | It is not `history` because it looks ahead, not back. It is not `review` because it is not about unresolved local decisions. | `aeat obligations show --year 2025`; `aeat obligations calendar 2025`; `aeat obligations modelos --for active-profile` | Public when deadlines and applicability are truthful for the supported profile inputs |
| `data` | Kent uses this to import, classify, categorize, link, and manually edit financial evidence. | This is the longest operational phase and must stay visible as its own work surface. | It is not nested under `file` because Kent spends substantial time preparing data before draft construction. | `aeat data import statement C:/path/to.pdf`; `aeat data classify transactions --with llm`; `aeat data edit transaction tx_123` | Public now, with explicit caveats where the current path is still partial or multi-step |
| `file` | Kent uses this to build, inspect, and validate filing drafts for a target modelo and period. | Draft construction is distinct from data prep, review approval, artifact export, and correction of already filed periods. | It is not `export` because draft construction is upstream of the finish line. It is not `revise` because first-time draft work is not the same operator intent as correcting a prior filing. | `aeat file build 303 --period 2025Q1`; `aeat file show 303 2025Q1`; `aeat file validate 303 2025Q1` | Public when draft operations are truthful, including current file-driven inputs and per-modelo limits |
| `review` | Kent uses this to see what still needs judgment and to approve or revoke decisions. | Review spans both data and filing. It is a cross-cutting human gate, not a leaf helper. | It is not nested under `data` or `file` because it covers both. | `aeat review queue`; `aeat review show draft 303/2025Q1`; `aeat review approve draft 303/2025Q1` | Public now |
| `export` | Kent uses this to preflight, dry-run, export, diff, and verify the artifact he will upload manually. | Before `1.0.0`, this is the default finish line of the product. | It is not nested under `file` because artifact creation and artifact trust are separate user questions. | `aeat export modelo 303 2025Q1`; `aeat export verify 303 2025Q1`; `aeat export schemas` | Public now, but help must disclose exact `(modelo, ejercicio)` support |
| `history` | Kent uses this to inspect what already happened: local filing records, exported artifacts, receipts, and later live AEAT reads. | Backward-looking evidence is a distinct mental model from obligations and pending review. | It is not `obligations` because it is retrospective. It is not `review` because history is not a queue of pending decisions. `review history` remains decision history only; root `history` is filing and evidence history. | `aeat history filings --year 2025`; `aeat history receipts show --modelo 303`; `aeat history aeat fetch filings` | Public only when each child command truthfully discloses whether it is local-only or live AEAT-backed |
| `revise` | Kent uses this to correct something that was already filed. | Revising a past period starts from an existing filing record, not from a clean current-period draft. | It is not just another `file` action because the operator intent is correction of prior state, not first-time preparation. `revise` owns import of previously filed declarations, justificantes, and later amendment mechanics. | `aeat revise start 303 2025Q1`; `aeat revise import justificante C:/receipt.pdf`; `aeat revise export 303 2025Q1` | Reserved root: public only when correction paths are coherent and truthful |
| `advanced` | Kent usually does not need this. Contributors and expert operators use it for provider wiring, reference corpora, schemas, portal utilities, debugging, replay, and compatibility aliases. | The product needs an explicit quarantine for real but non-Kent-first tooling. | It is not nested under the Kent path because that would re-pollute the first-contact tree. | `aeat advanced schema list`; `aeat advanced workflow run`; `aeat advanced portals show 303` | Public now, but curated aggressively |

### Initial subtree contract

The tree below is the construction scaffold that later `--help` wireframes must
refine. It is not a promise that every command already ships.

```text
aeat
|-- configure
|   |-- profile
|   |   |-- set
|   |   |-- show
|   |   `-- use
|   |-- auth
|   |   |-- set
|   |   `-- show
|   |-- modelos
|   |   |-- add
|   |   |-- remove
|   |   |-- list
|   |   `-- calendar
|   |-- import
|   `-- export
|-- auth
|   |-- login
|   |-- logout
|   |-- status
|   `-- whoami
|-- obligations
|   |-- show
|   |-- calendar
|   `-- modelos
|-- data
|   |-- import
|   |   |-- statement
|   |   |-- invoice
|   |   |-- receipt
|   |   `-- filing
|   |-- classify
|   |   `-- transactions
|   |-- categorize
|   |   `-- transactions
|   |-- link
|   |   |-- invoice
|   |   `-- receipt
|   |-- edit
|   |   |-- transaction
|   |   |-- invoice
|   |   `-- receipt
|   `-- show
|-- file
|   |-- build
|   |   `-- <modelo>
|   |-- show
|   |   `-- <modelo>
|   |-- validate
|   |   `-- <modelo>
|   `-- list
|-- review
|   |-- queue
|   |-- show
|   |-- approve
|   |-- unapprove
|   `-- history
|-- export
|   |-- modelo
|   |-- preflight
|   |-- dry-run
|   |-- verify
|   |-- diff
|   `-- schemas
|-- history
|   |-- filings
|   |-- receipts
|   |-- notifications
|   `-- aeat
|       |-- fetch
|       `-- show
|-- revise
|   |-- start
|   |-- import
|   |   |-- declaration
|   |   |-- draft
|   |   `-- justificante
|   |-- compare
|   |-- build
|   |-- export
|   `-- verify
`-- advanced
    |-- workflow
    |-- submission
    |-- status
    |-- schema
    |-- portals
    |-- manuals
    `-- providers
```

### Verb-system rules

The CLI language system adopts these verb rules:

- One verb maps to one operator intent.
- `approve`, `export`, and `verify` remain explicit verbs.
- `doctor`, `preflight`, `review`, `verify`, and live-history inspection
  remain distinct concepts.
- `build` is permitted only when the object is unambiguous inside its cluster.
- `import` is the canonical verb for bringing external records into AEAT local
  state.
- `classify` is the canonical verb for business and personal assignment.
- `categorize` is the canonical verb for AEAT tax-category assignment.
- `edit` is the canonical verb for manual correction.
- `show` and `list` remain utility leaves, not stage names.
- `workflow` and `run` are not canonical Kent verbs even if they survive as
  advanced aliases.

### Noun and jargon exclusions

The Kent-first root excludes or demotes these noun classes:

- Provider and infrastructure nouns such as `cloud`, `drive`, `docs`,
  `sheets`, `oauth-client`, `browser`, and `sync`
- Internal-engineering nouns such as `schema`, `catalogue`, `run`, and raw
  transport or storage terms
- Bare AEAT internal nouns such as `expedientes`, `devoluciones`,
  `datos-fiscales`, and `borrador` without plain-language framing
- Raw filing-internal nouns such as `casilla`, `complementaria`, and
  `rectificativa` as first-contact taxonomy
- Unqualified `profile` as a root-language noun, because the codebase already
  overloads that term for browser profile, taxpayer profile, filing runtime
  profile, and financial usage-ratio profile

Spanish legal or AEAT-native vocabulary is still valid at the leaf level, in
help text, aliases, and model-specific explanations where precision matters.

### Availability and truthfulness rules

Public wireframe language must disclose actual maturity:

- The strongest current shipped roots that back this architecture are `auth`,
  `review`, `financial`, `filing`, `submission`, and `inbox`.
- The new public names `configure`, `data`, `file`, `export`, and `history`
  are architectural targets, not a claim that those exact root namespaces are
  already public on `main`.
- The future `file` root must say when the backed draft path is still
  file-driven or model-specific instead of wizard-driven.
- `history` is conditional at the child level, not uniformly public as one
  solved live-read cluster.
- `revise` is a reserved root until its correction journey is coherent.
- Help must disclose support by `modelo`, `ejercicio`, and stage.

Required example disclosures:

- `130` and `303` support export and verify for `2024` and `2025`
- `390` may be draft-capable while export remains pending
- unsupported paths must say `not yet supported for this modelo` instead of
  failing generically

### Treatment of existing namespaces

The new tree is architectural. Existing public namespaces do not disappear just
because the new language is cleaner. They move under these rules:

- `workflow`
  - not canonical Kent root language
  - may survive under `advanced`
  - any live-adjacent flags remain quarantined outside the default Kent path
- `submission`
  - current shipped namespace remains public during migration
  - maps conceptually into the `export` family
  - current browser-backed `preflight` and `dry-run` behavior must be described
    honestly until any rename happens
- `status`
  - remains non-canonical while it exposes no visible public child commands
  - future live AEAT reads belong under the `history` contract only when each
    child command is visible and truthful
- `setup`
  - likely migrates into `configure` plus `auth`
  - the exact alias story remains an approval point
- `inbox`
  - remains real current functionality
  - conceptually belongs to the `history` and `review` boundary, depending on
    whether the command is about received notices or pending human action
- `review history`
  - remains decision history only
  - must not become a synonym for filing history or receipt history

### Advanced namespace strategy

`advanced` is a quarantine boundary, not a dumping ground. It must be curated
into internal buckets:

- provider setup and wiring
- reference corpora and manuals
- schema and portal tooling
- debug, replay, and workflow shortcuts
- compatibility aliases for renamed namespaces

If a surface cannot justify placement in one of those buckets, it does not
belong in `advanced` either.

### Default live-submit posture before `1.0.0`

Before `1.0.0`, the default CLI posture remains export-first and non-submitting.

The wireframe rules are:

- No Kent-first root node is named `submit`.
- No public default help path in the target Kent tree advertises live
  submission.
- Any live-submit capability remains outside the default Kent tree, behind an
  explicit opt-in namespace and the existing safety gates.
- This quarantine applies to every default Kent-facing path, not just the root
  nouns and not just `submission`.
- Current `main` still exposes live-adjacent wording under non-canonical
  surfaces such as `workflow` and amendment submit flows. The target tree must
  not repeat that exposure.
- `export` is the default finish line. The human uploads the artifact through
  AEAT's portal.
- Verification remains part of the default path because the product promise is
  not just `generate a file`, but `generate a file Kent can trust`.

### Approval points requiring user sign-off

The following decisions are intentionally preserved as approval points before
implementation:

- Approve `configure` as the persistent local identity/defaults root
- Approve whether `auth` stays a first-class root or becomes `configure auth`
- Approve `obligations` versus retaining `deadlines` as the public awareness
  noun
- Approve `file` versus `filing` as the draft-construction root noun
- Approve `export` as the public finish-line family, with current `submission`
  retained during migration
- Approve `history` versus a competing noun such as `records` for the
  backward-looking evidence tree
- Approve `revise` as a reserved root instead of a `file` substage
- Approve whether `workflow` remains hidden or sits under `advanced`
- Approve the initial public width and ordering of the root tree
- Approve the representative subtree contract before `--help` wireframes are
  drafted

## Rationale

This architecture chooses Kent's mental model over subsystem archaeology. The
current root teaches the repository structure more clearly than it teaches the
user journey. The revised wireframe corrects that by doing three things the
first draft did not do well enough:

- it defines a stable root language
- it gives every root a Kent POV and a boundary
- it shows representative command sentences and tree structure

The choice to center `configure`, `auth`, `data`, `file`, `review`, and
`export` reflects the strongest truths already present in the repo:

- Kent's operator path is not the same as the package layout
- review and approval are first-class product stages
- live submission is not default behavior
- current export truth is stronger than current live-submit truth
- current live-read truth is uneven and must not be flattened into one vague
  `status` bucket
- correction flows already exist and therefore need a reserved home

The architecture also creates a stable language boundary for later work. New
commands can appear inside the approved trees without re-litigating the root
every time. Expert tooling can grow behind `advanced` without breaking Kent's
first screen. The later `--help` wireframes can now be judged against a real
construction contract instead of against abstract naming principles alone.

## Consequences

Positive consequences:

- The ADR is now a usable construction artifact rather than a naming memo.
- The root becomes narrower, more legible, and aligned with Kent's actual
  operator questions.
- Kent-facing help becomes more honest because local evidence, live reads,
  review state, and export support are separated explicitly.
- Export-first posture becomes clearer because `export` and `verify` remain
  explicit public concepts.
- Review, approval, and staleness retain first-class status instead of being
  buried under broader filing language.
- Revise and amendment work now has a reserved architectural home.
- Advanced tooling remains available without distorting the main UX.

Negative consequences:

- The project will need compatibility handling for renamed or demoted namespaces
  such as `submission`, `status`, `setup`, and `workflow`.
- Some contributors will lose the convenience of seeing every subsystem at the
  root.
- Several root nouns remain open for user taste approval.
- `advanced` must be curated carefully or it will become a new dumping ground.

Open risks:

- `auth` may still prove too important to nest under `configure`, or too
  narrow to justify a permanent root, depending on later `--help` wireframes.
- `history` may still be the wrong noun if it collides too hard with existing
  review-history language or with the live/local evidence split.
- `file` may still lose to `filing` if prose testing shows that the shorter
  noun feels ambiguous.
- If compatibility aliases remain forever, the language system may drift back
  into dual-taxonomy confusion.
- If per-modelo and per-year capability disclosure is weak, a cleaner
  wireframe could still mislead Kent about what `390` can do today.
- If live-adjacent paths remain visible in default Kent-facing flows, they can
  undermine the export-first posture even after the root is cleaned up.

## Hardening pass iteration 1 (2026-04-24)

This hardening pass is a continuous-audit loop iteration. It supersedes the
earlier draft tree. It is grounded in four parallel discovery subagent reports
run on 2026-04-24: current CLI structural audit (coverage, duplication,
shadowing, advanced-quarantine candidates, unreclaimed surfaces), internal
vocabulary leakage scan across CLI help text and coverage docs, evidence
lineage code discovery across checksums, provenance, run traces, replay,
formula ledgers, reference attachments, persisted artifacts, diff/verify
outputs, decision history, and local-vs-AEAT baseline. The Kent roleplay on
the four weakest areas was performed by the primary contributor.

Where this section conflicts with earlier ADR content, this section wins.

### Superseding root tree

The Kent-first root is hardened to thirteen roots. This tree reflects the
paired-GPT-5.5 convergence decisions recorded in the linked roleplay audit on
`status` vs `compare`, `audit` vs `export`, and `transactions` vs `review`, and
adds the hardening rules derived from the four-area Kent roleplay.

```text
aeat
|-- configure    [public target]
|-- auth         [public target]
|-- status       [public target]
|-- data         [public target]
|-- transactions [public target]
|-- draft        [public target]
|-- review       [public target]
|-- compare      [public target]
|-- export       [public target]
|-- audit        [public target]
|-- revise       [reserved target]
|-- records      [public target]
`-- advanced     [public target]
```

Deltas against the earlier draft tree:

- `obligations` is folded into `status`. Forward-looking filing awareness is a
  projection of reconciled obligation truth, not a separate root.
- `file` is replaced by `draft`. `file` collided with live-filing implication.
  `draft` names the local object Kent can inspect before any upload.
- `history` is replaced by `records`. `records` is a retrospective inventory
  noun; it does not reconcile what is owed.
- `transactions` becomes first class. Transaction-throughput work is the
  largest Kent time sink and must not be buried under `financial txs`.
- `compare` becomes first class. Discrepancy-case work is distinct from raw
  artifact diff and from obligation reconciliation.
- `audit` becomes first class. Case-level evidence packaging is distinct from
  the `formulas audit` engineering leaf and from artifact verification.

### Hardened Kent path boundaries

| Step | Kent question | Entry condition | Exit artefact |
| --- | --- | --- | --- |
| `configure` | Who am I and what defaults does this workspace use | None | Active local taxpayer/profile defaults |
| `auth` | Can I authenticate to AEAT right now | Local config exists | Live session or explicit auth failure |
| `status` | What do I owe, where do I stand, what is blocked, what should I resume | Identity known | `ObligationCase` rows across `today`, `show`, `backlog`, `resume`, `history` projections |
| `data` | Do I have the evidence objects (statements, invoices, receipts, attachments) for this period | Target period known | Imported evidence files, explicit readiness verdict by evidence class |
| `transactions` | Can I classify, categorize, link, and edit the derived transaction rows | Evidence imported | Classified/categorized transactions, grouped inspection, resumable session |
| `draft` | Can I build a filing draft for this `(modelo, period)` | Filing-ready transactions and evidence exist | `FilingDraft` record |
| `review` | What still needs judgment before export | Drafts or findings exist | Approvals, unapprovals, stale flags, cross-domain decisions |
| `compare` | What differs between local, AEAT, receipt, or export | Baseline or target artefact exists | `ComparisonCase` with `DiscrepancyItem` rows, explanation, fix staging, reverify |
| `export` | Can I generate and trust the upload artefact | Approved draft exists for a supported `(modelo, ejercicio)` | Exported fichero plus verification verdict |
| `audit` | Do I have a complete, provenance-tagged evidence bundle for this case | Filing evidence exists | Assembled bundle, verify result, portable archive, deterministic replay |
| `revise` | How do I correct an already filed period | Prior filing baseline exists | Amendment draft, amendment kind, amendment record |
| `records` | What already happened, what do I have on file | Local records exist | Retrospective inventory by class: filings, receipts, notifications, amendments, AEAT-fetched artefacts |
| `advanced` | (non-Kent) expert, provider, reference, diagnostic, alias tooling | None | Expert tooling reachable without polluting first contact |

Stop conditions per root:

- `status` stops at the truthful boundary between local, AEAT, and blocked
  reconciliation rows.
- `data` stops if readiness cannot be honestly computed (missing statements,
  unlinked receipts, unassigned opening/closing balances).
- `transactions` stops if the catalogue is empty or if the automation path is
  non-resumable.
- `draft` stops if `(modelo, ejercicio)` builder support is missing.
- `review` stops with an unresolved-findings count.
- `compare` stops if the baseline artefact does not exist.
- `export` stops if schema support is missing or verification fails.
- `audit` stops with a bundle-completeness verdict: complete, degraded, or
  blocked.
- `revise` stops if the baseline is missing or if the `--kind` is unsupported
  for the modelo.
- `records` stops at an inventory row; it never re-verifies.

### Data vs transactions boundary (hardening)

Discovery facts grounding this hardening: the current CLI exposes transaction
work under `financial txs` and invoice work under `financial invoices`; a
receipt parser lives under a separate `justificante` root; `filing import`
exposes raw Spanish options (`--from-borrador`, `--from-declaracion`,
`--from-justificante`) in the default path; no unified `data link`,
`data edit`, or `data readiness` surface exists today.

Kent roleplay (PDF bank statement scenario): Kent downloads a BBVA 2025Q1
statement. He runs `aeat data import statement ./bbva-2025q1.pdf`. The CLI
parses and emits derived transaction rows plus a catalogue identifier. The
command reports boundaries explicitly: imported as evidence, derived N rows,
next step `transactions automate --period 2025Q1`. Kent then runs
`aeat transactions automate --period 2025Q1 --with llm`. He finds a wrong row
and runs `aeat transactions edit tx_123`. He wants to attach a takeaway
receipt to a specific transaction and runs
`aeat transactions link receipt tx_123 ./ticket.pdf`. When he wants to attach
a supporting email PDF to an invoice rather than a transaction, he runs
`aeat data link attachment invoice_456 ./email.pdf`.

Hardening rules:

- `data` owns evidence artefacts at the file level. Verbs: `import`, `edit`,
  `link`, `show`, `readiness`. Objects: `statement`, `invoice`, `receipt`,
  `attachment`.
- `transactions` owns derived transaction rows. Verbs: `build`, `automate`,
  `classify`, `categorize`, `edit`, `inspect`, `link`, `resume`, `show`.
- Link semantics live where the owning object lives. Linking a receipt to a
  transaction is `transactions link receipt`. Linking a sub-evidence file to a
  parent evidence file is `data link attachment`.
- `data readiness <modelo> --period <period>` is mandatory before
  `draft create`. It returns per-evidence-class status (present, missing,
  ambiguous, unlinked) with per-modelo requirements.
- Per-period readiness is always keyed by `(modelo, period, profile_tax_id)`
  and matches the underlying `ObligationCase` addressing already used by
  `status`.
- `financial txs`, `financial invoices`, and `justificante parse` are retired
  from default. They survive under `advanced aliases` for one migration
  milestone, then are removed.
- `filing import --from-justificante` and its `--from-borrador` /
  `--from-declaracion` siblings are retired from the default tree. Baseline
  import migrates to `revise import-baseline <path>` (auto-detects the PDF
  kind). Advanced paths may retain typed variants.

### Revise semantics (hardening)

Discovery facts: `FilingAmendment` exists in
`src/aeat/application/filing/_complementaria.py` with an `amendment_kind` field, persisted
as JSON under `aeat_submissions_dir/amendments/`. `SubmittedFiling` carries
`profile_tax_id` and acts as the baseline. Import from a justificante PDF is
implemented; live AEAT baseline import is not. There is no modelo-level
amendment-kind policy enforcement today.

Kent roleplay scenarios and their canonical paths:

- Owes more tax after a forgotten invoice (modelo 303, 2024Q2, complementaria):
  `aeat revise import-baseline ./303-2024Q2-justificante.pdf`;
  `aeat revise start 303 --period 2024Q2 --kind complementaria`;
  `aeat transactions edit tx_xxx`; `aeat compare show 303 --period 2024Q2 --against receipt`;
  `aeat draft validate 303 --period 2024Q2`; `aeat review approve draft 303/2024Q2`;
  `aeat export modelo 303 --period 2024Q2 --kind complementaria`; manual portal upload.
- Correction that reduces liability (rectificativa). Same shape, different
  `--kind`. AEAT rules differ. The CLI must enforce per-modelo `--kind`
  support.
- AEAT rejection of prior filing. Not a revise. Belongs under
  `compare explain --against aeat` then redraft from scratch under `draft`.
- Never-submitted period. Not a revise. Belongs under
  `status backlog scaffold` with an extemporánea note.

Hardening rules:

- `revise start <modelo> --period <period> --kind <kind>`: `--kind` is
  required. No default. Valid values: `complementaria`, `rectificativa`,
  `sustitutiva`. Unrecognised `--kind` fails the command.
- Baseline must exist before `revise start`. If no baseline is present, the
  command fails with: `No baseline submission found for (modelo, period). Run
  "aeat revise import-baseline ./<justificante.pdf>" first, or wait for live
  import support.`
- Per-modelo `--kind` support is enforced against a registry table. Kent must
  see a truthful support matrix in `revise start --help`. Unsupported
  combinations fail with: `<kind> revise is not yet supported for modelo
  <modelo>. Currently supported: <supported list>. For unsupported paths,
  upload manually through the AEAT portal.`
- `revise` never submits live. It ends at `export modelo <modelo> --period
  <period> --kind <kind>` producing a fichero that Kent uploads manually.
- Every revise produces a first-class `FilingAmendment` record that appears
  under `records amendments list` and `records amendments show <amendment_id>`.
- `revise` delegates: discrepancy to `compare`, construction to `draft`,
  export to `export`, evidence packaging to `audit`. It never duplicates
  those responsibilities.
- Language hardening: Kent-facing options use plain language. `revise
  import-baseline <path>` auto-detects the PDF kind. Spanish legal nouns
  (`justificante`, `declaración`, `borrador`, `complementaria`,
  `rectificativa`, `sustitutiva`) are retained inside `--help` text and in
  the `--kind` value set, never as option names.
- Rejection-flow and backlog-flow have explicit redirect help when the
  operator reaches for `revise` under the wrong conditions.

### Records vs audit evidence lineage (hardening)

Discovery facts:

- Content-addressed checksums exist for `run_id`, `submission_id`, `draft_id`,
  `review_checksum`. All SHA-256. All persisted.
- `profile_tax_id` is persisted on every stored record **except**
  `WorkflowResult`. That is a provenance gap.
- `ComputationLedger` and `AuditReport` live in memory only. They are not
  persisted. That is the biggest evidence gap.
- `VerificationVerdict` lives in memory only. That is the second-biggest gap.
- `aeat submission diff` and `aeat submission verify` print to console only;
  nothing is persisted.
- The approval record carries `approved_at` and `approved_by` but no
  per-decision reason, no ordered ledger, and no prior/next checksum trail.
- `corpus_sha256` gating exists in `run replay` but is not uniformly carried on
  workflow results or filing drafts.
- There is no live-AEAT baseline import. All baselines originate from a local
  PDF today.

Kent roleplay (inspector scenario): an AEAT inspector asks Kent to prove that
his 303/2024Q1 numbers match records. Kent runs `aeat audit show 303 --period
2024Q1` and sees a table of evidence with tick/cross per artefact. He runs
`aeat audit verify 303 --period 2024Q1`, which rechecks every SHA-256, reruns
the formula ledger from stored inputs, and compares against the filed receipt.
It returns pass/fail per artefact with a reason. He runs `aeat audit export
303 --period 2024Q1 --output ./audit-303-2024q1.zip` and emails the portable
bundle to the inspector. Later, he runs `aeat audit replay 303 --period
2024Q1` to confirm deterministic reproduction of the ledger against today's
code and today's corpus. If replay fails, the command marks the bundle
`replay-degraded` and flags the divergent artefact.

Hardening rules (evidence-lineage guarantees `audit` must uphold):

- The audit bundle contains, at minimum:
  - `filing/draft.json`: final approved `FilingDraft` record.
  - `filing/approval-basis.json`: `FilingApprovalBasis` snapshot at approval
    time.
  - `filing/approval-journal.json` **(NEW)**: ordered decision journal with
    timestamp, actor, action, reason, prior and next review checksum.
  - `export/fichero.boe`: byte-exact exported fichero.
  - `export/fichero.boe.sha256`: SHA-256 digest next to the fichero.
  - `export/verify.json` **(NEW)**: persisted `VerificationVerdict` with
    status, classified discrepancies, narrative, verified-at timestamp.
  - `formulas/ledger.json` **(NEW)**: persisted `ComputationLedger` with
    ruleset_id, entries, operand refs, operand values.
  - `formulas/audit.json` **(NEW)**: persisted `AuditReport` with
    discrepancies classified as extraction, roundoff, structural, or
    computed.
  - `submission/submitted.json`: baseline `SubmittedFiling` with justificante
    CSV and PDF path.
  - `submission/amendments/*.json`: every `FilingAmendment` linked to the
    baseline.
  - `workflow/run.json`: `WorkflowResult` with run_id, timings, step trace,
    and `profile_tax_id` **(NEW FIELD)**.
  - `references/manuals/*.json`: every `ManualRule` cited in
    `findings.references_rules`.
  - `references/normatives/*.json`: every `LegalCitation` linked to a filing
    validation.
  - `corpus/sha256.txt`: corpus_sha256 for manual, normative, and schema
    registry at approval time.
  - `manifest.json`: bundle_version, bundle_id (content-addressed SHA-256
    over all above files), created_at, modelo, period, profile_tax_id,
    builder_version, and a contained-files table with per-file SHA-256.
- Pre-approval persistence work that must land before `audit` ships truthfully:
  - Persist `ComputationLedger` and `AuditReport` under
    `var/audit/{modelo}/{period}/`.
  - Persist `VerificationVerdict` under
    `var/audit/{modelo}/{period}/verify-results/`.
  - Add an `ApprovalLedgerEntry` record type and persist decision history
    under `var/audit/{modelo}/{period}/approval-journal/`.
  - Add `profile_tax_id` to `WorkflowResult` and include `corpus_sha256`.
- Boundary guarantees:
  - `records` is inventory only. It lists and shows. It never re-verifies.
    Example: `records filings list` returns every `FilingDraft`;
    `records receipts show <justificante_csv>` returns the SubmittedFiling
    PDF path. `records amendments list` enumerates persisted amendments.
  - `audit` is the re-verifier and packager. Every `audit verify` rechecks
    SHA-256 over persisted artefacts, reruns the formula ledger from stored
    inputs, and reports per-artefact pass/fail with a reason.
  - `audit replay <modelo> --period <period>` requires stored ruleset and
    stored `corpus_sha256`. If reproduction diverges, the command marks the
    bundle `replay-degraded` and flags divergent artefacts; it does not fail
    silently.
  - `export verify` remains the artefact-trust check. `audit verify` is the
    case-bundle completeness check. They are not duplicates; they live side by
    side.

### Advanced quarantine (hardening)

Discovery facts: more than twenty current CLI roots are non-Kent-first and
route into `advanced` under the hardened tree. `workflow run` and
`workflow next` currently expose `--no-dry-run` and
`--i-understand-this-is-real` in their default non-hidden help. That is a
direct violation of the live-write safety charter. The `run` namespace still
holds `run show`, `run list`, and `run replay`; only `run replay` implements
actual replay semantics.

Advanced internal buckets (closed set; ad-hoc expansion requires ADR update):

- `advanced reference`: schema, modelos, normatives, manuals, casillas,
  categories, vat, portals.
- `advanced providers`: oauth-client, cloud, drive, sheets, docs, browser,
  bootstrap.
- `advanced formulas`: formulas engine inspection (compute with ledger, audit
  rulesets).
- `advanced workflow`: legacy orchestration shortcuts migrating out of
  default `workflow run` and `workflow next` (non-live default only).
- `advanced runs`: `run show`, `run list`, `run replay` as forensic surfaces;
  distinct from `audit replay`.
- `advanced diagnostics`: browser health, llm cache inspect, sync probe.
- `advanced aliases`: compatibility aliases for renamed commands during the
  migration window (sunsets after one milestone).

Admission criteria (all must hold):

- The command is not required for Kent's filing journey.
- It has a concrete non-Kent-first purpose (contributor, ops, debug,
  reference, legacy alias).
- It fits exactly one of the closed buckets above.
- Its help text declares its bucket and its non-Kent-first purpose in the
  first sentence.
- It does not duplicate a Kent-first command's primary job.

Root-level removals and relocations:

- `hello` is removed. Fixture only; no Kent or contributor value.
- `doctor` stays at root. It answers a Kent question: "is my workspace
  healthy?" It is diagnostic, not definitional; it is not nested under
  `configure`.
- `inbox` merges into `records notifications`. Live-fetch behaviour is retained
  inside `records aeat fetch`.
- `deadlines` merges into `status today` and `configure modelos calendar`.
- `justificante` (as a root) merges into `revise import-baseline` (parser
  reused) and `records receipts show` (read-only inspection).

Critical pre-approval blocker (closure required before ADR approval):

`aeat workflow run` and `aeat workflow next` must stop exposing
`--no-dry-run` and `--i-understand-this-is-real` in any default non-hidden
path. Three acceptable closure paths, ordered by preference:

1. Move both commands under `advanced workflow` and strip the live-write flags
   from the default surface.
2. If a live execution path is retained inside `advanced workflow`, route it
   through an explicit `advanced workflow run --live` leaf that requires the
   full four-factor safety gate (`AEAT_ALLOW_LIVE_SUBMIT_OPT_IN=1`,
   `AEAT_LIVE_SUBMIT_ENABLED=1`, a typed opt-in flag whose name matches the
   auth-provider abstraction, and a per-submission interactive prompt). The
   leaf is undiscoverable from the Kent root tree.
3. Excise the live execution branch entirely until the 1.0.0 reintroduction
   work lands alongside the `AuthProvider` abstraction.

### Vocabulary retirement table

| Current surface | Leaked term | Fate under hardened CLI |
| --- | --- | --- |
| `financial txs *` | `txs` | Retire. Surface under `transactions` root. Alias optional for one milestone. |
| `financial invoices *` | `invoices` under `financial` | Retire. Surface under `data` (`data import invoice`, `data edit invoice`, `data link invoice`). |
| `financial profile *` | overloaded `profile` | Move to `configure defaults` or keep as `advanced aliases`. |
| `filing build` | `filing build` | Retire. Replace with `draft create`. |
| `filing show/list/validate` | `filing` | Retire. Replace with `draft show/list/validate`. |
| `filing import --from-justificante` | `--from-justificante` | Retire. Replace with `revise import-baseline <path>` (auto-detect). |
| `filing import --from-declaracion` | `--from-declaracion` | Retire from default. Advanced alias only. |
| `filing import --from-borrador` | `--from-borrador` | Retire from default. Advanced alias only. |
| `filing import --from-aeat` | live import | Reserve for 1.0.0 reintroduction under `revise import-baseline --from-aeat`. |
| `submission preflight/dry-run/export/verify/diff/schemas` | `submission` | Retire. Migrate to `export {preflight,dry-run,modelo,verify,diff,schemas}`. |
| `submission export` | `submission export` | Retire. Replace with `export modelo`. |
| `workflow run` | `--no-dry-run`, `--i-understand-this-is-real` | Excise flags from default; move command under `advanced workflow`. |
| `workflow next` | `--no-dry-run`, `--i-understand-this-is-real` | Excise flags from default; move command under `advanced workflow`. |
| `workflow list` | `workflow` | Move under `advanced workflow list` or `advanced runs list`. |
| `run show/list/replay` | `run` as root namespace | Move under `advanced runs`. `run replay` is forensic; `audit replay` is the Kent-facing evidence replay. |
| `bootstrap` | root-level infrastructure noun | Move under `advanced providers bootstrap`. |
| `casillas` | root-level Spanish jargon | Move under `advanced reference casillas`. |
| `categories` | root-level reference | Move under `advanced reference categories`. |
| `vat` | root-level VAT taxonomy | Move under `advanced reference vat`. |
| `modelos` | root-level reference | Move under `advanced reference modelos` and surface applicable-to/calendar under `configure modelos` for the Kent-facing case. |
| `normatives` | root-level | Move under `advanced reference normatives`. |
| `manual` | root-level | Move under `advanced reference manuals`. |
| `portals` | root-level | Move under `advanced reference portals`. |
| `schema` | root-level | Move under `advanced reference schema`. |
| `formulas` | root-level | Move under `advanced formulas`. |
| `oauth-client` | root-level | Move under `advanced providers oauth-client`. |
| `cloud`, `drive`, `sheets`, `docs` | Google Workspace nouns | Move under `advanced providers`. |
| `browser` | root-level | Move under `advanced diagnostics browser`. |
| `attachments` | root-level infrastructure | Move under `advanced reference attachments` or fold into `data link attachment`. |
| `sync` | root-level | Move under `advanced workflow sync`. |
| `llm` | root-level | Move under `advanced llm`. |
| `inbox` | root-level live-read | Merge into `records notifications`. |
| `justificante` | root-level Spanish noun | Merge into `revise import-baseline` (parser) and `records receipts`. |
| `deadlines` | root-level | Merge into `status today` + `configure modelos calendar`. |
| `hello` | root-level fixture | Delete. |

Terms preserved with explicit framing:

- `AEAT` acronym at any depth.
- Modelo identifiers (`130`, `303`, `390`, `100`, `111`, `115`, etc.).
- `fichero BOE` at leaf help text only, introduced as "exported filing file
  (fichero BOE) that AEAT accepts for upload".
- `complementaria`, `rectificativa`, `sustitutiva` as `revise --kind` values
  and in `--help` prose, never as top-level CLI verbs or option names.

### Hardened initial subtree contract

This subtree supersedes the earlier "Initial subtree contract" block. It is
the construction scaffold future `--help` wireframes must refine. Leaves that
are not yet implemented are explicit so later pipeline work cannot ship a
command before it is truthful.

```text
aeat
|-- configure
|   |-- profile (set|show|use)
|   |-- modelos (add|remove|list|calendar)
|   |-- defaults (set|show)
|   |-- import
|   `-- export
|-- auth
|   |-- login
|   |-- logout
|   |-- status
|   |-- whoami
|   `-- list-providers
|-- status
|   |-- today
|   |-- show <modelo> --period <period>
|   |-- backlog (show|import|scaffold|resume) --from <period> --to <period> [--modelo <modelo>]
|   |-- resume <modelo> --period <period>
|   `-- history <modelo> --period <period>
|-- data
|   |-- import (statement|invoice|receipt)
|   |-- link (invoice|receipt|attachment)
|   |-- edit (invoice|receipt)
|   |-- show
|   `-- readiness <modelo> --period <period>
|-- transactions
|   |-- build --period <period>
|   |-- automate --period <period> [--with llm]
|   |-- classify <transaction_id>
|   |-- categorize <transaction_id>
|   |-- edit <transaction_id>
|   |-- link (receipt|invoice) <transaction_id> <path>
|   |-- inspect --group-by (merchant|pattern)
|   |-- resume
|   `-- show <transaction_id>
|-- draft
|   |-- create <modelo> --period <period>
|   |-- show <modelo> --period <period>
|   |-- validate <modelo> --period <period>
|   `-- list
|-- review
|   |-- queue [--kind <kind>]
|   |-- show <item_id>
|   |-- approve <item_id> [--reason <text>]
|   |-- unapprove <item_id> [--reason <text>]
|   `-- history
|-- compare
|   |-- show <modelo> --period <period> --against (aeat|receipt|export)
|   |-- explain <modelo> --period <period> --against (aeat|receipt|export)
|   |-- fix <modelo> --period <period> --against (aeat|receipt|export)
|   `-- verify <modelo> --period <period> --against (aeat|receipt|export)
|-- export
|   |-- modelo <modelo> --period <period> [--kind <kind>]
|   |-- preflight <modelo> --period <period>
|   |-- dry-run <modelo> --period <period>
|   |-- verify <path>
|   |-- diff <path> --against (aeat|receipt)
|   `-- schemas
|-- audit
|   |-- show <modelo> --period <period>
|   |-- verify <modelo> --period <period>
|   |-- export <modelo> --period <period> --output <path>
|   |-- replay <modelo> --period <period>
|   `-- manifest <modelo> --period <period>
|-- revise
|   |-- start <modelo> --period <period> --kind (complementaria|rectificativa|sustitutiva)
|   |-- import-baseline <path>
|   |-- status <modelo> --period <period>
|   |-- resume <modelo> --period <period>
|   `-- show <modelo> --period <period>
|-- records
|   |-- filings list/show
|   |-- receipts list/show
|   |-- notifications list/show
|   |-- amendments list/show
|   `-- aeat fetch/show
`-- advanced
    |-- reference (schema|modelos|normatives|manuals|casillas|categories|vat|portals|attachments)
    |-- providers (oauth-client|cloud|drive|sheets|docs|browser|bootstrap)
    |-- formulas (compute|audit|rulesets)
    |-- workflow (run|next|list|sync) [non-live default only]
    |-- runs (show|list|replay)
    |-- diagnostics (browser|llm|sync)
    `-- aliases (financial-txs|filing-build|submission-*|...)
```

### Truthfulness and availability rules (updated)

- Roots `configure`, `auth`, `status`, `data`, `transactions`, `draft`,
  `review`, `export`, `records`, and `advanced` are architectural targets.
  Their current Kent-facing public names are not yet on `main` in this exact
  shape; migration is required.
- `compare` and `audit` ship as case-first Kent surfaces only when persistence
  work for `ComputationLedger`, `AuditReport`, `VerificationVerdict`, and the
  decision journal has landed. Until then, both show an explicit
  partial-coverage banner and route to the underlying engineering leaves via
  `advanced formulas` and `advanced runs`.
- `revise` ships as a reserved root with `--kind` required and a per-modelo
  support matrix visible in help. Unsupported paths fail with a plain-language
  explanation and route Kent to the AEAT portal.
- `status backlog` ships before `status today` if triage signal quality is not
  yet ready; `today` is a promoted slice of `status`, not a parallel root.
- Help copy must disclose support by `modelo`, `ejercicio`, stage, and
  revision kind. It must stay ASCII-safe and Windows-terminal-safe.

### Approval points (extended by iteration 1)

All earlier approval points remain open. Iteration 1 adds the following:

- Approve the superseding thirteen-root tree.
- Approve `status` as the reconciliation root with `today`, `show`, `backlog`,
  `resume`, and `history` subcommands.
- Approve `transactions` as the first-class throughput root (not nested
  under `financial`).
- Approve `draft` as the draft-construction root noun (over `file` and
  `filing`).
- Approve `compare` as a first-class discrepancy case root.
- Approve `audit` as a first-class evidence-bundle root distinct from
  `export`.
- Approve `records` as the retrospective inventory root (over `history`).
- Approve the data/transactions boundary rules and the `link` ownership rule.
- Approve the revise `--kind` registry contract and baseline requirement.
- Approve the evidence-bundle manifest contract as the pre-ship gate for
  `audit`.
- Approve the advanced quarantine bucket set and the admission criteria.
- Approve the vocabulary retirement table.
- Approve the pre-approval blocker closure path for
  `workflow run/next` live flags.

### Open risks added by iteration 1

- The live-flag leak in `workflow run` and `workflow next` predates this ADR
  but now serves as a pre-approval blocker. If the leak is not closed before
  approval, the ADR commits the project to a truth it does not yet hold.
- Persistence additions (formula ledger, audit report, verification verdict,
  decision journal, workflow profile_tax_id) are non-trivial migrations. They
  must be scoped before `audit` becomes a public promise, or `audit` ships
  hollow.
- The `records` root consolidates inventory language scattered across `filing
  list`, `workflow list`, `submission list`, `inbox list`, and
  `status expedientes`. The consolidation is mechanical but unavoidable.
- `data readiness` is greenfield. Without it, `draft create` cannot honestly
  prevent Kent from building drafts on incomplete evidence.
- Migration aliases under `advanced aliases` risk persisting forever. They
  carry a one-milestone sunset horizon and must be removed by the next
  release.
- `transactions` promotion exposes the codebase-level debt of
  `financial txs` naming. A full rename wave is needed or the codebase stays
  bilingual, which will drift back into dual-taxonomy confusion.
- The revise per-modelo `--kind` registry is currently implicit in domain
  code. Making it explicit and truthful requires either a registry module or
  a test that enforces coverage parity with AEAT's actual modelo rules.
- `audit replay` deterministic reproduction depends on pinned
  `corpus_sha256`. If corpus updates are not versioned explicitly, replay will
  silently drift.

### Next iteration focus (self-paced loop)

Iteration 2 (Kent roleplay on hardened revise `--kind` matrix and baseline
edge cases): per-modelo `(130, 303, 390)` times `(complementaria,
rectificativa, sustitutiva)` support table with per-cell truth status;
baseline edge cases (local PDF, future live AEAT, AEAT rejected prior
filing, never-submitted period); extemporánea boundary; redirect messages for
wrong-root invocations. Appended as iteration 2 hardening.

Iteration 3 (evidence-bundle manifest schema spec): formal JSON shape of
`manifest.json` and every subsidiary record (`approval-journal.json`,
`verify.json`, `ledger.json`, `audit.json`, `workflow/run.json`); field
names, required/optional, checksum algorithm, bundle_version discipline,
per-file provenance envelope, build-tool version recorded. Appended as
iteration 3 hardening.

Iteration 4 (advanced bucket allocation table and migration-window roleplay):
exact allocation of every current root to a hardened advanced sub-bucket with
a one-line non-Kent justification; day-1 post-migration Kent walkthrough; old
invocation error messages; alias help text. Appended as iteration 4
hardening.

Iteration 5 (pre-approval blocker closure verification): confirm whether the
`workflow run/next` live-flag leak has been closed via a concurrent issue; if
still open, produce a file-level excision plan and an issue skeleton; if
closed, strike the pre-approval blocker from this ADR.

Each iteration appends a new `## Hardening pass iteration N` section to this
document. Earlier iterations are not overwritten; their decision trail is
preserved. The ADR stays `proposed` until all pre-approval blockers are
closed and the user signs off.

## Hardening pass iteration 2 (2026-04-24)

Iteration 2 focus: hardening the `revise` root. Kent roleplay across six
baseline scenarios against the per-modelo amendment-kind support matrix. The
Kent reasoning is primary; discovery support comes from iteration 1's
evidence-lineage code discovery.

### Per-modelo × amendment-kind support registry

Ground truth framing: the CLI cannot ship `revise` without an explicit
registry of which `(modelo, ejercicio, kind)` triples AEAT actually accepts
today. Current code defines an `amendment_kind` enum but does not enforce a
per-modelo truth table. That is a gap.

Kent's three core modelos:

- `130`: IRPF pagos fraccionados autónomos. Quarterly self-liquidation of
  estimated personal income tax.
- `303`: IVA autoliquidación. Quarterly VAT return (or monthly for large
  taxpayers, outside Kent's scope).
- `390`: IVA resumen anual. Annual VAT summary. Informativa (not a
  self-liquidation).

AEAT amendment-kind semantics (Kent's scope):

- `complementaria`: additive declaration used when the corrected figure
  increases the taxpayer's liability relative to the original filing.
  Classical AEAT path available for autoliquidaciones like `130` and `303`.
- `rectificativa`: corrective declaration used when the correction decreases
  liability or asserts a different non-additive result. For `303` the
  modernised "Autoliquidación Rectificativa IVA" path was introduced post-2023
  and lives alongside classic rectificativa requests. For `130` the
  rectificativa path is not a first-class IRPF-fraccionado surface and is
  generally resolved through the annual IRPF procedure.
- `sustitutiva`: fully replaces the prior filing. Used for informativas like
  `390` when an entirely new annual summary must be submitted.

Registry truth table (Kent scope, current AEAT rules; pinned by ejercicio):

| Modelo | `complementaria` | `rectificativa` | `sustitutiva` |
| --- | --- | --- | --- |
| `130` | supported | not a first-class CLI path; route to IRPF annual via redirect message | not applicable |
| `303` | supported | supported (Autoliquidación Rectificativa IVA, post-2023 ejercicios only) | not applicable |
| `390` | not applicable | supported (corrección) | supported (full replacement) |

Pre-approval registry requirements:

- A new module `RevisionSupportRegistry` encodes this truth table. Each entry
  is a frozen Pydantic v2 model: `modelo`, `ejercicio`, `kind`, `supported`,
  `notes_es`, `notes_en`, `notes_hu`.
- `revise start --help` renders the applicable row for the caller's
  `(modelo, ejercicio)` so Kent sees the supported kinds before he types one.
- A machine-checked test verifies registry rows against a curated AEAT policy
  reference per ejercicio. Without the test the registry silently drifts with
  AEAT law changes.
- Registry entries live under `src/aeat/revise/_registry.py` (subpackage-root
  convention already in use for domain registries).

### Baseline edge-case scenarios (Kent roleplay)

Each scenario is narrated as Kent in front of the terminal, with the exact
command shape and the expected CLI response.

Scenario (a): local PDF baseline — implemented today.

- State: Kent has downloaded `303-2024Q2-justificante.pdf` from the AEAT
  portal.
- Commands: `aeat revise import-baseline ./303-2024Q2-justificante.pdf`;
  `aeat revise start 303 --period 2024Q2 --kind complementaria`;
  `aeat transactions edit tx_xxx`; `aeat compare show 303 --period 2024Q2
  --against receipt`; `aeat draft validate 303 --period 2024Q2`;
  `aeat review approve draft 303/2024Q2`;
  `aeat export modelo 303 --period 2024Q2 --kind complementaria`.
- Response: each step confirms state transition; final step emits the
  complementaria fichero for Kent's manual portal upload.

Scenario (b): live AEAT baseline — deferred to 1.0.0.

- State: Kent wants to pull the baseline without a local PDF.
- Command: `aeat revise import-baseline --from-aeat 303 --period 2024Q2`.
- Response: explicit deferral. "Live AEAT baseline import is not yet
  supported. Download the justificante PDF from the AEAT portal and run:
  `aeat revise import-baseline ./justificante.pdf`. Live import is planned
  for `1.0.0` alongside the AuthProvider abstraction."
- Hardening rule: the `--from-aeat` option is allow-listed in the parser
  only when 1.0.0 reintroduction ADR lands; before that the option is
  removed entirely rather than stubbed.

Scenario (c): AEAT rejected the prior filing.

- State: Kent submitted `303/2024Q2` but the AEAT receipt-of-submission
  returned a rejection code. No accepted baseline exists.
- Command: `aeat revise start 303 --period 2024Q2 --kind complementaria`.
- Response: "AEAT rejected your `303/2024Q2` submission on `<date>` with
  reason `<code: reason>`. `revise` applies to accepted baselines only. Run
  `aeat compare explain 303 --period 2024Q2 --against aeat` to inspect the
  rejection, fix the issue, and build a new draft with
  `aeat draft create 303 --period 2024Q2`."
- Hardening rule: `revise start` inspects the baseline's `status` field and
  refuses any non-`ACCEPTED` status with the redirect above.

Scenario (d): never-submitted period (extemporánea territory).

- State: Kent never submitted `303/2023Q3` and it is now past the statutory
  deadline.
- Command: `aeat revise start 303 --period 2023Q3 --kind complementaria`.
- Response: "`303/2023Q3` was never submitted. `revise` applies to previously
  filed periods. For extemporánea (out-of-term) filings, run `aeat status
  backlog scaffold --from 2023Q3 --to 2023Q3 --modelo 303` to register the
  overdue obligation, then `aeat draft create 303 --period 2023Q3` to build
  the draft. Surcharges apply per AEAT rules; see `aeat advanced reference
  normatives show ley-58-2003-surcharges`."
- Hardening rule: `revise start` checks for any persisted `SubmittedFiling`
  under `(modelo, period, profile_tax_id)` before accepting; if none exists,
  it redirects to `status backlog scaffold` with the explicit surcharge
  reference.

Scenario (e): baseline pre-dates the current schema version.

- State: Kent wants to revise `303/2022Q1`. The 2022 modelo schema differs
  from the 2024 modelo schema.
- Command: `aeat revise start 303 --period 2022Q1 --kind complementaria`.
- Response: the revise draft is built against the baseline's stored
  `schema_version_2022`. Export fichero uses the 2022 format. If the 2022
  schema is not present in the schema registry, the command fails: "Modelo
  303 ejercicio 2022 is not available in the schema registry. Run
  `aeat advanced reference schema refresh --modelo 303 --ejercicio 2022` to
  fetch it, or upload manually through the AEAT portal."
- Hardening rules:
  - Persist `schema_version` on every `SubmittedFiling` (audit gap from
    iteration 1 — confirm status; add if absent).
  - `revise` always builds against the baseline's original schema version,
    never head.
  - `draft show` for a baseline-pinned period must also render against the
    baseline schema, not head.

Scenario (f): multi-amendment chain.

- State: Kent already filed `303/2024Q2`, then a complementaria was filed
  and accepted, and he has now found another error.
- Command: `aeat revise start 303 --period 2024Q2 --kind complementaria`.
- Response: the baseline lookup walks the amendment chain and selects the
  most recent `ACCEPTED` filing (the first complementaria). The new revise
  draft is built on top of that baseline. `records amendments list --modelo
  303 --period 2024Q2` enumerates the full chain with timestamps and kinds.
- Hardening rules:
  - `list_amendments()` extends with `latest_accepted()` that walks the
    chain by `submitted_at` and `status=ACCEPTED`.
  - `revise` refuses to stack on top of a rejected amendment; it selects the
    last accepted one instead.
  - The amendment record carries `parent_submission_id` so the chain is
    traversable without re-scanning files.

### Hardening rules derived from iteration 2

- Every `revise start` requires a persisted baseline with `status=ACCEPTED`.
  Rejected, failed, or in-flight baselines are refused with a plain-language
  redirect.
- The baseline lookup walks the amendment chain and picks the most recent
  accepted filing. The CLI never silently picks a rejected amendment.
- `revise --kind` validation consults `RevisionSupportRegistry`. Unsupported
  `(modelo, ejercicio, kind)` triples fail with the registry's `notes_*`
  explanation in Kent's selected output language.
- `revise --kind sustitutiva` is accepted only when the modelo is marked as
  informativa in the modelo registry.
- `revise` honours the baseline's original schema version. `draft create`,
  `draft show`, `draft validate`, and `export modelo` under a revise flow all
  dispatch on the stored `schema_version`, not head.
- Rejection and extemporánea flows redirect to `compare explain --against
  aeat` and `status backlog scaffold` respectively. Silent failure is not
  acceptable.
- `revise` help text must show the per-modelo support row for the current
  invocation before Kent types a `--kind`.
- Every amendment record carries `parent_submission_id`, `amendment_kind`,
  and `schema_version` so the chain is traversable and deterministically
  reproducible.

### Open risks added by iteration 2

- `RevisionSupportRegistry` is only as good as its curation. Without a
  machine-checked test against an AEAT policy reference per ejercicio it
  will silently drift.
- Post-2023 "Autoliquidación Rectificativa IVA" has filing requirements that
  differ materially from classic rectificativa. The registry must
  distinguish the two or Kent's rectificativa 303 flow will emit a fichero
  AEAT does not accept.
- Schema-version pinning on revise requires that old schemas stay loadable
  indefinitely. A schema pruning policy would silently break old revises.
- Chain-walk performance degrades if an amendment chain grows unbounded;
  pagination and caching may be needed when revises stack.
- Kent selecting the wrong `--kind` is an easy error with tax consequences.
  `revise start` should summarise the chosen kind's implication ("this
  declaration will increase your liability by X") before accepting.

## Hardening pass iteration 3 (2026-04-24)

Iteration 3 focus: formal specification of the audit evidence bundle. This
section is the pre-ship contract for `audit show`, `audit verify`,
`audit export`, `audit replay`, and `audit manifest`. Without this contract
`audit` ships hollow.

### Bundle directory layout

An exported bundle is a zip archive (tar.gz is an accepted alias) with the
following internal layout:

```text
audit-{modelo}-{period}.zip
|-- manifest.json
|-- filing/
|   |-- draft.json
|   |-- approval-basis.json
|   `-- approval-journal.json
|-- export/
|   |-- fichero.boe
|   |-- fichero.boe.sha256
|   `-- verify.json
|-- formulas/
|   |-- ledger.json
|   `-- audit.json
|-- submission/
|   |-- submitted.json
|   |-- justificante.pdf
|   `-- amendments/
|       `-- {amendment_id}.json
|-- workflow/
|   `-- run.json
|-- references/
|   |-- manuals/
|   |   `-- {rule_id}.json
|   `-- normatives/
|       `-- {citation_id}.json
`-- corpus/
    `-- sha256.txt
```

Missing required files cause the writer to refuse to emit; an in-flight
failure never leaves a partial bundle claiming to be valid.

### manifest.json schema

The top-level manifest is the authoritative index. Every audit verifier reads
this first and trusts no other file until manifest integrity is confirmed.

Required fields:

- `bundle_version`: SemVer string. v1 ships as `"1.0"`.
- `bundle_id`: hex SHA-256 digest computed over the sorted concatenation of
  `{path}\0{sha256}\n` across every entry in `contained_files`. This is the
  bundle's content-addressed identity.
- `created_at`: ISO-8601 UTC timestamp with seconds precision.
- `created_by`: tool identity and semantic version (for example
  `"aeat-cli 0.18.2"`).
- `modelo`: canonical modelo identifier string (`"303"`).
- `ejercicio`: four-digit year (`"2024"`).
- `period`: canonical period identifier (`"2024Q1"`, `"2024"`, or monthly
  form where applicable).
- `profile_tax_id`: NIE/NIF string tied to the filing's taxpayer.
- `contained_files`: ordered list of objects, each with `path` (bundle-root
  relative), `sha256` (hex), `size_bytes` (int), `content_kind` (enum string
  from a closed set below), and `schema_version` (SemVer).
- `build_inputs`: object with `aeat_cli_version`, `corpus_sha256`,
  `schema_registry_sha256`, `python_version`, and `platform` strings.
- `audit_verdict`: object with `status` (enum: `complete`, `degraded`,
  `blocked`), `evaluated_at` timestamp, `checks_passed` int,
  `checks_failed` int, `notes` list of strings.

Closed `content_kind` enum for v1:

`filing-draft`, `filing-approval-basis`, `filing-approval-journal`,
`export-fichero-boe`, `export-fichero-sha256`, `export-verify`,
`formula-ledger`, `formula-audit`, `submission-baseline`,
`submission-justificante-pdf`, `submission-amendment`, `workflow-run`,
`reference-manual`, `reference-normative`, `corpus-sha256`.

New content kinds must be added via an ADR amendment. They bump
`bundle_version` minor.

### Subsidiary record contracts

`filing/draft.json` mirrors the persisted `FilingDraft`. It includes
`draft_id`, `profile_tax_id`, `modelo`, `period`, `status`, `values`,
`findings`, `approved_at`, `approved_by`, `approval_basis`,
`review_checksum`, and `schema_version`.

`filing/approval-basis.json` is the frozen `FilingApprovalBasis` fingerprint
snapshot at approval time. Its purpose is verifiable staleness detection.

`filing/approval-journal.json` is an ordered array of decision ledger
entries. Each entry has `entry_id` (UUIDv4), `timestamp` (ISO-8601 UTC),
`actor` (string, validated non-empty), `action` (enum: `approve`,
`unapprove`), `reason` (string, required, non-empty), `prior_review_checksum`
(nullable on first action), `next_review_checksum`, `prior_status` (enum),
`next_status` (enum). The decision journal is append-only.

`export/fichero.boe` is the byte-exact exported fichero in AEAT's BOE format.
`export/fichero.boe.sha256` is a sidecar containing the hex digest on one
line with trailing newline.

`export/verify.json` is the persisted `VerificationVerdict`. Fields:
`modelo`, `ejercicio`, `period`, `profile_tax_id`, `verified_at`, `status`
(enum: `PASS`, `FAIL`, `PARTIAL`), `narrative` (string), `discrepancies`
(array of discrepancy records with `casilla_id`, `user_value`,
`computed_value`, `delta`, `category` enum, `formula_id`), `tolerance`
(decimal string), `ruleset_id`, `corpus_sha256`.

`formulas/ledger.json` is the persisted `ComputationLedger`. Fields:
`ruleset_id`, `modelo`, `period`, `computed_at`, `entries` (array of
`LedgerEntry` with `casilla_id`, `value` as decimal string, `op` enum,
`formula_id`, `operand_refs` array, `operand_values` array, `notes`).

`formulas/audit.json` is the persisted `AuditReport`. Fields:
`ledger_ref` (path to `formulas/ledger.json`), `discrepancies` (array of
`Discrepancy` with `casilla_id`, `user_value`, `computed_value`, `delta`,
`formula_id`, `contributing_casillas`, `ruleset_id`, `category` enum).

`submission/submitted.json` is the baseline `SubmittedFiling` record.

`submission/justificante.pdf` is the AEAT receipt PDF as received (if
available).

`submission/amendments/{amendment_id}.json` is one `FilingAmendment` per
amendment in the chain. Fields: `amendment_id`, `parent_submission_id`,
`amendment_kind`, `delta` (array of `CasillaChange`), `amended_draft`
(full `FilingDraft`), `schema_version`, `created_at`, `submitted_at`,
`justificante_csv`, `status` (enum: `ACCEPTED`, `REJECTED`, `PENDING`).

`workflow/run.json` is the `WorkflowResult`. Fields include
`run_id`, `profile_tax_id` (NEW, per iteration 1), `corpus_sha256` (NEW),
`started_at`, `ended_at`, `final_stage`, `aborted_reason`, `obligation`,
`draft_id`, `submission_id`, `steps` (array of `WorkflowStep` with
`stage`, `started_at`, `ended_at`, `success`, `summary`, `details`,
`site_health_alert`).

`references/manuals/{rule_id}.json` is one `ManualRule` per cited rule.
Fields: `rule_id`, `manual_slug`, `anchor`, `text_es`, `published_at`,
`retrieval_date`, `is_curated_summary`.

`references/normatives/{citation_id}.json` is one `LegalCitation` per cited
normative reference. Fields: `citation_id`, `source` (enum), `article`,
`url`, `quoted_text_es`, `retrieval_date`, `is_curated_summary`.

`corpus/sha256.txt` is a plain-text file with named digests, one per line,
for the manual corpus, normatives corpus, schema registry, and ruleset
registry. Example:

```text
manuals=abc123...
normatives=def456...
schemas=789abc...
rulesets=0f1e2d...
```

### Provenance envelope (every record)

Every JSON record inside the bundle carries the following provenance envelope
fields alongside its content-specific fields:

- `record_schema_version`: SemVer string for this record type.
- `profile_tax_id`: NIE/NIF string. Redundant with the manifest, but required
  so each record stands alone under forensic extraction.
- `created_at`: ISO-8601 UTC when the record was first persisted.
- `source`: closed enum (`user-local`, `aeat-live`, `derived`, `imported`).
- `parent_id`: nullable string. Populated when the record has a durable
  parent (for example an amendment's `parent_submission_id`).

### Checksum algorithm

- Algorithm: SHA-256 over raw bytes for every file under `contained_files`.
- `manifest.bundle_id` is the SHA-256 of the sorted concatenation of
  `{path}\0{sha256}\n` across every entry in `contained_files`, hex-encoded.
  Sort key is lexical byte order of `path`.
- Digest files like `export/fichero.boe.sha256` carry the hex digest of the
  adjacent binary on one line with a trailing newline.

### Replay contract

`audit replay <modelo> --period <period>` requires the following stored
inputs:

- `formulas/ledger.json` with its `ruleset_id`.
- `workflow/run.json` with its `corpus_sha256`.
- `corpus/sha256.txt` for the manual, normative, schema, and ruleset
  registries at approval time.
- `filing/draft.json` for the original input values.

Deterministic reproduction rule: given identical `ruleset_id`,
`corpus_sha256`, `schema_registry_sha256`, and draft `values`, running the
ledger computation against today's engine must yield a byte-identical
`formulas/ledger.json`. Any divergence is classified:

- `replay-degraded`: ledger differs because ruleset, corpus, or schema has
  drifted since approval. The bundle is not invalid, but the case state must
  be re-verified with the current engine. The replay command emits a diff
  and marks the bundle `degraded` in its in-memory verdict.
- `replay-corrupt`: required inputs are missing or malformed. The bundle is
  treated as incomplete.
- `replay-match`: identical output. The bundle is deterministic.

Replay never silently passes on divergence.

### Bundle emission and integrity rules

- Bundle writer collects every required file, computes per-file digests,
  writes the manifest last, and only then finalises the zip archive. Partial
  writes never appear valid.
- Bundle writer refuses to emit if any required file is missing or any
  digest mismatch is detected against the stored records.
- Bundle writer refuses to emit if `profile_tax_id` differs between the
  manifest and any subsidiary record.
- Bundle writer refuses to overwrite an existing output without `--force`.
- Bundle reader accepts `bundle_version >= 1.0` and warns on minor-version
  drift. Major-version drift refuses to open.
- Bundle reader re-checks every `contained_files[*].sha256` before trusting
  the record for `audit verify` output.

### Language and output rules

- `audit show` emits a Kent-facing table with one row per evidence class,
  status tick or cross, and a plain-language note. ASCII-safe and
  Windows-terminal-safe.
- `audit manifest` emits the raw `manifest.json` to stdout for operator
  inspection.
- `audit export` emits a zip archive and prints the bundle path plus
  `bundle_id` to stdout.
- `audit verify` emits a PASS/FAIL/PARTIAL summary with per-artefact row
  detail on FAIL.
- `audit replay` emits `replay-match`, `replay-degraded`, or
  `replay-corrupt` with a unified diff when the mode is `degraded`.

All four commands carry output-language handling (`AEAT_OUTPUT_LANGUAGE`).

### Hardening rules derived from iteration 3

- `bundle_version` follows SemVer. Major bumps change required fields; minor
  bumps add optional fields or new content kinds.
- Every record inside the bundle carries a provenance envelope. Missing
  envelope fields fail bundle validation.
- `profile_tax_id` must be consistent across the manifest and every record.
  Cross-record mismatch is a validation error, not a warning.
- SHA-256 is the only supported digest algorithm in v1. Future migrations
  keep v1 readers compatible by parallel-emitting old digests during a
  migration window.
- `audit replay` is not optional. Any bundle that cannot replay is
  `degraded` and must be marked as such in its audit verdict.
- `audit export` runs `audit verify` as a precondition; a FAIL or PARTIAL
  verdict warns before emission and requires `--force-incomplete` to proceed.

### Open risks added by iteration 3

- Signed bundles (cryptographic signature tying the bundle to a known public
  key) are not in v1 but are plausible v2 requirements for legal-grade
  evidence.
- Compression versus indexability tradeoff: zip is self-contained but not
  streamable; a directory tree is indexable but fragile. v1 emits zip by
  default.
- Large ledgers for complex modelos may exceed sensible single-JSON sizes.
  v1 stores ledger as a single file; v2 may chunk.
- Record schema drift across `record_schema_version` and `bundle_version`
  must be centrally tracked in a compatibility table or they silently
  diverge.
- `corpus_sha256` depends on the corpus being content-addressed end to end.
  If any corpus source is not hashed in a stable order, replay silently
  drifts.

## Hardening pass iteration 4 (2026-04-24)

Iteration 4 focus: exact allocation of every current CLI root to its fate
under the hardened tree, plus day-1 post-migration Kent roleplay of old
invocation paths. This section closes the advanced quarantine contract by
specifying which command maps where, with sunset rules for aliases.

### Complete root-allocation table

Every current root listed in the structural audit is accounted for. The
verdict column is one of: `root-promoted` (stays or becomes a hardened root),
`root-dissolved` (split across several hardened roots), `root-merged`
(absorbed into an existing Kent root), `advanced-moved` (relocated under a
closed advanced bucket), `alias-sunset` (lives under `advanced aliases` for
one milestone then is removed), or `removed` (deleted).

| Current root | Verdict | Target path |
| --- | --- | --- |
| `setup` | root-merged | `configure profile set` (interactive first-run remains inside `configure`) |
| `auth` | root-promoted | `auth` |
| `doctor` | root-promoted | `doctor` (Kent diagnostic; stays at root) |
| `bootstrap` | advanced-moved | `advanced providers bootstrap` |
| `deadlines` | root-dissolved | `status today` plus `configure modelos calendar` |
| `status` | root-promoted | `status` (formerly hidden-only, now the reconciliation root) |
| `inbox` | root-merged | `records notifications` (live-fetch behaviour via `records aeat fetch`) |
| `justificante` | root-dissolved | parser reused inside `revise import-baseline`; read-only view at `records receipts show` |
| `financial` | root-dissolved | `txs` -> `transactions`; `invoices` -> `data`; `profile` -> `configure defaults` |
| `filing` | root-dissolved | `build/show/list/validate` -> `draft`; `import --from-*` -> `revise import-baseline` |
| `review` | root-promoted | `review` |
| `submission` | root-dissolved | `preflight/dry-run/export/verify/diff/schemas` -> `export`; live-adjacent semantics deleted |
| `workflow` | advanced-moved | `advanced workflow` (live flags closed before move; see iteration 1 pre-approval blocker) |
| `formulas` | advanced-moved | `advanced formulas` |
| `run` | advanced-moved | `advanced runs` (show/list/replay) |
| `sync` | advanced-moved | `advanced workflow sync` |
| `schema` | advanced-moved | `advanced reference schema` |
| `modelos` | advanced-moved | `advanced reference modelos`; Kent-facing applicable-to/calendar lives under `configure modelos` |
| `normatives` | advanced-moved | `advanced reference normatives` |
| `manual` | advanced-moved | `advanced reference manuals` |
| `casillas` | advanced-moved | `advanced reference casillas` |
| `categories` | advanced-moved | `advanced reference categories` |
| `vat` | advanced-moved | `advanced reference vat` |
| `portals` | advanced-moved | `advanced reference portals` |
| `attachments` | advanced-moved | `advanced reference attachments`; Kent-facing link behaviour via `data link attachment` |
| `oauth-client` | advanced-moved | `advanced providers oauth-client` |
| `cloud` | advanced-moved | `advanced providers cloud` |
| `drive` | advanced-moved | `advanced providers drive` |
| `sheets` | advanced-moved | `advanced providers sheets` |
| `docs` | advanced-moved | `advanced providers docs` |
| `browser` | advanced-moved | `advanced diagnostics browser` |
| `llm` | advanced-moved | `advanced llm` (inspection, cache, translation utilities) |
| `hello` | removed | no replacement; was a smoke-test fixture |

Derived new first-class roots not present in current code:

| New root | Origin | Implementation status |
| --- | --- | --- |
| `status` | promoted from hidden stubs | greenfield for `today`, `backlog`, `resume`; `show` and `history` consolidate existing fragments |
| `data` | new | greenfield for `require`/`readiness`; reuses existing ingest/link primitives |
| `transactions` | promoted from `financial txs` | rename plus missing verbs (`automate`, `inspect`, `resume`, `link`) |
| `draft` | promoted from `filing build/show/list/validate` | rename, retire developer input path |
| `compare` | new | new case-first surface over existing `submission verify`/`diff` primitives |
| `audit` | new | greenfield; depends on iteration 3 manifest persistence work |
| `revise` | promoted from `filing complementaria`/`filing import` | new verbs (`start`, `import-baseline`, `status`, `resume`); registry work per iteration 2 |
| `records` | consolidation | absorbs `filing list`, `inbox list`, `submission list`, `status expedientes` |

### Alias surface under `advanced aliases`

Each alias forwards to its target, emits a stderr deprecation notice, and
fails instead of running when the call carries live-write flags. Aliases are
removed in the release that follows their introduction. Scripts with
`--silence-alias-deprecation` skip the notice.

| Alias | Target |
| --- | --- |
| `advanced aliases financial-txs *` | `transactions *` |
| `advanced aliases financial-invoices *` | `data link invoice` and `data edit invoice` |
| `advanced aliases financial-profile *` | `configure defaults *` |
| `advanced aliases filing-build *` | `draft create` (loses `--inputs` JSON path) |
| `advanced aliases filing-show/list/validate *` | `draft show/list/validate` |
| `advanced aliases filing-import-from-justificante *` | `revise import-baseline` |
| `advanced aliases filing-import-from-declaracion *` | `revise import-baseline` with advanced typed kind |
| `advanced aliases filing-import-from-borrador *` | `revise import-baseline` with advanced typed kind |
| `advanced aliases submission-preflight/dry-run/export/verify/diff/schemas *` | `export *` |
| `advanced aliases workflow-run/next *` | `advanced workflow run/next`; live flags rejected outright |
| `advanced aliases deadlines *` | `status today` and `configure modelos calendar` |
| `advanced aliases inbox *` | `records notifications` |
| `advanced aliases schema/modelos/normatives/manual/casillas/categories/vat/portals *` | `advanced reference <noun> *` (retained without sunset; these are expert paths) |

Aliases in the non-sunset set (reference nouns) stay indefinitely because
they are expert surfaces and `advanced reference *` is the only long-lived
home.

### Day-1 post-migration Kent roleplay

Kent opens his terminal the day after the migration ships. He runs
`aeat --help`.

```text
Usage: aeat [OPTIONS] COMMAND [ARGS]...

  File your Spanish tax returns: produce, verify, and export AEAT-ready
  drafts and records.

Kent's filing journey:
  configure    Identity, taxpayer profile, defaults, and modelos calendar
  auth         Live AEAT session: login, logout, status, providers
  status       Obligation truth: today, show, backlog, resume, history
  data         Evidence: import, link, edit, readiness
  transactions Throughput: build, automate, classify, categorize, edit, inspect
  draft        Filing draft: create, show, validate, list
  review       Judgment gate: queue, show, approve, unapprove, history
  compare      Discrepancy analysis: show, explain, fix, verify
  export       AEAT upload artefacts: modelo, preflight, dry-run, verify, diff, schemas
  audit        Evidence bundle: show, verify, export, replay, manifest
  revise       Correct a filed period: start, import-baseline, status, resume

Records and diagnostics:
  records      Retrospective inventory
  doctor       Check workspace health

Advanced:
  advanced     Expert, provider, reference, formula, runs, diagnostic, and alias tooling

Run `aeat COMMAND --help` for any command.
```

Kent then types six invocations from muscle memory. The CLI behaves as
follows.

`aeat financial txs classify tx_123`:

```text
[deprecated] `aeat financial txs` is now `aeat transactions`.
Forwarding to `aeat transactions classify tx_123`.
This alias will be removed in the next release; update your scripts.
```

The command succeeds.

`aeat filing build 303 --period 2024Q1 --inputs ./in.json`:

```text
[deprecated] `aeat filing build` is now `aeat draft create`. The `--inputs`
JSON path was retired: build uses the current transaction catalogue and
data-readiness state for the period.

Run `aeat data readiness 303 --period 2024Q1` first, then
`aeat draft create 303 --period 2024Q1`. Exit 2 (alias requires manual
migration).
```

The command refuses to run because the forwarding target cannot honour
`--inputs`. Kent updates his script.

`aeat submission export 303 2024Q1`:

```text
[deprecated] `aeat submission export` is now `aeat export modelo`.
Forwarding to `aeat export modelo 303 --period 2024Q1`.
Alias removed in the next release.
```

`aeat workflow run --modelo 303 --period 2024Q1 --no-dry-run --i-understand-this-is-real`:

```text
Refused. Live-submit flags are rejected on this invocation path.

`aeat workflow run` has moved to `aeat advanced workflow run`. Live
execution requires the four-factor safety gate defined in the live-submit
excision ADR (2026-04-18): environment variables
`AEAT_ALLOW_LIVE_SUBMIT_OPT_IN=1` and `AEAT_LIVE_SUBMIT_ENABLED=1`, an
explicit `--live` flag, and an interactive per-submission prompt.

For a dry-run equivalent:
  aeat advanced workflow run --modelo 303 --period 2024Q1
Exit 5 (live-write flags refused).
```

The alias does not forward. It refuses outright.

`aeat status`:

```text
Usage: aeat status [OPTIONS] COMMAND [ARGS]...

  Reconciled obligation truth across expected, local, AEAT, and blocked.

Commands:
  today                       What needs attention now
  show <modelo>               Reconcile one filing; next action
  backlog                     Multi-period recovery across years
  resume <modelo>             Reopen the highest-value unresolved work
  history <modelo>            Prior reconciliation transitions
```

Previously this was advertised as a root but exposed no visible children.
After migration it is truthful.

`aeat hello`:

```text
`aeat hello` has been removed. It was a smoke-test fixture without Kent or
contributor value. If you were checking workspace health, run
`aeat doctor`. Exit 127.
```

`aeat schema show 303`:

```text
`aeat schema` has moved to `aeat advanced reference schema` (expert).
Forwarding to `aeat advanced reference schema show 303`. No deprecation;
this alias is retained.
```

### Hardening rules derived from iteration 4

- Alias stderr notices use a stable prefix `[deprecated]` or `[moved]` so
  scripts can grep reliably.
- Aliases that cannot honour all original option semantics refuse rather
  than silently dropping arguments. Exit 2.
- Aliases that would forward live-write semantics refuse rather than
  forwarding. Exit 5.
- Aliases that are retained indefinitely use `[moved]` (never
  `[deprecated]`).
- Every alias carries `--silence-alias-deprecation` for CI-friendly silence.
- The root `--help` order is Kent clusters, then Records/Diagnostics, then
  Advanced. Advanced is visible but appears last.
- `aeat advanced --help` renders bucket nouns only: `reference`,
  `providers`, `formulas`, `workflow`, `runs`, `diagnostics`, `llm`,
  `aliases`. It does not render per-leaf listings; users drill in.
- Release notes announce each alias's sunset release explicitly.

### Open risks added by iteration 4

- One-milestone alias lifetime may be too short for CI-heavy users. The
  release cadence must publish sunset dates with each release so users can
  plan.
- Alias sprawl returns if authors add new aliases without a matching ADR
  amendment. The admission rule must be enforced by a test that scans
  `advanced aliases` leaves against an allow-list.
- `advanced llm` versus `advanced diagnostics llm` collision: iteration 4
  picks `advanced llm` as the canonical home and routes diagnostic checks
  as leaves inside it. `advanced diagnostics llm` is not introduced.
- Root `--help` length: adding Records and Diagnostics as a combined
  cluster keeps the root short. Adding a future cluster must either
  compress an existing one or move into Advanced.
- Kent may interpret `removed` as a regression when `hello` vanishes. The
  migration notes include `hello` in the removal list explicitly.

## Hardening pass iteration 5 (2026-04-24)

Iteration 5 focus: verify the pre-approval blocker set in iteration 1 (the
`aeat workflow run` and `aeat workflow next` live-flag leak) and produce a
file-level excision plan plus a tracking-issue skeleton. Discovery was
handled by a Haiku subagent with read-only scope over the workflow CLI,
related safety-gate code, git history on those files, and existing issue
labels. The decision framework is primary-agent work.

### Verification summary

The blocker is not closed.

- `src/aeat/entrypoints/cli/workflow/run.py`: `--no-dry-run` registered on lines 23 to 27,
  `--i-understand-this-is-real` registered on lines 28 to 32. Neither the
  command nor the hosting group is marked `hidden=True`. Both flags are
  discoverable through `aeat workflow run --help`.
- `src/aeat/entrypoints/cli/workflow/next.py`: `--no-dry-run` registered on lines 28 to
  32, `--i-understand-this-is-real` registered on lines 33 to 37. Not
  hidden. Discoverable through `aeat workflow next --help`.
- `src/aeat/entrypoints/cli/workflow/__init__.py`: registers both commands via
  `app.command()` on lines 33 to 40 without `hidden=True`.
- Inline guard: both command bodies reject `--no-dry-run` without the
  companion flag at exit code 2, which is defence in depth, but the flags
  themselves remain first-contact discoverable.
- Engine-level four-factor gate:
  `src/aeat/adapters/outbound/aeat/export/_engine.py` lines 210 to 224 respect
  `AEAT_LIVE_SUBMIT_ENABLED` through `AeatAccessGate.require_live_write()`
  plus the `live_transport_supported` default. This is correct and intact.
- `live_transport_supported=True` audit: no production code site sets this
  True. Only test fixtures at
  `src/aeat/adapters/outbound/aeat/export/test_safety_helpers.py` line 238 and the visibility
  test at `src/aeat/entrypoints/cli/submission/test_live_submit_defer_visibility.py`
  lines 66 and 80 set it. This complies with the excision ADR mandate.
- Issue tracking: the live-write safety charter (#116) and the static-audit
  enumeration task (#118) are both open. The architectural hardening work
  (#117) is referenced by #116 but the CLI-help-visibility surface is not
  yet enumerated in #118. No closed issue addresses the workflow CLI
  flag-visibility gap.
- Git history: no recent commit targets `workflow/run.py` or
  `workflow/next.py` for live-flag excision. The most recent safety-adjacent
  commit is `9bf831e` (submission safety gaps, #157) and predates the
  current flag exposure.

### Decision

The pre-approval blocker remains active. The ADR stays `proposed`. A
concurrent remediation issue must be opened and closed before this ADR can
be approved.

Iteration 1 defined three acceptable closure paths. Iteration 5 selects the
minimum-intrusion path that preserves existing behaviour for engineering
users while closing the Kent-facing leak: path 3 (excise the live branch
from the default CLI entirely before any public root renames ship). This
preserves the engine-level live-write capability for programmatic callers
and keeps the `advanced workflow run --live` reintroduction path open for
the 1.0.0 work, without requiring the advanced-quarantine migration to land
first.

The closure sequence is:

1. Excise the two flags and the live-execution branch from the default
   workflow commands.
2. Open a tracking issue that links to this ADR and to the safety charter
   #116.
3. Land the excision behind the normal PR pipeline with regression tests.
4. Strike the pre-approval blocker in a follow-up iteration of this ADR.

The advanced-quarantine migration from iteration 4 remains the next-step
follow-through but is not a prerequisite for closing the leak.

### File-level excision plan

Scope: three files. All changes are dry-run-preserving. No engine changes.
No default behaviour change for scripts that did not invoke the live flags.

Change 1: `src/aeat/entrypoints/cli/workflow/run.py`.

- Remove the `--no-dry-run` Click option at lines 23 to 27.
- Remove the `--i-understand-this-is-real` Click option at lines 28 to 32.
- Remove the corresponding `no_dry_run: bool` and `i_understand_this_is_real:
  bool` parameters from the `run_cmd` signature.
- Remove the early refuse-branch at lines 54 to 58 that validates the
  combination.
- Force `dry_run=True` wherever the downstream engine invocation is called.
  The existing call shape under the dry-run path stays unchanged.
- Help text: remove any mention of live execution. Add a single sentence:
  `Runs the workflow in dry-run mode. Live execution is not available from
  this command; see release notes for planned 1.0.0 reintroduction.`

Change 2: `src/aeat/entrypoints/cli/workflow/next.py`.

- Remove `--no-dry-run` at lines 28 to 32.
- Remove `--i-understand-this-is-real` at lines 33 to 37.
- Remove `no_dry_run: bool` and `i_understand_this_is_real: bool` from the
  `next_cmd` signature.
- Remove the refuse-branch at lines 58 to 62.
- Force `dry_run=True` downstream.
- Help text: identical one-sentence addition as Change 1.

Change 3: `src/aeat/entrypoints/cli/workflow/__init__.py`.

- At the `app.command()` registrations on lines 33 to 40, decide between
  two sub-options:
  - Minimum intrusion: leave registrations as-is. The commands remain
    public under `aeat workflow run/next` but no longer carry live flags.
    Kent-facing leak is closed.
  - Preferred per iteration 4: mark the hosting group or both commands
    with `hidden=True` and add an `--advanced` discovery surface. Partial
    advance of the iteration 4 migration.
- This ADR's iteration 5 selects the minimum-intrusion sub-option for
  closure speed. The iteration 4 migration work runs on its own track.

Regression tests (new, colocated per project conventions):

- `src/aeat/entrypoints/cli/workflow/test_run_help_ascii_safe.py`:
  - Invoke the Click command's `--help` under a Click test runner.
  - Assert that `--no-dry-run` does not appear in the rendered help.
  - Assert that `--i-understand-this-is-real` does not appear.
  - Assert the help text is ASCII-only (Windows-terminal-safe).
- `src/aeat/entrypoints/cli/workflow/test_next_help_ascii_safe.py`: equivalent for
  `next_cmd`.
- `src/aeat/entrypoints/cli/workflow/test_run_refuses_live_flags.py`:
  - Invoke the Click command with `--no-dry-run --i-understand-this-is-real`.
  - Assert exit code is non-zero (Click unknown-option error).
  - Assert stderr describes the flag as unknown, not as rejected.
- `src/aeat/entrypoints/cli/workflow/test_next_refuses_live_flags.py`: equivalent for
  `next_cmd`.

Access-gate assertions (ensure excision does not weaken the four-factor
gate at the engine layer):

- `src/aeat/adapters/outbound/aeat/export/test_access_gate_workflow_untouched.py`:
  - Verify `AeatAccessGate.require_live_write()` still refuses when
    `AEAT_LIVE_SUBMIT_ENABLED` is unset.
  - Verify `SubmissionEngine` default `live_transport_supported=False`
    remains a constructor-level default.

Markers per `tests/README.md` and `.vault/adr/2026-04-17-pytest-markers-adr.md`:

- `pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]` for the
  help-rendering tests.
- `pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]` for the
  access-gate assertion tests.

Documentation updates required by the excision:

- `docs/coverage/pipeline.md`: remove any reference to live execution through
  the workflow CLI; cite the excision ADR and this hardening iteration.
- `docs/coverage/kent-capabilities.md`: confirm no Kent-facing live-submit
  language remains.

### Tracking-issue skeleton

The following is the literal body for a new GitHub issue to open on
`wgergely/aeat`. Every bracketed placeholder must be filled in by the person
opening the issue. The issue is a prerequisite for approving this ADR.

```text
Title: excise aeat workflow run/next live-flag leak (pre-approval blocker for CLI wireframe ADR)

Labels: type:bug, domain:aeat-remote, domain:submission, priority:P0-blocker, effort:S, parallel-safe

Milestone: (pin to the release that precedes CLI wireframe ADR approval)

Body:

## What Kent can do now that he couldn't before

Kent cannot accidentally discover or invoke a live AEAT submission from the
default CLI surface. `aeat workflow run --help` and `aeat workflow next --help`
no longer advertise `--no-dry-run` or `--i-understand-this-is-real`.

## Context

The live-submit CLI excision ADR (2026-04-18) removed `aeat submission submit`
from the default CLI. However, `aeat workflow run` and `aeat workflow next`
were added earlier (#59, #63, #140) and still expose the live-execution flags
`--no-dry-run` and `--i-understand-this-is-real` in their default non-hidden
help. These flags dispatch through SubmissionEngine, which is correctly gated
at the engine layer, but the Kent-facing discoverability undermines the
safety charter (#116) and the excision ADR.

This is the pre-approval blocker set by the CLI wireframe ADR hardening pass
iteration 1 (2026-04-24).

## Scope

- `src/aeat/entrypoints/cli/workflow/run.py`: remove `--no-dry-run` and
  `--i-understand-this-is-real` options; remove the refuse-branch; force
  `dry_run=True` at the engine call site.
- `src/aeat/entrypoints/cli/workflow/next.py`: same.
- `src/aeat/entrypoints/cli/workflow/__init__.py`: no visibility change in this issue.
  The advanced-quarantine migration from the CLI wireframe ADR handles
  visibility separately.
- Regression tests: help-rendering assertions, flag-rejection assertions,
  access-gate assertions.
- Documentation: update `docs/coverage/pipeline.md` and
  `docs/coverage/kent-capabilities.md` to match.

## Out of scope

- Introducing `advanced workflow run --live`. That belongs with the 1.0.0
  live-submit reintroduction work and the AuthProvider abstraction (#279).
- Engine-level changes to `_engine.py`. The four-factor gate is intact;
  this excision deliberately does not touch it.
- The broader advanced-quarantine migration from the CLI wireframe ADR.

## DoR

- Kent-observable acceptance: `aeat workflow run --help` and
  `aeat workflow next --help` do not advertise any live-execution flag.
- Labels correct; priority P0-blocker; parallel-safe; effort S.
- Affects two CLI files plus tests; does not require a new ADR.

## DoD

- Both workflow CLI files updated per the plan.
- Regression tests added and passing locally.
- Coverage floor 60 percent preserved per project mandate.
- Pre-commit hooks pass. Conventional commit message used.
- PR links to this issue and to the CLI wireframe ADR.

## References

- Safety charter: #116
- Env-gate hardening: #117
- Static audit: #118
- CLI wireframe ADR: `.vault/adr/2026-04-24-aeat-cli-wireframe-adr.md`
- Excision ADR: `.vault/adr/2026-04-18-live-submit-cli-excision-adr.md`
- Verification discovery: iteration 5 above
```

### Hardening rules derived from iteration 5

- The ADR stays `proposed` until the tracking issue ships. No approval in
  this state.
- Iteration 5 findings are appended, not retrofitted. Future iterations may
  flip the blocker once closure is verified; iteration 5 itself is immutable
  discovery.
- A help-rendering regression test in `src/aeat/entrypoints/cli/workflow/` is the
  primary gate for re-closure of this leak. Without that test, the leak can
  silently return under future refactors.
- The excision does not touch the engine-level gate. That layer is correct
  and must remain intact; any later live-submit reintroduction must route
  through the AuthProvider abstraction.
- `live_transport_supported` stays default-False across the codebase; only
  test sites may set it True. The project mandate at the top of `CLAUDE.md`
  reinforces this and iteration 5 confirms compliance.

### Open risks added by iteration 5

- A future refactor may accidentally reintroduce the flags when the
  advanced-quarantine migration lands. The regression tests on
  `aeat workflow run/next --help` must survive that migration; if the
  commands move to `advanced workflow`, the same tests must move with them.
- The excision closes only the Kent-facing leak. If another engineer
  surfaces another live-adjacent flag on another command, the blocker
  pattern recurs. A follow-up audit should enumerate every CLI command that
  accepts a live-write flag and assert each one is either hidden or
  programmatic-only.
- If the tracking issue lingers open, the CLI wireframe ADR cannot progress.
  Project coordination must weight this against the ADR's other approval
  points.

### Next iteration focus

Subsequent work happens inside the tracking issue and through the
milestone-scoped migration issues derived from iteration 4's allocation
table. The ADR status flips from `proposed (hardening iteration 1 applied)`
to `proposed (approval-ready)` when all pre-approval blockers close. Further
hardening iterations (6+) target meta-level production concerns: error
taxonomy, output contract, determinism, internationalization, rollout
sequencing.


## Hardening iterations 6 through 33

Iterations 6 through 33 have been moved to a supplementary reference
document because this ADR exceeded the project's 500 KB file-size
policy. They remain part of the controlling decision record for the
Kent-first CLI redesign.

See the reference document `2026-04-24-aeat-cli-wireframe-reference`
under `.vault/reference/`. Topics covered in the reference:

- iteration 6: error-code registry and category taxonomy
- iteration 7: `--json` output contract and schema registry
- iteration 8: determinism, idempotency, undo, and concurrency
- iteration 9: internationalization (es / en / hu)
- iteration 10: Phase A through E migration rollout
- iteration 11: multi-profile support
- iteration 12: credential hygiene and security contract
- iteration 13: onboarding UX and doctor redesign
- iteration 14: test-layer harness and Kent-wall regression catalogue
- iteration 15: local-first telemetry and diagnostics
- iteration 16: performance budgets and scale fixture
- iteration 17: backup, restore, and workspace portability
- iteration 18: modelo coverage expansion framework
- iteration 19: signed corpus bundle and offline install
- iteration 20: LLM automation quality metrics
- iteration 21: AEAT portal drift change management
- iteration 22: Windows cross-platform regression catalogue
- iteration 23: release process hardening
- iteration 24: structural audit harness automation
- iteration 25: runbook authoring and operational docs discipline
- iteration 26: per-profile master keys
- iteration 27: Autoliquidación Rectificativa IVA deep dive
- iteration 28: GDPR and data retention compliance
- iteration 29: collaboration and delegated access
- iteration 30: sandbox and dry-run mode
- iteration 31: filing-season deadline pressure UX
- iteration 32: regional tax regimes (Vasco, Navarra, Canarias)
- iteration 33: post-filing AEAT response monitoring

Each iteration has a tracked GitHub issue under EPIC 392.
