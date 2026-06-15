---
tags:
  - '#audit'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-14'
modified: '2026-06-14'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
  - '[[2026-06-04-aeat-cli-userdocs-hardening-adr]]'
  - '[[2026-06-10-aeat-cli-userdocs-hardening-audit]]'
---

# `aeat-cli-userdocs-hardening` audit: `userdocs backlog and decision steps resolution`

## Scope

Resolution pass over the six product-gap and decision steps the userdocs
hardening plan deferred for live-CLI assessment: `S11` (curated root-help
advertising decision) and the five backlog candidates `S20`, `S26`, `S32`,
`S37`, `S52`. Each was assessed against the live CLI and the source to decide
whether the operator need is already met (close as already-covered), genuinely
missing (record a backlog item with acceptance criteria), or a decision to make
and act on. The prior session audit flagged exactly this set as
backlog/decision candidates depending on the CLI surface.

## Findings

### S11 | DECISION (acted) | Curated help omitted journey-critical surfaces

The backend-authored curated help in `src/aeat/application/operator_surface/_help.py`
advertised `import` through `export` for the ledger and `list`/`describe`/`bindings`/`work`
for modelo, but omitted six real surfaces from `aeat app --help`: `ledger add`,
`ledger evidence`, `ledger doclink`, `ledger providers`, `modelo
verification-report`, and `modelo m036`. Decision: advertise the three
first-journey surgical surfaces and leave the evidence/provider power surfaces to
`aeat app ledger --help`. Acted on: added curated entries for `aeat app ledger
add`, `aeat app modelo verification-report list`, and `aeat app modelo m036`,
with locale keys authored through the locale CLI in all four catalogues
(`ledger_add`, `modelo_verification_report`, `modelo_m036`). Verified rendering
in `aeat --language en app --help`; locale scaffold, parity, and translation
honesty gates green.

### S20 | CLOSED already covered | Profile-driven applicability is answerable

`aeat app overview calendar --show-suppressed` enumerates applicable and
non-applicable modelos for the active profile with each verdict and reason, and
`aeat app overview explain MODELO` decomposes one modelo into its
registry-backed rationale plus the profile facts the decision depends on. The
"which enrolments apply, and why" need is met from the profile in plain language.

### S26 | CLOSED already covered | Ledger review surface is sufficient

`aeat app ledger status` (readiness rollup), `aeat app ledger review --filter
issue` (the actionable queue), and `aeat app ledger preflight --year --period`
(the per-field missing-facts report) together answer "what still needs review?"
plainly. No missing surface.

### S32 | BACKLOG | Discovery report exists; guided manual-value prompt does not

The discovery half is already answered: `aeat app modelo bindings list` shows a
per-binding `source` plus a plain-language `readiness` column (the
`_BINDING_SOURCE_TO_READINESS` mapping), and `--missing` filters to bindings
still owed, so users do not have to infer sources from raw ids. The residual gap
is a guided entry flow: `aeat app modelo work calculate` takes raw repeatable
`--casilla` and `--binding` flags with no interactive prompt. This is recorded
as a backlog item (acceptance criteria in Recommendations).

### S37 | CLOSED already covered | Verification findings carry a plain next action

`ModeloVerificationFinding` carries a typed `next_action` rendered across the
text, JSON, and notice transports. The values are operator-plain concrete
commands (for example a missing-casilla finding emits the exact `work calculate
... --casilla ...` to run; an unsupported-IVA finding names the `ledger attach`
step). `legal_refs`/`source_refs` ride alongside but never replace the plain
action.

### S52 | CLOSED already covered | Filing-history surface separates local vs AEAT state

`aeat app overview calendar`/`agenda`/`backlog` answer what is filed, what was
missed, and what remains due, and keep local state distinct from official AEAT
state: each row carries a separate `local_filing_state` and an
`aeat_submission_state` that defaults to `NOT_OBSERVED` until a real AEAT pull
populates it. The calendar therefore never implies official AEAT state it has not
observed.

## Verification gates and tooling (W07.P14)

- **S44 (conformance gate, process):** SATISFIED. `test_educational_docs_conformance.py`
  was run after every narrative docs change this campaign; green at 75/75 at close
  (up from 73 with the new live-data hub page).
- **S45 (generated CLI reference reconciliation):** SATISFIED. The live leaf count
  is 204 and the generated `docs/cli/index.rst` reads "all 204 leaf commands"; the
  historical 193-vs-188 discrepancy is resolved. `docs/cli/` is gitignored build
  output regenerated at build time, and the drift plus conformance gates
  (`dev/docs/tests/test_cli_reference_drift.py`,
  `test_cli_reference_conformance.py`) are green (6 passed). The leaf collector now
  lives at `dev.docs.cli_reference`, not the retired production `_doc_reference.py`.
- **S46 (Sphinx nitpicky build):** RUN; one campaign regression fixed, residual
  external blocker recorded. The build surfaced that the profile-setup rewrite had
  renamed the `What the active profile means` heading, breaking six cross-page
  anchor xrefs in `check-aeat-notifications.md`, `classify-with-llm.md`, and
  `filing-calendar.md`; the heading was restored to repair them. The residual
  build failures are outside the userdocs surface and owned by peer churn in the
  shared worktree: the first full build (before the regression fix) flagged a
  peer-owned production docstring warning
  (`aeat.core.external_constants.MODELO_720_REPORTING_THRESHOLD_EUR` py:class xref
  `bloque`, from config-refactor commit `8401ce4cf`) plus dependency `hoverxref`
  deprecation warnings; a confirmation re-run then failed at pytest collection on a
  peer circular import (`cannot import name CoreValidationError from partially
  initialized module aeat.core.errors`), triggered by an uncommitted peer edit to
  `src/aeat/core/hashing.py`. Both blockers are peer-owned `core` churn, not the
  userdocs surface. The campaign regression (the six broken anchor xrefs) is fixed
  and verified; the residual is recorded honestly per the step's allowance and the
  full-tree-gate-must-distinguish-owner rule.
- **S47 (dual review per page, process):** SATISFIED. Every new or rewritten page
  this campaign passed a live-CLI technical review and a zero-context editorial
  review before commit, per the `userdocs-pages-require-live-cli-technical-review`
  codification candidate.
- **S49 (autobuild/watch):** SATISFIED. `just docs-serve` already wraps
  sphinx-autobuild (`dev/docs/serve.py`) with live reload over `docs/` and
  `src/aeat/`, excluding self-generated output. No new recipe warranted.
- **S59 (relocate doc tooling out of production):** PARTIALLY SATISFIED, residual
  DEFERRED. The plan-named production generator `_doc_reference.py` is already
  relocated to `dev/docs/cli_reference.py`, and no `scripts/` path exists; the doc
  tooling lives under `dev/docs/`. The one residual is the `src/aeat/terminology/`
  package (plus its `_data/terminology/` authoring tree and tests), which is
  doc-generation tooling with zero production runtime importers but still resides in
  the production package. Relocating it is a distinct, high-risk multi-file atomic
  move (packaging, ~10 `dev/docs/` importers, the terminology CLI, and tree-wide
  conformance gates) governed by the relocation-atomicity rule. It is deferred as a
  standalone follow-up rather than bundled into this userdocs-prose campaign.
  **Update (2026-06-15):** the follow-up landed via the `docs-tooling-separation`
  feature (research + ADR + plan, option D1): the terminology package code and
  tests moved to `dev/docs/terminology_handbook/` (commit `d6250dcf5`), the
  authoring data stays shipped and is read via `bundled_path`, the gates and
  autodoc stubs were reconciled, and `W07.P14.S59` is now complete.

## Recommendations

- **S32 backlog acceptance criteria.** Deliver a guided manual-value entry flow
  (an interactive verb, or an `--interactive` mode on `work calculate`) that
  iterates the `bindings list --missing` set, shows each binding's plain
  `readiness`/`source` and casilla label, prompts for the value with type and
  format hints, validates at the boundary, and persists the same draft revision
  `work calculate` would. Acceptance: on a work unit with N missing non-constant
  bindings it prompts for exactly those N and produces an equivalent draft. The
  documentation already covers the discovery report and the honest first-filing
  zero pattern, so this backlog item is a UX surface, not a docs gap.
- **S11 follow-on (optional).** A future pass may also surface `ledger evidence`
  / `doclink` / `providers` in `aeat app ledger --help` prose; they remain
  reachable via the Typer help and are intentionally out of the first-journey
  curated set.

## Campaign-close honesty review

A fresh-context honesty review ran before declaring the campaign structurally
complete, per the campaign-close honesty-review discipline. Verdict: honestly
structurally complete, with `S59` legitimately deferred. The review independently
verified against source that the contested closures are substantive, not
assertion-dressing: `S22`/`S23` are honest section strengthenings of the canonical
pages (no duplicate stubs); `S11` is fully landed (`_help.py` entries plus the
three locale keys present with real translations across all four catalogues);
`S20`/`S26`/`S37`/`S52` each point at a real command surface that answers the
operator need (`overview --show-suppressed`, ledger `status`/`review`/`preflight`,
the typed finding `next_action`, and the separate `local_filing_state` vs
`aeat_submission_state`); `S32` is correctly scoped as a UX backlog, not a docs
gap; and the residual red full-tree gates are peer-owned `core` churn, not a gate
this campaign left red. A prose/Diataxis spot-read of profile-setup, the
read-live-aeat-data hub, and reconcile found no remaining over-claim or
type-mixing.

One INFO note surfaced, out of scope for this docs campaign: the codebase carries
two parallel reconciliation verdict taxonomies (the domain `ReconciliationStatus`
and the `application/modelo` `ModeloReconciliationVerdict`). reconcile.md
documents the correct one (the CLI verb's `ModeloReconciliationVerdict`), so the
docs are accurate, but the duplication is a candidate for the next semantic-overlap
structural audit swarm. No new verification-gated step is mandated; the review
surfaced no blocking item.

## Step-evidence convention

Per the plan-closure discipline, this campaign records step completion through its
per-step commits (each `docs(userdocs)` commit names the steps it closes and the
green conformance gate) plus this resolution audit and the prior
`2026-06-10-aeat-cli-userdocs-hardening-audit`, rather than one exec record per
step. This matches the convention the earlier waves used. `S59` is left unchecked
and deferred with its follow-up named here.

## Codification candidates

No finding meets the three durability criteria. S11 is a one-time curated-help
completion already enforced by the locale parity and honesty gates; the four
CLOSED items are confirmations of existing capability; the S32 backlog is a
single tracked UX follow-up. Nothing here generalises into a new cross-session
rule.
