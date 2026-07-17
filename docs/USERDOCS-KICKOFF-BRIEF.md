# Userdocs initiative — kickoff brief

**Audience of this brief:** the agent (or session) that will drive the
user-facing documentation initiative for `aeat`.
**Status:** kickoff. Read fully, then **hold for the operator's instruction**
(see the final section) before authoring anything.

---

## 1. What `aeat` is

`aeat` is a local-first Python CLI that helps Spanish *autónomos* (self-employed
filers) and small businesses prepare tax filings for the Agencia Estatal de
Administración Tributaria (AEAT). It models the regulatory registry, ingests and
classifies financial transactions, computes the numbered boxes (*casillas*) of
each tax form (*modelo*), validates and verifies a draft, and exports a filing
artifact the operator submits themselves.

**It never files live.** The pipeline is build → validate → verify → export;
remote submission is a human step outside the app. Any userdoc must reflect this
— never imply the tool submits to AEAT.

The CLI has exactly two root command families:
- `aeat config` — profile, authentication, diagnostics.
- `aeat app` — ledger, modelo lifecycle, verify, borrador, live, etc.

The core operator journey is the modelo lifecycle:
`aeat app modelo work create → calculate → verify → file`, then
`aeat app modelo export`.

## 2. What documentation exists today (the starting point)

Three documentation surfaces (see the `docs-architecture` ADR; audiences are
deliberately separated):
1. **Operator-facing CLI help** — localized, sourced from `tr()` locale keys in
   `src/aeat/locales/{en,es,ca,hu}.yml`. Maintained via the `aeat.locales` CLI
   (`aeat-locales-cli` rule). **Userdocs must NOT reuse locale keys or
   re-author flag help** — different audience, single source.
2. **Contributor English docstrings** — feed the autodoc API reference; gated by
   interrogate + the nitpicky build. (A large docstring-hardening pass just
   landed; ~259 docstrings across ~48 modules.)
3. **Generated reference** — the API stub tree (`docs/api/`, via
   `python -m dev.docs.apidocs scaffold` — `aeat-docs-scaffolding-cli` rule) and the
   build-time CLI reference. Never hand-edited.

The **narrative user-facing set** (the focus of this initiative) lives under
`docs/` and is wired into `docs/index.rst`:
- `docs/tutorials/index.md` — one Tutorial: "Build your first modelo, start to
  finish" (currently Modelo 130 end-to-end; see constraint in §6).
- `docs/how-to/index.md` — a handful of How-to recipes (303 quarterly, annual
  390, censo, verify+export).
- `docs/explanation/index.md` — one Explanation of the pipeline + why it is
  human-gated + registry provenance.
- `docs/how-to/quickstart.md`, `docs/architecture.md`, `docs/authoring-guide.md`,
  root `README.md`.

A multi-lens review of this set (Diátaxis type-purity + newcomer clarity, two
independent reviewers per doc) is recorded in the audit
`.vault/audit/2026-06-02-docs-educational-surface-audit.md`. architecture and
README came back clean; the others were revised.

**Assessment: foundational but thin.** One page per Diátaxis type. The breadth
(more recipes, per-modelo coverage, more tutorials), depth (richer worked
examples, troubleshooting, conceptual coverage), and navigation (a real landing
/ index experience) are largely unbuilt. This is the underdeveloped domain.

## 3. Binding principles (non-negotiable)

- **Diátaxis is binding.** Every page is exactly one of Tutorial (learning,
  on-rails, no theory/options), How-to (goal-oriented for a competent user, no
  teaching), Reference (lookup; = the generated autodoc/CLI reference), or
  Explanation (understanding, no step-by-step). The cardinal sin is mixing
  types. Full rules: `.claude/skills/vaultspec-documentation/references/diataxis-rules.md`.
- **Single-source / relocation-resilient.** Reference stable CLI *verbs*, never
  internal module paths (the codebase is under active relocation). Never
  re-author flag help; link to the generated CLI/API reference. Do not reuse
  locale keys.
- **Agent-driven, multi-reviewed, prose-verified.** Do not hand-edit narrative
  prose. Produce each document through the documentation pipeline (wireframe →
  refinement → context → draft → technical review → editorial), and review every
  doc with at least two independent lenses (Diátaxis type-purity + a
  zero-context newcomer-clarity reviewer). Prose style:
  `.claude/skills/vaultspec-documentation/references/prose-style-rules.md`.
- **Ground every command against the live CLI.** Verify each `aeat ...` verb and
  flag by actually running that command's live `--help` output (or the command)
  before citing it. Never invent commands, flags, or outputs. The grounded-tutorial pass
  caught that Modelo 303 `calculate` is currently broken (§6) precisely because
  it ran the CLI.

## 4. Gates and tooling (how work is verified)

- **Conformance gate** — `src/aeat/entrypoints/cli/test_educational_docs_conformance.py`
  (`pytest -m "docs and domain_application"`, seconds): every `aeat ...` verb
  cited in `docs/{tutorials,explanation,how-to}` must resolve in the live CLI,
  and every relative link must resolve to a real file. Fast; run it on every
  prose change.
- **Nitpicky build** — `src/aeat/tests/test_docs_build.py` (the `-n -W` Sphinx
  build; perf-fixed to `dummy` builder + `-j auto`, ~4–7 min cold; an
  incremental build into a fixed output dir is ~1–2 min for iteration).
  NOTE: this gate is **transiently down fleet-wide** on a peer ErrorCode gap
  (see `.vault` task / §6) — but it covers autodoc; pure narrative `.md` edits
  are validated primarily by the conformance gate + myst rendering, and the
  full build re-confirms once peers unblock it.
- **Doc-skill assets** — the `vaultspec-documentation` skill and its
  `agents/{wireframe-agent.md, editorial-reviewer.md}` + `references/` personas.
- **The multi-agent review/draft workflow pattern** is proven: schema-free
  agents returning JSON in fenced blocks (the StructuredOutput tool is
  unreliable here), parsed tolerantly, fault-tolerant. Reuse it for fan-out
  review/drafting; the coordinator applies + commits serially.

## 5. How to work in this worktree

- **Shared multi-agent worktree.** Many concurrent campaigns hold uncommitted
  WIP. NEVER use destructive git (`stash`/`reset`/`checkout <path>`/`restore`/
  `clean`/`rebase`/`revert`/force-push). Before editing a file, `git diff -- <file>`
  and abort on non-authored WIP. Commit explicit-path only
  (`git commit -- <paths>`), never `git add -A`.
- **Atomic, gated commits.** One coherent change per commit; run the conformance
  gate (and, when available, the `-n -W` build) before committing.
- **The relevant ADRs/audit** to read first: `docs-educational-surface` ADR
  (`.vault/adr/2026-06-01-docs-educational-surface-adr.md`), the
  `docs-architecture` ADR, and the audit
  `.vault/audit/2026-06-02-docs-educational-surface-audit.md`.

## 6. Known constraints and live blockers

- **Modelo 303 `calculate` is currently broken** on this branch (`NameError:
  IvaRate` — the in-flight `iva/_invoice_classification` refactor). The tutorial
  was therefore grounded to Modelo 130. Do not write a 303 worked example until
  303 runs end-to-end via the CLI; re-check before relying on it.
- **The `-n -W` docs gate is transiently down** (peer `ModeloIvaWalletReconciliationBlockedError`
  missing an ErrorCode entry, crashing the CLI-reference build hook). Narrative
  prose work can still be conformance-gated; re-confirm under `-n -W` when it
  clears. Do not absorb the peer's incomplete change.
- **Markdown link discipline:** myst rejects empty/`#` targets and bare
  directory links (`../cli/`); link to a concrete file (`../cli/index.rst`).

## 7. Candidate scope (for the operator to prioritise — do NOT start yet)

Illustrative directions the userdocs initiative *could* take. The operator will
choose scope and priority:
- **Breadth of How-to recipes** — one per common operator goal/modelo (130, 303,
  390, 347, 349, 036/037 censo, OSS/IOSS, …), each a tight goal→steps recipe.
- **More Tutorials** — additional on-rails learning paths (e.g. annual cycle;
  importing real bank exports; the verify→export→file handoff) once their CLI
  paths are green.
- **Deeper Explanation** — registry authority & provenance, the casilla/binding/
  formula model, the safety/legal gating, the local-first design.
- **Onboarding & navigation** — install/bootstrap, a real docs landing page,
  cross-linking, a "choose your path" entry.
- **Troubleshooting / diagnostics** How-to (from `aeat config repair` / the
  diagnostics surface).
- **Audience/localisation** — docs are English-only today; whether/when to add a
  documentation translation matrix (must NOT reuse the runtime locale catalogues)
  is an open decision.

## 8. HOLD FOR INSTRUCTION

**Do not begin authoring or dispatching documentation work from this brief
alone.** This brief establishes context and the operating frame only.

Before any wireframe, draft, or commit, **STOP and present to the operator:**
1. a one-paragraph read-back of the current userdocs state and the biggest gaps
   you see;
2. a proposed prioritised scope (which documents, which audiences, breadth vs
   depth first) drawn from §7 — as options, not a fait accompli;
3. any clarifying questions (target reader, first deliverable, how many
   docs in the first wave).

Then **wait for the operator's explicit instruction** on scope and priority.
Proceed only on that instruction. The operator drives; this brief does not
authorise autonomous execution.
