---
tags:
  - '#adr'
  - '#docs-educational-surface'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - '[[2026-05-30-docs-architecture-adr]]'
  - '[[2026-05-30-docs-architecture-research]]'
  - '[[2026-05-30-docs-cli-conformance-adr]]'
  - '[[2026-06-01-docs-cli-buildtime-adr]]'
  - '[[2026-06-04-docs-educational-surface-research]]'
---

# `docs-educational-surface` adr: `educational surface: a Diataxis doc set with a single-source conformance contract` | (**status:** `accepted`)

## Problem Statement

The accepted documentation-architecture taxonomy defines three surfaces —
operator-facing localized CLI help (sourced from `tr()` locale keys),
contributor-facing English docstrings, and autodoc-generated API reference — and
explicitly *defers* a user-facing instructional surface. A prior narrative-docs
effort was reverted as over-build. The result: a new operator has no guided path
that teaches building, validating, verifying, and exporting a modelo. Docstrings
are correct but terse and contributor-scoped; CLI `--help` is reference-grade,
not instructional. This ADR sanctions the missing surface as a disciplined
Diataxis doc set, with a single-source contract that prevents the
redeclaration/localization drift and the relocation churn that make naive
documentation a liability, and a per-document production discipline that prevents
a second over-build.

## Considerations

- **Diataxis is binding.** The four documentation needs (Tutorial, How-to,
  Reference, Explanation) are kept strictly separate; mixing them — a how-to
  bloated with theory, a tutorial drifting into reference — is the cardinal
  failure mode. Reference already exists (autodoc). The gap is Tutorial,
  How-to, and Explanation.
- **Redeclaration is the central risk.** The same concept (what `modelo 303`
  does, what a flag means) can appear in CLI help, docstrings, and a tutorial and
  drift apart. The taxonomy already forbids docs reusing locale keys (deliberate
  operator/contributor separation); the educational surface must therefore not
  re-author flag/command help — it references the canonical CLI surface and the
  generated reference, and demonstrates *flows*, not flag tables.
- **Relocation churn.** The autodoc tree mirrors module paths 1:1 and a
  relocation campaign is in flight; any educational doc that names module paths
  rots on the next move. Educational docs reference stable CLI verbs
  (`aeat app modelo work`) and public concepts, never internal module paths.
- **Localization explosion.** Localizing the educational surface into four
  languages multiplies a drift surface the team already struggles to keep fresh.
  The existing narrative surface is English-only; the educational surface follows
  suit initially, deferring localization to a separate, later decision.
- **Quality is unenforceable by a machine.** Docstring/doc *presence* and shape
  are gated (`D100`/`D104`/`interrogate`/nitpicky roles), but instructional
  *readability* is not. A non-developer-persona prose review is the only
  instrument that judges whether a learner can actually follow the prose.

## Constraints

- No frontier risk; this is markdown narrative under `docs/` plus conformance
  tests, built on the existing Sphinx/autodoc + locale infrastructure.
- Educational docs MUST NOT reuse locale keys or re-author CLI help text (the
  docs-architecture constraint), and MUST remain compatible with the
  Sphinx build and the docs-cli-buildtime generated reference.
- Every command, verb, and example in an educational doc MUST resolve against the
  live CLI surface — enforced by a conformance gate, the same discipline the
  docs-cli-conformance and docs-cli-buildtime ADRs apply to the reference.
- The surface is incremental: it earns its place one document at a time through a
  production pipeline and a bound conformance gate, never as a sprawling
  hand-authored tree (the failure mode of the reverted effort).

## Implementation

The educational surface is a Diataxis doc set under the narrative `docs/`
surface, English-only initially:

- **Tutorial** — a single on-rails lesson taking a new operator through one
  modelo end to end (profile -> ledger import/classify/allocate ->
  `aeat app modelo work` -> `aeat app verify` -> export/borrador -> human files
  outside the app). One worked example, no decision points, no theory.
- **Explanation** — the build->validate->verify->export data-flow narrative, why
  the app never files (the safety/legal gate), and how every computed number
  carries legal-reference provenance.
- **How-to guides** — goal-oriented recipes for competent operators (quarterly
  IVA via modelo 303, an annual summary, a censo update), no scaffolded learning,
  no theory.

Each document is produced through the `vaultspec-documentation` skill pipeline in
full — wireframe, fresh-context refinement review, per-section context gathering,
isolated drafting, technical review against the codebase, and a zero-context
editorial prose review — never hand-authored. Documents reference the canonical
CLI surface and the generated reference rather than restating them.

A **single-source conformance gate** (sibling to the existing CLI-conformance
tests) parses the educational docs and asserts every referenced `aeat ...` verb
resolves to a live command and every fenced example invocation is shape-valid; it
fails when a doc names a retired/renamed verb. This makes redeclaration *visible*
(the gate reds on drift) rather than relying on author discipline, and makes the
surface relocation-resilient because it binds to verbs, not module paths.

Docstring instructional quality is a separate, standing track: a
non-developer-persona prose-readability review over user-facing docstrings,
producing audit findings actioned as targeted clarity fixes *within* contributor
scope (docstrings are not tutorialized — the educational surface carries that
load). Its cadence joins the swarm-audit rotation.

## Rationale

A disciplined Diataxis set fills the one deferred taxonomy slot without repeating
the over-build: each doc is pipeline-produced, prose-reviewed, and
conformance-gated, so the surface grows only as fast as it can be kept correct.
The single-source gate converts the redeclaration risk the team rightly fears
from an author-discipline problem (which drifts) into a tested invariant (which
reds on drift). English-only + verb-referencing keeps the localization and
relocation blast radius bounded. Reference stays autodoc; the educational surface
links to it rather than competing with it.

## Consequences

- New operators gain a guided path; the project stops relying on terse
  contributor docstrings to carry user instruction they were never scoped for.
- A new conformance gate must be authored and kept green; example invocations in
  docs become tested artifacts (a maintenance cost, but the cost that prevents
  rot).
- Localization is deliberately deferred — non-Spanish-reading operators get an
  English educational surface until a later localization decision; the CLI itself
  remains localized.
- The per-document pipeline is slower than hand-authoring, by design: it is the
  guard against the second over-build.
- Opens a path to localize the set later, and to fold docstring-quality findings
  into the same review discipline.

## Codification candidates

- **Rule slug:** `educational-docs-reference-not-redeclare`.
  **Rule:** User-facing educational docs reference the canonical CLI surface and
  generated reference (by stable verb, never module path) and never re-author
  flag/command help; every referenced verb and example invocation must resolve
  against the live CLI, enforced by a conformance gate.
- **Rule slug:** `educational-docs-are-pipeline-produced`.
  **Rule:** Every educational document is produced through the full
  `vaultspec-documentation` skill pipeline (wireframe -> fresh-context refinement
  -> context -> isolated drafting -> technical review -> zero-context editorial
  review), never hand-authored, so structure and prose each pass an independent
  gate.
