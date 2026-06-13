---
tags:
  - '#research'
  - '#aeat-cli-wireframe'
date: '2026-04-24'
modified: '2026-04-24'
related:
  - "[[2026-04-21-auth-cli-adr]]"
  - "[[2026-04-18-category-assignment-cli-adr]]"
  - "[[2026-04-18-unified-review-queue-adr]]"
---



# `aeat-cli-wireframe` research: `kent cli ux wireframe research`

This research documents the current AEAT CLI shape as it exists on `main`
on 2026-04-24 and extracts the constraints that matter for a CLI wireframe
ADR. The focus is not generic CLI advice. It is Kent's operator path through
the product direction already established in the repo: produce, verify,
export, with live submission deferred from the default CLI surface.

## Findings

### Evidence base

This research is grounded in four source classes:

- Product direction and milestone language in `ROADMAP.md` and
  `CONTRIBUTING.md`
- Current capability truth in `docs/coverage/kent-capabilities.md`,
  `docs/coverage/pipeline.md`, and `docs/coverage/modelos.md`
- Kent-journey failure analysis in
  `.vault/audit/2026-04-17-kent-ux-journey-audit.md` and
  `.vault/audit/2026-04-18-kent-data-prep-journey-audit.md`
- The shipped CLI tree and help text in `src/aeat/entrypoints/cli/__init__.py`,
  `src/aeat/entrypoints/cli/status/__init__.py`, `src/aeat/entrypoints/cli/financial/__init__.py`,
  `src/aeat/entrypoints/cli/review/__init__.py`, `src/aeat/entrypoints/cli/filing/__init__.py`,
  `src/aeat/entrypoints/cli/workflow/next.py`, `src/aeat/entrypoints/cli/workflow/run.py`, and live
  `uv run aeat ... --help` output

Two older audit findings are already partially remediated on `main` and must
not be repeated as current-state facts in the ADR:

- The root tagline is now Kent-facing: `aeat --help` says
  `File your Spanish tax returns: produce, verify, and export AEAT-ready drafts and records.`
- `aeat setup` now exists again and is advertised at the root

### Current CLI shape

The root command currently exposes 34 entries. That width is the first
wireframe problem. Kent-critical journey surfaces sit at the same level as
provider utilities, reference corpora, dev helpers, and obvious non-user
commands such as `hello`.

#### Root-level clusters as shipped

| Cluster | Current root entries | Research signal |
| --- | --- | --- |
| First-run and readiness | `setup`, `doctor`, `auth`, `bootstrap` | This is the closest thing to an onboarding cluster, but `bootstrap` is infrastructure language, not Kent language. |
| Situation awareness | `deadlines`, `status`, `inbox`, `justificante` | These are Kent questions: what do I owe, what did AEAT say, what did I file. Today they are split across live, local, and parsing surfaces. |
| Data preparation | `financial`, `invoices`, `categories`, `vat`, `attachments` | The real work lives here, but the cluster is fragmented between workflow actions and taxonomy/reference nouns. |
| Draft, review, export | `filing`, `review`, `submission`, `workflow`, `formulas` | This is the strongest shipped spine, but it is split between stage nouns and engineering nouns. |
| Reference and admin | `manual`, `modelos`, `normatives`, `schema`, `portals`, `drive`, `sheets`, `docs`, `cloud`, `browser`, `llm`, `sync`, `run`, `casillas`, `oauth-client`, `hello` | These surfaces are real, but they should not compete with Kent's first-contact path at the same root depth. |

#### Important current-state facts

- `status` is publicly advertised but effectively empty for Kent today. `aeat status --help` shows no visible subcommands, while `src/aeat/entrypoints/cli/status/__init__.py` still registers `expedientes`, `notificaciones`, `devoluciones`, `borrador`, `datos-fiscales`, and `calendario` as `hidden=True`.
- `submission` is the cleanest statement of the export-first contract. It advertises `preflight`, `dry-run`, `export`, `verify`, `diff`, `schemas`, `check-nif`, `show`, and `list`, and explicitly says there is no default CLI live-submit command.
- `workflow` duplicates part of the `filing -> review -> submission` path and still exposes `--no-dry-run` plus `--i-understand-this-is-real`. That is a naming and policy tension the ADR must address.
- `financial` is materially ahead of the April 18 audit snapshot. The shipped surface now includes `txs build`, `classify`, `classify-llm`, invoice linking and reconciliation, and `financial profile set-ratio`. The data-prep language is still system-shaped, but the surface is no longer purely browse-only.
- `filing build` still reflects a developer-shaped input model. Its source help text says `--inputs` is a JSON file with `casilla -> value mapping`.
- On this Windows environment, `uv run aeat filing build --help` crashes with a `UnicodeEncodeError` because the help text contains the `->` arrow rendered as a Unicode glyph. Wireframe copy must remain terminal-safe.

### Kent POV root-node requirements

The root wireframe must satisfy Kent's first four questions without forcing him
to know the codebase or AEAT internals:

- What is this tool for right now
- What should I do next
- What is already configured versus blocked
- Which filing or obligation is the current focus

That implies these root-node requirements:

- The first-contact node must stay Kent-facing and capability-based, not contributor-facing. `ROADMAP.md` and `CONTRIBUTING.md` both require every milestone and issue to answer what Kent can do.
- The root must privilege the milestone spine already expressed in the roadmap: install and readiness, see obligations, prepare data, build draft, review and approve, export and verify, then later live history and notifications.
- The root must be stateful. When the workspace is unconfigured, the first route should be setup and readiness, not a flat list of every namespace.
- The root must be truthful about unavailable surfaces. An advertised node with no visible commands, as with `status`, is worse than a narrower tree with an explicit dependency note.
- The root must preserve the export-first promise. Kent's normal path is produce, verify, export. Live submission is not the default language system.
- The root must separate Kent workflow nodes from advanced reference or provider nodes. Experts can still reach `schema`, `normatives`, `cloud`, and similar surfaces, but those should not define the first wireframe.

### Naming and verb-system requirements

The current CLI already contains many useful verbs, but they are distributed
inconsistently across journey stages and implementation layers.

#### Current verb inventory

- Setup and access: `setup`, `init`, `configure`, `login`, `logout`
- Health and checking: `doctor`, `status`, `verify`, `preflight`, `check-nif`, `show`
- Planning and awareness: `next`, `list`, `explain`
- Data prep: `ingest`, `build`, `classify`, `classify-llm`, `link`, `reconcile`
- Filing stages: `build`, `validate`, `approve`, `unapprove`, `dry-run`, `export`, `diff`
- Runtime and transport verbs: `run`, `sync`, `bootstrap`, `fetch`

#### Requirements for the new language system

- Root-stage verbs must be few, stable, and semantically unique. One verb should map to one operator intent.
- The wireframe must distinguish four separate kinds of "check" that are currently easy to blur: workstation readiness, AEAT live status, draft review state, and exported-file verification.
- `build` currently means at least two different things: build a transaction catalogue and build a filing draft. The later ADR must decide whether shared `build` is acceptable or whether stage-specific verbs are required.
- `workflow` and `run` are engineering nouns, not Kent nouns. Kent thinks in obligations, drafts, reviews, exports, history, and notifications.
- `approve` should remain an explicit verb. The coverage matrix and review surface make approval state and staleness first-class product behavior, not incidental UI sugar.
- `export` and `verify` should remain explicit verbs or explicit stage labels. They are load-bearing product concepts in the roadmap and submission surface.
- Leaf utility verbs such as `list` and `show` are fine, but they should support a primary journey surface rather than become the journey language themselves.
- Help copy must remain ASCII-safe and terminal-safe across Windows consoles. The wireframe should not depend on Unicode flourishes for essential meaning.

### Noun and jargon exclusions

The later ADR should treat these as exclusions or demotions from the Kent root
language unless they are wrapped in plain-language framing.

#### Exclude from first-contact Kent navigation

- Infrastructure nouns: `GCP`, `OAuth client`, `cloud`, `drive`, `sheets`, `docs`, `browser`, `provider`, `sync`
- Internal model nouns: `schema`, `NDJSON`, `RawTransaction`, `run`, `catalogue` when used without user framing
- Bare AEAT surface nouns without framing: `expedientes`, `devoluciones`, `borrador`, `datos-fiscales`
- Raw filing-internals nouns without framing: `casilla`, `fichero-BOE`, `complementaria`, `rectificativa`

#### Acceptable at Kent root when contextualized

- `AEAT`
- `modelo 130`, `modelo 303`, `modelo 390`
- `deadlines`
- `draft`
- `review`
- `approve`
- `export`
- `verify`
- `history`
- `notifications`

The project-wide language constraint matters here. Spanish is the authoritative
terminology baseline, but Kent in the audits prefers English. The wireframe
should therefore default to plain English stage nouns while preserving Spanish
legal terms as leaf-level specificity, aliases, or explanatory labels rather
than first-contact taxonomy.

### Functional clustering requirements

The wireframe should cluster around user goals, not code ownership.

| Functional cluster | Kent question | Current shipped evidence | Wireframe requirement |
| --- | --- | --- | --- |
| Start and readiness | Can I use the tool safely today | `setup`, `doctor`, `auth` | Keep this as the first path when unconfigured. Demote `bootstrap` and provider-specific setup under it. |
| Obligations and awareness | What do I owe, what happened, what is waiting | `deadlines`, hidden `status` surfaces, `inbox`, `justificante` | Present one coherent awareness cluster and label live-dependency requirements clearly. |
| Data preparation | Do I have enough clean data to compute this filing | `financial`, invoice linking, usage-ratio profile, categories and VAT support surfaces | Make preparation a first-class cluster. Taxonomy/reference helpers should sit beneath it, not beside it. |
| Draft and review | What draft exists and what still needs my decision | `filing`, `review`, `formulas` | Keep review separate enough to protect approval state, but do not force Kent to understand internal formula tooling to trust the numbers. |
| Export and evidence | Can I safely generate and check the artifact I will upload | `submission export`, `verify`, `diff`, `schemas`, `show`, `list` | Preserve the export-first contract and make schema support discoverable by modelo. |
| Advanced and reference | What does the system know and how is it wired | `manual`, `normatives`, `schema`, `modelos`, `portals`, provider helpers | Move out of Kent-first root navigation without deleting expert reach. |

### Domain dependency notes

These constraints should shape the wireframe language even if the ADR chooses a
different tree than the current CLI.

- Live AEAT history depends on the auth-provider layer and the still-hidden status backend. The wireframe must distinguish local information from live AEAT reads.
- The roadmap and project mandates are explicit that the normal product path is export-first. The submission group already expresses this clearly; the wireframe should inherit that posture.
- `workflow next` and `workflow run` still expose live-submission flags despite the default CLI live-submit excision. That is a policy edge the ADR must either normalize or remove from the Kent-first language.
- Deadline computation and some filing flows depend on an `AutonomoProfile`. The root language should expose that as Kent profile/setup language, not as raw domain object language.
- Google Workspace and GCP are supporting dependencies for storage and automation. They are not Kent's mental model of the product and should not be root nouns unless the user is already in an advanced/admin surface.
- Review state and approval staleness are real product behavior, not implementation detail. The wireframe must preserve an explicit place where Kent can inspect and renew approval.
- Coverage is per modelo, not universal. The current `submission schemas` output shows export and verify support for `130` and `303` in `2024` and `2025`. The modelo matrix says `390` has schema, rules, and builder work but export remains pending. The wireframe must never imply parity that the registry does not actually ship.

### Command coverage expectations for the wireframe

The later ADR should assume the new language system must cover both what ships
today and what the roadmap says Kent must be able to do next.

#### Minimum command-family coverage

- Readiness and setup: setup, readiness check, auth status, explicit next-step guidance
- Obligations and awareness: deadlines, filing history/status, inbox/notifications, justificante/evidence lookup
- Data preparation: statement import or catalogue build, transaction classification, invoice linkage, per-category usage ratios, readiness dashboard
- Draft creation: draft build and validation for supported modelos and periods
- Review: queue, history, approval, stale-state inspection
- Export and verification: preflight, dry-run, export, verify, diff, supported-schema disclosure

#### Coverage truth the wireframe must preserve

- `docs/coverage/kent-capabilities.md` says Kent can already see which modelos apply and when, approve a draft, and use the review queue/history surfaces.
- `docs/coverage/pipeline.md` still shows T6 period close and casilla derivation as the load-bearing gap. The wireframe therefore needs a visible slot for preparation/readiness even if the underlying automation is still incomplete.
- `docs/coverage/modelos.md` shows the primary forms are `130`, `303`, and `390`, but only `130` and `303` are currently in the shipped export/verify schema registry.
- The roadmap milestone ladder still matters. Even where the shipped CLI has moved faster than the older milestone wording, the wireframe should reserve stable homes for install, awareness, data prep, review/approval, export, amendment, and later live history.

### Core wireframe design principles

- Kent-first beats subsystem-first.
- Stage-first beats storage-provider-first.
- Truthful availability beats placeholder breadth.
- Safe default path beats hidden dangerous branches.
- Review and approval are product stages, not incidental buttons.
- Export and verification remain explicit, visible concepts.
- Advanced/reference tools stay reachable but out of first-contact root navigation.
- Copy must survive plain terminal environments without Unicode rendering assumptions.

### Unresolved tensions and open questions for the ADR

- Should `workflow` remain a primary user-facing node, or should the Kent wireframe make the stage nodes primary and demote `workflow` to an advanced shortcut?
- Should `submission` continue to own `export` and `verify`, or does the live-submit excision justify renaming that cluster around artifact generation rather than submission?
- Should an advertised but dependency-blocked surface such as `status` be hidden, shown with explicit dependency notes, or replaced with a narrower live-history node until the backend is real?
- How much Spanish tax vocabulary should be first-class in navigation versus aliases or explanatory labels under English stage names?
- How should the wireframe surface per-modelo partial coverage without turning `--help` into a matrix dump?
- Where should advanced reference and provider namespaces live after Kent-root simplification: separate root cluster, `admin`, `reference`, or hidden expert mode?
- Should live-submission flags remain anywhere in the Kent-first default tree before milestone `1.0.0`, given the roadmap and default CLI excision policy?
- Is approval a top-level stage beside filing, or a substage inside filing with a persistent visible state summary?
