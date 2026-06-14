---
tags:
  - '#plan'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-04'
modified: '2026-06-04'
tier: L3
related:
  - '[[2026-06-01-docs-educational-surface-adr]]'
  - '[[2026-06-02-docs-educational-surface-audit]]'
  - '[[2026-05-30-docs-architecture-adr]]'
  - '[[2026-06-01-docs-cli-buildtime-adr]]'
  - '[[2026-05-20-testimonial-driven-cli-verification-playbook-reference]]'
  - '[[2026-06-04-aeat-cli-userdocs-hardening-adr]]'
  - '[[2026-06-04-aeat-cli-userdocs-hardening-research]]'
---


# `aeat-cli-userdocs-hardening` `AEAT CLI user documentation handbook hardening` plan

## Wave `W01` - Audit and drift capture

Establish the source of truth before rewriting prose: live CLI help, generated reference, narrative docs, glossary, and reader-review findings.

### Phase `W01.P01` - Scope and corpus inventory

Define the documentation topic, audit surface, and rewrite scope, then inventory the existing corpus and the live command surface.

- [x] `W01.P01.S01` - Record the explicit topic, audience, audit surface, and rewrite scope for AEAT CLI user documentation hardening; `.vault/plan/2026-06-04-aeat-cli-userdocs-hardening-plan.md`.
- [x] `W01.P01.S02` - Inventory narrative docs by Diataxis type and map each page to the operator journey it currently supports; `docs/`.
- [x] `W01.P01.S03` - Compare generated CLI reference command count and paths with the live CLI leaf tree; `docs/cli/index.rst and src/aeat/entrypoints/cli/_doc_reference.py`.
- [x] `W01.P01.S04` - Capture runtime help-language anomalies where `--language en` does not render English help consistently, and distinguish runtime flags from `AEAT_OUTPUT_LANGUAGE` import-time pinning; `src/aeat/entrypoints/cli and src/aeat/locales`.

### Phase `W01.P02` - Reader review baseline

Run the documentation through non-developer and editorial lenses before choosing the first rewrite wave.

- [x] `W01.P02.S05` - Run a zero-context wireframe review on the proposed handbook corpus structure and revise type boundaries until it is understandable; `review artifacts`.
- [x] `W01.P02.S06` - Run non-technical operator reviews over setup, censo, ledger, modelo, verification, export, and troubleshooting pages; `review artifacts`.
- [x] `W01.P02.S07` - Produce a concise findings inventory separating prose gaps, navigation gaps, command drift, and missing product surfaces; `.vault/plan/2026-06-04-aeat-cli-userdocs-hardening-plan.md`.

## Wave `W02` - Handbook spine and navigation

Turn the rough documentation set into a linked handbook corpus, not one mixed mega-document. Each page keeps one Diataxis type and links out for other needs.

### Phase `W02.P03` - Landing and route map

Give readers a reliable place to start and choose their next page by task.

- [x] `W02.P03.S08` - Rewrite the userdocs landing route so non-technical readers can choose setup, ledger, modelo filing, troubleshooting, or reference without understanding the architecture first; `docs/index.md or docs/index.rst`.
- [x] `W02.P03.S09` - Add a short "where to ask for help" route covering the issue tracker, diagnostic outputs to include, and what not to paste publicly; `docs landing route`.
- [x] `W02.P03.S10` - Replace glossary-dependent routes with inline first-use definitions and search/reference-backed lookup surfaces; `do not make the monolithic glossary the primary explanation path for general readers; `docs navigation and future search/reference backlog`.
- [ ] `W02.P03.S11` - Decide whether curated root help should advertise handbook-critical surfaces omitted today: manual ledger add, evidence/doclink, verification reports, providers, and M036; `CLI root help backlog`.
- [ ] `W02.P03.S50` - Revise the rejected documentation index through the VaultSpec documentation pipeline and present only built canonical HTML for human review; `docs/index.md`.
- [x] `W02.P03.S51` - Normalize landing-page route labels, target document H1s, and document filenames so user-facing guide names do not diverge; `docs/index.md and linked user guides`.

### Phase `W02.P04` - Diataxis cleanup

Split pages that currently mix tutorials, recipes, explanation, and reference material.

- [x] `W02.P04.S12` - Split `docs/how-to/index.md` into an index plus focused recipes instead of a broad mixed reference-and-recipe page; `docs/how-to/index.md`.
- [x] `W02.P04.S13` - Remove conceptual detours from tutorial and how-to pages, replacing them with links to explanation and generated reference; `docs/tutorials and docs/how-to`.
- [x] `W02.P04.S14` - Convert reference-style command/flag restatement in narrative docs into stable links; `docs/cli/index.rst`.
- [x] `W02.P04.S55` - Audit and remove public handbook escape hatches where route pages or next-step blocks send general readers to a glossary, issue tracker, or backlog list instead of inline plain-language explanation, troubleshooting, or command reference; `docs/index.md, docs/getting-started.md, docs/how-to/index.md, docs/tutorials/index.md, and how-to next-step blocks`.
- [x] `W02.P04.S57` - Rewrite the generated CLI reference entry page through the full VaultSpec documentation pipeline so it acts as a navigation and root-behaviour page only: remove retired command cataloguing, move schema-registry internals out of the user-facing entry surface, avoid one-page subject conflation, and link to command-family, handbook, automation, and developer/tooling follow-up pages instead of embedding their content; `src/aeat/entrypoints/cli/_doc_reference.py and docs/cli/index.rst`.
- [x] `W02.P04.S58` - Gate any Mermaid or graph-based explanation before it appears on a user-facing entry page: the graph must be grounded in real top-level product architecture, mobile-first, visually constrained, scrollable when wider than the viewport, short enough to avoid long chains, and simple enough to reduce mental load rather than decorate the page; `docs visual explanation constraints`.

## Wave `W03` - Setup, profile, and enrolment guides

Make the first operator decision points plain: identity, taxpayer type, censo facts, activity, IVA regime, and which facts affect modelo applicability.

### Phase `W03.P05` - Profile facts

Help a user create a complete profile without turning profile setup into a flag catalogue.

- [x] `W03.P05.S15` - Rewrite the profile setup guide around choices a user recognizes: DNI for Spanish citizens, NIE for foreign individuals, NIF/CIF for tax identifiers, name fields, taxpayer type, activity, postcode, IRPF category, IVA regime, and output language; `docs/how-to/profile-setup.md`.
- [x] `W03.P05.S16` - Add a "check your profile facts before calculating" recipe using `aeat config profile status`, `show`, `validate`, and `preflight`; `profile how-to docs`.
- [x] `W03.P05.S17` - Document how wrong or missing profile facts affect modelo applicability without restating every profile flag; `profile how-to docs`.
- [x] `W03.P05.S53` - Normalize DNI, NIE, NIF, and CIF terminology across user-facing docs and profile tax-id CLI help so Spanish citizens are not routed toward NIE-first language; `docs/ and src/aeat/locales`.

### Phase `W03.P06` - Censo and enrolment

Separate AEAT census facts from ordinary local profile editing.

- [x] `W03.P06.S18` - Create a standalone censo/enrolment how-to for config profile censo refresh, show, compare, and apply, including authenticated read-only AEAT access, local snapshot review, apply-only-after-review guidance, post-apply profile validation, and handoff to calendar or ledger setup; `censo how-to docs`.
- [x] `W03.P06.S19` - Create a standalone Modelo 036 lifecycle how-to for `app modelo m036 alta`, `modificacion`, and `baja`, clearly stating these record declarations filed at sede and do not file remotely; `M036 how-to docs`.
- [ ] `W03.P06.S20` - Backlog any missing "what enrolments do I need?" product surface if the CLI cannot answer it from the active profile in plain language; `product backlog`.

## Wave `W04` - Ledger operation guides

Make the ledger usable before modelo calculation: import, manual entry, evidence, classification, allocation, correction, and readiness.

### Phase `W04.P07` - Ledger readiness

Turn ledger import into a complete "make the ledger tax-ready" path.

- [x] `W04.P07.S21` - Expand the bank-import guide with the full loop: import, list, view, classify, allocate, fix, preflight, and status; `docs/how-to/import-bank-statements.md`.
- [x] `W04.P07.S22` - Add a manual transaction guide for `aeat app ledger add`, including date, amount, direction, category, IVA fields, source jurisdiction, and evidence ids; `ledger how-to docs`.
- [x] `W04.P07.S23` - Add a mixed-use allocation guide that explains business percentage and usage ratios in operator language; `ledger how-to docs`.

### Phase `W04.P08` - Evidence and correction

Document how paper and PDF evidence connects to ledger rows.

- [x] `W04.P08.S24` - Add a purchase-invoice evidence guide for `ledger evidence add/list/view/update/remove` and `ledger attach`; `ledger evidence docs`.
- [x] `W04.P08.S25` - Add a correction guide for `ledger update`, `remove`, `merge`, `split`, `stash`, and `history`, focused on safe operator workflows; `ledger correction docs`.
- [ ] `W04.P08.S26` - Backlog any missing ledger "what still needs review?" surface if existing `ledger review`, `status`, and `preflight` cannot answer it plainly; `product backlog`.

## Wave `W05` - Modelo lifecycle and manual inputs

Make the filing path readable from modelo selection through calculation, including the manual values the application cannot infer.

### Phase `W05.P09` - Modelo lifecycle

Separate the repeated lifecycle from per-modelo recipes.

- [x] `W05.P09.S27` - Create a stable lifecycle how-to for `work create`, `calculate`, `verify`, optional internal `file`, and `export`, with the work-unit id vs calculation-revision id distinction; `modelo lifecycle docs`.
- [x] `W05.P09.S28` - Fix output-file naming consistency across getting-started, quickstart, tutorial, and recipes so the final artifact is not described as `.xml` in one place and fichero-BOE text elsewhere; `narrative docs`.
- [x] `W05.P09.S29` - Add a "which modelo should I file?" guide using `overview explain`, `overview calendar`, `overview agenda`, `modelo list`, and `modelo describe`; `modelo selection docs`.
- [ ] `W05.P09.S52` - Backlog a plain tax-year filing-history surface that can answer what has been filed, what was missed, and what remains due without implying overview calendar has official AEAT state; `product backlog`.
- [x] `W05.P09.S56` - Rewrite modelo lifecycle prose so general readers first see the filing task in plain language, with work units, calculation revisions, registry revisions, selectors, checksums, and exact IDs introduced only as advanced details after the export and manual AEAT handoff are clear; `docs/getting-started.md, docs/how-to/quickstart.md, docs/how-to/filing-spine.md, docs/how-to/modelo-303.md, docs/how-to/modelo-390.md, docs/tutorials/index.md`.

### Phase `W05.P10` - Casillas and bindings

Give missing values their own operational guide.

- [ ] `W05.P10.S30` - Create a focused guide for entering missing `--casilla` values: how to list casillas, identify the printed box, enter a value, and avoid guessing; `manual values docs`.
- [ ] `W05.P10.S31` - Create a focused guide for entering missing `--binding` values: how to run `bindings list --missing`, distinguish profile, ledger, prior-period, relation, and manual values, and record first-filing zeroes honestly; `manual values docs`.
- [ ] `W05.P10.S32` - Backlog a natural manual-value product surface if users must infer binding/casilla sources from raw ids rather than a guided prompt or report; `product backlog`.
- [ ] `W05.P10.S33` - Document relation rows and typed `--row` inputs for multi-record modelos only after confirming the live CLI examples and output are stable; `manual values docs`.

## Wave `W06` - Verification, export, filing handoff, and reconciliation

Make the final boundary impossible to misread: the app verifies locally, exports locally, the human files at AEAT, then reconciles with evidence.

### Phase `W06.P11` - Verification reports

Make verification failures actionable.

- [x] `W06.P11.S34` - Create a verification-report guide for `modelo work verify`, `verification-report list`, and `verification-report view`; `verification docs`.
- [x] `W06.P11.S35` - Add symptom-first advice for incomplete, blocked, no exportable revision, deadline passed, and id mix-up failures; `verification docs`.
- [x] `W06.P11.S36` - Fix or backlog the invalid verification-report next-action path if it is user-visible: `aeat app modelo work verification-report list` should route to the live `aeat app modelo verification-report list/view` surface; `CLI next-action backlog`.
- [ ] `W06.P11.S37` - Backlog any missing "plain next action" product surface for verification findings that only expose internal ids or registry terms; `product backlog`.

### Phase `W06.P12` - Export and manual filing

Write the final handoff checklist.

- [x] `W06.P12.S38` - Create a verify-export-upload-record-reconcile checklist: verify result, export path, checksum or file identity, upload manually in the AEAT portal, save justificante, record the local filed marker only after real upload, then reconcile; `filing handoff docs`.
- [ ] `W06.P12.S39` - Rewrite `work file` language in userdocs so "filed" always reads as an internal state, never remote submission; `filing handoff docs`.
- [ ] `W06.P12.S40` - Expand the reconciliation guide with what to do when casillas diverge and what evidence to keep; `reconciliation docs`.

## Wave `W07` - Troubleshooting, live-read, and gates

Make help practical when something refuses, and keep the corpus from drifting again.

### Phase `W07.P13` - Troubleshooting and live reads

Move from subsystem diagnostics to symptoms a user recognizes.

- [x] `W07.P13.S41` - Rewrite troubleshooting around symptoms: no active profile, wrong profile, ledger not ready, missing binding, wrong period token, no exportable revision, deadline passed, localization mismatch, and live-read gate closed; `troubleshooting docs`.
- [ ] `W07.P13.S42` - Add a read-only live-data guide for app live and censo surfaces, emphasizing configured AEAT authentication, zero live-write capability, local-only application of downloaded facts, and that AEAT_LIVE_TESTS_ENABLED is test/developer wording rather than an operator switch; `live-read docs`.
- [x] `W07.P13.S43` - Add a privacy-safe support checklist naming command outputs and logs to include without exposing tax ids or personal data; `support docs`.

### Phase `W07.P14` - Verification gates

Make documentation quality enforceable where machines can help and reviewed where they cannot.

- [ ] `W07.P14.S44` - Run `src/aeat/entrypoints/cli/test_educational_docs_conformance.py` after every narrative docs change; `docs conformance gate`.
- [ ] `W07.P14.S45` - Regenerate or check the generated CLI reference after CLI tree changes and reconcile the observed 193 live leaves versus the stale 188-leaf generated index; `generated reference gate`.
- [ ] `W07.P14.S46` - Run the Sphinx nitpicky docs build when the shared gate is available, or record the external blocker honestly; `docs build gate`.
- [ ] `W07.P14.S47` - Require a technical review against live CLI help and a zero-context editorial/non-technical review before marking each handbook page complete; `review gates`.
- [x] `W07.P14.S48` - Implement a real single-source-page docs build that writes the requested page into the canonical HTML build output without rebuilding generated API/autodoc surfaces or producing a separate preview artifact; `docs build tooling`.
- [ ] `W07.P14.S49` - Evaluate and implement an autobuild server or watch recipe for canonical docs page rebuilds after the single-page build path is stable; `docs build tooling`.
- [x] `W07.P14.S54` - Run a corpus terminology sweep for identity and tax-identifier wording after each profile, censo, or authentication docs edit: DNI for Spanish citizens, NIE for foreign individuals, NIF/CIF for tax identifiers and legal entities, and DNI/NIE only where Cl@ve identity specifically requires it; `docs/ and src/aeat/locales`.
- [ ] `W07.P14.S59` - Move documentation generators, build helpers, and documentation verifier tests out of production package code and unsupported `scripts/` paths into supported `docs/tools/` tooling; update Sphinx hooks, just recipes, and generated API stubs so production code does not own documentation generation responsibilities; `docs/tools, docs/conf.py, justfile, docs/api, and docs verifier tests`.

## Description

This plan hardens the AEAT CLI user documentation into a linked quick-reference handbook corpus for non-technical operators and tax-adjacent users. It does not author one mixed handbook page. It coordinates a Diataxis-separated set of pages: tutorials for learning, how-to guides for task execution, explanation pages for mental models, and generated reference for lookup. The reader should be able to set up a profile, record or apply censo facts, prepare the ledger, calculate a modelo, enter manual casilla and binding values when needed, verify the draft, export a fichero-BOE artifact, file manually at AEAT, and reconcile the justificante afterward.

The audit surface is the complete operator CLI documentation path: live localized `aeat --help` output, generated `docs/cli/*.rst`, narrative docs under `docs/tutorials`, `docs/how-to`, `docs/explanation`, `docs/getting-started.md`, and `docs/glossary.md`, plus the conformance gates that keep command examples tied to the live CLI. The rewrite scope is user-facing prose and navigation first. Product gaps discovered during prose review are logged as backlog items rather than hidden by confident prose.

The first review wave already surfaced the main readability risks. A zero-context wireframe reviewer understood the documentation goal but flagged that "quick-reference handbook" could blend Diataxis types unless the corpus is explicitly linked instead of merged. A non-technical reader found that the first-time path skips ledger readiness, profile choices lack plain-language support, censo is buried, ledger operation stops too early, casilla and binding inputs are scattered, export/file/upload language remains easy to confuse, output file extensions conflict, and troubleshooting starts from internals rather than user symptoms.

Several technical drifts are known at plan authoring time. `collect_live_leaf_paths_in_subprocess()` reports 193 live leaf commands, while the pre-generation `docs/cli/index.rst` said 188 and omitted newly visible surfaces: `ledger.doclink`, `ledger.providers`, `modelo.m036.alta`, `modelo.m036.modificacion`, and `modelo.m036.baja`. Running `generate_cli_reference_in_subprocess(Path('docs').resolve())` locally refreshes the ignored generated reference to 193 leaves and includes the five missing surfaces, but `docs/cli/` is gitignored and not tracked in HEAD, so a durable mitigation must decide whether generated CLI reference output remains ignored build output or becomes a checked artifact. `uv run aeat --language en config profile create --help` still rendered Spanish help in this environment, while `modelo work calculate` and other app surfaces rendered English; a separate explorer observed that `AEAT_OUTPUT_LANGUAGE=en` before import renders English for affected censo help where runtime `--language en` does not. The verification-report next-action string may also point at `aeat app modelo work verification-report list`, while the live command is `aeat app modelo verification-report list`. These are documentation trust problems as much as implementation problems: users cannot rely on examples if generated reference, runtime help, and next-action guidance disagree.

## Parallelization

W01 can run as three parallel audits: command/reference drift, narrative Diataxis mapping, and non-technical reader review. W02 should follow W01 because the landing and route map depend on the audited page inventory. W03 through W06 can then proceed as separate page families with disjoint write scopes: profile/censo, ledger, modelo/manual inputs, and verification/export. W07 gate work should run continuously after each page family, with conformance and CLI-help checks local to the touched pages.

Each new or rewritten page should use the `vaultspec-documentation` pipeline as a single-document unit: wireframe, zero-context refinement, context gathering, isolated drafting, technical review, editorial review, and final approval. Non-technical operator review is mandatory for profile, censo, ledger, manual value entry, verification, and troubleshooting pages because those are the places where implementation vocabulary most easily leaks into user instructions.

## Verification

Run the fast narrative conformance gate after every docs change:

```text
uv run pytest src/aeat/entrypoints/cli/test_educational_docs_conformance.py
```

Run generated-reference drift checks when CLI surfaces change or when a plan step touches command examples:

```text
uv run python -m aeat.apidocs scaffold --check
uv run python -c "from aeat.entrypoints.cli._doc_reference import collect_live_leaf_paths_in_subprocess; print(len(collect_live_leaf_paths_in_subprocess()))"
```

Run the Sphinx gate when available, and record any external blocker rather than claiming it passed:

```text
uv run pytest src/aeat/tests/test_docs_build.py
```

For each page, also verify representative command help directly with the live CLI in the documented language, usually with `uv run aeat --language en ... --help`. If `--language en` does not produce English for a surface, log it as a CLI/localization backlog item and avoid pretending the runtime output matches the generated English reference.

`vaultspec-core` was not available on PATH while this plan was authored, so the Wave/Phase/Step structure was written directly instead of through `vaultspec-core vault plan ...` commands. Future structural edits should use the plan-editing CLI if it is available, then restore prose last per `vaultspec-plan-editing-discipline`.
