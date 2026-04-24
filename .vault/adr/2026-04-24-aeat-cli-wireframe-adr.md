---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/adr/ location)
# Feature tag (replace aeat-cli-wireframe with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#adr'
  - '#aeat-cli-wireframe'
# ISO date format (e.g., 2026-02-06)
date: '2026-04-24'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - "[[2026-04-24-aeat-cli-wireframe-research]]"
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-18-live-submit-cli-excision-adr]]"
  - "[[2026-04-21-auth-cli-adr]]"
  - "[[2026-04-18-unified-review-queue-adr]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `aeat-cli-wireframe` adr: `kent-first cli language system and root wireframe` | (**status:** `proposed`)

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
